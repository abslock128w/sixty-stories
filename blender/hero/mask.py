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
Z_BOTTOM = 1.488          # hood ends on the neck here (tucked under the white collar)
# lens design (degrees on the head sphere; u = 0 front, + = character's left)
LENS_U = (5.0, 79.0)      # inner end at the nose bridge -> blade tip past the temple
LENS_VC = (-12.5, 3.0)    # centre line rises toward the temple (swept back)
LENS_H = 15.5             # half-height at the inner end (degrees)


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
            G[i, j] = min(hit[3], 0.135) if hit[0] is not None else 0.135
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
    Gs = Gs + OFFSET
    # per column: lowest elevation whose surface point is still above Z_BOTTOM
    vb = np.zeros(NU)
    for j in range(NU):
        z = C[2] + Gs[:, j] * np.sin(vr)
        k = len(vg) - 1
        while k > 0 and z[k - 1] >= Z_BOTTOM and vg[k - 1] > -78:
            k -= 1
        # interpolate the crossing
        if k > 0:
            z0, z1 = z[k - 1], z[k]
            f = (Z_BOTTOM - z0) / max(z1 - z0, 1e-6)
            vb[j] = vg[k - 1] + f * (vg[k] - vg[k - 1])
        else:
            vb[j] = vg[0]
    vb = np.convolve(np.concatenate([vb[-6:], vb, vb[:6]]), np.ones(13) / 13, 'same')[6:-6]
    NV = 150
    rows = []
    for i in range(NV):
        t = i / (NV - 1)
        rows.append(vb + (89.2 - vb) * (t ** 1.15))
    V = np.array(rows)
    R = np.zeros_like(V)
    for j in range(NU):
        R[:, j] = np.interp(V[:, j], vg, Gs[:, j])
    Vr = np.radians(V)
    dirs = np.stack([np.sin(ur)[None] * np.cos(Vr), -np.cos(ur)[None] * np.cos(Vr), np.sin(Vr)], -1)
    Pg = C[None, None] + dirs * R[..., None]
    # tuck: the bottom edge rolls inward 2 mm (tucked under the collar)
    tuck = Pg[0] - dirs[0] * 0.002 + np.array([0, 0, 0.003])
    Pg = np.concatenate([tuck[None], Pg], 0)
    verts = Pg.reshape(-1, 3).tolist()
    top = C + np.array([0, 0, R[-1].mean()])
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
    hp[:, 2] = np.repeat(np.arange(NR), NU) / (NR - 1)
    hp = np.concatenate([hp, [[0, 90, 1]]], 0)
    return dict(verts=np.array(verts), faces=faces, hp=hp, C=C, u=u, vg=vg, Gs=Gs)


def surface_point(md, uu, vv, extra=0.0):
    """point on the hood surface at (u, v) degrees, plus `extra` radial offset"""
    u = md['u']; vg = md['vg']; Gs = md['Gs']
    j = (uu + 180.0) / (360.0 / len(u)) - 0.5
    j0 = int(math.floor(j)) % len(u); j1 = (j0 + 1) % len(u); fj = j - math.floor(j)
    r = (1 - fj) * np.interp(vv, vg, Gs[:, j0]) + fj * np.interp(vv, vg, Gs[:, j1])
    ur, vr = math.radians(uu), math.radians(vv)
    d = np.array([math.sin(ur) * math.cos(vr), -math.cos(ur) * math.cos(vr), math.sin(vr)])
    return md['C'] + d * (r + extra)


def lens(md, side=1, na=48, ns=26):
    """One swept-blade lens: returns verts, faces, material index per face (0 frame, 1 glass).
    Frame: raised 2.4 mm with a rounded outer bevel and an inner bevel down to the glass,
    which sits 1.1 mm proud of the fabric and bulges slightly."""
    u0, u1 = LENS_U
    L_deg = u1 - u0
    def outline(a):
        uu = u0 + L_deg * a
        vc = LENS_VC[0] + (LENS_VC[1] - LENS_VC[0]) * a ** 1.5
        h = LENS_H * (1 - a) ** 0.75
        h *= 0.55 + 0.45 * math.sqrt(min(1.0, a / 0.10))      # blunt rounded inner end
        h = max(h, 0.25)
        return uu, vc, h
    As = np.concatenate([[0.0, 0.004, 0.012, 0.025, 0.045], np.linspace(0.07, 0.93, na), [0.955, 0.975, 0.988, 0.996, 1.0]])
    Ss = np.concatenate([[-1.0, -0.985, -0.95, -0.9, -0.84, -0.78, -0.72], np.linspace(-0.62, 0.62, ns), [0.72, 0.78, 0.84, 0.9, 0.95, 0.985, 1.0]])
    r_mm = 0.105 * math.pi / 180.0 * 1000.0          # mm per degree on the head
    V, mats_v = [], []
    for a in As:
        uu, vc, h = outline(a)
        for s in Ss:
            # lower edge straighter than the upper (blade)
            vv = vc + h * (s if s > 0 else 0.72 * s)
            d_edge = min((1 - abs(s)) * h * r_mm * (1.0 if s > 0 else 0.72), a * L_deg * r_mm * 0.9,
                         (1 - a) * L_deg * r_mm * 0.9)
            # height profile (mm): bevel up to frame top, frame, inner bevel down to glass
            if d_edge < 0.9:
                z = 0.2 + 2.2 * math.sin(min(1.0, d_edge / 0.9) * math.pi / 2)
            elif d_edge < 2.6:
                z = 2.4
            elif d_edge < 3.4:
                z = 2.4 - 1.5 * smoothstep(2.6, 3.4, d_edge)
            else:
                z = 0.9 + 0.5 * min(1.0, (d_edge - 3.4) / 6.0)
            V.append(surface_point(md, uu * side, vv, z / 1000.0 - 0.0006))
            mats_v.append(1 if d_edge > 3.0 else 0)
    na_, ns_ = len(As), len(Ss)
    F, M = [], []
    for i in range(na_ - 1):
        for k in range(ns_ - 1):
            a = i * ns_ + k
            f = (a, a + ns_, a + ns_ + 1, a + 1) if side > 0 else (a, a + 1, a + ns_ + 1, a + ns_)
            F.append(f)
            M.append(1 if min(mats_v[a], mats_v[a + 1], mats_v[a + ns_], mats_v[a + ns_ + 1]) == 1 else 0)
    return np.array(V), F, M
