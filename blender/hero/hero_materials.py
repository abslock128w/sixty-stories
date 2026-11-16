"""Self-contained Cycles materials for VESPER (no image textures, no world dependence).

Body patterns read per-vertex attributes stored on the rest mesh (rest, pipe_sd, ...),
so nothing swims when the rig deforms.
"""
import bpy

AMBER = (0.80, 0.28, 0.03)
GRAPHITE = (0.054, 0.054, 0.055)
CHARCOAL = (0.040, 0.040, 0.041)
NEARBLACK = (0.0105, 0.0105, 0.011)
PIPE_EMIT = 0.75


class NB:
    """tiny node-building helper"""
    def __init__(self, mat):
        self.m = mat
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.x = 0

    def n(self, kind, **kw):
        node = self.nt.nodes.new(kind)
        for k, v in kw.items():
            if k == 'op':
                node.operation = v
            elif k == 'blend':
                node.blend_type = v
            elif k == 'dtype':
                node.data_type = v
            else:
                setattr(node, k, v)
        node.location = (self.x, 0)
        self.x += 40
        return node

    def link(self, a, b):
        self.nt.links.new(a, b)

    def val(self, v):
        if isinstance(v, (int, float)):
            node = self.n('ShaderNodeValue'); node.outputs[0].default_value = v
            return node.outputs[0]
        return v

    def math(self, op, a, b=None, c=None, clamp=False):
        node = self.n('ShaderNodeMath', op=op)
        node.use_clamp = clamp
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                node.inputs[i].default_value = v
            else:
                self.link(v, node.inputs[i])
        return node.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        node = self.n('ShaderNodeVectorMath', op=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (tuple, list)):
                node.inputs[i].default_value = v
            else:
                self.link(v, node.inputs[i])
        if scale is not None:
            if isinstance(scale, (int, float)):
                node.inputs['Scale'].default_value = scale
            else:
                self.link(scale, node.inputs['Scale'])
        return node.outputs['Value'] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else node.outputs['Vector']

    def attr(self, name):
        node = self.n('ShaderNodeAttribute'); node.attribute_name = name
        return node

    def mix(self, fac, a, b, kind='FLOAT'):
        node = self.n('ShaderNodeMix', dtype=kind)
        if kind == 'RGBA':
            ia, ib, out = 6, 7, 2
        elif kind == 'VECTOR':
            ia, ib, out = 4, 5, 1
        else:
            ia, ib, out = 2, 3, 0
        for idx, v in ((0, fac), (ia, a), (ib, b)):
            if isinstance(v, (int, float)):
                node.inputs[idx].default_value = v
            elif isinstance(v, (tuple, list)):
                node.inputs[idx].default_value = tuple(v) + ((1.0,) if kind == 'RGBA' and len(v) == 3 else ())
            else:
                self.link(v, node.inputs[idx])
        return node.outputs[out]

    def smooth(self, e0, e1, x):
        node = self.n('ShaderNodeMapRange')
        node.interpolation_type = 'SMOOTHSTEP'
        node.inputs['From Min'].default_value = e0
        node.inputs['From Max'].default_value = e1
        self.link(x, node.inputs['Value'])
        return node.outputs['Result']

    def maprange(self, x, a, b, c, d, clamp=True):
        node = self.n('ShaderNodeMapRange')
        node.clamp = clamp
        for k, v in (('From Min', a), ('From Max', b), ('To Min', c), ('To Max', d)):
            node.inputs[k].default_value = v
        self.link(x, node.inputs['Value'])
        return node.outputs['Result']

    def bsdf(self):
        b = self.n('ShaderNodeBsdfPrincipled')
        out = self.n('ShaderNodeOutputMaterial')
        self.link(b.outputs[0], out.inputs['Surface'])
        return b, out

    def set(self, node, name, v):
        if isinstance(v, (int, float)):
            node.inputs[name].default_value = v
        elif isinstance(v, (tuple, list)):
            node.inputs[name].default_value = tuple(v) + ((1.0,) if len(v) == 3 and node.inputs[name].type == 'RGBA' else ())
        else:
            self.link(v, node.inputs[name])


def _new(name):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    # self-glow (piping, visor, indicators) is seen directly but never used as a light
    # source for next-event estimation: otherwise every body triangle becomes a mesh
    # light (huge render cost, extra noise)
    try:
        m.cycles.emission_sampling = 'NONE'
    except Exception:
        pass
    return m


def suit_material():
    m = _new('HERO_suit')
    b = NB(m)
    bs, out = b.bsdf()
    rest = b.attr('rest').outputs['Vector']
    A = lambda n: b.attr(n).outputs['Fac']
    near_p = b.smooth(0.009, 0.006, A('pipe_d'))
    near_s = b.smooth(0.009, 0.006, A('seam_d'))
    # outside the near band push the signed values far away (kills spurious crossings)
    pipe_sd = b.mix(near_p, 0.03, A('pipe_sd'))
    seam_sd = b.mix(near_s, 0.03, A('seam_sd'))
    pipe_s, seam_s = A('pipe_s'), A('seam_s')
    tone_sd = A('tone_sd')
    hand, grip, foot, sole = A('hand'), A('grip'), A('foot'), A('sole')
    wrk = A('wrk')
    wrk_t = A('wrk_t')

    # ---------------- fabric micro weave (ripstop-like cross weave in rest space)
    p_mm = b.vmath('SCALE', rest, scale=1000.0)                    # millimetres
    sep = b.n('ShaderNodeSeparateXYZ'); b.link(p_mm, sep.inputs[0])
    def wave(coord, period):
        s = b.math('SINE', b.math('MULTIPLY', coord, 6.2831853 / period))
        return b.math('ABSOLUTE', s)
    # two diagonal yarn directions + slight noise warp
    noise = b.n('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 0.12
    noise.inputs['Detail'].default_value = 0.0
    b.link(p_mm, noise.inputs['Vector'])
    warp = b.math('MULTIPLY', noise.outputs['Fac'], 0.6)
    d1 = b.math('ADD', b.math('ADD', sep.outputs[0], sep.outputs[2]), warp)
    d2 = b.math('ADD', b.math('SUBTRACT', sep.outputs[1], sep.outputs[2]), warp)
    w1 = wave(d1, 0.8); w2 = wave(d2, 0.8)
    weave = b.math('MULTIPLY', b.math('ADD', w1, w2), 0.5)
    # ripstop reinforcement grid every ~5 mm
    g1 = b.smooth(0.90, 0.985, wave(b.math('ADD', sep.outputs[0], b.math('MULTIPLY', sep.outputs[1], 0.7)), 5.5))
    g2 = b.smooth(0.90, 0.985, wave(b.math('ADD', sep.outputs[2], b.math('MULTIPLY', sep.outputs[1], -0.5)), 5.5))
    grid = b.math('MAXIMUM', g1, g2)
    fabric_h = b.math('ADD', b.math('MULTIPLY', weave, 0.6), b.math('MULTIPLY', grid, 0.5))

    # grip rubber: small hex pads
    vor = b.n('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'
    vor.inputs['Scale'].default_value = 0.42
    b.link(p_mm, vor.inputs['Vector'])
    pads = b.smooth(0.03, 0.14, vor.outputs['Distance'])
    tread = b.val(0.0)

    # ---------------- wrinkles (folds across the limb near joints)
    nz = b.n('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 22.0
    nz.inputs['Detail'].default_value = 1.0
    b.link(rest, nz.inputs['Vector'])
    ph = b.math('ADD', b.math('MULTIPLY', wrk_t, 6.2831853 / 0.016), b.math('MULTIPLY', nz.outputs['Fac'], 7.0))
    folds = b.math('POWER', b.math('ABSOLUTE', b.math('SINE', ph)), 2.5)
    fold_h = b.math('MULTIPLY', folds, b.math('MULTIPLY', wrk, -1.0))

    # ---------------- piping cord
    W = 0.0021
    apd = b.math('ABSOLUTE', pipe_sd)
    cord = b.math('SQRT', b.math('MAXIMUM', b.math('SUBTRACT', 1.0, b.math('POWER', b.math('DIVIDE', apd, W), 2.0)), 0.0))
    cord_mask = b.smooth(W + 0.0002, W - 0.0003, apd)
    welt = b.math('MULTIPLY', b.smooth(W + 0.0014, W + 0.0002, apd), b.math('SUBTRACT', 1.0, cord_mask))
    # stitches beside the piping (both sides, 3 mm pitch)
    def stitches(adist, s, off, pitch=0.003, width=0.00045):
        row = b.smooth(width, width * 0.3, b.math('ABSOLUTE', b.math('SUBTRACT', adist, off)))
        dash = b.math('ABSOLUTE', b.math('SINE', b.math('MULTIPLY', s, 3.14159265 / pitch)))
        dash = b.smooth(0.25, 0.75, dash)
        return b.math('MULTIPLY', row, dash)
    pst = stitches(apd, pipe_s, W + 0.0024)
    # ---------------- seams (groove + double stitch row)
    asd = b.math('ABSOLUTE', seam_sd)
    groove = b.smooth(0.0011, 0.0002, asd)
    sst = b.math('MAXIMUM', stitches(asd, seam_s, 0.0026), stitches(asd, seam_s, 0.0042))
    # tone boundary seam away from the piping (inner arm / inner leg)
    atd = b.math('ABSOLUTE', tone_sd)
    far_pipe = b.smooth(0.006, 0.01, apd)
    tgroove = b.math('MULTIPLY', b.smooth(0.0011, 0.0002, atd), far_pipe)
    # stitch coordinate along the tone seam: use rest z / x combination as a proxy
    tst = b.math('MULTIPLY', stitches(atd, b.math('ADD', b.math('MULTIPLY', sep.outputs[2], 0.001), b.math('MULTIPLY', sep.outputs[0], 0.0004)), 0.0028), far_pipe)
    groove = b.math('MAXIMUM', groove, tgroove)
    stitch = b.math('MAXIMUM', b.math('MAXIMUM', pst, sst), tst)

    # ---------------- zones
    toneB = b.smooth(-0.00025, 0.00025, tone_sd)
    zone_glove = b.smooth(0.35, 0.65, hand)
    zone_grip = b.smooth(0.35, 0.65, grip)
    zone_shoe = b.smooth(0.45, 0.75, foot)
    zone_sole = b.smooth(0.3, 0.7, sole)

    col = b.mix(toneB, GRAPHITE, CHARCOAL, 'RGBA')
    # subtle colour variation of the yarn
    col = b.mix(b.math('ADD', b.math('MULTIPLY', weave, 0.12), b.math('MULTIPLY', grid, 0.10)), col, (0.066, 0.066, 0.067), 'RGBA')
    # near-black side panels (torso flanks) and inner limbs: graphic shape in silhouette
    inner_f = A('inner_f'); side_f = A('side_f')
    darkp = b.math('MAXIMUM', b.smooth(0.24, 0.30, inner_f), b.smooth(0.47, 0.53, side_f))
    col = b.mix(b.math('MULTIPLY', darkp, b.math('SUBTRACT', 1.0, zone_glove)), col, NEARBLACK, 'RGBA')
    pgroove = b.math('MAXIMUM', b.smooth(0.03, 0.008, b.math('ABSOLUTE', b.math('SUBTRACT', inner_f, 0.27))),
                     b.smooth(0.035, 0.01, b.math('ABSOLUTE', b.math('SUBTRACT', side_f, 0.5))))
    pgroove = b.math('MULTIPLY', pgroove, b.math('SUBTRACT', 1.0, zone_glove))
    col = b.mix(zone_glove, col, (0.024, 0.024, 0.026), 'RGBA')
    col = b.mix(zone_shoe, col, (0.028, 0.028, 0.03), 'RGBA')
    col = b.mix(zone_grip, col, (0.012, 0.012, 0.012), 'RGBA')
    col = b.mix(zone_sole, col, (0.010, 0.010, 0.010), 'RGBA')
    col = b.mix(b.math('MULTIPLY', stitch, 0.85), col, (0.09, 0.088, 0.085), 'RGBA')
    col = b.mix(b.math('MULTIPLY', groove, 0.6), col, (0.008, 0.008, 0.009), 'RGBA')
    col = b.mix(cord_mask, col, AMBER, 'RGBA')

    rough = b.mix(toneB, 0.62, 0.70)
    rough = b.math('ADD', rough, b.math('MULTIPLY', b.math('SUBTRACT', weave, 0.5), 0.22))
    rough = b.math('SUBTRACT', rough, b.math('MULTIPLY', grid, 0.12))
    rough = b.mix(zone_glove, rough, 0.55)
    rough = b.mix(zone_grip, rough, b.math('ADD', 0.82, b.math('MULTIPLY', pads, -0.2)))
    rough = b.mix(zone_sole, rough, 0.9)
    rough = b.mix(cord_mask, rough, 0.32)

    # height field for bump
    h = b.math('MULTIPLY', fabric_h, 0.00011)
    h = b.math('ADD', h, b.math('MULTIPLY', pgroove, -0.0004))
    h = b.math('ADD', h, b.math('MULTIPLY', fold_h, 0.0009))
    h = b.mix(zone_grip, h, b.math('MULTIPLY', pads, 0.0005))
    h = b.mix(zone_sole, h, b.math('MULTIPLY', tread, 0.0012))
    h = b.math('ADD', h, b.math('MULTIPLY', groove, -0.00045))
    h = b.math('ADD', h, b.math('MULTIPLY', welt, -0.00035))
    h = b.math('ADD', h, b.math('MULTIPLY', stitch, 0.00012))
    h = b.math('ADD', h, b.math('MULTIPLY', cord, 0.0011))
    bump = b.n('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 1.0
    bump.inputs['Distance'].default_value = 1.0
    b.link(h, bump.inputs['Height'])
    try:
        bump.invert = False
    except Exception:
        pass

    b.set(bs, 'Base Color', col)
    b.set(bs, 'Roughness', rough)
    b.set(bs, 'Normal', bump.outputs['Normal'])
    sheen = b.mix(zone_grip, 0.95, 0.1)
    sheen = b.mix(cord_mask, sheen, 0.2)
    b.set(bs, 'Sheen Weight', sheen)
    b.set(bs, 'Sheen Roughness', 0.32)
    b.set(bs, 'Sheen Tint', (0.62, 0.61, 0.60))
    b.set(bs, 'Specular IOR Level', b.mix(cord_mask, 0.45, 0.6))
    b.set(bs, 'Emission Color', AMBER)
    b.set(bs, 'Emission Strength', b.math('MULTIPLY', cord_mask, PIPE_EMIT))
    return m


def helmet_materials():
    # shell: satin graphite + clearcoat with micro scratches + panel lines
    m = _new('HERO_helmet_shell')
    b = NB(m)
    bs, out = b.bsdf()
    tc = b.n('ShaderNodeTexCoord')
    obj = tc.outputs['Object']
    hp = b.attr('hp').outputs['Vector']
    sep = b.n('ShaderNodeSeparateXYZ'); b.link(hp, sep.inputs[0])
    u, v, dvc = sep.outputs[0], sep.outputs[1], sep.outputs[2]
    au = b.math('ABSOLUTE', u)
    # panel lines in (deg) param space -> approx metres (r ~ 0.105 m, 1 deg = 1.83 mm)
    def groove_at(dist_deg, w=0.42):
        return b.smooth(w, w * 0.25, b.math('ABSOLUTE', dist_deg))
    # crown lines: u = +-24 deg from 6 deg above the visor back to the nape
    crown = b.math('MULTIPLY', groove_at(b.math('SUBTRACT', au, b.math('ADD', 24.0, b.math('MULTIPLY', b.math('MAXIMUM', b.math('SUBTRACT', v, 20.0), 0.0), 0.10)))),
                   b.smooth(4.0, 7.0, dvc))
    # cheek panel break: follows the cheek-plane / side-plane edge down to the rim
    cheek = b.math('MULTIPLY', groove_at(b.math('SUBTRACT', au, 62.0), 0.5),
                   b.math('MULTIPLY', b.smooth(-5.0, -8.0, dvc), b.smooth(-70, -64, v)))
    # back seam = continuation of the visor line; an amber accent rides in it from the
    # visor corner back over the ear
    seam_w = b.math('ABSOLUTE', b.math('SUBTRACT', b.math('ABSOLUTE', dvc), 0.75))
    backseam = b.math('MULTIPLY', b.smooth(0.45, 0.1, seam_w), b.smooth(86, 92, au))
    accent = b.math('MULTIPLY', b.math('MULTIPLY', b.smooth(0.42, 0.22, b.math('ABSOLUTE', dvc)), b.smooth(86, 92, au)),
                    b.smooth(152, 138, au))
    # two small intake slits on the chin bar
    slit = b.math('MULTIPLY', b.smooth(1.15, 0.75, b.math('ABSOLUTE', b.math('SUBTRACT', au, 8.5))),
                  b.math('MULTIPLY', b.smooth(-55.0, -53.5, v), b.smooth(-45.0, -46.5, v)))
    grooves = b.math('MAXIMUM', b.math('MAXIMUM', b.math('MAXIMUM', crown, cheek), backseam), slit)
    # faint edge wear on convex breaks
    geo = b.n('ShaderNodeNewGeometry')
    wn = b.n('ShaderNodeTexNoise'); wn.inputs['Scale'].default_value = 140.0
    b.link(obj, wn.inputs['Vector'])
    edge = b.math('MULTIPLY', b.smooth(0.515, 0.56, geo.outputs['Pointiness']), b.smooth(0.45, 0.6, wn.outputs['Fac']))
    # micro scratches in the clear coat (object space, rigid)
    sc_n = b.n('ShaderNodeTexNoise'); sc_n.inputs['Scale'].default_value = 3.0
    sc_n.inputs['Detail'].default_value = 1.0
    stretch = b.vmath('MULTIPLY', obj, (900.0, 60.0, 900.0))
    b.link(stretch, sc_n.inputs['Vector'])
    scr1 = b.smooth(0.495, 0.5, sc_n.outputs['Fac'])
    scr1 = b.math('MULTIPLY', b.smooth(0.5, 0.505, sc_n.outputs['Fac']), -1.0) if False else scr1
    sc2 = b.n('ShaderNodeTexWave'); sc2.wave_type = 'BANDS'; sc2.inputs['Scale'].default_value = 900.0
    sc2.inputs['Distortion'].default_value = 25.0; sc2.inputs['Detail'].default_value = 2
    b.link(obj, sc2.inputs['Vector'])
    scr = b.smooth(0.985, 1.0, sc2.outputs['Fac'])
    big = b.n('ShaderNodeTexNoise'); big.inputs['Scale'].default_value = 25.0
    b.link(obj, big.inputs['Vector'])
    scr = b.math('MULTIPLY', scr, b.smooth(0.5, 0.65, big.outputs['Fac']))
    # satin finish: broad roughness variation (handling wear) + micro scratches
    wear = b.n('ShaderNodeTexNoise'); wear.inputs['Scale'].default_value = 9.0
    wear.inputs['Detail'].default_value = 6.0
    b.link(obj, wear.inputs['Vector'])
    col = b.mix(b.math('MULTIPLY', grooves, 0.85), (0.046, 0.046, 0.047), (0.006, 0.006, 0.006), 'RGBA')
    col = b.mix(b.math('MULTIPLY', scr, 0.5), col, (0.08, 0.08, 0.08), 'RGBA')
    col = b.mix(b.math('MULTIPLY', edge, 0.6), col, (0.11, 0.105, 0.10), 'RGBA')
    col = b.mix(b.math('MULTIPLY', slit, 0.9), col, (0.002, 0.002, 0.002), 'RGBA')
    col = b.mix(accent, col, AMBER, 'RGBA')
    b.set(bs, 'Base Color', col)
    b.set(bs, 'Emission Color', AMBER)
    b.set(bs, 'Emission Strength', b.math('MULTIPLY', accent, PIPE_EMIT * 1.2))
    rgh = b.maprange(wear.outputs['Fac'], 0.3, 0.7, 0.44, 0.58)
    rgh = b.math('ADD', rgh, b.math('MULTIPLY', scr, 0.15))
    b.set(bs, 'Roughness', b.mix(grooves, rgh, 0.7))
    b.set(bs, 'Coat Weight', 0.22)
    b.set(bs, 'Coat Roughness', b.math('ADD', 0.18, b.math('MULTIPLY', scr, 0.3)))
    # fine orange-peel + groove bump
    op = b.n('ShaderNodeTexNoise'); op.inputs['Scale'].default_value = 900.0
    b.link(obj, op.inputs['Vector'])
    hgt = b.math('ADD', b.math('MULTIPLY', grooves, -0.0004), b.math('MULTIPLY', op.outputs['Fac'], 0.000006))
    hgt = b.math('ADD', hgt, b.math('MULTIPLY', slit, -0.0012))
    bump = b.n('ShaderNodeBump'); bump.inputs['Distance'].default_value = 1.0
    b.link(hgt, bump.inputs['Height'])
    b.set(bs, 'Normal', bump.outputs['Normal'])
    cb = b.n('ShaderNodeBump'); cb.inputs['Distance'].default_value = 1.0
    b.link(b.math('ADD', b.math('MULTIPLY', scr, 0.00002), b.math('MULTIPLY', grooves, -0.0004)), cb.inputs['Height'])
    b.set(bs, 'Coat Normal', cb.outputs['Normal'])
    b.set(bs, 'Sheen Weight', 0.25)
    b.set(bs, 'Sheen Roughness', 0.5)
    shell = m

    m = _new('HERO_visor_frame')   # rubber gasket around the visor
    b = NB(m); bs, out = b.bsdf()
    b.set(bs, 'Base Color', (0.008, 0.008, 0.008))
    b.set(bs, 'Metallic', 0.0)
    b.set(bs, 'Roughness', 0.62)
    b.set(bs, 'Sheen Weight', 0.3)
    frame = m

    m = _new('HERO_visor_inner')
    b = NB(m); bs, out = b.bsdf()
    hp = b.attr('hp').outputs['Vector']
    sep = b.n('ShaderNodeSeparateXYZ'); b.link(hp, sep.inputs[0])
    # faint amber glow, strongest along the centre line of the band, fading to the temples
    au = b.math('ABSOLUTE', sep.outputs[0])
    g = b.math('MULTIPLY', b.smooth(80, 20, au), b.smooth(5.0, 0.0, b.math('ABSOLUTE', sep.outputs[2])))
    b.set(bs, 'Base Color', (0.006, 0.005, 0.004))
    b.set(bs, 'Roughness', 0.35)
    b.set(bs, 'Emission Color', (1.0, 0.45, 0.08))
    b.set(bs, 'Emission Strength', b.maprange(g, 0, 1, 0.04, 0.55))
    glass = m

    m = _new('HERO_helmet_lip')
    b = NB(m); bs, out = b.bsdf()
    b.set(bs, 'Base Color', (0.008, 0.008, 0.008))
    b.set(bs, 'Roughness', 0.8)
    lip = m
    return [shell, frame, glass, lip]


def visor_glass_material():
    """amber-tinted mirrored glass pane: partly metallic (mirror coating) + transmission,
    clear coat on top, thin-film for a slight colour shift at grazing angles."""
    m = _new('HERO_visor_glass')
    b = NB(m); bs, out = b.bsdf()
    lw = b.n('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.3
    col = b.mix(lw.outputs['Facing'], (0.62, 0.26, 0.04), (0.95, 0.62, 0.30), 'RGBA')
    b.set(bs, 'Base Color', col)
    b.set(bs, 'Metallic', 0.55)
    b.set(bs, 'Roughness', 0.025)
    b.set(bs, 'Transmission Weight', 1.0)
    b.set(bs, 'IOR', 1.52)
    b.set(bs, 'Coat Weight', 1.0)
    b.set(bs, 'Coat Roughness', 0.0)
    b.set(bs, 'Coat IOR', 1.6)
    try:
        b.set(bs, 'Thin Film Thickness', 320.0)
        b.set(bs, 'Thin Film IOR', 1.45)
    except Exception:
        pass
    try:
        m.surface_render_method = 'BLENDED'
    except Exception:
        pass
    return m


def plate_material():
    """moulded armour: dark composite, slightly glossy, faint forged texture."""
    m = _new('HERO_armor')
    b = NB(m); bs, out = b.bsdf()
    tc = b.n('ShaderNodeTexCoord')
    pos = b.attr('prest').outputs['Vector']
    vor = b.n('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 180.0
    b.link(pos, vor.inputs['Vector'])
    nz = b.n('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 60.0
    b.link(pos, nz.inputs['Vector'])
    t = b.math('ADD', b.math('MULTIPLY', vor.outputs['Distance'], 0.6), b.math('MULTIPLY', nz.outputs['Fac'], 0.4))
    col = b.mix(t, (0.013, 0.013, 0.0135), (0.022, 0.022, 0.023), 'RGBA')
    geo = b.n('ShaderNodeNewGeometry')
    edge = b.smooth(0.52, 0.58, geo.outputs['Pointiness'])
    col = b.mix(b.math('MULTIPLY', edge, 0.7), col, (0.07, 0.068, 0.066), 'RGBA')
    b.set(bs, 'Base Color', col)
    b.set(bs, 'Roughness', b.maprange(t, 0.2, 0.8, 0.22, 0.32))
    b.set(bs, 'Coat Weight', 0.7)
    b.set(bs, 'Coat Roughness', 0.08)
    bump = b.n('ShaderNodeBump'); bump.inputs['Distance'].default_value = 1.0
    b.link(b.math('MULTIPLY', t, 0.00004), bump.inputs['Height'])
    b.set(bs, 'Normal', bump.outputs['Normal'])
    edge = m
    # amber inlay strip used on some plates
    return m


def gunmetal_material():
    m = _new('HERO_gunmetal')
    b = NB(m); bs, out = b.bsdf()
    tc = b.n('ShaderNodeTexCoord')
    obj = tc.outputs['Object']
    # brushed: noise stretched along local Y
    nz = b.n('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.0
    nz.inputs['Detail'].default_value = 4.0
    b.link(b.vmath('MULTIPLY', obj, (2500.0, 30.0, 2500.0)), nz.inputs['Vector'])
    b.set(bs, 'Base Color', b.mix(nz.outputs['Fac'], (0.07, 0.07, 0.075), (0.11, 0.11, 0.115), 'RGBA'))
    b.set(bs, 'Metallic', 1.0)
    b.set(bs, 'Roughness', b.maprange(nz.outputs['Fac'], 0.3, 0.7, 0.22, 0.34))
    b.set(bs, 'Anisotropic', 0.5)
    return m


def amber_light_material():
    m = _new('HERO_amber_light')
    b = NB(m); bs, out = b.bsdf()
    b.set(bs, 'Base Color', AMBER)
    b.set(bs, 'Roughness', 0.15)
    b.set(bs, 'Emission Color', (1.0, 0.42, 0.06))
    b.set(bs, 'Emission Strength', 2.5)
    b.set(bs, 'Coat Weight', 1.0)
    return m


def black_rubber_material():
    m = _new('HERO_rubber')
    b = NB(m); bs, out = b.bsdf()
    b.set(bs, 'Base Color', (0.012, 0.012, 0.012))
    b.set(bs, 'Roughness', 0.7)
    b.set(bs, 'Sheen Weight', 0.2)
    return m


def webbing_material():
    """belt webbing / pouch fabric (cordura-ish), object-space rigid or attribute space"""
    m = _new('HERO_webbing')
    b = NB(m); bs, out = b.bsdf()
    pos = b.attr('prest').outputs['Vector']
    wv = b.n('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = 1800.0
    wv.wave_type = 'BANDS'; wv.bands_direction = 'Z'
    b.link(pos, wv.inputs['Vector'])
    nz = b.n('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 400.0
    b.link(pos, nz.inputs['Vector'])
    t = b.math('ADD', b.math('MULTIPLY', wv.outputs['Fac'], 0.7), b.math('MULTIPLY', nz.outputs['Fac'], 0.3))
    b.set(bs, 'Base Color', b.mix(t, (0.016, 0.016, 0.017), (0.03, 0.03, 0.032), 'RGBA'))
    b.set(bs, 'Roughness', 0.75)
    b.set(bs, 'Sheen Weight', 0.5)
    b.set(bs, 'Sheen Roughness', 0.4)
    bump = b.n('ShaderNodeBump'); bump.inputs['Distance'].default_value = 1.0
    b.link(b.math('MULTIPLY', t, 0.00015), bump.inputs['Height'])
    b.set(bs, 'Normal', bump.outputs['Normal'])
    return m


def web_material():
    """pale high-tensile braided line"""
    m = _new('HERO_web')
    b = NB(m); bs, out = b.bsdf()
    a_u = b.attr('web_u').outputs['Fac']        # metres along the line
    a_t = b.attr('web_t').outputs['Fac']        # 0..1 around the line
    # braid: two counter-rotating helices (pitch 6 mm)
    p1 = b.math('SINE', b.math('MULTIPLY', b.math('ADD', b.math('DIVIDE', a_u, 0.006), a_t), 6.2831853 * 2))
    p2 = b.math('SINE', b.math('MULTIPLY', b.math('SUBTRACT', b.math('DIVIDE', a_u, 0.006), a_t), 6.2831853 * 2))
    br = b.math('MULTIPLY', b.math('ADD', b.math('MAXIMUM', p1, p2), 1.0), 0.5)
    b.set(bs, 'Base Color', b.mix(br, (0.68, 0.67, 0.63), (0.94, 0.93, 0.89), 'RGBA'))
    b.set(bs, 'Roughness', b.maprange(br, 0, 1, 0.5, 0.3))
    b.set(bs, 'Sheen Weight', 0.6)
    b.set(bs, 'Coat Weight', 0.3)
    b.set(bs, 'Coat Roughness', 0.2)
    bump = b.n('ShaderNodeBump'); bump.inputs['Distance'].default_value = 1.0
    b.link(b.math('MULTIPLY', br, 0.0006), bump.inputs['Height'])
    b.set(bs, 'Normal', bump.outputs['Normal'])
    return m


def inlay_material():
    m = _new('HERO_amber_inlay')
    b = NB(m); bs, out = b.bsdf()
    b.set(bs, 'Base Color', AMBER)
    b.set(bs, 'Roughness', 0.3)
    b.set(bs, 'Coat Weight', 0.6)
    b.set(bs, 'Emission Color', AMBER)
    b.set(bs, 'Emission Strength', PIPE_EMIT * 1.1)
    return m


def sole_material():
    m = _new('HERO_sole')
    b = NB(m); bs, out = b.bsdf()
    pos = b.attr('prest').outputs['Vector']
    vor = b.n('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'
    vor.inputs['Scale'].default_value = 160.0
    b.link(pos, vor.inputs['Vector'])
    tread = b.smooth(0.03, 0.12, vor.outputs['Distance'])
    b.set(bs, 'Base Color', b.mix(tread, (0.008, 0.008, 0.008), (0.018, 0.018, 0.018), 'RGBA'))
    b.set(bs, 'Roughness', b.maprange(tread, 0, 1, 0.9, 0.62))
    bump = b.n('ShaderNodeBump'); bump.inputs['Distance'].default_value = 1.0
    b.link(b.math('MULTIPLY', tread, 0.0008), bump.inputs['Height'])
    b.set(bs, 'Normal', bump.outputs['Normal'])
    b.set(bs, 'Sheen Weight', 0.25)
    return m


def shoe_material():
    """sock-shoe: engineered knit upper, moulded rubber sole wrapping up ~2 cm."""
    m = _new('HERO_shoe')
    b = NB(m); bs, out = b.bsdf()
    pos = b.attr('prest').outputs['Vector']
    sep = b.n('ShaderNodeSeparateXYZ'); b.link(pos, sep.inputs[0])
    sole = b.smooth(0.0262, 0.0252, sep.outputs[2])
    rim = b.math('MULTIPLY', b.smooth(0.0285, 0.0275, sep.outputs[2]), b.smooth(0.0262, 0.0270, sep.outputs[2]))
    p_mm = b.vmath('SCALE', pos, scale=1000.0)
    knit = b.n('ShaderNodeTexWave'); knit.wave_type = 'BANDS'; knit.bands_direction = 'Y'
    knit.inputs['Scale'].default_value = 0.9; knit.inputs['Distortion'].default_value = 1.5
    b.link(p_mm, knit.inputs['Vector'])
    vor = b.n('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'
    vor.inputs['Scale'].default_value = 0.18
    b.link(p_mm, vor.inputs['Vector'])
    tread = b.smooth(0.04, 0.16, vor.outputs['Distance'])
    col = b.mix(b.math('MULTIPLY', knit.outputs['Fac'], 0.4), (0.026, 0.026, 0.028), (0.045, 0.045, 0.048), 'RGBA')
    toecap = b.math('MULTIPLY', b.smooth(-0.03, -0.045, sep.outputs[1]), b.smooth(0.06, 0.05, sep.outputs[2]))
    col = b.mix(toecap, col, (0.012, 0.012, 0.012), 'RGBA')
    col = b.mix(sole, col, (0.011, 0.011, 0.011), 'RGBA')
    col = b.mix(b.math('MULTIPLY', rim, 0.9), col, AMBER, 'RGBA')
    b.set(bs, 'Base Color', col)
    b.set(bs, 'Roughness', b.mix(sole, b.mix(toecap, 0.62, 0.3), b.maprange(tread, 0, 1, 0.92, 0.7)))
    b.set(bs, 'Sheen Weight', b.mix(sole, 0.6, 0.15))
    b.set(bs, 'Sheen Roughness', 0.4)
    h = b.mix(sole, b.math('MULTIPLY', knit.outputs['Fac'], 0.00018), b.math('MULTIPLY', tread, 0.0007))
    bump = b.n('ShaderNodeBump'); bump.inputs['Distance'].default_value = 1.0
    b.link(h, bump.inputs['Height'])
    b.set(bs, 'Normal', bump.outputs['Normal'])
    b.set(bs, 'Emission Color', AMBER)
    b.set(bs, 'Emission Strength', b.math('MULTIPLY', rim, PIPE_EMIT))
    return m


def strap_material():
    """climbing webbing: tight twill rib along the strap, stitched edges."""
    m = _new('HERO_strap')
    b = NB(m); bs, out = b.bsdf()
    uv = b.attr('strap_uv').outputs['Vector']
    sep = b.n('ShaderNodeSeparateXYZ'); b.link(uv, sep.inputs[0])
    a, s = sep.outputs[0], sep.outputs[1]
    rib = b.math('ABSOLUTE', b.math('SINE', b.math('MULTIPLY', b.math('ADD', s, b.math('MULTIPLY', a, 0.004)), 6.2831853 / 0.0011)))
    row = b.math('MAXIMUM', b.smooth(0.05, 0.015, b.math('ABSOLUTE', b.math('SUBTRACT', a, 0.78))),
                 b.smooth(0.05, 0.015, b.math('ABSOLUTE', b.math('ADD', a, 0.78))))
    dash = b.smooth(0.3, 0.7, b.math('ABSOLUTE', b.math('SINE', b.math('MULTIPLY', s, 3.14159265 / 0.003))))
    st = b.math('MULTIPLY', row, dash)
    col = b.mix(b.math('MULTIPLY', rib, 0.5), (0.014, 0.014, 0.0145), (0.03, 0.03, 0.031), 'RGBA')
    col = b.mix(st, col, (0.09, 0.088, 0.085), 'RGBA')
    b.set(bs, 'Base Color', col)
    b.set(bs, 'Roughness', 0.62)
    b.set(bs, 'Sheen Weight', 0.7)
    b.set(bs, 'Sheen Roughness', 0.3)
    h = b.math('ADD', b.math('MULTIPLY', rib, 0.00008), b.math('MULTIPLY', st, 0.00015))
    bump = b.n('ShaderNodeBump'); bump.inputs['Distance'].default_value = 1.0
    b.link(h, bump.inputs['Height'])
    b.set(bs, 'Normal', bump.outputs['Normal'])
    return m


def gaiter_material():
    """ribbed neck gaiter"""
    m = _new('HERO_gaiter')
    b = NB(m); bs, out = b.bsdf()
    pos = b.attr('prest').outputs['Vector']
    sep = b.n('ShaderNodeSeparateXYZ'); b.link(pos, sep.inputs[0])
    rib = b.math('POWER', b.math('ABSOLUTE', b.math('SINE', b.math('MULTIPLY', sep.outputs[2], 6.2831853 / 0.0042))), 0.6)
    b.set(bs, 'Base Color', b.mix(rib, (0.012, 0.012, 0.0125), (0.028, 0.028, 0.029), 'RGBA'))
    b.set(bs, 'Roughness', 0.7)
    b.set(bs, 'Sheen Weight', 0.9)
    b.set(bs, 'Sheen Roughness', 0.3)
    bump = b.n('ShaderNodeBump'); bump.inputs['Distance'].default_value = 1.0
    b.link(b.math('MULTIPLY', rib, 0.0007), bump.inputs['Height'])
    b.set(bs, 'Normal', bump.outputs['Normal'])
    return m


# =====================================================================================
# VESPER v2 (cobalt / bone white / gold)

BLUE = (0.012, 0.034, 0.235)
WHITE = (0.66, 0.64, 0.585)
GOLD = (0.95, 0.68, 0.30)


def _rgb_node(b, name, col):
    n = b.n('ShaderNodeRGB')
    n.name = name; n.label = name
    n.outputs[0].default_value = (*col, 1.0)
    return n.outputs[0]


def fabric_material(name, rest_attr='rest', has_white=True, mask=False):
    """Matte-satin stretch suit. Body: cobalt + bone-white panels (attribute white_sd,
    > 0 on white), gold piping along every blue/white border, engraved streamline thread
    on the white panels.  Mask: cobalt hood with a stitched centre seam and a gold edge.
    Colours are exposed as RGB nodes named BLUE_COLOR / WHITE_COLOR / GOLD_COLOR."""
    m = _new(name)
    b = NB(m)
    bs, out = b.bsdf()
    rest = b.attr(rest_attr).outputs['Vector']
    p_mm = b.vmath('SCALE', rest, scale=1000.0)
    blue = _rgb_node(b, 'BLUE_COLOR', BLUE)
    white = _rgb_node(b, 'WHITE_COLOR', WHITE)
    gold = _rgb_node(b, 'GOLD_COLOR', GOLD)
    # --- micro-texture: printed hex cells ~1 mm + fine knit noise
    vor = b.n('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'
    vor.inputs['Scale'].default_value = 1.0
    b.link(p_mm, vor.inputs['Vector'])
    cell = b.smooth(0.0, 0.16, vor.outputs['Distance'])          # 0 in the grooves
    knit = b.n('ShaderNodeTexNoise'); knit.inputs['Scale'].default_value = 2.2
    knit.inputs['Detail'].default_value = 0.0
    b.link(p_mm, knit.inputs['Vector'])
    # --- wrinkles at joints (body only)
    if not mask:
        wrk = b.attr('wrk').outputs['Fac']; wrk_t = b.attr('wrk_t').outputs['Fac']
        nz = b.n('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 22.0
        nz.inputs['Detail'].default_value = 1.0
        b.link(rest, nz.inputs['Vector'])
        ph = b.math('ADD', b.math('MULTIPLY', wrk_t, 6.2831853 / 0.016), b.math('MULTIPLY', nz.outputs['Fac'], 7.0))
        folds = b.math('POWER', b.math('ABSOLUTE', b.math('SINE', ph)), 2.5)
        fold_h = b.math('MULTIPLY', folds, b.math('MULTIPLY', wrk, -0.0009))
    else:
        fold_h = b.val(0.0)
    hval = b.math('ADD', b.math('MULTIPLY', cell, 0.00007), b.math('MULTIPLY', knit.outputs['Fac'], 0.00003))
    hval = b.math('ADD', hval, fold_h)
    if has_white:
        wsd = b.attr('white_sd').outputs['Fac']
        wf = b.smooth(-0.00022, 0.00022, wsd)
        aw = b.math('ABSOLUTE', wsd)
        # gold piping cord along the border + a small shadow groove each side
        W = 0.0011
        cord = b.math('SQRT', b.math('MAXIMUM', b.math('SUBTRACT', 1.0, b.math('POWER', b.math('DIVIDE', aw, W), 2.0)), 0.0))
        cmask = b.smooth(W + 0.0001, W - 0.00025, aw)
        groove = b.math('MULTIPLY', b.smooth(W + 0.0007, W + 0.0001, aw), b.math('SUBTRACT', 1.0, cmask))
        # streamlines: offset contours of the panel border, gently warped, white only
        wn = b.n('ShaderNodeTexNoise'); wn.inputs['Scale'].default_value = 18.0
        wn.inputs['Detail'].default_value = 0.0
        b.link(rest, wn.inputs['Vector'])
        ws = b.math('ADD', wsd, b.math('MULTIPLY', b.math('SUBTRACT', wn.outputs['Fac'], 0.5), 0.006))
        phs = b.math('DIVIDE', ws, 0.0045)
        dd = b.math('MULTIPLY', b.math('ABSOLUTE', b.math('SUBTRACT', phs, b.math('ROUND', phs))), 4.5)
        sline = b.math('MULTIPLY', b.smooth(0.34, 0.14, dd),
                       b.math('MULTIPLY', b.smooth(0.0032, 0.0048, wsd), b.smooth(0.075, 0.065, wsd)))
        col = b.mix(wf, blue, white, 'RGBA')
        col = b.mix(b.math('MULTIPLY', sline, 0.75), col, (0.40, 0.39, 0.36), 'RGBA')
        hval = b.math('ADD', hval, b.math('MULTIPLY', sline, 0.00009))
        hval = b.math('ADD', hval, b.math('MULTIPLY', cord, 0.0009))
        hval = b.math('ADD', hval, b.math('MULTIPLY', groove, -0.0003))
    else:
        wf = b.val(0.0)
        cmask = b.val(0.0)
        col = blue
        if mask:
            hp = b.attr('hp').outputs['Vector']
            sp = b.n('ShaderNodeSeparateXYZ'); b.link(hp, sp.inputs[0])
            au = b.math('ABSOLUTE', sp.outputs[0])
            seamd = b.math('MINIMUM', au, b.math('SUBTRACT', 180.0, au))
            seam = b.math('MULTIPLY', b.smooth(0.55, 0.15, seamd), b.smooth(-25.0, -15.0, sp.outputs[1]))
            st_row = b.math('MAXIMUM', b.smooth(0.25, 0.1, b.math('ABSOLUTE', b.math('SUBTRACT', seamd, 1.25))), b.val(0.0))
            dash = b.smooth(0.3, 0.7, b.math('ABSOLUTE', b.math('SINE', b.math('MULTIPLY', sp.outputs[1], 3.14159 / 1.6))))
            stitch = b.math('MULTIPLY', b.math('MULTIPLY', st_row, dash), b.smooth(-25.0, -15.0, sp.outputs[1]))
            edge = b.smooth(0.02, 0.008, sp.outputs[2])
            cmask = edge
            col = b.mix(b.math('MULTIPLY', stitch, 0.7), col, (0.05, 0.07, 0.25), 'RGBA')
            hval = b.math('ADD', hval, b.math('MULTIPLY', seam, -0.0004))
            hval = b.math('ADD', hval, b.math('MULTIPLY', stitch, 0.0001))
            hval = b.math('ADD', hval, b.math('MULTIPLY', edge, 0.0007))
    # darker in the weave valleys (blue more than white), slight colour drift
    shade = b.maprange(cell, 0, 1, 0.72, 1.0)
    shade = b.mix(wf, shade, b.maprange(cell, 0, 1, 0.9, 1.0))
    colm = b.n('ShaderNodeMix', dtype='RGBA', blend='MULTIPLY')
    colm.inputs[0].default_value = 1.0
    b.link(col, colm.inputs[6])
    shc = b.n('ShaderNodeCombineColor')
    for k in range(3):
        b.link(shade, shc.inputs[k])
    b.link(shc.outputs[0], colm.inputs[7])
    col = colm.outputs[2]
    col = b.mix(cmask, col, gold, 'RGBA')
    rough = b.mix(wf, b.maprange(cell, 0, 1, 0.74, 0.58), b.maprange(cell, 0, 1, 0.62, 0.5))
    rough = b.mix(cmask, rough, 0.32)
    b.set(bs, 'Base Color', col)
    b.set(bs, 'Roughness', rough)
    b.set(bs, 'Metallic', cmask)
    b.set(bs, 'Sheen Weight', b.mix(cmask, 0.85, 0.0))
    b.set(bs, 'Sheen Roughness', 0.32)
    b.set(bs, 'Sheen Tint', (0.75, 0.75, 0.78))
    b.set(bs, 'Specular IOR Level', 0.42)
    bump = b.n('ShaderNodeBump'); bump.inputs['Distance'].default_value = 1.0
    b.link(hval, bump.inputs['Height'])
    b.set(bs, 'Normal', bump.outputs['Normal'])
    return m


def gold_material(name='HERO_gold'):
    m = _new(name)
    b = NB(m); bs, out = b.bsdf()
    tc = b.n('ShaderNodeTexCoord')
    nz = b.n('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 400.0
    b.link(tc.outputs['Object'], nz.inputs['Vector'])
    b.set(bs, 'Base Color', _rgb_node(b, 'GOLD_COLOR', GOLD))
    b.set(bs, 'Metallic', 1.0)
    b.set(bs, 'Roughness', b.maprange(nz.outputs['Fac'], 0.3, 0.7, 0.22, 0.34))
    return m


def lens_frame_material():
    m = _new('HERO_lens_frame')
    b = NB(m); bs, out = b.bsdf()
    b.set(bs, 'Base Color', (0.011, 0.011, 0.012))
    b.set(bs, 'Roughness', 0.32)
    b.set(bs, 'Coat Weight', 0.5)
    b.set(bs, 'Coat Roughness', 0.15)
    return m


def lens_glass_material():
    """mirrored gold lens: metal-coated glass under a clear coat, thin-film shimmer,
    faint hex micro-mesh in the coating"""
    m = _new('HERO_lens_glass')
    b = NB(m); bs, out = b.bsdf()
    tc = b.n('ShaderNodeTexCoord')
    vor = b.n('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'
    vor.inputs['Scale'].default_value = 900.0
    b.link(tc.outputs['Object'], vor.inputs['Vector'])
    mesh = b.smooth(0.0, 0.06, vor.outputs['Distance'])
    lw = b.n('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.3
    col = b.mix(lw.outputs['Facing'], (1.0, 0.74, 0.32), (1.0, 0.86, 0.55), 'RGBA')
    col = b.mix(b.math('MULTIPLY', b.math('SUBTRACT', 1.0, mesh), 0.6), col, (0.45, 0.30, 0.10), 'RGBA')
    b.set(bs, 'Base Color', col)
    b.set(bs, 'Metallic', 1.0)
    b.set(bs, 'Roughness', 0.11)
    b.set(bs, 'Emission Color', (1.0, 0.7, 0.3))
    b.set(bs, 'Emission Strength', 0.06)
    b.set(bs, 'Coat Weight', 1.0)
    b.set(bs, 'Coat Roughness', 0.0)
    try:
        b.set(bs, 'Thin Film Thickness', 260.0)
        b.set(bs, 'Thin Film IOR', 1.4)
    except Exception:
        pass
    return m


def shoe_material_v2():
    """suit-covered foot: white weave over a thin dark sole with a gold edge line"""
    m = _new('HERO_shoe')
    b = NB(m); bs, out = b.bsdf()
    pos = b.attr('prest').outputs['Vector']
    sep = b.n('ShaderNodeSeparateXYZ'); b.link(pos, sep.inputs[0])
    p_mm = b.vmath('SCALE', pos, scale=1000.0)
    vor = b.n('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'
    vor.inputs['Scale'].default_value = 1.0
    b.link(p_mm, vor.inputs['Vector'])
    cell = b.smooth(0.0, 0.16, vor.outputs['Distance'])
    sole = b.smooth(0.0085, 0.0075, sep.outputs[2])
    line = b.math('MULTIPLY', b.smooth(0.0105, 0.0098, sep.outputs[2]), b.smooth(0.0085, 0.0092, sep.outputs[2]))
    white = _rgb_node(b, 'WHITE_COLOR', WHITE)
    col = b.mix(b.math('MULTIPLY', b.math('SUBTRACT', 1.0, cell), 0.12), white, (0.3, 0.29, 0.27), 'RGBA')
    col = b.mix(sole, col, (0.03, 0.03, 0.032), 'RGBA')
    col = b.mix(line, col, GOLD, 'RGBA')
    b.set(bs, 'Base Color', col)
    b.set(bs, 'Metallic', line)
    b.set(bs, 'Roughness', b.mix(sole, b.maprange(cell, 0, 1, 0.6, 0.5), 0.8))
    b.set(bs, 'Sheen Weight', b.mix(sole, 0.8, 0.1))
    b.set(bs, 'Sheen Roughness', 0.32)
    bump = b.n('ShaderNodeBump'); bump.inputs['Distance'].default_value = 1.0
    b.link(b.math('ADD', b.math('MULTIPLY', cell, 0.00007), b.math('MULTIPLY', line, 0.0005)), bump.inputs['Height'])
    b.set(bs, 'Normal', bump.outputs['Normal'])
    return m
