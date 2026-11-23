# Facade realism audit (phase 1, 2026-11-23)

Inspected: `blender/out/preview/assets/facade_v1/` (facade_full, facade_wall, facade_window_close,
facade_shopfront, facade_fire_escape, facade_dusk) and the builder `facade.py` / `facade_proofs.py`.
Verdict: it reads as a clean archviz model, not a photographed street. The causes, by subsystem:

## Brick (facade_wall, facade_window_close)
- Every brick is a flat, clean colour pick from an 8-entry palette with a mild noise tint; the face has
  no clay texture, no pores, no fire-skin, no spalls or chipped arrises. At 2 m it reads as a printed
  brick-slip wallpaper.
- Colour contrast between bricks is high but the *spatial* structure is white noise: no batches, no
  kiln flashing, no darker headers, no repairs/repointing patches. That is the classic procedural tell.
- Mortar is a uniform pale grey, a perfect 10 mm everywhere, perfectly flush-recessed, no dirt in the
  bed joints, no erosion, no smearing onto the brick faces. Joints look drawn.
- No staining logic: nothing darker under sills, no run-off below lintels and cornice, no soot band
  under the cornice, no green/black splash zone above the sidewalk. The few dirt patches that exist are
  round blobs ("random dirt") – e.g. the pale disc on the wall right of the balcony in facade_wall.
- Jack arches are perfectly clean and the same tone as the field; the keystone is a crisp white stick.

## Windows and glass (facade_window_close, facade_wall, facade_full)
- Glass is a clean mirror: no dust film, no tint variance between panes/units, no rain marks, no
  wavy old panes, so reflections of the neighbours are too perfect and dark ("black glass").
- Frames are one flat paint, no chipped edges, no putty line, no gaskets/seals, no dirt in the
  sash corners, no sill grime. Stone sills are clean and crisp.
- Interiors (upper floors) are mostly empty boxes with a lone plant; at dusk every lit room is the
  same flat white box. The building doesn't look occupied.

## Storefronts (facade_shopfront)
- Bakery products are plain coloured boxes on shelves ("books"), loaves are faceted low-poly
  wedges; nothing reads as bread, pastry or cake. No display case, register, menu board or packaging
  readable.
- Shopfront joinery is clean CG paint: no wear on the stallriser, no kick marks, no dirt line at
  the base, no handle/hinge detail. Stone piers and pilasters perfectly clean and evenly lit.
- Sign letters perfect, no weathering behind/around them.

## Awnings
- Flat smooth planes with a satin sheen; no canvas weave, no seams between widths, no stitched hems,
  no valance scallop/edge fray, no sag between arms, no tension folds, no fading on the sun face, no
  dirt along the bottom edge. Reads as painted sheet metal.

## Fire escape, metal (facade_fire_escape, facade_full)
- One flat, slightly glossy blue-black paint on everything; no welds, bolts, overpaint drips, wear on
  treads and handrails, or rust at joints/brackets; no rust streaks running down the brick below.
- Same paint-roughness as the window frames and shopfront: materials don't separate.

## Stone, concrete, sidewalk (facade_full, facade_shopfront)
- Stone trim and the ground floor rustication are a single pale, crisp, clean material.
- The sidewalk is a pale, nearly uniform slab: no slab joints at street scale, no gum, stains, oil,
  edge wear, curb grime or dark wet zone at the building base. It dominates the frame in facade_full
  and is the single largest "CG" tell there.

## Lighting and camera
- Midday-ish neutral sky fill with a weak sun; contact shadows under sills, cornice and awning are
  weak, there is little warm bounce from the street, and the ground floor looks flatly lit.
- The interior/exterior exposure story is missing in daylight: shop interiors are as bright as the
  street (no window-reflection dominance), upper rooms are either black or flat white.
- Dusk: lit rooms are pure white boxes; street lamps barely contribute; everything else crushes.
- The wall shot shows obvious denoiser smearing (soft, painterly brick in facade_wall), i.e. too few
  samples / too strong prefilter for close-ups.

## Repetition / "default material" tells
- Identical window units with identical blinds/curtains positions floor after floor.
- Uniform roughness ~0.5–0.8 across paint, metal, stone: everything has the same specular response.

## Plan (by brief phase)
2 Brick: per-brick faces sampled from a CC0 scanned brick set (Poly Haven `red_brick`), remapped per
  brick into our coursing; batch/kiln variation; irregular, dirty, eroded mortar; gravity masks
  (under sills/cornice run-off, soot under cornice, ground splash).
3 Windows: dusty/streaked glass with per-pane tint and wave, gaskets/putty, frame wear; furnished,
  varied interiors.
4 Storefronts: modelled bread/baguettes/pastries/cakes, display case, register, menu board;
  canvas awning with weave, seams, sag and fading.
5–8 Weathering, scanned concrete/asphalt/rust for secondary materials, golden-hour lighting with
  stronger bounce and contact shadows, purposeful detail.
