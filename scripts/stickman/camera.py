"""Camera system — keyframed camera plus procedural motion presets.

Camera model (mirrors the reverse-engineered native semantics):

    screen = center + R(-angle) * (world - focus) * zoom

where ``focus`` is the world point shown at the canvas centre and ``zoom``
is the magnification (2 = twice as large). The native container's camera
stores focus as an offset from canvas centre with reciprocal scale; the
exporter performs that conversion.

Procedural motions stack on top of keyframed travel, exactly like
StykAnimate's Motion row: shake, handheld, wobble, impact punch, zoom pulse
and a critically-damped follow.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from . import easing as ez

TAU = math.pi * 2.0


@dataclass
class CameraKey:
    t: float
    x: Optional[float] = None        # focus x (world); None = inherit previous
    y: Optional[float] = None
    zoom: Optional[float] = None
    angle: Optional[float] = None    # radians
    easing: str = "ease_in_out"


class CameraTrack:
    def __init__(self, start_x: float = 640.0, start_y: float = 300.0,
                 start_zoom: float = 1.0, start_angle: float = 0.0):
        self.keys: List[CameraKey] = [CameraKey(0.0, start_x, start_y, start_zoom, start_angle)]
        self.motions: List[dict] = []

    def key(self, t: float, **kw) -> "CameraTrack":
        self.keys.append(CameraKey(t, **kw))
        self.keys.sort(key=lambda k: k.t)
        return self

    def motion(self, kind: str, start: float, duration: float, **params) -> "CameraTrack":
        if kind not in ("shake", "handheld", "wobble", "impact_punch", "zoom_pulse", "follow"):
            raise ValueError(f"Unknown camera motion '{kind}'")
        self.motions.append({"kind": kind, "start": start, "duration": duration, **params})
        return self

    # ------------------------------------------------------------- sampling
    def sample(self, t: float, actor_pos: Optional[Callable] = None) -> Dict[str, float]:
        """Sample camera state at time t. ``actor_pos(actor_id, t) -> (x, y)``."""
        keys = self.keys
        if t <= keys[0].t:
            k = keys[0]
            x, y, z, a = k.x, k.y, k.zoom, k.angle
            base_t = 0.0
        else:
            i = len(keys) - 1
            while i > 0 and keys[i].t > t:
                i -= 1
            lo, hi = keys[i], keys[i + 1] if i + 1 < len(keys) else keys[i]
            if hi is lo:
                x, y, z, a = lo.x, lo.y, lo.zoom, lo.angle
            else:
                span = max(hi.t - lo.t, 1e-9)
                f = ez.resolve(lo.easing)((t - lo.t) / span)
                def ch(l, h, cur):
                    if l is None and h is None: return cur
                    if l is None: return h
                    if h is None: return l
                    return ez.lerp(l, h, f)
                prev = keys[i - 1] if i > 0 else lo
                x = ch(lo.x, hi.x, prev.x)
                y = ch(lo.y, hi.y, prev.y)
                z = ch(lo.zoom, hi.zoom, prev.zoom or 1.0)
                a = ch(lo.angle, hi.angle, prev.angle or 0.0)

        x = 640.0 if x is None else x
        y = 300.0 if y is None else y
        z = 1.0 if z is None else z
        a = 0.0 if a is None else a

        # -------------------------------------------------- procedural layer
        dx = dy = 0.0
        dzoom = 1.0
        dangle = 0.0
        for m in self.motions:
            on = m["start"] <= t < m["start"] + m["duration"]
            if not on:
                continue
            local = t - m["start"]
            life = m["duration"]
            env = min(1.0, local / 0.12) * min(1.0, (life - local) / 0.25)  # fade edges
            env = max(0.0, env)
            kind = m["kind"]
            if kind == "shake":
                amp = m.get("amplitude", 14)
                freq = m.get("frequency", 11)
                decay = m.get("decay", 2.2)
                rng = random.Random(m.get("seed", 3))
                # deterministic layered sines (no accumulated state, like native)
                d1 = math.sin(local * freq * TAU) * 0.6 + math.sin(local * freq * TAU * 1.7 + 1.3) * 0.4
                d2 = math.cos(local * freq * TAU * 0.9 + 0.7) * 0.6 + math.sin(local * freq * TAU * 2.3) * 0.4
                fall = math.exp(-local * decay)
                dx += d1 * amp * fall * env
                dy += d2 * amp * 0.8 * fall * env
                dangle += math.sin(local * freq * TAU * 1.1) * 0.008 * amp / 14 * fall * env
            elif kind == "handheld":
                amp = m.get("amplitude", 5)
                dx += (math.sin(local * 1.3) + math.sin(local * 2.7 + 1.0)) * amp * 0.5
                dy += (math.cos(local * 1.7 + 0.4) + math.sin(local * 3.1)) * amp * 0.4
                dangle += math.sin(local * 0.9 + 2.0) * 0.004 * amp / 5
            elif kind == "wobble":
                amp = m.get("amplitude", 10)
                dx += math.sin(local * 2.2) * amp * env
                dy += math.cos(local * 1.6 + 0.8) * amp * 0.6 * env
            elif kind == "impact_punch":
                amp = m.get("amplitude", 1.0)
                p = local / life
                spike = math.exp(-p * 7) * math.sin(min(p * 30, math.pi))
                dzoom *= 1 + 0.06 * amp * spike
                dangle += 0.02 * amp * spike
            elif kind == "zoom_pulse":
                amp = m.get("amplitude", 0.08)
                p = local / life
                dzoom *= 1 + amp * math.sin(p * math.pi) * env
            elif kind == "follow":
                if actor_pos is None:
                    continue
                fx, fy = actor_pos(m.get("actor"), t)
                amount = m.get("amount", 1.0)
                # critically damped catch-up (deterministic from t)
                lag = m.get("lag", 0.25)
                lx, ly = actor_pos(m.get("actor"), max(0.0, t - lag))
                smooth_x = fx * (1 - lag * 0.5) + lx * (lag * 0.5)
                look = m.get("look_ahead", 0.0)
                if look:
                    ax, ay = actor_pos(m.get("actor"), t + look)
                    smooth_x = smooth_x * (1 - look) + ax * look
                    smooth_y = fy * (1 - look) + ay * look
                else:
                    smooth_y = fy
                dead = m.get("dead_zone", 0.0)
                # dead zone: pull only beyond a fraction of the frame
                offx, offy = smooth_x - x, smooth_y - y
                dead_px = dead * 400
                mag = math.hypot(offx, offy)
                if mag > dead_px and dead_px > 0:
                    k = (mag - dead_px) / mag
                    offx, offy = offx * k, offy * k
                elif dead_px > 0:
                    offx = offy = 0.0
                dx += offx * amount
                dy += offy * amount

        return {"x": x + dx / z, "y": y + dy / z, "zoom": z * dzoom, "angle": a + dangle}


def camera_matrix(state: Dict[str, float], W: int, H: int):
    """Affine (a,b,c,d,e,f) mapping world→screen for a camera state."""
    z = state["zoom"]
    ang = -state.get("angle", 0.0)
    cos_a, sin_a = math.cos(ang), math.sin(ang)
    fx, fy = state["x"], state["y"]
    a, b = cos_a * z, sin_a * z
    c, d = -sin_a * z, cos_a * z
    e = W / 2 - (a * fx + c * fy)
    f = H / 2 - (b * fx + d * fy)
    return (a, b, c, d, e, f)


def apply_matrix(m, pt: Tuple[float, float]) -> Tuple[float, float]:
    a, b, c, d, e, f = m
    x, y = pt
    return (a * x + c * y + e, b * x + d * y + f)
