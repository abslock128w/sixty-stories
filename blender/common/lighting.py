"""Sixty Stories - shared lighting: sky, sun, clouds, haze and the LIGHT_CTRL rig.

Usage (any bpy script):
    import sys; sys.path.insert(0, "/home/user/sixty/blender/common")
    import lighting
    lighting.setup_lighting(scene, dusk=0.0)       # create or update everything
    lighting.set_dusk(scene, 0.6, frame=300)        # write + keyframe every driven value

How it works
------------
An empty object named LIGHT_CTRL carries custom properties. Everything that changes
with time of day (sun lamp rotation/colour/strength, sky sun position, sky + cloud
strength, haze density, window / street-light / car-light emission, exposure) is driven
by plain single-property drivers that read those properties (no Python expressions,
so drivers work without "auto-run scripts").

`set_dusk(scene, d, frame)` computes all derived values from the scalar `dusk` (0 =
golden hour, sun 7 deg up straight down the avenue; 1 = blue hour, sun just below the
horizon, lights up) and writes them to LIGHT_CTRL, inserting keyframes when `frame` is
given. To animate dusk over a shot, call set_dusk at a few frames (e.g. every 6 frames)
or keyframe individual properties by hand.

LIGHT_CTRL properties
    dusk            0..1 master value (informational once the others are written)
    sun_elev        sun elevation, radians      sun_azim   azimuth from +Y toward +X, radians
    sun_rot_x/z     sun lamp euler (derived)    sun_strength  sun lamp W/m^2
    sun_r/g/b       sun lamp colour             sky_strength  world sky multiplier
    cloud_strength  cloud layer brightness      cloud_r/g/b   cloud sunlit tint
    haze_density    base haze extinction 1/m    haze_r/g/b    haze scatter colour
    window_emit     interior light multiplier (materials read it)
    window_frac     fraction of windows that are lit (0..1)
    street_emit     street lamp / traffic light / sign multiplier
    car_emit        head/tail light multiplier
    exposure        drives scene.view_settings.exposure
"""
import math
import bpy

CTRL_NAME = "LIGHT_CTRL"
SUN_AZIM_DEG = 2.0          # sun bearing, degrees from +Y toward +X (east wall catches light)
SUN_ELEV0_DEG = 7.0         # golden hour elevation at dusk = 0
HAZE_HALF_EXTENT = 15000.0   # haze boxes cover +-this in x and y
ATMO_COLLECTION = "CITY_atmo"


def _lerp(a, b, t):
    return a + (b - a) * t


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def dusk_values(dusk):
    """All LIGHT_CTRL values for a dusk amount in 0..1."""
    d = max(0.0, min(1.0, float(dusk)))
    elev = math.radians(_lerp(SUN_ELEV0_DEG, -1.5, d))
    azim = math.radians(SUN_AZIM_DEG + 0.5 * d)
    # direct sun dies as it sinks below ~0.5 deg
    above = _smooth((math.degrees(elev) + 0.6) / 4.0)
    sun_col = (1.0, _lerp(0.60, 0.40, d), _lerp(0.30, 0.13, d))
    v = dict(
        dusk=d,
        sun_elev=elev,
        sun_azim=azim,
        sun_rot_x=-(math.pi / 2 - elev),
        sun_rot_z=-azim,
        sun_strength=_lerp(10.0, 6.0, d) * above,
        sun_r=sun_col[0], sun_g=sun_col[1], sun_b=sun_col[2],
        sky_strength=_lerp(0.17, 0.40, _smooth(d)),
        cloud_strength=_lerp(1.0, 0.55, d),
        cloud_r=1.0, cloud_g=_lerp(0.52, 0.30, d), cloud_b=_lerp(0.36, 0.42, d),
        haze_density=_lerp(0.0003, 0.0004, d),
        haze_r=1.0, haze_g=_lerp(0.93, 0.85, d), haze_b=_lerp(0.86, 0.95, d),
        window_emit=_lerp(0.4, 0.8, _smooth(d)),
        window_frac=_lerp(0.13, 0.30, _smooth(d)),
        street_emit=_lerp(0.25, 3.0, _smooth(d)),
        car_emit=_lerp(0.3, 2.5, _smooth(d)),
        exposure=_lerp(0.1, 1.0, _smooth(d)),
    )
    return v


def sun_vector(dusk=0.0):
    """Unit vector from the scene toward the sun."""
    v = dusk_values(dusk)
    e, a = v["sun_elev"], v["sun_azim"]
    return (math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e))


# ---------------------------------------------------------------- drivers
def get_ctrl(scene=None):
    return bpy.data.objects.get(CTRL_NAME)


def drive(id_block, data_path, prop, index=-1, ctrl=None):
    """Drive id_block.data_path[index] from LIGHT_CTRL[prop] (single-prop driver)."""
    ctrl = ctrl or get_ctrl()
    try:
        id_block.driver_remove(data_path, index)
    except Exception:
        pass
    fc = id_block.driver_add(data_path, index) if index >= 0 else id_block.driver_add(data_path)
    drv = fc.driver
    drv.type = 'AVERAGE'
    while drv.variables:
        drv.variables.remove(drv.variables[0])
    var = drv.variables.new()
    var.name = "v"
    var.type = 'SINGLE_PROP'
    var.targets[0].id_type = 'OBJECT'
    var.targets[0].id = ctrl
    var.targets[0].data_path = f'["{prop}"]'
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    return fc


def drive_node_input(node_tree, node, input_name_or_index, prop, index=-1):
    """Drive a node socket default_value from LIGHT_CTRL[prop]."""
    sock = node.inputs[input_name_or_index]
    i = list(node.inputs).index(sock)
    path = f'nodes["{node.name}"].inputs[{i}].default_value'
    return drive(node_tree, path, prop, index)


def ctrl_value_node(node_tree, prop, label=None, location=(0, 0)):
    """A Value node in node_tree whose output follows LIGHT_CTRL[prop]."""
    n = node_tree.nodes.new('ShaderNodeValue')
    n.name = n.label = label or f"CTRL_{prop}"
    n.location = location
    ctrl = get_ctrl()
    n.outputs[0].default_value = float(ctrl[prop]) if ctrl and prop in ctrl else 1.0
    drive(node_tree, f'nodes["{n.name}"].outputs[0].default_value', prop)
    return n


# ---------------------------------------------------------------- builders
def _ensure_ctrl(scene):
    ctrl = bpy.data.objects.get(CTRL_NAME)
    if ctrl is None:
        ctrl = bpy.data.objects.new(CTRL_NAME, None)
        ctrl.empty_display_type = 'SPHERE'
        ctrl.empty_display_size = 20
        ctrl.location = (0, 0, 300)
        scene.collection.objects.link(ctrl)
    for k, val in dusk_values(0.0).items():
        if k not in ctrl:
            ctrl[k] = float(val)
    return ctrl


def _ensure_collection(scene, name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        parent = bpy.data.collections.get("CITY")
        (parent.children if parent else scene.collection.children).link(col)
    return col


def _build_sun(scene):
    sun = bpy.data.objects.get("SUN")
    if sun is None:
        ld = bpy.data.lights.new("SUN", 'SUN')
        sun = bpy.data.objects.new("SUN", ld)
        _ensure_collection(scene, ATMO_COLLECTION).objects.link(sun)
    ld = sun.data
    ld.angle = math.radians(0.55)
    sun.location = (0, 0, 500)
    sun.rotation_mode = 'XYZ'
    drive(sun, "rotation_euler", "sun_rot_x", 0)
    drive(sun, "rotation_euler", "sun_rot_z", 2)
    sun.rotation_euler[1] = 0.0
    drive(ld, "energy", "sun_strength")
    for i, p in enumerate(("sun_r", "sun_g", "sun_b")):
        drive(ld, "color", p, i)
    return sun


def _build_world(scene):
    w = bpy.data.worlds.get("CITY_world") or bpy.data.worlds.new("CITY_world")
    scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links

    def node(t, x, y, **kw):
        n = N.new(t)
        n.location = (x, y)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    out = node('ShaderNodeOutputWorld', 1600, 0)
    # two skies: with disc (camera rays) and without (lighting; the sun lamp does direct light)
    sky_d = node('ShaderNodeTexSky', -200, 300, sky_type='MULTIPLE_SCATTERING', name="SkyDisc")
    sky_n = node('ShaderNodeTexSky', -200, 0, sky_type='MULTIPLE_SCATTERING', name="SkyNoDisc")
    sky_d.sun_disc = True
    sky_n.sun_disc = False
    for s in (sky_d, sky_n):
        s.altitude = 30.0
        s.air_density = 1.0
        s.aerosol_density = 2.2
        s.ozone_density = 1.0
        s.sun_size = math.radians(0.55)
        s.sun_intensity = 0.6
        drive(nt, f'nodes["{s.name}"].sun_elevation', "sun_elev")
        drive(nt, f'nodes["{s.name}"].sun_rotation', "sun_azim")
    lp = node('ShaderNodeLightPath', -200, 600)
    mix_sky = node('ShaderNodeMix', 100, 200, data_type='RGBA', name="MixSky")
    L.new(lp.outputs['Is Camera Ray'], mix_sky.inputs['Factor'])
    L.new(sky_n.outputs['Color'], mix_sky.inputs['A'])
    L.new(sky_d.outputs['Color'], mix_sky.inputs['B'])

    # ---- cloud layer (thin high cirrus/altocumulus projected on a plane) ----
    tc = node('ShaderNodeTexCoord', -1400, -400)
    sep = node('ShaderNodeSeparateXYZ', -1200, -400)
    L.new(tc.outputs['Generated'], sep.inputs[0])
    zc = node('ShaderNodeMath', -1000, -550, operation='MAXIMUM')
    zc.inputs[1].default_value = 0.035
    L.new(sep.outputs['Z'], zc.inputs[0])
    comb = node('ShaderNodeCombineXYZ', -1000, -350)
    L.new(sep.outputs['X'], comb.inputs['X'])
    L.new(sep.outputs['Y'], comb.inputs['Y'])
    proj = node('ShaderNodeVectorMath', -800, -400, operation='DIVIDE')
    L.new(comb.outputs[0], proj.inputs[0])
    L.new(zc.outputs[0], proj.inputs[1])  # scalar->vector broadcast
    # stretch clouds into streaks (wind along x)
    stretch = node('ShaderNodeVectorMath', -600, -400, operation='MULTIPLY')
    stretch.inputs[1].default_value = (0.55, 1.6, 1.0)
    L.new(proj.outputs[0], stretch.inputs[0])
    warp = node('ShaderNodeTexNoise', -400, -650)
    warp.inputs['Scale'].default_value = 0.9
    warp.inputs['Detail'].default_value = 3.0
    warpm = node('ShaderNodeVectorMath', -200, -600, operation='MULTIPLY_ADD')
    L.new(warp.outputs['Color'], warpm.inputs[0])
    warpm.inputs[1].default_value = (0.6, 0.6, 0.0)
    L.new(stretch.outputs[0], warpm.inputs[2])
    L.new(stretch.outputs[0], warp.inputs['Vector'])
    cn = node('ShaderNodeTexNoise', 0, -450)
    cn.inputs['Scale'].default_value = 1.6
    cn.inputs['Detail'].default_value = 9.0
    cn.inputs['Roughness'].default_value = 0.62
    cn.inputs['Lacunarity'].default_value = 2.3
    L.new(warpm.outputs[0], cn.inputs['Vector'])
    cov = node('ShaderNodeMapRange', 200, -450)
    cov.inputs['From Min'].default_value = 0.44
    cov.inputs['From Max'].default_value = 0.66
    L.new(cn.outputs['Fac'], cov.inputs['Value'])
    # large-scale coverage mask so the sky has clear patches
    big = node('ShaderNodeTexNoise', 0, -750)
    big.inputs['Scale'].default_value = 0.18
    big.inputs['Detail'].default_value = 1.0
    L.new(proj.outputs[0], big.inputs['Vector'])
    bigr = node('ShaderNodeMapRange', 200, -750)
    bigr.inputs['From Min'].default_value = 0.36
    bigr.inputs['From Max'].default_value = 0.52
    L.new(big.outputs['Fac'], bigr.inputs['Value'])
    cmask = node('ShaderNodeMath', 400, -550, operation='MULTIPLY')
    L.new(cov.outputs[0], cmask.inputs[0])
    L.new(bigr.outputs[0], cmask.inputs[1])
    # fade toward horizon (haze) and below
    hz = node('ShaderNodeMapRange', 400, -800)
    hz.inputs['From Min'].default_value = 0.02
    hz.inputs['From Max'].default_value = 0.16
    L.new(sep.outputs['Z'], hz.inputs['Value'])
    alpha = node('ShaderNodeMath', 600, -600, operation='MULTIPLY')
    L.new(cmask.outputs[0], alpha.inputs[0])
    L.new(hz.outputs[0], alpha.inputs[1])
    alpha2 = node('ShaderNodeMath', 750, -600, operation='MULTIPLY', name="CloudOpacity")
    alpha2.inputs[1].default_value = 0.92
    L.new(alpha.outputs[0], alpha2.inputs[0])
    # cloud colour: forward-scatter glow toward the sun + underlit warm tint
    sunvec = node('ShaderNodeCombineXYZ', -400, -1000, name="SunVec")
    for i, ax in enumerate("XYZ"):
        pass
    # sun vector from ctrl: x = sin(az)cos(el), y = cos(az)cos(el), z = sin(el); approximated by drivers
    ctrl = get_ctrl()
    v0 = dusk_values(ctrl["dusk"] if ctrl else 0.0)
    sv = sun_vector(v0["dusk"])
    for i in range(3):
        sunvec.inputs[i].default_value = sv[i]
    dot = node('ShaderNodeVectorMath', -200, -1000, operation='DOT_PRODUCT')
    L.new(tc.outputs['Generated'], dot.inputs[0])
    L.new(sunvec.outputs[0], dot.inputs[1])
    dclamp = node('ShaderNodeMath', 0, -1000, operation='MAXIMUM')
    dclamp.inputs[1].default_value = 0.0
    L.new(dot.outputs['Value'], dclamp.inputs[0])
    dpow = node('ShaderNodeMath', 200, -1000, operation='POWER')
    dpow.inputs[1].default_value = 6.0
    L.new(dclamp.outputs[0], dpow.inputs[0])
    glow = node('ShaderNodeMath', 400, -1000, operation='MULTIPLY_ADD')
    glow.inputs[1].default_value = 5.0
    glow.inputs[2].default_value = 0.55
    L.new(dpow.outputs[0], glow.inputs[0])
    ccol = node('ShaderNodeCombineColor', 400, -1200, name="CloudTint")
    drive_node_input(nt, ccol, 0, "cloud_r")
    drive_node_input(nt, ccol, 1, "cloud_g")
    drive_node_input(nt, ccol, 2, "cloud_b")
    # shadowed side of cloud: dusky violet-grey
    dark = node('ShaderNodeRGB', 400, -1400)
    dark.outputs[0].default_value = (0.20, 0.17, 0.22, 1)
    thick = node('ShaderNodeMapRange', 600, -1300)
    thick.inputs['From Min'].default_value = 0.55
    thick.inputs['From Max'].default_value = 0.95
    L.new(cn.outputs['Fac'], thick.inputs['Value'])
    cmix = node('ShaderNodeMix', 800, -1200, data_type='RGBA')
    cmix.inputs['Factor'].default_value = 0.0
    L.new(thick.outputs[0], cmix.inputs['Factor'])
    L.new(ccol.outputs[0], cmix.inputs['A'])
    L.new(dark.outputs[0], cmix.inputs['B'])
    cscale = node('ShaderNodeVectorMath', 1000, -1100, operation='SCALE')
    L.new(cmix.outputs['Result'], cscale.inputs[0])
    L.new(glow.outputs[0], cscale.inputs['Scale'])
    cstr = ctrl_value_node(nt, "cloud_strength", location=(1000, -1350))
    cscale2 = node('ShaderNodeVectorMath', 1150, -1100, operation='SCALE')
    L.new(cscale.outputs[0], cscale2.inputs[0])
    L.new(cstr.outputs[0], cscale2.inputs['Scale'])

    # sky strength
    sstr = ctrl_value_node(nt, "sky_strength", location=(300, 400))
    skys = node('ShaderNodeVectorMath', 500, 200, operation='SCALE')
    L.new(mix_sky.outputs['Result'], skys.inputs[0])
    L.new(sstr.outputs[0], skys.inputs['Scale'])
    # clouds partially occlude the sky (scale cloud by sky luminance so dusk darkens them)
    cmixsky = node('ShaderNodeMix', 1300, 100, data_type='RGBA', name="CloudOver")
    L.new(alpha2.outputs[0], cmixsky.inputs['Factor'])
    L.new(skys.outputs[0], cmixsky.inputs['A'])
    L.new(cscale2.outputs[0], cmixsky.inputs['B'])
    # below-horizon ground colour (never really seen: water/ground planes cover it)
    bg = node('ShaderNodeBackground', 1450, 0)
    L.new(cmixsky.outputs['Result'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
    L.new(bg.outputs[0], out.inputs['Surface'])
    # keep the sun-vector node following dusk via drivers on its components
    _drive_sunvec(nt, sunvec)
    return w


def _drive_sunvec(nt, sunvec):
    """Sun vector components as LIGHT_CTRL props (sun_x/y/z) so clouds follow dusk."""
    ctrl = get_ctrl()
    for i, p in enumerate(("sun_x", "sun_y", "sun_z")):
        if p not in ctrl:
            ctrl[p] = 0.0
        drive_node_input(nt, sunvec, i, p)


def _haze_material():
    m = bpy.data.materials.get("ATMO_haze") or bpy.data.materials.new("ATMO_haze")
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (600, 0)
    vol = nt.nodes.new('ShaderNodeVolumePrincipled')
    vol.location = (300, 0)
    vol.inputs['Anisotropy'].default_value = 0.68
    vol.inputs['Absorption Color'].default_value = (0.0, 0.0, 0.0, 1)
    nt.links.new(vol.outputs[0], out.inputs['Volume'])
    dens = ctrl_value_node(nt, "haze_density", location=(-200, -100))
    nt.links.new(dens.outputs[0], vol.inputs['Density'])
    col = nt.nodes.new('ShaderNodeCombineColor')
    col.name = "HazeColor"
    col.location = (0, 150)
    nt.links.new(col.outputs[0], vol.inputs['Color'])
    for i, p in enumerate(("haze_r", "haze_g", "haze_b")):
        drive_node_input(nt, col, i, p)
    # second, denser ground layer uses a multiplier via object-level material copy
    return m


def _haze_variant(base, name, mult):
    m = bpy.data.materials.get(name)
    if m is None:
        m = base.copy()
        m.name = name
    mul = m.node_tree.nodes.get("LowMul")
    if mul is None:
        mul = m.node_tree.nodes.new('ShaderNodeMath')
        mul.name = "LowMul"
        mul.operation = 'MULTIPLY'
        mul.location = (100, -150)
        dens = m.node_tree.nodes.get("CTRL_haze_density")
        vol = [n for n in m.node_tree.nodes if n.type == 'PRINCIPLED_VOLUME'][0]
        m.node_tree.links.new(dens.outputs[0], mul.inputs[0])
        m.node_tree.links.new(mul.outputs[0], vol.inputs['Density'])
    mul.inputs[1].default_value = mult
    if name.endswith('canyon') and m.node_tree.nodes.get("HazeBreakup") is None:
        # heterogeneous breakup so shafts vary in density (slow-moving blobs ~20-60 m)
        nt = m.node_tree
        tc = nt.nodes.new('ShaderNodeTexCoord')
        nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.name = "HazeBreakup"
        nz.inputs['Scale'].default_value = 0.035
        nz.inputs['Detail'].default_value = 2.0
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs['From Min'].default_value = 0.3
        mr.inputs['From Max'].default_value = 0.7
        mr.inputs['To Min'].default_value = 0.25
        mr.inputs['To Max'].default_value = 1.6
        nt.links.new(nz.outputs['Fac'], mr.inputs['Value'])
        m2 = nt.nodes.new('ShaderNodeMath')
        m2.operation = 'MULTIPLY'
        vol = [n for n in nt.nodes if n.type == 'PRINCIPLED_VOLUME'][0]
        nt.links.new(mul.outputs[0], m2.inputs[0])
        nt.links.new(mr.outputs[0], m2.inputs[1])
        nt.links.new(m2.outputs[0], vol.inputs['Density'])
    return m


# (name, multiplier of haze_density, x0, x1, y0, y1, z0, z1); overlapping volumes add up
HAZE_BOXES = [
    ("ATMO_haze_box", 1.0, None, None, None, None, -2.0, 650.0),
    ("ATMO_haze_low_box", 2.0, None, None, None, None, -1.0, 140.0),
    # the avenue corridor: a denser warm veil inside the canyon (Manhattanhenge air)
    ("ATMO_haze_canyon", 2.2, -16.0, 16.0, -1200.0, 1460.0, -0.5, 80.0),
]


def _build_haze(scene):
    """Nested homogeneous boxes (analytic in Cycles, no ray marching). None of them
    shadows the sun lamp (its strength already includes atmospheric extinction)."""
    col = _ensure_collection(scene, ATMO_COLLECTION)
    base = _haze_material()
    H = HAZE_HALF_EXTENT
    for name, mult, x0, x1, y0, y1, z0, z1 in HAZE_BOXES:
        mat = base if mult == 1.0 else _haze_variant(base, name.replace("_box", "").replace("ATMO_haze", "ATMO_haze_mat"), mult)
        x0 = -H if x0 is None else x0
        x1 = H if x1 is None else x1
        y0 = -H if y0 is None else y0
        y1 = H if y1 is None else y1
        ob = bpy.data.objects.get(name)
        if ob is None:
            me = bpy.data.meshes.new(name)
            verts = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
            faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
            me.from_pydata(verts, [], faces)
            me.materials.append(mat)
            ob = bpy.data.objects.new(name, me)
            col.objects.link(ob)
        # normals MUST point outward: Cycles decides "camera inside volume" from face
        # orientation; inward faces silently disabled the haze for every camera ray.
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(ob.data)
        bm.free()
        ob.display_type = 'WIRE'
        ob.visible_shadow = False
        ob.hide_viewport = False
    return col


# Recommended per-shot overrides applied on top of dusk_values() (key them per shot).
PRESETS = {
    "none": dict(),
    "canyon": dict(exposure=1.3, sky_strength=0.24, window_frac=0.24),                        # s3-s5 (defaults + canyon exposure)
    "aerial": dict(haze_density=0.00012, haze_r=0.18, haze_g=0.17, haze_b=0.17, exposure=0.5, sky_strength=0.13),  # s1, s6 wide
    "closeup": dict(haze_density=0.0002, exposure=0.4),  # s2 perch, 85-135 mm
    "dusk_wide": dict(haze_density=0.00012, haze_r=0.35, haze_g=0.32, haze_b=0.36),  # apply_preset(scene, "dusk_wide", dusk=1.0): s6 end
}


def apply_preset(scene, name, dusk=0.0, frame=None):
    """set_dusk(dusk) then override with PRESETS[name]; keys everything when frame is given."""
    set_dusk(scene, dusk, frame)
    ctrl = get_ctrl()
    for k, v in PRESETS[name].items():
        ctrl[k] = float(v)
        if frame is not None:
            ctrl.keyframe_insert(f'["{k}"]', frame=frame)
    touch(scene)


def set_dusk(scene, dusk, frame=None):
    ctrl = get_ctrl()
    vals = dusk_values(dusk)
    sv = sun_vector(dusk)
    vals.update(sun_x=sv[0], sun_y=sv[1], sun_z=sv[2])
    for k, v in vals.items():
        ctrl[k] = float(v)
        if frame is not None:
            ctrl.keyframe_insert(f'["{k}"]', frame=frame)
    touch(scene)
    return vals


def touch(scene=None):
    """Custom-property edits do not tag the depsgraph: call after editing LIGHT_CTRL by hand
    so drivers re-evaluate (set_dusk does this itself). Keyframed props need nothing."""
    ctrl = get_ctrl()
    if ctrl is not None:
        ctrl.update_tag()
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass


def setup_lighting(scene, dusk=0.0, haze=True):
    """Create (or refresh) sun, sky, clouds, haze and LIGHT_CTRL for `scene`."""
    ctrl = _ensure_ctrl(scene)
    set_dusk(scene, dusk)
    _build_sun(scene)
    _build_world(scene)
    if haze:
        _build_haze(scene)
    drive(scene, "view_settings.exposure", "exposure")
    set_dusk(scene, dusk)
    return ctrl
