"""Easing functions — mirrors StykAnimate's keyframe easing registry.

Modes: linear, ease_in (cubic 0.42,0,1,1), ease_out (0,0,0.58,1),
ease_in_out (bezier 0.42,0,0.58,1), smoothstep ("Auto" with two isolated
keys), hold (constant), plus bounce/back springs for cartoon energy.
"""
from __future__ import annotations

import math


def _clamp01(t: float) -> float:
    return 0.0 if t < 0 else (1.0 if t > 1 else t)


def linear(t: float) -> float:
    return t


def smoothstep(t: float) -> float:
    t = _clamp01(t)
    return t * t * (3.0 - 2.0 * t)


def ease_in(t: float) -> float:
    """CSS ease-in ≈ cubic-bezier(0.42, 0, 1, 1)."""
    t = _clamp01(t)
    return t * t * t


def ease_out(t: float) -> float:
    """CSS ease-out ≈ cubic-bezier(0, 0, 0.58, 1)."""
    t = _clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def ease_in_out(t: float) -> float:
    """CSS ease-in-out ≈ cubic-bezier(0.42, 0, 0.58, 1)."""
    t = _clamp01(t)
    return t * t * t * (t * (6.0 * t - 15.0) + 10.0)


def hold(t: float) -> float:
    return 0.0


def ease_out_back(t: float) -> float:
    """Overshoot (anticipation/follow-through) — k ≈ 1.70158 + 10%."""
    t = _clamp01(t)
    k = 1.87
    return 1.0 + (k + 1.0) * (t - 1.0) ** 3 + k * (t - 1.0) ** 2


def ease_in_back(t: float) -> float:
    t = _clamp01(t)
    k = 1.87
    return (k + 1.0) * t ** 3 - k * t ** 2


def ease_out_bounce(t: float) -> float:
    t = _clamp01(t)
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def ease_out_elastic(t: float) -> float:
    t = _clamp01(t)
    if t in (0.0, 1.0):
        return t
    return (2.0 ** (-10.0 * t)) * math.sin((t * 10.0 - 0.75) * ((2.0 * math.pi) / 3.0)) + 1.0


EASINGS = {
    "linear": linear,
    "smoothstep": smoothstep,
    "auto": smoothstep,          # alias matching StykAnimate "Auto"
    "ease_in": ease_in,
    "ease_out": ease_out,
    "ease_in_out": ease_in_out,
    "hold": hold,
    "constant": hold,
    "ease_out_back": ease_out_back,
    "ease_in_back": ease_in_back,
    "bounce": ease_out_bounce,
    "elastic": ease_out_elastic,
}


def resolve(name: str):
    fn = EASINGS.get(name)
    if fn is None:
        raise ValueError(f"Unknown easing '{name}'. Valid: {sorted(EASINGS)}")
    return fn


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_angle(a: float, b: float, t: float, shortest_arc: bool = True) -> float:
    """Interpolate angles; unwrap along the shortest arc (native behaviour)."""
    if not shortest_arc:
        return lerp(a, b, t)
    d = (b - a) % math.tau
    if d > math.pi:
        d -= math.tau
    return a + d * t
