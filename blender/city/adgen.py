"""Procedural advertising atlas (PIL): 64 invented ads/posters/screens in an 8x8 atlas.

Every brand, title and slogan here is invented for this film. build_atlas(path) writes a 4096^2
PNG and returns a list of dicts: {i, kind, aspect, uv:(u0,v0,u1,v1)} (Blender UV, v up).
"""
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CELL = 512
N = 8
F = "/usr/share/fonts/opentype/inter/"
FONTS = {
    'black': F + "InterDisplay-Black.otf", 'bold': F + "Inter-Bold.otf", 'xbi': F + "InterDisplay-ExtraBoldItalic.otf",
    'light': F + "InterDisplay-Light.otf", 'thin': F + "InterDisplay-Thin.otf",
    'serif': "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    'serif2': "/usr/share/fonts/truetype/liberation/LiberationSerif-BoldItalic.ttf",
    'cond': "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf",
    'mono': "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-ExtraBold.ttf",
}
BRANDS = ["NOVA COLA", "KESTREL", "orbit air", "LUMA", "HALCYON", "VESPER", "ZENITH", "PULSE", "MERCER", "AURORA",
          "BRISK", "TANGO", "OSPREY", "QUILL", "FLUX", "MAPLE & IVY", "RIVET", "SOLACE", "ATLAS", "CIRRUS", "PEPPERJACK",
          "GLINT", "MONARCH", "NIMBUS", "ECHO", "PARAGON", "SABLE", "VOLTA", "JUNIPER", "COBALT", "FABLE", "HOLLIS"]
SLOGANS = ["TASTE THE CITY", "BUILT FOR THE NIGHT", "FEEL EVERY SECOND", "NOW ON EVERY CORNER", "GO FURTHER",
           "THE NEW CLASSIC", "MADE TO MOVE", "ONLY IN THE CITY", "LIMITED EDITION", "OPEN LATE", "SAY IT LOUDER",
           "EVERY DAY, BETTER", "THINK BRIGHT", "ALWAYS ON", "STAY CURIOUS", "THE ORIGINAL"]
TITLES = ["THE LAST TIDE", "NIGHT OF GLASS", "IRON HARBOR", "SEVEN BRIDGES", "PAPER CROWNS", "LOW SUN", "AFTERGLOW",
          "THE QUIET ROOF", "NORTHBOUND", "VELVET STATIC", "HALF MOON BAY", "THE CARTOGRAPHER", "RED LANTERN",
          "BLUE HOUR", "WILDFIRE SEASON", "THE GLASS GARDEN"]
SHOWS = ["MIDNIGHT ON 9TH", "STARDUST REVUE", "THE LANTERN GIRLS", "BROKEN COMPASS", "GOLDEN MILE", "ECHO PARK"]
PAL = [((222, 30, 40), (255, 255, 255)), ((250, 200, 20), (20, 20, 20)), ((20, 40, 120), (255, 210, 60)),
       ((10, 10, 12), (255, 255, 255)), ((240, 90, 30), (255, 245, 230)), ((30, 160, 120), (255, 255, 255)),
       ((120, 30, 160), (255, 230, 80)), ((245, 245, 240), (200, 20, 40)), ((0, 150, 220), (255, 255, 255)),
       ((250, 70, 140), (255, 255, 255)), ((40, 40, 45), (90, 230, 200)), ((180, 140, 90), (30, 20, 15))]
ASPECTS = [0.33, 0.5, 0.67, 0.75, 1.0, 1.33, 1.5, 2.0, 3.0, 4.0]


def font(k, s):
    return ImageFont.truetype(FONTS[k], max(8, int(s)))


def fit_text(d, text, k, w, h):
    s = h
    while s > 8:
        f = font(k, s)
        bb = d.textbbox((0, 0), text, font=f)
        if bb[2] - bb[0] <= w and bb[3] - bb[1] <= h:
            return f, bb
        s *= 0.9
    f = font(k, 8)
    return f, d.textbbox((0, 0), text, font=f)


def text_in(d, text, k, box, fill, align='c'):
    x0, y0, x1, y1 = box
    f, bb = fit_text(d, text, k, x1 - x0, y1 - y0)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x = x0 + ((x1 - x0) - tw) / 2 - bb[0] if align == 'c' else x0 - bb[0]
    y = y0 + ((y1 - y0) - th) / 2 - bb[1]
    d.text((x, y), text, font=f, fill=fill)


def grad(w, h, c0, c1, vertical=True):
    im = Image.new('RGB', (w, h))
    px = im.load()
    for j in range(h if vertical else w):
        t = j / max(1, (h if vertical else w) - 1)
        c = tuple(int(a + (b - a) * t) for a, b in zip(c0, c1))
        if vertical:
            for i in range(w):
                px[i, j] = c
        else:
            for i in range(h):
                px[j, i] = c
    return im


def figure(d, cx, base, hgt, col, r):
    """Simple human silhouette (head, shoulders, torso, legs) in a pose."""
    s = hgt / 8.0
    d.ellipse([cx - s * 0.55, base - hgt, cx + s * 0.55, base - hgt + s * 1.25], fill=col)
    d.polygon([(cx - s * 1.3, base - hgt + s * 1.5), (cx + s * 1.3, base - hgt + s * 1.5), (cx + s * 0.9, base - hgt + s * 4.4),
               (cx - s * 0.9, base - hgt + s * 4.4)], fill=col)
    lean = r.uniform(-0.8, 0.8) * s
    d.polygon([(cx - s * 0.9, base - hgt + s * 4.3), (cx - s * 0.05, base - hgt + s * 4.3), (cx - s * 0.3 - lean, base),
               (cx - s * 0.95 - lean, base)], fill=col)
    d.polygon([(cx + s * 0.05, base - hgt + s * 4.3), (cx + s * 0.9, base - hgt + s * 4.3), (cx + s * 0.95 + lean, base),
               (cx + s * 0.3 + lean, base)], fill=col)
    a = r.uniform(-1.0, 1.0)
    for sg in (-1, 1):
        x0, y0 = cx + sg * s * 1.2, base - hgt + s * 1.7
        x1, y1 = x0 + sg * s * 1.0 * math.cos(a), y0 + s * 2.6
        d.line([(x0, y0), (x1, y1)], fill=col, width=max(2, int(s * 0.5)))


def ad_product(im, r, aspect):
    w, h = im.size
    bg, fg = r.choice(PAL)
    bg2 = tuple(max(0, min(255, c + r.randint(-60, 60))) for c in bg)
    im.paste(grad(w, h, bg, bg2, r.random() < 0.6))
    d = ImageDraw.Draw(im)
    brand = r.choice(BRANDS)
    # product: bottle / can / circle burst
    kind = r.choice(['can', 'bottle', 'burst', 'phone', 'shoe'])
    cx = w * (0.72 if aspect > 1.2 else 0.5)
    cy = h * (0.55 if aspect > 1.2 else 0.62)
    sz = min(w, h) * 0.32
    acc = r.choice([(255, 255, 255), (255, 220, 40), (20, 20, 20), (230, 40, 50), (40, 200, 255)])
    if kind == 'burst':
        for k in range(18):
            ang = k * math.pi / 9
            d.polygon([(cx, cy), (cx + math.cos(ang) * sz * 2, cy + math.sin(ang) * sz * 2),
                       (cx + math.cos(ang + 0.15) * sz * 2, cy + math.sin(ang + 0.15) * sz * 2)], fill=bg2)
        d.ellipse([cx - sz * 0.7, cy - sz * 0.7, cx + sz * 0.7, cy + sz * 0.7], fill=acc)
    elif kind == 'can':
        d.rounded_rectangle([cx - sz * 0.4, cy - sz, cx + sz * 0.4, cy + sz], radius=int(sz * 0.12), fill=acc)
        d.rectangle([cx - sz * 0.4, cy - sz * 0.25, cx + sz * 0.4, cy + sz * 0.25], fill=fg)
    elif kind == 'bottle':
        d.rounded_rectangle([cx - sz * 0.35, cy - sz * 0.5, cx + sz * 0.35, cy + sz * 1.1], radius=int(sz * 0.2), fill=acc)
        d.rectangle([cx - sz * 0.12, cy - sz * 1.1, cx + sz * 0.12, cy - sz * 0.4], fill=acc)
        d.rectangle([cx - sz * 0.35, cy, cx + sz * 0.35, cy + sz * 0.4], fill=fg)
    elif kind == 'phone':
        d.rounded_rectangle([cx - sz * 0.5, cy - sz, cx + sz * 0.5, cy + sz], radius=int(sz * 0.15), fill=(15, 15, 18))
        d.rounded_rectangle([cx - sz * 0.44, cy - sz * 0.92, cx + sz * 0.44, cy + sz * 0.92], radius=int(sz * 0.12),
                            fill=bg2)
        d.ellipse([cx - sz * 0.3, cy - sz * 0.3, cx + sz * 0.3, cy + sz * 0.3], fill=acc)
    else:
        d.polygon([(cx - sz, cy + sz * 0.4), (cx + sz, cy + sz * 0.4), (cx + sz, cy + sz * 0.1), (cx, cy - sz * 0.2),
                   (cx - sz * 0.6, cy - sz * 0.5), (cx - sz, cy - sz * 0.3)], fill=acc)
        d.rectangle([cx - sz, cy + sz * 0.3, cx + sz, cy + sz * 0.45], fill=fg)
    if aspect > 1.2:
        text_in(d, brand, r.choice(['black', 'xbi', 'cond']), (w * 0.05, h * 0.1, w * 0.52, h * 0.5), fg, 'l')
        text_in(d, r.choice(SLOGANS), 'bold', (w * 0.05, h * 0.58, w * 0.5, h * 0.72), fg, 'l')
    else:
        text_in(d, brand, r.choice(['black', 'xbi', 'cond']), (w * 0.08, h * 0.05, w * 0.92, h * 0.24), fg)
        text_in(d, r.choice(SLOGANS), 'bold', (w * 0.1, h * 0.88, w * 0.9, h * 0.96), fg)


def ad_person(im, r, aspect):
    """Fashion / lifestyle: big figure silhouette against a colour field, brand in the corner."""
    w, h = im.size
    bg, fg = r.choice(PAL)
    im.paste(grad(w, h, bg, tuple(int(c * 0.55) for c in bg)))
    d = ImageDraw.Draw(im)
    figc = r.choice([(15, 12, 12), (240, 235, 225), (60, 30, 25), (200, 50, 60)])
    n = 1 if aspect < 1.4 else r.randint(1, 3)
    for k in range(n):
        cx = w * ((k + 0.5) / n if n > 1 else r.uniform(0.35, 0.65))
        figure(d, cx, h * 1.02, h * r.uniform(0.75, 0.95), figc, r)
    text_in(d, r.choice(BRANDS), r.choice(['black', 'serif', 'thin']), (w * 0.05, h * 0.04, w * 0.6, h * 0.17), fg, 'l')
    text_in(d, r.choice(SLOGANS), 'bold', (w * 0.05, h * 0.18, w * 0.5, h * 0.24), fg, 'l')


def ad_movie(im, r, aspect):
    w, h = im.size
    c0 = r.choice([(10, 12, 25), (30, 8, 8), (8, 20, 18), (25, 18, 5)])
    c1 = r.choice([(200, 90, 30), (40, 90, 200), (190, 30, 50), (230, 180, 60)])
    im.paste(grad(w, h, c0, c1))
    d = ImageDraw.Draw(im)
    # sun / moon disc and skyline
    d.ellipse([w * 0.3, h * 0.25, w * 0.7, h * 0.25 + w * 0.4], fill=tuple(min(255, c + 50) for c in c1))
    x = 0
    while x < w:
        bw = r.uniform(0.04, 0.12) * w
        bh = r.uniform(0.1, 0.35) * h
        d.rectangle([x, h * 0.75 - bh, x + bw, h], fill=c0)
        x += bw
    figure(d, w * r.uniform(0.35, 0.65), h * 0.98, h * 0.55, (5, 5, 8), r)
    title = r.choice(TITLES)
    text_in(d, title, r.choice(['serif', 'black', 'cond', 'serif2']), (w * 0.06, h * 0.05, w * 0.94, h * 0.2), (245, 235, 220))
    text_in(d, "IN THEATERS FRIDAY", 'bold', (w * 0.2, h * 0.21, w * 0.8, h * 0.25), (230, 220, 200))
    for k in range(3):
        d.rectangle([w * 0.15, h * (0.88 + k * 0.02), w * 0.85, h * (0.885 + k * 0.02)], fill=(160, 150, 140))


def ad_show(im, r, aspect):
    w, h = im.size
    bg = r.choice([(120, 10, 20), (15, 15, 60), (10, 10, 10), (90, 20, 90)])
    im.paste(Image.new('RGB', (w, h), bg))
    d = ImageDraw.Draw(im)
    gold = (240, 200, 90)
    d.rectangle([w * 0.03, h * 0.03, w * 0.97, h * 0.97], outline=gold, width=max(3, int(w * 0.012)))
    text_in(d, r.choice(SHOWS), r.choice(['serif2', 'serif', 'black']), (w * 0.08, h * 0.3, w * 0.92, h * 0.62), gold)
    text_in(d, "NOW PLAYING  -  THE ORPHEUM", 'bold', (w * 0.15, h * 0.7, w * 0.85, h * 0.8), (255, 240, 220))
    for k in range(int(w / 30)):
        d.ellipse([k * 30 + 8, 6, k * 30 + 20, 18], fill=(255, 230, 160))
        d.ellipse([k * 30 + 8, h - 18, k * 30 + 20, h - 6], fill=(255, 230, 160))


def ad_logo(im, r, aspect):
    """Lightbox / LED identity: bold logo mark + wordmark."""
    w, h = im.size
    bg, fg = r.choice(PAL)
    im.paste(Image.new('RGB', (w, h), bg))
    d = ImageDraw.Draw(im)
    m = min(w, h) * 0.6
    cx, cy = (w * 0.2, h / 2) if aspect > 1.4 else (w / 2, h * 0.35)
    shape = r.choice(['circle', 'tri', 'ring', 'diamond'])
    bb = [cx - m / 2, cy - m / 2, cx + m / 2, cy + m / 2]
    if shape == 'circle':
        d.ellipse(bb, fill=fg)
    elif shape == 'ring':
        d.ellipse(bb, outline=fg, width=int(m * 0.15))
    elif shape == 'tri':
        d.polygon([(cx, bb[1]), (bb[2], bb[3]), (bb[0], bb[3])], fill=fg)
    else:
        d.polygon([(cx, bb[1]), (bb[2], cy), (cx, bb[3]), (bb[0], cy)], fill=fg)
    name = r.choice(BRANDS)
    if aspect > 1.4:
        text_in(d, name, r.choice(['black', 'bold', 'serif']), (w * 0.38, h * 0.2, w * 0.95, h * 0.8), fg, 'l')
    else:
        text_in(d, name, r.choice(['black', 'bold', 'serif']), (w * 0.08, h * 0.68, w * 0.92, h * 0.88), fg)


def ad_type(im, r, aspect):
    """Type-only campaign: huge words, stripes."""
    w, h = im.size
    bg, fg = r.choice(PAL)
    im.paste(Image.new('RGB', (w, h), bg))
    d = ImageDraw.Draw(im)
    acc = r.choice([(255, 220, 40), (230, 40, 60), (40, 200, 255), (255, 255, 255)])
    for k in range(r.randint(2, 5)):
        y = r.uniform(0, h)
        d.rectangle([0, y, w, y + h * 0.03], fill=acc)
    words = r.choice(SLOGANS).split()
    n = len(words)
    for i, wd in enumerate(words):
        text_in(d, wd, 'black', (w * 0.06, h * (0.08 + 0.84 * i / n), w * 0.94, h * (0.08 + 0.84 * (i + 1) / n) - h * 0.02), fg,
                'l')
    text_in(d, r.choice(BRANDS), 'bold', (w * 0.6, h * 0.9, w * 0.95, h * 0.97), acc)


KINDS = [ad_product, ad_product, ad_person, ad_person, ad_movie, ad_show, ad_logo, ad_logo, ad_type]


def build_atlas(path, seed=606):
    r = random.Random(seed)
    atlas = Image.new('RGB', (CELL * N, CELL * N), (0, 0, 0))
    info = []
    for i in range(N * N):
        aspect = ASPECTS[i % len(ASPECTS)]
        fn = KINDS[(i * 5 + i // 9) % len(KINDS)]
        if aspect >= 1:
            w, h = CELL, int(CELL / aspect)
        else:
            w, h = int(CELL * aspect), CELL
        im = Image.new('RGB', (w, h))
        fn(im, random.Random(seed * 100 + i), aspect)
        # slight print grain / softness
        im = im.filter(ImageFilter.GaussianBlur(0.5))
        cx, cy = (i % N) * CELL, (i // N) * CELL
        ox, oy = cx + (CELL - w) // 2, cy + (CELL - h) // 2
        atlas.paste(im, (ox, oy))
        S = CELL * N
        # PIL y down -> Blender v up
        info.append(dict(i=i, kind=fn.__name__, aspect=aspect,
                         uv=((ox + 1) / S, 1 - (oy + h - 1) / S, (ox + w - 1) / S, 1 - (oy + 1) / S)))
    atlas.save(path)
    return info


if __name__ == "__main__":
    import sys
    inf = build_atlas(sys.argv[1])
    print(len(inf))
