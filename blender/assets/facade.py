"""Sixty Stories - HERO ASSET B: pre-war New-York-style mixed-use brick facade section.

Usage (any bpy session):
    import sys; sys.path.insert(0, "/home/user/sixty/blender/assets")
    import facade
    col = facade.build()                                  # default hero variant
    col = facade.build(dict(bays=3, storeys=4, brick='buff', shop='hardware', seed=7))

build(variant) returns a collection named ASSET_facade (or variant['name']) holding every
object of the asset.  Origin = ground-floor front-left corner, facade faces -Y, Z up,
metres.  The building body extends into +Y; a return wall of `ret` metres runs along +Y on
the right-hand corner (x = width).  Every mesh is built in asset space with its object at
the collection origin, so the asset can be instanced (collection instance) anywhere and
the coordinate-driven shaders (brick field, weathering map) stay locked to the building.

Variant keys (all optional): bays (int, 3 m each), storeys (upper floors), brick
('red'|'brown'|'buff'|'dark' or list of sRGB tuples), trim ('black'|'green'|'oxblood'|
'cream'), shop ('bakery'|'hardware'|'deli'), shop_name, number, seed, fire_escape_bay,
balcony (bay, floor), ac (bay, floor), ret (return length), interiors_lit (0..1 fraction).

Brickwork: real geometry bricks (215x65 mm faces, 10 mm recessed mortar, running bond,
per-brick offset / depth / tilt jitter) on the two lowest brick storeys, on the return,
and within ~0.45 m of every upper opening (jambs, jack arches). The rest of the wall
field is a coordinate-driven brick shader that uses the same coursing and the same
per-brick colour function (white noise of the brick cell id), so geometry bricks and
shaded bricks are the same bricks; a per-cell mask image turns the shader into plain
recessed mortar wherever a geometry brick sits in front of it.  The change of technique
happens behind a stone belt course.
"""
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = "/home/user/sixty"

# ----------------------------------------------------------------------------- constants
CH = 0.075           # brick course height (65 brick + 10 mortar)
CL = 0.225           # brick module length (215 + 10)
MORT = 0.005         # half mortar joint
BRICK_PROUD = 0.006  # brick face in front of mortar plane (lightly struck joints, weathered back)

PALETTES = {  # sRGB 0..255; several bricks per palette, the last one is a rare clinker
    'red':   [(120, 54, 40), (106, 48, 36), (132, 62, 46), (114, 60, 46), (98, 44, 34), (128, 72, 54), (110, 52, 42), (72, 38, 32)],
    'brown': [(112, 62, 44), (98, 54, 40), (126, 72, 52), (106, 66, 50), (90, 48, 36), (134, 84, 62), (64, 40, 32)],
    'buff':  [(190, 160, 120), (176, 146, 108), (198, 172, 134), (168, 140, 106), (184, 150, 112), (204, 182, 146), (130, 104, 80)],
    'dark':  [(84, 52, 46), (72, 46, 42), (96, 60, 52), (80, 56, 50), (66, 42, 38), (104, 70, 60), (46, 34, 32)],
}
TRIMS = {  # window/shopfront paint, sRGB
    'black': (26, 27, 26), 'green': (28, 52, 40), 'oxblood': (78, 24, 22), 'cream': (214, 204, 182),
}
SHOPS = {
    'bakery':   dict(name="HALVERSEN BROS. BAKERY", sub="BREAD  -  PASTRY  -  SINCE 1921", sign_col=(28, 40, 34), letter='gold',
                     awning=(122, 30, 28), blade="BAKERY"),
    'hardware': dict(name="KOVAC HARDWARE & PAINT", sub="KEYS CUT  -  TOOLS  -  SUPPLY", sign_col=(24, 30, 52), letter='cream',
                     awning=(30, 64, 46), blade="HARDWARE"),
    'deli':     dict(name="ORLOWSKI DELICATESSEN", sub="SANDWICHES  -  COFFEE  -  GROCERY", sign_col=(70, 20, 22), letter='gold',
                     awning=(26, 40, 70), blade="DELI"),
}
GOODS = [(0.32, 0.20, 0.10), (0.75, 0.72, 0.66), (0.45, 0.06, 0.05), (0.05, 0.08, 0.18), (0.62, 0.52, 0.34), (0.20, 0.24, 0.12),
         (0.55, 0.40, 0.08), (0.04, 0.04, 0.04), (0.40, 0.30, 0.22), (0.70, 0.62, 0.48), (0.10, 0.22, 0.20), (0.58, 0.20, 0.08)]
FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_SANS = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def srgb(c):
    def f(x):
        x = x / 255.0
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return (f(c[0]), f(c[1]), f(c[2]), 1.0)


# ============================================================================ mesh builder
class MB:
    """Accumulates verts/faces in asset space; one MB -> one object."""

    def __init__(self, name):
        self.name = name
        self.v = []
        self.f = []
        self.fm = []
        self.mats = []
        self.cell = []       # per-face float3 attribute (brick id / product colour)
        self.closed = True

    def mat(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def add_v(self, p):
        self.v.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.v) - 1

    def face(self, idx, m, cell=(0.0, 0.0, 0.0)):
        self.f.append(tuple(idx))
        self.fm.append(self.mat(m))
        self.cell.append(cell)

    def quad(self, pts, m, cell=(0, 0, 0)):
        i = [self.add_v(p) for p in pts]
        self.face(i, m, cell)

    def box(self, mn, mx, m, cell=(0, 0, 0)):
        x0, y0, z0 = mn
        x1, y1, z1 = mx
        P = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        b = len(self.v)
        for p in P:
            self.add_v(p)
        for q in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
            self.face([b + k for k in q], m, cell)

    def obox(self, c, ax, ay, az, m, cell=(0, 0, 0)):
        """Oriented box: centre c, half-axis vectors ax, ay, az (right-handed)."""
        c, ax, ay, az = Vector(c), Vector(ax), Vector(ay), Vector(az)
        b = len(self.v)
        for sz in (-1, 1):
            for sy, sx in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
                self.add_v(c + ax * sx + ay * sy + az * sz)
        for q in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
            self.face([b + k for k in q], m, cell)

    def bar(self, p0, p1, w, h, m, up=(0, 0, 1), cell=(0, 0, 0)):
        """Rectangular bar from p0 to p1, width w (side) and height h (along 'up')."""
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        L = d.length
        if L < 1e-6:
            return
        a = d / L
        u = Vector(up)
        if abs(a.dot(u)) > 0.95:
            u = Vector((1, 0, 0)) if abs(a.x) < 0.9 else Vector((0, 1, 0))
        s = a.cross(u).normalized()
        u = s.cross(a).normalized()
        self.obox((p0 + p1) / 2, s * (w / 2), u * (h / 2), a * (L / 2), m, cell)

    def rod(self, p0, p1, r, m, seg=8, caps=True, r1=None, cell=(0, 0, 0)):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        L = d.length
        if L < 1e-6:
            return
        a = d / L
        t = Vector((0, 0, 1)) if abs(a.z) < 0.9 else Vector((1, 0, 0))
        s = a.cross(t).normalized()
        u = s.cross(a).normalized()
        r1 = r if r1 is None else r1
        b = len(self.v)
        for k in range(seg):
            ang = 2 * math.pi * k / seg
            off = s * math.cos(ang) + u * math.sin(ang)
            self.add_v(p0 + off * r)
            self.add_v(p1 + off * r1)
        for k in range(seg):
            k2 = (k + 1) % seg
            self.face([b + 2 * k, b + 2 * k2, b + 2 * k2 + 1, b + 2 * k + 1], m, cell)
        if caps:
            self.face([b + 2 * k for k in range(seg)][::-1], m, cell)
            self.face([b + 2 * k + 1 for k in range(seg)], m, cell)

    def tube(self, pts, r, m, seg=8, cell=(0, 0, 0)):
        """Polyline tube with mitred joints (rings at every point)."""
        P = [Vector(p) for p in pts]
        n = len(P)
        rings = []
        prev_s = None
        for i in range(n):
            if i == 0:
                t = (P[1] - P[0]).normalized()
            elif i == n - 1:
                t = (P[-1] - P[-2]).normalized()
            else:
                t = ((P[i] - P[i - 1]).normalized() + (P[i + 1] - P[i]).normalized()).normalized()
            if prev_s is None:
                ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
                s = t.cross(ref).normalized()
            else:
                s = (prev_s - t * prev_s.dot(t)).normalized()
            u = t.cross(s).normalized()
            prev_s = s
            scale = 1.0
            if 0 < i < n - 1:
                d0 = (P[i] - P[i - 1]).normalized()
                scale = 1.0 / max(0.5, d0.dot(t))
            ring = []
            for k in range(seg):
                ang = 2 * math.pi * k / seg
                off = s * math.cos(ang) + u * math.sin(ang)
                # stretch only the component in the bend plane
                ring.append(self.add_v(P[i] + off * r))
            rings.append(ring)
        for i in range(n - 1):
            a, b = rings[i], rings[i + 1]
            for k in range(seg):
                k2 = (k + 1) % seg
                self.face([a[k], a[k2], b[k2], b[k]], m, cell)
        self.face(rings[0][::-1], m, cell)
        self.face(rings[-1], m, cell)

    def prism(self, poly, ext, m, cell=(0, 0, 0)):
        """Planar polygon (3D points, CCW seen from -ext side... any) extruded by vector ext."""
        ext = Vector(ext)
        n = len(poly)
        b = len(self.v)
        for p in poly:
            self.add_v(p)
        for p in poly:
            self.add_v(Vector(p) + ext)
        self.face([b + k for k in range(n)][::-1], m, cell)
        self.face([b + n + k for k in range(n)], m, cell)
        for k in range(n):
            k2 = (k + 1) % n
            self.face([b + k, b + k2, b + n + k2, b + n + k], m, cell)

    def sweep(self, profile, path, m, closed_ends=True, cell=(0, 0, 0)):
        """Sweep 2D profile [(o, z)] (o = outward offset, z = height) along an XY polyline.
        Outward normal of a segment with direction t is (t.y, -t.x, 0)."""
        P = [Vector((p[0], p[1], 0)) for p in path]
        n = len(P)
        rings = []
        for i in range(n):
            if i == 0:
                t = (P[1] - P[0]).normalized()
                nv = Vector((t.y, -t.x, 0))
                sc = 1.0
            elif i == n - 1:
                t = (P[-1] - P[-2]).normalized()
                nv = Vector((t.y, -t.x, 0))
                sc = 1.0
            else:
                t0 = (P[i] - P[i - 1]).normalized()
                t1 = (P[i + 1] - P[i]).normalized()
                n0 = Vector((t0.y, -t0.x, 0))
                n1 = Vector((t1.y, -t1.x, 0))
                nv = (n0 + n1).normalized()
                sc = 1.0 / max(0.3, nv.dot(n0))
            ring = [self.add_v(P[i] + nv * (o * sc) + Vector((0, 0, z))) for (o, z) in profile]
            rings.append(ring)
        k = len(profile)
        for i in range(n - 1):
            a, b = rings[i], rings[i + 1]
            for j in range(k - 1):
                self.face([a[j], b[j], b[j + 1], a[j + 1]], m, cell)
        if closed_ends:
            self.face(rings[0], m, cell)
            self.face(rings[-1][::-1], m, cell)


def _box_uv(me):
    """World-scale box projection UVs (1 UV unit = 1 m)."""
    nv = len(me.vertices)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    npoly = len(me.polygons)
    nrm = np.empty(npoly * 3, np.float32)
    me.polygons.foreach_get('normal', nrm)
    nrm = np.abs(nrm.reshape(-1, 3))
    ls = np.empty(npoly, np.int32)
    lt = np.empty(npoly, np.int32)
    me.polygons.foreach_get('loop_start', ls)
    me.polygons.foreach_get('loop_total', lt)
    nl = len(me.loops)
    lv = np.empty(nl, np.int32)
    me.loops.foreach_get('vertex_index', lv)
    poly_of_loop = np.repeat(np.arange(npoly), lt)
    ax = np.argmax(nrm, axis=1)[poly_of_loop]
    c = co[lv]
    uv = np.where(ax[:, None] == 0, c[:, [1, 2]], np.where(ax[:, None] == 1, c[:, [0, 2]], c[:, [0, 1]]))
    lay = me.uv_layers.new(name="UVMap")
    lay.data.foreach_set('uv', uv.astype(np.float32).ravel())


def finalize(mb, col, materials, smooth=False, bevel=0.0, bevel_seg=2, recalc=True):
    if not mb.f:
        return None
    me = bpy.data.meshes.new(mb.name)
    me.from_pydata(mb.v, [], mb.f)
    me.validate(clean_customdata=False)
    if recalc or smooth:
        bm = bmesh.new()
        bm.from_mesh(me)
        if recalc:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        if smooth:
            for f in bm.faces:
                f.smooth = True
            for e in bm.edges:
                if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(40):
                    e.smooth = False
        bm.to_mesh(me)
        bm.free()
    for m in mb.mats:
        me.materials.append(materials[m])
    if len(me.polygons) == len(mb.fm):
        me.polygons.foreach_set('material_index', mb.fm)
        if any(c != (0, 0, 0) for c in mb.cell[:2000]) or any(c != (0, 0, 0) for c in mb.cell[-2000:]):
            at = me.attributes.new("cell", 'FLOAT_VECTOR', 'FACE')
            at.data.foreach_set('vector', np.array(mb.cell, np.float32).ravel())
    _box_uv(me)
    ob = bpy.data.objects.new(mb.name, me)
    col.objects.link(ob)
    if bevel > 0:
        md = ob.modifiers.new("Bevel", 'BEVEL')
        md.width = bevel
        md.segments = bevel_seg
        md.limit_method = 'ANGLE'
        md.angle_limit = math.radians(40)
        md.harden_normals = smooth
    return ob


# ============================================================================ node helpers
class NT:
    def __init__(self, tree):
        self.t = tree
        self.N = tree.nodes
        self.L = tree.links

    def n(self, typ, inputs=None, **props):
        nd = self.N.new(typ)
        for k, v in props.items():
            setattr(nd, k, v)
        if inputs:
            for k, v in inputs.items():
                self.set(nd.inputs[k], v)
        return nd

    def set(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.L.new(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=None, c=None, clamp=False):
        nd = self.N.new('ShaderNodeMath')
        nd.operation = op
        nd.use_clamp = clamp
        self.set(nd.inputs[0], a)
        if b is not None:
            self.set(nd.inputs[1], b)
        if c is not None:
            self.set(nd.inputs[2], c)
        return nd.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        nd = self.N.new('ShaderNodeVectorMath')
        nd.operation = op
        self.set(nd.inputs[0], a)
        if b is not None:
            self.set(nd.inputs[1], b)
        if scale is not None:
            self.set(nd.inputs['Scale'], scale)
        return nd.outputs[1] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else nd.outputs[0]

    def mix(self, f, a, b):
        nd = self.N.new('ShaderNodeMix')
        nd.data_type = 'RGBA'
        self.set(nd.inputs[0], f)
        self.set(nd.inputs[6], a)
        self.set(nd.inputs[7], b)
        return nd.outputs[2]

    def mixf(self, f, a, b):
        nd = self.N.new('ShaderNodeMix')
        nd.data_type = 'FLOAT'
        self.set(nd.inputs[0], f)
        self.set(nd.inputs[2], a)
        self.set(nd.inputs[3], b)
        return nd.outputs[0]

    def mul_col(self, a, b):
        nd = self.N.new('ShaderNodeMix')
        nd.data_type = 'RGBA'
        nd.blend_type = 'MULTIPLY'
        nd.inputs[0].default_value = 1.0
        self.set(nd.inputs[6], a)
        self.set(nd.inputs[7], b)
        return nd.outputs[2]

    def smooth(self, x, a, b):
        nd = self.N.new('ShaderNodeMapRange')
        nd.interpolation_type = 'SMOOTHSTEP'
        self.set(nd.inputs[0], x)
        nd.inputs[1].default_value = a
        nd.inputs[2].default_value = b
        return nd.outputs[0]

    def remap(self, x, a, b, c, d, clamp=True):
        nd = self.N.new('ShaderNodeMapRange')
        nd.clamp = clamp
        self.set(nd.inputs[0], x)
        nd.inputs[1].default_value = a
        nd.inputs[2].default_value = b
        nd.inputs[3].default_value = c
        nd.inputs[4].default_value = d
        return nd.outputs[0]

    def noise(self, vec, scale, detail=4.0, rough=0.55, dim='3D', w=None, distortion=0.0):
        nd = self.N.new('ShaderNodeTexNoise')
        nd.noise_dimensions = dim
        self.set(nd.inputs['Vector'], vec)
        nd.inputs['Scale'].default_value = scale
        nd.inputs['Detail'].default_value = detail
        nd.inputs['Roughness'].default_value = rough
        nd.inputs['Distortion'].default_value = distortion
        if w is not None:
            self.set(nd.inputs['W'], w)
        return nd

    def xyz(self, v):
        nd = self.N.new('ShaderNodeSeparateXYZ')
        self.set(nd.inputs[0], v)
        return nd.outputs

    def comb(self, x, y, z):
        nd = self.N.new('ShaderNodeCombineXYZ')
        self.set(nd.inputs[0], x)
        self.set(nd.inputs[1], y)
        self.set(nd.inputs[2], z)
        return nd.outputs[0]

    def ramp(self, f, stops, interp='LINEAR'):
        nd = self.N.new('ShaderNodeValToRGB')
        cr = nd.color_ramp
        cr.interpolation = interp
        while len(cr.elements) > 1:
            cr.elements.remove(cr.elements[-1])
        cr.elements[0].position = stops[0][0]
        cr.elements[0].color = stops[0][1]
        for pos, colr in stops[1:]:
            e = cr.elements.new(pos)
            e.color = colr
        self.set(nd.inputs[0], f)
        return nd.outputs[0]

    def bump(self, h, strength=1.0, dist=0.01, normal=None):
        nd = self.N.new('ShaderNodeBump')
        self.set(nd.inputs['Height'], h)
        nd.inputs['Strength'].default_value = strength
        nd.inputs['Distance'].default_value = dist
        if normal is not None:
            self.set(nd.inputs['Normal'], normal)
        return nd.outputs[0]


def new_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    T = NT(nt)
    out = T.n('ShaderNodeOutputMaterial')
    return m, T, out

def tex_image(rel, color=False):
    """Load a texture shipped with the asset (blender/assets/<rel>), shared by every facade instance."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    return img


def principled(T, out, base, rough=0.5, metal=0.0, normal=None, **extra):
    p = T.n('ShaderNodeBsdfPrincipled')
    T.set(p.inputs['Base Color'], base)
    T.set(p.inputs['Roughness'], rough)
    T.set(p.inputs['Metallic'], metal)
    if normal is not None:
        T.set(p.inputs['Normal'], normal)
    for k, v in extra.items():
        T.set(p.inputs[k.replace('_', ' ')], v)
    if out is not None:
        T.L.new(p.outputs[0], out.inputs['Surface'])
    return p


# ============================================================================ weathering map
def _vnoise(rng, shape, cells, octaves=4, persistence=0.55):
    """Smooth value noise in [0,1] on an array of `shape` (rows, cols)."""
    from scipy.ndimage import zoom
    acc = np.zeros(shape, np.float32)
    amp, tot = 1.0, 0.0
    cy, cx = cells
    for o in range(octaves):
        gy, gx = max(2, int(cy * 2 ** o)), max(2, int(cx * 2 ** o))
        g = rng.random((gy + 1, gx + 1)).astype(np.float32)
        z = zoom(g, (shape[0] / (gy + 1), shape[1] / (gx + 1)), order=3)[:shape[0], :shape[1]]
        if z.shape != shape:
            z = np.pad(z, ((0, shape[0] - z.shape[0]), (0, shape[1] - z.shape[1])), mode='edge')
        acc += amp * z
        tot += amp
        amp *= persistence
    acc /= tot
    acc = np.nan_to_num(acc)
    return np.clip((acc - acc.min()) / max(1e-6, float(acc.max() - acc.min())), 0, 1)


class Weather:
    """Painter for the facade weathering map: channels soot, streak, efflorescence, rust.
    Map space: u (facade metres, front then return) x v (height)."""
    RES = 0.01

    def __init__(self, U, V, seed):
        self.U, self.V = U, V
        self.nx = int(math.ceil(U / self.RES)) + 1
        self.ny = int(math.ceil(V / self.RES)) + 1
        self.ch = np.zeros((4, self.ny, self.nx), np.float32)
        self.rng = np.random.default_rng(seed)

    def _ix(self, u):
        return int(np.clip(round(u / self.RES), 0, self.nx - 1))

    def _iy(self, v):
        return int(np.clip(round(v / self.RES), 0, self.ny - 1))

    def drip(self, ch, u0, u1, v_top, length, strength, density=1.0, width=(0.006, 0.03)):
        """Rain / rust streaks hanging below a ledge from u0..u1 starting at v_top."""
        rng = self.rng
        n = max(2, int((u1 - u0) / 0.035 * density))
        for _ in range(n):
            u = rng.uniform(u0, u1)
            L = length * rng.uniform(0.35, 1.0)
            w = rng.uniform(*width)
            s = strength * rng.uniform(0.3, 1.0)
            ia, ib = self._ix(u - w * 2), self._ix(u + w * 2) + 1
            ja, jb = self._iy(v_top - L), self._iy(v_top) + 1
            if ib <= ia or jb <= ja:
                continue
            uu = np.arange(ia, ib) * self.RES
            vv = np.arange(ja, jb) * self.RES
            prof_u = np.exp(-((uu - u) / w) ** 2)
            t = np.clip((v_top - vv) / L, 0, 1)
            prof_v = (1 - t) ** 1.6 * np.clip(t * 12, 0, 1)
            wob = 1.0 + 0.4 * np.sin(vv * rng.uniform(8, 20) + rng.uniform(0, 6))
            self.ch[ch, ja:jb, ia:ib] = np.maximum(self.ch[ch, ja:jb, ia:ib], s * prof_v[:, None] * wob[:, None] * prof_u[None, :])

    def blob(self, ch, u, v, ru, rv, strength, noisy=True):
        ia, ib = self._ix(u - ru * 2), self._ix(u + ru * 2) + 1
        ja, jb = self._iy(v - rv * 2), self._iy(v + rv * 2) + 1
        if ib <= ia or jb <= ja:
            return
        uu = np.arange(ia, ib) * self.RES
        vv = np.arange(ja, jb) * self.RES
        d = ((uu[None, :] - u) / ru) ** 2 + ((vv[:, None] - v) / rv) ** 2
        g = np.exp(-d * 1.5)
        if noisy:
            nz = _vnoise(self.rng, g.shape, (max(2, g.shape[0] // 25), max(2, g.shape[1] // 25)), 3)
            g = np.clip(g * (0.3 + 1.4 * nz) - 0.25, 0, 1)
        self.ch[ch, ja:jb, ia:ib] = np.maximum(self.ch[ch, ja:jb, ia:ib], g * strength)

    def band(self, ch, v0, v1, strength, falloff_up=True, u0=0.0, u1=None):
        u1 = self.U if u1 is None else u1
        ja, jb = self._iy(v0), self._iy(v1) + 1
        ia, ib = self._ix(u0), self._ix(u1) + 1
        vv = np.arange(ja, jb) * self.RES
        t = (vv - v0) / max(1e-6, v1 - v0)
        prof = (1 - t) if falloff_up else t
        self.ch[ch, ja:jb, ia:ib] = np.maximum(self.ch[ch, ja:jb, ia:ib], strength * prof[:, None] ** 1.5)

    def image(self, name):
        rng = self.rng
        # large-scale mottling so nothing is uniform
        mott = _vnoise(rng, (self.ny, self.nx), (self.ny // 300 + 2, self.nx // 300 + 2), 5)
        self.ch[0] = np.clip(self.ch[0] + 0.18 * mott ** 2, 0, 1)
        brk = _vnoise(rng, (self.ny, self.nx), (self.ny // 40 + 2, self.nx // 40 + 2), 3)
        for c in (1, 3):
            self.ch[c] *= (0.55 + 0.9 * brk)
        self.ch[2] *= np.clip(brk * 1.6 - 0.2, 0, 1)
        from scipy.ndimage import gaussian_filter
        self.ch = np.nan_to_num(self.ch, nan=0.0)
        for c in range(4):
            self.ch[c] = gaussian_filter(self.ch[c], 0.8)
        img = bpy.data.images.new(name, self.nx, self.ny, alpha=True, float_buffer=False)
        img.colorspace_settings.name = 'Non-Color'
        px = np.clip(np.stack(self.ch, axis=-1), 0, 1).astype(np.float32)
        img.pixels.foreach_set(px.ravel())
        img.pack()
        return img


# ============================================================================ the builder
class Facade:
    def __init__(self, variant):
        v = dict(bays=4, bay_w=3.0, storeys=5, brick='red', trim='black', shop='bakery', shop_name=None,
                 number="214", seed=11, fire_escape_bay=0, balcony=(2, 2), ac=(3, 3), ret=3.0,
                 interiors_lit=0.45, name="ASSET_facade", corner=True)
        v.update(variant or {})
        self.vt = v
        self.seed = v['seed']
        self.R = random.Random(v['seed'])
        self.bays = int(v['bays'])
        self.bw = float(v['bay_w'])
        self.S = int(v['storeys'])
        self.W = self.bays * self.bw
        self.corner = bool(v['corner'])
        self.RET = float(v['ret']) if self.corner else 0.0
        self.GH = 62 * CH                       # ground floor height 4.65
        self.SH = 44 * CH                       # storey height 3.30
        self.TOPW = self.GH + self.S * self.SH  # top of last storey
        self.ZC = self.TOPW + 0.15              # cornice bottom
        self.ZP = self.ZC + 0.75                # parapet start (cornice top)
        self.ZTOP = self.ZP + 0.75              # parapet top under coping
        self.GEO_TOP = self.GH + 2 * self.SH    # end of full-geometry brick zone (belt course)
        self.shop = SHOPS.get(v['shop'], SHOPS['bakery'])
        self.shop_name = v['shop_name'] or self.shop['name']
        self.mb = {}
        self.openings = []      # dicts: wall, u0,u1,v0,v1, kind
        self.excl = []          # (wall, polygon in (u,v)) brick exclusions (convex)
        self.geo_cells = set()
        self.lights = []
        self.U_TOT = self.W + self.RET
        self.path = [(0, 0), (self.W, 0), (self.W, self.RET)] if self.corner else [(0, 0), (self.W, 0)]
        self.walls = (('F', self.W), ('R', self.RET)) if self.corner else (('F', self.W),)

    # ---------------------------------------------------------------- wall frames
    def wp(self, wall, u, v, d):
        """wall 'F' (front, y=0 plane, outward -Y) or 'R' (return, x=W plane, outward +X)."""
        if wall == 'F':
            return Vector((u, -d, v))
        return Vector((self.W + d, u, v))

    def wvec(self, wall, du, dv, dd):
        if wall == 'F':
            return Vector((du, -dd, dv))
        return Vector((dd, du, dv))

    def uoff(self, wall):
        return 0.0 if wall == 'F' else self.W

    def M(self, key):
        if key not in self.mb:
            self.mb[key] = MB(key)
        return self.mb[key]

    # ---------------------------------------------------------------- layout
    def window_slots(self):
        """Upper-floor windows: (wall, u_center, width, floor k)."""
        slots = []
        for k in range(1, self.S + 1):
            for b in range(self.bays):
                slots.append(('F', (b + 0.5) * self.bw, 1.05, k))
            if self.corner:
                slots.append(('R', self.RET * 0.55, 0.80, k))
        return slots

    def floor_base(self, k):
        return self.GH + (k - 1) * self.SH

    # ---------------------------------------------------------------- build
    def build(self):
        name = self.vt['name']
        old = bpy.data.collections.get(name)
        if old:
            for ob in list(old.all_objects):
                bpy.data.objects.remove(ob, do_unlink=True)
            bpy.data.collections.remove(old)
        self.col = bpy.data.collections.new(name)
        self.weather = Weather(self.U_TOT, self.ZTOP + 0.2, self.seed)
        self.plan_openings()
        self.build_trim_stone()
        self.build_windows()
        self.build_shopfront()
        self.build_cornice()
        self.build_fire_escape()
        self.build_balcony()
        self.build_services()
        self.build_interiors()
        self.build_bricks()
        self.build_wall_planes()
        self.paint_weather()
        self.make_materials()
        self.emit_objects()
        return self.col

    # ---------------------------------------------------------------- openings & stone
    def plan_openings(self):
        for (wall, uc, w, k) in self.window_slots():
            base = self.floor_base(k)
            v0 = base + 11 * CH
            v1 = v0 + 26 * CH
            u0, u1 = uc - w / 2, uc + w / 2
            arch = k <= 2 or k == self.S          # jack arches low and on the top floor; stone lintels between
            self.openings.append(dict(wall=wall, u0=u0, u1=u1, v0=v0, v1=v1, k=k, arch=arch, w=w))
            ex = MORT
            self.excl.append((wall, [(u0 - ex, v0 - 0.10), (u1 + ex, v0 - 0.10), (u1 + ex, v1), (u0 - ex, v1)]))
            if arch:
                e = 0.10 * w / 1.05
                self.excl.append((wall, [(u0 - ex, v1 - 0.001), (u1 + ex, v1 - 0.001), (u1 + e + ex, v1 + 4 * CH + ex), (u0 - e - ex, v1 + 4 * CH + ex)]))
            else:
                self.excl.append((wall, [(u0 - 0.12, v1 - 0.001), (u1 + 0.12, v1 - 0.001), (u1 + 0.12, v1 + 4 * CH + ex), (u0 - 0.12, v1 + 4 * CH + ex)]))
        # quoins on the corner (both faces), belt courses
        W = self.W
        for wall in ('F', 'R'):
            self.excl.append((wall, [(-1, self.GEO_TOP - ex), (self.U_TOT + 1, self.GEO_TOP - ex), (self.U_TOT + 1, self.GEO_TOP + 3 * CH + ex), (-1, self.GEO_TOP + 3 * CH + ex)]))
        z = self.GH
        i = 0
        while self.corner and z < self.ZC - 0.31:
            long_ = (i % 2 == 0)
            lf = 0.46 if long_ else 0.30
            lr = 0.30 if long_ else 0.46
            h = 4 * CH
            if not (self.GEO_TOP - 0.01 < z + h and z < self.GEO_TOP + 3 * CH):
                self.excl.append(('F', [(W - lf - ex, z - ex), (W + 1, z - ex), (W + 1, z + h + ex), (W - lf - ex, z + h + ex)]))
                self.excl.append(('R', [(-1, z - ex), (lr + ex, z - ex), (lr + ex, z + h + ex), (-1, z + h + ex)]))
                self.quoin(z, h, lf, lr)
            z += h
            i += 1
        # vent grille between bays on floor 2
        self.vent = ('F', self.bw * 2, self.floor_base(1) + 20 * CH, 0.45, 0.30)
        wall, uc, vc, w, h = self.vent
        self.excl.append((wall, [(uc - w / 2 - ex, vc - ex), (uc + w / 2 + ex, vc - ex), (uc + w / 2 + ex, vc + h + ex), (uc - w / 2 - ex, vc + h + ex)]))

    def quoin(self, z, h, lf, lr):
        mb = self.M('stone')
        W = self.W
        g = 0.006   # joint
        d = 0.025
        # L-shaped stone: two boxes, front face proud by d
        mb.box((W - lf + g, -d, z + g), (W + d, 0.12, z + h - g), 'stone')
        mb.box((W - 0.12, 0.12, z + g), (W + d, lr - g, z + h - g), 'stone')

    def build_trim_stone(self):
        mb = self.M('stone')
        W, R = self.W, self.RET
        # belt course at the change of brick technique, profiled, wraps the corner
        z0 = self.GEO_TOP
        prof = [(0.0, z0), (0.07, z0), (0.07, z0 + 0.03), (0.05, z0 + 0.05), (0.05, z0 + 0.19), (0.075, z0 + 0.20), (0.075, z0 + 3 * CH - 0.02), (0.06, z0 + 3 * CH), (0.0, z0 + 3 * CH)]
        mb.sweep(prof, self.path, 'stone')
        # window sills and lintels
        for op in self.openings:
            wall, u0, u1, v0, v1 = op['wall'], op['u0'], op['u1'], op['v0'], op['v1']
            ext = 0.09
            # sill profile (d outward, v): drip groove underneath, weathered top sloping outward
            sp = [(-0.12, v0 - 0.10), (0.055, v0 - 0.10), (0.055, v0 - 0.085), (0.040, v0 - 0.085), (0.040, v0 - 0.078),
                  (0.065, v0 - 0.078), (0.068, v0 - 0.035), (0.060, v0 - 0.028), (-0.02, v0 - 0.005), (-0.12, v0 - 0.005)]
            poly = [self.wp(wall, u0 - ext, vv, dd) for (dd, vv) in sp]
            mb.prism(poly, self.wvec(wall, (u1 - u0) + 2 * ext, 0, 0), 'stone')
            if not op['arch']:
                # flat stone lintel with ears and a slight projecting fillet
                e = 0.12
                mb.box(*self._wbox(wall, u0 - e, u1 + e, v1, v1 + 4 * CH - 0.008, -0.08, 0.018), 'stone')
                mb.box(*self._wbox(wall, u0 - e - 0.02, u1 + e + 0.02, v1 + 4 * CH - 0.06, v1 + 4 * CH - 0.008, -0.08, 0.035), 'stone')
        # parapet coping
        mb.sweep([(-0.40, self.ZTOP), (0.05, self.ZTOP), (0.05, self.ZTOP + 0.09), (0.0, self.ZTOP + 0.11), (-0.40, self.ZTOP + 0.11)],
                 self.path, 'stone')
        # parapet back face (hidden from the street but closes the silhouette)
        self.M('brickback').box((0, 0.30, self.ZP), (W - 0.3, 0.36, self.ZTOP), 'mortar')

    def _wbox(self, wall, u0, u1, v0, v1, din, dout):
        """Box in wall space: u0..u1, v0..v1, depth from din (inside, negative) to dout (proud)."""
        a = self.wp(wall, u0, v0, din)
        b = self.wp(wall, u1, v1, dout)
        mn = (min(a.x, b.x), min(a.y, b.y), min(a.z, b.z))
        mx = (max(a.x, b.x), max(a.y, b.y), max(a.z, b.z))
        return mn, mx

    # ---------------------------------------------------------------- windows
    def build_windows(self):
        R = self.R
        trim = self.vt['trim']
        for i, op in enumerate(self.openings):
            self.window(op, i)

    def window(self, op, idx):
        R = random.Random(self.seed * 1000 + idx)
        wall, u0, u1, v0, v1 = op['wall'], op['u0'], op['u1'], op['v0'], op['v1']
        fr = self.M('win_frame')
        gl = self.M('glass')
        pu = self.M('putty')
        w = u1 - u0
        h = v1 - v0
        D0 = -0.095      # outer face of the frame (inside the reveal)
        wb = lambda a, b, c, d, e, f, m='paint': fr.box(*self._wbox(wall, a, b, c, d, e, f), m)
        # reveal (plain brick-shaded plaster returns, separate mesh with brick shader w/o mask)
        rv = self.M('reveal')
        din = -0.33
        for (a, b) in ((u0, u0), (u1, u1)):
            pass
        rv.box(*self._wbox(wall, u0 - 0.02, u0, v0 - 0.005, v1, din, 0.0), 'reveal')
        rv.box(*self._wbox(wall, u1, u1 + 0.02, v0 - 0.005, v1, din, 0.0), 'reveal')
        rv.box(*self._wbox(wall, u0 - 0.02, u1 + 0.02, v1, v1 + 0.02, din, 0.0), 'reveal')
        # interior plaster reveal + stool
        rv.box(*self._wbox(wall, u0 - 0.10, u1 + 0.10, v0 - 0.03, v0 + 0.0, din - 0.03, -0.20), 'plaster')
        # box frame: blind stop / casing
        fw = 0.055
        wb(u0, u0 + fw, v0, v1, -0.22, D0)
        wb(u1 - fw, u1, v0, v1, -0.22, D0)
        wb(u0, u1, v1 - fw, v1, -0.22, D0)
        # brick mould: a moulded casing strip at the outer edge of the frame, seen in the reveal
        bm = 0.035
        wb(u0, u0 + bm, v0, v1, D0 - 0.02, D0 + 0.012)
        wb(u1 - bm, u1, v0, v1, D0 - 0.02, D0 + 0.012)
        wb(u0, u1, v1 - bm, v1, D0 - 0.02, D0 + 0.012)
        wb(u0 + bm, u0 + bm + 0.012, v0, v1 - bm, D0 - 0.02, D0 + 0.004)
        wb(u1 - bm - 0.012, u1 - bm, v0, v1 - bm, D0 - 0.02, D0 + 0.004)
        wb(u0 + bm, u1 - bm, v1 - bm - 0.012, v1 - bm, D0 - 0.02, D0 + 0.004)
        # wooden sub-sill sloping (simple)
        wb(u0, u1, v0, v0 + 0.035, -0.22, D0 + 0.03)
        # parting bead
        iu0, iu1 = u0 + fw, u1 - fw
        iv0, iv1 = v0 + 0.035, v1 - fw
        mid = (iv0 + iv1) / 2 + R.uniform(-0.02, 0.02)
        open_low = R.random() < 0.18
        raise_amt = R.uniform(0.10, 0.35) if open_low else 0.0
        lower_upper = R.uniform(0.04, 0.18) if (not open_low and R.random() < 0.10) else 0.0
        panes = 2 if (R.random() < 0.35 and w > 0.9) else 1
        sh_h = (iv1 - iv0) / 2 + 0.02
        # upper sash: outer track
        self.sash(wall, iu0, iu1, mid - 0.02 - lower_upper, iv1 - lower_upper, -0.105, -0.150, panes, top=True)
        # lower sash: inner track
        self.sash(wall, iu0, iu1, iv0 + raise_amt, mid + 0.02 + raise_amt, -0.155, -0.200, panes, top=False)
        op['mid'] = mid
        op['open'] = raise_amt

    def sash(self, wall, u0, u1, v0, v1, d0, d1, panes, top):
        fr = self.M('win_frame')
        gl = self.M('glass')
        pu = self.M('putty')
        st = 0.048
        rail_t = 0.05
        rail_b = 0.075 if not top else 0.024     # meeting rails are slim
        rail_tt = 0.024 if not top else 0.05
        b = lambda a, bb, c, dd, m='paint': fr.box(*self._wbox(wall, a, bb, c, dd, d1, d0), m)
        b(u0, u0 + st, v0, v1)
        b(u1 - st, u1, v0, v1)
        b(u0 + st, u1 - st, v0, v0 + rail_b)
        b(u0 + st, u1 - st, v1 - rail_tt, v1)
        gu0, gu1, gv0, gv1 = u0 + st, u1 - st, v0 + rail_b, v1 - rail_tt
        dg = (d0 + d1) / 2
        # stepped sticking on the outside face of the sash (reads as a moulded profile)
        so = 0.010
        for (a, bb, c, dd) in ((gu0 - so, gu0, gv0 - so, gv1 + so), (gu1, gu1 + so, gv0 - so, gv1 + so), (gu0, gu1, gv0 - so, gv0), (gu0, gu1, gv1, gv1 + so)):
            fr.box(*self._wbox(wall, a, bb, c, dd, d0 - 0.002, d0 + 0.006), 'paint')
        cols = [(gu0, gu1)]
        if panes == 2:
            m = (gu0 + gu1) / 2
            b(m - 0.011, m + 0.011, gv0, gv1)
            cols = [(gu0, m - 0.011), (m + 0.011, gu1)]
        for (a, c) in cols:
            p0 = self.wp(wall, a, gv0, dg)
            p1 = self.wp(wall, c, gv0, dg)
            p2 = self.wp(wall, c, gv1, dg)
            p3 = self.wp(wall, a, gv1, dg)
            gl.quad([p0, p1, p2, p3], 'glass')
            # putty bevels on the outside face of the glass (triangular-ish strips)
            pw, pd = 0.010, 0.010
            do = dg + pd
            for (x0, x1, y0, y1) in ((a, c, gv0, gv0 + pw), (a, c, gv1 - pw, gv1), (a, a + pw, gv0, gv1), (c - pw, c, gv0, gv1)):
                pu.box(*self._wbox(wall, x0, x1, y0, y1, dg, do), 'putty')
        gl.closed = False

    # ---------------------------------------------------------------- bricks
    def _clip(self, poly, a, b):
        """Keep the part of convex polygon `poly` on the left of directed line a->b."""
        out = []
        n = len(poly)
        def side(p):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        for i in range(n):
            p, q = poly[i], poly[(i + 1) % n]
            sp, sq = side(p), side(q)
            if sp >= 0:
                out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq)
                out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
        return out

    @staticmethod
    def _area(poly):
        s = 0
        for i in range(len(poly)):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % len(poly)]
            s += x0 * y1 - x1 * y0
        return s / 2

    def _subtract(self, poly, ex):
        """poly minus convex ex: keep the largest one-sided piece (one straight cut)."""
        # quick bbox reject
        pu = [p[0] for p in poly]; pv = [p[1] for p in poly]
        eu = [p[0] for p in ex]; ev = [p[1] for p in ex]
        if max(pu) <= min(eu) or min(pu) >= max(eu) or max(pv) <= min(ev) or min(pv) >= max(ev):
            return poly
        # ex assumed CCW; outside of edge (a->b) = right side -> clip with reversed edge
        best, best_a = None, -1
        inside_all = True
        A0 = abs(self._area(poly))
        for i in range(len(ex)):
            a, b = ex[i], ex[(i + 1) % len(ex)]
            piece = self._clip(poly, b, a)
            if len(piece) >= 3:
                ar = abs(self._area(piece))
                if ar > A0 - 1e-9:
                    return poly           # fully outside this edge
                if ar > best_a:
                    best, best_a = piece, ar
        return best if best_a > 0 else None

    def _brick(self, mb, wall, poly, cell, R, proud=BRICK_PROUD):
        """Chamfered brick slab from a convex 2D polygon in wall (u, v)."""
        n = len(poly)
        if n < 3:
            return
        cu = sum(p[0] for p in poly) / n
        cv = sum(p[1] for p in poly) / n
        # per-brick jitter: in-plane shift, depth, small rotations
        du, dv = R.gauss(0, 0.0012), R.gauss(0, 0.0009)
        dd = R.gauss(0, 0.0014)
        rz = R.gauss(0, 0.004)
        tu, tv = R.gauss(0, 0.012), R.gauss(0, 0.012)   # tilt of the face (rad-ish)
        ch = 0.0026
        def inset(pts, d):
            res = []
            m = len(pts)
            for i in range(m):
                p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % m])
                e0 = (p1 - p0).normalized(); e1 = (p2 - p1).normalized()
                n0 = Vector((-e0.y, e0.x)); n1 = Vector((-e1.y, e1.x))
                bis = (n0 + n1)
                if bis.length < 1e-6:
                    res.append(p1); continue
                bis.normalize()
                k = d / max(0.3, bis.dot(n0))
                res.append(p1 + bis * k)
            return res
        if self._area(poly) < 0:
            poly = poly[::-1]
        P = [Vector(p) for p in poly]
        Pi = inset(P, ch)
        cs, sn = math.cos(rz), math.sin(rz)
        def tr(p, depth):
            x, y = p.x - cu, p.y - cv
            x, y = x * cs - y * sn, x * sn + y * cs
            d = depth + dd + (x * tu + y * tv) * (depth / proud)
            return self.wp(wall, cu + x + du, cv + y + dv, d)
        b = len(mb.v)
        for p in P:
            mb.add_v(tr(p, -0.004))
        for p in P:
            mb.add_v(tr(p, proud - ch))
        for p in Pi:
            mb.add_v(tr(p, proud))
        for k in range(n):
            k2 = (k + 1) % n
            mb.face([b + k, b + k2, b + n + k2, b + n + k], 'brick', cell)
            mb.face([b + n + k, b + n + k2, b + 2 * n + k2, b + 2 * n + k], 'brick', cell)
        mb.face([b + 2 * n + k for k in range(n)], 'brick', cell)

    def build_bricks(self):
        mb = self.M('bricks')
        mb.closed = False
        R = random.Random(self.seed + 5)
        near = 0.45
        upper_ops = [o for o in self.openings if o['v0'] > self.GEO_TOP]
        self.ni = int(math.ceil(self.U_TOT / CL)) + 3
        self.nj = int(math.ceil((self.ZTOP + 0.2) / CH)) + 1
        mask = np.zeros((self.nj, self.ni), np.float32)
        for wall, ub in self.walls:
            ua = 0.0
            off = self.uoff(wall)
            excl = [e[1] for e in self.excl if e[0] == wall]
            ops = [o for o in upper_ops if o['wall'] == wall]
            j0 = int(round(self.GH / CH))
            j1 = int(round(self.ZTOP / CH))
            for j in range(j0, j1):
                v = j * CH
                shift = (j % 2) * CL / 2
                i0 = int(math.floor((off + ua + shift) / CL))
                i1 = int(math.ceil((off + ub + shift) / CL))
                for i in range(i0, i1):
                    gu0 = i * CL - shift          # global u of the cell start
                    lu0, lu1 = gu0 - off, gu0 + CL - off
                    if lu1 <= ua or lu0 >= ub:
                        continue
                    geo = (v < self.GEO_TOP) or wall == 'R' and v < self.GEO_TOP
                    if not geo:
                        for o in ops:
                            if (o['u0'] - near < lu1 and lu0 < o['u1'] + near and o['v0'] - 0.25 < v + CH and v < o['v1'] + 4 * CH + 0.15):
                                geo = True
                                break
                    if not geo:
                        continue
                    poly = [(max(lu0 + MORT, ua), v + MORT), (min(lu1 - MORT, ub), v + MORT), (min(lu1 - MORT, ub), v + CH - MORT), (max(lu0 + MORT, ua), v + CH - MORT)]
                    if poly[1][0] - poly[0][0] < 0.03:
                        continue
                    for ex in excl:
                        if poly is None:
                            break
                        poly = self._subtract(poly, ex)
                    if poly is None or len(poly) < 3 or abs(self._area(poly)) < 0.0012:
                        mask[j, (i % self.ni)] = 1.0 if poly is None else mask[j, (i % self.ni)]
                        continue
                    mask[j, i % self.ni] = 1.0
                    self._brick(mb, wall, poly, (float(i), float(j), 0.0), R)
        # jack arches (voussoirs)
        for oi, op in enumerate(self.openings):
            if op['arch']:
                self.jack_arch(mb, op, oi, R, mask)
        self.mask_img = bpy.data.images.new(self.vt['name'] + "_brickmask", self.ni, self.nj, alpha=False, float_buffer=False)
        self.mask_img.colorspace_settings.name = 'Non-Color'
        px = np.zeros((self.nj, self.ni, 4), np.float32)
        px[..., 0] = mask
        px[..., 3] = 1
        self.mask_img.pixels.foreach_set(px.ravel())
        self.mask_img.pack()
        self.mask_img.use_fake_user = True

    def jack_arch(self, mb, op, oi, R, mask):
        wall, u0, u1, v1 = op['wall'], op['u0'], op['u1'], op['v1']
        w = u1 - u0
        e = 0.10 * w / 1.05
        H = 4 * CH
        uc = (u0 + u1) / 2
        # centre of radiation
        k = H / e
        cz = v1 - k * (uc - u0)
        C = (uc, cz)
        aL = math.atan2(v1 + H - cz, (u0 - e) - uc)
        aR = math.atan2(v1 + H - cz, (u1 + e) - uc)
        n = int(round((w + e) / 0.075))
        if n % 2 == 0:
            n += 1
        def line_hit(ang, off, vz):
            # ray from C at angle ang, shifted perpendicular by off; intersect v = vz
            dx, dz = math.cos(ang), math.sin(ang)
            px, pz = C[0] - dz * off, C[1] + dx * off
            t = (vz - pz) / dz
            return (px + dx * t, vz)
        for s in range(n):
            a0 = aR + (aL - aR) * s / n
            a1 = aR + (aL - aR) * (s + 1) / n
            poly = [line_hit(a0, MORT, v1 + MORT), line_hit(a1, -MORT, v1 + MORT), line_hit(a1, -MORT, v1 + H - MORT), line_hit(a0, MORT, v1 + H - MORT)]
            if s == n // 2 and op['k'] == 1:
                # stone keystone, slightly taller and proud
                kp = [line_hit(a0, MORT, v1 - 0.03), line_hit(a1, -MORT, v1 - 0.03), line_hit(a1, -MORT, v1 + H + 0.06), line_hit(a0, MORT, v1 + H + 0.06)]
                self.M('stone').prism([self.wp(wall, p[0], p[1], -0.06) for p in kp], self.wvec(wall, 0, 0, 0.09), 'stone')
                continue
            self._brick(mb, wall, poly, (5000.0 + oi * 40 + s, 7.0, 0.0), R, proud=BRICK_PROUD + 0.002)
        off = self.uoff(wall)
        j0 = int(round(v1 / CH))
        for j in range(j0, j0 + 4):
            shift = (j % 2) * CL / 2
            for i in range(int((off + u0 - e - 0.3 + shift) / CL), int((off + u1 + e + 0.3 + shift) / CL) + 1):
                mask[j, i % self.ni] = 1.0

    # ---------------------------------------------------------------- wall planes (shaded brick field)
    def build_wall_planes(self):
        mb = self.M('wall')
        mb.closed = False
        for wall, ulen in self.walls:
            holes = [(o['u0'], o['u1'], o['v0'] - 0.005, o['v1']) for o in self.openings if o['wall'] == wall]
            if wall == 'F':
                wv = self.vent
                holes.append((wv[1] - wv[3] / 2, wv[1] + wv[3] / 2, wv[2], wv[2] + wv[4]))
            us = sorted(set([0.0, ulen] + [h[0] for h in holes] + [h[1] for h in holes]))
            vs = sorted(set([self.GH, self.ZTOP] + [h[2] for h in holes] + [h[3] for h in holes]))
            for a, b in zip(us[:-1], us[1:]):
                for c, d in zip(vs[:-1], vs[1:]):
                    cu, cv = (a + b) / 2, (c + d) / 2
                    if any(h[0] <= cu <= h[1] and h[2] <= cv <= h[3] for h in holes):
                        continue
                    mb.quad([self.wp(wall, a, c, 0), self.wp(wall, b, c, 0), self.wp(wall, b, d, 0), self.wp(wall, a, d, 0)], 'brickfield')

    # ---------------------------------------------------------------- shopfront
    def build_shopfront(self):
        R = random.Random(self.seed + 77)
        st = self.M('stone')
        ci = self.M('shop_paint')     # painted cast iron / timber
        gl = self.M('glass')
        W, GH, bw = self.W, self.GH, self.bw
        F = 'F'
        g = 0.011
        # --- rusticated stone piers (left pier and the corner pier wrapping the return)
        def rust_pier(wall, u0, u1, z0, z1, d=0.08):
            z = z0
            i = 0
            while z < z1 - 0.01:
                h = min(0.30, z1 - z)
                st.box(*self._wbox(wall, u0 + g, u1 - g, z + g, z + h - g, -0.05, d), 'stone')
                # chamfered joint reveals: slightly smaller inner block behind
                z += h
                i += 1
            st.box(*self._wbox(wall, u0, u1, z0, z1, -0.06, d - 0.028), 'mortar')
        rust_pier(F, 0.0, 0.45, 0.0, 3.75)
        rust_pier(F, W - 0.55, W, 0.0, 3.75)
        if self.corner:
            self.return_ground(st, rust_pier)
        # --- bay 0: residential entrance in a stone surround
        du0, du1 = 1.05, 2.15
        rust_pier(F, 0.45, du0 - 0.22, 0.0, 3.75, d=0.05)
        rust_pier(F, du1 + 0.22, bw - 0.16, 0.0, 3.75, d=0.05)
        rust_pier(F, du0 - 0.22, du1 + 0.22, 3.50, 3.75, d=0.05)
        self.res_door(du0, du1)
        # --- cast iron pilasters at bay lines
        for b in range(1, self.bays):
            uc = b * bw
            self.pilaster(uc, ci)
        # --- shop bays
        u_start, u_end = bw + 0.16, W - 0.55
        self.shop_bays(u_start, u_end, R)
        self.shop_upper(u_start, u_end)

    def return_ground(self, st, rust_pier):
        rust_pier('R', 0.0, 0.55, 0.0, 3.75)
        st.box(*self._wbox('R', 0.55, self.RET, 0.0, 0.45, -0.05, 0.05), 'stone')
        st.box(*self._wbox('R', 0.55, self.RET, 0.45, 3.75, -0.05, 0.035), 'stone')
        for zz in np.arange(0.75, 3.75, 0.45):
            st.box(*self._wbox('R', 0.55, self.RET, zz - 0.004, zz + 0.004, -0.05, 0.036), 'mortar')

    def shop_upper(self, u_start, u_end):
        F = 'F'
        W, bw = self.W, self.bw
        ci = self.M('shop_paint')
        # --- shop cornice (whole width) and sign fascia
        prof = [(0.0, 3.75), (0.10, 3.75), (0.10, 3.80), (0.14, 3.84), (0.14, 4.30), (0.20, 4.33), (0.20, 4.38), (0.30, 4.44),
                (0.34, 4.52), (0.34, 4.58), (0.30, 4.60), (0.30, 4.63), (0.0, 4.66)]
        ci.sweep(prof, [(0, 0), (W, 0), (W, 0.55)] if self.corner else [(0, 0), (W, 0)], 'shop_paint')
        # sign board recessed panel with mouldings
        fu0, fu1 = u_start + 0.05, u_end - 0.05
        ci.box(*self._wbox(F, fu0, fu1, 3.84, 4.26, -0.02, 0.152), 'sign_board')
        for (a, b, c, d) in ((fu0, fu1, 3.84, 3.875), (fu0, fu1, 4.225, 4.26), (fu0, fu0 + 0.035, 3.84, 4.26), (fu1 - 0.035, fu1, 3.84, 4.26)):
            ci.box(*self._wbox(F, a, b, c, d, 0.0, 0.17), 'shop_paint')
        self.text(self.shop_name, FONT_SERIF, size=0.25, wall=F, u=(fu0 + fu1) / 2, v=4.05, d=0.152, depth=0.012, mat='letters',
                  key='letters', width_max=fu1 - fu0 - 0.25)
        # consoles at pilasters
        for b in range(1, self.bays):
            uc = b * bw
            p = [(0.0, 3.80), (0.18, 3.80), (0.18, 3.95), (0.30, 4.40), (0.0, 4.40)]
            st_ = [self.wp(F, uc - 0.09, vv, dd) for (dd, vv) in p]
            ci.prism(st_, self.wvec(F, 0.18, 0, 0), 'shop_paint')
        # awning over shop bays
        self.awning(u_start + 0.05, u_end - 0.05)

    def pilaster(self, uc, ci):
        F = 'F'
        w = 0.32
        # plinth, fluted shaft, capital
        ci.box(*self._wbox(F, uc - w / 2 - 0.02, uc + w / 2 + 0.02, 0.0, 0.32, -0.05, 0.15), 'shop_paint')
        ci.box(*self._wbox(F, uc - w / 2, uc + w / 2, 0.32, 3.45, -0.05, 0.10), 'shop_paint')
        nfl = 5
        for k in range(nfl + 1):
            # fillets between flutes stand proud; flutes are the gaps
            fu = uc - w / 2 + 0.03 + k * (w - 0.06) / nfl
            ci.box(*self._wbox(F, fu - 0.012, fu + 0.012, 0.45, 3.32, 0.09, 0.125), 'shop_paint')
        ci.box(*self._wbox(F, uc - w / 2 - 0.01, uc + w / 2 + 0.01, 0.32, 0.45, -0.05, 0.13), 'shop_paint')
        ci.box(*self._wbox(F, uc - w / 2 - 0.01, uc + w / 2 + 0.01, 3.32, 3.40, -0.05, 0.13), 'shop_paint')
        ci.box(*self._wbox(F, uc - w / 2 - 0.04, uc + w / 2 + 0.04, 3.40, 3.52, -0.05, 0.16), 'shop_paint')
        ci.box(*self._wbox(F, uc - w / 2 - 0.06, uc + w / 2 + 0.06, 3.52, 3.62, -0.05, 0.18), 'shop_paint')
        # rosette on the capital
        ci.rod(self.wp(F, uc, 3.57, 0.18), self.wp(F, uc, 3.57, 0.205), 0.035, 'shop_paint', seg=10)

    def shop_bays(self, ua, ub, R):
        F = 'F'
        ci = self.M('shop_paint')
        gl = self.M('glass')
        kick = self.M('brass')
        D = -0.10        # glazing line depth
        bw = self.bw
        segs = []
        for b in range(1, self.bays):
            a = max(ua, b * bw + 0.16)
            c = min(ub, (b + 1) * bw - 0.16)
            segs.append((b, a, c))
        ent_bay = 1 + (self.bays - 1) // 2
        self.shop_door = None
        for (b, a, c) in segs:
            if b == ent_bay:
                mid = (a + c) / 2
                e0, e1 = mid - 0.62, mid + 0.62
                self.display(a, e0, D, R, side_return=True)
                self.display(e1, c, D, R, side_return=True)
                self.entrance(e0, e1, D, R)
            else:
                self.display(a, c, D, R)
        # transom band over all shop bays
        for (b, a, c) in segs:
            n = 5
            ci.box(*self._wbox(F, a, c, 2.86, 2.95, D - 0.05, D + 0.05), 'shop_paint')
            ci.box(*self._wbox(F, a, c, 3.62, 3.75, D - 0.05, 0.10), 'shop_paint')
            for k in range(n + 1):
                uu = a + (c - a) * k / n
                ci.box(*self._wbox(F, uu - 0.025, uu + 0.025, 2.95, 3.62, D - 0.04, D + 0.04), 'shop_paint')
            for k in range(n):
                uu0 = a + (c - a) * k / n + 0.025
                uu1 = a + (c - a) * (k + 1) / n - 0.025
                gl.quad([self.wp(F, uu0, 2.95, D), self.wp(F, uu1, 2.95, D), self.wp(F, uu1, 3.62, D), self.wp(F, uu0, 3.62, D)], 'prism_glass')
            # side jamb trims
            ci.box(*self._wbox(F, a - 0.02, a + 0.04, 0, 3.75, D - 0.05, 0.10), 'shop_paint')
            ci.box(*self._wbox(F, c - 0.04, c + 0.02, 0, 3.75, D - 0.05, 0.10), 'shop_paint')

    def display(self, a, c, D, R, side_return=False):
        F = 'F'
        ci = self.M('shop_paint')
        gl = self.M('glass')
        kick = self.M('brass')
        # bulkhead with raised panels and a brass kick strip
        ci.box(*self._wbox(F, a, c, 0.0, 0.55, D - 0.05, D + 0.06), 'shop_paint')
        n = max(1, int(round((c - a) / 0.75)))
        for k in range(n):
            p0 = a + (c - a) * k / n + 0.07
            p1 = a + (c - a) * (k + 1) / n - 0.07
            ci.box(*self._wbox(F, p0, p1, 0.14, 0.47, D + 0.06, D + 0.075), 'shop_paint')
            ci.box(*self._wbox(F, p0 + 0.035, p1 - 0.035, 0.175, 0.435, D + 0.075, D + 0.085), 'shop_paint')
        kick.box(*self._wbox(F, a, c, 0.0, 0.09, D + 0.06, D + 0.064), 'brass')
        # sill
        ci.box(*self._wbox(F, a - 0.01, c + 0.01, 0.55, 0.60, D - 0.06, D + 0.09), 'shop_paint')
        # glazing bars
        ci.box(*self._wbox(F, a, c, 0.60, 0.64, D - 0.03, D + 0.03), 'shop_paint')
        nm = 1 if (c - a) > 1.6 else 0
        bars = [a + (c - a) * (k + 1) / (nm + 1) for k in range(nm)]
        edges = [a] + bars + [c]
        for bu in bars:
            ci.box(*self._wbox(F, bu - 0.03, bu + 0.03, 0.60, 2.86, D - 0.04, D + 0.04), 'shop_paint')
        for k in range(len(edges) - 1):
            g0 = edges[k] + (0.03 if k > 0 else 0.0)
            g1 = edges[k + 1] - (0.03 if k < len(edges) - 2 else 0.0)
            gl.quad([self.wp(F, g0, 0.64, D), self.wp(F, g1, 0.64, D), self.wp(F, g1, 2.86, D), self.wp(F, g0, 2.86, D)], 'glass')
        self.displays = getattr(self, 'displays', []) + [(a, c)]

    def entrance(self, e0, e1, D, R):
        F = 'F'
        ci = self.M('shop_paint')
        gl = self.M('glass')
        br = self.M('brass')
        rec = 1.15
        # recess floor: mosaic tile, brass threshold
        self.M('tile').box(*self._wbox(F, e0, e1, -0.02, 0.012, D - rec - 0.05, D + 0.02), 'tile')
        br.box(*self._wbox(F, e0 + 0.02, e1 - 0.02, 0.012, 0.018, D - rec - 0.02, D - rec + 0.04), 'brass')
        # glazed side returns
        for (uu, sgn) in ((e0, 1), (e1, -1)):
            ci.box(*self._wbox(F, uu - 0.03, uu + 0.03, 0, 0.60, D - rec, D), 'shop_paint')
            ci.box(*self._wbox(F, uu - 0.03, uu + 0.03, 2.86, 2.95, D - rec, D), 'shop_paint')
            p = [self.wp(F, uu, 0.60, D - 0.03), self.wp(F, uu, 0.60, D - rec + 0.05), self.wp(F, uu, 2.86, D - rec + 0.05), self.wp(F, uu, 2.86, D - 0.03)]
            gl.quad(p, 'glass')
            ci.box(*self._wbox(F, uu - 0.035, uu + 0.035, 0, 2.95, D - 0.06, D + 0.04), 'shop_paint')
        # recess ceiling (soffit) with a small lamp
        ci.box(*self._wbox(F, e0, e1, 2.86, 2.95, D - rec, D), 'shop_paint')
        # door frame at the back of the recess
        dd = D - rec
        ci.box(*self._wbox(F, e0, e0 + 0.12, 0, 2.86, dd - 0.06, dd + 0.02), 'shop_paint')
        ci.box(*self._wbox(F, e1 - 0.12, e1, 0, 2.86, dd - 0.06, dd + 0.02), 'shop_paint')
        ci.box(*self._wbox(F, e0, e1, 2.32, 2.42, dd - 0.06, dd + 0.02), 'shop_paint')
        # transom glass
        gl.quad([self.wp(F, e0 + 0.12, 2.42, dd - 0.02), self.wp(F, e1 - 0.12, 2.42, dd - 0.02), self.wp(F, e1 - 0.12, 2.86, dd - 0.02), self.wp(F, e0 + 0.12, 2.86, dd - 0.02)], 'glass')
        # the door: stiles/rails with a large glass light
        a, c = e0 + 0.12, e1 - 0.12
        d0, d1 = dd - 0.045, dd + 0.0
        ci.box(*self._wbox(F, a, a + 0.11, 0.0, 2.32, d0, d1), 'shop_paint')
        ci.box(*self._wbox(F, c - 0.11, c, 0.0, 2.32, d0, d1), 'shop_paint')
        ci.box(*self._wbox(F, a + 0.11, c - 0.11, 0.0, 0.32, d0, d1), 'shop_paint')
        ci.box(*self._wbox(F, a + 0.11, c - 0.11, 2.20, 2.32, d0, d1), 'shop_paint')
        gl.quad([self.wp(F, a + 0.11, 0.32, dd - 0.022), self.wp(F, c - 0.11, 0.32, dd - 0.022), self.wp(F, c - 0.11, 2.20, dd - 0.022), self.wp(F, a + 0.11, 2.20, dd - 0.022)], 'glass')
        # kick plate and push bar / pull handle
        br.box(*self._wbox(F, a + 0.01, c - 0.01, 0.02, 0.28, d1, d1 + 0.003), 'brass')
        hz = 1.05
        hu = c - 0.07
        br.rod(self.wp(F, hu, hz - 0.18, d1 + 0.055), self.wp(F, hu, hz + 0.18, d1 + 0.055), 0.013, 'brass', seg=10)
        for zz in (hz - 0.16, hz + 0.16):
            br.rod(self.wp(F, hu, zz, d1), self.wp(F, hu, zz, d1 + 0.06), 0.009, 'brass', seg=8)
        br.box(*self._wbox(F, a + 0.15, c - 0.15, 1.02, 1.10, d1, d1 + 0.004), 'brass')  # push plate
        self.shop_door = (e0, e1, dd)
        # "OPEN" hours decal is in the glass material? -> small painted lettering instead
        self.text("OPEN 7AM - 7PM", FONT_SANS, size=0.035, wall=F, u=(a + c) / 2, v=1.45, d=dd + 0.003, depth=0.0, mat='letters_white', key='letters_flat')

    def res_door(self, u0, u1):
        F = 'F'
        st = self.M('stone')
        ci = self.M('door')
        gl = self.M('glass')
        br = self.M('brass')
        # granite step
        st.box(*self._wbox(F, u0 - 0.15, u1 + 0.15, 0.0, 0.16, -0.30, 0.26), 'granite')
        # architrave surround
        for (a, b) in ((u0 - 0.22, u0), (u1, u1 + 0.22)):
            st.box(*self._wbox(F, a, b, 0.16, 3.25, -0.05, 0.075), 'stone')
        st.box(*self._wbox(F, u0 - 0.28, u1 + 0.28, 3.25, 3.42, -0.05, 0.11), 'stone')
        st.box(*self._wbox(F, u0 - 0.32, u1 + 0.32, 3.42, 3.50, -0.05, 0.14), 'stone')
        # recess reveals
        dd = -0.28
        st.box(*self._wbox(F, u0 - 0.02, u0, 0.16, 3.25, dd, 0.0), 'stone')
        st.box(*self._wbox(F, u1, u1 + 0.02, 0.16, 3.25, dd, 0.0), 'stone')
        st.box(*self._wbox(F, u0, u1, 3.23, 3.25, dd, 0.0), 'stone')
        # frame & transom bar
        ci.box(*self._wbox(F, u0, u0 + 0.07, 0.16, 3.23, dd - 0.05, dd + 0.02), 'door')
        ci.box(*self._wbox(F, u1 - 0.07, u1, 0.16, 3.23, dd - 0.05, dd + 0.02), 'door')
        ci.box(*self._wbox(F, u0, u1, 2.55, 2.65, dd - 0.05, dd + 0.02), 'door')
        gl.quad([self.wp(F, u0 + 0.07, 2.65, dd - 0.02), self.wp(F, u1 - 0.07, 2.65, dd - 0.02), self.wp(F, u1 - 0.07, 3.23, dd - 0.02), self.wp(F, u0 + 0.07, 3.23, dd - 0.02)], 'glass')
        # transom numerals in gold leaf
        self.text(self.vt['number'], FONT_SERIF, size=0.22, wall=F, u=(u0 + u1) / 2, v=2.86, d=dd - 0.018, depth=0.0, mat='letters', key='letters_flat')
        # door leaf: wood with glazed upper panel and an iron grille
        a, c = u0 + 0.07, u1 - 0.07
        d0, d1 = dd - 0.05, dd
        ci.box(*self._wbox(F, a, a + 0.13, 0.16, 2.55, d0, d1), 'door')
        ci.box(*self._wbox(F, c - 0.13, c, 0.16, 2.55, d0, d1), 'door')
        ci.box(*self._wbox(F, a + 0.13, c - 0.13, 0.16, 0.95, d0, d1), 'door')
        ci.box(*self._wbox(F, a + 0.13, c - 0.13, 2.40, 2.55, d0, d1), 'door')
        ci.box(*self._wbox(F, a + 0.20, c - 0.20, 0.30, 0.82, d1, d1 + 0.012), 'door')
        gl.quad([self.wp(F, a + 0.13, 0.95, dd - 0.025), self.wp(F, c - 0.13, 0.95, dd - 0.025), self.wp(F, c - 0.13, 2.40, dd - 0.025), self.wp(F, a + 0.13, 2.40, dd - 0.025)], 'glass')
        ir = self.M('iron')
        for k in range(6):
            uu = a + 0.13 + (c - a - 0.26) * (k + 0.5) / 6
            ir.rod(self.wp(F, uu, 0.97, d1 + 0.02), self.wp(F, uu, 2.38, d1 + 0.02), 0.007, 'iron', seg=6)
        for zz in (1.25, 2.05):
            ir.box(*self._wbox(F, a + 0.13, c - 0.13, zz, zz + 0.02, d1 + 0.008, d1 + 0.03), 'iron')
        for zz in (0.98, 2.37):
            ir.box(*self._wbox(F, a + 0.13, c - 0.13, zz - 0.01, zz + 0.01, d1, d1 + 0.03), 'iron')
        # knob, lock, letter plate
        br.rod(self.wp(F, c - 0.07, 1.0, d1), self.wp(F, c - 0.07, 1.0, d1 + 0.05), 0.008, 'brass', seg=8)
        br.rod(self.wp(F, c - 0.07, 1.0, d1 + 0.05), self.wp(F, c - 0.07, 1.0, d1 + 0.075), 0.028, 'brass', seg=12)
        br.box(*self._wbox(F, c - 0.10, c - 0.04, 1.12, 1.22, d1, d1 + 0.006), 'brass')
        # intercom panel and building plaque on the surround
        br.box(*self._wbox(F, u1 + 0.04, u1 + 0.18, 1.25, 1.55, 0.075, 0.09), 'steel')
        for k in range(6):
            br.rod(self.wp(F, u1 + 0.11, 1.30 + k * 0.035, 0.09), self.wp(F, u1 + 0.11, 1.30 + k * 0.035, 0.097), 0.006, 'brass', seg=8)
        # vestibule behind the door
        vb = self.M('interior')
        vb.box(*self._wbox(F, u0 - 0.6, u1 + 0.6, 0.16, 3.3, dd - 2.6, dd - 2.55), 'wall_hall')
        vb.box(*self._wbox(F, u0 - 0.6, u1 + 0.6, 0.10, 0.16, dd - 2.6, dd), 'tile')
        vb.box(*self._wbox(F, u0 - 0.6, u0 - 0.55, 0.16, 3.3, dd - 2.6, dd), 'wall_hall')
        vb.box(*self._wbox(F, u1 + 0.55, u1 + 0.6, 0.16, 3.3, dd - 2.6, dd), 'wall_hall')
        vb.box(*self._wbox(F, u0 - 0.6, u1 + 0.6, 3.25, 3.3, dd - 2.6, dd), 'wall_hall')
        for r_ in range(3):
            for c_ in range(4):
                br.box(*self._wbox(F, u0 - 0.5 + c_ * 0.13, u0 - 0.39 + c_ * 0.13, 1.3 + r_ * 0.2, 1.47 + r_ * 0.2, dd - 2.55, dd - 2.53), 'brass')
        self.lights.append(dict(kind='point', loc=self.wp(F, (u0 + u1) / 2, 3.0, dd - 1.3), energy=25, color=(1.0, 0.78, 0.5), radius=0.05, group='interior'))

    # ---------------------------------------------------------------- awning
    def awning(self, a, c):
        F = 'F'
        fab = self.M('awning')
        fr = self.M('iron')
        z_top, proj, z_front = 3.72, 1.25, 3.02
        val = 0.26
        nu = int((c - a) / 0.05) + 1
        nv = 14
        arms = [a + (c - a) * k / 4 for k in range(5)]
        # fabric grid with sag between arms
        grid = []
        for j in range(nv + 1):
            t = j / nv
            row = []
            for i in range(nu + 1):
                uu = a + (c - a) * i / nu
                # distance to nearest arm -> sag
                da = min(abs(uu - x) for x in arms)
                sag = 0.018 * math.sin(math.pi * min(1, da / ((c - a) / 8))) * math.sin(math.pi * t)
                d = proj * t
                z = z_top + (z_front - z_top) * t - sag - 0.02 * math.sin(math.pi * t)
                row.append(fab.add_v(self.wp(F, uu, z, d)))
            grid.append(row)
        for j in range(nv):
            for i in range(nu):
                fab.face([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]], 'awning')
        # valance: slight scallop-free flat skirt with a hem
        top = [self.wp(F, a + (c - a) * i / nu, z_front - 0.0, proj + 0.004) for i in range(nu + 1)]
        vrow0 = [fab.add_v(p) for p in top]
        vrow1 = []
        for i in range(nu + 1):
            uu = a + (c - a) * i / nu
            wav = 0.004 * math.sin(uu * 9.0)
            vrow1.append(fab.add_v(self.wp(F, uu, z_front - val, proj + 0.004 + wav)))
        for i in range(nu):
            fab.face([vrow1[i], vrow1[i + 1], vrow0[i + 1], vrow0[i]], 'awning')
        # side panels (triangles)
        for uu in (a, c):
            p0 = fab.add_v(self.wp(F, uu, z_top, 0.0))
            p1 = fab.add_v(self.wp(F, uu, z_front, proj))
            p2 = fab.add_v(self.wp(F, uu, z_front - val, proj))
            p3 = fab.add_v(self.wp(F, uu, z_top - 0.15, 0.0))
            fab.face([p0, p1, p2, p3], 'awning')
        fab.closed = False
        # frame: arms, front bar, wall rail
        r = 0.014
        fr.rod(self.wp(F, a, z_top - 0.03, 0.02), self.wp(F, c, z_top - 0.03, 0.02), r, 'iron', seg=8)
        fr.rod(self.wp(F, a, z_front - 0.03, proj - 0.02), self.wp(F, c, z_front - 0.03, proj - 0.02), r, 'iron', seg=8)
        for x in arms:
            fr.rod(self.wp(F, x, z_top - 0.03, 0.02), self.wp(F, x, z_front - 0.03, proj - 0.02), r, 'iron', seg=8)
            fr.rod(self.wp(F, x, z_top - 0.55, 0.02), self.wp(F, x, z_front - 0.05, proj * 0.75), 0.010, 'iron', seg=6)
            fr.box(*self._wbox(F, x - 0.04, x + 0.04, z_top - 0.62, z_top - 0.48, 0.0, 0.012), 'iron')
        # lettering on the valance
        self.text(self.shop_name, FONT_SANS, size=0.11, wall=F, u=(a + c) / 2, v=z_front - val / 2, d=proj + 0.007, depth=0.0,
                  mat='letters_white', key='letters_flat', width_max=c - a - 0.6)

    # ---------------------------------------------------------------- cornice
    def build_cornice(self):
        W, R = self.W, self.RET
        cm = self.M('cornice')
        z = self.ZC
        P = [(0.0, z - 0.30), (0.03, z - 0.30), (0.03, z - 0.06), (0.06, z - 0.04), (0.06, z), (0.10, z + 0.02), (0.13, z + 0.07),
             (0.13, z + 0.22), (0.15, z + 0.22), (0.15, z + 0.30), (0.56, z + 0.30), (0.58, z + 0.32), (0.58, z + 0.50),
             (0.61, z + 0.52), (0.61, z + 0.55), (0.64, z + 0.58), (0.67, z + 0.63), (0.68, z + 0.68), (0.66, z + 0.71),
             (0.66, z + 0.75), (0.0, z + 0.75)]
        cm.sweep(P, self.path, 'cornice')
        # frieze panels with raised mouldings between brackets
        brk_u = [0.18] + [0.18 + k * (W - 0.36) / max(1, round((W - 0.36) / 0.95)) for k in range(1, int(round((W - 0.36) / 0.95)) + 1)]
        for uu in brk_u:
            self.bracket('F', uu, z)
        for uu in (0.45, 1.4, 2.4):
            if uu < R - 0.1:
                self.bracket('R', uu, z)
        # dentils under the corona
        cm2 = self.M('cornice')
        k = 0
        uu = 0.05
        while uu < W - 0.02:
            cm2.box(*self._wbox('F', uu, uu + 0.055, z + 0.20, z + 0.30, 0.13, 0.23), 'cornice')
            uu += 0.11
        uu = 0.20
        while uu < R - 0.05:
            cm2.box(*self._wbox('R', uu, uu + 0.055, z + 0.20, z + 0.30, 0.13, 0.23), 'cornice')
            uu += 0.11
        # frieze raised panels
        for a, b in zip(brk_u[:-1], brk_u[1:]):
            cm.box(*self._wbox('F', a + 0.12, b - 0.12, z - 0.24, z - 0.04, 0.03, 0.045), 'cornice')
        # weathering: drip curtain under the cornice and soot band
        self.weather.drip(1, 0, self.U_TOT, z - 0.30, 2.6, 0.55, density=2.2, width=(0.01, 0.05))
        self.weather.band(0, z - 1.2, z - 0.25, 0.35, falloff_up=False)

    def bracket(self, wall, uc, z):
        cm = self.M('cornice')
        # scroll console under the soffit, extruded across 0.14
        prof = [(0.0, z - 0.62), (0.07, z - 0.62), (0.10, z - 0.58), (0.11, z - 0.50), (0.09, z - 0.44), (0.10, z - 0.36),
                (0.15, z - 0.24), (0.24, z - 0.10), (0.36, z + 0.02), (0.48, z + 0.12), (0.54, z + 0.18), (0.56, z + 0.24),
                (0.56, z + 0.30), (0.0, z + 0.30)]
        poly = [self.wp(wall, uc - 0.07, vv, dd) for (dd, vv) in prof]
        cm.prism(poly, self.wvec(wall, 0.14, 0, 0), 'cornice')
        # side scroll discs
        for s in (-0.072, 0.072):
            cm.rod(self.wp(wall, uc + s, z - 0.52, 0.065), self.wp(wall, uc + s * 1.12, z - 0.52, 0.065), 0.045, 'cornice', seg=12)
            cm.rod(self.wp(wall, uc + s, z + 0.17, 0.47), self.wp(wall, uc + s * 1.12, z + 0.17, 0.47), 0.05, 'cornice', seg=12)
        # acanthus-ish leaf block on the face
        cm.box(*self._wbox(wall, uc - 0.045, uc + 0.045, z - 0.40, z - 0.12, 0.10, 0.17), 'cornice')

    # ---------------------------------------------------------------- fire escape
    def build_fire_escape(self):
        F = 'F'
        b = self.vt['fire_escape_bay']
        if b is None:
            return
        ir = self.M('fire_escape')
        u0 = b * self.bw + 0.10
        u1 = (b + 1) * self.bw - 0.10
        if b == 0:
            u0 = 0.55
        D = 0.95
        top_k = self.S
        R = random.Random(self.seed + 9)
        plats = []
        for k in range(1, top_k + 1):
            zp = self.floor_base(k) + 11 * CH - 0.55
            plats.append(zp)
            self.platform(ir, u0, u1, D, zp, k, R)
            # wall brackets: diagonal struts and anchor plates
            for uu in (u0 + 0.12, u1 - 0.12):
                ir.bar(self.wp(F, uu, zp - 0.95, 0.03), self.wp(F, uu, zp - 0.03, D - 0.08), 0.05, 0.008, 'fire_escape', up=(1, 0, 0))
                ir.box(*self._wbox(F, uu - 0.06, uu + 0.06, zp - 1.05, zp - 0.85, 0.0, 0.012), 'fire_escape')
                ir.box(*self._wbox(F, uu - 0.06, uu + 0.06, zp - 0.08, zp + 0.02, 0.0, 0.012), 'fire_escape')
                for bz in (zp - 1.0, zp - 0.90):
                    ir.rod(self.wp(F, uu, bz, 0.012), self.wp(F, uu, bz, 0.03), 0.012, 'fire_escape', seg=6)
                fu = self.uoff(F) + uu
                self.weather.drip(3, fu - 0.06, fu + 0.06, zp - 1.05, 1.4, 0.55, density=1.0)
                self.weather.drip(3, fu - 0.04, fu + 0.04, zp - 0.10, 0.9, 0.4, density=1.0)
        # stairs between platforms (descending toward u0)
        for i in range(1, len(plats)):
            ztop, zbot = plats[i], plats[i - 1]
            self.stair(ir, u1 - 0.15, u0 + 0.55, ztop, zbot, D - 0.52, D - 0.06)
        # drop ladder hanging from the lowest platform (stowed position)
        z0 = plats[0]
        lu0, lu1 = u0 + 0.10, u0 + 0.55
        dl = D - 0.05
        for uu in (lu0, lu1):
            ir.bar(self.wp(F, uu, z0 - 2.1, dl), self.wp(F, uu, z0 + 0.9, dl), 0.05, 0.010, 'fire_escape', up=(0, 1, 0))
        zz = z0 - 2.0
        while zz < z0 + 0.85:
            ir.rod(self.wp(F, lu0, zz, dl), self.wp(F, lu1, zz, dl), 0.010, 'fire_escape', seg=6)
            zz += 0.30
        # gooseneck roof ladder from the top platform over the parapet
        zt = plats[-1]
        gu0, gu1 = u1 - 0.55, u1 - 0.12
        dd = 0.82
        pts_rail = []
        for uu in (gu0, gu1):
            path = [self.wp(F, uu, zt + 0.0, dd), self.wp(F, uu, self.ZTOP + 0.5, dd), self.wp(F, uu, self.ZTOP + 0.85, dd - 0.15),
                    self.wp(F, uu, self.ZTOP + 1.0, dd - 0.45), self.wp(F, uu, self.ZTOP + 0.95, dd - 0.75), self.wp(F, uu, self.ZTOP + 0.12, dd - 0.95)]
            ir.tube(path, 0.016, 'fire_escape', seg=6)
        zz = zt + 0.3
        while zz < self.ZTOP + 0.5:
            ir.rod(self.wp(F, gu0, zz, dd), self.wp(F, gu1, zz, dd), 0.009, 'fire_escape', seg=6)
            zz += 0.30
        # stays from ladder to the cornice
        ir.bar(self.wp(F, gu0, self.ZC - 0.5, dd), self.wp(F, gu0, self.ZC - 0.5, 0.0), 0.04, 0.008, 'fire_escape')
        ir.bar(self.wp(F, gu1, self.ZC - 0.5, dd), self.wp(F, gu1, self.ZC - 0.5, 0.0), 0.04, 0.008, 'fire_escape')
        self.fe = (u0, u1, D, plats)

    def platform(self, ir, u0, u1, D, zp, k, R):
        F = 'F'
        # perimeter angles
        t = 0.008
        ir.box(*self._wbox(F, u0, u1, zp - 0.06, zp, D - 0.06, D), 'fire_escape')            # front angle (vertical leg)
        ir.box(*self._wbox(F, u0, u1, zp - 0.008, zp, D - 0.06, D), 'fire_escape')
        ir.box(*self._wbox(F, u0, u1, zp - 0.06, zp, 0.0, 0.06), 'fire_escape')
        for uu in (u0, u1 - 0.06):
            ir.box(*self._wbox(F, uu, uu + 0.06, zp - 0.06, zp, 0.0, D), 'fire_escape')
        # cross bearers
        n = 4
        for i in range(1, n):
            uu = u0 + (u1 - u0) * i / n
            ir.box(*self._wbox(F, uu - 0.004, uu + 0.004, zp - 0.05, zp - 0.006, 0.0, D), 'fire_escape')
        # slatted floor: flat bars on edge running parallel to the wall, opening for the stair
        d = 0.07
        hole = (u0 + 0.45, u1 - 0.10, D - 0.55, D - 0.04) if k > 1 else None
        while d < D - 0.07:
            segs = [(u0 + 0.06, u1 - 0.06)]
            if hole and hole[2] < d < hole[3]:
                segs = [(u0 + 0.06, hole[0])]
            for (a, b) in segs:
                ir.box(*self._wbox(F, a, b, zp - 0.035, zp - 0.003, d - 0.003, d + 0.003), 'fire_escape')
            d += 0.045
        # railing: posts, top rail, mid rail, balusters
        H = 0.95
        posts = [(u0 + 0.02, D - 0.02), (u1 - 0.02, D - 0.02), (u0 + 0.02, 0.05), (u1 - 0.02, 0.05), ((u0 + u1) / 2, D - 0.02)]
        for (uu, dd) in posts:
            ir.box(*self._wbox(F, uu - 0.016, uu + 0.016, zp, zp + H, dd - 0.016, dd + 0.016), 'fire_escape')
        rails = [((u0, D - 0.02), (u1, D - 0.02)), ((u0 + 0.02, 0.05), (u0 + 0.02, D)), ((u1 - 0.02, 0.05), (u1 - 0.02, D))]
        for (p, q) in rails:
            for (zz, w, h) in ((zp + H, 0.05, 0.012), (zp + 0.12, 0.035, 0.008)):
                ir.bar(self.wp(F, p[0], zz, p[1]), self.wp(F, q[0], zz, q[1]), w, h, 'fire_escape')
            L = math.hypot(q[0] - p[0], q[1] - p[1])
            nb = int(L / 0.115)
            for i in range(1, nb):
                tt = i / nb
                uu = p[0] + (q[0] - p[0]) * tt
                dd = p[1] + (q[1] - p[1]) * tt
                ir.rod(self.wp(F, uu, zp + 0.12, dd), self.wp(F, uu, zp + H, dd), 0.008, 'fire_escape', seg=6, caps=False)
        # a few signs of life: flower pot, folded chair on some platforms
        if R.random() < 0.6:
            pots = self.M('props')
            uu = R.uniform(u0 + 0.2, u0 + 0.4)
            pots.rod(self.wp(F, uu, zp, 0.35), self.wp(F, uu, zp + 0.22, 0.35), 0.11, 'terracotta', seg=14, r1=0.14)
            pots.rod(self.wp(F, uu, zp + 0.2, 0.35), self.wp(F, uu, zp + 0.24, 0.35), 0.125, 'soil', seg=14)
            for _ in range(5):
                a = R.uniform(0, 6.28)
                rr = R.uniform(0.02, 0.09)
                tip = self.wp(F, uu + math.cos(a) * rr * 2.2, zp + R.uniform(0.45, 0.65), 0.35 + math.sin(a) * rr * 2.2)
                pots.rod(self.wp(F, uu + math.cos(a) * rr * 0.3, zp + 0.23, 0.35 + math.sin(a) * rr * 0.3), tip, 0.008, 'leaf', seg=5)
                pots.obox(tip, Vector((0.05, 0, 0)), Vector((0, 0.03, 0)), Vector((0, 0, 0.004)), 'leaf')

    def stair(self, ir, ua, ub, ztop, zbot, d0, d1):
        F = 'F'
        # stringers from (ua, ztop) down to (ub, zbot)
        for dd in (d0, d1):
            ir.bar(self.wp(F, ua, ztop + 0.02, dd), self.wp(F, ub, zbot, dd), 0.012, 0.13, 'fire_escape', up=(0, 0, 1))
        n = int((ztop - zbot) / 0.22)
        for i in range(1, n):
            t = i / n
            uu = ua + (ub - ua) * t
            zz = ztop + (zbot - ztop) * t
            for k in range(3):
                ir.box(*self._wbox(F, uu - 0.06 + k * 0.045, uu - 0.06 + k * 0.045 + 0.03, zz - 0.006, zz + 0.006, d0, d1), 'fire_escape')
        # hand rail on the outside
        ir.rod(self.wp(F, ua, ztop + 0.85, d1 + 0.03), self.wp(F, ub, zbot + 0.85, d1 + 0.03), 0.014, 'fire_escape', seg=6)
        for t in (0.15, 0.5, 0.85):
            uu = ua + (ub - ua) * t
            zz = ztop + (zbot - ztop) * t
            ir.rod(self.wp(F, uu, zz, d1 + 0.03), self.wp(F, uu, zz + 0.85, d1 + 0.03), 0.009, 'fire_escape', seg=6)

    # ---------------------------------------------------------------- balcony
    def build_balcony(self):
        bal = self.vt['balcony']
        if not bal:
            return
        b, k = bal
        op = next((o for o in self.openings if o['wall'] == 'F' and o['k'] == k and abs((o['u0'] + o['u1']) / 2 - (b + 0.5) * self.bw) < 0.1), None)
        if op is None:
            return
        F = 'F'
        st = self.M('stone')
        ir = self.M('iron')
        u0, u1 = op['u0'] - 0.35, op['u1'] + 0.35
        z = op['v0'] - 0.10
        D = 0.55
        st.box(*self._wbox(F, u0, u1, z - 0.12, z, -0.05, D), 'stone')
        st.box(*self._wbox(F, u0 - 0.02, u1 + 0.02, z - 0.03, z, D - 0.02, D + 0.02), 'stone')
        for uu in (u0 + 0.15, u1 - 0.15):
            prof = [(0.0, z - 0.55), (0.06, z - 0.55), (0.12, z - 0.42), (0.22, z - 0.30), (0.40, z - 0.18), (0.48, z - 0.12), (0.0, z - 0.12)]
            st.prism([self.wp(F, uu - 0.06, vv, dd) for (dd, vv) in prof], self.wvec(F, 0.12, 0, 0), 'stone')
            fu = uu
            self.weather.drip(3, fu - 0.05, fu + 0.05, z - 0.5, 1.2, 0.35)
        H = 0.95
        top = z + H
        corners = [(u0 + 0.05, 0.02), (u0 + 0.05, D - 0.05), (u1 - 0.05, D - 0.05), (u1 - 0.05, 0.02)]
        for (p, q) in zip(corners[:-1], corners[1:]):
            ir.bar(self.wp(F, p[0], top, p[1]), self.wp(F, q[0], top, q[1]), 0.045, 0.022, 'iron')
            ir.bar(self.wp(F, p[0], z + 0.10, p[1]), self.wp(F, q[0], z + 0.10, q[1]), 0.03, 0.012, 'iron')
            L = math.hypot(q[0] - p[0], q[1] - p[1])
            n = int(L / 0.12)
            for i in range(n + 1):
                t = i / n
                uu = p[0] + (q[0] - p[0]) * t
                dd = p[1] + (q[1] - p[1]) * t
                ir.box(*self._wbox(F, uu - 0.008, uu + 0.008, z + 0.10, top, dd - 0.008, dd + 0.008), 'iron')
                if i % 2 == 1:
                    # cast collars on alternate balusters
                    ir.rod(self.wp(F, uu, z + 0.48, dd), self.wp(F, uu, z + 0.56, dd), 0.016, 'iron', seg=8)
        for (uu, dd) in corners:
            ir.box(*self._wbox(F, uu - 0.02, uu + 0.02, z, top + 0.02, dd - 0.02, dd + 0.02), 'iron')
            ir.rod(self.wp(F, uu, top + 0.02, dd), self.wp(F, uu, top + 0.09, dd), 0.022, 'iron', seg=10, r1=0.008)

    # ---------------------------------------------------------------- services
    def build_services(self):
        F = 'F'
        W = self.W
        sv = self.M('services')
        # --- downpipe at the far end of the return, with hopper head and brackets
        RW = 'R' if self.corner else 'F'
        pu = self.RET - 0.18 if self.corner else W - 0.15
        pd = 0.09
        r = 0.05
        top = self.ZC - 0.35
        sv.rod(self.wp(RW, pu, 0.12, pd), self.wp(RW, pu, top, pd), r, 'downpipe', seg=14)
        # shoe
        sv.tube([self.wp(RW, pu, 0.30, pd), self.wp(RW, pu, 0.12, pd), self.wp(RW, pu, 0.04, pd + 0.12)], r, 'downpipe', seg=14)
        # joints (sockets) every 1.8 m and brackets
        zz = 0.9
        while zz < top - 0.2:
            sv.rod(self.wp(RW, pu, zz, pd), self.wp(RW, pu, zz + 0.08, pd), r + 0.006, 'downpipe', seg=14)
            sv.box(*self._wbox(RW, pu - 0.012, pu + 0.012, zz + 0.09, zz + 0.12, 0.0, pd), 'downpipe')
            sv.rod(self.wp(RW, pu - 0.065, zz + 0.105, 0.0), self.wp(RW, pu + 0.065, zz + 0.105, 0.0), 0.01, 'downpipe', seg=6)
            fu = self.U_TOT - 0.18
            self.weather.drip(3, fu - 0.03, fu + 0.03, zz + 0.08, 0.6, 0.6, density=0.6)
            self.weather.drip(2, fu - 0.08, fu + 0.08, zz + 0.1, 0.8, 0.5, density=1.5, width=(0.01, 0.03))
            zz += 1.8
        # hopper head (tapered box) under the cornice
        hz = top
        poly = [self.wp(RW, pu - 0.16, hz + 0.32, pd - 0.13), self.wp(RW, pu + 0.16, hz + 0.32, pd - 0.13), self.wp(RW, pu + 0.07, hz, pd - 0.06), self.wp(RW, pu - 0.07, hz, pd - 0.06)]
        sv.prism(poly, self.wvec(RW, 0, 0, 0.25), 'downpipe')
        sv.box(*self._wbox(RW, pu - 0.175, pu + 0.175, hz + 0.32, hz + 0.36, pd - 0.14, pd + 0.14), 'downpipe')
        # --- electrical conduit: up the left pier, along above the shop cornice to the sign lamps and blade sign
        cr = 0.0125
        cu = 0.30
        y0 = 0.08 + cr     # stand-off from the stone pier face
        cz = 4.82
        pts = [self.wp(F, cu, 0.55, y0), self.wp(F, cu, cz - 0.08, y0), self.wp(F, cu + 0.08, cz, y0 - 0.06 - cr + 0.02), self.wp(F, W - 0.75, cz, 0.02 + cr)]
        sv.tube([self.wp(F, cu, 0.55, y0), self.wp(F, cu, 3.70, y0)], cr, 'conduit', seg=8)
        sv.tube([self.wp(F, cu, 3.70, y0), self.wp(F, cu, 4.62, 0.36)], cr, 'conduit', seg=8)
        sv.tube([self.wp(F, cu, 4.62, 0.36), self.wp(F, cu, cz, 0.36), self.wp(F, cu, cz, 0.02 + cr)], cr, 'conduit', seg=8)
        sv.tube([self.wp(F, cu, cz, 0.02 + cr), self.wp(F, W - 0.75, cz, 0.02 + cr)], cr, 'conduit', seg=8)
        # pull box near the ground, junction boxes, straps
        sv.box(*self._wbox(F, cu - 0.09, cu + 0.09, 0.35, 0.60, 0.08, 0.17), 'conduit')
        sv.box(*self._wbox(F, cu - 0.08, cu + 0.08, 3.62, 3.80, 0.08, 0.15), 'conduit')
        jb_u = [cu + 0.2] + [x for x in (self.bw * 1.5, self.bw * (self.bays - 0.5)) if x < W - 1] + [W - 0.75]
        for x in jb_u:
            sv.box(*self._wbox(F, x - 0.06, x + 0.06, cz - 0.06, cz + 0.06, 0.01, 0.075), 'conduit')
            sv.rod(self.wp(F, x, cz, 0.075), self.wp(F, x, cz, 0.08), 0.03, 'conduit', seg=10)
        uu = cu + 0.6
        while uu < W - 0.9:
            sv.box(*self._wbox(F, uu - 0.012, uu + 0.012, cz - 0.03, cz + 0.03, 0.01, 0.02 + 2 * cr + 0.002), 'conduit')
            self.weather.drip(3, uu - 0.01, uu + 0.01, cz - 0.03, 0.35, 0.3, density=0.5)
            uu += 1.0
        for zz in np.arange(1.0, 3.6, 0.9):
            sv.box(*self._wbox(F, cu - 0.03, cu + 0.03, zz, zz + 0.025, 0.08, y0 + cr + 0.003), 'conduit')
        # --- gooseneck sign lamps
        for x in jb_u[1:-1]:
            self.gooseneck(x, cz)
        # --- wall lantern beside the residential door
        lu = 0.78
        lz = 2.15
        sv.box(*self._wbox(F, lu - 0.06, lu + 0.06, lz - 0.12, lz + 0.12, 0.04, 0.06), 'iron')
        sv.rod(self.wp(F, lu, lz, 0.06), self.wp(F, lu, lz, 0.16), 0.012, 'iron', seg=8)
        lb = self.wp(F, lu, lz - 0.05, 0.22)
        sv.box(lb - Vector((0.07, 0.07, 0.17)), lb + Vector((0.07, 0.07, 0.17)), 'lantern_glass')
        for sx in (-1, 1):
            for sy in (-1, 1):
                sv.rod(lb + Vector((0.07 * sx, 0.07 * sy, -0.18)), lb + Vector((0.07 * sx, 0.07 * sy, 0.18)), 0.007, 'iron', seg=6)
        sv.rod(lb + Vector((0, 0, 0.17)), lb + Vector((0, 0, 0.26)), 0.10, 'iron', seg=4, r1=0.01)
        sv.rod(lb + Vector((0, 0, -0.17)), lb + Vector((0, 0, -0.20)), 0.09, 'iron', seg=4)
        self.M('bulbs').rod(lb + Vector((0, 0, -0.06)), lb + Vector((0, 0, 0.05)), 0.025, 'bulb', seg=10)
        self.lights.append(dict(kind='point', loc=lb, energy=8, color=(1.0, 0.72, 0.42), radius=0.03, group='exterior'))
        # --- blade sign at the corner
        self.blade_sign()
        # --- through-wall AC unit
        self.ac_unit()
        # --- vent grille
        wall, uc, vc, w, h = self.vent
        sv.box(*self._wbox(wall, uc - w / 2 - 0.02, uc + w / 2 + 0.02, vc - 0.02, vc + h + 0.02, -0.02, 0.025), 'grille')
        n = 8
        for i in range(n):
            zz = vc + 0.02 + (h - 0.04) * (i + 0.5) / n
            p = [self.wp(wall, uc - w / 2, zz - 0.012, 0.03), self.wp(wall, uc - w / 2, zz + 0.012, 0.0), self.wp(wall, uc - w / 2, zz + 0.016, 0.004), self.wp(wall, uc - w / 2, zz - 0.008, 0.034)]
            sv.prism(p, self.wvec(wall, w, 0, 0), 'grille')
        self.M('interior').box(*self._wbox(wall, uc - w / 2, uc + w / 2, vc, vc + h, -0.25, -0.02), 'void')
        self.weather.drip(0, uc - w / 2, uc + w / 2, vc, 1.4, 0.8, density=2.5, width=(0.01, 0.05))
        self.weather.blob(0, uc, vc + h + 0.15, w * 0.7, 0.25, 0.5)

    def gooseneck(self, x, cz):
        F = 'F'
        sv = self.M('services')
        base = self.wp(F, x, cz + 0.06, 0.08)
        sv.rod(self.wp(F, x, cz + 0.02, 0.075), self.wp(F, x, cz + 0.12, 0.075), 0.035, 'iron', seg=10)
        pts = [self.wp(F, x, cz + 0.07, 0.08)]
        for t in np.linspace(0, 1, 9)[1:]:
            a = math.pi * 0.95 * t
            pts.append(self.wp(F, x, cz + 0.07 + 0.38 * math.sin(a), 0.08 + 0.38 * (1 - math.cos(a)) * 0.95))
        sv.tube(pts, 0.012, 'iron', seg=8)
        tip = pts[-1]
        # RLM-style shade, aimed down/back toward the sign
        sv.rod(tip + Vector((0, 0, -0.01)), tip + Vector((0, 0.0, -0.06)), 0.03, 'iron', seg=10)
        sh = self.M('shade')
        sh.rod(tip + Vector((0, 0, -0.06)), tip + Vector((0, 0.0, -0.17)), 0.035, 'shade', seg=20, r1=0.17, caps=False)
        self.M('bulbs').rod(tip + Vector((0, 0, -0.09)), tip + Vector((0, 0, -0.15)), 0.03, 'bulb', seg=10)
        self.lights.append(dict(kind='spot', loc=tip + Vector((0, 0, -0.12)), energy=60, color=(1.0, 0.76, 0.48), radius=0.03,
                                target=self.wp(F, x, 4.05, 0.15), spot=math.radians(110), group='exterior'))

    def blade_sign(self):
        F = 'F'
        W = self.W
        sv = self.M('services')
        uc = W - 0.30
        z = 5.55
        # wall plate and two-arm bracket with a scroll brace
        sv.box(*self._wbox(F, uc - 0.08, uc + 0.08, z - 0.75, z + 0.12, 0.02, 0.035), 'iron')
        arm0, arm1 = self.wp(F, uc, z, 0.035), self.wp(F, uc, z, 1.35)
        sv.bar(arm0, arm1, 0.03, 0.04, 'iron', up=(0, 0, 1))
        sv.bar(self.wp(F, uc, z - 0.70, 0.035), self.wp(F, uc, z - 0.02, 0.85), 0.02, 0.025, 'iron')
        ring = [self.wp(F, uc, z - 0.17 + 0.13 * math.sin(a), 0.42 + 0.13 * math.cos(a)) for a in np.linspace(0, 2 * math.pi, 17)]
        sv.tube(ring, 0.008, 'iron', seg=6)
        sv.rod(self.wp(F, uc, z + 0.03, 1.35), self.wp(F, uc, z + 0.06, 1.38), 0.03, 'iron', seg=10, r1=0.004)
        # sign board hanging on S-hooks
        bd0, bd1 = 0.42, 1.28
        top = z - 0.12
        bot = top - 0.62
        for dd in (bd0 + 0.06, bd1 - 0.06):
            sv.rod(self.wp(F, uc, z - 0.02, dd), self.wp(F, uc, top + 0.0, dd), 0.006, 'iron', seg=6)
        bs = self.M('blade')
        bs.box(*self._wbox(F, uc - 0.025, uc + 0.025, bot, top, bd0, bd1), 'sign_board')
        for (a, b, c, d) in ((bd0, bd1, top - 0.03, top), (bd0, bd1, bot, bot + 0.03), (bd0, bd0 + 0.03, bot, top), (bd1 - 0.03, bd1, bot, top)):
            bs.box(*self._wbox(F, uc - 0.035, uc + 0.035, c, d, a, b), 'letters')
        for side in (-1, 1):
            self.text_side(self.shop['blade'], FONT_SERIF, 0.12, uc + side * 0.026, (bd0 + bd1) / 2, (top + bot) / 2 + 0.06, side)
            self.text_side("EST. 1921", FONT_SANS, 0.055, uc + side * 0.026, (bd0 + bd1) / 2, (top + bot) / 2 - 0.13, side)
        self.weather.drip(3, W - 0.38, W - 0.22, z - 0.75, 1.2, 0.5)

    def ac_unit(self):
        ac = self.vt['ac']
        if not ac:
            return
        b, k = ac
        op = next((o for o in self.openings if o['wall'] == 'F' and o['k'] == k and abs((o['u0'] + o['u1']) / 2 - (b + 0.5) * self.bw) < 0.1), None)
        if op is None:
            return
        F = 'F'
        sv = self.M('services')
        uc = (op['u0'] + op['u1']) / 2 + 0.05
        z0 = self.floor_base(k) + 3 * CH
        w, h = 0.66, 0.40
        # sleeve opening exclusion is approximated by the bricks sitting behind the sleeve frame
        sv.box(*self._wbox(F, uc - w / 2 - 0.02, uc + w / 2 + 0.02, z0 - 0.02, z0 + h + 0.02, -0.05, 0.03), 'ac_body')
        sv.box(*self._wbox(F, uc - w / 2, uc + w / 2, z0, z0 + h, 0.0, 0.17), 'ac_body')
        # rear grille louvres
        n = 14
        for i in range(n):
            zz = z0 + 0.03 + (h - 0.06) * (i + 0.5) / n
            sv.box(*self._wbox(F, uc - w / 2 + 0.03, uc + w / 2 - 0.03, zz - 0.004, zz + 0.004, 0.17, 0.178), 'grille')
        # side louvres
        for s in (-1, 1):
            for i in range(6):
                zz = z0 + 0.06 + i * 0.05
                sv.box(*self._wbox(F, uc + s * (w / 2) - 0.002, uc + s * (w / 2) + 0.002, zz, zz + 0.02, 0.03, 0.15), 'grille')
        # support angle brackets
        for s in (-1, 1):
            sv.bar(self.wp(F, uc + s * 0.25, z0 - 0.30, 0.0), self.wp(F, uc + s * 0.25, z0 - 0.01, 0.15), 0.03, 0.005, 'fire_escape', up=(1, 0, 0))
        # condensate drip stain
        fu = uc
        self.weather.drip(1, fu - 0.25, fu + 0.25, z0, 2.4, 0.9, density=2.5, width=(0.01, 0.05))
        self.weather.drip(3, fu - 0.28, fu - 0.22, z0 - 0.3, 1.0, 0.7)
        self.weather.drip(3, fu + 0.22, fu + 0.28, z0 - 0.3, 1.0, 0.7)

    # ---------------------------------------------------------------- interiors
    def build_interiors(self):
        it = self.M('interior')
        R = random.Random(self.seed + 31)
        W, S = self.W, self.S
        DEEP = 4.6
        WT = 0.33
        lit_frac = float(self.vt['interiors_lit'])
        for k in range(1, S + 1):
            z0 = self.floor_base(k)
            zc = z0 + self.SH - 0.28
            # floor, ceiling, back wall, side walls
            it.box((WT, WT, z0 - 0.02), (W - WT, DEEP, z0 + 0.0), 'floor_wood')
            it.box((WT, WT, zc), (W - WT, DEEP, zc + 0.02), 'ceiling')
            # per-bay rooms
            for b in range(self.bays):
                x0 = b * self.bw + (WT if b == 0 else 0.06)
                x1 = (b + 1) * self.bw - (WT if b == self.bays - 1 else 0.06)
                wall_col = R.choice(['wall_a', 'wall_b', 'wall_c', 'wall_d'])
                it.box((x0, DEEP - 0.02, z0), (x1, DEEP, zc), wall_col)
                it.box((x0 - 0.06 if b > 0 else x0 - 0.02, WT, z0), (x0, DEEP, zc), wall_col)
                it.box((x1, WT, z0), (x1 + 0.06 if b < self.bays - 1 else x1 + 0.02, DEEP, zc), wall_col)
                # front inner wall (between windows) visible obliquely
                wu0 = (b + 0.5) * self.bw - 0.525 - 0.10
                wu1 = (b + 0.5) * self.bw + 0.525 + 0.10
                wv0 = z0 + 11 * CH - 0.03
                wv1 = z0 + 37 * CH
                for (aa, bb, cc, dd) in ((x0, wu0, z0, zc), (wu1, x1, z0, zc), (wu0, wu1, z0, wv0), (wu0, wu1, wv1, zc)):
                    if bb > aa and dd > cc:
                        it.box((aa, WT, cc), (bb, WT + 0.01, dd), wall_col)
                self.furnish(it, R, x0, x1, z0, zc, DEEP, k, b)
                lit = R.random() < lit_frac
                self.lights.append(dict(kind='area', loc=Vector(((x0 + x1) / 2, DEEP * 0.55, zc - 0.05)), size=0.5,
                                        energy=(260 if lit else 0), color=R.choice([(1.0, 0.80, 0.58), (1.0, 0.86, 0.68), (0.95, 0.92, 0.85)]),
                                        group='interior', lit=lit))
                self.M('bulbs').box(((x0 + x1) / 2 - 0.18, DEEP * 0.55 - 0.18, zc - 0.03), ((x0 + x1) / 2 + 0.18, DEEP * 0.55 + 0.18, zc), 'bulb' if lit else 'fixture_off')
            # window treatments for this floor
        for i, op in enumerate(self.openings):
            self.treatment(op, random.Random(self.seed * 7 + i))
        # shop interior
        self.shop_interior(R)

    def furnish(self, it, R, x0, x1, z0, zc, D, k, b):
        kind = R.choice(['living', 'office', 'bed', 'living', 'office', 'store'])
        cx = (x0 + x1) / 2
        if kind == 'living':
            # sofa against the back wall, picture, floor lamp, bookshelf on a side wall
            sc = R.choice(['fab_a', 'fab_b', 'fab_c'])
            it.box((cx - 1.0, D - 0.95, z0), (cx + 1.0, D - 0.02, z0 + 0.42), sc)
            it.box((cx - 1.0, D - 0.25, z0 + 0.42), (cx + 1.0, D - 0.05, z0 + 0.85), sc)
            for s in (-1, 1):
                it.box((cx + s * 1.0 - 0.12 * (s > 0), D - 0.95, z0), (cx + s * 1.0 + 0.12 * (s < 0) * 0 + (0.12 if s > 0 else 0), D - 0.05, z0 + 0.62), sc)
            it.box((cx - 0.45, D - 0.03, z0 + 1.35), (cx + 0.45, D - 0.0, z0 + 1.95), 'frame_dark')
            it.box((cx - 0.40, D - 0.035, z0 + 1.40), (cx + 0.40, D - 0.03, z0 + 1.90), R.choice(['art_a', 'art_b']))
            it.box((cx - 0.5, D - 2.1, z0), (cx + 0.5, D - 1.6, z0 + 0.42), 'wood_dark')
            it.box((x0 + 0.02, D - 2.5, z0), (x0 + 0.35, D - 0.6, z0 + 2.1), 'wood_mid')
            for sh in range(5):
                zz = z0 + 0.35 + sh * 0.38
                for bk in range(int(1.8 / 0.06)):
                    if R.random() < 0.8:
                        h = R.uniform(0.18, 0.30)
                        yy = D - 2.45 + bk * 0.06
                        it.box((x0 + 0.06, yy, zz), (x0 + 0.30, yy + 0.05, zz + h), R.choice(['book_a', 'book_b', 'book_c', 'book_d']))
            lx = x1 - 0.4
            it.rod((lx, D - 0.6, z0), (lx, D - 0.6, z0 + 1.55), 0.012, 'brass')
            it.rod((lx, D - 0.6, z0 + 1.45), (lx, D - 0.6, z0 + 1.75), 0.18, 'lampshade', seg=16, r1=0.12)
            if R.random() < 0.5:
                self.lights.append(dict(kind='point', loc=Vector((lx, D - 0.6, z0 + 1.6)), energy=20, color=(1.0, 0.7, 0.4), radius=0.08, group='interior', lit=True))
        elif kind == 'office':
            for dx in (-0.75, 0.75):
                it.box((cx + dx - 0.6, D - 1.6, z0 + 0.72), (cx + dx + 0.6, D - 0.85, z0 + 0.75), 'wood_light')
                it.box((cx + dx - 0.58, D - 1.55, z0), (cx + dx - 0.54, D - 0.9, z0 + 0.72), 'steel')
                it.box((cx + dx + 0.54, D - 1.55, z0), (cx + dx + 0.58, D - 0.9, z0 + 0.72), 'steel')
                it.box((cx + dx - 0.28, D - 1.05, z0 + 0.75), (cx + dx + 0.28, D - 1.02, z0 + 1.10), 'screen')
                it.box((cx + dx - 0.25, D - 2.1, z0 + 0.45), (cx + dx + 0.25, D - 1.65, z0 + 0.52), 'fab_c')
                it.box((cx + dx - 0.25, D - 2.15, z0 + 0.52), (cx + dx + 0.25, D - 2.08, z0 + 1.05), 'fab_c')
                it.rod((cx + dx, D - 1.9, z0), (cx + dx, D - 1.9, z0 + 0.45), 0.025, 'steel')
            for f in range(3):
                it.box((x1 - 0.5, D - 0.6 - f * 0.5, z0), (x1 - 0.02, D - 0.15 - f * 0.5, z0 + 1.3), 'steel_cab')
            it.box((cx - 1.2, D - 0.03, z0 + 1.2), (cx + 1.2, D - 0.0, z0 + 2.1), 'board')
        elif kind == 'bed':
            it.box((cx - 0.8, D - 2.1, z0), (cx + 0.8, D - 0.05, z0 + 0.5), 'fab_d')
            it.box((cx - 0.8, D - 0.12, z0), (cx + 0.8, D - 0.02, z0 + 1.1), 'wood_dark')
            it.box((cx - 0.7, D - 0.55, z0 + 0.5), (cx + 0.7, D - 0.15, z0 + 0.62), 'fab_e')
            it.box((x0 + 0.05, D - 3.2, z0), (x0 + 0.55, D - 2.2, z0 + 1.1), 'wood_mid')
            it.box((x0 + 0.1, D - 3.0, z0 + 1.1), (x0 + 0.12, D - 2.5, z0 + 1.7), 'mirror')
        else:
            for _ in range(R.randint(5, 10)):
                bx, by = R.uniform(x0 + 0.3, x1 - 0.8), R.uniform(D - 2.5, D - 0.6)
                s = R.uniform(0.35, 0.6)
                zz = z0
                for st in range(R.randint(1, 3)):
                    it.box((bx, by, zz), (bx + s, by + s * 0.8, zz + s * 0.7), 'cardboard')
                    zz += s * 0.7
                    s *= 0.9

    def treatment(self, op, R):
        wall, u0, u1, v0, v1 = op['wall'], op['u0'], op['u1'], op['v0'], op['v1']
        tr = self.M('treat')
        kind = R.choice(['blind', 'blind', 'curtain', 'curtain', 'venetian', 'none'])
        din = -0.36
        h = v1 - v0
        if kind == 'blind':
            low = v1 - h * R.uniform(0.12, 0.85)
            tr.box(*self._wbox(wall, u0 + 0.02, u1 - 0.02, low, v1 - 0.02, din - 0.004, din), R.choice(['shade_white', 'shade_cream', 'shade_green']))
            tr.box(*self._wbox(wall, u0 + 0.02, u1 - 0.02, low - 0.02, low, din - 0.015, din + 0.005), 'wood_light')
            tr.rod(self.wp(wall, (u0 + u1) / 2, low - 0.02, din - 0.01), self.wp(wall, (u0 + u1) / 2, low - 0.14, din - 0.01), 0.002, 'cord', seg=4)
            tr.rod(self.wp(wall, u0 + 0.02, v1 - 0.04, din - 0.02), self.wp(wall, u1 - 0.02, v1 - 0.04, din - 0.02), 0.022, 'shade_white', seg=10)
        elif kind == 'curtain':
            mat = R.choice(['fab_a', 'fab_e', 'curtain_sheer', 'curtain_sheer', 'fab_b'])
            for side in (0, 1):
                if R.random() < 0.25:
                    continue
                open_ = R.uniform(0.15, 0.5)
                a = u0 - 0.10 if side == 0 else u1 - (u1 - u0) * open_
                b = u0 + (u1 - u0) * open_ if side == 0 else u1 + 0.10
                n = 24
                rows = []
                bottom = v0 - 0.05 if R.random() < 0.6 else v0 + 0.1
                for z in (bottom, v1 + 0.10):
                    row = []
                    for i in range(n + 1):
                        t = i / n
                        uu = a + (b - a) * t
                        d = din - 0.06 - 0.035 * (0.5 + 0.5 * math.sin(t * math.pi * 2 * (b - a) / 0.11))
                        row.append(tr.add_v(self.wp(wall, uu, z, d)))
                    rows.append(row)
                for i in range(n):
                    tr.face([rows[0][i], rows[0][i + 1], rows[1][i + 1], rows[1][i]], mat)
            tr.rod(self.wp(wall, u0 - 0.15, v1 + 0.12, din - 0.07), self.wp(wall, u1 + 0.15, v1 + 0.12, din - 0.07), 0.01, 'brass', seg=6)
        elif kind == 'venetian':
            low = v1 - h * R.uniform(0.3, 0.95)
            tilt = R.uniform(-0.6, 0.6)
            z = v1 - 0.05
            while z > low:
                c = self.wp(wall, (u0 + u1) / 2, z, din - 0.02)
                ax = self.wvec(wall, (u1 - u0 - 0.04) / 2, 0, 0)
                ay = self.wvec(wall, 0, math.sin(tilt) * 0.0125, math.cos(tilt) * 0.0125)
                az = self.wvec(wall, 0, math.cos(tilt) * 0.0006, -math.sin(tilt) * 0.0006)
                tr.obox(c, ax, ay, az, R.choice(['shade_white']))
                z -= 0.022
            tr.box(*self._wbox(wall, u0 + 0.02, u1 - 0.02, low - 0.02, low, din - 0.035, din - 0.005), 'shade_white')
        # plants / objects on some interior sills
        if R.random() < 0.3:
            uu = R.uniform(u0 + 0.15, u1 - 0.15)
            c = self.wp(wall, uu, v0, -0.27)
            tr.rod(c, c + Vector((0, 0, 0.14)), 0.06, R.choice(['terracotta', 'pot_white']), seg=12, r1=0.075)
            for _ in range(6):
                a = R.uniform(0, 6.28)
                tip = c + Vector((math.cos(a) * 0.12, math.sin(a) * 0.06, R.uniform(0.22, 0.38)))
                tr.rod(c + Vector((0, 0, 0.13)), tip, 0.005, 'leaf', seg=4)
                tr.obox(tip, Vector((0.04, 0, 0)), Vector((0, 0.025, 0)), Vector((0, 0, 0.003)), 'leaf')

    def shop_interior(self, R):
        it = self.M('shop_in')
        W, bw = self.W, self.bw
        x0, x1 = bw + 0.2, W - 0.6
        D = 6.5
        it.box((x0, -0.0, -0.02), (x1, D, 0.0), 'shop_floor')
        it.box((x0, 0.1, 3.55), (x1, D, 3.6), 'tin_ceiling')
        it.box((x0, D - 0.05, 0), (x1, D, 3.6), 'wall_shop')
        it.box((x0 - 0.05, 0.1, 0), (x0, D, 3.6), 'wall_shop')
        it.box((x1, 0.1, 0), (x1 + 0.05, D, 3.6), 'wall_shop')
        # back shelving with goods
        sh_z = [0.35, 0.80, 1.25, 1.70, 2.15]
        it.box((x0 + 0.1, D - 0.45, 0), (x1 - 0.1, D - 0.05, 0.3), 'wood_dark')
        for z in sh_z:
            it.box((x0 + 0.1, D - 0.45, z - 0.03), (x1 - 0.1, D - 0.05, z), 'wood_mid')
            x = x0 + 0.15
            while x < x1 - 0.25:
                w = R.uniform(0.07, 0.18)
                h = R.uniform(0.12, 0.38)
                col = R.choice(GOODS)
                if R.random() < 0.5:
                    it.box((x, D - 0.40, z), (x + w, D - 0.12, z + h), 'goods', cell=col)
                else:
                    it.rod((x + w / 2, D - 0.25, z), (x + w / 2, D - 0.25, z + h * 0.8), w / 2, 'goods', seg=10, cell=col)
                x += w + R.uniform(0.005, 0.03)
        # counter with glass case, register
        cx0, cx1 = x0 + 0.6, x0 + 3.6
        it.box((cx0, 3.1, 0), (cx1, 3.75, 0.95), 'wood_dark')
        it.box((cx0, 3.1, 0.95), (cx1, 3.8, 0.99), 'marble')
        it.box((cx0 + 0.6, 3.3, 0.99), (cx0 + 0.95, 3.6, 1.2), 'steel')
        # display window goods: tiered stands with produce
        for (a, c) in getattr(self, 'displays', []):
            it.box((a + 0.05, 0.16, 0.0), (c - 0.05, 0.95, 0.62), 'wood_mid')
            for tier, (y0, h) in enumerate(((0.22, 0.62), (0.55, 0.9))):
                it.box((a + 0.15, y0, h - 0.03), (c - 0.15, y0 + 0.35, h), 'wood_light')
                x = a + 0.22
                while x < c - 0.3:
                    col = R.choice(GOODS)
                    kind = self.vt['shop']
                    if kind == 'bakery':
                        # loaves: squashed spheres approximated by bevelled boxes; cakes as cylinders
                        rr = R.random()
                        if rr < 0.35:
                            # basket of long loaves
                            it.rod((x + 0.15, y0 + 0.17, h), (x + 0.15, y0 + 0.17, h + 0.12), 0.15, 'wicker', seg=16, r1=0.17)
                            for q in range(R.randint(3, 6)):
                                a0 = R.uniform(-0.5, 0.5)
                                c0 = Vector((x + 0.15, y0 + 0.17, h + 0.12))
                                d0 = Vector((math.cos(a0) * 0.18, math.sin(a0) * 0.10, R.uniform(0.15, 0.3)))
                                it.rod(c0 - d0 * 0.6, c0 + d0, R.uniform(0.028, 0.04), 'bread', seg=10)
                            x += 0.38
                        elif rr < 0.7:
                            for q in range(R.randint(2, 4)):
                                rr2 = R.uniform(0.065, 0.09)
                                yy = y0 + R.uniform(0.1, 0.25)
                                it.rod((x + rr2, yy, h), (x + rr2, yy, h + 0.04), rr2, 'bread', seg=14, r1=rr2 * 0.95)
                                it.rod((x + rr2, yy, h + 0.04), (x + rr2, yy, h + 0.085), rr2 * 0.95, 'bread', seg=14, r1=rr2 * 0.45)
                                x += 2 * rr2 + 0.02
                            x += 0.04
                        elif rr < 0.8:
                            l = R.uniform(0.22, 0.32)
                            for q in range(3):
                                it.rod((x, y0 + 0.08 + q * 0.09, h + 0.04), (x + l, y0 + 0.08 + q * 0.09, h + 0.04), 0.04, 'bread', seg=10)
                            x += l + 0.06
                        else:
                            r = R.uniform(0.09, 0.14)
                            it.rod((x + r, y0 + 0.17, h), (x + r, y0 + 0.17, h + 0.015), r + 0.03, 'pot_white', seg=16)
                            it.rod((x + r, y0 + 0.17, h + 0.015), (x + r, y0 + 0.17, h + R.uniform(0.08, 0.14)), r, 'cake', seg=16, cell=col)
                            x += 2 * r + 0.08
                    else:
                        w = R.uniform(0.08, 0.2)
                        hh = R.uniform(0.1, 0.3)
                        it.box((x, y0 + 0.08, h), (x + w, y0 + 0.25, h + hh), 'goods', cell=col)
                        x += w + 0.04
        self.lights.append(dict(kind='area', loc=Vector(((x0 + x1) / 2, 3.2, 3.5)), size=4.0, energy=160, color=(1.0, 0.86, 0.68), group='shop', lit=True))
        # pendant lights
        for xx in np.linspace(x0 + 0.9, x1 - 0.9, 4):
            it.rod((xx, 2.2, 3.55), (xx, 2.2, 2.75), 0.004, 'iron', seg=4)
            it.rod((xx, 2.2, 2.75), (xx, 2.2, 2.55), 0.04, 'shade', seg=16, r1=0.22, caps=False)
            self.M('bulbs').rod((xx, 2.2, 2.63), (xx, 2.2, 2.56), 0.05, 'bulb', seg=10)
            self.lights.append(dict(kind='point', loc=Vector((xx, 2.2, 2.6)), energy=90, color=(1.0, 0.78, 0.5), radius=0.05, group='shop', lit=True))

    # ---------------------------------------------------------------- text
    def text(self, s, font, size, wall, u, v, d, depth, mat, key, width_max=None):
        cu = bpy.data.curves.new("tmp_txt", 'FONT')
        cu.body = s
        try:
            cu.font = bpy.data.fonts.load(font, check_existing=True)
        except Exception:
            pass
        cu.size = size
        cu.align_x = 'CENTER'
        cu.align_y = 'CENTER'
        cu.extrude = depth / 2 if depth > 0 else 0.0
        cu.bevel_depth = min(0.002, depth / 4) if depth > 0 else 0.0
        cu.bevel_resolution = 1
        cu.resolution_u = 4
        ob = bpy.data.objects.new("tmp_txt", cu)
        bpy.context.scene.collection.objects.link(ob)
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        bpy.data.objects.remove(ob)
        bpy.data.curves.remove(cu)
        co = [Vector(vv.co) for vv in me.vertices]
        if not co:
            return
        xs = [c.x for c in co]
        sc = 1.0
        if width_max and (max(xs) - min(xs)) > width_max:
            sc = width_max / (max(xs) - min(xs))
        mb = self.M(key)
        if key == 'letters_flat':
            mb.closed = False
        base = len(mb.v)
        for c in co:
            # font space: x right, y up, z out (toward viewer)
            mb.add_v(self.wp(wall, u + c.x * sc, v + c.y * sc, d + (c.z + depth / 2 if depth > 0 else 0.0) + 0.0005))
        for p in me.polygons:
            mb.face([base + i for i in p.vertices], mat)
        bpy.data.meshes.remove(me)

    def text_side(self, s, font, size, x, yc, zc, side):
        """Text on the blade sign (plane x = const, facing +X (side=1) or -X (side=-1))."""
        cu = bpy.data.curves.new("tmp_txt", 'FONT')
        cu.body = s
        cu.font = bpy.data.fonts.load(font, check_existing=True)
        cu.size = size
        cu.align_x = 'CENTER'
        cu.align_y = 'CENTER'
        cu.extrude = 0.002
        ob = bpy.data.objects.new("tmp_txt", cu)
        bpy.context.scene.collection.objects.link(ob)
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        bpy.data.objects.remove(ob)
        bpy.data.curves.remove(cu)
        mb = self.M('letters')
        base = len(mb.v)
        for vv in me.vertices:
            c = vv.co
            # facing +X: text x maps to +Y; facing -X: text x maps to -Y
            mb.add_v((x + side * (c.z + 0.002), yc + side * c.x, zc + c.y))
        for p in me.polygons:
            mb.face([base + i for i in p.vertices], 'letters')
        bpy.data.meshes.remove(me)

    # ---------------------------------------------------------------- weathering
    def paint_weather(self):
        Wm = self.weather
        rng = Wm.rng
        for op in self.openings:
            fu0 = self.uoff(op['wall']) + op['u0']
            fu1 = self.uoff(op['wall']) + op['u1']
            v0 = op['v0'] - 0.10
            # streak curtain under the sill, heavier at the sill ends
            Wm.drip(1, fu0 - 0.05, fu1 + 0.05, v0, rng.uniform(0.8, 1.9), 0.65, density=1.6)
            Wm.drip(1, fu0 + 0.02, fu1 - 0.02, v0, rng.uniform(1.0, 2.2), 0.35, density=0.35, width=(0.05, 0.14))
            for e in (fu0 - 0.07, fu1 + 0.07):
                Wm.drip(1, e - 0.04, e + 0.04, v0, rng.uniform(1.5, 2.6), 0.9, density=1.5, width=(0.01, 0.025))
            # soot above window heads (sheltered under the lintel/arch is less, above is dirty)
            Wm.blob(0, (fu0 + fu1) / 2, op['v1'] + 0.45, (fu1 - fu0) * 0.6, 0.25, 0.35)
            if rng.random() < 0.4:
                e = rng.uniform(fu0, fu1)
                Wm.drip(2, e - 0.15, e + 0.15, v0 - 0.05, rng.uniform(0.5, 1.2), 0.45, density=1.0, width=(0.01, 0.03))
        # efflorescence near the shop cornice (splash zone) and under the parapet
        for _ in range(7):
            e = rng.uniform(0, self.U_TOT)
            Wm.drip(2, e - rng.uniform(0.1, 0.4), e + rng.uniform(0.1, 0.4), self.GH + rng.uniform(0.6, 1.4), rng.uniform(0.5, 1.2), 0.5, density=1.2, width=(0.01, 0.04))
        for _ in range(5):
            Wm.blob(2, rng.uniform(0, self.U_TOT), self.ZTOP - rng.uniform(0.1, 0.5), rng.uniform(0.3, 0.8), 0.2, 0.6)
        # dirt from the belt course
        Wm.drip(1, 0, self.U_TOT, self.GEO_TOP, 1.4, 0.45, density=1.5)
        # sooty upper wall, darker toward the parapet
        Wm.band(0, self.ZC - 3.5, self.ZC, 0.25, falloff_up=False)
        Wm.band(0, self.ZP, self.ZTOP, 0.45, falloff_up=False)
        # splash/dirt band above the shop cornice
        Wm.band(0, self.GH, self.GH + 0.5, 0.35)
        self.weather_img = Wm.image(self.vt['name'] + "_weather")
        self.weather_img.use_fake_user = True

    # ---------------------------------------------------------------- materials
    def make_materials(self):
        v = self.vt
        pal = v['brick']
        pal = PALETTES[pal] if isinstance(pal, str) else pal
        trim = srgb(TRIMS.get(v['trim'], TRIMS['black']))
        sign = srgb(self.shop['sign_col'])
        awn = srgb(self.shop['awning'])
        tag = v['name']
        Mt = {}
        bc = self.brick_color_group(pal, tag)
        wg = self.weather_group(tag)
        Mt['brick'] = self.mat_brick_geo(bc, wg, tag)
        Mt['brickfield'] = self.mat_brick_field(bc, wg, tag, use_mask=True)
        Mt['reveal'] = self.mat_brick_field(bc, wg, tag + "_rev", use_mask=False)
        Mt['mortar'] = self.mat_simple(tag + "_mortar", srgb((132, 124, 112)), 0.9, wg=wg, noise=0.25)
        Mt['stone'] = self.mat_stone(tag + "_stone", srgb((150, 138, 118)), wg)
        Mt['granite'] = self.mat_stone(tag + "_granite", srgb((96, 94, 92)), wg, rough=0.55, speck=True)
        Mt['paint'] = self.mat_paint(tag + "_winpaint", trim, wg, chip=0.35)
        Mt['putty'] = self.mat_simple(tag + "_putty", srgb((122, 116, 100)), 0.8)
        Mt['glass'] = self.mat_glass(tag + "_glass")
        Mt['prism_glass'] = self.mat_glass(tag + "_prism", prism=True)
        Mt['shop_paint'] = self.mat_paint(tag + "_shoppaint", sign if v['trim'] != 'cream' else trim, wg, chip=0.6, ground=True)
        Mt['sign_board'] = self.mat_paint(tag + "_signboard", sign, wg, chip=0.25, gloss=True)
        Mt['letters'] = self.mat_metal(tag + "_gold", srgb((222, 170, 92)) if self.shop['letter'] == 'gold' else srgb((230, 222, 200)),
                                       0.28, metal=(1.0 if self.shop['letter'] == 'gold' else 0.0))
        Mt['letters_white'] = self.mat_simple(tag + "_lettwhite", srgb((236, 230, 214)), 0.6)
        Mt['brass'] = self.mat_metal(tag + "_brass", srgb((190, 150, 90)), 0.32, tarnish=True)
        Mt['steel'] = self.mat_metal(tag + "_steel", srgb((150, 152, 156)), 0.35)
        Mt['iron'] = self.mat_paint(tag + "_iron", srgb((22, 22, 22)), wg, chip=0.5, rust=True)
        Mt['fire_escape'] = self.mat_paint(tag + "_fe", srgb((24, 24, 23)), wg, chip=0.7, rust=True)
        Mt['door'] = self.mat_paint(tag + "_door", trim, wg, chip=0.3, gloss=True)
        Mt['tile'] = self.mat_tile(tag + "_tile")
        Mt['awning'] = self.mat_fabric(tag + "_awning", awn, outdoor=True)
        Mt['cornice'] = self.mat_paint(tag + "_cornice", srgb((96, 90, 80)) if v['trim'] != 'cream' else srgb((170, 160, 140)), wg, chip=0.5, rust=True)
        Mt['downpipe'] = self.mat_paint(tag + "_pipe", srgb((70, 66, 60)), wg, chip=0.3, rust=True)
        Mt['conduit'] = self.mat_metal(tag + "_conduit", srgb((156, 158, 160)), 0.45, galv=True)
        Mt['grille'] = self.mat_paint(tag + "_grille", srgb((60, 58, 54)), wg, chip=0.4, rust=True)
        Mt['ac_body'] = self.mat_paint(tag + "_ac", srgb((196, 188, 168)), wg, chip=0.2, rust=True)
        Mt['lantern_glass'] = self.mat_emit_glass(tag + "_lantglass")
        Mt['bulb'] = self.mat_emit(tag + "_bulb", (1.0, 0.75, 0.45), 6.0)
        Mt['fixture_off'] = self.mat_simple(tag + "_fixoff", srgb((220, 216, 205)), 0.4)
        Mt['shade'] = self.mat_metal(tag + "_shade", srgb((30, 48, 38)), 0.4, metal=0.0, two_tone=True)
        Mt['void'] = self.mat_simple(tag + "_void", (0.01, 0.01, 0.01, 1), 0.9)
        Mt['plaster'] = self.mat_simple(tag + "_plaster", srgb((210, 202, 186)), 0.8)
        Mt['terracotta'] = self.mat_simple(tag + "_terra", srgb((168, 88, 58)), 0.8, noise=0.2)
        Mt['soil'] = self.mat_simple(tag + "_soil", srgb((40, 30, 24)), 1.0)
        Mt['leaf'] = self.mat_simple(tag + "_leaf", srgb((52, 92, 40)), 0.55, noise=0.4)
        Mt['pot_white'] = self.mat_simple(tag + "_potw", srgb((226, 222, 212)), 0.3)
        Mt['blade'] = Mt['sign_board']
        # interiors
        for nm, c in (('wall_a', (196, 186, 164)), ('wall_b', (170, 182, 172)), ('wall_c', (210, 196, 176)), ('wall_d', (150, 132, 116)),
                      ('wall_hall', (120, 104, 84)), ('wall_shop', (190, 176, 150)), ('ceiling', (214, 208, 196))):
            Mt[nm] = self.mat_simple(tag + "_" + nm, srgb(c), 0.85, noise=0.12)
        Mt['floor_wood'] = self.mat_wood(tag + "_floorwood", srgb((120, 78, 46)))
        Mt['shop_floor'] = self.mat_tile(tag + "_shopfloor", checker=True)
        Mt['tin_ceiling'] = self.mat_simple(tag + "_tin", srgb((200, 196, 184)), 0.35)
        for nm, c in (('fab_a', (110, 40, 36)), ('fab_b', (60, 76, 96)), ('fab_c', (58, 58, 60)), ('fab_d', (180, 170, 150)), ('fab_e', (210, 200, 180))):
            Mt[nm] = self.mat_fabric(tag + "_" + nm, srgb(c))
        Mt['curtain_sheer'] = self.mat_fabric(tag + "_sheer", srgb((236, 230, 214)), sheer=True)
        for nm, c in (('shade_white', (226, 220, 204)), ('shade_cream', (214, 196, 160)), ('shade_green', (70, 96, 70))):
            Mt[nm] = self.mat_fabric(tag + "_" + nm, srgb(c), sheer=True)
        for nm, c, r in (('wood_dark', (60, 36, 24), 0.45), ('wood_mid', (110, 72, 42), 0.5), ('wood_light', (170, 130, 88), 0.5),
                         ('frame_dark', (30, 24, 18), 0.4), ('cardboard', (150, 112, 70), 0.9), ('steel_cab', (110, 114, 110), 0.5),
                         ('board', (230, 230, 226), 0.3), ('screen', (12, 14, 16), 0.15), ('cord', (220, 220, 210), 0.7), ('marble', (226, 222, 214), 0.2),
                         ('mirror', (220, 220, 220), 0.03), ('lampshade', (230, 210, 170), 0.8), ('book_a', (110, 30, 26), 0.6),
                         ('book_b', (30, 50, 80), 0.6), ('book_c', (190, 170, 130), 0.6), ('book_d', (40, 70, 50), 0.6)):
            Mt[nm] = self.mat_simple(tag + "_" + nm, srgb(c), r, noise=0.15)
        Mt['art_a'] = self.mat_simple(tag + "_art_a", srgb((180, 120, 60)), 0.6, noise=1.0)
        Mt['art_b'] = self.mat_simple(tag + "_art_b", srgb((70, 110, 140)), 0.6, noise=1.0)
        Mt['goods'] = self.mat_attr(tag + "_goods", 0.45)
        Mt['bread'] = self.mat_bread(tag + "_bread")
        Mt['wicker'] = self.mat_simple(tag + "_wicker", srgb((140, 100, 56)), 0.8, noise=0.6)
        Mt['cake'] = self.mat_attr(tag + "_cake", 0.5, pastel=True)
        self.materials = Mt

    def brick_color_group(self, pal, tag):
        """Per-brick colour / roughness / normal.  Inputs: Cell (i, j, kind), Pos (object coords), Local (lu, lv in metres
        from the cell's lower-left corner incl. mortar), Scan (1 = use the scanned-face atlas).  The palette sets each
        brick's colour; a face cut from the CC0 red_brick scan (tex_gen/brick_atlas_*) supplies clay texture, pores, fire
        flashing, chips and arrises; low-frequency cell noise adds batch / scaffold-lift variation."""
        g = bpy.data.node_groups.new(tag + "_BrickColor", 'ShaderNodeTree')
        for nm, st in (("Cell", 'NodeSocketVector'), ("Pos", 'NodeSocketVector'), ("Local", 'NodeSocketVector'), ("Scan", 'NodeSocketFloat')):
            g.interface.new_socket(nm, in_out='INPUT', socket_type=st)
        g.interface.new_socket("Color", in_out='OUTPUT', socket_type='NodeSocketColor')
        g.interface.new_socket("Rough", in_out='OUTPUT', socket_type='NodeSocketFloat')
        g.interface.new_socket("Height", in_out='OUTPUT', socket_type='NodeSocketFloat')
        g.interface.new_socket("Normal", in_out='OUTPUT', socket_type='NodeSocketVector')
        T = NT(g)
        gi = T.n('NodeGroupInput')
        go = T.n('NodeGroupOutput')
        cellv = gi.outputs['Cell']
        wn = T.n('ShaderNodeTexWhiteNoise', {'Vector': cellv}, noise_dimensions='3D')
        wn2 = T.n('ShaderNodeTexWhiteNoise', {'Vector': T.vmath('ADD', cellv, (17.3, 5.1, 2.2))}, noise_dimensions='3D')
        wn3 = T.n('ShaderNodeTexWhiteNoise', {'Vector': T.vmath('ADD', cellv, (3.7, 41.9, 8.4))}, noise_dimensions='3D')
        n = len(pal)
        stops = []
        weights = [1.0] * (n - 1) + [0.25]
        tot = sum(weights)
        acc = 0.0
        for c, w in zip(pal, weights):
            stops.append((acc / tot, srgb(c)))
            acc += w
        col = T.ramp(wn.outputs['Value'], stops, interp='CONSTANT')
        sep = T.xyz(wn.outputs['Color'])
        # batch / lift variation: neighbouring bricks correlate (bricks came from the same pallet, laid the same day)
        cs = T.xyz(cellv)
        batch = T.noise(T.comb(T.math('MULTIPLY', cs[0], 0.11), T.math('MULTIPLY', cs[1], 0.07), 0.0), 1.0, 2, 0.5)
        lift = T.n('ShaderNodeTexWhiteNoise', {'Vector': T.comb(T.math('FLOOR', T.math('DIVIDE', cs[1], 13.0)), 0.5, 0.5)}, noise_dimensions='3D')
        bright = T.math('MULTIPLY', T.remap(sep[0], 0, 1, 0.80, 1.10), T.remap(batch.outputs['Factor'], 0.3, 0.7, 0.86, 1.10))
        bright = T.math('MULTIPLY', bright, T.remap(lift.outputs['Value'], 0, 1, 0.95, 1.04))
        hue = T.n('ShaderNodeHueSaturation', {'Hue': T.remap(sep[1], 0, 1, 0.493, 0.507), 'Saturation': T.remap(sep[2], 0, 1, 0.80, 1.0),
                                               'Value': bright, 'Color': col})
        # ---- scanned face from the atlas
        loc = T.xyz(gi.outputs['Local'])
        fu = T.remap(loc[0], MORT, CL - MORT, 0.004, 0.996)
        fv = T.remap(loc[1], MORT, CH - MORT, 0.01, 0.99)
        flip = T.math('GREATER_THAN', wn3.outputs['Value'], 0.5)
        fu = T.mixf(flip, fu, T.math('SUBTRACT', 1.0, fu))
        fv = T.mixf(flip, fv, T.math('SUBTRACT', 1.0, fv))
        k = T.math('FLOOR', T.math('MULTIPLY', T.xyz(wn3.outputs['Color'])[0], 63.999))
        tx = T.math('FLOORED_MODULO', k, 8.0)
        ty = T.math('FLOOR', T.math('DIVIDE', k, 8.0))
        auv = T.comb(T.math('DIVIDE', T.math('ADD', tx, fu), 8.0), T.math('DIVIDE', T.math('ADD', ty, fv), 8.0), 0.0)
        ia = T.n('ShaderNodeTexImage', {'Vector': auv}, image=tex_image("tex_gen/brick_atlas_detail.png"), interpolation='Linear', extension='EXTEND')
        inn = T.n('ShaderNodeTexImage', {'Vector': auv}, image=tex_image("tex_gen/brick_atlas_nor_gl.png"), interpolation='Linear', extension='EXTEND')
        ir = T.n('ShaderNodeTexImage', {'Vector': auv}, image=tex_image("tex_gen/brick_atlas_rough.png"), interpolation='Linear', extension='EXTEND')
        scan = gi.outputs['Scan']
        det = T.mix(scan, (0.5, 0.5, 0.5, 1), ia.outputs['Color'])
        det = T.vmath('POWER', T.vmath('SCALE', det, scale=2.0), (1.35, 1.35, 1.35))
        pos = gi.outputs['Pos']
        mott = T.noise(pos, 38.0, 6, 0.6)
        m1 = T.remap(mott.outputs['Factor'], 0.3, 0.7, 0.94, 1.05)
        c1 = T.mul_col(hue.outputs[0], T.comb(m1, m1, m1))
        c2 = T.mul_col(c1, det)
        # a century of city air: a grey-brown film, uneven, heavier on some bricks (more porous) than others
        pat = T.noise(pos, 3.0, 4, 0.6)
        pf = T.math('ADD', T.remap(pat.outputs['Factor'], 0.3, 0.7, 0.10, 0.30), T.remap(wn2.outputs['Value'], 0, 1, -0.06, 0.10))
        c2 = T.mix(pf, T.mul_col(c2, (0.86, 0.86, 0.86, 1)), srgb((88, 76, 66)))
        T.L.new(c2, go.inputs['Color'])
        rr = T.math('ADD', T.remap(ir.outputs['Color'], 0.5, 1.0, 0.70, 0.93), T.remap(wn2.outputs['Value'], 0, 1, -0.04, 0.04))
        T.L.new(T.mixf(scan, T.remap(wn2.outputs['Value'], 0, 1, 0.74, 0.9), rr), go.inputs['Rough'])
        T.L.new(T.math('MULTIPLY', mott.outputs['Factor'], 0.4), go.inputs['Height'])
        # tangent-space (OpenGL) normal -> world: T = z x N, B = N x T
        geo = T.n('ShaderNodeNewGeometry')
        N = geo.outputs['Normal']
        Tn = T.vmath('NORMALIZE', T.vmath('CROSS_PRODUCT', (0.0, 0.0, 1.0), N))
        Bn = T.vmath('CROSS_PRODUCT', N, Tn)
        ns = T.xyz(inn.outputs['Color'])
        sgn = T.mixf(flip, 1.0, -1.0)
        nx = T.math('MULTIPLY', T.math('MULTIPLY', T.math('SUBTRACT', T.math('MULTIPLY', ns[0], 2.0), 1.0), sgn), 1.0)
        ny = T.math('MULTIPLY', T.math('MULTIPLY', T.math('SUBTRACT', T.math('MULTIPLY', ns[1], 2.0), 1.0), sgn), 1.0)
        nw = T.vmath('ADD', T.vmath('ADD', T.vmath('SCALE', Tn, scale=nx), T.vmath('SCALE', Bn, scale=ny)), N)
        nw = T.vmath('NORMALIZE', nw)
        nrm = T.n('ShaderNodeMix', data_type='VECTOR')
        T.set(nrm.inputs[0], scan)
        T.set(nrm.inputs[4], N)
        T.set(nrm.inputs[5], nw)
        T.L.new(nrm.outputs[1], go.inputs['Normal'])
        return g

    def weather_group(self, tag):
        """Inputs Color, Rough, Strength; uses object coords to look up the weathering map."""
        g = bpy.data.node_groups.new(tag + "_Weather", 'ShaderNodeTree')
        for nm, st in (("Color", 'NodeSocketColor'), ("Rough", 'NodeSocketFloat'), ("Strength", 'NodeSocketFloat')):
            g.interface.new_socket(nm, in_out='INPUT', socket_type=st)
        g.interface.new_socket("Color", in_out='OUTPUT', socket_type='NodeSocketColor')
        g.interface.new_socket("Rough", in_out='OUTPUT', socket_type='NodeSocketFloat')
        g.interface.new_socket("UV", in_out='OUTPUT', socket_type='NodeSocketVector')
        T = NT(g)
        gi = T.n('NodeGroupInput')
        go = T.n('NodeGroupOutput')
        tc = T.n('ShaderNodeTexCoord')
        p = T.xyz(tc.outputs['Object'])
        onret = T.math('GREATER_THAN', p[0], self.W - 0.06)
        u = T.math('ADD', T.math('MINIMUM', p[0], self.W), T.math('MULTIPLY', onret, T.math('MAXIMUM', p[1], 0.0)))
        uv = T.comb(T.math('DIVIDE', u, self.weather.nx * Weather.RES), T.math('DIVIDE', p[2], self.weather.ny * Weather.RES), 0.0)
        T.L.new(T.comb(u, p[2], 0.0), go.inputs['UV'])
        im = T.n('ShaderNodeTexImage', {'Vector': uv}, image=self.weather_img, extension='EXTEND', interpolation='Linear')
        sep = T.n('ShaderNodeSeparateColor', {'Color': im.outputs['Color']})
        alpha = im.outputs['Alpha']
        nz = T.noise(tc.outputs['Object'], 9.0, 4, 0.6)
        nzf = T.remap(nz.outputs['Factor'], 0.3, 0.7, 0.55, 1.35)
        S = T.math('MULTIPLY', gi.outputs['Strength'], 2.2)
        soot = T.math('MULTIPLY', T.math('MULTIPLY', sep.outputs[0], nzf), S, clamp=True)
        streak = T.math('MULTIPLY', T.math('MULTIPLY', sep.outputs[1], nzf), S, clamp=True)
        effl = T.math('MULTIPLY', T.math('MULTIPLY', sep.outputs[2], nzf), S, clamp=True)
        rust = T.math('MULTIPLY', T.math('MULTIPLY', alpha, nzf), S, clamp=True)
        c = gi.outputs['Color']
        c = T.mix(T.math('MULTIPLY', soot, 0.85), c, T.mul_col(c, (0.16, 0.15, 0.14, 1)))
        c = T.mix(T.math('MINIMUM', T.math('MULTIPLY', streak, 1.3), 1.0), c, T.mul_col(c, (0.36, 0.34, 0.32, 1)))
        c = T.mix(T.math('MULTIPLY', effl, 0.75), c, (0.62, 0.60, 0.55, 1))
        c = T.mix(T.math('MULTIPLY', rust, 0.8), c, srgb((92, 46, 22)))
        T.L.new(c, go.inputs['Color'])
        r = T.math('ADD', gi.outputs['Rough'], T.math('MULTIPLY', T.math('ADD', soot, effl), 0.15))
        T.L.new(T.math('MINIMUM', r, 1.0), go.inputs['Rough'])
        return g

    def _group(self, T, g, inputs):
        nd = T.n('ShaderNodeGroup')
        nd.node_tree = g
        for k, v in inputs.items():
            T.set(nd.inputs[k], v)
        return nd

    def _ao_dirt(self, T, col, rough, amount=0.55):
        """Grime collecting in concave corners (reveals, under sills, against the belt course)."""
        ao = T.n('ShaderNodeAmbientOcclusion', {'Distance': 0.35}, samples=6, only_local=False)
        occ = T.math('POWER', T.math('SUBTRACT', 1.0, ao.outputs['AO']), 1.4)
        nz = T.noise(T.n('ShaderNodeTexCoord').outputs['Object'], 7.0, 4, 0.6)
        f = T.math('MULTIPLY', T.math('MULTIPLY', occ, amount), T.remap(nz.outputs['Factor'], 0.35, 0.65, 0.5, 1.3), clamp=True)
        return T.mix(f, col, T.mul_col(col, (0.42, 0.40, 0.38, 1))), T.math('ADD', rough, T.math('MULTIPLY', f, 0.05))

    def _brick_local(self, T, u, v, i, j):
        off = T.math('MULTIPLY', T.math('FLOORED_MODULO', j, 2.0), CL / 2)
        lu = T.math('SUBTRACT', T.math('ADD', u, off), T.math('MULTIPLY', i, CL))
        lv = T.math('SUBTRACT', v, T.math('MULTIPLY', j, CH))
        return lu, lv

    def mat_brick_geo(self, bc, wg, tag):
        m, T, out = new_mat(tag + "_brick")
        at = T.n('ShaderNodeAttribute', attribute_name='cell')
        tc = T.n('ShaderNodeTexCoord')
        w0 = self._group(T, wg, {'Color': (0.5, 0.5, 0.5, 1), 'Rough': 0.5, 'Strength': 0.0})
        uvs = T.xyz(w0.outputs['UV'])
        cs = T.xyz(at.outputs['Vector'])
        lu, lv = self._brick_local(T, uvs[0], uvs[1], cs[0], cs[1])
        scan = T.math('LESS_THAN', cs[0], 4999.0)       # voussoirs (radial) keep the procedural face
        b = self._group(T, bc, {'Cell': at.outputs['Vector'], 'Pos': tc.outputs['Object'], 'Local': T.comb(lu, lv, 0.0), 'Scan': scan})
        w = self._group(T, wg, {'Color': b.outputs['Color'], 'Rough': b.outputs['Rough'], 'Strength': 1.0})
        c, r = self._ao_dirt(T, w.outputs['Color'], w.outputs['Rough'], 0.45)
        nrm = T.bump(b.outputs['Height'], 0.25, 0.0015, normal=b.outputs['Normal'])
        principled(T, out, c, r, normal=nrm)
        return m

    def mat_brick_field(self, bc, wg, name, use_mask=True):
        m, T, out = new_mat(name + "_brickfield")
        tc = T.n('ShaderNodeTexCoord')
        w0 = self._group(T, wg, {'Color': (0.5, 0.5, 0.5, 1), 'Rough': 0.5, 'Strength': 0.0})
        uvs = T.xyz(w0.outputs['UV'])
        u, v = uvs[0], uvs[1]
        j = T.math('FLOOR', T.math('DIVIDE', v, CH))
        off = T.math('MULTIPLY', T.math('FLOORED_MODULO', j, 2.0), CL / 2)
        uu = T.math('ADD', u, off)
        i = T.math('FLOOR', T.math('DIVIDE', uu, CL))
        lu = T.math('SUBTRACT', uu, T.math('MULTIPLY', i, CL))
        lv = T.math('SUBTRACT', v, T.math('MULTIPLY', j, CH))
        ex = T.math('MINIMUM', lu, T.math('SUBTRACT', CL, lu))
        ey = T.math('MINIMUM', lv, T.math('SUBTRACT', CH, lv))
        # irregular joint edges: hand-laid arrises, worn corners, occasional spall into the joint
        jn = T.noise(tc.outputs['Object'], 140.0, 4, 0.65)
        jn2 = T.noise(tc.outputs['Object'], 18.0, 2, 0.5)
        corner = T.math('MULTIPLY', T.smooth(ex, 0.02, 0.0), T.smooth(ey, 0.02, 0.0))
        e = T.math('ADD', T.math('MINIMUM', ex, ey), T.math('MULTIPLY', T.math('SUBTRACT', jn.outputs['Factor'], 0.5), 0.0045))
        e = T.math('SUBTRACT', e, T.math('MULTIPLY', corner, T.remap(jn2.outputs['Factor'], 0.4, 0.7, 0.0, 0.006)))
        brick = T.smooth(e, 0.0040, 0.0062)
        if use_mask:
            mu = T.math('DIVIDE', T.math('ADD', T.math('FLOORED_MODULO', i, float(self.ni)), 0.5), float(self.ni))
            mv = T.math('DIVIDE', T.math('ADD', j, 0.5), float(self.nj))
            mimg = T.n('ShaderNodeTexImage', {'Vector': T.comb(mu, mv, 0.0)}, image=self.mask_img, extension='CLIP', interpolation='Closest')
            sepm = T.n('ShaderNodeSeparateColor', {'Color': mimg.outputs['Color']})
            brick = T.math('MULTIPLY', brick, T.math('SUBTRACT', 1.0, sepm.outputs[0]))
        cell = T.comb(i, j, 0.0)
        b = self._group(T, bc, {'Cell': cell, 'Pos': tc.outputs['Object'], 'Local': T.comb(lu, lv, 0.0), 'Scan': 1.0})
        # mortar: lime-sand texture from the CC0 concrete scan, dirt in the bed joints, repointed patches
        mp = T.vmath('SCALE', T.comb(u, v, 0.0), scale=1.0 / 0.9)
        mimg2 = T.n('ShaderNodeTexImage', {'Vector': mp}, image=tex_image("tex_scan/hangar_concrete_floor_diff_4k.jpg", color=True), interpolation='Linear')
        ml = T.n('ShaderNodeRGBToBW', {'Color': mimg2.outputs['Color']}).outputs[0]
        mort_n = T.noise(tc.outputs['Object'], 60.0, 4, 0.6)
        mf = T.math('MULTIPLY', T.remap(ml, 0.02, 0.045, 0.72, 1.2), T.remap(mort_n.outputs['Factor'], 0.3, 0.7, 0.85, 1.08))
        bed = T.math('LESS_THAN', ey, ex)
        mf = T.math('MULTIPLY', mf, T.mixf(bed, 1.0, 0.82))
        mort = T.mul_col(srgb((128, 121, 110)), T.comb(mf, mf, mf))
        rep = T.n('ShaderNodeTexVoronoi', {'Vector': T.comb(T.math('MULTIPLY', u, 0.5), v, 0.0), 'Scale': 0.9})
        rpf = T.math('GREATER_THAN', T.n('ShaderNodeTexWhiteNoise', {'Vector': rep.outputs['Position']}, noise_dimensions='3D').outputs['Value'], 0.9)
        mort = T.mix(rpf, mort, T.mul_col(srgb((150, 148, 142)), T.comb(*([T.remap(ml, 0.02, 0.045, 0.9, 1.06)] * 3))))
        col = T.mix(brick, mort, b.outputs['Color'])
        rough = T.mixf(brick, 0.96, b.outputs['Rough'])
        w = self._group(T, wg, {'Color': col, 'Rough': rough, 'Strength': 1.0})
        c, r = self._ao_dirt(T, w.outputs['Color'], w.outputs['Rough'], 0.5)
        # height: brick faces with per-brick tilt, recessed mortar (raked deeper where eroded)
        wn = T.n('ShaderNodeTexWhiteNoise', {'Vector': cell}, noise_dimensions='3D')
        tilt = T.xyz(wn.outputs['Color'])
        tlt = T.math('ADD', T.math('MULTIPLY', T.math('SUBTRACT', lu, CL / 2), T.math('SUBTRACT', tilt[0], 0.5)),
                     T.math('MULTIPLY', T.math('SUBTRACT', lv, CH / 2), T.math('SUBTRACT', tilt[1], 0.5)))
        h = T.math('ADD', T.math('MULTIPLY', brick, 0.008), T.math('MULTIPLY', tlt, 0.05))
        h = T.math('ADD', h, T.math('MULTIPLY', b.outputs['Height'], 0.0006))
        h = T.math('ADD', h, T.math('MULTIPLY', T.math('SUBTRACT', 1.0, brick), T.math('MULTIPLY', ml, 0.12)))
        nrm = T.bump(h, 1.0, 1.0, normal=b.outputs['Normal'])
        principled(T, out, c, r, normal=nrm)
        return m

    def mat_simple(self, name, col, rough, wg=None, noise=0.0, metal=0.0):
        m, T, out = new_mat(name)
        tc = T.n('ShaderNodeTexCoord')
        c = col
        if noise > 0:
            nz = T.noise(tc.outputs['Object'], 6.0, 5, 0.6)
            f = T.remap(nz.outputs['Factor'], 0.3, 0.7, 1 - 0.5 * noise, 1 + 0.4 * noise)
            c = T.mul_col(col, T.comb(f, f, f))
        r = rough
        if wg is not None:
            w = self._group(T, wg, {'Color': c, 'Rough': rough, 'Strength': 1.0})
            c, r = w.outputs['Color'], w.outputs['Rough']
        principled(T, out, c, r, metal)
        return m

    def mat_stone(self, name, col, wg, rough=0.8, speck=False):
        m, T, out = new_mat(name)
        tc = T.n('ShaderNodeTexCoord')
        geo = T.n('ShaderNodeNewGeometry')
        p = tc.outputs['Object']
        n1 = T.noise(p, 3.0, 6, 0.6)
        n2 = T.noise(p, 45.0, 6, 0.7)
        f = T.math('MULTIPLY', T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.78, 1.12), T.remap(n2.outputs['Factor'], 0.2, 0.8, 0.86, 1.1))
        c = T.mul_col(col, T.comb(f, f, f))
        n3 = T.noise(p, 0.8, 3, 0.5)
        c = T.mix(T.smooth(n3.outputs['Factor'], 0.45, 0.65), c, T.mul_col(c, (0.86, 0.84, 0.8, 1)))
        pores = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 400.0})
        pore = T.smooth(pores.outputs['Distance'], 0.08, 0.0)
        c = T.mix(T.math('MULTIPLY', pore, 0.5), c, T.mul_col(c, (0.5, 0.5, 0.5, 1)))
        if speck:
            vs = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 180.0})
            sp = T.smooth(vs.outputs['Distance'], 0.05, 0.25)
            c = T.mix(sp, T.mul_col(c, (0.35, 0.35, 0.35, 1)), c)
        # dirt band near the ground and in upward faces (pigeon / grime on ledges)
        z = T.xyz(p)[2]
        ground = T.math('MULTIPLY', T.smooth(z, 0.7, 0.0), T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.6, 1.0))
        c = T.mix(T.math('MULTIPLY', ground, 0.8), c, T.mul_col(c, (0.30, 0.27, 0.24, 1)))
        up = T.xyz(geo.outputs['Normal'])[2]
        upf = T.math('MULTIPLY', T.smooth(up, 0.5, 0.95), T.remap(n2.outputs['Factor'], 0.35, 0.65, 0.3, 1.0))
        c = T.mix(T.math('MULTIPLY', upf, 0.65), c, T.mul_col(c, (0.40, 0.37, 0.33, 1)))
        # pigeon droppings on ledges
        dv = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 30.0})
        dn = T.noise(p, 2.0, 2, 0.5)
        drop = T.math('MULTIPLY', T.math('MULTIPLY', T.smooth(dv.outputs['Distance'], 0.10, 0.03), T.smooth(up, 0.6, 0.9)), T.smooth(dn.outputs['Factor'], 0.5, 0.62))
        c = T.mix(drop, c, (0.75, 0.74, 0.70, 1))
        w = self._group(T, wg, {'Color': c, 'Rough': rough, 'Strength': 1.0})
        nrm = T.bump(T.math('ADD', T.math('ADD', n2.outputs['Factor'], T.math('MULTIPLY', pore, -0.6)), T.math('MULTIPLY', drop, 0.5)), 0.35, 0.002)
        principled(T, out, w.outputs['Color'], w.outputs['Rough'], normal=nrm)
        return m

    def mat_paint(self, name, col, wg, chip=0.4, rust=False, gloss=False, ground=False):
        m, T, out = new_mat(name)
        tc = T.n('ShaderNodeTexCoord')
        p = tc.outputs['Object']
        n1 = T.noise(p, 14.0, 8, 0.7, distortion=0.3)
        n2 = T.noise(p, 2.5, 3, 0.5)
        thr = 1.0 - 0.32 * chip
        chipm = T.math('MULTIPLY', T.smooth(n1.outputs['Factor'], thr, thr + 0.015), T.smooth(n2.outputs['Factor'], 0.42, 0.6))
        under = srgb((96, 50, 30)) if rust else srgb((150, 140, 120))
        nf = T.remap(n2.outputs['Factor'], 0.3, 0.7, 0.85, 1.12)
        c = T.mul_col(col, T.comb(nf, nf, nf))
        c = T.mix(chipm, c, under)
        if ground:
            z = T.xyz(p)[2]
            gb = T.math('MULTIPLY', T.smooth(z, 0.5, 0.0), T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.5, 1.0))
            c = T.mix(T.math('MULTIPLY', gb, 0.75), c, T.mul_col(c, (0.4, 0.36, 0.3, 1)))
        r0 = 0.28 if gloss else 0.42
        r = T.mixf(chipm, T.remap(n2.outputs['Factor'], 0.3, 0.7, r0 - 0.08, r0 + 0.15), 0.8)
        w = self._group(T, wg, {'Color': c, 'Rough': r, 'Strength': 0.7})
        nrm = T.bump(T.math('MULTIPLY', T.math('SUBTRACT', 1.0, chipm), 1.0), 0.4, 0.0006)
        principled(T, out, w.outputs['Color'], w.outputs['Rough'], normal=nrm, Coat_Weight=(0.25 if gloss else 0.0))
        return m

    def mat_metal(self, name, col, rough, metal=1.0, tarnish=False, galv=False, two_tone=False):
        m, T, out = new_mat(name)
        tc = T.n('ShaderNodeTexCoord')
        p = tc.outputs['Object']
        n1 = T.noise(p, 20.0, 6, 0.6)
        c = col
        if tarnish:
            c = T.mix(T.smooth(n1.outputs['Factor'], 0.45, 0.7), col, srgb((90, 70, 40)))
        if galv:
            vg = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 60.0})
            c = T.mul_col(col, T.comb(*([T.remap(vg.outputs['Distance'], 0, 0.6, 0.8, 1.05)] * 3)))
        r = T.remap(n1.outputs['Factor'], 0.3, 0.7, rough * 0.7, rough * 1.4)
        if two_tone:
            geo = T.n('ShaderNodeNewGeometry')
            c = T.mix(geo.outputs['Backfacing'], col, (0.9, 0.88, 0.82, 1))
        principled(T, out, c, r, metal)
        return m

    def mat_glass(self, name, prism=False):
        m, T, out = new_mat(name)
        tc = T.n('ShaderNodeTexCoord')
        p = tc.outputs['Object']
        # old cylinder glass: gentle horizontal waviness
        mp = T.n('ShaderNodeMapping', {'Vector': p, 'Scale': (6.0, 6.0, 1.2) if not prism else (40, 40, 40)})
        n1 = T.noise(mp.outputs[0], 2.0, 2, 0.4)
        nrm = T.bump(n1.outputs['Factor'], 0.06 if not prism else 0.5, 0.01)
        dirt = T.noise(p, 3.0, 5, 0.6)
        rough = T.remap(dirt.outputs['Factor'], 0.45, 0.8, 0.0, 0.035)
        if prism:
            rough = 0.4
        pr = principled(T, None, (0.94, 0.95, 0.93, 1), rough, normal=nrm, Transmission_Weight=1.0, IOR=1.52)
        pr.inputs['Thin Wall'].default_value = True
        # a little grime film reduces transmission
        dif = T.n('ShaderNodeBsdfDiffuse', {'Color': srgb((150, 132, 100)) if prism else srgb((110, 104, 96))})
        ms = T.n('ShaderNodeMixShader', {'Fac': 0.55 if prism else T.remap(dirt.outputs['Factor'], 0.5, 0.85, 0.0, 0.05)})
        T.L.new(pr.outputs[0], ms.inputs[1])
        T.L.new(dif.outputs[0], ms.inputs[2])
        T.L.new(ms.outputs[0], out.inputs['Surface'])
        return m

    def mat_emit_glass(self, name):
        m, T, out = new_mat(name)
        pr = principled(T, None, (0.95, 0.9, 0.8, 1), 0.3, Transmission_Weight=1.0)
        pr.inputs['Thin Wall'].default_value = True
        em = T.n('ShaderNodeEmission', {'Color': (1.0, 0.75, 0.45, 1), 'Strength': 0.0})
        em.name = "LampEmit"
        add = T.n('ShaderNodeAddShader')
        T.L.new(pr.outputs[0], add.inputs[0])
        T.L.new(em.outputs[0], add.inputs[1])
        T.L.new(add.outputs[0], out.inputs['Surface'])
        return m

    def mat_emit(self, name, col, strength):
        m, T, out = new_mat(name)
        em = T.n('ShaderNodeEmission', {'Color': (*col, 1.0), 'Strength': strength})
        em.name = "LampEmit"
        T.L.new(em.outputs[0], out.inputs['Surface'])
        return m

    def mat_fabric(self, name, col, outdoor=False, sheer=False):
        m, T, out = new_mat(name)
        tc = T.n('ShaderNodeTexCoord')
        p = tc.outputs['Object']
        wv = T.n('ShaderNodeTexWave', {'Vector': p, 'Scale': 220.0}, wave_type='BANDS')
        n1 = T.noise(p, 4.0, 4, 0.6)
        f = T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.85, 1.08)
        c = T.mul_col(col, T.comb(f, f, f))
        if outdoor:
            # sun-faded top, dirty lower edge
            z = T.xyz(p)[2]
            c = T.mix(T.math('MULTIPLY', T.smooth(n1.outputs['Factor'], 0.4, 0.7), 0.35), c, T.mul_col(col, (1.5, 1.4, 1.35, 1)))
            c = T.mix(T.math('MULTIPLY', T.smooth(z, 3.0, 2.75), 0.5), c, T.mul_col(c, (0.5, 0.45, 0.42, 1)))
        nrm = T.bump(wv.outputs['Fac'], 0.15, 0.001)
        pr = principled(T, None, c, 0.85, normal=nrm, Sheen_Weight=0.4, Sheen_Tint=(1, 1, 1, 1))
        tl = T.n('ShaderNodeBsdfTranslucent', {'Color': c})
        ms = T.n('ShaderNodeMixShader', {'Fac': 0.55 if sheer else 0.2})
        T.L.new(pr.outputs[0], ms.inputs[1])
        T.L.new(tl.outputs[0], ms.inputs[2])
        T.L.new(ms.outputs[0], out.inputs['Surface'])
        return m

    def mat_tile(self, name, checker=False):
        m, T, out = new_mat(name)
        tc = T.n('ShaderNodeTexCoord')
        if checker:
            ck = T.n('ShaderNodeTexChecker', {'Vector': tc.outputs['Object'], 'Scale': 3.3, 'Color1': srgb((200, 194, 180)), 'Color2': srgb((40, 40, 40))})
            c = ck.outputs['Color']
        else:
            vo = T.n('ShaderNodeTexVoronoi', {'Vector': tc.outputs['Object'], 'Scale': 45.0, 'Randomness': 0.0})
            c = T.mix(T.smooth(vo.outputs['Distance'], 0.40, 0.46), srgb((222, 216, 200)), srgb((90, 86, 80)))
            wn = T.n('ShaderNodeTexWhiteNoise', {'Vector': vo.outputs['Position']}, noise_dimensions='3D')
            c = T.mix(T.math('GREATER_THAN', wn.outputs['Value'], 0.88), c, srgb((40, 70, 60)))
        principled(T, out, c, 0.4)
        return m

    def mat_wood(self, name, col):
        m, T, out = new_mat(name)
        tc = T.n('ShaderNodeTexCoord')
        mp = T.n('ShaderNodeMapping', {'Vector': tc.outputs['Object'], 'Scale': (1.0, 12.0, 1.0)})
        wv = T.n('ShaderNodeTexWave', {'Vector': mp.outputs[0], 'Scale': 3.0, 'Distortion': 6.0, 'Detail': 4.0})
        f = T.remap(wv.outputs['Fac'], 0, 1, 0.7, 1.1)
        principled(T, out, T.mul_col(col, T.comb(f, f, f)), 0.35)
        return m

    def mat_attr(self, name, rough, pastel=False):
        m, T, out = new_mat(name)
        at = T.n('ShaderNodeAttribute', attribute_name='cell')
        hsv = T.n('ShaderNodeHueSaturation', {'Color': at.outputs['Color'], 'Saturation': 0.6 if pastel else 1.0, 'Value': 1.0})
        c = T.mix(0.5 if pastel else 0.0, hsv.outputs[0], (0.9, 0.85, 0.75, 1))
        principled(T, out, c, rough)
        return m

    def mat_bread(self, name):
        m, T, out = new_mat(name)
        tc = T.n('ShaderNodeTexCoord')
        n1 = T.noise(tc.outputs['Object'], 30.0, 4, 0.6)
        c = T.mix(n1.outputs['Factor'], srgb((150, 90, 40)), srgb((210, 160, 90)))
        principled(T, out, c, 0.7, Subsurface_Weight=0.1)
        return m

    # ---------------------------------------------------------------- objects
    def emit_objects(self):
        Mt = self.materials
        spec = {  # key: (smooth, bevel)
            'bricks': (False, 0.0), 'wall': (False, 0.0), 'reveal': (False, 0.0), 'stone': (False, 0.006),
            'win_frame': (False, 0.003), 'glass': (False, 0.0), 'putty': (False, 0.0), 'shop_paint': (False, 0.004),
            'brass': (True, 0.0), 'tile': (False, 0.0), 'door': (False, 0.003), 'iron': (True, 0.0), 'awning': (True, 0.0),
            'cornice': (False, 0.004), 'fire_escape': (True, 0.0), 'services': (True, 0.0), 'shade': (True, 0.0),
            'bulbs': (True, 0.0), 'interior': (False, 0.0), 'treat': (True, 0.0), 'shop_in': (False, 0.0), 'letters': (False, 0.0),
            'letters_flat': (False, 0.0), 'props': (True, 0.0), 'blade': (False, 0.004), 'brickback': (False, 0.0),
        }
        self.objects = {}
        for key, mb in self.mb.items():
            sm, bev = spec.get(key, (False, 0.0))
            ob = finalize(mb, self.col, Mt, smooth=sm, bevel=bev, recalc=mb.closed)
            if ob:
                ob.name = f"{self.vt['name']}_{key}"
                self.objects[key] = ob
                if key in ('glass', 'letters_flat', 'awning', 'treat'):
                    pass
        # lights
        for i, L in enumerate(self.lights):
            if L['kind'] == 'area':
                ld = bpy.data.lights.new(f"{self.vt['name']}_L{i}", 'AREA')
                ld.size = L.get('size', 0.5)
            elif L['kind'] == 'spot':
                ld = bpy.data.lights.new(f"{self.vt['name']}_L{i}", 'SPOT')
                ld.spot_size = L.get('spot', 1.5)
                ld.spot_blend = 0.6
                ld.shadow_soft_size = L.get('radius', 0.05)
            else:
                ld = bpy.data.lights.new(f"{self.vt['name']}_L{i}", 'POINT')
                ld.shadow_soft_size = L.get('radius', 0.05)
            ld.energy = L['energy']
            ld.color = L['color']
            ob = bpy.data.objects.new(ld.name, ld)
            ob.location = L['loc']
            if L['kind'] == 'spot' and 'target' in L:
                d = (Vector(L['target']) - Vector(L['loc'])).normalized()
                ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
            ob["group"] = L['group']
            ob["base_energy"] = L['energy']
            self.col.objects.link(ob)


def build(variant=None):
    """Build the facade asset and return its collection (not linked to any scene)."""
    return Facade(variant).build()


def set_lights(col, day=True, interior_mult=1.0, exterior_mult=1.0, shop_mult=1.0):
    """Scale the asset's practical lights: day=True dims exterior lamps and lantern glows."""
    for ob in col.all_objects:
        if ob.type == 'LIGHT':
            g = ob.get("group", "interior")
            mult = {'interior': interior_mult, 'exterior': exterior_mult, 'shop': shop_mult}.get(g, 1.0)
            if day and g == 'exterior':
                mult *= 0.0
            ob.data.energy = ob.get("base_energy", 10) * mult
    for m in bpy.data.materials:
        if m.name.startswith(col.name) and m.node_tree and "LampEmit" in m.node_tree.nodes:
            em = m.node_tree.nodes["LampEmit"]
            if m.name.endswith("_lantglass"):
                em.inputs['Strength'].default_value = 0.0 if day else 4.0
            elif m.name.endswith("_bulb"):
                em.inputs['Strength'].default_value = 3.0 if day else 12.0
