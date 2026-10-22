# The StykAnimate Native Format (Reverse-Engineered Spec)

Derived by static analysis of the StykAnimate-App source (v1.2.5) with the
REA toolchain plus the app's own docs. Everything here is implemented in
`scripts/stickman/styk_export.py` and verified by round-trip reading.

## Container format (v1) — `.styk` / `.stkz`

Lossless compressed container, all integers little-endian:

| Offset | Bytes | Meaning |
|---|---|---|
| 0 | 4 | ASCII magic: `STYK` (project) or `STKZ` (figure) |
| 4 | 1 | Container version `1` |
| 5 | 1 | Compression method `1` = zlib-wrapped DEFLATE |
| 6 | 2 | Reserved flags, `0` |
| 8 | 8 | Uncompressed payload length (u64) |
| 16 | 8 | Compressed payload length (u64) |
| 24 | 32 | SHA-256 of the **uncompressed** payload |
| 56 | … | zlib-compressed UTF-8 JSON document |

Plain (uncompressed) JSON files are also readable by the app, so the exporter
can emit `.styk.json` alongside the container.

## Document schema (decoded Pivot scene, version 2–5)

```jsonc
{
  "version": 5,
  "canvas_width": 1920, "canvas_height": 1080,
  "fps": 30,                        // 1–1000 ticks per second
  "figure_types": [ /* see below */ ],
  "keyframes":   [ /* see below */ ],
  "backgrounds": [ /* see below */ ],
  "_styk": { "palette": { "version": 1, "colors": ["#rrggbb", …] } }
}
```

### figure_types[]

```jsonc
{
  "figure_type_id": 1, "name": "Blue", "segment_count": 10,
  "segments": [{
    "segment_id": 1,            // 1–65535, unique within the figure
    "parent_id": 0,             // 0 = root (attaches at object root_x/y)
    "length": 78.0,             // float32
    "angle_rad": -1.5708,       // default/rest absolute angle
    "thickness": 16.0,          // float32, stroke width
    "bend_rad": 0.0,
    "primitive_code": 0,        // 0 = line, 3 = filled circle
    "segment_type": "line",     // "line" | "circle"
    "segment_kind": "line",     // "line" | "circleFill" | "circle"
    "color_rgb": [13, 153, 255],
    "transparency": 0,          // 0–255, 0 = opaque
    "visible": true,
    "z_order": 1,
    "name": "Torso"
  }, /* … */],
  "polyfills": [], "image_assets": [], "text_assets": [],
  "_styk": { "colorMode": "segments" }   // per-segment colors on v5
}
```

### keyframes[]

```jsonc
{
  "objects": [{
    "object_slot": 0, "unique_id": 1,   // unique_id unique per keyframe
    "figure_type_id": 1,
    "root_x": 480.0, "root_y": 280.0,   // float32, the hip joint
    "scale": 1.0,                        // > 0; multiplies lengths+thickness
    "angles": [/* ABSOLUTE radians, one per segment, in segment order */],
    "len_flag": 0, "lengths": [],        // per-segment length overrides
    "bend_flag": 0, "bends": [],
    "join": null,                         // or {target_object_slot, target_handle_id}
    "color_override_raw": 0,              // ARGB u32 or 0
    "field28": 0                          // transparency 0–255
  }],
  "duration_raw": 1,                      // ticks this key is held (0–65535)
  "background_id": 1,
  "camera": {
    "x": -320.0, "y": -240.0,             // offset of focus from canvas centre
    "scale": 0.5,                          // RECIPROCAL of zoom (zoom = 2)
    "angle_rad": 0.0,
    "is_default": false
  },
  "object_draw_order": [0, 1, 2]          // permutation of object slots
}
```

Key semantics (verified against `src/pivot/model.mjs` and `geometry.mjs`):

- A key **owns the transition from itself to the next key** over its
  `duration_raw` ticks; the last key holds.
- Pose `angles[i]` are **absolute world angles**. The evaluator converts to
  relative by subtracting the parent's absolute angle (+ parent bend).
- Geometry: `end = start + scale·length·(cos a, sin a)`, y-down.
- Circle primitives: centre = midpoint(start, end), radius
  `(length + width)/2` when filled, `(length)/2` outlined.
- Camera: the world point `(canvas_w/2 + camera.x, canvas_h/2 + camera.y)`
  maps to the canvas centre; scale is reciprocal zoom; rotation is applied
  as `R(-angle)`.

### backgrounds[]

```jsonc
{ "background_id": 1, "kind": 2, "color": 4294967295 }        // solid, ARGB u32
{ "background_id": 1, "kind": 3,                               // linear gradient
  "color_a": 4287549685, "color_b": 4293457663,
  "x1": 960, "y1": 0, "x2": 960, "y2": 1080 }                  // endpoints
// kind 4 = radial (color_a, color_b, x1,y1 = centre, x2,y2 = radii)
```

## What the exporter writes

- One `.styk` per plan scene, one keyframe per rendered frame
  (`duration_raw: 1` at the plan's fps) — lossless pose-for-pose fidelity,
  and any easing already lives inside the dense keys.
- Figures from actor rigs (per-segment colors, circle heads).
- Simple props (box/platform/ball/tree/hurdle/chair/crash_mat) converted to
  line-chain or circle segment figures, drawn behind the actors.
- Camera converted per frame from the engine's (focus, zoom, angle) model.
- Background as a 2-stop linear gradient of the environment's sky.
- Figure opacity → `field28` transparency.

MP4-only features (weather, scenery art, text overlays, scene fades) have no
native representation and are intentionally excluded from the export.

## Verification

`write_container()` output is read back with `read_container()` on every
build (magic/version/length/SHA-256 checks). `scripts/stickman_video.py
build` fails the build if the round-trip mismatches.
