"""Suit design fields, computed once on the rest-pose mesh and stored as per-vertex
attributes (so every pattern sticks to the deforming surface):

  pipe_sd  signed distance (m) to the nearest amber piping line (zero on the line)
  pipe_s   arc length (m) along that line (for stitches)
  seam_sd  signed distance to the nearest stitched (non-glowing) seam
  seam_s   arc length along that seam
  tone_sd  signed distance to the nearest panel boundary, positive on the dark-panel side
  zone     0 suit, 1 glove, 2 grip (palm / finger pads), 3 shoe upper, 4 sole

Lines are authored as control points on the rest body (ray cast from inside bones /
torso axis outward), joined by straight segments that are densified and snapped to the
surface, giving clean geometric tension seams.
"""
import math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

CAP = 0.03


class Surf:
    def __init__(self, P, F, J):
        self.P = P
        self.bvh = BVHTree.FromPolygons([tuple(p) for p in P], [tuple(f) for f in F])
        self.J = J

    def cast(self, anchor, d):
        d = Vector(d).normalized()
        hit = self.bvh.ray_cast(Vector(anchor), d, 1.0)
        if hit[0] is None:
            raise RuntimeError(f'no hit from {anchor} dir {tuple(d)}')
        return np.array(hit[0])

    def j(self, name):
        return np.array(self.J[name])

    def torso(self, z, ang, yc=0.025, x=0.0):
        a = math.radians(ang)
        return self.cast((x, yc, z), (math.sin(a), -math.cos(a), 0.0))

    def limb(self, j0, j1, t, d):
        a = self.j(j0 + '____head' if '____' not in j0 else j0)
        b = self.j(j1 + '____head' if '____' not in j1 else j1)
        c = a + (b - a) * t
        ax = (b - a) / np.linalg.norm(b - a)
        d = np.array(d, float)
        d = d - ax * d.dot(ax)
        return self.cast(c, d)

    def ring(self, j0, j1, t, n=40, start=0.0):
        a = self.j(j0 + '____head'); b = self.j(j1 + '____head')
        c = a + (b - a) * t
        ax = (b - a) / np.linalg.norm(b - a)
        ref = np.array([0, -1.0, 0]) if abs(ax[1]) < 0.8 else np.array([0, 0, 1.0])
        e1 = ref - ax * ref.dot(ax); e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax, e1)
        pts = []
        for k in range(n + 1):
            th = start + 2 * math.pi * k / n
            pts.append(self.cast(c, e1 * math.cos(th) + e2 * math.sin(th)))
        return pts

    def nearest(self, p):
        r = self.bvh.find_nearest(Vector(p))
        return np.array(r[0]), np.array(r[1])

    def densify(self, pts, step=0.002):
        out = [np.array(pts[0])]
        for a, b in zip(pts[:-1], pts[1:]):
            a = np.array(a); b = np.array(b)
            n = max(1, int(np.linalg.norm(b - a) / step))
            for k in range(1, n + 1):
                q = a + (b - a) * k / n
                out.append(q)
        res = np.array([self.nearest(q)[0] for q in out])
        # control points stay fixed; the rest is relaxed along the line and re-snapped,
        # which removes the zig-zag of snapping deep chord points to faceted faces
        fixed = np.zeros(len(res), bool)
        k = 0
        fixed[0] = True
        for a, b in zip(pts[:-1], pts[1:]):
            k += max(1, int(np.linalg.norm(np.array(b) - np.array(a)) / step))
            fixed[k] = True
        for it in range(12):
            sm = res.copy()
            sm[1:-1] = (res[:-2] + 2 * res[1:-1] + res[2:]) / 4
            sm[fixed] = res[fixed]
            res = np.array([self.nearest(q)[0] for q in sm])
        return res


def line_frame(S, pts):
    """per-sample tangent, surface normal, side vector, arc length"""
    t = np.gradient(pts, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    nrm = np.array([S.nearest(p)[1] for p in pts])
    # smooth the surface normal along the line (face normals of the base mesh are faceted)
    k = 9
    pad = np.concatenate([np.repeat(nrm[:1], k, 0), nrm, np.repeat(nrm[-1:], k, 0)], 0)
    cs = np.cumsum(pad, 0)
    nrm = (cs[2 * k:] - np.concatenate([np.zeros((1, 3)), cs[:-2 * k - 1]], 0))[:len(nrm)]
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    side = np.cross(t, nrm)
    side /= np.maximum(np.linalg.norm(side, axis=1, keepdims=True), 1e-9)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    return t, nrm, side, s


def mirror_pts(pts):
    a = np.array(pts, float).copy()
    a[:, 0] *= -1
    return a


def design(S):
    """returns (piping lines, seam lines) as lists of dense point arrays (both sides)."""
    J = S.J
    pipe, seam = [], []

    # --- P1: wrist -> outer arm -> shoulder -> scapula -> flank -> outer leg -> ankle
    arm = [
        S.limb('lowerarm02.L', 'wrist.L', 0.75, (0.55, 0.45, 1)),
        S.limb('lowerarm01.L', 'lowerarm02.L', 0.75, (0.6, 0.35, 1)),
        S.limb('lowerarm01.L', 'lowerarm02.L', 0.05, (0.7, 0.4, 1)),
        S.limb('upperarm02.L', 'lowerarm01.L', 0.55, (0.8, 0.15, 1)),
        S.limb('upperarm01.L', 'upperarm02.L', 0.3, (0.6, 0.25, 1)),
        S.limb('shoulder01.L', 'upperarm01.L', 0.45, (0.0, 0.45, 1)),
        S.torso(1.395, 146),
        S.torso(1.255, 162),
        S.torso(1.150, 128),
        S.torso(1.060, 98),
        S.torso(0.985, 94),
    ]
    leg = [
        S.limb('upperleg01.L', 'upperleg02.L', 0.45, (1, 0.05, 0)),
        S.limb('upperleg02.L', 'lowerleg01.L', 0.45, (1, 0.12, 0)),
        S.limb('upperleg02.L', 'lowerleg01.L', 0.97, (1, 0.05, 0)),
        S.limb('lowerleg01.L', 'lowerleg02.L', 0.6, (1, 0.45, 0)),
        S.limb('lowerleg02.L', 'foot.L', 0.88, (1, 0.25, 0)),
    ]
    p1 = S.densify(arm + leg)
    pipe.append(p1)
    # chevron between the shoulder blades
    pipe.append(S.densify([arm[7], S.torso(1.185, 180, x=0.0)]))
    # kite on the sternum (closed)
    kite = [S.cast((x, 0.0, z), (0, -1, 0)) for x, z in
            ((0.0, 1.402), (0.030, 1.352), (0.0, 1.262), (-0.030, 1.352), (0.0, 1.402))]
    kite_line = S.densify(kite)

    # --- stitched seams
    yoke = S.densify([S.torso(1.475, 16), S.limb('clavicle.L', 'shoulder01.L', 0.6, (0, -0.6, 1)),
                      S.limb('upperarm01.L', 'upperarm02.L', 0.25, (0.1, -1, 0.3)),
                      S.torso(1.295, 62)])
    underpec = S.densify([S.torso(1.235, 0), S.torso(1.205, 32), S.torso(1.135, 74), S.torso(1.085, 97)])
    abs_l = S.densify([S.torso(1.205, 32), S.torso(1.10, 30), S.torso(1.00, 22)])
    back_yoke = S.densify([S.torso(1.49, 168), S.torso(1.395, 146)])
    spine = S.densify([S.torso(1.48, 180), S.torso(1.185, 180)])
    spine2 = S.densify([S.torso(1.185, 180), S.torso(0.99, 180)])
    inner_arm = S.densify([S.torso(1.300, 72),
                           S.limb('upperarm02.L', 'lowerarm01.L', 0.2, (-0.7, 0.2, -1)),
                           S.limb('upperarm02.L', 'lowerarm01.L', 0.95, (-0.7, -0.1, -1)),
                           S.limb('lowerarm01.L', 'lowerarm02.L', 0.6, (-0.6, -0.35, -1)),
                           S.limb('lowerarm02.L', 'wrist.L', 0.75, (-0.55, -0.45, -1))])
    inner_leg = S.densify([S.limb('upperleg01.L', 'upperleg02.L', 0.9, (-1, 0.1, 0)),
                           S.limb('upperleg02.L', 'lowerleg01.L', 0.5, (-1, 0.05, 0)),
                           S.limb('upperleg02.L', 'lowerleg01.L', 0.97, (-1, 0.0, 0)),
                           S.limb('lowerleg01.L', 'lowerleg02.L', 0.6, (-1, 0.2, 0)),
                           S.limb('lowerleg02.L', 'foot.L', 0.88, (-1, 0.1, 0))])
    thigh_diag = S.densify([S.torso(0.965, 40), S.limb('upperleg02.L', 'lowerleg01.L', 0.55, (-0.2, -1, 0)),
                            S.limb('upperleg02.L', 'lowerleg01.L', 0.97, (-0.6, -1, 0))])
    rings = [S.densify(S.ring('lowerarm02.L', 'wrist.L', 0.86)),
             S.densify(S.ring('lowerleg02.L', 'foot.L', 0.80))]
    waist = S.densify([S.torso(0.995, a) for a in range(0, 361, 8)])
    L_seams = [yoke, underpec, abs_l, back_yoke, inner_arm, inner_leg, thigh_diag] + rings
    for sm in L_seams:
        seam.append(sm); seam.append(mirror_pts(sm))
    seam += [spine, spine2, waist]
    pipe = [p1, mirror_pts(p1), pipe[1], mirror_pts(pipe[1])]
    return pipe, seam


def _field(P, lines, S, cap=CAP):
    """nearest-line signed distance and arc length for every vertex."""
    n = len(P)
    best = np.full(n, 9.0); sd = np.full(n, cap); sl = np.zeros(n); lid = -np.ones(n, int)
    for li, pts in enumerate(lines):
        t, nrm, side, s = line_frame(S, pts)
        lo = pts.min(0) - 2.5 * cap; hi = pts.max(0) + 2.5 * cap
        idx = np.nonzero(np.all((P > lo) & (P < hi), axis=1))[0]
        if len(idx) == 0:
            continue
        Q = P[idx]
        # nearest sample (dense at 2 mm), then project onto the local segment
        for c0 in range(0, len(idx), 4096):
            q = Q[c0:c0 + 4096]
            d2 = ((q[:, None, :] - pts[None, :, :]) ** 2).sum(-1)
            k = d2.argmin(1)
            dist = np.sqrt(d2[np.arange(len(q)), k])
            vi = idx[c0:c0 + 4096]
            better = dist < best[vi]
            if not better.any():
                continue
            vb = vi[better]; kb = k[better]; qb = q[better]
            sgn = ((qb - pts[kb]) * side[kb]).sum(1)
            # perpendicular distance (removes the 1 mm sampling ripple)
            perp = sgn
            best[vb] = dist[better]
            sd[vb] = np.clip(perp, -cap, cap)
            sl[vb] = s[kb] + ((qb - pts[kb]) * t[kb]).sum(1)
            lid[vb] = li
    # NOTE: the sign is kept far from the line (no reset to +cap) so that no spurious
    # zero crossing appears near the line; shaders mask with the unsigned distance.
    return sd, sl, lid, np.minimum(best, cap)


def edges_of(F):
    E = set()
    for f in F:
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            E.add((min(a, b), max(a, b)))
    return np.array(sorted(E))


def components(nv, E, cut):
    parent = np.arange(nv)
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for (a, b), c in zip(E, cut):
        if c:
            continue
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    return np.array([find(i) for i in range(nv)])


# tone of each panel, chosen by seed points: 1 = dark charcoal panel, 0 = graphite
def tone_seeds(S):
    seeds = []
    def add(p, tone):
        seeds.append((p, tone)); q = np.array(p).copy(); q[0] *= -1; seeds.append((q, tone))
    add(S.torso(1.33, 25), 0)          # chest
    add(S.torso(1.10, 8), 0)           # abs centre
    add(S.torso(1.12, 60), 1)          # side abdomen
    add(S.torso(1.30, 150), 1)         # back below the shoulder line
    add(S.torso(1.45, 140), 0)         # upper back yoke
    add(S.torso(1.08, 150), 1)         # lower back
    add(S.limb('upperarm02.L', 'lowerarm01.L', 0.5, (0, 1, -0.3)), 1)  # posterior arm
    add(S.limb('upperarm02.L', 'lowerarm01.L', 0.5, (0, -1, 0.3)), 0)  # anterior arm
    add(S.limb('upperleg02.L', 'lowerleg01.L', 0.5, (0, 1, 0)), 1)     # back of leg
    add(S.limb('upperleg02.L', 'lowerleg01.L', 0.4, (1, -0.4, 0)), 0)  # outer front thigh
    add(S.limb('upperleg02.L', 'lowerleg01.L', 0.4, (-0.3, -1, 0)), 1)  # inner front thigh
    return seeds


def compute(P, F, J, weights):
    S = Surf(P, F, J)
    pipe, seam = design(S)
    pipe_sd, pipe_s, pipe_id, pipe_d = _field(P, pipe, S)
    seam_sd, seam_s, seam_id, seam_d = _field(P, seam, S)
    tone_sd, inner_f, side_f = tone_field(P, S, pipe, weights, S_faces=[F])
    # palm / finger pad grip zones and soles
    hand_w = sum(weights[n] for n in weights if n.startswith(('finger', 'metacarpal')))
    tips = sum(weights[n] for n in weights if n.endswith(('-3.L', '-3.R')) and n.startswith('finger'))
    nrmv = vertex_normals(P, F)
    dors = {}
    for sd_, sname in ((1, 'L'), (-1, 'R')):
        w = J[f'wrist.{sname}____head']; k1 = J[f'finger2-1.{sname}____head']; k4 = J[f'finger5-1.{sname}____head']
        m = J[f'finger3-1.{sname}____head']
        fw = (m - w) / np.linalg.norm(m - w); ac = k1 - k4
        n = np.cross(fw, ac) if sname == 'L' else np.cross(ac, fw)
        dors[sd_] = n / np.linalg.norm(n)
    dsel = np.where(P[:, 0][:, None] > 0, dors[1][None], dors[-1][None])
    palm = np.clip(-(nrmv * dsel).sum(1) * 2.5, 0, 1) * np.clip(hand_w * 1.5, 0, 1)
    grip = np.clip(np.maximum(palm, np.clip(tips * 1.3, 0, 1)), 0, 1)
    foot = sum(weights[n] for n in weights if n.startswith(('foot', 'toes')))
    sole = np.clip((-nrmv[:, 2] - 0.35) * 3, 0, 1) * (P[:, 2] < 0.045)
    comp = np.zeros(len(P), int)
    # zones from weights (hands / feet)
    hand = np.clip(sum(weights[n] for n in weights if n.startswith(('finger', 'metacarpal', 'wrist'))), 0, 1)
    return dict(pipe_sd=pipe_sd, pipe_s=pipe_s, seam_sd=seam_sd, seam_s=seam_s, tone_sd=tone_sd,
                pipe_d=pipe_d, seam_d=seam_d, inner_f=inner_f, side_f=side_f,
                comp=comp, lines=(pipe, seam), hand=hand, foot=np.clip(foot, 0, 1), grip=grip, sole=sole)


def vertex_normals(P, F):
    N = np.zeros_like(P)
    for f in F:
        f = list(f)
        a, b, c = P[f[0]], P[f[1]], P[f[2]]
        n = np.cross(b - a, c - a)
        if len(f) == 4:
            n = n + np.cross(c - a, P[f[3]] - a)
        N[f] += n
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)


def _angz(P, yc=0.025):
    ang = np.degrees(np.arctan2(P[:, 0], -(P[:, 1] - yc))) % 360.0
    return np.stack([ang, P[:, 2]], 1)


def _inside(poly, pts):
    x, y = pts[:, 0], pts[:, 1]
    ins = np.zeros(len(pts), bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        c = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / ((y2 - y1) + 1e-12) + x1)
        ins ^= c
    return ins


def tone_field(P, S, pipe, weights, S_faces=None):
    """signed distance to the panel boundary, + on the dark (charcoal) side."""
    n = len(P)
    grp = lambda pre: sum(weights[k] for k in weights if k.startswith(pre))
    w_arm = grp(('shoulder01', 'upperarm', 'lowerarm', 'wrist', 'finger', 'metacarpal'))
    w_leg = grp(('upperleg', 'lowerleg', 'foot', 'toes'))
    w_tor = np.clip(1 - w_arm - w_leg, 0, 1)
    region = np.argmax(np.stack([w_tor, w_arm, w_leg], 1), 1)
    out = np.zeros(n)
    inner = np.full(n, -1.0)
    NV_ = vertex_normals(P, S_faces[0]) if S_faces else None
    # limbs: half-space of the main line (front graphite / back charcoal)
    for side, pts in ((1, pipe[0]), (-1, pipe[1])):
        t, nrm, sv, s = line_frame(S, pts)
        idx = np.nonzero((P[:, 0] * side > 0) & (region > 0))[0]
        Q = P[idx]
        for c0 in range(0, len(idx), 4096):
            q = Q[c0:c0 + 4096]
            d2 = ((q[:, None, :] - pts[None, :, :]) ** 2).sum(-1)
            k = d2.argmin(1)
            v = ((q - pts[k]) * sv[k]).sum(1) * side
            r = region[idx[c0:c0 + 4096]]
            out[idx[c0:c0 + 4096]] = np.where(r == 1, v, -v)
            if NV_ is not None:
                inner[idx[c0:c0 + 4096]] = -(NV_[idx[c0:c0 + 4096]] * nrm[k]).sum(1)
    # torso: dark back panel bounded by the scapula chevron, the flank lines and hips
    p1 = pipe[0]
    az = _angz(p1)
    i0 = int(np.argmin(np.linalg.norm(p1 - pipe[2][0], axis=1)))   # inner scapula
    seg = [i for i in range(i0, len(p1)) if p1[i, 2] > 0.80]
    left = az[seg]
    chev = _angz(pipe[2])                      # inner scapula -> spine
    right = left.copy(); right[:, 0] = 360 - right[:, 0]
    poly = np.concatenate([chev[::-1][:-1] * [1, 1] if False else chev[::-1], left,
                           [[left[-1, 0], 0.70], [right[-1, 0], 0.70]], right[::-1],
                           chev * [-1, 1] + [360, 0]], 0)
    # order: spine (top of V) -> left inner scapula ... wait chev[::-1] starts at spine
    tor = np.nonzero(region == 0)[0]
    B = _inside(poly, _angz(P[tor]))
    # distance to the boundary lines (P1 both sides + chevrons)
    lines = [pipe[0], pipe[1], pipe[2], pipe[3]]
    dmin = np.full(len(tor), CAP)
    Q = P[tor]
    for pts in lines:
        for c0 in range(0, len(tor), 4096):
            q = Q[c0:c0 + 4096]
            dd = np.sqrt(((q[:, None, :] - pts[None, :, :]) ** 2).sum(-1)).min(1)
            dmin[c0:c0 + 4096] = np.minimum(dmin[c0:c0 + 4096], dd)
    out[tor] = np.where(B, 1, -1) * dmin
    # torso side panels: a band centred on each flank line below the armpit
    sidef = np.zeros(n)
    azp = _angz(pipe[0])
    sel = (pipe[0][:, 2] > 0.9) & (pipe[0][:, 2] < 1.25) & (np.abs(pipe[0][:, 0]) > 0.08)
    if sel.any():
        zz = azp[sel, 1]; aa = azp[sel, 0]
        o = np.argsort(zz); zz = zz[o]; aa = aa[o]
        Q = _angz(P[tor])
        for sgn in (1, -1):
            a_line = np.interp(Q[:, 1], zz, aa if sgn == 1 else 360 - aa)
            d = np.abs(Q[:, 0] - a_line)
            band = 1 - d / 17.0
            band *= np.clip((1.24 - Q[:, 1]) / 0.03, 0, 1) * np.clip((Q[:, 1] - 0.93) / 0.02, 0, 1)
            sidef[tor] = np.maximum(sidef[tor], band)
    return np.clip(out, -CAP, CAP), np.clip(inner, -1, 1), np.clip(sidef, -1, 1)


def white_field(P, J, weights, p1_left):
    """VESPER v2 colour blocking: signed distance-like field (m), > 0 on the bone-white
    panels: shoulder yoke sweeping to a point at the sternum, a tapering stripe down the
    outside of each arm into white gauntlets, white boots with a diagonal top edge."""
    n = len(P)
    grp = lambda pre: sum(weights[k] for k in weights if k.startswith(pre))
    w_arm = grp(('shoulder01', 'upperarm', 'lowerarm', 'wrist', 'finger', 'metacarpal'))
    w_leg = grp(('upperleg', 'lowerleg', 'foot', 'toes'))
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ax = np.abs(x)
    # --- yoke: V at the front pointing to the sternum, shallower V at the back
    zf = 1.300 + 0.95 * ax
    zb = 1.352 + 0.55 * ax
    sb = np.clip((y - 0.0) / 0.10, 0, 1)
    sb = sb * sb * (3 - 2 * sb)
    zy = zf * (1 - sb) + zb * sb
    f_yoke = (z - zy) * (0.72 * (1 - sb) + 0.87 * sb)
    out = f_yoke.copy()
    # --- arms: stripe along the outer line, tapering, into the gauntlet
    for side, pts in ((1, p1_left), (-1, mirror_pts(p1_left))):
        S0 = np.array(J['upperarm01.' + ('L' if side > 0 else 'R') + '____head'])
        W0 = np.array(J['wrist.' + ('L' if side > 0 else 'R') + '____head'])
        axv = W0 - S0; La = np.linalg.norm(axv); axv /= La
        tp = ((pts - S0) @ axv) / La
        dax = np.linalg.norm((pts - S0) - np.outer((pts - S0) @ axv, axv), axis=1)
        arm_pts = pts[(tp > -0.25) & (tp < 1.05) & (dax < 0.09)]
        idx = np.nonzero((x * side > 0.06) & (w_arm > 0.3))[0]
        Q = P[idx]
        t = ((Q - S0) @ axv) / La
        d = np.full(len(idx), 1.0)
        for c0 in range(0, len(idx), 4096):
            q = Q[c0:c0 + 4096]
            d[c0:c0 + 4096] = np.sqrt(((q[:, None, :] - arm_pts[None, ::2, :]) ** 2).sum(-1)).min(1)
        w = np.interp(t, [-0.2, 0.0, 0.25, 0.52], [0.075, 0.058, 0.03, 0.013])
        f_stripe = w - d
        f_gaunt = (t - 0.585) * La * 0.9
        f_arm = np.maximum(f_stripe, f_gaunt)
        out[idx] = np.maximum(out[idx], f_arm * np.clip(w_arm[idx] * 2, 0, 1) + out[idx] * (1 - np.clip(w_arm[idx] * 2, 0, 1)))
    # --- boots: diagonal top edge (higher at the front of the shin)
    for side in ('L', 'R'):
        K = np.array(J['lowerleg01.' + side + '____head']); A = np.array(J['foot.' + side + '____head'])
        idx = np.nonzero((np.sign(x) == (1 if side == 'L' else -1)) & (w_leg > 0.4) & (z < 0.6))[0]
        Q = P[idx]
        tt = np.clip((Q[:, 2] - A[2]) / (K[2] - A[2]), 0, 1)
        cy = A[1] + (K[1] - A[1]) * tt
        cx = A[0] + (K[0] - A[0]) * tt
        sgn = 1 if side == 'L' else -1
        zc = 0.305 - 0.75 * (Q[:, 1] - cy) + 0.25 * (Q[:, 0] - cx) * sgn
        f_boot = (zc - Q[:, 2]) * 0.8
        out[idx] = np.maximum(out[idx], f_boot)
    return np.clip(out, -0.08, 0.08)
