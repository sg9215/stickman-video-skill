# Professional Planning Guide — Directing Stickman Videos

Adapted from the stickman-video-director methodology (5-Stage High-Completion
Heartbeat Engine) for a rendering engine instead of an external video AI.

## The contract

Turn one source (topic, script, story idea) into an approved director's
proposal, then into a `plan.json` the engine renders. Preserve the source's
meaning while structuring it through a 5-stage emotional arc. The planning
language matches the user; on-screen text follows the video's language choice.

## Setup gate (before any planning)

Require: source material, aspect ratio (`16:9`/`9:16`), target duration,
visual style (classic/themed), and narration approach (subtitles vs. audio
track). If items are missing, ask for all of them in one concise message and
stop. Defaults: 16:9, 30–60s, themed, subtitles. Never pick a ratio or style
silently; pressure to "just use normal settings" does not waive the gate.

## The 5-Stage Heartbeat Engine

Structure every script through this progression; scale stage timing to
duration:

1. **Golden Hook** (first 2–5s) — an unexpected question or visual paradox.
   Never open with throat-clearing; put the figure IN motion.
2. **Disrupting Assumptions** — state what everyone believes, then shatter it
   in one beat. Visual metaphor beats exposition.
3. **Insider Secrets** — pull back the curtain: the hidden mechanism, the
   real obstacle. This is where the demo/explainer payload lives.
4. **Ultimate Truth Revelation** — the "aha": the underlying logic delivered
   with maximum clarity. Slow down; let a single action carry it.
5. **Elevation & Payoff** — crystallize the takeaway in a memorable final
   image + one-line caption. End on the emotional beat, not a fade.

Duration allocation guide:
- **20–30s**: hook (1 beat) → assumptions (1) → secret (1–2) → truth+payoff (1–2)
- **45–60s**: add a full demonstration scene and a setback beat
- **90s+**: full five stages with 2 scenes per stage; consider a second character

## Storyboard rows

One row per scene (scenes are 5–12s each). Every row needs:

- **Time** and **narrative purpose** (which stage it serves)
- **Scene description**: environment, who is on stage, key staging
- **Actions & camera**: the performance chain and camera behaviour
- **Text**: titles/bubbles/subtitles with in/out times
- **Continuity**: what the NEXT scene inherits (pose, direction, prop, cut)

Rules of thumb that keep videos looking professional:

- A visible change every 2–3 seconds (action, camera, text, or environment).
- Three beats per scene: establish (0–30%), develop (30–70%), land (70–100%).
- Never leave a figure idle for > 1.5s without `idle` breathing at minimum.
- One camera idea per scene (a push-in, a follow, a shake on impact) — not all
  at once.
- End each scene on a pose or motion the next scene can pick up.

## Timing budget for the plan

Actions have known costs (seconds): walk ≈ distance/speed + 0.4 settle;
run ≈ distance/speed + 0.45; jump ≈ 0.85–1.2; punch ≈ 0.44; kick ≈ 0.61;
fall ≈ 0.42; get_up ≈ 0.65; backflip ≈ 1.7; cheer ≈ 0.9 + 0.32·jumps;
wave ≈ 0.7 + 0.36·reps; idle = duration; pose = transition + hold.
Budget the sum ≤ scene duration; the validator warns on overshoot.

## Style guidance

- **classic**: light background (`abstract_light`/`studio`), black/one-color
  figures, max 3 accent colors with fixed meaning (danger=red, success=gold…).
- **themed**: match environment to emotion — `outdoor_day` (neutral/open),
  `outdoor_sunset` (triumph/nostalgia), `night`/`city_night` (tension),
  `dojo` (discipline), `indoor_room` (conversation/explainer).
- Color-code characters (blue protagonist, red rival) and stay consistent.
- Subtitles: 1 line, ≤ 8 words, ≥ 1.6s on screen. Titles: ≤ 5 words.
- Speech bubbles: short (≤ 6 words), 1.5–2.5s, point at the speaker.

## Phase A output template

```
# Director's Proposal — <Title>
Core message: <one sentence>
Hook: <the opening beat>

| # | Time | Purpose | Scene | Actions & camera | Text |
|---|------|---------|-------|------------------|------|
| 1 | 0–8s | Golden Hook | ... | ... | ... |

Continuity: 1→2 (hero runs out of frame right), 2→3 (cut on impact)...
Palette: blue hero / red rival, sunset finale
```

Ask for approval. On any global change, rewrite the proposal.
