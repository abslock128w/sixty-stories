"""Hard parts generated against the rest body: armour plates, wrist launchers, belt."""
import math
import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree


def _edge_params(n, dense=(0.0, 0.006, 0.02, 0.045, 0.08)):
    """0..1 samples, refined near both ends (for rounded edges)."""
    inner = np.linspace(dense[-1], 1 - dense[-1], n)
    return np.unique(np.concatenate([dense, inner, 1 - np.array(dense)]))


def round_profile(d, H, R):
    x = np.clip(d / R, 0, 1)
    return H * np.sqrt(1 - (1 - x) ** 2)


class Shaper:
    def __init__(self, P, F, J):
        self.bvh = BVHTree.FromPolygons([tuple(p) for p in P], [tuple(f) for f in F])
        self.J = J

    def j(self, n):
        if not isinstance(n, str):
            return np.array(n, float)
        return np.array(self.J[n + '____head'] if '____' not in n else self.J[n])

    def cast(self, o, d):
        hit = self.bvh.ray_cast(Vector(o), Vector(d), 0.5)
        if hit[0] is None:
            return None
        return np.array(hit[0])

    def plate(self, a, b, t0, t1, center_dir, half, H=0.004, base=0.0015, R=0.003, wrap=False,
              nt=36, na=36, axis_shift=(0, 0, 0), sink=0.0025, smooth_iters=6):
        """surface-conforming plate.  half(t) -> half angular width (radians)."""
        A = self.j(a); B = self.j(b)
        ax = (B - A) / np.linalg.norm(B - A)
        L = np.linalg.norm(B - A) * (t1 - t0)
        e1 = np.array(center_dir, float); e1 -= ax * e1.dot(ax); e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax, e1)
        ts = _edge_params(nt)
        if wrap:
            ss = np.linspace(0, 1, na, endpoint=False)
        else:
            ss = _edge_params(na)
        NT, NA = len(ts), len(ss)
        top = np.zeros((NT, NA, 3)); low = np.zeros((NT, NA, 3))
        Cc = np.zeros((NT, NA, 3)); Dd = np.zeros((NT, NA, 3)); Rr = np.zeros((NT, NA)); DD = np.zeros((NT, NA))
        for i, tt in enumerate(ts):
            t = t0 + (t1 - t0) * tt
            c = A + (B - A) * t + np.array(axis_shift)
            hw = half(tt) if not wrap else math.pi
            for j_, s in enumerate(ss):
                phi = (-hw + 2 * hw * s) if not wrap else 2 * math.pi * s
                d = e1 * math.cos(phi) + e2 * math.sin(phi)
                p = self.cast(c, d)
                if p is None:
                    p = c + d * 0.05
                r = np.linalg.norm(p - c)
                dt = min(tt, 1 - tt) * L
                da = (min(s, 1 - s) * 2 * hw * r) if not wrap else 1.0
                Cc[i, j_] = c; Dd[i, j_] = d; Rr[i, j_] = r; DD[i, j_] = min(dt, da)
        # smooth the sampled radius (base mesh is faceted)
        for it in range(smooth_iters):
            P_ = np.pad(Rr, ((1, 1), (0, 0)), mode='edge')
            P_ = np.pad(P_, ((0, 0), (1, 1)), mode='wrap' if wrap else 'edge')
            Rr = 0.5 * Rr + 0.125 * (P_[:-2, 1:-1] + P_[2:, 1:-1] + P_[1:-1, :-2] + P_[1:-1, 2:])
        prof = round_profile(DD, H, R)
        top = Cc + Dd * (Rr + base + prof)[..., None]
        low = Cc + Dd * (Rr + base - sink)[..., None]
        return self._mesh_from(top, low, wrap)

    def _mesh_from(self, top, low, wrap):
        NT, NA, _ = top.shape
        V = []
        idx = {}
        def add(p):
            V.append(tuple(p)); return len(V) - 1
        T = [[add(top[i, j]) for j in range(NA)] for i in range(NT)]
        F = []
        jr = range(NA) if wrap else range(NA - 1)
        for i in range(NT - 1):
            for j in jr:
                j2 = (j + 1) % NA
                F.append((T[i][j], T[i + 1][j], T[i + 1][j2], T[i][j2]))
        # skirt along the outline
        if wrap:
            loops = [[(0, j) for j in range(NA)] + [(0, 0)], [(NT - 1, j) for j in range(NA)][::-1] + [(NT - 1, NA - 1)]]
        else:
            ring = [(0, j) for j in range(NA)] + [(i, NA - 1) for i in range(1, NT)] + \
                   [(NT - 1, j) for j in range(NA - 2, -1, -1)] + [(i, 0) for i in range(NT - 2, -1, -1)]
            loops = [ring]
        for lp in loops:
            Lw = [add(low[i, j]) for (i, j) in lp]
            for k in range(len(lp) - 1):
                a = T[lp[k][0]][lp[k][1]]; b = T[lp[k + 1][0]][lp[k + 1][1]]
                F.append((b, a, Lw[k], Lw[k + 1]))
        return np.array(V), F


def mesh_object(name, V, F, mats=(), smooth=True, mat_idx=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in V], [], [tuple(f) for f in F])
    me.validate()
    me.update()
    # consistent outward normals
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    for m in mats:
        me.materials.append(m)
    if mat_idx is not None:
        me.polygons.foreach_set('material_index', mat_idx)
    a = me.attributes.new('prest', 'FLOAT_VECTOR', 'POINT')
    co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
    a.data.foreach_set('vector', co)
    ob = bpy.data.objects.new(name, me)
    return ob


def bevel_box(name, size, bevel=0.002, segs=3):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    bmesh.ops.bevel(bm, geom=list(bm.edges) + list(bm.verts), offset=bevel, segments=segs,
                    affect='EDGES', profile=0.5)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def bevel_cyl(name, r, depth, bevel=0.0012, segs=3, verts=32, r2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts,
                          radius1=r, radius2=r2 if r2 else r, depth=depth)
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and
             e.calc_face_angle() > 0.6]
    bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=segs, affect='EDGES', profile=0.5)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def merge_meshes(name, parts):
    """parts: list of (mesh, Matrix, material_index) -> one mesh object data"""
    bm = bmesh.new()
    for me, M, mi in parts:
        tmp = bmesh.new(); tmp.from_mesh(me)
        bmesh.ops.transform(tmp, matrix=M, verts=tmp.verts)
        for f in tmp.faces:
            f.material_index = mi
        me2 = bpy.data.meshes.new('tmp'); tmp.to_mesh(me2); tmp.free()
        bm.from_mesh(me2)
        bpy.data.meshes.remove(me2)
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out); bm.free()
    for p in out.polygons:
        p.use_smooth = True
    return out


def frame_from(origin, y, z_hint):
    y = Vector(y).normalized()
    x = y.cross(Vector(z_hint)).normalized()
    z = x.cross(y).normalized()
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = Vector(origin)
    return M


def torus_mesh(name, R, r, nu=48, nv=16, squash=(1, 1, 1)):
    V, F = [], []
    for i in range(nu):
        a = 2 * math.pi * i / nu
        for j in range(nv):
            b = 2 * math.pi * j / nv
            x = (R + r * math.cos(b)) * math.cos(a)
            y = (R + r * math.cos(b)) * math.sin(a)
            z = r * math.sin(b)
            V.append((x * squash[0], y * squash[1], z * squash[2]))
    for i in range(nu):
        for j in range(nv):
            a = i * nv + j; b = ((i + 1) % nu) * nv + j
            c = ((i + 1) % nu) * nv + (j + 1) % nv; d = i * nv + (j + 1) % nv
            F.append((a, b, c, d))
    me = bpy.data.meshes.new(name)
    me.from_pydata(V, [], F); me.update()
    for p in me.polygons:
        p.use_smooth = True
    return me


def shoe_shell(bvh_obj, heel, toe, nt=44, nphi=56, ncap=10, offset=0.0032, z_collar=0.105, up=(0, 0, 1), ankle=None, welt=0.0042, close=3):
    """Capsule-parameterised envelope of the foot (closing + blur), offset outward.
    Returns verts (rows x cols), a per-vertex 'keep' mask (below the ankle collar) and
    the grid shape.  Toes are swallowed by the envelope -> a clean shoe."""
    H = np.array(heel, float); T = np.array(toe, float)
    ax = (T - H); L = np.linalg.norm(ax); ax /= L
    upv = np.array(up, float); upv -= ax * upv.dot(ax); upv /= np.linalg.norm(upv)
    side = np.cross(ax, upv)
    rows = []
    for k in range(ncap, 0, -1):
        rows.append(('h', k / ncap))
    for i in range(nt + 1):
        rows.append(('m', i / nt))
    for k in range(1, ncap + 1):
        rows.append(('t', k / ncap))
    NR = len(rows)
    O = np.zeros((NR, nphi, 3)); D = np.zeros((NR, nphi, 3)); R = np.zeros((NR, nphi))
    for i, (kind, s) in enumerate(rows):
        for j in range(nphi):
            ph = 2 * math.pi * j / nphi
            rad = upv * math.cos(ph) + side * math.sin(ph)
            if kind == 'm':
                o = H + ax * L * s; d = rad
            elif kind == 'h':
                a = s * math.pi / 2 * 0.98
                o = H; d = rad * math.cos(a) - ax * math.sin(a)
            else:
                a = s * math.pi / 2 * 0.98
                o = T; d = rad * math.cos(a) + ax * math.sin(a)
            hit = bvh_obj.ray_cast(Vector(o), Vector(d), 0.3)
            r = hit[3] if hit[0] is not None else 0.03
            O[i, j] = o; D[i, j] = d; R[i, j] = min(r, 0.075)
    # closing (max then min) + blur, wrap in phi
    def mx(A, w):
        out = A.copy()
        for du in range(-w, w + 1):
            sh = np.roll(A, du, axis=1)
            for dv in range(-w, w + 1):
                s2 = np.concatenate([sh[dv:], np.repeat(sh[-1:], dv, 0)], 0) if dv > 0 else (
                    np.concatenate([np.repeat(sh[:1], -dv, 0), sh[:dv]], 0) if dv < 0 else sh)
                out = np.maximum(out, s2)
        return out
    Rc = -mx(-mx(R, close), close)
    # toe box: one smooth cap over the front third (no individual toes)
    front = np.zeros(NR); front[int(NR * 0.55):] = 1.0
    Rt = mx(Rc, close + 2)
    Rc = Rc * (1 - front[:, None]) + Rt * front[:, None]
    for it in range(8 + 2 * close):
        P_ = np.pad(Rc, ((1, 1), (0, 0)), mode='edge')
        P_ = np.pad(P_, ((0, 0), (1, 1)), mode='wrap')
        Rc = 0.4 * Rc + 0.15 * (P_[:-2, 1:-1] + P_[2:, 1:-1] + P_[1:-1, :-2] + P_[1:-1, 2:])
    V = O + D * (Rc + offset)[..., None]
    # thick sole: a welt that steps out ~4 mm around the bottom 2.4 cm
    zz = V[..., 2]
    wsole = np.clip((0.027 - zz) / 0.004, 0, 1)
    hd = D.copy(); hd[..., 2] = 0
    hn = np.linalg.norm(hd, axis=-1, keepdims=True)
    hd = hd / np.maximum(hn, 1e-6)
    V = V + hd * (welt * wsole)[..., None] * (hn > 0.2)
    if ankle is not None:
        # above the collar the shell dives smoothly into the ankle (hidden inside the leg)
        A = np.array(ankle, float)
        z = V[..., 2]
        w = np.clip((z - (z_collar - 0.004)) / 0.03, 0, 1)
        w = w * w * (3 - 2 * w) * 0.92
        tgt = np.stack([np.full_like(z, A[0]), np.full_like(z, A[1] + 0.01), z], -1)
        V = V * (1 - w[..., None]) + tgt * w[..., None]
    return V, NR, nphi


def shoe_mesh(V, NR, nphi, z_collar):
    """faces for the capsule grid, dropping the ankle opening (z above the collar)."""
    flat = V.reshape(-1, 3)
    F = []
    for i in range(NR - 1):
        for j in range(nphi):
            a = i * nphi + j; b = i * nphi + (j + 1) % nphi
            c = (i + 1) * nphi + (j + 1) % nphi; d = (i + 1) * nphi + j
            if max(flat[a][2], flat[b][2], flat[c][2], flat[d][2]) > z_collar:
                continue
            F.append((a, d, c, b))
    used = sorted({v for f in F for v in f})
    remap = {v: k for k, v in enumerate(used)}
    return flat[used], [tuple(remap[v] for v in f) for f in F]


def ribbon(surf, ctrl, width=0.032, H=0.0028, base=0.0016, closed=False, step=0.003, lift=None):
    """A strap of real thickness laid along a surface path.
    surf: suit_fields.Surf; ctrl: control points on the surface.  Returns verts, faces,
    per-vertex (across -1..1, along metres) for the stitch shader."""
    import suit_fields as SF
    pts = surf.densify(ctrl, step=step)
    if closed and np.linalg.norm(pts[0] - pts[-1]) < 1e-6:
        pts = pts[:-1]
    t, nrm, side, s = SF.line_frame(surf, pts)
    if closed:
        t = np.roll(pts, -1, 0) - np.roll(pts, 1, 0)
        t /= np.linalg.norm(t, axis=1, keepdims=True)
        side = np.cross(t, nrm); side /= np.linalg.norm(side, axis=1, keepdims=True)
    # cross-section (across, height): rounded rectangle, sunk slightly into the body
    sec = [(-1.0, -0.6), (-1.0, 0.55), (-0.96, 0.9), (-0.85, 1.0), (0.85, 1.0), (0.96, 0.9),
           (1.0, 0.55), (1.0, -0.6)]
    V, UVa = [], []
    n = len(pts)
    lifts = np.zeros(n) if lift is None else lift(s)
    for i in range(n):
        for a, h in sec:
            p = pts[i] + side[i] * a * width / 2 + nrm[i] * (base + lifts[i] + h * H)
            V.append(p); UVa.append((a, s[i]))
    m = len(sec)
    F = []
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        i2 = (i + 1) % n
        for k in range(m - 1):
            F.append((i * m + k, i * m + k + 1, i2 * m + k + 1, i2 * m + k))
    if not closed:
        for i, rev in ((0, True), (n - 1, False)):
            ring = [i * m + k for k in range(m)]
            F.append(tuple(ring[::-1] if rev else ring))
    return np.array(V), F, np.array(UVa)


def tube_along(pts, normals, radius, lift=0.0, nsides=10, caps=True):
    """round tube following a polyline, raised along per-point normals by lift+radius*0.6"""
    pts = np.asarray(pts, float); normals = np.asarray(normals, float)
    t = np.gradient(pts, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    V, F = [], []
    n = len(pts)
    for i in range(n):
        nr = normals[i] - t[i] * normals[i].dot(t[i]); nr /= max(np.linalg.norm(nr), 1e-9)
        bn = np.cross(t[i], nr)
        c = pts[i] + nr * (lift + radius * 0.6)
        for k in range(nsides):
            a = 2 * math.pi * k / nsides
            V.append(c + radius * (nr * math.cos(a) + bn * math.sin(a)))
    for i in range(n - 1):
        for k in range(nsides):
            a = i * nsides + k; b = i * nsides + (k + 1) % nsides
            F.append((a, b, b + nsides, a + nsides))
    if caps:
        F.append(tuple(range(nsides))[::-1])
        F.append(tuple(range((n - 1) * nsides, n * nsides)))
    return np.array(V), F


def surf_line(surf, ctrl, step=0.003):
    """densified surface polyline + smoothed surface normals"""
    import suit_fields as SF
    pts = surf.densify(ctrl, step=step)
    t, nrm, side, s = SF.line_frame(surf, pts)
    return pts, nrm


def star_mesh(name, r=0.0065, h=0.004):
    """small faceted stud: an 8-point star cushion (two-level pyramid)"""
    V = [(0, 0, h)]
    for k in range(16):
        a = 2 * math.pi * k / 16
        rr = r if k % 2 == 0 else r * 0.55
        V.append((rr * math.cos(a), rr * math.sin(a), h * 0.35))
    for k in range(16):
        a = 2 * math.pi * k / 16
        rr = (r if k % 2 == 0 else r * 0.55) * 1.05
        V.append((rr * math.cos(a), rr * math.sin(a), -0.001))
    F = [(0, 1 + k, 1 + (k + 1) % 16) for k in range(16)]
    for k in range(16):
        F.append((1 + k, 17 + k, 17 + (k + 1) % 16, 1 + (k + 1) % 16))
    me = bpy.data.meshes.new(name)
    me.from_pydata(V, [], F); me.update()
    for p in me.polygons:
        p.use_smooth = False
    return me
