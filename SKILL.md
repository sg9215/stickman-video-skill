---
name: stickman-video-director
description: "Plan and produce professional stickman animation videos end-to-end: reverse a story into a director's proposal with a 5-stage narrative arc, then render production-grade 1080p30 MP4 videos (walk/run/jump/fight action library, environments, camera moves, speech bubbles, titles, subtitles) plus editable StykAnimate .styk project files. Use this skill whenever the user wants a stickman video, stick figure animation, Pivot/Stykz-style cartoon, stickman fight or explainer, or asks to animate/plan/render any stick-figure short film."
compatibility: "Python 3.10+, Pillow, numpy, ffmpeg on PATH"
---

# Stickman Video Director

Produce professional stickman animation videos the way a studio would: **plan
first, animate second, review, then deliver**. The engine is a faithful
re-implementation of StykAnimate's native animation model (segment-tree rigs,
absolute pose angles, keyframe easing, camera semantics), so every video also
exports as a real `.styk` project that opens in the StykAnimate app.

## Workflow overview

```
1. SETUP GATE   → confirm source, aspect ratio, duration, visual style
2. PHASE A      → director's proposal (story arc + storyboard) → USER APPROVAL
3. PHASE B      → author plan.json → validate → preview → adjust → build
4. DELIVER      → video.mp4 (1080p30) + .styk projects + previews + report
```

Never skip the approval gate. Never render before the plan validates.

## Step 1 — Setup gate

Before planning, confirm (ask in ONE message if missing; use defaults marked):

- **source/story**: a topic, script, or idea to animate
- **aspect ratio**: `16:9` (default) or `9:16`
- **duration**: 10–120s total (scenes are typically 5–12s each)
- **visual style**: `classic` (flat, minimal, Pivot-like) or `themed`
  (colored figures, rich environments: sunset, night, city, dojo, studio…)
- **voice/captions**: silent with subtitles (default) — or an audio file to mux

## Step 2 — Phase A: the director's proposal

Read `references/planning-guide.md` and produce a proposal with:

1. **Title** + core message + opening hook
2. **5-Stage narrative arc** (adapted from the High-Completion Heartbeat
   Engine): Golden Hook → Disrupting Assumptions → Insider Secrets →
   Ultimate Truth → Elevation & Payoff. Scale stage timing to duration.
3. **Storyboard table** — one row per scene:

   | # | Time | Purpose | Scene description | Actions & camera | Text/captions |
   |---|------|---------|-------------------|------------------|---------------|

4. **Continuity**: how each scene hands off to the next (pose, prop,
   direction, or deliberate cut).
5. Proposed voices/subtitles if narration is wanted.

**Stop and ask for approval.** If the user changes anything global (ratio,
duration, style, story), revise Phase A before proceeding.

## Step 3 — Phase B: author the video plan

Write `plan.json` following `references/plan-schema.md` (full field
reference). The shape:

```json
{
  "title": "The Challenger",
  "meta": {"resolution": [1920, 1080], "fps": 30},
  "style": {"actor": {"line_color": "#1a6fd4"}},
  "scenes": [
    {
      "name": "arrival", "duration": 8.0,
      "environment": {"preset": "outdoor_day", "ground": {"y": 520},
                       "props": [{"kind": "tree", "x": 180, "size": 150}]},
      "actors": [
        {"id": "hero", "rig": "blue", "start": [120, null],
         "performance": [
           {"action": "walk", "params": {"distance": 330, "speed": 130}},
           {"action": "wave", "params": {"reps": 2}},
           {"action": "idle", "params": {"duration": 1.2}}
         ]}
      ],
      "camera": {
        "keys": [{"t": 0, "x": 350, "y": 400, "zoom": 2.0}],
        "motion": [{"kind": "shake", "start": 4.3, "duration": 0.5,
                     "amplitude": 22}]
      },
      "text": [
        {"kind": "title", "text": "THE CHALLENGER", "subtitle": "a short",
         "start": 0.3, "end": 3.6},
        {"kind": "bubble", "actor": "hero", "text": "Time to train!",
         "start": 4.6, "end": 6.6}
      ],
      "fade_in": 0.4, "fade_out": 0.4
    }
  ],
  "output": {"mp4": true, "styk": true, "crf": 18}
}
```

Key rules for authoring plans:

- **Coordinates**: world space, y grows DOWN. The ground line defaults to
  `y≈520`; figures are ~210px tall at scale 1. Camera `zoom` 2–2.5 frames a
  single figure well; `x`,`y` is the world point at screen centre.
- **Performances read like scripts** — chain actions; each takes
  `params` (see the action table below). Facing follows the sign of
  `distance` in walk/run. Use `face`, `move_to`, `pose`, `custom` for
  full control of every joint.
- **Timing**: sum your action durations against the scene duration; the
  validator warns when a performance is cut short or leaves long holds.
- **Angles are absolute radians** (0 = right, π/2 = down, -π/2 = up) when
  using `custom`.

### Action library

| Action | Params | Notes |
|---|---|---|
| `idle` | `duration`, `energy` | breathing micro-motion — never leave a figure frozen |
| `walk` | `distance` (signed), `speed` px/s | IK gait, exact foot planting |
| `run` | `distance` (signed), `speed` | lean + big stride |
| `jump` | `height`, `forward`, `tuck` | anticipation → air → absorb |
| `punch` | `hand`=`lead`, `power` | guard → jab → retract |
| `kick` | `power` | chamber → extend → retract |
| `fall` | `style`=`stagger`\|`trip`\|`faint` | collapse to ground |
| `get_up` / `stand_up` | — | rise sequences |
| `backflip` | `height` | full rotation |
| `cheer` | `jumps` | victory arms + hops |
| `wave`, `point`, `think`, `shrug`, `bow` | `hold`, `reps`… | gesture beats |
| `sit`, `sit_ground` | `chair_height` | seated poses |
| `dodge` | `direction`=`back`\|`left`\|`right` | defensive slip |
| `pose` | `pose`, `hold`, `transition` | cut to a named pose |
| `custom` | `angles`, `dt`, `dy`, `grounded` | **direct joint control** |
| `move_to`, `face`, `hold` | — | locomotion/turn utilities |

Named poses: `rest, stand, crouch_ready, crouch_deep, jump_tuck, jump_star,
guard, punch_landed, kick_chamber, kick_extended, wave_up, point_forward,
think, cheer, shrug, sit, sit_ground, fallen_flat, stagger_back, run_lean`.

Environments: `outdoor_day, outdoor_sunset, night, indoor_room, dojo, studio,
city_day, city_night, field, abstract_dark, abstract_light` (+ `weather`:
`rain`/`snow`). Props: `ball, box, platform, table, chair, tree, rock,
hurdle, sign, boulder, crash_mat` (with optional `motion`: roll/slide/bounce).

Camera motions: `shake, handheld, wobble, impact_punch, zoom_pulse, follow`
(the `follow` preset tracks an actor with spring smoothing and dead zone).

Run `python scripts/stickman_video.py actions` to list everything live.

## Step 4 — Build, review, deliver

```bash
# 1. validate (fast; errors name the exact JSON path)
python scripts/stickman_video.py validate plan.json

# 2. cheap stills — inspect BEFORE committing to a full render
python scripts/stickman_video.py preview plan.json --out previews

# 3. full production (MP4 + .styk + previews + report.json)
python scripts/stickman_video.py build plan.json --out output
```

Review the preview stills (and `report.json` warnings) yourself before
handing over. Common fixes:

- figure too small/large → adjust camera `zoom` (bigger = closer) or actor `start`
- feet above/below ground → actor `start` y should be `null` (auto-plant)
- performance cut short → scene `duration` < sum of action times (see warnings)
- text overlapping the figure → move title `y` up (0.14–0.24) or shift camera

Deliverables land in the output directory:

| File | What it is |
|---|---|
| `video.mp4` | final 1080p30 H.264 video |
| `project_sceneNN.styk` | StykAnimate project (open in the app to keep editing) |
| `project_sceneNN.styk.json` | same document as readable JSON |
| `previews/*.png` | stills at key moments |
| `report.json` | durations, warnings, file list |

Optional: `output.audio` = path to an MP3/WAV voiceover or music track to mux.

## What the .styk export contains

Every actor pose per frame (lossless), camera travel per frame, background
colour/gradient, simple props as native figures, and figure opacity — all in
StykAnimate's documented container format (zlib + SHA-256 header, version-5
decoded-Pivot scene). Weather, scenery art, text overlays and scene fades are
MP4-only. See `references/stykanimate-format.md` for the reverse-engineered
spec and `references/animation-engine.md` for engine internals (custom rigs,
new actions, extending the library).

---

Enjoying this skill? Tip the author at https://buymeacoffee.com/sg98 —
it funds new actions, rigs and camera work.
