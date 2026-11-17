"""Proof renders for the taxi hero asset.

/home/user/tools/bl/bin/python blender/assets/taxi_proof.py -- --shots front34,side --res 640 \
    --samples 32 --threads 2 [--variant yellow_cab] [--out DIR] [--save]

Neutral golden-hour exterior: sky texture with a low warm sun (12 deg), asphalt ground,
a kerb + pavement, and a ring of building blocks for the paint and glass to reflect.
"""
import bpy
import math
import os
import sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import taxi  # noqa: E402

OUT = os.path.join(taxi.ROOT, "blender", "out", "preview", "assets")

# shot: camera location, look-at, focal length, sun azimuth (deg, from +Y toward +X... see below)
SHOTS = {
    "front34": dict(cam=(4.9, 6.4, 1.62), at=(0.0, 0.35, 0.72), lens=50, sun_az=60.0),
    "rear34": dict(cam=(-4.6, -6.6, 1.62), at=(0.0, -0.3, 0.72), lens=50, sun_az=20.0),   # backlit
    "side": dict(cam=(8.6, 0.05, 1.05), at=(0.0, 0.05, 0.72), lens=50, sun_az=120.0),
    "wheel_close": dict(cam=(2.15, 2.75, 0.62), at=(0.82, 1.45, 0.36), lens=85, sun_az=70.0),
    "lamp_close": dict(cam=(1.85, 4.05, 1.10), at=(0.62, 2.28, 0.76), lens=85, sun_az=60.0),
    "interior": dict(cam=(1.75, -0.95, 1.30), at=(-0.25, 0.25, 0.90), lens=30, sun_az=150.0),
}


def setup_world(scene, sun_az_deg, sun_el_deg=12.0):
    w = bpy.data.worlds.new("proof_sky")
    scene.world = w
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(sun_el_deg)
    # sun_rotation: angle around Z measured from +Y? (Blender: 0 = sun toward -Y... we compute
    # from the requested azimuth so that the sun sits at direction (sin az, cos az) from origin)
    sky.sun_rotation = math.radians(sun_az_deg)
    sky.sun_disc = True
    sky.altitude = 50.0
    sky.air_density = 1.4
    sky.aerosol_density = 2.2
    ring = bpy.data.objects.get("proof_ring")
    if ring:
        ring.rotation_euler = (0, 0, -math.radians(sun_az_deg))
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.22
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])


def mat_asphalt():
    m, nt, b = taxi._new_mat("proof_asphalt")
    tc = taxi._texco(nt)
    n1 = taxi._n(nt, "ShaderNodeTexNoise", -800, 0, Scale=1.2, Detail=8.0, Roughness=0.6)
    taxi._l(nt, tc.outputs["Object"], n1.inputs["Vector"])
    v = taxi._n(nt, "ShaderNodeTexVoronoi", -800, -300, Scale=900.0)
    taxi._l(nt, tc.outputs["Object"], v.inputs["Vector"])
    agg = taxi._maprange(nt, v.outputs["Distance"], 0.0, 0.5, 1.0, 0.0)
    col = taxi._mixc(nt, taxi._maprange(nt, n1.outputs["Fac"], 0.35, 0.65), (0.040, 0.039, 0.038, 1), (0.058, 0.056, 0.054, 1))
    col = taxi._mixc(nt, taxi._math(nt, "MULTIPLY", agg, 0.25), col, (0.11, 0.105, 0.10, 1))
    taxi._l(nt, col, b.inputs["Base Color"])
    taxi._l(nt, taxi._maprange(nt, n1.outputs["Fac"], 0.3, 0.7, 0.62, 0.9), b.inputs["Roughness"])
    bp = taxi._n(nt, "ShaderNodeBump", 0, -400, Strength=0.35, Distance=0.002)
    taxi._l(nt, agg, bp.inputs["Height"])
    taxi._l(nt, bp.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_block(i):
    m, nt, b = taxi._new_mat("proof_block_%d" % i)
    tc = taxi._texco(nt)
    br = taxi._n(nt, "ShaderNodeTexBrick", -500, 0, Scale=1.0)
    br.inputs["Mortar Size"].default_value = 0.35
    br.inputs["Brick Width"].default_value = 2.2
    br.inputs["Row Height"].default_value = 3.4
    br.offset = 0.0
    br.squash = 1.0
    tones = [(0.30, 0.17, 0.11), (0.42, 0.38, 0.33), (0.20, 0.20, 0.21), (0.48, 0.36, 0.25), (0.13, 0.14, 0.16)]
    t = tones[i % len(tones)]
    br.inputs["Color1"].default_value = (0.03, 0.035, 0.04, 1)
    br.inputs["Color2"].default_value = (0.05, 0.06, 0.07, 1)
    br.inputs["Mortar"].default_value = t + (1,)
    taxi._l(nt, tc.outputs["Object"], br.inputs["Vector"])
    taxi._l(nt, br.outputs["Color"], b.inputs["Base Color"])
    rough = taxi._maprange(nt, br.outputs["Fac"], 0.0, 1.0, 0.15, 0.85)
    taxi._l(nt, rough, b.inputs["Roughness"])
    return m


def setup_stage(scene):
    import bmesh
    coll = bpy.data.collections.new("PROOF_stage")
    scene.collection.children.link(coll)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=150)
    me = bpy.data.meshes.new("proof_ground")
    bm.to_mesh(me)
    g = bpy.data.objects.new("proof_ground", me)
    me.materials.append(mat_asphalt())
    coll.objects.link(g)
    # kerb + pavement along -X side (behind the car in the front3/4 view)
    conc = taxi.mat_simple("proof_concrete", (0.36, 0.35, 0.33), rough=0.8, bump=0.3, bump_scale=60.0)
    for (sx, sy, sz, loc) in (((0.25, 60, 0.15), None, None, (-4.2, 0, 0.075)),
                              ((6.0, 60, 0.14), None, None, (-7.3, 0, 0.07))):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=sx, verts=bm.verts)
        me = bpy.data.meshes.new("proof_kerb")
        bm.to_mesh(me)
        o = bpy.data.objects.new("proof_kerb", me)
        o.location = loc
        me.materials.append(conc)
        coll.objects.link(o)
    # ring of building blocks for reflections
    import random
    rnd = random.Random(7)
    ring = bpy.data.objects.new("proof_ring", None)
    coll.objects.link(ring)
    for i in range(18):
        # leave a gap around local +Y; setup_world turns the ring so the gap faces the sun
        a = math.radians(45 + 270 * i / 17) + rnd.uniform(-0.04, 0.04)
        r = rnd.uniform(26, 40)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        h = rnd.uniform(14, 55)
        bmesh.ops.scale(bm, vec=(rnd.uniform(10, 18), rnd.uniform(10, 16), h), verts=bm.verts)
        bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=bm.verts)
        me = bpy.data.meshes.new("proof_block")
        bm.to_mesh(me)
        o = bpy.data.objects.new("proof_block", me)
        o.location = (r * math.sin(a), r * math.cos(a), 0)
        o.rotation_euler = (0, 0, -a)
        o.parent = ring
        me.materials.append(mat_block(i))
        coll.objects.link(o)
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
    scene.view_settings.exposure = -1.3
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
    ap.add_argument("--elev", type=float, default=12.0)
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
    for shot in a.shots.split(","):
        if not shot:
            continue
        setup_world(scene, SHOTS[shot]["sun_az"], a.elev)
        set_camera(scene, shot)
        scene.render.filepath = os.path.join(a.out, a.prefix + shot + ".png")
        bpy.ops.render.render(write_still=True)
        print("wrote", scene.render.filepath)


if __name__ == "__main__":
    main()
