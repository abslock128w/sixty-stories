"""Placeholder frames for SITE development, in the exact delivery format (BIBLE section 6).

Writes  <out>/frames/color/f_%04d.png  (1920x804 RGB)
        <out>/frames/depth/f_%04d.png  (960x402 L, v = round(255/(1+z/25)), sky = 0)
        <out>/shots.json               (same schema as blender/out/shots.json)

The picture is a procedural golden-hour skyline built from parallax layers at known depths,
so the site's depth parallax, frame blending and cut handling can be judged by eye. Each frame
has its global index and shot id burned in, plus a small "hero" marker with its own depth.

Usage:  $PY tools/make_placeholder_frames.py [--out tools/dev] [--jobs 2] [--only 0-47]
Default output is tools/dev (never blender/out/frames).
"""
import argparse, json, math, os, sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 804
DW, DH = 960, 402
SHOTS = [
    dict(id="s1", title="THE CITY", start=0, count=48, lens_mm=35,
         logline="High aerial over the skyline, slow push-in and tilt-down through haze."),
    dict(id="s2", title="THE PERCH", start=48, count=48, lens_mm=105,
         logline="Long-lens arc around the hero crouched on the gargoyle, 228 m up."),
    dict(id="s3", title="THE DROP", start=96, count=48, lens_mm=18,
         logline="He tips forward and dives; the tower face streaks past."),
    dict(id="s4", title="THE SWING", start=144, count=72, lens_mm=24,
         logline="A line fires across the avenue and he pendulums down the canyon."),
    dict(id="s5", title="THREAD THE NEEDLE", start=216, count=48, lens_mm=85,
         logline="Release, tuck, flip through the gap, fire again."),
    dict(id="s6", title="APEX", start=264, count=72, lens_mm=50,
         logline="Weightless against the sun, then the city at dusk."),
]
TOTAL = 336
LAYER_Z = [22.0, 45.0, 90.0, 180.0, 420.0, 1100.0]  # metres

# per-shot camera: (pan px/frame at z=25m, vertical px/frame at z=25m, zoom per frame, horizon y)
CAM = {
    "s1": dict(pan=1.5, rise=-0.6, zoom=0.0016, horizon=0.36, dusk=0.0),
    "s2": dict(pan=-7.0, rise=0.0, zoom=0.0, horizon=0.58, dusk=0.05),
    "s3": dict(pan=0.6, rise=-14.0, zoom=0.004, horizon=0.20, dusk=0.08),
    "s4": dict(pan=14.0, rise=1.5, zoom=0.0, horizon=0.62, dusk=0.12),
    "s5": dict(pan=-20.0, rise=0.0, zoom=0.0, horizon=0.55, dusk=0.18),
    "s6": dict(pan=3.0, rise=2.4, zoom=-0.0025, horizon=0.66, dusk=0.0),
}


def shot_of(i):
    for s in SHOTS:
        if s["start"] <= i < s["start"] + s["count"]:
            return s
    raise ValueError(i)


def telemetry(i):
    s = shot_of(i); t = (i - s["start"]) / max(1, s["count"] - 1)
    if s["id"] == "s1":
        alt, spd = 350 - 60 * t, 40 + 10 * t
    elif s["id"] == "s2":
        alt, spd = 228.0, 0.0
    elif s["id"] == "s3":
        alt = 228 - 175 * t ** 1.6; spd = 10 + 150 * t
    elif s["id"] == "s4":
        alt = 53 - 28 * math.sin(math.pi * t); spd = 160 - 60 * math.sin(math.pi * t) + 30 * t
    elif s["id"] == "s5":
        alt = 70 + 10 * math.sin(math.pi * t); spd = 120 - 20 * t
    else:
        u = t
        alt = 95 + 20 * math.sin(min(1, u * 2) * math.pi / 2) if u < 0.4 else 115 + 400 * (u - 0.4) ** 1.5
        spd = max(0.0, 90 * (1 - u * 3)) if u < 0.4 else 20 + 60 * (u - 0.4)
    return dict(i=i, altitude_m=round(alt, 1), speed_kmh=round(spd, 1))


def sky_colours(dusk):
    top = np.array([0.20, 0.30, 0.52]) * (1 - dusk) + np.array([0.08, 0.10, 0.22]) * dusk
    hor = np.array([1.00, 0.70, 0.38]) * (1 - dusk) + np.array([0.85, 0.42, 0.30]) * dusk
    return top, hor


def build_layer(seed, z, width, horizon_px, dusk):
    """RGBA strip of a skyline layer at distance z (metres)."""
    rng = np.random.default_rng(seed)
    img = Image.new("RGBA", (width, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    scale = 25.0 / z  # apparent size relative to a building 25 m away
    x = -50
    near = z < 100
    base_y = horizon_px + int(60 * scale ** 0.5)
    while x < width + 50:
        bw = int(rng.uniform(60, 200) * min(3.0, scale * 2.0) + 20)
        if z < 60:      # sparse framing towers close to camera
            bh = int(rng.uniform(0.55, 1.1) * H)
        elif z < 200:
            bh = int(rng.uniform(0.18, 0.55) * H)
        else:
            bh = int(rng.uniform(0.04, 0.22) * H)
        top = base_y - bh
        shade = 0.10 + 0.25 * (1 - min(1, scale))
        warm = np.array([0.95, 0.62, 0.38])
        col = (np.array([0.10, 0.10, 0.13]) * (1 - shade) + warm * shade * 0.6)
        c = tuple(int(255 * v) for v in col) + (255,)
        d.rectangle([x, top, x + bw, H], fill=c)
        # sunlit edge
        d.rectangle([x + bw - max(2, bw // 12), top, x + bw, H],
                    fill=tuple(int(255 * v) for v in (col * 0.5 + warm * 0.5)) + (255,))
        # crown / setback
        if rng.random() < 0.35:
            cw = bw // 2; ch = int(bh * 0.12)
            d.rectangle([x + bw // 4, top - ch, x + bw // 4 + cw, top], fill=c)
            if rng.random() < 0.5:
                d.polygon([(x + bw // 4, top - ch), (x + bw // 2, top - ch * 2.2),
                           (x + bw // 4 + cw, top - ch)], fill=c)
        # windows
        if bw > 30:
            wx = max(4, int(8 * min(3, scale * 2))); wy = max(5, int(12 * min(3, scale * 2)))
            glow = 0.15 + 0.6 * dusk
            for yy in range(top + wy, H, wy * 2):
                for xx in range(x + wx, x + bw - wx, wx * 2):
                    r = rng.random()
                    if r < glow * 0.35:
                        d.rectangle([xx, yy, xx + wx - 1, yy + wy - 1], fill=(255, 196, 120, 255))
                    elif r < 0.6:
                        d.rectangle([xx, yy, xx + wx - 1, yy + wy - 1],
                                    fill=tuple(int(v * 0.6) for v in c[:3]) + (255,))
        x += bw + (int(rng.uniform(500, 1300)) if z < 60 else int(rng.uniform(0, 60) * min(2, scale * 3)))
    return img


SHOT_CACHE = {}


def shot_assets(sid):
    if sid in SHOT_CACHE:
        return SHOT_CACHE[sid]
    cam = CAM[sid]; s = next(s for s in SHOTS if s["id"] == sid)
    horizon_px = int(H * cam["horizon"])
    layers = []
    for k, z in enumerate(LAYER_Z):
        travel = abs(cam["pan"]) * (25.0 / z) * s["count"]
        width = int(W * 1.3 + travel + 400)
        img = build_layer(hash((sid, k)) & 0xFFFF, z, width, horizon_px, cam["dusk"])
        layers.append((z, np.asarray(img).astype(np.float32) / 255.0))
    SHOT_CACHE[sid] = (horizon_px, layers)
    return SHOT_CACHE[sid]


_FONT_CACHE = {}


def font(size):
    if size not in _FONT_CACHE:
        for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"]:
            if os.path.exists(p):
                _FONT_CACHE[size] = ImageFont.truetype(p, size); break
        else:
            _FONT_CACHE[size] = ImageFont.load_default()
    return _FONT_CACHE[size]


def render(i):
    s = shot_of(i); sid = s["id"]; cam = CAM[sid]; f = i - s["start"]
    horizon_px, layers = shot_assets(sid)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    top, hor = sky_colours(cam["dusk"])
    sh = (yy - cam["rise"] * f * 0.2) / H
    g = np.clip(sh / max(0.05, cam["horizon"] + 0.05), 0, 1)[..., None]
    rgb = top * (1 - g) + hor * g
    # sun: low, slightly off-centre, moves with pan very slowly (infinite distance)
    sx = W * 0.62 - cam["pan"] * f * 0.02; sy = horizon_px - 40 + cam["rise"] * f * 0.03
    r = np.sqrt((xx - sx) ** 2 + (yy - sy) ** 2)
    rgb = rgb + np.array([1.0, 0.75, 0.45]) * (np.exp(-r / 220) * 0.55)[..., None]
    rgb = np.where((r < 34)[..., None], np.array([1.0, 0.96, 0.86]), rgb)
    zbuf = np.full((H, W), np.inf, np.float32)
    zoom = 1.0 + cam["zoom"] * f
    for z, layer in reversed(layers):
        par = 25.0 / z
        ox = cam["pan"] * f * par; oy = cam["rise"] * f * par
        # sample layer with offset + zoom around centre
        lx = ((xx - W / 2) / zoom + W / 2 + 200 + (ox if cam["pan"] >= 0 else (layer.shape[1] - W * 1.3 - 400) + ox))
        ly = ((yy - H / 2) / zoom + H / 2 - oy)
        lxi = np.clip(lx.astype(np.int32), 0, layer.shape[1] - 1)
        lyi = np.clip(ly.astype(np.int32), 0, H - 1)
        smp = layer[lyi, lxi]
        a = smp[..., 3:4] * ((ly >= 0) & (ly < H))[..., None]
        haze = 1 - math.exp(-z / 900.0)
        col = smp[..., :3] * (1 - haze) + hor * haze * 0.9
        rgb = rgb * (1 - a) + col * a
        zbuf = np.where(a[..., 0] > 0.5, z, zbuf)
    # hero marker (s2..s6): a dark figure with amber visor at ~14 m
    if sid != "s1" or f > 40:
        hz = 14.0 if sid != "s1" else 400.0
        t = f / max(1, s["count"] - 1)
        hx = {"s1": 0.47, "s2": 0.55, "s3": 0.5, "s4": 0.35 + 0.3 * t, "s5": 0.7 - 0.4 * t, "s6": 0.52}[sid] * W
        hy = {"s1": 0.40, "s2": 0.45, "s3": 0.55 - 0.1 * t, "s4": 0.42 + 0.12 * math.sin(math.pi * t),
              "s5": 0.42, "s6": 0.40 - 0.1 * t}[sid] * H
        hs = 46 if sid != "s1" else 4
        if sid == "s6":
            hs = int(46 * max(0.08, 1 - t * 1.1))
        m = ((xx - hx) / (hs * 0.45)) ** 2 + ((yy - hy) / hs) ** 2 < 1
        rgb = np.where(m[..., None], np.array([0.09, 0.09, 0.10]), rgb)
        v = m & (np.abs(yy - (hy - hs * 0.55)) < max(1, hs * 0.06))
        rgb = np.where(v[..., None], np.array([1.0, 0.55, 0.15]), rgb)
        zbuf = np.where(m, hz, zbuf)
    # grade
    rgb = np.clip(rgb, 0, 1) ** (1 / 1.05)
    img = Image.fromarray((rgb * 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(img)
    d.text((W - 60, H - 60), f"{i:04d}", font=font(120), fill=(255, 255, 255), anchor="rs",
           stroke_width=3, stroke_fill=(0, 0, 0))
    d.text((60, 70), f"{sid.upper()}  {s['title']}  f{f:02d}/{s['count']}", font=font(34),
           fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    # centre crosshair to judge parallax/overscan
    d.line([(W / 2 - 20, H / 2), (W / 2 + 20, H / 2)], fill=(255, 255, 255), width=1)
    d.line([(W / 2, H / 2 - 20), (W / 2, H / 2 + 20)], fill=(255, 255, 255), width=1)
    dz = np.where(np.isinf(zbuf), 0, np.round(255.0 / (1.0 + zbuf / 25.0))).astype(np.uint8)
    depth = Image.fromarray(dz, "L").resize((DW, DH), Image.BILINEAR)
    return img, depth


def write_frame(args):
    i, out = args
    img, depth = render(i)
    for kind, im in (("color", img), ("depth", depth)):
        p = os.path.join(out, "frames", kind, f"f_{i:04d}.png")
        tmp = p + ".tmp.png"
        im.save(tmp, compress_level=3)
        os.replace(tmp, p)
    return i


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "dev"))
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--only", default=None, help="range a-b of global frames")
    a = ap.parse_args()
    for k in ("color", "depth"):
        os.makedirs(os.path.join(a.out, "frames", k), exist_ok=True)
    shots = dict(fps=24, width=W, height=H, total=TOTAL, shots=SHOTS,
                 telemetry=[telemetry(i) for i in range(TOTAL)], placeholder=True)
    with open(os.path.join(a.out, "shots.json"), "w") as fh:
        json.dump(shots, fh, indent=1)
    lo, hi = 0, TOTAL - 1
    if a.only:
        lo, hi = (int(v) for v in a.only.split("-"))
    # sort by shot so each worker builds shot layers once
    todo = [(i, a.out) for i in range(lo, hi + 1)]
    with Pool(a.jobs) as p:
        for n, i in enumerate(p.imap(write_frame, todo, chunksize=8)):
            if n % 24 == 0:
                print("frame", i, flush=True)
    print("done", len(todo))


if __name__ == "__main__":
    main()
