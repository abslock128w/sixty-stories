"""Sixty Stories - street corner hero asset: shared mesh helpers + materials.

Follows facade.py conventions (MB mesh builder, NT node helper, object-space procedural
shaders, world-scale box UVs).  Extra: per-face explicit UVs for decals / signs, lathe,
tapered tubes, and a material cache so every prop function can be called on its own.
"""
import math
import os
import random

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import facade
from facade import NT, new_mat, principled, srgb
import corner_tex

TEX = corner_tex.TEX_DIR
TAU = 2 * math.pi
_M = {}


def reset():
    _M.clear()


# ============================================================================ mesh builder
class MB(facade.MB):
    def __init__(self, name):
        super().__init__(name)
        self.fuv = []
        self.vattr = {}          # name -> list per vertex (float)

    def face(self, idx, m, cell=(0.0, 0.0, 0.0), uv=None):
        super().face(idx, m, cell)
        self.fuv.append(uv)

    def quad_uv(self, pts, uvs, m, cell=(0, 0, 0)):
        i = [self.add_v(p) for p in pts]
        self.face(i, m, cell, uv=list(uvs))

    def lathe(self, prof, m, seg=24, M=None, cell=(0, 0, 0), caps=True):
        """Revolve [(r, z)] around local Z, transformed by Matrix M. r==0 -> pole vertex."""
        M = M or Matrix.Identity(4)
        rings = []
        for r, z in prof:
            if r <= 1e-7:
                rings.append(self.add_v(M @ Vector((0, 0, z))))
            else:
                rings.append([self.add_v(M @ Vector((r * math.cos(TAU * k / seg), r * math.sin(TAU * k / seg), z))) for k in range(seg)])
        for a, b in zip(rings[:-1], rings[1:]):
            if isinstance(a, int) and isinstance(b, int):
                continue
            for k in range(seg):
                k2 = (k + 1) % seg
                if isinstance(a, int):
                    self.face([a, b[k], b[k2]], m, cell)
                elif isinstance(b, int):
                    self.face([a[k], b, a[k2]], m, cell)
                else:
                    self.face([a[k], b[k], b[k2], a[k2]], m, cell)
        if caps and not isinstance(rings[0], int):
            self.face(rings[0][::-1], m, cell)
        if caps and not isinstance(rings[-1], int):
            self.face(rings[-1], m, cell)

    def ttube(self, pts, radii, m, seg=8, caps=(True, True), cell=(0, 0, 0)):
        """Tapered tube along a polyline with parallel-transported frames."""
        P = [Vector(p) for p in pts]
        n = len(P)
        rings = []
        prev = None
        for i in range(n):
            if i == 0:
                t = (P[1] - P[0]).normalized()
            elif i == n - 1:
                t = (P[-1] - P[-2]).normalized()
            else:
                t = ((P[i] - P[i - 1]).normalized() + (P[i + 1] - P[i]).normalized()).normalized()
            if prev is None:
                ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
                s = t.cross(ref).normalized()
            else:
                s = (prev - t * prev.dot(t)).normalized()
            u = t.cross(s).normalized()
            prev = s
            r = radii[i]
            rings.append([self.add_v(P[i] + (s * math.cos(TAU * k / seg) + u * math.sin(TAU * k / seg)) * r) for k in range(seg)])
        for a, b in zip(rings[:-1], rings[1:]):
            for k in range(seg):
                k2 = (k + 1) % seg
                self.face([a[k], a[k2], b[k2], b[k]], m, cell)
        if caps[0]:
            self.face(rings[0][::-1], m, cell)
        if caps[1]:
            self.face(rings[-1], m, cell)

    def ring_tube(self, center, R, r, m, seg=24, rseg=6, M=None, a0=0.0, a1=TAU, cell=(0, 0, 0)):
        """Torus (or arc of one) of major radius R in the local XY plane."""
        M = M or Matrix.Identity(4)
        full = abs(a1 - a0 - TAU) < 1e-6
        ns = seg if full else seg + 1
        rings = []
        for i in range(ns):
            a = a0 + (a1 - a0) * i / seg
            c = Vector((math.cos(a), math.sin(a), 0))
            ring = []
            for k in range(rseg):
                b = TAU * k / rseg
                p = Vector(center) + c * (R + r * math.cos(b)) + Vector((0, 0, r * math.sin(b)))
                ring.append(self.add_v(M @ p))
            rings.append(ring)
        pairs = list(zip(rings, rings[1:] + ([rings[0]] if full else [])))
        for a, b in pairs:
            for k in range(rseg):
                k2 = (k + 1) % rseg
                self.face([a[k], b[k], b[k2], a[k2]], m, cell)
        if not full:
            self.face(rings[0][::-1], m, cell)
            self.face(rings[-1], m, cell)

    def hexnut(self, c, normal, r, h, m, cell=(0, 0, 0), sides=6, rot=0.0):
        M = frame(c, normal, rot)
        self.lathe([(0, 0), (r, 0), (r, h * 0.8), (r * 0.8, h), (0, h)], m, seg=sides, M=M, cell=cell)


def frame(c, normal, rot=0.0):
    """Matrix placing local Z along `normal` at point c."""
    n = Vector(normal).normalized()
    q = n.to_track_quat('Z', 'Y')
    return Matrix.Translation(Vector(c)) @ q.to_matrix().to_4x4() @ Matrix.Rotation(rot, 4, 'Z')


def finalize(mb, col, mats, smooth=False, bevel=0.0, bevel_seg=2, recalc=True, angle=40):
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
                if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(angle):
                    e.smooth = False
        bm.to_mesh(me)
        bm.free()
    for m in mb.mats:
        me.materials.append(mats[m] if isinstance(m, str) else m)
    ok = len(me.polygons) == len(mb.fm)
    if ok:
        me.polygons.foreach_set('material_index', mb.fm)
        if any(c != (0, 0, 0) for c in mb.cell):
            at = me.attributes.new("cell", 'FLOAT_VECTOR', 'FACE')
            at.data.foreach_set('vector', np.array(mb.cell, np.float32).ravel())
    facade._box_uv(me)
    if ok and any(u is not None for u in mb.fuv):
        uvl = me.uv_layers[0].data
        for pi, uv in enumerate(mb.fuv):
            if uv is None:
                continue
            p = me.polygons[pi]
            for j, li in enumerate(range(p.loop_start, p.loop_start + p.loop_total)):
                uvl[li].uv = uv[j % len(uv)]
    for name, vals in mb.vattr.items():
        if len(vals) == len(me.vertices):
            at = me.attributes.new(name, 'FLOAT', 'POINT')
            at.data.foreach_set('value', np.array(vals, np.float32))
    ob = bpy.data.objects.new(mb.name, me)
    col.objects.link(ob)
    if bevel > 0:
        md = ob.modifiers.new("Bevel", 'BEVEL')
        md.width = bevel
        md.segments = bevel_seg
        md.limit_method = 'ANGLE'
        md.angle_limit = math.radians(angle)
        md.harden_normals = smooth
    return ob


def new_col(name):
    c = bpy.data.collections.new(name)
    return c


# ============================================================================ textures
def img(name, noncolor=False):
    path = os.path.join(TEX, name)
    im = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        im.colorspace_settings.name = 'Non-Color'
    return im


def tex(T, name, vec=None, noncolor=False, ext='EXTEND', interp='Linear'):
    nd = T.n('ShaderNodeTexImage')
    nd.image = img(name, noncolor)
    nd.extension = ext
    nd.interpolation = interp
    if vec is not None:
        T.set(nd.inputs['Vector'], vec)
    return nd


def coords(T):
    tc = T.n('ShaderNodeTexCoord')
    p = tc.outputs['Object']
    oi = T.n('ShaderNodeObjectInfo')
    r = oi.outputs['Random']
    off = T.comb(T.math('MULTIPLY', r, 17.3), T.math('MULTIPLY', r, 31.7), T.math('MULTIPLY', r, 7.1))
    return p, T.vmath('ADD', p, off), tc


def sepc(T, c):
    nd = T.n('ShaderNodeSeparateColor')
    T.set(nd.inputs[0], c)
    return nd.outputs


def ao(T, dist):
    nd = T.n('ShaderNodeAmbientOcclusion', {'Distance': dist})
    nd.samples = 8
    return nd.outputs['AO']


def grime(T, c, p, h=0.35, amt=0.75, col=(0.30, 0.27, 0.23)):
    z = T.xyz(p)[2]
    n = T.noise(p, 5.0, 5, 0.6)
    g = T.math('MULTIPLY', T.smooth(z, h, 0.0), T.remap(n.outputs['Factor'], 0.3, 0.7, 0.35, 1.0))
    return T.mix(T.math('MULTIPLY', g, amt), c, T.mul_col(c, (*col, 1))), g


def dust_up(T, c, amt=0.35, col=(0.42, 0.40, 0.36)):
    geo = T.n('ShaderNodeNewGeometry')
    up = T.xyz(geo.outputs['Normal'])[2]
    f = T.math('MULTIPLY', T.smooth(up, 0.5, 0.95), amt)
    return T.mix(f, c, (*col, 1))


# ============================================================================ materials
def cache(fn):
    def w(name, *a, **k):
        m = _M.get(name)
        if m is not None:
            try:
                m.name
                return m
            except ReferenceError:
                pass
        m = fn(name, *a, **k)
        _M[name] = m
        return m
    w.__name__ = fn.__name__
    return w


@cache
def m_paint(name, col, chip=0.35, rust=True, gloss=False, grime_h=0.4, grime_amt=0.7, rough=0.42, scale=1.0, under=None):
    m, T, out = new_mat(name)
    p, pv, _ = coords(T)
    n1 = T.noise(T.vmath('SCALE', pv, scale=scale), 9.0, 8, 0.72, distortion=0.35)
    n2 = T.noise(pv, 1.6, 3, 0.5)
    thr = 1.0 - 0.30 * chip
    z = T.xyz(p)[2]
    low = T.smooth(z, 0.5, 0.05)          # kicked / scraped near the ground
    thr_s = T.math('SUBTRACT', thr, T.math('MULTIPLY', low, 0.08))
    nd = T.n('ShaderNodeMapRange', {'Value': n1.outputs['Factor']})
    T.set(nd.inputs[1], thr_s)
    T.set(nd.inputs[2], T.math('ADD', thr_s, 0.012))
    chipm = T.math('MULTIPLY', nd.outputs[0], T.smooth(n2.outputs['Factor'], 0.38, 0.55))
    if under is None:
        rn = T.noise(pv, 30.0, 4, 0.6)
        under = T.mix(rn.outputs['Factor'], srgb((70, 38, 22)), srgb((150, 80, 36))) if rust else srgb((150, 146, 136))
    nf = T.remap(n2.outputs['Factor'], 0.3, 0.7, 0.86, 1.10)
    c = T.mul_col(col, T.comb(nf, nf, nf))
    # paint halo around chips (rust bleed)
    halo = T.math('MULTIPLY', T.smooth(n1.outputs['Factor'], thr - 0.10, thr), T.smooth(n2.outputs['Factor'], 0.38, 0.55))
    if rust:
        c = T.mix(T.math('MULTIPLY', halo, 0.45), c, T.mul_col(c, srgb((150, 100, 70))))
    c = T.mix(chipm, c, under)
    c, g = grime(T, c, p, grime_h, grime_amt)
    c = dust_up(T, c, 0.25)
    r0 = 0.25 if gloss else rough
    r = T.mixf(chipm, T.remap(n2.outputs['Factor'], 0.3, 0.7, r0 - 0.07, r0 + 0.15), 0.75)
    r = T.mixf(g, r, 0.85)
    nrm = T.bump(T.math('ADD', T.math('SUBTRACT', 1.0, chipm), T.math('MULTIPLY', T.noise(pv, 60, 3, 0.5).outputs['Factor'], 0.15)), 0.35, 0.0008)
    principled(T, out, c, r, normal=nrm, Coat_Weight=(0.3 if gloss else 0.0))
    return m


@cache
def m_galv(name, col=(150, 152, 150), rough=0.42, grime_amt=0.6, metal=0.85):
    m, T, out = new_mat(name)
    p, pv, _ = coords(T)
    vg = T.n('ShaderNodeTexVoronoi', {'Vector': pv, 'Scale': 35.0})
    sp = T.remap(sepc(T, vg.outputs['Color'])[0], 0, 1, 0.82, 1.06)
    c = T.mul_col(srgb(col), T.comb(sp, sp, sp))
    mp = T.n('ShaderNodeMapping', {'Vector': pv, 'Scale': (14.0, 14.0, 0.8)})
    st = T.noise(mp.outputs[0], 3.0, 6, 0.6)
    streak = T.smooth(st.outputs['Factor'], 0.5, 0.72)
    c = T.mix(T.math('MULTIPLY', streak, 0.5), c, T.mul_col(c, srgb((120, 112, 100))))
    wh = T.noise(pv, 4.0, 6, 0.65)
    white = T.smooth(wh.outputs['Factor'], 0.58, 0.72)
    c = T.mix(T.math('MULTIPLY', white, 0.55), c, srgb((196, 196, 190)))
    c, g = grime(T, c, p, 0.5, grime_amt)
    r = T.math('ADD', T.remap(sp, 0.82, 1.06, rough + 0.1, rough - 0.08), T.math('MULTIPLY', white, 0.3))
    mt = T.mixf(T.math('ADD', white, g), metal, 0.2)
    principled(T, out, c, r, mt, normal=T.bump(st.outputs['Factor'], 0.1, 0.001))
    return m


@cache
def m_metal(name, col, rough, metal=1.0):
    m, T, out = new_mat(name)
    p, pv, _ = coords(T)
    n1 = T.noise(pv, 25.0, 5, 0.6)
    principled(T, out, srgb(col), T.remap(n1.outputs['Factor'], 0.3, 0.7, rough * 0.7, rough * 1.4), metal)
    return m


@cache
def m_iron(name, rust=0.5, polish=False, base=(52, 50, 47)):
    """Cast iron.  polish=True reads point attribute 'h' (raised = traffic-polished)."""
    m, T, out = new_mat(name)
    p, pv, _ = coords(T)
    n1 = T.noise(pv, 12.0, 6, 0.65)
    n2 = T.noise(pv, 2.5, 4, 0.5)
    rn = T.noise(pv, 40.0, 4, 0.6)
    rustc = T.mix(rn.outputs['Factor'], srgb((58, 40, 30)), srgb((104, 66, 42)))
    occ = T.math('SUBTRACT', 1.0, ao(T, 0.03))
    rm = T.math('MULTIPLY', T.math('ADD', T.smooth(n1.outputs['Factor'], 0.62 - 0.2 * rust, 0.72 - 0.2 * rust), T.math('MULTIPLY', occ, 1.4 * rust)), T.smooth(n2.outputs['Factor'], 0.3, 0.55))
    rm = T.math('MINIMUM', rm, 1.0)
    c = T.mix(rm, srgb(base), rustc)
    r = T.mixf(rm, 0.55, 0.85)
    mt = T.mixf(rm, 0.55, 0.0)
    if polish:
        at = T.n('ShaderNodeAttribute', attribute_name='h')
        h = at.outputs['Fac']
        pol = T.smooth(h, 0.55, 0.85)
        c = T.mix(pol, T.mul_col(c, (0.5, 0.48, 0.45, 1)), srgb((112, 108, 102)))
        r = T.mixf(pol, r, 0.32)
        mt = T.mixf(pol, mt, 0.9)
        dirt = T.smooth(h, 0.5, 0.25)
        c = T.mix(T.math('MULTIPLY', dirt, 0.7), c, srgb((40, 34, 28)))
    principled(T, out, c, r, mt, normal=T.bump(n1.outputs['Factor'], 0.25, 0.0015))
    return m


@cache
def m_concrete(name, col=(146, 142, 134), use_cell=True, gum=1.0, stain=1.0, fresh=0.0):
    m, T, out = new_mat(name)
    tc = T.n('ShaderNodeTexCoord')
    p = tc.outputs['Object']
    c = srgb(col)
    if use_cell:
        at = T.n('ShaderNodeAttribute', attribute_name='cell')
        cx, cy, cz = T.xyz(at.outputs['Vector'])
        f = T.remap(cx, 0, 1, 0.80, 1.07)
        c = T.mul_col(c, T.comb(f, f, T.math('MULTIPLY', f, T.remap(cy, 0, 1, 0.93, 1.03))))
    nb = T.noise(p, 0.55, 4, 0.6)
    nm = T.noise(p, 4.0, 6, 0.65)
    f = T.math('MULTIPLY', T.remap(nb.outputs['Factor'], 0.3, 0.7, 0.84, 1.06), T.remap(nm.outputs['Factor'], 0.3, 0.7, 0.93, 1.05))
    c = T.mul_col(c, T.comb(f, f, f))
    # aggregate specks
    vs = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 230.0})
    sp = T.smooth(vs.outputs['Distance'], 0.16, 0.05)
    spc = sepc(T, vs.outputs['Color'])[0]
    c = T.mix(T.math('MULTIPLY', sp, 0.6), c, T.mix(spc, (0.10, 0.10, 0.10, 1), (0.55, 0.52, 0.48, 1)))
    # stains: dark blotches + rusty drips
    if stain > 0:
        ns = T.noise(p, 1.1, 6, 0.62, distortion=0.4)
        st = T.math('MULTIPLY', T.smooth(ns.outputs['Factor'], 0.60, 0.74), 0.55 * stain)
        c = T.mix(st, c, T.mul_col(c, srgb((140, 128, 112))))
    # gum spots
    gm = None
    if gum > 0:
        dn = T.noise(p, 8.0, 2, 0.5)
        pg = T.vmath('ADD', p, T.vmath('SCALE', dn.outputs['Color'], scale=0.025))
        vg = T.n('ShaderNodeTexVoronoi', {'Vector': pg, 'Scale': 4.2})
        sel = T.smooth(sepc(T, vg.outputs['Color'])[1], 1.0 - 0.6 * gum, 1.0 - 0.6 * gum + 0.01)
        gm = T.math('MULTIPLY', T.smooth(vg.outputs['Distance'], 0.030, 0.022), sel)
        gcol = T.mix(sepc(T, vg.outputs['Color'])[2], srgb((38, 38, 38)), srgb((96, 94, 90)))
        c = T.mix(gm, c, gcol)
    # joint / edge grime: border attribute (slabs) + AO
    ea = T.n('ShaderNodeAttribute', attribute_name='edge')
    en = T.noise(p, 9.0, 4, 0.6)
    eg = T.math('MULTIPLY', T.math('POWER', ea.outputs['Fac'], 2.5), T.remap(en.outputs['Factor'], 0.3, 0.7, 0.35, 1.0))
    c = T.mix(T.math('MULTIPLY', eg, 0.75), c, T.mul_col(c, srgb((96, 90, 80))))
    occ = T.math('SUBTRACT', 1.0, ao(T, 0.06))
    c = T.mix(T.math('MULTIPLY', occ, 1.0), c, T.mul_col(c, srgb((70, 66, 60))))
    # broad dirt / foot-traffic grime
    dd = T.noise(p, 0.25, 5, 0.65, distortion=0.6)
    c = T.mix(T.math('MULTIPLY', T.smooth(dd.outputs['Factor'], 0.42, 0.7), 0.6), c, T.mul_col(c, srgb((150, 140, 124))))
    if fresh > 0:
        c = T.mix(fresh, c, srgb((176, 174, 168)))
    # broom finish + pits
    mp = T.n('ShaderNodeMapping', {'Vector': p, 'Scale': (5.0, 160.0, 5.0)})
    br = T.noise(mp.outputs[0], 1.0, 3, 0.5)
    pv = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 90.0})
    pit = T.smooth(pv.outputs['Distance'], 0.07, 0.0)
    h = T.math('ADD', T.math('MULTIPLY', br.outputs['Factor'], 0.5), T.math('MULTIPLY', pit, -0.8))
    h = T.math('ADD', h, T.math('MULTIPLY', nm.outputs['Factor'], 0.3))
    if gm is not None:
        h = T.math('ADD', h, T.math('MULTIPLY', gm, 0.6))
    r = T.remap(nb.outputs['Factor'], 0.3, 0.7, 0.82, 0.95)
    if gm is not None:
        r = T.mixf(gm, r, 0.55)
    principled(T, out, c, r, normal=T.bump(h, 0.3, 0.002))
    return m


@cache
def m_granite(name, col=(134, 131, 126), concrete=False):
    m, T, out = new_mat(name)
    tc = T.n('ShaderNodeTexCoord')
    p = tc.outputs['Object']
    geo = T.n('ShaderNodeNewGeometry')
    vg = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 260.0 if not concrete else 200.0})
    wv = sepc(T, vg.outputs['Color'])[0]
    if not concrete:
        grain = T.ramp(wv, [(0.0, srgb((26, 26, 28))), (0.22, srgb((112, 110, 106))), (0.7, srgb((176, 170, 162))), (0.86, srgb((206, 196, 186)))], 'CONSTANT')
        c = T.mix(0.55, srgb(col), grain)
    else:
        c = T.mix(T.math('MULTIPLY', T.smooth(vg.outputs['Distance'], 0.15, 0.05), 0.4), srgb(col), srgb((90, 88, 84)))
    n1 = T.noise(p, 1.2, 5, 0.6)
    f = T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.85, 1.08)
    c = T.mul_col(c, T.comb(f, f, f))
    z = T.xyz(p)[2]
    up = T.xyz(geo.outputs['Normal'])[2]
    nz = T.noise(p, 6.0, 5, 0.6)
    # road grime on the face, darker toward the gutter; tyre scuffs
    low = T.math('MULTIPLY', T.smooth(z, -0.02, -0.15), T.remap(nz.outputs['Factor'], 0.3, 0.7, 0.4, 1.0))
    side = T.smooth(up, 0.6, 0.2)
    c = T.mix(T.math('MULTIPLY', T.math('MULTIPLY', low, side), 0.85), c, T.mul_col(c, srgb((70, 64, 58))))
    mp = T.n('ShaderNodeMapping', {'Vector': p, 'Scale': (2.0, 2.0, 40.0)})
    sc = T.noise(mp.outputs[0], 2.0, 4, 0.6)
    scuff = T.math('MULTIPLY', T.math('MULTIPLY', T.smooth(sc.outputs['Factor'], 0.62, 0.75), side), T.smooth(z, -0.03, -0.09))
    c = T.mix(T.math('MULTIPLY', scuff, 0.8), c, srgb((22, 21, 20)))
    occ = T.math('SUBTRACT', 1.0, ao(T, 0.04))
    c = T.mix(T.math('MULTIPLY', occ, 0.8), c, T.mul_col(c, srgb((80, 74, 66))))
    worn = T.math('MULTIPLY', T.smooth(up, 0.7, 0.95), 0.25)
    c = T.mix(worn, c, T.mul_col(c, (1.12, 1.12, 1.10, 1)))
    r = T.mixf(T.smooth(up, 0.7, 0.95), 0.68, 0.5)
    h = T.math('ADD', T.math('MULTIPLY', vg.outputs['Distance'], 0.3), T.math('MULTIPLY', nz.outputs['Factor'], 0.5))
    principled(T, out, c, r, normal=T.bump(h, 0.25, 0.0015))
    return m


@cache
def m_asphalt(name, masks=True, patch=0.0, base=(62, 61, 59)):
    m, T, out = new_mat(name)
    tc = T.n('ShaderNodeTexCoord')
    p = tc.outputs['Object']
    if masks:
        mp = T.n('ShaderNodeMapping', {'Vector': p, 'Location': (0.5, 0.5, 0.0), 'Scale': (0.05, 0.05, 1.0)})
        A = tex(T, "road_a.png", mp.outputs[0], True, 'CLIP')
        B = tex(T, "road_b.png", mp.outputs[0], True, 'CLIP')
        crack, stain, wet = sepc(T, A.outputs['Color'])
        ptch = A.outputs['Alpha']
        seal, wheel, rav = sepc(T, B.outputs['Color'])
    else:
        crack, stain, wet, seal, wheel = 0.0, 0.25, 0.0, 0.0, 0.0
        ptch = patch
        rav = T.noise(p, 3.0, 4, 0.6).outputs['Factor']
    vo = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 150.0})
    stone_v = sepc(T, vo.outputs['Color'])[0]
    stone_c = T.ramp(stone_v, [(0.0, srgb((70, 68, 66))), (0.4, srgb((112, 110, 106))), (0.75, srgb((140, 134, 126))), (0.92, srgb((168, 160, 150)))])
    smask = T.smooth(vo.outputs['Distance'], 0.34, 0.20)
    E = T.math('ADD', T.math('ADD', 0.25, T.math('MULTIPLY', rav, 0.55)), T.math('MULTIPLY', wheel, 0.25))
    E = T.math('MULTIPLY', E, T.math('SUBTRACT', 1.0, T.math('MULTIPLY', ptch, 0.75)), clamp=True)
    nb = T.noise(p, 0.35, 4, 0.6)
    nmid = T.noise(p, 3.0, 6, 0.6)
    bf = T.math('MULTIPLY', T.remap(nb.outputs['Factor'], 0.3, 0.7, 0.85, 1.12), T.remap(nmid.outputs['Factor'], 0.3, 0.7, 0.92, 1.06))
    binder = T.mul_col(srgb(base), T.comb(bf, bf, bf))
    binder = T.mix(ptch, binder, srgb((34, 34, 34)))
    c = T.mix(T.math('MULTIPLY', smask, E), binder, stone_c)
    fs = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 650.0})
    fsp = T.smooth(fs.outputs['Distance'], 0.25, 0.05)
    c = T.mix(T.math('MULTIPLY', fsp, 0.35), c, srgb((150, 146, 140)))
    # oil / grime
    c = T.mix(T.math('MULTIPLY', stain, 0.75), c, T.mul_col(c, srgb((70, 66, 62))))
    c = T.mix(T.math('MULTIPLY', wheel, 0.25), c, T.mul_col(c, srgb((150, 150, 150))))
    c = T.mix(seal, c, srgb((16, 16, 16)))
    c = T.mix(crack, c, srgb((10, 10, 10)))
    wetf = T.math('MULTIPLY', wet, 1.0)
    c = T.mix(T.math('MULTIPLY', wetf, 0.55), c, T.mul_col(c, srgb((90, 90, 92))))
    r = T.remap(nmid.outputs['Factor'], 0.3, 0.7, 0.78, 0.92)
    r = T.mixf(T.math('MULTIPLY', stain, 0.6), r, 0.55)
    r = T.mixf(T.math('MULTIPLY', wheel, 0.5), r, 0.6)
    r = T.mixf(seal, r, 0.35)
    r = T.mixf(T.smooth(wetf, 0.15, 0.6), r, 0.04)
    h = T.math('ADD', T.math('MULTIPLY', T.math('MULTIPLY', smask, E), 0.8), T.math('MULTIPLY', nmid.outputs['Factor'], 0.25))
    h = T.math('SUBTRACT', h, T.math('MULTIPLY', crack, 1.6))
    h = T.math('MULTIPLY', h, T.math('SUBTRACT', 1.0, T.math('MULTIPLY', T.smooth(wetf, 0.5, 0.9), 0.9)))
    principled(T, out, c, r, normal=T.bump(h, 0.55, 0.004))
    return m


@cache
def m_thermo(name, col=(228, 226, 216), wear=0.5):
    m, T, out = new_mat(name)
    tc = T.n('ShaderNodeTexCoord')
    p = tc.outputs['Object']
    mp = T.n('ShaderNodeMapping', {'Vector': p, 'Location': (0.5, 0.5, 0.0), 'Scale': (0.05, 0.05, 1.0)})
    B = tex(T, "road_b.png", mp.outputs[0], True, 'CLIP')
    wheel = sepc(T, B.outputs['Color'])[1]
    n1 = T.noise(p, 4.0, 8, 0.72, distortion=0.25)
    w = T.math('ADD', n1.outputs['Factor'], T.math('MULTIPLY', wheel, 0.35 * wear))
    hole = T.smooth(w, 0.80 - 0.18 * wear, 0.82 - 0.18 * wear)
    vc = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 9.0}, feature='DISTANCE_TO_EDGE')
    craze = T.smooth(vc.outputs['Distance'], 0.03, 0.0)
    hole = T.math('MAXIMUM', hole, T.math('MULTIPLY', craze, T.smooth(n1.outputs['Factor'], 0.45, 0.6)))
    dn = T.noise(p, 1.2, 5, 0.6)
    d = T.remap(dn.outputs['Factor'], 0.3, 0.7, 0.62, 0.95)
    c = T.mul_col(srgb(col), T.comb(d, d, d))
    c = T.mix(T.math('MULTIPLY', wheel, 0.5), c, T.mul_col(c, srgb((120, 118, 112))))
    vs = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 160.0})
    c = T.mix(T.math('MULTIPLY', T.smooth(vs.outputs['Distance'], 0.2, 0.05), 0.4), c, srgb((80, 78, 74)))
    pr = principled(T, None, c, T.remap(dn.outputs['Factor'], 0.3, 0.7, 0.45, 0.7), normal=T.bump(T.math('ADD', vs.outputs['Distance'], craze), 0.3, 0.0015))
    tr = T.n('ShaderNodeBsdfTransparent')
    ms = T.n('ShaderNodeMixShader', {'Fac': hole})
    T.L.new(pr.outputs[0], ms.inputs[1])
    T.L.new(tr.outputs[0], ms.inputs[2])
    T.L.new(ms.outputs[0], out.inputs['Surface'])
    return m


@cache
def m_image(name, image, rough=0.4, alpha=False, emit=0.0, dirt=0.4, noncolor=False, metal=0.0, interp='Linear', ext='EXTEND'):
    """UV-mapped image (signs, decals).  alpha=True cuts out by the image alpha."""
    m, T, out = new_mat(name)
    p, pv, tc = coords(T)
    t = tex(T, image, tc.outputs['UV'], noncolor, ext, interp)
    c = t.outputs['Color']
    dn = T.noise(pv, 6.0, 6, 0.6)
    if dirt > 0:
        d = T.math('MULTIPLY', T.smooth(dn.outputs['Factor'], 0.45, 0.75), dirt)
        c = T.mix(d, c, T.mul_col(c, srgb((150, 138, 118))))
    pr = principled(T, None, c, T.remap(dn.outputs['Factor'], 0.3, 0.7, rough * 0.8, rough * 1.3), metal)
    if emit > 0:
        T.set(pr.inputs['Emission Color'], t.outputs['Color'])
        pr.inputs['Emission Strength'].default_value = emit
    sh = pr.outputs[0]
    if alpha:
        tr = T.n('ShaderNodeBsdfTransparent')
        ms = T.n('ShaderNodeMixShader')
        T.L.new(t.outputs['Alpha'], ms.inputs['Fac'])
        T.L.new(tr.outputs[0], ms.inputs[1])
        T.L.new(sh, ms.inputs[2])
        sh = ms.outputs[0]
    T.L.new(sh, out.inputs['Surface'])
    return m


@cache
def m_emit(name, col, strength, glass=True):
    m, T, out = new_mat(name)
    em = T.n('ShaderNodeEmission', {'Color': (*col, 1.0), 'Strength': strength})
    em.name = "LampEmit"
    if glass:
        pr = principled(T, None, (*[c * 0.3 for c in col], 1.0), 0.08, Coat_Weight=1.0)
        add = T.n('ShaderNodeAddShader')
        T.L.new(pr.outputs[0], add.inputs[0])
        T.L.new(em.outputs[0], add.inputs[1])
        T.L.new(add.outputs[0], out.inputs['Surface'])
    else:
        T.L.new(em.outputs[0], out.inputs['Surface'])
    return m


@cache
def m_lens(name, col):
    """Unlit signal lens: tinted, glossy, slightly dusty."""
    m, T, out = new_mat(name)
    p, pv, _ = coords(T)
    dn = T.noise(pv, 8.0, 5, 0.6)
    principled(T, out, (*col, 1.0), T.remap(dn.outputs['Factor'], 0.3, 0.7, 0.08, 0.3), Coat_Weight=1.0)
    return m


@cache
def m_plain(name, col, rough=0.5, metal=0.0, noise=0.15, scale=8.0, sss=0.0, coat=0.0):
    m, T, out = new_mat(name)
    p, pv, _ = coords(T)
    n1 = T.noise(pv, scale, 5, 0.6)
    f = T.remap(n1.outputs['Factor'], 0.3, 0.7, 1 - noise, 1 + noise * 0.8)
    principled(T, out, T.mul_col(srgb(col), T.comb(f, f, f)), T.remap(n1.outputs['Factor'], 0.3, 0.7, rough * 0.85, min(1.0, rough * 1.2)), metal,
               normal=T.bump(n1.outputs['Factor'], 0.1, 0.002), Coat_Weight=coat)
    return m


@cache
def m_plastic_bag(name):
    m, T, out = new_mat(name)
    p, pv, _ = coords(T)
    n1 = T.noise(pv, 14.0, 6, 0.6)
    c = T.mul_col(srgb((22, 22, 24)), T.comb(*([T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.8, 1.3)] * 3)))
    principled(T, out, c, T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.22, 0.45), normal=T.bump(n1.outputs['Factor'], 0.25, 0.004), Coat_Weight=0.2)
    return m


@cache
def m_attr(name, rough=0.5, sss=False, transl=0.0, bump=0.0):
    """Base colour from the per-face 'cell' attribute (leaves, litter, bark variants)."""
    m, T, out = new_mat(name)
    p, pv, _ = coords(T)
    at = T.n('ShaderNodeAttribute', attribute_name='cell')
    n1 = T.noise(pv, 30.0, 5, 0.6)
    f = T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.82, 1.12)
    c = T.mul_col(at.outputs['Color'], T.comb(f, f, f))
    pr = principled(T, None, c, T.remap(n1.outputs['Factor'], 0.3, 0.7, rough * 0.8, min(1, rough * 1.25)),
                    normal=(T.bump(n1.outputs['Factor'], bump, 0.002) if bump > 0 else None))
    sh = pr.outputs[0]
    if transl > 0:
        tl = T.n('ShaderNodeBsdfTranslucent')
        T.set(tl.inputs['Color'], T.mul_col(c, (1.2, 1.15, 0.6, 1)))
        ms = T.n('ShaderNodeMixShader', {'Fac': transl})
        T.L.new(sh, ms.inputs[1])
        T.L.new(tl.outputs[0], ms.inputs[2])
        sh = ms.outputs[0]
    T.L.new(sh, out.inputs['Surface'])
    return m


@cache
def m_bark(name):
    m, T, out = new_mat(name)
    p, pv, _ = coords(T)
    mp = T.n('ShaderNodeMapping', {'Vector': pv, 'Scale': (9.0, 9.0, 3.2)})
    n1 = T.noise(mp.outputs[0], 3.0, 10, 0.75, distortion=1.2)
    vo = T.n('ShaderNodeTexVoronoi', {'Vector': T.vmath('ADD', mp.outputs[0], T.vmath('SCALE', n1.outputs['Color'], scale=0.35)), 'Scale': 2.2}, feature='DISTANCE_TO_EDGE')
    ridge = T.math('MULTIPLY', T.smooth(vo.outputs['Distance'], 0.0, 0.10), T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.6, 1.0))
    c = T.mix(ridge, srgb((44, 38, 32)), srgb((112, 104, 94)))
    lic = T.noise(pv, 5.0, 5, 0.6)
    c = T.mix(T.math('MULTIPLY', T.smooth(lic.outputs['Factor'], 0.6, 0.7), 0.5), c, srgb((110, 118, 90)))
    c, _g = grime(T, c, p, 0.4, 0.6)
    principled(T, out, c, 0.88, normal=T.bump(T.math('ADD', ridge, T.math('MULTIPLY', n1.outputs['Factor'], 0.6)), 1.0, 0.015))
    return m


@cache
def m_soil(name):
    m, T, out = new_mat(name)
    p, pv, _ = coords(T)
    n1 = T.noise(pv, 6.0, 8, 0.7)
    vo = T.n('ShaderNodeTexVoronoi', {'Vector': pv, 'Scale': 70.0})
    peb = T.smooth(vo.outputs['Distance'], 0.25, 0.1)
    c = T.mix(n1.outputs['Factor'], srgb((40, 30, 22)), srgb((74, 60, 46)))
    c = T.mix(T.math('MULTIPLY', peb, 0.5), c, srgb((120, 112, 100)))
    principled(T, out, c, 0.95, normal=T.bump(T.math('ADD', n1.outputs['Factor'], peb), 0.6, 0.01))
    return m


@cache
def m_water(name):
    """Shallow puddle: fresnel mix of transparency (road shows through) and a sharp mirror."""
    m, T, out = new_mat(name)
    p, pv, _ = coords(T)
    n1 = T.noise(pv, 2.0, 3, 0.5)
    nrm = T.bump(n1.outputs['Factor'], 0.03, 0.003)
    fr = T.n('ShaderNodeFresnel', {'IOR': 1.33})
    T.set(fr.inputs['Normal'], nrm)
    gl = T.n('ShaderNodeBsdfGlossy', {'Color': (0.9, 0.9, 0.9, 1), 'Roughness': 0.015})
    T.set(gl.inputs['Normal'], nrm)
    tr = T.n('ShaderNodeBsdfTransparent', {'Color': (0.82, 0.80, 0.76, 1)})
    ms = T.n('ShaderNodeMixShader')
    T.L.new(fr.outputs[0], ms.inputs['Fac'])
    T.L.new(tr.outputs[0], ms.inputs[1])
    T.L.new(gl.outputs[0], ms.inputs[2])
    T.L.new(ms.outputs[0], out.inputs['Surface'])
    return m


@cache
def m_glass(name, tint=(0.92, 0.94, 0.93), dirt=0.15, rough=0.02):
    m, T, out = new_mat(name)
    p, pv, _ = coords(T)
    dn = T.noise(pv, 5.0, 6, 0.6)
    r = T.remap(dn.outputs['Factor'], 0.4, 0.8, rough, rough + 0.12)
    pr = principled(T, None, (*tint, 1), r, Transmission_Weight=1.0, IOR=1.5)
    pr.inputs['Thin Wall'].default_value = True
    dif = T.n('ShaderNodeBsdfDiffuse', {'Color': srgb((120, 114, 104))})
    ms = T.n('ShaderNodeMixShader', {'Fac': T.remap(dn.outputs['Factor'], 0.45, 0.85, 0.0, dirt)})
    T.L.new(pr.outputs[0], ms.inputs[1])
    T.L.new(dif.outputs[0], ms.inputs[2])
    T.L.new(ms.outputs[0], out.inputs['Surface'])
    return m


@cache
def m_dark(name, col=(8, 8, 8)):
    m, T, out = new_mat(name)
    principled(T, out, srgb(col), 0.9)
    return m
