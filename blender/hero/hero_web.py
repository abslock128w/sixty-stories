"""Geometry-nodes group for the hero's line ("web"): hand empty -> anchor empty."""
import bpy


def make_nodegroup(name='HERO_web_line'):
    ng = bpy.data.node_groups.get(name)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    I = ng.interface
    I.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    I.new_socket('Hand', in_out='INPUT', socket_type='NodeSocketObject')
    I.new_socket('Anchor', in_out='INPUT', socket_type='NodeSocketObject')
    s = I.new_socket('Slack', in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = 0.0
    r = I.new_socket('Radius', in_out='INPUT', socket_type='NodeSocketFloat'); r.default_value = 0.006
    I.new_socket('Material', in_out='INPUT', socket_type='NodeSocketMaterial')
    I.new_socket('Head Material', in_out='INPUT', socket_type='NodeSocketMaterial')
    I.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; L = ng.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')

    def node(kind, **kw):
        n = N.new(kind)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def math(op, a, b=None, vec=False):
        n = N.new('ShaderNodeVectorMath' if vec else 'ShaderNodeMath')
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v if not vec else (v, v, v)
            elif isinstance(v, tuple):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n

    oh = node('GeometryNodeObjectInfo', transform_space='RELATIVE')
    L.new(gi.outputs['Hand'], oh.inputs['Object'])
    oa = node('GeometryNodeObjectInfo', transform_space='RELATIVE')
    L.new(gi.outputs['Anchor'], oa.inputs['Object'])
    A = oh.outputs['Location']; B = oa.outputs['Location']
    line = node('GeometryNodeCurvePrimitiveLine')
    L.new(A, line.inputs['Start']); L.new(B, line.inputs['End'])
    rs = node('GeometryNodeResampleCurve')
    try:
        rs.mode = 'COUNT'
    except Exception:
        pass
    rs.inputs['Count'].default_value = 96
    L.new(line.outputs['Curve'], rs.inputs['Curve'])
    sp = node('GeometryNodeSplineParameter')
    # sag: down (world-ish -Z of the object) * slack * 0.06 * len * 4 f (1 - f)
    AB = math('SUBTRACT', B, A, vec=True)
    ln = math('LENGTH', AB.outputs[0], vec=True)
    f = sp.outputs['Factor']
    omf = math('SUBTRACT', 1.0, f)
    par = math('MULTIPLY', math('MULTIPLY', f, omf.outputs[0]).outputs[0], 4.0)
    amp = math('MULTIPLY', math('MULTIPLY', gi.outputs['Slack'], ln.outputs['Value']).outputs[0], 0.06)
    sag = math('MULTIPLY', par.outputs[0], amp.outputs[0])
    # a little lateral S-wave in a just-fired line
    wv = math('SINE', math('MULTIPLY', f, 9.42).outputs[0])
    lat = math('MULTIPLY', math('MULTIPLY', wv.outputs[0], amp.outputs[0]).outputs[0], 0.0)
    side = math('NORMALIZE', math('CROSS_PRODUCT', AB.outputs[0], (0.0, 0.0, 1.0), vec=True).outputs[0], vec=True)
    comb = node('ShaderNodeCombineXYZ')
    negsag = math('MULTIPLY', sag.outputs[0], -1.0)
    L.new(negsag.outputs[0], comb.inputs['Z'])
    latv = math('SCALE', side.outputs[0], vec=True)
    L.new(lat.outputs[0], latv.inputs['Scale'])
    off = math('ADD', comb.outputs[0], latv.outputs[0], vec=True)
    setp = node('GeometryNodeSetPosition')
    L.new(rs.outputs[0], setp.inputs['Geometry'])
    L.new(off.outputs[0], setp.inputs['Offset'])
    # attributes for the braid shader
    st1 = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    st1.inputs['Name'].default_value = 'web_u'
    L.new(setp.outputs[0], st1.inputs['Geometry'])
    sp2 = node('GeometryNodeSplineParameter')
    L.new(sp2.outputs['Length'], st1.inputs['Value'])
    circ = node('GeometryNodeCurvePrimitiveCircle')
    circ.inputs['Resolution'].default_value = 12
    circ.inputs['Radius'].default_value = 1.0
    st2 = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    st2.inputs['Name'].default_value = 'web_t'
    L.new(circ.outputs['Curve'], st2.inputs['Geometry'])
    sp3 = node('GeometryNodeSplineParameter')
    L.new(sp3.outputs['Factor'], st2.inputs['Value'])
    # radius
    scr = node('GeometryNodeSetCurveRadius')
    L.new(st1.outputs[0], scr.inputs['Curve'])
    L.new(gi.outputs['Radius'], scr.inputs['Radius'])
    c2m = node('GeometryNodeCurveToMesh')
    L.new(scr.outputs[0], c2m.inputs['Curve'])
    L.new(st2.outputs[0], c2m.inputs['Profile Curve'])
    if 'Scale' in c2m.inputs:
        L.new(gi.outputs['Radius'], c2m.inputs['Scale'])
    sm1 = node('GeometryNodeSetMaterial')
    L.new(c2m.outputs[0], sm1.inputs['Geometry'])
    L.new(gi.outputs['Material'], sm1.inputs['Material'])
    # kite-shaped grapnel at the anchor: two 4-sided cones base to base (short nose,
    # long tail toward the line), flattened
    c1 = node('GeometryNodeMeshCone')
    c1.inputs['Vertices'].default_value = 4
    c1.inputs['Radius Bottom'].default_value = 0.03
    c1.inputs['Radius Top'].default_value = 0.0
    c1.inputs['Depth'].default_value = 0.035
    t1 = node('GeometryNodeTransform')
    L.new(c1.outputs['Mesh'], t1.inputs['Geometry'])
    t1.inputs['Translation'].default_value = (0, 0, 0.0175)
    c2 = node('GeometryNodeMeshCone')
    c2.inputs['Vertices'].default_value = 4
    c2.inputs['Radius Bottom'].default_value = 0.03
    c2.inputs['Radius Top'].default_value = 0.0
    c2.inputs['Depth'].default_value = 0.075
    t2 = node('GeometryNodeTransform')
    L.new(c2.outputs['Mesh'], t2.inputs['Geometry'])
    t2.inputs['Translation'].default_value = (0, 0, -0.0375)
    t2.inputs['Rotation'].default_value = (3.14159265, 0, 0)
    joinh = node('GeometryNodeJoinGeometry')
    L.new(t1.outputs[0], joinh.inputs[0]); L.new(t2.outputs[0], joinh.inputs[0])
    flat = node('GeometryNodeTransform')
    L.new(joinh.outputs[0], flat.inputs['Geometry'])
    flat.inputs['Scale'].default_value = (1.0, 0.35, 1.0)
    flat.inputs['Rotation'].default_value = (0, 0, 0.785398)
    joinh2 = node('GeometryNodeJoinGeometry')
    L.new(flat.outputs[0], joinh2.inputs[0])
    joinh = joinh2
    # orient: local +Z of the head toward the anchor (away from the hand)
    dirv = math('NORMALIZE', AB.outputs[0], vec=True)
    al = node('FunctionNodeAlignRotationToVector')
    al.axis = 'Z'
    L.new(dirv.outputs[0], al.inputs['Vector'])
    th = node('GeometryNodeTransform')
    L.new(joinh.outputs[0], th.inputs['Geometry'])
    try:
        th.mode = 'COMPONENTS'
    except Exception:
        pass
    L.new(al.outputs[0], th.inputs['Rotation'])
    L.new(B, th.inputs['Translation'])
    sm2 = node('GeometryNodeSetMaterial')
    L.new(th.outputs[0], sm2.inputs['Geometry'])
    L.new(gi.outputs['Head Material'], sm2.inputs['Material'])
    # T-handle the fist closes around: a short bar along the hand empty's local X
    bar = node('GeometryNodeMeshCylinder')
    bar.inputs['Vertices'].default_value = 16
    bar.inputs['Radius'].default_value = 0.0095
    bar.inputs['Depth'].default_value = 0.115
    tb = node('GeometryNodeTransform')
    L.new(bar.outputs['Mesh'], tb.inputs['Geometry'])
    tb.inputs['Rotation'].default_value = (0, 1.5707963, 0)
    th2 = node('GeometryNodeTransform')
    L.new(tb.outputs[0], th2.inputs['Geometry'])
    L.new(oh.outputs['Location'], th2.inputs['Translation'])
    L.new(oh.outputs['Rotation'], th2.inputs['Rotation'])
    sm3 = node('GeometryNodeSetMaterial')
    L.new(th2.outputs[0], sm3.inputs['Geometry'])
    L.new(gi.outputs['Head Material'], sm3.inputs['Material'])
    j = node('GeometryNodeJoinGeometry')
    L.new(sm1.outputs[0], j.inputs[0]); L.new(sm2.outputs[0], j.inputs[0]); L.new(sm3.outputs[0], j.inputs[0])
    ss = node('GeometryNodeSetShadeSmooth')
    L.new(j.outputs[0], ss.inputs['Geometry'])
    L.new(ss.outputs[0], go.inputs['Geometry'])
    return ng
