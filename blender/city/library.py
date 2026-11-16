"""Hero-detail building library: 18 archetypes, reused (re-seeded / mirrored) on the near-ring lots.

Each archetype is a parametric recipe on top of a style family (the family, footprint, tiers and
height of every lot are unchanged, so city_meta.json stays identical). An archetype sets the
facade materials and palette, detail kit (window frames as geometry, sills, lintels, cornice,
fire escapes, window AC units), the interior programme behind its windows (which room modules are
shuffled in) and rooftop furniture. Overrides here must not consume the building's main RNG.
"""
import random

LIB = {
    'prewar': [
        dict(name='white_stone_bank', wall='limestone', cols=[(0.66, 0.63, 0.57), (0.62, 0.60, 0.55)], use='office',
             fire_escape=False, ac_p=0.0, lintels=True, cornice=1.6, frames=True, base_trim=True, trim_col=1),
        dict(name='terracotta_apartments', wall='brick', cols=[(0.50, 0.24, 0.13), (0.46, 0.20, 0.11)], use='residential',
             fire_escape=True, ac_p=0.15, lintels=True, cornice=1.2, frames=True, base_trim=True),
        dict(name='tenement_red', wall='brick', cols=[(0.34, 0.12, 0.07), (0.38, 0.14, 0.08)], use='residential',
             fire_escape=True, ac_p=0.22, lintels=True, cornice=1.1, frames=True),
        dict(name='tenement_buff', wall='brick', cols=[(0.52, 0.42, 0.28), (0.56, 0.45, 0.30)], use='residential',
             fire_escape=True, ac_p=0.18, lintels=True, cornice=0.9, frames=True),
        dict(name='brown_apartments', wall='brick', cols=[(0.17, 0.10, 0.07), (0.20, 0.12, 0.08)], use='residential',
             fire_escape=False, ac_p=0.12, lintels=True, cornice=1.3, frames=True, terrace=True),
        dict(name='prewar_hotel', wall='limestone', cols=[(0.42, 0.37, 0.29), (0.45, 0.40, 0.31)], use='hotel',
             fire_escape=False, ac_p=0.0, lintels=True, cornice=1.4, frames=True),
        dict(name='mixed_use_brick', wall='brick', cols=[(0.30, 0.14, 0.08), (0.33, 0.20, 0.12)], use='residential',
             fire_escape=True, ac_p=0.15, lintels=False, cornice=0.8, frames=True),
        dict(name='loft_offices', wall='brick', cols=[(0.26, 0.15, 0.10), (0.22, 0.17, 0.13)], use='office',
             fire_escape=True, ac_p=0.05, lintels=True, cornice=0.7, frames=True),
    ],
    'deco': [
        dict(name='red_brick_copper_tower', wall='brick', cols=[(0.40, 0.13, 0.07), (0.36, 0.12, 0.07)], spandrel='terracotta',
             use='office', frames=True, base_trim=True, patina=True),
        dict(name='terracotta_deco_hotel', wall='limestone', cols=[(0.58, 0.36, 0.22)], spandrel='metal_bronze', use='hotel',
             frames=True, base_trim=True, patina=True),
        dict(name='white_deco_tower', wall='limestone', cols=[(0.64, 0.61, 0.55)], spandrel='metal_dark', use='office',
             frames=True, base_trim=True),
        dict(name='deco_limestone_office', wall='limestone', cols=[(0.56, 0.50, 0.40)], spandrel='metal_bronze',
             use='office', frames=True, terrace=True),
        dict(name='deco_brick_office', wall='brick', cols=[(0.30, 0.20, 0.13), (0.34, 0.24, 0.15)], spandrel='terracotta',
             use='office', frames=True),
        dict(name='deco_hotel', wall='limestone', cols=[(0.58, 0.52, 0.42)], spandrel='metal_dark', use='hotel',
             frames=True, terrace=True),
        dict(name='deco_residential', wall='limestone', cols=[(0.52, 0.44, 0.33)], spandrel='terracotta',
             use='residential', frames=True, ac_p=0.08, terrace=True),
    ],
    'slab': [
        dict(name='slab_white_office', wall='panel', cols=[(0.62, 0.61, 0.58)], use='office'),
        dict(name='slab_dark_office', wall='panel', cols=[(0.07, 0.07, 0.08)], use='office'),
        dict(name='slab_residential', wall='panel', cols=[(0.42, 0.38, 0.32)], use='residential', ac_p=0.1, terrace=True),
    ],
    'glass': [
        dict(name='dark_steel_grid', cols=[(0.05, 0.055, 0.06)], use='office', steel_grid=True),
        dict(name='green_glass_office', cols=[(0.12, 0.26, 0.22)], use='office'),
        dict(name='glass_blue_office', cols=[(0.16, 0.24, 0.28), (0.12, 0.20, 0.22)], use='office'),
        dict(name='glass_bronze_office', cols=[(0.36, 0.22, 0.11), (0.30, 0.25, 0.18)], use='office'),
        dict(name='glass_condo', cols=[(0.20, 0.27, 0.27), (0.26, 0.28, 0.30)], use='residential', terrace=True),
        dict(name='glass_hotel', cols=[(0.11, 0.24, 0.19), (0.17, 0.19, 0.22)], use='hotel'),
        dict(name='glass_black_office', cols=[(0.07, 0.08, 0.09)], use='office'),
    ],
}
ALL = [a for fam in LIB.values() for a in fam]


def choose(spec):
    fam = 'glass' if spec['style'] in ('glass', 'twin') else spec['style']
    r = random.Random(spec['seed'] * 31 + 7)
    arch = dict(r.choice(LIB[fam]))
    if spec['style'] == 'twin':
        arch = dict(LIB['glass'][0], name='twin_tower', use='office')
    arch['rng'] = r
    return arch


def apply(arch, P, bcol):
    """Return (P, bcol) with archetype overrides (P is modified in place)."""
    r = arch['rng']
    if 'wall' in arch and not P['curtain']:
        P['wall'] = arch['wall']
    if 'spandrel' in arch:
        P['spandrel'] = arch['spandrel']
    if 'lintels' in arch:
        P['lintels'] = arch['lintels']
    if 'cornice' in arch and P['style'] == 'prewar':
        P['cornice'] = arch['cornice']
    if arch.get('frames') and not P['curtain'] and not P['ribbon']:
        P['frames_z'] = 0.0
        P['frames_zmax'] = 60.0
    P['use'] = arch['use']
    P['ac_p'] = arch.get('ac_p', 0.0) * 0.5
    P['rooms'] = True
    P['base_trim'] = arch.get('base_trim', False)
    P['patina'] = arch.get('patina', False)
    if arch.get('steel_grid'):
        P['dp'] = 0.45
        P['pw'] = 0.12
    P['fire_escape'] = arch.get('fire_escape', False)
    P['arch'] = arch['name']
    c = r.choice(arch['cols'])
    j = r.uniform(0.92, 1.08)
    bcol = (c[0] * j, c[1] * j, c[2] * j, bcol[3])
    return P, bcol
