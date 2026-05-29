from __future__ import annotations

import math
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


OUT_DIR = Path(__file__).resolve().parent
MP4_PATH = OUT_DIR / "earth_moon_tides_barycenter.mp4"
PREVIEW_PATH = OUT_DIR / "earth_moon_tides_barycenter_preview.png"

W, H = 1280, 720
FPS = 30
DURATION = 18
N_FRAMES = FPS * DURATION
SCALE = 2


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size * SCALE)
        except OSError:
            pass
    return ImageFont.load_default()


FONT_TITLE = font(28, True)
FONT_LABEL = font(18, True)
FONT_SMALL = font(14)
FONT_CAPTION = font(22, True)
FONT_NOTE = font(15)


def sxy(x: float, y: float) -> tuple[int, int]:
    return round(x * SCALE), round(y * SCALE)


def box(cx: float, cy: float, rx: float, ry: float | None = None) -> tuple[int, int, int, int]:
    ry = rx if ry is None else ry
    return (
        round((cx - rx) * SCALE),
        round((cy - ry) * SCALE),
        round((cx + rx) * SCALE),
        round((cy + ry) * SCALE),
    )


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
) -> None:
    x, y = sxy(*xy)
    bbox = draw.textbbox((0, 0), text, font=fnt)
    draw.text((x - (bbox[2] - bbox[0]) / 2, y - (bbox[3] - bbox[1]) / 2), text, font=fnt, fill=fill)


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    fill: tuple[int, int, int],
    width: int = 5,
) -> None:
    sx, sy = start
    ex, ey = end
    draw.line([sxy(sx, sy), sxy(ex, ey)], fill=fill, width=width * SCALE)
    ang = math.atan2(ey - sy, ex - sx)
    head_len = 16
    spread = 0.55
    pts = [
        sxy(ex, ey),
        sxy(ex - head_len * math.cos(ang - spread), ey - head_len * math.sin(ang - spread)),
        sxy(ex - head_len * math.cos(ang + spread), ey - head_len * math.sin(ang + spread)),
    ]
    draw.polygon(pts, fill=fill)


def draw_rotated_ellipse(
    layer: Image.Image,
    center: tuple[float, float],
    radii: tuple[float, float],
    angle: float,
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int] | None = None,
    width: int = 2,
) -> None:
    cx, cy = center
    rx, ry = radii
    t = np.linspace(0, 2 * math.pi, 220)
    ca, sa = math.cos(angle), math.sin(angle)
    xs = cx + rx * np.cos(t) * ca - ry * np.sin(t) * sa
    ys = cy + rx * np.cos(t) * sa + ry * np.sin(t) * ca
    pts = [sxy(float(x), float(y)) for x, y in zip(xs, ys)]
    d = ImageDraw.Draw(layer)
    d.polygon(pts, fill=fill)
    if outline:
        d.line(pts + [pts[0]], fill=outline, width=width * SCALE, joint="curve")


def draw_earth(draw: ImageDraw.ImageDraw, earth: tuple[float, float], radius: float) -> None:
    ex, ey = earth
    draw.ellipse(box(ex + 5, ey + 7, radius), fill=(0, 25, 45, 130))
    draw.ellipse(box(ex, ey, radius), fill=(21, 111, 177), outline=(142, 219, 255), width=3 * SCALE)
    for i in range(16):
        rr = radius * (1 - i / 18)
        alpha = 28 - i
        col = (38, 161, 219, alpha)
        overlay = Image.new("RGBA", (W * SCALE, H * SCALE), (0, 0, 0, 0))
        ImageDraw.Draw(overlay).ellipse(box(ex - radius * 0.10, ey - radius * 0.12, rr), outline=col, width=SCALE)
    draw.arc(box(ex, ey, radius * 0.86, radius * 0.86), 252, 74, fill=(184, 232, 255), width=2 * SCALE)


def draw_moon(draw: ImageDraw.ImageDraw, moon: tuple[float, float], radius: float) -> None:
    mx, my = moon
    draw.ellipse(box(mx + 4, my + 5, radius), fill=(0, 0, 0, 95))
    draw.ellipse(box(mx, my, radius), fill=(185, 189, 188), outline=(230, 232, 230), width=2 * SCALE)
    craters = [(-0.35, -0.20, 0.16), (0.20, -0.28, 0.11), (0.25, 0.20, 0.18), (-0.12, 0.30, 0.10)]
    for dx, dy, rr in craters:
        draw.ellipse(box(mx + dx * radius, my + dy * radius, rr * radius), fill=(155, 159, 158))


def caption_for(progress: float) -> str:
    if progress < 0.25:
        return "Earth and Moon both orbit their shared center of gravity: the barycenter."
    if progress < 0.50:
        return "For a liquid-covered Earth, the water envelope stretches along the Earth-Moon line."
    if progress < 0.75:
        return "The barycenter motion and lunar gravity make the ocean surface elliptical, not spherical."
    return "High water forms along the long axis; low water forms around the shorter axis."


def render_frame(i: int) -> np.ndarray:
    p = i / (N_FRAMES - 1)
    img = Image.new("RGBA", (W * SCALE, H * SCALE), (9, 16, 27, 255))
    draw = ImageDraw.Draw(img)

    # Background stars.
    rng = np.random.default_rng(14)
    for _ in range(120):
        x = int(rng.integers(0, W)) * SCALE
        y = int(rng.integers(0, H)) * SCALE
        lum = int(rng.integers(80, 190))
        draw.point((x, y), fill=(lum, lum, lum, 160))

    bary = (640, 365)
    earth_radius = 112
    moon_radius = 35
    earth_moon_distance = 345
    bary_offset = earth_radius * 0.73
    orbit_angle = 2 * math.pi * p - 0.12
    ux, uy = math.cos(orbit_angle), math.sin(orbit_angle)
    earth = (bary[0] - bary_offset * ux, bary[1] - bary_offset * uy)
    moon = (bary[0] + (earth_moon_distance - bary_offset) * ux, bary[1] + (earth_moon_distance - bary_offset) * uy)

    draw.ellipse(box(bary[0], bary[1], earth_moon_distance - bary_offset), outline=(85, 110, 145, 80), width=SCALE)
    draw.line([sxy(earth[0], earth[1]), sxy(moon[0], moon[1])], fill=(90, 124, 158, 130), width=SCALE)

    tide_layer = Image.new("RGBA", (W * SCALE, H * SCALE), (0, 0, 0, 0))
    draw_rotated_ellipse(
        tide_layer,
        earth,
        (earth_radius * 1.42, earth_radius * 1.10),
        orbit_angle,
        (30, 159, 220, 138),
        (137, 222, 255, 210),
        2,
    )
    img = Image.alpha_composite(img, tide_layer)
    draw = ImageDraw.Draw(img)

    draw_earth(draw, earth, earth_radius)
    draw_moon(draw, moon, moon_radius)

    # Barycenter marker.
    bx, by = bary
    draw.line([sxy(bx - 10, by), sxy(bx + 10, by)], fill=(255, 209, 83), width=3 * SCALE)
    draw.line([sxy(bx, by - 10), sxy(bx, by + 10)], fill=(255, 209, 83), width=3 * SCALE)
    draw.ellipse(box(bx, by, 4), fill=(255, 209, 83))
    label_x, label_y = bx + 120, by - 44
    draw.line([sxy(bx + 7, by + 7), sxy(label_x - 10, label_y + 10)], fill=(255, 209, 83), width=2 * SCALE)
    draw.rounded_rectangle(
        [(label_x - 10) * SCALE, (label_y - 6) * SCALE, (label_x + 216) * SCALE, (label_y + 52) * SCALE],
        radius=8 * SCALE,
        fill=(9, 16, 27, 205),
    )
    draw.text(sxy(label_x, label_y), "barycenter", font=FONT_LABEL, fill=(255, 226, 142))
    draw.text(sxy(label_x, label_y + 28), "shared center of gravity", font=FONT_SMALL, fill=(225, 231, 238))

    # Tide labels.
    side_x, side_y = -uy * 18, ux * 18
    near = (earth[0] + earth_radius * 1.66 * ux + side_x, earth[1] + earth_radius * 1.66 * uy + side_y)
    far = (earth[0] - earth_radius * 1.66 * ux - side_x, earth[1] - earth_radius * 1.66 * uy - side_y)
    low1 = (earth[0] + earth_radius * 1.30 * -uy, earth[1] + earth_radius * 1.30 * ux)
    low2 = (earth[0] - earth_radius * 1.30 * -uy, earth[1] - earth_radius * 1.30 * ux)
    draw_centered_text(draw, near, "HIGH TIDE", FONT_LABEL, (112, 242, 172))
    draw_centered_text(draw, far, "HIGH TIDE", FONT_LABEL, (112, 242, 172))
    draw_centered_text(draw, low1, "LOW", FONT_SMALL, (204, 225, 240))
    draw_centered_text(draw, low2, "LOW", FONT_SMALL, (204, 225, 240))

    # Force arrows near the system.
    arrow_start = (moon[0] - moon_radius - 75 * ux, moon[1] - 75 * uy)
    arrow_end = (moon[0] - moon_radius - 15 * ux, moon[1] - 15 * uy)
    draw_arrow(draw, arrow_start, arrow_end, (74, 221, 132), width=4)
    moon_label_x = min(max(moon[0] + 58, 70), 980)
    moon_label_y = min(max(moon[1] - 62, 100), 520)
    draw.text(sxy(moon_label_x, moon_label_y), "Moon's gravity", font=FONT_LABEL, fill=(116, 245, 161))
    draw.text(sxy(moon_label_x, moon_label_y + 28), "stronger on near-side ocean", font=FONT_SMALL, fill=(218, 239, 226))

    inertial = (earth[0] - earth_radius * 1.85 * ux, earth[1] - earth_radius * 1.85 * uy)
    draw_arrow(draw, (inertial[0] + 55 * ux, inertial[1] + 55 * uy), inertial, (255, 102, 94), width=4)
    draw.text(sxy(52, 520), "Long-axis water bulge", font=FONT_LABEL, fill=(255, 145, 139))
    draw.text(sxy(52, 548), "liquid surface stretched away from spherical shape", font=FONT_SMALL, fill=(243, 221, 219))

    caption = caption_for(p)
    draw.rounded_rectangle(
        [42 * SCALE, 625 * SCALE, 1238 * SCALE, 682 * SCALE],
        radius=10 * SCALE,
        fill=(15, 28, 46, 225),
        outline=(57, 83, 111, 255),
        width=SCALE,
    )
    draw.text(sxy(64, 640), caption, font=FONT_CAPTION, fill=(239, 246, 255))
    draw.text(
        sxy(64, 676),
        "Simplified scale: the liquid envelope is exaggerated so the elliptical deformation is visible.",
        font=FONT_NOTE,
        fill=(180, 197, 214),
    )

    draw.rounded_rectangle(
        [32 * SCALE, 22 * SCALE, 680 * SCALE, 72 * SCALE],
        radius=8 * SCALE,
        fill=(9, 16, 27, 235),
    )
    draw.text(
        sxy(42, 32),
        "Tides and the Earth-Moon Center of Gravity",
        font=FONT_TITLE,
        fill=(240, 247, 255),
    )

    img = img.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    return np.asarray(img)


def main() -> None:
    writer = imageio.get_writer(
        MP4_PATH,
        fps=FPS,
        codec="libx264",
        quality=8,
        macro_block_size=16,
        ffmpeg_log_level="error",
    )
    try:
        for i in range(N_FRAMES):
            frame = render_frame(i)
            writer.append_data(frame)
            if i == FPS * 2:
                Image.fromarray(frame).save(PREVIEW_PATH)
    finally:
        writer.close()
    print(MP4_PATH)
    print(PREVIEW_PATH)


if __name__ == "__main__":
    main()
