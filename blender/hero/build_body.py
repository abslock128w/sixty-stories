"""Body mesh + HERO_RIG armature from the MakeHuman data (see mh_body.py)."""
import numpy as np
import bpy
from mathutils import Vector, Matrix

import mh_body

FACE_PREFIX = ('jaw', 'eye', 'levator', 'oculi', 'orbicularis', 'oris', 'risorius',
               'special', 'temporalis', 'tongue')

# bones kept from the MakeHuman default skeleton (others merged into their parents)
def _kept(name):
    if name.startswith(FACE_PREFIX):
        return False
    if name.startswith('breast') or name.startswith('toe'):
        return False
    return True


def _merge_target(name, bones):
    if name.startswith('toe'):
        return 'toes.' + name[-1]
    n = name
    while not _kept(n):
        n = bones[n]['parent']
    return n


def neighbours(nv, faces):
    nb = [set() for _ in range(nv)]
    for f in faces:
        k = len(f)
        for i in range(k):
            a, b = f[i], f[(i + 1) % k]
            nb[a].add(b); nb[b].add(a)
    return [np.array(sorted(s)) for s in nb]


def taubin(P, nb, mask_w, iters=30, lam=0.5, mu=-0.53):
    """Taubin smoothing, per-vertex strength mask_w (0..1)."""
    P = P.copy()
    idx = np.nonzero(mask_w > 0)[0]
    for it in range(iters):
        for f in (lam, mu):
            avg = np.array([P[nb[i]].mean(0) for i in idx])
            P[idx] += (f * mask_w[idx])[:, None] * (avg - P[idx])
    return P


def build_body_data():
    d = mh_body.build()
    P = d['verts']; F = d['faces']
    nv = len(P)
    # merged per-vertex weights
    W = {}
    for bone, (vi, w) in d['weights'].items():
        t = _merge_target(bone, d['bones'])
        arr = W.setdefault(t, np.zeros(nv))
        np.add.at(arr, vi, w)
    nb = neighbours(nv, F)
    # turn bare toes into a single smooth toe box (sock-shoe)
    toe = np.clip((W.get('toes.L', 0) + W.get('toes.R', 0)) * 1.6, 0, 1)
    # grow the mask a bit
    for _ in range(3):
        toe = np.maximum(toe, np.array([toe[n].max() * 0.75 if len(n) else 0 for n in nb]))
    P = taubin(P, nb, toe, iters=40)
    P = taubin(P, nb, toe, iters=30, lam=0.5, mu=0.0)   # plain laplacian: merge the toes
    d['verts'] = P
    d['W'] = W
    d['nb'] = nb
    return d


def make_mesh(name, d):
    P = d['verts']; F = d['faces']
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in P], [], [tuple(f) for f in F])
    me.update()
    uv = me.uv_layers.new(name='UVMap')
    co = []
    for fuv in d['face_uvs']:
        co.extend(fuv)
    uv.data.foreach_set('uv', np.array(co, float).ravel())
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    # rest position attribute (used by every procedural pattern so nothing swims)
    att = me.attributes.new('rest', 'FLOAT_VECTOR', 'POINT')
    att.data.foreach_set('vector', P.ravel())
    for bone, w in d['W'].items():
        vg = ob.vertex_groups.new(name=bone)
        nz = np.nonzero(w > 1e-4)[0]
        for i in nz:
            vg.add([int(i)], float(min(w[i], 1.0)), 'REPLACE')
    return ob


def _dorsal(J, side):
    s = side
    wrist = J[f'wrist.{s}____head']
    k_index = J[f'finger2-1.{s}____head']
    k_pinky = J[f'finger5-1.{s}____head']
    mid = J[f'finger3-1.{s}____head']
    fwd = (mid - wrist); fwd /= np.linalg.norm(fwd)
    across = k_index - k_pinky
    n = np.cross(fwd, across) if s == 'L' else np.cross(across, fwd)
    return n / np.linalg.norm(n)


def make_armature(d, name='HERO_RIG'):
    J = d['joints']; B = d['bones']
    arm = bpy.data.armatures.new(name)
    arm.display_type = 'OCTAHEDRAL'
    ob = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones
    dors = {s: _dorsal(J, s) for s in 'LR'}
    kept = [n for n in B if _kept(n)]
    # deterministic order: parents first
    order = []
    def visit(n):
        if n in order:
            return
        p = B[n]['parent']
        if p and _kept(p):
            visit(p)
        order.append(n)
    for n in sorted(kept):
        visit(n)
    for n in order:
        b = eb.new(n)
        b.head = Vector(J[B[n]['head']]); b.tail = Vector(J[B[n]['tail']])
        if (b.tail - b.head).length < 1e-4:
            b.tail = b.head + Vector((0, 0, 0.02))
    for n in order:
        p = B[n]['parent']
        if p:
            eb[n].parent = eb[p]
            eb[n].use_connect = False
    # toes: one bone per foot, from the ball of the foot to the toe tips
    for s in 'LR':
        heads = np.array([J[B[f'toe{k}-1.{s}']['head']] for k in range(1, 6)])
        tips = np.array([J[B[f'toe{k}-{3 if k > 1 else 2}.{s}']['tail']] for k in range(1, 6)])
        b = eb.new(f'toes.{s}')
        b.head = Vector(heads.mean(0)); b.tail = Vector(tips.mean(0))
        b.parent = eb[f'foot.{s}']
    # rolls: Z axis = front for body/limbs, up for feet, dorsal for hands
    for b in eb:
        n = b.name
        if n.startswith(('foot', 'toes')):
            b.align_roll(Vector((0, 0, 1)))
        elif n.startswith(('metacarpal', 'finger', 'wrist')):
            b.align_roll(Vector(dors[n[-1]]))
        else:
            ref = Vector((0, -1, 0))
            dirn = (b.tail - b.head).normalized()
            if abs(dirn.dot(ref)) > 0.9:
                ref = Vector((0, 0, 1))
            b.align_roll(ref)
    # helper bones: grip point (centre of the fist) and launcher nozzle
    for s in 'LR':
        dn = Vector(dors[s])
        k = [Vector(J[B[f'finger{i}-1.{s}']['head']]) for i in (2, 3, 4, 5)]
        knuck = sum(k, Vector()) / 4
        w = eb[f'wrist.{s}']
        fwd = (knuck - w.head).normalized()
        g = eb.new(f'grip.{s}')
        g.head = knuck - dn * 0.030 + fwd * 0.004
        g.tail = g.head + fwd * 0.04
        g.align_roll(dn)
        g.parent = w
        la = eb[f'lowerarm02.{s}']
        ax = (la.tail - la.head).normalized()
        nz = eb.new(f'nozzle.{s}')
        nz.head = la.tail - ax * 0.035 - dn * 0.040
        nz.tail = nz.head + ax * 0.04
        nz.align_roll(dn)
        nz.parent = la
    # a ground-level master bone so the whole body can be moved inside the rig too
    m = eb.new('master'); m.head = (0, 0, 0); m.tail = (0, 0.25, 0)
    m.align_roll(Vector((0, 0, 1)))
    eb['root'].parent = m
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in ob.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    for b in arm.bones:
        b.use_deform = not b.name.startswith(('master', 'grip', 'nozzle'))
    return ob
