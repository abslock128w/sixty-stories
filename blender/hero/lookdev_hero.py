"""Look-dev renders of the appended hero.  Usage:
   python lookdev_hero.py turn|close|poses|swing|details|test [samples] [scale]
"""
import sys, os, math, time
sys.path.insert(0, '/home/user/sixty/blender/hero')
import bpy
import numpy as np
from mathutils import Vector
import hero_api as H
import lookdev as LD

OUT = LD.OUT
mode = sys.argv[1] if len(sys.argv) > 1 else 'turn'
SAMPLES = int(sys.argv[2]) if len(sys.argv) > 2 else 48
SCALE = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
TMP = '/tmp/claude-0/ld'
os.makedirs(TMP, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
rig = H.append_hero()
if os.environ.get('DETAIL'):
    H.set_detail(rig, int(os.environ['DETAIL']))
if os.environ.get('EMIS'):
    for m in bpy.data.materials:
        m.cycles.emission_sampling = os.environ['EMIS']
if os.environ.get('SIMPLE'):
    for nm in os.environ['SIMPLE'].split(','):
        mt = bpy.data.materials[nm]; nt_ = mt.node_tree
        for nd in list(nt_.nodes):
            nt_.nodes.remove(nd)
        bsd = nt_.nodes.new('ShaderNodeBsdfPrincipled'); ou = nt_.nodes.new('ShaderNodeOutputMaterial')
        nt_.links.new(bsd.outputs[0], ou.inputs[0])
if os.environ.get('NOGLASS'):
    bpy.data.materials['HERO_visor_glass'].node_tree.nodes['Principled BSDF'].inputs['Transmission Weight'].default_value = 0.0
if os.environ.get('NOSHEEN'):
    for m in bpy.data.materials:
        if m.node_tree:
            for nd in m.node_tree.nodes:
                if nd.type == 'BSDF_PRINCIPLED':
                    for l in list(nd.inputs['Sheen Weight'].links):
                        m.node_tree.links.remove(l)
                    nd.inputs['Sheen Weight'].default_value = 0.0
for _n in os.environ.get('HIDE', '').split(','):
    if _n and _n in bpy.data.objects:
        bpy.data.objects[_n].hide_render = True
LD.setup_scene(sc, samples=SAMPLES)
LD.world_gradient(sc, strength=0.8)


def res(w, h):
    sc.render.resolution_x = int(w * SCALE); sc.render.resolution_y = int(h * SCALE)


def bbox_center():
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in rig.children:
        if o.type == 'MESH' and o.name.startswith('HERO_body'):
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
            co = co.reshape(-1, 3)
            M = np.array(o.matrix_world)
            pts = co @ M[:3, :3].T + M[:3, 3]
            ev.to_mesh_clear()
    return pts.min(0), pts.max(0)


def orbit_cam(target, dist, az, el, lens, name='cam', dof=None):
    a, e = math.radians(az), math.radians(el)
    loc = Vector(tuple(target)) + float(dist) * Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    return LD.camera(sc, loc, tuple(target), lens=lens, name=name, dof=dof)


if mode == 'turn':
    res(480, 800)
    H.pose_now(rig, 'rest')
    LD.rim_rig(sc, key_az=150, key_el=12, key_energy=4.0, fill=1.0)
    paths = []
    for k, az in enumerate((0, -40, -90, 180)):
        orbit_cam((0, 0, 0.92), 6.5, az, 4, 60)
        paths.append(LD.render(sc, f'{TMP}/turn_{k}.png'))
    LD.contact_sheet(paths, f'{OUT}/a_turnaround.png', 4, ['front', '3/4', 'side', 'back'])

elif mode == 'close':
    res(1920, 804)
    pose = sys.argv[4] if len(sys.argv) > 4 else 'perch_look_up'
    H.pose_now(rig, pose)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = rig.evaluated_get(dg)
    head = ev.matrix_world @ ev.pose.bones['head'].head
    hz = ev.matrix_world @ ev.pose.bones['head'].tail
    tgt = head * 0.55 + hz * 0.45 + Vector((0, 0, -0.05))
    REAR = bool(os.environ.get('REAR'))
    if REAR:
        LD.world_gradient(sc, strength=0.5, glow_az=-15)
        LD.rim_rig(sc, key_az=-18, key_el=7, key_energy=30.0, fill=0.25)
        bpy.data.objects['LD_kick'].data.energy = 140
        bpy.data.objects['LD_fill'].data.energy = 160
    else:
        LD.world_gradient(sc, strength=0.45, glow_az=110)
        LD.rim_rig(sc, key_az=165, key_el=9, key_energy=30.0, fill=0.25)
    bpy.data.materials["LD_ground_mat"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.03, 0.028, 0.026, 1)
    if REAR:
        tgt = tgt + Vector((0, 0.04, -0.11))
    cam = orbit_cam(tgt, 2.9 if REAR else 2.5, 132 if REAR else -48, 10 if REAR else 3, 135, dof=2.8)
    LD.backdrop(sc, cam, tgt, dist=6.0)
    cam.data.dof.focus_distance = (cam.location - (head * 0.5 + hz * 0.5 + Vector((0, -0.08, 0)))).length
    t = time.time()
    LD.render(sc, os.environ.get('OUTP', f'{OUT}/b_closeup.png'))
    print('close render seconds', round(time.time() - t, 1))

elif mode == 'poses':
    res(400, 480)
    LD.rim_rig(sc, key_az=160, key_el=10, key_energy=4.0, fill=1.0)
    names = sys.argv[4].split(',') if len(sys.argv) > 4 else [n for n in H.POSES if n != 'rest']
    VIEWS = [(-50, 8)] if len(names) > 6 else [(-60, 8), (30, 12)]
    paths = []
    for n in names:
        H.pose_now(rig, n)
        lo, hi = bbox_center()
        c = (lo + hi) / 2
        size = np.linalg.norm(hi - lo)
        for vi, (az, el) in enumerate(VIEWS):
            orbit_cam(Vector(tuple(c)), float(size * 1.9 + 0.6), az, el, 50)
            paths.append(LD.render(sc, f'{TMP}/pose_{n}_{vi}.png'))
    labels = [n + ('' if len(VIEWS) == 1 else ' v%d' % v) for n in names for v in range(len(VIEWS))]
    LD.contact_sheet(paths, f'{OUT}/c_poses.png' if len(names) > 6 else f'{TMP}/poses_sel.png', min(6, len(paths)), labels)

elif mode == 'details':
    res(640, 640)
    pose = sys.argv[4] if len(sys.argv) > 4 else 'stand'
    H.pose_now(rig, pose)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = rig.evaluated_get(dg)
    P = lambda b, tail=False: ev.matrix_world @ (ev.pose.bones[b].tail if tail else ev.pose.bones[b].head)
    LD.rim_rig(sc, key_az=140, key_el=14, key_energy=4.0, fill=1.2)
    shots = [
        ('torso', P('spine01') + Vector((0, -0.05, 0.02)), 2.2, -30, 6, 85),
        ('back', P('spine02') + Vector((0, 0.05, 0.05)), 2.4, 160, 10, 85),
        ('hand_L', P('wrist.L') + Vector((0.02, -0.02, 0)), 0.75, -70, 15, 85),
        ('launcher_R', P('lowerarm02.R') + Vector((0, 0, 0)), 0.75, 60, -10, 85),
        ('feet', (P('foot.L') + P('foot.R')) / 2 + Vector((0, -0.05, -0.03)), 1.4, -25, 12, 85),
        ('helmet_side', P('head') + Vector((0, 0, 0.06)), 1.1, -95, 4, 85),
    ]
    sel = sys.argv[5].split(',') if len(sys.argv) > 5 else None
    paths, labels = [], []
    for nm, tgt, dist, az, el, lens in shots:
        if sel and nm not in sel:
            continue
        orbit_cam(tgt, dist, az, el, lens)
        paths.append(LD.render(sc, f'{TMP}/det_{nm}.png')); labels.append(nm)
    LD.contact_sheet(paths, f'{OUT}/e_details.png' if not sel else f'{TMP}/details_sel.png', 3, labels)

elif mode == 'swing':
    res(960, 402)
    sc.frame_start, sc.frame_end = 1, 25
    anchor = Vector((0.0, 0.0, 28.0))
    Rr = 25.0
    H.apply_pose(rig, 'swing_R', 1)
    H.apply_pose(rig, 'swing_R', 9)
    H.apply_pose(rig, 'swing_tuck', 17, weight=0.7)
    for f in range(1, 18, 2):
        th = -0.42 + 0.84 * (f - 1) / 16.0
        g = anchor + Rr * Vector((0, math.sin(th), -math.cos(th)))
        travel = Vector((0, math.cos(th), math.sin(th)))
        H.orient_to_line(rig, f, 'R', anchor, g, travel)
    web = H.add_web(rig, 'R', anchor=tuple(anchor), frame_on=1, frame_off=30, name='swing_web')
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    LD.world_gradient(sc, strength=0.8, glow_az=160)
    LD.rim_rig(sc, key_az=165, key_el=8, key_energy=12.0, fill=0.6)
    fr = int(sys.argv[4]) if len(sys.argv) > 4 else 9
    cam = LD.camera(sc, (0, 0, 0), (0, 1, 0), lens=40)
    cam.data.dof.use_dof = False
    # chase camera: keyed every frame relative to the grip, so only the swing's
    # relative motion (limbs, line, background) blurs
    for f in range(1, 18):
        sc.frame_set(f)
        gp = H.grip_world(rig, 'R')
        th = -0.42 + 0.84 * (f - 1) / 16.0
        cam.location = gp + Vector((-5.0, -2.6, -1.4))
        LD.aim(cam, gp + Vector((0, 0.0, -0.45)))
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_euler', frame=f)
    sc.frame_set(fr)
    gp = H.grip_world(rig, 'R')
    t = time.time()
    LD.render(sc, f'{OUT}/d_swing.png')
    print('swing render seconds', round(time.time() - t, 1), 'grip', tuple(round(x, 2) for x in gp))

elif mode == 'head':
    res(420, 420)
    poses = sys.argv[4].split(',') if len(sys.argv) > 4 else ['rest']
    LD.rim_rig(sc, key_az=150, key_el=20, key_energy=5.0, fill=1.4)
    paths, labels = [], []
    for pz in poses:
        H.pose_now(rig, pz)
        bpy.context.view_layer.update()
        ev = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        hd = ev.matrix_world @ ev.pose.bones['head'].head
        tgt = hd + Vector((0, 0, 0.0))
        for az in ((0, -40, -90) if len(poses) == 1 else (-90,)):
            orbit_cam(tgt + Vector((0, 0, -0.08)), float(os.environ.get('HD', 1.6)), az, 4, 85)
            paths.append(LD.render(sc, f'{TMP}/head_{pz}_{az}.png')); labels.append(f'{pz} {az}')
    LD.contact_sheet(paths, f'{TMP}/head.png', min(4, len(paths)), labels)
