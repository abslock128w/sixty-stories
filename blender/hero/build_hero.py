"""Build VESPER -> /home/user/sixty/blender/out/hero.blend (deterministic).

    /home/user/tools/bl/bin/python /home/user/sixty/blender/hero/build_hero.py
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
import bpy

import math
from mathutils import Vector, Matrix

import build_body
import helmet
import mask
import suit_fields
import gear
import hero_materials as HM
import hero_web

OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'hero.blend'))


def log(*a):
    print('[hero]', *a, flush=True)


def subdivide_once(ob):
    """apply one Catmull-Clark level to the base mesh (weights + UVs are interpolated)."""
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    m = ob.modifiers.new('pre_sub', 'SUBSURF')
    m.levels = 1
    m.uv_smooth = 'PRESERVE_BOUNDARIES'
    bpy.ops.object.modifier_apply(modifier=m.name)


def mesh_arrays(me):
    P = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get('co', P)
    P = P.reshape(-1, 3)
    F = [tuple(p.vertices) for p in me.polygons]
    return P, F


def vertex_weights(ob):
    me = ob.data
    W = {vg.name: np.zeros(len(me.vertices)) for vg in ob.vertex_groups}
    names = {vg.index: vg.name for vg in ob.vertex_groups}
    for v in me.vertices:
        for g in v.groups:
            W[names[g.group]][v.index] = g.weight
    return W


def set_attr(me, name, arr, kind='FLOAT', domain='POINT'):
    if name in me.attributes:
        me.attributes.remove(me.attributes[name])
    a = me.attributes.new(name, kind, domain)
    arr = np.asarray(arr, float)
    if kind == 'FLOAT':
        a.data.foreach_set('value', arr.ravel())
    else:
        a.data.foreach_set('vector', arr.ravel())


def delete_faces(ob, face_mask):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    kill = [bm.faces[i] for i in np.nonzero(face_mask)[0]]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(ob.data)
    bm.free()


def build_body_and_rig(sc):
    t = time.time()
    d = build_body.build_body_data()
    body = build_body.make_mesh('HERO_body', d)
    sc.collection.objects.link(body)
    rig = build_body.make_armature(d)
    subdivide_once(body)
    P, F = mesh_arrays(body.data)
    log('body subdivided', len(P), 'verts', round(time.time() - t, 1), 's')
    md = mask.build(P, F)
    # the body's own head and upper neck live under the hood: remove them
    W0 = vertex_weights(body)
    P, hid = mask.tuck_body(P, md, W0.get('head', np.zeros(len(P))))
    body.data.vertices.foreach_set('co', P.ravel()); body.data.update()
    hid |= (P[:, 2] > 1.585) & (W0.get('head', 0) > 0.5) & (np.abs(P[:, 0]) < 0.12)
    delete_faces(body, np.array([hid[list(f)].all() for f in F]))
    P, F = mesh_arrays(body.data)
    W = vertex_weights(body)
    log('head trimmed', len(P), 'verts')
    flds = suit_fields.compute(P, F, d['joints'], W)
    me = body.data
    set_attr(me, 'rest', P, 'FLOAT_VECTOR')
    wrk, wrk_t = wrinkle_fields(P, d['joints'])
    set_attr(me, 'wrk', wrk); set_attr(me, 'wrk_t', wrk_t)
    wsd, ink = suit_fields.sail_fields(P, d['joints'], W, flds['grip'], flds['inner_f'], flds['side_f'])
    set_attr(me, 'white_sd', wsd)
    set_attr(me, 'ink_f', ink)
    log('fields', round(time.time() - t, 1), 's')
    d['P_final'] = P; d['F_final'] = F; d['W_final'] = W; d['mask'] = md
    return d, body, rig, flds


def wrinkle_fields(P, J):
    j = lambda n: np.array(J[n + '____head'])
    items = []
    for s in 'LR':
        items += [
            (j(f'lowerarm01.{s}'), j(f'wrist.{s}') - j(f'upperarm02.{s}'), 0.05, 1.0),
            (j(f'lowerleg01.{s}'), j(f'foot.{s}') - j(f'upperleg02.{s}'), 0.055, 0.9),
            (j(f'upperarm01.{s}') + np.array([0, 0.0, -0.07]), j(f'lowerarm01.{s}') - j(f'upperarm01.{s}'), 0.05, 0.6),
            (j(f'upperleg01.{s}') + np.array([0, -0.06, -0.02]), j(f'lowerleg01.{s}') - j(f'upperleg01.{s}'), 0.05, 0.5),
            (j(f'foot.{s}') + np.array([0, -0.02, 0.0]), j(f'foot.{s}') - j(f'lowerleg01.{s}'), 0.035, 0.5),
            (j(f'wrist.{s}'), j(f'wrist.{s}') - j(f'lowerarm01.{s}'), 0.03, 0.4),
        ]
    items.append((np.array([0, -0.02, 1.07]), np.array([0, 0, 1.0]), 0.06, 0.55))
    best = np.zeros(len(P)); wt = np.zeros(len(P)); tot = np.zeros(len(P))
    for c, ax, sig, st in items:
        ax = ax / np.linalg.norm(ax)
        g = st * np.exp(-0.5 * (np.linalg.norm(P - c, axis=1) / sig) ** 2)
        t = (P - c) @ ax
        upd = g > best
        wt[upd] = t[upd]; best[upd] = g[upd]
        tot += g
    return np.clip(tot, 0, 1), wt


def link(ob, col):
    for c in ob.users_collection:
        c.objects.unlink(ob)
    col.objects.link(ob)


def rigid(ob, rig, bone):
    ob.parent = rig
    vg = ob.vertex_groups.new(name=bone)
    vg.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
    m = ob.modifiers.new('Armature', 'ARMATURE'); m.object = rig
    return ob


def copy_weights(ob, rig, P, W, k=4):
    """skin a gear mesh with the weights of the nearest body vertices (inverse distance)."""
    ob.parent = rig
    co = np.zeros(len(ob.data.vertices) * 3); ob.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    names = [n for n in W if W[n].max() > 0]
    WM = np.stack([W[n] for n in names], 1)
    groups = {n: ob.vertex_groups.new(name=n) for n in names}
    for i, p in enumerate(co):
        d = np.linalg.norm(P - p, axis=1)
        nn = np.argpartition(d, k)[:k]
        w = 1.0 / (d[nn] + 1e-4)
        ww = (WM[nn] * w[:, None]).sum(0) / w.sum()
        for gi in np.nonzero(ww > 0.01)[0]:
            groups[names[gi]].add([i], float(ww[gi]), 'REPLACE')
    m = ob.modifiers.new('Armature', 'ARMATURE'); m.object = rig
    return ob


def build_gear(d, rig, mats):
    J = d['joints']
    P, F = d['P_final'], d['F_final']
    sh = gear.Shaper(P, F, J)
    objs = []
    nozzles = {}
    for s in 'LR':
        mx = 1 if s == 'L' else -1
        M = lambda v: (v[0] * mx, v[1], v[2])
        dn = build_body._dorsal(J, s)
        def chamfer(h0, h1, c=0.3, e=0.14):
            return lambda tt: (h0 + (h1 - h0) * tt) * (1 - c * max(0.0, 1 - min(tt, 1 - tt) / e))
        # shoulder cap
        V, Fc = sh.plate(f'shoulder01.{s}', f'lowerarm01.{s}', 0.13, 0.43, M((0.6, 0.2, 1)),
                         chamfer(0.86, 0.66, 0.35, 0.22), H=0.0045, R=0.0018)
        o = gear.mesh_object(f'HERO_plate_shoulder.{s}', V, Fc, [mats['armor']])
        objs.append(rigid(o, rig, f'upperarm01.{s}'))
        # second, smaller layer on top: reads as a designed, stacked moulding
        V, Fc = sh.plate(f'shoulder01.{s}', f'lowerarm01.{s}', 0.18, 0.38, M((0.6, 0.2, 1)),
                         chamfer(0.60, 0.46, 0.4, 0.25), H=0.0022, R=0.0012, base=0.0015 + 0.0045 - 0.0006)
        o = gear.mesh_object(f'HERO_plate_shoulder2.{s}', V, Fc, [mats['armor']])
        objs.append(rigid(o, rig, f'upperarm01.{s}'))
        # forearm guard (elbow half, dorsal)
        V, Fc = sh.plate(f'lowerarm01.{s}', f'wrist.{s}', 0.07, 0.585, dn,
                         chamfer(0.95, 0.70, 0.3, 0.12), H=0.0048, R=0.002)
        o = gear.mesh_object(f'HERO_plate_forearm.{s}', V, Fc, [mats['armor']])
        objs.append(rigid(o, rig, f'lowerarm01.{s}'))
        # shin guard
        V, Fc = sh.plate(f'lowerleg01.{s}', f'foot.{s}', 0.12, 0.80, M((0.15, -1, 0)),
                         chamfer(0.78, 0.52, 0.35), H=0.0055, R=0.0022)
        o = gear.mesh_object(f'HERO_plate_shin.{s}', V, Fc, [mats['armor']])
        objs.append(rigid(o, rig, f'lowerleg01.{s}'))
        # knee cap
        V, Fc = sh.plate(f'upperleg02.{s}', f'lowerleg01.{s}', 0.86, 1.10, M((0.1, -1, 0)),
                         chamfer(0.85, 0.70, 0.4, 0.3), H=0.0065, R=0.0025)
        o = gear.mesh_object(f'HERO_plate_knee.{s}', V, Fc, [mats['armor']])
        objs.append(rigid(o, rig, f'lowerleg01.{s}'))
        # ---- line launcher (lowerarm02): dorsal housing, cuff, ventral barrel + nozzle
        Vh, Fh = sh.plate(f'lowerarm01.{s}', f'wrist.{s}', 0.60, 0.90, dn,
                          chamfer(0.58, 0.50, 0.3, 0.22), H=0.0078, R=0.0045, base=0.002)
        Vc, Fcf = sh.plate(f'lowerarm01.{s}', f'wrist.{s}', 0.835, 0.895, dn, None, H=0.0024,
                           R=0.0012, base=0.0012, wrap=True, nt=8, na=72)
        Vi, Fi = sh.plate(f'lowerarm01.{s}', f'wrist.{s}', 0.67, 0.80, dn,
                          lambda tt: 0.035, H=0.0008, R=0.0004, base=0.002 + 0.0078 - 0.0003, nt=10, na=6)
        # barrel on the inner (palm) side
        A = np.array(J[f'lowerarm01.{s}____head']); B = np.array(J[f'wrist.{s}____head'])
        ax = (B - A) / np.linalg.norm(B - A)
        c = A + (B - A) * 0.80
        dv = -np.array(dn); dv -= ax * dv.dot(ax); dv /= np.linalg.norm(dv)
        surf = sh.cast(c, dv)
        bc = surf + dv * 0.0085
        barrel = gear.bevel_cyl('barrel', 0.0068, 0.05, bevel=0.0015)
        tip = gear.bevel_cyl('tip', 0.0042, 0.016, bevel=0.0008, r2=0.0036)
        bore = gear.bevel_cyl('bore', 0.0022, 0.004, bevel=0.0003)
        Mb = Matrix.Translation(Vector(bc)) @ Vector((0, 0, 1)).rotation_difference(Vector(ax)).to_matrix().to_4x4()
        Mt = Mb @ Matrix.Translation((0, 0, 0.032))
        Mbore = Mb @ Matrix.Translation((0, 0, 0.0385))
        # strut joining barrel to the cuff
        strut = gear.bevel_box('strut', (0.006, 0.006, 0.010), bevel=0.0012)
        Ms = Matrix.Translation(Vector(bc - dv * 0.006)) @ Vector((0, 0, 1)).rotation_difference(Vector(ax)).to_matrix().to_4x4() @ Matrix.Translation((0, 0, 0.012))
        hard = gear.merge_meshes('launcher_hard', [(barrel, Mb, 0), (tip, Mt, 0), (bore, Mbore, 1), (strut, Ms, 0)])
        for me_ in (barrel, tip, bore, strut):
            bpy.data.meshes.remove(me_)
        oh = gear.mesh_object(f'HERO_launcher.{s}', Vh, Fh, [mats['armor']])
        oc = gear.mesh_object(f'HERO_launcher_cuff.{s}', Vc, Fcf, [mats['gunmetal']])
        oi = gear.mesh_object(f'HERO_launcher_light.{s}', Vi, Fi, [mats['amber']])
        ob = bpy.data.objects.new(f'HERO_launcher_barrel.{s}', hard)
        hard.materials.append(mats['gunmetal']); hard.materials.append(mats['rubber'])
        for o in (oh, oc, oi, ob):
            objs.append(rigid(o, rig, f'lowerarm02.{s}'))
        nozzles[s] = (bc + ax * 0.0405, ax)
    # ---- shoes: capsule envelope of each foot (toes swallowed), deform with foot + toes
    for s in 'LR':
        ank = np.array(J[f'foot.{s}____head'])
        tips = np.array([J[f'toe{k}-{3 if k > 1 else 2}.{s}____tail'] for k in range(1, 6)]).mean(0)
        heel = ank + np.array([0, 0.045, -0.035])
        toe = tips + np.array([0, 0.02, 0.008])
        zc = ank[2] + 0.028
        Vs, NR, NP = gear.shoe_shell(sh.bvh, heel, toe, z_collar=zc, ankle=ank)
        V2, F2 = gear.shoe_mesh(Vs, NR, NP, 9.0)
        o = gear.mesh_object(f'HERO_shoe.{s}', V2, F2, [mats['shoe']])
        objs.append(copy_weights(o, rig, P, d['W_final']))
        # instep strap: a band over the shoe (ray-cast against the shoe shell)
        from mathutils.bvhtree import BVHTree as _B
        sb = gear.Shaper(V2, F2, J)
        Vst, Fst = sb.plate(heel, toe, 0.44, 0.56, (0, 0, 1), lambda tt: 1.2, H=0.0026, R=0.001,
                            base=0.0004, nt=8, na=40, smooth_iters=3)
        o2 = gear.mesh_object(f'HERO_boot_strap.{s}', Vst, Fst, [mats['strap']])
        o2.data.attributes.new('strap_uv', 'FLOAT_VECTOR', 'POINT')
        objs.append(copy_weights(o2, rig, P, d['W_final']))
    # ---- chest kite: amber outline + inner diamond, slightly raised
    def kite_pts(cx, top, mid, bot, hw, n=24):
        corners = [(cx, top), (cx + hw, mid), (cx, bot), (cx - hw, mid), (cx, top)]
        out = []
        for (x0, z0), (x1, z1) in zip(corners[:-1], corners[1:]):
            for k in range(n):
                t = k / n
                out.append((x0 + (x1 - x0) * t, z0 + (z1 - z0) * t))
        return out
    def ring(outer, inner, base, H):
        Vr, Fr = [], []
        n = len(outer)
        def proj(xz, off):
            p = sh.cast((xz[0], -0.4, xz[1]), (0, 1, 0))
            return p + np.array([0, -1, 0]) * off
        for (xz_o, xz_i) in zip(outer, inner):
            Vr += [proj(xz_o, base - 0.002), proj(xz_o, base + H), proj(xz_i, base + H), proj(xz_i, base - 0.002)]
        for k in range(n):
            a = 4 * k; b = 4 * ((k + 1) % n)
            for q in range(3):
                Fr.append((a + q, b + q, b + q + 1, a + q + 1))
        return Vr, Fr
    outer = kite_pts(0, 1.398, 1.352, 1.282, 0.026)
    inner = kite_pts(0, 1.389, 1.352, 1.296, 0.0205)
    V1, F1 = ring(outer, inner, 0.0012, 0.0012)
    o1 = kite_pts(0, 1.371, 1.350, 1.322, 0.0085)
    Vc = [sh.cast((x, -0.4, z), (0, 1, 0)) + np.array([0, -0.0024, 0]) for x, z in o1]
    cen = sh.cast((0, -0.4, 1.348), (0, 1, 0)) + np.array([0, -0.0027, 0])
    nb = len(V1)
    V1 = list(V1) + Vc + [cen]
    for k in range(len(Vc)):
        F1.append((nb + k, nb + (k + 1) % len(Vc), nb + len(Vc)))
    o = gear.mesh_object('HERO_kite', np.array(V1), F1, [mats['inlay']])
    objs.append(copy_weights(o, rig, P, d['W_final']))
    # ---- harness: hip belt, shoulder straps over the traps meeting a back plate where
    # the piping chevrons meet, chest strap; all real thickness + stitching
    import suit_fields as SF
    surf = SF.Surf(P, F, J)
    def strap(name, ctrl, width, H=0.0028, base=0.0016, closed=False):
        Vr, Fr, UVr = gear.ribbon(surf, ctrl, width=width, H=H, base=base, closed=closed)
        o = gear.mesh_object(name, Vr, Fr, [mats['strap']])
        at = o.data.attributes.new('strap_uv', 'FLOAT_VECTOR', 'POINT')
        at.data.foreach_set('vector', np.concatenate([UVr, np.zeros((len(UVr), 1))], 1).ravel())
        return copy_weights(o, rig, P, d['W_final'])
    objs.append(strap('HERO_belt', [surf.torso(0.995, a_) for a_ in range(0, 361, 6)], 0.040, H=0.0034, closed=True))
    for s_, mx in (('L', 1), ('R', -1)):
        def tz(z, ang, sgn=mx):
            return surf.torso(z, ang if sgn > 0 else 360 - ang)
        trap = surf.cast((0.105 * mx, 0.035, 1.40), (0, 0, 1))
        ctrl = [tz(1.02, 27), tz(1.235, 27), tz(1.37, 31), trap, tz(1.37, 156), tz(1.215, 172)]
        objs.append(strap(f'HERO_strap_shoulder.{s_}', ctrl, 0.030, base=0.0019 + (0.0006 if s_ == 'R' else 0)))
    objs.append(strap('HERO_strap_back', [surf.torso(1.19, 180), surf.torso(1.02, 180)], 0.030))
    objs.append(strap('HERO_strap_chest', [surf.torso(1.235, 36), surf.torso(1.238, 0), surf.torso(1.235, 324)], 0.024, base=0.0042))
    # back plate (meeting point of straps and piping chevrons) and chest buckle
    pb = surf.torso(1.20, 180)
    disc = gear.bevel_cyl('backplate', 0.022, 0.006, bevel=0.0018, verts=40)
    ringm = gear.torus_mesh('bpring', 0.0145, 0.0012, nu=48, nv=10)
    Mb = Matrix.Translation(Vector(pb + np.array([0, 0.0068, 0]))) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
    mm = gear.merge_meshes('backplate_m', [(disc, Mb, 0), (ringm, Mb @ Matrix.Translation((0, 0, -0.0031)), 1)])
    bpy.data.meshes.remove(disc); bpy.data.meshes.remove(ringm)
    mm.materials.append(mats['gunmetal']); mm.materials.append(mats['inlay'])
    o = bpy.data.objects.new('HERO_backplate', mm)
    objs.append(copy_weights(o, rig, P, d['W_final']))
    pc = surf.torso(1.238, 0)
    bx = gear.bevel_box('chestbuckle', (0.036, 0.009, 0.03), bevel=0.003, segs=3)
    bx.transform(Matrix.Translation(Vector(pc + np.array([0, -0.009, 0]))))
    bx.materials.append(mats['gunmetal'])
    o = bpy.data.objects.new('HERO_chest_buckle', bx)
    objs.append(copy_weights(o, rig, P, d['W_final']))
    # ---- neck gaiter: short ribbed collar from the neck base up under the cowl rim
    A0 = np.array([0, 0.040, 1.44]); A1 = np.array([0, 0.004, 1.63])
    axg = (A1 - A0) / np.linalg.norm(A1 - A0)
    e1 = np.array([0, -1.0, 0]); e1 -= axg * e1.dot(axg); e1 /= np.linalg.norm(e1)
    e2 = np.cross(axg, e1)
    nphi, ntt = 96, 18
    # neck cross-section measured once on a clean slice, then a gently tapered tube
    c0 = A0 + (A1 - A0) * 0.42
    r0 = []
    for j in range(nphi):
        ph = 2 * math.pi * j / nphi
        dd = e1 * math.cos(ph) + e2 * math.sin(ph)
        hp = sh.cast(c0, dd)
        r0.append(np.linalg.norm(hp - c0) if hp is not None else 0.055)
    r0 = np.array(r0)
    for it in range(6):
        r0 = 0.5 * r0 + 0.25 * (np.roll(r0, 1) + np.roll(r0, -1))
    Vg, Fg = [], []
    for i in range(ntt + 1):
        tt = i / ntt
        t = 0.28 + 0.60 * tt
        c = A0 + (A1 - A0) * t
        rib = 0.0
        for j in range(nphi):
            ph = 2 * math.pi * j / nphi
            dd = e1 * math.cos(ph) + e2 * math.sin(ph)
            rr = r0[j] * (1.0 - 0.06 * (t - 0.42)) + 0.0045
            if i == 0:
                rr -= 0.002
            Vg.append(c + dd * rr)
    for i in range(ntt):
        for j in range(nphi):
            a_ = i * nphi + j; b_ = i * nphi + (j + 1) % nphi
            Fg.append((a_, b_, b_ + nphi, a_ + nphi))
    Vg = np.array(Vg)
    o = gear.mesh_object('HERO_gaiter', Vg, Fg, [mats['gaiter']])
    o.parent = rig
    gw = {n: o.vertex_groups.new(name=n) for n in ('spine01', 'neck01', 'neck02', 'neck03', 'head')}
    for i in range(ntt + 1):
        tt = i / ntt
        w = dict(spine01=max(0.0, 0.5 - 2.0 * tt), neck01=max(0.0, 1 - abs(tt - 0.15) / 0.35),
                 neck02=max(0.0, 1 - abs(tt - 0.5) / 0.35), neck03=max(0.0, 1 - abs(tt - 0.82) / 0.3),
                 head=0.45 * max(0.0, (tt - 0.7) / 0.3))
        tot = sum(w.values())
        ids = list(range(i * nphi, (i + 1) * nphi))
        for n, v in w.items():
            if v > 0:
                gw[n].add(ids, v / tot, 'REPLACE')
    mg = o.modifiers.new('Armature', 'ARMATURE'); mg.object = rig
    objs.append(o)
    # ---- gloves (cuff + knuckle guard) and boots (ankle cuff + instep strap)
    for s_ in 'LR':
        dn = build_body._dorsal(J, s_)
        Vc_, Fc_ = sh.plate(f'lowerarm01.{s_}', f'wrist.{s_}', 0.925, 1.02, dn, None, H=0.0032,
                            R=0.0012, base=0.0015, wrap=True, nt=8, na=64)
        o = gear.mesh_object(f'HERO_glove_cuff.{s_}', Vc_, Fc_, [mats['rubber']])
        objs.append(copy_weights(o, rig, P, d['W_final']))
        kn = np.array(J[f'finger3-1.{s_}____head'])
        Vk, Fk = sh.plate(f'wrist.{s_}', kn, 0.60, 1.02, dn, lambda tt: 0.85 * (1 - 0.25 * max(0.0, 1 - min(tt, 1 - tt) / 0.2)),
                          H=0.0032, R=0.0014, base=0.0012, nt=16, na=24)
        o = gear.mesh_object(f'HERO_knuckles.{s_}', Vk, Fk, [mats['armor']])
        objs.append(rigid(o, rig, f'wrist.{s_}'))
        Va, Fa = sh.plate(f'lowerleg02.{s_}', f'foot.{s_}', 0.86, 0.99, (0, -1, 0), None, H=0.0042,
                          R=0.0015, base=0.0022, wrap=True, nt=8, na=64)
        o = gear.mesh_object(f'HERO_boot_cuff.{s_}', Va, Fa, [mats['strap']])
        o.data.attributes.new('strap_uv', 'FLOAT_VECTOR', 'POINT')
        objs.append(copy_weights(o, rig, P, d['W_final']))
    for k, ang in enumerate((128, -128)):
        a = math.radians(ang)
        dirv = np.array([math.sin(a), -math.cos(a), 0.0])
        p = sh.cast((0, 0.025, 0.99), dirv)
        me_ = gear.bevel_box('pouch', (0.07, 0.028, 0.055), bevel=0.006, segs=4)
        flap = gear.bevel_box('flap', (0.072, 0.03, 0.02), bevel=0.003, segs=3)
        snap = gear.bevel_cyl('snap', 0.0045, 0.004, bevel=0.0012)
        Mp = gear.frame_from(p + dirv * 0.0175 + np.array([0, 0, -0.008]), (0, 0, 1), dirv)
        # frame_from: y = up; z ~ outward
        Mp = Matrix.Translation(Vector(p + dirv * 0.017 + np.array([0, 0, -0.01]))) @ \
            Matrix.Rotation(a, 4, 'Z')
        parts = [(me_, Mp @ Matrix.Translation((0, 0, 0)), 0),
                 (flap, Mp @ Matrix.Translation((0, -0.0025, 0.021)), 0),
                 (snap, Mp @ Matrix.Translation((0, -0.0175, 0.018)) @ Matrix.Rotation(math.pi / 2, 4, 'X'), 1)]
        mm = gear.merge_meshes(f'pouch{k}', parts)
        for x in (me_, flap, snap):
            bpy.data.meshes.remove(x)
        mm.materials.append(mats['webbing']); mm.materials.append(mats['gunmetal'])
        co = np.zeros(len(mm.vertices) * 3); mm.vertices.foreach_get('co', co)
        at = mm.attributes.new('prest', 'FLOAT_VECTOR', 'POINT'); at.data.foreach_set('vector', co)
        o = bpy.data.objects.new(f'HERO_pouch.{"L" if ang > 0 else "R"}', mm)
        objs.append(rigid(o, rig, 'root'))
    # buckle: small gunmetal plate with the kite motif in amber
    p = sh.cast((0, 0.025, 0.995), (0, -1, 0))
    bk = gear.bevel_box('buckle', (0.05, 0.008, 0.036), bevel=0.003, segs=3)
    kite = bpy.data.meshes.new('kite')
    kv = [(0, -0.0045, 0.012), (0.008, -0.0045, 0.002), (0, -0.0045, -0.012), (-0.008, -0.0045, 0.002)]
    kite.from_pydata(kv, [], [(0, 1, 2, 3)])
    Mk = Matrix.Translation(Vector(p + np.array([0, -0.006, 0])))
    mm = gear.merge_meshes('buckle_m', [(bk, Mk, 0), (kite, Mk, 1)])
    bpy.data.meshes.remove(bk); bpy.data.meshes.remove(kite)
    mm.materials.append(mats['gunmetal']); mm.materials.append(mats['amber'])
    o = bpy.data.objects.new('HERO_buckle', mm)
    objs.append(rigid(o, rig, 'root'))
    # D-ring / carabiner on the left hip
    a = math.radians(70)
    dirv = np.array([math.sin(a), -math.cos(a), 0.0])
    p = sh.cast((0, 0.025, 0.985), dirv)
    tor = gear.torus_mesh('dring', 0.011, 0.0022, squash=(1, 1.45, 1))
    tor.transform(Matrix.Rotation(math.pi / 2, 4, 'X'))
    tor.transform(Matrix.Translation(Vector(p + dirv * 0.008 + np.array([0, 0, -0.022]))) @ Matrix.Rotation(a, 4, 'Z'))
    tor.materials.append(mats['gunmetal'])
    o = bpy.data.objects.new('HERO_dring', tor)
    objs.append(rigid(o, rig, 'root'))
    return objs, nozzles


def set_nozzles(rig, nozzles):
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for s, (p, ax) in nozzles.items():
        b = rig.data.edit_bones[f'nozzle.{s}']
        roll = b.roll
        b.head = Vector(p); b.tail = Vector(p + ax * 0.04)
        b.roll = roll
    bpy.ops.object.mode_set(mode='OBJECT')


def build_gear_v2(d, rig, mats):
    """round 2: kite launchers, boots, open-kite signature with the evening-star studs,
    flying line, bridle + spine lines, collar band, hood and lenses"""
    import suit_fields as SF
    J = d['joints']
    P, F = d['P_final'], d['F_final']
    sh = gear.Shaper(P, F, J)
    surf = SF.Surf(P, F, J)
    objs, nozzles = [], {}
    W_ = d['W_final']
    def skin(o):
        return copy_weights(o, rig, P, W_)
    # ---------------- launchers: kite-shaped housing on the outer forearm
    for s in 'LR':
        big = s == 'L'
        A = np.array(J[f'lowerarm01.{s}____head']); B = np.array(J[f'wrist.{s}____head'])
        ax = (B - A) / np.linalg.norm(B - A); La = np.linalg.norm(B - A)
        outv = np.array([1.0 if s == 'L' else -1.0, 0.0, 0.25]); outv -= ax * outv.dot(ax); outv /= np.linalg.norm(outv)
        t0, t1 = (0.30, 0.93) if big else (0.45, 0.93)
        wid = 0.62 if big else 0.48
        kite = lambda tt, w=wid: w * float(np.interp(tt, [0.0, 0.07, 0.32, 0.92, 1.0], [0.08, 0.35, 1.0, 0.45, 0.2]))
        Vh, Fh = sh.plate(f'lowerarm01.{s}', f'wrist.{s}', t0, t1, outv, kite, H=0.0085 if big else 0.0065,
                          R=0.0035, base=-0.0015, sink=0.004, nt=40, na=28)
        oh = gear.mesh_object(f'HERO_launcher.{s}', Vh, Fh, [mats['chrome']])
        objs.append(rigid(oh, rig, f'lowerarm02.{s}'))
        # gold ribs across the housing
        for k, tr in enumerate((0.42, 0.55, 0.68) if big else (0.6, 0.72)):
            Vr, Fr = sh.plate(f'lowerarm01.{s}', f'wrist.{s}', tr, tr + 0.018, outv, lambda tt, tr=tr: kite((tr - t0) / (t1 - t0)) * 0.85,
                              H=0.0011, R=0.0005, base=(0.0085 if big else 0.0065) - 0.0016, nt=6, na=20)
            objs.append(rigid(gear.mesh_object(f'HERO_launcher_rib{k}.{s}', Vr, Fr, [mats['gold']]), rig, f'lowerarm02.{s}'))
        # charge strip (cool white)
        Vc, Fc = sh.plate(f'lowerarm01.{s}', f'wrist.{s}', t0 + 0.08, t1 - 0.12, outv, lambda tt: 0.045, H=0.0006,
                          R=0.0003, base=(0.0085 if big else 0.0065) - 0.0003, nt=10, na=5)
        objs.append(rigid(gear.mesh_object(f'HERO_launcher_strip.{s}', Vc, Fc, [mats['star']]), rig, f'lowerarm02.{s}'))
        # nozzle at the wrist end + reel drum near the elbow end
        top = sh.cast(A + (B - A) * (t1 - 0.04), outv)
        bc = top + outv * ((0.0085 if big else 0.0065) + 0.002)
        barrel = gear.bevel_cyl('barrel', 0.0048 if big else 0.0038, 0.03, bevel=0.0009)
        bore = gear.bevel_cyl('bore', 0.0019, 0.003, bevel=0.0002)
        Mb = Matrix.Translation(Vector(bc)) @ Vector((0, 0, 1)).rotation_difference(Vector(ax)).to_matrix().to_4x4()
        parts = [(barrel, Mb, 0), (bore, Mb @ Matrix.Translation((0, 0, 0.0155)), 1)]
        if big:
            drum = gear.bevel_cyl('drum', 0.012, 0.014, bevel=0.0015, verts=40)
            ring = gear.torus_mesh('drumring', 0.0105, 0.0011, nu=40, nv=8)
            pd = sh.cast(A + (B - A) * 0.36, outv) + outv * 0.012
            side_ax = np.cross(ax, outv)
            Md = Matrix.Translation(Vector(pd)) @ Vector((0, 0, 1)).rotation_difference(Vector(side_ax)).to_matrix().to_4x4()
            parts += [(drum, Md, 0), (ring, Md @ Matrix.Translation((0, 0, 0.0072)), 2), (ring, Md @ Matrix.Translation((0, 0, -0.0072)), 2)]
        hard = gear.merge_meshes('launcher_hard', parts)
        for me_ in {id(p[0]): p[0] for p in parts}.values():
            bpy.data.meshes.remove(me_)
        hard.materials.append(mats['chrome']); hard.materials.append(mats['rubber']); hard.materials.append(mats['gold'])
        objs.append(rigid(bpy.data.objects.new(f'HERO_launcher_barrel.{s}', hard), rig, f'lowerarm02.{s}'))
        nozzles[s] = (bc + ax * 0.016, ax)
    # ---------------- boots: smooth toe box + separate rubber sole with a gold welt
    for s in 'LR':
        ank = np.array(J[f'foot.{s}____head'])
        tips = np.array([J[f'toe{k}-{3 if k > 1 else 2}.{s}____tail'] for k in range(1, 6)]).mean(0)
        heel = ank + np.array([0, 0.045, -0.035]); toe = tips + np.array([0, 0.02, 0.008])
        zc = ank[2] + 0.05
        Vs, NR, NP = gear.shoe_shell(sh.bvh, heel, toe, z_collar=zc, ankle=ank, offset=0.0028, welt=0.0, close=6)
        V2, F2 = gear.shoe_mesh(Vs, NR, NP, 9.0)
        V2 = V2 + np.array([0, 0, 0.0055])           # stand on the sole
        o = gear.mesh_object(f'HERO_shoe.{s}', V2, F2, [mats['shoe']])
        objs.append(skin(o))
        sb = gear.Shaper(V2, F2, J)
        Vso, Fso = sb.plate(heel + np.array([0, 0.012, 0.0]), toe + np.array([0, -0.012, 0.004]), -0.04, 1.04, (0, 0, -1),
                            lambda tt: 1.5, H=0.0065, R=0.0012, base=-0.0012, sink=0.004, nt=44, na=30, smooth_iters=4)
        o2 = gear.mesh_object(f'HERO_sole.{s}', Vso, Fso, [mats['sole']])
        objs.append(skin(o2))
    # ---------------- signature: open kites, evening-star studs, flying line
    def kite_corners(cx, cz, height, width, tilt_deg):
        # irregular quadrilateral: short top third, long tail
        loc = [(0.0, 0.33), (width * 0.5, 0.0), (0.0, -0.67), (-width * 0.5, 0.0)]
        a = math.radians(tilt_deg)
        out = []
        for x_, z_ in loc:
            zz = z_ * height
            out.append((cx + x_ * math.cos(a) - zz * math.sin(a), cz + x_ * math.sin(a) + zz * math.cos(a)))
        return out
    def body_pt(x_, z_, back=False):
        return surf.cast((x_, 0.45 if back else -0.45, z_), (0, -1 if back else 1, 0))
    def gold_line(name, ctrl, radius=0.0019, lift=0.0006):
        pts, nrm = gear.surf_line(surf, ctrl, step=0.002)
        V_, F_ = gear.tube_along(pts, nrm, radius, lift=lift)
        return skin(gear.mesh_object(name, V_, F_, [mats['gold']]))
    def kite_emblem(tag, cx, cz, h, w, tilt, back=False):
        c4 = kite_corners(cx, cz, h, w, tilt)
        pts = [body_pt(x_, z_, back) for x_, z_ in c4]
        out = [gold_line(f'HERO_kite_{tag}_frame', pts + [pts[0]], radius=0.0022 if not back else 0.0028)]
        out.append(gold_line(f'HERO_kite_{tag}_spine', [pts[0], pts[2]]))
        out.append(gold_line(f'HERO_kite_{tag}_spar', [pts[1], pts[3]]))
        # star at the crossing of spine and spar (cz level)
        cr = body_pt(cx - (0.0) , cz, back)
        _, nrm = surf.nearest(cr)
        nrm = np.array(nrm)
        st = gear.star_mesh(f'star_{tag}', r=0.007 if not back else 0.009)
        M = Matrix.Translation(Vector(cr + nrm * 0.0015)) @ Vector((0, 0, 1)).rotation_difference(Vector(nrm)).to_matrix().to_4x4()
        st.transform(M)
        st.materials.append(mats['star'])
        so = bpy.data.objects.new(f'HERO_star_{tag}', st)
        co = np.zeros(len(st.vertices) * 3); st.vertices.foreach_get('co', co)
        at = st.attributes.new('prest', 'FLOAT_VECTOR', 'POINT'); at.data.foreach_set('vector', co)
        out.append(skin(so))
        return out, pts
    ko, kpts = kite_emblem('chest', -0.088, 1.335, 0.13, 0.072, 20.0)
    objs += ko
    kb, bpts = kite_emblem('back', 0.0, 1.30, 0.32, 0.17, 0.0, back=True)
    objs += kb
    # flying line: chest kite tail -> right hip -> around the hip -> up to the back kite tail
    hipF = surf.torso(0.965, 318)
    hipS = surf.torso(0.955, 270)
    hipB = surf.torso(0.965, 215)
    objs.append(gold_line('HERO_flying_line', [kpts[2], hipF, hipS, hipB, bpts[2]], radius=0.0018))
    # spine line: from the hood rim at the nape down to the top of the back kite
    nape = surf.cast((0.0, 0.25, 1.505), (0, -1, 0))
    objs.append(gold_line('HERO_spine_line', [nape, bpts[0]], radius=0.0018))
    # gold bead on the sail edge near the collar / shoulder (close-shot borders)
    # collar band: low standing indigo band + gold bead on top, at the hood rim
    md = d['mask']
    Cn = md['ring_c']; rn = md['ring_r']; u = md['u']; ur = np.radians(u)
    ringv, ringf = [], []
    NU_ = len(u)
    for i, (dz, dr) in enumerate([(-0.012, -0.003), (-0.010, 0.0018), (0.004, 0.0024), (0.008, 0.0005), (0.009, -0.003)]):
        for j in range(NU_):
            dh = np.array([math.sin(ur[j]), -math.cos(ur[j]), 0.0])
            ringv.append(Cn + dh * (rn[j] + mask.OFFSET + dr) + np.array([0, 0, dz]))
    for i in range(4):
        for j in range(NU_):
            a_ = i * NU_ + j; b_ = i * NU_ + (j + 1) % NU_
            ringf.append((a_, b_, b_ + NU_, a_ + NU_))
    oc = gear.mesh_object('HERO_collar', np.array(ringv), ringf, [mats['ink']])
    objs.append(skin(oc))
    bead = []
    for j in range(NU_ + 1):
        jj = j % NU_
        dh = np.array([math.sin(ur[jj]), -math.cos(ur[jj]), 0.0])
        bead.append(Cn + dh * (rn[jj] + mask.OFFSET + 0.0015) + np.array([0, 0, 0.0095]))
    bead = np.array(bead)
    Vb, Fb = gear.tube_along(bead, np.tile([0, 0, 1.0], (len(bead), 1)), 0.0017, lift=-0.001, caps=False)
    objs.append(skin(gear.mesh_object('HERO_collar_bead', Vb, Fb, [mats['gold']])))
    # hood: weights blend head -> neck by height so it moves like fabric on the neck
    md = d['mask']
    ob = gear.mesh_object('HERO_mask', md['verts'], md['faces'], [mats['mask']])
    at = ob.data.attributes.new('hp', 'FLOAT_VECTOR', 'POINT')
    at.data.foreach_set('vector', np.asarray(md['hp'], float).ravel())
    ob.parent = rig
    # neck rows: body weights of the nearest suit vertices, blending into pure 'head'
    # at the jaw line; head rows: 'head' only (the hood moves with the skull)
    Wb = d['W_final']
    names = [n for n in Wb if Wb[n].max() > 0]
    WM = np.stack([Wb[n] for n in names], 1)
    gw = {}
    def grp(nme):
        if nme not in gw:
            gw[nme] = ob.vertex_groups.new(name=nme)
        return gw[nme]
    Vm = md['verts']
    nn = md['n_neck'] * md['NU']
    for i in range(len(Vm)):
        if i < nn:
            row = i // md['NU']
            t = row / (md['n_neck'] - 1)
            t = t * t * (3 - 2 * t)
            col_u = abs(md['u'][i % md['NU']])
            back = min(1.0, max(0.0, (col_u - 90.0) / 50.0))
            t = t ** (1.0 + 2.5 * back)
            dist = np.linalg.norm(P - Vm[i], axis=1)
            k = np.argpartition(dist, 6)[:6]
            w = 1.0 / (dist[k] + 1e-4)
            ww = (WM[k] * w[:, None]).sum(0) / w.sum() * (1 - t)
            for gi in np.nonzero(ww > 0.01)[0]:
                nme = names[gi]
                grp(nme).add([i], float(ww[gi]), 'REPLACE')
            if t > 0.01:
                grp('head').add([i], float(t), 'REPLACE')
    # first head rows at the back (nape) keep some neck weight too
    for i in range(nn, len(Vm)):
        row = i // md['NU'] - md['n_neck']
        col_u = abs(md['u'][i % md['NU']])
        back = min(1.0, max(0.0, (col_u - 90.0) / 50.0))
        tn = max(0.0, 1 - row / 18.0) * back * 0.5
        grp('head').add([i], 1.0 - tn, 'REPLACE')
        if tn > 0:
            grp('neck03').add([i], tn * 0.6, 'REPLACE'); grp('neck02').add([i], tn * 0.4, 'REPLACE')
    mm_ = ob.modifiers.new('Armature', 'ARMATURE'); mm_.object = rig
    objs.append(ob)
    # lenses + bridle lines (rigid on the head)
    for side, s in ((1, 'L'), (-1, 'R')):
        V_, F_, M_ = mask.lens(md, side)
        o = gear.mesh_object(f'HERO_lens.{s}', V_, F_, [mats['lens_frame'], mats['lens_glass']], mat_idx=M_)
        objs.append(rigid(o, rig, 'head'))
        bp = mask.bridle_path(md, side)
        nr = bp - md['C']; nr /= np.linalg.norm(nr, axis=1, keepdims=True)
        Vb_, Fb_ = gear.tube_along(bp, nr, 0.0018, lift=-0.0002)
        objs.append(rigid(gear.mesh_object(f'HERO_bridle.{s}', Vb_, Fb_, [mats['gold']]), rig, 'head'))
    return objs, nozzles


def build():
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    d, body, rig, flds = build_body_and_rig(sc)
    mats = dict(suit=HM.fabric_material('HERO_suit', 'rest', True),
                mask=HM.fabric_material('HERO_mask', 'prest', False, mask=True),
                gold=HM.gold_material(), gunmetal=HM.gunmetal_material(),
                amber=HM.amber_light_material(), rubber=HM.black_rubber_material(),
                web=HM.web_material(), shoe=HM.shoe_material_v2(),
                lens_frame=HM.lens_frame_material(), lens_glass=HM.lens_glass_material(),
                chrome=HM.chrome_material(), star=HM.star_material(), sole=HM.sole_material_v2(),
                ink=HM.ink_material())
    body.data.materials.append(mats['suit'])
    gobjs, nozzles = build_gear_v2(d, rig, mats)
    # drop the bare-foot faces now hidden inside the feet covers
    Pb, Fb = mesh_arrays(body.data)
    Wb = vertex_weights(body)
    fw = sum(Wb[n] for n in Wb if n.startswith(('foot', 'toes')))
    zc = d['joints']['foot.L____head'][2] + 0.012
    hid = (fw > 0.55) & (Pb[:, 2] < zc)
    delete_faces(body, np.array([hid[list(f)].all() for f in Fb]))
    set_nozzles(rig, nozzles)
    hero_web.make_nodegroup()
    col = bpy.data.collections.new('HERO')
    sc.collection.children.link(col)
    link(rig, col)
    rig.show_in_front = False
    rig.hide_render = True
    body.parent = rig
    am = body.modifiers.new('Armature', 'ARMATURE'); am.object = rig
    cs = body.modifiers.new('CorrectiveSmooth', 'CORRECTIVE_SMOOTH')
    cs.factor = 0.5; cs.iterations = 6; cs.scale = 1.0
    cs.smooth_type = 'LENGTH_WEIGHTED'; cs.use_only_smooth = False
    cs.rest_source = 'ORCO'
    sub = body.modifiers.new('Subdivision', 'SUBSURF'); sub.levels = 0; sub.render_levels = 1
    sub.uv_smooth = 'PRESERVE_BOUNDARIES'
    link(body, col)
    for o in gobjs:
        if o.name not in col.objects:
            col.objects.link(o)
    for o in [body] + gobjs:
        if hasattr(o, 'cycles') and hasattr(o.cycles, 'motion_steps'):
            o.cycles.motion_steps = 3
    contacts = []
    for s_ in 'LR':
        so = bpy.data.objects[f'HERO_shoe.{s_}']
        co = np.array([v.co for v in so.data.vertices])
        low = co[co[:, 2] < co[:, 2].min() + 0.004]
        sel = low[np.linspace(0, len(low) - 1, min(24, len(low))).astype(int)]
        for p in sel:
            bn = f'toes.{s_}' if p[1] < np.array(d['joints'][f'toe1-1.{s_}____head'])[1] else f'foot.{s_}'
            M = rig.data.bones[bn].matrix_local
            lp = M.inverted() @ Vector(p)
            contacts += [bn, lp.x, lp.y, lp.z]
    rig['contacts'] = ' '.join(str(c) if isinstance(c, str) else '%.5f' % c for c in contacts)
    rig['hero_height'] = 1.78
    rig['grip_bones'] = 'grip.L grip.R'
    rig['nozzle_bones'] = 'nozzle.L nozzle.R'
    rig['design'] = 'VESPER v2'
    nf = sum(len(o.data.polygons) for o in col.objects if o.type == 'MESH')
    log('objects', len(col.objects), 'base faces', nf, 'time', round(time.time() - t0, 1))
    return rig


def save(path=OUT):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # drop helper scene objects (none should exist outside HERO)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    log('saved', path)


if __name__ == '__main__':
    build()
    save()
