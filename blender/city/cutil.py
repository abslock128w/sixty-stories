"""Low-level helpers: fast mesh building, collections, linked instances."""
import math
import random
import bpy
import numpy as np


class MB:
    """Mesh builder: accumulates quads/polys with material index, UVs and per-face
    float-colour attributes, then makes one bpy mesh."""

    def __init__(self, attrs=()):
        self.V = []
        self.F = []
        self.M = []
        self.UV = []
        self.attr_names = list(attrs)
        self.A = {a: [] for a in self.attr_names}
        self.smooth = []

    def _push_attrs(self, attrs):
        for a in self.attr_names:
            v = attrs.get(a) if attrs else None
            self.A[a].append(v if v is not None else (0.0, 0.0, 0.0, 0.0))

    def poly(self, pts, mat=0, uv=None, attrs=None, smooth=False):
        b = len(self.V)
        self.V.extend(pts)
        self.F.append(tuple(range(b, b + len(pts))))
        self.M.append(mat)
        if uv is None:
            uv = [(0.0, 0.0)] * len(pts)
        self.UV.extend(uv)
        self.smooth.append(smooth)
        self._push_attrs(attrs)

    def quad(self, p0, p1, p2, p3, mat=0, uv=None, attrs=None):
        self.poly([p0, p1, p2, p3], mat, uv or [(0, 0), (1, 0), (1, 1), (0, 1)], attrs)

    def box(self, x0, x1, y0, y1, z0, z1, mat=0, skip=(), attrs=None, uvscale=None):
        """Axis aligned box. skip: subset of {'+x','-x','+y','-y','+z','-z'}."""
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        P = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        faces = {'-z': (0, 3, 2, 1), '+z': (4, 5, 6, 7), '-y': (0, 1, 5, 4),
                 '+x': (1, 2, 6, 5), '+y': (2, 3, 7, 6), '-x': (3, 0, 4, 7)}
        for k, f in faces.items():
            if k in skip:
                continue
            pts = [P[i] for i in f]
            self.poly(pts, mat, _world_uv(pts, k) if uvscale else None, attrs)

    def obox(self, c, d, hl, hw, z0, z1, mat=0, skip=(), attrs=None):
        """Oriented box: centre c=(x,y), unit dir d=(dx,dy) along length, half length hl,
        half width hw (perpendicular), z0..z1. skip uses '+l','-l','+w','-w','+z','-z'."""
        cx, cy = c
        dx, dy = d
        nx, ny = -dy, dx
        P = []
        for z in (z0, z1):
            for sl, sw in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                P.append((cx + dx * hl * sl + nx * hw * sw, cy + dy * hl * sl + ny * hw * sw, z))
        faces = {'-z': (0, 3, 2, 1), '+z': (4, 5, 6, 7), '-w': (0, 1, 5, 4),
                 '+l': (1, 2, 6, 5), '+w': (2, 3, 7, 6), '-l': (3, 0, 4, 7)}
        for k, f in faces.items():
            if k in skip:
                continue
            self.poly([P[i] for i in f], mat, None, attrs)

    def prism(self, pts2d, z0, z1, mat=0, top=True, bottom=False, attrs=None, side_mat=None):
        """Vertical extrusion of a CCW polygon."""
        n = len(pts2d)
        sm = mat if side_mat is None else side_mat
        for i in range(n):
            a = pts2d[i]
            b = pts2d[(i + 1) % n]
            self.poly([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], sm, None, attrs)
        if top:
            self.poly([(p[0], p[1], z1) for p in pts2d], mat, None, attrs)
        if bottom:
            self.poly([(p[0], p[1], z0) for p in reversed(pts2d)], mat, None, attrs)

    def extend(self, other, offset=(0, 0, 0)):
        b = len(self.V)
        ox, oy, oz = offset
        self.V.extend([(v[0] + ox, v[1] + oy, v[2] + oz) for v in other.V])
        self.F.extend([tuple(i + b for i in f) for f in other.F])
        self.M.extend(other.M)
        self.UV.extend(other.UV)
        self.smooth.extend(other.smooth)
        for a in self.attr_names:
            self.A[a].extend(other.A.get(a, [(0, 0, 0, 0)] * len(other.F)))

    def build(self, name, mats, merge=False):
        me = bpy.data.meshes.new(name)
        if not self.F:
            return me
        V = np.asarray(self.V, dtype=np.float32)
        nloops = [len(f) for f in self.F]
        loop_start = np.zeros(len(self.F), dtype=np.int32)
        loop_start[1:] = np.cumsum(nloops)[:-1]
        loops = np.fromiter((i for f in self.F for i in f), dtype=np.int32)
        me.vertices.add(len(V))
        me.vertices.foreach_set("co", V.ravel())
        me.loops.add(len(loops))
        me.loops.foreach_set("vertex_index", loops)
        me.polygons.add(len(self.F))
        me.polygons.foreach_set("loop_start", loop_start)
        me.polygons.foreach_set("material_index", np.asarray(self.M, dtype=np.int32))
        me.polygons.foreach_set("use_smooth", np.asarray(self.smooth, dtype=bool))
        uvl = me.uv_layers.new(name="UVMap")
        uvl.data.foreach_set("uv", np.asarray(self.UV, dtype=np.float32).ravel())
        for a in self.attr_names:
            at = me.attributes.new(a, 'FLOAT_COLOR', 'FACE')
            at.data.foreach_set("color", np.asarray(self.A[a], dtype=np.float32).ravel())
        me.update(calc_edges=True)
        me.validate(clean_customdata=False)
        for m in mats:
            me.materials.append(m)
        if merge:
            import bmesh
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
            bm.to_mesh(me)
            bm.free()
        return me


def _world_uv(pts, k):
    if k in ('+z', '-z'):
        return [(p[0], p[1]) for p in pts]
    if k in ('+x', '-x'):
        return [(p[1], p[2]) for p in pts]
    return [(p[0], p[2]) for p in pts]


def get_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent.children if parent else bpy.context.scene.collection.children).link(col)
    return col


def new_object(name, data, col, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    ob = bpy.data.objects.new(name, data)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    col.objects.link(ob)
    return ob


def bevel_mod(ob, width=0.02, segments=1, limit_angle=40):
    m = ob.modifiers.new("bevel", 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(limit_angle)
    m.harden_normals = False
    return m


def hash01(*args):
    """Deterministic pseudo random in 0..1 from ints/floats."""
    h = 2166136261
    for a in args:
        for b in repr(a).encode():
            h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return (h % 1000003) / 1000003.0
