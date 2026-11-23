"""Proof renders for the taxi hero asset.

/home/user/tools/bl/bin/python blender/assets/taxi_proof.py -- --shots front34,side --res 640 \
    --samples 32 --threads 2 [--variant yellow_cab] [--out DIR] [--save]

Street stage: physical sky (sun 32 deg, along the street axis), asphalt with markings,
granite kerbs + pavements, two rows of glazed building blocks and lamp posts, so the
clearcoat and glass have a real city to reflect. Car parked at the left kerb.
"""
import bpy
import math
import os
import sys
import time
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import taxi  # noqa: E402

OUT = os.path.join(taxi.ROOT, "blender", "out", "preview", "assets")

# shot: camera location, look-at, focal length, sun azimuth (deg; sun direction (sin az, cos az))
# The street runs along Y, so the sun is kept within ~30 deg of the street axis.
SHOTS = {
    "front34": dict(cam=(4.9, 6.4, 1.62), at=(0.0, 0.35, 0.72), lens=50, sun_az=28.0),
    "rear34": dict(cam=(-3.6, -7.0, 1.70), at=(0.0, -0.3, 0.72), lens=50, sun_az=208.0),
    "side": dict(cam=(8.3, 0.05, 1.05), at=(0.0, 0.05, 0.72), lens=50, sun_az=158.0),
    "wheel_close": dict(cam=(2.15, 2.75, 0.62), at=(0.82, 1.45, 0.37), lens=85, sun_az=30.0),
    "lamp_close": dict(cam=(1.85, 4.05, 1.10), at=(0.62, 2.28, 0.76), lens=85, sun_az=24.0),
    "interior": dict(cam=(1.75, -0.95, 1.30), at=(-0.25, 0.25, 0.90), lens=30, sun_az=160.0),
    "variants": dict(cam=(7.6, 9.6, 2.3), at=(-0.4, -1.2, 0.70), lens=40, sun_az=28.0),
}
CURB_L, CURB_R = -1.30, 9.0          # kerb faces (car parked at the left kerb)
BLD_L, BLD_R = -5.6, 12.5            # building lines


def setup_world(scene, sun_az_deg, sun_el_deg=32.0):
    w = bpy.data.worlds.get("proof_sky") or bpy.data.worlds.new("proof_sky")
    scene.world = w
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(sun_el_deg)
    sky.sun_rotation = math.radians(sun_az_deg)
    sky.sun_disc = True
    sky.altitude = 50.0
    sky.air_density = 1.0
    sky.aerosol_density = 1.2
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.20
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])


def mat_asphalt():
    m, nt, b = taxi._new_mat("proof_asphalt")
    tc = taxi._texco(nt)
    n1 = taxi._n(nt, "ShaderNodeTexNoise", -800, 0, Scale=0.6, Detail=8.0, Roughness=0.6)
    taxi._l(nt, tc.outputs["Object"], n1.inputs["Vector"])
    v = taxi._n(nt, "ShaderNodeTexVoronoi", -800, -300, Scale=700.0)
    taxi._l(nt, tc.outputs["Object"], v.inputs["Vector"])
    agg = taxi._maprange(nt, v.outputs["Distance"], 0.0, 0.5, 1.0, 0.0)
    col = taxi._mixc(nt, taxi._maprange(nt, n1.outputs["Fac"], 0.35, 0.65), (0.050, 0.050, 0.051, 1), (0.075, 0.074, 0.072, 1))
    col = taxi._mixc(nt, taxi._math(nt, "MULTIPLY", agg, 0.3), col, (0.16, 0.155, 0.15, 1))
    taxi._l(nt, col, b.inputs["Base Color"])
    taxi._l(nt, taxi._maprange(nt, n1.outputs["Fac"], 0.3, 0.7, 0.62, 0.92), b.inputs["Roughness"])
    b.inputs["Specular IOR Level"].default_value = 0.4
    bp = taxi._n(nt, "ShaderNodeBump", 0, -400, Strength=0.4, Distance=0.002)
    taxi._l(nt, agg, bp.inputs["Height"])
    taxi._l(nt, bp.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_block(i):
    """Building block: wall tone + a grid of glazed windows (reflective) in facade coords."""
    m, nt, b = taxi._new_mat("proof_block_%d" % i)
    tc = taxi._texco(nt)
    sep = taxi._n(nt, "ShaderNodeSeparateXYZ", -900, 0)
    taxi._l(nt, tc.outputs["Object"], sep.inputs["Vector"])
    comb = taxi._n(nt, "ShaderNodeCombineXYZ", -700, 0)
    taxi._l(nt, taxi._math(nt, "ADD", sep.outputs["X"], sep.outputs["Y"]), comb.inputs["X"])
    taxi._l(nt, taxi._math(nt, "SUBTRACT", sep.outputs["Z"], 0.9), comb.inputs["Y"])
    br = taxi._n(nt, "ShaderNodeTexBrick", -500, 0, Scale=1.0)
    br.offset = 0.0
    br.squash = 1.0
    br.inputs["Mortar Size"].default_value = 0.55 + 0.25 * (i % 2)
    br.inputs["Brick Width"].default_value = 2.1 + 0.5 * (i % 3)
    br.inputs["Row Height"].default_value = 3.3 + 0.3 * (i % 2)
    tones = [(0.34, 0.16, 0.10), (0.55, 0.50, 0.43), (0.22, 0.22, 0.23), (0.50, 0.38, 0.27),
             (0.62, 0.60, 0.56), (0.28, 0.14, 0.10), (0.40, 0.41, 0.43)]
    t = tones[i % len(tones)]
    br.inputs["Color1"].default_value = (0.020, 0.024, 0.028, 1)
    br.inputs["Color2"].default_value = (0.035, 0.040, 0.046, 1)
    br.inputs["Mortar"].default_value = t + (1,)
    taxi._l(nt, comb.outputs[0], br.inputs["Vector"])
    wall = br.outputs["Fac"]          # 1 = wall (mortar), 0 = window
    nz = taxi._n(nt, "ShaderNodeTexNoise", -500, 300, Scale=0.4, Detail=6.0)
    taxi._l(nt, tc.outputs["Object"], nz.inputs["Vector"])
    col = taxi._mixc(nt, taxi._maprange(nt, nz.outputs["Fac"], 0.3, 0.7, 0.0, 0.35), br.outputs["Color"], (0.06, 0.055, 0.05, 1))
    taxi._l(nt, col, b.inputs["Base Color"])
    taxi._l(nt, taxi._mixf(nt, wall, 0.04, 0.85), b.inputs["Roughness"])
    taxi._l(nt, taxi._mixf(nt, wall, 1.0, 0.5), b.inputs["Specular IOR Level"])
    return m


def _box(coll, name, size, loc, mat):
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    o.location = loc
    me.materials.append(mat)
    coll.objects.link(o)
    return o


def setup_stage(scene):
    import bmesh
    import random
    coll = bpy.data.collections.new("PROOF_stage")
    scene.collection.children.link(coll)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=300)
    me = bpy.data.meshes.new("proof_ground")
    bm.to_mesh(me)
    g = bpy.data.objects.new("proof_ground", me)
    me.materials.append(mat_asphalt())
    coll.objects.link(g)
    conc = taxi.mat_simple("proof_concrete", (0.36, 0.35, 0.33), rough=0.8, bump=0.3, bump_scale=60.0)
    kerb = taxi.mat_simple("proof_kerbstone", (0.30, 0.30, 0.29), rough=0.7, bump=0.4, bump_scale=30.0)
    paint = taxi.mat_simple("proof_roadpaint", (0.62, 0.60, 0.55), rough=0.6)
    yel = taxi.mat_simple("proof_roadpaint_y", (0.60, 0.42, 0.05), rough=0.6)
    L = 300.0
    # kerbs (granite, 15 cm) + pavements on both sides
    _box(coll, "proof_kerb", (0.22, L, 0.15), (CURB_L - 0.11, 0, 0.075), kerb)
    _box(coll, "proof_pavement", (BLD_L - CURB_L + 0.22, L, 0.14), ((BLD_L + CURB_L - 0.22) / 2, 0, 0.07), conc)
    _box(coll, "proof_kerb", (0.22, L, 0.15), (CURB_R + 0.11, 0, 0.075), kerb)
    _box(coll, "proof_pavement", (BLD_R - CURB_R - 0.22, L, 0.14), ((BLD_R + CURB_R + 0.22) / 2, 0, 0.07), conc)
    # road markings: parking-lane edge line + dashed double centre line
    _box(coll, "proof_line", (0.12, L, 0.004), (CURB_L + 2.45, 0, 0.002), paint)
    for y in range(-60, 60, 6):
        _box(coll, "proof_dash", (0.12, 3.0, 0.004), (4.6, y, 0.002), yel)
        _box(coll, "proof_dash", (0.12, 3.0, 0.004), (4.85, y, 0.002), yel)
    # street furniture for reflections: lamp posts on the left kerb
    pole = taxi.mat_simple("proof_pole", (0.05, 0.055, 0.05), rough=0.4, metal=0.6)
    for y in (-9.0, 13.0):
        _box(coll, "proof_post", (0.14, 0.14, 6.0), (CURB_L - 0.45, y, 3.0), pole)
        _box(coll, "proof_arm", (1.6, 0.10, 0.10), (CURB_L + 0.3, y, 5.95), pole)
    # building rows: blocks of varying width / height along both building lines
    rnd = random.Random(11)
    for side, xline in ((-1, BLD_L), (1, BLD_R)):
        y = -90.0
        i = 0 if side < 0 else 3
        while y < 90.0:
            wdt = rnd.uniform(9.0, 20.0)
            h = rnd.uniform(14.0, 34.0) if side < 0 else rnd.uniform(9.0, 18.0)
            dep = 14.0
            setb = rnd.uniform(0.0, 0.6)
            _box(coll, "proof_block", (dep, wdt - 0.4, h),
                 (xline + side * (dep / 2 + setb), y + wdt / 2, h / 2), mat_block(i))
            y += wdt
            i += 1
    # cross street far ahead (+Y) and behind (-Y): distant towers
    for k in range(10):
        h = rnd.uniform(30, 80)
        _box(coll, "proof_tower", (rnd.uniform(16, 30), 20, h),
             (rnd.uniform(-60, 60), (130 if k % 2 else -130) + rnd.uniform(-10, 10), h / 2), mat_block(k + 2))
    return coll


def setup_render(scene, res, samples, threads, aspect=(16, 9)):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.02
    scene.cycles.max_bounces = 10
    scene.cycles.glossy_bounces = 6
    scene.cycles.transmission_bounces = 10
    scene.cycles.transparent_max_bounces = 16
    scene.cycles.sample_clamp_indirect = 8.0
    scene.render.threads_mode = "FIXED"
    scene.render.threads = threads
    scene.render.resolution_x = res
    scene.render.resolution_y = int(res * aspect[1] / aspect[0])
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    scene.view_settings.exposure = -1.6
    scene.render.image_settings.file_format = "PNG"


def set_camera(scene, shot):
    s = SHOTS[shot]
    cam = scene.camera
    if cam is None:
        cd = bpy.data.cameras.new("proof_cam")
        cam = bpy.data.objects.new("proof_cam", cd)
        scene.collection.objects.link(cam)
        scene.camera = cam
    cam.data.lens = s["lens"]
    cam.data.sensor_width = 36.0
    cam.location = s["cam"]
    d = Vector(s["at"]) - Vector(s["cam"])
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.data.dof.use_dof = shot in ("wheel_close", "lamp_close")
    cam.data.dof.focus_distance = d.length
    cam.data.dof.aperture_fstop = 5.6


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default="front34")
    ap.add_argument("--res", type=int, default=640)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--variant", default="yellow_cab")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--prefix", default="taxi_")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--elev", type=float, default=32.0)
    a = ap.parse_args(argv)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    taxi.build(a.variant)
    setup_stage(scene)
    setup_render(scene, a.res, a.samples, a.threads)
    os.makedirs(a.out, exist_ok=True)
    if a.save:
        setup_world(scene, SHOTS["front34"]["sun_az"], a.elev)
        set_camera(scene, "front34")
        bpy.ops.wm.save_as_mainfile(filepath=taxi.OUT_BLEND, compress=True)
        print("saved", taxi.OUT_BLEND)
    shots = [x for x in a.shots.split(",") if x]
    if "variants" in shots:            # extra cars only for the line-up, rendered last
        shots = [x for x in shots if x != "variants"] + ["variants"]
    t_all = time.time()
    for shot in shots:
        if shot == "variants":
            for k, (vn, sd) in enumerate((("black_sedan", 3), ("silver_sedan", 5), ("white_sedan", 9))):
                c = taxi.build(vn, seed=sd)
                bpy.data.objects[c.name + "_root"].location = (0.0, -5.4 * (k + 1), 0.0)
        t0 = time.time()
        setup_world(scene, SHOTS[shot]["sun_az"], a.elev)
        set_camera(scene, shot)
        scene.render.filepath = os.path.join(a.out, a.prefix + shot + ".png")
        bpy.ops.render.render(write_still=True)
        print("wrote", scene.render.filepath, "%.1fs" % (time.time() - t0))
    print("total %.1fs" % (time.time() - t_all))


if __name__ == "__main__":
    main()
