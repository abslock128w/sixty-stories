# Owner's realism overhaul brief (2026-11-16, supersedes stage ordering in CITY_DIRECTIVE.md)

Do NOT generate another city and do NOT expand it. Preserve the layout, road network,
composition, camera position (the s_street view), major buildings, billboards, skybridges
and identity. Transform what is visible in that view from "recognisable procedural city"
into a professionally authored AAA open-world environment. Benchmark: refs/ref_street.webp.
Do not destroy or needlessly replace working assets.

1. ARCHITECTURAL DETAIL (real geometry, not textures): individually modelled window
   frames, recessed windows, glass thickness, metal mullions, panel joints, concrete edges,
   ledges, balconies, exterior pipes, ventilation, AC units, fire escapes, structural
   beams, detailed entrances. Every major building a distinct facade design. Break
   repetitive patterns with controlled variation in geometry, materials, window placement
   and structure.
2. VEHICLES: replace placeholder-looking vehicles with convincing models: correct
   proportions, wheel geometry, tyres, headlights, taillights, mirrors, glass, door seams,
   bumpers, plates, realistic paint and reflections, contact shadows. Several types and
   models; improve trucks, taxis, cars and buses individually. No primitive cubes.
3. ROAD AND SIDEWALK: asphalt aggregate, roughness variation, repairs, cracks, patches,
   faded markings, manholes, drain covers, tyre marks, oil stains, potholes, sidewalk
   joints, damaged pavement, curbs, tactile paving, storm drains. Interesting, not wrecked.
4. STOREFRONTS: real architectural depth; functioning businesses with detailed entrances,
   display windows, interior lighting, shelving, furniture, products, counters, signage,
   real glass reflections. No flat billboard-like storefronts.
5. STREET OBJECTS: signals, street signs, utility boxes, electrical cables, streetlights,
   hydrants, bins, benches, parking meters, bollards, newspaper boxes, bus shelters,
   advertising structures, security cameras, drainage, construction barriers; subtle
   imperfection and variation.
6. MATERIALS: concrete with believable roughness and imperfections; glass with convincing
   reflections, Fresnel and tint variation; metal with real highlights and wear; asphalt
   with visible aggregate and roughness variation. No excessive bump or obviously
   procedural textures; proper UVs / world-space mapping and variation.
7. LIGHTING: keep the warm cinematic direction; make it physically credible; reduce
   over-exposure in bright areas; keep the sun rays but make density and distribution more
   natural; better contact shadows, reflections, interior illumination, material response.
   No bloom to hide weak geometry.
8. QUALITY CONTROL: render the SAME camera view after every major improvement; inspect
   individual buildings, vehicles, roads, storefronts; fix what looks artificial,
   repetitive, unfinished or mis-scaled. Do not just raise polygon counts.

FINAL: the next render must show a substantial improvement over the current image. Do not
expand the city until the visible area is at a significantly higher standard. Do not claim
completion until the scene is actually modified, saved and rendered.
