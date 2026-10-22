"""Action library — parametric motion generators for stickman actors.

A Performance chains named actions on one actor's timeline. Each action
appends keyframes and advances the performance clock, so scenes read like a
script:  pf.do("walk", distance=260).do("jump", height=120).do("land")...

Conventions
-----------
* Angles are absolute radians; forward-oriented angles are mirrored when the
  actor faces left (a -> pi - a) via :func:`mirror_pose`.
* Root Y for grounded actions is auto-planted so the lowest foot touches the
  ground for that exact pose (the same trick the rig's foot_y computes).
* All durations are seconds.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from . import poses as P
from .animation import Actor, ActorTimeline, Keyframe
from .rig import Rig

PI = math.pi
D = PI / 180.0


def deg(x: float) -> float:
    return x * D


def mirror_pose(pose: Dict[str, float]) -> Dict[str, float]:
    """Mirror a facing-right pose horizontally (a -> pi - a)."""
    return {k: PI - v for k, v in pose.items()}


def oriented(pose: Dict[str, float], facing: int) -> Dict[str, float]:
    return dict(pose) if facing >= 0 else mirror_pose(pose)


@dataclass
class Performance:
    actor: Actor
    ground_y: float
    t: float = 0.0
    pose: Dict[str, float] = None
    facing: int = 1

    def __post_init__(self):
        if self.pose is None:
            self.pose = dict(P.STAND_TALL)
        self.x = self.actor.start_x
        self.y = self.actor.plant_y(self.ground_y, self.pose)
        # seed the timeline with the opening key
        self.timeline = self.actor.timeline
        self.timeline.add(Keyframe(0.0, dict(self.pose), self.x, self.y,
                                   self.actor.start_scale, "linear"))

    # ------------------------------------------------------------ internals
    def _key(self, dt: float, pose: Dict[str, float], *, x: Optional[float] = None,
             y: Optional[float] = None, grounded: bool = True, dy: float = 0.0,
             easing: str = "ease_in_out", label: str = "") -> Keyframe:
        """Append a key dt seconds after the current clock."""
        self.pose = dict(pose)
        if x is None:
            x = self.x
        if grounded:
            y = self.actor.plant_y(self.ground_y, self.pose) + dy
        elif y is None:
            y = self.y + dy
        kf = Keyframe(self.t + dt, dict(self.pose), x, y, self.actor.start_scale,
                      easing, 1.0, label)
        self.timeline.add(kf)
        self.t += dt
        self.x, self.y = x, y
        return kf

    def _transition(self, pose: Dict[str, float], dt: float = 0.22, **kw) -> None:
        self._key(dt, pose, **kw)

    # ------------------------------------------------------------ utilities
    def do(self, action: str, **params) -> "Performance":
        fn = ACTIONS.get(action)
        if fn is None:
            raise ValueError(f"Unknown action '{action}'. Available: {sorted(ACTIONS)}")
        fn(self, **params)
        return self

    def hold(self, dt: float = 0.5) -> "Performance":
        self._key(dt, self.pose, easing="linear", label="hold")
        return self

    def move_to(self, x: float, dt: Optional[float] = None, ease: str = "ease_in_out") -> "Performance":
        """Slide to an absolute x over dt seconds (default: 220 px/s)."""
        if dt is None:
            dt = max(abs(x - self.x) / 220.0, 0.05)
        self._key(dt, self.pose, x=x, easing=ease, label="move")
        return self

    def face(self, direction: int, dt: float = 0.12) -> "Performance":
        """Turn to face +1 (right) or -1 (left); re-orients the current pose."""
        direction = 1 if direction >= 0 else -1
        if direction != self.facing:
            self.facing = direction
            self._transition(oriented(self.pose if direction > 0 else mirror_pose(self.pose), direction), dt)
        return self

    def set_pose(self, pose_name: str, dt: float = 0.3, ease: str = "ease_in_out") -> "Performance":
        pose = P.NAMED_POSES.get(pose_name)
        if pose is None:
            raise ValueError(f"Unknown pose '{pose_name}'. Available: {sorted(P.NAMED_POSES)}")
        self._key(dt, oriented(pose, self.facing), easing=ease, label=f"pose:{pose_name}")
        return self

    def custom(self, pose: Dict[str, float], dt: float = 0.3, *, x: Optional[float] = None,
               dy: float = 0.0, grounded: bool = True, y: Optional[float] = None,
               easing: str = "ease_in_out") -> "Performance":
        """Direct joint control: give any subset of absolute angles (degrees or
        radians via numbers; head/torso stay if omitted)."""
        full = dict(self.pose)
        full.update({k: float(v) for k, v in pose.items()})
        self._key(dt, full, x=x, dy=dy, grounded=grounded, y=y, easing=easing, label="custom")
        return self


# ============================================================ action library

def act_idle(pf: Performance, duration: float = 1.2, energy: float = 1.0) -> None:
    """Idle breathing/sway — never let a character look dead."""
    base = dict(P.STAND_TALL)
    half = duration / 2.0
    breath = deg(2.5) * energy
    up = dict(base)
    up["l_upper_arm"] += breath; up["r_upper_arm"] -= breath
    up["l_forearm"] += breath * 0.6; up["r_forearm"] -= breath * 0.6
    up["head"] = -PI / 2 + deg(3) * energy
    pf._transition(oriented(up, pf.facing), half, label="idle_in")
    pf._transition(oriented(base, pf.facing), half, label="idle_out")


def act_wave(pf: Performance, reps: float = 2.0, speed: float = 1.0) -> None:
    """Wave hello/goodbye. Raises arm then oscillates the forearm."""
    pf._transition(oriented(P.WAVE_UP, pf.facing), 0.25)
    swing = deg(26)
    for i in range(max(1, round(reps * 2))):
        pose = dict(oriented(P.WAVE_UP, pf.facing))
        side = 1 if i % 2 == 0 else -1
        pose["l_forearm"] += side * swing
        pf._key(0.18 / speed, pose, label="wave")
    pf._key(0.22, oriented(P.STAND_TALL, pf.facing), label="wave_end")


def _solve_leg(hip, foot, L1: float, L2: float, facing: int):
    """Two-bone IK: thigh/shin absolute angles from hip to foot.

    Knee bends FORWARD (toward the facing direction), the anatomically
    correct bend for bipedal locomotion.
    """
    dx, dy = foot[0] - hip[0], foot[1] - hip[1]
    d = math.hypot(dx, dy)
    d = max(abs(L1 - L2) + 0.5, min(L1 + L2 - 0.5, d))
    base = math.atan2(dy, dx)
    cos_a = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)
    a = math.acos(max(-1.0, min(1.0, cos_a)))
    thigh = base - facing * a
    knee = (hip[0] + L1 * math.cos(thigh), hip[1] + L1 * math.sin(thigh))
    shin = math.atan2(foot[1] - knee[1], foot[0] - knee[0])
    return thigh, shin


def _smoothstep01(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _gait_pose(phase: float, *, thigh_fwd: float, hip_h: float, lift: float,
               lean: float, arm_swing: float, elbow: float,
               L1: float, L2: float, facing: int, with_stance_rel: bool = False):
    """IK-driven bipedal gait. phase 0..1; L leg contacts at phase 0.

    Feet follow physical trajectories: the stance foot stays planted (moving
    backward relative to the advancing hip) while the swing foot arcs
    forward with a sinusoidal lift — so feet never cross or drag.
    With ``with_stance_rel`` also return the stance foot's x offset relative
    to the hip, so callers can pin the stance foot exactly in world space.
    """
    ph = phase % 1.0
    half = (L1 + L2) * 0.92 * math.sin(math.radians(thigh_fwd))  # half step
    # hip rides highest at mid-stance (ph 0.25 / 0.75) — natural gait bob
    bob = lift * 0.18 * math.sin(PI * 2 * ph) ** 2
    hip = (0.0, -hip_h - bob)

    def foot_x(p, swing):
        # stance: linear back; swing: smoothstep forward
        if not swing:
            return half - 2 * half * p
        return -half + 2 * half * _smoothstep01(p)

    def foot_y(p, swing):
        if not swing:
            return 0.0
        return -lift * math.sin(PI * p)

    # L foot: stance 0..0.5, swing 0.5..1.  R foot is half a cycle ahead.
    # Foot targets are authored in the +x-forward frame; flip them for a
    # left-facing figure so the IK legs physically step toward -x.
    if ph < 0.5:
        l_foot = (foot_x(ph / 0.5, False) * facing, foot_y(ph / 0.5, False))
        r_prog = ph  # R's own phase is (ph+0.5)%1 = ph+0.5 -> swing, progress ph
        r_foot = (foot_x(r_prog, True) * facing, foot_y(r_prog, True))
        stance_rel = foot_x(ph / 0.5, False) * facing
    else:
        r_prog = ph - 0.5          # R stance, its own phase in [0, 0.5)
        r_foot = (foot_x(r_prog, False) * facing, foot_y(r_prog, False))
        l_prog = (ph - 0.5) / 0.5  # L swing
        l_foot = (foot_x(l_prog, True) * facing, foot_y(l_prog, True))
        stance_rel = foot_x(r_prog, False) * facing

    l_thigh, l_shin = _solve_leg(hip, l_foot, L1, L2, facing)
    r_thigh, r_shin = _solve_leg(hip, r_foot, L1, L2, facing)

    # arms counter-swing through contact/mid-stance keys
    s = math.cos(2 * PI * ph)   # +1 at L contact, -1 at R contact
    l_arm = PI / 2 + deg(arm_swing) * s
    r_arm = PI / 2 - deg(arm_swing) * s
    pose = {
        "torso": -PI / 2 + deg(lean), "head": -PI / 2 + deg(lean * 0.35),
        "l_upper_arm": l_arm, "l_forearm": l_arm - deg(elbow),
        "r_upper_arm": r_arm, "r_forearm": r_arm + deg(elbow * 0.45),
        "l_thigh": l_thigh, "l_shin": l_shin,
        "r_thigh": r_thigh, "r_shin": r_shin,
    }
    if facing < 0:
        # Mirror ONLY the procedurally-authored channels (torso/head/arms
        # were computed in the canonical facing-right frame). The IK-solved
        # leg angles are already in world coordinates for this facing and
        # must NOT be mirrored again.
        for k in ("torso", "head", "l_upper_arm", "l_forearm",
                  "r_upper_arm", "r_forearm"):
            pose[k] = PI - pose[k]
    if with_stance_rel:
        return pose, stance_rel
    return pose


def _emit_gait_keys(pf: Performance, gait, period: float, cycles: float,
                    distance: float, keys_per_cycle: int, label: str) -> None:
    """Emit gait keyframes with EXACT world-space stance-foot planting.

    The stance foot's world position is pinned analytically: each half cycle
    the plant point advances by one stride (2*half), so the foot visibly
    grips the ground instead of sliding. The last key absorbs the rounding
    residual so the actor lands exactly on the requested distance.
    """
    facing = pf.facing
    total_keys = max(keys_per_cycle, round(cycles * keys_per_cycle))
    dt = period / keys_per_cycle
    half = gait("half_rel", 0.0)
    start_x = pf.x
    base_plant = pf.x + half * facing     # stance foot world x at contact
    stride = 2 * half                     # world advance per step (half cycle)
    for i in range(1, total_keys + 1):
        ph = (i % keys_per_cycle) / keys_per_cycle
        pose, stance_rel = gait("pose", ph)
        # stance_rel = stance foot offset from the root in WORLD x (already
        # facing-oriented inside _gait_pose). Plant points advance one stride
        # per half cycle in the facing direction:
        #   ph in (0, 0.5) -> L stance, plant 0; ph in (0.5, 1) -> R, plant 1;
        #   ph == 0 -> fresh L contact of a later cycle, two strides along.
        if ph > 0:
            # strides from completed cycles + position within the current one
            steps_done = 2 * ((i - 1) // keys_per_cycle) + int(ph * 2)
        else:
            # ph == 0: fresh L contact beginning cycle (i // kpc)
            steps_done = 2 * (i // keys_per_cycle)
        plant = base_plant + steps_done * stride * facing
        x = plant - stance_rel              # pins the stance foot in world x
        if i == total_keys:
            x = start_x + distance          # absorb rounding residual
        pf._key(dt, pose, x=x, easing="ease_in_out", label=f"{label}:{ph:.2f}")


class _WalkGait:
    def __init__(self, params, facing):
        self.params = params
        self.facing = facing

    def __call__(self, what, ph):
        if what == "half_rel":
            # analytic half-step for this gait (positive, forward)
            L1, L2 = self.params["L1"], self.params["L2"]
            return (L1 + L2) * 0.92 * math.sin(math.radians(self.params["thigh_fwd"]))
        return _gait_pose(ph, with_stance_rel=True, facing=self.facing, **self.params)


def act_walk(pf: Performance, distance: float = 200.0, speed: float = 120.0,
             start_delay: float = 0.0) -> None:
    """Walk forward (signed distance; sign also sets heading)."""
    if start_delay:
        pf.hold(start_delay)
    facing = 1 if distance >= 0 else -1
    if facing != pf.facing:
        pf.face(facing)
    rig = pf.actor.rig
    L1 = rig.by_name["l_thigh"].length
    L2 = rig.by_name["l_shin"].length
    thigh_fwd = 26.0
    params = dict(thigh_fwd=thigh_fwd, hip_h=(L1 + L2) * 0.94, lift=20.0,
                  lean=3.0, arm_swing=24.0, elbow=14.0, L1=L1, L2=L2)
    gait = _WalkGait(params, pf.facing)
    half = gait("half_rel", 0.0)
    # One step advances the body 2*half; a full cycle is two steps.
    period = 4 * half / max(speed, 40.0)          # full gait-cycle period
    cycles = abs(distance) / (period * speed)

    pf._transition(gait("pose", 0.0)[0], 0.18)
    if cycles > 0.02:
        _emit_gait_keys(pf, gait, period, cycles, distance, 8, "walk")
    pf._key(0.22, oriented(P.STAND_TALL, pf.facing), label="walk_end")


def act_run(pf: Performance, distance: float = 300.0, speed: float = 260.0) -> None:
    """Run forward (signed distance sets heading)."""
    facing = 1 if distance >= 0 else -1
    if facing != pf.facing:
        pf.face(facing)
    rig = pf.actor.rig
    L1 = rig.by_name["l_thigh"].length
    L2 = rig.by_name["l_shin"].length
    thigh_fwd = 40.0
    params = dict(thigh_fwd=thigh_fwd, hip_h=(L1 + L2) * 0.88, lift=42.0,
                  lean=15.0, arm_swing=48.0, elbow=58.0, L1=L1, L2=L2)
    gait = _WalkGait(params, pf.facing)
    half = gait("half_rel", 0.0)
    # One step advances the body 2*half; a full cycle is two steps.
    period = max(0.5, 4 * half / max(speed, 60.0))
    cycles = max(abs(distance) / (period * speed), 0.1)

    pf._transition(gait("pose", 0.0)[0], 0.14)
    _emit_gait_keys(pf, gait, period, cycles, distance, 8, "run")
    pf._key(0.3, oriented(P.STAND_TALL, pf.facing), label="run_end")


def act_jump(pf: Performance, height: float = 130.0, tuck: bool = True,
             forward: float = 0.0) -> None:
    """Crouch → launch → (tuck) → extend → land-and-absorb → stand."""
    facing = 1 if forward >= 0 else -1
    if forward and facing != pf.facing:
        pf.face(facing)
    up = max(height, 20.0)
    air_t = 0.28 + up / 600.0
    # anticipation
    pf._transition(oriented(P.CROUCH_READY, pf.facing), 0.14, label="jump_antic")
    pf._key(0.10, oriented(P.CROUCH_DEEP, pf.facing), label="jump_load")
    # launch
    launch = dict(oriented(P.JUMP_STAR if not tuck else P.CROUCH_READY, pf.facing))
    launch["l_thigh"] = PI / 2 - deg(10); launch["l_shin"] = PI / 2 - deg(4)
    launch["r_thigh"] = PI / 2 + deg(10); launch["r_shin"] = PI / 2 + deg(4)
    dx = forward / 2.0
    pf._key(0.12, launch, x=pf.x + dx, grounded=False, dy=-up * 0.55,
            easing="ease_out", label="jump_launch")
    # apex
    apex = oriented(P.JUMP_TUCK if tuck else P.JUMP_STAR, pf.facing)
    pf._key(air_t * 0.5, apex, x=pf.x + dx, grounded=False, dy=-up,
            easing="linear", label="jump_apex")
    # descend
    fall = dict(apex)
    fall["l_thigh"] = PI / 2 - deg(30); fall["r_thigh"] = PI / 2 + deg(30)
    fall["l_shin"] = PI / 2 - deg(12); fall["r_shin"] = PI / 2 + deg(12)
    pf._key(air_t * 0.5, fall, x=pf.x + dx, grounded=False, dy=-up * 0.45,
            easing="ease_in", label="jump_fall")
    # land & absorb (snappy impact: fast in, brief deep crouch, recover)
    pf._key(0.07, oriented(P.CROUCH_DEEP, pf.facing), grounded=True,
            easing="ease_in", label="jump_land")
    pf._key(0.09, oriented(P.CROUCH_READY, pf.facing), label="jump_absorb")
    pf._key(0.20, oriented(P.STAND_TALL, pf.facing), label="jump_recover")


def act_punch(pf: Performance, hand: str = "lead", power: float = 1.0) -> None:
    """Guard up → jab/cross → impact hold → retract to guard."""
    pf._transition(oriented(P.GUARD, pf.facing), 0.16, label="guard")
    lead = "l_upper_arm" if pf.facing > 0 else "r_upper_arm"
    lead_f = "l_forearm" if lead.startswith("l") else "r_forearm"
    back = "r_upper_arm" if lead.startswith("l") else "l_upper_arm"
    back_f = "r_forearm" if back.startswith("r") else "l_forearm"
    # wind up
    wind = dict(oriented(P.GUARD, pf.facing))
    wind[lead] += deg(28) * pf.facing * -1 if False else deg(18) * (1 if pf.facing < 0 else -1)
    pf._key(0.08 * (1 / power), wind, label="punch_wind")
    # extend (impact)
    hit = dict(oriented(P.PUNCH_LANDED, pf.facing))
    if lead.startswith("r"):  # mirror arm channels
        hit["r_upper_arm"], hit["r_forearm"] = hit["l_upper_arm"], hit["l_forearm"]
        hit["l_upper_arm"], hit["l_forearm"] = PI / 2 + deg(55), PI / 2 + deg(88)
    pf._key(0.10, hit, dy=-1.5, easing="ease_out", label="punch_hit")
    pf._key(0.10, dict(oriented(P.GUARD, pf.facing)), easing="ease_out", label="punch_back")


def act_kick(pf: Performance, power: float = 1.0) -> None:
    """Weight shift → chamber → extend → retract."""
    pf._transition(oriented(P.GUARD, pf.facing), 0.14, label="guard")
    pf._key(0.10, oriented(P.KICK_CHAMBER, pf.facing), dy=-2.0, label="kick_chamber")
    pf._key(0.09, oriented(P.KICK_EXTENDED, pf.facing), dy=-4.0,
            easing="ease_out", label="kick_hit")
    pf._key(0.10, oriented(P.KICK_CHAMBER, pf.facing), easing="ease_in_out", label="kick_retract")
    pf._key(0.18, oriented(P.GUARD, pf.facing), label="kick_recover")


def act_fall(pf: Performance, style: str = "stagger") -> None:
    """Stagger backwards and collapse (style: stagger | trip | faint)."""
    if style == "trip":
        pf._key(0.22, oriented(P.STAGGER_BACK, pf.facing), dy=-6, easing="ease_in", label="trip")
        pf._key(0.16, oriented(P.FALLEN_FLAT, pf.facing), grounded=False,
                y=pf.ground_y - 14, easing="ease_in", label="trip_down")
    elif style == "faint":
        pf._key(0.30, oriented(P.FALLEN_FLAT, pf.facing), grounded=False,
                y=pf.ground_y - 14, easing="ease_in_out", label="faint")
    else:
        pf._key(0.20, oriented(P.STAGGER_BACK, pf.facing), dy=-8, easing="ease_in", label="stagger1")
        pf._key(0.22, oriented(P.FALLEN_FLAT, pf.facing), grounded=False,
                y=pf.ground_y - 14, easing="ease_in", label="stagger2")


def act_get_up(pf: Performance) -> None:
    """Rise from the ground back to standing."""
    pf._key(0.30, oriented(P.CROUCH_DEEP, pf.facing), grounded=True,
            easing="ease_out", label="getup_push")
    pf._key(0.35, oriented(P.STAND_TALL, pf.facing), label="getup_stand")


def act_backflip(pf: Performance, height: float = 160.0) -> None:
    """Crouch → launch → full backward rotation (8 keys) → land."""
    pf._transition(oriented(P.CROUCH_READY, pf.facing), 0.16, label="flip_antic")
    pf._key(0.12, oriented(P.CROUCH_DEEP, pf.facing), label="flip_load")
    air_t = 0.85
    up = max(height, 80.0)
    # torso rotates a full turn; emit 8 keys so shortest-arc follows intent
    for i in range(1, 9):
        frac = i / 8.0
        spin = -PI / 2 - 2 * PI * frac          # backward rotation
        y_frac = math.sin(frac * PI)            # arc
        pose = {
            "torso": spin, "head": spin + deg(20) * math.cos(frac * PI),
            "l_upper_arm": spin + deg(150), "l_forearm": spin + deg(170),
            "r_upper_arm": spin - deg(150), "r_forearm": spin - deg(170),
            "l_thigh": spin + deg(115), "l_shin": spin + deg(160),
            "r_thigh": spin - deg(115), "r_shin": spin - deg(160),
        }
        dy = -up * y_frac
        ease = "ease_out" if frac < 0.5 else "ease_in"
        pf._key(air_t / 8.0, pose, grounded=False, dy=dy, easing=ease, label=f"flip{ i}")
    pf._key(0.14, oriented(P.CROUCH_DEEP, pf.facing), grounded=True,
            easing="ease_in", label="flip_land")
    pf._key(0.28, oriented(P.STAND_TALL, pf.facing), label="flip_recover")


def act_cheer(pf: Performance, jumps: int = 2) -> None:
    """Victory celebration: arms up + little hops."""
    pf._transition(oriented(P.CHEER, pf.facing), 0.2, label="cheer_up")
    for i in range(max(1, jumps)):
        pf._key(0.16, oriented(P.CHEER, pf.facing), grounded=False, dy=-34,
                easing="ease_out", label="cheer_hop")
        pf._key(0.16, oriented(P.CHEER, pf.facing), grounded=True,
                easing="ease_in", label="cheer_down")
    pf._key(0.24, oriented(P.STAND_TALL, pf.facing), label="cheer_end")


def act_point(pf: Performance, hold: float = 0.6) -> None:
    pf._transition(oriented(P.POINT_FORWARD, pf.facing), 0.2, label="point")
    pf.hold(hold)
    pf._key(0.22, oriented(P.STAND_TALL, pf.facing), label="point_end")


def act_think(pf: Performance, duration: float = 1.2) -> None:
    pf._transition(oriented(P.THINK, pf.facing), 0.25, label="think_in")
    n = max(2, round(duration / 0.6))
    for i in range(n):
        pose = dict(oriented(P.THINK, pf.facing))
        pose["head"] += deg(6) * (1 if i % 2 == 0 else -1)
        pf._key(duration / n, pose, label="think_nod")
    pf._key(0.25, oriented(P.STAND_TALL, pf.facing), label="think_end")


def act_shrug(pf: Performance, hold: float = 0.5) -> None:
    pf._transition(oriented(P.SHRUG, pf.facing), 0.22, label="shrug_up")
    pf.hold(hold)
    pf._key(0.26, oriented(P.STAND_TALL, pf.facing), label="shrug_end")


def act_sit(pf: Performance, chair_height: float = 96.0) -> None:
    """Sit down onto an invisible/chair-height seat."""
    seat_y = pf.ground_y - chair_height
    pf._transition(oriented(P.CROUCH_READY, pf.facing), 0.2, label="sit_antic")
    pf._key(0.3, oriented(P.SIT, pf.facing), grounded=False, y=seat_y,
            easing="ease_out", label="sit_down")


def act_sit_ground(pf: Performance) -> None:
    pf._key(0.3, oriented(P.CROUCH_DEEP, pf.facing), label="sit_g_antic")
    pf._key(0.35, oriented(P.SIT_GROUND, pf.facing), grounded=False,
            y=pf.ground_y - 16, easing="ease_out", label="sit_g_down")


def act_stand_up(pf: Performance) -> None:
    pf._key(0.3, oriented(P.CROUCH_DEEP, pf.facing), grounded=True,
            easing="ease_out", label="stand_push")
    pf._key(0.32, oriented(P.STAND_TALL, pf.facing), label="stand_tall")


def act_dodge(pf: Performance, direction: str = "back") -> None:
    """Quick defensive slip (back | left | right)."""
    pose = dict(oriented(P.CROUCH_READY, pf.facing))
    if direction == "back":
        pose["torso"] -= deg(16); dx = -46 * pf.facing
    elif direction == "left":
        pose["torso"] += deg(10); dx = -60
    else:
        pose["torso"] += deg(10); dx = 60
    pf._key(0.12, pose, x=pf.x + dx, easing="ease_out", label="dodge")
    pf._key(0.24, oriented(P.GUARD, pf.facing), easing="ease_in_out", label="dodge_back")


def act_bow(pf: Performance, depth: float = 1.0) -> None:
    bow = dict(oriented(P.STAND_TALL, pf.facing))
    bow["torso"] += deg(55) * depth
    bow["head"] += deg(20) * depth
    bow["l_upper_arm"] += deg(30) * depth; bow["r_upper_arm"] -= deg(30) * depth
    pf._key(0.35, bow, easing="ease_in_out", label="bow_down")
    pf._key(0.4, oriented(P.STAND_TALL, pf.facing), label="bow_up")


ACTIONS: Dict[str, Callable] = {
    "idle": act_idle,
    "wave": act_wave,
    "walk": act_walk,
    "run": act_run,
    "jump": act_jump,
    "punch": act_punch,
    "kick": act_kick,
    "fall": act_fall,
    "get_up": act_get_up,
    "backflip": act_backflip,
    "cheer": act_cheer,
    "point": act_point,
    "think": act_think,
    "shrug": act_shrug,
    "sit": act_sit,
    "sit_ground": act_sit_ground,
    "stand_up": act_stand_up,
    "dodge": act_dodge,
    "bow": act_bow,
}
