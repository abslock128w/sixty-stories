"""Look-dev scene helpers for preview renders (not part of hero.blend)."""
import math
import bpy
from mathutils import Vector, Euler

OUT = '/home/user/sixty/blender/out/preview/hero'


def setup_scene(scene=None, samples=48, res=(960, 402), threads=2):
    sc = scene or bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.max_bounces = 6
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = threads
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    sc.render.image_settings.file_format = 'PNG'
    return sc


def world_gradient(sc, strength=1.0, dusk=False, glow_az=180.0):
    """Golden-hour-ish environment: warm low horizon on one side, cool sky above,
    dark ground. Gives the visor something to reflect."""
    w = sc.world or bpy.data.worlds.new('LD_World')
    sc.world = w
    nt = w.node_tree if w.node_tree else None
    if nt is None:
        try:
            w.use_nodes = True
        except Exception:
            pass
        nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    # elevation ramp
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(sep.outputs['Z'], ramp.inputs[0])
    # Generated for world = view direction; Z in -1..1 -> use map range
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = -1.0
    mr.inputs['From Max'].default_value = 1.0
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    nt.links.new(mr.outputs['Result'], ramp.inputs[0])
    el = ramp.color_ramp.elements
    el[0].position = 0.40; el[0].color = (0.035, 0.03, 0.028, 1)
    el[1].position = 0.505; el[1].color = (1.0, 0.55, 0.22, 1)
    e = el.new(0.53); e.color = (0.55, 0.42, 0.36, 1)
    e = el.new(0.70); e.color = (0.18, 0.24, 0.38, 1)
    e = el.new(1.0); e.color = (0.07, 0.11, 0.24, 1)
    # warm glow concentrated toward +Y (the sun side)
    dotn = nt.nodes.new('ShaderNodeVectorMath'); dotn.operation = 'DOT_PRODUCT'
    nt.links.new(tc.outputs['Generated'], dotn.inputs[0])
    ga = math.radians(glow_az)
    dotn.inputs[1].default_value = (math.sin(ga), -math.cos(ga), 0.0)
    sepy = dotn.outputs['Value']
    gl = nt.nodes.new('ShaderNodeMapRange')
    gl.inputs['From Min'].default_value = -0.6
    gl.inputs['From Max'].default_value = 1.0
    gl.inputs['To Min'].default_value = 0.3
    gl.inputs['To Max'].default_value = 1.9
    nt.links.new(sepy, gl.inputs['Value'])
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    nt.links.new(ramp.outputs['Color'], mul.inputs[6])
    comb = nt.nodes.new('ShaderNodeCombineColor')
    for k in range(3):
        nt.links.new(gl.outputs['Result'], comb.inputs[k])
    nt.links.new(comb.outputs[0], mul.inputs[7])
    # fake skyline: blocky silhouettes just above the horizon, a few lit windows
    def m(op, a, b=None):
        n = nt.nodes.new('ShaderNodeMath'); n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]
    az = m('ARCTAN2', sep.outputs['Y'], sep.outputs['X'])
    blk = m('DIVIDE', m('FLOOR', m('MULTIPLY', az, 38.0)), 38.0)
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 7.0
    nz.noise_dimensions = '1D'
    nt.links.new(blk, nz.inputs['W'])
    hgt = m('MULTIPLY', m('POWER', nz.outputs['Fac'], 2.2), 0.20)
    inb = m('MULTIPLY', m('GREATER_THAN', sep.outputs['Z'], -0.002), m('LESS_THAN', sep.outputs['Z'], hgt))
    # windows
    wn = nt.nodes.new('ShaderNodeTexNoise'); wn.inputs['Scale'].default_value = 900.0
    nt.links.new(tc.outputs['Generated'], wn.inputs['Vector'])
    win = m('MULTIPLY', m('GREATER_THAN', wn.outputs['Fac'], 0.80), 1.2)
    sil = nt.nodes.new('ShaderNodeMix'); sil.data_type = 'RGBA'
    nt.links.new(inb, sil.inputs['Factor'])
    nt.links.new(mul.outputs[2], sil.inputs[6])
    wc = nt.nodes.new('ShaderNodeCombineColor')
    nt.links.new(m('ADD', 0.03, m('MULTIPLY', win, 1.0)), wc.inputs[0])
    nt.links.new(m('ADD', 0.028, m('MULTIPLY', win, 0.55)), wc.inputs[1])
    nt.links.new(m('ADD', 0.03, m('MULTIPLY', win, 0.2)), wc.inputs[2])
    nt.links.new(wc.outputs[0], sil.inputs[7])
    nt.links.new(sil.outputs[2], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    nt.links.new(bg.outputs[0], out.inputs[0])
    return w


def add_light(name, kind, loc, rot_deg, energy, color, size=0.3):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == 'AREA':
        ld.size = size
    elif kind == 'SUN':
        ld.angle = math.radians(size)
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    ob.rotation_euler = Euler([math.radians(a) for a in rot_deg])
    bpy.context.scene.collection.objects.link(ob)
    return ob


def aim(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def rim_rig(sc, key_az=160, key_el=8, key_energy=6.0, fill=0.6):
    """Low warm sun behind/beside the subject (sun at +Y, subject faces -Y), cool fill
    from the front, neutral ground plane and dark backdrop."""
    for o in list(sc.collection.objects):
        if o.name.startswith('LD_'):
            bpy.data.objects.remove(o)
    az = math.radians(key_az); el = math.radians(key_el)
    d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    sun = add_light("LD_sun", "SUN", (0, 0, 0), (0, 0, 0), key_energy, (1.0, 0.5, 0.2), size=0.6)
    sun.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    f = add_light('LD_fill', 'AREA', (-2.5, -4.0, 2.4), (0, 0, 0), 250 * fill, (0.78, 0.84, 1.0), size=3.0)
    aim(f, (0, 0, 1.2))
    k2 = add_light('LD_kick', 'AREA', (3.0, 2.5, 2.8), (0, 0, 0), 300, (1.0, 0.7, 0.45), size=1.0)
    aim(k2, (0, 0, 1.3))
    for o in (f, k2):
        o.visible_glossy = False
    # ground
    me = bpy.data.meshes.new('LD_ground')
    s = 30
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new('LD_ground', me)
    m = bpy.data.materials.new('LD_ground_mat')
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (0.11, 0.105, 0.1, 1)
    bsdf.inputs['Roughness'].default_value = 0.8
    me.materials.append(m)
    sc.collection.objects.link(g)
    return sun


def camera(sc, loc, target, lens=85, name='LD_cam', sensor=36, dof=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = sensor
    ob = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(ob)
    ob.location = loc
    aim(ob, target)
    if dof:
        cd.dof.use_dof = True
        cd.dof.focus_distance = (Vector(target) - Vector(loc)).length
        cd.dof.aperture_fstop = dof
    sc.camera = ob
    return ob


def render(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def contact_sheet(paths, out, cols, labels=None, pad=4):
    from PIL import Image, ImageDraw
    ims = [Image.open(p).convert('RGB') for p in paths]
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * w + (cols + 1) * pad, rows * h + (rows + 1) * pad), (10, 10, 10))
    dr = ImageDraw.Draw(sheet)
    for k, im in enumerate(ims):
        r, c = divmod(k, cols)
        x = pad + c * (w + pad); y = pad + r * (h + pad)
        sheet.paste(im, (x, y))
        if labels:
            dr.text((x + 6, y + 4), labels[k], fill=(230, 200, 160))
    sheet.save(out)
    return out


def backdrop(sc, cam, target, dist=7.0, size=30.0, color=(0.018, 0.017, 0.016)):
    """dark card behind the subject (as seen from cam); casts no shadows."""
    from mathutils import Vector
    d = (Vector(target) - cam.location).normalized()
    c = Vector(target) + d * dist
    me = bpy.data.meshes.new('LD_backdrop')
    s = size / 2
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new('LD_backdrop', me)
    ob.location = c
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    m = bpy.data.materials.new('LD_backdrop_mat')
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = 0.9
    me.materials.append(m)
    ob.visible_shadow = False
    ob.visible_glossy = False
    sc.collection.objects.link(ob)
    return ob
