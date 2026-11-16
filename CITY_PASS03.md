# Owner's brief: AAA photorealism pass 03 (2026-11-16). Supersedes the remaining items of CITY_OVERHAUL.md.

Do not regenerate the city. Do not change the camera composition (s_street), major
building positions, street layout, lighting direction or architectural identity. Goal:
remove the remaining procedural look; substantial improvement in object quality, material
realism and environmental detail. Save a NEW version; do not overwrite the previous
working version (previous scene is kept as blender/out/city_pass02.blend).

1. VEHICLE RECONSTRUCTION (major priority): replace every visibly primitive vehicle with
   detailed automotive geometry: taxis, sedans, delivery trucks, other traffic. Tyres and
   rims, headlight housings, taillights, door handles, mirrors, window frames, windshields,
   bumpers, grilles, plates, body panel separation, realistic automotive paint, proper
   reflections and contact shadows. No box-shaped trucks or cars.
2. MATERIAL REALISM across the visible environment: brick with individual bricks and
   mortar; concrete with roughness variation, dirt, weathering, imperfections; glass with
   proper reflections, transparency and visible interior depth; metal with believable
   reflections and wear; asphalt with visible aggregate, patches, real roughness. Dedicated
   material systems per surface, not one noise texture for everything.
3. BUILDING INTERIORS in visible windows: variation in interior lighting, curtains, blinds,
   office furniture, desks, chairs, plants, partitions, ceiling lights, window reflections.
   Not every window lit; not every window the same.
4. STREET-LEVEL RECONSTRUCTION of the sidewalks: individual pavement slabs, utility covers,
   drain grates, street signs, traffic signal equipment, electrical cabinets, hydrants,
   trash bins, benches, bollards, newspaper boxes, streetlights, construction details,
   small clutter; each with realistic geometry, materials and placement.
5. PEDESTRIANS: realistic proportions, natural clothing, varied poses, believable
   placement; no repeated identical models; groups with natural spacing and orientations.
6. ARCHITECTURAL WEATHERING (subtle): water stains, dirt at window edges, brick
   discolouration, rust at metal connections, weathered concrete, dust, paint variation,
   surface damage. Realism, not an abandoned city.
7. RENDER AND VERIFY: render the exact same camera composition as the previous iteration;
   compare against the previous version; identify which improvements are actually visible.
   Do not report an improvement because more objects or polygons exist. The final image
   must show substantially improved photorealism.
