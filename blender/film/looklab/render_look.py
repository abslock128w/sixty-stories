"""Render look-candidate stills from the look-neutral plate.

    $PY blender/film/looklab/render_look.py --look <name-or-path.py> --out <dir>
        [--frames 0,90,130,180,244,276,335] [--width 960] [--samples N] [--threads 4] [--exr]
    $PY blender/film/looklab/render_look.py --look <name-or-path.py> --comp-only <exr dir> --out <dir>

Opens blender/out/looklab/plate.blend, imports the look module by path (or by name from
blender/film/looks/), calls apply(scene), and renders each frame through the real compositor
to <out>/f_XXXX.png at the requested width (2.39:1). Quality follows the per-shot final
settings in shot_settings.py (samples overridable with --samples).
--exr also writes <out>/exr/f_XXXX.exr: the scene-linear combined pass BEFORE the
compositor (ZIP, half float), so grade/compositor changes can be iterated with --comp-only:
that re-runs only the look's compositor on those EXRs (scene geometry is excluded from the
render, so each frame costs ~1-2 s) and writes PNGs to --out.

The whole run holds an exclusive flock on blender/out/looklab/.render.lock (blocking), so
concurrent callers queue instead of overloading the 4 cores / 15 GB.
"""
import fcntl
import importlib.util
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FILM = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(FILM, '..', '..'))
LOOKLAB = os.path.join(ROOT, 'blender', 'out', 'looklab')
PLATE = os.path.join(LOOKLAB, 'plate.blend')
LOCK = os.path.join(LOOKLAB, '.render.lock')
sys.path.insert(0, FILM)
sys.path.insert(0, os.path.join(FILM, 'looks'))
sys.path.insert(0, os.path.join(ROOT, 'blender', 'common'))

SHOT_RANGES = [('s1', 0, 47), ('s2', 48, 95), ('s3', 96, 143), ('s4', 144, 215), ('s5', 216, 263),
               ('s6', 264, 335)]


def shot_of(i):
    for sid, a, b in SHOT_RANGES:
        if a <= i <= b:
            return sid
    raise ValueError(i)


def parse(argv):
    o = dict(look=None, frames='0,90,130,180,244,276,335', width='960', samples='0', threads='4',
             out=None, exr=False, comp_only=None)
    i = 0
    while i < len(argv):
        k = argv[i][2:].replace('-', '_')
        if k == 'exr':
            o['exr'] = True
            i += 1
            continue
        o[k] = argv[i + 1]
        i += 2
    if not o['look'] or not o['out']:
        raise SystemExit(__doc__)
    return o


def load_look(spec):
    path = spec if spec.endswith('.py') else os.path.join(FILM, 'looks', spec + '.py')
    path = os.path.abspath(path)
    name = 'look_' + os.path.splitext(os.path.basename(path))[0]
    sp = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    return mod, path


def log(*a):
    print('[render_look]', *a, flush=True)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    o = parse(argv)
    os.makedirs(o['out'], exist_ok=True)
    os.makedirs(LOOKLAB, exist_ok=True)
    lf = open(LOCK, 'a+')
    t_wait = time.time()
    fcntl.flock(lf, fcntl.LOCK_EX)
    log('lock acquired after %.0fs' % (time.time() - t_wait))
    try:
        run(o)
    finally:
        fcntl.flock(lf, fcntl.LOCK_UN)
        lf.close()


def run(o):
    import bpy
    import shot_settings as SS
    bpy.ops.wm.open_mainfile(filepath=PLATE)
    scene = bpy.context.scene
    mod, path = load_look(o['look'])
    t = time.time()
    mod.apply(scene)
    log('applied %s in %.1fs' % (path, time.time() - t))
    r = scene.render
    r.compositor_device = 'CPU'
    r.use_compositing = True
    r.threads_mode = 'FIXED'
    r.threads = int(o['threads'])
    W = int(o['width'])
    r.resolution_x = W
    r.resolution_y = int(round(W * 804 / 1920))
    r.resolution_percentage = 100
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_depth = '8'
    r.image_settings.color_mode = 'RGB'
    ng = scene.compositing_node_group
    if ng is not None and ng.nodes.get('DEPTH_OUT'):
        ng.nodes['DEPTH_OUT'].mute = True
    for k, v in SS.CYCLES.items():
        setattr(scene.cycles, k, v)
    rig = bpy.data.objects.get('HERO_RIG')
    subs = [m for ob in (rig.children if rig else []) for m in ob.modifiers if m.type == 'SUBSURF']
    frames = [int(x) for x in o['frames'].split(',') if x.strip()]
    if o['comp_only']:
        return comp_only(o, scene, ng, frames)
    exr_node = None
    if o['exr'] and ng is not None:
        rl = [n for n in ng.nodes if n.type == 'R_LAYERS'][0]
        exr_node = ng.nodes.new('CompositorNodeOutputFile')
        exr_node.name = 'LOOKLAB_EXR'
        exr_node.format.media_type = 'IMAGE'
        exr_node.format.file_format = 'OPEN_EXR'
        exr_node.format.color_depth = '16'
        exr_node.format.exr_codec = 'ZIP'
        exr_node.file_output_items.clear()
        exr_node.file_output_items.new('RGBA', 'Image')
        ng.links.new(rl.outputs['Image'], exr_node.inputs['Image'])
        os.makedirs(os.path.join(o['out'], 'exr'), exist_ok=True)
    for f in frames:
        st = SS.SHOT[shot_of(f)]
        scene.cycles.samples = int(o['samples']) if int(o['samples']) > 0 else st['samples']
        scene.cycles.adaptive_threshold = st['threshold']
        for m in subs:
            m.render_levels = st['subsurf']
        scene.frame_set(f)
        tmpd = None
        if exr_node is not None:
            tmpd = os.path.join(o['out'], 'exr', '_tmp_%d' % f)
            os.makedirs(tmpd, exist_ok=True)
            exr_node.directory = tmpd + os.sep
            exr_node.file_name = 'x'
        fn = os.path.join(o['out'], 'f_%04d.png' % f)
        r.filepath = fn + '.tmp.png'
        t = time.time()
        bpy.ops.render.render(write_still=True)
        os.replace(fn + '.tmp.png', fn)
        if tmpd:
            ex = [x for x in os.listdir(tmpd) if x.endswith('.exr')]
            if ex:
                os.replace(os.path.join(tmpd, ex[0]), os.path.join(o['out'], 'exr', 'f_%04d.exr' % f))
            for x in os.listdir(tmpd):
                os.remove(os.path.join(tmpd, x))
            os.rmdir(tmpd)
        log('f%d %dpx %dspp %.1fs -> %s' % (f, W, scene.cycles.samples, time.time() - t, fn))


def comp_only(o, scene, ng, frames):
    """Re-run the look's compositor on saved scene-linear EXRs (no scene render)."""
    import bpy
    rl = [n for n in ng.nodes if n.type == 'R_LAYERS'][0]
    links = [(l.from_socket.name, l.to_socket) for l in ng.links if l.from_node == rl]
    img_node = ng.nodes.new('CompositorNodeImage')
    img_node.name = 'LOOKLAB_IN'
    for name, to in links:
        if name == 'Image':
            ng.links.new(img_node.outputs['Image'], to)
    ng.nodes.remove(rl)
    # make the actual render nearly free: exclude every collection, 1 sample
    for lc in scene.view_layers[0].layer_collection.children:
        lc.exclude = True
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.render.use_motion_blur = False
    r = scene.render
    for f in frames:
        src = os.path.join(o['comp_only'], 'f_%04d.exr' % f)
        if not os.path.exists(src):
            log('missing', src)
            continue
        im = bpy.data.images.load(src, check_existing=False)
        img_node.image = im
        r.resolution_x, r.resolution_y = im.size[0], im.size[1]
        scene.frame_set(f)
        fn = os.path.join(o['out'], 'f_%04d.png' % f)
        r.filepath = fn + '.tmp.png'
        t = time.time()
        bpy.ops.render.render(write_still=True)
        os.replace(fn + '.tmp.png', fn)
        bpy.data.images.remove(im)
        log('comp-only f%d %.1fs -> %s' % (f, time.time() - t, fn))


if __name__ == '__main__':
    main()
