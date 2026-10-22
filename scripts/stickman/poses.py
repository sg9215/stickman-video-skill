"""Named static poses (canonical facing-right forms).

Angle conventions (absolute world radians, y grows DOWN):
    0 = right (forward)   pi/2 = straight down   pi = left   -pi/2 = up
For a figure facing LEFT, action generators mirror forward-oriented angles
(a -> pi - a); vertical limbs are unchanged. Head/torso stay upright.
"""
from __future__ import annotations

import math
from typing import Dict

PI = math.pi
D = PI / 180.0  # degrees helper


def deg(x: float) -> float:
    return x * D


REST = {
    "torso": -PI / 2, "head": -PI / 2,
    "l_upper_arm": 1.05, "l_forearm": 1.32,
    "r_upper_arm": 2.09, "r_forearm": 1.82,
    "l_thigh": 1.12, "l_shin": 1.52,
    "r_thigh": 2.02, "r_shin": 1.62,
}

STAND_TALL = {
    "torso": -PI / 2, "head": -PI / 2,
    "l_upper_arm": PI / 2 - deg(13), "l_forearm": PI / 2 - deg(24),
    "r_upper_arm": PI / 2 + deg(13), "r_forearm": PI / 2 + deg(24),
    "l_thigh": PI / 2 - deg(5), "l_shin": PI / 2 - deg(2),
    "r_thigh": PI / 2 + deg(5), "r_shin": PI / 2 + deg(2),
}

CROUCH_READY = {
    "torso": -PI / 2 + deg(12), "head": -PI / 2 + deg(6),
    "l_upper_arm": PI / 2 - deg(30), "l_forearm": PI / 2 - deg(55),
    "r_upper_arm": PI / 2 + deg(30), "r_forearm": PI / 2 + deg(55),
    "l_thigh": PI / 2 - deg(35), "l_shin": PI / 2 + deg(50),
    "r_thigh": PI / 2 + deg(35), "r_shin": PI / 2 - deg(50),
}

CROUCH_DEEP = {
    "torso": -PI / 2 + deg(22), "head": -PI / 2 + deg(10),
    "l_upper_arm": PI / 2 - deg(15), "l_forearm": PI / 2 - deg(70),
    "r_upper_arm": PI / 2 + deg(15), "r_forearm": PI / 2 + deg(70),
    "l_thigh": PI / 2 - deg(62), "l_shin": PI / 2 + deg(78),
    "r_thigh": PI / 2 + deg(62), "r_shin": PI / 2 - deg(78),
}

JUMP_TUCK = {
    "torso": -PI / 2 + deg(10), "head": -PI / 2,
    "l_upper_arm": PI / 2 - deg(70), "l_forearm": PI / 2 - deg(95),
    "r_upper_arm": PI / 2 + deg(70), "r_forearm": PI / 2 + deg(95),
    "l_thigh": PI / 2 - deg(80), "l_shin": PI / 2 + deg(100),
    "r_thigh": PI / 2 + deg(80), "r_shin": PI / 2 - deg(100),
}

JUMP_STAR = {
    "torso": -PI / 2, "head": -PI / 2,
    "l_upper_arm": -PI / 2 + deg(35), "l_forearm": -PI / 2 + deg(20),
    "r_upper_arm": -PI / 2 - deg(35), "r_forearm": -PI / 2 - deg(20),
    "l_thigh": PI / 2 - deg(28), "l_shin": PI / 2 - deg(20),
    "r_thigh": PI / 2 + deg(28), "r_shin": PI / 2 + deg(20),
}

GUARD = {  # boxing guard, fists up
    "torso": -PI / 2 + deg(8), "head": -PI / 2 + deg(4),
    "l_upper_arm": PI / 2 - deg(62), "l_forearm": -deg(18),
    "r_upper_arm": PI / 2 + deg(38), "r_forearm": deg(20),
    "l_thigh": PI / 2 - deg(14), "l_shin": PI / 2 - deg(6),
    "r_thigh": PI / 2 + deg(14), "r_shin": PI / 2 + deg(6),
}

PUNCH_LANDED = {  # full extension (left arm = lead)
    "torso": -PI / 2 + deg(14), "head": -PI / 2 + deg(8),
    "l_upper_arm": deg(4), "l_forearm": deg(1),
    "r_upper_arm": PI / 2 + deg(55), "r_forearm": PI / 2 + deg(88),
    "l_thigh": PI / 2 - deg(26), "l_shin": PI / 2 - deg(10),
    "r_thigh": PI / 2 + deg(30), "r_shin": PI / 2 + deg(12),
}

KICK_CHAMBER = {
    "torso": -PI / 2 - deg(10), "head": -PI / 2 - deg(4),
    "l_upper_arm": PI / 2 - deg(45), "l_forearm": PI / 2 - deg(80),
    "r_upper_arm": PI / 2 + deg(45), "r_forearm": PI / 2 + deg(80),
    "l_thigh": PI / 2 - deg(6), "l_shin": PI / 2 - deg(4),
    "r_thigh": -deg(12), "r_shin": PI / 2 - deg(75),
}

KICK_EXTENDED = {
    "torso": -PI / 2 - deg(22), "head": -PI / 2 - deg(10),
    "l_upper_arm": PI / 2 - deg(80), "l_forearm": PI / 2 - deg(95),
    "r_upper_arm": PI / 2 + deg(10), "r_forearm": PI / 2 + deg(15),
    "l_thigh": PI / 2 + deg(8), "l_shin": PI / 2 + deg(4),
    "r_thigh": deg(2), "r_shin": deg(-2),
}

WAVE_UP = {
    "torso": -PI / 2, "head": -PI / 2 + deg(6),
    "l_upper_arm": -PI / 2 + deg(28), "l_forearm": -PI / 2 - deg(18),
    "r_upper_arm": PI / 2 + deg(26), "r_forearm": PI / 2 + deg(42),
    "l_thigh": PI / 2 - deg(6), "l_shin": PI / 2 - deg(2),
    "r_thigh": PI / 2 + deg(6), "r_shin": PI / 2 + deg(2),
}

POINT_FORWARD = {
    "torso": -PI / 2 + deg(4), "head": -PI / 2,
    "l_upper_arm": deg(6), "l_forearm": deg(2),
    "r_upper_arm": PI / 2 + deg(10), "r_forearm": PI / 2 + deg(6),
    "l_thigh": PI / 2 - deg(6), "l_shin": PI / 2 - deg(2),
    "r_thigh": PI / 2 + deg(6), "r_shin": PI / 2 + deg(2),
}

THINK = {
    "torso": -PI / 2 - deg(4), "head": -PI / 2 - deg(10),
    "l_upper_arm": PI / 2 - deg(85), "l_forearm": -PI / 2 + deg(55),
    "r_upper_arm": PI / 2 + deg(12), "r_forearm": PI / 2 + deg(6),
    "l_thigh": PI / 2 - deg(8), "l_shin": PI / 2 - deg(2),
    "r_thigh": PI / 2 + deg(8), "r_shin": PI / 2 + deg(2),
}

CHEER = {
    "torso": -PI / 2, "head": -PI / 2 - deg(8),
    "l_upper_arm": -PI / 2 + deg(14), "l_forearm": -PI / 2 + deg(6),
    "r_upper_arm": -PI / 2 - deg(14), "r_forearm": -PI / 2 - deg(6),
    "l_thigh": PI / 2 - deg(6), "l_shin": PI / 2 - deg(2),
    "r_thigh": PI / 2 + deg(6), "r_shin": PI / 2 + deg(2),
}

SHRUG = {
    "torso": -PI / 2, "head": -PI / 2 + deg(10),
    "l_upper_arm": PI / 2 - deg(52), "l_forearm": PI / 2 - deg(58),
    "r_upper_arm": PI / 2 + deg(52), "r_forearm": PI / 2 + deg(58),
    "l_thigh": PI / 2 - deg(6), "l_shin": PI / 2 - deg(2),
    "r_thigh": PI / 2 + deg(6), "r_shin": PI / 2 + deg(2),
}

SIT = {  # seated (chair height handled by action)
    "torso": -PI / 2 + deg(6), "head": -PI / 2,
    "l_upper_arm": PI / 2 - deg(18), "l_forearm": PI / 2 - deg(60),
    "r_upper_arm": PI / 2 + deg(18), "r_forearm": PI / 2 + deg(60),
    "l_thigh": deg(4), "l_shin": PI / 2 + deg(4),
    "r_thigh": deg(10), "r_shin": PI / 2 + deg(8),
}

SIT_GROUND = {  # legs flat forward
    "torso": -PI / 2 + deg(18), "head": -PI / 2 + deg(8),
    "l_upper_arm": PI / 2 - deg(8), "l_forearm": PI / 2 - deg(30),
    "r_upper_arm": PI / 2 + deg(8), "r_forearm": PI / 2 + deg(30),
    "l_thigh": deg(6), "l_shin": deg(3),
    "r_thigh": deg(14), "r_shin": deg(6),
}

FALLEN_FLAT = {  # lying on back, limbs up-ish sprawl
    "torso": PI / 2, "head": PI / 2 - deg(60),
    "l_upper_arm": PI / 2 + deg(40), "l_forearm": PI / 2 + deg(70),
    "r_upper_arm": PI / 2 - deg(50), "r_forearm": PI / 2 - deg(80),
    "l_thigh": deg(70), "l_shin": deg(95),
    "r_thigh": deg(110), "r_shin": deg(140),
}

STAGGER_BACK = {
    "torso": -PI / 2 - deg(28), "head": -PI / 2 - deg(34),
    "l_upper_arm": PI / 2 + deg(60), "l_forearm": PI / 2 + deg(85),
    "r_upper_arm": PI / 2 + deg(78), "r_forearm": PI / 2 + deg(100),
    "l_thigh": PI / 2 + deg(22), "l_shin": PI / 2 + deg(48),
    "r_thigh": PI / 2 - deg(38), "r_shin": PI / 2 - deg(8),
}

RUN_LEAN = {  # running body position (cycle adds limb swing)
    "torso": -PI / 2 + deg(20), "head": -PI / 2 + deg(12),
    "l_upper_arm": PI / 2 - deg(10), "l_forearm": PI / 2 - deg(35),
    "r_upper_arm": PI / 2 + deg(10), "r_forearm": PI / 2 + deg(35),
    "l_thigh": PI / 2 - deg(10), "l_shin": PI / 2 + deg(12),
    "r_thigh": PI / 2 + deg(10), "r_shin": PI / 2 - deg(12),
}

NAMED_POSES = {
    "rest": REST, "stand": STAND_TALL, "crouch_ready": CROUCH_READY,
    "crouch_deep": CROUCH_DEEP, "jump_tuck": JUMP_TUCK, "jump_star": JUMP_STAR,
    "guard": GUARD, "punch_landed": PUNCH_LANDED, "kick_chamber": KICK_CHAMBER,
    "kick_extended": KICK_EXTENDED, "wave_up": WAVE_UP, "point_forward": POINT_FORWARD,
    "think": THINK, "cheer": CHEER, "shrug": SHRUG, "sit": SIT,
    "sit_ground": SIT_GROUND, "fallen_flat": FALLEN_FLAT, "stagger_back": STAGGER_BACK,
    "run_lean": RUN_LEAN,
}
