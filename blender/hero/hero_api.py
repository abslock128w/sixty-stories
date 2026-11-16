"""VESPER hero API  (Sixty Stories, HERO builder)

Import from any bpy script:

    import sys; sys.path.insert(0, '/home/user/sixty/blender/hero')
    import hero_api as H
    rig = H.append_hero()                         # collection HERO -> current scene
    H.apply_pose(rig, 'perch_crouch', 1)
    H.apply_pose(rig, 'perch_look_up', 40)
    H.apply_pose(rig, 'leap', 60)
    H.set_head_look(rig, 30, yaw=20, pitch=-10)  # optional extra head offset, keyed
    web = H.add_web(rig, 'R', anchor=(30, 120, 160), frame_on=60, frame_off=120,
                    name='web_A', slack=0.0)
    H.key_slack(web, 60, 0.35); H.key_slack(web, 64, 0.0)   # just-fired sag -> taut

Nothing happens at import time.

Rig facts
---------
* Collection `HERO`, armature object `HERO_RIG` (all meshes parented to it). 1.78 m tall,
  origin on the ground between the feet, rest pose (A-pose) facing -Y.
* Every pose bone uses rotation_mode 'QUATERNION'. apply_pose keys rotation_quaternion of
  ALL deforming bones (plus location of `root`), then re-runs a hemisphere fix over all keys
  of the rig so consecutive keyed poses always interpolate along the short path (no flips).
* Bones: master (ground, parent of everything) > root (hips) > spine05..spine01 (5 spine
  bones, 05 lowest) > neck01..03 > head; clavicle/shoulder01/upperarm01-02 (twist pair)/
  lowerarm01-02 (twist pair)/wrist/metacarpal1-4/finger1-1..5-3 (1 = thumb);
  pelvis/upperleg01-02/lowerleg01-02/foot/toes;  .L/.R suffixes.
  Non-deforming helpers: grip.L/.R (centre of the fist, where a held line passes),
  nozzle.L/.R (launcher muzzle on the inside of the wrist, pointing along the forearm).
* GRIP: line attachment point = head of bone `grip.<side>` (child of wrist.<side>).
  grip_world(rig, side) returns its world position for the current frame.
* Moving the whole character: animate the HERO_RIG object (location + rotation, any
  rotation mode). The rig origin is between the feet; for airborne shots it is usually
  nicer to pivot about the hips: use place_rig(rig, frame, hips=..., forward=..., up=...)
  or orient_to_line(...) which key the object transform for you.

Poses
-----
POSES[name] is a pure-data spec resolved against the rig at apply time:
  root_rot (deg XYZ, rig axes, about the hips), root_loc (m), spine/neck/head (flex,
  side, twist deg), head_aim (rig-space look direction), clav_<S> (elevate, protract),
  arm_<S>: up/fore = upper-arm / forearm directions (out, forward, up) in the chest frame
           or ik = wrist target (rig space, x mirrored per side, or (bone, offset)),
           pole, pron, wrist (ext, dev) or hand_aim (fingers dir, back-of-hand dir),
           hand = HANDS preset name;
  leg_<S>: thigh/shin directions in the pelvis frame or ik = ankle target, pole,
           foot (deg) or foot_aim (toe direction), toes (deg);
  ground=True drops the body so the lowest shoe sole point touches z = 0.
'out' is toward the limb's own side, so equal numbers on L and R are symmetric;
mirror_spec() makes the _L poses. Names:
  rest, stand, perch_crouch, perch_look_up, leap, dive, dive_reach, shoot_R, shoot_L,
  swing_R, swing_L, swing_tuck, release_arch, flip_tuck, apex_classic, freefall_spread,
  plus hand-only presets in HANDS.
apply_pose(rig, name_or_spec, frame, weight=1.0) blends (slerp) from the pose the rig has
at that frame (evaluated from its keys, or the current pose if not animated).
Pitfalls: blending two very different poses with weight 0.5 can pass limbs through the
body (it is a rotation blend, not a path planner); key an intermediate pose instead.
Keys use Bezier interpolation; for snappy moves set `interpolation='LINEAR'`/'CONSTANT'
via the `interp` argument.

Lines ("web")
-------------
add_web(rig, hand, anchor, frame_on, frame_off, name, slack=0.0, attach='grip')
creates a geometry-nodes line (default radius 6 mm, taut pale gold-bronze cable) between an empty that
is bone-parented to grip/nozzle and an empty at `anchor` (world space), with a small
gold kite-shaped grapnel at the anchor and a T-handle (along the grip bone's X axis) at
the hand. It follows the hand at every (sub)frame, so it is correct
under motion blur and when HERO_RIG itself is animated. Visibility (render + viewport)
is keyed on at frame_on and off at frame_off (CONSTANT keys). slack (0..1) sags the line
(slack * 6% of its length at mid-span, a smooth catenary-like sag). key_slack(web, frame, value) animates it.

Render detail / cost
--------------------
set_detail(rig, level): HERO_body render subdivision. hero.blend ships with 1 (about 250k
faces in total, right for everything but the s2 close-up); use 2 for s2 (about 690k).
All hero materials have emission_sampling = 'NONE' (the amber glow is seen directly
and in bounces but is not sampled as a light), which keeps the light tree small.

Motion blur
-----------
Everything is deformation driven by the armature, which Cycles samples per motion step.
Use scene.render.use_motion_blur = True, motion_blur_shutter 0.5; set
`HERO_body` object's cycles.motion_steps = 3 (already stored in hero.blend) for curved
blur on fast limbs. Lines use the same deformation blur (geometry nodes are re-evaluated
per step).
"""
import math
import os
import sys

try:
    import bpy
    from mathutils import Matrix, Quaternion, Vector, Euler
except ImportError:  # allows reading POSES outside Blender
    bpy = None

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.normpath(os.path.join(HERE, '..', 'out', 'hero.blend'))
HEIGHT = 1.78
GRIP = {
    'bone': {'L': 'grip.L', 'R': 'grip.R'},
    'nozzle_bone': {'L': 'nozzle.L', 'R': 'nozzle.R'},
    'note': 'Line attaches at the head of bone grip.<side> (centre of the closed fist, '
            'child of wrist.<side>). For a just-fired line use attach="nozzle".',
}

# ---------------------------------------------------------------------------------
# pose data
# vectors are (out, forward, up) in the chest frame (arms) or pelvis frame (legs);
# 'out' means toward the limb's own side, so the same numbers on L and R are symmetric.
# angles in degrees.

HANDS = {
    # per finger: (mcp, pip, dip) curl, + spread; thumb: (t1x, t1z, t2, t3)
    'relaxed': dict(f=[(18, 25, 15), (22, 30, 18), (26, 34, 20), (30, 38, 22)], spread=0.3, thumb=(8, 10, 10, 10)),
    'fist': dict(f=[(80, 95, 60), (85, 95, 60), (88, 95, 60), (90, 95, 60)], spread=-0.2, thumb=(25, 35, 30, 40)),
    'grip': dict(f=[(70, 85, 50), (75, 85, 50), (78, 85, 50), (80, 85, 50)], spread=-0.2, thumb=(30, 30, 25, 30)),
    'spread': dict(f=[(-8, 4, 2), (-6, 4, 2), (-6, 4, 2), (-4, 4, 2)], spread=1.6, thumb=(-10, -25, 0, 0)),
    'flat': dict(f=[(-3, 3, 2), (0, 3, 2), (2, 4, 2), (4, 5, 2)], spread=0.5, thumb=(0, -10, 5, 5)),
    'plant': dict(f=[(-20, 15, 10), (-18, 15, 10), (-16, 15, 10), (-14, 15, 10)], spread=1.0, thumb=(-5, -25, 5, 5)),
    'claw': dict(f=[(30, 55, 40), (32, 55, 40), (34, 58, 40), (36, 60, 40)], spread=1.0, thumb=(10, 0, 20, 25)),
    'point': dict(f=[(0, 5, 3), (75, 90, 55), (80, 90, 55), (85, 90, 55)], spread=0.0, thumb=(25, 25, 25, 30)),
    'expressive': dict(f=[(5, 12, 6), (14, 20, 10), (22, 28, 14), (30, 34, 18)], spread=1.1, thumb=(-5, -15, 8, 8)),
    'blade': dict(f=[(0, 2, 1), (0, 2, 1), (1, 2, 1), (2, 3, 1)], spread=-0.35, thumb=(20, 30, 15, 10)),
    'open': dict(f=[(-6, 6, 3), (2, 10, 5), (8, 16, 8), (14, 22, 12)], spread=1.5, thumb=(-12, -28, 4, 4)),
}

POSES = {
    'rest': dict(rest=True),
    'stand': dict(
        spine=(2, 0, 0), neck=(-2, 0, 0), head=(0, 0, 0),
        arm_L=dict(up=(0.18, 0.02, -1), fore=(0.12, 0.25, -1), pron=10, wrist=(0, 0), hand='relaxed'),
        arm_R=dict(up=(0.18, 0.02, -1), fore=(0.12, 0.25, -1), pron=10, wrist=(0, 0), hand='relaxed'),
        leg_L=dict(thigh=(0.06, 0, -1), shin=(0.04, -0.02, -1), foot=(0, 0)),
        leg_R=dict(thigh=(0.06, 0, -1), shin=(0.04, -0.02, -1), foot=(0, 0)),
        ground=True),
    # deep gargoyle squat: on the balls of the feet, knees wide, left hand planted between
    # the feet, right forearm draped over the right knee, head tilted down to the street
    # falconer's kneel on the ledge: right knee down, left foot forward and flat, torso
    # long and upright, left forearm across the raised left knee, right hand resting on
    # the ornament (a point 0.45 m up, 0.30 m ahead and 0.24 m to his right), head turned
    # out over the street to his right and slightly down
    'perch_crouch': dict(
        root_loc=(0, 0.05, -0.45), root_rot=(4, 0, 6), spine=(8, 0, 6), neck=(4, -6, 0),
        head_aim=(-0.55, -0.80, -0.22),
        clav_L=(4, 4), clav_R=(0, 2),
        leg_L=dict(ik=(0.12, -0.28, 0.105), pole=(0.25, 1.0, 0.2), foot_aim=(0.06, 1.0, -0.15), toes=0),
        leg_R=dict(ik=(0.11, 0.34, 0.095), pole=(0.05, 1.0, -0.6), foot_aim=(0.0, -0.15, -1.0), toes=55),
        arm_L=dict(ik=('lowerleg01', (-0.11, -0.05, 0.03)), pole=(1.0, 0.2, -0.4), pron=40,
                   hand_aim=((-0.8, -0.3, -0.4), (0.0, 0.0, 1.0)), hand='relaxed'),
        arm_R=dict(ik=(0.24, -0.30, 0.46), pole=(1.0, 0.3, -0.5), pron=30, wrist=(10, 0), hand='relaxed'),
        ground=True),
    'perch_look_up': dict(
        base='perch_crouch',
        spine=(2, 0, 5), neck=(-6, -4, 0), head_aim=(-0.32, -0.94, 0.12)),
    # launch off the ledge: body pitched forward, arms reaching, push-off leg extended
    'leap': dict(
        root_rot=(30, 0, 4), spine=(-12, 0, 6), neck=(-14, 0, 0), head=(-8, 4, 0),
        clav_L=(8, 8), clav_R=(8, 8),
        arm_L=dict(up=(0.25, 0.85, 0.5), fore=(0.15, 0.95, 0.35), pron=30, wrist=(15, 0), hand='relaxed'),
        arm_R=dict(up=(0.3, 0.8, 0.25), fore=(0.2, 0.95, 0.15), pron=30, wrist=(10, 0), hand='relaxed'),
        leg_L=dict(thigh=(0.08, 0.75, -0.45), shin=(0.04, -0.4, -1), foot=(-30, 0), toes=-10),
        leg_R=dict(thigh=(0.05, -0.45, -1), shin=(0.03, -0.75, -0.6), foot=(-50, 0), toes=-25)),
    # head first, arms swept back along the body, legs together, toes pointed
    'dive': dict(
        root_rot=(150, 0, 0), spine=(-10, 0, 0), neck=(-22, 0, 0), head=(-14, 0, 0),
        clav_L=(10, -14), clav_R=(10, -14),
        arm_L=dict(up=(0.32, -0.5, -1), fore=(0.15, -0.35, -1), pole=(0.3, 1, 0), pron=-40, wrist=(-20, 0), hand='flat'),
        arm_R=dict(up=(0.32, -0.5, -1), fore=(0.15, -0.35, -1), pole=(0.3, 1, 0), pron=-40, wrist=(-20, 0), hand='flat'),
        leg_L=dict(thigh=(0.0, -0.08, -1), shin=(-0.02, -0.12, -1), foot=(-55, 0), toes=-25),
        leg_R=dict(thigh=(0.01, -0.03, -1), shin=(-0.01, -0.25, -1), foot=(-52, 0), toes=-25)),
    'dive_reach': dict(
        root_rot=(155, 0, 8), spine=(-10, 4, 8), neck=(-14, 0, 0), head=(-18, 6, 0),
        clav_R=(20, 6),
        arm_R=dict(up=(0.15, 0.3, 1), fore=(0.05, 0.4, 1), pron=40, wrist=(35, 0), hand='spread'),
        arm_L=dict(up=(0.45, -0.5, -0.9), fore=(0.3, -0.25, -1), pron=-30, wrist=(-15, 0), hand='flat'),
        leg_L=dict(thigh=(0.06, -0.15, -1), shin=(0.04, -0.6, -1), foot=(-55, 0), toes=-20),
        leg_R=dict(thigh=(0.04, 0.2, -1), shin=(0.02, -0.25, -1), foot=(-50, 0), toes=-20)),
    # firing arm thrown out straight, blade hand along the forearm
    'shoot_R': dict(
        root_rot=(4, 0, 0), spine=(2, -6, 24), neck=(0, 14, 0), head_aim=(-0.45, -0.85, 0.28),
        clav_R=(6, 14),
        arm_R=dict(up=(0.35, 0.88, 0.32), fore=(0.33, 0.88, 0.34), pole=(-0.3, 0.2, -1), pron=-85, wrist=(0, 0), hand='blade'),
        arm_L=dict(up=(0.6, -0.45, -0.45), fore=(0.3, 0.2, -0.9), pron=10, wrist=(0, 0), hand='relaxed'),
        leg_L=dict(thigh=(0.1, 0.6, -0.6), shin=(0.06, -0.55, -1), foot=(-30, 0), toes=-12),
        leg_R=dict(thigh=(0.06, -0.3, -1), shin=(0.04, -0.85, -0.55), foot=(-52, 0), toes=-25)),
    # hanging from the right hand, body arced, legs trailing and bent
    'swing_R': dict(
        root_rot=(-22, 0, -8), spine=(-30, 8, -12), neck=(-6, -6, 0), head_aim=(0.12, -0.96, -0.05),
        clav_R=(30, 2), clav_L=(4, -18),
        arm_R=dict(up=(0.12, 0.10, 1), fore=(0.08, 0.06, 1), pole=(0.2, -1, 0), pron=60, wrist=(-12, 0), hand='fist'),
        arm_L=dict(up=(0.55, -0.75, -0.3), fore=(0.35, -0.92, -0.05), pron=-20, wrist=(-20, 8), hand='relaxed'),
        leg_L=dict(thigh=(0.10, -0.22, -1), shin=(0.05, -0.85, -0.55), foot=(-48, 0), toes=-20),
        leg_R=dict(thigh=(0.06, -0.62, -0.8), shin=(0.03, -0.98, -0.2), foot=(-58, 0), toes=-25)),
    'swing_tuck': dict(
        root_rot=(-20, 0, -5), spine=(26, 4, -6), neck=(10, 0, 0), head=(-6, -6, 0),
        clav_R=(30, 0),
        arm_R=dict(up=(0.1, 0.12, 1), fore=(0.05, 0.1, 1), pole=(0.2, -1, 0), pron=60, wrist=(-10, 0), hand='fist'),
        arm_L=dict(up=(0.45, 0.6, -0.35), fore=(0.1, 0.9, 0.2), pron=40, wrist=(10, 0), hand='fist'),
        leg_L=dict(thigh=(0.22, 1, 0.55), shin=(0.08, -0.25, -1), foot=(-35, 0), toes=-15),
        leg_R=dict(thigh=(0.18, 1, 0.25), shin=(0.04, -0.45, -1), foot=(-40, 0), toes=-15)),
    # full hollow-back arch after letting go, arms wide and back, knees bent back
    'release_arch': dict(
        root_rot=(-18, 0, 0), spine=(-62, 0, 0), neck=(-24, 0, 0), head=(-26, 0, 0),
        clav_L=(18, -16), clav_R=(18, -16),
        arm_L=dict(up=(1, -0.35, 0.55), fore=(0.8, -0.55, 0.45), pron=-30, wrist=(-15, 0), hand='relaxed'),
        arm_R=dict(up=(1, -0.3, 0.6), fore=(0.8, -0.5, 0.5), pron=-30, wrist=(-15, 0), hand='relaxed'),
        leg_L=dict(thigh=(0.12, -0.32, -1), shin=(0.06, -0.95, -0.45), foot=(-55, 0), toes=-25),
        leg_R=dict(thigh=(0.15, -0.2, -1), shin=(0.08, -1.0, -0.2), foot=(-58, 0), toes=-25)),
    # tight tuck in the flip: hands on the shins, chin to chest
    'flip_tuck': dict(
        root_rot=(40, 0, 0), spine=(50, 0, 0), neck=(28, 0, 0), head=(24, 0, 0),
        clav_L=(4, 16), clav_R=(4, 16),
        leg_L=dict(thigh=(0.14, 1, 0.5), shin=(0.04, -0.25, -1), foot=(-45, 0), toes=-20),
        leg_R=dict(thigh=(0.12, 1, 0.47), shin=(0.04, -0.2, -1), foot=(-45, 0), toes=-20),
        arm_L=dict(ik=('lowerleg01', (0.02, -0.07, -0.14)), pole=(1, 0.3, -0.3), pron=50, wrist=(0, 0), hand='fist'),
        arm_R=dict(ik=('lowerleg01', (0.02, -0.07, -0.14)), pole=(1, 0.3, -0.3), pron=50, wrist=(0, 0), hand='fist')),
    # aerialist's layout at the top of the arc: long open body, legs extended and slightly
    # split, chest lifted, right arm reaching along the travel direction (-Y), left arm
    # swept back; no tucked knee
    'apex_classic': dict(
        root_rot=(-12, 0, 4), spine=(-16, -4, 10), neck=(-6, 6, 0), head_aim=(-0.2, -0.92, 0.35),
        clav_R=(16, 12), clav_L=(6, -14),
        arm_R=dict(up=(0.2, 0.85, 0.5), fore=(0.18, 0.85, 0.52), pole=(-0.3, 0.2, -1), pron=-60, wrist=(0, 0), hand='blade'),
        arm_L=dict(up=(0.55, -0.78, -0.15), fore=(0.45, -0.88, 0.05), pron=-30, wrist=(-20, 5), hand='relaxed'),
        leg_L=dict(thigh=(0.08, 0.12, -1), shin=(0.05, 0.02, -1), foot=(-58, 0), toes=-25),
        leg_R=dict(thigh=(0.06, -0.32, -1), shin=(0.04, -0.4, -1), foot=(-60, 0), toes=-28)),
    # skydiver arch: belly down, hips lowest, arms and legs up and open
    'freefall_spread': dict(
        root_rot=(82, 0, 0), spine=(-26, 0, 0), neck=(-28, 0, 0), head=(-18, 0, 0),
        clav_L=(10, -4), clav_R=(10, -4),
        arm_L=dict(up=(1, -0.15, 0.45), fore=(0.55, -0.3, 0.8), pole=(0, 1, 0.2), pron=-40, wrist=(-15, 0), hand='relaxed'),
        arm_R=dict(up=(1, -0.15, 0.45), fore=(0.55, -0.3, 0.8), pole=(0, 1, 0.2), pron=-40, wrist=(-15, 0), hand='relaxed'),
        leg_L=dict(thigh=(0.38, -0.32, -1), shin=(0.18, -0.95, -0.45), foot=(-50, 0), toes=-22),
        leg_R=dict(thigh=(0.38, -0.32, -1), shin=(0.18, -0.95, -0.45), foot=(-50, 0), toes=-22)),
}


def mirror_spec(spec):
    """Left/right mirror of a pose spec (swap limbs, negate yaw/roll-type angles)."""
    out = {}
    for k, v in spec.items():
        if k.endswith('_L'):
            out[k[:-2] + '_R'] = v
        elif k.endswith('_R'):
            out[k[:-2] + '_L'] = v
        elif k in ('spine', 'neck', 'head'):
            out[k] = (v[0], -v[1], -v[2])
        elif k == 'root_rot':
            out[k] = (v[0], -v[1], -v[2])
        elif k == 'root_loc':
            out[k] = (-v[0], v[1], v[2])
        elif k == 'base':
            out[k] = v[:-2] + ('_L' if v.endswith('_R') else '_R') if v.endswith(('_L', '_R')) else v
        else:
            out[k] = v
    return out


POSES['swing_L'] = mirror_spec(POSES['swing_R'])
POSES['shoot_L'] = mirror_spec(POSES['shoot_R'])


def _spec(name_or_spec):
    spec = POSES[name_or_spec] if isinstance(name_or_spec, str) else name_or_spec
    if 'base' in spec:
        base = dict(_spec(spec['base']))
        base.update({k: v for k, v in spec.items() if k != 'base'})
        return base
    return spec


# ---------------------------------------------------------------------------------
# solver

SPINE = [('spine05', 0.16), ('spine04', 0.18), ('spine03', 0.2), ('spine02', 0.24), ('spine01', 0.22)]
NECK = [('neck01', 0.3), ('neck02', 0.35), ('neck03', 0.35)]


def _side_vec(v, side):
    o, f, u = v
    return Vector(((o if side == 'L' else -o), -f, u)).normalized()


def _mirror_q(q, side):
    return q if side == 'L' else Quaternion((q.w, q.x, -q.y, -q.z))


def _euler_q(x, y, z):
    return Euler((math.radians(x), math.radians(y), math.radians(z)), 'XYZ').to_quaternion()


def _frame(y, h):
    y = y.normalized()
    h = (h - y * h.dot(y)).normalized()
    z = h.cross(y)
    return Matrix((h, y, z)).transposed()  # columns: x=h, y, z


def _swing_twist(q, axis=Vector((0, 1, 0))):
    p = Vector((q.x, q.y, q.z))
    proj = axis * p.dot(axis)
    tw = Quaternion((q.w, proj.x, proj.y, proj.z))
    if tw.magnitude < 1e-9:
        tw = Quaternion()
    tw.normalize()
    sw = q @ tw.inverted()
    return sw, tw


def _qpow(q, t):
    return Quaternion().slerp(q, t)


class _Solver:
    def __init__(self, rig):
        self.rig = rig
        self.bones = rig.data.bones
        self.rest = {b.name: b.matrix_local.copy() for b in self.bones}
        self.basis = {b.name: [Vector(), Quaternion()] for b in self.bones}
        self.order = []
        def visit(b):
            self.order.append(b.name)
            for c in b.children:
                visit(c)
        for b in self.bones:
            if b.parent is None:
                visit(b)
        self.pose = {}

    def fk(self):
        P = {}
        for n in self.order:
            b = self.bones[n]
            loc, q = self.basis[n]
            M = Matrix.Translation(loc) @ q.to_matrix().to_4x4()
            if b.parent:
                pn = b.parent.name
                P[n] = P[pn] @ self.rest[pn].inverted() @ self.rest[n] @ M
            else:
                P[n] = self.rest[n] @ M
        self.pose = P
        return P

    def unrot(self, n):
        b = self.bones[n]
        pn = b.parent.name
        return (self.pose[pn] @ self.rest[pn].inverted() @ self.rest[n]).to_3x3()

    def frame_rot(self, n):
        """rotation that maps rest armature-space directions to posed ones for bone n"""
        return (self.pose[n] @ self.rest[n].inverted()).to_3x3()

    # -- limbs
    def limb(self, side, a1, a2, b1, b2, U, F, pole, hinge_rest, pron=0.0, pron_split=(0.4, 0.6), end='wrist'):
        s = side
        a1n, a2n, b1n, b2n = a1 + '.' + s, a2 + '.' + s, b1 + '.' + s, b2 + '.' + s
        en = end + '.' + s
        self.fk()
        A = self.unrot(a1n)
        R1i = self.rest[a1n].to_3x3().inverted()
        h_loc = R1i @ hinge_rest
        seg_up = (self.rest[b1n].translation - self.rest[a1n].translation).normalized()
        seg_lo = (self.rest[en].translation - self.rest[b1n].translation).normalized()
        y0 = A @ (R1i @ seg_up); h0 = A @ h_loc
        ang = U.angle(F) if U.length and F.length else 0.0
        Hc = U.cross(F)
        Hp = pole.cross(U) if pole is not None else None
        if Hp is None or Hp.length < 1e-6:
            Hp = h0 - U * h0.dot(U)
        Hp.normalize()
        if Hc.length > 1e-6:
            Hc.normalize()
            t = min(1.0, max(0.0, (math.degrees(ang) - 4.0) / 10.0))
            H = (Hc * t + Hp * (1 - t)).normalized()
        else:
            H = Hp
        Q = _frame(U, H) @ _frame(y0, h0).transposed()
        basis = (A.inverted() @ Q @ A).to_quaternion()
        if a1.startswith('upperarm'):
            # twist shared by the two (parallel) upper-arm bones: no candy-wrapper
            sw, tw = _swing_twist(basis)
            self.basis[a1n][1] = sw @ _qpow(tw, 0.5)
            self.basis[a2n][1] = _qpow(tw, 0.5)
        else:
            self.basis[a1n][1] = basis
            self.basis[a2n][1] = Quaternion()
        # hinge
        # lower segment: minimal rotation of the (hinge-bent) rest lower segment onto F
        self.fk()
        Ab = self.unrot(b1n)
        cur = Ab @ (self.rest[b1n].to_3x3().inverted() @ seg_lo)
        Qb = cur.rotation_difference(F.normalized()).to_matrix()
        qh = (Ab.inverted() @ Qb @ Ab).to_quaternion()
        tw1 = Quaternion(Vector((0, 1, 0)), math.radians(pron) * pron_split[0])
        tw2 = Quaternion(Vector((0, 1, 0)), math.radians(pron) * pron_split[1])
        self.basis[b1n][1] = qh @ tw1
        self.basis[b2n][1] = tw2

    def ik_dirs(self, s, a1, b1, end, target, pole):
        """directions U, F so that `end` reaches target (armature space)."""
        self.fk()
        S = self.pose[a1 + '.' + s].translation
        L1 = (self.rest[b1 + '.' + s].translation - self.rest[a1 + '.' + s].translation).length
        L2 = (self.rest[end + '.' + s].translation - self.rest[b1 + '.' + s].translation).length
        D = target - S
        d = min(D.length, (L1 + L2) * 0.999)
        D.normalize()
        ca = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)
        a = math.acos(max(-1, min(1, ca)))
        pp = pole - D * pole.dot(D)
        if pp.length < 1e-6:
            pp = Vector((0, 0, 1)) - D * D.z
        pp.normalize()
        E = S + L1 * (math.cos(a) * D + math.sin(a) * pp)
        P = S + D * d
        return (E - S).normalized(), (P - E).normalized()

    def aim(self, n, y_dir, z_hint=None):
        """rotate bone n (basis) so its Y axis points along y_dir (rig space), Z toward z_hint"""
        self.fk()
        A = self.unrot(n)
        y0 = A @ Vector((0, 1, 0)); x0 = A @ Vector((1, 0, 0))
        y1 = Vector(y_dir).normalized()
        if z_hint is not None:
            x1 = y1.cross(Vector(z_hint))
            if x1.length < 1e-6:
                x1 = x0
            Q = _frame(y1, x1.normalized()) @ _frame(y0, x0).transposed()
        else:
            Q = y0.rotation_difference(y1).to_matrix()
        self.basis[n][1] = (A.inverted() @ Q @ A).to_quaternion()

    def euler_bone(self, n, x, y, z, side='L'):
        self.basis[n][1] = _mirror_q(_euler_q(x, y, z), side)

    def hand(self, s, preset):
        h = HANDS[preset] if isinstance(preset, str) else preset
        spread = h.get('spread', 0.0)
        for i, (c1, c2, c3) in enumerate(h['f']):
            fn = i + 2
            sp = (1.5 - i) * 6.0 * spread  # index spreads toward thumb, pinky away
            self.euler_bone(f'finger{fn}-1.{s}', -c1, 0, sp, s)
            self.euler_bone(f'finger{fn}-2.{s}', -c2, 0, 0, s)
            self.euler_bone(f'finger{fn}-3.{s}', -c3, 0, 0, s)
            if i < 4 and f'metacarpal{i + 1}.{s}' in self.basis:
                # cupping of the palm for curled hands
                cup = 0.12 * c1 * (i - 1.5) / 1.5
                self.euler_bone(f'metacarpal{i + 1}.{s}', 0, cup, 0, s)
        t1x, t1z, t2, t3 = h['thumb']
        self.euler_bone(f'finger1-1.{s}', -t1x, 0, t1z, s)
        self.euler_bone(f'finger1-2.{s}', -t2, 0, 0, s)
        self.euler_bone(f'finger1-3.{s}', -t3, 0, 0, s)


ARM_HINGE = {}


def _arm_hinge(sv, s):
    ya = (sv.rest[f'lowerarm01.{s}'].translation - sv.rest[f'upperarm01.{s}'].translation).normalized()
    yb = (sv.rest[f'wrist.{s}'].translation - sv.rest[f'lowerarm01.{s}'].translation).normalized()
    return ya.cross(yb).normalized()


def _resolve(rig, name_or_spec):
    """-> {bone: Quaternion}, root location (Vector, bone-local)"""
    spec = _spec(name_or_spec)
    sv = _Solver(rig)
    if spec.get('rest'):
        return {n: Quaternion() for n in sv.basis}, Vector()
    # root orientation (rig space euler about the hips)
    R0 = sv.rest['root'].to_3x3()
    rr = spec.get('root_rot', (0, 0, 0))
    Qw = Euler([math.radians(a) for a in rr], 'XYZ').to_matrix()
    sv.basis['root'][1] = (R0.inverted() @ Qw @ R0).to_quaternion()
    rl = Vector(spec.get('root_loc', (0, 0, 0)))
    sv.basis['root'][0] = R0.inverted() @ rl
    f, sd, tw = spec.get('spine', (0, 0, 0))
    for n, w in SPINE:
        sv.euler_bone(n, f * w, tw * w, -sd * w)
    p, y, r = spec.get('neck', (0, 0, 0))
    for n, w in NECK:
        sv.euler_bone(n, p * w, y * w, -r * w)
    p, y, r = spec.get('head', (0, 0, 0))
    sv.euler_bone('head', p, y, -r)
    def target(t, s):
        if isinstance(t[0], str):
            sv.fk()
            base = sv.pose[t[0] + '.' + s].translation
            o = Vector(t[1]); o.x = o.x if s == 'L' else -o.x
            return base + o
        v = Vector(t); v.x = v.x if s == 'L' else -v.x
        return v

    def rigvec(v, s):
        return _side_vec(v, s)

    # legs first (arms may reference knees)
    for s in 'LR':
        leg = spec.get('leg_' + s)
        if not leg:
            continue
        sv.fk()
        pelvis = sv.frame_rot('root')
        pole = pelvis @ _side_vec(leg.get('pole', (0.1, 1, 0)), s)
        if 'ik' in leg:
            U, F = sv.ik_dirs(s, 'upperleg01', 'lowerleg01', 'foot', target(leg['ik'], s), pole)
        else:
            U = pelvis @ _side_vec(leg['thigh'], s)
            F = pelvis @ _side_vec(leg['shin'], s)
        sv.limb(s, 'upperleg01', 'upperleg02', 'lowerleg01', 'lowerleg02', U, F, pole,
                Vector((1, 0, 0)), pron=leg.get('twist', 0) * (1 if s == 'L' else -1), pron_split=(0.5, 0.5),
                end='foot')
        if 'foot_aim' in leg:
            sv.aim('foot.' + s, rigvec(leg['foot_aim'], s), Vector((0, 0, 1)))
        else:
            fx, fz = leg.get('foot', (0, 0))
            sv.euler_bone('foot.' + s, fx, 0, fz, s)
        sv.euler_bone('toes.' + s, leg.get('toes', 0), 0, 0, s)
    for s in 'LR':
        sv.fk()
        chest = sv.frame_rot('spine01')
        arm = spec.get('arm_' + s)
        el, pr = spec.get('clav_' + s, (0, 0))
        if arm and 'ik' not in arm:
            el += 0.22 * max(0.0, math.degrees(math.asin(max(-1, min(1, _side_vec(arm['up'], s).z)))))
        sv.euler_bone('clavicle.' + s, pr, 0, el, s)
        if not arm:
            continue
        sv.fk()
        chest = sv.frame_rot('spine01')
        pole = chest @ _side_vec(arm.get('pole', (0.3, 0.6, -0.3)), s)
        if 'ik' in arm:
            U, F = sv.ik_dirs(s, 'upperarm01', 'lowerarm01', 'wrist', target(arm['ik'], s), pole)
        else:
            U = chest @ _side_vec(arm['up'], s)
            F = chest @ _side_vec(arm['fore'], s)
        sv.limb(s, 'upperarm01', 'upperarm02', 'lowerarm01', 'lowerarm02', U, F, pole,
                _arm_hinge(sv, s), pron=arm.get('pron', 0) * (1 if s == 'L' else -1))
        if 'hand_aim' in arm:
            ha = arm['hand_aim']
            sv.aim('wrist.' + s, rigvec(ha[0], s), rigvec(ha[1], s))
        else:
            we, wd = arm.get('wrist', (0, 0))
            sv.euler_bone('wrist.' + s, we, 0, wd, s)
        sv.hand(s, arm.get('hand', 'relaxed'))
    if 'head_aim' in spec:
        f = Vector(spec['head_aim']).normalized()
        up = Vector((0, 0, 1)); y = (up - f * up.dot(f)).normalized()
        sv.aim('head', y, f)
    if spec.get('ground'):
        sv.fk()
        zmin = min(_contact_points(sv))
        R0i = R0.inverted()
        sv.basis['root'][0] = sv.basis['root'][0] + R0i @ Vector((0, 0, -zmin))
    return {n: v[1].normalized() for n, v in sv.basis.items()}, sv.basis['root'][0].copy()


def _contact_points(sv):
    cs = sv.rig.get('contacts')
    if cs:
        tok = cs.split()
        out = []
        for i in range(0, len(tok), 4):
            M = sv.pose[tok[i]]
            out.append((M @ Vector((float(tok[i + 1]), float(tok[i + 2]), float(tok[i + 3])))).z)
        return out
    pts = []
    for s in 'LR':
        for n, off in ((f'foot.{s}', (0, -0.075, 0)), (f'foot.{s}', (0, 0.055, -0.065)),
                       (f'toes.{s}', (0, 0.05, -0.012)), (f'toes.{s}', (0, 0.0, -0.02))):
            M = sv.pose[n]
            pts.append((M @ Vector(off)).z)
    return pts


# ---------------------------------------------------------------------------------
# keys

def _channelbag(rig, create=False):
    ad = rig.animation_data
    if ad is None or ad.action is None:
        return None
    try:
        from bpy_extras import anim_utils
        return anim_utils.animdata_get_channelbag_for_assigned_slot(ad)
    except Exception:
        return None


def _fcurves(rig):
    cb = _channelbag(rig)
    if cb is not None:
        return cb.fcurves
    act = rig.animation_data.action if rig.animation_data else None
    return getattr(act, 'fcurves', []) if act else []


def _current(rig, frame):
    """pose (quats, root loc) the rig has at `frame` from its keys (or current values)."""
    cur = {pb.name: pb.rotation_quaternion.copy() for pb in rig.pose.bones}
    loc = rig.pose.bones['root'].location.copy()
    for fc in _fcurves(rig):
        dp = fc.data_path
        if not dp.startswith('pose.bones["'):
            continue
        bn = dp.split('"')[1]
        if bn not in cur:
            continue
        v = fc.evaluate(frame)
        if dp.endswith('rotation_quaternion'):
            cur[bn][fc.array_index] = v
        elif dp.endswith('location') and bn == 'root':
            loc[fc.array_index] = v
    return cur, loc


def _fix_hemispheres(rig):
    fcs = {}
    for fc in _fcurves(rig):
        if fc.data_path.endswith('rotation_quaternion'):
            fcs.setdefault(fc.data_path, [None] * 4)[fc.array_index] = fc
    for dp, chans in fcs.items():
        if None in chans:
            continue
        n = len(chans[0].keyframe_points)
        if any(len(c.keyframe_points) != n for c in chans):
            continue
        order = sorted(range(n), key=lambda i: chans[0].keyframe_points[i].co.x)
        prev = None
        for i in order:
            q = [c.keyframe_points[i].co.y for c in chans]
            if prev is not None and sum(a * b for a, b in zip(q, prev)) < 0:
                for c in chans:
                    kp = c.keyframe_points[i]
                    kp.co.y = -kp.co.y
                    kp.handle_left.y = -kp.handle_left.y
                    kp.handle_right.y = -kp.handle_right.y
                q = [-v for v in q]
            prev = q
        for c in chans:
            c.update()


def apply_pose(rig, name, frame, weight=1.0, interp=None, bones=None):
    """Key pose `name` (or a spec dict) on rig at frame. weight<1 slerps from the pose the
    rig has at that frame. `bones`: optional iterable restricting which bones are keyed."""
    target, rloc = _resolve(rig, name)
    cur, cloc = _current(rig, frame)
    for pb in rig.pose.bones:
        if pb.name not in target or (bones is not None and pb.name not in bones):
            continue
        if pb.name in ('master',) or pb.name.startswith(('grip', 'nozzle', 'aim')):
            continue
        pb.rotation_mode = 'QUATERNION'
        q = target[pb.name]
        c = cur[pb.name]
        if weight < 1.0:
            q = c.slerp(q, weight)
        if c.dot(q) < 0:
            q = Quaternion((-q.w, -q.x, -q.y, -q.z))
        pb.rotation_quaternion = q
        pb.keyframe_insert('rotation_quaternion', frame=frame, group=pb.name)
    if bones is None or 'root' in bones:
        pb = rig.pose.bones['root']
        pb.location = cloc.lerp(rloc, weight) if weight < 1.0 else rloc
        pb.keyframe_insert('location', frame=frame, group='root')
    _fix_hemispheres(rig)
    if interp:
        for fc in _fcurves(rig):
            for kp in fc.keyframe_points:
                if abs(kp.co.x - frame) < 1e-3:
                    kp.interpolation = interp
    return rig


def pose_now(rig, name, weight=1.0):
    """Set a pose without keying (for stills / tests)."""
    target, rloc = _resolve(rig, name)
    for pb in rig.pose.bones:
        if pb.name in target and pb.name != 'master' and not pb.name.startswith(('grip', 'nozzle', 'aim')):
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = pb.rotation_quaternion.slerp(target[pb.name], weight) if weight < 1 else target[pb.name]
    rig.pose.bones['root'].location = rloc


def set_head_look(rig, frame, yaw=0.0, pitch=0.0, roll=0.0, key=True):
    """Add a head/neck look offset (degrees; yaw + = toward the character's left,
    pitch + = look down) on top of the pose already keyed at `frame`, and key it."""
    cur, _ = _current(rig, frame)
    for n, w in (('neck02', 0.2), ('neck03', 0.3), ('head', 0.5)):
        pb = rig.pose.bones[n]
        pb.rotation_mode = 'QUATERNION'
        q = cur[n] @ _euler_q(pitch * w, yaw * w, -roll * w)
        pb.rotation_quaternion = q
        if key:
            pb.keyframe_insert('rotation_quaternion', frame=frame, group=n)
    if key:
        _fix_hemispheres(rig)


# ---------------------------------------------------------------------------------
# placement helpers

def grip_world(rig, side='R', attach='grip'):
    """World position of the grip (or nozzle) point for the current frame (depsgraph)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = rig.evaluated_get(dg)
    bn = (GRIP['bone'] if attach == 'grip' else GRIP['nozzle_bone'])[side]
    return ev.matrix_world @ ev.pose.bones[bn].head


def _key_obj(ob, frame):
    ob.keyframe_insert('location', frame=frame)
    if ob.rotation_mode == 'QUATERNION':
        ob.keyframe_insert('rotation_quaternion', frame=frame)
    else:
        ob.keyframe_insert('rotation_euler', frame=frame)


def place_rig(rig, frame, hips=(0, 0, 0), forward=(0, -1, 0), up=(0, 0, 1), key=True):
    """Put the hips (rest hip point, 0.98 m above the rig origin) at world `hips`, with the
    character's front along `forward` and head along `up` (in world space)."""
    f = Vector(forward).normalized(); u = Vector(up)
    u = (u - f * u.dot(f)).normalized()
    x = (-f).cross(u)  # character left... rig +X
    M = Matrix((x, -f, u)).transposed()  # rig axes: +X left side, -Y front, +Z up
    hip_local = Vector((0, 0, 0.98))
    rig.rotation_mode = 'QUATERNION'
    rig.rotation_quaternion = M.to_quaternion()
    rig.location = Vector(hips) - M @ hip_local
    if key:
        _key_obj(rig, frame)


def orient_to_line(rig, frame, side, anchor, grip_pos, travel, key=True):
    """Rotate/translate HERO_RIG so that, in its current pose at `frame`, the grip point of
    `side` sits at world `grip_pos`, the shoulder->grip direction points at `anchor`, and the
    character's front faces as close as possible to `travel`."""
    bpy.context.scene.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = rig.evaluated_get(dg)
    g = ev.pose.bones[GRIP['bone'][side]].head.copy()           # rig space
    sh = ev.pose.bones['upperarm01.' + side].head.copy()
    a_local = (g - sh).normalized()
    a_world = (Vector(anchor) - Vector(grip_pos)).normalized()
    front_local = Vector((0, -1, 0))
    t = Vector(travel); t = (t - a_world * t.dot(a_world)).normalized()
    fl = (front_local - a_local * front_local.dot(a_local)).normalized()
    Mw = _frame(a_world, t); Ml = _frame(a_local, fl)
    R = Mw @ Ml.transposed()
    rig.rotation_mode = 'QUATERNION'
    rig.rotation_quaternion = R.to_quaternion()
    rig.location = Vector(grip_pos) - R @ g
    if key:
        _key_obj(rig, frame)


# ---------------------------------------------------------------------------------
# render detail

def set_detail(rig, level=1):
    """Render subdivision of the suit body (HERO_body). 1 = default (film wide/medium
    shots, ~250k faces total), 2 = close-ups (s2), ~690k faces. Viewport stays at 0."""
    for o in rig.children:
        for m in o.modifiers:
            if m.type == 'SUBSURF':
                m.render_levels = int(level)


# ---------------------------------------------------------------------------------
# append

def append_hero(blend_path=DEFAULT, scene=None, link_to=None):
    """Append collection HERO from hero.blend into the scene; returns HERO_RIG."""
    scene = scene or bpy.context.scene
    before = set(bpy.data.objects)
    with bpy.data.libraries.load(blend_path, link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c == 'HERO']
    col = dst.collections[0]
    (link_to or scene.collection).children.link(col)
    rig = None
    for ob in col.all_objects:
        if ob.type == 'ARMATURE' and ob.name.startswith('HERO_RIG'):
            rig = ob
    return rig


# ---------------------------------------------------------------------------------
# web line

def _web_material():
    m = bpy.data.materials.get('HERO_web')
    if m:
        return m
    import hero_materials
    return hero_materials.web_material()


def _web_nodegroup():
    ng = bpy.data.node_groups.get('HERO_web_line')
    if ng:
        return ng
    import hero_web
    return hero_web.make_nodegroup()


def add_web(rig, hand='R', anchor=(0, 0, 0), frame_on=1, frame_off=100, name='HERO_web',
            slack=0.0, attach='grip', collection=None, radius=0.006):
    """Line from the hand to a world-space anchor; see module doc."""
    side = hand
    col = collection or (rig.users_collection[0] if rig.users_collection else bpy.context.scene.collection)
    e1 = bpy.data.objects.new(name + '_hand', None)
    e1.empty_display_size = 0.03
    e1.parent = rig
    e1.parent_type = 'BONE'
    e1.parent_bone = (GRIP['bone'] if attach == 'grip' else GRIP['nozzle_bone'])[side]
    # bone parenting places the child at the bone TAIL; shift back to the head
    bl = rig.data.bones[e1.parent_bone].length
    e1.location = (0, -bl, 0)
    e2 = bpy.data.objects.new(name + '_anchor', None)
    e2.empty_display_size = 0.2
    e2.location = anchor
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    for o in (e1, e2, ob):
        col.objects.link(o)
    mod = ob.modifiers.new('web', 'NODES')
    ng = _web_nodegroup()
    mod.node_group = ng
    ids = {it.name: it.identifier for it in ng.interface.items_tree if getattr(it, 'in_out', '') == 'INPUT'}
    _set_input(mod, ids['Hand'], e1)
    _set_input(mod, ids['Anchor'], e2)
    _set_input(mod, ids['Slack'], float(slack))
    _set_input(mod, ids['Radius'], float(radius))
    _set_input(mod, ids['Material'], _web_material())
    _set_input(mod, ids['Head Material'], bpy.data.materials.get('HERO_gold') or _web_material())
    ob['slack_id'] = ids['Slack']
    ob.cycles.use_motion_blur = True if hasattr(ob, 'cycles') else None
    # visibility
    for o in (ob,):
        for fr, vis in ((frame_on - 1, False), (frame_on, True), (frame_off, False)):
            o.hide_render = not vis
            o.hide_viewport = not vis
            o.keyframe_insert('hide_render', frame=fr)
            o.keyframe_insert('hide_viewport', frame=fr)
        for fc in _obj_fcurves(o):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
    if frame_on - 1 < frame_on:
        pass
    return ob


def _obj_fcurves(ob):
    return list(_fcurves(ob))


def _set_input(mod, ident, value):
    """set a geometry-nodes modifier input (Blender 5.x interface API, 4.x fallback)"""
    try:
        getattr(mod.properties.inputs, ident).value = value
        return getattr(mod.properties.inputs, ident).path_from_id('value')
    except AttributeError:
        mod[ident] = value
        return f'modifiers["{mod.name}"]["{ident}"]'


def key_slack(web, frame, value):
    """Animate the sag of a line made by add_web (0 = taut)."""
    mod = web.modifiers['web']
    path = _set_input(mod, web['slack_id'], float(value))
    web.keyframe_insert(path, frame=frame)
