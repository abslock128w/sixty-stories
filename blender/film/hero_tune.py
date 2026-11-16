"""hero_tune: hero-specific per-shot colour tuning (film-owned, separate from looks).

Called by build_film.py after the hero is appended and animated; not part of any look
module. The values below are for Vesper v1 (graphite suit read pale grey from above in s3);
set them for the v2 costume once hero.blend is final.
"""
import bpy

import plan as PL


def log(*a):
    print('[hero_tune]', *a, flush=True)


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


# suit look correction (film-side only): the hero's sheen / coat read pale grey when the
# sky lights him from above (s3). Darken sheen tint, scale sheen + specular, soften coat.
SUIT_FIX = {
    'HERO_suit': dict(sheen_tint=(0.10, 0.10, 0.11), sheen_mul=0.45, spec_mul=0.55),
    'HERO_strap': dict(sheen_tint=(0.10, 0.10, 0.11), sheen_mul=0.4),
    'HERO_webbing': dict(sheen_tint=(0.10, 0.10, 0.11), sheen_mul=0.4),
    'HERO_gaiter': dict(sheen_tint=(0.10, 0.10, 0.11), sheen_mul=0.4),
    'HERO_helmet_shell': dict(sheen_tint=(0.12, 0.12, 0.13), sheen_mul=0.5, coat_mul=0.7),
    'HERO_armor': dict(coat_mul=0.5, coat_rough=0.18),
    'HERO_shoe': dict(sheen_tint=(0.10, 0.10, 0.11), sheen_mul=0.5),
}


def _scale_input(nt, node, name, mul):
    s = node.inputs.get(name)
    if s is None:
        return
    if not s.is_linked:
        s.default_value = s.default_value * mul
        return
    lk = s.links[0]
    m = nt.nodes.new('ShaderNodeMath')
    m.operation = 'MULTIPLY'
    m.inputs[1].default_value = mul
    m.location = (node.location.x - 180, node.location.y - 200)
    nt.links.new(lk.from_socket, m.inputs[0])
    nt.links.new(m.outputs[0], s)


# per-shot darkening (base colour, specular, coat multipliers), keyed CONSTANT per shot:
# seen from above in the sunlit canyon (s3) the graphite suit read pale grey
SUIT_DARK = {'s1': (1.0, 1.0), 's2': (1.0, 1.0), 's3': (0.2, 0.08), 's4': (0.5, 0.35),
             's5': (0.5, 0.35), 's6': (1.0, 1.0)}   # Vesper v1 values; re-tune for v2
SUIT_DARK_MATS = ('HERO_suit', 'HERO_armor', 'HERO_helmet_shell', 'HERO_strap', 'HERO_shoe')


def fix_suit(rig):
    mats = {s.material for o in rig.children for s in o.material_slots if s.material}
    for mat in mats:
        base = mat.name.split('.')[0]
        fx = SUIT_FIX.get(base)
        if not mat.node_tree:
            continue
        nt = mat.node_tree
        for n in [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED']:
            if fx:
                if 'sheen_tint' in fx and not n.inputs['Sheen Tint'].is_linked:
                    n.inputs['Sheen Tint'].default_value = fx['sheen_tint'] + (1.0,)
                if 'sheen_mul' in fx:
                    _scale_input(nt, n, 'Sheen Weight', fx['sheen_mul'])
                if 'spec_mul' in fx:
                    _scale_input(nt, n, 'Specular IOR Level', fx['spec_mul'])
                if 'coat_mul' in fx:
                    _scale_input(nt, n, 'Coat Weight', fx['coat_mul'])
                if 'coat_rough' in fx and not n.inputs['Coat Roughness'].is_linked:
                    n.inputs['Coat Roughness'].default_value = fx['coat_rough']
            if base in SUIT_DARK_MATS:
                _dark_keys(nt, n)
        log('suit fix', mat.name)


def _dark_keys(nt, n):
    # base colour multiply
    s = n.inputs['Base Color']
    mix = nt.nodes.new('ShaderNodeMix')
    mix.name = 'FILM_dark_base'
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    if s.is_linked:
        nt.links.new(s.links[0].from_socket, mix.inputs['A'])
    else:
        mix.inputs['A'].default_value = s.default_value
    nt.links.new(mix.outputs['Result'], s)
    mults = []
    for name in ('Specular IOR Level', 'Coat Weight'):
        si = n.inputs[name]
        m = nt.nodes.new('ShaderNodeMath')
        m.operation = 'MULTIPLY'
        m.name = 'FILM_dark_' + name.split()[0]
        if si.is_linked:
            nt.links.new(si.links[0].from_socket, m.inputs[0])
        else:
            m.inputs[0].default_value = si.default_value
        nt.links.new(m.outputs[0], si)
        mults.append(m)
    for sh in PL.SHOTS:
        bm, sm = SUIT_DARK[sh['id']]
        f = sh['start']
        mix.inputs['B'].default_value = (bm, bm, bm, 1.0)
        mix.inputs['B'].keyframe_insert('default_value', frame=f)
        for m in mults:
            m.inputs[1].default_value = sm
            m.inputs[1].keyframe_insert('default_value', frame=f)
    for fc in _fcurves(nt):
        for kp in fc.keyframe_points:
            kp.interpolation = 'CONSTANT'




def apply(rig):
    fix_suit(rig)
