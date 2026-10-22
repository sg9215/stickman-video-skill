"""Video plan — schema validation and compilation into renderable Scenes.

The plan is a single JSON document the AI agent authors after the planning
phase. Structure::

    {
      "title": "...",
      "meta":   {"resolution": [1920,1080], "fps": 30},
      "actors" (global style defaults, optional),
      "scenes": [
        {
          "name": "...", "duration": 10,
          "environment": {"preset": "outdoor_day", "ground": {...},
                          "props": [...], "weather": "rain"},
          "actors": [{"id": "hero", "rig": "blue", "start": [300, null],
                      "style": {...}, "performance": [
                        {"action": "walk", "params": {"distance": 240}},
                        {"action": "pose", "params": {"pose": "cheer"}}]}],
          "camera": {"keys": [...], "motion": [...]},       # optional = auto
          "text": [...], "fade_in": 0.4, "fade_out": 0.4
        }
      ],
      "output": {"mp4": true, "styk": true, "preview_times": [...],
                 "audio": null, "crf": 18}
    }

Validation is strict and every error names the JSON path — agents can
self-correct from the message alone.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import poses as P
from .actions import ACTIONS, Performance
from .animation import Actor, Keyframe
from .camera import CameraTrack
from .environment import ENV_PRESETS, Environment, GroundSpec, PROP_KINDS, hex_rgb
from .renderer import Scene
from .rig import RigStyle, RIG_PRESETS, default_rig
from .textover import TextElement


class PlanError(ValueError):
    pass


def _err(path: str, msg: str):
    raise PlanError(f"{path}: {msg}")


def _num(path, v, lo=None, hi=None, default=None):
    if v is None:
        if default is None:
            _err(path, "required")
        return default
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
        _err(path, f"must be a finite number, got {v!r}")
    if lo is not None and v < lo:
        _err(path, f"must be >= {lo}, got {v}")
    if hi is not None and v > hi:
        _err(path, f"must be <= {hi}, got {v}")
    return float(v)


def _str(path, v, default=None, choices=None):
    if v is None:
        if default is None:
            _err(path, "required")
        return default
    if not isinstance(v, str):
        _err(path, f"must be a string, got {v!r}")
    if choices and v not in choices:
        _err(path, f"must be one of {sorted(choices)}, got {v!r}")
    return v


def _list(path, v, default=None):
    if v is None:
        return list(default) if default is not None else _err(path, "required")
    if not isinstance(v, list):
        _err(path, f"must be a list, got {type(v).__name__}")
    return v


def _dict(path, v, default=None):
    if v is None:
        return dict(default or {})
    if not isinstance(v, dict):
        _err(path, f"must be an object, got {type(v).__name__}")
    return v


# ------------------------------------------------------------------ validation

def validate_plan(plan: dict) -> dict:
    """Validate the whole plan; returns it normalized. Raises PlanError."""
    plan = _dict("plan", plan)
    _str("plan.title", plan.get("title"), default="Untitled")

    meta = _dict("plan.meta", plan.get("meta"), default={})
    res = _list("plan.meta.resolution", meta.get("resolution"), default=[1920, 1080])
    if len(res) != 2 or not all(isinstance(r, int) and 240 <= r <= 4096 for r in res):
        _err("plan.meta.resolution", f"must be [width, height] ints in 240..4096, got {res}")
    fps = meta.get("fps", 30)
    if not isinstance(fps, int) or not 12 <= fps <= 60:
        _err("plan.meta.fps", f"must be an int in 12..60, got {fps!r}")

    scenes = _list("plan.scenes", plan.get("scenes"))
    if not scenes:
        _err("plan.scenes", "at least one scene is required")
    if len(scenes) > 40:
        _err("plan.scenes", "too many scenes (max 40)")
    for si, sc in enumerate(scenes):
        p = f"plan.scenes[{si}]"
        sc = _dict(p, sc)
        _str(f"{p}.name", sc.get("name"), default=f"scene{si + 1}")
        dur = _num(f"{p}.duration", sc.get("duration"), lo=0.5, hi=300.0)
        env = _dict(f"{p}.environment", sc.get("environment"), default={})
        preset = env.get("preset") or env.get("type") or "outdoor_day"
        _str(f"{p}.environment.preset", preset, choices=ENV_PRESETS.keys())
        ground = _dict(f"{p}.environment.ground", env.get("ground"), default={})
        _num(f"{p}.environment.ground.y", ground.get("y", 520), lo=50, hi=4000)
        for pi, prop in enumerate(_list(f"{p}.environment.props", env.get("props"), default=[])):
            pp = f"{p}.environment.props[{pi}]"
            prop = _dict(pp, prop)
            kind = _str(f"{pp}.kind", prop.get("kind", "box"), choices=PROP_KINDS)
            _num(f"{pp}.x", prop.get("x", 300), lo=-20000, hi=20000)
            if prop.get("y") is not None:
                _num(f"{pp}.y", prop["y"], lo=-20000, hi=20000)
            _num(f"{pp}.size", prop.get("size", 60), lo=4, hi=2000)
        if env.get("weather") is not None:
            _str(f"{p}.environment.weather", env["weather"], choices=["rain", "snow"])

        acts = _list(f"{p}.actors", sc.get("actors"))
        if not acts:
            _err(f"{p}.actors", "each scene needs at least one actor")
        if len(acts) > 8:
            _err(f"{p}.actors", "too many actors (max 8 per scene)")
        seen_ids = set()
        for ai, ac in enumerate(acts):
            ap = f"{p}.actors[{ai}]"
            ac = _dict(ap, ac)
            aid = _str(f"{ap}.id", ac.get("id"))
            if aid in seen_ids:
                _err(ap, f"duplicate actor id '{aid}'")
            seen_ids.add(aid)
            _str(f"{ap}.rig", ac.get("rig", "blue"), choices=list(RIG_PRESETS.keys()))
            start = _list(f"{ap}.start", ac.get("start"), default=[400, None])
            if len(start) != 2:
                _err(f"{ap}.start", "must be [x, y|null]")
            _num(f"{ap}.start[0]", start[0], lo=-20000, hi=20000)
            if start[1] is not None:
                _num(f"{ap}.start[1]", start[1], lo=-20000, hi=20000)
            perf = _list(f"{ap}.performance", ac.get("performance"), default=[])
            for ki, step in enumerate(perf):
                kp = f"{ap}.performance[{ki}]"
                step = _dict(kp, step)
                act = _str(f"{kp}.action", step.get("action"))
                if act == "pose":
                    _str(f"{kp}.params.pose", _dict(f"{kp}.params", step.get("params")).get("pose"),
                         choices=P.NAMED_POSES.keys())
                elif act == "custom":
                    ang = _dict(f"{kp}.params", step.get("params")).get("angles")
                    if not isinstance(ang, dict) or not ang:
                        _err(f"{kp}.params.angles", "custom action needs an angles object")
                elif act not in ACTIONS and act not in ("hold", "pose", "custom", "move_to", "face", "idle"):
                    _err(kp, f"unknown action '{act}'. Available: "
                             f"{sorted(set(list(ACTIONS) + ['hold', 'pose', 'custom', 'move_to', 'face']))}")

        cam = sc.get("camera")
        if cam is not None:
            cam = _dict(f"{p}.camera", cam)
            for ki, k in enumerate(_list(f"{p}.camera.keys", cam.get("keys"), default=[])):
                _num(f"{p}.camera.keys[{ki}].t", _dict(f"{p}.camera.keys[{ki}]", k).get("t", 0), lo=0, hi=300)
            for mi, m in enumerate(_list(f"{p}.camera.motion", cam.get("motion"), default=[])):
                mp = f"{p}.camera.motion[{mi}]"
                m = _dict(mp, m)
                _str(f"{mp}.kind", m.get("kind"),
                     choices=["shake", "handheld", "wobble", "impact_punch", "zoom_pulse", "follow"])
                _num(f"{mp}.start", m.get("start", 0), lo=0, hi=300)
                _num(f"{mp}.duration", m.get("duration", 1), lo=0.05, hi=300)

        for ti, tx in enumerate(_list(f"{p}.text", sc.get("text"), default=[])):
            tp = f"{p}.text[{ti}]"
            tx = _dict(tp, tx)
            _str(f"{tp}.kind", tx.get("kind"), choices=["title", "subtitle", "bubble", "annotation"])
            _str(f"{tp}.text", tx.get("text"))
            _num(f"{tp}.start", tx.get("start", 0), lo=0, hi=300)
            _num(f"{tp}.end", tx.get("end", 1), lo=0, hi=300)

        _num(f"{p}.fade_in", sc.get("fade_in", 0.4), lo=0, hi=5)
        _num(f"{p}.fade_out", sc.get("fade_out", 0.4), lo=0, hi=5)

    out = _dict("plan.output", plan.get("output"), default={})
    if out.get("audio") is not None and not isinstance(out["audio"], str):
        _err("plan.output.audio", "must be a file path string or null")
    return plan


# ------------------------------------------------------------------- compiling

def _rig_style(spec: Optional[dict], path: str) -> RigStyle:
    spec = _dict(path, spec, default={})
    style = RigStyle()
    if spec.get("line_color"):
        try:
            style.line_color = hex_rgb(spec["line_color"])
        except Exception:
            _err(f"{path}.line_color", f"bad hex color {spec['line_color']!r}")
    if spec.get("head_color"):
        try:
            style.head_color = hex_rgb(spec["head_color"])
        except Exception:
            _err(f"{path}.head_color", f"bad hex color {spec['head_color']!r}")
    style.thickness_scale = _num(f"{path}.thickness_scale", spec.get("thickness_scale"), lo=0.1, hi=6.0, default=1.0)
    style.head_filled = bool(spec.get("head_filled", True))
    style.head_outline_only = bool(spec.get("head_outline_only", False))
    style.head_scale = _num(f"{path}.head_scale", spec.get("head_scale"), lo=0.3, hi=3.0, default=1.0)
    return style


def compile_scene(scene_spec: dict, warnings: List[str], si: int,
                  global_style: Optional[dict] = None) -> Tuple[Scene, List[str]]:
    env = Environment.from_dict(scene_spec.get("environment") or {})
    ground_y = env.ground.y

    actors: List[Actor] = []
    actor_states: Dict[str, Performance] = {}
    for spec in scene_spec.get("actors", []):
        style_spec = dict(global_style or {})
        style_spec.update(spec.get("style") or {})
        style = _rig_style(style_spec, f"actors[{spec['id']}].style")
        rig = RIG_PRESETS[spec.get("rig", "blue")](style)
        start = spec.get("start") or [400, None]
        start_x = float(start[0])
        actor = Actor(actor_id=spec["id"], rig=rig, start_x=start_x,
                      start_y=(float(start[1]) if start[1] is not None else 0.0),
                      mirror=bool(spec.get("mirror", False)),
                      z=int(spec.get("z", 1)))
        pf = Performance(actor, ground_y)
        if start[1] is not None:
            pf.y = float(start[1])
            actor.timeline.keys[0].y = pf.y
        actor_states[spec["id"]] = pf
        actors.append(actor)

        # run the performance script
        for step in spec.get("performance", []):
            name = step.get("action")
            params = dict(step.get("params") or {})
            try:
                if name == "hold":
                    pf.hold(params.get("duration", 0.5))
                elif name == "pose":
                    pf.set_pose(params.get("pose"), dt=params.get("transition", 0.3),
                                ease=params.get("easing", "ease_in_out"))
                    if params.get("hold"):
                        pf.hold(float(params["hold"]))
                elif name == "custom":
                    pf.custom(params.get("angles", {}), dt=params.get("dt", 0.3),
                              x=params.get("x"), dy=params.get("dy", 0.0),
                              grounded=params.get("grounded", True),
                              easing=params.get("easing", "ease_in_out"))
                elif name == "move_to":
                    pf.move_to(params.get("x", pf.x), dt=params.get("dt"),
                               ease=params.get("easing", "ease_in_out"))
                elif name == "face":
                    pf.face(int(params.get("direction", 1)), dt=params.get("dt", 0.12))
                else:
                    pf.do(name, **params)
            except TypeError as e:
                raise PlanError(f"actors[{spec['id']}].performance[{name}]: bad params: {e}")
            except ValueError as e:
                raise PlanError(f"actors[{spec['id']}].performance[{name}]: {e}")

    # camera
    cam_spec = scene_spec.get("camera") or {}
    cam = CameraTrack()
    duration = float(scene_spec.get("duration", 10))
    if not cam_spec.get("keys"):
        # auto framing: fill ~470 world px of height, ground at 2/3 of frame
        zoom = 1080.0 / 470.0
        cx = _scene_center_x(actors)
        cy = ground_y - 135
        cam.key(0.0, x=cx, y=cy, zoom=zoom, angle=0.0)
    else:
        base = cam_spec["keys"][0]
        cam.key(float(base.get("t", 0)),
                x=base.get("x"), y=base.get("y"),
                zoom=base.get("zoom"), angle=base.get("angle"),
                easing=base.get("easing", "ease_in_out"))
        for k in cam_spec["keys"][1:]:
            prev = cam.keys[-1]
            cam.key(float(k.get("t", prev.t + 1)),
                    x=k.get("x"), y=k.get("y"), zoom=k.get("zoom"),
                    angle=k.get("angle"), easing=k.get("easing", "ease_in_out"))
    for m in cam_spec.get("motion", []):
        if m.get("kind") == "follow" and m.get("actor") == "auto":
            first_actor = scene_spec.get("actors", [{}])[0].get("id")
            m = dict(m); m["actor"] = first_actor
        cam.motion(m.get("kind"), float(m.get("start", 0)), float(m.get("duration", 1)),
                   **{k: v for k, v in m.items() if k not in ("kind", "start", "duration")})

    # text
    texts = []
    for tx in scene_spec.get("text", []):
        texts.append(TextElement(
            kind=tx["kind"], text=tx["text"],
            start=float(tx.get("start", 0)), end=float(tx.get("end", 1)),
            fade=float(tx.get("fade", 0.35)),
            x=tx.get("x"), y=tx.get("y"), size=int(tx.get("size", 0)),
            color=tx.get("color", "#ffffff"),
            subtitle=tx.get("subtitle"), band=bool(tx.get("band", True)),
            actor=tx.get("actor"),
            tail=(float(tx["tail"][0]), float(tx["tail"][1])) if tx.get("tail") else None,
            bg=tx.get("bg", "#ffffff"), fg=tx.get("fg", "#1a1a1a"),
        ))

    scene = Scene(
        name=scene_spec.get("name", f"scene{si + 1}"),
        environment=env, actors=actors, camera=cam, texts=texts,
        duration=duration,
        fade_in=float(scene_spec.get("fade_in", 0.4)),
        fade_out=float(scene_spec.get("fade_out", 0.4)),
    )

    # warnings: performance vs scene length
    for actor in actors:
        end_t = actor.timeline.bounds()[1]
        if end_t > duration + 0.05:
            warnings.append(
                f"[{scene.name}] actor '{actor.actor_id}' performance ends at {end_t:.2f}s "
                f"but scene duration is {duration:.2f}s — trailing motion will be cut")
        elif end_t < duration - 1.0:
            warnings.append(
                f"[{scene.name}] actor '{actor.actor_id}' performance ends at {end_t:.2f}s "
                f"(scene {duration:.2f}s) — figure holds its final pose")
    return scene


def _scene_center_x(actors) -> float:
    if not actors:
        return 640.0
    xs = [a.timeline.keys[-1].x if a.timeline.keys else a.start_x for a in actors]
    x0 = [a.timeline.keys[0].x if a.timeline.keys else a.start_x for a in actors]
    lo, hi = min(min(xs), min(x0)), max(max(xs), max(x0))
    return (lo + hi) / 2.0


def compile_plan(plan: dict) -> Tuple[List[Scene], dict, List[str]]:
    """Validate + compile a plan into Scenes and output options."""
    plan = validate_plan(plan)
    warnings: List[str] = []
    global_style = (plan.get("style") or {}).get("actor")
    scenes = []
    for i, sc in enumerate(plan["scenes"]):
        scenes.append(compile_scene(sc, warnings, i, global_style))
    out = plan.get("output") or {}
    options = {
        "mp4": bool(out.get("mp4", True)),
        "styk": bool(out.get("styk", True)),
        "styk_json": bool(out.get("styk_json", False)),
        "preview_times": out.get("preview_times") or "auto",
        "crf": int(out.get("crf", 18)),
        "preset": out.get("preset", "medium"),
        "audio": out.get("audio"),
        "supersample": int(out.get("supersample", 2)),
    }
    return scenes, options, warnings
