"""Sixty Stories - hero asset A: modern city taxi (original design, invented livery).

Run:  /home/user/tools/bl/bin/python blender/assets/taxi.py      -> builds ASSET_taxi, saves
      blender/out/assets/taxi.blend
Use:  import taxi; coll = taxi.build("yellow_cab")   # or black_sedan / silver_sedan / white_sedan
      build(variant, name=None, seed=None, dirt=None) returns a collection whose root empty
      "<name>_root" sits on the ground under the car centre, front toward +Y, metres, Z up.

Construction (how a vehicle artist would do it, but scripted):
  * Lower body: one quad cage built as a box lattice whose grid lines are placed exactly on
    panel seams, lamp / grille cut-outs and support loops. A shape function maps lattice
    parameters (u across, Y along, w up) to the body surface (plan sweep, tumblehome,
    shoulder character line, fender flares, bonnet crown). Panel gaps are 4 mm face strips
    removed from the cage, so doors, bonnet, boot lid, bumpers and fuel flap are separate
    panels; Solidify (sheet thickness, rolled edges) -> Subdivision -> Boolean wheel arches.
  * Greenhouse: second lattice whose bottom edge is evaluated ON the body beltline, raked
    windscreen / backlight, A/B/C pillars, black surrounds, flush glass as its own mesh.
  * Lamp lenses are the body faces of the lamp regions (so they are flush with the panels);
    housings are extruded from them and filled with reflector bowls, projector lenses,
    DRL light guides, indicators.
  * Wheels: lathed tyre with real circumferential + lateral tread grooves, sidewall bulge
    and lettering bump; 10-spoke alloy, lug nuts, centre cap, vented disc, caliper.
  * Interior, partition, taxi equipment, plates, livery decals (all invented).
"""
import bpy
import bmesh
import math
import os
import sys
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_BLEND = os.path.join(ROOT, "blender", "out", "assets", "taxi.blend")
TEX_DIR = os.path.join(ROOT, "blender", "out", "assets", "taxi_tex")
FONT_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
FONT_X = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
FONT_M = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
FONT_D = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ---------------------------------------------------------------- key dimensions (m)
YF, YR = 2.425, -2.425           # bumper extremes (length 4.85)
AXF, AXR = 1.45, -1.35           # axles (wheelbase 2.80)
WHEEL_R = 0.34                   # tyre modelled at 0.68 m, instanced at WHEEL_SCALE
WHEEL_SCALE = 1.045              # -> 0.71 m (225/55 R18)
WHEEL_Z = 0.352                  # slightly loaded
TRACK_X = 0.795                  # wheel centre plane
ARCH_R = 0.405
STEER_DEG = -7.0                 # front wheels turned slightly (reads as a parked / turning car)
COWL_Y, DECK_Y = 0.88, -1.62      # greenhouse footprint on the body

VARIANTS = {
    "yellow_cab": dict(paint=(0.76, 0.44, 0.003), metal=0.05, flake=0.10, coat_rough=0.035,
                       taxi=True, trim="black", dirt=0.85, plate=("T 482 77C", "TAXI"), rims="silver"),
    "black_sedan": dict(paint=(0.012, 0.012, 0.014), metal=0.55, flake=0.35, coat_rough=0.02,
                        taxi=False, trim="chrome", dirt=0.55, plate=("HC 4471", "LIVERY"), rims="dark"),
    "silver_sedan": dict(paint=(0.42, 0.43, 0.44), metal=0.85, flake=0.45, coat_rough=0.03,
                         taxi=False, trim="chrome", dirt=0.65, plate=("KLM 2093", "HARBOR"), rims="silver"),
    "white_sedan": dict(paint=(0.80, 0.80, 0.78), metal=0.08, flake=0.12, coat_rough=0.03,
                        taxi=False, trim="black", dirt=0.75, plate=("JRT 7716", "HARBOR"), rims="silver"),
}


# ================================================================== small math helpers
def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def pchip(keys):
    xs = np.array([k[0] for k in keys], float)
    ys = np.array([k[1] for k in keys], float)
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.zeros_like(ys)
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(xs) - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        if x <= xs[0]:
            return float(ys[0])
        if x >= xs[-1]:
            return float(ys[-1])
        i = int(np.searchsorted(xs, x)) - 1
        t = (x - xs[i]) / h[i]
        t2, t3 = t * t, t * t * t
        return float((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i]
                     + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h[i] * m[i + 1])
    return f


def plin(keys):
    xs = [k[0] for k in keys]
    ys = [k[1] for k in keys]
    return lambda x: float(np.interp(x, xs, ys))


def lines(req, lo, hi, fill):
    """Sorted grid coordinates: required values (exact) + uniform fill so no gap > fill."""
    vals = sorted(set([round(v, 6) for v in req if lo - 1e-9 <= v <= hi + 1e-9] + [lo, hi]))
    out = [vals[0]]
    for v in vals[1:]:
        if v - out[-1] < 4e-4:
            continue
        gap = v - out[-1]
        n = int(math.ceil(gap / fill - 1e-6))
        a = out[-1]
        for s in range(1, n):
            out.append(a + gap * s / n)
        out.append(v)
    return out


def seam_lines(v, g, sup):
    return [v - g - sup, v - g, v + g, v + g + sup]


def edge_lines(v, sup):
    return [v - sup, v, v + sup]


# ================================================================== lattice
class Lattice:
    """Closed box-surface quad cage on parameter grid (U across, V along, W up)."""

    def __init__(self, U, V, W, pos):
        self.U, self.V, self.W, self.pos = U, V, W, pos
        nu, nv, nw = len(U), len(V), len(W)
        self.vid = {}
        self.co = []
        self.faces = []

        def vt(i, j, k):
            key = (i, j, k)
            if key not in self.vid:
                self.vid[key] = len(self.co)
                self.co.append(tuple(pos(U[i], V[j], W[k])))
            return self.vid[key]

        for j in range(nv - 1):
            for k in range(nw - 1):
                for side, i in (("R", nu - 1), ("L", 0)):
                    f = [vt(i, j, k), vt(i, j + 1, k), vt(i, j + 1, k + 1), vt(i, j, k + 1)]
                    if side == "L":
                        f = f[::-1]
                    self.faces.append((f, side, {"u": (U[i], U[i]), "v": (V[j], V[j + 1]), "w": (W[k], W[k + 1])}))
        for i in range(nu - 1):
            for j in range(nv - 1):
                for side, k in (("T", nw - 1), ("B", 0)):
                    f = [vt(i, j, k), vt(i + 1, j, k), vt(i + 1, j + 1, k), vt(i, j + 1, k)]
                    if side == "B":
                        f = f[::-1]
                    self.faces.append((f, side, {"u": (U[i], U[i + 1]), "v": (V[j], V[j + 1]), "w": (W[k], W[k])}))
            for k in range(nw - 1):
                for side, j in (("F", nv - 1), ("K", 0)):
                    f = [vt(i, j, k), vt(i, j, k + 1), vt(i + 1, j, k + 1), vt(i + 1, j, k)]
                    if side == "K":
                        f = f[::-1]
                    self.faces.append((f, side, {"u": (U[i], U[i + 1]), "v": (V[j], V[j]), "w": (W[k], W[k + 1])}))

    def normal(self, u, v, w, side, eps=1e-3):
        p = Vector(self.pos(u, v, w))
        if side in "RL":
            a = Vector(self.pos(u, v + eps, w)) - p
            b = Vector(self.pos(u, v, w + eps)) - p
            n = a.cross(b) * (1 if side == "R" else -1)
        elif side in "TB":
            a = Vector(self.pos(u + eps, v, w)) - p
            b = Vector(self.pos(u, v + eps, w)) - p
            n = a.cross(b) * (1 if side == "T" else -1)
        else:
            a = Vector(self.pos(u, v, w + eps)) - p
            b = Vector(self.pos(u + eps, v, w)) - p
            n = a.cross(b) * (1 if side == "F" else -1)
        return p, n.normalized()


def _mid(r):
    return 0.5 * (r[0] + r[1])


def in_region(face, sides, cons):
    f, side, r = face
    if side not in sides:
        return False
    for ax, (lo, hi) in cons.items():
        c = _mid(r[ax])
        if not (lo - 1e-6 <= c <= hi + 1e-6):
            return False
    return True


def in_strip(face, sides, ax, val, g, cons):
    f, side, r = face
    if side not in sides:
        return False
    a, b = r[ax]
    if abs(a - (val - g)) > 1e-5 or abs(b - (val + g)) > 1e-5:
        return False
    for ax2, (lo, hi) in cons.items():
        c = _mid(r[ax2])
        if not (lo - 1e-6 <= c <= hi + 1e-6):
            return False
    return True


def mesh_from_faces(name, lat, faces, mat_of_face=None, uv_scale=1.0):
    used = {}
    verts = []
    polys = []
    for f in faces:
        poly = []
        for vi in f[0]:
            if vi not in used:
                used[vi] = len(verts)
                verts.append(lat.co[vi])
            poly.append(used[vi])
        polys.append(poly)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], polys)
    me.update()
    uvl = me.uv_layers.new(name="UVMap")
    li = 0
    for pi, f in enumerate(faces):
        side = f[1]
        for vi in f[0]:
            x, y, z = lat.co[vi]
            if side in "RL":
                uv = (y * (1 if side == "R" else -1), z)
            elif side in "TB":
                uv = (x, y)
            else:
                uv = (x * (1 if side == "F" else -1), z)
            uvl.data[li].uv = (uv[0] * uv_scale, uv[1] * uv_scale)
            li += 1
    if mat_of_face:
        for pi, f in enumerate(faces):
            me.polygons[pi].material_index = mat_of_face(f)
    for p in me.polygons:
        p.use_smooth = True
    return me


# ================================================================== body shape
_Zb = pchip([(-2.6, 0.345), (-2.25, 0.32), (-1.85, 0.235), (-1.6, 0.205), (1.65, 0.20),
             (2.0, 0.225), (2.6, 0.265)])
_Zt = pchip([(-2.6, 0.960), (-2.38, 1.025), (-2.0, 1.048), (-1.45, 1.04), (-0.9, 1.03),
             (0.0, 1.002), (0.8, 0.975), (1.4, 0.915), (2.0, 0.835), (2.3, 0.785), (2.6, 0.755)])
_W0 = pchip([(-2.6, 0.855), (-2.25, 0.895), (-1.8, 0.918), (0.0, 0.925), (1.85, 0.918),
             (2.2, 0.895), (2.6, 0.865)])
# cross-section (w = 0 sill .. 1 top): sill tuck-under, crowned door skin, soft shoulder,
# then tumblehome rolling over into the deck
_prof = pchip([(0.0, 0.905), (0.06, 0.940), (0.16, 0.968), (0.32, 0.988), (0.50, 0.998),
               (0.64, 1.0), (0.74, 0.995), (0.84, 0.978), (0.93, 0.950), (1.0, 0.918)])


def body_pos(u, v, w):
    # end shaping: plan sweep of the front / rear corners and fascia lean
    tF = smooth((v - (YF - 0.62)) / 0.62)
    tR = smooth(((YR + 0.62) - v) / 0.62)
    if w < 0.42:
        leanF = 0.11 * ((0.42 - w) / 0.42) ** 2
    else:
        leanF = 0.15 * ((w - 0.42) / 0.58) ** 2.2
    if w < 0.40:
        leanR = 0.12 * ((0.40 - w) / 0.40) ** 2
    else:
        leanR = 0.035 * ((w - 0.40) / 0.60) ** 2
    au = abs(u)
    # plan view: corners swept back progressively (no crease where fascia meets the flank)
    sweepF = 0.11 * au ** 2 + 0.17 * au ** 5
    sweepR = 0.07 * au ** 2 + 0.12 * au ** 4.5
    Y = v - tF * (leanF + sweepF) + tR * (leanR + sweepR)
    zb, zt = _Zb(Y), _Zt(Y)
    Z = zb + w * (zt - zb)
    # bonnet / boot crown and bonnet feature ridges
    crown = 0.034 if Y > 0.5 else 0.024
    Z += crown * (1 - u * u) * w ** 4
    if Y > 0.9:
        Z += 0.007 * math.exp(-((au - 0.48) / 0.07) ** 2) * w ** 6 * smooth((Y - 0.9) / 0.4)
    # boot lid trailing edge kicks up into a small integrated lip
    Z += 0.014 * smooth((-2.05 - Y) / 0.30) * w ** 10 * (1 - 0.3 * u * u)
    # front fascia: slightly lower nose in plan corners
    Z -= tF * 0.03 * au ** 3 * w
    # half width
    # deck / bonnet / boot roll-off toward the flanks (rounded shoulder in section)
    Z -= 0.040 * smooth((au - 0.50) / 0.50) ** 1.6 * w ** 6
    hw = _W0(Y) * _prof(w)
    hw += 0.0045 * math.exp(-((w - 0.71) / 0.032) ** 2)          # soft shoulder character line
    hw -= 0.005 * math.exp(-((w - 0.26) / 0.07) ** 2)             # lower door scallop
    for ax in (AXF, AXR):                                         # fender blisters over the wheels
        hw += 0.026 * math.exp(-((Y - ax) / 0.48) ** 2) * math.exp(-((w - 0.55) / 0.28) ** 2)
    # flanks tuck in toward the bumpers (rounded corners in plan)
    hw *= 1.0 - 0.050 * smooth((Y - (YF - 0.55)) / 0.55) ** 2 - 0.035 * smooth(((YR + 0.45) - Y) / 0.45) ** 2
    X = u * hw
    return (X, Y, Z)


# ------------------------------------------------------------------ cabin shape
_cabB = [(-1.0, DECK_Y), (-0.5, -0.94), (0.0, -0.24), (0.14, -0.10), (0.88, 0.78), (1.0, COWL_Y)]
_cabT = [(-1.0, -0.90), (-0.5, -0.74), (0.0, -0.38), (0.14, -0.26), (0.88, 0.05), (1.0, 0.10)]
_Yb = plin(_cabB)
_Yt = plin(_cabT)
_Zroof = pchip([(-1.0, 1.405), (-0.6, 1.452), (-0.25, 1.468), (0.05, 1.452), (0.15, 1.438)])


def cabin_pos(u, s, w):
    Yb, Yt = _Yb(s), _Yt(s)
    pb = body_pos(u, Yb, 1.0)
    rw = 0.705 - 0.045 * max(0.0, -s - 0.55) ** 2 - 0.05 * smooth((s - 0.55) / 0.45) ** 2
    pt = (u * rw, Yt, _Zroof(Yt) + 0.046 * (1 - u * u) - 0.022 * smooth((abs(u) - 0.55) / 0.45) ** 2)
    X = pb[0] + (pt[0] - pb[0]) * w
    Y = pb[1] + (pt[1] - pb[1]) * w
    Z = pb[2] + (pt[2] - pb[2]) * w
    sF = smooth((s - 0.80) / 0.2)
    sR = smooth((-0.80 - s) / 0.2)
    Y += (-0.11 * sF + 0.08 * sR) * u * u * w ** 0.6
    X += u * abs(u) ** 6 * 0.024 * math.sin(math.pi * w)
    # windscreen / backlight slight convexity
    Y += sF * 0.018 * math.sin(math.pi * w) * (1 - u * u)
    Y -= sR * 0.012 * math.sin(math.pi * w) * (1 - u * u)
    return (X, Y, Z)


# ================================================================== image textures
def _img_to_blender(name, path, colorspace="sRGB", alpha=True):
    img = bpy.data.images.get(name)
    if img is None:
        img = bpy.data.images.load(path)
        img.name = name
    img.colorspace_settings.name = colorspace
    try:
        img.pack()
    except Exception:
        pass
    return img


def make_textures(variant, cfg):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    os.makedirs(TEX_DIR, exist_ok=True)
    out = {}

    # ---- tyre sidewall lettering (height map, outer sidewall band)
    p = os.path.join(TEX_DIR, "tyre_side.png")
    if not os.path.exists(p):
        W, H = 8192, 320
        im = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(im)
        fb = ImageFont.truetype(FONT_X, 140)
        fs = ImageFont.truetype(FONT_B, 68)
        ft = ImageFont.truetype(FONT_M, 30)
        for k in range(2):
            x0 = k * W // 2
            d.text((x0 + 240, 80), "VANTERRA", font=fb, fill=255)
            d.text((x0 + 1240, 116), "ROADMASTER  A/S", font=fs, fill=235)
            d.text((x0 + 2360, 80), "225/55 R18", font=fb, fill=255)
            d.text((x0 + 3280, 128), "94V  M+S  TUBELESS", font=fs, fill=225)
            d.text((x0 + 1240, 210), "DOT 4XK9 R7T2 3125   MAX LOAD 670 kg   MAX PRESS 350 kPa", font=ft, fill=200)
        # moulded rim-protector rib ring + fine radial serration band near the bead
        d.rectangle((0, 16, W, 28), fill=150)
        for x in range(0, W, 6):
            d.line((x, 288, x, 316), fill=90, width=2)
        im = im.filter(ImageFilter.GaussianBlur(0.7))
        im.save(p)
    out["tyre_side"] = _img_to_blender("taxi_tyre_side", p, "Non-Color")

    if cfg["taxi"]:
        # ---- livery decal: top half = right side (u = Y), bottom half = left side (u = -Y)
        p = os.path.join(TEX_DIR, "livery_taxi.png")
        if not os.path.exists(p):
            W, HH = 4096, 640
            Y0, Y1, Z0, Z1 = -2.45, 2.45, 0.25, 1.00
            im = Image.new("RGBA", (W, 2 * HH), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)

            def px(Y, Z, half, flip):
                u = (-Y if flip else Y)
                x = (u - Y0) / (Y1 - Y0) * W
                y = (1 - (Z - Z0) / (Z1 - Z0)) * HH + half * HH
                return x, y

            def text(half, flip, Yc, Zc, s, font, fill, anchor="mm"):
                x, y = px(Yc, Zc, half, flip)
                d.text((x, y), s, font=font, fill=fill, anchor=anchor)

            f_big = ImageFont.truetype(FONT_X, 66)
            f_mid = ImageFont.truetype(FONT_B, 30)
            f_sm = ImageFont.truetype(FONT_M, 19)
            f_num = ImageFont.truetype(FONT_X, 58)
            blk = (12, 12, 12, 255)
            for half, flip in ((0, False), (1, True)):
                # checker band along the flank, under the shoulder line
                sq = 0.021
                Ys = -2.05
                n = int((2.05 + 1.98) / sq)
                for i in range(n):
                    for row in range(2):
                        Ya = Ys + i * sq
                        Za = 0.668 + row * sq
                        col = blk if (i + row) % 2 == 0 else (238, 236, 228, 255)
                        xa, ya = px(Ya, Za + sq, half, flip)
                        xb, yb = px(Ya + sq, Za, half, flip)
                        d.rectangle((min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb)), fill=col)
                # front door: company name + emblem
                text(half, flip, 0.30, 0.535, "HALLOWAY", f_big, blk)
                text(half, flip, 0.30, 0.47, "CAB  COMPANY", f_mid, blk)
                ex, ey = px(-0.08 if not flip else -0.08, 0.51, half, flip)
                ex, ey = px(-0.06, 0.51, half, flip)
                r = 34
                d.ellipse((ex - r, ey - r, ex + r, ey + r), outline=blk, width=6)
                d.text((ex, ey), "H", font=f_mid, fill=blk, anchor="mm")
                # rear door: licence + fare panel
                text(half, flip, -0.56, 0.58, "LICENSED  TAXICAB", f_mid, blk)
                x0, y0 = px(-0.84, 0.545, half, flip)
                x1, y1 = px(-0.28, 0.395, half, flip)
                d.rectangle((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), outline=blk, width=3)
                text(half, flip, -0.56, 0.522, "RATE OF FARE", f_sm, blk)
                text(half, flip, -0.56, 0.49, "$3.20  UPON ENTRY", f_sm, blk)
                text(half, flip, -0.56, 0.462, "$0.75  PER 1/5 MILE", f_sm, blk)
                text(half, flip, -0.56, 0.434, "$0.75  PER 60 SEC STOPPED", f_sm, blk)
                text(half, flip, -0.56, 0.408, "NIGHT SURCHARGE  $1.00", f_sm, blk)
                # medallion number on the front fender
                text(half, flip, 1.36, 0.80, "7K42", f_num, blk)
                text(half, flip, -1.55, 0.86, "HC-7K42", f_sm, blk)
            im.save(p)
        out["livery"] = _img_to_blender("taxi_livery", p, "sRGB")

        p = os.path.join(TEX_DIR, "roofsign.png")
        if not os.path.exists(p):
            W, H = 1024, 384
            im = Image.new("RGB", (W, H), (250, 246, 236))
            d = ImageDraw.Draw(im)
            d.rectangle((0, 0, W, 40), fill=(20, 20, 20))
            d.rectangle((0, H - 40, W, H), fill=(20, 20, 20))
            d.text((W // 2, H // 2 - 26), "TAXI", font=ImageFont.truetype(FONT_X, 170), fill=(18, 18, 18), anchor="mm")
            d.text((W // 2, H - 92), "7K42", font=ImageFont.truetype(FONT_B, 60), fill=(18, 18, 18), anchor="mm")
            d.text((W - 120, 20), "HC", font=ImageFont.truetype(FONT_B, 26), fill=(240, 200, 40), anchor="mm")
            im.save(p)
        out["roofsign"] = _img_to_blender("taxi_roofsign", p, "sRGB")

    # ---- licence plate (invented state "HARBOR STATE")
    num, foot = cfg["plate"]
    p = os.path.join(TEX_DIR, "plate_%s.png" % num.replace(" ", "_"))
    if not os.path.exists(p):
        W, H = 1024, 512
        im = Image.new("RGB", (W, H), (236, 234, 226))
        d = ImageDraw.Draw(im)
        for y in range(H):  # faint blue to white gradient background
            t = y / H
            c = (int(236 - 50 * (1 - t) ** 3), int(234 - 30 * (1 - t) ** 3), int(226 + 10 * (1 - t) ** 3))
            d.line((0, y, W, y), fill=c)
        d.rounded_rectangle((6, 6, W - 6, H - 6), radius=28, outline=(30, 50, 120), width=10)
        d.text((W // 2, 62), "HARBOR  STATE", font=ImageFont.truetype(FONT_B, 54), fill=(25, 45, 120), anchor="mm")
        d.text((W // 2, 272), num, font=ImageFont.truetype(FONT_D, 172), fill=(28, 28, 34), anchor="mm")
        d.text((W // 2, 452), foot, font=ImageFont.truetype(FONT_B, 50),
               fill=(160, 30, 30) if foot == "TAXI" else (25, 45, 120), anchor="mm")
        for cx in (W * 0.22, W * 0.78):
            d.ellipse((cx - 16, 120 - 16, cx + 16, 120 + 16), fill=(150, 150, 150))
        im.save(p)
    out["plate"] = _img_to_blender("taxi_plate_" + num.replace(" ", "_"), p, "sRGB")
    return out


# ================================================================== materials
def _n(nt, t, x=0, y=0, **kw):
    n = nt.nodes.new(t)
    n.location = (x, y)
    for k, v in kw.items():
        if k in n.inputs:
            n.inputs[k].default_value = v
        else:
            setattr(n, k, v)
    return n


def _l(nt, a, b):
    nt.links.new(a, b)


def _math(nt, op, a, b=None, clamp=False):
    m = nt.nodes.new("ShaderNodeMath")
    m.operation = op
    m.use_clamp = clamp
    for idx, val in ((0, a), (1, b)):
        if val is None:
            continue
        if isinstance(val, (int, float)):
            m.inputs[idx].default_value = val
        else:
            nt.links.new(val, m.inputs[idx])
    return m.outputs[0]


def _maprange(nt, val, a, b, c=0.0, d=1.0, clamp=True, interp="LINEAR"):
    m = nt.nodes.new("ShaderNodeMapRange")
    m.interpolation_type = interp
    m.clamp = clamp
    nt.links.new(val, m.inputs["Value"])
    m.inputs["From Min"].default_value = a
    m.inputs["From Max"].default_value = b
    m.inputs["To Min"].default_value = c
    m.inputs["To Max"].default_value = d
    return m.outputs["Result"]


def _inp(node, ident):
    for i in node.inputs:
        if i.identifier == ident:
            return i
    raise KeyError(ident)


def _outp(node, ident):
    for o in node.outputs:
        if o.identifier == ident:
            return o
    raise KeyError(ident)


def _mixc(nt, fac, a, b):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "RGBA"
    for inp, val in ((_inp(m, "Factor_Float"), fac), (_inp(m, "A_Color"), a), (_inp(m, "B_Color"), b)):
        if isinstance(val, (int, float)):
            inp.default_value = val
        elif isinstance(val, tuple):
            inp.default_value = val if len(val) == 4 else val + (1.0,)
        else:
            nt.links.new(val, inp)
    return _outp(m, "Result_Color")


def _mixf(nt, fac, a, b):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "FLOAT"
    for inp, val in ((_inp(m, "Factor_Float"), fac), (_inp(m, "A_Float"), a), (_inp(m, "B_Float"), b)):
        if isinstance(val, (int, float)):
            inp.default_value = val
        else:
            nt.links.new(val, inp)
    return _outp(m, "Result_Float")


def _new_mat(name):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = _n(nt, "ShaderNodeOutputMaterial", 900, 0)
    bsdf = _n(nt, "ShaderNodeBsdfPrincipled", 600, 0)
    _l(nt, bsdf.outputs[0], out.inputs["Surface"])
    return m, nt, bsdf


def _texco(nt):
    t = _n(nt, "ShaderNodeTexCoord", -1200, 0)
    return t


def _set(bsdf, **kw):
    for k, v in kw.items():
        bsdf.inputs[k.replace("_", " ")].default_value = v


def mat_simple(name, color, rough=0.5, metal=0.0, bump=0.0, bump_scale=300.0, coat=0.0, spec=0.5,
               emission=None, estrength=0.0, transmission=0.0, ior=1.45, alpha=1.0):
    m, nt, b = _new_mat(name)
    b.inputs["Base Color"].default_value = color + (1.0,) if len(color) == 3 else color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Specular IOR Level"].default_value = spec
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = ior
    b.inputs["Alpha"].default_value = alpha
    if emission:
        b.inputs["Emission Color"].default_value = emission + (1.0,)
        b.inputs["Emission Strength"].default_value = estrength
    if bump > 0:
        tc = _texco(nt)
        nz = _n(nt, "ShaderNodeTexNoise", -800, -300, Scale=bump_scale, Detail=6.0, Roughness=0.6)
        _l(nt, tc.outputs["Object"], nz.inputs["Vector"])
        bp = _n(nt, "ShaderNodeBump", 200, -300, Strength=bump, Distance=0.0006)
        _l(nt, nz.outputs["Fac"], bp.inputs["Height"])
        _l(nt, bp.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_paint(name, cfg, textures, dirt):
    """Multi-layer car paint: base + flake + clearcoat w/ orange peel, grime graded from the
    sills, splash behind the wheels, sparse stone chips, scuffed front-left bumper corner,
    vinyl livery decal."""
    m, nt, b = _new_mat(name)
    tc = _texco(nt)
    obj = tc.outputs["Object"]
    sep = _n(nt, "ShaderNodeSeparateXYZ", -1000, 400)
    _l(nt, obj, sep.inputs["Vector"])
    X, Y, Z = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]

    # orange peel on the clearcoat
    op = _n(nt, "ShaderNodeTexNoise", -800, -500, Scale=260.0, Detail=2.0, Roughness=0.5)
    _l(nt, obj, op.inputs["Vector"])
    opb = _n(nt, "ShaderNodeBump", 200, -500, Strength=0.05, Distance=0.0003)
    _l(nt, op.outputs["Fac"], opb.inputs["Height"])
    # metallic flake in the base layer
    fl = _n(nt, "ShaderNodeTexVoronoi", -800, -800, Scale=2200.0)
    _l(nt, obj, fl.inputs["Vector"])
    flb = _n(nt, "ShaderNodeBump", 200, -800, Strength=cfg["flake"], Distance=0.0002)
    _l(nt, fl.outputs["Distance"], flb.inputs["Height"])

    # ---- grime: graded up from the sills, broken up by noise, heavier behind wheels
    gz = _maprange(nt, Z, 0.20, 0.40, 1.0, 0.0, interp="SMOOTHSTEP")
    gz = _math(nt, "POWER", gz, 1.6)
    gn = _n(nt, "ShaderNodeTexNoise", -800, 600, Scale=7.0, Detail=10.0, Roughness=0.62)
    _l(nt, obj, gn.inputs["Vector"])
    gn2 = _n(nt, "ShaderNodeTexNoise", -800, 800, Scale=55.0, Detail=6.0, Roughness=0.7)
    _l(nt, obj, gn2.inputs["Vector"])
    gnn = _maprange(nt, gn.outputs["Fac"], 0.35, 0.68, 0.35, 1.0)
    # splash ring behind each wheel (toward the rear of the arch)
    splash = None
    for ax in (AXF, AXR):
        cc = _n(nt, "ShaderNodeCombineXYZ", -900, 1000, X=0.0, Y=ax - 0.12, Z=WHEEL_Z)
        vs = nt.nodes.new("ShaderNodeVectorMath")
        vs.operation = "MULTIPLY"
        _l(nt, obj, vs.inputs[0])
        vs.inputs[1].default_value = (0.0, 1.0, 1.0)
        dd = nt.nodes.new("ShaderNodeVectorMath")
        dd.operation = "DISTANCE"
        _l(nt, vs.outputs[0], dd.inputs[0])
        _l(nt, cc.outputs[0], dd.inputs[1])
        ring = _maprange(nt, dd.outputs["Value"], 0.58, 0.42, 0.0, 1.0, interp="SMOOTHSTEP")
        # only the trailing half of the arch, and only below the hub-ish line
        ring = _math(nt, "MULTIPLY", ring, _maprange(nt, Y, ax - 0.05, ax - 0.40))
        ring = _math(nt, "MULTIPLY", ring, _maprange(nt, Z, 0.62, 0.36))
        splash = ring if splash is None else _math(nt, "MAXIMUM", splash, ring)
    grime = _math(nt, "MAXIMUM", gz, _math(nt, "MULTIPLY", splash, 0.75))
    grime = _math(nt, "MULTIPLY", grime, gnn)
    grime = _math(nt, "MULTIPLY", grime, dirt, clamp=True)

    # ---- chips: sparse, only low on the body and on the nose
    cn = _n(nt, "ShaderNodeTexNoise", -800, 1200, Scale=38.0, Detail=12.0, Roughness=0.75)
    _l(nt, obj, cn.inputs["Vector"])
    chip = _maprange(nt, cn.outputs["Fac"], 0.715, 0.735)
    zone = _math(nt, "MAXIMUM", _maprange(nt, Z, 0.52, 0.30), _maprange(nt, Y, 2.15, 2.35))
    chip = _math(nt, "MULTIPLY", chip, zone)
    # ---- scuff on the front-left bumper corner
    sc0 = _n(nt, "ShaderNodeCombineXYZ", -900, 1400, X=-0.80, Y=2.17, Z=0.46)
    sd = nt.nodes.new("ShaderNodeVectorMath")
    sd.operation = "DISTANCE"
    _l(nt, obj, sd.inputs[0])
    _l(nt, sc0.outputs[0], sd.inputs[1])
    szone = _maprange(nt, sd.outputs["Value"], 0.17, 0.05, interp="SMOOTHSTEP")
    smap = _n(nt, "ShaderNodeMapping", -900, 1600)
    _l(nt, obj, smap.inputs["Vector"])
    smap.inputs["Scale"].default_value = (4.0, 4.0, 160.0)
    scn = _n(nt, "ShaderNodeTexNoise", -700, 1600, Scale=3.0, Detail=4.0, Roughness=0.6)
    _l(nt, smap.outputs[0], scn.inputs["Vector"])
    scuff = _math(nt, "MULTIPLY", _maprange(nt, scn.outputs["Fac"], 0.5, 0.62), szone)

    paint = cfg["paint"] + (1.0,)
    col = _mixc(nt, 0.0, paint, paint)
    if cfg["taxi"] and "livery" in textures:
        # decal coords: u = (Y*sign(X) + 2.45)/4.9, v = half + (Z-0.25)/0.75 * 0.5
        sg = _math(nt, "SIGN", X)
        uu = _math(nt, "MULTIPLY", Y, sg)
        uu = _math(nt, "ADD", uu, 2.45)
        uu = _math(nt, "DIVIDE", uu, 4.9)
        vv = _maprange(nt, Z, 0.25, 1.0, 0.0, 0.5, clamp=False)
        half = _maprange(nt, X, -0.01, 0.01, 0.0, 0.5)  # right side -> top half
        vv = _math(nt, "ADD", vv, half)
        cxyz = _n(nt, "ShaderNodeCombineXYZ", -300, 200)
        _l(nt, uu, cxyz.inputs["X"])
        _l(nt, vv, cxyz.inputs["Y"])
        im = _n(nt, "ShaderNodeTexImage", -100, 200)
        im.image = textures["livery"]
        im.extension = "CLIP"
        im.interpolation = "Cubic"
        _l(nt, cxyz.outputs[0], im.inputs["Vector"])
        side = _maprange(nt, _math(nt, "ABSOLUTE", X), 0.70, 0.78)
        zlim = _math(nt, "MULTIPLY", _maprange(nt, Z, 0.25, 0.26), _maprange(nt, Z, 0.99, 0.985))
        a = _math(nt, "MULTIPLY", im.outputs["Alpha"], side)
        a = _math(nt, "MULTIPLY", a, zlim)
        # decals are under the dirt but above the paint; slightly weathered (noise breakup)
        wear = _maprange(nt, gn2.outputs["Fac"], 0.70, 0.78, 1.0, 0.35)
        a = _math(nt, "MULTIPLY", a, wear)
        col = _mixc(nt, a, paint, im.outputs["Color"])
    dirt_col = (0.115, 0.098, 0.080, 1.0)
    col = _mixc(nt, chip, col, (0.30, 0.30, 0.29, 1.0))
    col = _mixc(nt, _math(nt, "MULTIPLY", scuff, 0.85), col, (0.55, 0.53, 0.49, 1.0))
    col = _mixc(nt, _math(nt, "MULTIPLY", grime, 0.80), col, dirt_col)
    _l(nt, col, b.inputs["Base Color"])
    b.inputs["Metallic"].default_value = cfg["metal"]
    rough = _mixf(nt, grime, cfg.get("base_rough", 0.22), 0.80)
    rough = _math(nt, "MAXIMUM", rough, _math(nt, "MULTIPLY", chip, 0.6))
    _l(nt, rough, b.inputs["Roughness"])
    coat = _math(nt, "SUBTRACT", 1.0, _math(nt, "MAXIMUM", _math(nt, "MULTIPLY", grime, 0.95),
                                               _math(nt, "MAXIMUM", chip, scuff)), clamp=True)
    _l(nt, coat, b.inputs["Coat Weight"])
    b.inputs["Coat Roughness"].default_value = cfg["coat_rough"]
    b.inputs["Coat IOR"].default_value = 1.5
    _l(nt, opb.outputs["Normal"], b.inputs["Coat Normal"])
    _l(nt, flb.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_glass(name, tint=(0.86, 0.93, 0.90), dirt=0.5, wiper=False, frit=False):
    """Glass with road dust; on the windscreen the two wiper sweeps are clean."""
    m, nt, b = _new_mat(name)
    tc = _texco(nt)
    obj = tc.outputs["Object"]
    sep = _n(nt, "ShaderNodeSeparateXYZ", -1000, 400)
    _l(nt, obj, sep.inputs["Vector"])
    dn = _n(nt, "ShaderNodeTexNoise", -800, 600, Scale=18.0, Detail=10.0, Roughness=0.65)
    _l(nt, obj, dn.inputs["Vector"])
    dn2 = _n(nt, "ShaderNodeTexNoise", -800, 800, Scale=160.0, Detail=4.0, Roughness=0.7)
    _l(nt, obj, dn2.inputs["Vector"])
    dust = _math(nt, "MULTIPLY", _maprange(nt, dn.outputs["Fac"], 0.35, 0.70, 0.15, 1.0),
                 _maprange(nt, dn2.outputs["Fac"], 0.3, 0.7, 0.5, 1.0))
    # more dust low on the glass
    dust = _math(nt, "MULTIPLY", dust, _maprange(nt, sep.outputs["Z"], 1.45, 1.0, 0.45, 1.0))
    if wiper:
        clean = None
        for px_, rr in ((-0.42, 0.58), (0.18, 0.62)):
            # pivots sit at the cowl; sweep radius rr measured in the glass plane (approx XY+Z)
            cc = _n(nt, "ShaderNodeCombineXYZ", -900, 1000, X=px_, Y=0.88, Z=0.975)
            dd = nt.nodes.new("ShaderNodeVectorMath")
            dd.operation = "DISTANCE"
            _l(nt, obj, dd.inputs[0])
            _l(nt, cc.outputs[0], dd.inputs[1])
            r = _maprange(nt, dd.outputs["Value"], rr, rr - 0.03, 0.0, 1.0)
            rin = _maprange(nt, dd.outputs["Value"], 0.10, 0.13, 0.0, 1.0)
            r = _math(nt, "MULTIPLY", r, rin)
            clean = r if clean is None else _math(nt, "MAXIMUM", clean, r)
        dust = _math(nt, "MULTIPLY", dust, _math(nt, "SUBTRACT", 1.0, _math(nt, "MULTIPLY", clean, 0.85)))
    dust = _math(nt, "MULTIPLY", dust, dirt, clamp=True)
    b.inputs["Base Color"].default_value = tint + (1.0,)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.52
    b.inputs["Specular Tint"].default_value = (0.88, 0.97, 0.93, 1.0)
    rough = _mixf(nt, dust, 0.0, 0.12)
    _l(nt, rough, b.inputs["Roughness"])
    # dust is a thin diffuse layer on top: use coat tint-less, plus sheen-like whitening via mix shader
    diff = _n(nt, "ShaderNodeBsdfDiffuse", 300, -300)
    diff.inputs["Color"].default_value = (0.42, 0.40, 0.36, 1.0)
    mix = _n(nt, "ShaderNodeMixShader", 760, 0)
    _l(nt, _math(nt, "MULTIPLY", dust, 0.07), mix.inputs[0])
    _l(nt, b.outputs[0], mix.inputs[1])
    _l(nt, diff.outputs[0], mix.inputs[2])
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    _l(nt, mix.outputs[0], out.inputs["Surface"])
    return m


def mat_tyre(name, tex):
    m, nt, b = _new_mat(name)
    tc = _texco(nt)
    im = _n(nt, "ShaderNodeTexImage", -600, -300)
    im.image = tex["tyre_side"]
    im.extension = "CLIP"
    _l(nt, tc.outputs["UV"], im.inputs["Vector"])
    nz = _n(nt, "ShaderNodeTexNoise", -600, -600, Scale=900.0, Detail=4.0)
    _l(nt, tc.outputs["Object"], nz.inputs["Vector"])
    h = _math(nt, "ADD", im.outputs["Color"], _math(nt, "MULTIPLY", nz.outputs["Fac"], 0.15))
    bp = _n(nt, "ShaderNodeBump", 200, -300, Strength=1.0, Distance=0.0016)
    _l(nt, h, bp.inputs["Height"])
    _l(nt, bp.outputs["Normal"], b.inputs["Normal"])
    # brownish road dust on the lower sidewall / tread shoulders, cleaner letters
    dn = _n(nt, "ShaderNodeTexNoise", -600, 300, Scale=30.0, Detail=8.0)
    _l(nt, tc.outputs["Object"], dn.inputs["Vector"])
    # dust settles in the tread grooves and the occluded lower sidewall, letters stay cleaner
    ao = _n(nt, "ShaderNodeAmbientOcclusion", -600, 500, Distance=0.012)
    ao.samples = 6
    groove = _maprange(nt, ao.outputs["AO"], 0.9, 0.5, 0.0, 1.0)
    dust = _math(nt, "MULTIPLY", _maprange(nt, dn.outputs["Fac"], 0.35, 0.7, 0.25, 1.0),
                 _math(nt, "MAXIMUM", groove, 0.18))
    dust = _math(nt, "MULTIPLY", dust, 0.55)
    col = _mixc(nt, dust, (0.011, 0.011, 0.011, 1.0), (0.085, 0.082, 0.076, 1.0))
    col = _mixc(nt, _math(nt, "MULTIPLY", im.outputs["Color"], 0.55), col, (0.035, 0.035, 0.035, 1.0))
    _l(nt, col, b.inputs["Base Color"])
    _l(nt, _mixf(nt, dust, 0.55, 0.92), b.inputs["Roughness"])
    b.inputs["Specular IOR Level"].default_value = 0.40
    return m


def mat_rim(name, kind):
    """Painted alloy; brake dust collects in occluded areas and toward the barrel."""
    m, nt, b = _new_mat(name)
    base = (0.30, 0.31, 0.32, 1.0) if kind == "silver" else (0.04, 0.04, 0.045, 1.0)
    ao = _n(nt, "ShaderNodeAmbientOcclusion", -600, 300, Distance=0.05)
    ao.samples = 8
    tc = _texco(nt)
    dn = _n(nt, "ShaderNodeTexNoise", -600, 500, Scale=90.0, Detail=8.0)
    _l(nt, tc.outputs["Object"], dn.inputs["Vector"])
    dust = _math(nt, "MULTIPLY", _maprange(nt, ao.outputs["AO"], 0.95, 0.35, 0.15, 1.0),
                 _maprange(nt, dn.outputs["Fac"], 0.3, 0.7, 0.55, 1.0))
    col = _mixc(nt, _math(nt, "MULTIPLY", dust, 0.75), base, (0.09, 0.075, 0.06, 1.0))
    _l(nt, col, b.inputs["Base Color"])
    b.inputs["Metallic"].default_value = 0.85
    _l(nt, _mixf(nt, dust, 0.22, 0.7), b.inputs["Roughness"])
    b.inputs["Coat Weight"].default_value = 0.6
    _l(nt, _mixf(nt, dust, 0.05, 0.6), b.inputs["Coat Roughness"])
    return m


def mat_machined(name):
    """Diamond-cut alloy face: bright bare aluminium, fine concentric lathe marks, clear lacquer."""
    m, nt, b = _new_mat(name)
    tc = _texco(nt)
    sep = _n(nt, "ShaderNodeSeparateXYZ", -900, 0)
    _l(nt, tc.outputs["Object"], sep.inputs["Vector"])
    r = _math(nt, "SQRT", _math(nt, "ADD", _math(nt, "MULTIPLY", sep.outputs["Y"], sep.outputs["Y"]),
                                _math(nt, "MULTIPLY", sep.outputs["Z"], sep.outputs["Z"])))
    rings = _math(nt, "SINE", _math(nt, "MULTIPLY", r, 9000.0))
    bp = _n(nt, "ShaderNodeBump", 200, -300, Strength=0.05, Distance=0.0001)
    _l(nt, rings, bp.inputs["Height"])
    _l(nt, bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Base Color"].default_value = (0.86, 0.86, 0.87, 1.0)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.14
    b.inputs["Anisotropic"].default_value = 0.6
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.03
    return m


def mat_image(name, img, rough=0.4, emission=0.0, metal=0.0, coat=0.0):
    m, nt, b = _new_mat(name)
    tc = _texco(nt)
    im = _n(nt, "ShaderNodeTexImage", -400, 0)
    im.image = img
    im.interpolation = "Cubic"
    _l(nt, tc.outputs["UV"], im.inputs["Vector"])
    _l(nt, im.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    if emission > 0:
        _l(nt, im.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emission
    return m


def mat_lens(name, color, rough=0.02, pattern=0.0):
    """Lamp lens: clear/tinted polycarbonate, optional fine optic ribs."""
    m, nt, b = _new_mat(name)
    b.inputs["Base Color"].default_value = color + (1.0,)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.58
    b.inputs["Roughness"].default_value = rough
    if pattern > 0:
        tc = _texco(nt)
        wv = _n(nt, "ShaderNodeTexWave", -400, -300, Scale=180.0, Distortion=0.0)
        wv.wave_type = "BANDS"
        wv.bands_direction = "Z"
        _l(nt, tc.outputs["Object"], wv.inputs["Vector"])
        bp = _n(nt, "ShaderNodeBump", 200, -300, Strength=pattern, Distance=0.0005)
        _l(nt, wv.outputs["Fac"], bp.inputs["Height"])
        _l(nt, bp.outputs["Normal"], b.inputs["Normal"])
    return m


def _get(fn, name):
    """Reuse a shared material if it already exists (several cars per file), else build it."""
    m = bpy.data.materials.get(name)
    return m if m is not None else fn()


def build_materials(variant, cfg, tex, dirt, tag=None):
    sfx = "_" + (tag or variant)
    M = {}
    M["paint"] = _get(lambda: mat_paint("taxi_paint" + sfx, cfg, tex, dirt), "taxi_paint" + sfx)
    M["inner"] = _get(lambda: mat_simple("taxi_inner" + sfx, (0.045, 0.045, 0.047), rough=0.7), "taxi_inner" + sfx)
    M["black_tex"] = _get(lambda: mat_simple("taxi_black_plastic", (0.022, 0.022, 0.023), rough=0.62, bump=0.25, bump_scale=900.0), "taxi_black_plastic")
    M["black_gloss"] = _get(lambda: mat_simple("taxi_black_gloss", (0.008, 0.008, 0.009), rough=0.08, coat=1.0), "taxi_black_gloss")
    M["rubber"] = _get(lambda: mat_simple("taxi_rubber", (0.018, 0.018, 0.018), rough=0.7, spec=0.3), "taxi_rubber")
    M["chrome"] = _get(lambda: mat_simple("taxi_chrome", (0.92, 0.92, 0.92), rough=0.04, metal=1.0), "taxi_chrome")
    M["satin"] = _get(lambda: mat_simple("taxi_satin_alu", (0.6, 0.6, 0.62), rough=0.28, metal=1.0), "taxi_satin_alu")
    M["trim"] = M["chrome"] if cfg["trim"] == "chrome" else M["black_gloss"]
    M["glass_ws"] = _get(lambda: mat_glass("taxi_glass_ws" + sfx, dirt=dirt, wiper=True), "taxi_glass_ws" + sfx)
    M["glass"] = _get(lambda: mat_glass("taxi_glass" + sfx, tint=(0.78, 0.86, 0.83), dirt=dirt * 0.6), "taxi_glass" + sfx)
    M["frit"] = _get(lambda: mat_simple("taxi_glass_frit", (0.006, 0.006, 0.007), rough=0.45, coat=1.0, spec=0.3), "taxi_glass_frit")
    M["machined"] = _get(lambda: mat_machined("taxi_rim_machined"), "taxi_rim_machined")
    M["lamp_chrome"] = _get(lambda: mat_simple("taxi_lamp_chrome", (0.80, 0.80, 0.82), rough=0.06, metal=1.0), "taxi_lamp_chrome")
    M["lamp_black"] = _get(lambda: mat_simple("taxi_lamp_black", (0.012, 0.012, 0.013), rough=0.35, coat=0.0), "taxi_lamp_black")
    M["mirror"] = _get(lambda: mat_simple("taxi_mirror", (0.85, 0.87, 0.88), rough=0.02, metal=1.0), "taxi_mirror")
    M["lens_clear"] = _get(lambda: mat_lens("taxi_lens_clear", (0.96, 0.97, 0.97), rough=0.01), "taxi_lens_clear")
    M["lens_red"] = _get(lambda: mat_lens("taxi_lens_red", (0.75, 0.025, 0.02), rough=0.02, pattern=0.08), "taxi_lens_red")
    M["lens_amber"] = _get(lambda: mat_lens("taxi_lens_amber", (0.95, 0.42, 0.02), rough=0.02), "taxi_lens_amber")
    M["reflector"] = _get(lambda: mat_simple("taxi_reflector", (0.9, 0.9, 0.92), rough=0.08, metal=1.0), "taxi_reflector")
    M["housing"] = _get(lambda: mat_simple("taxi_lamp_housing", (0.55, 0.55, 0.57), rough=0.16, metal=1.0), "taxi_lamp_housing")
    M["drl"] = _get(lambda: mat_simple("taxi_drl", (0.9, 0.95, 1.0), rough=0.3, emission=(0.86, 0.93, 1.0), estrength=14.0), "taxi_drl")
    M["tail_led"] = _get(lambda: mat_simple("taxi_tail_led", (0.6, 0.02, 0.01), rough=0.3, emission=(1.0, 0.03, 0.01), estrength=9.0), "taxi_tail_led")
    M["amber_led"] = _get(lambda: mat_simple("taxi_amber_led", (0.8, 0.35, 0.0), rough=0.4), "taxi_amber_led")
    M["tyre"] = _get(lambda: mat_tyre("taxi_tyre", tex), "taxi_tyre")
    M["rim"] = _get(lambda: mat_rim("taxi_rim_" + cfg["rims"], cfg["rims"]), "taxi_rim_" + cfg["rims"])
    M["disc"] = _get(lambda: mat_simple("taxi_brake_disc", (0.16, 0.15, 0.145), rough=0.32, metal=0.85, bump=0.15, bump_scale=600.0), "taxi_brake_disc")
    M["caliper"] = _get(lambda: mat_simple("taxi_caliper", (0.10, 0.10, 0.105), rough=0.45, metal=0.3), "taxi_caliper")
    M["liner"] = _get(lambda: mat_simple("taxi_liner", (0.012, 0.012, 0.012), rough=0.85, bump=0.4, bump_scale=200.0), "taxi_liner")
    M["under"] = _get(lambda: mat_simple("taxi_underbody", (0.02, 0.02, 0.02), rough=0.9), "taxi_underbody")
    M["seat"] = _get(lambda: mat_simple("taxi_seat_vinyl", (0.028, 0.028, 0.03), rough=0.42, bump=0.12, bump_scale=420.0), "taxi_seat_vinyl")
    M["dash"] = _get(lambda: mat_simple("taxi_dash", (0.035, 0.035, 0.037), rough=0.62, bump=0.2, bump_scale=700.0), "taxi_dash")
    M["headliner"] = _get(lambda: mat_simple("taxi_headliner", (0.30, 0.29, 0.27), rough=0.95), "taxi_headliner")
    M["carpet"] = _get(lambda: mat_simple("taxi_carpet", (0.03, 0.03, 0.032), rough=1.0, bump=0.5, bump_scale=1500.0), "taxi_carpet")
    M["screen"] = _get(lambda: mat_simple("taxi_screen", (0.02, 0.03, 0.05), rough=0.05, emission=(0.25, 0.45, 0.9), estrength=1.2), "taxi_screen")
    M["perspex"] = _get(lambda: mat_simple("taxi_perspex", (0.95, 0.95, 0.95), rough=0.03, transmission=1.0, ior=1.49), "taxi_perspex")
    M["plate"] = _get(lambda: mat_image("taxi_plate_" + cfg["plate"][0].replace(" ", "_"), tex["plate"], rough=0.35, coat=0.3), "taxi_plate_" + cfg["plate"][0].replace(" ", "_"))
    if cfg["taxi"]:
        M["roofsign"] = _get(lambda: mat_image("taxi_roofsign", tex["roofsign"], rough=0.25, emission=1.6), "taxi_roofsign")
        M["sign_body"] = _get(lambda: mat_simple("taxi_sign_body", (0.85, 0.83, 0.78), rough=0.3), "taxi_sign_body")
    return M


# ================================================================== object helpers
def obj_from_mesh(name, me, coll, mats=(), parent=None):
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    for mt in mats:
        me.materials.append(mt)
    if parent:
        ob.parent = parent
    return ob


def add_bevel(ob, width=0.0008, segs=2, angle=30.0):
    """Tight bevel on hard edges: they catch a thin highlight instead of a soft roll."""
    md = ob.modifiers.new("EdgeBevel", "BEVEL")
    md.width = width
    md.segments = segs
    md.limit_method = "ANGLE"
    md.angle_limit = math.radians(angle)
    md.harden_normals = False
    return md


def add_subsurf(ob, levels=1, render=2):
    md = ob.modifiers.new("Subdivision", "SUBSURF")
    md.levels = levels
    md.render_levels = render
    md.boundary_smooth = "PRESERVE_CORNERS"
    return md


def bm_to_obj(name, bm, coll, mats=(), parent=None, smooth=True, sharp=None):
    """sharp: mark edges whose face angle exceeds this (degrees) as sharp, so hard machined
    edges shade crisply instead of rolling off (smooth shading elsewhere)."""
    if sharp is not None:
        lim = math.radians(sharp)
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim:
                e.smooth = False
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    return obj_from_mesh(name, me, coll, mats, parent)


def lathe(profile, segments, axis="X", close=False, uv_v=None, angle=2 * math.pi, start=0.0):
    """profile: list of (a, r) with a along the axis. Returns bmesh."""
    bm = bmesh.new()
    rings = []
    full = abs(angle - 2 * math.pi) < 1e-6
    nseg = segments if full else segments + 1
    for s in range(nseg):
        th = start + angle * s / segments
        ring = []
        for (a, r) in profile:
            if axis == "X":
                co = (a, r * math.sin(th), r * math.cos(th))
            else:
                co = (r * math.cos(th), r * math.sin(th), a)
            ring.append(bm.verts.new(co))
        rings.append(ring)
    uvl = bm.loops.layers.uv.new("UVMap")
    nprof = len(profile)
    for s in range(segments):
        r0 = rings[s]
        r1 = rings[(s + 1) % nseg] if full else rings[s + 1]
        for i in range(nprof - 1):
            f = bm.faces.new((r0[i], r0[i + 1], r1[i + 1], r1[i]))
            uvs = ((s, i), (s, i + 1), (s + 1, i + 1), (s + 1, i))
            for lp, (ss, ii) in zip(f.loops, uvs):
                vv = uv_v[ii] if uv_v else ii / (nprof - 1)
                lp[uvl].uv = (ss / segments, vv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def sweep_tube(points, radius, segs=8, closed=False, scale_xy=(1.0, 1.0), up=Vector((0, 0, 1))):
    """Simple tube along a polyline (for trims, lips, wipers, DRL guides). radius may be a
    list (one per point) for tapered parts."""
    bm = bmesh.new()
    pts = [Vector(p) for p in points]
    radii = list(radius) if isinstance(radius, (list, tuple)) else [radius] * len(pts)
    rings = []
    n = len(pts)
    for i, p in enumerate(pts):
        if closed:
            t = (pts[(i + 1) % n] - pts[i - 1]).normalized()
        else:
            t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        upv = up if abs(t.dot(up)) < 0.95 else Vector((1, 0, 0))
        x = t.cross(upv).normalized()
        y = x.cross(t).normalized()
        ring = []
        for s in range(segs):
            a = 2 * math.pi * s / segs
            off = x * math.cos(a) * radii[i] * scale_xy[0] + y * math.sin(a) * radii[i] * scale_xy[1]
            ring.append(bm.verts.new(p + off))
        rings.append(ring)
    m = n if closed else n - 1
    for i in range(m):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for s in range(segs):
            bm.faces.new((r0[s], r0[(s + 1) % segs], r1[(s + 1) % segs], r1[s]))
    if not closed:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def loft(stations, segs=24):
    """Closed loft along +X through superellipse sections.
    stations: (x, cy, cz, half_depth_front, half_depth_rear, half_height, exp_front, exp_rear)
    in the YZ plane. Ends are capped with a fan (meant for a Subdivision modifier)."""
    bm = bmesh.new()
    rings = []
    for (x, cy, cz, hf, hr, hh, ef, er) in stations:
        ring = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            c, s_ = math.cos(a), math.sin(a)
            e = ef if c >= 0 else er
            yy = cy + (hf if c >= 0 else hr) * math.copysign(abs(c) ** (2.0 / e), c)
            zz = cz + hh * math.copysign(abs(s_) ** (2.0 / e), s_)
            ring.append(bm.verts.new((x, yy, zz)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(segs):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % segs], rings[i + 1][(k + 1) % segs], rings[i + 1][k]))
    for ring, rev in ((rings[0], True), (rings[-1], False)):
        c = bm.verts.new(sum((v.co for v in ring), Vector()) / len(ring))
        for k in range(segs):
            f = (c, ring[k], ring[(k + 1) % segs])
            bm.faces.new(f[::-1] if rev else f)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def rounded_box(name, size, coll, mats, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), sup=0.18,
                levels=2, shape=None):
    """Box cage with support loops -> subdivided rounded block. shape(u,v,w)->offset fn."""
    sx, sy, sz = size
    U = [-1, -1 + sup, -0.5, 0, 0.5, 1 - sup, 1]
    V = [-1, -1 + sup, -0.5, 0, 0.5, 1 - sup, 1]
    W = [0, sup * 0.5, 0.25, 0.5, 0.75, 1 - sup * 0.5, 1]

    def pos(u, v, w):
        p = [u * sx / 2, v * sy / 2, (w - 0.5) * sz]
        if shape:
            d = shape(u, v, w)
            p = [p[0] + d[0], p[1] + d[1], p[2] + d[2]]
        return tuple(p)
    lat = Lattice(U, V, W, pos)
    me = mesh_from_faces(name, lat, lat.faces, uv_scale=1.0)
    ob = obj_from_mesh(name, me, coll, mats, parent)
    ob.location = loc
    ob.rotation_euler = rot
    add_subsurf(ob, levels - 1 if levels > 1 else 1, levels)
    return ob


# ================================================================== body
GU, GW, GY = 0.0022, 0.0026, 0.002      # half panel gap in u / w / metres
SU, SW, SY = 0.012, 0.014, 0.011        # support loop distance


def body_rules():
    S_SIDE = "RL"
    strips = [
        (S_SIDE, "v", 0.87, GY, {"w": (0.10, 1.0)}),       # front door / fender
        (S_SIDE, "v", -0.17, GY, {"w": (0.10, 1.0)}),      # B seam
        (S_SIDE, "v", -0.95, GY, {"w": (0.10, 1.0)}),      # rear door / quarter
        (S_SIDE, "w", 0.10, GW, {"v": (-0.95, 0.87)}),     # door bottoms
        ("T", "u", 0.86, GU, {"v": (0.94, 9)}),            # bonnet sides
        ("T", "u", -0.86, GU, {"v": (0.94, 9)}),
        ("T", "v", 0.94, GY, {"u": (-0.86, 0.86)}),        # bonnet rear
        ("F", "u", 0.86, GU, {"w": (0.90, 1.0)}),
        ("F", "u", -0.86, GU, {"w": (0.90, 1.0)}),
        ("F", "w", 0.90, GW, {"u": (-0.86, 0.86)}),        # bonnet front edge
        ("T", "u", 0.80, GU, {"v": (-9, -1.66)}),          # boot lid
        ("T", "u", -0.80, GU, {"v": (-9, -1.66)}),
        ("T", "v", -1.66, GY, {"u": (-0.80, 0.80)}),
        ("K", "u", 0.80, GU, {"w": (0.88, 1.0)}),
        ("K", "u", -0.80, GU, {"w": (0.88, 1.0)}),
        ("K", "u", 0.50, GU, {"w": (0.60, 0.68)}),
        ("K", "u", -0.50, GU, {"w": (0.60, 0.68)}),
        ("K", "w", 0.60, GW, {"u": (-1, 1)}),              # boot / rear bumper
        (S_SIDE, "v", -1.88, GY, {"w": (0.0, 0.60)}),      # rear bumper / quarter
        (S_SIDE, "w", 0.60, GW, {"v": (-9, -1.88)}),
        (S_SIDE, "v", 1.96, GY, {"w": (0.0, 0.69)}),       # front bumper / fender
        (S_SIDE, "w", 0.69, GW, {"v": (1.96, 9)}),
        ("F", "w", 0.69, GW, {"u": (0.50, 1.0)}),
        ("F", "w", 0.69, GW, {"u": (-1.0, -0.50)}),
        ("R", "v", -1.04, GY, {"w": (0.74, 0.92)}),        # fuel flap (right rear quarter)
        ("R", "v", -1.22, GY, {"w": (0.74, 0.92)}),
        ("R", "w", 0.74, GW, {"v": (-1.22, -1.04)}),
        ("R", "w", 0.92, GW, {"v": (-1.22, -1.04)}),
    ]
    HL = dict(F={"u": (0.50, 1.0), "w": (0.70, 0.885)}, S={"v": (YF - 0.27, YF), "w": (0.70, 0.885)})
    TL = dict(K={"u": (0.50, 1.0), "w": (0.68, 0.88)}, S={"v": (YR, YR + 0.22), "w": (0.68, 0.88)})
    return strips, HL, TL


def build_body(coll, M, parent):
    strips, HL, TL = body_rules()
    ureq, vreq, wreq = [], [], []
    for sides, ax, val, g, cons in strips:
        sup = {"u": SU, "v": SY, "w": SW}[ax]
        {"u": ureq, "v": vreq, "w": wreq}[ax].extend(seam_lines(val, g, sup))
    for s in (1, -1):
        ureq += [s * x for x in (0.42, 0.50, 0.58, 0.93, 0.42 - 0.012, 0.42 + 0.012,
                                 0.58 + 0.012, 0.58 - 0.012, 0.50 + 0.012, 0.50 - 0.012)]
    ureq += [0.0]
    wreq += edge_lines(0.70, 0.010) + edge_lines(0.885, 0.010) + edge_lines(0.68, 0.009)
    wreq += edge_lines(0.88, 0.009) + edge_lines(0.08, 0.012) + edge_lines(0.30, 0.012)
    wreq += edge_lines(0.60, 0.012) + edge_lines(0.86, 0.010) + edge_lines(0.16, 0.012)
    wreq += [0.0, 0.04, 0.94, 0.67, 0.69, 0.72, 0.73]
    vreq += [YF, YF - 0.09, YR, YR + 0.08, YF - 0.27, YF - 0.27 - 0.012,
             YF - 0.27 + 0.012, YR + 0.22, YR + 0.22 - 0.012, YR + 0.22 + 0.012, COWL_Y, COWL_Y + 0.012,
             DECK_Y, DECK_Y - 0.012]
    U = lines(ureq, -1, 1, 0.11)
    V = lines(vreq, YR, YF, 0.10)
    W = lines(wreq, 0, 1, 0.09)
    print("body lattice", len(U), len(V), len(W))
    lat = Lattice(U, V, W, body_pos)

    keep, hl, tl = [], {"R": [], "L": []}, {"R": [], "L": []}
    holes = 0
    for f in lat.faces:
        side = f[1]
        if any(in_strip(f, *s) for s in strips):
            continue
        if side == "T" and in_region(f, "T", {"v": (DECK_Y, COWL_Y)}):
            continue
        if side == "F" and (in_region(f, "F", {"u": (-0.42, 0.42), "w": (0.60, 0.86)})
                            or in_region(f, "F", {"u": (-0.58, 0.58), "w": (0.08, 0.30)})):
            holes += 1
            continue
        lamp = None
        for sgn, key in ((1, "R"), (-1, "L")):
            uh = (0.50, 1.0) if sgn > 0 else (-1.0, -0.50)
            if in_region(f, "F", {"u": uh, "w": HL["F"]["w"]}) or in_region(f, key, HL["S"]):
                lamp = ("h", key)
            if in_region(f, "K", {"u": uh, "w": TL["K"]["w"]}) or in_region(f, key, TL["S"]):
                lamp = ("t", key)
        if lamp:
            (hl if lamp[0] == "h" else tl)[lamp[1]].append(f)
            continue
        keep.append(f)

    # material slots: 0 paint, 1 black textured, 2 underbody, 3 inner (solidify offset)
    def mat_of(f):
        side, r = f[1], f[2]
        if side == "B":
            return 2
        if side == "T" and _mid(r["v"]) > COWL_Y and _mid(r["v"]) < 0.94 and abs(_mid(r["u"])) < 0.86:
            return 1
        if side == "F" and _mid(r["w"]) < 0.08:
            return 1
        if side == "K" and _mid(r["w"]) < 0.16:
            return 1
        return 0
    me = mesh_from_faces("taxi_body", lat, keep, mat_of)
    body = obj_from_mesh("taxi_body", me, coll, [M["paint"], M["black_tex"], M["under"], M["inner"]], parent)
    sol = body.modifiers.new("Sheet", "SOLIDIFY")
    sol.thickness = 0.0028
    sol.offset = -1.0
    sol.use_rim = True
    sol.use_even_offset = True
    sol.material_offset = 3
    sol.material_offset_rim = 0
    add_subsurf(body, 1, 2)
    # wheel arch cutters
    cut_coll = bpy.data.collections.new(coll.name + "_cutters")
    coll.children.link(cut_coll)
    for ax in (AXF, AXR):
        for sx in (1, -1):
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=96, radius1=ARCH_R, radius2=ARCH_R, depth=0.6)
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
            bmesh.ops.translate(bm, verts=bm.verts, vec=(sx * 0.93, ax, WHEEL_Z + 0.012))
            c = bm_to_obj("taxi_archcut", bm, cut_coll, (), parent)
            c.display_type = "WIRE"
            c.hide_render = True
    cut_coll.hide_render = True
    bo = body.modifiers.new("Arches", "BOOLEAN")
    bo.operation = "DIFFERENCE"
    bo.operand_type = "COLLECTION"
    bo.collection = cut_coll
    bo.solver = "MANIFOLD"
    return body, lat, hl, tl


def build_cabin(coll, M, parent):
    ureq = [0.0]
    for s in (1, -1):
        ureq += [s * x for x in (0.865, 0.88, 0.885, 0.90, 0.80, 0.94, 0.6, 0.3)]
    sreq = [-1, -0.985, -0.95, -0.5, -0.485, -0.015, 0.0, 0.14, 0.155, 0.865, 0.88, 0.95, 0.985, 1.0, -0.8, 0.8]
    wreq = [0, 0.02, 0.03, 0.035, 0.045, 0.05, 0.065, 0.11, 0.86, 0.905, 0.92, 0.935, 0.95, 0.955, 0.97, 1.0, 0.25, 0.5, 0.75]
    U = lines(ureq, -1, 1, 0.09)
    S = lines(sreq, -1, 1, 0.07)
    W = lines(wreq, 0, 1, 0.09)
    lat = Lattice(U, S, W, cabin_pos)
    glass_ws, glass_side, glass_back, rest = [], [], [], []

    def side_open(f, inset):
        e = 0.015 if inset else 0.0
        return (in_region(f, "RL", {"v": (0.14 + e, 0.88 - e), "w": (0.05 + e, 0.92 - e)})
                or in_region(f, "RL", {"v": (-0.50 + e, 0.0 - e), "w": (0.05 + e, 0.92 - e)}))
    for f in lat.faces:
        side = f[1]
        if side == "B":
            continue
        if in_region(f, "F", {"u": (-0.885, 0.885), "w": (0.035, 0.955)}):
            glass_ws.append(f)
        elif in_region(f, "K", {"u": (-0.865, 0.865), "w": (0.045, 0.935)}):
            glass_back.append(f)
        elif side_open(f, True):
            glass_side.append(f)
        else:
            rest.append(f)

    def mat_of(f):
        side = f[1]
        if in_region(f, "F", {"u": (-0.90, 0.90), "w": (0.02, 0.97)}):
            return 1
        if in_region(f, "K", {"u": (-0.88, 0.88), "w": (0.03, 0.95)}):
            return 1
        if side_open(f, False):
            return 1
        if in_region(f, "RL", {"v": (0.0, 0.14), "w": (0.0, 0.92)}):
            return 2
        return 0
    me = mesh_from_faces("taxi_cabin", lat, rest, mat_of)
    cab = obj_from_mesh("taxi_cabin", me, coll, [M["paint"], M["rubber"], M["black_gloss"], M["headliner"]], parent)
    sol = cab.modifiers.new("Sheet", "SOLIDIFY")
    sol.thickness = 0.012
    sol.offset = -1.0
    sol.use_rim = True
    sol.material_offset = 3
    sol.material_offset_rim = 1
    add_subsurf(cab, 1, 2)
    glass_objs = []

    def frit_of(f):
        # black ceramic band (screen-printed on the inner face) around the bonded screens
        if f[1] in "FK":
            r = f[2]
            if abs(_mid(r["u"])) > 0.80 or _mid(r["w"]) < 0.11 or _mid(r["w"]) > 0.86:
                return 1
        return 0
    for nm, fl, mt in (("taxi_glass_ws", glass_ws, M["glass_ws"]), ("taxi_glass_side", glass_side, M["glass"]),
                       ("taxi_glass_rear", glass_back, M["glass"])):
        gme = mesh_from_faces(nm, lat, fl, frit_of)
        g = obj_from_mesh(nm, gme, coll, [mt, M["frit"]], parent)
        d = g.modifiers.new("Inset", "DISPLACE")
        d.strength = -0.004
        d.mid_level = 0.0
        add_subsurf(g, 1, 2)
        s2 = g.modifiers.new("Thickness", "SOLIDIFY")
        s2.thickness = 0.0045
        s2.offset = -1.0
        glass_objs.append(g)
    return cab, lat, glass_objs


# ================================================================== lamps
def build_lamps(coll, M, parent, blat, hl, tl):
    objs = []
    for kind, groups in (("head", hl), ("tail", tl)):
        for key, faces in groups.items():
            if not faces:
                continue
            sgn = 1 if key == "R" else -1
            lens_mat = M["lens_clear"] if kind == "head" else M["lens_red"]
            me = mesh_from_faces("taxi_%slamp_lens_%s" % (kind, key), blat, faces)
            lens = obj_from_mesh(me.name, me, coll, [lens_mat], parent)
            add_subsurf(lens, 1, 2)
            s = lens.modifiers.new("Thickness", "SOLIDIFY")
            s.thickness = 0.003
            s.offset = -1.0
            # housing: extrude the lens patch inward, drop the outer faces
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.normal_update()
            vn = {v.index: v.normal.copy() for v in bm.verts}
            res = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
            newv = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
            depth = 0.085 if kind == "head" else 0.06
            avg = Vector((0, 0, 0))
            for v in bm.verts:
                avg += v.normal
            for v in newv:
                v.co -= v.normal.normalized() * depth if v.normal.length > 0 else Vector((0, 0, 0))
            # keep only extruded copy + side walls (remove original outer faces = faces not touching newv)
            news = set(newv)
            outer = [f for f in bm.faces if not any(v in news for v in f.verts)]
            bmesh.ops.delete(bm, geom=outer, context="FACES_ONLY")
            hs = bm_to_obj("taxi_%slamp_housing_%s" % (kind, key), bm, coll, [M["housing"]], parent)
            add_subsurf(hs, 1, 1)
            objs += [lens, hs]

            # interior parts, placed in lattice parameter space
            def P(u, w, inset, side="F"):
                if kind == "head":
                    p, n = blat.normal(u, YF, w, "F")
                else:
                    p, n = blat.normal(u, YR, w, "K")
                return p - n * inset, n
            if kind == "head":
                for (u, r, proj) in ((0.63, 0.047, True), (0.81, 0.040, False)):
                    p, n = P(sgn * u, 0.785, 0.058)
                    # chrome bezel ring around each module
                    rg = lathe([(0.0, r + 0.002), (0.004, r + 0.002), (0.004, r + 0.010), (-0.01, r + 0.016)], 40, axis="Z")
                    ob_ = bm_to_obj("taxi_hl_ring", rg, coll, [M["chrome"]], parent)
                    ob_.location = p + n * 0.002
                    ob_.rotation_euler = Vector((0, 0, 1)).rotation_difference(n).to_euler()
                    objs.append(ob_)
                    bowl = lathe([(-0.035, 0.002), (-0.03, r * 0.45), (-0.018, r * 0.8), (0.0, r)], 32, axis="Z")
                    o = bm_to_obj("taxi_hl_bowl", bowl, coll, [M["reflector"]], parent)
                    o.location = p
                    o.rotation_euler = Vector((0, 0, 1)).rotation_difference(n).to_euler()
                    objs.append(o)
                    if proj:
                        lb = bmesh.new()
                        bmesh.ops.create_uvsphere(lb, u_segments=24, v_segments=12, radius=0.024)
                        o2 = bm_to_obj("taxi_hl_projector", lb, coll, [M["lens_clear"]], parent)
                        o2.location = p + n * 0.012
                        o2.scale = (1, 1, 0.55)
                        o2.rotation_euler = o.rotation_euler
                        rg = lathe([(0.0, 0.026), (0.006, 0.026), (0.006, 0.03), (0.0, 0.03)], 32, axis="Z")
                        o3 = bm_to_obj("taxi_hl_bezel", rg, coll, [M["chrome"]], parent)
                        o3.location = p + n * 0.006
                        o3.rotation_euler = o.rotation_euler
                        objs += [o2, o3]
                # DRL light guide: along the upper edge of the lens, wrapping to the side
                pts = []
                for t in np.linspace(0.53, 1.0, 14):
                    p, n = blat.normal(sgn * t, YF, 0.862, "F")
                    pts.append(p - n * 0.014)
                for t in np.linspace(0.02, 0.2, 5):
                    p, n = blat.normal(sgn, YF - t, 0.862, "R" if sgn > 0 else "L")
                    pts.append(p - n * 0.014)
                o = bm_to_obj("taxi_drl", sweep_tube(pts, 0.0045, 8, scale_xy=(1.0, 0.6)), coll, [M["drl"]], parent)
                objs.append(o)
                # black inner mask: a fin under the modules and a cowl over them
                for (wf, ins, th) in ((0.722, 0.030, 0.010), (0.842, 0.036, 0.007)):
                    pts = []
                    for t in np.linspace(0.53, 0.97, 16):
                        p, n = blat.normal(sgn * t, YF, wf, "F")
                        pts.append(p - n * ins)
                    o = bm_to_obj("taxi_hl_mask", sweep_tube(pts, 0.024, 8, scale_xy=(th / 0.024, 1.0),
                                                             up=Vector((0, 1, 0))), coll, [M["lamp_black"]], parent)
                    objs.append(o)
                # LED high-beam cubes in a row between the modules, with chrome collars
                for k in range(3):
                    p, n = P(sgn * (0.705 + 0.022 * (k - 1)), 0.76, 0.045)
                    o = rounded_box("taxi_hl_led", (0.014, 0.012, 0.012), coll, [M["lamp_chrome"]], parent,
                                    loc=p, sup=0.3, levels=1)
                    o2 = rounded_box("taxi_hl_led_chip", (0.007, 0.006, 0.006), coll, [M["drl"]], parent,
                                     loc=p + n * 0.006, sup=0.3, levels=1)
                    objs += [o, o2]
                # amber indicator block in the outer, wrapped part
                p, n = blat.normal(sgn, YF - 0.10, 0.75, "R" if sgn > 0 else "L")
                o = rounded_box("taxi_indicator", (0.006, 0.08, 0.022), coll, [M["amber_led"]], parent,
                                loc=p - n * 0.03, levels=1)
                objs.append(o)
            else:
                # tail: C-shaped LED light guide + reflector strip + reverse lamp
                pts = []
                for t in np.linspace(0.18, 0.02, 6):
                    p, n = blat.normal(sgn, YR + t, 0.86, "R" if sgn > 0 else "L")
                    pts.append(p - n * 0.012)
                for t in np.linspace(0.98, 0.56, 10):
                    p, n = blat.normal(sgn * t, YR, 0.86, "K")
                    pts.append(p - n * 0.012)
                for t in np.linspace(0.56, 0.98, 10):
                    p, n = blat.normal(sgn * t, YR, 0.70, "K")
                    pts.append(p - n * 0.012)
                o = bm_to_obj("taxi_tail_guide", sweep_tube(pts, 0.005, 8), coll, [M["tail_led"]], parent)
                objs.append(o)
                # stacked light blades inside the C
                for wb in (0.745, 0.78, 0.815):
                    pts = []
                    for t in np.linspace(0.66, 0.95, 8):
                        p, n = blat.normal(sgn * t, YR, wb, "K")
                        pts.append(p - n * 0.018)
                    o = bm_to_obj("taxi_tail_blade", sweep_tube(pts, 0.0032, 6, scale_xy=(1.0, 0.5)), coll,
                                  [M["tail_led"]], parent)
                    objs.append(o)
                for (u, w, mt, nm) in ((0.58, 0.78, M["reflector"], "taxi_tail_reverse"),
                                       ):
                    p, n = blat.normal(sgn * u, YR, w, "K")
                    o = rounded_box(nm, (0.07, 0.012, 0.09), coll, [mt], parent, loc=p - n * 0.03, levels=1)
                    o.rotation_euler = Vector((0, -1, 0)).rotation_difference(-n).to_euler()
                    objs.append(o)
    return objs


# ================================================================== wheels
def tyre_bmesh(segs=360):
    # profile from inner bead, around the outside, to outer bead; a = axial (x), r = radius
    R = WHEEL_R
    side_in = [(-0.098, 0.222), (-0.104, 0.232), (-0.110, 0.248), (-0.114, 0.266), (-0.1155, 0.282),
               (-0.114, 0.298), (-0.110, 0.312), (-0.104, 0.324), (-0.096, 0.332), (-0.088, R - 0.002)]
    tread = []
    grooves = [(-0.068, 0.0055), (-0.030, 0.005), (0.030, 0.005), (0.068, 0.0055)]
    xs = list(np.linspace(-0.082, 0.082, 34))
    for g, hw in grooves:
        xs += [g - hw - 0.0012, g - hw, g + hw, g + hw + 0.0012]
    xs = sorted(set([round(x, 5) for x in xs]))
    depth = 0.0085
    for x in xs:
        ing = any(abs(x - g) < hw - 1e-6 for g, hw in grooves)
        edge = any(abs(abs(x - g) - hw) < 1e-6 for g, hw in grooves)
        r = R - depth if (ing or edge and False) else R
        # rounded shoulders
        r -= 0.004 * max(0.0, (abs(x) - 0.070) / 0.012) ** 2
        tread.append((x, r))
    # make groove walls: points exactly at g +- hw become bottom-of-groove pairs
    prof = side_in + tread + [(-a, r) for (a, r) in reversed(side_in)]
    # groove walls: duplicate wall points (top & bottom)
    out = []
    for (a, r) in prof:
        wall = any(abs(abs(a - g) - hw) < 1e-6 for g, hw in grooves)
        if wall:
            inside_left = any(abs(a - (g - hw)) < 1e-6 for g, hw in grooves)
            if inside_left:
                out += [(a, R), (a, R - depth)]
            else:
                out += [(a, R - depth), (a, R)]
        else:
            out.append((a, r))
    # UV v: outer sidewall (positive a) band 0.235..0.326 -> 0..1 else outside image
    uv_v = []
    for (a, r) in out:
        if a > 0.09:
            uv_v.append(0.5 * ((r - 0.232) / (0.330 - 0.232)) + 0.5 if False else (r - 0.236) / (0.328 - 0.236))
        else:
            uv_v.append(-1.0)
    bm = lathe(out, segs, axis="X", uv_v=uv_v)
    # lateral grooves in the shoulder blocks + sipes in the centre rib
    for v in bm.verts:
        x, y, z = v.co
        r = math.hypot(y, z)
        if r < R - 0.0015:
            continue
        th = math.atan2(y, z) % (2 * math.pi)
        P = 68.0                                   # tread pitches around the tyre
        ax = abs(x)
        cut = 0.0
        if ax > 0.0745 and ax < 0.086:
            # shoulder blocks: lateral slots, staggered left/right
            f = (th / (2 * math.pi) * P + (0.0 if x > 0 else 0.5)) % 1.0
            if f < 0.20:
                cut = 0.0078
        elif 0.0365 < ax < 0.061:
            # intermediate ribs: angled sipes (phase drifts with x)
            f = (th / (2 * math.pi) * P + (ax - 0.036) * 14.0 + (0.25 if x > 0 else 0.75)) % 1.0
            if abs(f - 0.5) < 0.06:
                cut = 0.0060
        elif ax < 0.0235:
            f = (th / (2 * math.pi) * P * 2 + x * 10.0) % 1.0
            if abs(f - 0.5) < 0.07:
                cut = 0.0035
        if cut:
            v.co *= Vector((1, (r - cut) / r, (r - cut) / r))
    return bm


def rim_parts(coll, M, parent, spokes=10):
    parts = []
    # barrel + lip (rim face toward +X)
    prof = [(-0.098, 0.214), (-0.105, 0.222), (-0.100, 0.226), (-0.090, 0.214), (-0.06, 0.196),
            (0.03, 0.196), (0.065, 0.198), (0.092, 0.212), (0.103, 0.222), (0.110, 0.226),
            (0.112, 0.221), (0.106, 0.210), (0.095, 0.200), (0.080, 0.192), (0.030, 0.188),
            (-0.060, 0.188), (-0.096, 0.208)]
    bm = lathe(prof, 96, axis="X")
    o = bm_to_obj("taxi_rim_barrel", bm, coll, [M["rim"]], parent, sharp=40)
    add_bevel(o, 0.0006, 2, 40)
    parts.append(o)
    # spokes: swept closed section from hub to lip
    bm = bmesh.new()
    nr, ns = 9, 8
    for sp in range(spokes):
        base = (sp // 2) * (2 * math.pi / (spokes // 2))
        off = math.radians(6.5) * (1 if sp % 2 else -1)
        rings = []
        for i in range(nr):
            t = i / (nr - 1)
            r = 0.058 + t * (0.205 - 0.058)          # ends buried in the barrel lip
            th = base + off * (0.35 + 0.65 * t)
            wdt = 0.042 - 0.012 * t
            dep = 0.026 - 0.008 * t
            xf = 0.078 + 0.016 * t ** 1.4 + 0.004 * math.sin(math.pi * t)  # face position (dish)
            ring = []
            # machined spoke section: flat face with chamfered edges, tapered flanks, flat back
            sec = [(-0.50, 0.70), (-0.38, 1.0), (0.38, 1.0), (0.50, 0.70),
                   (0.44, 0.05), (0.15, 0.0), (-0.15, 0.0), (-0.44, 0.05)]
            for s in range(ns):
                lat = sec[s][0] * wdt
                ax_ = xf - dep + sec[s][1] * dep
                yy = r * math.sin(th) + lat * math.cos(th)
                zz = r * math.cos(th) - lat * math.sin(th)
                ring.append(bm.verts.new((ax_, yy, zz)))
            rings.append(ring)
        for i in range(nr - 1):
            for s in range(ns):
                f = bm.faces.new((rings[i][s], rings[i][(s + 1) % ns], rings[i + 1][(s + 1) % ns], rings[i + 1][s]))
                if s == 1 and i < nr - 2:
                    f.material_index = 1          # flat spoke face: diamond-cut
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = bm_to_obj("taxi_rim_spokes", bm, coll, [M["rim"], M["machined"]], parent, sharp=28)
    add_bevel(o, 0.0007, 2, 28)
    parts.append(o)
    # hub face + centre cap
    hub = [(0.050, 0.0), (0.078, 0.0), (0.079, 0.02), (0.081, 0.030), (0.084, 0.050), (0.084, 0.064),
           (0.070, 0.066), (0.060, 0.064)]
    o = bm_to_obj("taxi_rim_hub", lathe(hub, 64, axis="X"), coll, [M["rim"]], parent, sharp=35)
    add_bevel(o, 0.0006, 2, 35)
    parts.append(o)
    # valve stem (chrome cap on a black rubber stem) through the barrel near the lip
    th_v = math.radians(18)
    stem = lathe([(0.0, 0.0045), (0.016, 0.0045), (0.016, 0.0038), (0.030, 0.0038), (0.031, 0.0)], 16, axis="Z")
    cap = lathe([(0.016, 0.0040), (0.030, 0.0040), (0.031, 0.0)], 16, axis="Z")
    # stem axis tilts outward (+X) and radially out, baked into the mesh (wheel copies get re-spun)
    ax_dir = Vector((0.55, 0.0, 0.835)).normalized()
    vm = (Matrix.Rotation(-th_v, 4, "X") @ Matrix.Translation((0.084, 0.0, 0.192))
          @ Vector((0, 0, 1)).rotation_difference(ax_dir).to_matrix().to_4x4())
    for nm_, b_, mt_ in (("taxi_valve_stem", stem, M["rubber"]), ("taxi_valve_cap", cap, M["chrome"])):
        b_.transform(vm)
        parts.append(bm_to_obj(nm_, b_, coll, [mt_], parent, sharp=50))
    cap = [(0.084, 0.0), (0.0905, 0.0), (0.0900, 0.018), (0.0880, 0.026), (0.084, 0.028), (0.080, 0.028)]
    parts.append(bm_to_obj("taxi_rim_cap", lathe(cap, 40, axis="X"), coll, [M["black_gloss"]], parent))
    # lug nuts (5 x PCD 114.3)
    bm = bmesh.new()
    for k in range(5):
        th = 2 * math.pi * k / 5 + 0.3
        nut = lathe([(0.084, 0.0), (0.084, 0.0095), (0.098, 0.0095), (0.1015, 0.0075), (0.1025, 0.0)], 6, axis="X")
        mat = Matrix.Translation((0, 0.0572 * math.sin(th), 0.0572 * math.cos(th)))
        bmesh.ops.transform(nut, matrix=mat, verts=nut.verts)
        tmp = bpy.data.meshes.new("tmp")
        nut.to_mesh(tmp)
        nut.free()
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    o = bm_to_obj("taxi_lug_nuts", bm, coll, [M["chrome"]], parent, sharp=30)
    add_bevel(o, 0.0005, 1, 30)
    parts.append(o)
    # brake disc (vented) + caliper
    disc = [(-0.012, 0.075), (0.012, 0.075), (0.013, 0.160), (-0.013, 0.160)]
    db = lathe(disc + [disc[0]], 72, axis="X")
    parts.append(bm_to_obj("taxi_brake_disc", db, coll, [M["disc"]], parent, sharp=40))
    sl = bmesh.new()
    for k in range(6):
        a0 = 2 * math.pi * k / 6
        pts = [(0.0133, r_ * math.sin(a0 + (r_ - 0.10) * 3.2), r_ * math.cos(a0 + (r_ - 0.10) * 3.2))
               for r_ in np.linspace(0.098, 0.150, 8)]
        tb = sweep_tube(pts, 0.0022, 6, scale_xy=(0.35, 1.0), up=Vector((1, 0, 0)))
        tmp = bpy.data.meshes.new("tmp")
        tb.to_mesh(tmp)
        tb.free()
        sl.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    parts.append(bm_to_obj("taxi_disc_slots", sl, coll, [M["under"]], parent))
    hat = [(0.012, 0.075), (0.040, 0.075), (0.050, 0.070), (0.052, 0.0), (0.040, 0.0)]
    parts.append(bm_to_obj("taxi_brake_hat", lathe(hat, 48, axis="X"), coll, [M["disc"]], parent))

    def cal_shape(u, v, w):
        # bend the box around the disc: v -> angle
        return (0, 0, 0)
    cal = bmesh.new()
    na = 8
    rings = []
    for i in range(na + 1):
        th = math.radians(-28 + 56 * i / na)
        ring = []
        for (a, r) in ((-0.032, 0.128), (0.030, 0.128), (0.034, 0.150), (0.030, 0.178), (-0.032, 0.178), (-0.036, 0.150)):
            ring.append(cal.verts.new((a, r * math.sin(th), r * math.cos(th))))
        rings.append(ring)
    for i in range(na):
        for s in range(6):
            cal.faces.new((rings[i][s], rings[i][(s + 1) % 6], rings[i + 1][(s + 1) % 6], rings[i + 1][s]))
    cal.faces.new(rings[0][::-1])
    cal.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(cal, faces=cal.faces)
    o = bm_to_obj("taxi_caliper", cal, coll, [M["caliper"]], parent, sharp=35)
    add_bevel(o, 0.0015, 2, 35)
    parts.append(o)
    return parts


def build_wheels(coll, M, parent, tyre_segs=360):
    """One wheel built from shared meshes, instanced at the 4 corners as linked duplicates."""
    proto = bpy.data.collections.new(coll.name + "_wheel_proto")
    tyre = bm_to_obj("taxi_tyre", tyre_bmesh(tyre_segs), proto, [M["tyre"]], sharp=38)
    parts = [tyre] + rim_parts(proto, M, None)
    objs = []
    for (ax, sx) in ((AXF, 1), (AXF, -1), (AXR, 1), (AXR, -1)):
        tag = ("F" if ax > 0 else "R") + ("R" if sx > 0 else "L")
        steer = math.radians(STEER_DEG) if ax > 0 else 0.0
        empty = bpy.data.objects.new("taxi_wheel_" + tag, None)
        coll.objects.link(empty)
        empty.parent = parent
        empty.location = (sx * TRACK_X, ax, WHEEL_Z)
        empty.rotation_euler = (0, 0, (0 if sx > 0 else math.pi) + steer)
        empty.empty_display_size = 0.35
        empty.scale = (WHEEL_SCALE,) * 3
        for p in parts:
            if p.name.startswith("taxi_caliper"):
                d = p.copy()
                # calipers sit toward the rear of the disc on every corner
                # (wheel empties on the left are turned 180 deg, so mirror the angle)
                d.rotation_euler = (math.radians(32 if sx > 0 else -32), 0, 0)
            else:
                d = p.copy()
                # spin each wheel differently so the 4 corners don't match exactly
                spin = {"FR": 0.0, "FL": 0.9, "RR": 2.1, "RL": 3.3}[tag]
                d.rotation_euler = (spin, 0, 0)
            coll.objects.link(d)
            d.parent = empty
            objs.append(d)
        objs.append(empty)
    for p in parts:
        bpy.data.objects.remove(p)
    return objs


# ================================================================== details
def surface_hit(bvh, origin, direction):
    hit = bvh.ray_cast(Vector(origin), Vector(direction).normalized(), 5.0)
    return hit  # (loc, normal, index, dist)


def build_details(coll, M, parent, cfg, body, blat, clat, tex):
    objs = []
    dg = bpy.context.evaluated_depsgraph_get()
    body_eval = body.evaluated_get(dg)
    bvh = BVHTree.FromObject(body_eval, dg)

    def on_side(sx, Y, Z):
        h = surface_hit(bvh, (sx * 2.0, Y, Z), (-sx, 0, 0))
        return h

    # ---- wheel arch lips (rolled edge) + liners
    for ax in (AXF, AXR):
        for sx in (1, -1):
            pts = []
            for k in range(0, 61):
                a = math.radians(-84 + 168 * k / 60)
                Y = ax + (ARCH_R + 0.004) * math.sin(a)
                Z = WHEEL_Z + 0.012 + (ARCH_R + 0.004) * math.cos(a)
                h = on_side(sx, Y, Z)
                if h[0] is None or Z < _Zb(Y) + 0.03 or abs(h[1].x) < 0.55:
                    continue
                pts.append(h[0] - Vector((sx * 0.006, 0, 0)))
            if len(pts) > 3:
                n_ = len(pts)
                rad = [0.0075 * min(1.0, 0.35 + 0.65 * min(i, n_ - 1 - i) / 5.0) for i in range(n_)]
                bm = sweep_tube(pts, rad, 8, scale_xy=(1.0, 1.3), up=Vector((1, 0, 0)))
                o = bm_to_obj("taxi_arch_lip", bm, coll, [M["paint"]], parent)
                objs.append(o)
            prof = [(sx * 0.58, ARCH_R + 0.0), (sx * 0.92, ARCH_R + 0.0)]
            bm = lathe([(0.0, ARCH_R - 0.003), (0.34, ARCH_R - 0.003)], 40, axis="X",
                       angle=math.radians(196), start=math.radians(-98))
            o = bm_to_obj("taxi_wheel_liner", bm, coll, [M["liner"]], parent)
            o.location = (sx * 0.58 if sx > 0 else -0.92, ax, WHEEL_Z + 0.012)
            objs.append(o)

    # ---- underbody tray / shadow box
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(1.60, 3.85, 0.05), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0.0, 0.225), verts=bm.verts)
    objs.append(bm_to_obj("taxi_underbody", bm, coll, [M["under"]], parent, smooth=False))
    # floor pan inside the cabin
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(1.72, 2.35, 0.03), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, -0.30, 0.30), verts=bm.verts)
    objs.append(bm_to_obj("taxi_floor", bm, coll, [M["carpet"]], parent, smooth=False))

    # ---- grille + lower intake: recessed mesh panels behind the cut-outs
    def grille_panel(name, u0, u1, w0, w1, inset, cell, mat_frame):
        # diamond mesh: two families of thin flat bars at +-38 deg, conformed to the fascia
        bm = bmesh.new()
        hu = (u1 - u0) * 0.92          # metres across (approx)
        hw = (w1 - w0) * 0.55          # metres up (approx)
        ang = math.radians(38)
        step = cell
        for fam in (1, -1):
            k = -int((hu + hw) / step) - 2
            while k * step < hu + hw + step:
                c0 = k * step
                pts = []
                for t in np.linspace(-0.2, 1.2, 40):
                    xm = c0 + t * hw / math.tan(ang) * fam
                    zm = t * hw
                    uu = u0 + xm / 0.92
                    ww = w0 + zm / 0.55
                    if u0 - 0.01 <= uu <= u1 + 0.01 and w0 - 0.01 <= ww <= w1 + 0.01:
                        p, n = blat.normal(uu, YF, ww, "F")
                        pts.append(p - n * (inset + (0.004 if fam > 0 else 0.0)))
                if len(pts) >= 2:
                    tb = sweep_tube(pts, 0.006, 4, scale_xy=(0.45, 1.0), up=Vector((0, 1, 0)))
                    tmp = bpy.data.meshes.new("tmp")
                    tb.to_mesh(tmp)
                    tb.free()
                    bm.from_mesh(tmp)
                    bpy.data.meshes.remove(tmp)
                k += 1
        o = bm_to_obj(name, bm, coll, [mat_frame], parent, smooth=False)
        objs.append(o)
        # dark backing surface
        U = list(np.linspace(u0 - 0.02, u1 + 0.02, 12))
        W = list(np.linspace(w0 - 0.02, w1 + 0.02, 5))
        bm = bmesh.new()
        vv = [[bm.verts.new(blat.normal(u, YF, w, "F")[0] - blat.normal(u, YF, w, "F")[1] * (inset + 0.03))
               for w in W] for u in U]
        for i in range(len(U) - 1):
            for j in range(len(W) - 1):
                bm.faces.new((vv[i][j], vv[i + 1][j], vv[i + 1][j + 1], vv[i][j + 1]))
        objs.append(bm_to_obj(name + "_back", bm, coll, [M["under"]], parent))
        # walls around the opening (the cut-out edge returns into the bumper)
        loop = []
        for u in np.linspace(u0, u1, 16):
            loop.append((u, w0))
        for w in np.linspace(w0, w1, 6)[1:]:
            loop.append((u1, w))
        for u in np.linspace(u1, u0, 16)[1:]:
            loop.append((u, w1))
        for w in np.linspace(w1, w0, 6)[1:-1]:
            loop.append((u0, w))
        bm = bmesh.new()
        outer, inner = [], []
        for (u, w) in loop:
            p, n = blat.normal(u, YF, w, "F")
            outer.append(bm.verts.new(p - n * 0.002))
            inner.append(bm.verts.new(p - n * (inset + 0.03)))
        L = len(loop)
        for k in range(L):
            bm.faces.new((outer[k], outer[(k + 1) % L], inner[(k + 1) % L], inner[k]))
        objs.append(bm_to_obj(name + "_wall", bm, coll, [M["black_tex"]], parent))
    grille_panel("taxi_grille", -0.42, 0.42, 0.60, 0.86, 0.012, 0.075, M["black_gloss"] if cfg["trim"] != "chrome" else M["chrome"])
    grille_panel("taxi_intake", -0.58, 0.58, 0.08, 0.30, 0.02, 0.06, M["black_tex"])

    # ---- licence plates (305 x 152 mm) on the bumper / boot
    for front in (True, False):
        if front:
            p, n = blat.normal(0.0, YF, 0.465, "F")
        else:
            p, n = blat.normal(0.0, YR, 0.705, "K")
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
        bmesh.ops.scale(bm, vec=(0.305, 0.152, 1), verts=bm.verts)
        uvl = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            for lp in f.loops:
                lp[uvl].uv = (lp.vert.co.x / 0.305 + 0.5, lp.vert.co.y / 0.152 + 0.5)
        o = bm_to_obj("taxi_plate_" + ("front" if front else "rear"), bm, coll, [M["plate"]], parent)
        o.location = p + n * 0.0085
        tilt = math.atan2(n.z, abs(n.y))
        # plane normal (+Z) -> outward fascia normal, image upright for a viewer facing it
        o.rotation_euler = (math.radians(90) - tilt, 0, math.pi if front else 0.0)
        objs.append(o)
        fr = rounded_box("taxi_plate_frame", (0.325, 0.008, 0.172), coll, [M["black_tex"]], parent,
                         loc=p + n * 0.003, levels=1, sup=0.08)
        fr.rotation_euler = ((tilt if front else -tilt), 0, 0)
        objs.append(fr)

    # ---- mirrors: lofted aero housing (rounded nose, flat glass face), stalk, glass, repeater
    for sx in (1, -1):
        h = on_side(sx, 0.70, 0.99)
        base = h[0] if h[0] else Vector((sx * 0.9, 0.64, 1.0))
        frame = Matrix.Translation(base + Vector((0.0, 0.0, 0.055))) @ Matrix.Rotation(sx * math.radians(-7), 4, "Z")
        if sx < 0:
            frame = frame @ Matrix.Scale(-1, 4, (1, 0, 0))
        st = [(0.035, 0.000, 0.000, 0.030, 0.022, 0.040, 2.4, 4.0),
              (0.050, 0.004, 0.004, 0.048, 0.026, 0.050, 2.4, 4.5),
              (0.090, 0.008, 0.008, 0.056, 0.028, 0.057, 2.4, 5.0),
              (0.160, 0.008, 0.010, 0.054, 0.028, 0.058, 2.4, 5.0),
              (0.205, 0.004, 0.008, 0.046, 0.026, 0.052, 2.4, 4.5),
              (0.228, 0.000, 0.006, 0.030, 0.022, 0.038, 2.4, 3.5),
              (0.238, -0.002, 0.005, 0.012, 0.010, 0.016, 2.2, 3.0)]
        bm = loft(st, 28)
        bm.transform(frame)
        if sx < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        hous = bm_to_obj("taxi_mirror_housing", bm, coll, [M["paint"]], parent)
        add_subsurf(hous, 1, 2)
        # stalk from the door skin into the housing (black textured)
        bm = loft([(-0.02, -0.005, -0.012, 0.040, 0.030, 0.016, 2.5, 2.5),
                   (0.015, -0.005, -0.010, 0.032, 0.022, 0.014, 2.5, 2.5),
                   (0.050, -0.002, -0.004, 0.024, 0.018, 0.016, 2.5, 2.5)], 16)
        bm.transform(frame)
        if sx < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        arm = bm_to_obj("taxi_mirror_arm", bm, coll, [M["black_tex"]], parent)
        add_subsurf(arm, 1, 2)
        # glass: thin rounded plate set into the rear face, with a black surround
        bm = loft([(0.062, -0.021, 0.008, 0.004, 0.004, 0.046, 2, 2),
                   (0.064, -0.023, 0.008, 0.004, 0.004, 0.050, 2, 2),
                   (0.196, -0.023, 0.008, 0.004, 0.004, 0.050, 2, 2),
                   (0.200, -0.021, 0.008, 0.004, 0.004, 0.044, 2, 2)], 16)
        bm.transform(frame)
        if sx < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        glass = bm_to_obj("taxi_mirror_glass", bm, coll, [M["mirror"]], parent)
        add_subsurf(glass, 1, 1)
        bm = loft([(0.056, -0.020, 0.008, 0.005, 0.005, 0.052, 2, 2),
                   (0.060, -0.021, 0.008, 0.006, 0.006, 0.055, 2, 2),
                   (0.200, -0.021, 0.008, 0.006, 0.006, 0.055, 2, 2),
                   (0.206, -0.020, 0.008, 0.005, 0.005, 0.048, 2, 2)], 16)
        bm.transform(frame)
        if sx < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        objs.append(bm_to_obj("taxi_mirror_surround", bm, coll, [M["black_tex"]], parent))
        # side repeater: slim amber light guide on the lower front of the cap
        pts = [frame @ Vector((x, 0.050 - 0.06 * (x - 0.13) ** 2 * 4, -0.030 + 0.04 * (x - 0.10))) for x in np.linspace(0.10, 0.215, 10)]
        rep = bm_to_obj("taxi_mirror_repeater", sweep_tube(pts, [0.0025] + [0.0042] * 8 + [0.0025], 8, scale_xy=(1.0, 0.7)),
                        coll, [M["lens_amber"]], parent)
        objs += [hous, arm, glass, rep]

    # ---- door handles: tapered pull bar standing off a recessed cup (follows the skin)
    for sx in (1, -1):
        for Yh in (0.04, -0.82):
            h = on_side(sx, Yh, 0.905)
            if h[0] is None:
                continue
            n = h[1]
            cup = rounded_box("taxi_handle_cup", (0.004, 0.15, 0.045), coll, [M["black_tex"]], parent,
                              loc=h[0] - n * 0.0005, sup=0.45, levels=2)
            cup.rotation_euler = Vector((1, 0, 0)).rotation_difference(n * sx).to_euler()
            ts = [0.0, 0.025, 0.08, 0.2, 0.35, 0.5, 0.65, 0.8, 0.92, 0.975, 1.0]
            pts, rad = [], []
            for t in ts:
                bulge = math.sin(math.pi * min(1.0, max(0.0, (t - 0.05) / 0.9)))
                pts.append(h[0] + n * (0.004 + 0.010 * bulge) + Vector((0, (t - 0.55) * 0.178, 0.0)))
                rad.append(0.0125 * (0.55 + 0.45 * math.sin(math.pi * t) ** 0.35))
            bm = sweep_tube(pts, rad, 12, scale_xy=(0.62, 1.0))
            hd = bm_to_obj("taxi_door_handle", bm, coll,
                           [M["chrome"] if cfg["trim"] == "chrome" else M["paint"]], parent)
            add_subsurf(hd, 1, 2)
            objs += [cup, hd]

    # ---- beltline trim strips (chrome or black) along the glass base
    for sx in (1, -1):
        pts = []
        for s in np.linspace(-0.5, 0.88, 40):
            p = Vector(cabin_pos(sx * 1.0, s, 0.0))
            pts.append(p + Vector((sx * 0.004, 0, 0.004)))
        bm = sweep_tube(pts, 0.007, 8, scale_xy=(1.0, 0.45), up=Vector((sx, 0, 0)))
        objs.append(bm_to_obj("taxi_belt_trim", bm, coll, [M["trim"]], parent))

    # ---- cowl + wipers
    for (px_, length, ang) in ((-0.42, 0.58, 8.0), (0.18, 0.62, 12.0)):
        pts = []
        for t in np.linspace(0, 1, 18):
            u = (px_ + 0.04 + (length * t)) / 0.80 if False else None
            Xw = px_ + 0.03 - length * t * math.cos(math.radians(ang)) * (-1)
            # blade lies along the bottom of the screen, pointing toward +X (passenger side)
            uu = max(-0.86, min(0.86, Xw / 0.82))
            ww = 0.05 + 0.10 * t * math.sin(math.radians(ang)) * 4
            p, n = clat.normal(uu, 1.0, ww, "F")
            pts.append(p + n * 0.012)
        arm = sweep_tube(pts, 0.0065, 6, scale_xy=(1.0, 0.6))
        objs.append(bm_to_obj("taxi_wiper_arm", arm, coll, [M["black_tex"]], parent))
        blade = sweep_tube([q - Vector((0, 0, 0)) for q in pts[2:]], 0.009, 6, scale_xy=(0.5, 1.0))
        o = bm_to_obj("taxi_wiper_blade", blade, coll, [M["rubber"]], parent)
        objs.append(o)
        pv = Vector(clat.normal(px_ / 0.82, 1.0, 0.0, "F")[0])
        bm = lathe([(0.0, 0.018), (0.022, 0.018), (0.03, 0.01), (0.03, 0.0)], 16, axis="Z")
        o = bm_to_obj("taxi_wiper_pivot", bm, coll, [M["black_tex"]], parent)
        o.location = pv + Vector((0, 0.03, -0.01))
        objs.append(o)

    # ---- rear garnish between the tail lamps (gloss black / chrome) + maker emblems
    U = list(np.linspace(-0.495, 0.495, 24))
    W = list(np.linspace(0.815, 0.865, 3))
    bm = bmesh.new()
    vv = [[bm.verts.new(blat.normal(u, YR, w, "K")[0] + blat.normal(u, YR, w, "K")[1] * 0.0015) for w in W] for u in U]
    for i in range(len(U) - 1):
        for j in range(len(W) - 1):
            bm.faces.new((vv[i][j], vv[i][j + 1], vv[i + 1][j + 1], vv[i + 1][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    g = bm_to_obj("taxi_rear_garnish", bm, coll, [M["trim"]], parent)
    sg = g.modifiers.new("Thickness", "SOLIDIFY")
    sg.thickness = 0.003
    sg.offset = 1.0
    objs.append(g)
    for (side_, u, w, r) in (("K", 0.0, 0.84, 0.022), ("F", 0.0, 0.73, 0.036)):
        p, n = blat.normal(u, YR if side_ == "K" else YF, w, side_)
        em = lathe([(0.0, 0.0), (0.004, 0.0), (0.006, r * 0.55), (0.006, r * 0.75), (0.004, r), (0.0, r + 0.002)], 40, axis="Z")
        # chevron inside the ring
        o = bm_to_obj("taxi_emblem", em, coll, [M["chrome"]], parent, sharp=35)
        o.location = p + n * (0.004 if side_ == "K" else 0.02)
        o.rotation_euler = Vector((0, 0, 1)).rotation_difference(n).to_euler()
        o.scale = (1.35, 1.0, 1.0)
        objs.append(o)

    # ---- exhaust (rear left, under the bumper)
    bm = lathe([(0.0, 0.032), (0.18, 0.032), (0.18, 0.027), (0.02, 0.027)], 24, axis="Z")
    o = bm_to_obj("taxi_exhaust", bm, coll, [M["satin"]], parent)
    o.location = (-0.55, YR + 0.07, 0.29)
    o.rotation_euler = (math.radians(90), 0, 0)
    objs.append(o)

    # ---- fuel flap cap (hinge line read)
    # (flap panel itself is cut from the body by panel gaps on the right rear quarter)

    # ---- roof sign + taxi interior equipment
    if cfg["taxi"]:
        zr = _Zroof(-0.42) + 0.03

        def sshape(u, v, w):
            return (0.0, -v * 0.045 * w, 0.0)   # tapered (A-frame) sign
        sign = rounded_box("taxi_roof_sign", (0.62, 0.24, 0.20), coll, [M["sign_body"]], parent,
                           loc=(0, -0.42, zr + 0.12), sup=0.2, shape=sshape, levels=2)
        objs.append(sign)
        for k, sy in enumerate((1, -1)):
            bm = bmesh.new()
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
            bmesh.ops.scale(bm, vec=(0.52, 0.155, 1), verts=bm.verts)
            uvl = bm.loops.layers.uv.new("UVMap")
            for f in bm.faces:
                for lp in f.loops:
                    lp[uvl].uv = (lp.vert.co.x / 0.52 + 0.5, lp.vert.co.y / 0.155 + 0.5)
            o = bm_to_obj("taxi_roof_sign_face", bm, coll, [M["roofsign"]], parent)
            tilt = math.atan2(0.045, 0.20)
            o.location = (0, -0.42 + sy * (0.12 - 0.022 + 0.0035), zr + 0.12)
            o.rotation_euler = (math.radians(90) - tilt, 0, math.pi if sy > 0 else 0.0)
            objs.append(o)
        for sx in (1, -1):
            o = rounded_box("taxi_sign_rail", (0.03, 0.40, 0.025), coll, [M["black_tex"]], parent,
                            loc=(sx * 0.24, -0.42, zr + 0.01), sup=0.3, levels=1)
            objs.append(o)
    return objs


# ================================================================== interior
def build_interior(coll, M, parent, cfg):
    objs = []

    def seat(name, x, y, z, width, sdepth, back_h, recline, bench=False):
        cush = rounded_box(name + "_cushion", (width, sdepth, 0.13), coll, [M["seat"]], parent,
                           loc=(x, y, z), sup=0.35, levels=2,
                           shape=lambda u, v, w: (0, 0, (0.025 * (u * u) if not bench else 0.0) - 0.015 * (1 - v) * w))
        back = rounded_box(name + "_back", (width, 0.13, back_h), coll, [M["seat"]], parent,
                           loc=(x, y - sdepth / 2 + 0.02, z + back_h / 2 + 0.02), sup=0.35, levels=2,
                           shape=lambda u, v, w: (0, (0.03 * u * u if not bench else 0.0), 0))
        back.rotation_euler = (math.radians(-recline), 0, 0)
        objs.extend([cush, back])
        if not bench:
            top = Vector((x, y - sdepth / 2 + 0.02 - math.sin(math.radians(recline)) * (back_h + 0.03), z + back_h + 0.10))
            hr = rounded_box(name + "_headrest", (0.26, 0.10, 0.16), coll, [M["seat"]], parent,
                             loc=top, sup=0.45, levels=2)
            hr.rotation_euler = (math.radians(-recline), 0, 0)
            objs.append(hr)
            for px_ in (-0.06, 0.06):
                bm = lathe([(0.0, 0.006), (0.09, 0.006)], 8, axis="Z")
                o = bm_to_obj(name + "_post", bm, coll, [M["chrome"]], parent)
                o.location = top + Vector((px_, 0.01, -0.16))
                objs.append(o)

    seat("taxi_seat_drv", -0.37, 0.08, 0.50, 0.50, 0.50, 0.62, 18)
    seat("taxi_seat_pas", 0.37, 0.08, 0.50, 0.50, 0.50, 0.62, 18)
    seat("taxi_bench", 0.0, -0.86, 0.50, 1.36, 0.52, 0.56, 24, bench=True)
    # dashboard: rounded slab under the windscreen base + instrument binnacle
    dash = rounded_box("taxi_dash", (1.62, 0.46, 0.22), coll, [M["dash"]], parent, loc=(0, 0.74, 0.86),
                       sup=0.3, levels=2, shape=lambda u, v, w: (0, -0.08 * w * (1 - u * u) * 0.3, 0.03 * v))
    objs.append(dash)
    bin_ = rounded_box("taxi_binnacle", (0.38, 0.16, 0.10), coll, [M["dash"]], parent, loc=(-0.37, 0.50, 0.99),
                       sup=0.4, levels=2)
    objs.append(bin_)
    scr = rounded_box("taxi_centre_screen", (0.24, 0.02, 0.15), coll, [M["screen"]], parent,
                      loc=(0.0, 0.44, 0.92), sup=0.2, levels=1)
    scr.rotation_euler = (math.radians(-12), 0, 0)
    objs.append(scr)
    cons = rounded_box("taxi_console", (0.22, 0.75, 0.22), coll, [M["dash"]], parent, loc=(0, 0.15, 0.48),
                       sup=0.3, levels=2)
    objs.append(cons)
    # steering wheel
    bm = bmesh.new()
    ring = lathe([(0.0, 0.0)], 4, axis="Z")
    ring.free()
    rim_pts = [Vector((0.18 * math.cos(a), 0.0, 0.18 * math.sin(a))) for a in np.linspace(0, 2 * math.pi, 49)[:-1]]
    wbm = sweep_tube(rim_pts, 0.017, 10, closed=True, up=Vector((0, 1, 0)))
    o = bm_to_obj("taxi_steering_wheel", wbm, coll, [M["seat"]], parent)
    o.location = (-0.37, 0.37, 0.90)
    o.rotation_euler = (math.radians(-25), 0, 0)
    objs.append(o)
    hub = rounded_box("taxi_steering_hub", (0.30, 0.06, 0.11), coll, [M["dash"]], parent,
                      loc=(-0.37, 0.39, 0.89), sup=0.4, levels=2)
    hub.rotation_euler = (math.radians(-25), 0, 0)
    objs.append(hub)
    col_ = rounded_box("taxi_steering_column", (0.08, 0.30, 0.09), coll, [M["dash"]], parent,
                       loc=(-0.37, 0.53, 0.85), sup=0.4, levels=2)
    col_.rotation_euler = (math.radians(-25), 0, 0)
    objs.append(col_)
    # door cards / armrests
    for sx in (1, -1):
        for (y0, ln) in ((0.33, 0.72), (-0.57, 0.62)):
            ar = rounded_box("taxi_armrest", (0.07, ln, 0.06), coll, [M["dash"]], parent,
                             loc=(sx * 0.80, y0, 0.72), sup=0.3, levels=2)
            objs.append(ar)
            pnl = rounded_box("taxi_door_card", (0.03, ln + 0.1, 0.42), coll, [M["dash"]], parent,
                              loc=(sx * 0.845, y0, 0.66), sup=0.2, levels=1)
            objs.append(pnl)
    # parcel shelf
    objs.append(rounded_box("taxi_parcel_shelf", (1.55, 0.40, 0.03), coll, [M["dash"]], parent,
                            loc=(0, -1.28, 1.02), sup=0.2, levels=1))
    if cfg["taxi"]:
        # partition: lower panel + clear upper pane + frame + rear-facing passenger screen
        objs.append(rounded_box("taxi_partition_lower", (1.50, 0.04, 0.42), coll, [M["dash"]], parent,
                                loc=(0, -0.30, 0.60), sup=0.15, levels=1))
        objs.append(rounded_box("taxi_partition_pane", (1.40, 0.012, 0.42), coll, [M["perspex"]], parent,
                                loc=(0, -0.30, 1.02), sup=0.05, levels=1))
        for x in (-0.72, 0.0, 0.72):
            objs.append(rounded_box("taxi_partition_post", (0.04, 0.05, 0.86), coll, [M["satin"]], parent,
                                    loc=(x, -0.30, 0.82), sup=0.3, levels=1))
        objs.append(rounded_box("taxi_partition_top", (1.48, 0.05, 0.035), coll, [M["satin"]], parent,
                                loc=(0, -0.30, 1.245), sup=0.3, levels=1))
        o = rounded_box("taxi_rear_screen", (0.26, 0.02, 0.16), coll, [M["screen"]], parent,
                        loc=(0.30, -0.33, 0.70), sup=0.2, levels=1)
        objs.append(o)
        # taximeter on the dash
        objs.append(rounded_box("taxi_meter", (0.16, 0.09, 0.05), coll, [M["black_gloss"]], parent,
                                loc=(0.22, 0.52, 1.00), sup=0.3, levels=1))
    return objs


# ================================================================== assembly
def build(variant="yellow_cab", name=None, seed=None, dirt=None, parent_coll=None, lod=0):
    """lod 0 = hero (close-ups, 720-segment tyres, bevelled wheel parts); lod 1 = city (render
    subdiv 1, 252-segment tyres); lod 2 = background traffic (no interior, no bevels, subdiv 1,
    180-segment tyres). seed: per-instance front-wheel steer; dirt: grime amount 0..1."""
    cfg = dict(VARIANTS[variant])
    name = name or ("ASSET_taxi" if variant == "yellow_cab" else "ASSET_taxi_" + variant)
    dirt = cfg["dirt"] if dirt is None else dirt
    old = bpy.data.collections.get(name)
    if old:
        for ob in list(old.all_objects):
            bpy.data.objects.remove(ob)
        bpy.data.collections.remove(old)
    for mn in ("taxi_paint_", "taxi_glass_ws_", "taxi_glass_"):
        m = bpy.data.materials.get(mn + name)
        if m is not None and m.users == 0:
            bpy.data.materials.remove(m)
    coll = bpy.data.collections.new(name)
    (parent_coll or bpy.context.scene.collection).children.link(coll)
    root = bpy.data.objects.new(name + "_root", None)
    root.empty_display_type = "ARROWS"
    coll.objects.link(root)
    root["variant"] = variant
    tex = make_textures(variant, cfg)
    M = build_materials(variant, cfg, tex, dirt, name)
    body, blat, hl, tl = build_body(coll, M, root)
    cab, clat, glass = build_cabin(coll, M, root)
    build_lamps(coll, M, root, blat, hl, tl)
    build_wheels(coll, M, root, 720 if lod == 0 else (252 if lod == 1 else 180))
    build_details(coll, M, root, cfg, body, blat, clat, tex)
    if lod < 2:
        build_interior(coll, M, root, cfg)
    if lod >= 2:
        for ob in coll.all_objects:
            for md in [m for m in ob.modifiers if m.type == "BEVEL"]:
                ob.modifiers.remove(md)
    if lod >= 1:
        for ob in coll.all_objects:
            for md in ob.modifiers:
                if md.type == "SUBSURF":
                    md.render_levels = min(md.render_levels, 1)
                    md.levels = min(md.levels, 1)
    # per-instance variation: front wheel steer, dirt is in the paint, seed spins the wheels
    if seed is not None:
        import random
        rnd = random.Random(seed)
        for ob in coll.objects:
            if ob.name.startswith("taxi_wheel_F"):
                ob.rotation_euler.z += math.radians(rnd.uniform(-12, 12)) - math.radians(STEER_DEG)
    root["lod"] = lod
    return coll


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build("yellow_cab")
    os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
    print("saved", OUT_BLEND)


if __name__ == "__main__":
    main()
