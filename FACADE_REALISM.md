# Owner's brief: AAA realism overhaul of the existing facade/storefront asset (2026-11-23)

Benchmark for material and lighting credibility: a current photoreal AAA survival-horror
title (owner named Resident Evil Requiem): real-world material behaviour, physical
imperfection, environmental integration, complex lighting, photographic credibility.
Do NOT start over, do not replace existing assets with generic ones, do not just add
objects. Find why the scene reads as a polished architectural visualisation instead of a
photographed place, and remove those causes. Preserve architectural identity and scene
structure. Save after each major stage (new numbered versions; never overwrite a working
one). Report honestly; no claimed improvement without inspecting the render.

1 AUDIT: inspect scene + renders: brick walls, window frames and glass, window interiors,
  storefronts, fabric awnings, fire escapes, concrete/sidewalks, trim and transitions.
  Name the actual causes of artificiality (repetition, uniform materials, missing
  micro-detail, unreal reflections, excess cleanliness, artificial light). Test renders first.
2 BRICK: believable masonry: per-brick variation in red/brown/orange/muted tones and
  roughness, uneven colour, chips, worn edges, pores, clay texture, irregular mortar, dirt in
  joints, weathering at corners, water staining under windows, darker areas under ledges.
  Use scanned PBR brick textures where possible (colour, roughness, normal, displacement)
  combined with procedural variation. Real brick dimensions. No exaggerated displacement.
3 WINDOWS: glass thickness, Fresnel, transmission, varied tint, real frame materials,
  rubber seals and gaskets, frame imperfections, dust, fine scratches, water marks, interior
  visibility, correct reflections of sky and neighbours. Glass must not just look black.
  Interiors: realistic furniture, curtains/blinds, ceiling lights, lamps, wall details,
  shelving, objects, varied illumination; several distinct interiors, correct scale,
  logical placement; the building must look occupied.
4 STOREFRONTS (bakery + neighbour): glass, metal frames, painted trim, handles, hinges,
  signage, interiors, shelving, individual products, display counters, light fixtures,
  reflections, subtle dirt and wear. AWNING: real canvas: weave, roughness variation,
  tension, seams, stitching, folds, slight sag, natural edges, very subtle fading. Bakery
  interior as a real operating bakery: shelves, display cases, pastries, bread, packaging,
  counters, warm light. No placeholder cubes as products.
5 WEATHERING following gravity, exposure and material logic: dirt under windows, water
  streaks, rain marks, dust on ledges, darkened concrete corners, weathered paint, chipped
  plaster, corrosion on metal, dirt at drainpipes, sidewalk variation, stains near ground.
  Maintained but exposed; no random dirt.
6 SECONDARY MATERIALS: fire escapes: painted metal, roughness variation, welds, bolts,
  paint wear, local corrosion. Concrete: aggregate, pores, colour differences, erosion,
  seams, small cracks. Sidewalks: individual slabs, joints, edge wear, stains,
  irregularities. Materials must not all share one roughness and look.
7 LIGHTING: physically convincing: indirect light, ambient, contact shadows, reflections,
  light through windows, interior/exterior exposure balance, shadow softness, natural sky,
  material response. Cycles. No excessive contrast, crushed shadows, clipped highlights or
  artificial gloss. One consistent lighting condition for everything.
8 DETAIL WITH A REASON: small electrical fixtures, screws, window drainage channels,
  brackets, cable attachments, thresholds, sign imperfections, individual products, small
  debris, building joints, drainage.
9 RENDER QC after each subsystem, real close-ups: brick wall; window glass; window
  interior; bakery storefront; awning; fire escape; full building street-level. Ask: does
  it resemble a photograph; are materials distinguishable; are imperfections believable;
  does glass behave; does geometry look manufactured; any procedural repetition; anything
  like a default Blender material; reflections consistent? If artificial, find why and fix.
10 Reusable material systems, sensible texture resolution and UV density, no needless
  duplication. End result: a real urban location shot on a cinema camera, credible at
  every scale.
