"""Text overlays — title cards, speech bubbles, subtitles, annotations.

All elements have fade in/out windows and are drawn in SCREEN space on top of
the composed frame. Fonts are resolved from common system locations; text
containing CJK codepoints automatically uses a CJK-capable font.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

CJK_RE = re.compile(r"[\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")

_FONT_CACHE = {}
_SEARCH_PATHS = [
    "/usr/share/fonts/truetype/dejavu/",
    "/usr/share/fonts/truetype/chinese/",
    "/usr/share/fonts/truetype/noto-serif-sc/",
    "/usr/share/fonts/truetype/english/",
    "/usr/share/fonts/truetype/liberation/",
    "/usr/share/fonts/",
]

_LATIN = ["DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "LiberationSans-Bold.ttf",
          "LiberationSans-Regular.ttf", "Carlito-Bold.ttf", "NotoSansSC-Regular.ttf"]
_CJK = ["NotoSansSC-Bold.ttf", "NotoSansSC-Regular.ttf", "SarasaMonoSC-Bold.ttf",
        "WenQuanYi-Zen-Hei.ttf", "LiberationSans-Bold.ttf"]


def _find_font(names: List[str]) -> Optional[str]:
    for base in _SEARCH_PATHS:
        for name in names:
            p = os.path.join(base, name)
            if os.path.exists(p):
                return p
    return None


def load_font(size: int, bold: bool = True, text: str = "") -> ImageFont.FreefontFont:
    has_cjk = bool(CJK_RE.search(text or ""))
    key = ("cjk" if has_cjk else "lat", size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    if has_cjk:
        path = _find_font(_CJK)
    else:
        path = _find_font(_LATIN if bold else _LATIN[1:] + _LATIN[:1])
    font = None
    if path:
        try:
            font = ImageFont.truetype(path, size)
        except OSError:
            font = None
    if font is None:
        try:
            font = ImageFont.load_default(size)
        except TypeError:
            font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def text_size(draw, text: str, font) -> Tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw, text: str, font, max_w: int) -> List[str]:
    lines, cur = [], ""
    for raw_line in text.split("\n"):
        cur = ""
        for word in raw_line.split(" "):
            trial = (cur + " " + word).strip()
            if text_size(draw, trial, font)[0] <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


@dataclass
class TextElement:
    kind: str                 # title | subtitle | bubble | annotation
    text: str
    start: float
    end: float
    fade: float = 0.35
    # title/subtitle placement
    x: Optional[float] = None         # screen fraction 0..1 (None = centre)
    y: Optional[float] = None
    size: int = 0                     # 0 = auto by kind
    color: str = "#ffffff"
    # title extras
    subtitle: Optional[str] = None
    band: bool = True                 # dark band behind title
    # bubble
    actor: Optional[str] = None       # anchor actor id (bubble)
    anchor: Optional[Tuple[float, float]] = None   # world point (annotation)
    tail: Optional[Tuple[float, float]] = None     # screen-space tail tip
    bg: str = "#ffffff"
    fg: str = "#1a1a1a"
    outline: bool = True

    def alpha(self, t: float) -> float:
        if t < self.start or t > self.end:
            return 0.0
        a = 1.0
        if self.fade > 0:
            a = min(a, (t - self.start) / self.fade, (self.end - t) / self.fade)
        return max(0.0, min(1.0, a))


def draw_text_layer(img: Image.Image, elements: List[TextElement], t: float,
                    world_to_screen=None) -> None:
    """Composite all text elements for time t onto img (RGBA over RGB)."""
    W, H = img.size
    for el in elements:
        a = el.alpha(t)
        if a <= 0.01:
            continue
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        if el.kind == "title":
            _draw_title(d, el, W, H)
        elif el.kind == "subtitle":
            _draw_subtitle(d, el, W, H)
        elif el.kind == "bubble":
            _draw_bubble(d, el, W, H, world_to_screen)
        elif el.kind == "annotation":
            _draw_annotation(d, el, W, H, world_to_screen)
        if a < 1.0:
            alpha = overlay.getchannel("A").point(lambda v: int(v * a))
            overlay.putalpha(alpha)
        img.paste(overlay, (0, 0), overlay)


def _hex(s: str, default=(255, 255, 255)):
    try:
        s = s.lstrip("#")
        if len(s) == 3:
            s = "".join(c * 2 for c in s)
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return default


def _draw_title(d, el, W, H):
    size = el.size or int(H * 0.085)
    font = load_font(size, bold=True, text=el.text)
    tw, th = text_size(d, el.text, font)
    cx = (el.x if el.x is not None else 0.5) * W
    cy = (el.y if el.y is not None else 0.26) * H
    sub_th = 0
    if el.subtitle:
        sf = load_font(int(size * 0.42), bold=False, text=el.subtitle)
        _, sub_th = text_size(d, el.subtitle, sf)
    if el.band:
        # compact band hugging the text block, full width, gentle alpha
        pad_v = th * 0.55
        band_top = cy - th / 2 - pad_v
        band_bot = cy + th / 2 + pad_v + (sub_th + th * 0.5 if el.subtitle else 0)
        d.rectangle([0, band_top, W, band_bot], fill=(10, 12, 20, 150))
    d.text((cx - tw / 2, cy - th / 2), el.text, font=font, fill=_hex(el.color) + (255,))
    if el.subtitle:
        sw, _ = text_size(d, el.subtitle, sf)
        d.text((cx - sw / 2, cy + th * 0.72), el.subtitle, font=sf,
               fill=_hex(el.color, (255, 255, 255)) + (235,))


def _draw_subtitle(d, el, W, H):
    size = el.size or int(H * 0.045)
    font = load_font(size, bold=True, text=el.text)
    max_w = int(W * 0.8)
    lines = wrap_text(d, el.text, font, max_w)
    line_h = size * 1.35
    total_h = line_h * len(lines)
    cy = H * 0.92 - total_h
    for i, line in enumerate(lines):
        tw, th = text_size(d, line, font)
        y = cy + i * line_h
        d.text(((W - tw) / 2, y), line, font=font, fill=_hex(el.color) + (255,),
               stroke_width=max(2, size // 16), stroke_fill=(0, 0, 0, 220))


def _draw_bubble(d, el, W, H, world_to_screen):
    size = el.size or int(H * 0.036)
    font = load_font(size, bold=False, text=el.text)
    max_w = int(W * 0.30)
    lines = wrap_text(d, el.text, font, max_w)
    line_h = size * 1.32
    tw = max(text_size(d, line, font)[0] for line in lines)
    bw = tw + size * 1.6
    bh = line_h * len(lines) + size * 1.1

    # tail target
    tip = None
    if el.tail is not None:
        tip = el.tail
    elif el.actor and world_to_screen is not None and el.anchor is None:
        tip = None  # renderer injects .tail each frame via anchor_actor
    if getattr(el, "_tail_pos", None):
        tip = el._tail_pos

    # default position: upper-left-ish, nudged toward anchor
    bx = (el.x if el.x is not None else 0.30) * W - bw / 2
    by = (el.y if el.y is not None else 0.16) * H
    if tip:
        if tip[0] < W / 2:
            bx = min(tip[0] + 40, W - bw - 20)
        else:
            bx = max(tip[0] - bw - 40, 20)
        by = max(min(tip[1] - bh - 46, H * 0.6), 16)
    bx = max(12, min(bx, W - bw - 12))

    # bubble body
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=int(bh * 0.28),
                        fill=_hex(el.bg) + (246,), outline=(40, 40, 40, 255), width=3)
    if tip:
        # triangle tail from bubble bottom edge to tip
        mx = max(bx + 30, min(tip[0], bx + bw - 30))
        side = 16 if tip[0] >= mx else -16
        d.polygon([(mx - 14, by + bh - 2), (mx + 14, by + bh - 2), (tip[0], tip[1])],
                  fill=_hex(el.bg) + (246,))
    ty = by + size * 0.55
    for line in lines:
        lw, _ = text_size(d, line, font)
        d.text((bx + (bw - lw) / 2, ty), line, font=font, fill=_hex(el.fg, (30, 30, 30)) + (255,))
        ty += line_h


def _draw_annotation(d, el, W, H, world_to_screen):
    size = el.size or int(H * 0.032)
    font = load_font(size, bold=True, text=el.text)
    tw, th = text_size(d, el.text, font)
    pt = None
    if el.tail and world_to_screen:
        pt = world_to_screen(el.tail)
    cx = (el.x if el.x is not None else 0.5) * W
    cy = (el.y if el.y is not None else 0.3) * H
    if pt:
        d.line([(cx, cy + th / 2), pt], fill=(255, 210, 60, 230), width=4)
        d.ellipse([pt[0] - 6, pt[1] - 6, pt[0] + 6, pt[1] + 6], fill=(255, 210, 60, 230))
    pad = size * 0.5
    d.rounded_rectangle([cx - tw / 2 - pad, cy - pad, cx + tw / 2 + pad, cy + th + pad],
                        radius=10, fill=(255, 210, 60, 235))
    d.text((cx - tw / 2, cy), el.text, font=font, fill=(40, 30, 5, 255))
