from __future__ import annotations

import math
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
VIDEOS = ROOT / "videos"
W, H = 1280, 720
FPS = 24
DURATION = 12
FRAMES = FPS * DURATION
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


TITLE = font(28, True)
LABEL = font(18, True)
SMALL = font(14)
CAPTION = font(22, True)
TINY = font(12)


def sxy(x: float, y: float) -> tuple[int, int]:
    return round(x * SCALE), round(y * SCALE)


def bbox(cx: float, cy: float, rx: float, ry: float | None = None) -> tuple[int, int, int, int]:
    ry = rx if ry is None else ry
    return (
        round((cx - rx) * SCALE),
        round((cy - ry) * SCALE),
        round((cx + rx) * SCALE),
        round((cy + ry) * SCALE),
    )


def base(title: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (W * SCALE, H * SCALE), (8, 14, 24, 255))
    draw = ImageDraw.Draw(img)
    rng = np.random.default_rng(5)
    for _ in range(130):
        x = int(rng.integers(0, W)) * SCALE
        y = int(rng.integers(0, H)) * SCALE
        lum = int(rng.integers(70, 180))
        draw.point((x, y), fill=(lum, lum, lum, 140))
    draw.rounded_rectangle([32 * SCALE, 22 * SCALE, 900 * SCALE, 74 * SCALE], radius=8 * SCALE, fill=(8, 14, 24, 235))
    draw.text(sxy(42, 32), title, font=TITLE, fill=(242, 247, 255))
    return img, draw


def arrow(draw: ImageDraw.ImageDraw, start, end, fill, width: int = 5) -> None:
    sx, sy = start
    ex, ey = end
    draw.line([sxy(sx, sy), sxy(ex, ey)], fill=fill, width=width * SCALE)
    a = math.atan2(ey - sy, ex - sx)
    for sign in (-1, 1):
        p = (ex - 17 * math.cos(a + sign * 0.55), ey - 17 * math.sin(a + sign * 0.55))
        draw.line([sxy(ex, ey), sxy(*p)], fill=fill, width=width * SCALE)


def centered(draw: ImageDraw.ImageDraw, xy, text: str, fnt, fill) -> None:
    x, y = sxy(*xy)
    b = draw.textbbox((0, 0), text, font=fnt)
    draw.text((x - (b[2] - b[0]) / 2, y - (b[3] - b[1]) / 2), text, font=fnt, fill=fill)


def caption(draw: ImageDraw.ImageDraw, text: str) -> None:
    draw.rounded_rectangle(
        [42 * SCALE, 625 * SCALE, 1238 * SCALE, 682 * SCALE],
        radius=10 * SCALE,
        fill=(15, 28, 46, 225),
        outline=(57, 83, 111, 255),
        width=SCALE,
    )
    draw.text(sxy(64, 641), text, font=CAPTION, fill=(239, 246, 255))


def progress_caption(p: float, lines: list[str]) -> str:
    return lines[min(len(lines) - 1, int(p * len(lines)))]


def earth(draw, cx, cy, r, tilt=0.0):
    draw.ellipse(bbox(cx + 4, cy + 6, r), fill=(0, 0, 0, 80))
    draw.ellipse(bbox(cx, cy, r), fill=(22, 110, 177), outline=(143, 221, 255), width=3 * SCALE)
    ax = math.sin(tilt) * r * 1.25
    ay = math.cos(tilt) * r * 1.25
    draw.line([sxy(cx - ax, cy + ay), sxy(cx + ax, cy - ay)], fill=(255, 232, 132), width=3 * SCALE)


def render_seasons(i: int) -> np.ndarray:
    p = i / (FRAMES - 1)
    img, draw = base("Why Seasons Happen")
    sun = (200, 360)
    draw.ellipse(bbox(*sun, 70), fill=(255, 188, 54), outline=(255, 235, 130), width=3 * SCALE)
    centered(draw, sun, "SUN", LABEL, (70, 35, 5))
    for y in [250, 310, 370, 430, 490]:
        arrow(draw, (290, y), (515, y), (255, 215, 98), 3)
    angle = 2 * math.pi * p
    ex, ey = 760 + 185 * math.cos(angle), 360 + 95 * math.sin(angle)
    earth(draw, ex, ey, 82, tilt=math.radians(23.5))
    draw.ellipse(bbox(760, 360, 185, 95), outline=(83, 111, 145, 150), width=SCALE)
    draw.text(sxy(870, 125), "Axis stays tilted", font=LABEL, fill=(255, 232, 132))
    draw.text(sxy(870, 153), "Sun angle and day length change", font=SMALL, fill=(226, 235, 245))
    caption(draw, progress_caption(p, [
        "Seasons are caused by Earth's tilt, not by being closer to the Sun.",
        "The tilted hemisphere gets higher Sun angles and longer days.",
        "Six months later, the other hemisphere receives the stronger sunlight.",
    ]))
    return finish(img)


def render_sky(i: int) -> np.ndarray:
    p = i / (FRAMES - 1)
    img, draw = base("Why the Sky Is Blue and Sunsets Are Red")
    draw.rectangle([0, 120 * SCALE, W * SCALE, 610 * SCALE], fill=(33, 105, 177, 180))
    draw.ellipse(bbox(640, 690, 620, 150), fill=(22, 94, 58), outline=(83, 173, 119), width=2 * SCALE)
    sun_y = 180 + 260 * p
    draw.ellipse(bbox(132, sun_y, 46), fill=(255, 202, 84))
    ray_color = (255, 235, 150) if p < 0.55 else (255, 119, 78)
    for off in [-40, -10, 20, 50]:
        arrow(draw, (190, sun_y + off), (880, 300 + off * 0.3), ray_color, 3)
    rng = np.random.default_rng(16 + i // 4)
    for _ in range(85):
        x = int(rng.integers(300, 950))
        y = int(rng.integers(170, 490))
        col = (98, 187, 255, 165) if p < 0.60 else (255, 118, 70, 155)
        draw.ellipse(bbox(x, y, 3), fill=col)
    draw.text(sxy(870, 160), "Blue scatters easily", font=LABEL, fill=(144, 211, 255))
    draw.text(sxy(870, 190), "Long sunset path leaves red/orange", font=SMALL, fill=(255, 184, 144))
    caption(draw, progress_caption(p, [
        "Air molecules scatter shorter blue wavelengths more strongly.",
        "That scattered blue light comes from every direction in the daytime sky.",
        "At sunset, sunlight travels through more air, so more blue is removed.",
    ]))
    return finish(img)


def render_lensing(i: int) -> np.ndarray:
    p = i / (FRAMES - 1)
    img, draw = base("How Gravity Bends Light")
    mass = (650, 360)
    for x in range(180, 1120, 80):
        bend = 28 * math.exp(-((x - mass[0]) / 150) ** 2)
        draw.line([sxy(x, 145 + bend), sxy(x, 565 - bend)], fill=(62, 81, 108, 130), width=SCALE)
    for y in range(160, 560, 70):
        pts = []
        for x in np.linspace(170, 1120, 80):
            dy = 42 * math.exp(-((x - mass[0]) / 150) ** 2) * np.sign(y - mass[1])
            pts.append(sxy(float(x), float(y + dy)))
        draw.line(pts, fill=(62, 81, 108, 130), width=SCALE)
    draw.ellipse(bbox(*mass, 62), fill=(26, 26, 36), outline=(190, 190, 214), width=3 * SCALE)
    draw.ellipse(bbox(*mass, 28), fill=(245, 221, 142))
    star = (175, 310)
    draw.ellipse(bbox(*star, 8), fill=(255, 255, 190))
    for side in [-1, 1]:
        pts = []
        for t in np.linspace(0, 1, 90):
            x = star[0] + (1030 - star[0]) * t
            y = star[1] + side * 90 * math.sin(math.pi * t) + 45 * t
            pts.append(sxy(x, y))
        draw.line(pts, fill=(102, 221, 255), width=3 * SCALE)
    draw.text(sxy(710, 235), "mass curves spacetime", font=LABEL, fill=(245, 221, 142))
    draw.text(sxy(910, 405), "light follows the curve", font=LABEL, fill=(123, 228, 255))
    caption(draw, progress_caption(p, [
        "Light does not need to have mass to be affected by gravity.",
        "A massive object curves spacetime around it.",
        "Light follows that curved geometry, producing gravitational lensing.",
    ]))
    return finish(img)


def render_time(i: int) -> np.ndarray:
    p = i / (FRAMES - 1)
    img, draw = base("Why Time Slows Down Near Massive Objects")
    planet = (640, 525)
    draw.ellipse(bbox(*planet, 205), fill=(35, 78, 132), outline=(130, 202, 255), width=3 * SCALE)
    near = (510, 325)
    far = (830, 195)
    draw.line([sxy(*near), sxy(*far)], fill=(70, 98, 132), width=SCALE)
    for pos, label, rate in [(near, "lower clock", 0.70), (far, "higher clock", 1.05)]:
        x, y = pos
        draw.rounded_rectangle([(x - 58) * SCALE, (y - 38) * SCALE, (x + 58) * SCALE, (y + 38) * SCALE], radius=10 * SCALE, fill=(18, 32, 52), outline=(190, 215, 240), width=2 * SCALE)
        hand = 2 * math.pi * ((p * 4 * rate) % 1)
        draw.ellipse(bbox(x, y, 26), outline=(230, 238, 245), width=2 * SCALE)
        draw.line([sxy(x, y), sxy(x + 20 * math.sin(hand), y - 20 * math.cos(hand))], fill=(255, 226, 112), width=3 * SCALE)
        centered(draw, (x, y + 58), label, SMALL, (226, 235, 245))
    draw.text(sxy(770, 480), "closer to mass = slower time", font=LABEL, fill=(255, 226, 112))
    caption(draw, progress_caption(p, [
        "Gravity affects time itself, not just motion.",
        "A clock closer to a massive body ticks slightly slower.",
        "GPS satellites must correct for this or navigation would drift.",
    ]))
    return finish(img)


def render_temperature(i: int) -> np.ndarray:
    p = i / (FRAMES - 1)
    img, draw = base("What Temperature Really Means")
    panels = [(330, "cold", (91, 184, 255), 0.45), (950, "hot", (255, 125, 78), 1.2)]
    for cx, label, col, speed in panels:
        draw.rounded_rectangle([(cx - 250) * SCALE, 150 * SCALE, (cx + 250) * SCALE, 555 * SCALE], radius=10 * SCALE, fill=(16, 29, 47), outline=(70, 98, 130), width=2 * SCALE)
        centered(draw, (cx, 185), label.upper(), LABEL, col)
        rng = np.random.default_rng(25 + int(cx))
        for n in range(28):
            ox = rng.uniform(-190, 190)
            oy = rng.uniform(-135, 145)
            phase = p * speed * 90 + n
            x = cx + ox + 18 * math.sin(phase)
            y = 355 + oy + 18 * math.cos(phase * 1.3)
            draw.ellipse(bbox(x, y, 7), fill=col)
            arrow(draw, (x, y), (x + 22 * speed * math.cos(phase), y + 22 * speed * math.sin(phase)), col, 2)
    caption(draw, progress_caption(p, [
        "Temperature is a measure of average microscopic motion.",
        "Cold matter still has moving particles; they just move less energetically.",
        "Heat is energy transferred from hotter matter to colder matter.",
    ]))
    return finish(img)


def render_electricity(i: int) -> np.ndarray:
    p = i / (FRAMES - 1)
    img, draw = base("How Electricity Actually Moves Through a Wire")
    left, right, top, bottom = 185, 1060, 225, 430
    copper = (214, 134, 65)
    bright = (255, 190, 108)
    field = (255, 226, 112)
    electron = (105, 210, 255)
    ion = (255, 154, 104)
    tungsten = (238, 220, 160)

    # Complete circuit path.
    wire = [(left, bottom), (left, top), (right, top), (right, bottom), (left, bottom)]
    for a, b in zip(wire, wire[1:]):
        draw.line([sxy(*a), sxy(*b)], fill=copper, width=18 * SCALE)
        draw.line([sxy(*a), sxy(*b)], fill=bright, width=6 * SCALE)

    # Battery, switch, and bulb make the circuit recognizable.
    draw.rounded_rectangle([95 * SCALE, 303 * SCALE, 185 * SCALE, 397 * SCALE], radius=8 * SCALE, fill=(28, 42, 62), outline=(230, 238, 245), width=2 * SCALE)
    draw.line([sxy(125, 330), sxy(125, 370)], fill=(230, 238, 245), width=5 * SCALE)
    draw.line([sxy(155, 343), sxy(155, 357)], fill=(230, 238, 245), width=5 * SCALE)
    draw.text(sxy(102, 280), "battery pushes charge", font=SMALL, fill=(226, 235, 245))

    switch_closed = p > 0.14
    draw.line([sxy(492, top), sxy(560, top)], fill=bright, width=6 * SCALE)
    if switch_closed:
        draw.line([sxy(560, top), sxy(635, top)], fill=bright, width=6 * SCALE)
    else:
        draw.line([sxy(560, top), sxy(625, top - 42)], fill=(230, 238, 245), width=5 * SCALE)
    draw.text(sxy(515, 181), "switch closes", font=SMALL, fill=(226, 235, 245))

    bulb_y = 328
    draw.ellipse(bbox(right, bulb_y, 58), outline=(240, 240, 190), width=5 * SCALE)
    # Filament: the high-resistance part where energy becomes heat/light.
    filament = []
    for t in np.linspace(0, 1, 90):
        x = right - 30 + 60 * t
        y = bulb_y + 10 * math.sin(t * 7 * math.pi)
        filament.append(sxy(x, y))
    draw.line(filament, fill=tungsten, width=4 * SCALE)
    lit = p > 0.34
    if lit:
        glow = int(120 + 70 * math.sin(p * 12 * math.pi) ** 2)
        draw.ellipse(bbox(right, bulb_y, 76), fill=(255, 231, 95, glow))
        draw.line(filament, fill=(255, 246, 143), width=5 * SCALE)
    draw.text(sxy(1000, 405), "tungsten filament", font=SMALL, fill=(226, 235, 245))

    # Slow electron drift along the wire.
    path_points = []
    for x in np.linspace(left, right, 26):
        path_points.append((x, top))
    for y in np.linspace(top, bottom, 9):
        path_points.append((right, y))
    for x in np.linspace(right, left, 26):
        path_points.append((x, bottom))
    for y in np.linspace(bottom, top, 9):
        path_points.append((left, y))
    drift = p * 4.0
    for n, (x, y) in enumerate(path_points):
        phase = drift + n * 0.35
        dx = 5 * math.sin(phase)
        dy = 5 * math.cos(phase * 1.2)
        draw.ellipse(bbox(x + dx, y + dy, 4), fill=electron)

    # Fast field/energy front propagating around the whole circuit after the switch closes.
    if p > 0.14:
        q = min(1.0, (p - 0.14) / 0.24)
        segments = [
            ((560, top), (right, top)),
            ((right, top), (right, bottom)),
            ((right, bottom), (left, bottom)),
            ((left, bottom), (left, top)),
            ((left, top), (560, top)),
        ]
        total = [500, 240, 850, 240, 350]
        travel = q * sum(total)
        used = 0
        for (a, b), length in zip(segments, total):
            local = max(0, min(1, (travel - used) / length))
            used += length
            if local <= 0:
                continue
            sx, sy = a
            ex, ey = b
            x2 = sx + (ex - sx) * local
            y2 = sy + (ey - sy) * local
            draw.line([sxy(sx, sy), sxy(x2, y2)], fill=field, width=4 * SCALE)
            for offset in [-28, 28]:
                if abs(ex - sx) > abs(ey - sy):
                    draw.line([sxy(sx, sy + offset), sxy(x2, y2 + offset)], fill=(255, 226, 112, 120), width=2 * SCALE)
                else:
                    draw.line([sxy(sx + offset, sy), sxy(x2 + offset, y2)], fill=(255, 226, 112, 120), width=2 * SCALE)
        draw.text(sxy(585, 135), "field sets up the push", font=LABEL, fill=field)

    # Microscopic view of the wire and filament.
    zoom = [80 * SCALE, 485 * SCALE, 1200 * SCALE, 610 * SCALE]
    draw.rounded_rectangle(zoom, radius=10 * SCALE, fill=(14, 27, 45), outline=(62, 90, 120), width=2 * SCALE)
    draw.text(sxy(105, 500), "inside the metal", font=LABEL, fill=(238, 245, 255))
    draw.text(sxy(105, 528), "Cu+ ions stay fixed; mobile electrons drift through the lattice", font=SMALL, fill=(206, 221, 237))

    lattice_y = 580
    xs = list(range(370, 860, 42))
    for idx, x in enumerate(xs):
        y = lattice_y + (idx % 2) * 14
        draw.ellipse(bbox(x, y, 13), fill=ion, outline=(255, 207, 172), width=SCALE)
        centered(draw, (x, y), "Cu+", TINY, (60, 22, 12))
        next_x = x + 22 + 18 * ((p * 3 + idx * 0.07) % 1)
        draw.ellipse(bbox(next_x, y - 22, 5), fill=electron)
    for idx in range(len(xs) - 1):
        x1 = xs[idx] + 15
        x2 = xs[idx + 1] - 15
        y1 = lattice_y + (idx % 2) * 14 - 22
        y2 = lattice_y + ((idx + 1) % 2) * 14 - 22
        arrow(draw, (x1, y1), (x2, y2), electron, 2)

    arrow(draw, (410, 545), (555, 545), electron, 3)
    draw.text(sxy(420, 520), "electron flow (-)", font=SMALL, fill=electron)
    arrow(draw, (725, 545), (580, 545), (255, 178, 104), 3)
    draw.text(sxy(610, 520), "conventional current (+)", font=SMALL, fill=(255, 178, 104))

    filament_x = 965
    draw.text(sxy(910, 500), "filament/device", font=LABEL, fill=tungsten)
    for n in range(7):
        x = filament_x + n * 24
        y = 555 + 18 * math.sin(n + p * 9)
        draw.ellipse(bbox(x, y, 10), fill=tungsten, outline=(255, 244, 190), width=SCALE)
        if lit:
            draw.line([sxy(x - 11, y - 19), sxy(x + 11, y - 31)], fill=(255, 117, 80), width=2 * SCALE)
            draw.line([sxy(x + 13, y + 17), sxy(x + 27, y + 25)], fill=(255, 117, 80), width=2 * SCALE)
    draw.text(sxy(900, 590), "more collisions = heat/light or motor work", font=SMALL, fill=(255, 206, 144))

    draw.text(sxy(230, 456), "electron drift is slow", font=LABEL, fill=electron)
    draw.text(sxy(230, 478), "the electric field push appears around the circuit quickly", font=SMALL, fill=(226, 235, 245))
    caption(draw, progress_caption(p, [
        "The battery sets up an electric field that pushes mobile electrons through the metal.",
        "In the wire, electrons drift through a lattice of positive copper ions.",
        "In a filament or motor, collisions and resistance turn that electrical energy into heat, light, or motion.",
    ]))
    return finish(img)


def render_buoyancy(i: int) -> np.ndarray:
    p = i / (FRAMES - 1)
    img, draw = base("Why Boats Float and Submarines Sink")
    draw.rectangle([0, 360 * SCALE, W * SCALE, H * SCALE], fill=(20, 94, 151))
    for x in range(0, W + 80, 80):
        y = 360 + 8 * math.sin(p * 2 * math.pi + x / 80)
        draw.arc([x * SCALE, (y - 20) * SCALE, (x + 90) * SCALE, (y + 20) * SCALE], 0, 180, fill=(116, 211, 255), width=2 * SCALE)
    boat = [(320, 330), (585, 330), (535, 420), (370, 420)]
    draw.polygon([sxy(*pt) for pt in boat], fill=(196, 108, 62), outline=(245, 178, 120))
    displaced = [(355, 420), (550, 420), (510, 470), (395, 470)]
    draw.polygon([sxy(*pt) for pt in displaced], fill=(69, 159, 216, 160))
    arrow(draw, (455, 455), (455, 350), (112, 240, 160), 5)
    arrow(draw, (455, 282), (455, 375), (255, 120, 104), 5)
    sub_y = 455 + 55 * math.sin(p * 2 * math.pi)
    draw.rounded_rectangle([760 * SCALE, (sub_y - 30) * SCALE, 1030 * SCALE, (sub_y + 30) * SCALE], radius=30 * SCALE, fill=(86, 101, 118), outline=(206, 215, 225), width=2 * SCALE)
    draw.text(sxy(735, 250), "ballast changes density", font=LABEL, fill=(226, 235, 245))
    caption(draw, progress_caption(p, [
        "Water pushes upward on anything that displaces it.",
        "Floating happens when upward buoyancy balances weight.",
        "Submarines sink or rise by changing their average density with ballast.",
    ]))
    return finish(img)


def render_airplanes(i: int) -> np.ndarray:
    p = i / (FRAMES - 1)
    img, draw = base("Why Airplanes Fly")
    wing = [(420, 330), (785, 300), (880, 332), (780, 365), (420, 365)]
    draw.polygon([sxy(*pt) for pt in wing], fill=(185, 197, 208), outline=(242, 248, 255))
    for y in [235, 270, 410, 450]:
        pts = []
        for t in np.linspace(0, 1, 90):
            x = 140 + 930 * t
            curve = -42 * math.exp(-((x - 630) / 200) ** 2) if y < 330 else 26 * math.exp(-((x - 630) / 190) ** 2)
            pts.append(sxy(x, y + curve + 8 * math.sin(8 * t + p * 5)))
        draw.line(pts, fill=(106, 211, 255), width=3 * SCALE)
    arrow(draw, (670, 390), (670, 235), (116, 245, 161), 6)
    arrow(draw, (645, 385), (645, 500), (255, 132, 112), 5)
    draw.text(sxy(710, 220), "lift", font=LABEL, fill=(116, 245, 161))
    draw.text(sxy(690, 505), "air deflected downward", font=LABEL, fill=(255, 157, 138))
    caption(draw, progress_caption(p, [
        "A wing makes air speed and pressure differ around it.",
        "The wing also deflects air downward; the air pushes the wing upward.",
        "The common 'equal transit time' explanation is not the real reason.",
    ]))
    return finish(img)


def render_satellites(i: int) -> np.ndarray:
    p = i / (FRAMES - 1)
    img, draw = base("Why Satellites Do Not Fall Straight Down")
    earth_pos = (405, 380)
    draw.ellipse(bbox(*earth_pos, 118), fill=(28, 111, 176), outline=(138, 221, 255), width=3 * SCALE)
    draw.ellipse(bbox(*earth_pos, 190), outline=(73, 105, 142), width=SCALE)
    a = 2 * math.pi * p
    sat = (earth_pos[0] + 190 * math.cos(a), earth_pos[1] + 190 * math.sin(a))
    draw.ellipse(bbox(*sat, 13), fill=(230, 235, 240))
    arrow(draw, sat, (sat[0] - 80 * math.cos(a), sat[1] - 80 * math.sin(a)), (255, 130, 112), 4)
    arrow(draw, sat, (sat[0] - 80 * math.sin(a), sat[1] + 80 * math.cos(a)), (116, 230, 255), 4)
    draw.text(sxy(145, 145), "gravity pulls inward", font=LABEL, fill=(255, 130, 112))
    draw.text(sxy(145, 175), "sideways speed keeps missing Earth", font=SMALL, fill=(216, 232, 245))
    far_x = 930
    draw.ellipse(bbox(far_x, 390, 8), fill=(230, 235, 240))
    for r in [70, 130, 195]:
        draw.ellipse(bbox(far_x, 390, r), outline=(70, 92, 120, 90), width=SCALE)
    draw.text(sxy(820, 150), "far from major masses", font=LABEL, fill=(226, 235, 245))
    draw.text(sxy(790, 180), "gravity is tiny, so motion is nearly straight drift", font=SMALL, fill=(190, 207, 224))
    caption(draw, progress_caption(p, [
        "Near a planet, a satellite is falling, but it has sideways speed.",
        "It keeps falling around Earth instead of into Earth.",
        "Far from strong gravity sources, pull becomes tiny and motion looks like floating drift.",
    ]))
    return finish(img)


def finish(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGB").resize((W, H), Image.Resampling.LANCZOS))


VIDEOS_TO_RENDER = [
    ("02_seasons", "why_seasons_happen.mp4", render_seasons, "Why Seasons Happen"),
    ("03_sky_color", "why_sky_blue_sunsets_red.mp4", render_sky, "Why the Sky Is Blue and Sunsets Are Red"),
    ("04_gravity_bends_light", "gravity_bends_light.mp4", render_lensing, "How Gravity Bends Light"),
    ("05_gravity_time", "gravity_slows_time.mp4", render_time, "Why Time Slows Down Near Massive Objects"),
    ("06_temperature", "what_temperature_means.mp4", render_temperature, "What Temperature Really Means"),
    ("07_electricity_wire", "electricity_in_wire.mp4", render_electricity, "How Electricity Actually Moves Through a Wire"),
    ("08_buoyancy", "boats_float_submarines_sink.mp4", render_buoyancy, "Why Boats Float and Submarines Sink"),
    ("09_airplanes_lift", "why_airplanes_fly.mp4", render_airplanes, "Why Airplanes Fly"),
    ("10_satellites_orbit", "why_satellites_do_not_fall.mp4", render_satellites, "Why Satellites Do Not Fall Straight Down"),
]


def write_notes(folder: Path, title: str, filename: str) -> None:
    folder.joinpath("notes.md").write_text(
        f"# {title}\n\n"
        "## Files\n\n"
        f"- `{filename}`: rendered video\n"
        "- `preview.png`: still preview frame\n\n"
        "## Style\n\n"
        "Plain-language physics explainer with exaggerated visuals where needed for clarity.\n",
        encoding="utf-8",
    )


def write_wrapper(folder: Path, slug: str) -> None:
    folder.joinpath("render.py").write_text(
        "from pathlib import Path\n"
        "import runpy\n\n"
        "root = Path(__file__).resolve().parents[2]\n"
        "script = root / 'tools' / 'render_remaining_videos.py'\n"
        f"runpy.run_path(str(script), run_name='__main__')\n",
        encoding="utf-8",
    )


def render_one(slug: str, filename: str, renderer, title: str) -> None:
    folder = VIDEOS / slug
    folder.mkdir(parents=True, exist_ok=True)
    mp4 = folder / filename
    preview = folder / "preview.png"
    writer = imageio.get_writer(mp4, fps=FPS, codec="libx264", quality=8, macro_block_size=16, ffmpeg_log_level="error")
    try:
        for i in range(FRAMES):
            frame = renderer(i)
            writer.append_data(frame)
            if i == FPS * 2:
                Image.fromarray(frame).save(preview)
    finally:
        writer.close()
    write_notes(folder, title, filename)
    write_wrapper(folder, slug)
    print(mp4)


def main() -> None:
    for item in VIDEOS_TO_RENDER:
        render_one(*item)


if __name__ == "__main__":
    main()
