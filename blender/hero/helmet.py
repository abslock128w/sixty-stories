"""VESPER cowl: a smooth helmet shell fitted to the MakeHuman head by ray casting, with
one continuous recessed visor band (bevelled dark frame + amber mirrored glass).

Mesh is generated directly at render density (no subsurf). Material slots:
0 shell, 1 visor frame, 2 visor glass, 3 inner lip (dark).
"""
import math
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

NU = 400                       # columns around the head
V_TOP = 90.0
VISOR_U = 84.0                 # visor half-extent in degrees (temple to temple)
# designed lower face: horizontal distances (m) from the head centre at visor level /
# at the chin, and the underside height (front, side, back)
CHIN_PROF = ((-72, 0.094), (-52, 0.106), (-34, 0.1175), (-20, 0.110), (-12, 0.102), (0, 0.100))
CHEEK_PROF = ((-72, 0.070), (-45, 0.088), (-25, 0.099), (-10, 0.098), (0, 0.098))
SIDE_PROF = ((-72, 0.064), (-40, 0.078), (-10, 0.084), (0, 0.084))
BOTTOM_Z = (1.552, 1.572, 1.590)
BROW = 0.0032
VISOR_H_MM = 31.0              # visor height at centre
VISOR_DEPTH = 0.0048           # recess depth
# fractions across the band (bottom->top) and recess profile (0 = shell surface, 1 = floor)
BAND_F = [0.0, 0.02, 0.045, 0.07, 0.085, 0.10, 0.125, 0.15, 0.17, 0.30, 0.5, 0.70, 0.83, 0.85, 0.875, 0.90, 0.915, 0.93, 0.955, 0.98, 1.0]
BAND_D = [0.0, -0.07, -0.10, -0.07, 0.05, 0.45, 0.85, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.85, 0.45, 0.05, -0.07, -0.10, -0.07, 0.0]
#         raised bevelled lip      | wall down to the dark floor | inner (behind glass) |  wall | lip
#         edge  bevel ...  frame floor  | glass (slightly convex) |   frame floor ... bevel  edge
BAND_MAT = [1] * 8 + [2] * 4 + [1] * 8   # per face row inside band (len = len(BAND_F) - 1)
GLASS_F = (0.11, 0.89)   # glass pane spans the walls, sits at GLASS_D of the depth
GLASS_D = 0.42


def _blur_wrap(R, sig_u, sig_v):
    """separable gaussian on (v, u) grid, wrapping in u, clamped in v (in cells)."""
    def k1(s):
        n = max(1, int(3 * s))
        x = np.arange(-n, n + 1)
        k = np.exp(-0.5 * (x / max(s, 1e-3)) ** 2)
        return k / k.sum(), n
    k, n = k1(sig_u)
    out = np.zeros_like(R)
    for i, w in enumerate(k):
        out += w * np.roll(R, i - n, axis=1)
    R = out
    k, n = k1(sig_v)
    P = np.pad(R, ((n, n), (0, 0)), mode='edge')
    out = np.zeros_like(R)
    for i, w in enumerate(k):
        out += w * P[i:i + R.shape[0]]
    return out


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def build(body_verts, body_faces, center=(0.0, -0.006, 1.690), offset=0.0062):
    C = np.array(center)
    bvh = BVHTree.FromPolygons([tuple(p) for p in body_verts], [tuple(f) for f in body_faces])
    u = np.linspace(-180, 180, NU, endpoint=False) + 180.0 / NU   # 0 = front, + = char left
    ur = np.radians(u)
    au = np.abs(u)
    # bottom edge elevation per column: under the chin at the front, jaw corner at the
    # sides, nape at the back
    vmin = -66 + 4 * smoothstep(0, 100, au) + 7 * smoothstep(110, 180, au)
    # visor geometry (angle units): centre line rises slightly toward the temples
    vr_nom = 0.103
    v_c = -12.5 + 9.0 * (au / VISOR_U) ** 2
    hmm = VISOR_H_MM * (1 - 0.38 * (au / VISOR_U) ** 2.5)
    # band ends: rounded by shrinking height in the last few degrees
    endk = np.sqrt(np.clip((VISOR_U - au) / 7.0, 0, 1))
    hmm = np.where(au <= VISOR_U, np.maximum(hmm * (0.25 + 0.75 * endk), 2.0), 9.0)
    dv = np.degrees(hmm / 1000.0 / vr_nom)
    v_lo = v_c - dv / 2
    v_hi = v_c + dv / 2
    # around the back, continue the band rows as a smooth line (becomes a panel seam)
    back = au > VISOR_U
    v_lo = np.where(back, v_c - 2.5, v_lo)
    v_hi = np.where(back, v_c + 2.5, v_hi)
    # rows: bottom lip (2), lower zone, band rows, upper zone, pole
    n_low, n_up = 46, 100
    rows = []
    for k in range(n_low):
        t = k / n_low
        rows.append(('low', vmin + (v_lo - vmin) * t, 0.0))
    for k, f in enumerate(BAND_F):
        rows.append(('band', v_lo + (v_hi - v_lo) * f, BAND_D[k]))
    for k in range(1, n_up):
        t = k / n_up
        # denser near the band, sparser toward the crown
        tt = t ** 1.25
        rows.append(('up', v_hi + (V_TOP - 0.6 - v_hi) * tt, 0.0))
    NV = len(rows)
    V = np.array([r[1] for r in rows])          # (NV, NU) degrees
    D = np.array([r[2] * np.ones(NU) for r in rows])
    vr = np.radians(V)
    dirs = np.stack([np.sin(ur)[None] * np.cos(vr), -np.cos(ur)[None] * np.cos(vr), np.sin(vr)], -1)
    # --- radius field on a uniform 1-degree grid, then resampled onto the rows
    vg = np.arange(-85.0, 90.5, 1.0)
    vgr = np.radians(vg)
    G = np.zeros((len(vg), NU))
    for i in range(len(vg)):
        for j in range(NU):
            d = Vector((math.sin(ur[j]) * math.cos(vgr[i]), -math.cos(ur[j]) * math.cos(vgr[i]), math.sin(vgr[i])))
            hit = bvh.ray_cast(Vector(C), d, 0.4)
            G[i, j] = hit[3] if hit[0] is not None else 0.1
    cpd = NU / 360.0                         # columns per degree
    def maxf(R, wu_deg, wv):
        out = R.copy()
        for du in range(-int(wu_deg * cpd), int(wu_deg * cpd) + 1, max(1, int(cpd))):
            sh = np.roll(R, du, axis=1)
            for dv_ in range(-wv, wv + 1):
                s2 = np.concatenate([sh[dv_:], np.repeat(sh[-1:], dv_, 0)], 0) if dv_ > 0 else (
                    np.concatenate([np.repeat(sh[:1], -dv_, 0), sh[:dv_]], 0) if dv_ < 0 else sh)
                out = np.maximum(out, s2)
        return out
    def minf(R, wu_deg, wv):
        return -maxf(-R, wu_deg, wv)
    UU, VV = np.meshgrid(u, vg)
    AU = np.abs(UU)
    # morphological closing fills concavities (eye sockets, ear gaps) but keeps convex
    # forms: brow ridge, cheekbones, jaw, chin
    Gc = minf(maxf(G, 6, 6), 6, 6)
    Gs = _blur_wrap(Gc, 4.5 * cpd, 4.0)
    ear = smoothstep(66, 80, AU) * (1 - smoothstep(110, 124, AU)) * smoothstep(-45, -32, VV) * (1 - smoothstep(0, 12, VV))
    Gs = Gs * (1 - ear) + _blur_wrap(Gs, 12 * cpd, 10) * ear
    Gs = 0.35 * _blur_wrap(Gs, 14 * cpd, 12) + 0.65 * Gs
    # --- cranium: tight to the skull, a little lower/smaller at the crown, flat temples
    Gcr = Gs * (1 - 0.05 * smoothstep(-25, 10, VV) - 0.02 * smoothstep(40, 85, VV)) + offset
    temple = smoothstep(52, 66, AU) * (1 - smoothstep(108, 125, AU)) * smoothstep(-22, -8, VV) * (1 - smoothstep(20, 40, VV))
    Gcr = Gcr * (1 - 0.04 * temple)
    # --- lower face: designed planes (chin bar front, cheek planes angled in, sides) and
    # a flat underside, combined with a soft minimum -> crisp bevelled breaks
    cosv = np.cos(np.radians(VV)); sinv = np.sin(np.radians(VV))
    lo = np.clip((-VV - 12) / 50.0, 0, 1)            # 0 at the visor, 1 near the chin
    planes = []
    def hplane(theta, d):
        c = np.cos(np.radians(AU - theta))
        return np.where(c > 0.15, d / np.maximum(cosv * c, 1e-3), 9.0)
    prof = lambda P_: np.interp(VV, [p[0] for p in P_], [p[1] for p in P_])
    planes.append(hplane(0.0, prof(CHIN_PROF)))
    planes.append(hplane(40.0, prof(CHEEK_PROF)))
    planes.append(hplane(82.0, prof(SIDE_PROF)))
    zb = BOTTOM_Z[0] + (BOTTOM_Z[1] - BOTTOM_Z[0]) * smoothstep(0, 100, AU) + (BOTTOM_Z[2] - BOTTOM_Z[1]) * smoothstep(110, 180, AU)
    planes.append(np.where(sinv < -0.05, (C[2] - zb) / np.maximum(-sinv, 1e-3), 9.0))
    k = 0.0028
    Pm = np.stack(planes, 0)
    Rpl = -k * np.log(np.exp(-(Pm - Pm.min(0)) / k).sum(0)) + Pm.min(0)
    # back of the head: skull + the underside plane
    Rbk = -k * np.log(np.exp(-(Gcr - np.minimum(Gcr, planes[-1])) / k) + np.exp(-(planes[-1] - np.minimum(Gcr, planes[-1])) / k)) + np.minimum(Gcr, planes[-1])
    wfront = 1 - smoothstep(98, 128, AU)
    Rlow = Rpl * wfront + Rbk * (1 - wfront)
    # visor band rides on the chin-bar/cheek surface; above it the cranium takes over
    vce = -12.5 + 9.0 * (np.clip(AU, 0, VISOR_U) / VISOR_U) ** 2
    wtop = smoothstep(vce + 3, vce + 14, VV) * wfront + (1 - wfront) * smoothstep(-40, -20, VV)
    Gd = Rlow * (1 - wtop) + Gcr * wtop
    # nothing of the real head may poke through
    Gd = np.maximum(Gd, _blur_wrap(Gc, 2 * cpd, 2) + 0.0042)
    # brow overhang above the visor (visor sits recessed under it), occipital roll
    brow = np.exp(-0.5 * ((VV - (vce + 10.0)) / 3.0) ** 2) * (1 - smoothstep(35, 70, AU))
    Gd = Gd + BROW * brow
    occ = np.exp(-0.5 * ((VV + 12) / 5.0) ** 2) * smoothstep(118, 150, AU)
    Gd = Gd + 0.0032 * occ
    Gs = Gd
    # resample per column onto the row elevations
    Rf = np.zeros((NV, NU)); R = np.zeros((NV, NU))
    for j in range(NU):
        Rf[:, j] = np.interp(V[:, j], vg, Gs[:, j])
        R[:, j] = np.interp(V[:, j], vg, G[:, j])
    # crown centre ridge: raised soft fin from the visor top over to the nape
    ridge_w = np.radians(4.0)
    ang = np.minimum(np.abs(ur), np.pi - np.abs(ur))   # distance to the mid-sagittal plane
    vis_top = V > (v_hi[None] + 6)
    ridge = 0.0022 * np.exp(-0.5 * (ang / ridge_w) ** 2)[None] * vis_top * smoothstep(0, 18, V - v_hi[None])
    Rf = Rf + ridge
    # visor recess (only inside the visor columns)
    in_vis = (au <= VISOR_U)
    Dm = D * in_vis[None]
    Rpre = Rf.copy()
    Rf = Rf - VISOR_DEPTH * Dm
    P = C[None, None] + dirs * Rf[..., None]
    # bottom rolled lip: two extra rows going inward and up
    n0 = dirs[0]
    lip1 = P[0] - n0 * 0.0035 + np.array([0, 0, -0.0012])
    lip2 = P[0] - n0 * 0.0055 + np.array([0, 0, 0.006])
    P = np.concatenate([lip2[None], lip1[None], P], 0)
    NV2 = P.shape[0]
    top = C + np.array([0, 0, Rf[-1].mean() + 0.0002])
    verts = P.reshape(-1, 3).tolist() + [top.tolist()]
    itop = len(verts) - 1
    faces, mats, uvs = [], [], []
    band0 = 2 + n_low                        # first band row index in P
    def vid(i, j):
        return i * NU + (j % NU)
    # uv: x = arc around (metres at nominal radius), y = elevation metres
    for i in range(NV2 - 1):
        for j in range(NU):
            faces.append((vid(i, j), vid(i, j + 1), vid(i + 1, j + 1), vid(i + 1, j)))
            m = 0
            if i < 2:
                m = 3
            elif band0 <= i < band0 + len(BAND_F) - 1:
                jj = j
                if abs(u[jj]) <= VISOR_U - 1.2 and abs(u[(jj + 1) % NU]) <= VISOR_U - 1.2:
                    m = 2 if BAND_MAT[i - band0] == 2 else 1
                elif abs(u[jj]) <= VISOR_U + 0.5:
                    m = 1
            mats.append(m)
    for j in range(NU):
        faces.append((vid(NV2 - 1, j), vid(NV2 - 1, j + 1), itop))
        mats.append(0)
    # per-vertex params (u deg, v deg, band fraction) for shader panel lines
    Vfull = np.concatenate([V[:1] - 3, V[:1] - 1.5, V], 0)
    Ufull = np.broadcast_to(u[None], Vfull.shape)
    params = np.stack([Ufull, Vfull, np.zeros_like(Vfull)], -1).reshape(-1, 3)
    params = np.concatenate([params, [[0, 90, 0]]], 0)
    # band position helper: signed distance (deg) above band centre line
    vc_full = np.broadcast_to(v_c[None], Vfull.shape).reshape(-1)
    params[:-1, 2] = Vfull.reshape(-1) - vc_full
    # glass pane: a separate thin surface floating inside the recess (real depth)
    gcols = [j for j in range(NU) if abs(u[j]) <= VISOR_U - 0.8]
    gcols.sort(key=lambda j: u[j])
    nf = 14
    GV, GF = [], []
    for jj, j in enumerate(gcols):
        for k in range(nf + 1):
            f = GLASS_F[0] + (GLASS_F[1] - GLASS_F[0]) * k / nf
            vv = v_lo[j] + (v_hi[j] - v_lo[j]) * f
            rr = np.interp(vv, V[:, j], Rpre[:, j]) - VISOR_DEPTH * GLASS_D
            # slight convex bow across the pane
            rr += 0.0006 * math.sin(math.pi * k / nf)
            vr_ = math.radians(vv)
            dvec = np.array([math.sin(ur[j]) * math.cos(vr_), -math.cos(ur[j]) * math.cos(vr_), math.sin(vr_)])
            GV.append(C + dvec * rr)
    for jj in range(len(gcols) - 1):
        for k in range(nf):
            a = jj * (nf + 1) + k
            GF.append((a, a + 1, a + nf + 2, a + nf + 1))
    return dict(verts=np.array(verts), faces=faces, mats=mats, params=params,
                glass=(np.array(GV), GF),
                center=C, v_c=v_c, u=u, Vgrid=V, Rgrid=Rf + VISOR_DEPTH * Dm, vmin=vmin)


def fit_body(P, hd, margin=0.0045, hide_margin=0.010, head_w=None):
    """Pull body vertices that would poke through the shell inside it, and flag those
    deep inside (their faces can be deleted)."""
    C = hd['center']; u = hd['u']; V = hd['Vgrid']; R = hd['Rgrid']; vmin = hd['vmin']
    P = P.copy()
    d = P - C
    r = np.linalg.norm(d, axis=1)
    pu = np.degrees(np.arctan2(d[:, 0], -d[:, 1]))
    pv = np.degrees(np.arcsin(np.clip(d[:, 2] / np.maximum(r, 1e-9), -1, 1)))
    j = np.clip(np.round((pu + 180 - 180.0 / len(u)) / (360.0 / len(u))).astype(int), 0, len(u) - 1)
    inside = np.zeros(len(P), bool)
    for k in range(len(P)):
        if r[k] > 0.25:
            continue
        jj = j[k]
        vlo = vmin[jj]
        if pv[k] < vlo - 8:
            continue
        Rh = np.interp(pv[k], V[:, jj], R[:, jj])
        # blend: fully constrained above the lip, fading out 25 deg below it
        w = np.clip((pv[k] - (vlo - 8)) / 10.0, 0, 1) ** 1.5
        lim = Rh - margin
        if r[k] > lim and w > 0 and r[k] < Rh + 0.012:
            rn = r[k] + (lim - r[k]) * w
            P[k] = C + d[k] / r[k] * rn
        # seal: the neck fabric flares out to meet the inside of the bottom lip
        ws = 0.0
        if ws > 0 and r[k] < lim and r[k] > Rh - 0.06:
            P[k] = C + d[k] / r[k] * (r[k] + (lim - r[k]) * ws)
        if pv[k] > vlo + 3 and r[k] < Rh - 0.004:
            inside[k] = True
    return P, inside


def make_object(data, name='HERO_helmet'):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in data['verts']], [], data['faces'])
    me.update()
    me.polygons.foreach_set('material_index', data['mats'])
    for p in me.polygons:
        p.use_smooth = True
    a = me.attributes.new('hp', 'FLOAT_VECTOR', 'POINT')
    a.data.foreach_set('vector', np.asarray(data['params'], float).ravel())
    r = me.attributes.new('rest', 'FLOAT_VECTOR', 'POINT')
    r.data.foreach_set('vector', np.asarray(data['verts'], float).ravel())
    ob = bpy.data.objects.new(name, me)
    return ob
