"""Frame renderer — composites environment, actors, weather and text.

Pipeline per frame:
    1. screen-space background with parallax
    2. world-space ground and props through the camera matrix
    3. world-space actors (segment trees drawn as round-cap strokes and
       filled circles, exactly the native primitive rules)
    4. weather particles
    5. supersampled downscale (LANCZOS) for crisp anti-aliasing
    6. screen-space text overlays and scene fades
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from .animation import Actor
from .camera import CameraTrack, apply_matrix, camera_matrix
from .environment import Environment
from .textover import TextElement, draw_text_layer
from .rig import EvaluatedSegment, Rig


@dataclass
class Scene:
    name: str = "scene"
    environment: Environment = None
    actors: List[Actor] = field(default_factory=list)
    camera: CameraTrack = None
    texts: List[TextElement] = field(default_factory=list)
    duration: float = 10.0
    fade_in: float = 0.4
    fade_out: float = 0.4
    fade_color: Tuple[int, int, int] = (0, 0, 0)

    def __post_init__(self):
        if self.camera is None:
            self.camera = CameraTrack()


class SceneRenderer:
    def __init__(self, scene: Scene, width: int = 1920, height: int = 1080,
                 supersample: int = 2):
        self.scene = scene
        self.W, self.H = width, height
        self.SS = max(1, supersample)
        self.env = scene.environment or Environment.from_dict({})
        self.actors = sorted(scene.actors, key=lambda a: a.z)
        self.by_id = {a.actor_id: a for a in self.actors}

    # ------------------------------------------------------------ positions
    def actor_pos(self, actor_id: str, t: float) -> Tuple[float, float]:
        """Torso centre in world space — the follow-cam anchor."""
        a = self.by_id.get(actor_id)
        if a is None:
            return (640.0, 300.0)
        kf = a.timeline.sample(t)
        ev = a.rig.evaluate(kf.x, kf.y, kf.pose, kf.scale, a.mirror)
        for e in ev:
            if e.segment.name == "torso":
                return ((e.start.x + e.end.x) / 2, (e.start.y + e.end.y) / 2)
        return (kf.x, kf.y)

    def actor_head_pos(self, actor_id: str, t: float) -> Tuple[float, float]:
        a = self.by_id.get(actor_id)
        if a is None:
            return (640.0, 200.0)
        kf = a.timeline.sample(t)
        ev = a.rig.evaluate(kf.x, kf.y, kf.pose, kf.scale, a.mirror)
        for e in ev:
            if e.segment.name == "head":
                m = e.mid
                return (m.x, m.y)
        return (kf.x, kf.y - 100)

    # -------------------------------------------------------------- frames
    def render_frame(self, t: float) -> Image.Image:
        W, H, SS = self.W, self.H, self.SS
        sw, sh = W * SS, H * SS
        img = Image.new("RGB", (sw, sh), (255, 255, 255))
        cam_state = self.scene.camera.sample(t, actor_pos=self.actor_pos)
        # zoom must be scaled to the supersampled canvas so the camera fills
        # the frame identically at any supersample factor
        mat = camera_matrix({**cam_state, "zoom": cam_state["zoom"] * SS}, sw, sh)
        zoom = cam_state["zoom"] * SS

        def to_screen(pt):
            return apply_matrix(mat, pt)

        view = {"zoom": cam_state["zoom"] * SS}

        # 1. background (parallax uses camera travel from the default focus)
        base = self.scene.camera.sample(0.0) if False else None
        cam_dx = cam_state["x"] - 640.0
        self.env.draw_background(img, cam_dx=cam_dx, cam_scale=cam_state["zoom"])

        # 2. ground + props
        self.env.draw_ground(img, to_screen, view)
        self.env.draw_props(img, to_screen, t, view)

        # 3. actors (world-space geometry transformed through the camera)
        for actor in self.actors:
            kf = actor.timeline.sample(t)
            ev = actor.rig.evaluate(kf.x, kf.y, kf.pose, kf.scale, actor.mirror)
            self._draw_figure(img, ev, zoom, actor, kf.opacity, to_screen)

        # 4. weather
        self.env.draw_weather(img, t)

        # 5. downscale
        if SS > 1:
            img = img.resize((W, H), Image.LANCZOS)

        # 6. text overlays (bubbles anchored to actor heads)
        mat_final = camera_matrix(cam_state, W, H)
        texts = []
        for el in self.scene.texts:
            el2 = el
            if el.kind == "bubble" and el.actor:
                hp = self.actor_head_pos(el.actor, t)
                el2 = _bubble_with_tail(el, apply_matrix(mat_final, hp))
            texts.append(el2)
        draw_text_layer(img, texts, t, world_to_screen=lambda p: apply_matrix(mat_final, p))

        # 7. scene fades
        fade = 0.0
        if self.scene.fade_in > 0 and t < self.scene.fade_in:
            fade = max(fade, 1.0 - t / self.scene.fade_in)
        if self.scene.fade_out > 0 and t > self.scene.duration - self.scene.fade_out:
            fade = max(fade, 1.0 - (self.scene.duration - t) / self.scene.fade_out)
        if fade > 0.001:
            fc = self.scene.fade_color
            black = Image.new("RGB", img.size, fc)
            img = Image.blend(img, black, min(1.0, fade))
        return img

    # ------------------------------------------------------------- figures
    def _draw_figure(self, img: Image.Image, ev: List[EvaluatedSegment],
                     zoom: float, actor: Actor, opacity: float, to_screen) -> None:
        d = ImageDraw.Draw(img, "RGBA")
        style = actor.rig.style
        # Far-side limbs draw first, slightly thinner and darker — the classic
        # 2D-animation depth cue that keeps the passing leg from looking fused.
        far_prefix = "r_" if actor.mirror else "l_"

        def zkey(e):
            name = e.segment.name
            is_far = name.startswith(far_prefix) and ("arm" in name or "leg" in name
                                                      or "thigh" in name or "shin" in name
                                                      or "forearm" in name)
            return (0 if is_far else 1, e.segment.z_order)

        drawables = sorted(ev, key=zkey)
        alpha = int(round(max(0.0, min(1.0, opacity)) * 255))
        if alpha <= 2:
            return
        for e in drawables:
            seg = e.segment
            name = seg.name
            is_far = name.startswith(far_prefix) and ("arm" in name or "thigh" in name
                                                       or "shin" in name or "forearm" in name)
            color = tuple(seg.color) + (alpha,)
            w = seg.thickness * zoom
            if is_far and style.far_side_shading:
                # color-only depth cue: keep thickness identical so joints
                # between shaded/unshaded chain links stay perfectly smooth
                color = tuple(int(c * 0.78) for c in seg.color) + (alpha,)
            if seg.primitive == "circle":
                filled = style.head_filled and seg.circle_fill
                r = (abs(e.length) + (w if filled else 0.0)) / 2.0
                m = to_screen((e.mid.x, e.mid.y))
                if filled:
                    d.ellipse([m[0] - r, m[1] - r, m[0] + r, m[1] + r], fill=color)
                else:
                    d.ellipse([m[0] - r, m[1] - r, m[0] + r, m[1] + r],
                              fill=(255, 255, 255, alpha), outline=color,
                              width=max(2, int(w)))
            else:
                if w <= 0.4:
                    continue
                p0 = to_screen((e.start.x, e.start.y))
                p1 = to_screen((e.end.x, e.end.y))
                d.line([p0, p1], fill=color, width=int(round(max(1, w))))
                # round caps
                r = max(1.0, w / 2.0)
                for p in (p0, p1):
                    d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)


def _bubble_with_tail(el: TextElement, tip: Tuple[float, float]) -> TextElement:
    """Copy a bubble element with a concrete screen-space tail position."""
    import copy
    el2 = copy.copy(el)
    el2._tail_pos = tip
    return el2
