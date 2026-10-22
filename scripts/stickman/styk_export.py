"""StykAnimate native export — writes `.styk` project containers.

The container and document schema follow the reverse-engineered native
format (docs/native-file-format.md + src/pivot/model.mjs):

* Container v1: 56-byte header — magic 'STYK'/'STKZ', version 1, compression
  method 1 (zlib DEFLATE), u16 reserved 0, u64 LE uncompressed length,
  u64 LE compressed length, SHA-256 of the uncompressed payload, then the
  zlib-compressed UTF-8 JSON document. Plain JSON `.styk`/`.json` is also
  readable by the app, so both writers are provided.
* Document: decoded Pivot scene (version 5) with figure_types (segment
  trees), keyframes (objects with ABSOLUTE per-segment angles, in ticks at
  `fps`), backgrounds (solid / linear gradient) and per-frame cameras.
* Camera mapping: native focus = canvas_centre + (camera.x, camera.y) and
  native scale is RECIPROCAL of zoom, so this exporter converts from the
  engine's (focus, zoom, angle) model.

What exports faithfully: every actor pose per frame, camera travel, prop
geometry (boxes, platforms, balls, trees, hurdles as line/circle figures),
background colour/gradient, figure opacity. What stays MP4-only: weather,
hills/clouds/sun art, text overlays and scene fades.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
import zlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .animation import Actor
from .camera import CameraTrack
from .environment import Environment, Prop, hex_rgb, prop_transform
from .renderer import Scene, SceneRenderer
from .rig import Rig


def f32(x: float) -> float:
    """Round to float32 precision (native validates f32 representability)."""
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def _argb_u32(rgb: Tuple[int, int, int], alpha: int = 255) -> int:
    r, g, b = (int(c) & 255 for c in rgb)
    return ((alpha & 255) << 24) | (r << 16) | (g << 8) | b


# ------------------------------------------------------------------- rig -> type

def rig_to_figure_type(rig: Rig, type_id: int) -> dict:
    segs = []
    for s in rig.segments:
        prim = 3 if s.primitive == "circle" else 0
        kind = "circleFill" if (s.primitive == "circle" and s.circle_fill) else (
            "circle" if s.primitive == "circle" else "line")
        segs.append({
            "segment_id": s.segment_id,
            "parent_id": s.parent_id,
            "length": f32(s.length),
            "angle_rad": f32(s.angle_rad),
            "thickness": f32(s.thickness),
            "bend_rad": f32(0.0),
            "primitive_code": prim,
            "aux_code": 0,
            "flags": 0,
            "segment_type": "circle" if s.primitive == "circle" else "line",
            "segment_kind": kind,
            "color_rgb": [int(c) & 255 for c in s.color],
            "transparency": 0,
            "visible": True,
            "z_order": s.z_order,
            "name": s.name,
        })
    return {
        "figure_type_id": type_id,
        "name": getattr(rig, "name", "figure").title(),
        "segment_count": len(segs),
        "segments": segs,
        "polyfills": [],
        "image_assets": [],
        "text_assets": [],
        "_styk": {"colorMode": "segments"},
    }


# ------------------------------------------------------------------ prop figures

def prop_to_segments(p: Prop, ground_y: float) -> Optional[List[dict]]:
    """Convert simple props into line/circle segment chains (Pivot artwork)."""
    x, y = p.x, (p.y if p.y is not None else ground_y)
    s = p.size
    col = list(hex_rgb(p.color) if p.color else (150, 110, 70))
    sid = [1]

    def seg(parent, length, angle, thickness, z, name, prim=0, kind="line"):
        d = {
            "segment_id": sid[0], "parent_id": parent,
            "length": f32(length), "angle_rad": f32(angle),
            "thickness": f32(thickness), "bend_rad": f32(0.0),
            "primitive_code": prim, "aux_code": 0, "flags": 0,
            "segment_type": "circle" if prim == 3 else "line",
            "segment_kind": kind, "color_rgb": col, "transparency": 0,
            "visible": True, "z_order": z, "name": name,
        }
        sid[0] += 1
        return d

    H = s * 0.55 if p.kind == "platform" else s
    if p.kind in ("box", "platform", "crash_mat"):
        w = s * 1.4 if p.kind == "crash_mat" else s
        return [
            seg(0, w, 0.0, 8, 1, "top"),
            seg(sid[0] - 1, H, math.pi / 2, 8, 2, "right"),
            seg(sid[0] - 1, w, math.pi, 8, 3, "bottom"),
            seg(sid[0] - 1, H, -math.pi / 2, 8, 4, "left"),
        ]
    if p.kind == "ball":
        return [seg(0, s, -math.pi / 2, 0, 1, "ball", prim=3, kind="circleFill")]
    if p.kind == "tree":
        return [
            seg(0, s * 0.65, -math.pi / 2, 14, 1, "trunk"),
            seg(sid[0] - 1, s * 0.62, -math.pi / 2, 0, 2, "crown", prim=3, kind="circleFill"),
        ]
    if p.kind == "hurdle":
        top = y - s * 0.6
        return [
            seg(0, s * 0.8, 0.0, 8, 1, "bar"),
        ]
    return None


def prop_root(p: Prop, ground_y: float) -> Tuple[float, float]:
    """World anchor for a prop figure (top-left of the chain start)."""
    s = p.size
    if p.kind in ("box", "platform", "crash_mat"):
        w = s * 1.4 if p.kind == "crash_mat" else s
        return (p.x - w / 2, (p.y if p.y is not None else ground_y) - (s * 0.55 if p.kind == "platform" else s))
    if p.kind == "ball":
        c = (p.y if p.y is not None else ground_y) - s / 2
        return (p.x - s / 2, c - s / 2 + s / 2)
    if p.kind == "tree":
        return (p.x, (p.y if p.y is not None else ground_y))
    return (p.x, (p.y if p.y is not None else ground_y))


# ------------------------------------------------------------------- exporter

@dataclass
class StykExportOptions:
    fps: int = 30
    canvas_width: int = 1920
    canvas_height: int = 1080
    include_props: bool = True


def build_document(scene: Scene, renderer: SceneRenderer,
                   opts: Optional[StykExportOptions] = None) -> dict:
    opts = opts or StykExportOptions()
    env = scene.environment or Environment.from_dict({})
    ground_y = env.ground.y

    # ---- figure types: props first (behind actors), then actors
    figure_types: List[dict] = []
    entries: List[dict] = []      # {type_id, actor|prop, draw info}
    next_type = 1
    if opts.include_props:
        for p in env.props:
            segs = prop_to_segments(p, ground_y)
            if not segs:
                continue
            ft = {"figure_type_id": next_type, "name": p.kind.title(),
                  "segment_count": len(segs), "segments": segs,
                  "polyfills": [], "image_assets": [], "text_assets": [],
                  "_styk": {"colorMode": "segments"}}
            figure_types.append(ft)
            entries.append({"type": "prop", "type_id": next_type, "prop": p})
            next_type += 1
    for actor in scene.actors:
        ft = rig_to_figure_type(actor.rig, next_type)
        figure_types.append(ft)
        entries.append({"type": "actor", "type_id": next_type, "actor": actor})
        next_type += 1

    # ---- background
    sky = env.spec.get("sky", ["#ffffff", "#ffffff"])
    bg_id = 1
    if len(sky) >= 2:
        background = {
            "background_id": bg_id, "kind": 3,
            "color_a": _argb_u32(hex_rgb(sky[0])),
            "color_b": _argb_u32(hex_rgb(sky[-1])),
            "x1": f32(opts.canvas_width / 2), "y1": f32(0.0),
            "x2": f32(opts.canvas_width / 2), "y2": f32(opts.canvas_height),
        }
    else:
        background = {"background_id": bg_id, "kind": 2,
                      "color": _argb_u32(hex_rgb(sky[0]))}

    # ---- keyframes: one per rendered frame (lossless, holds at the end)
    n_frames = max(1, int(round(scene.duration * opts.fps)))
    keyframes = []
    uid = 1
    for i in range(n_frames):
        t = i / opts.fps
        objects = []
        order = []
        for slot, entry in enumerate(entries):
            if entry["type"] == "actor":
                a: Actor = entry["actor"]
                kf = a.timeline.sample(t)
                angles = [f32(kf.pose.get(s.name, s.angle_rad)) for s in a.rig.segments]
                transparency = int(round((1.0 - max(0.0, min(1.0, kf.opacity))) * 255))
                objects.append({
                    "object_slot": slot, "unique_id": uid,
                    "figure_type_id": entry["type_id"],
                    "root_x": f32(kf.x), "root_y": f32(kf.y),
                    "scale": f32(kf.scale if kf.scale > 0 else 1.0),
                    "color_override_raw": 0, "field28": transparency,
                    "angles": angles,
                    "len_flag": 0, "lengths": [], "bend_flag": 0, "bends": [],
                    "join": None,
                })
            else:
                p: Prop = entry["prop"]
                rx, ry = prop_root(p, ground_y)
                if p.motion:
                    px, py = prop_transform(p, t, ground_y)
                    base_x, base_y = prop_root(p, ground_y)
                    rx, ry = rx + (px - p.x), ry
                segs = figure_types[entry["type_id"] - 1]["segments"]
                angles = [f32(s["angle_rad"]) for s in segs]
                objects.append({
                    "object_slot": slot, "unique_id": uid,
                    "figure_type_id": entry["type_id"],
                    "root_x": f32(rx), "root_y": f32(ry), "scale": f32(1.0),
                    "color_override_raw": 0, "field28": 0,
                    "angles": angles,
                    "len_flag": 0, "lengths": [], "bend_flag": 0, "bends": [],
                    "join": None,
                })
            order.append(slot)
            uid += 1
        cam = scene.camera.sample(t, actor_pos=renderer.actor_pos)
        native_cam = {
            "x": f32(cam["x"] - opts.canvas_width / 2),
            "y": f32(cam["y"] - opts.canvas_height / 2),
            "scale": f32(1.0 / max(1e-6, cam["zoom"])),
            "angle_rad": f32(cam["angle"]),
            "is_default": False,
        }
        keyframes.append({
            "objects": objects,
            "duration_raw": 1,
            "background_id": bg_id,
            "camera": native_cam,
            "object_draw_order": order,
        })

    # palette from figure colors
    colors: List[str] = []
    for ft in figure_types:
        for s in ft["segments"]:
            c = "#{:02x}{:02x}{:02x}".format(*s["color_rgb"])
            if c not in colors and len(colors) < 64:
                colors.append(c)

    return {
        "version": 5,
        "canvas_width": opts.canvas_width,
        "canvas_height": opts.canvas_height,
        "fps": opts.fps,
        "figure_types": figure_types,
        "keyframes": keyframes,
        "backgrounds": [background],
        "_styk": {"palette": {"version": 1, "colors": colors}},
    }


def build_figure_document(rig: Rig, pose: Dict[str, float], root_x: float,
                          root_y: float, scale: float = 1.0) -> dict:
    """A `.stkz`-style single-figure document with one evaluated pose."""
    ft = rig_to_figure_type(rig, 1)
    angles = [f32(pose.get(s.name, s.angle_rad)) for s in rig.segments]
    return {
        "version": 5,
        "canvas_width": 640, "canvas_height": 480, "fps": 30,
        "figure_types": [ft],
        "keyframes": [{
            "objects": [{
                "object_slot": 0, "unique_id": 1, "figure_type_id": 1,
                "root_x": f32(root_x), "root_y": f32(root_y),
                "scale": f32(scale), "color_override_raw": 0, "field28": 0,
                "angles": angles, "len_flag": 0, "lengths": [],
                "bend_flag": 0, "bends": [], "join": None,
            }],
            "duration_raw": 1,
            "background_id": 0,
            "camera": {"x": 0, "y": 0, "scale": 1, "angle_rad": 0, "is_default": True},
            "object_draw_order": [0],
        }],
        "backgrounds": [],
        "_styk": {"palette": {"version": 1, "colors": [
            "#{:02x}{:02x}{:02x}".format(*s["color_rgb"]) for s in rig.segments[:8]
        ]}},
    }


# ------------------------------------------------------------------ container

def write_container(document: dict, path: str, magic: str = "STYK",
                    compress: bool = True) -> str:
    """Write a native v1 container (zlib DEFLATE, SHA-256) or plain JSON."""
    payload = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if not compress:
        with open(path, "wb") as f:
            f.write(payload)
        return path
    assert magic in ("STYK", "STKZ"), "magic must be STYK or STKZ"
    compressed = zlib.compress(payload, 6)
    digest = hashlib.sha256(payload).digest()
    header = bytearray(56)
    header[0:4] = magic.encode("ascii")
    header[4] = 1                      # container version
    header[5] = 1                      # compression: zlib-wrapped DEFLATE
    header[6:8] = struct.pack("<H", 0)  # reserved flags
    header[8:16] = struct.pack("<Q", len(payload))
    header[16:24] = struct.pack("<Q", len(compressed))
    header[24:56] = digest
    with open(path, "wb") as f:
        f.write(bytes(header))
        f.write(compressed)
    return path


def read_container(path: str) -> dict:
    """Read back a native container (for round-trip verification)."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] in (b"STYK", b"STKZ"):
        version, method = data[4], data[5]
        if version != 1 or method != 1:
            raise ValueError(f"Unsupported container version {version}/method {method}")
        ulen, clen = struct.unpack("<QQ", data[8:24])
        digest = data[24:56]
        payload = zlib.decompress(data[56:56 + clen])
        assert len(payload) == ulen, "length mismatch"
        assert hashlib.sha256(payload).digest() == digest, "checksum mismatch"
        return json.loads(payload.decode("utf-8"))
    return json.loads(data.decode("utf-8"))
