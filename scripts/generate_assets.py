#!/usr/bin/env python3
"""Render Mars watchface assets for Amazfit Bip 6 (390x450).

Mars completes one full rotation per Earth day (86400 s).
24 frames = 15 degrees / hour. Frame index == local hour.
Texture: NASA Viking-derived equirectangular albedo (threex.planets).
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
ASSETS = ROOT / "assets" / "default"

W, H = 390, 450
MARS_DIAM = 268
MARS_CX, MARS_CY = W // 2, 248
FRAME_COUNT = 48

# Valles Marineris ~59W, 14S. Shift so it faces the camera around 10:00,
# matching the design preview people will see during the day.
VM_LON_DEG = -59.0
SHOWCASE_HOUR = 10.0

INK = (237, 230, 214, 255)  # warm off-white from the preview
INK_RGB = INK[:3]
TIME_FONT_SIZE = 96
DATE_FONT_SIZE = 36
FOOTER_FONT_SIZE = 24


def ensure_dirs() -> None:
    for sub in ("mars", "time", "date", "data", "battery", "fonts"):
        (ASSETS / sub).mkdir(parents=True, exist_ok=True)


def load_texture() -> np.ndarray:
    path = TOOLS / "mars_tex.jpg"
    img = Image.open(path).convert("RGB")
    # Grade toward the rust-orange of the design preview.
    img = ImageEnhance.Color(img).enhance(1.12)
    img = ImageEnhance.Contrast(img).enhance(1.28)
    img = ImageEnhance.Brightness(img).enhance(0.98)
    arr = np.asarray(img, dtype=np.float32)
    arr[..., 0] = np.clip(arr[..., 0] * 1.06, 0, 255)
    arr[..., 1] = np.clip(arr[..., 1] * 0.94, 0, 255)
    arr[..., 2] = np.clip(arr[..., 2] * 0.68, 0, 255)
    return arr


def make_starfield() -> Image.Image:
    rng = np.random.default_rng(24)
    px = np.zeros((H, W, 3), dtype=np.uint8)
    n = 260
    xs = rng.integers(0, W, n)
    ys = rng.integers(0, H, n)
    bright = rng.integers(70, 220, n)
    for x, y, b in zip(xs, ys, bright):
        px[y, x] = (b, b, int(b * 0.95))
        if b > 180 and 0 < x < W - 1 and 0 < y < H - 1:
            dim = b // 3
            px[y, x - 1] = np.maximum(px[y, x - 1], (dim, dim, dim))
            px[y, x + 1] = np.maximum(px[y, x + 1], (dim, dim, dim))
            px[y - 1, x] = np.maximum(px[y - 1, x], (dim, dim, dim))
            px[y + 1, x] = np.maximum(px[y + 1, x], (dim, dim, dim))
    # A few warmer/cooler pinpoints
    for _ in range(18):
        x = int(rng.integers(0, W))
        y = int(rng.integers(0, H))
        if rng.random() < 0.5:
            px[y, x] = (180, 160, 110)
        else:
            px[y, x] = (140, 165, 210)
    return Image.fromarray(px, "RGB")


def render_globe(tex: np.ndarray, lon_offset_rad: float, size: int) -> Image.Image:
    """Orthographic globe, north up, fixed sun, texture rotating under it."""
    th, tw = tex.shape[:2]
    yy, xx = np.mgrid[0:size, 0:size]
    cx = cy = (size - 1) / 2.0
    r = size / 2.0 - 2.0
    dx = (xx - cx) / r
    dy = (yy - cy) / r
    rr = dx * dx + dy * dy
    mask = rr <= 1.0
    dz = np.zeros_like(dx)
    dz[mask] = np.sqrt(np.clip(1.0 - rr[mask], 0.0, 1.0))

    x = dx
    y = -dy
    z = dz

    cos_t = math.cos(lon_offset_rad)
    sin_t = math.sin(lon_offset_rad)
    x2 = x * cos_t + z * sin_t
    z2 = -x * sin_t + z * cos_t
    y2 = y

    lon = np.arctan2(x2, z2)
    lat = np.arcsin(np.clip(y2, -1.0, 1.0))
    u = ((lon + math.pi) / (2.0 * math.pi) * tw).astype(np.int32) % tw
    v = ((0.5 - lat / math.pi) * th).astype(np.int32)
    np.clip(v, 0, th - 1, out=v)

    rgb = np.zeros((size, size, 3), dtype=np.float32)
    rgb[mask] = tex[v[mask], u[mask]]

    # Sun from the right-front, slightly above — matches the preview terminator.
    lx, ly, lz = 0.58, 0.18, 0.79
    nrm = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / nrm, ly / nrm, lz / nrm
    ndotl = np.clip(x * lx + y * ly + z * lz, 0.0, 1.0)
    ambient = 0.055
    shade = ambient + (1.0 - ambient) * (ndotl ** 1.35)
    rgb *= shade[..., None]

    # Thin rusty atmosphere on the limb
    limb = np.clip((rr - 0.82) / 0.18, 0.0, 1.0)
    atm = np.zeros((size, size, 3), dtype=np.float32)
    glow = (1.0 - limb) * mask
    atm[..., 0] = 210 * glow * 0.35
    atm[..., 1] = 110 * glow * 0.22
    atm[..., 2] = 50 * glow * 0.10
    rgb = np.clip(rgb + atm, 0, 255)

    alpha = np.zeros((size, size), dtype=np.uint8)
    alpha[mask] = 255
    # Soft edge
    edge = (rr > 0.97) & (rr <= 1.02)
    fade = np.clip((1.02 - np.sqrt(np.clip(rr, 0, 4))) / 0.05, 0, 1)
    alpha[edge] = (fade[edge] * 255).astype(np.uint8)

    rgba = np.dstack([rgb.astype(np.uint8), alpha])
    img = Image.fromarray(rgba, "RGBA")
    return img.filter(ImageFilter.GaussianBlur(radius=0.4))


def hour_to_lon(hour_float: float) -> float:
    """Longitude of the sub-camera meridian.

    One Earth day = one rotation. Increasing time brings new eastern
    longitudes into view (west-to-east planetary rotation).
    """
    day_frac = (hour_float % 24.0) / 24.0
    rot = day_frac * 360.0
    # At SHOWCASE_HOUR, Valles Marineris faces the camera.
    lon = VM_LON_DEG - rot + (SHOWCASE_HOUR / 24.0) * 360.0
    return math.radians(lon)


def composite_frame(starfield: Image.Image, globe: Image.Image) -> Image.Image:
    frame = starfield.copy()
    gx = MARS_CX - globe.size[0] // 2
    gy = MARS_CY - globe.size[1] // 2
    frame.paste(globe, (gx, gy), globe)
    return frame


def font_path() -> Path:
    p = TOOLS / "BlackOpsOne-Regular.ttf"
    if not p.exists():
        p = TOOLS / "StardosStencil-Bold.ttf"
    return p


def load_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path()), size=size)


def render_glyph(
    text: str,
    font: ImageFont.FreeTypeFont,
    padding: tuple[int, int] = (2, 2),
    box: tuple[int, int] | None = None,
) -> Image.Image:
    dummy = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if box:
        w, h = box
    else:
        w, h = tw + padding[0] * 2, th + padding[1] * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x = (w - tw) // 2 - bbox[0]
    y = (h - th) // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=INK)
    return img


def _crop_ink(img: Image.Image, pad: int) -> Image.Image:
    ink = img.split()[-1].getbbox()
    if not ink:
        return img
    l, t, r, b = ink
    l = max(0, l - pad)
    t = max(0, t - pad)
    r = min(img.size[0], r + pad)
    b = min(img.size[1], b + pad)
    return img.crop((l, t, r, b))


def generate_time_digits() -> dict:
    font = load_font(TIME_FONT_SIZE)
    dummy = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    bboxes = {str(i): draw.textbbox((0, 0), str(i), font=font) for i in range(10)}
    max_w = max(b[2] - b[0] for b in bboxes.values())
    top = min(b[1] for b in bboxes.values())
    bot = max(b[3] for b in bboxes.values())
    pad = 3
    canvas_w = max_w + 24
    canvas_h = (bot - top) + 24

    out = ASSETS / "time"
    digit_w = 0
    digit_h = 0
    for i in range(10):
        img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        bb = bboxes[str(i)]
        gw = bb[2] - bb[0]
        x = (canvas_w - gw) // 2 - bb[0]
        y = 12 - top
        d.text((x, y), str(i), font=font, fill=INK)
        cropped = _crop_ink(img, pad)
        cropped.save(out / f"{i}.png")
        digit_w = max(digit_w, cropped.size[0])
        digit_h = max(digit_h, cropped.size[1])

    # Same-size cells so IMG_TIME alignment stays even after crop.
    for i in range(10):
        src = Image.open(out / f"{i}.png")
        cell = Image.new("RGBA", (digit_w, digit_h), (0, 0, 0, 0))
        cell.paste(src, ((digit_w - src.size[0]) // 2, (digit_h - src.size[1]) // 2), src)
        cell.save(out / f"{i}.png")

    sq = 13
    gap = 16
    colon_pad_x = 4
    colon_pad_y = 6
    colon_w = sq + colon_pad_x * 2
    colon_h = sq + gap + sq + colon_pad_y * 2
    colon = Image.new("RGBA", (colon_w, colon_h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(colon)
    x0 = colon_pad_x
    y0 = colon_pad_y
    cd.rectangle([x0, y0, x0 + sq - 1, y0 + sq - 1], fill=INK_RGB)
    y1 = y0 + sq + gap
    cd.rectangle([x0, y1, x0 + sq - 1, y1 + sq - 1], fill=INK_RGB)
    colon.save(out / "colon.png")
    return {
        "w": digit_w,
        "h": digit_h,
        "colon_w": colon_w,
        "colon_h": colon_h,
    }


def generate_digit_set(out: Path, size: int, extras: dict[str, str] | None = None) -> dict:
    font = load_font(size)
    dummy = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    widths, heights = [], []
    for ch in "0123456789":
        b = draw.textbbox((0, 0), ch, font=font)
        widths.append(b[2] - b[0])
        heights.append(b[3] - b[1])
    cell_w = max(widths) + 3
    cell_h = max(heights) + 4
    out.mkdir(parents=True, exist_ok=True)
    for i in range(10):
        render_glyph(str(i), font, box=(cell_w, cell_h)).save(out / f"{i}.png")
    metrics = {"w": cell_w, "h": cell_h}
    extras = extras or {}
    for name, text in extras.items():
        img = render_glyph(text, font)
        img.save(out / f"{name}.png")
        metrics[name + "_w"] = img.size[0]
        metrics[name + "_h"] = img.size[1]
    return metrics


def generate_date_digits() -> dict:
    metrics = generate_digit_set(
        ASSETS / "date",
        DATE_FONT_SIZE,
        {"slash": "/"},
    )
    slash = render_glyph("/", load_font(DATE_FONT_SIZE), box=(max(10, metrics["w"] // 2), metrics["h"]))
    slash.save(ASSETS / "date" / "slash.png")
    metrics["slash_w"] = slash.size[0]
    return metrics


def generate_data_digits() -> dict:
    metrics = generate_digit_set(
        ASSETS / "data",
        FOOTER_FONT_SIZE,
        {"dash": "-", "percent": "%", "label_hr": "HR", "label_bat": "BAT"},
    )
    dash = render_glyph("-", load_font(FOOTER_FONT_SIZE), box=(metrics["w"], metrics["h"]))
    dash.save(ASSETS / "data" / "dash.png")
    percent = render_glyph("%", load_font(FOOTER_FONT_SIZE), box=(metrics["w"] + 6, metrics["h"]))
    percent.save(ASSETS / "data" / "percent.png")
    metrics["percent_w"] = percent.size[0]
    return metrics


def generate_battery_frames() -> dict:
    w, h = 76, 22
    body_w = w - 5
    out = ASSETS / "battery"
    out.mkdir(parents=True, exist_ok=True)
    for level in range(11):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([0, 1, body_w - 1, h - 2], radius=3, outline=INK_RGB, width=2)
        nub_y0 = 6
        nub_y1 = h - 7
        draw.rectangle([body_w - 1, nub_y0, w - 1, nub_y1], fill=INK_RGB)
        inner = [4, 5, body_w - 5, h - 6]
        inner_w = inner[2] - inner[0]
        fill_w = int(round(inner_w * level / 10.0))
        if fill_w > 0:
            draw.rectangle(
                [inner[0], inner[1], inner[0] + fill_w - 1, inner[3]],
                fill=INK_RGB,
            )
        img.save(out / f"{level}.png")
    return {"w": w, "h": h}


def generate_ticks() -> None:
    w, h = 56, 14
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = INK_RGB + (200,)
    gap_start, gap_end = 40, 56
    x = 0
    while x < w:
        if x < gap_start or x >= gap_end:
            draw.rectangle([x, 4, x + 1, h - 4], fill=color)
        x += 6
    img.save(ASSETS / "data" / "ticks.png")


def overlay_preview(frame: Image.Image, time_metrics: dict) -> Image.Image:
    """Store/picker preview at watch resolution, then scale to 266x307."""
    img = frame.convert("RGBA")
    font_lg = load_font(TIME_FONT_SIZE)
    font_sm = load_font(DATE_FONT_SIZE)
    font_ft = load_font(FOOTER_FONT_SIZE)
    draw = ImageDraw.Draw(img)

    def center_text(text, font, cy):
        b = draw.textbbox((0, 0), text, font=font)
        tw = b[2] - b[0]
        th = b[3] - b[1]
        x = (W - tw) // 2 - b[0]
        y = cy - th // 2 - b[1]
        draw.text((x, y), text, font=font, fill=INK)

    center_text("10:09", font_lg, 56)
    center_text("9/18", font_sm, 108)

    hr = "HR 72"
    b = draw.textbbox((0, 0), hr, font=font_ft)
    draw.text((32 - b[0], 400 - b[1]), hr, font=font_ft, fill=INK)
    bar = Image.open(ASSETS / "battery" / "6.png")
    img.alpha_composite(bar.convert("RGBA"), (284, 400))
    return img.convert("RGB")


def generate_icon(globe: Image.Image) -> None:
    icon = Image.new("RGBA", (128, 128), (0, 0, 0, 255))
    g = globe.resize((120, 120), Image.Resampling.LANCZOS)
    icon.paste(g, (4, 4), g)
    icon.save(ASSETS / "icon.png")
    icon.save(ROOT / "icon.png")


def copy_font() -> None:
    src = font_path()
    dest = ASSETS / "fonts" / src.name
    dest.write_bytes(src.read_bytes())


def write_metrics(time_metrics: dict, date_metrics: dict, data_metrics: dict) -> None:
    total_time_w = time_metrics["w"] * 6 + time_metrics["colon_w"] * 2
    start_x = (W - total_time_w) // 2
    text = f"""// Auto-generated by scripts/generate_assets.py
export const LAYOUT = {{
  W: {W},
  H: {H},
  TIME_X: {start_x},
  TIME_Y: 26,
  TIME_DIGIT_W: {time_metrics["w"]},
  TIME_DIGIT_H: {time_metrics["h"]},
  TIME_COLON_W: {time_metrics["colon_w"]},
  DATE_Y: 82,
  DATE_H: {date_metrics["h"]},
  DATE_DIGIT_W: {date_metrics["w"]},
  DATE_SLASH_W: {date_metrics.get("slash_w", 10)},
  FOOTER_Y: 396,
  DATA_DIGIT_W: {data_metrics["w"]},
  DATA_DIGIT_H: {data_metrics["h"]},
  LABEL_HR_W: {data_metrics.get("label_hr_w", 34)},
  LABEL_BAT_W: {data_metrics.get("label_bat_w", 46)},
  PERCENT_W: {data_metrics.get("percent_w", 22)},
  FRAME_COUNT: {FRAME_COUNT},
  FONT: 'fonts/{font_path().name}',
}}
"""
    (ROOT / "watchface" / "layout.js").write_text(text, encoding="utf-8")


def main() -> None:
    import sys

    glyphs_only = "--glyphs" in sys.argv
    ensure_dirs()
    copy_font()

    showcase = None
    if not glyphs_only:
        print("loading texture...")
        tex = load_texture()
        print("starfield...")
        stars = make_starfield()
        stars.save(ASSETS / "starfield.png")

        print(f"rendering {FRAME_COUNT} mars frames...")
        hours_per_frame = 24.0 / FRAME_COUNT
        showcase_i = int(round(SHOWCASE_HOUR / hours_per_frame)) % FRAME_COUNT
        for i in range(FRAME_COUNT):
            lon = hour_to_lon(i * hours_per_frame)
            globe = render_globe(tex, lon, MARS_DIAM)
            frame = composite_frame(stars, globe)
            dest = ASSETS / "mars" / f"{i:02d}.png"
            frame.save(dest, optimize=True, compress_level=9)
            print(f"  {dest.name} {dest.stat().st_size // 1024} KB")
            if i == showcase_i:
                showcase = (frame, globe)
    else:
        frame = Image.open(ASSETS / "mars" / f"{int(SHOWCASE_HOUR):02d}.png")
        showcase = (frame, None)

    print("glyphs...")
    time_metrics = generate_time_digits()
    date_metrics = generate_date_digits()
    data_metrics = generate_data_digits()
    generate_battery_frames()
    generate_ticks()
    write_metrics(time_metrics, date_metrics, data_metrics)

    assert showcase is not None
    frame, globe = showcase
    preview = overlay_preview(frame, time_metrics)
    preview.save(ASSETS / "preview.png", optimize=True)
    picker = preview.resize((266, 307), Image.Resampling.LANCZOS)
    picker.save(ASSETS / "preview_picker.png", optimize=True)
    if globe is not None:
        generate_icon(globe)

    preview.save(TOOLS / "watch_preview.png")
    print("done")
    print("time cell", time_metrics)
    print("date cell", date_metrics)
    print("data cell", data_metrics)


if __name__ == "__main__":
    main()
