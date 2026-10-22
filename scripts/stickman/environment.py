"""Environment system — backgrounds, ground, props and weather.

Environments are data-driven (dict specs) so video plans can reference
presets by name or customize every layer. Two coordinate spaces:

* Background layers (sky, celestial bodies, skylines, hills) are drawn in
  SCREEN space with parallax factors responding to camera translation.
* Ground and props live in WORLD space and are transformed by the camera,
  so figures and props share one physical stage.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

# --------------------------------------------------------------------- utils

def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t) -> Tuple[int, int, int]:
    return tuple(int(round(lerp(a, b, t))) for a, b in zip(c1, c2))


def hex_rgb(s: str) -> Tuple[int, int, int]:
    s = s.lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


ENV_PRESETS: Dict[str, dict] = {
    "outdoor_day": {
        "sky": ["#8ed0f5", "#e8f6ff"], "sun": "#ffd94d", "sun_pos": [0.82, 0.16],
        "clouds": "#ffffff", "hills": ["#7fc97f", "#5cab5c"], "hills_alpha": 1.0,
        "ground": {"color": "#6db33f", "line": "#4c8f2c", "grass": True},
    },
    "outdoor_sunset": {
        "sky": ["#2e2a5e", "#ff8c5a", "#ffd27a"], "sun": "#ffcf5e", "sun_pos": [0.5, 0.74],
        "sun_big": True, "clouds": "#ffb99a", "hills": ["#6b4a7e", "#4a3260"],
        "ground": {"color": "#3f6b35", "line": "#2e5226", "grass": True},
    },
    "night": {
        "sky": ["#0b1030", "#1b2a5e"], "stars": 90, "moon": "#f2f0d8", "moon_pos": [0.76, 0.18],
        "clouds": None, "hills": ["#141b3d", "#0e1330"],
        "ground": {"color": "#16264a", "line": "#0d1830", "grass": False},
    },
    "indoor_room": {
        "sky": ["#e9e2d4", "#dcd2bd"], "window": True, "picture": True,
        "clouds": None, "hills": [],
        "ground": {"color": "#b98a5a", "line": "#8f6540", "planks": True},
    },
    "dojo": {
        "sky": ["#f4ead8", "#e8dcc2"], "window": False, "picture": False,
        "clouds": None, "hills": [],
        "ground": {"color": "#c9a06a", "line": "#a37c4c", "planks": True},
    },
    "studio": {
        "sky": ["#ffffff", "#f2f4f7"], "grid": "#dfe4ea", "clouds": None, "hills": [],
        "ground": {"color": "#f7f8fa", "line": "#e3e7ec", "grid": True},
    },
    "city_day": {
        "sky": ["#a8c8e8", "#e8eef4"], "skyline": "#8fa8c0", "skyline_windows": "#fff6cf",
        "clouds": "#ffffff", "hills": [],
        "ground": {"color": "#7a7f88", "line": "#5f646d", "road": True},
    },
    "city_night": {
        "sky": ["#0d1230", "#232c54"], "stars": 60, "skyline": "#161c3e",
        "skyline_windows": "#ffd97a", "clouds": None, "hills": [],
        "ground": {"color": "#20263e", "line": "#141a30", "road": True},
    },
    "field": {
        "sky": ["#9fd4f0", "#eaf7ff"], "sun": "#ffe066", "sun_pos": [0.14, 0.14],
        "clouds": "#ffffff", "hills": ["#8fd08f", "#6fb26f"],
        "ground": {"color": "#77c04a", "line": "#579636", "grass": True},
    },
    "abstract_dark": {
        "sky": ["#101014", "#1c1f26"], "clouds": None, "hills": [],
        "ground": {"color": "#14161c", "line": "#262a33"},
    },
    "abstract_light": {
        "sky": ["#ffffff", "#ffffff"], "clouds": None, "hills": [],
        "ground": {"color": "#f4f4f6", "line": "#e2e2e6"},
    },
}


@dataclass
class GroundSpec:
    y: float = 520.0                      # world-space ground line
    color: str = "#6db33f"
    line: Optional[str] = None
    grass: bool = False
    planks: bool = False
    grid: bool = False
    road: bool = False

    @staticmethod
    def from_dict(d: dict, default_y: float = 520.0) -> "GroundSpec":
        d = dict(d or {})
        d.setdefault("y", default_y)
        return GroundSpec(**{k: v for k, v in d.items() if k in GroundSpec.__dataclass_fields__})


@dataclass
class Prop:
    kind: str
    x: float
    y: Optional[float] = None             # None = resting on ground
    size: float = 60.0
    color: Optional[str] = None
    label: Optional[str] = None
    # simple motion (world units per second or keyframes)
    motion: Optional[dict] = None         # {"type": "roll"|"bounce"|"slide", ...}
    state: dict = field(default_factory=dict)


PROP_KINDS = {
    "ball", "box", "platform", "table", "chair", "tree", "rock",
    "hurdle", "sign", "boulder", "crash_mat",
}


def make_prop(spec: dict, ground_y: float) -> Prop:
    kind = spec.get("kind", "box")
    if kind not in PROP_KINDS:
        raise ValueError(f"Unknown prop kind '{kind}'. Available: {sorted(PROP_KINDS)}")
    p = Prop(
        kind=kind,
        x=float(spec.get("x", 300)),
        y=(float(spec["y"]) if spec.get("y") is not None else None),
        size=float(spec.get("size", 60)),
        color=spec.get("color"),
        label=spec.get("label"),
        motion=spec.get("motion"),
    )
    p.state = dict(spec)
    return p


def prop_ground_y(p: Prop, ground_y: float) -> float:
    if p.y is not None:
        return p.y
    return ground_y


# --------------------------------------------------------------- prop motion

def prop_transform(p: Prop, t: float, ground_y: float) -> Tuple[float, float]:
    """Animated position (x, y) of a prop at time t (seconds)."""
    x, y = p.x, prop_ground_y(p, ground_y)
    m = p.motion or {}
    if m.get("type") == "roll":
        x += m.get("vx", 0) * t
    elif m.get("type") == "slide":
        x += m.get("vx", 0) * min(t, m.get("until", 1e9))
    elif m.get("type") == "bounce":
        g = 2600.0
        v0 = m.get("v0", -900.0)
        x += m.get("vx", 160.0) * t
        y = prop_ground_y(p, ground_y) - p.size / 2 + v0 * t + 0.5 * g * t * t
        floor = prop_ground_y(p, ground_y) - p.size / 2
        if y > floor:  # simple ground clamp (bounce resets handled by caller)
            y = floor
    return x, y


# ------------------------------------------------------------- environments

@dataclass
class Environment:
    spec: dict
    ground: GroundSpec
    props: List[Prop] = field(default_factory=list)
    weather: Optional[str] = None        # "rain" | "snow" | None
    weather_intensity: float = 0.6
    _seed: int = 7

    @staticmethod
    def from_dict(d: dict) -> "Environment":
        d = dict(d or {})
        preset_name = d.get("preset") or d.get("type") or "outdoor_day"
        if preset_name in ENV_PRESETS:
            spec = dict(ENV_PRESETS[preset_name])
        else:
            raise ValueError(f"Unknown environment preset '{preset_name}'. "
                             f"Available: {sorted(ENV_PRESETS)}")
        # allow overrides
        for k, v in d.items():
            if k not in ("preset", "type", "ground", "props", "weather", "weather_intensity", "seed"):
                spec[k] = v
        ground = GroundSpec.from_dict(d.get("ground"))
        props = [make_prop(p, ground.y) for p in d.get("props", [])]
        return Environment(spec=spec, ground=ground, props=props,
                           weather=d.get("weather"), 
                           weather_intensity=float(d.get("weather_intensity", 0.6)),
                           _seed=int(d.get("seed", 7)))

    # ------------------------------------------------------------ rendering
    def draw_background(self, img: Image.Image, cam_dx: float = 0.0,
                        cam_scale: float = 1.0) -> None:
        """Screen-space background with parallax from camera travel."""
        draw = ImageDraw.Draw(img)
        W, H = img.size
        # sky gradient
        stops = [hex_rgb(c) if isinstance(c, str) else tuple(c) for c in self.spec.get("sky", ["#ffffff", "#ffffff"])]
        if len(stops) == 2:
            stops = [stops[0], mix(stops[0], stops[1], 0.5), stops[1]]
        bands = 120
        for i in range(bands):
            t = i / (bands - 1)
            if t < 0.5:
                c = mix(stops[0], stops[1], t * 2)
            else:
                c = mix(stops[1], stops[2], (t - 0.5) * 2)
            draw.line([(0, i * H / bands), (W, i * H / bands)], fill=c, width=math.ceil(H / bands) + 1)

        px = cam_dx * 0.12   # parallax response to camera pan
        rng = random.Random(self._seed)

        # stars
        n_stars = self.spec.get("stars")
        if n_stars:
            for _ in range(int(n_stars)):
                sx = (rng.uniform(0, W) - px) % W
                sy = rng.uniform(0, H * 0.62)
                r = rng.choice((1, 1, 1, 2))
                a = rng.uniform(120, 235)
                draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(255, 255, 240, int(a)))

        # sun / moon
        sun_c = self.spec.get("sun") or self.spec.get("moon")
        if sun_c:
            fx, fy = self.spec.get("sun_pos", [0.8, 0.16])
            r = (66 if self.spec.get("sun_big") else 44)
            cx, cy = W * fx - px * 0.6, H * fy
            col = hex_rgb(sun_c)
            if self.spec.get("moon"):
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
                # crescent bite
                draw.ellipse([cx - r * 0.35, cy - r * 0.5, cx + r * 0.75, cy + r * 0.45],
                             fill=mix(hex_rgb(self.spec["sky"][1]), hex_rgb(self.spec["sky"][0]), 0.4))
            else:
                for a in range(12):
                    ang = a * math.tau / 12
                    x1 = cx + math.cos(ang) * r * 1.35
                    y1 = cy + math.sin(ang) * r * 1.35
                    x2 = cx + math.cos(ang) * r * (1.6 + (a % 3) * 0.12)
                    y2 = cy + math.sin(ang) * r * (1.6 + (a % 3) * 0.12)
                    draw.line([(x1, y1), (x2, y2)], fill=col, width=5)
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)

        # clouds
        if self.spec.get("clouds"):
            col = hex_rgb(self.spec["clouds"])
            for i in range(5):
                cx = (rng.uniform(0, W) - px * 0.3 - i * 37) % (W + 300) - 150
                cy = rng.uniform(H * 0.08, H * 0.4)
                s = rng.uniform(0.6, 1.3)
                puff = [(cx - 70 * s, cy), (cx + 70 * s, cy)]
                for j, (ex, ey) in enumerate(puff):
                    rr = 26 * s
                    draw.ellipse([ex - rr * 2, ey - rr, ex + rr * 2, ey + rr], fill=col)
                rr = 30 * s
                draw.ellipse([cx - rr, cy - rr * 1.4, cx + rr, cy + rr * 0.6], fill=col)
                draw.ellipse([cx - rr * 1.9, cy - rr * 0.6, cx - rr * 0.3, cy + rr * 0.7], fill=col)

        # indoor wall features
        if self.spec.get("window"):
            self._draw_window(draw, W, H, px)
        if self.spec.get("picture"):
            self._draw_picture(draw, W, H, px, rng)

        # skyline
        if self.spec.get("skyline"):
            self._draw_skyline(draw, W, H, px, rng)

        # hills
        hills = self.spec.get("hills") or []
        if hills:
            self._draw_hills(draw, W, H, px, hills)

        # studio grid floor hint
        if self.spec.get("grid"):
            gcol = hex_rgb(self.spec["grid"])
            for i in range(-6, 20):
                x = (i * 140 - px * 0.4) % (W + 280) - 140
                draw.line([(x, H * 0.66), (x + 90, H)], fill=gcol, width=2)

    def _draw_window(self, draw, W, H, px):
        x0, y0, x1, y1 = W * 0.62 - px * 0.2, H * 0.10, W * 0.86 - px * 0.2, H * 0.42
        draw.rectangle([x0, y0, x1, y1], fill="#bfe3f5", outline="#8a7550", width=10)
        draw.line([(x0 + y1 - y0, y0), (x0 + (y1 - y0), y1)] if False else [(x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2)], fill="#8a7550", width=8)
        draw.line([((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)], fill="#8a7550", width=8)

    def _draw_picture(self, draw, W, H, px, rng):
        x0, y0, x1, y1 = W * 0.10 - px * 0.2, H * 0.14, W * 0.26 - px * 0.2, H * 0.34
        draw.rectangle([x0, y0, x1, y1], fill="#f6efe0", outline="#8a7550", width=8)
        draw.line([(x0, y1 - 14), (x1, y1 - 14)], fill="#a8c8e8", width=6)
        draw.polygon([(x0 + 12, y1 - 14), (x0 + 34, y0 + 22), (x0 + 56, y1 - 14)], fill="#7fbf7f")

    def _draw_skyline(self, draw, W, H, px, rng):
        col = hex_rgb(self.spec["skyline"])
        win = hex_rgb(self.spec.get("skyline_windows", "#ffd97a"))
        base = H * 0.72
        x = -80 - px * 0.25
        i = 0
        while x < W + 80:
            bw = rng.randint(90, 190)
            bh = rng.randint(120, 330)
            top = base - bh
            draw.rectangle([x, top, x + bw, base], fill=col)
            # windows
            wr = random.Random(100 + i)
            for wy in range(int(top + 18), int(base - 14), 26):
                for wx in range(int(x + 12), int(x + bw - 12), 24):
                    if wr.random() < 0.55:
                        draw.rectangle([wx, wy, wx + 12, wy + 14], fill=win)
            x += bw + rng.randint(10, 42)
            i += 1

    def _draw_hills(self, draw, W, H, px, hills):
        for idx, hcol in enumerate(hills):
            col = hex_rgb(hcol) if isinstance(hcol, str) else tuple(hcol)
            par = 0.22 + idx * 0.1
            base = H * (0.60 + idx * 0.06)
            rng = random.Random(self._seed + idx * 31)
            pts = [(0 - px * par % 40, H + 10)]
            x = -60
            while x < W + 120:
                h = rng.uniform(40, 150) * (1.2 - idx * 0.25)
                cx = x + rng.uniform(60, 160)
                pts += [(cx, base - h), (x + rng.uniform(200, 320), base)]
                x += rng.uniform(260, 420)
            pts.append((W + 60, H + 10))
            draw.polygon(pts, fill=col)

    # ----------------------------------------------------- ground & weather
    def draw_ground(self, img: Image.Image, to_screen, view) -> None:
        """World-space ground band (transformed by camera)."""
        draw = ImageDraw.Draw(img)
        g = self.ground
        col = hex_rgb(g.color)
        line = hex_rgb(g.line) if g.line else mix(col, (0, 0, 0), 0.25)
        W, H = img.size
        # ground band: from ground line to far below the view
        far = g.y + 4000
        left = to_screen((-4000, g.y))
        right = to_screen((8000, g.y))
        bottom = to_screen((0, far))
        draw.polygon([(left[0], left[1]), (right[0], right[1]),
                      (right[0], bottom[1] + 10), (left[0], bottom[1] + 10)], fill=col)
        draw.line([left, right], fill=line, width=max(3, int(4 * view.get("zoom", 1))))
        # texture
        rng = random.Random(4)
        if g.grass:
            for _ in range(160):
                wx = rng.uniform(-2000, 5000)
                wy = g.y + rng.uniform(2, 26)
                p = to_screen((wx, wy))
                if -10 <= p[0] <= W + 10 and p[1] < H + 20:
                    draw.line([p, (p[0] + rng.uniform(-3, 3), p[1] - rng.uniform(4, 9) * view.get("zoom", 1))],
                              fill=line, width=2)
        if g.planks:
            for i in range(40):
                wx = -2000 + i * 120
                a = to_screen((wx, g.y + 1))
                b = to_screen((wx, g.y + 40))
                draw.line([a, b], fill=line, width=2)
        if g.road:
            for i in range(80):
                wx = -2000 + i * 130
                a = to_screen((wx, g.y + 26))
                b = to_screen((wx + 60, g.y + 26))
                draw.line([a, b], fill="#f2d24b", width=5)

    def draw_weather(self, img: Image.Image, t: float) -> None:
        if not self.weather:
            return
        draw = ImageDraw.Draw(img)
        W, H = img.size
        rng = random.Random(991)
        n = int(140 * self.weather_intensity)
        if self.weather == "rain":
            for _ in range(n):
                x0 = rng.uniform(0, W * 1.4)
                speed = rng.uniform(900, 1400)
                y = (rng.uniform(0, H) + t * speed) % (H + 40) - 20
                x = (x0 - t * 220) % (W * 1.4)
                ln = 18 + rng.uniform(0, 14)
                draw.line([(x, y), (x - ln * 0.28, y + ln)], fill=(190, 205, 230, 150), width=2)
        elif self.weather == "snow":
            for _ in range(n):
                x0 = rng.uniform(0, W * 1.2)
                speed = rng.uniform(60, 140)
                phase = rng.uniform(0, 10)
                y = (rng.uniform(0, H) + t * speed) % (H + 20) - 10
                x = (x0 + math.sin(t * 1.7 + phase) * 24) % (W * 1.2)
                r = rng.choice((2, 2, 3))
                draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 220))

    # --------------------------------------------------------------- props
    def draw_props(self, img: Image.Image, to_screen, t: float, view) -> None:
        draw = ImageDraw.Draw(img)
        for p in self.props:
            x, y = prop_transform(p, t, self.ground.y)
            self._draw_prop(draw, p, x, y, to_screen, view)

    def _draw_prop(self, draw, p: Prop, x: float, y_base: float, to_screen, view) -> None:
        zoom = view.get("zoom", 1)
        s = p.size
        col = hex_rgb(p.color) if p.color else None
        line = mix(col or (90, 90, 90), (0, 0, 0), 0.3)

        def box(cx, cy, w, h, fill, outline):
            a = to_screen((cx - w / 2, cy - h))
            b = to_screen((cx + w / 2, cy))
            draw.rectangle([a, b], fill=fill, outline=outline, width=max(2, int(3 * zoom)))

        if p.kind == "ball":
            c = col or (230, 60, 60)
            r = s / 2
            center = to_screen((x, y_base - r))
            r *= zoom
            draw.ellipse([center[0] - r, center[1] - r, center[0] + r, center[1] + r],
                         fill=c, outline=mix(c, (0, 0, 0), 0.35), width=max(2, int(3 * zoom)))
            draw.arc([center[0] - r * 0.55, center[1] - r * 0.55,
                      center[0] + r * 0.55, center[1] + r * 0.55], 200, 340,
                     fill=mix(c, (255, 255, 255), 0.55), width=max(2, int(3 * zoom)))
        elif p.kind in ("box", "platform"):
            c = col or (196, 148, 88)
            box(x, y_base, s, s * (0.55 if p.kind == "platform" else 1.0), c, mix(c, (0, 0, 0), 0.4))
        elif p.kind == "table":
            c = col or (172, 120, 70)
            top_h = 12
            a = to_screen((x - s / 2, y_base - s * 0.55))
            b = to_screen((x + s / 2, y_base - s * 0.55 + top_h))
            draw.rectangle([a, b], fill=c, outline=mix(c, (0, 0, 0), 0.35), width=3)
            for lx in (-s / 2 + 8, s / 2 - 8):
                la = to_screen((x + lx, y_base - s * 0.55 + top_h))
                lb = to_screen((x + lx, y_base))
                draw.line([la, lb], fill=mix(c, (0, 0, 0), 0.25), width=max(4, int(6 * zoom)))
        elif p.kind == "chair":
            c = col or (150, 100, 60)
            seat = s * 0.52
            a = to_screen((x - seat / 2, y_base - s * 0.62))
            b = to_screen((x + seat / 2, y_base - s * 0.62 + 10))
            draw.rectangle([a, b], fill=c, outline=mix(c, (0, 0, 0), 0.35), width=3)
            back_a = to_screen((x + seat / 2 - 8, y_base - s * 0.62))
            back_b = to_screen((x + seat / 2, y_base - s))
            draw.rectangle([back_a, back_b], fill=c, outline=mix(c, (0, 0, 0), 0.35), width=3)
            for lx in (-seat / 2 + 5, seat / 2 - 5):
                la = to_screen((x + lx, y_base - s * 0.62 + 10))
                lb = to_screen((x + lx, y_base))
                draw.line([la, lb], fill=mix(c, (0, 0, 0), 0.25), width=max(3, int(5 * zoom)))
        elif p.kind == "tree":
            trunk = col or (120, 82, 50)
            a = to_screen((x, y_base))
            b = to_screen((x, y_base - s * 0.65))
            draw.line([a, b], fill=trunk, width=max(8, int(14 * zoom)))
            green = (74, 154, 74)
            for (ox, oy, rr) in ((-s * 0.22, -s * 0.78, s * 0.30), (s * 0.20, -s * 0.80, s * 0.32), (0, -s * 0.98, s * 0.34)):
                c = to_screen((x + ox, y_base + oy))
                r = rr * zoom
                draw.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=green)
        elif p.kind in ("rock", "boulder"):
            c = col or (138, 138, 142)
            pts = []
            rng = random.Random(int(p.x))
            for i in range(7):
                ang = math.pi * (i / 6)
                rr = s * 0.5 * rng.uniform(0.75, 1.15)
                wx = x + math.cos(ang) * rr
                wy = (y_base - s * 0.28) - math.sin(ang) * rr * 0.72
                pts.append(to_screen((wx, wy)))
            draw.polygon(pts, fill=c, outline=mix(c, (0, 0, 0), 0.35))
        elif p.kind == "hurdle":
            c = col or (220, 170, 60)
            top = y_base - s * 0.6
            for lx in (-s * 0.4, s * 0.4):
                draw.line([to_screen((x + lx, y_base)), to_screen((x + lx, top))], fill=mix(c, (0, 0, 0), 0.2), width=max(4, int(6 * zoom)))
            draw.line([to_screen((x - s * 0.48, top)), to_screen((x + s * 0.48, top))], fill=c, width=max(5, int(8 * zoom)))
            draw.line([to_screen((x - s * 0.48, top + 14)), to_screen((x + s * 0.48, top + 14))], fill=c, width=max(3, int(5 * zoom)))
        elif p.kind == "sign":
            c = col or (240, 240, 240)
            a = to_screen((x, y_base))
            b = to_screen((x, y_base - s * 0.5))
            draw.line([a, b], fill=(120, 120, 120), width=max(4, int(6 * zoom)))
            ta = to_screen((x - s * 0.45, y_base - s))
            tb = to_screen((x + s * 0.45, y_base - s * 0.5))
            draw.rectangle([ta, tb], fill=c, outline=(90, 90, 90), width=3)
        elif p.kind == "crash_mat":
            c = col or (70, 90, 190)
            box(x, y_base, s * 1.4, s * 0.35, c, mix(c, (0, 0, 0), 0.4))
