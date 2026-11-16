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
