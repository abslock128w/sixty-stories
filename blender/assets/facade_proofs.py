"""Proof scene + renders for the facade hero asset.

    $PY facade_proofs.py [shot ...] [--w 640] [--samples 32] [--threads 2] [--save] [--tag x]
shots: full shopfront window fire dusk  (default: all)
Writes blender/out/preview/assets/facade_<shot>[_tag].png ; --save writes blender/out/assets/facade.blend
"""
import math
import os
import sys
import time

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import facade  # noqa: E402

ROOT = facade.ROOT
OUT_PREV = os.path.join(ROOT, "blender", "out", "preview", "assets")
OUT_BLEND = os.path.join(ROOT, "blender", "out", "assets", "facade.blend")


def clean():
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.images, bpy.data.node_groups, bpy.data.worlds):
        for x in list(blk):
            blk.remove(x)


def sun_dir(az_deg, el_deg):
    """az measured from +Y toward +X (compass-like, +Y = north)."""
    a, e = math.radians(az_deg), math.radians(el_deg)
    return Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))


def setup_world(scene, az, el, dusk=False):
    w = bpy.data.worlds.new("PROOF_world")
    scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    T = facade.NT(nt)
    out = T.n('ShaderNodeOutputWorld')
    skies = []
    for disc in (True, False):
        s = T.n('ShaderNodeTexSky', sky_type='MULTIPLE_SCATTERING')
        s.sun_disc = disc
        s.sun_elevation = math.radians(el)
        s.sun_rotation = math.radians(az)
        s.altitude = 30.0
        s.air_density = 1.0
        s.aerosol_density = 2.0
        s.ozone_density = 1.0
        s.sun_size = math.radians(0.55)
        s.sun_intensity = 0.25
        skies.append(s)
    lp = T.n('ShaderNodeLightPath')
    mx = T.mix(lp.outputs['Is Camera Ray'], skies[1].outputs['Color'], skies[0].outputs['Color'])
    bg = T.n('ShaderNodeBackground', {'Color': mx, 'Strength': 1.0})
    T.L.new(bg.outputs[0], out.inputs['Surface'])
    # sun lamp
    ld = bpy.data.lights.new("PROOF_sun", 'SUN')
    if not dusk:
        ld.energy = 4.5
        ld.color = (1.0, 0.66, 0.40)
    else:
        ld.energy = 0.0
    ld.angle = math.radians(0.6)
    ob = bpy.data.objects.new("PROOF_sun", ld)
    d = sun_dir(az, el)
    ob.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(ob)
    return w


def env_material(name, col, kind='plain'):
    m, T, out = facade.new_mat(name)
    tc = T.n('ShaderNodeTexCoord')
    p = tc.outputs['Object']
    if kind == 'windows':
        bk = T.n('ShaderNodeTexBrick', {'Vector': p, 'Scale': 1.0, 'Color1': col, 'Color2': col, 'Mortar': (0.03, 0.035, 0.04, 1),
                                        'Mortar Size': 0.0, 'Brick Width': 1.0, 'Row Height': 1.0})
        # windows: grid in x/z (or y/z) using two waves
        sep = T.xyz(p)
        wx = T.math('PINGPONG', T.math('ADD', sep[0], sep[1]), 1.5)
        wz = T.math('PINGPONG', sep[2], 1.65)
        win = T.math('MULTIPLY', T.smooth(wx, 0.55, 0.6), T.smooth(wz, 0.45, 0.5))
        nz = T.noise(p, 0.5, 2, 0.5)
        wc = T.mix(T.smooth(nz.outputs['Factor'], 0.4, 0.6), (0.02, 0.025, 0.03, 1), (0.08, 0.09, 0.1, 1))
        c = T.mix(win, col, wc)
        r = T.mixf(win, 0.85, 0.08)
        facade.principled(T, out, c, r)
    elif kind == 'concrete':
        sep = T.xyz(p)
        jx = T.math('PINGPONG', sep[0], 0.75)
        jy = T.math('PINGPONG', sep[1], 0.75)
        joint = T.math('MAXIMUM', T.smooth(jx, 0.008, 0.0), T.smooth(jy, 0.008, 0.0))
        n1 = T.noise(p, 1.5, 6, 0.6)
        n2 = T.noise(p, 30.0, 6, 0.7)
        vo = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 0.66})
        wn = T.n('ShaderNodeTexWhiteNoise', {'Vector': vo.outputs['Position']}, noise_dimensions='3D')
        f = T.math('MULTIPLY', T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.75, 1.1), T.remap(wn.outputs['Value'], 0, 1, 0.9, 1.08))
        c = T.mul_col(col, T.comb(f, f, f))
        # gum spots and stains
        gv = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 9.0})
        gum = T.smooth(gv.outputs['Distance'], 0.05, 0.03)
        c = T.mix(T.math('MULTIPLY', gum, 0.7), c, (0.06, 0.06, 0.06, 1))
        c = T.mix(T.math('MULTIPLY', joint, 0.8), c, (0.04, 0.04, 0.04, 1))
        h = T.math('ADD', T.math('MULTIPLY', joint, -1.0), T.math('MULTIPLY', n2.outputs['Factor'], 0.15))
        facade.principled(T, out, c, T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.75, 0.95), normal=T.bump(h, 0.6, 0.004))
    elif kind == 'asphalt':
        n1 = T.noise(p, 2.0, 6, 0.6)
        vo = T.n('ShaderNodeTexVoronoi', {'Vector': p, 'Scale': 300.0})
        f = T.math('MULTIPLY', T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.7, 1.15), T.remap(vo.outputs['Distance'], 0, 0.8, 0.8, 1.15))
        c = T.mul_col(col, T.comb(f, f, f))
        facade.principled(T, out, c, T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.55, 0.9), normal=T.bump(vo.outputs['Distance'], 0.3, 0.002))
    else:
        n1 = T.noise(p, 2.0, 5, 0.6)
        f = T.remap(n1.outputs['Factor'], 0.3, 0.7, 0.85, 1.1)
        facade.principled(T, out, T.mul_col(col, T.comb(f, f, f)), 0.8)
    return m


def box(col, name, mn, mx, mat):
    mb = facade.MB(name)
    mb.box(mn, mx, 'm')
    return facade.finalize(mb, col, {'m': mat})


def setup_env(scene, F):
    col = bpy.data.collections.new("PROOF_env")
    scene.collection.children.link(col)
    W, R = F.W, F.RET
    conc = env_material("env_concrete", facade.srgb((150, 146, 138)), 'concrete')
    asph = env_material("env_asphalt", facade.srgb((52, 52, 54)), 'asphalt')
    gran = env_material("env_granite", facade.srgb((120, 118, 114)))
    # sidewalks (L shape around the corner) at z=0, roads at -0.15
    box(col, "sidewalk_front", (-40, -4.6, -0.2), (W + 4.6, 0.0, 0.0), conc)
    box(col, "sidewalk_side", (W, 0.0, -0.2), (W + 4.6, 40, 0.0), conc)
    box(col, "curb_front", (-40, -4.78, -0.2), (W + 4.78, -4.6, 0.0), gran)
    box(col, "curb_side", (W + 4.6, -4.78, -0.2), (W + 4.78, 40, 0.0), gran)
    box(col, "road", (-80, -60, -0.4), (80, 60, -0.15), asph)
    box(col, "sidewalk_far", (-60, -32, -0.2), (W + 3.0, -25.0, 0.0), conc)
    box(col, "sidewalk_far2", (W + 17, -32, -0.2), (80, -25.0, 0.0), conc)
    box(col, "sidewalk_x", (W + 17, -25, -0.2), (W + 22, 60, 0.0), conc)
    # buildings around (simple massing with window grids), so glass has something to reflect
    blds = [
        ((-60, -60, 0), (-20, -32, 9), (120, 100, 86)), ((-20, -62, 0), (0, -32, 8), (150, 120, 96)),
        ((0, -58, 0), (W + 3, -32, 9), (170, 160, 146)), ((W + 17, -60, 0), (W + 40, -32, 30), (110, 80, 66)),
        ((-90, -140, 0), (-40, -100, 30), (140, 130, 120)), ((-30, -120, 0), (10, -90, 28), (120, 110, 100)),
        ((W + 22, -25, 0), (W + 45, 10, 34), (160, 150, 130)), ((W + 22, 10, 0), (W + 45, 40, 60), (120, 116, 112)),
        ((W + 0.02, 3.0, 0), (W + 0.8, 25, 0.1), (100, 100, 100)),
        ((-40, 25, 0), (W + 4, 45, 70), (150, 146, 140)),
    ]
    for i, (mn, mx, c) in enumerate(blds):
        m = env_material(f"env_bld{i}", facade.srgb(c), 'windows')
        box(col, f"bld{i}", mn, mx, m)
    # continuation of the return wall past the asset (same brick field shader -> same bricks)
    mb = facade.MB("return_cont")
    mb.quad([(W, R, F.GH), (W, 20, F.GH), (W, 20, F.ZTOP), (W, R, F.ZTOP)], 'm')
    mb.closed = False
    facade.finalize(mb, col, {'m': F.materials['reveal']}, recalc=False)
    mb = facade.MB("return_cont_base")
    mb.box((W - 0.3, R, 0), (W + 0.035, 20, F.GH), 'm')
    facade.finalize(mb, col, {'m': F.materials['stone']})
    # the neighbour's front wall (painted brick, lower) to the left
    return col


CAMS = {
    # name: (location, target, lens, res (w,h) ratio, sun az, sun el, dusk)
    'full': ((19.0, -27.5, 1.65), (6.6, 0.0, 10.6), 35, (1920, 1440), 226, 11, False),
    'shopfront': ((9.2, -4.3, 1.62), (4.8, 0.0, 2.25), 30, (1920, 1080), 215, 18, False),
    'window': ((5.2, -3.4, 10.0), (4.45, 0.0, 9.9), 32, (1920, 1280), 226, 11, False),
    'fire': ((2.3, -2.6, 1.7), (1.35, 0.4, 14.0), 22, (1280, 1920), 25, 14, False),
    'wall': ((6.4, -5.5, 6.9), (5.6, 0.0, 7.6), 35, (1920, 1280), 226, 11, False),
    'dusk': ((19.0, -27.5, 1.65), (6.6, 0.0, 10.6), 35, (1920, 1440), 260, -3.5, True),
}


def setup_render(scene, w, h, samples, threads):
    scene.render.engine = 'CYCLES'
    c = scene.cycles
    c.device = 'CPU'
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.02
    c.use_denoising = True
    c.denoiser = 'OPENIMAGEDENOISE'
    c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    c.denoising_prefilter = 'ACCURATE'
    c.max_bounces = 8
    c.diffuse_bounces = 3
    c.glossy_bounces = 4
    c.transmission_bounces = 6
    c.transparent_max_bounces = 8
    c.sample_clamp_indirect = 10.0
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.blur_glossy = 0.5
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.render.resolution_percentage = 100
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = threads
    scene.view_settings.view_transform = 'AgX'
    try:
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    scene.render.image_settings.file_format = 'PNG'


def make_cam(scene, loc, tgt, lens):
    cd = bpy.data.cameras.new("PROOF_cam")
    cd.lens = lens
    cd.sensor_width = 36
    cd.clip_start = 0.05
    cd.clip_end = 500
    ob = bpy.data.objects.new("PROOF_cam", cd)
    ob.location = loc
    ob.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(ob)
    scene.camera = ob
    return ob


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    opt = dict(w=640, samples=32, threads=2, tag='', save=False)
    shots = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--save':
            opt['save'] = True
        elif a.startswith('--'):
            opt[a[2:]] = argv[i + 1]
            i += 1
        else:
            shots.append(a)
        i += 1
    shots = shots or list(CAMS)
    clean()
    scene = bpy.context.scene
    t0 = time.time()
    F = facade.Facade({})
    col = F.build()
    scene.collection.children.link(col)
    print(f"[facade] built in {time.time() - t0:.1f}s", flush=True)
    nf = sum(len(o.data.polygons) for o in col.all_objects if o.type == 'MESH')
    print(f"[facade] base faces (pre-modifier): {nf}", flush=True)
    nb = facade.Facade(dict(name='ASSET_facade_nb', bays=4, storeys=4, brick='buff', trim='cream', shop='deli', number='210', seed=23,
                            fire_escape_bay=2, balcony=None, ac=(1, 2), corner=False, interiors_lit=0.3))
    ncol = nb.build()
    scene.collection.children.link(ncol)
    for ob in ncol.all_objects:
        ob.location.x -= nb.W
    setup_env(scene, F)
    os.makedirs(OUT_PREV, exist_ok=True)
    if opt['save']:
        os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
        setup_world(scene, 226, 11)
        make_cam(scene, *CAMS['full'][:3])
        bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
        print("[facade] saved", OUT_BLEND, flush=True)
    for s in shots:
        loc, tgt, lens, res, az, el, dusk = CAMS[s]
        for ob in [o for o in scene.objects if o.name.startswith("PROOF_sun") or o.name.startswith("PROOF_cam")]:
            bpy.data.objects.remove(ob)
        setup_world(scene, az, el, dusk)
        make_cam(scene, loc, tgt, lens)
        w = int(opt['w'])
        h = int(round(w * res[1] / res[0]))
        setup_render(scene, w, h, int(opt['samples']), int(opt['threads']))
        facade.set_lights(col, day=not dusk, interior_mult=(1.0 if dusk else 0.6), shop_mult=(1.0 if dusk else 0.6))
        scene.view_settings.exposure = 2.4 if dusk else 0.0
        fn = os.path.join(OUT_PREV, f"facade_{s if s != 'fire' else 'fire_escape'}" + (s == 'window' and '_close' or '') + (f"_{opt['tag']}" if opt['tag'] else '') + ".png")
        if s == 'full':
            fn = fn.replace('facade_full', 'facade_full')
        scene.render.filepath = fn
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[render] {s} {w}x{h} {opt['samples']}spp: {time.time() - t1:.1f}s -> {fn}", flush=True)


if __name__ == "__main__":
    main()
