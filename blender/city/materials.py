"""Procedural Cycles materials for the city. All materials are created once and cached.

Conventions:
  * facade meshes carry two FACE float-colour attributes:
      win  = (rand, lit_rank, blind, tint)   on window/pane faces
      bcol = (r, g, b, building_rand)        on every face of a building
  * world-space coordinates are used for masonry/brick/asphalt patterns (meshes are
    built in world space), UVs (0..1 per opening) for window frames and blinds.
  * every emissive material reads LIGHT_CTRL via drivers (lighting.ctrl_value_node).
"""
import math
import bpy
import lighting

_cache = {}


# ----------------------------------------------------------------- node helper
class NB:
    def __init__(self, mat):
        self.mat = mat
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.x = 0

    def n(self, t, loc=None, **props):
        node = self.nt.nodes.new(t)
        if loc:
            node.location = loc
        else:
            self.x += 180
            node.location = (self.x, 0)
        for k, v in props.items():
            if k.startswith('i_'):
                self.set_in(node, k[2:], v)
            else:
                setattr(node, k, v)
        return node

    def set_in(self, node, name, v):
        name = name.replace('_', ' ')
        sock = None
        if isinstance(name, str) and name.isdigit():
            sock = node.inputs[int(name)]
        else:
            for s in node.inputs:
                if s.name == name and s.enabled:
                    sock = s
                    break
            if sock is None:
                sock = node.inputs[name]
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        else:
            sock.default_value = v

    def link(self, a, b):
        self.nt.links.new(a, b)

    def math(self, op, a, b=None, c=None, clamp=False):
        m = self.n('ShaderNodeMath', operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                self.link(v, m.inputs[i])
            else:
                m.inputs[i].default_value = v
        return m.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        m = self.n('ShaderNodeVectorMath', operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                self.link(v, m.inputs[i])
            else:
                m.inputs[i].default_value = v
        if scale is not None:
            s = m.inputs['Scale']
            if isinstance(scale, bpy.types.NodeSocket):
                self.link(scale, s)
            else:
                s.default_value = scale
        return m.outputs[0] if op not in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else m.outputs['Value']

    def mix(self, fac, a, b, dtype='RGBA', blend='MIX'):
        m = self.n('ShaderNodeMix', data_type=dtype, blend_type=blend)
        ins = [s for s in m.inputs if s.enabled]
        # enabled inputs: Factor, A, B
        for sock, v in zip(ins, (fac, a, b)):
            if isinstance(v, bpy.types.NodeSocket):
                self.link(v, sock)
            else:
                sock.default_value = v if not (dtype == 'RGBA' and isinstance(v, (int, float)) and sock is not ins[0]) else (v, v, v, 1)
        return [s for s in m.outputs if s.enabled][0]

    def ramp(self, fac, stops, interp='LINEAR'):
        r = self.n('ShaderNodeValToRGB')
        r.color_ramp.interpolation = interp
        els = r.color_ramp.elements
        while len(els) > 1:
            els.remove(els[-1])
        els[0].position = stops[0][0]
        els[0].color = _c4(stops[0][1])
        for p, c in stops[1:]:
            e = els.new(p)
            e.color = _c4(c)
        self.link(fac, r.inputs[0])
        return r.outputs[0]

    def attr(self, name, kind='GEOMETRY'):
        a = self.n('ShaderNodeAttribute', attribute_type=kind, attribute_name=name)
        return a

    def ctrl(self, prop):
        return lighting.ctrl_value_node(self.nt, prop, location=(self.x, -400)).outputs[0]

    def out(self, surface=None, volume=None, disp=None):
        o = self.n('ShaderNodeOutputMaterial')
        if surface is not None:
            self.link(surface, o.inputs['Surface'])
        if volume is not None:
            self.link(volume, o.inputs['Volume'])
        if disp is not None:
            self.link(disp, o.inputs['Displacement'])
        return o

    def principled(self, **kw):
        p = self.n('ShaderNodeBsdfPrincipled')
        for k, v in kw.items():
            self.set_in(p, k, v)
        return p


def _c4(c):
    if isinstance(c, (int, float)):
        return (c, c, c, 1.0)
    if len(c) == 3:
        return (c[0], c[1], c[2], 1.0)
    return tuple(c)


NO_EMIT_SAMPLING = {'window', 'curtain', 'far', 'shop', 'flood', 'sign_warm', 'sign_white', 'sign_red', 'sign_blue',
                    'headlight', 'taillight', 'sig_red', 'sig_green', 'sig_amber'}


def _new(name):
    if name in _cache:
        return None, _cache[name]
    m = bpy.data.materials.new(name)
    _cache[name] = m
    if name in NO_EMIT_SAMPLING:
        m.cycles.emission_sampling = 'NONE'
    return NB(m), m


def get(name):
    """Return a material by logical name, building it on first use."""
    if name in _cache:
        return _cache[name]
    fn = BUILDERS[name]
    return fn(name)


# ----------------------------------------------------------------- shared bits
def facade_coords(nb):
    """World position; horizontal facade coordinate h (follows the face) and z."""
    geo = nb.n('ShaderNodeNewGeometry')
    sep = nb.n('ShaderNodeSeparateXYZ', i_Vector=geo.outputs['Position'])
    nsep = nb.n('ShaderNodeSeparateXYZ', i_Vector=geo.outputs['Normal'])
    ax = nb.math('ABSOLUTE', nsep.outputs['X'])
    ay = nb.math('ABSOLUTE', nsep.outputs['Y'])
    h = nb.math('ADD', nb.math('MULTIPLY', sep.outputs['X'], ay), nb.math('MULTIPLY', sep.outputs['Y'], ax))
    return geo, sep, nsep, h


def grime(nb, geo, sep, strength=0.35, streak_scale=1.0):
    """0..1 dirt factor: vertical rain streaks + ground grime + large blotches."""
    pos = geo.outputs['Position']
    st = nb.vmath('MULTIPLY', pos, (0.9 * streak_scale, 0.9 * streak_scale, 0.035 * streak_scale))
    n1 = nb.n('ShaderNodeTexNoise', i_Vector=st, i_Scale=3.0, i_Detail=6.0, i_Roughness=0.6)
    streak = nb.n('ShaderNodeMapRange', i_Value=n1.outputs['Fac'], **{'i_From Min': 0.45, 'i_From Max': 0.75})
    n2 = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=0.05, i_Detail=3.0)
    blot = nb.n('ShaderNodeMapRange', i_Value=n2.outputs['Fac'], **{'i_From Min': 0.4, 'i_From Max': 0.7})
    ground = nb.n('ShaderNodeMapRange', i_Value=sep.outputs['Z'], **{'i_From Min': 6.0, 'i_From Max': 0.0})
    g = nb.math('ADD', nb.math('MULTIPLY', streak.outputs[0], 0.6), nb.math('MULTIPLY', blot.outputs[0], 0.5))
    g = nb.math('ADD', g, nb.math('MULTIPLY', ground.outputs[0], 0.6))
    return nb.math('MULTIPLY', g, strength, clamp=True)


def emission_add(nb, bsdf, color, strength):
    em = nb.n('ShaderNodeEmission', i_Color=color, i_Strength=strength)
    add = nb.n('ShaderNodeAddShader')
    nb.link(bsdf, add.inputs[0])
    nb.link(em.outputs[0], add.inputs[1])
    return add.outputs[0]


# ----------------------------------------------------------------- windows
ROOM_LOD = (70.0, 110.0)


def room_lod(nb):
    """1 near the camera, 0 beyond ROOM_LOD[1] m: distant panes stay opaque (painted interior),
    so rays only enter the room modules where they can be seen."""
    lp = nb.n('ShaderNodeLightPath')
    r = nb.n('ShaderNodeMapRange', i_Value=lp.outputs['Ray Length'],
             **{'i_From Min': ROOM_LOD[0], 'i_From Max': ROOM_LOD[1], 'i_To Min': 1.0, 'i_To Max': 0.0})
    return r.outputs[0]


def _window_shader(nb, curtain=False):
    """Shared window/pane network. Returns shader socket."""
    win = nb.attr('win')
    bc = nb.attr('bcol')
    sep = nb.n('ShaderNodeSeparateColor', i_Color=win.outputs['Color'])
    rnd, lrank, blind = sep.outputs[0], sep.outputs[1], sep.outputs[2]
    tint = win.outputs['Alpha']
    uv = nb.n('ShaderNodeUVMap', uv_map="UVMap")
    uvs = nb.n('ShaderNodeSeparateXYZ', i_Vector=uv.outputs['UV'])
    u, v = uvs.outputs['X'], uvs.outputs['Y']
    # ---- lit?
    frac = nb.ctrl('window_frac')
    lit = nb.math('LESS_THAN', lrank, frac)
    inten = nb.math('MULTIPLY_ADD', rnd, 1.6, 0.35)
    wem = nb.ctrl('window_emit')
    estr = nb.math('MULTIPLY', nb.math('MULTIPLY', lit, inten), wem)
    # ceiling-light gradient inside the room
    grad = nb.math('MULTIPLY_ADD', v, 0.8, 0.45)
    estr = nb.math('MULTIPLY', estr, grad)
    ecol = nb.ramp(tint, [(0.0, (1.0, 0.62, 0.30)), (0.55, (1.0, 0.74, 0.45)), (0.78, (1.0, 0.88, 0.70)),
                          (0.80, (0.78, 0.88, 1.0)), (1.0, (0.85, 0.92, 1.0))], interp='CONSTANT')
    # ---- blinds: v above (1 - blind) is blind
    bl = nb.math('GREATER_THAN', v, nb.math('SUBTRACT', 1.0, blind))
    # ---- interior (unlit) colour: very dark with variation; blinds beige
    interior = nb.ramp(rnd, [(0.0, (0.016, 0.018, 0.022)), (0.35, (0.035, 0.033, 0.03)), (0.7, (0.05, 0.05, 0.055)), (1.0, (0.08, 0.07, 0.06))])
    blindc = nb.ramp(rnd, [(0.0, (0.42, 0.40, 0.34)), (0.5, (0.55, 0.52, 0.46)), (1.0, (0.30, 0.31, 0.32))])
    base = nb.mix(bl, interior, blindc)
    # blinds are lit by the room (translucent glow), slightly weaker
    estr = nb.math('MULTIPLY', estr, nb.math('MULTIPLY_ADD', bl, -0.35, 1.0))
    # panes with a real room module behind them ('wroom' face attribute = 1): the room's own
    # lamps light it, so the painted-on interior glow is switched off (blinds keep theirs)
    wr = nb.n('ShaderNodeSeparateColor', i_Color=nb.attr('wroom').outputs['Color']).outputs[0]
    clear = nb.math('MULTIPLY', wr, nb.math('SUBTRACT', 1.0, bl))
    clear = nb.math('MULTIPLY', clear, room_lod(nb))
    estr = nb.math('MULTIPLY', estr, nb.math('SUBTRACT', 1.0, clear))
    # ---- glass tilt wobble from per-pane random
    wn = nb.n('ShaderNodeTexWhiteNoise', noise_dimensions='3D',
              i_Vector=nb.vmath('MULTIPLY', win.outputs['Color'], (137.1, 71.3, 13.7)))
    jit = nb.vmath('SUBTRACT', wn.outputs['Color'], (0.5, 0.5, 0.5))
    geo = nb.n('ShaderNodeNewGeometry')
    nrm = nb.vmath('NORMALIZE', nb.vmath('MULTIPLY_ADD', jit, (0.035, 0.035, 0.035)) if False else
                   nb.vmath('ADD', geo.outputs['Normal'], nb.vmath('SCALE', jit, scale=0.03 if curtain else 0.02)))
    rough = nb.math('MULTIPLY_ADD', rnd, 0.03, 0.005)
    rough = nb.mix(bl, rough, 0.55, dtype='FLOAT')
    if curtain:
        gcol = bc.outputs['Color']
        # reflective coated glass: metallic tinted reflection over dark interior
        metal = nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, bl), 0.8)
        basec = nb.mix(metal, base, gcol)
        glass = nb.principled(**{'Base Color': basec, 'Metallic': metal, 'Roughness': rough,
                                 'IOR': 1.52, 'Normal': nrm})
    else:
        # dark room behind a clear specular coat (double glazing: two reflecting surfaces)
        glass = nb.principled(**{'Base Color': base, 'Roughness': nb.mix(bl, 0.35, 0.55, dtype='FLOAT'), 'IOR': 1.52,
                                 'Normal': nrm, 'Specular IOR Level': 1.0, 'Coat Weight': nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', bl, 0.3)),
                                 'Coat Roughness': rough, 'Coat IOR': 1.6, 'Coat Normal': nrm})
    sh = emission_add(nb, glass.outputs[0], ecol, estr)
    # Art-directed reflection lift. At grazing angles the true mirror ray of a recessed pane hits
    # its own reveal or the shadowed opposite wall, so panes read as black holes. Add a faint
    # Fresnel-weighted environment term: warm haze toward the sun, cool sky elsewhere.
    # No extra rays; fades out as the sun sets.
    lw = nb.n('ShaderNodeLayerWeight', i_Blend=0.35, i_Normal=nrm)
    fres = nb.math('POWER', lw.outputs['Facing'], 3.0)
    refl = nb.vmath('REFLECT', geo.outputs['Incoming'] if False else nb.vmath('SCALE', geo.outputs['Incoming'], scale=-1.0), nrm)
    sv = nb.n('ShaderNodeCombineXYZ', i_X=nb.ctrl('sun_x'), i_Y=nb.ctrl('sun_y'), i_Z=nb.ctrl('sun_z'))
    tos = nb.math('POWER', nb.math('MAXIMUM', nb.vmath('DOT_PRODUCT', refl, sv.outputs[0]), 0.0), 6.0)
    envc = nb.mix(nb.math('MINIMUM', tos, 1.0), (0.30, 0.36, 0.46, 1), (1.0, 0.70, 0.42, 1))
    envs = nb.math('MULTIPLY_ADD', tos, 3.0, 0.55)
    dayk = nb.math('MULTIPLY_ADD', nb.ctrl('sun_strength'), 0.1, 0.12)
    estr2 = nb.math('MULTIPLY', nb.math('MULTIPLY', fres, envs), dayk)
    estr2 = nb.math('MULTIPLY', estr2, nb.math('SUBTRACT', 1.0, bl))
    estr2 = nb.math('MULTIPLY', estr2, 0.6 if curtain else 0.9)
    sh = emission_add(nb, sh, envc, estr2)
    # see-through glass into the room: Fresnel decides reflect vs transmit (Transparent BSDF so
    # daylight and shadows enter the room cheaply; the coat above provides the reflection)
    fr_ = nb.n('ShaderNodeFresnel', i_IOR=1.52, i_Normal=nrm).outputs[0]
    refl_w = nb.math('MINIMUM', nb.math('MULTIPLY_ADD', fr_, 2.2 if curtain else 2.0, 0.22 if curtain else 0.03), 1.0)
    tfac = nb.math('MULTIPLY', clear, nb.math('SUBTRACT', 1.0, refl_w))
    tr = nb.n('ShaderNodeBsdfTransparent', i_Color=(0.92, 0.94, 0.93, 1) if not curtain else nb.mix(0.3, (0.92, 0.94, 0.93, 1), bc.outputs['Color']))
    mxr = nb.n('ShaderNodeMixShader', i_Fac=tfac)
    mxr.name = 'ROOM_see_through'
    nb.link(sh, mxr.inputs[1])
    nb.link(tr.outputs[0], mxr.inputs[2])
    sh = mxr.outputs[0]
    if not curtain:
        # thin frame + mullion inside the opening (UV based)
        fw = 0.035
        fx = nb.math('MAXIMUM', nb.math('LESS_THAN', u, fw), nb.math('GREATER_THAN', u, 1 - fw))
        fy = nb.math('MAXIMUM', nb.math('LESS_THAN', v, fw * 0.8), nb.math('GREATER_THAN', v, 1 - fw * 0.8))
        mull = nb.math('LESS_THAN', nb.math('ABSOLUTE', nb.math('SUBTRACT', u, 0.5)), 0.012)
        mull = nb.math('MULTIPLY', mull, nb.math('GREATER_THAN', rnd, 0.35))
        trans = nb.math('LESS_THAN', nb.math('ABSOLUTE', nb.math('SUBTRACT', v, 0.72)), 0.012)
        frame = nb.math('MAXIMUM', nb.math('MAXIMUM', fx, fy), nb.math('MAXIMUM', mull, trans))
        fcol = nb.ramp(bc.outputs['Alpha'], [(0.0, (0.03, 0.03, 0.03)), (0.6, (0.06, 0.05, 0.04)),
                                              (0.8, (0.55, 0.53, 0.50)), (1.0, (0.20, 0.10, 0.06))], interp='CONSTANT')
        fr = nb.principled(**{'Base Color': fcol, 'Roughness': 0.45, 'Metallic': 0.3})
        mx = nb.n('ShaderNodeMixShader', i_Fac=frame)
        nb.link(sh, mx.inputs[1])
        nb.link(fr.outputs[0], mx.inputs[2])
        sh = mx.outputs[0]
    return sh


def m_window(name):
    nb, m = _new(name)
    nb.out(_window_shader(nb, curtain=False))
    return m


def m_curtain(name):
    nb, m = _new(name)
    nb.out(_window_shader(nb, curtain=True))
    return m


def m_cw_spandrel(name):
    """Opaque shadow-box glass at slab level of curtain walls."""
    nb, m = _new(name)
    bc = nb.attr('bcol')
    dark = nb.mix(0.55, bc.outputs['Color'], (0.02, 0.022, 0.025, 1))
    p = nb.principled(**{'Base Color': dark, 'Metallic': 0.55, 'Roughness': 0.08, 'IOR': 1.52})
    nb.out(p.outputs[0])
    return m


# ----------------------------------------------------------------- masonry
def m_stone(name, ashlar=(1.6, 0.62), rough=0.78, grime_k=0.45, bevel=False, tower=False):
    nb, m = _new(name)
    bc = nb.attr('bcol')
    geo, sep, nsep, h = facade_coords(nb)
    vec = nb.n('ShaderNodeCombineXYZ', i_X=h, i_Y=sep.outputs['Z'], i_Z=0.0)
    br = nb.n('ShaderNodeTexBrick', i_Vector=vec.outputs[0], i_Color1=(1, 1, 1, 1), i_Color2=(0.8, 0.8, 0.8, 1),
              i_Mortar=(0.55, 0.55, 0.55, 1), i_Scale=1.0, **{'i_Mortar Size': 0.012, 'i_Brick Width': ashlar[0],
                                                              'i_Row Height': ashlar[1], 'i_Mortar Smooth': 0.3})
    br.offset = 0.5
    br.squash = 1.0
    var = br.outputs['Color']
    noise = nb.n('ShaderNodeTexNoise', i_Vector=geo.outputs['Position'], i_Scale=2.5, i_Detail=8.0, i_Roughness=0.65)
    fine = nb.n('ShaderNodeMapRange', i_Value=noise.outputs['Fac'], **{'i_To Min': 0.85, 'i_To Max': 1.12})
    base = nb.mix(1.0, bc.outputs['Color'], var, blend='MULTIPLY')
    base = nb.mix(1.0, base, fine.outputs[0], blend='MULTIPLY')
    g = grime(nb, geo, sep, grime_k)
    dirt = (0.08, 0.075, 0.07, 1)
    base = nb.mix(g, base, dirt, blend='MULTIPLY')
    base = nb.mix(nb.math('MULTIPLY', g, 0.5), base, dirt)
    bump_h = nb.math('ADD', nb.math('MULTIPLY', br.outputs['Fac'], -1.0), nb.math('MULTIPLY', noise.outputs['Fac'], 0.3))
    nrm_in = None
    if bevel:
        bv = nb.n('ShaderNodeBevel', samples=4, i_Radius=0.04)
        nrm_in = bv.outputs['Normal']
    bump = nb.n('ShaderNodeBump', i_Strength=0.25, i_Distance=0.01, i_Height=bump_h)
    if nrm_in is not None:
        nb.link(nrm_in, bump.inputs['Normal'])
    rr = nb.math('ADD', rough, nb.math('MULTIPLY', g, 0.15))
    p = nb.principled(**{'Base Color': base, 'Roughness': rr, 'Normal': bump.outputs['Normal'],
                         'Specular IOR Level': 0.4})
    nb.out(p.outputs[0])
    return m


def m_brick(name):
    nb, m = _new(name)
    bc = nb.attr('bcol')
    geo, sep, nsep, h = facade_coords(nb)
    vec = nb.n('ShaderNodeCombineXYZ', i_X=h, i_Y=sep.outputs['Z'], i_Z=0.0)
    br = nb.n('ShaderNodeTexBrick', i_Vector=vec.outputs[0], i_Color1=(1.0, 1.0, 1.0, 1), i_Color2=(0.62, 0.6, 0.58, 1),
              i_Mortar=(2.2, 2.1, 1.9, 1), i_Scale=1.0, **{'i_Mortar Size': 0.008, 'i_Brick Width': 0.215,
                                                         'i_Row Height': 0.072, 'i_Mortar Smooth': 0.1, 'i_Bias': 0.0})
    base = nb.mix(1.0, bc.outputs['Color'], br.outputs['Color'], blend='MULTIPLY')
    noise = nb.n('ShaderNodeTexNoise', i_Vector=geo.outputs['Position'], i_Scale=0.6, i_Detail=4.0)
    fine = nb.n('ShaderNodeMapRange', i_Value=noise.outputs['Fac'], **{'i_To Min': 0.8, 'i_To Max': 1.2})
    base = nb.mix(1.0, base, fine.outputs[0], blend='MULTIPLY')
    g = grime(nb, geo, sep, 0.5)
    base = nb.mix(g, base, (0.10, 0.09, 0.085, 1), blend='MULTIPLY')
    bump = nb.n('ShaderNodeBump', i_Strength=0.3, i_Distance=0.005, i_Height=br.outputs['Fac'])
    p = nb.principled(**{'Base Color': base, 'Roughness': 0.85, 'Normal': bump.outputs['Normal'],
                         'Specular IOR Level': 0.35})
    nb.out(p.outputs[0])
    return m


def m_simple(name, color, rough=0.6, metal=0.0, noise_amt=0.15, noise_scale=3.0, use_bcol=False, spec=0.5,
             grime_k=0.0, bump=0.0, coat=0.0):
    nb, m = _new(name)
    geo = nb.n('ShaderNodeNewGeometry')
    sep = nb.n('ShaderNodeSeparateXYZ', i_Vector=geo.outputs['Position'])
    noise = nb.n('ShaderNodeTexNoise', i_Vector=geo.outputs['Position'], i_Scale=noise_scale, i_Detail=6.0)
    f = nb.n('ShaderNodeMapRange', i_Value=noise.outputs['Fac'], **{'i_To Min': 1 - noise_amt, 'i_To Max': 1 + noise_amt})
    col = nb.attr('bcol').outputs['Color'] if use_bcol else _c4(color)
    base = nb.mix(1.0, col, f.outputs[0], blend='MULTIPLY')
    if grime_k:
        g = grime(nb, geo, sep, grime_k)
        base = nb.mix(g, base, (0.08, 0.075, 0.07, 1), blend='MULTIPLY')
    kw = {'Base Color': base, 'Roughness': rough, 'Metallic': metal, 'Specular IOR Level': spec}
    if bump:
        b = nb.n('ShaderNodeBump', i_Strength=bump, i_Distance=0.02, i_Height=noise.outputs['Fac'])
        kw['Normal'] = b.outputs['Normal']
    if coat:
        kw['Coat Weight'] = coat
        kw['Coat Roughness'] = 0.05
    p = nb.principled(**kw)
    nb.out(p.outputs[0])
    return m


def m_emit(name, color, ctrl_prop, base_strength, bsdf_color=(0.8, 0.8, 0.8)):
    nb, m = _new(name)
    s = nb.math('MULTIPLY', nb.ctrl(ctrl_prop), base_strength)
    p = nb.principled(**{'Base Color': _c4(bsdf_color), 'Roughness': 0.2, 'Emission Color': _c4(color),
                         'Emission Strength': s})
    nb.out(p.outputs[0])
    return m


# ----------------------------------------------------------------- far facades
def m_far(name):
    """Shader-only windows for mid/far buildings. Faces carry bcol (wall colour + rand)
    and bprm (style 0 masonry..1 glass, bay width, storey height, lit bias)."""
    nb, m = _new(name)
    bc = nb.attr('bcol')
    pr = nb.attr('bprm')
    prs = nb.n('ShaderNodeSeparateColor', i_Color=pr.outputs['Color'])
    style, bay, storey = prs.outputs[0], prs.outputs[1], prs.outputs[2]
    brand = bc.outputs['Alpha']
    geo, sep, nsep, h = facade_coords(nb)
    z = sep.outputs['Z']
    hu = nb.math('DIVIDE', h, bay)
    zv = nb.math('DIVIDE', z, storey)
    cu = nb.math('FLOOR', hu)
    cv = nb.math('FLOOR', zv)
    fu = nb.math('FRACT', hu)
    fv = nb.math('FRACT', zv)
    # window opening size: masonry ~ 55% x 55%, glass ~ 94% x 78%
    ww = nb.mix(style, 0.52, 0.94, dtype='FLOAT')
    wh = nb.mix(style, 0.55, 0.76, dtype='FLOAT')
    inu = nb.math('LESS_THAN', nb.math('ABSOLUTE', nb.math('SUBTRACT', fu, 0.5)), nb.math('MULTIPLY', ww, 0.5))
    inv = nb.math('LESS_THAN', nb.math('ABSOLUTE', nb.math('SUBTRACT', fv, 0.55)), nb.math('MULTIPLY', wh, 0.5))
    vert = nb.math('LESS_THAN', nb.math('ABSOLUTE', nsep.outputs['Z']), 0.5)
    ground = nb.math('GREATER_THAN', z, 4.5)
    win = nb.math('MULTIPLY', nb.math('MULTIPLY', inu, inv), nb.math('MULTIPLY', vert, ground))
    cell = nb.n('ShaderNodeCombineXYZ', i_X=cu, i_Y=cv, i_Z=nb.math('MULTIPLY', brand, 1000.0))
    # include the face orientation so opposite faces differ
    cellv = nb.vmath('ADD', cell.outputs[0], nb.vmath('SCALE', geo.outputs['Normal'], scale=17.0))
    wn = nb.n('ShaderNodeTexWhiteNoise', noise_dimensions='3D', i_Vector=cellv)
    r1 = wn.outputs['Value']
    wsep = nb.n('ShaderNodeSeparateColor', i_Color=wn.outputs['Color'])
    frac = nb.ctrl('window_frac')
    # lit windows cluster by floor and tenant (groups of 5 bays)
    tcell = nb.n('ShaderNodeCombineXYZ', i_X=nb.math('FLOOR', nb.math('DIVIDE', cu, 5.0)), i_Y=cv,
                 i_Z=nb.math('MULTIPLY', brand, 1000.0))
    tcv = nb.vmath('ADD', tcell.outputs[0], nb.vmath('SCALE', geo.outputs['Normal'], scale=31.0))
    tn = nb.n('ShaderNodeTexWhiteNoise', noise_dimensions='3D', i_Vector=tcv)
    rank = nb.math('ADD', nb.math('MULTIPLY', tn.outputs['Value'], 0.8), nb.math('MULTIPLY', wsep.outputs[1], 0.2))
    lit = nb.math('LESS_THAN', rank, frac)
    wem = nb.ctrl('window_emit')
    estr = nb.math('MULTIPLY', nb.math('MULTIPLY', lit, nb.math('MULTIPLY_ADD', r1, 0.6, 0.6)), wem)
    estr = nb.math('MULTIPLY', estr, nb.mix(style, 1.0, 0.55, dtype='FLOAT'))
    estr = nb.math('MULTIPLY', estr, win)
    # distance LOD: window grids fade into the wall with distance (kills dot repetition in aerials)
    lpd = nb.n('ShaderNodeLightPath').outputs['Ray Length']
    dfade = nb.n('ShaderNodeMapRange', i_Value=lpd, **{'i_From Min': 350.0, 'i_From Max': 2200.0, 'i_To Min': 1.0,
                                                        'i_To Max': 0.35}).outputs[0]
    estr = nb.math('MULTIPLY', estr, dfade)
    win = nb.math('MULTIPLY', win, nb.math('MULTIPLY_ADD', dfade, 0.6, 0.4))
    ecol = nb.ramp(wsep.outputs[2], [(0.0, (1.0, 0.62, 0.30)), (0.55, (1.0, 0.76, 0.48)), (0.8, (0.8, 0.9, 1.0))],
                   interp='CONSTANT')
    # wall: bcol with large-scale noise
    noise = nb.n('ShaderNodeTexNoise', i_Vector=geo.outputs['Position'], i_Scale=0.08, i_Detail=4.0)
    f = nb.n('ShaderNodeMapRange', i_Value=noise.outputs['Fac'], **{'i_To Min': 0.82, 'i_To Max': 1.15})
    wall = nb.mix(1.0, bc.outputs['Color'], f.outputs[0], blend='MULTIPLY')
    # glass colour: dark interior for masonry, tinted reflective for glass styles
    gl = nb.mix(style, (0.03, 0.033, 0.036, 1), bc.outputs['Color'])
    basec = nb.mix(win, wall, gl)
    metal = nb.math('MULTIPLY', win, nb.math('MULTIPLY', style, 0.85))
    rough = nb.mix(win, 0.8, nb.math('MULTIPLY_ADD', r1, 0.06, 0.02), dtype='FLOAT')
    spec = nb.mix(win, 0.35, 0.9, dtype='FLOAT')
    p = nb.principled(**{'Base Color': basec, 'Metallic': metal, 'Roughness': rough, 'Specular IOR Level': spec})
    nb.out(emission_add(nb, p.outputs[0], ecol, estr))
    return m


# ----------------------------------------------------------------- street
def m_asphalt(name):
    nb, m = _new(name)
    geo = nb.n('ShaderNodeNewGeometry')
    pos = geo.outputs['Position']
    sep = nb.n('ShaderNodeSeparateXYZ', i_Vector=pos)
    n1 = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=0.08, i_Detail=4.0)
    patches = nb.n('ShaderNodeTexVoronoi', i_Vector=pos, i_Scale=0.06)
    pf = nb.math('GREATER_THAN', patches.outputs['Distance'], 0.62)
    n2 = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=18.0, i_Detail=4.0)
    base = nb.ramp(n1.outputs['Fac'], [(0.3, (0.050, 0.050, 0.052)), (0.7, (0.085, 0.083, 0.08))])
    base = nb.mix(nb.math('MULTIPLY', pf, 0.7), base, (0.035, 0.035, 0.037, 1))
    fine = nb.n('ShaderNodeMapRange', i_Value=n2.outputs['Fac'], **{'i_To Min': 0.8, 'i_To Max': 1.2})
    base = nb.mix(1.0, base, fine.outputs[0], blend='MULTIPLY')
    # wheel tracks: darker oily bands. Avenue lanes along Y (|x|<10): tracks at lane centre +-0.8 m
    x = sep.outputs['X']
    lane = nb.math('FRACT', nb.math('DIVIDE', nb.math('ADD', x, 7.6), 3.3))
    tr = nb.math('LESS_THAN', nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('ABSOLUTE', nb.math('SUBTRACT', lane, 0.5)), 0.25)), 0.09)
    inav = nb.math('LESS_THAN', nb.math('ABSOLUTE', x), 10.0)
    tnoise = nb.n('ShaderNodeTexNoise', i_Vector=nb.vmath('MULTIPLY', pos, (1.0, 0.05, 1.0)), i_Scale=1.5)
    tr = nb.math('MULTIPLY', nb.math('MULTIPLY', tr, inav), tnoise.outputs['Fac'])
    base = nb.mix(nb.math('MULTIPLY', tr, 0.8), base, (0.025, 0.024, 0.024, 1))
    # wet sheen near curbs (|x| in 8.6..10): smoother
    wet = nb.n('ShaderNodeMapRange', i_Value=nb.math('ABSOLUTE', x), **{'i_From Min': 8.4, 'i_From Max': 9.9})
    wet = nb.math('MULTIPLY', wet.outputs[0], inav)
    wetn = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=0.4, i_Detail=3.0)
    wet = nb.math('MULTIPLY', wet, nb.math('GREATER_THAN', wetn.outputs['Fac'], 0.47))
    rnoise = nb.n('ShaderNodeMapRange', i_Value=n1.outputs['Fac'], **{'i_To Min': 0.28, 'i_To Max': 0.62})
    rough = nb.mix(wet, rnoise.outputs[0], 0.08, dtype='FLOAT')
    rough = nb.math('SUBTRACT', rough, nb.math('MULTIPLY', tr, 0.25))
    base = nb.mix(nb.math('MULTIPLY', wet, 0.5), base, (0.02, 0.02, 0.02, 1))
    # cracks: thin voronoi edge network masked by noise, sealed-crack tar lines, and potholes
    # cracks: noise-distorted (organic, not cellular) edge network, sparse
    dn = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=0.9, i_Detail=4.0)
    dpos = nb.vmath('ADD', pos, nb.vmath('SCALE', nb.vmath('SUBTRACT', dn.outputs['Color'], (0.5, 0.5, 0.5)), scale=2.2))
    cv = nb.n('ShaderNodeTexVoronoi', feature='DISTANCE_TO_EDGE', i_Vector=dpos, i_Scale=0.32)
    cm = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=0.07, i_Detail=2.0)
    crack = nb.math('MULTIPLY', nb.math('LESS_THAN', cv.outputs['Distance'], 0.01),
                    nb.math('GREATER_THAN', cm.outputs['Fac'], 0.6))
    # aggregate: small light stones + fine roughness variation
    ag = nb.n('ShaderNodeTexVoronoi', i_Vector=pos, i_Scale=70.0)
    stone = nb.math('MULTIPLY', nb.math('LESS_THAN', ag.outputs['Distance'], 0.22), 0.35)
    base = nb.mix(stone, base, (0.16, 0.155, 0.15, 1))
    # oil drips down the lane centres
    oil_n = nb.n('ShaderNodeTexNoise', i_Vector=nb.vmath('MULTIPLY', pos, (1.5, 0.4, 1.0)), i_Scale=1.2, i_Detail=3.0)
    lanec = nb.math('LESS_THAN', nb.math('ABSOLUTE', nb.math('SUBTRACT', lane, 0.5)), 0.12)
    oil = nb.math('MULTIPLY', nb.math('MULTIPLY', lanec, inav), nb.math('GREATER_THAN', oil_n.outputs['Fac'], 0.56))
    base = nb.mix(nb.math('MULTIPLY', oil, 0.75), base, (0.015, 0.014, 0.014, 1))
    base = nb.mix(nb.math('MULTIPLY', crack, 0.85), base, (0.012, 0.012, 0.012, 1))
    seal = nb.n('ShaderNodeTexVoronoi', feature='DISTANCE_TO_EDGE', i_Vector=pos, i_Scale=0.11)
    sealm = nb.math('MULTIPLY', nb.math('LESS_THAN', seal.outputs['Distance'], 0.012),
                    nb.math('GREATER_THAN', cm.outputs['Fac'], 0.62))
    base = nb.mix(nb.math('MULTIPLY', sealm, 0.9), base, (0.018, 0.018, 0.02, 1))
    rough = nb.mix(sealm, rough, 0.3, dtype='FLOAT')
    rough = nb.mix(nb.math('MULTIPLY', oil, 0.8), rough, 0.18, dtype='FLOAT')
    rough = nb.math('ADD', rough, nb.math('MULTIPLY', stone, -0.25))
    hb = nb.math('ADD', nb.math('ADD', n2.outputs['Fac'], nb.math('MULTIPLY', crack, -1.5)), nb.math('MULTIPLY', stone, 0.8))
    bump = nb.n('ShaderNodeBump', i_Strength=0.3, i_Distance=0.01, i_Height=hb)
    p = nb.principled(**{'Base Color': base, 'Roughness': rough, 'Normal': bump.outputs['Normal']})
    nb.out(p.outputs[0])
    return m


def m_sidewalk(name):
    nb, m = _new(name)
    geo = nb.n('ShaderNodeNewGeometry')
    pos = geo.outputs['Position']
    br = nb.n('ShaderNodeTexBrick', i_Vector=pos, i_Color1=(1, 1, 1, 1), i_Color2=(0.86, 0.85, 0.83, 1),
              i_Mortar=(0.5, 0.5, 0.5, 1), i_Scale=1.0, **{'i_Mortar Size': 0.012, 'i_Brick Width': 1.5,
                                                         'i_Row Height': 1.5, 'i_Mortar Smooth': 0.2})
    br.offset = 0.0
    n1 = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=0.3, i_Detail=5.0)
    stain = nb.ramp(n1.outputs['Fac'], [(0.35, (0.36, 0.35, 0.33)), (0.65, (0.24, 0.235, 0.225))])
    base = nb.mix(1.0, stain, br.outputs['Color'], blend='MULTIPLY')
    gum = nb.n('ShaderNodeTexVoronoi', i_Vector=pos, i_Scale=6.0)
    gm = nb.math('LESS_THAN', gum.outputs['Distance'], 0.05)
    base = nb.mix(gm, base, (0.12, 0.12, 0.12, 1))
    cv = nb.n('ShaderNodeTexVoronoi', feature='DISTANCE_TO_EDGE', i_Vector=pos, i_Scale=1.3)
    cm = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=0.35, i_Detail=2.0)
    crack = nb.math('MULTIPLY', nb.math('LESS_THAN', cv.outputs['Distance'], 0.012),
                    nb.math('GREATER_THAN', cm.outputs['Fac'], 0.58))
    base = nb.mix(nb.math('MULTIPLY', crack, 0.8), base, (0.05, 0.05, 0.05, 1))
    hb = nb.math('ADD', br.outputs['Fac'], nb.math('MULTIPLY', crack, -0.6))
    bump = nb.n('ShaderNodeBump', i_Strength=0.3, i_Distance=0.005, i_Height=hb)
    p = nb.principled(**{'Base Color': base, 'Roughness': 0.85, 'Normal': bump.outputs['Normal']})
    nb.out(p.outputs[0])
    return m


def m_water(name):
    nb, m = _new(name)
    geo = nb.n('ShaderNodeNewGeometry')
    pos = nb.vmath('MULTIPLY', geo.outputs['Position'], (1.0, 1.0, 1.0))
    w = nb.n('ShaderNodeTexNoise', i_Vector=nb.vmath('MULTIPLY', pos, (0.25, 0.08, 1.0)), i_Scale=1.0, i_Detail=8.0,
             i_Roughness=0.55)
    w2 = nb.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Y', i_Vector=pos, i_Scale=0.05,
              i_Distortion=8.0, i_Detail=4.0)
    hgt = nb.math('ADD', w.outputs['Fac'], nb.math('MULTIPLY', w2.outputs['Fac'], 0.3))
    bump = nb.n('ShaderNodeBump', i_Strength=0.35, i_Distance=0.3, i_Height=hgt)
    p = nb.principled(**{'Base Color': (0.012, 0.022, 0.026, 1), 'Roughness': 0.09, 'IOR': 1.333,
                         'Normal': bump.outputs['Normal'], 'Specular IOR Level': 1.0})
    nb.out(p.outputs[0])
    return m


def _paint_layers(nb, col, metal=0.5, rough=0.32):
    """Clearcoat paint with metallic flake and road dirt on the lower panels (object z)."""
    tc = nb.n('ShaderNodeTexCoord')
    geo = nb.n('ShaderNodeNewGeometry')
    oz = nb.n('ShaderNodeSeparateXYZ', i_Vector=tc.outputs['Object']).outputs['Z']
    flake = nb.n('ShaderNodeTexVoronoi', i_Vector=geo.outputs['Position'], i_Scale=900.0)
    fn = nb.n('ShaderNodeBump', i_Strength=0.08, i_Distance=0.0005, i_Height=flake.outputs['Distance'])
    dn = nb.n('ShaderNodeTexNoise', i_Vector=nb.vmath('MULTIPLY', tc.outputs['Object'], (6.0, 2.0, 14.0)), i_Scale=1.0,
              i_Detail=4.0)
    low = nb.n('ShaderNodeMapRange', i_Value=oz, **{'i_From Min': 0.75, 'i_From Max': 0.25}).outputs[0]
    dirt = nb.math('MULTIPLY', low, nb.n('ShaderNodeMapRange', i_Value=dn.outputs['Fac'],
                                          **{'i_From Min': 0.35, 'i_From Max': 0.7}).outputs[0], clamp=True)
    base = nb.mix(nb.math('MULTIPLY', dirt, 0.75), col, (0.14, 0.12, 0.10, 1))
    p = nb.principled(**{'Base Color': base, 'Metallic': nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, dirt), metal),
                         'Roughness': nb.math('ADD', rough, nb.math('MULTIPLY', dirt, 0.5)), 'Normal': fn.outputs['Normal'],
                         'Coat Weight': nb.math('SUBTRACT', 1.0, dirt), 'Coat Roughness': 0.025})
    return p


def m_car_paint(name):
    nb, m = _new(name)
    oi = nb.n('ShaderNodeObjectInfo')
    col = nb.ramp(oi.outputs['Random'], [
        (0.0, (0.02, 0.02, 0.022)), (0.16, (0.55, 0.56, 0.57)), (0.30, (0.80, 0.80, 0.78)),
        (0.42, (0.10, 0.11, 0.13)), (0.52, (0.25, 0.02, 0.02)), (0.60, (0.03, 0.06, 0.15)),
        (0.68, (0.30, 0.30, 0.31)), (0.78, (0.85, 0.85, 0.84)), (0.88, (0.06, 0.12, 0.08)),
        (0.94, (0.18, 0.12, 0.08))], interp='CONSTANT')
    nb.out(_paint_layers(nb, col).outputs[0])
    return m


def _paint_mat(name, col, metal):
    nb, m = _new(name)
    nb.out(_paint_layers(nb, _c4(col), metal=metal).outputs[0])
    return m


def m_car_glass(name):
    """Tinted automotive glass: Fresnel reflection, see-through near normal incidence."""
    nb, m = _new(name)
    fr = nb.n('ShaderNodeLayerWeight', i_Blend=0.3).outputs['Fresnel']
    g = nb.principled(**{'Base Color': (0.01, 0.012, 0.014, 1), 'Roughness': 0.03, 'Specular IOR Level': 1.0})
    tr = nb.n('ShaderNodeBsdfTransparent', i_Color=(0.42, 0.46, 0.46, 1))
    mx = nb.n('ShaderNodeMixShader', i_Fac=nb.math('MINIMUM', nb.math('MULTIPLY_ADD', fr, 1.4, 0.35), 1.0))
    nb.link(tr.outputs[0], mx.inputs[1])
    nb.link(g.outputs[0], mx.inputs[2])
    nb.out(mx.outputs[0])
    return m


def m_leaves(name):
    nb, m = _new(name)
    oi = nb.n('ShaderNodeObjectInfo')
    geo = nb.n('ShaderNodeNewGeometry')
    n = nb.n('ShaderNodeTexNoise', i_Vector=geo.outputs['Position'], i_Scale=4.0)
    fac = nb.math('ADD', nb.math('MULTIPLY', oi.outputs['Random'], 0.5), nb.math('MULTIPLY', n.outputs['Fac'], 0.6))
    col = nb.ramp(fac, [(0.15, (0.035, 0.07, 0.015)), (0.5, (0.07, 0.11, 0.025)), (0.85, (0.16, 0.15, 0.04))])
    p = nb.principled(**{'Base Color': col, 'Roughness': 0.55, 'Specular IOR Level': 0.4,
                         'Transmission Weight': 0.0, 'Subsurface Weight': 0.0})
    tr = nb.n('ShaderNodeBsdfTranslucent', i_Color=nb.mix(1.0, col, (1.4, 1.6, 0.6, 1), blend='MULTIPLY'))
    mx = nb.n('ShaderNodeMixShader', i_Fac=0.35)
    nb.link(p.outputs[0], mx.inputs[1])
    nb.link(tr.outputs[0], mx.inputs[2])
    nb.out(mx.outputs[0])
    return m


def m_steam(name):
    """Homogeneous low-density scattering puffs (overlaps add up toward the core)."""
    nb, m = _new(name)
    v = nb.n('ShaderNodeVolumePrincipled', i_Density=0.55, i_Color=(0.95, 0.95, 0.95, 1), i_Anisotropy=0.45)
    nb.out(volume=v.outputs[0])
    return m


def m_louvre(name):
    nb, m = _new(name)
    geo = nb.n('ShaderNodeNewGeometry')
    w = nb.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z', i_Vector=geo.outputs['Position'],
             i_Scale=0.9, i_Distortion=0.0, **{'i_Detail': 0.0})
    w.wave_profile = 'SAW'
    bump = nb.n('ShaderNodeBump', i_Strength=0.6, i_Distance=0.03, i_Height=w.outputs['Fac'])
    col = nb.mix(w.outputs['Fac'], (0.05, 0.05, 0.05, 1), (0.16, 0.16, 0.15, 1))
    p = nb.principled(**{'Base Color': col, 'Roughness': 0.5, 'Metallic': 0.6, 'Normal': bump.outputs['Normal']})
    nb.out(p.outputs[0])
    return m


def m_tower_spandrel(name):
    """Dark bronze spandrel panels with Deco chevron relief (bump)."""
    nb, m = _new(name)
    geo, sep, nsep, h = facade_coords(nb)
    z = sep.outputs['Z']
    tri = nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('FRACT', nb.math('DIVIDE', h, 0.66)), 0.5))
    chev = nb.math('FRACT', nb.math('DIVIDE', nb.math('ADD', z, nb.math('MULTIPLY', tri, 0.5)), 0.22))
    ridge = nb.math('ABSOLUTE', nb.math('SUBTRACT', chev, 0.5))
    # vertical flutes on alternate panels
    flute = nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('FRACT', nb.math('DIVIDE', h, 0.11)), 0.5))
    hgt = nb.math('ADD', ridge, nb.math('MULTIPLY', flute, 0.25))
    n = nb.n('ShaderNodeTexNoise', i_Vector=geo.outputs['Position'], i_Scale=6.0, i_Detail=6.0)
    g = grime(nb, geo, sep, 0.45)
    base = nb.ramp(n.outputs['Fac'], [(0.3, (0.07, 0.05, 0.03)), (0.7, (0.13, 0.09, 0.05))])
    base = nb.mix(nb.math('MULTIPLY', ridge, 0.6), base, (0.06, 0.05, 0.04, 1))
    base = nb.mix(g, base, (0.05, 0.045, 0.04, 1), blend='MULTIPLY')
    bump = nb.n('ShaderNodeBump', i_Strength=0.55, i_Distance=0.02, i_Height=hgt)
    p = nb.principled(**{'Base Color': base, 'Metallic': 0.7, 'Roughness': nb.math('ADD', 0.45, nb.math('MULTIPLY', g, 0.3)),
                         'Normal': bump.outputs['Normal']})
    nb.out(p.outputs[0])
    return m


def m_gargoyle(name):
    """Weathered limestone: crevice crust (AO), rain streaks, bird-stain streaks, pitting."""
    nb, m = _new(name)
    geo = nb.n('ShaderNodeNewGeometry')
    pos = geo.outputs['Position']
    sep = nb.n('ShaderNodeSeparateXYZ', i_Vector=pos)
    n1 = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=3.0, i_Detail=10.0, i_Roughness=0.62)
    n2 = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=28.0, i_Detail=6.0, i_Roughness=0.7)
    vor = nb.n('ShaderNodeTexVoronoi', i_Vector=pos, i_Scale=55.0)
    pit = nb.math('LESS_THAN', vor.outputs['Distance'], 0.12)
    ao = nb.n('ShaderNodeAmbientOcclusion', samples=4, i_Distance=0.35)
    crev = nb.n('ShaderNodeMapRange', i_Value=ao.outputs['AO'], **{'i_From Min': 0.5, 'i_From Max': 0.98,
                                                                     'i_To Min': 1.0, 'i_To Max': 0.0})
    streak_v = nb.vmath('MULTIPLY', pos, (4.0, 4.0, 0.5))
    sn = nb.n('ShaderNodeTexNoise', i_Vector=streak_v, i_Scale=2.0, i_Detail=5.0)
    streak = nb.n('ShaderNodeMapRange', i_Value=sn.outputs['Fac'], **{'i_From Min': 0.6, 'i_From Max': 0.75})
    # streaks only on downward/vertical faces (rain runs down), weaker overall
    nz = nb.n('ShaderNodeSeparateXYZ', i_Vector=geo.outputs['Normal'])
    vertf = nb.math('LESS_THAN', nz.outputs['Z'], 0.6)
    streak = nb.n('ShaderNodeMath', operation='MULTIPLY', i_0=streak.outputs[0], i_1=vertf)
    gn = nb.n('ShaderNodeTexNoise', i_Vector=nb.vmath('MULTIPLY', pos, (9.0, 9.0, 0.6)), i_Scale=1.7, i_Detail=4.0)
    guano = nb.n('ShaderNodeMapRange', i_Value=gn.outputs['Fac'], **{'i_From Min': 0.66, 'i_From Max': 0.72})
    base = nb.ramp(n1.outputs['Fac'], [(0.25, (0.17, 0.16, 0.145)), (0.5, (0.33, 0.31, 0.27)), (0.75, (0.45, 0.42, 0.36))])
    base = nb.mix(nb.math('MULTIPLY', n2.outputs['Fac'], 0.4), base, (0.36, 0.33, 0.30, 1))
    base = nb.mix(nb.math('MULTIPLY', streak.outputs[0], 0.7), base, (0.10, 0.09, 0.08, 1), blend='MULTIPLY')
    base = nb.mix(nb.math('MULTIPLY', crev.outputs[0], 0.85), base, (0.035, 0.032, 0.03, 1))
    base = nb.mix(nb.math('MULTIPLY', pit, 0.5), base, (0.08, 0.075, 0.07, 1))
    base = nb.mix(nb.math('MULTIPLY', guano.outputs[0], 0.85), base, (0.70, 0.69, 0.64, 1))
    lic = nb.n('ShaderNodeTexVoronoi', i_Vector=pos, i_Scale=9.0)
    lichen = nb.math('MULTIPLY', nb.math('LESS_THAN', lic.outputs['Distance'], 0.18),
                     nb.math('GREATER_THAN', n1.outputs['Fac'], 0.55))
    base = nb.mix(nb.math('MULTIPLY', lichen, 0.5), base, (0.30, 0.31, 0.22, 1))
    hgt = nb.math('ADD', nb.math('MULTIPLY', n1.outputs['Fac'], 0.6), nb.math('MULTIPLY', n2.outputs['Fac'], 0.35))
    hgt = nb.math('SUBTRACT', hgt, nb.math('MULTIPLY', pit, 0.25))
    bump = nb.n('ShaderNodeBump', i_Strength=1.0, i_Distance=0.02, i_Height=hgt)
    rough = nb.math('ADD', 0.72, nb.math('MULTIPLY', guano.outputs[0], -0.25))
    p = nb.principled(**{'Base Color': base, 'Roughness': rough, 'Normal': bump.outputs['Normal'],
                         'Specular IOR Level': 0.4})
    nb.out(p.outputs[0])
    return m


def m_roof(name):
    """Roof types picked per building (bcol alpha): tar, gravel ballast, white membrane, green."""
    nb, m = _new(name)
    bc = nb.attr('bcol')
    geo = nb.n('ShaderNodeNewGeometry')
    pos = geo.outputs['Position']
    kind = bc.outputs['Alpha']
    typ = nb.ramp(kind, [(0.0, (0.055, 0.052, 0.05)), (0.35, (0.20, 0.19, 0.175)), (0.72, (0.33, 0.33, 0.32)),
                         (0.94, (0.05, 0.09, 0.03))], interp='CONSTANT')
    sp = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=25.0, i_Detail=2.0)
    spk = nb.n('ShaderNodeMapRange', i_Value=sp.outputs['Fac'], **{'i_To Min': 0.7, 'i_To Max': 1.3})
    br = nb.n('ShaderNodeTexBrick', i_Vector=pos, i_Color1=(1, 1, 1, 1), i_Color2=(0.93, 0.93, 0.93, 1),
              i_Mortar=(0.7, 0.7, 0.7, 1), i_Scale=1.0, **{'i_Mortar Size': 0.03, 'i_Brick Width': 10.0, 'i_Row Height': 1.9})
    big = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=0.15, i_Detail=4.0)
    stain = nb.n('ShaderNodeMapRange', i_Value=big.outputs['Fac'], **{'i_To Min': 0.6, 'i_To Max': 1.15})
    base = nb.mix(1.0, typ, spk.outputs[0], blend='MULTIPLY')
    base = nb.mix(1.0, base, br.outputs['Color'], blend='MULTIPLY')
    base = nb.mix(1.0, base, stain.outputs[0], blend='MULTIPLY')
    p = nb.principled(**{'Base Color': base, 'Roughness': 0.85})
    nb.out(p.outputs[0])
    return m


def m_steel_prow(name):
    """Weathered stainless/nickel steel: soft anisotropic brushed reflections, streak staining
    running down from edges, warm tarnish patches."""
    nb, m = _new(name)
    geo = nb.n('ShaderNodeNewGeometry')
    pos = geo.outputs['Position']
    streak_v = nb.vmath('MULTIPLY', pos, (3.0, 3.0, 0.25))
    sn = nb.n('ShaderNodeTexNoise', i_Vector=streak_v, i_Scale=2.5, i_Detail=5.0)
    streak = nb.n('ShaderNodeMapRange', i_Value=sn.outputs['Fac'], **{'i_From Min': 0.55, 'i_From Max': 0.78})
    tn = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=3.0, i_Detail=6.0)
    tarn = nb.n('ShaderNodeMapRange', i_Value=tn.outputs['Fac'], **{'i_From Min': 0.55, 'i_From Max': 0.7})
    brush = nb.n('ShaderNodeTexNoise', i_Vector=nb.vmath('MULTIPLY', pos, (2.0, 2.0, 120.0)), i_Scale=4.0, i_Detail=2.0)
    base = nb.mix(tarn.outputs[0], (0.60, 0.59, 0.56, 1), (0.42, 0.36, 0.28, 1))
    base = nb.mix(nb.math('MULTIPLY', streak.outputs[0], 0.45), base, (0.2, 0.19, 0.17, 1))
    rough = nb.math('ADD', nb.math('MULTIPLY', streak.outputs[0], 0.25), nb.math('MULTIPLY_ADD', brush.outputs['Fac'], 0.12, 0.14))
    bump = nb.n('ShaderNodeBump', i_Strength=0.08, i_Distance=0.002, i_Height=brush.outputs['Fac'])
    p = nb.principled(**{'Base Color': base, 'Metallic': 1.0, 'Roughness': rough, 'Anisotropic': 0.55,
                         'Normal': bump.outputs['Normal']})
    nb.out(p.outputs[0])
    return m


def m_paint_worn(name, col):
    """Road paint worn by tyres: noisy loss patches showing dark asphalt, rougher edges, grime."""
    nb, m = _new(name)
    geo = nb.n('ShaderNodeNewGeometry')
    pos = geo.outputs['Position']
    n1 = nb.n('ShaderNodeTexNoise', i_Vector=nb.vmath('MULTIPLY', pos, (3.0, 0.8, 3.0)), i_Scale=1.6, i_Detail=6.0)
    n2 = nb.n('ShaderNodeTexNoise', i_Vector=pos, i_Scale=14.0, i_Detail=3.0)
    wear = nb.math('GREATER_THAN', nb.math('ADD', n1.outputs['Fac'], nb.math('MULTIPLY', n2.outputs['Fac'], 0.35)), 0.78)
    dirt = nb.n('ShaderNodeMapRange', i_Value=n1.outputs['Fac'], **{'i_To Min': 0.65, 'i_To Max': 1.0})
    base = nb.mix(1.0, _c4(col), dirt.outputs[0], blend='MULTIPLY')
    base = nb.mix(wear, base, (0.05, 0.05, 0.05, 1))
    p = nb.principled(**{'Base Color': base, 'Roughness': nb.mix(wear, 0.55, 0.85, dtype='FLOAT')})
    nb.out(p.outputs[0])
    return m


def m_contact_shadow(name):
    """Soft ambient-occlusion decal under vehicles/props: dark centre fading to transparent at the UV edge."""
    nb, m = _new(name)
    uv = nb.n('ShaderNodeUVMap', uv_map="UVMap")
    sp = nb.n('ShaderNodeSeparateXYZ', i_Vector=uv.outputs['UV'])
    du = nb.math('ABSOLUTE', nb.math('SUBTRACT', sp.outputs['X'], 0.5))
    dv = nb.math('ABSOLUTE', nb.math('SUBTRACT', sp.outputs['Y'], 0.5))
    d = nb.math('MAXIMUM', nb.math('MULTIPLY', du, 2.0), nb.math('MULTIPLY', dv, 2.0))
    a = nb.n('ShaderNodeMapRange', i_Value=d, **{'i_From Min': 0.55, 'i_From Max': 1.0, 'i_To Min': 0.8, 'i_To Max': 0.0}).outputs[0]
    dk = nb.principled(**{'Base Color': (0.0, 0.0, 0.0, 1), 'Roughness': 1.0, 'Specular IOR Level': 0.0})
    tr = nb.n('ShaderNodeBsdfTransparent')
    mx = nb.n('ShaderNodeMixShader', i_Fac=a)
    nb.link(tr.outputs[0], mx.inputs[1])
    nb.link(dk.outputs[0], mx.inputs[2])
    nb.out(mx.outputs[0])
    return m


BUILDERS = {}


def _reg():
    B = BUILDERS
    B['window'] = m_window
    B['curtain'] = m_curtain
    B['cw_spandrel'] = m_cw_spandrel
    B['limestone'] = lambda n: m_stone(n)
    B['tower_stone'] = lambda n: m_stone(n, ashlar=(1.25, 0.5), rough=0.72, grime_k=0.55, bevel=True, tower=True)
    B['brick'] = m_brick
    B['trim'] = lambda n: m_simple(n, (0.58, 0.54, 0.47), rough=0.7, noise_amt=0.2, grime_k=0.5, bump=0.2)
    B['terracotta'] = lambda n: m_simple(n, (0.62, 0.50, 0.38), rough=0.6, noise_amt=0.2, grime_k=0.35, bump=0.1)
    B['metal_dark'] = lambda n: m_simple(n, (0.035, 0.032, 0.03), rough=0.38, metal=0.8, noise_amt=0.3, spec=0.6)
    B['metal_bronze'] = lambda n: m_simple(n, (0.20, 0.13, 0.07), rough=0.35, metal=1.0, noise_amt=0.3, grime_k=0.3)
    B['metal_alu'] = lambda n: m_simple(n, (0.62, 0.63, 0.64), rough=0.28, metal=1.0, noise_amt=0.1)
    B['steel_deco'] = lambda n: m_simple(n, (0.70, 0.71, 0.72), rough=0.18, metal=1.0, noise_amt=0.15, grime_k=0.25)
    B['concrete'] = lambda n: m_simple(n, (0.42, 0.41, 0.39), rough=0.85, noise_amt=0.25, grime_k=0.4, bump=0.15)
    B['panel'] = lambda n: m_simple(n, None, rough=0.55, use_bcol=True, noise_amt=0.12, grime_k=0.25)
    B['wall_bcol'] = lambda n: m_simple(n, None, rough=0.8, use_bcol=True, noise_amt=0.2, grime_k=0.35)
    B['roof'] = m_roof
    B['far'] = m_far
    B['asphalt'] = m_asphalt
    B['sidewalk'] = m_sidewalk
    B['curb'] = lambda n: m_simple(n, (0.33, 0.33, 0.34), rough=0.6, noise_amt=0.3, noise_scale=12.0, bump=0.2)
    B['paint_white'] = lambda n: m_paint_worn(n, (0.62, 0.62, 0.6))
    B['paint_yellow'] = lambda n: m_paint_worn(n, (0.65, 0.45, 0.06))
    B['bike_green'] = lambda n: m_paint_worn(n, (0.08, 0.25, 0.10))
    B['water'] = m_water
    B['car_paint'] = m_car_paint
    B['cab_yellow'] = lambda n: _paint_mat(n, (0.85, 0.55, 0.03), 0.1)
    B['bus_paint'] = lambda n: m_simple(n, (0.75, 0.76, 0.78), rough=0.35, coat=0.6, noise_amt=0.05)
    B['car_glass'] = m_car_glass
    B['rubber'] = lambda n: m_simple(n, (0.02, 0.02, 0.02), rough=0.8, noise_amt=0.1)
    B['chrome'] = lambda n: m_simple(n, (0.8, 0.8, 0.8), rough=0.12, metal=1.0, noise_amt=0.0)
    B['headlight'] = lambda n: m_emit(n, (1.0, 0.93, 0.8), 'car_emit', 4.0)
    B['taillight'] = lambda n: m_emit(n, (1.0, 0.03, 0.01), 'car_emit', 2.6, bsdf_color=(0.4, 0.02, 0.02))
    B['lamp_emit'] = lambda n: m_emit(n, (1.0, 0.78, 0.5), 'street_emit', 12.0, bsdf_color=(0.9, 0.85, 0.7))
    B['sig_red'] = lambda n: m_emit(n, (1.0, 0.05, 0.02), 'street_emit', 18.0, bsdf_color=(0.3, 0.02, 0.02))
    B['sig_green'] = lambda n: m_emit(n, (0.1, 1.0, 0.55), 'street_emit', 14.0, bsdf_color=(0.02, 0.2, 0.1))
    B['sig_amber'] = lambda n: m_emit(n, (1.0, 0.5, 0.05), 'street_emit', 10.0, bsdf_color=(0.3, 0.15, 0.02))
    B['sign_warm'] = lambda n: m_emit(n, (1.0, 0.55, 0.2), 'street_emit', 8.0, bsdf_color=(0.6, 0.4, 0.2))
    B['sign_white'] = lambda n: m_emit(n, (0.95, 0.95, 1.0), 'street_emit', 6.0, bsdf_color=(0.8, 0.8, 0.8))
    B['sign_red'] = lambda n: m_emit(n, (1.0, 0.08, 0.06), 'street_emit', 8.0, bsdf_color=(0.6, 0.05, 0.05))
    B['sign_blue'] = lambda n: m_emit(n, (0.15, 0.45, 1.0), 'street_emit', 8.0, bsdf_color=(0.05, 0.1, 0.5))
    B['bark'] = lambda n: m_simple(n, (0.06, 0.05, 0.04), rough=0.9, noise_amt=0.4, noise_scale=8.0, bump=0.4)
    B['leaves'] = m_leaves
    B['fabric_green'] = lambda n: m_simple(n, (0.04, 0.12, 0.07), rough=0.9, noise_amt=0.1)
    B['fabric_red'] = lambda n: m_simple(n, (0.25, 0.03, 0.03), rough=0.9, noise_amt=0.1)
    B['fabric_navy'] = lambda n: m_simple(n, (0.02, 0.03, 0.08), rough=0.9, noise_amt=0.1)
    B['fabric_cream'] = lambda n: m_simple(n, (0.6, 0.55, 0.45), rough=0.9, noise_amt=0.1)
    B['shed_green'] = lambda n: m_simple(n, (0.05, 0.13, 0.08), rough=0.6, noise_amt=0.2, grime_k=0.3)
    B['plywood'] = lambda n: m_simple(n, (0.35, 0.26, 0.16), rough=0.85, noise_amt=0.3, noise_scale=6)
    B['steam'] = m_steam
    B['skin'] = lambda n: m_simple(n, (0.35, 0.22, 0.16), rough=0.6, noise_amt=0.2)
    B['cloth_dark'] = lambda n: m_simple(n, (0.04, 0.04, 0.045), rough=0.9, noise_amt=0.2)
    B['cloth_var'] = m_cloth_var
    B['glass_clear'] = m_glass_clear
    B['shop'] = m_shop
    B['louvre'] = m_louvre
    B['contact_shadow'] = m_contact_shadow
    B['black_trim'] = lambda n: m_simple(n, (0.02, 0.02, 0.022), rough=0.45, noise_amt=0.2, noise_scale=8.0, spec=0.4)
    B['hvac_paint'] = lambda n: m_simple(n, (0.33, 0.32, 0.29), rough=0.55, metal=0.2, noise_amt=0.2, grime_k=0.4)
    B['tower_spandrel'] = m_tower_spandrel
    B['gargoyle'] = m_gargoyle
    B['steel_prow'] = m_steel_prow
    B['flood'] = lambda n: m_emit(n, (1.0, 0.82, 0.6), 'street_emit', 3.0, bsdf_color=(0.6, 0.55, 0.5))


def m_cloth_var(name):
    nb, m = _new(name)
    oi = nb.n('ShaderNodeObjectInfo')
    col = nb.ramp(oi.outputs['Random'], [(0.0, (0.03, 0.03, 0.035)), (0.3, (0.25, 0.22, 0.18)), (0.5, (0.05, 0.07, 0.15)),
                                         (0.7, (0.4, 0.05, 0.04)), (0.85, (0.5, 0.5, 0.48))], interp='CONSTANT')
    p = nb.principled(**{'Base Color': col, 'Roughness': 0.85})
    nb.out(p.outputs[0])
    return m


def m_glass_clear(name):
    nb, m = _new(name)
    p = nb.principled(**{'Base Color': (0.8, 0.85, 0.85, 1), 'Roughness': 0.02, 'Transmission Weight': 1.0,
                         'IOR': 1.45, 'Thin Wall': True})
    nb.out(p.outputs[0])
    return m


def m_shop(name):
    """Storefront glass: always-lit warm interiors with depth variation."""
    nb, m = _new(name)
    win = nb.attr('win')
    sep = nb.n('ShaderNodeSeparateColor', i_Color=win.outputs['Color'])
    uv = nb.n('ShaderNodeUVMap', uv_map="UVMap")
    uvs = nb.n('ShaderNodeSeparateXYZ', i_Vector=uv.outputs['UV'])
    geo = nb.n('ShaderNodeNewGeometry')
    n = nb.n('ShaderNodeTexNoise', i_Vector=geo.outputs['Position'], i_Scale=0.9, i_Detail=3.0)
    shelf = nb.n('ShaderNodeTexWave', i_Vector=geo.outputs['Position'], wave_type='BANDS', bands_direction='Z',
                 i_Scale=1.3, i_Distortion=0.0)
    inner = nb.math('MULTIPLY', n.outputs['Fac'], nb.math('MULTIPLY_ADD', shelf.outputs['Fac'], 0.5, 0.7))
    ecol = nb.ramp(sep.outputs[3] if len(sep.outputs) > 3 else win.outputs['Alpha'],
                   [(0.0, (1.0, 0.70, 0.40)), (0.6, (1.0, 0.85, 0.65)), (0.85, (0.85, 0.92, 1.0))], interp='CONSTANT')
    s = nb.math('MULTIPLY', nb.math('MULTIPLY_ADD', sep.outputs[0], 1.0, 0.6), inner)
    s = nb.math('MULTIPLY', s, nb.math('ADD', nb.ctrl('street_emit'), 1.2))
    wr = nb.n('ShaderNodeSeparateColor', i_Color=nb.attr('wroom').outputs['Color']).outputs[0]
    wr = nb.math('MULTIPLY', wr, room_lod(nb))
    s = nb.math('MULTIPLY', s, nb.math('SUBTRACT', 1.0, wr))
    p = nb.principled(**{'Base Color': (0.02, 0.02, 0.02, 1), 'Roughness': 0.03, 'IOR': 1.52})
    sh = emission_add(nb, p.outputs[0], ecol, s)
    fr_ = nb.n('ShaderNodeFresnel', i_IOR=1.52).outputs[0]
    tfac = nb.math('MULTIPLY', wr, nb.math('SUBTRACT', 1.0, nb.math('MINIMUM', nb.math('MULTIPLY_ADD', fr_, 2.5, 0.08), 1.0)))
    tr = nb.n('ShaderNodeBsdfTransparent', i_Color=(0.85, 0.88, 0.86, 1))
    mx = nb.n('ShaderNodeMixShader', i_Fac=tfac)
    nb.link(sh, mx.inputs[1])
    nb.link(tr.outputs[0], mx.inputs[2])
    nb.out(mx.outputs[0])
    return m


_reg()


def optimise(max_detail=3.0, keep=('gargoyle', 'tower_stone', 'tower_spandrel', 'water')):
    """Cap fBm octaves on materials that are never seen up close (noise detail is a big
    part of shading cost on CPU)."""
    for name, m in _cache.items():
        if name in keep or not m.node_tree:
            continue
        for n in m.node_tree.nodes:
            if n.type == 'TEX_NOISE' and n.inputs['Detail'].default_value > max_detail:
                n.inputs['Detail'].default_value = max_detail
