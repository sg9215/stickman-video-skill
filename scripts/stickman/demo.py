"""Built-in showcase demo — a 3-scene, ~24s stickman short.

Scene 1  "Arrival"    — outdoor day, hero walks in, waves, speech bubble,
                        title card, follow camera.
Scene 2  "Challenge"  — rival appears, jump over a box, punch combo with
                        camera shake + impact punch, rival falls, gets up.
Scene 3  "Victory"    — sunset, cheer, subtitle outro, slow zoom out.
"""
from __future__ import annotations


def demo_plan() -> dict:
    return {
        "title": "The Challenger — Stickman Demo",
        "meta": {"resolution": [1920, 1080], "fps": 30, "aspect": "16:9"},
        "style": {"actor": {"line_color": "#1a6fd4"}},
        "scenes": [
            {
                "name": "arrival",
                "duration": 8.0,
                "environment": {
                    "preset": "outdoor_day",
                    "ground": {"y": 520, "grass": True},
                    "props": [
                        {"kind": "tree", "x": 180, "size": 150},
                        {"kind": "tree", "x": 1150, "size": 120},
                    ],
                },
                "actors": [
                    {
                        "id": "hero", "rig": "blue", "start": [120, None], "z": 2,
                        "performance": [
                            {"action": "hold", "params": {"duration": 0.6}},
                            {"action": "walk", "params": {"distance": 330, "speed": 130}},
                            {"action": "wave", "params": {"reps": 2.5}},
                            {"action": "idle", "params": {"duration": 1.4}},
                        ],
                    }
                ],
                "camera": {
                    "keys": [
                        {"t": 0, "x": 350, "y": 400, "zoom": 1.85, "easing": "ease_in_out"},
                        {"t": 3.5, "x": 440, "y": 380, "zoom": 2.6},
                        {"t": 8.0, "x": 450, "y": 375, "zoom": 2.4},
                    ],
                    "motion": [
                        {"kind": "handheld", "start": 0.0, "duration": 8.0, "amplitude": 3},
                    ],
                },
                "text": [
                    {"kind": "title", "text": "THE CHALLENGER",
                     "subtitle": "a stickman short", "start": 0.3, "end": 3.6,
                     "y": 0.16},
                    {"kind": "bubble", "actor": "hero", "text": "Time to train!",
                     "start": 4.6, "end": 6.6},
                ],
                "fade_in": 0.5, "fade_out": 0.35,
            },
            {
                "name": "challenge",
                "duration": 9.5,
                "environment": {
                    "preset": "field",
                    "ground": {"y": 520, "grass": True},
                    "props": [
                        {"kind": "box", "x": 560, "size": 70, "color": "#c8965a"},
                        {"kind": "hurdle", "x": 940, "size": 90},
                    ],
                },
                "actors": [
                    {
                        "id": "hero", "rig": "blue", "start": [140, None], "z": 2,
                        "style": {"line_color": "#1a6fd4"},
                        "performance": [
                            {"action": "run", "params": {"distance": 420, "speed": 300}},
                            {"action": "jump", "params": {"height": 150, "forward": 150}},
                            {"action": "run", "params": {"distance": 200, "speed": 280}},
                            {"action": "punch", "params": {"hand": "lead", "power": 1.0}},
                            {"action": "punch", "params": {"hand": "lead", "power": 1.1}},
                            {"action": "kick", "params": {"power": 1.2}},
                            {"action": "idle", "params": {"duration": 0.8}},
                        ],
                    },
                    {
                        "id": "rival", "rig": "blue", "start": [880, None], "z": 1,
                        "mirror": True,
                        "style": {"line_color": "#d43a3a"},
                        "performance": [
                            {"action": "idle", "params": {"duration": 2.2, "energy": 0.7}},
                            {"action": "dodge", "params": {"direction": "back"}},
                            {"action": "dodge", "params": {"direction": "back"}},
                            {"action": "fall", "params": {"style": "stagger"}},
                            {"action": "hold", "params": {"duration": 0.7}},
                            {"action": "get_up", "params": {}},
                            {"action": "bow", "params": {"depth": 0.8}},
                        ],
                    },
                ],
                "camera": {
                    "keys": [
                        {"t": 0, "x": 560, "y": 385, "zoom": 1.9},
                        {"t": 2.2, "x": 640, "y": 380, "zoom": 2.2},
                        {"t": 4.3, "x": 700, "y": 378, "zoom": 2.55},
                        {"t": 6.4, "x": 730, "y": 380, "zoom": 2.2},
                        {"t": 9.5, "x": 760, "y": 382, "zoom": 2.0},
                    ],
                    "motion": [
                        {"kind": "shake", "start": 2.78, "duration": 0.4,
                         "amplitude": 12, "frequency": 12, "decay": 3.2},
                        {"kind": "shake", "start": 4.35, "duration": 0.5,
                         "amplitude": 22, "frequency": 12, "decay": 3.0},
                        {"kind": "impact_punch", "start": 4.35, "duration": 0.45, "amplitude": 1.3},
                        {"kind": "shake", "start": 5.15, "duration": 0.5,
                         "amplitude": 18, "frequency": 11, "decay": 3.0},
                        {"kind": "impact_punch", "start": 5.15, "duration": 0.45, "amplitude": 1.2},
                        {"kind": "shake", "start": 6.0, "duration": 0.6,
                         "amplitude": 26, "frequency": 10, "decay": 2.6},
                        {"kind": "impact_punch", "start": 6.0, "duration": 0.5, "amplitude": 1.6},
                        {"kind": "zoom_pulse", "start": 8.2, "duration": 1.2, "amplitude": 0.06},
                    ],
                },
                "text": [
                    {"kind": "subtitle", "text": "Round one — the challenger attacks!",
                     "start": 3.6, "end": 5.4},
                    {"kind": "subtitle", "text": "And the rival goes down!",
                     "start": 6.2, "end": 8.0},
                ],
                "fade_in": 0.3, "fade_out": 0.35,
            },
            {
                "name": "victory",
                "duration": 7.0,
                "environment": {
                    "preset": "outdoor_sunset",
                    "ground": {"y": 520, "grass": True},
                    "props": [{"kind": "rock", "x": 1000, "size": 80}],
                },
                "actors": [
                    {
                        "id": "hero", "rig": "blue", "start": [420, None], "z": 2,
                        "style": {"line_color": "#1a6fd4"},
                        "performance": [
                            {"action": "cheer", "params": {"jumps": 2}},
                            {"action": "wave", "params": {"reps": 2.0}},
                            {"action": "pose", "params": {"pose": "point_forward", "hold": 0.8}},
                            {"action": "idle", "params": {"duration": 1.2}},
                        ],
                    },
                ],
                "camera": {
                    "keys": [
                        {"t": 0, "x": 500, "y": 390, "zoom": 2.5},
                        {"t": 3.4, "x": 515, "y": 385, "zoom": 2.2},
                        {"t": 7.0, "x": 520, "y": 378, "zoom": 1.75},
                    ],
                },
                "text": [
                    {"kind": "subtitle", "text": "Train hard. Fight fair. Never give up.",
                     "start": 3.8, "end": 6.6},
                    {"kind": "annotation", "text": "GOOD JOB!", "x": 0.30, "y": 0.24,
                     "start": 1.2, "end": 2.6, "tail": [430, 360]},
                ],
                "fade_in": 0.4, "fade_out": 1.0,
            },
        ],
        "output": {
            "mp4": True, "styk": True, "styk_json": True,
            "preview_times": [0.5, 2.0, 4.0, 6.5],
            "crf": 18, "preset": "medium",
        },
    }
