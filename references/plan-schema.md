# Video Plan Schema Reference

The plan is a single JSON document. Validation is strict; every error names
the exact JSON path. Top level:

| Field | Type | Default | Notes |
|---|---|---|---|
| `title` | string | "Untitled" | |
| `meta.resolution` | [w,h] | [1920,1080] | ints 240–4096 |
| `meta.fps` | int | 30 | 12–60 |
| `style.actor` | object | — | default actor style (below) |
| `scenes` | array | required | 1–40 scenes |
| `output` | object | — | output options (below) |

## Scene

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | sceneN | used in filenames |
| `duration` | number | required | 0.5–300 seconds |
| `environment` | object | outdoor_day | preset + overrides |
| `actors` | array | required | 1–8 |
| `camera` | object | auto-frame | keys + motion |
| `text` | array | [] | overlays |
| `fade_in` / `fade_out` | number | 0.4 | seconds, from/to black |

## Environment

```json
{
  "preset": "outdoor_day",          // see SKILL.md list
  "ground": {"y": 520, "grass": true, "color": "#6db33f"},
  "props": [
    {"kind": "box", "x": 560, "y": null, "size": 70, "color": "#c8965a",
     "label": "crate", "motion": {"type": "slide", "vx": -80, "until": 2.0}}
  ],
  "weather": "rain",                // or "snow"
  "weather_intensity": 0.6,
  "seed": 7                         // deterministic scatter
}
```

Prop `y: null` rests the prop on the ground. Motions: `roll` (`vx`), `slide`
(`vx`, `until`), `bounce` (`vx`, `v0`).

## Actor

| Field | Type | Default | Notes |
|---|---|---|---|
| `id` | string | required | unique per scene; referenced by camera/text |
| `rig` | string | "blue" | `blue` (classic) or `slim` (thin lines) |
| `start` | [x, y\|null] | [400, null] | `null` y auto-plants feet on ground |
| `mirror` | bool | false | start facing left |
| `z` | int | 1 | draw order (higher = in front) |
| `style` | object | — | per-actor overrides |
| `performance` | array | [] | action chain |

Actor style fields: `line_color` (#rrggbb), `head_color`, `thickness_scale`
(0.1–6), `head_filled` (bool), `head_outline_only` (bool — hollow head),
`head_scale` (0.3–3).

## Performance steps

```json
{"action": "walk",  "params": {"distance": 240, "speed": 130}}
{"action": "pose",  "params": {"pose": "guard", "transition": 0.3, "hold": 0.6}}
{"action": "custom","params": {"angles": {"l_upper_arm": 0.1, "torso": -1.2},
                                "dt": 0.3, "dy": -20, "grounded": false,
                                "easing": "ease_out"}}
{"action": "move_to","params": {"x": 640, "dt": 2.0}}
{"action": "face",  "params": {"direction": -1}}
{"action": "hold",  "params": {"duration": 0.5}}
```

- `custom.angles` — absolute radians, any subset of joints; unspecified
  joints hold their current value. `dy` offsets root y (negative = up),
  `grounded: false` keeps the offset instead of re-planting.
- Easings: `linear, smoothstep, ease_in, ease_out, ease_in_out, hold,
  ease_out_back, ease_in_back, bounce, elastic`.

## Camera

```json
{
  "keys": [
    {"t": 0,   "x": 350, "y": 400, "zoom": 2.0, "angle": 0,
     "easing": "ease_in_out"}
  ],
  "motion": [
    {"kind": "follow", "actor": "hero", "start": 0, "duration": 8,
     "amount": 0.85, "lag": 0.25, "look_ahead": 0.3, "dead_zone": 0.05},
    {"kind": "shake", "start": 4.3, "duration": 0.5,
     "amplitude": 22, "frequency": 12, "decay": 3.0},
    {"kind": "impact_punch", "start": 4.3, "duration": 0.45, "amplitude": 1.3},
    {"kind": "zoom_pulse", "start": 8.0, "duration": 1.2, "amplitude": 0.06},
    {"kind": "handheld", "start": 0, "duration": 10, "amplitude": 3},
    {"kind": "wobble", "start": 0, "duration": 6, "amplitude": 10}
  ]
}
```

- Omit `keys` for auto-framing (fills ~470 world px of height, ground at the
  lower third, centred on the actors).
- `x`,`y` = world point shown at screen centre. `zoom` = magnification
  (2–2.5 frames one figure; 1.4–1.8 frames two).
- `angle` = roll in radians (small values: ±0.03 for dutch tilt).
- Per-key easing governs the transition to the NEXT key (last key holds).

## Text overlays

```json
{"kind": "title", "text": "THE CHALLENGER", "subtitle": "a stickman short",
 "start": 0.3, "end": 3.6, "y": 0.18, "band": true, "color": "#ffffff"}
{"kind": "subtitle", "text": "Round one!", "start": 3.6, "end": 5.4}
{"kind": "bubble", "actor": "hero", "text": "Time to train!",
 "start": 4.6, "end": 6.6, "bg": "#ffffff", "fg": "#1a1a1a"}
{"kind": "annotation", "text": "GOOD JOB!", "x": 0.3, "y": 0.24,
 "start": 1.2, "end": 2.6, "tail": [430, 360]}
```

- `x`/`y` are screen fractions (0–1). `fade` (default 0.35s) fades edges.
- `size` overrides font size (px). Titles default ~8.5% height, subtitles
  ~4.5%, bubbles ~3.6%.
- `bubble.tail` auto-tracks the actor's head when `actor` is set.
- `annotation.tail` is a world-space point the callout line points at.
- Text containing CJK characters automatically uses a CJK font.

## Output

| Field | Default | Notes |
|---|---|---|
| `mp4` | true | final video |
| `styk` | true | `.styk` project per scene |
| `styk_json` | false | also plain-JSON `.styk.json` |
| `preview_times` | "auto" | list of seconds, or auto 6 stills/scene |
| `crf` | 18 | H.264 quality (lower = better) |
| `preset` | "medium" | x264 speed preset |
| `supersample` | 2 | 2 = 2× supersampled render |
| `audio` | null | path to MP3/WAV muxed into the video |
