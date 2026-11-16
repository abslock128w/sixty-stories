# City production report

Entries are appended per stage. They list only what is actually in `blender/out/city.blend`.

## 2026-11-16, Stage 1: hero avenue street level and lower ten storeys

Rebuild with `/home/user/tools/bl/bin/python blender/city/build_city.py`: about 70 s, 11.6k objects, peak RAM about 3.2 GB at 1280 px.

Proof renders (1280 px, 32 spp, 4 threads, in `blender/out/preview/city/`):

| File | View | Render time |
|---|---|---|
| `s_street.png` | Street level, matched to `refs/ref_street.webp` | 82 s |
| `s_dusk.png` | Same view at dusk | 77 s |
| `b.png` | Canyon | 81 s |
| `a.png` | Aerial | 48 s |

### Now in the scene

**Advertising system** (`adgen.py`, `signage.py`)
- A 64-ad procedural atlas, generated with PIL at 4096x4096 and packed into the blend. Every brand, title and slogan is invented.
- Ad types: product, fashion figure, movie poster, theatre show, logo lightbox, type-only.
- Ten aspect ratios, from 0.33 to 4.0.
- Placed on near-ring buildings that face the avenue:

| Item | Count |
|---|---|
| Printed billboards (catwalks and lamp arms) | 42 |
| LED screens (pixel grid, self-lit by day, brighter at dusk via `street_emit`) | 21 |
| Blade signs (ads on both faces, neon edge) | 31 |
| Theatre marquees (bulb fascia, bulb soffit, letterboard) | 7 |
| Lightboxes over shopfronts | 194 |
| Neon window words (bevelled tube text in pink, cyan, green and amber) | 64 |
| Corner LED wraps (avenue face plus cross-street face) | 20 |

The 95 text shop signs from round 1 remain.

**Street furniture**
- New:
  - Subway entrances (railings, dark stairwell, green globe lamps): 18.
  - Lamp-post banners: 70.
  - Corner bollards: 324.
  - Mailboxes: 50.
  - Lit newsstand kiosks with ad panels.
  - Planters.
  - Building flags (fictional stripes).
  - Storm-drain grates at every curb approach.
- Already present: lamps, mast-arm signals, hydrants, trash cans, newsboxes, bus shelters, trees, awnings, sidewalk sheds, steam vents.

**Storytelling vignettes**
- Trash-bag piles.
- Outdoor cafe sets with parasols.
- Bicycles locked at the curb.
- Construction barriers with cones.

**People**
- Six pedestrian models in four poses (two walking strides, standing, on a phone).
- Built from tapered limbs, with shoulders, shoes, a two-tone head and hair.
- Shirt and trouser colours are randomised per instance.
- About 2,000 placed on the avenue sidewalks, waiting at crossings and crossing the cross streets. The old box figures are replaced.

**Vehicles**
- Eleven types: sedan, town car (black), hatchback, SUV, pickup, cab, cab SUV, van, step van, box truck, bus.
- New types replace old ones in place, so traffic counts and lanes in `city_meta.json` are unchanged.
- Taxi roof signs reduced to their real size.

**Road and sidewalk**
- Asphalt now has:
  - Hairline cracks.
  - Tar-sealed crack lines.
  - Patches, wheel tracks and wet edges near the curbs (from earlier rounds).
- Sidewalks now have slab cracks.
- Already present: markings, crosswalks, stop lines and manholes.

**Aerial additions (first pass)**
- A park, 464 x 430 m: grass, a pond, paths, 1,089 trees. It replaces far-ring lots more than 250 m from the hero avenue, so no `city_meta.json` building changes.
- Three suspension bridges (towers, catenary cables, suspenders, decks, approach ramps).
- 260 industrial shapes on the far shores.
- Copper-patina pyramids and spires on about half of the Deco crowns.
- Far-facade window grids fade into the wall with distance.

**Unchanged:** `city_meta.json` is byte-identical apart from its `counts` block.

### Not yet in the scene

- **No real storefront businesses with branded interiors.** Shopfronts show generic shop modules (shelves, counter, person) behind glass, plus lightboxes and neon.
- **Missing street furniture:**
  - Parking meters.
  - Utility poles and electrical boxes.
  - Benches and bike racks.
  - Security cameras.
  - Notice boards.
- **Missing road detail:**
  - Tactile paving.
  - Curb ramps.
  - Arrows and studs.
  - Weeds.
- **Missing surface micro-detail:**
  - Stickers.
  - Graffiti.
  - Rust at bolts.
  - Leaves and litter beyond the trash bags.
- **Vehicles are box-built:**
  - No mirrors.
  - No wheel arches.
  - No motorcycles.
  - No moving bicycles; the only bicycles are the parked ones.
- **Facades:**
  - No drainpipes, conduits or building numbers.
  - Retail podiums are not separate masses, because tiers are frozen in the meta.
- **Places not built:**
  - Alleys.
  - Waterfront promenade.
  - Underpasses.
  - Parking structures.
- **No showcase cameras yet** (`CAMERAS_SHOWCASE`).

### Gap against `refs/ref_street.webp` (honest)

**Where ours is behind:**
1. **Building variety and identity.** The reference has a red-brick tower with a copper crown, a white-stone tower, a glass grid and a dark steel tower side by side. Ours still reads as a repeated family of dark masonry and glass slabs.
2. **Signage hierarchy.** The reference's screens follow the architecture: wraps, vertical bands, layered sizes. Ours are flat panels, several of them very large and evenly bright.
3. **Vehicles.** Box-like at close range: no rounded bodies, mirrors or wheel arches. The white box trucks read as plain blocks.
4. **Pedestrians.** Simple shapes; acceptable at 20 m and beyond, not closer.
5. **Street-level glazing.** The east-side curtain-wall ground floors read as striped bars.
6. **Lighting at street level.** Ours is hazier and warmer overall. The reference has cleaner air near the camera and crisper sun on the upper floors.

**Where ours is on par:**
- Density of signs.
- Traffic queues.
- Number of pedestrians.
- Lamp, signal and crosswalk dressing.
- The glowing vanishing point.

### Gap against `refs/ref_aerial.webp`

- Ours is foggier and flatter. The reference keeps near towers crisp and fades only the far distance.
- Building silhouettes are still too uniform. There are few named-landmark-grade crowns.
- The park and bridges exist but are not in the `a` camera's view.

## 2026-11-16, Stage 1b: building identity, vehicles, signage integration

Proofs: `s_street.png`, `s_dusk.png`, `car_close.png` (1280 px, 32 spp, 4 threads, about 85 s each, about 3.2 GB).

### Now in the scene

**New archetypes** (`library.py`, now 25 in total)
- White-stone bank: heavy cornice, rusticated granite-tone base.
- Terracotta apartments with fire escapes.
- Red-brick Deco tower with a copper-patina crown.
- Terracotta Deco hotel, also with a patina crown.
- White Deco tower.
- Dark steel-and-glass grid (deep 0.45 m fins).
- Green-glass office.

**Facade palettes**
- Existing masonry palettes brightened and widened, so neighbouring frontages differ in value and hue.

**Base, middle and top treatment**
- Archetypes flagged `base_trim` get thicker base piers in the trim material plus a string course at the top of the shop zone.

**Curtain-wall shopfronts are now real bays**
- Stall riser, bay mullions, a door frame on every third bay, and the sign band.
- This replaces the bare striped glass.

**Signage**
- Big billboards are capped at about 10 m tall and 75% of the frontage.
- New layer of paste-up posters at street level, 1.1–1.6 m, on masonry bases.
- Overall layering is now: posters, then lightboxes, then mid boards and blades, then a few big boards.

**Vehicles v2** (`vehicles.py`)
- Lofted bodies with a raked windscreen and backlight, tumblehome greenhouse, pillars, and glass assigned per face.
- Wheel-arch liners, round tyres with shoulders, dished 5-spoke rims, hub caps.
- Head-lamp units with chrome surrounds, grille, bumpers, front and rear plates, door shut lines, mirrors.
- Pickup with an open bed.
- Vans and trucks: cab with raked windscreen, side glass, mirrors and grille; ad liveries from the atlas on the cargo sides.
- Bus: window bands, pillars, livery stripe, destination sign.

**New vehicle types**
- 40 motorcycles with riders.
- Cyclists ridden in the bike lane.

### Still short

- **Car bodies are still faceted** up close:
  - The cross-section has only 9 points per side.
  - No body creases.
  - Tyres show from the side only.
- **Signage is still flat panels on frames.** It is not built into the architecture as the reference's wraps and vertical LED columns are.
- **The east-side glass podium still reads uniform from distance.**
- **Building identity is better but still not a lineup of nameable landmarks.** The left wall reads as varied masonry, but there are no strongly distinct silhouettes at street height.

## 2026-11-16, Stages 2–6 (condensed pass): Tower surroundings and dive, rooftops, aerial, waterfront, showcase cameras

Proofs: `e.png`, `c.png`, and the seven `showcase_*.png` (1280 px, 32 spp, 4 threads, 52–89 s each).

### Now in the scene

**Rooftop kit v2** (on near-ring library buildings, placed by their own RNG)
- Bulkheads: concrete, steel door, louvre, light.
- Satellite dishes.
- Skylights.
- Pipe racks and cable trays with walkway gratings.
- HVAC units repainted grey-beige with fan grilles and side louvres.
- Also present from earlier rounds: duct runs, tanks set back at least 14 m from the avenue, roof terraces with furniture, parapets and cornices.

**Aerial**
- `aerial` preset re-tuned: haze 0.00012 with a darker, partly absorbing haze colour (0.18) and exposure +0.5.
  - Near towers are now crisper; the far city fades to warm haze.
  - Window grids fade with distance.
- Also present:
  - Patina crowns.
  - The park (pond, paths, 1,089 trees).
  - Three suspension bridges. Main cables are now smooth square tubes; they were staircase boxes before.
  - Far-shore industry.

**Waterfront**
- North-shore promenade: paving strip, steel railing with balusters, street lamps every 25 m, trees, cafe sets, people.

**Showcase cameras**
- Collection `CAMERAS_SHOWCASE` with the seven directive compositions:
  - Aerial skyline (30 mm).
  - Rooftop view across the city, from The Tower's setback roof (30 mm).
  - Street architecture, looking up at The Tower (18 mm).
  - Side street (40 mm, f/5.6).
  - Commercial avenue (22 mm).
  - Waterfront skyline from the east shore (50 mm).
  - Close-up facade (35 mm, f/5.6).
- Rendered with `render_showcase.py`.

### Not done, or short (honest)

**Stage 3: skybridge towers**
- No dedicated work this pass.
- They are the library's blue-glass office archetype with rooms and shopfront bays.
- No bespoke lobby, crown or bridge-junction detail beyond round 1's bridges.

**Stage 2: around The Tower**
- The neighbours use the library and rooftop kit.
- Nothing bespoke was added around the dive line.
- In the dive view, the roofs far below read as dark flat planes with small scattered units.

**Alleys**
- None. The block layout has no alley slots, and lots are frozen.
- The side-street camera uses an 18 m cross street instead.

**Cross streets**
- Empty: no traffic, people or signage. Trees and lamps exist.
- Street dressing so far is concentrated on the hero avenue.

**Waterfront**
- The far shores are low boxes with shader windows.
- The waterline is a straight seawall.
- No piers or boats.

**Aerial**
- Still more uniform in silhouette than the reference.
- The near city is backlit and dark because the camera looks into the sun.
- The horizon land plane reads as a flat band.

**Street items still missing**
- Parking meters, utility poles and electrical boxes, benches, bike racks, security cameras, notice boards.
- Tactile paving, curb ramps, arrows, weeds.
- Stickers, graffiti, rust, litter and leaves.
- Drainpipes, conduits, building numbers.

**Vehicle close-up**
- Still faceted, as noted in Stage 1b.

## 2026-11-16, Realism overhaul (CITY_OVERHAUL.md), priorities 1–4

The `s_street` camera was held fixed throughout. Step renders (1280 px, 64 spp) are in `blender/out/preview/city/`:
- `overhaul_00_before.png`: the scene before this overhaul, rendered from the committed city at 32 spp.
- `overhaul_01_facades.png`, `overhaul_03_road.png`, `overhaul_04_storefronts.png`: the same camera after each step.
- No `overhaul_02` full-view image exists. Vehicles were improved in the same build as facades, so their proofs are `overhaul_02_vehicles_close.png` and `car_close.png`.
- Close-ups: `car_close.png`, `road_close.png`, `base_close.png`.

### Step 1: facades

**Avenue frontages split into separate sub-buildings** (`buildings.street_wall`)
- The avenue-facing faces of library lots are split into street-wall buildings 12–28 m wide.
- Each sub-building has its own style family, wall and trim material (brick, light stone, buff brick, terracotta, glass, panel), colour, storey height and window rhythm.
- Heights vary: 3 to 14 storeys plus the storefront zone.
- Each has a cornice and parapet line.
- Recessed party-wall joints sit between sub-buildings.
- Above each sub-building, the lot's main tower facade continues.
- Lot envelopes, tiers and meta values are unchanged.

**Added to sub-buildings**
- Balconies on some residential sub-buildings: slab plus steel railing with balusters.
- An entrance canopy and door surround on each.

### Step 2: vehicles

**Cars, taxis, SUVs and pickups**
- Bodies are rebuilt as two bevelled solids: lower body and greenhouse, 3-segment rounded edges.
- Tumblehome: the body sides and greenhouse narrow toward the top.
- Glass versus paint is assigned by face orientation, so the rounded corners read as A and C pillars.
- Two-part B pillars.
- A side character line.
- Wheel openings are dark half-discs, with the tyres slightly proud of them.
- Larger tail-lamp units with surrounds.

**Trucks, vans and buses**
- Bevelled throughout (0.035–0.06 m).
- Wheel offsets corrected.
- Livery text is no longer mirrored on the right-hand side.

**Daytime lamps**
- Tail-lamp and head-lamp intensity reduced.

### Step 3: road

**Asphalt**
- Cracks are now a sparse, noise-distorted network. The old cellular pattern read as hexagons up close.
- Aggregate speckle.
- Oil drips down the lane centres.
- Roughness varies with oil and stone.

**Markings and plates**
- Road paint (white, yellow and the green bike lane) is worn by tyre paths, with grime.
- 30 steel road plates.

**Unchanged:** sidewalk material (joints and cracks from stage 1), tactile strips, drains.

### Step 4: storefronts

**Five business interiors behind shop glass**, alternating with the generic shop module
- Cafe: counter, espresso machine, menu board, window bar with stools, pendants, staff and customer.
- Grocer: glowing fridges, produce crates at the window, centre shelving unit.
- Clothing: mannequins in the window, rails of garments, mirror, display table.
- Pharmacy: white shelving packed with products, counter, back-lit sign.
- Restaurant: tables with cloths, pendants, seated diners, bar and bottle wall.

**Shop fit-out**
- Dark tiled floors, panelled side walls, timber back wall, ceiling band, downlights.

**Masonry storefront frames**
- Metal frames with jambs, transom bar, centre mullion, and a recessed door every third bay.

### Still looks procedural (honest)

**Main facades above the street wall**
- Still repeated pier-and-window grids per building.
- No exterior pipes, structural beams or panel joints as geometry.

**People**
- Pedestrians and the figures inside rooms are blocky low-poly shapes.

**Vehicles**
- Read as toys up close: simple wheel discs, no door handles, no interior.
- Buses and trucks are still boxy.

**Road and sidewalk**
- Improvements are mostly invisible at `s_street` distance. They show only in the close-ups.
- Not added: potholes, curb ramps, damaged slab geometry.

**Storefronts at street distance**
- They read as pale or colour-lit slabs.
- No outdoor product displays or A-frame signs.

**Not yet done**
- Lighting (priority 7): the end of the avenue is still over-exposed.
- Street-object wear (priority 5).
- Material pass (priority 6).

## 2026-11-16, Overhaul A (vehicles) and B (lighting)

New renders in `blender/out/preview/city/`:
- `overhaul_05_vehicles_close.png` (`car_close`).
- `overhaul_05_bus_truck_close.png` (`bus_close`). It shows a cab in the foreground with a bus behind; no truck is in frame.
- `overhaul_06_lighting.png`: the fixed `s_street` view.
- `xstreet_close.png`: an unplanned cross-street view.

### A. Vehicles

**Search for free models**
- I spent about 15 minutes looking on public GitHub for CC0 or MIT vehicle models.
- The only CC0 model set found, a USD port of Poly Haven assets, has no vehicles.
- Nothing usable was found, so vehicles stay procedural. Nothing was imported, so `CREDITS.md` is unchanged.

**Car bodies**
- Larger, rounder bevels: 0.15 m on the lower body, 0.11 m on the glass cabin, 4 segments each.
- Proportions changed: more steeply raked windscreens and rear glass, higher beltline, 0.36–0.40 m wheels.

**Lamps**
- Wrap-around lamp clusters at all four corners, each with a chrome bezel, lens, and a side-wrap section.
- Rear clusters have an amber indicator; front clusters have a daytime running-light strip.

**Wheels**
- Cars: 10-spoke split alloys with a concave barrel, centre cap and hub.
- Trucks and buses: steel disc wheels with 10 hand holes, hub and 8 nuts.

**Interior**
- Seats, dashboard, steering wheel and a driver figure, visible through the new see-through glass.

**Exterior details**
- Door handles and wipers.

**Materials**
- `car_glass` now reflects at grazing angles and is tinted see-through at normal incidence.
- Car paint now has a clearcoat, a metallic-flake bump, and road dirt on the lower panels.
- The taxi's yellow paint uses the same layered material.

**Contact shadows**
- A soft shadow decal sits under every car, truck and bus.

**Bug fixed**
- Props and vehicles were using the room material `room_dark`, which became emissive in round 5. Grilles, bumpers, wheel wells and drain grates glowed pale.
- They now use a new `black_trim` material.

### B. Lighting

**Canyon haze**
- The canyon haze box is now heterogeneous: noise breaks it into blobs of 0.25–1.6× density, so the shafts vary.
- Its density multiplier dropped from 3.0 to 2.2.
- Haze anisotropy dropped from 0.80 to 0.68. Together these reduce the blown-out glow at the end of the avenue.

**Canyon preset**
- `sky_strength` raised to 0.24 for more fill in the shade; `exposure` set to 1.3.

**Shop interiors**
- About 2.4× brighter, via a new per-instance room brightness attribute `rb`.

### Honest list

**Cars**
- Still read as boxy 1980s sedans, not modern curved cars.
- The B-pillar boxes and mirrors protrude as visible blocks in close-up.
- No modelled headlight lens interior.

**Buses and trucks**
- Bodies are still boxy.

**Lighting**
- The sky at the end of the avenue still clips to white.
- Contact shadows exist only for vehicles, not for street furniture.
- No light falls on the street from shop interiors, because room surfaces are emission-only.

## 2026-11-16, Pass 03 (CITY_PASS03.md), items 1–3

The `s_street` camera was held fixed. Renders are 1280 px, 64 spp, 4 threads, about 150 s per frame, peak 3.6–3.8 GB, all in `blender/out/preview/city/`.

Scene copies kept before each rebuild:
- `blender/out/city_pass02.blend`: made by the orchestrator before item 1.
- `city_pass03.blend`: before the item 1 rebuild.
- `city_pass04.blend`: before the item 2 rebuild.
- `city_pass05.blend`: before the item 3 rebuild.

### Item 1: vehicles (`vehicles2.py`)

**What was built**
- **Cars:** bodies built from clean low-poly cross-section cages, 14→18 points per ring, never collapsed.
  - Holding loops around every window, Catmull-Clark subdivision level 2 applied at build time.
  - Glass assigned on cage faces (side windows between pillars, windscreen, rear glass).
  - Designs: sedan (also used for the town car and the taxi) and crossover (also used for the SUV, hatch and crossover taxi).
  - Details: mirrors on stalks with chrome glass (no floating blocks); lamp clusters tucked into the body corners; plates; rear diffuser; door handles; seats, dashboard, steering wheel and driver.
- **Panel van:** curved cab front, side glass at the cab only.
- **Box truck:** curved high cab with raked windscreen, cargo box with ribs and livery, under-ride bar, chassis, fuel tank.
- **City bus:** subdivided shell, glazed belt with mullions, front glass panel, destination sign, livery stripe, doors, mirror arms, roof pods, steel disc wheels.
- **Inside the body:** the inner surface of the shell is dark trim, so it no longer shows paint colour through the glass.

**Visible in `pass03_01_vehicles.png` (vs the previous `overhaul_08`)**
- Taxis and cars now have curved bodies and raked glass.
- The truck at the bottom centre has a rounded cab.

**Visible in `pass03_01_car_close.png`**
- Curved bodies.
- Tail lamps show only as small lit points; the lamp clusters are mostly inside the body.

### Item 2: materials (`materials.py`)

**What was built**
- **Brick v2:** running bond with a per-brick colour hash (clinker, light and dark bricks), recessed mortar joints with their own colour, chipped edges, efflorescence bloom, soot.
- **Concrete:** blotchy value variation, formwork joints at 2.4 x 1.2 m with tie holes, water stains, roughness variation.
- **`metal_dark` became worn metal:** scratches, rust patches, mild anisotropy.
- **Asphalt:** larger aggregate, plus darker repair strips along the lanes.

**Visible**
- `pass03_02_brick_close.png`: individual bricks and mortar are clearly visible on brick piers.
- `pass03_02_road_close.png`: worn paint and the patched road read.
- `pass03_02_materials.png` (full street view): no visible change from item 1 at this distance.

**Defects found**
- Pale speckles on sunlit stone. Direct-light clamp is now set to 8 to tame them; I have not confirmed the fix.
- A crossover tailgate-glass glitch. Fixed in the item 3 build, but not checked in a close-up.

### Item 3: interiors (`interiors.py`)

**What was built**
- New window-treatment variants added to the room mix:
  - Living room with drapes.
  - Kitchen with a roller blind 45% down.
  - Office with venetian blinds at 55% and 25%.
  - Meeting room with blinds at 80%.
  - Bedroom with a roller blind.
- Already present from round 5: lit/unlit mix, warm/cool tints, furniture, people, office desks, monitors and ceiling panels.

**Visible**
- `pass03_03_r_close.png`:
  - A kitchen with pendant lamps.
  - Shelving and a TV-lit living room.
  - Coloured walls.
  - The camera now frames a different building, because the street-wall subdivision changed what stands at that spot.
- `pass03_03_r_office.png`:
  - Glass office floors with desks, monitors, plants and ceiling lights.
  - Some floors show blinds partly lowered.
- `pass03_03_interiors.png` (full street view): no visible change from item 2 at this distance.
