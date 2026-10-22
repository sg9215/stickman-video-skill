"""Command-line interface for the stickman video engine.

Commands:
    validate <plan.json>          validate a plan without rendering
    preview  <plan.json>          render stills at chosen times (+ contact sheet)
    build    <plan.json>          full production: MP4 + .styk + previews + report
    demo                          build the built-in showcase demo
    actions                       list actions / poses / presets / props
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from . import poses as P
from .actions import ACTIONS
from .camera import CameraTrack
from .environment import ENV_PRESETS, PROP_KINDS
from .plan import PlanError, compile_plan, validate_plan
from .renderer import SceneRenderer
from .rig import RIG_PRESETS
from .styk_export import StykExportOptions, build_document, read_container, write_container
from .textover import TextElement
from . import video


def _load_plan(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(f"error: plan file not found: {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"error: {path} is not valid JSON: {e}")


def _preview_times(scene, times_spec):
    if isinstance(times_spec, (list, tuple)) and times_spec:
        return [float(t) for t in times_spec]
    n = 6
    return [ (i + 0.5) * scene.duration / n for i in range(n) ]


def cmd_validate(args):
    plan = _load_plan(args.plan)
    try:
        validate_plan(plan)
        scenes, options, warnings = compile_plan(plan)
    except PlanError as e:
        sys.exit(f"INVALID PLAN — {e}")
    total = sum(s.duration for s in scenes)
    print(f"OK: '{plan.get('title')}' — {len(scenes)} scene(s), {total:.1f}s total")
    for sc in scenes:
        print(f"  - {sc.name}: {sc.duration:.1f}s, {len(sc.actors)} actor(s), "
              f"{len(sc.texts)} text element(s), env={sc.environment.spec.get('_preset', 'preset')}")
    for w in warnings:
        print(f"  warning: {w}")
    return 0


def cmd_preview(args):
    plan = _load_plan(args.plan)
    scenes, options, warnings = compile_plan(plan)
    os.makedirs(args.out, exist_ok=True)
    W, H = (plan.get("meta") or {}).get("resolution", [1920, 1080])
    ss = args.supersample or options["supersample"]
    for w in warnings:
        print(f"warning: {w}")
    count = 0
    for si, scene in enumerate(scenes):
        renderer = SceneRenderer(scene, W, H, supersample=ss)
        times = _preview_times(scene, args.times or options["preview_times"])
        for t in times:
            t = min(max(0.0, t), max(0.0, scene.duration - 0.01))
            img = renderer.render_frame(t)
            path = os.path.join(args.out, f"{si:02d}_{scene.name}_{t:05.2f}s.png".replace(" ", "_"))
            img.save(path)
            print(f"  preview: {path}")
            count += 1
    print(f"done: {count} preview frame(s) in {args.out}")
    return 0


def cmd_build(args):
    t0 = time.time()
    plan = _load_plan(args.plan)
    scenes, options, warnings = compile_plan(plan)
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    W, H = (plan.get("meta") or {}).get("resolution", [1920, 1080])
    fps = (plan.get("meta") or {}).get("fps", 30)
    ss = options["supersample"]
    for w in warnings:
        print(f"warning: {w}")

    report = {"title": plan.get("title"), "scenes": [], "warnings": warnings}

    # ---- previews first (cheap; agent can inspect before committing)
    if args.skip_previews is False:
        pv_dir = os.path.join(out_dir, "previews")
        os.makedirs(pv_dir, exist_ok=True)
        for si, scene in enumerate(scenes):
            renderer = SceneRenderer(scene, W, H, supersample=max(1, ss // 2))
            for t in _preview_times(scene, options["preview_times"]):
                t = min(max(0.0, t), max(0.0, scene.duration - 0.01))
                img = renderer.render_frame(t)
                img.save(os.path.join(pv_dir, f"{si:02d}_{t:05.2f}s.png"))
        print(f"[1/4] previews written to {pv_dir}")

    # ---- render + encode each scene
    seg_paths = []
    for si, scene in enumerate(scenes):
        renderer = SceneRenderer(scene, W, H, supersample=ss)
        n_frames = max(1, int(round(scene.duration * fps)))
        seg_path = os.path.join(out_dir, f"_seg{si:02d}.mp4")

        def frames():
            for i in range(n_frames):
                yield renderer.render_frame(i / fps)

        print(f"[2/4] encoding scene {si} '{scene.name}' — {n_frames} frames @ {fps}fps "
              f"({W}x{H}, ss={ss})")
        last = [0]

        def prog(n, total):
            pct = int(100 * n / total)
            if pct - last[0] >= 10:
                last[0] = pct
                print(f"       {pct}%")

        video.encode_frames(frames(), seg_path, W, H, fps, total_frames=n_frames,
                            crf=options["crf"], preset=options["preset"], progress=prog)
        seg_paths.append(seg_path)
        report["scenes"].append({"name": scene.name, "duration": scene.duration,
                                 "frames": n_frames})

    # ---- concat + audio
    final = os.path.join(out_dir, "video.mp4")
    if seg_paths:
        video.concat_videos(seg_paths, final)
        for p in seg_paths:
            os.remove(p)
    print(f"[3/4] video: {final}")

    # ---- styk export
    styk_files = []
    if options["styk"] or options["styk_json"]:
        for si, scene in enumerate(scenes):
            renderer = SceneRenderer(scene, W, H, supersample=1)
            doc = build_document(scene, renderer, StykExportOptions(fps=fps, canvas_width=W, canvas_height=H))
            base = os.path.join(out_dir, f"project_scene{si:02d}")
            if options["styk"]:
                p = write_container(doc, base + ".styk")
                # round-trip verification
                read_container(p)
                styk_files.append(p)
            if options["styk_json"]:
                styk_files.append(write_container(doc, base + ".styk.json", compress=False))
        print(f"[4/4] StykAnimate project(s): {', '.join(os.path.basename(p) for p in styk_files)}")
    else:
        print("[4/4] StykAnimate export disabled")

    report["outputs"] = {
        "video": final,
        "styk": styk_files,
        "previews": os.path.join(out_dir, "previews"),
        "duration_s": round(video.probe_duration(final), 2),
        "render_seconds": round(time.time() - t0, 1),
    }
    # copy the plan next to outputs for provenance
    with open(os.path.join(out_dir, "plan_used.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"done in {report['outputs']['render_seconds']}s → {out_dir}")
    print(json.dumps(report["outputs"], indent=2))
    return 0


def cmd_actions(_args):
    print("ACTIONS (params):")
    docs = {
        "idle": "duration=1.2, energy=1.0 — breathing micro-motion",
        "wave": "reps=2, speed=1.0 — friendly wave",
        "walk": "distance=200 (signed), speed=120 px/s",
        "run": "distance=300 (signed), speed=260 px/s",
        "jump": "height=130, tuck=true, forward=0 (signed px)",
        "punch": "hand='lead', power=1.0",
        "kick": "power=1.0",
        "fall": "style='stagger'|'trip'|'faint'",
        "get_up": "— rise from ground",
        "backflip": "height=160",
        "cheer": "jumps=2 — victory arms + hops",
        "point": "hold=0.6",
        "think": "duration=1.2 — hand to chin, head nods",
        "shrug": "hold=0.5",
        "sit": "chair_height=96",
        "sit_ground": "— sit on the floor",
        "stand_up": "— from chair/crouch",
        "dodge": "direction='back'|'left'|'right'",
        "bow": "depth=1.0",
        "hold": "duration=0.5 (control)",
        "pose": "pose=<name>, transition=0.3, hold=0 (control)",
        "custom": "angles={joint:rad}, dt=0.3, dy, x (control — direct joint control)",
        "move_to": "x, dt (control — slide without pose change)",
        "face": "direction=±1 (control — turn around)",
    }
    for k, v in sorted(docs.items()):
        print(f"  {k:12s} {v}")
    print("\nPOSES:", ", ".join(sorted(P.NAMED_POSES)))
    print("RIGS:", ", ".join(RIG_PRESETS))
    print("ENVIRONMENTS:", ", ".join(sorted(ENV_PRESETS)))
    print("PROPS:", ", ".join(sorted(PROP_KINDS)))
    print("CAMERA MOTIONS: shake, handheld, wobble, impact_punch, zoom_pulse, follow")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="stickman_video",
                                 description="Professional stickman video engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="validate a plan JSON")
    v.add_argument("plan")
    v.set_defaults(fn=cmd_validate)

    p = sub.add_parser("preview", help="render preview stills")
    p.add_argument("plan")
    p.add_argument("--out", default="previews")
    p.add_argument("--times", default=None, help="comma-separated seconds")
    p.add_argument("--supersample", type=int, default=0)
    p.set_defaults(fn=cmd_preview)

    b = sub.add_parser("build", help="full production: MP4 + .styk + previews")
    b.add_argument("plan")
    b.add_argument("--out", default="output")
    b.add_argument("--skip-previews", action="store_true")
    b.set_defaults(fn=cmd_build)

    d = sub.add_parser("demo", help="build the built-in showcase demo")
    d.add_argument("--out", default="demo_output")
    d.set_defaults(fn=lambda a: cmd_demo(a))

    a = sub.add_parser("actions", help="list actions, poses, presets")
    a.set_defaults(fn=cmd_actions)

    args = ap.parse_args(argv)
    return args.fn(args)


def cmd_demo(args):
    from .demo import demo_plan
    plan_path = os.path.join(os.path.dirname(args.out) or ".", "demo_plan.json")
    os.makedirs(os.path.dirname(os.path.abspath(plan_path)), exist_ok=True)
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(demo_plan(), f, ensure_ascii=False, indent=2)
    print(f"demo plan written: {plan_path}")
    args.plan = plan_path
    args.skip_previews = False
    return cmd_build(args)


if __name__ == "__main__":
    sys.exit(main())
