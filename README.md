# Stickman Video Director

A production-grade skill that lets AI agents **plan and render professional
stickman animation videos** — then hand you both the final MP4 *and* an
editable StykAnimate project file.

```
story idea ──▶ director's proposal ──▶ approval ──▶ plan.json ──▶ 1080p MP4 + .styk
              (5-stage narrative arc)               (validated)    + previews + report
```

## What it does

- **Plans like a director** — a setup gate, a 5-stage High-Completion
  narrative arc (Golden Hook → Disrupting Assumptions → Insider Secrets →
  Ultimate Truth → Elevation), a storyboard with continuity notes, and an
  explicit approval step before any rendering. (Methodology adapted from
  [stickman-video-director](https://github.com/kaomei/stickman-video-director).)
- **Animates with full joint control** — the stickman is a 10-segment rig
  (a faithful re-creation of StykAnimate's default figure). Drive it through
  a 20+ action library (IK walk/run with exact foot planting, jumps, punches,
  kicks, falls, backflips, gestures…) or set **every joint angle directly**.
- **Controls the whole environment** — 11 environment presets (day, sunset,
  night, city, dojo, studio…), ground types, props with physics-ish motion,
  rain/snow.
- **Real camera work** — keyframed pan/zoom/roll plus procedural shake,
  impact punch, handheld, wobble, zoom pulse and a spring-damped follow cam.
- **Text systems** — title cards, speech bubbles that track the speaker,
  subtitles, callout annotations.
- **Renders** — 1080p30 H.264 MP4 via a supersampled PIL pipeline into
  ffmpeg; multi-scene stories with fades.
- **Exports native `.styk` projects** — a real StykAnimate container
  (reverse-engineered: zlib + SHA-256 header, decoded-Pivot scene JSON) so
  you can keep editing the animation in the StykAnimate app.

The animation model was reverse-engineered from
[StykAnimate-App](https://github.com/filippocalippo/StykAnimate-App) using
the [REA](https://github.com/morluto/rea) toolchain — see
`references/stykanimate-format.md` for the full spec.

## Quick start

```bash
# requirements: python 3.10+, Pillow, ffmpeg on PATH
python scripts/stickman_video.py demo --out demo_output   # watch the showcase
python scripts/stickman_video.py actions                  # list the library
python scripts/stickman_video.py validate my_plan.json    # check a plan
python scripts/stickman_video.py preview my_plan.json --out previews
python scripts/stickman_video.py build my_plan.json --out output
```

Agent installation: point your agent at this repository; it reads `SKILL.md`
and drives the CLI. `assets/example_plan.json` is a documented starting
point.

## Repository layout

```
SKILL.md                     agent instructions (start here)
manifest.json                package manifest
scripts/stickman_video.py    CLI entry point
scripts/stickman/            engine modules (rig, actions, camera, render, …)
references/                  planning guide, plan schema, engine + format specs
assets/example_plan.json     annotated example plan
demo/                        pre-rendered showcase (video + .styk + previews)
```

## Demo

`demo/video.mp4` is a 24.5s, 3-scene short ("The Challenger") rendered by
this engine: walk-in with title card and speech bubble, a fight scene with
run/jump/punch/kick, camera shakes and impact punches, a fall and get-up,
and a sunset victory cheer — exported alongside its three `.styk` projects.

## License

MIT. The engine re-implements an interoperable subset of StykAnimate's
documented file format for compatibility; StykAnimate itself is GPL-3.0 and
is not required to render videos with this skill.
