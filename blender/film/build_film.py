"""Sixty Stories - FILM build: city.blend + hero -> film.blend + shots.json.

    /home/user/tools/bl/bin/python blender/film/build_film.py [--no-save] [--quick]

Opens blender/out/city.blend (retrying while another builder is writing it), appends the
hero through hero_api, keys every pose, the hero's flight path (plan.py physics),
lines, six shot cameras bound by timeline markers, per-shot lighting/exposure keys on
LIGHT_CTRL, render settings and the compositor; saves blender/out/film.blend and
blender/out/shots.json. Everything is regenerated from the two source files: never
hand-edit film.blend.
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'blender', 'common'))
sys.path.insert(0, os.path.join(ROOT, 'blender', 'hero'))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402

import lighting  # noqa: E402
import hero_api as H  # noqa: E402
import plan as PL  # noqa: E402
import cameras as CAM  # noqa: E402
from curves import gaussian_smooth  # noqa: E402
import shot_settings as SS  # noqa: E402

OUT = os.path.join(ROOT, 'blender', 'out')
CITY = os.path.join(OUT, 'city.blend')
HERO = os.path.join(OUT, 'hero.blend')
FILM = os.path.join(OUT, 'film.blend')
SHOTS_JSON = os.path.join(OUT, 'shots.json')
LOOKLAB = os.path.join(OUT, 'looklab')
PLATE = os.path.join(LOOKLAB, 'plate.blend')


def log(*a):
    print('[film]', *a, flush=True)


# ------------------------------------------------------------------------------ load
def _stable(path, wait=3.0):
    s0 = os.path.getsize(path)
    m0 = os.path.getmtime(path)
    time.sleep(wait)
    return s0 == os.path.getsize(path) and m0 == os.path.getmtime(path)


def open_city(retries=40):
    for k in range(retries):
        try:
            if not _stable(CITY) or not _stable(HERO, 0.5):
                raise RuntimeError('source file still being written')
            bpy.ops.wm.open_mainfile(filepath=CITY)
            if bpy.context.scene.name and bpy.data.objects.get('LIGHT_CTRL'):
                return bpy.context.scene
            raise RuntimeError('city.blend incomplete')
        except Exception as e:  # noqa
            log('open failed (%s), retry %d' % (e, k))
            time.sleep(15)
    raise SystemExit('could not open city.blend')


# ------------------------------------------------------------------------------ hero
def mirrored(name):
    if name.endswith('_L') and name[:-2] + '_R' in H.POSES and name not in H.POSES:
        return H.mirror_spec(H.POSES[name[:-2] + '_R'])
    if name == 'swing_tuck_L':
        return H.mirror_spec(H.POSES['swing_tuck'])
    return name


def key_poses(rig):
    for f, name, w in PL.POSE_KEYS:
        H.apply_pose(rig, mirrored(name), f, weight=w)
    for f, yaw, pitch in PL.HEAD_KEYS:
        H.set_head_look(rig, f, yaw=yaw, pitch=pitch)
    # quaternion keys: smooth bezier, no overshoot
    ad = rig.animation_data
    for fc in _fcurves(rig):
        for kp in fc.keyframe_points:
            kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'


def _fcurves(idb):
    ad = idb.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    try:
        return list(act.fcurves)
    except AttributeError:
        pass
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def _rest_rot(rig, bone):
    return rig.data.bones[bone].matrix_local.to_3x3()


def body_local(rig, frame, scene):
    """Evaluated rig-space info at frame: hips point, chest (front, up), shoulder->grip."""
    scene.frame_set(frame)
    ev = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
    pb = ev.pose.bones
    hips = pb['root'].head.copy()
    Rb = pb['spine03'].matrix.to_3x3() @ _rest_rot(rig, 'spine03').inverted()
    Rh = pb['root'].matrix.to_3x3() @ _rest_rot(rig, 'root').inverted()
    Rc = (Rb.to_quaternion().slerp(Rh.to_quaternion(), 0.35)).to_matrix()
    up = Rc @ Vector((0, 0, 1))
    front = Rc @ Vector((0, -1, 0))
    arms = {}
    for s in 'LR':
        arms[s] = (pb[H.GRIP['bone'][s]].head - pb['upperarm01.' + s].head).normalized()
    return hips, front, up, arms


def place_hero(rig, scene, hero):
    """Key HERO_RIG world transform for every frame: perch frames pinned at the perch
    top, flight frames pin the hips to the physics path and orient the body per intent."""
    rig.rotation_mode = 'QUATERNION'
    base = Quaternion((0, 0, 1), math.radians(90))     # rest faces -Y -> faces +X
    perch = Vector(PL.PERCH)
    for f, lean in ((0, 0.0), (84, 0.0), (95, 7.0)):
        q = base @ Quaternion((1, 0, 0), -math.radians(lean))   # lean forward over the edge
        rig.rotation_quaternion = q
        rig.location = perch
        rig.keyframe_insert('location', frame=f)
        rig.keyframe_insert('rotation_quaternion', frame=f)
    # real hips at the push-off frame: shift the scripted s3 path to start there
    scene.frame_set(95)
    ev = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
    hips95 = np.array(ev.matrix_world @ ev.pose.bones['root'].head)
    P = hero['P'].copy()
    d = hips95 - P[96]
    fade = np.clip((np.arange(PL.TOTAL) - 96) / 40.0, 0, 1)
    for i in range(96, 144):
        P[i] = P[i] + d * (1 - 0.5 * fade[i])
    hero['P_used'] = P
    intents = PL.body_intent(hero)
    quats, hipsl = {}, {}
    for i in range(96, PL.TOTAL):
        hips, front, up, arms = body_local(rig, i, scene)
        it = intents[i]
        if it[0] == 'line':
            side, A, trav = it[1], it[2], it[3]
            aw = Vector(A) - Vector(P[i])
            Mw = H._frame(aw, Vector(trav))
            Ml = H._frame(arms[side], front)
        else:
            fw, uw = it[1], it[2]
            Mw = H._frame(Vector(uw), Vector(fw))
            Ml = H._frame(up, front)
        R = Mw @ Ml.transposed()
        quats[i] = np.array(R.to_quaternion())
        hipsl[i] = np.array(hips)
    # per shot: hemisphere-align, smooth (body lag), re-normalise
    for sh in PL.SHOTS[2:]:
        fr = list(range(sh['start'], sh['start'] + sh['count']))
        Q = np.array([quats[i] for i in fr])
        for k in range(1, len(Q)):
            if Q[k].dot(Q[k - 1]) < 0:
                Q[k] = -Q[k]
        Q = gaussian_smooth(Q, 1.3)
        Q /= np.linalg.norm(Q, axis=1)[:, None]
        for k, i in enumerate(fr):
            q = Quaternion(Q[k])
            rig.rotation_quaternion = q
            rig.location = Vector(P[i]) - q.to_matrix() @ Vector(hipsl[i])
            rig.keyframe_insert('location', frame=i)
            rig.keyframe_insert('rotation_quaternion', frame=i)
    for fc in _fcurves(rig):
        if fc.data_path in ('location', 'rotation_quaternion'):
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.handle_left_type = kp.handle_right_type = 'AUTO'
    # cuts: nothing on the rig (transform or pose) interpolates across a cut, so the
    # last frame's shutter interval (frame..frame+0.5) never blends toward the next shot
    for sh in PL.SHOTS[1:]:
        for fc in _fcurves(rig):
            for kp in fc.keyframe_points:
                if abs(kp.co.x - (sh['start'] - 1)) < 0.01:
                    kp.interpolation = 'CONSTANT'


def add_lines(rig, scene, hero):
    webs = []
    for w in hero['webs']:
        on, off = w['on'], w['off']
        ob = H.add_web(rig, w['side'], tuple(w['anchor']), on, off, w['name'], slack=0.0, attach='grip')
        anc = bpy.data.objects[w['name'] + '_anchor']
        taut = w['taut']
        fly = w.get('fly_frames', max(1, taut - on))
        if taut > on:
            scene.frame_set(on)
            g = np.array(H.grip_world(rig, w['side']))
            A = np.array(w['anchor'])
            for k in range(0, fly + 1):
                f = on + k
                if f > off:
                    break
                t = k / float(fly)
                tt = 1 - (1 - t) ** 1.6
                anc.location = Vector(g + (A - g) * tt)
                anc.keyframe_insert('location', frame=f)
            for fc in _fcurves(anc):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
            H.key_slack(ob, on, 0.7)
            H.key_slack(ob, min(taut, off), 0.5 if taut > off else 0.25)
            if taut <= off:
                H.key_slack(ob, taut + 2, 0.0)
        else:
            H.key_slack(ob, on, 0.0)
        webs.append(ob)
    return webs


# ------------------------------------------------------------------------------ cameras
def build_cameras(scene, cams):
    objs = {}
    for sh in PL.SHOTS:
        sid = sh['id']
        c = cams[sid]
        cd = bpy.data.cameras.new('CAM_' + sid)
        cd.sensor_fit = 'HORIZONTAL'
        cd.sensor_width = 36.0
        cd.clip_start = 0.05
        cd.clip_end = 40000
        cd.dof.use_dof = True
        cd.dof.aperture_blades = 7
        cd.dof.aperture_rotation = math.radians(12)
        ob = bpy.data.objects.new('CAM_' + sid, cd)
        scene.collection.objects.link(ob)
        ob.rotation_mode = 'QUATERNION'
        prev = None
        for k, f in enumerate(c['frames']):
            q = Matrix(c['rot'][k].tolist()).to_quaternion()
            if prev is not None and q.dot(prev) < 0:
                q = -q
            prev = q
            ob.location = Vector(c['loc'][k])
            ob.rotation_quaternion = q
            ob.keyframe_insert('location', frame=int(f))
            ob.keyframe_insert('rotation_quaternion', frame=int(f))
            cd.lens = float(c['lens'][k])
            cd.dof.focus_distance = float(c['focus'][k])
            cd.dof.aperture_fstop = float(c['fstop'][k])
            cd.keyframe_insert('lens', frame=int(f))
            cd.keyframe_insert('dof.focus_distance', frame=int(f))
            cd.keyframe_insert('dof.aperture_fstop', frame=int(f))
        # extrapolate one frame past the end so the shutter interval of the last frame
        # sees continuous motion (no freeze at the cut)
        for idb in (ob, cd):
            for fc in _fcurves(idb):
                fc.extrapolation = 'LINEAR'
                for kp in fc.keyframe_points:
                    kp.interpolation = 'BEZIER'
                    kp.handle_left_type = kp.handle_right_type = 'AUTO'
        m = scene.timeline_markers.new(sid, frame=sh['start'])
        m.camera = ob
        objs[sid] = ob
    scene.camera = objs['s1']
    return objs


# ------------------------------------------------------------------------------ lighting
def key_lighting(scene):
    """Look-neutral lighting: the city presets as shipped, keyed per shot (SS.NEUTRAL_LIGHT).
    The selected look module re-keys everything afterwards."""
    ctrl = lighting.get_ctrl()
    for f, preset, d in SS.NEUTRAL_LIGHT:
        lighting.apply_preset(scene, preset, dusk=d, frame=f)
        ctrl['haze_density'] = max(0.00012, float(ctrl['haze_density']))
        ctrl.keyframe_insert('["haze_density"]', frame=f)
    for fc in _fcurves(ctrl):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    lighting.touch(scene)


def apply_look(scene, name):
    import importlib
    sys.path.insert(0, os.path.join(HERE, 'looks'))
    mod = importlib.import_module(name)
    mod.apply(scene)
    log('look applied:', name)


# ------------------------------------------------------------------------------ render
def render_settings(scene):
    r = scene.render
    r.engine = 'CYCLES'
    r.resolution_x, r.resolution_y, r.resolution_percentage = SS.RES[0], SS.RES[1], 100
    r.fps = 24
    r.fps_base = 1.0
    scene.frame_start, scene.frame_end = 0, PL.TOTAL - 1
    r.use_motion_blur = True
    r.motion_blur_shutter = 0.5
    # shutter opens AT the frame: a cut frame never samples the previous shot
    r.motion_blur_position = 'START'
    # per-frame shutter (render_frames.py also sets it per frame)
    for i in range(PL.TOTAL):
        if i == 0 or SS.shutter(i) != SS.shutter(i - 1):
            r.motion_blur_shutter = SS.shutter(i)
            scene.keyframe_insert('render.motion_blur_shutter', frame=i)
    for fc in _fcurves(scene):
        if fc.data_path == 'render.motion_blur_shutter':
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
    r.use_persistent_data = True
    r.film_transparent = False
    try:
        r.compositor_device = 'CPU'
    except Exception:
        pass
    r.threads_mode = 'FIXED'
    r.threads = 2
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_depth = '8'
    r.image_settings.color_mode = 'RGB'
    c = scene.cycles
    c.device = 'CPU'
    c.samples = 32
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.02
    c.use_denoising = True
    c.denoiser = 'OPENIMAGEDENOISE'
    try:
        c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
        c.denoising_prefilter = 'ACCURATE'
        c.denoising_quality = 'HIGH'
    except Exception:
        pass
    c.film_exposure = 1.0
    for k, v in SS.CYCLES.items():
        setattr(c, k, v)
    c.pixel_filter_type = 'BLACKMAN_HARRIS'
    c.filter_width = 1.2
    c.sample_clamp_indirect = 6.0
    c.sample_clamp_direct = 0.0
    vs = scene.view_settings
    vs.view_transform = 'AgX'
    vs.look = 'None'
    vl = scene.view_layers[0]
    vl.use_pass_z = True
    vl.use_pass_combined = True
    build_compositor(scene)


def build_compositor(scene):
    """Look-neutral compositor: render layers -> output, plus the DEPTH_OUT file node."""
    sys.path.insert(0, os.path.join(HERE, 'looks'))
    import lookkit
    lookkit.new_compositor(scene)


def _gset(node, **kw):
    for k, v in kw.items():
        s = node.inputs.get(k)
        if s is None:
            log('glare input missing', k)
            continue
        try:
            s.default_value = v
        except Exception as e:
            log('glare set fail', k, v, e)


def hero_detail(rig, scene):
    """Body subdivision per shot (hero_api.set_detail semantics), keyed CONSTANT."""
    subs = [(o, m) for o in rig.children for m in o.modifiers if m.type == 'SUBSURF']
    for sh in PL.SHOTS:
        lvl = SS.SHOT[sh['id']]['subsurf']
        for o, m in subs:
            m.render_levels = lvl
            o.keyframe_insert('modifiers["%s"].render_levels' % m.name, frame=sh['start'])
    for o, m in subs:
        for fc in _fcurves(o):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'


# ------------------------------------------------------------------------------ meta out
def shots_json(scene, rig, hero, cams):
    P = hero['P_used']
    V = hero['V']
    tele = []
    hs = []
    bones = ['head', 'spine03', 'root', 'foot.L', 'foot.R', 'hand.L' if 'hand.L' in rig.pose.bones else 'wrist.L',
             'wrist.R', 'toes.L', 'toes.R', 'neck03']
    bones = [b for b in bones if b in rig.pose.bones]
    for i in range(PL.TOTAL):
        sh = PL.shot(i)
        c = cams[sh['id']]
        k = i - sh['start']
        if sh['id'] == 's1':
            loc = c['loc']
            v = (loc[min(k + 1, len(loc) - 1)] - loc[max(k - 1, 0)]) / (2 / 24.0) if len(loc) > 1 else 0
            tele.append(dict(i=i, altitude_m=round(float(loc[k][2]), 1), speed_kmh=round(float(np.linalg.norm(v) * 3.6), 1),
                             lens_mm=round(float(c['lens'][k]), 1)))
        else:
            vv = V[i] if i >= 96 else np.zeros(3)
            tele.append(dict(i=i, altitude_m=round(float(P[i][2] if i >= 96 else PL.PERCH[2]), 1),
                             speed_kmh=round(float(np.linalg.norm(vv) * 3.6), 1),
                             lens_mm=round(float(c['lens'][k]), 1)))
        scene.frame_set(i)
        ev = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mw = ev.matrix_world
        pts = [np.array(mw @ ev.pose.bones[b].head) for b in bones]
        pts.append(np.array(mw @ ev.pose.bones['head'].tail))
        chest = np.array(mw @ ev.pose.bones['spine03'].head)
        M, eye, lens = c['rot'][k], c['loc'][k], c['lens'][k]
        pc = CAM.project(M, eye, chest, lens)
        ys = [CAM.project(M, eye, p, lens) for p in pts]
        ys = [y for y in ys if y is not None]
        if pc is None or abs(pc[0]) > 0.5 or abs(pc[1]) > 0.5:
            hs.append(None)
        else:
            hgt = (max(y[1] for y in ys) - min(y[1] for y in ys)) if ys else 0.0
            hs.append(dict(x=round(pc[0] + 0.5, 4), y=round(0.5 - pc[1], 4), h=round(float(hgt), 4)))
    data = dict(fps=24, width=SS.RES[0], height=SS.RES[1], total=PL.TOTAL,
                shots=[dict(id=s['id'], title=s['title'], start=s['start'], count=s['count'],
                            lens_mm=s['lens_mm'], logline=s['logline']) for s in PL.SHOTS],
                telemetry=tele,
                hero_screen=[dict(i=i, **h) if h else None for i, h in enumerate(hs)],
                notes=dict(hero_screen='x,y normalised from the top-left of the frame (chest); h = '
                                       'approximate height of the hero as a fraction of frame height',
                           telemetry='altitude above the street (m) and speed (km/h) of the hero; '
                                     'camera for s1'))
    tmp = SHOTS_JSON + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, SHOTS_JSON)


# ------------------------------------------------------------------------------ main
def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    t0 = time.time()
    scene = open_city()
    log('city open', round(time.time() - t0, 1))
    # the city's own preview camera stays, unused
    rig = H.append_hero(HERO, scene)
    log('hero appended', rig.name)
    hero = PL.design_hero()
    key_poses(rig)
    place_hero(rig, scene, hero)
    log('hero keyed', round(time.time() - t0, 1))
    add_lines(rig, scene, hero)
    cams = CAM.design_cameras(dict(hero, P=hero['P_used']))
    build_cameras(scene, cams)
    key_lighting(scene)
    render_settings(scene)
    hero_detail(rig, scene)
    import hero_tune
    hero_tune.apply(rig)
    scene.frame_set(0)
    shots_json(scene, rig, hero, cams)
    log('shots.json written', round(time.time() - t0, 1))
    if '--no-save' not in args:
        os.makedirs(LOOKLAB, exist_ok=True)
        tmp = PLATE + '.tmp.blend'
        bpy.ops.wm.save_as_mainfile(filepath=tmp, compress=True, copy=True)
        os.replace(tmp, PLATE)
        import shutil
        shutil.copyfile(SHOTS_JSON, os.path.join(LOOKLAB, 'shots.json'))
        log('saved look-neutral plate', PLATE)
    apply_look(scene, SS.LOOK)
    if '--no-save' not in args:
        tmp = FILM + '.tmp.blend'
        bpy.ops.wm.save_as_mainfile(filepath=tmp, compress=True, copy=True)
        os.replace(tmp, FILM)
        log('saved', FILM, round(time.time() - t0, 1))


if __name__ == '__main__':
    main()
