"""VESPER v2 masked head: a skin-tight fabric hood that follows the skull (soft brow,
nose bridge, cheekbones, jaw; no ears, lips or nostrils), plus the swept-blade lenses.

The hood is a clean (u, v) grid ray-cast from the head centre against the MakeHuman head,
morphologically closed and smoothed, offset by the fabric thickness. The lenses are real
geometry laid on that surface: raised dark bevelled frame + inset mirrored-gold glass.
"""
import math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from helmet import _blur_wrap, smoothstep

NU = 320
C_HEAD = (0.0, -0.006, 1.690)
OFFSET = 0.0024
Z_BOTTOM = 1.500          # hood ends on the neck here (tucked under the white collar)
# lens design (degrees on the head sphere; u = 0 front, + = character's left)
LENS_U = (4.0, 82.0)      # inner end at the nose bridge -> blade tip past the temple
LENS_VC = (-12.5, 3.0)    # centre line rises toward the temple (swept back)
LENS_H = 20.0             # half-height at the inner end (degrees)


def _maxf(R, wu, wv, cpd):
    out = R.copy()
    for du in range(-int(wu * cpd), int(wu * cpd) + 1, max(1, int(cpd))):
        sh = np.roll(R, du, axis=1)
        for dv in range(-wv, wv + 1):
            s2 = np.concatenate([sh[dv:], np.repeat(sh[-1:], dv, 0)], 0) if dv > 0 else (
                np.concatenate([np.repeat(sh[:1], -dv, 0), sh[:dv]], 0) if dv < 0 else sh)
            out = np.maximum(out, s2)
    return out


def build(body_verts, body_faces):
    C = np.array(C_HEAD)
    bvh = BVHTree.FromPolygons([tuple(p) for p in body_verts], [tuple(f) for f in body_faces])
    u = np.linspace(-180, 180, NU, endpoint=False) + 180.0 / NU
    ur = np.radians(u)
    vg = np.arange(-85.0, 89.6, 0.7)
    vr = np.radians(vg)
    G = np.zeros((len(vg), NU))
    for i in range(len(vg)):
        for j in range(NU):
            d = Vector((math.sin(ur[j]) * math.cos(vr[i]), -math.cos(ur[j]) * math.cos(vr[i]), math.sin(vr[i])))
            hit = bvh.ray_cast(Vector(C), d, 0.5)
            rmax = 0.135 if vg[i] > -35 else min(0.30, (C[2] - 1.455) / max(math.sin(-vr[i]), 0.2))
            G[i, j] = min(hit[3], rmax) if hit[0] is not None else rmax
    cpd = NU / 360.0
    UU, VV = np.meshgrid(u, vg)
    AU = np.abs(UU)
    # closing fills eye sockets and the gaps under the ears; light blur keeps the skull
    Gc = -_maxf(-_maxf(G, 4, 6, cpd), 4, 6, cpd)
    Gs = _blur_wrap(Gc, 2.4 * cpd, 3.4)
    # nose: a soft bridge only (no tip, no nostrils)
    nose = (1 - smoothstep(9, 22, AU)) * smoothstep(-40, -32, VV) * (1 - smoothstep(-12, -4, VV))
    Gn = _blur_wrap(_maxf(G, 6, 4, cpd), 7 * cpd, 6)
    Gn = np.minimum(Gn, _blur_wrap(Gc, 9 * cpd, 9) + 0.010)        # caps the nose tip
    Gs = Gs * (1 - nose) + np.maximum(Gs, Gn) * nose
    # mouth: lips smoothed away, chin and jaw kept
    mouth = (1 - smoothstep(26, 40, AU)) * smoothstep(-62, -54, VV) * (1 - smoothstep(-40, -33, VV))
    Gm = _blur_wrap(_maxf(Gc, 8, 6, cpd), 9 * cpd, 8)
    Gs = Gs * (1 - mouth) + Gm * mouth
    # ears: strong local smoothing (no ear shapes under the fabric)
    ear = smoothstep(62, 76, AU) * (1 - smoothstep(110, 124, AU)) * smoothstep(-50, -36, VV) * (1 - smoothstep(0, 12, VV))
    Gs = Gs * (1 - ear) + _blur_wrap(Gs, 12 * cpd, 12) * ear
    # low centre crest from the brow over the crown to the nape
    ang = np.minimum(AU, 180 - AU)
    crest = 0.0024 * np.exp(-0.5 * (ang / 2.6) ** 2) * smoothstep(0, 14, VV) * (AU < 90) \
        + 0.0024 * np.exp(-0.5 * (ang / 2.6) ** 2) * smoothstep(-30, -10, VV) * (AU >= 90)
    Gs = Gs + OFFSET + crest
    Gref = _blur_wrap(Gs, 20 * cpd, 20)
    # head part: from the jaw line up to the crown
    au = np.abs(u)
    vjaw = -42 + 12 * smoothstep(0, 95, au) - 14 * smoothstep(110, 180, au)
    NVH = 130
    rows = [vjaw + (89.2 - vjaw) * ((i / (NVH - 1)) ** 1.12) for i in range(NVH)]
    Vh = np.array(rows)
    Rh = np.zeros_like(Vh)
    for j in range(NU):
        Rh[:, j] = np.interp(Vh[:, j], vg, Gs[:, j])
    Vr = np.radians(Vh)
    dirs = np.stack([np.sin(ur)[None] * np.cos(Vr), -np.cos(ur)[None] * np.cos(Vr), np.sin(Vr)], -1)
    Ph = C[None, None] + dirs * Rh[..., None]
    # neck part: a smooth loft from a ring on the neck up to the jaw line (the hood skin
    # bridges under the chin like real fabric: no throat cavities, no chin under-cut)
    Cn = np.array([0.0, 0.028, Z_BOTTOM])
    rn = np.zeros(NU)
    for j in range(NU):
        dh = Vector((math.sin(ur[j]), -math.cos(ur[j]), 0.0))
        hit = bvh.ray_cast(Vector(Cn), dh, 0.2)
        rn[j] = min(hit[3], 0.066) if hit[0] is not None else 0.06
    for it in range(8):
        rn = 0.5 * rn + 0.25 * (np.roll(rn, 1) + np.roll(rn, -1))
    ring = Cn[None] + np.stack([np.sin(ur), -np.cos(ur), np.zeros(NU)], -1) * (rn + OFFSET)[:, None]
    NVN = 22
    jaw = Ph[0]
    # tangent continuity at the jaw: start direction follows the head surface downward
    tj = Ph[0] - Ph[2]
    tj /= np.linalg.norm(tj, axis=1, keepdims=True)
    span = np.linalg.norm(jaw - ring, axis=1, keepdims=True)
    neck = []
    for i in range(NVN):
        t = i / NVN
        h00 = 2 * t ** 3 - 3 * t ** 2 + 1; h10 = t ** 3 - 2 * t ** 2 + t
        h01 = -2 * t ** 3 + 3 * t ** 2; h11 = t ** 3 - t ** 2
        m0 = np.array([0, 0, 1.0])[None] * span * 0.3        # leave the neck vertically
        m1 = -tj * span * 0.25                                # arrive along the head surface (keeps a jaw undercut)
        neck.append(h00 * ring + h10 * m0 + h01 * jaw + h11 * m1)
    Pg = np.concatenate([np.array(neck), Ph], 0)
    V = np.concatenate([np.full((NVN, NU), -80.0) + np.arange(NVN)[:, None] * 0.0, Vh], 0)
    R = np.concatenate([np.zeros((NVN, NU)), Rh], 0)
    # tuck: the bottom edge rolls inward 2 mm (tucked under the collar)
    nd = np.stack([np.sin(ur), -np.cos(ur), np.zeros(NU)], -1)
    tuck = Pg[0] - nd * 0.002 + np.array([0, 0, 0.003])
    Pg = np.concatenate([tuck[None], Pg], 0)
    verts = Pg.reshape(-1, 3).tolist()
    top = C + np.array([0, 0, Rh[-1].mean()])
    verts.append(top.tolist())
    itop = len(verts) - 1
    NR = Pg.shape[0]
    faces = []
    for i in range(NR - 1):
        for j in range(NU):
            a = i * NU + j; b = i * NU + (j + 1) % NU
            faces.append((a, b, b + NU, a + NU))
    for j in range(NU):
        faces.append(((NR - 1) * NU + j, (NR - 1) * NU + (j + 1) % NU, itop))
    Vfull = np.concatenate([V[:1] - 0.5, V], 0)
    hp = np.stack([np.broadcast_to(u[None], Vfull.shape), Vfull, np.zeros_like(Vfull)], -1).reshape(-1, 3)
    hp[:, 2] = np.repeat(np.arange(NR), NU) / float(NVN + 1)      # 0..1 neck loft, > 1 on the head
    hp = np.concatenate([hp, [[0, 90, 1]]], 0)
    return dict(verts=np.array(verts), faces=faces, hp=hp, C=C, u=u, vg=vg, Gs=Gs, n_neck=NVN + 1, NU=NU, ring_r=rn, ring_c=Cn, Gref=Gref)


def surface_point(md, uu, vv, extra=0.0):
    """point on the hood surface at (u, v) degrees, plus `extra` radial offset"""
    u = md['u']; vg = md['vg']; Gs = md['Gs']
    j = (uu + 180.0) / (360.0 / len(u)) - 0.5
    j0 = int(math.floor(j)) % len(u); j1 = (j0 + 1) % len(u); fj = j - math.floor(j)
    r = (1 - fj) * np.interp(vv, vg, Gs[:, j0]) + fj * np.interp(vv, vg, Gs[:, j1])
    ur, vr = math.radians(uu), math.radians(vv)
    d = np.array([math.sin(ur) * math.cos(vr), -math.cos(ur) * math.cos(vr), math.sin(vr)])
    return md['C'] + d * (r + extra)


def _env_point(md, uu, vv, extra):
    u = md['u']; vg = md['vg']
    j = (uu + 180.0) / (360.0 / len(u)) - 0.5
    j0 = int(math.floor(j)) % len(u); j1 = (j0 + 1) % len(u); fj = j - math.floor(j)
    def rad(G):
        return (1 - fj) * np.interp(vv, vg, G[:, j0]) + fj * np.interp(vv, vg, G[:, j1])
    r = max(rad(md['Gref']), rad(md['Gs']) + 0.0003)
    ur, vr = math.radians(uu), math.radians(vv)
    d = np.array([math.sin(ur) * math.cos(vr), -math.cos(ur) * math.cos(vr), math.sin(vr)])
    return md['C'] + d * (r + extra)


# lens: sideways irregular kite (degrees on the head sphere, u from the midline)
#        inner tip   top corner   tail (up and back past the temple)   bottom corner
KITE = [(7.4, -15.0), (20.0, -5.0), (93.0, 4.0), (28.0, -20.0)]


def _kite_outline(n=160):
    """closed smooth outline of the lens (corners slightly rounded)"""
    pts = np.array(KITE + [KITE[0]], float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, s[-1], n, endpoint=False)
    P = np.stack([np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])], 1)
    for it in range(4):
        P = 0.5 * P + 0.25 * (np.roll(P, 1, 0) + np.roll(P, -1, 0))
    return P


def lens(md, side=1, nring=None):
    """One lens: rings inset from the outline by distance (mm): outer bevel rising to a
    3.5 mm dark-bronze bezel, inner bevel, then an opaque domed mirror.  Built on the
    smoothed envelope Gref (no socket/eyeball relief).  Returns verts, faces, mat index
    (0 bezel, 1 glass)."""
    O = _kite_outline()
    c = O.mean(0)
    r_mm = 0.105 * math.pi / 180.0 * 1000.0
    # (inset mm, height mm, material)
    # inset: mm from the outline, or (negative) a fraction of the way to the centre
    prof = [(-1.2, -1.2, 0), (0.0, 0.3, 0), (0.6, 1.6, 0), (1.5, 2.3, 0), (3.0, 2.3, 0), (3.5, 1.7, 0),
            (3.9, 1.1, 1), (-0.42, 1.55, 1), (-0.62, 1.85, 1), (-0.80, 2.05, 1), (-0.92, 2.15, 1)]
    V, rings = [], []
    n = len(O)
    for inset, h, m in prof:
        ring = []
        for k in range(n):
            p = O[k]
            d = c - p
            L = np.linalg.norm(d) * r_mm
            if inset < 0:
                f = max(-inset, min(3.9 / max(L, 1e-6), 0.35) + 0.02)
            else:
                f = min(inset / max(L, 1e-6), 0.33)
            q = p + d * f
            ring.append(len(V))
            V.append(_env_point(md, q[0] * side, q[1], h / 1000.0))
        rings.append(ring)
    V.append(_env_point(md, c[0] * side, c[1], 2.25 / 1000.0)); ic = len(V) - 1
    F, M = [], []
    for r in range(len(prof) - 1):
        for k in range(n):
            a, b = rings[r][k], rings[r][(k + 1) % n]
            c2, d2 = rings[r + 1][(k + 1) % n], rings[r + 1][k]
            F.append((a, b, c2, d2) if side > 0 else (a, d2, c2, b))
            M.append(prof[r + 1][2] if prof[r][2] == prof[r + 1][2] else 0)
    for k in range(n):
        a, b = rings[-1][k], rings[-1][(k + 1) % n]
        F.append((a, b, ic) if side > 0 else (a, ic, b)); M.append(1)
    return np.array(V), F, M


def bridle_path(md, side=1, n=60):
    """from the lens tail around the skull to the nape (degrees), for the gold bridle line"""
    u0, v0 = KITE[2]
    pts = []
    for k in range(n + 1):
        t = k / n
        uu = u0 + (176.0 - u0) * t
        vv = v0 + (-30.0 - v0) * (t ** 1.4)
        pts.append(_env_point(md, uu * side, vv, 0.0))
    return np.array(pts)


def tuck_body(P, md, head_w, margin=0.005):
    """keep the suit's neck inside the hood: clamp the horizontal radius of body
    vertices above the hood rim to the rim radius; flag head/jaw vertices to delete."""
    P = P.copy()
    Cn = md['ring_c']; rn = md['ring_r']; u = md['u']
    kill = np.zeros(len(P), bool)
    for k in range(len(P)):
        z = P[k, 2]
        if z <= Z_BOTTOM - 0.004 or abs(P[k, 0]) > 0.13:
            continue
        dx, dy = P[k, 0] - Cn[0], P[k, 1] - Cn[1]
        r = math.hypot(dx, dy)
        if r > 0.14:
            continue
        a = math.degrees(math.atan2(dx, -dy))
        lim = np.interp(a, u, rn, period=360.0) + OFFSET - margin
        w = min(1.0, (z - (Z_BOTTOM - 0.004)) / 0.01)
        # trapezius rising above the collar: slope it down to meet under the collar band
        zmax = Z_BOTTOM + 0.003 + max(0.0, r - lim) * 0.55
        if z > zmax and r < lim + 0.05 and r > lim + 0.012 and z < Z_BOTTOM + 0.06:
            P[k, 2] = zmax
            z = zmax
        if r > lim:
            rr = r + (lim - r) * w
            P[k, 0] = Cn[0] + dx / r * rr; P[k, 1] = Cn[1] + dy / r * rr
        if z > Z_BOTTOM + 0.035 and head_w[k] > 0.2:
            kill[k] = True
        if z > Z_BOTTOM + 0.022 and dy > 0.0:          # nape: always under the hood
            kill[k] = True
        if z > Z_BOTTOM + 0.006 and r < lim + margin + 0.004:   # neck under hood + collar
            kill[k] = True
    return P, kill
