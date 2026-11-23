"""Proof scene + renders for the street-corner hero asset (lighting as facade_proofs.py).

    $PY corner_proofs.py [shot ...] [--w 640] [--samples 32] [--threads 2] [--save] [--tag x] [--nofacade]
shots: wide signal curb props manhole  (default: all)
Writes blender/out/preview/assets/corner_<shot>[_tag].png ; --save writes blender/out/assets/corner.blend
The facade hero asset (blender/out/assets/facade.blend, ASSET_facade) is instanced on the
building quadrant as context, rotated so its shopfront faces the avenue.
"""
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import facade  # noqa: E402
import facade_proofs as FP  # noqa: E402
import corner  # noqa: E402
import corner_kit as K  # noqa: E402

ROOT = facade.ROOT
OUT_PREV = os.path.join(ROOT, "blender", "out", "preview", "assets")
OUT_BLEND = os.path.join(ROOT, "blender", "out", "assets", "corner.blend")
FACADE_BLEND = os.path.join(ROOT, "blender", "out", "assets", "facade.blend")
AV_W = 18.0   # avenue curb-to-curb
CS_W = 18.0   # cross street curb-to-curb

CAMS = {
    # name: (location, target, lens, (w, h), sun az, sun el)
    'wide': ((-11.0, -9.0, 1.65), (3.2, 4.0, 2.3), 28, (1920, 1080), 255, 15),
    'signal': ((-3.6, -0.2, 1.65), (4.6, -2.6, 3.6), 30, (1920, 1280), 255, 15),
    'curb': ((-1.45, 9.7, 1.5), (0.1, 4.6, -0.25), 32, (1920, 1080), 255, 15),
    'props': ((4.7, 3.7, 1.45), (7.6, 0.55, 0.55), 30, (1920, 1080), 255, 15),
    'manhole': ((-4.15, 6.35, 1.2), (-5.0, 7.6, -0.08), 42, (1920, 1280), 255, 15),
}


def env_road_z(x, y):
    A = corner.crown(np.minimum(-x, x + AV_W))
    C = corner.crown(np.minimum(-y, y + CS_W))
    inA = (x < 0) & (x > -AV_W)
    inC = (y < 0) & (y > -CS_W)
    return np.where(inA & inC, np.maximum(A, C), np.where(inA, A, np.where(inC, C, -0.15)))


def setup_env(scene):
    col = bpy.data.collections.new("PROOF_env")
    scene.collection.children.link(col)
    E = 70.0

    def road_keep(cx, cy):
        inA = (cx < 0) & (cx > -AV_W)
        inC = (cy < 0) & (cy > -CS_W)
        patch = (np.abs(cx) < 10) & (np.abs(cy) < 10)
        return (inA | inC) & ~patch
    corner.grid_mesh("env_road", col, K.m_asphalt("crn_asphalt"), -E, -E, E, E, 0.5, env_road_z, keep=road_keep)
    conc = FP.env_material("env_concrete", facade.srgb((156, 152, 144)), 'concrete')
    gran = K.m_granite("crn_granite")
    blocks = [  # sidewalk rectangles (x0, y0, x1, y1) and the side their curb faces
        (10, 0, E, 6), (0, 10, 6, E),
        (-E, 0, -AV_W, E), (-E, -E, -AV_W, -CS_W), (0, -E, E, -CS_W),
    ]
    for i, (x0, y0, x1, y1) in enumerate(blocks):
        FP.box(col, f"env_walk{i}", (x0 + (0.18 if x0 == 0 else 0), y0 + (0.18 if y0 == 0 else 0), -0.2), (x1 - (0.18 if x1 == -AV_W else 0), y1 - (0.18 if y1 == -CS_W else 0), 0.0), conc)
    curbs = [(10, -0.0, E, 0.18), (-0.0, 10, 0.18, E), (-AV_W - 0.18, 0, -AV_W, E), (-AV_W - 0.18, -E, -AV_W, -CS_W), (0, -CS_W - 0.18, E, -CS_W),
             (-E, -CS_W - 0.18, -AV_W, -CS_W), (-E, 0, -AV_W, 0.18)]
    for i, (x0, y0, x1, y1) in enumerate(curbs):
        FP.box(col, f"env_curb{i}", (x0, y0, -0.45), (x1, y1, 0.0), gran)
    blds = [
        ((-48, 0, 0), (-22, 24, 4.2), (150, 120, 96)), ((-48, 24, 0), (-22, 50, 44), (120, 110, 100)),
        ((-48, -60, 0), (-22, -26, 34), (110, 80, 66)), ((-20, -50, 0), (2, -22, 24), (160, 150, 130)), ((2, -50, 0), (30, -22, 52), (120, 116, 112)),
        ((30, -50, 0), (60, -22, 20), (150, 146, 140)), ((-60, -60, 0), (-48, 60, 60), (140, 130, 120)),
    ]
    for i, (mn, mx, c) in enumerate(blds):
        FP.box(col, f"bld{i}", mn, mx, FP.env_material(f"env_bld{i}", facade.srgb(c), 'windows'))
    return col


def add_facade(scene):
    if not os.path.exists(FACADE_BLEND):
        return None
    with bpy.data.libraries.load(FACADE_BLEND, link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c == "ASSET_facade"]
    fc = dst.collections[0]
    W = max(max((o.matrix_world @ Vector(b)).x for b in o.bound_box) for o in fc.all_objects if o.type == 'MESH')
    W = round(W * 2) / 2
    try:
        facade.set_lights(fc, day=True, interior_mult=0.6, shop_mult=0.6)
    except Exception as e:
        print("[corner] set_lights failed", e)
    em = bpy.data.objects.new("PROOF_facade", None)
    em.instance_type = 'COLLECTION'
    em.instance_collection = fc
    em.location = (corner.SW, corner.SW + W, 0.0)
    em.rotation_euler = (0, 0, -math.pi / 2)
    scene.collection.objects.link(em)
    # neighbour massing beyond the facade on both streets
    col = bpy.data.collections.new("PROOF_env2")
    scene.collection.children.link(col)
    FP.box(col, "bld_av", (corner.SW, corner.SW + W, 0), (40, 70, 30), FP.env_material("env_bld_av", facade.srgb((140, 124, 110)), 'windows'))
    FP.box(col, "bld_cs", (corner.SW + 12, corner.SW, 0), (70, 30, 24), FP.env_material("env_bld_cs", facade.srgb((160, 150, 136)), 'windows'))
    print(f"[corner] facade instanced, width {W:.2f} m", flush=True)
    return em


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    opt = dict(w=640, samples=32, threads=2, tag='', save=False, nofacade=False)
    shots = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('--save', '--nofacade'):
            opt[a[2:]] = True
        elif a.startswith('--'):
            opt[a[2:]] = argv[i + 1]
            i += 1
        else:
            shots.append(a)
        i += 1
    shots = shots or list(CAMS)
    if 'cam' in opt:
        v = [float(x) for x in opt['cam'].split(',')]
        CAMS['custom'] = (tuple(v[0:3]), tuple(v[3:6]), v[6], (1920, 1080), 255, 15)
        shots = ['custom']
    FP.clean()
    scene = bpy.context.scene
    t0 = time.time()
    col = corner.build()
    scene.collection.children.link(col)
    print(f"[corner] built in {time.time() - t0:.1f}s", flush=True)
    dg = bpy.context.evaluated_depsgraph_get()
    nf = 0
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type == 'MESH':
            nf += len(ob.data.polygons)
    print(f"[corner] rendered faces incl. instances (evaluated): {nf}", flush=True)
    setup_env(scene)
    os.makedirs(OUT_PREV, exist_ok=True)
    if opt['save']:
        os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
        FP.setup_world(scene, *CAMS['wide'][4:6])
        FP.make_cam(scene, *CAMS['wide'][:3])
        for im in bpy.data.images:
            if im.source == 'FILE' and not im.packed_file:
                try:
                    im.pack()
                except Exception as e:
                    print("pack failed", im.name, e)
        bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
        print("[corner] saved", OUT_BLEND, flush=True)
    if not opt['nofacade']:
        add_facade(scene)
    for s in shots:
        loc, tgt, lens, res, az, el = CAMS[s]
        for ob in [o for o in scene.objects if o.name.startswith("PROOF_sun") or o.name.startswith("PROOF_cam")]:
            bpy.data.objects.remove(ob)
        FP.setup_world(scene, az, el)
        FP.make_cam(scene, loc, tgt, lens)
        w = int(opt['w'])
        h = int(round(w * res[1] / res[0]))
        FP.setup_render(scene, w, h, int(opt['samples']), int(opt['threads']))
        scene.view_settings.exposure = 0.0
        fn = os.path.join(OUT_PREV, f"corner_{'curb_close' if s == 'curb' else s}" + (f"_{opt['tag']}" if opt['tag'] else '') + ".png")
        scene.render.filepath = fn
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[render] {s} {w}x{h} {opt['samples']}spp: {time.time() - t1:.1f}s -> {fn}", flush=True)


if __name__ == "__main__":
    main()
