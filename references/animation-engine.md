# Animation Engine Internals

How the engine works, and how to extend it. All modules live in
`scripts/stickman/`. Python 3.10+, no dependencies beyond Pillow + numpy
(numpy is optional — used only by debug tooling) and ffmpeg on PATH.

## Module map

| Module | Responsibility |
|---|---|
| `rig.py` | Segment-tree figures, style system, world-space geometry |
| `poses.py` | Named static poses (facing-right canonical forms) |
| `easing.py` | Easing registry incl. StykAnimate-compatible curves |
| `animation.py` | Actor timelines: keyframes, sampling, shortest-arc angles |
| `actions.py` | Action library + IK gait + `Performance` chaining API |
| `environment.py` | Presets, backgrounds w/ parallax, ground, props, weather |
| `camera.py` | Keyframed camera + procedural motions (shake/follow/…) |
| `textover.py` | Titles, subtitles, speech bubbles, annotations |
| `renderer.py` | Frame compositor (supersampled PIL pipeline) |
| `video.py` | ffmpeg piping, concat, audio mux, probing |
| `styk_export.py` | Native `.styk`/`.stkz` container writer |
| `plan.py` | Plan validation + compilation to Scenes |
| `cli.py` | validate / preview / build / demo / actions commands |

## Geometry model (mirrors StykAnimate)

A figure is a tree of segments; each segment has `length`, rest `angle_rad`,
`thickness`, `primitive` (line | circle) and a parent. **Pose angles are
ABSOLUTE world radians** (y-down: 0 = +x, π/2 = down, -π/2 = up). Evaluation
walks the tree in topological order:

- root segments start at the actor's root joint (the hip)
- children start at their parent's END joint
- `end = start + scale * length * (cos a, sin a)`
- circle segments draw centred on the segment midpoint, radius
  `(length + width) / 2` (filled) — the head

Joint names (default rig): `torso, head, l/r_upper_arm, l/r_forearm,
l/r_thigh, l/shin`. The default "blue" rig is a 1:1 re-creation of
StykAnimate's startup figure (10 segments, filled circular head, symmetric
limbs, slightly bent elbows/knees).

### Angles & mirroring

Poses are authored facing right. For a left-facing figure, forward-oriented
angles mirror as `a -> π - a`; vertical limbs are unchanged. `Performance`
tracks `facing` and orients poses automatically; the IK gait solves legs in
world space directly (foot targets are flipped per facing).

## Timelines

`ActorTimeline.keys` is a time-sorted list of `Keyframe(time, pose, x, y,
scale, easing, opacity)`. Each key **owns the transition to the next key**
(the same rule as StykAnimate). Sampling at time t:

1. find bracketing keys; fraction `f = easing((t - t0)/(t1 - t0))`
2. every angle interpolates along the **shortest arc** (native behaviour)
3. the last key holds (native rule)

Gait cycles emit 8 keys per cycle with exact world-space foot planting: the
stance foot's plant point advances one stride (2·half) per half cycle, and
each key's root x is solved so the stance foot's world position is pinned.
Leg angles come from analytic 2-bone IK (`_solve_leg`) driven by physical
foot trajectories (stance foot planted, swing foot on a sinusoidal arc with
knee bend toward the facing direction).

## Adding a new action

```python
def act_spin(pf: Performance, turns: float = 1.0) -> None:
    """Wind up, spin full turns with arms out, recover."""
    pf._transition(oriented(P.CROUCH_READY, pf.facing), 0.16, label="spin_antic")
    n = max(8, round(turns * 8))            # dense keys follow the rotation
    for i in range(1, n + 1):
        frac = i / n
        a = -PI/2 - 2 * PI * turns * frac   # continuous rotation channel
        pose = {"torso": a, "head": a + deg(15),
                "l_upper_arm": a + deg(160), "l_forearm": a + deg(160),
                "r_upper_arm": a - deg(160), "r_forearm": a - deg(160),
                "l_thigh": a + deg(120), "l_shin": a + deg(150),
                "r_thigh": a - deg(120), "r_shin": a - deg(150)}
        pf._key(1.2 / n, pose, dy=-30 * math.sin(frac * PI),
                grounded=False, label=f"spin{i}")
    pf._key(0.2, oriented(P.STAND_TALL, pf.facing), label="spin_recover")

ACTIONS["spin"] = act_spin
```

Rules for good actions:

- **anticipate** before the move (a small opposite beat), **follow through**
  after (overshoot/settle) — that's what reads as "professional"
- emit enough keys that no single interval rotates more than ~45°
- use `pf._key(dt, pose, x=…, dy=…, grounded=…)`; grounded re-plants feet
  for the pose, `dy` lifts the root, `grounded=False` keeps manual control
- full rotations need the dense-key trick (shortest-arc sampling)
- label keys for debuggability

## Building custom rigs

```python
from stickman.rig import Rig, Segment

segments = [
    Segment(1, 0, "tail_base", 40, -PI/2, 10, z_order=1),
    Segment(2, 1, "tail_tip",  45, -PI/2 + 0.6, 6, z_order=2),
    # ... attach a tail, ears, a weapon; any tree works
]
rig = Rig(segments, name="critter")
```

Register it in `RIG_PRESETS` to use it from plans. Poses/actions that
reference missing joints fall back to rest angles, so generic actions still
work on custom rigs (the rig's own joints just hold still unless you address
them).

## Renderer pipeline

Per frame: background (screen-space, parallax from camera pan) → ground +
props (world→screen via the camera affine) → actors (sorted by z; far-side
limbs drawn first with a subtle darker shade for depth) → weather →
supersampled downscale (LANCZOS) → text overlays → scene fades. Camera
model: `screen = centre + R(-angle) · (world - focus) · zoom`.

## Performance notes

A 25s 1080p30 video renders in ~100s at `supersample: 2` on a laptop CPU.
Use `supersample: 1` (still antialiased, softer) for ~4× faster drafts, and
the `preview` command (stills only) for iteration. Rendering is single-
threaded per frame but frames stream into ffmpeg while rendering.

## Validation & verification hooks

- `python scripts/stickman_video.py validate plan.json` — schema + compile
- `.styk` exports are round-tripped (read back + checksum) on every build
- `report.json` lists warnings (performance overflow, long holds) and outputs
