"""Texture preparation for the facade asset (run with the bpy python: /home/user/tools/bl/bin/python, which has numpy, Pillow, scipy).

    python3 facade_tex.py        # writes blender/assets/tex_gen/*

1. brick atlas: individual brick faces cut out of the CC0 Poly Haven `red_brick` scan (tex_scan/), each normalised to
   its own mean colour (so the facade palette sets the brick colour and the scan supplies clay texture, pores, fire
   flashing, chips and arrises), packed 8 x 8 into albedo-detail / normal / roughness atlases.  The shader picks one
   atlas brick per brick cell, so the scanned faces follow our real coursing instead of a tiled photo.
2. canvas set: tileable awning canvas (plain weave, slubs, albedo-detail / normal / roughness), generated procedurally.
"""
import os
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
SCAN = os.path.join(HERE, "tex_scan")
OUT = os.path.join(HERE, "tex_gen")
TW, TH = 256, 78          # atlas tile (215 x 65 mm brick face -> ~0.84 mm / px)
NA = 8


def runs(mask, minlen=3):
    r, i = [], 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j < len(mask) and mask[j]:
                j += 1
            if j - i >= minlen:
                r.append((i, j))
            i = j
        else:
            i += 1
    return r


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def brick_atlas():
    a = np.asarray(Image.open(os.path.join(SCAN, "red_brick_diff_2k.jpg")).convert('RGB')).astype(np.float32) / 255
    nrm = np.asarray(Image.open(os.path.join(SCAN, "red_brick_nor_gl_2k.jpg")).convert('RGB')).astype(np.float32) / 255
    rgh = np.asarray(Image.open(os.path.join(SCAN, "red_brick_rough_2k.jpg")).convert('L')).astype(np.float32) / 255
    s = a.max(2) - a.min(2)
    m = (s < np.percentile(s, 25)).astype(np.float32)
    beds = runs(m.mean(1) > 0.5, 2)
    bricks = []
    for (a0, a1), (b0, b1) in zip(beds[:-1], beds[1:]):
        y0, y1 = a1, b0
        if y1 - y0 < 60:
            continue
        col = m[y0 + 8:y1 - 8].mean(0)
        heads = runs(col > 0.5, 2)
        edges = [(0, 0)] + heads + [(a.shape[1], a.shape[1])]
        for (h0, h1), (k0, k1) in zip(edges[:-1], edges[1:]):
            x0, x1 = h1, k0
            if x0 == 0 or x1 == a.shape[1] or x1 - x0 < 150:
                continue     # skip bricks cut by the image border and half bats
            bricks.append((x0, x1, y0, y1))
    print("bricks found:", len(bricks))
    rng = np.random.default_rng(3)
    rng.shuffle(bricks)
    bricks = bricks[:NA * NA]
    alb = np.zeros((NA * TH, NA * TW, 3), np.float32)
    nor = np.zeros((NA * TH, NA * TW, 3), np.float32)
    rou = np.zeros((NA * TH, NA * TW), np.float32)
    for k in range(NA * NA):
        x0, x1, y0, y1 = bricks[k % len(bricks)]
        # 1 px inward so the mortar fringe never enters the face, keep the arrises
        sl = (slice(y0 + 5, y1 - 5), slice(x0 + 6, x1 - 6))
        def rs(img, mode=Image.LANCZOS):
            im = Image.fromarray(np.clip(img * 255, 0, 255).astype(np.uint8))
            return np.asarray(im.resize((TW, TH), mode)).astype(np.float32) / 255
        lin = srgb_to_lin(a[sl])
        mean = lin.reshape(-1, 3).mean(0)
        lum = lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        lm = float(mean @ np.array([0.2126, 0.7152, 0.0722], np.float32))
        chroma = (lin / np.maximum(lum, 1e-4)[..., None]) / (mean / lm)[None, None, :]
        det = (lum / lm)[..., None] ** 0.9 * np.clip(chroma, 0.2, 3.0) ** 0.35   # damp hue swings (mortar smear stays neutral)
        ty, tx = divmod(k, NA)
        tile = rs(np.clip(det * 0.5, 0, 1))        # stored as detail * 0.5 (linear, Non-Color)
        alb[ty * TH:(ty + 1) * TH, tx * TW:(tx + 1) * TW] = tile
        nor[ty * TH:(ty + 1) * TH, tx * TW:(tx + 1) * TW] = rs(nrm[sl])
        rou[ty * TH:(ty + 1) * TH, tx * TW:(tx + 1) * TW] = rs(rgh[sl])
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray((alb * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, "brick_atlas_detail.png"))
    Image.fromarray((nor * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, "brick_atlas_nor_gl.png"))
    Image.fromarray((rou * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, "brick_atlas_rough.png"))


def canvas(N=2048, threads=256, seed=5):
    """Plain-weave awning duck, tileable: N px = one tile.  `threads` warp/weft per tile."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:N, 0:N].astype(np.float32)
    p = N / threads
    # per-thread thickness / brightness variation (slubs) – tileable by construction
    wt = 1 + 0.25 * gaussian_filter(rng.standard_normal(threads), 0.7, mode='wrap')
    ft = 1 + 0.25 * gaussian_filter(rng.standard_normal(threads), 0.7, mode='wrap')
    ix = (x // p).astype(int) % threads
    iy = (y // p).astype(int) % threads
    fx = (x % p) / p
    fy = (y % p) / p
    over = ((ix + iy) % 2 == 0)
    warp = np.sin(np.pi * fx) ** 0.6 * wt[ix]       # vertical threads
    weft = np.sin(np.pi * fy) ** 0.6 * ft[iy]
    along_w = 0.75 + 0.25 * np.sin(np.pi * fy)       # thread rises over crossings
    along_f = 0.75 + 0.25 * np.sin(np.pi * fx)
    h = np.where(over, warp * along_w, weft * along_f)
    # fibre fuzz
    fz = rng.random((N, N)).astype(np.float32)
    fz = gaussian_filter(fz, 0.8, mode='wrap')
    h = h * 0.85 + 0.15 * (fz - fz.mean()) / fz.std() * 0.3
    # large soft mottling (dye unevenness), tileable via wrap
    mot = gaussian_filter(rng.standard_normal((N // 8, N // 8)).astype(np.float32), 6, mode='wrap')
    mot = np.kron(mot, np.ones((8, 8), np.float32))
    mot = gaussian_filter(mot, 6, mode='wrap')
    mot = (mot - mot.mean()) / (mot.std() + 1e-6)
    alb = 0.5 * (0.88 + 0.10 * h + 0.03 * mot + 0.04 * (fz - 0.5))
    hh = gaussian_filter(h, 0.6, mode='wrap')
    gy, gx = np.gradient(hh)
    k = 2.2
    n = np.stack([-gx * k, gy * k, np.ones_like(hh)], -1)    # OpenGL (green up)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    rough = 0.82 + 0.08 * (1 - h / max(1e-6, h.max())) + 0.03 * mot / 3
    Image.fromarray((np.clip(alb, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, "canvas_detail.png"))
    Image.fromarray(((n * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, "canvas_nor_gl.png"))
    Image.fromarray((np.clip(rough, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, "canvas_rough.png"))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    brick_atlas()
    canvas()
