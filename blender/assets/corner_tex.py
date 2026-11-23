"""Sixty Stories - street corner hero asset: generated texture images (numpy / Pillow).

All images are deterministic and written to blender/out/assets/corner_tex/.  corner.py loads
and packs them.  Masks are Non-Color data; signs / decals are sRGB.

Road masks cover the 20 m x 20 m asset patch x,y in [-10, 10] (image row 0 = y = +10).
  road_a.png  R cracks   G stain/oil/grime   B wet (gutter film + puddle)   A fresh patch
  road_b.png  R sealant (tar overband)   G wheel-path polish   B fine wear/ravelling
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
TEX_DIR = os.path.join(ROOT, "blender", "out", "assets", "corner_tex")
VERSION = "v9"
FONT_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
FONT_S = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
FONT_M = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
FONT_X = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
FONT_R = "/usr/share/fonts/opentype/inter/Inter-Regular.otf"

EXT = 10.0
R_CORNER = 2.0
N = 4096


def font(path, size):
    return ImageFont.truetype(path, size)


def fbm(n, seed, octaves=((6, 1.0), (12, 0.5), (24, 0.25), (48, 0.125), (96, 0.06))):
    from scipy.ndimage import zoom
    rng = np.random.default_rng(seed)
    acc = np.zeros((n, n), np.float32)
    tot = 0.0
    for res, amp in octaves:
        r = rng.random((res + 3, res + 3)).astype(np.float32)
        up = zoom(r, (n + 2 * n / res) / (res + 3), order=3)
        acc += amp * up[:n, :n]
        tot += amp
    acc /= tot
    acc -= acc.min()
    acc /= max(acc.max(), 1e-6)
    return acc


def w2p(x, y, n=N):
    return ((x + EXT) / (2 * EXT) * n, (EXT - y) / (2 * EXT) * n)


def curb_dist(X, Y):
    """Signed distance into the sidewalk from the curb face (negative = road)."""
    d = np.minimum(X, Y)
    corner = (X < R_CORNER) & (Y < R_CORNER)
    dc = R_CORNER - np.hypot(X - R_CORNER, Y - R_CORNER)
    return np.where(corner, dc, d)


def walk(rng, x, y, ang, length, step=0.05, wiggle=0.35):
    pts = [(x, y)]
    s = 0.0
    while s < length:
        ang += rng.gauss(0, wiggle) * step * 4
        x += math.cos(ang) * step
        y += math.sin(ang) * step
        pts.append((x, y))
        s += step
    return pts


def line_path(rng, x0, y0, x1, y1, step=0.05, amp=0.025):
    n = max(2, int(math.hypot(x1 - x0, y1 - y0) / step))
    nx, ny = -(y1 - y0), (x1 - x0)
    ln = math.hypot(nx, ny)
    nx, ny = nx / ln, ny / ln
    ph = [rng.uniform(0, 6.28) for _ in range(3)]
    pts = []
    off = 0.0
    for i in range(n + 1):
        t = i / n
        off += rng.gauss(0, amp * 0.25)
        off *= 0.92
        o = off + amp * (math.sin(t * 9 + ph[0]) * 0.6 + math.sin(t * 23 + ph[1]) * 0.3)
        pts.append((x0 + (x1 - x0) * t + nx * o, y0 + (y1 - y0) * t + ny * o))
    return pts


def draw_poly(dr, pts, width, val=255):
    pp = [w2p(x, y) for x, y in pts]
    dr.line(pp, fill=val, width=max(1, int(round(width))), joint="curve")


def road_masks():
    rng = random.Random(41)
    px = 2 * EXT / N
    c = (np.arange(N) + 0.5) * px - EXT
    X, Y = np.meshgrid(c, -c)          # row 0 -> y = +EXT
    dcurb = -curb_dist(X, Y)           # distance from curb face into the road (m)
    n1 = fbm(N, 1)
    n2 = fbm(N, 2, ((24, 1.0), (48, 0.6), (96, 0.4), (192, 0.25), (384, 0.15)))
    n3 = fbm(N, 3, ((3, 1.0), (6, 0.6), (12, 0.3)))

    # ---------------- cracks
    cr = Image.new("L", (N, N), 0)
    dr = ImageDraw.Draw(cr)
    # longitudinal paving joint on the avenue lane line (x=-3.4) and cross-street lane line
    LANE_J = line_path(random.Random(77), -3.36, -10.2, -3.30, 10.2)
    draw_poly(dr, LANE_J, 2.2)
    draw_poly(dr, line_path(rng, -10.2, -3.45, 0.2, -3.40), 2.0)
    # transverse cracks across the avenue
    for y0 in (9.1, 1.3, -6.2):
        draw_poly(dr, walk(rng, -0.25, y0, math.pi + rng.uniform(-0.1, 0.1), rng.uniform(5, 10), wiggle=0.25), 1.8)
    # hairline random cracks
    for _ in range(40):
        x0, y0 = rng.uniform(-10, 10), rng.uniform(-10, 10)
        draw_poly(dr, walk(rng, x0, y0, rng.uniform(0, 6.28), rng.uniform(0.3, 1.6), wiggle=0.6), 1.0, 170)
    # trench patch edge cracks (cross street, x in [8.6, 9.3])
    for xe in (8.6, 9.3):
        draw_poly(dr, line_path(random.Random(int(xe * 10)), xe, -10.2, xe, 0.05, amp=0.006), 1.6)
    # curb / asphalt joint
    joint = np.clip(1.0 - np.abs(dcurb - 0.006) / 0.006, 0, 1)
    crack = np.asarray(cr, np.float32) / 255.0
    # alligator cracking in the curb-lane wheel path (avenue x -2.6..-1.8, y 6.8..10)
    from scipy.spatial import cKDTree
    pts = np.array([(rng.uniform(-2.9, -1.5), rng.uniform(6.5, 10.3)) for _ in range(260)])
    tree = cKDTree(pts)
    sel = (X > -2.9) & (X < -1.5) & (Y > 6.6) & (Y < 10.2)
    q = np.stack([X[sel], Y[sel]], -1)
    d, _ = tree.query(q, k=2)
    edge = np.clip(1.0 - (d[:, 1] - d[:, 0]) / 0.012, 0, 1)
    fall = np.exp(-((X[sel] + 2.2) / 0.38) ** 2) * np.clip((Y[sel] - 6.7) / 0.6, 0, 1)
    crack[sel] = np.maximum(crack[sel], edge * (fall > 0.35) * (n2[sel] > 0.35))
    crack = np.maximum(crack, joint * 0.8)
    crack = np.asarray(Image.fromarray((crack * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255.0
    crack = np.clip(crack * 1.6, 0, 1)

    # ---------------- stains / oil / grime
    stain = np.zeros((N, N), np.float32)
    for xc in (-1.7, -5.1, -8.5):                       # avenue lane centres (one-way, -Y)
        stain += np.exp(-((X - xc) / 0.42) ** 2) * (0.35 + 0.65 * n1) * 0.65
    for yc in (-1.7, -5.1, -8.5):                       # cross street lane centres
        stain += np.exp(-((Y - yc) / 0.42) ** 2) * (0.35 + 0.65 * n1) * 0.5 * (X > 0.0)
    # heavier where cars queue behind the stop bar (avenue, y 6.8..10)
    stain *= 1.0 + 0.8 * np.clip((Y - 6.6) / 1.5, 0, 1) * (X < 0)
    # drip spots
    drip = (fbm(N, 9, ((64, 1.0), (128, 0.6), (256, 0.4))) > 0.70).astype(np.float32)
    stain += drip * np.exp(-((X + 1.7) / 0.35) ** 2) * 0.8 + drip * np.exp(-((X + 5.1) / 0.35) ** 2) * 0.6
    # grime band along the curb
    stain += np.clip(1.0 - dcurb / 0.55, 0, 1) * (0.4 + 0.6 * n2) * 0.7
    stain = np.clip(stain * (0.6 + 0.6 * n2), 0, 1)

    # ---------------- wet: gutter film along the avenue curb, puddle upstream of the inlet
    wet = np.clip(1.0 - dcurb / (0.20 + 0.25 * n3), 0, 1) * (X < 0.5) * np.clip((Y - 4.6) / 1.0, 0, 1)
    wet *= (0.55 + 0.45 * n1)
    pud = ((X + 0.42) / 0.62) ** 2 + ((Y - 8.55) / 0.72) ** 2 + (n2 - 0.5) * 0.9
    wet = np.maximum(wet, np.clip((1.0 - pud) * 6.0, 0, 1))
    pud2 = ((X + 0.30) / 0.30) ** 2 + ((Y - 6.75) / 0.35) ** 2 + (n2 - 0.5) * 0.8
    wet = np.maximum(wet, np.clip((1.0 - pud2) * 5.0, 0, 1))
    wet = np.clip(wet, 0, 1)

    # ---------------- fresh patches: trench strip (cross street x 8.6..9.3) + utility cut
    patch = (((X > 8.6) & (X < 9.3) & (Y < 0.05)).astype(np.float32))
    patch = np.maximum(patch, ((X > -8.3) & (X < -6.7) & (Y > -4.9) & (Y < -3.6)).astype(np.float32) * 0.65)
    patch = np.maximum(patch, (np.hypot(X + 5.0, Y - 7.6) < 0.62).astype(np.float32) * 0.45)

    # ---------------- sealant overband
    se = Image.new("L", (N, N), 0)
    ds = ImageDraw.Draw(se)
    draw_poly(ds, line_path(random.Random(78), -3.34, -10.2, -3.31, 10.2, amp=0.02), 0.075 / px)
    for xe in (8.6, 9.3):
        draw_poly(ds, line_path(random.Random(int(xe * 10) + 1), xe, -10.2, xe, 0.02, amp=0.015), 0.065 / px)
    seal = np.asarray(se.filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255.0
    seal *= (n2 > 0.22)
    # ---------------- wheel-path polish
    wheel = np.zeros((N, N), np.float32)
    for xc in (-1.7, -5.1, -8.5):
        for o in (-0.82, 0.82):
            wheel += np.exp(-((X - xc - o) / 0.28) ** 2) * (X < 0)
    for yc in (-1.7, -5.1, -8.5):
        for o in (-0.82, 0.82):
            wheel += np.exp(-((Y - yc - o) / 0.28) ** 2) * (Y < 0) * (X > 0)
    wheel = np.clip(wheel, 0, 1)
    rav = fbm(N, 11, ((32, 1.0), (64, 0.7), (128, 0.5), (256, 0.3)))

    a = np.stack([crack, stain, wet, patch], -1)
    # sidewalk corner region (unused by the road) is cleared: context road samples UV (0.999, 0.999)
    a[:8, -8:] = 0
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "RGBA").save(os.path.join(TEX_DIR, "road_a.png"))
    b = np.stack([seal, wheel, rav], -1)
    b[:8, -8:] = 0
    Image.fromarray((np.clip(b, 0, 1) * 255).astype(np.uint8), "RGB").save(os.path.join(TEX_DIR, "road_b.png"))


# =============================================================== cast iron covers
def cover_height(path, n, text_top, text_bot, kind="manhole"):
    S = n
    img = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(img)
    cx = cy = S / 2
    R = S / 2 - 2
    d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=150)
    # outer rim
    d.ellipse((cx - R * 0.985, cy - R * 0.985, cx + R * 0.985, cy + R * 0.985), fill=110)
    if kind == "manhole":
        # waffle / diamond field raised
        field = Image.new("L", (S, S), 150)
        fd = ImageDraw.Draw(field)
        step = S / 26.0
        for i in range(-30, 30):
            for j in range(-30, 30):
                x = cx + (i + 0.5 * (j % 2)) * step
                y = cy + j * step * 0.866
                r = step * 0.30
                fd.regular_polygon((x, y, r), 6, rotation=30, fill=210)
        mask = Image.new("L", (S, S), 0)
        ImageDraw.Draw(mask).ellipse((cx - R * 0.90, cy - R * 0.90, cx + R * 0.90, cy + R * 0.90), fill=255)
        ImageDraw.Draw(mask).ellipse((cx - R * 0.40, cy - R * 0.40, cx + R * 0.40, cy + R * 0.40), fill=0)
        # lettering band (two arcs) cleared
        ring = Image.new("L", (S, S), 0)
        ImageDraw.Draw(ring).ellipse((cx - R * 0.80, cy - R * 0.80, cx + R * 0.80, cy + R * 0.80), fill=255)
        ImageDraw.Draw(ring).ellipse((cx - R * 0.58, cy - R * 0.58, cx + R * 0.58, cy + R * 0.58), fill=0)
        mask = Image.fromarray(np.minimum(np.asarray(mask), 255 - np.asarray(ring)))
        img.paste(field, (0, 0), mask)
        # concentric raised rings
        for rr, w in ((0.90, 6), (0.80, 4), (0.58, 4), (0.40, 6)):
            d.ellipse((cx - R * rr, cy - R * rr, cx + R * rr, cy + R * rr), outline=225, width=w)
        # centre medallion: radial ribs + initials
        for k in range(16):
            a = k * math.pi / 8
            d.line((cx + math.cos(a) * R * 0.17, cy + math.sin(a) * R * 0.17,
                    cx + math.cos(a) * R * 0.38, cy + math.sin(a) * R * 0.38), fill=215, width=8)
        d.ellipse((cx - R * 0.17, cy - R * 0.17, cx + R * 0.17, cy + R * 0.17), fill=140, outline=225, width=5)
        f = font(FONT_X, int(S * 0.055))
        d.text((cx, cy), "B.S.L.", font=f, fill=235, anchor="mm")
        # pick holes
        for a in (0.3, 0.3 + math.pi):
            hx, hy = cx + math.cos(a) * R * 0.69, cy + math.sin(a) * R * 0.69
            d.rounded_rectangle((hx - 14, hy - 7, hx + 14, hy + 7), 6, fill=0)
        arc_text(img, text_top, cx, cy, R * 0.69, S * 0.05, top=True)
        arc_text(img, text_bot, cx, cy, R * 0.69, S * 0.05, top=False)
    else:
        f = font(FONT_X, int(S * 0.15))
        d.ellipse((cx - R * 0.86, cy - R * 0.86, cx + R * 0.86, cy + R * 0.86), outline=220, width=10)
        d.text((cx, cy), text_top, font=f, fill=235, anchor="mm")
        for k in range(24):
            a = k * math.pi / 12
            d.ellipse((cx + math.cos(a) * R * 0.75 - 6, cy + math.sin(a) * R * 0.75 - 6,
                       cx + math.cos(a) * R * 0.75 + 6, cy + math.sin(a) * R * 0.75 + 6), fill=220)
    img = img.filter(ImageFilter.GaussianBlur(1.3))
    img.save(path)


def arc_text(img, text, cx, cy, radius, size, top=True):
    f = font(FONT_X, int(size))
    n = len(text)
    span = min(math.pi * 0.95, n * size * 0.80 / radius)
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        t = (i + 0.5) / n - 0.5
        if top:
            a = -math.pi / 2 + t * span
            rot = -math.degrees(a) - 90
        else:
            a = math.pi / 2 - t * span
            rot = -math.degrees(a) + 90
        tile = Image.new("L", (int(size * 1.6), int(size * 1.6)), 0)
        ImageDraw.Draw(tile).text((tile.width / 2, tile.height / 2), ch, font=f, fill=255, anchor="mm")
        tile = tile.rotate(rot, resample=Image.BICUBIC)
        x = cx + math.cos(a) * radius - tile.width / 2
        y = cy + math.sin(a) * radius - tile.height / 2
        lay = Image.new("L", img.size, 0)
        lay.paste(tile, (int(x), int(y)))
        arr = np.maximum(np.asarray(img), (np.asarray(lay) > 100) * 232)
        img.paste(Image.fromarray(arr.astype(np.uint8)))


# =============================================================== signs & decals
GREEN = (0, 104, 71)


def blade(path, name, suffix, block):
    W, H = 1600, 340
    im = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((10, 10, W - 10, H - 10), 26, outline=(236, 240, 236), width=10)
    f = font(FONT_S, 210)
    fs = font(FONT_S, 120)
    tw = d.textlength(name, font=f)
    sw = d.textlength(suffix, font=fs)
    x0 = (W - tw - sw - 30) / 2
    d.text((x0, H / 2 + 8), name, font=f, fill=(240, 244, 240), anchor="lm")
    d.text((x0 + tw + 30, H / 2 + 46), suffix, font=fs, fill=(240, 244, 240), anchor="ls")
    d.text((60, 52), block, font=font(FONT_S, 48), fill=(240, 244, 240), anchor="lm")
    im.save(path)


def one_way(path):
    W, H = 1100, 380
    im = Image.new("RGB", (W, H), (12, 12, 12))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((8, 8, W - 8, H - 8), 20, outline=(238, 238, 236), width=10)
    pts = [(80, 120), (720, 120), (720, 50), (1030, 190), (720, 330), (720, 260), (80, 260)]
    d.polygon(pts, fill=(238, 238, 236))
    d.text((400, 192), "ONE WAY", font=font(FONT_B, 118), fill=(12, 12, 12), anchor="mm")
    im.save(path)


def no_parking(path):
    W, H = 600, 900
    im = Image.new("RGB", (W, H), (238, 238, 234))
    d = ImageDraw.Draw(im)
    red = (190, 24, 30)
    d.rounded_rectangle((8, 8, W - 8, H - 8), 22, outline=red, width=10)
    d.text((W / 2, 110), "NO", font=font(FONT_X, 150), fill=red, anchor="mm")
    d.text((W / 2, 245), "PARKING", font=font(FONT_X, 112), fill=red, anchor="mm")
    d.text((W / 2, 395), "7AM-7PM", font=font(FONT_B, 96), fill=red, anchor="mm")
    d.text((W / 2, 500), "MON-FRI", font=font(FONT_B, 86), fill=red, anchor="mm")
    d.text((W / 2, 600), "COMMERCIAL", font=font(FONT_S, 56), fill=red, anchor="mm")
    d.text((W / 2, 660), "VEHICLES ONLY", font=font(FONT_S, 56), fill=red, anchor="mm")
    # double arrow
    d.line((110, 790, 490, 790), fill=red, width=22)
    d.polygon([(70, 790), (140, 745), (140, 835)], fill=red)
    d.polygon([(530, 790), (460, 745), (460, 835)], fill=red)
    im.save(path)


def push_button(path):
    W, H = 460, 600
    im = Image.new("RGB", (W, H), (240, 240, 236))
    d = ImageDraw.Draw(im)
    d.rectangle((6, 6, W - 6, H - 6), outline=(20, 20, 20), width=8)
    d.text((W / 2, 80), "PUSH BUTTON", font=font(FONT_B, 58), fill=(15, 15, 15), anchor="mm")
    d.text((W / 2, 150), "FOR", font=font(FONT_B, 50), fill=(15, 15, 15), anchor="mm")
    # walking figure (simple)
    cx, cy = 140, 330
    d.ellipse((cx - 22, cy - 120, cx + 22, cy - 76), fill=(15, 15, 15))
    d.line((cx, cy - 70, cx - 6, cy + 10), fill=(15, 15, 15), width=26)
    d.line((cx - 6, cy + 10, cx - 46, cy + 110), fill=(15, 15, 15), width=22)
    d.line((cx - 6, cy + 10, cx + 40, cy + 110), fill=(15, 15, 15), width=22)
    d.line((cx, cy - 50, cx - 50, cy + 10), fill=(15, 15, 15), width=18)
    d.line((cx, cy - 50, cx + 45, cy), fill=(15, 15, 15), width=18)
    d.text((330, 330), "SIGNAL", font=font(FONT_B, 50), fill=(15, 15, 15), anchor="mm")
    d.polygon([(250, 470), (400, 470), (400, 440), (450, 500), (400, 560), (400, 530), (250, 530)], fill=(15, 15, 15))
    im.save(path)


def ped_face(path, kind, count=None):
    S = 512
    im = Image.new("RGB", (S, S), (6, 6, 6))
    d = ImageDraw.Draw(im)
    lay = Image.new("L", (S, S), 0)
    ld = ImageDraw.Draw(lay)
    if kind == "hand":
        cx, cy = 150, 270
        ld.rounded_rectangle((cx - 70, cy - 40, cx + 70, cy + 120), 40, fill=255)
        for i, (dx, h) in enumerate(((-55, 120), (-18, 150), (18, 145), (52, 115))):
            ld.rounded_rectangle((cx + dx - 16, cy - h, cx + dx + 16, cy), 16, fill=255)
        ld.rounded_rectangle((cx + 55, cy - 10, cx + 120, cy + 30), 18, fill=255)
        col = (255, 120, 20)
        if count is not None:
            f = font(FONT_B, 210)
            ld2 = Image.new("L", (S, S), 0)
            ImageDraw.Draw(ld2).text((375, 265), str(count), font=f, fill=255, anchor="mm")
            led2 = led_mask(ld2)
            im.paste(Image.new("RGB", (S, S), (255, 120, 20)), (0, 0), led2)
    else:
        cx, cy = 360, 260
        ld.ellipse((cx - 30, cy - 160, cx + 30, cy - 100), fill=255)
        ld.line((cx, cy - 90, cx - 8, cy + 30), fill=255, width=40)
        ld.line((cx - 8, cy + 30, cx - 70, cy + 170), fill=255, width=34)
        ld.line((cx - 8, cy + 30, cx + 60, cy + 170), fill=255, width=34)
        ld.line((cx, cy - 70, cx - 70, cy + 10), fill=255, width=28)
        ld.line((cx, cy - 70, cx + 62, cy - 2), fill=255, width=28)
        col = (235, 245, 255)
    im.paste(Image.new("RGB", (S, S), col), (0, 0), led_mask(lay))
    im.save(path)


def led_mask(lay):
    S = lay.size[0]
    a = np.asarray(lay, np.float32) / 255.0
    yy, xx = np.mgrid[0:S, 0:S]
    p = 9.0
    dots = np.clip(1.0 - (np.hypot((xx % p) - p / 2, (yy % p) - p / 2) / 3.6), 0, 1) ** 0.6
    return Image.fromarray((a * dots * 255).astype(np.uint8))


def stickers(path, seed=3):
    """1024x1024 atlas: 4 x 2 grid of stickers (each 256 x 512 cell) + used by UV rects in corner.py."""
    rng = random.Random(seed)
    S = 1024
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cells = [(0, 0), (256, 0), (512, 0), (768, 0), (0, 512), (256, 512), (512, 512), (768, 512)]
    # 0: round band sticker
    d.ellipse((20, 120, 236, 336), fill=(230, 60, 40, 255))
    d.text((128, 228), "GLUM", font=font(FONT_X, 62), fill=(250, 240, 220, 255), anchor="mm")
    # 1: rectangular "hello my name is"-ish (invented)
    d.rectangle((276, 140, 492, 300), fill=(30, 90, 200, 255))
    d.rectangle((286, 205, 482, 290), fill=(245, 245, 240, 255))
    d.text((384, 172), "HI, I'M", font=font(FONT_B, 40), fill=(255, 255, 255, 255), anchor="mm")
    d.text((384, 248), "zeno", font=font(FONT_B, 64), fill=(20, 20, 20, 255), anchor="mm")
    # 2: black sticker with yellow text
    d.rectangle((540, 100, 740, 400), fill=(20, 20, 20, 255))
    d.text((640, 180), "NIGHT", font=font(FONT_X, 54), fill=(250, 210, 40, 255), anchor="mm")
    d.text((640, 250), "MOTH", font=font(FONT_X, 54), fill=(250, 210, 40, 255), anchor="mm")
    d.text((640, 330), "live / thu", font=font(FONT_M, 30), fill=(250, 210, 40, 255), anchor="mm")
    # 3: torn white sticker remains
    poly = [(790, 160), (1000, 150), (990, 260), (930, 250), (900, 330), (800, 320)]
    d.polygon(poly, fill=(225, 222, 210, 255))
    d.text((890, 210), "TOWN", font=font(FONT_B, 40), fill=(80, 80, 80, 255), anchor="mm")
    # 4-7 lower row: flyer (uses two cells wide: 0..512 x 512..1024)
    d.rectangle((20, 530, 492, 1004), fill=(240, 236, 222, 255))
    d.text((256, 600), "ROOM", font=font(FONT_X, 90), fill=(25, 25, 25, 255), anchor="mm")
    d.text((256, 690), "FOR RENT", font=font(FONT_X, 70), fill=(25, 25, 25, 255), anchor="mm")
    for i, ln in enumerate(("sunny, 3rd floor", "near the park", "no smokers please")):
        d.text((256, 770 + 40 * i), ln, font=font(FONT_M, 32), fill=(40, 40, 40, 255), anchor="mm")
    for k in range(8):
        x = 38 + k * 57
        d.line((x, 900, x, 1004), fill=(120, 120, 120, 255), width=2)
        tab = Image.new("RGBA", (100, 40), (0, 0, 0, 0))
        ImageDraw.Draw(tab).text((50, 20), "555-0174", font=font(FONT_M, 22), fill=(40, 40, 40, 255), anchor="mm")
        tab = tab.rotate(90, expand=True)
        im.alpha_composite(tab, (x + 8, 905))
    # torn-off tabs (two missing)
    for k in (2, 5):
        x = 38 + k * 57
        d.rectangle((x + 2, 935, x + 55, 1004), fill=(0, 0, 0, 0))
    # 6: sticker "ANT FARM" green, 7: slap tag
    d.rounded_rectangle((532, 600, 748, 760), 20, fill=(70, 160, 80, 255))
    d.text((640, 680), "ANT FARM", font=font(FONT_X, 40), fill=(250, 250, 240, 255), anchor="mm")
    d.rectangle((780, 560, 1004, 720), fill=(250, 250, 248, 255))
    for k in range(6):
        x0 = 800 + rng.randint(0, 120)
        d.line([(x0, 600 + rng.randint(0, 20)), (x0 + rng.randint(30, 80), 640 + rng.randint(0, 40)),
                (x0 + rng.randint(40, 100), 690)], fill=(20, 20, 140, 255), width=8)
    d.rectangle((560, 800, 980, 980), fill=(250, 220, 60, 255))
    d.text((770, 860), "SIGNAL DIV", font=font(FONT_B, 54), fill=(20, 20, 20, 255), anchor="mm")
    d.text((770, 930), "CAB 4471-B", font=font(FONT_B, 54), fill=(20, 20, 20, 255), anchor="mm")
    im.save(path)


def news_front(path):
    W, H = 700, 900
    im = Image.new("RGB", (W, H), (226, 222, 210))
    d = ImageDraw.Draw(im)
    d.text((W / 2, 70), "The Harbor Ledger", font=font(FONT_X, 66), fill=(20, 20, 20), anchor="mm")
    d.line((30, 120, W - 30, 120), fill=(20, 20, 20), width=4)
    d.text((W / 2, 140), "TUESDAY  NOVEMBER 17   LATE CITY EDITION   $2.50", font=font(FONT_M, 18), fill=(40, 40, 40), anchor="mm")
    d.text((W / 2, 230), "TUNNEL TALKS", font=font(FONT_X, 84), fill=(20, 20, 20), anchor="mm")
    d.text((W / 2, 320), "STALL AGAIN", font=font(FONT_X, 84), fill=(20, 20, 20), anchor="mm")
    d.rectangle((40, 380, 420, 640), fill=(120, 116, 104))
    d.rectangle((60, 400, 400, 620), fill=(160, 150, 130))
    rng = random.Random(4)
    for col in (40, 440):
        for k in range(18):
            y = 660 + k * 13 if col == 40 else 390 + k * 14
            if y > H - 30:
                break
            wdt = rng.randint(180, 230) if col == 440 else rng.randint(300, 370)
            d.line((col, y, col + wdt, y), fill=(90, 90, 90), width=5)
    im.save(path)


def news_decal(path):
    W, H = 800, 300
    im = Image.new("RGB", (W, H), (24, 70, 140))
    d = ImageDraw.Draw(im)
    d.text((W / 2, 110), "The Harbor", font=font(FONT_X, 100), fill=(245, 245, 240), anchor="mm")
    d.text((W / 2, 220), "LEDGER", font=font(FONT_X, 104), fill=(245, 200, 40), anchor="mm")
    im.save(path)


def pay_decal(path):
    W, H = 600, 900
    im = Image.new("RGB", (W, H), (30, 30, 34))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 230), fill=(20, 80, 170))
    d.rounded_rectangle((30, 30, 200, 200), 24, fill=(245, 245, 245))
    d.text((115, 118), "P", font=font(FONT_X, 150), fill=(20, 80, 170), anchor="mm")
    d.text((400, 85), "PAY", font=font(FONT_X, 80), fill=(255, 255, 255), anchor="mm")
    d.text((400, 165), "HERE", font=font(FONT_X, 80), fill=(255, 255, 255), anchor="mm")
    for i, t in enumerate(("1  Enter plate", "2  Insert card or tap", "3  Take receipt")):
        d.text((50, 300 + i * 70), t, font=font(FONT_M, 40), fill=(230, 230, 230), anchor="lm")
    d.text((W / 2, 560), "CITY PARKING  ZONE 47", font=font(FONT_B, 40), fill=(250, 200, 40), anchor="mm")
    d.text((W / 2, 640), "MAX 2 HR  $4.50 / HR", font=font(FONT_B, 40), fill=(230, 230, 230), anchor="mm")
    im.save(path)


def screen(path):
    W, H = 400, 300
    im = Image.new("RGB", (W, H), (20, 40, 46))
    d = ImageDraw.Draw(im)
    d.text((W / 2, 70), "ZONE 47", font=font(FONT_B, 46), fill=(170, 230, 210), anchor="mm")
    d.text((W / 2, 150), "PRESS ANY KEY", font=font(FONT_M, 34), fill=(170, 230, 210), anchor="mm")
    d.text((W / 2, 220), "18:42", font=font(FONT_B, 50), fill=(170, 230, 210), anchor="mm")
    im.save(path)


def leaves(path):
    """Leaf atlas 4 x 2 (each cell 256 px), RGBA, autumn colours, original shapes."""
    rng = random.Random(8)
    S = 256
    im = Image.new("RGBA", (S * 4, S * 2), (0, 0, 0, 0))
    cols = [(150, 96, 30), (120, 72, 28), (178, 128, 40), (96, 64, 30), (140, 110, 50), (110, 50, 24),
            (170, 110, 36), (80, 56, 30)]
    for k in range(8):
        ox, oy = (k % 4) * S, (k // 4) * S
        lay = Image.new("L", (S, S), 0)
        ld = ImageDraw.Draw(lay)
        cx, cy = S / 2, S / 2
        if k % 2 == 0:   # lobed (plane-tree like)
            pts = []
            for i in range(60):
                a = i / 60 * 2 * math.pi
                r = 92 * (0.62 + 0.38 * abs(math.cos(2.5 * a)) ** 0.6)
                pts.append((cx + r * math.cos(a), cy - 10 + r * math.sin(a) * 0.95))
            ld.polygon(pts, fill=255)
        else:            # elliptic pointed
            pts = []
            for i in range(60):
                a = i / 60 * 2 * math.pi
                r = 105 / (1 + 0.6 * abs(math.sin(a)))
                pts.append((cx + 0.45 * r * math.cos(a) * (1.0 + 0.15 * math.sin(a)), cy + r * math.sin(a)))
            ld.polygon(pts, fill=255)
        ld.line((cx, cy + 105, cx, cy + 128), fill=255, width=6)    # stalk
        base = np.zeros((S, S, 4), np.uint8)
        c = cols[k]
        nz = np.asarray(Image.effect_noise((S, S), 40).filter(ImageFilter.GaussianBlur(3)), np.float32) / 255.0
        for ch in range(3):
            base[..., ch] = np.clip(c[ch] * (0.75 + 0.5 * nz), 0, 255)
        tile = Image.fromarray(base, "RGBA")
        td = ImageDraw.Draw(tile)
        td.line((cx, cy - 95, cx, cy + 120), fill=(c[0] // 2 + 60, c[1] // 2 + 50, c[2] // 2 + 20, 255), width=3)
        for j in range(5):
            y = cy - 60 + j * 30
            td.line((cx, y, cx - 50, y - 30), fill=(c[0] // 2 + 50, c[1] // 2 + 40, 30, 255), width=2)
            td.line((cx, y, cx + 50, y - 30), fill=(c[0] // 2 + 50, c[1] // 2 + 40, 30, 255), width=2)
        # dark rot spots
        for j in range(rng.randint(2, 6)):
            x, y, r = rng.uniform(70, 186), rng.uniform(60, 190), rng.uniform(4, 12)
            td.ellipse((x - r, y - r, x + r, y + r), fill=(60, 40, 20, 255))
        tile.putalpha(lay)
        im.paste(tile, (ox, oy))
    im.save(path)


def cup(path):
    W, H = 512, 256
    im = Image.new("RGB", (W, H), (236, 232, 222))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 90, W, 170), fill=(40, 110, 90))
    d.text((W / 2, 130), "MORNING CUP  MORNING CUP", font=font(FONT_B, 38), fill=(236, 232, 222), anchor="mm")
    im.save(path)


def cabinet_tag(path):
    """Invented spray tag: skewed heavy letters, black outline, chrome fill, drips, overspray."""
    W, H = 800, 400
    rng = random.Random(12)
    lay = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(lay)
    f = font(FONT_X, 190)
    x = 40
    for i, ch in enumerate("ZEKO"):
        t = Image.new("L", (260, 300), 0)
        ImageDraw.Draw(t).text((130, 150), ch, font=f, fill=255, anchor="mm")
        t = t.rotate(rng.uniform(-14, 10), resample=Image.BICUBIC, expand=False)
        t = t.transform(t.size, Image.AFFINE, (1, 0.25, -30, 0, 1, 0), resample=Image.BICUBIC)
        lay.paste(Image.fromarray(np.maximum(np.asarray(lay.crop((x, 40 + i * 8, x + 260, 340 + i * 8))), np.asarray(t))), (x, 40 + i * 8))
        x += 150 + rng.randint(-10, 15)
    outline = lay.filter(ImageFilter.MaxFilter(15))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    o = np.asarray(outline, np.float32) / 255.0
    fill = np.asarray(lay, np.float32) / 255.0
    yy = np.linspace(0, 1, H)[:, None]
    arr = np.zeros((H, W, 4), np.float32)
    arr[..., :3] = 12
    grad = 150 + 90 * (1 - yy)
    for c in range(3):
        arr[..., c] = np.where(fill > 0.5, grad + (12 if c == 2 else 0), 14)
    alpha = np.clip(o * 1.0, 0, 1)
    # drips below the letters
    dr = Image.new("L", (W, H), 0)
    dd = ImageDraw.Draw(dr)
    for _ in range(9):
        xx = rng.randint(60, W - 60)
        col_ = np.nonzero(o[:, xx] > 0.5)[0]
        if len(col_) == 0:
            continue
        y0 = col_.max()
        dd.line((xx, y0, xx, min(H - 4, y0 + rng.randint(15, 70))), fill=255, width=rng.randint(3, 6))
        dd.ellipse((xx - 4, y0 + 10, xx + 4, y0 + 18), fill=0)
    dra = np.asarray(dr, np.float32) / 255.0
    alpha = np.maximum(alpha, dra)
    spray = np.asarray(outline.filter(ImageFilter.GaussianBlur(10)), np.float32) / 255.0 * 0.35
    noise = np.random.default_rng(3).random((H, W)) < spray
    alpha = np.maximum(alpha, noise * 0.8)
    arr[..., 3] = alpha * 255
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA").filter(ImageFilter.GaussianBlur(0.8)).save(path)


def make_all(force=False):
    os.makedirs(TEX_DIR, exist_ok=True)
    stamp = os.path.join(TEX_DIR, "VERSION")
    if not force and os.path.exists(stamp) and open(stamp).read().strip() == VERSION:
        return TEX_DIR
    road_masks()
    cover_height(os.path.join(TEX_DIR, "manhole_h.png"), 1024, "BOROUGH STEAM & LIGHT", "1987   SEWER   No. 4", "manhole")
    cover_height(os.path.join(TEX_DIR, "valve_h.png"), 512, "W", "", "valve")
    blade(os.path.join(TEX_DIR, "blade_av.png"), "Harrow", "Av", "500")
    blade(os.path.join(TEX_DIR, "blade_cs.png"), "Cutler", "St", "W 200")
    one_way(os.path.join(TEX_DIR, "one_way.png"))
    no_parking(os.path.join(TEX_DIR, "no_parking.png"))
    push_button(os.path.join(TEX_DIR, "push_button.png"))
    ped_face(os.path.join(TEX_DIR, "ped_hand.png"), "hand", 17)
    ped_face(os.path.join(TEX_DIR, "ped_walk.png"), "walk")
    stickers(os.path.join(TEX_DIR, "stickers.png"))
    news_front(os.path.join(TEX_DIR, "news_front.png"))
    news_decal(os.path.join(TEX_DIR, "news_decal.png"))
    pay_decal(os.path.join(TEX_DIR, "pay_decal.png"))
    screen(os.path.join(TEX_DIR, "pay_screen.png"))
    leaves(os.path.join(TEX_DIR, "leaves.png"))
    cup(os.path.join(TEX_DIR, "cup.png"))
    cabinet_tag(os.path.join(TEX_DIR, "tag.png"))
    with open(stamp, "w") as f:
        f.write(VERSION)
    return TEX_DIR


if __name__ == "__main__":
    import time
    t = time.time()
    make_all(force=True)
    print("textures in", TEX_DIR, "%.1fs" % (time.time() - t))
