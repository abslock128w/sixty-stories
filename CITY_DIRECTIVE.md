# Owner's master directive for the city (2026-11-16, condensed faithfully; this is the standard)

Benchmark: the environmental fidelity, density, materials, lighting, reflections and
environmental storytelling of a current AAA open-world superhero game set in Manhattan
(reference stills: refs/ref_street.webp, refs/ref_aerial.webp). Use the quality as the bar;
create an ORIGINAL city: no copied assets, characters, logos, brands or specific places.
It must look like a real place photographed with a cinema camera, and hold up when the
camera moves close to buildings, streets, vehicles, storefronts. Never trade quality for
speed. Render time is unlimited.

## 1. City design and scale
Dense financial downtown; glass-and-steel skyscrapers; mid-rise commercial; residential
blocks; older brick buildings; distinctive landmarks; shopping streets; narrow side streets
and alleys; restaurants, cafes, convenience stores; rooftop mechanical structures; parking
structures; parks, plazas, green space; a waterfront; bridges, underpasses, elevated
infrastructure; service roads and loading areas. Coherent architectural identity, proper
grid, real road widths, setbacks, sidewalks, intersections, crossings, street hierarchy,
believable district transitions. Composed skyline silhouette; no repetitive skyscrapers;
every major building has its own identity. Real-world dimensions everywhere.

## 2. Architectural detail (top priority)
No boxes with a window texture: real depth. Facades: individual frames, recessed windows,
glass thickness, mullions, columns, slabs, cladding, brick patterns, stone panels, metal
panel joints, cornices, balconies, railings, fire escapes, drainpipes, AC units, conduits,
exterior light fixtures, vent grilles, signage, entrance canopies, ledges, building numbers,
maintenance structures. Glass: plausible reflections, Fresnel, tint and reflection
variation, interior visibility, frame depth, roughness variation, dirt; reflects neighbours
and sky; never uniformly clean/blue/mirror. Rooftops as functional spaces: HVAC, ducts,
water tanks, elevator machinery, electrical gear, antennas, dishes, walkways, railings,
access doors, skylights, drainage, pipes and cable trays, some roof gardens; believable
from a neighbouring tower.

## 3. Street level (critical)
Roads: aggregate texture, patches, cracks, faded lane markings, crossings, stop lines,
manholes, drain grates, utility covers, oil stains, tyre marks, potholes, repairs, studs,
arrows, parking markings, curb transitions. Sidewalks: individual slabs, joints, cracks,
damaged edges, tactile paving, curbs, storm drains, covers, ramps, steps, mixed materials,
weeds. Furniture: streetlights, signals, road signs, parking meters, hydrants, utility
poles, electrical boxes, newspaper boxes, trash and recycling bins, benches, bollards, bike
racks, bus shelters, ad panels, notice boards, security cameras; all correctly placed,
scaled and grounded. Micro-detail with controlled randomness: stickers, small posters,
graffiti, faded paint, rust at bolts, dirt at building bases, water stains, weathered
signs, scratches, dust on ledges, discolouration at vents, cable bundles, construction
materials, litter, leaves.

## 4. Storefronts and interiors
Real businesses with identities (restaurants, cafes, grocers, convenience, clothing,
pharmacies, offices, banks, small shops): unique signage, display windows, doors, interior
lighting, visible shelves/furniture/products, real depth, glass reflections. Some windows
reveal detailed interiors; mix of lit and unlit; offices with desks, chairs, screens,
plants, ceiling lights, partitions, people silhouettes. No two windows identical.

## 5. Vehicles and life
Cars, taxis, vans, buses, trucks, motorcycles, bicycles with proper geometry, glass,
wheels, lights, mirrors, tyres, material variation; natural traffic distribution.
Pedestrians at intersections, sidewalks, storefronts, plazas, transit: varied bodies,
clothes, poses, groups, believable activities.

## 6. Vegetation
Street, ornamental and mature trees, shrubs, planters, grass, ground cover, climbers, roof
and park vegetation; real leaf geometry; variation in colour, scale, orientation, density;
no obvious repeats; correct contact with paving and planters.

## 7. Materials
Physically plausible Principled library: concrete, asphalt, brick, granite, marble, painted
metal, stainless, aluminium, architectural glass, wood, plastic, rubber, road paint,
ceramic tile, weathered stone, dirt, wet surfaces; base colour, roughness, metallic,
normal/bump, displacement where justified, imperfections, variation; no visible tiling;
every surface reacts differently to light.

## 8. Lighting
Physically believable: sky/sun, global illumination, accurate shadows, reflections,
interior sources, streetlights with real pools of light, signals, shop light, billboard
light, rooftop warning lights, architectural lighting. Windows warm/cool/dark, never
uniform. Aerial perspective without fogging the whole city. Reflections (towers, car paint,
wet asphalt, shop glass, water, metal) must correspond to real sources and geometry.

## 9. Weather and storytelling
Not artificially clean: slightly wet roads, stains, weathering, uneven paving, dust, subtle
fog, leaves, puddles, condensation, dirt at drains. Storytelling vignettes: outdoor
restaurant seating, a delivery van at a loading door, maintenance gear on a roof,
construction barriers at a sidewalk repair, a chained bicycle, trash bags outside a shop.

## 10. Cameras
Showcase compositions at minimum: aerial skyline; rooftop view across the city; street
architectural shot; narrow alley; commercial avenue with vehicles and people; waterfront
skyline; close-up facade. Real focal lengths, composed framing, natural DOF, proper
exposure, controlled highlight roll-off; no excessive DOF, bloom, flares or saturation.

## 11. Technical
Built by Blender Python: modular, configurable generators (footprints, heights, facades,
windows, rooftops, storefronts, furniture, roads, sidewalks, vegetation); linked
duplicates, Geometry Nodes, collections, instancing, bevels where they catch light, correct
normals; LOD near/mid/far with far buildings still convincing. Organised scene; modular
scripts; the saved .blend contains the constructed city.

## 12. Quality control
Frequent preview renders from many distances; fix anything artificial, repetitive,
floating, mis-scaled or unfinished: floating objects, intersections, repeated facades,
window proportions, missing shadows, wrong reflections, repeated vegetation, UV stretching,
lighting inconsistencies, visible procedural repetition.

## 13. Stages
1 world foundation; 2 architecture; 3 high-detail assets; 4 street environment;
5 materials; 6 lighting; 7 cinematic presentation; 8 quality assurance, repeated until it
reaches the bar. A stage is not done because geometry exists: it must look convincing.

## 14. Non-negotiables
Never call a basic procedural city complete; never rely on flat textures for major
structure; never repeat identical buildings; never leave empty or artificial areas in
important views; never uniformly clean materials; never floating or misplaced objects;
never ignore scale; never use lighting to hide weak geometry/materials; never favour
building count over credibility; never stop at the skyline; never claim a feature exists
unless it is in the scene; never silently skip a hard feature: build the achievable
alternative and document the limit.

## 15. Deliverables
Editable .blend; all generation scripts; reusable asset system; material library;
organised hierarchy; multiple cinematic renders; a short production report of what is
implemented, limitations and optimisation decisions.
