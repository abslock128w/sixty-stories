# Credits and third-party assets

Every third-party asset used anywhere in this project is listed here: name, source URL, licence.


## Hero (VESPER) — HERO builder
- MakeHuman base mesh `hm08` (`makehuman/data/3dobjs/base.obj`), macro/detail morph targets (`makehuman/data/targets/...`), default skeleton (`makehuman/data/rigs/default.mhskel`) and its skin weights (`default_weights.mhw`). Source: https://github.com/makehumancommunity/makehuman . Licence: CC0 1.0 (assets released to CC0 in 2020 by Data Collection AB, Joel Palmius, Jonas Hauquier; see `blender/hero/mh_data/LICENSE.ASSETS.md`). Used only as data (parsed by our own scripts); the body was reshaped, re-topologised at the head, re-rigged and fully re-surfaced for VESPER.
- Everything else on the hero (cowl, visor, suit design, armour, launchers, belt, materials, line) is procedural and original to this project.

## Facade asset — scanned PBR textures (`blender/assets/tex_scan/`)
All from Poly Haven (https://polyhaven.com), licence CC0 1.0 (https://polyhaven.com/license). polyhaven.com itself is
not reachable from the build machine, so the files were taken unchanged from public GitHub mirrors (file sizes match
Poly Haven's published sizes where those are recorded):
- `red_brick` (diff / nor_gl / rough, 2k) — https://polyhaven.com/a/red_brick ; mirror: github.com/boku-ilen/landscapelab `Resources/Textures/Buildings/brick/`.
- `hangar_concrete_floor` (diff / nor_gl / rough, 4k, author Dimitrios Savva) — https://polyhaven.com/a/hangar_concrete_floor ; mirror: github.com/Kitjesen/MapPilot `sim/library/sources/polyhaven/textures/hangar_concrete_floor/4k/` (with source.json).
- `concrete_pavement`, `asphalt_02` (diff / nor_gl / arm, 2k) — https://polyhaven.com/a/concrete_pavement , https://polyhaven.com/a/asphalt_02 ; mirror: github.com/kennyhassmusic/sky-city `SourceArt/CC0/polyhaven/`.
- `rust_coarse_01` (diff / rough, 4k) — https://polyhaven.com/a/rust_coarse_01 ; mirror: github.com/tingyunaiai9/Echo-of-Time `Assets/Arts/Materials/`.
- `painted_concrete` (diff / rough, 2k) — https://polyhaven.com/a/painted_concrete ; mirror: github.com/taesiri/meter-ocr `assets/tex/`.
They are combined with procedural variation and geometry-driven weathering masks in `facade.py`; nothing else is third-party.
