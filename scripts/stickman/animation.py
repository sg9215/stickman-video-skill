"""Animation core — actors, keyframes, tracks and sampling.

An Actor owns a rig plus a timeline of keyframes. Each keyframe stores a full
pose (absolute angles by joint name), a root position, a scale and the easing
that governs the transition FROM this key TO the next — the same ownership
rule StykAnimate uses. Sampling a time t finds the bracketing keys, applies
the eased fraction, and interpolates every channel (angles take the shortest
arc, matching the native evaluator).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import easing as ez
from .rig import Rig, JOINT_NAMES


@dataclass
class Keyframe:
    time: float                       # seconds (scene-local)
    pose: Dict[str, float]            # absolute angles by joint name
    x: float                          # root joint x
    y: float                          # root joint y
    scale: float = 1.0
    easing: str = "ease_in_out"       # transition owned by THIS key
    opacity: float = 1.0
    label: str = ""


class ActorTimeline:
    def __init__(self, actor_id: str, rig: Rig):
        self.actor_id = actor_id
        self.rig = rig
        self.keys: List[Keyframe] = []
        self.mirror = False

    # ------------------------------------------------------------ building
    def add(self, kf: Keyframe) -> Keyframe:
        self.keys.append(kf)
        self.keys.sort(key=lambda k: k.time)
        return kf

    def pose_at(self, t: float) -> Dict[str, float]:
        return self.sample(t).pose

    # ------------------------------------------------------------ sampling
    def sample(self, t: float) -> Keyframe:
        if not self.keys:
            rest = self.rig.rest_pose()
            return Keyframe(t, rest, 0.0, 0.0)
        if t <= self.keys[0].time:
            k = self.keys[0]
            return Keyframe(t, dict(k.pose), k.x, k.y, k.scale, "linear", k.opacity)
        if t >= self.keys[-1].time:
            k = self.keys[-1]  # last key holds (native rule)
            return Keyframe(t, dict(k.pose), k.x, k.y, k.scale, "linear", k.opacity)
        # find bracketing keys
        hi = 1
        while self.keys[hi].time < t:
            hi += 1
        lo = self.keys[hi - 1]
        hi_k = self.keys[hi]
        span = max(hi_k.time - lo.time, 1e-9)
        fn = ez.resolve(lo.easing)
        f = fn((t - lo.time) / span)
        pose = {}
        for name in set(lo.pose) | set(hi_k.pose):
            a = lo.pose.get(name, self.rig.by_name[name].angle_rad if name in self.rig.by_name else 0.0)
            b = hi_k.pose.get(name, a)
            pose[name] = ez.lerp_angle(a, b, f)
        return Keyframe(
            t, pose,
            ez.lerp(lo.x, hi_k.x, f), ez.lerp(lo.y, hi_k.y, f),
            ez.lerp(lo.scale, hi_k.scale, f), "linear", ez.lerp(lo.opacity, hi_k.opacity, f),
        )

    def bounds(self):
        if not self.keys:
            return (0.0, 0.0)
        return (self.keys[0].time, self.keys[-1].time)

    def duration(self) -> float:
        lo, hi = self.bounds()
        return hi - lo

    # --------------------------------------------------------- conveniences
    def append_after(self, dt: float, pose, x=None, y=None, scale=None,
                     easing="ease_in_out", opacity=None, label="") -> Keyframe:
        """Append a key dt seconds after the current last key (keeps last pose
        for any channel not supplied)."""
        last = self.keys[-1] if self.keys else Keyframe(0.0, self.rig.rest_pose(), 0.0, 0.0)
        merged_pose = dict(last.pose)
        merged_pose.update(pose or {})
        kf = Keyframe(
            time=last.time + dt,
            pose=merged_pose,
            x=last.x if x is None else x,
            y=last.y if y is None else y,
            scale=last.scale if scale is None else scale,
            easing=easing,
            opacity=last.opacity if opacity is None else opacity,
            label=label,
        )
        return self.add(kf)

    def hold(self, dt: float, label: str = "hold") -> Keyframe:
        """Freeze the current pose for dt seconds."""
        last = self.keys[-1] if self.keys else Keyframe(0.0, self.rig.rest_pose(), 0.0, 0.0)
        return self.add(Keyframe(last.time + dt, dict(last.pose), last.x, last.y,
                                 last.scale, "linear", last.opacity, label))


@dataclass
class Actor:
    actor_id: str
    rig: Rig
    start_x: float = 400.0
    start_y: float = 400.0
    start_scale: float = 1.0
    mirror: bool = False
    z: int = 0                          # draw order (higher = front)
    timeline: ActorTimeline = field(init=False)

    def __post_init__(self):
        self.timeline = ActorTimeline(self.actor_id, self.rig)
        self.timeline.mirror = self.mirror

    def plant_y(self, ground_y: float, pose=None) -> float:
        """Root Y so the lowest foot sits exactly on ground_y for a pose."""
        pose = pose or self.rig.rest_pose()
        return ground_y - self.rig.foot_y(pose, self.start_scale)

    def grounded_key(self, t: float, pose, ground_y: float, x: Optional[float] = None,
                     easing="ease_in_out", scale=None, label="") -> Keyframe:
        """Keyframe whose root Y is auto-planted on the ground."""
        sc = self.start_scale if scale is None else scale
        foot = self.rig.foot_y(pose, sc)
        x = self.start_x if x is None else x
        return Keyframe(t, dict(pose), x, ground_y - foot, sc, easing, 1.0, label)
