"""lookkit: small shared helpers for look modules (blender/film/looks/<name>.py).

A look module may import: bpy, mathutils, lighting (blender/common), shot_settings, lookkit.
Everything here is idempotent: calling a look's apply(scene) twice gives the same scene.
"""
import bpy

import lighting

# global frame ranges (inclusive) of the six shots
SHOTS = {'s1': (0, 47), 's2': (48, 95), 's3': (96, 143), 's4': (144, 215), 's5': (216, 263),
         's6': (264, 335)}
REF_FRAMES = [0, 90, 130, 180, 244, 276, 335]
COMP_NAME = 'FILM_comp'


def log(*a):
    print('[look]', *a, flush=True)


# ------------------------------------------------------------------ animation helpers
def fcurves(idb):
    ad = getattr(idb, 'animation_data', None)
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


def _remove_fcurve(idb, fc):
    act = idb.animation_data.action
    try:
        act.fcurves.remove(fc)
        return
    except Exception:
        pass
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                if fc in list(cb.fcurves):
                    cb.fcurves.remove(fc)
                    return


def clear_ctrl_keys():
    """Remove every keyframe on LIGHT_CTRL custom properties (drivers elsewhere stay)."""
    ctrl = lighting.get_ctrl()
    for fc in fcurves(ctrl):
        if fc.data_path.startswith('["'):
            _remove_fcurve(ctrl, fc)


def set_interp(idb, interp='LINEAR'):
    for fc in fcurves(idb):
        for kp in fc.keyframe_points:
            kp.interpolation = interp


def key_light(scene, keys, base_ovr=None, ev_shift=0.0, min_haze=0.00012):
    """Key LIGHT_CTRL over the timeline.
    keys: list of (frame, preset, dusk, exposure_offset[, overrides]) where preset is a
    lighting.PRESETS name. overrides/base_ovr: {prop: value} absolute, or {'prop*': m}
    to multiply the preset's value. Exposure = preset (or dusk) exposure + offset + ev_shift.
    Every key writes every property, so values interpolate linearly between keys; put two
    keys at the ends of a shot to hold a value across it."""
    clear_ctrl_keys()
    ctrl = lighting.get_ctrl()
    for key in keys:
        f, preset, d, ev = key[:4]
        extra = key[4] if len(key) > 4 else {}
        lighting.apply_preset(scene, preset, dusk=d, frame=f)
        ovr = dict(base_ovr or {})
        ovr.update(extra)
        for k, v in ovr.items():
            if k.endswith('*'):
                k = k[:-1]
                ctrl[k] = float(ctrl[k]) * v
            else:
                ctrl[k] = float(v)
            ctrl.keyframe_insert(f'["{k}"]', frame=f)
        ctrl['haze_density'] = max(min_haze, float(ctrl['haze_density']))
        ctrl.keyframe_insert('["haze_density"]', frame=f)
        ctrl['exposure'] = float(ctrl['exposure']) + ev + ev_shift
        ctrl.keyframe_insert('["exposure"]', frame=f)
    set_interp(ctrl, 'LINEAR')
    lighting.touch(scene)


# ------------------------------------------------------------------ material helpers
def _node_name(base, inp):
    return 'LOOK_%s_%s' % (base, inp.replace(' ', '_'))


def scale_input(mat, node, inp, mul):
    """Multiply a Principled input by mul (inserting/updating a LOOK_ math node if linked)."""
    nt = mat.node_tree
    s = node.inputs[inp]
    name = _node_name('mul', inp) + '_' + node.name
    m = nt.nodes.get(name)
    orig_key = 'LOOK_orig_' + inp.replace(' ', '_') + '_' + node.name
    if m is not None:
        m.inputs[1].default_value = mul
        return
    if s.is_linked:
        m = nt.nodes.new('ShaderNodeMath')
        m.name = name
        m.operation = 'MULTIPLY'
        m.inputs[1].default_value = mul
        nt.links.new(s.links[0].from_socket, m.inputs[0])
        nt.links.new(m.outputs[0], s)
    else:
        if orig_key not in mat:
            mat[orig_key] = float(s.default_value)
        s.default_value = mat[orig_key] * mul


def set_input(mat, node, inp, value):
    """Set an unlinked Principled input (remembers the original for idempotency)."""
    s = node.inputs[inp]
    if s.is_linked:
        return
    s.default_value = value


def tint_base(mat, node, rgb):
    """Multiply Base Color by rgb (LOOK_ mix node, idempotent)."""
    nt = mat.node_tree
    s = node.inputs['Base Color']
    name = 'LOOK_tint_' + node.name
    mix = nt.nodes.get(name)
    if mix is None:
        mix = nt.nodes.new('ShaderNodeMix')
        mix.name = name
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1.0
        if s.is_linked:
            nt.links.new(s.links[0].from_socket, mix.inputs['A'])
        else:
            mix.inputs['A'].default_value = s.default_value
        nt.links.new(mix.outputs['Result'], s)
    mix.inputs['B'].default_value = tuple(rgb) + (1.0,)


def principled(mat_name):
    """-> (material, [principled nodes]) or (None, [])"""
    m = bpy.data.materials.get(mat_name)
    if not m or not m.node_tree:
        return None, []
    return m, [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED']


def haze_anisotropy(value):
    for m in bpy.data.materials:
        if m.name.startswith('ATMO_haze') and m.node_tree:
            for n in m.node_tree.nodes:
                if n.type == 'PRINCIPLED_VOLUME':
                    n.inputs['Anisotropy'].default_value = value


# ------------------------------------------------------------------ compositor
def new_compositor(scene):
    """Fresh compositor tree with RenderLayers, Group Output and the DEPTH_OUT file node
    the frame delivery needs. Returns (tree, render_layers_node, group_output_node).
    Insert your chain between rl.outputs['Image'] and out.inputs[0] (use chain())."""
    old = bpy.data.node_groups.get(COMP_NAME)
    if old:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(COMP_NAME, 'CompositorNodeTree')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = ng.nodes.new('CompositorNodeRLayers')
    rl.scene = scene
    rl.location = (-800, 0)
    out = ng.nodes.new('NodeGroupOutput')
    out.location = (900, 0)
    add_depth_out(ng, rl)
    scene.compositing_node_group = ng
    scene.render.use_compositing = True
    scene.render.compositor_device = 'CPU'
    return ng, rl, out


def add_depth_out(ng, rl):
    fo = ng.nodes.get('DEPTH_OUT')
    if fo is None:
        fo = ng.nodes.new('CompositorNodeOutputFile')
        fo.name = 'DEPTH_OUT'
    fo.location = (300, -350)
    fo.format.media_type = 'IMAGE'
    fo.format.file_format = 'OPEN_EXR'
    fo.format.color_depth = '32'
    fo.format.exr_codec = 'ZIP'
    try:
        fo.format.color_mode = 'BW'
    except Exception:
        pass
    fo.directory = '//_depth_tmp/'
    fo.file_name = 'depth_'
    fo.file_output_items.clear()
    fo.file_output_items.new('FLOAT', 'Depth')
    ng.links.new(rl.outputs['Depth'], fo.inputs['Depth'])
    return fo


def chain(ng, src_socket, nodes, dst_socket):
    """Link src -> nodes[0].Image -> ... -> nodes[-1] -> dst."""
    cur = src_socket
    for k, n in enumerate(nodes):
        n.location = (-500 + 180 * k, 150)
        inp = n.inputs.get('Image') or n.inputs[0]
        ng.links.new(cur, inp)
        cur = n.outputs.get('Image') or n.outputs[0]
    ng.links.new(cur, dst_socket)


def glare(ng, name, **kw):
    """Glare node. kw: Type ('Bloom','Streaks','Ghosts','Fog Glow','Simple Star','Sun Beams',
    'Kernel'), Quality, Threshold, Smoothness, Strength, Size, Saturation, Streaks,
    'Streaks Angle', Fade, Iterations, 'Color Modulation', Tint, 'Sun Position'..."""
    n = ng.nodes.new('CompositorNodeGlare')
    n.name = name
    for k, v in kw.items():
        s = n.inputs.get(k)
        if s is None:
            log('glare input missing', k)
            continue
        s.default_value = v
    return n


def cdl(ng, name, offset=(0, 0, 0), power=(1, 1, 1), slope=(1, 1, 1)):
    """Colour Balance (ASC-CDL), scene-linear, before the view transform."""
    n = ng.nodes.new('CompositorNodeColorBalance')
    n.name = name
    n.inputs['Type'].default_value = 'Offset/Power/Slope (ASC-CDL)'
    socks = {}
    for s in n.inputs:
        socks.setdefault((s.name, s.type), s)
    socks[('Offset', 'RGBA')].default_value = tuple(offset) + (1.0,)
    socks[('Power', 'RGBA')].default_value = tuple(power) + (1.0,)
    socks[('Slope', 'RGBA')].default_value = tuple(slope) + (1.0,)
    return n


def color_correction(ng, name, saturation=1.0, contrast=1.0, gamma=1.0, gain=1.0, offset=0.0):
    """Colour Correction node (master values; per-range inputs exist too, see LOOKLAB.md)."""
    n = ng.nodes.new('CompositorNodeColorCorrection')
    n.name = name
    n.inputs['Saturation'].default_value = saturation
    n.inputs['Contrast'].default_value = contrast
    n.inputs['Gamma'].default_value = gamma
    n.inputs['Gain'].default_value = gain
    n.inputs['Offset'].default_value = offset
    return n


def view(scene, look='None', transform='AgX'):
    vs = scene.view_settings
    vs.view_transform = transform
    try:
        vs.look = look
    except TypeError:
        log('unknown look', look)


def remove_look_objects():
    for ob in [o for o in bpy.data.objects if o.name.startswith('LOOK_')]:
        bpy.data.objects.remove(ob, do_unlink=True)
