"""Stickman rig — a Pivot/StykAnimate-compatible segment tree.

The default rig ("blue") is a faithful re-creation of StykAnimate's startup
figure: 10 segments, filled circular head, symmetric limbs, slightly bent
elbows and knees. Geometry semantics mirror the reverse-engineered native
model:

* Segments form a tree via ``parent_id`` (0 = root).
* Root segments start at the actor's ``root`` joint (the hip); children start
  at their parent's END joint.
* Pose angles are ABSOLUTE world radians (y grows downward, 0 = +x).
* ``end = start + scale * length * (cos a, sin a)``.
* Circle segments (the head) are drawn centred on the midpoint of
  (start, end) with radius (|length| + width) / 2.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

TAU = math.pi * 2.0


@dataclass
class Segment:
    segment_id: int
    parent_id: int
    name: str
    length: float
    angle_rad: float          # default (rest) absolute angle
    thickness: float
    primitive: str = "line"   # "line" | "circle"
    circle_fill: bool = True
    color: Tuple[int, int, int] = (13, 153, 255)
    z_order: int = 0

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "length": self.length,
            "angle_rad": self.angle_rad,
            "thickness": self.thickness,
            "primitive": self.primitive,
            "circle_fill": self.circle_fill,
            "color": list(self.color),
            "z_order": self.z_order,
        }


@dataclass
class RigStyle:
    """Visual style applied to a rig (the switchable art-style system)."""
    line_color: Tuple[int, int, int] = (13, 153, 255)   # classic StykAnimate blue
    head_color: Optional[Tuple[int, int, int]] = None    # None = same as line_color
    thickness_scale: float = 1.0
    head_filled: bool = True
    head_outline_only: bool = False                      # hollow head (Pivot classic)
    head_scale: float = 1.0
    limb_thickness_scale: float = 1.0
    torso_thickness_scale: float = 1.0
    opacity: float = 1.0
    far_side_shading: bool = True   # far limbs thinner/darker for depth

    def resolved_head_color(self, line_color):
        return self.head_color if self.head_color is not None else line_color


# Human-readable joint names for the default rig (used in poses & actions)
JOINT_NAMES = [
    "torso", "head",
    "l_upper_arm", "l_forearm", "r_upper_arm", "r_forearm",
    "l_thigh", "l_shin", "r_thigh", "r_shin",
]


def default_rig(style: Optional[RigStyle] = None) -> "Rig":
    """The canonical 10-segment stickman (StykAnimate 'Blue')."""
    style = style or RigStyle()
    line = style.line_color
    head = style.resolved_head_color(line)
    ts = style.thickness_scale
    segs = [
        # id, parent, name, len, rest-angle, thickness, primitive, fill, color, z
        Segment(1, 0, "torso", 78, -math.pi / 2, 16 * ts * style.torso_thickness_scale, "line", True, line, 1),
        Segment(2, 1, "head", 44 * style.head_scale, -math.pi / 2, 0, "circle", not style.head_outline_only, head, 2),
        Segment(3, 1, "l_upper_arm", 53, 1.05, 12 * ts * style.limb_thickness_scale, "line", True, line, 3),
        Segment(4, 3, "l_forearm", 48, 1.32, 12 * ts * style.limb_thickness_scale, "line", True, line, 4),
        Segment(5, 1, "r_upper_arm", 53, 2.09, 12 * ts * style.limb_thickness_scale, "line", True, line, 5),
        Segment(6, 5, "r_forearm", 48, 1.82, 12 * ts * style.limb_thickness_scale, "line", True, line, 6),
        Segment(7, 0, "l_thigh", 66, 1.12, 14 * ts * style.limb_thickness_scale, "line", True, line, 7),
        Segment(8, 7, "l_shin", 63, 1.52, 14 * ts * style.limb_thickness_scale, "line", True, line, 8),
        Segment(9, 0, "r_thigh", 66, 2.02, 14 * ts * style.limb_thickness_scale, "line", True, line, 9),
        Segment(10, 9, "r_shin", 63, 1.62, 14 * ts * style.limb_thickness_scale, "line", True, line, 10),
    ]
    return Rig(segs, style=style, name="blue")


def slim_rig(style: Optional[RigStyle] = None) -> "Rig":
    style = style or RigStyle()
    style = RigStyle(
        line_color=style.line_color, head_color=style.head_color,
        thickness_scale=style.thickness_scale * 0.6,
        head_filled=style.head_filled, head_outline_only=style.head_outline_only,
        head_scale=style.head_scale, limb_thickness_scale=style.limb_thickness_scale,
        torso_thickness_scale=style.torso_thickness_scale, opacity=style.opacity,
    )
    return default_rig(style)


RIG_PRESETS = {
    "blue": default_rig,
    "slim": slim_rig,
}


@dataclass
class Joint:
    x: float
    y: float


@dataclass
class EvaluatedSegment:
    segment: Segment
    start: Joint
    end: Joint
    angle: float          # absolute world angle actually used
    length: float         # world length (scale applied)

    @property
    def mid(self) -> Joint:
        return Joint((self.start.x + self.end.x) / 2, (self.start.y + self.end.y) / 2)


class Rig:
    def __init__(self, segments: List[Segment], style: Optional[RigStyle] = None, name: str = "custom"):
        self.segments = segments
        self.style = style or RigStyle()
        self.name = name
        self.by_id: Dict[int, Segment] = {}
        self.by_name: Dict[str, Segment] = {}
        self.children: Dict[int, List[int]] = {}
        for s in segments:
            self.by_id[s.segment_id] = s
            self.by_name[s.name] = s
            self.children.setdefault(s.parent_id, []).append(s.segment_id)
        # topological order (parents before children) — same traversal the
        # native geometry-definition builder uses.
        self.order: List[int] = []
        roots = list(self.children.get(0, []))
        queue = list(roots)
        while queue:
            sid = queue.pop(0)
            self.order.append(sid)
            queue.extend(self.children.get(sid, []))
        assert len(self.order) == len(segments), "segment tree has a cycle or orphan"

    # ------------------------------------------------------------------ poses
    def rest_pose(self) -> Dict[str, float]:
        return {s.name: s.angle_rad for s in self.segments}

    def pose_by_id(self, pose: Dict[str, float]) -> Dict[int, float]:
        """Convert name-keyed absolute angles to id-keyed, filling defaults."""
        out = {}
        for s in self.segments:
            out[s.segment_id] = float(pose.get(s.name, s.angle_rad))
        return out

    # -------------------------------------------------------------- geometry
    def evaluate(self, root_x: float, root_y: float, pose: Dict[str, float],
                 scale: float = 1.0, mirror: bool = False) -> List[EvaluatedSegment]:
        """Evaluate world-space joints for a pose (mirrors native evaluator)."""
        ang_by_id = self.pose_by_id(pose)
        ends: Dict[int, Joint] = {}
        out: List[EvaluatedSegment] = []
        for sid in self.order:
            seg = self.by_id[sid]
            a = ang_by_id[sid]
            if mirror:
                a = math.pi - a
            if seg.parent_id == 0:
                start = Joint(root_x, root_y)
            else:
                start = ends[seg.parent_id]
            length = seg.length * scale
            end = Joint(start.x + length * math.cos(a), start.y + length * math.sin(a))
            ends[sid] = end
            out.append(EvaluatedSegment(seg, start, end, a, length))
        return out

    def joints(self, ev: List[EvaluatedSegment]) -> Dict[str, Joint]:
        """Named world joints: hip, shoulder, head_top, hands, feet..."""
        by_name = {e.segment.name: e for e in ev}
        return {
            "hip": Joint(ev_root_start(ev)),
            "shoulder": by_name["torso"].end,
            "head_center": by_name["head"].mid,
            "head_top": by_name["head"].end,
            "l_hand": by_name["l_forearm"].end,
            "r_hand": by_name["r_forearm"].end,
            "l_foot": by_name["l_shin"].end,
            "r_foot": by_name["r_shin"].end,
            **{f"seg_{e.segment.name}": e.end for e in ev},
        }

    # ------------------------------------------------------------- utilities
    def foot_y(self, pose: Dict[str, float], scale: float = 1.0) -> float:
        """Lowest foot Y for a pose (used to plant actors on the ground)."""
        ang = self.pose_by_id(pose)
        best = 0.0
        for thigh, shin in (("l_thigh", "l_shin"), ("r_thigh", "r_shin")):
            t = self.by_name[thigh]; s = self.by_name[shin]
            a1, a2 = ang[t.segment_id], ang[s.segment_id]
            y = (t.length * math.sin(a1) + s.length * math.sin(a2)) * scale
            best = max(best, y)
        return best

    def standing_height(self, scale: float = 1.0) -> float:
        """Approximate total height of the figure standing (for framing)."""
        head = self.by_name["head"]
        torso = self.by_name["torso"]
        leg_reach = max(
            self.by_name["l_thigh"].length + self.by_name["l_shin"].length,
            self.by_name["r_thigh"].length + self.by_name["r_shin"].length,
        )
        return (leg_reach + torso.length + head.length) * scale


def ev_root_start(ev: List[EvaluatedSegment]) -> Joint:
    for e in ev:
        if e.segment.parent_id == 0 and e.segment.name == "torso":
            return e.start
    return ev[0].start if ev else Joint(0, 0)
