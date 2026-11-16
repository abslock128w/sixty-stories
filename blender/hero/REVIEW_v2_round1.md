# Vesper v2, round 1: four independent critiques (full text)

Previews judged: blender/out/preview/hero/{a_turnaround,b_closeup,b_closeup_rear,c_poses,d_swing,e_details}.png and blender/out/looklab/cand_base/f_0090.png, f_0276.png.

The orchestrator has resolved the conflicts between these critiques in the message that points you here; where a critique disagrees with that message, the message wins.


## CHARACTER DESIGN (costume designer / character art director)  (score 4/10)

The palette does its job: cobalt against the orange city pops, the white yoke and white extremities carry the action through motion blur (d_swing), and the apex silhouette is clean. But as a film costume it is still a painted mannequin: the lenses are see-through with eyeballs behind them, the boots are bare feet with toes, the face shows nose and lips under a ski mask, and there is no seam, panel or sole anywhere. The back of the head, which fills the one close shot, is a blank blue egg. The two-tone blocking (blue body, white gloves, white boots, solid V yoke, diamond) also sits close to several generic team-uniform looks; it needs a third value and its own head design to read as Vesper.


### 1. [must] b_closeup.png and e_details.png (torso tile): the lenses
- Problem: The lenses are transparent amber glass, not mirrored gold. The base mesh's eye socket and eyeball are visible through them, so he reads as a man in a ski mask wearing sunglasses. The black frame is thick, uneven and stair-stepped along the top edge. In the turnaround the lenses are so small they read as one short brown bar.
- Change: Make the lens an opaque shell: metallic 1.0, roughness about 0.12, warm gold base, no transmission, with a little warm emission (about 0.3-0.5) so they stay the brightest thing on the head when backlit. Delete or hide the eyeball and socket geometry behind them. Replace the black outline with a real raised rim of even 3 mm width in dark gunmetal, lens inset 1-2 mm, built from a smooth curve so there is no stair-stepping. Enlarge each lens about 1.6-1.8x: inner corner low beside the nose bridge, straight upper edge as a brow line, convex lower edge, outer tip swept up and back about 20-25 degrees and ending just past the temple contour. Keep them gold and bladed, never white or teardrop.


### 2. [must] b_closeup_rear.png (the film's angle) and the back tile of e_details.png: rear of the cowl and neck
- Problem: The one close shot shows the back of the head, and there is nothing on it: a smooth bald dome, one neck wrinkle and an unstructured collar roll. No construction, no graphic and no material change, across a third of the frame.
- Change: Give the rear of the cowl real construction. (1) A raised centre seam or low ridge (2-3 mm) from the brow over the crown to the nape. (2) Two curved panel seams from each lens tip around above the ear to the nape, so the lens rim visibly continues as a temple arm. (3) A bone-white elongated kite on the crown and occiput, widest at the crown and coming to a point at the nape, gold-piped, so the back of the head carries the same motif as the chest. (4) A structured collar: a 15-20 mm stand band in darker navy with gold piping top and bottom where the cowl meets the yoke. (5) A fine knit micro-bump (twill or hex, about 1 mm scale) on the blue so the 135 mm shot shows fabric.


### 3. [must] b_closeup.png, lower left: the white shoulder panel; also boots and gauntlets in e_details.png
- Problem: The white panel is covered in wavy contour lines like a topographic map or wood grain. It looks like a shader error, not ribbing. The same lines on boots and gauntlets are uneven and bend with the mesh.
- Change: Remove the contour pattern from the white material. If ribbing is wanted, drive it from a clean coordinate along the limb, and only on the gauntlet cuff and boot shaft, as even 4-5 mm ribs via bump. The yoke should be a smooth semi-gloss panel (roughness about 0.35) with a faint edge bevel, no lines.


### 4. [must] e_details.png (feet tile), f_0090.png (perch), c_poses.png: the boots
- Problem: The boots are bare feet painted white. The big-toe cleft and toe bulges are visible, there is no sole to speak of, no ankle seam and no heel. On the perch the curled toes read even at film distance. This is the strongest pyjama signal on the figure.
- Change: Build a boot. Cover the toes with a smooth toe-box shell (a shrinkwrapped offset shell over the forefoot, or flatten the toes with a morph) so no toe separation shows. Add a split sole as geometry: a forefoot pad and a heel pad, 6-8 mm thick, dark navy-charcoal rubber with a tread bump, wrapping 10 mm up the sides. Keep it thin and split so pointed feet still look right. Add an ankle seam, a rear spine seam up the Achilles, and gold piping plus a 10 mm navy band along the diagonal boot top.


### 5. [must] b_closeup.png, e_details.png (torso tile), a_turnaround.png front: face and neck under the mask
- Problem: Lips, nostrils, chin and ear lumps show through the mask, which reads as a stretch morphsuit. From the front the head and neck form one cylinder of equal width, a blue thumb, with no jaw break; the head is narrow and tall.
- Change: Simplify the face to a moulded faceplate: with morphs or a thin smoothed shell over the face, keep brow, nose bridge, cheekbone plane and jawline, and remove lips, nostril detail and ears (cover each ear area with a small flat temple pod where the lens arm ends). Separate head from neck: colour the under-jaw and the neck column in the darker navy, with a seam along the jawline. Widen the cranium about 5-8% and slim the neck about 8-10% if the morphs allow.


### 6. [must] a_turnaround.png (all four views), c_poses.png: overall colour blocking
- Problem: From the sternum to mid-shin the figure is one unbroken flat blue, about 60% of the body, with only two values in the whole suit. That is the pyjama read. Blue body plus white gloves, white boots, a solid V yoke and a diamond also sits close to several generic team-uniform looks, so it is not yet distinct. The back view reads as a nude mannequin in paint (glute cleft, no design lines).
- Change: Add a third value, an ink navy at about 35-40% of the cobalt's brightness, slightly rougher. Use it for: side panels from the armpit down the flank to the hip and on down the inner thigh (this narrows the waist and builds the V taper); under-jaw and neck; palms and finger undersides; soles; a 10-12 mm trim line bordering every white panel inside the gold piping. Add a low waist seam: a 20 mm navy band with gold piping that dips to a point at front and back, echoing the yoke. Add curved seat and hamstring seams on the back so the rear has tailoring rather than anatomy.


### 7. [must] f_0090.png (perch) and d_swing.png: white gauntlets, hands and boots against pale haze
- Problem: In backlight the white panels fall into shadow and land on the same beige value as the haze and stone. On the perch the forearms, hands and shins nearly dissolve into the background, leaving a blue torso with stumps. The white hand on the line is weak against the pale sky.
- Change: Keep the white but give it edges. Dark navy palms and finger undersides, navy soles, and the navy trim band plus gold piping at the gauntlet top and boot top, so every white extremity has a dark boundary. Tint the white slightly cool (about 0.80, 0.84, 0.90) so in shadow it separates from the warm haze instead of matching it.


### 8. [should] a_turnaround.png front and 3/4: build and proportion
- Problem: He reads as a slim, ordinary young man: narrow shoulders, thin arms and forearms, little chest or lat mass. A world-class acrobat has a gymnast's shoulders, lats and forearms over a small waist. The pecs vanish under the flat white yoke.
- Change: Morph toward a gymnast: muscle and tone up about 15-20%, shoulders wider by about 6-8%, more deltoid, lat and forearm mass, calves slightly up, waist and hips unchanged or slightly narrower. Lengthen the legs 2-3% for about 8 heads if scale allows without breaking the frozen overall height; otherwise leave height alone. Let the navy side panels do the rest of the taper.


### 9. [should] e_details.png (torso tile), a_turnaround.png side view: arm stripe, yoke and gauntlet edges
- Problem: The outer-arm stripe ends in a soft rounded lobe above the elbow and the gauntlet top has a wobbly notch; it looks like spilled paint. The suit's own language is the kite: sharp points on the yoke, emblem, boot tops and lenses. The left arm shows no stripe from the front.
- Change: Make every termination a sharp taper. The arm stripe narrows steadily from the shoulder cap to a point that meets the point of the gauntlet top, or runs unbroken into the gauntlet. The gauntlet top becomes a clean diagonal with a point on the outer forearm, mirroring the boot top. Check that both arms carry the same stripe.


### 10. [should] a_turnaround.png front and back, d_swing.png: chest and back emblem and gold piping
- Problem: The emblem is small and, being mirror metal, reflects the ground and reads as a brown speck. On the back it floats below the yoke point. The gold piping is too thin to exist outside the close shot, so gold is not yet a working colour in the scheme.
- Change: Enlarge the emblem to an elongated kite about 12 cm tall on the chest and 16-18 cm on the back, with the top point touching the yoke point on both sides. Make it a bevelled plate with a satin yellow-gold finish that has a diffuse component (not a pure mirror) so it keeps its colour in shadow. Widen the piping to 6-8 mm tube geometry on the yoke edge, collar, gauntlet tops and boot tops.


### 11. [should] e_details.png (hand_L, launcher_R tiles), d_swing.png: wrist launchers and gloves
- Problem: The launchers read as a fitness band or watch: a small black box on a thin gold strap. The gloves are bare hands painted white, with no seams, pads or cuff structure.
- Change: Build each launcher into the gauntlet: a tapered kite-shaped housing 12-14 cm long on the underside of the forearm, gunmetal with a gold end cap and a visible nozzle at the wrist, held by two gold bands. Gloves: navy palm and finger pads, a knuckle panel seam on the back of the hand, a seam at the wrist.


### 12. [should] c_poses.png: perch_crouch and perch_look_up; f_0090.png
- Problem: The deep splayed-knee squat with one hand planted between the feet is the signature perch of the wall-crawler this character must not resemble. It also hunches him and hides the chest design.
- Change: If pose content can change under the same names: an asymmetric kneel, one knee down and one up, torso long and upright, one forearm resting across the raised knee, the other hand lightly on the ornament, head turned out. It reads as a diver or falconer waiting, and shows the yoke and emblem.


### 13. [should] c_poses.png: shoot_R, shoot_L, stand, leap and most airborne poses: hands
- Problem: Almost every pose has flat, fully splayed fingers, which reads as a mannequin. In the shoot poses the firing hand is a flat open palm, a stop sign, with no character of its own.
- Change: Give him one firing gesture of his own: a blade hand, fingers together and thumb tucked, pointing along the line, wrist cocked slightly down so the launcher nozzle clears it. Do not use any folded-finger gesture. Non-acting hands: relaxed half-curl. The gripping hand in swings: a closed fist around the line or a short toggle.


### 14. [should] c_poses.png: release_arch, freefall_spread, flip_tuck
- Problem: In release_arch and freefall_spread the spine curls forward (back rounded, head lost), so they read as a body folding or draped over a bar, not an arch; allow that the preview angle may exaggerate this. In flip_tuck the arms stick out forward instead of holding the tuck.
- Change: release_arch: hollow back, hips forward, chest open, arms swept back and wide, head back, toes pointed. freefall_spread: a skydiver's arch with the hips lowest, chest and thighs lifted, arms wide and slightly back. flip_tuck: hands on the shins, chin to chest, knees together. Point the toes in every airborne pose (swing_tuck has one flexed foot).


### 15. [nice] f_0276.png (apex silhouette) and b_closeup_rear.png: silhouette
- Problem: The silhouette is clean but anonymous: any slim human on a line. Only the swept lens tip, visible in the rear close-up, gives the outline a mark of its own.
- Change: Let the head carry the signature: with the larger lenses, extend each outer tip 10-15 mm past the skull contour as a small rigid winglet, so the head outline has two swept points from the front and rear three-quarter views. Do not add ears, forearm fins or a cape.


### 16. [nice] d_swing.png: the line and its attachment
- Problem: The line leaves a bundle at the fist and reads as a soft white strand.
- Change: A single taut, perfectly straight filament in pale gold, leaving the launcher nozzle under the wrist and passing through the closed fist, with no knot or coil at the hand.


### 17. [nice] c_poses.png: stand
- Problem: Arms held away from the body with open palms; it reads as a rig rest pose.
- Change: Weight on one leg, shoulders tilted against the hips, arms close, loose fists, chin slightly down.


**Keep:**
- Cobalt blue against the orange sunset: the complementary contrast is strong and the body holds its colour in the swing preview.
- The white yoke coming to a point at the sternum and at the back: the largest and most readable shape on the figure, and it survives motion blur in d_swing.
- White on the forearms, hands and lower legs: bright extremities trace the arcs of the limbs in motion, which is the right idea for an acrobat seen at 5-40 metres.
- The diagonal boot top and the kite or diamond motif as a consistent shape language.
- Gold, not white, for the lenses, and a bladed shape: this keeps him well away from white teardrop eyes.
- The swept lens tip breaking the head outline in the rear three-quarter close-up.
- The apex silhouette in f_0276: limbs separated, line of action clear, the line reads.
- The dive, leap, apex_classic and swing_R poses: long lines, pointed feet, good limb separation.
- No web pattern, no spider motif, no red anywhere.


## ORIGINALITY (resemblance to existing characters)  (score 4/10)

Vesper v2 is not a copy of any single character, and it is clean of the forbidden Spider-Man costume elements (no red, no webs, no spider, no white teardrop eyes). But it is not yet its own design: every part is a stock piece that somebody already owns, and at film distance a viewer would name it "the Blue Power Ranger", "a colour-inverted Nightwing", or, in the perch and apex shots, "Spider-Man in blue". The fix is cheap and almost entirely shader masks: drop the mirror-symmetric yoke, rhombus and matching gloves and boots, and build one asymmetric language from his own world (a raked kite sail, taut gold lines).

Nearest existing designs, strongest first:
1. **Blue Ranger family** (Mighty Morphin Blue, Zeo Blue / OhBlue, sentai blues such as Jetman's Blue Swallow) — strong. Blue body with four matching white extremities and angled cuffs, a white chest yoke, a diamond (the Mighty Morphin suit motif), a featureless helmet-smooth dome, and gold lenses that fuse into one visor at distance. Zeo Blue adds a triangular visor, gold collar and gold-banded white gloves. In c_poses this is the first name a lay viewer would say.
2. **Nightwing** — moderate, strong for comics readers. A shoulder-spanning chevron dropping to a sternum point, continuing down the outer arms toward the hands and repeated on the back, on a line-swinging city acrobat. In backlight the cobalt drops to navy (f_0090), so the read becomes light chevron on dark suit.
3. **Spider-Man family** (2099, Cosmic / Captain Universe) — weak on costume, strong as a gestalt. A skull-hugging full-face mask with two large angular lenses, a lean build, a frog-squat ledge perch with one hand planted, a one-hand swing with a tucked knee, and a thin white strand. 2099 has a blue mask with blade eyes; Cosmic has blue with white shoulders and chest. The apex silhouette (f_0276) is indistinguishable from Spider-Man.
4. **Cyclops** — moderate to weak. A blue cowl with a gold bar across the eyes; in the front turnaround the two lenses read as one visor.
5. **Blue Beetle (Ted Kord)** — weak to moderate. A blue cowled suit with amber lenses, on an acrobat who swings from a line.
6. **Minor contributors** — weak. Fantastic Four uniforms (blue with white gloves and boots), Angel's blue-and-white X-Factor suit, The Tick (all-blue bald head), and a gold diamond centred on a blue chest as an empty Superman shield.


### 1. [must] a_turnaround (front, back), c_poses, e_details torso/feet/hands: gold rhombus emblem plus four matching white extremities
- Problem: Blue suit, white gloves, white boots with angled cuffs and a centred diamond is the Mighty Morphin / Zeo Blue Ranger recipe (the diamond is that suit's signature motif; Zeo adds gold-banded white gloves). At the size of the c_poses thumbnails, which is the film's 5 to 40 m distance, this is the dominant read. The centred gold diamond on a blue chest also faintly echoes an empty Superman shield.
- Change: 1) Replace the filled symmetric rhombus with an open kite: an irregular quadrilateral with a short top third and a long tail, drawn only in gold piping with a vertical spine and one cross-spar so cobalt shows through. Tilt it about 20 degrees and move it off-centre to the left chest. The back gets the same kite about 2.5 times larger between the shoulder blades, same tilt. 2) Break the four matching extremities. Left arm: white to the fingertips as part of the sail (next issue). Right arm: cobalt, white on the hand only, up to the launcher band. Right leg: stretch the existing diagonal boot top into one long raked point reaching the outer knee. Left leg: white on the foot only, below the ankle bone. The white then balances diagonally (left arm, right leg) and no two limbs match.


### 2. [must] a_turnaround front/3-4/back, e_details torso and back, f_0090: white shoulder yoke with sternum point and outer-arm stripes
- Problem: A shoulder-to-shoulder chevron that points at the sternum, continues down the outer arms and repeats on the back is Nightwing's graphic, on a character with Nightwing's job (acrobat on lines over a city at dusk). In backlight the cobalt goes navy, so it becomes light chevron on dark suit. A symmetric V-yoke is also the standard sentai chest device and close to the Cosmic Spider-Man white upper body.
- Change: Delete the symmetric yoke and both arm stripes. Replace them with one asymmetric bone-white 'sail' with straight, taut edges. It covers the left shoulder cap, left pectoral, left shoulder blade and the whole left arm. Its front edge is a single straight line from the right side of the neck base to the left lower ribs. Its back edge is a straight line from the right side of the nape to the left waist. The two edges meet in a long tail point on the left hip bone. Use no V, no chevron and no mirrored shape anywhere on the torso. Finish the sail edges with the existing gold piping.


### 3. [must] b_closeup, b_closeup_rear, e_details helmet_side, a_turnaround front: head and lenses
- Problem: A single-colour skull-following full-face mask with two big angular lenses is the Spider-Man / 2099 mask template. In the front turnaround the lenses fuse across the nose into one gold bar, which reads as a Cyclops visor or a Zeo / Jetman bird visor. The swept triangle itself is the generic bird-of-prey eye. From the film's rear close-up angle the head is a blank blue dome with nothing of Vesper on it (and reads as The Tick or a zentai suit).
- Change: 1) Keep two gold mirrored lenses but reshape each as a sideways irregular kite (four corners, short inner edges, long outer tail) at about 60% of the current height. Stop the inner corners 12 to 15 mm short of the midline so a cobalt nose bridge always separates them. Do not enlarge them and do not add a white or pale rim. 2) Continue each lens's outer tip as 3 to 4 mm gold piping around the skull. The two lines converge at the nape and run down as one line into the back kite: bridle lines meeting the flying line, visible in the rear close-up. 3) Make the head two-tone: extend the white sail up the nape as a narrowing tongue that ends in an off-centre point on the left occiput. The 135 mm rear shot then shows a white kite tail, two converging gold lines and a lens tip.


### 4. [must] d_swing, f_0276 apex silhouette: the line and the hanging figure
- Problem: A slim figure hanging one-handed from a single thin white strand is Spider-Man in silhouette, whatever the suit colour, and the white strand in d_swing reads as web. The apex frame is where the owner's original request is most visible.
- Change: Restyle the line as hardware. Use a warm gold-bronze metallic cable with tight specular glints in the sun, dead straight under load, never white, translucent, forked or sticky. End it in a small gold kite-shaped grapnel, not a splat. Add a second short line from the free wrist launcher up to a small gold kite-shaped traveller about 1.5 m above the gripping hand, so the rigging forms a Y bridle (he flies on a bridle like a kite; Spider-Man never has one). Drive it with a stretch-to constraint on an extra object between the existing wrist bone and the line; no rig change is needed.


### 5. [should] c_poses perch_crouch, perch_look_up, apex_classic; f_0090
- Problem: A deep frog squat on a ledge with knees wide and one hand planted low between the feet is the iconic Spider-Man perch. The apex_classic pose (one arm high, one knee tucked, trailing leg) is the iconic web-swing pose. With a full-face mask, these two poses do more to say 'Spider-Man' than any costume detail.
- Change: If pose contents may be edited (the names stay frozen), move both toward an aerialist. Perch: one knee down and the other foot forward, torso upright, the near hand holding the taut gold line at shoulder height instead of touching the ledge. Apex: a long open line with both legs extended and together (a trapeze 'flag' or layout) with the free arm swept back along the body, not a tucked knee. Check that no shoot pose curls the middle two fingers toward the palm.


### 6. [should] Whole suit: gold piping, seen in a_turnaround and e_details
- Problem: Gold is currently only trim on borrowed shapes, so there is no motif a viewer could describe as his. The topographic contour-line texture on the white (b_closeup) would turn into a web pattern if converging gold lines were laid across its concentric loops.
- Change: Make one continuous gold 'flying line' the signature. It runs from the tail of the chest kite straight down across the abdomen to the right hip, around the hip, and straight up the back to the tail of the back kite, where it joins the line coming down from the nape. Use three gold lines at most on the torso, all straight, as if under tension, and never crossing a ring pattern. Replace the concentric contour texture on the white with parallel diagonal sail-panel seams running along the sail's rake. Use no radial-plus-concentric line pattern anywhere.


### 7. [should] f_0276 and all backlit swing shots: body silhouette
- Problem: Even with the bridle, the body silhouette alone is a generic slim masked figure. Nothing in his outline is specific to him.
- Change: Optional and the highest-risk item: add a kite tail. One tapered bone-white ribbon about 1.1 m long with a gold tip and three small bow tabs, anchored at the tail of the back kite and parented to the existing spine bone. Do not use cloth simulation: drive a curve's control points with lagged or damped empties (or bake them from the hero's velocity) so it trails along the motion path. Anchor it at the back, never the neck (a neck scarf is Kamen Rider, Cyborg 009 and Strider). Drop this if it cannot be verified in every shot before the render.


### 8. [nice] a_turnaround, c_poses: body proportions
- Problem: The lean, narrow, long-limbed build is the Spider-Man body type and adds to the gestalt.
- Change: Use the morph targets to move toward a trapeze artist: wider shoulders and lats, a deeper chest, heavier forearms, a slightly shorter neck. Keep the waist slim.


### 9. [nice] e_details hand_L and launcher_R: wrist launchers
- Problem: The launchers are identical left and right and very small. They are already unlike hidden web-shooters, but they contribute nothing to recognition.
- Change: Make the left (white sail arm) launcher the primary: about twice the length along the forearm, with a visible gold reel drum and the kite-shaped grapnel seated in it. Leave the right one slim. Keep both on the outside of the forearm, never under the palm.


**Keep:**
- Cobalt as the dominant colour against the orange city: nothing here is red-and-blue, and there are no web patterns, spider motifs or white teardrop eyes.
- Mirrored gold lens material with a dark rim: gold reflective eyes on blue are far from any Spider-Man eye; only the shape and the fusion at the nose need to change.
- Warm bone white rather than pure white, and the fine blue-on-blue ribbing: both lift it off flat sentai spandex.
- The kite as the emblem idea and the name's evening theme: this is the right source for the motif; it needs to become an actual kite (irregular, tilted, with spars and a line) instead of a rhombus.
- The diagonal boot top: it is the one raked shape already on the suit and the seed of the new language.
- External slim wrist launchers with a gold band: visible hardware, unlike concealed web-shooters.
- Gold kept as thin piping, not large gold areas: this avoids Booster Gold, Doctor Fate and X-Men blue-and-gold blocking.


## THE OWNER'S EYES (first-glance impact for a young superhero-film fan)  (score 3/10)

Through the owner's eyes this is not yet "ok, that is sick": it reads as a blue-and-white morphsuit on a lanky mannequin, closer to a budget blue team-ranger or figure skater than a film hero. The white gloves and toe-socks, the stocking-over-face mask, the tiny lenses, the wristwatch launchers and the flat poster-paint blue are the dorky parts. The blue-against-orange idea, the swept-blade eye concept and the kite emblem are right, but everything is too small, too flat and too polite. The film's one close shot (rear 3/4) currently shows a featureless grey-blue egg above a white bib, and in the perch frame the blue goes muddy navy and the white goes cream.


### 1. [must] a_turnaround (all four views), c_poses: whole body
- Problem: The body is a skinny default mannequin: narrow sloping shoulders, long neck, flat chest, no lats, thin limbs and a head that looks large. With a smooth skin-tight suit this is the 'guy in a zentai suit' read, the opposite of a hero.
- Change: Push the morphs to a gymnast-superhero build: shoulder width +10 to 12%, deeper chest and visible pecs, lats flaring into a waist about 8% narrower, muscle definition near maximum with low body fat, thicker thighs and calves, bigger traps and a neck about 10% shorter, head about 4% smaller so he lands near 8 heads tall. Back this with shading: a subtle darker tone and a satin highlight line along the muscle valleys (pec underside, ab centre line, deltoid cut, spine furrow) so the build still reads at 20 m and in motion blur.


### 2. [must] b_closeup, e_details 'head' and 'helmet_side': mask surface
- Problem: Nose, lips, chin crease and ear bumps show through the mask like a stocking pulled over a face. It is the single dorkiest thing in the close shots and it kills any attitude.
- Change: Turn the mask into a sculpted faceplate: smooth away lips and nostrils (morph or a thin shell 3 to 4 mm proud), flatten the ears completely, keep only strong planes: brow ridge, cheekbone line, a firm jaw line and a clean chin. Add one hard panel seam from each lens tail around the jaw to the chin so the face has a designed 'expression' even with no mouth. Replace the rolled balaclava hem at the neck with a low standing collar in the dark secondary colour, edged with a gold bead.


### 3. [must] b_closeup, e_details 'head', a_turnaround front: lenses
- Problem: The lenses are small, neutral triangles that read as swim goggles or a costume-shop eye mask. They are see-through (eye and eyelid shapes are visible behind the gold glass in b_closeup), outlined in black like a sticker, and from the rear 3/4 only a nub is visible. Mirrored gold against an orange sky also just reflects the sunset and vanishes.
- Change: Make each lens about twice the area and angry: inner corner low at the nose bridge, top edge raked down toward the nose by 15 to 20 degrees (a scowl), outer tip sweeping up and back past the temple to finish above where the ear would be, as a long blade. Keep two separate lenses (no single visor). Make them opaque: a faceted mirror surface (two or three flat facets with a crisp break line) in pale champagne-gold, set in a raised polished gold bezel 3 mm wide instead of the black outline. Add a thin emissive core line in ice cyan (about #9FE8FF) along the lower edge of each lens, strong enough to bloom slightly, so the eyes read when the face is in backlit shadow. No white fill, no thick black rim, no teardrop shape.


### 4. [must] b_closeup_rear and f_0090: back of head, nape, shoulders (the film's one close angle)
- Problem: The shot that fills a third of the frame shows a blank grey-violet bowling ball on a plain white bib. There is no seam, texture, metal or light for the eye to land on. This is where 'so photoreal it looks unreal' has to happen and there is nothing there.
- Change: Design the rear on purpose. (1) A raised crest ridge 5 mm high from the brow over the crown to the nape, capped with a polished gold bead, so the sun draws a hot line over the skull. (2) The lens tails from the change above wrap far enough back to show as two glinting gold blades with a cyan glow from this angle. (3) Panel seams converging on the nape in an arrowhead, with the back of the head and neck in the dark secondary colour and the face and crown in the bright blue. (4) An emissive ice-cyan hairline 2 mm wide running from the nape down the spine into the back emblem. (5) Enlarge the back emblem (see emblem issue) so its top enters this frame.


### 5. [must] e_details (all panels), b_closeup, f_0090: suit material and colour
- Problem: The blue is flat mid-saturation poster paint with no micro-structure, so it looks like plastic or a game asset from 2008. In the film frame, under orange key light, it collapses to muddy navy-violet and the white goes cream. There is no darker secondary tone, so the body is one blob of one colour.
- Change: Three-tone suit. Primary: deeper, richer electric ultramarine (around #1A36D6, more saturated than now) with a strong blue-tinted sheen (#5AA0FF) and a pearlescent coat that shifts toward violet at grazing angles, so backlit edges light up instead of going grey. Secondary: midnight indigo-black (#080B1E) carbon-weave, slightly glossier (roughness about 0.35), on the flanks from armpit to hip as tapering blades, the inner arms, inner thighs, back of the head and neck. This carves a V-torso and makes the blue look brighter by contrast. Texture: procedural bump only (no displacement), a 2 to 2.5 mm hex or diamond knit on the blue, a finer twill on the dark panels, and raised rubberised panel lines 3 mm wide with a coat so they catch highlights. Vary roughness between panels (matte weave about 0.55, satin lines about 0.25).


### 6. [must] a_turnaround, e_details 'hand_L' and feet panel, f_0090: white gauntlets and boots
- Problem: Plain white cloth hands and white feet with visible toe lumps read as mime gloves and tube socks. In the perch frame the feet look like bare socks on steel. This is the main source of the costume-party look.
- Change: Rebuild the extremities as gear, not cloth. Feet: a real boot shell that hides the toes entirely, a 12 to 15 mm dark indigo sole with tread and a thin gold welt line, an ankle seam and a sharp diagonal top that comes to a point at the front of the shin. Shins and forearms: replace the full white sock and glove with pearl-white armour shards (glossy ceramic with clearcoat, about #E9E6DC), a pointed greave on the shin and a pointed bracer on the outer forearm, each edged in raised gold, sitting on dark indigo. Hands: dark indigo gloves with a white back-of-hand plate, gold knuckle bar and textured grip pads on palm and fingertips. White drops from about a quarter of the body to about a tenth, but stays on the outer limbs so the pose still reads at distance.


### 7. [must] e_details 'hand_L' and 'launcher_R', d_swing: wrist launchers
- Problem: The launcher is a small black box on a gold bangle. It looks like a smartwatch or a bracelet, is invisible beyond a few metres, and gives no sense that it fires the line the whole film depends on.
- Change: Make it a forearm weapon: a tapered housing 16 to 18 cm long and about 3 cm proud on the outer forearm, built into the bracer, in black chrome with three polished gold ribs. Give it a twin muzzle that sits over the back of the hand, a visible spool drum with gold filament wound on it, and an ice-cyan emissive charge strip along its length that the line visibly leaves from. Remove the bangle.


### 8. [must] d_swing and f_0276: the line
- Problem: In d_swing the line is a hair that almost disappears; in the apex frame it is a dark string. The signature gadget of the film has no look of its own.
- Change: Make it a 'thread of light': a braided metallic filament with high specular and a gold tint so the low sun runs a hot glint along it, with a minimum on-screen width (clamp so it never falls below about 1.5 pixels, roughly 6 to 8 mm at mid distance). Add a faint ice-cyan emissive pulse that travels from the launcher up the line at the moment of firing, a small gold dart or grapnel head at the tip, and a brief cyan muzzle flash at the wrist. Perfectly smooth and straight under tension: no web texture, no strands, no nodes.


### 9. [should] e_details torso and back panels, a_turnaround front and back: emblem
- Problem: The gold kite is the size of a brooch. It disappears at any film distance and has no presence as a logo someone would put on a wallpaper.
- Change: Front: elongate the kite to about 22 cm tall, pointing down like a dive, bevelled polished gold, split down its centre by a 3 mm ice-cyan emissive seam, with the yoke edges and two gold lines converging into its top point so the whole chest reads as one arrowhead. Back: a larger version, about 30 cm, sitting between the shoulder blades on the spine line, with the cyan spine hairline running through it.


### 10. [should] e_details torso and back, b_closeup: white yoke
- Problem: The yoke is a soft, rounded bib, like a sailor collar or skating costume, and in b_closeup it shows faint wobbly contour lines that look like a rendering glitch rather than a design.
- Change: Sharpen the yoke into a swept, pointed shape: hard straight edges, points reaching out to the deltoid caps, a deeper V down to the emblem, and a matching sharp V on the back. Make it the same pearl ceramic-look material as the limb shards. Replace the wobbly contour lines with deliberate fine chevron ribbing that follows the V (or remove them). End the arm stripe at the elbow with a point instead of running it continuously into the gauntlet, so the arm reads as bicep stripe, gap, bracer.


### 11. [should] e_details all panels, a_turnaround: gold piping
- Problem: The gold piping is a hairline that cannot be seen outside the detail crops, so the suit has nothing that catches the sun in the swings.
- Change: Make the piping a raised bead 6 to 8 mm wide in polished gold (metallic, roughness about 0.18) along the yoke edge, the flank blade edges, the bracer and greave edges and the head crest. Under a low sun these throw hard orange-white glints that streak in motion blur, which is the cheapest 'expensive film suit' effect available.


### 12. [should] f_0276 apex silhouette and all backlit swing shots: accent system
- Problem: Backlit, he is a plain dark stick figure. Nothing identifies him as Vesper once the colours are gone.
- Change: Use one consistent emissive accent, ice cyan, in exactly five places: lens core lines, emblem seam, spine hairline, launcher charge strips, and the line pulse. Keep strengths modest (visible bloom, not white clipping) and turn off multiple importance sampling on these materials so they do not add render noise. Add a strong sheen and coat on the suit so the sun wraps a bright rim around the silhouette edge instead of leaving it flat black.


### 13. [nice] b_closeup and b_closeup_rear: surface realism at 135 mm
- Problem: Every surface is perfectly clean and uniform, which reads as CG rather than as a real object photographed.
- Change: Add light, cheap imperfection through roughness and colour noise only: faint scuffs on the bracers and boot toes, dust in the lower greaves, slight wear on the gold bead high points, micro-scratches and a soft smudge on the lenses, and tiny stitch dots along the main seams.


### 14. [nice] e_details feet panel
- Problem: A stray gold sliver shows under the toes and the sole is paper thin.
- Change: Remove the gold sliver under the toe and fold it into the gold welt line of the new boot sole.


**Keep:**
- Blue as the main colour against the orange sunset: it is the right complementary choice and the figure separates from the city at every distance in c_poses.
- The swept-blade eye idea with gold: correct direction and clearly not any existing hero's eyes; it needs scale, attitude and glow, not replacement.
- The kite/diamond emblem: simple, ownable and original; keep the shape, enlarge it.
- The V of the yoke pointing down to the emblem: a good hero chest structure once it is sharpened.
- Light-coloured accents on the outer forearms and shins: they make the poses readable in fast shots; keep that placement while changing socks and gloves into armour shards.
- The poses themselves (dive, swing_tuck, apex_classic, freefall_spread) have real energy and a strong silhouette in f_0276.
- A skin-tight acrobat suit rather than the rejected helmeted tactical look: the right answer to 'too sober'.
- Gold as the metal: it will catch the low sun far better than silver once it is thick enough to see.


## PHOTOREAL MATERIALS AND TECHNICAL (look-dev supervisor; cites your code)  (score 4/10)

Not ready for the eight-hour render: at film distance the suit reads cleanly and nothing swims, but in the 135 mm shots it looks like a painted mannequin, not a stretch textile. The gold lens surface is lumpy and reads as an eye seen through gold film. A 0.85 cool-white sheen bleaches cobalt to chalk on every sunlit rim and greys the white in shade. The white panels carry pen-line contours like a topographic map, and the nape and hood rim crease and intersect at the film's own angle. These are all cheap fixes in /home/user/sixty/blender/hero/hero_materials.py, mask.py and build_hero.py (I read those files but ran nothing).


### 1. [must] b_closeup.png near lens; also the 'owl rings' in a_turnaround.png front and e_details.png torso
- Problem: The mirrored glass reads as an eyeball and eyelid under gold film: an arc-shaped dome, a recess and smeared concentric reflections. The material is opaque metal (Metallic 1.0), so this is not refraction. mask.lens() places every glass vertex on the hood surface Gs via surface_point(), so the mirror inherits the brow, socket and nose-flank relief and distorts its reflections into an eye shape. It is visible even at 5 m in the turnaround.
- Change: In mask.build() also return a heavily smoothed envelope, e.g. Gref = _blur_wrap(Gc, 20*cpd, 20). In mask.lens() build the frame top and all glass vertices on Gref, not Gs. Raise the whole lens by the largest deficit so glass sits at least 0.3 mm above Gs everywhere. Sink the outermost bevel row 1.5 mm below min(Gs, Gref) as a skirt so no gap opens. Give the glass one clean dome (0.9 mm at the frame rising smoothly to about 2 mm at centre) in place of the current linear ramp. In lens_glass_material() lower Roughness from 0.11 to 0.07, and drop the 900-scale hex micro-mesh or cut its mix from 0.6 to 0.2, since it is sub-pixel and only adds grain.


### 2. [must] b_closeup.png (cream band on the back of the crown and nape of the blue hood), a_turnaround.png side view (lavender-white band down the back of head, torso and leg), b_closeup_rear.png (hood reads slate-purple, not cobalt), e_details.png hand_L (white is cold grey)
- Problem: fabric_material() sets Sheen Weight 0.85 with a cool white Sheen Tint (0.75, 0.75, 0.78) on all fabric. Under grazing or back light the sheen lobe overwhelms the base colour: the cobalt turns chalk white with a hard crusty terminator and reads as a white panel on the head. The same cool sheen makes the white panels look like grey-lavender plastic in shade. The film is mostly backlit, so this is the dominant look of the hero.
- Change: In fabric_material() set Sheen Weight to mix(wf, 0.25, 0.30) (blue, white), Sheen Roughness 0.5, and Sheen Tint to mix(wf, (0.20, 0.38, 1.0), (1.0, 0.92, 0.80)) so the rim on blue stays saturated blue and the rim on white stays warm. Apply the same blue values to the HERO_mask material and the white values to shoe_material_v2 (currently 0.8). To compensate for the lost rim brightness, lift BLUE from (0.012, 0.034, 0.235) toward true cobalt, about (0.012, 0.060, 0.40) linear. Re-render b_closeup and the side turnaround to confirm the rim stays blue.


### 3. [must] b_closeup.png white shoulder yoke (wobbly contour lines with closed loops); e_details.png hand_L, launcher_R and feet (ruled horizontal lines on forearms and shins)
- Problem: The 'streamline thread' reads as pen-drawn topographic contours or wood grain on the shoulder and as ruled notebook paper on the limbs. In fabric_material() the lines are offset contours of white_sd every 4.5 mm, warped by ±3 mm of noise (which creates the islands), painted 75% toward dark grey (0.40, 0.39, 0.36), and allowed up to 65–75 mm from the border. No real garment has this, and the white yoke fills the film's close shot.
- Change: Remove the noise warp (wn) and the 4.5 mm contour stack. Replace it with two topstitch rows parallel to the piping only: row = smooth(0.00035, 0.00012, abs(wsd - 0.0035)) and the same at 0.0060. Colour them only about 10% darker than the white (mix factor 0.5 toward (0.70, 0.65, 0.55)) with +0.05 mm bump. If a full removal is quicker, set the sline colour mix from 0.75 to 0.0 and keep at most 0.03 mm bump.


### 4. [must] b_closeup_rear.png (deep crease across the nape with a dark orange spot inside it, fleshy roll below); b_closeup.png (dimple and pinch at the nape, stair-stepped hood rim against the white collar, lumpy yellow smear under the neck); e_details.png torso, back and helmet_side (ragged hood bottom edge with gold fragments); c_poses.png perch_look_up (hose-like neck)
- Problem: In the perch poses the hood folds sharply where the rigid 'head' rows meet the neck rows, and something pokes through the crease. The hood rim at Z_BOTTOM intersects the body, giving a jagged stair-stepped line. The shader-only gold 'edge' on the rim shows as intermittent smears. This is the film's 135 mm angle.
- Change: 1) In build_gear_v2() widen the nape blend: replace tn = max(0, 1 - row/18) * back * 0.5 with a smoothstep over about 40 rows and a peak of 0.8. 2) Add a Corrective Smooth modifier after the Armature on HERO_mask (factor 0.7, 20 iterations, rest source Original Coords). Limit it to a vertex group covering the neck rows and the back-of-head rows, with zero weight within 15 mm of the lenses so the hood does not slide under the rigid lenses. 3) Lower Z_BOTTOM from 1.500 to about 1.470, pull those extra rows 3 mm inward, and remove the gold 'edge' term from the mask shader. 4) Cover the junction with real geometry on the body: a collar welt ring about 14 mm tall and 2.5 mm thick with a gold tube of radius 1.8 mm on top, weights copied with the existing copy_weights(). Check perch_crouch and perch_look_up from the rear.


### 5. [must] e_details.png torso and hand_L (cold grey-white), d_swing.png and looklab f_0090.png (white panels read mid-grey on the shadow side); a_turnaround.png back shows the warm cream it should be
- Problem: The white is a believable warm bone only in direct sun. In shade, which is what the camera sees in a backlit film, it reads as grey plastic or porcelain. WHITE = (0.66, 0.64, 0.585) is too low and too neutral for white fabric, and roughness 0.50–0.62 gives a smooth plastic highlight.
- Change: Set WHITE to about (0.82, 0.76, 0.64) linear. Raise white roughness to maprange(cell, 0, 1, 0.70, 0.60). Reduce the valley darkening on white from 0.90 to 0.94. Apply the same colour to shoe_material_v2 through its WHITE_COLOR node. Together with the warm sheen tint this keeps the shade side cream.


### 6. [should] b_closeup.png and b_closeup_rear.png, all blue and white fabric
- Problem: No textile structure survives. The front close-up shows a pebbled sandpaper crust on the lit rim; the rear close-up is waxy smooth. The micro-texture is 1 mm Voronoi hex cells plus 0.45 mm noise, and the 135 mm shot resolves only about 0.4 mm per pixel, so it aliases into grain (a shimmer risk in motion) or is erased by the denoiser. There is also no large-scale variation, so each colour is one flat CG value.
- Change: In fabric_material() replace the Voronoi cell with an elongated knit rib in rest space: two sine waves on p_mm with pitch about 2.4 mm along the limb and 1.2 mm across. Use bump about 0.10 mm and colour modulation of 6–8% at most (shade 0.92–1.0 on blue). Add macro breakup: Noise(rest, scale about 10 per metre) driving roughness ±0.06 and value ±4%. Add Geometry > Pointiness mapped to about 6% lighter on convex stretched areas (deltoids, scapulae, knees). Expose one MICRO_GAIN value node on the bump height so wide shots can set it to 0 and avoid shimmer.


### 7. [should] e_details.png back (ribbed horizontal bands around both upper arms), launcher_R and hand_L (rope-like wavy patches on the blue thigh and hip)
- Problem: The joint 'wrinkles' read as ribbed hose and worm-like scratches, not tension folds. They are strictly periodic (16 mm pitch), sharp-profiled (|sin|^2.5), 0.9 mm deep, ring the whole limb, and are present even on straight limbs.
- Change: In fabric_material() change the pitch from 0.016 to about 0.035 m and the profile to a smooth 0.5 - 0.5*cos(ph). Cut the amplitude from 0.0009 to 0.0004. Multiply by a breakup mask, smooth(0.45, 0.60, Noise(rest, scale 9)), so only two or three irregular folds survive per joint. In suit_fields.py restrict the wrk attribute to the flexion side of each joint (elbow crook, back of knee, armpit, groin crease) and set it to zero on the outer upper arm.


### 8. [should] e_details.png torso and back (wobbly, kinked blue/white borders at yoke, elbows and arm stripe; piping thin and intermittent); a_turnaround.png (gold piping does not read at all)
- Problem: The panel borders and piping come from the per-vertex white_sd attribute, interpolated linearly over the coarse base mesh, so the border is a polyline with visible kinks. The piping is bump only (2.2 mm wide, 0.9 mm high): it has no silhouette or real highlight and vanishes beyond a couple of metres.
- Change: Subdivide the body one level (Catmull-Clark, vertex groups preserved) before suit_fields computes its attributes, so white_sd is sampled four times as densely. For the yoke and collar borders, which are in the close shot, extrude a real tube (radius 1.8 mm) along the white_sd = 0 isoline, with the gold material and weights from copy_weights(). Elsewhere widen the shader cord from W = 0.0011 to 0.0020 and its height from 0.0009 to 0.0014.


### 9. [should] b_closeup.png lens rim (stair-stepped black/gold boundary along the upper inner edge; flat inked-outline look)
- Problem: The frame/glass split is a per-face material index taken from a 3.0 mm d_edge threshold on a grid whose rows are fractions of the lens height. On the tapering blade the threshold crosses grid rows and leaves a staircase. The 0.9 mm bevel is sub-pixel and the frame is near-black, so it catches no highlight from the front and reads as a drawn outline.
- Change: In mask.lens() define the outer rows of Ss by distance from the edge in millimetres (0, 0.5, 1.5, 3.0, 3.6, 4.4 mm, clamped near the tip) so an edge loop lies exactly on the frame/glass boundary and on each bevel. Widen the frame to about 3.6 mm with a 1.5 mm outer bevel. In lens_frame_material() change the base from black (0.011) to a dark bronze metal, about (0.10, 0.07, 0.035) with Metallic 1 and Roughness 0.3, so the bevel carries a specular line.


### 10. [should] d_swing.png back emblem, e_details.png torso emblem, a_turnaround.png front emblem
- Problem: The gold kite reads as dull brown card whenever it is in shade or backlit. It is a pure metal with roughness 0.22–0.34, so it only reflects the dark ground and buildings. Its roughness noise also uses Object coordinates on a skinned mesh, so the mottle slides as the chest deforms.
- Change: In gold_material() raise roughness to 0.36–0.46 and add an emission floor (Emission Color GOLD, Strength 0.05, as the lens already does at 0.06) so the shadow side stays gold. Give the kite's centre facets a slightly steeper pyramid (centre offset 0.0013 raised to about 0.0025) so one facet always catches sky. Drive the noise from Generated coordinates or a stored rest attribute, not Object. Add the same emission floor to the piping cord (cmask) in fabric_material().


### 11. [should] b_closeup.png and e_details.png torso (mouth line and pout below the nose); a_turnaround.png side and e_details.png helmet_side (neck as wide as the jaw, bullet-shaped head)
- Problem: Ears and nostrils are correctly gone, but the lips still read as a ridge with a crease under the nose. In the other direction the under-jaw loft is over-filled: with no chin undercut at all, the head and neck become one thick tube and the surface looks like smooth vinyl.
- Change: In mask.build() enlarge the mouth mask from |u| 26–40 to 34–50 and from v -62..-33 to -66..-28, and raise its blur from 9 to about 14 degrees. Restore about half the jaw undercut by blending the neck loft with the ray-cast neck surface (about 0.5 loft, 0.5 body + OFFSET) between the chin and the ring, or halve the m1 tangent scale from 0.5 to 0.25. Keep a soft visible jawline.


### 12. [should] e_details.png feet; c_poses.png dive and dive_reach (soles face the camera)
- Problem: The foot covers read as socks over bare feet. The toe box is a bulbous lump with dark slits where the shell follows individual toes, and the 'sole' is only a shader colour band with no thickness or edge.
- Change: In gear.shoe_shell() apply a morphological close and blur to the ray-cast radii over the front third so the toe box is one smooth cap, as the hood does for the eye sockets. Give the sole real thickness in gear.shoe_mesh(): 6–7 mm with a 1 mm chamfered welt edge and a slight toe spring. Keep the gold edge line on that welt.


### 13. [should] e_details.png hand_L and launcher_R; torso panel (black block hanging off the wrist)
- Problem: The launcher plate reads as a flat black slab hovering beside the wrist, with a lifted edge and daylight under it, tied on by a thin bangle. It is built 1.2 mm above the skin with no side skirt and is rigid on lowerarm02 while the skin under it twists.
- Change: In build_gear_v2() change the plate's base from 0.0012 to about -0.002 and extrude its rim 4 mm inward along the surface normal so it always sinks into the sleeve. Thicken the gold cuff (H 0.0018 to 0.0025, band 0.855–0.895 widened to about 0.84–0.90) so the launcher visibly mounts on it. Check shoot_R and shoot_L for gaps.


### 14. [should] a_turnaround.png back, e_details.png back (deep cleft between the glutes; sharp sternum groove at front)
- Problem: The suit follows the anatomy exactly, so it reads as body paint. Real stretch fabric bridges concavities. This is visible in rear swing shots at 5–10 m.
- Change: At build time, before the fields are computed, bridge the concavities on the rest mesh: push vertices outward along the normal by max(0, blurred envelope - surface) in the gluteal cleft, sternum groove and armpit hollows, by about 60–80% of the depth. A masked Laplacian smooth of 10–15 iterations on those regions does the same job.


### 15. [nice] e_details.png hand_L; b_closeup_rear.png overall
- Problem: The gloves have no construction (no finger seams or knuckle folds), so the hand reads as a mannequin mitt. The rear close-up is waxy, which suggests the denoiser is erasing fine detail at preview sample counts.
- Change: Add shader-only glove detail in the hand zone: a seam groove along each finger side and three shallow knuckle folds, with 0.15 mm bump. For the 135 mm shot only, raise samples and denoise with albedo and normal guide passes so the weave and sheen breakup survive.


**Keep:**
- All body patterns read rest-space vertex attributes (rest, white_sd, wrk), so nothing swims between the sixteen poses. Keep that architecture.
- Ears and nostrils do not read under the hood, and the skull, brow and cheekbone still do. The ear flattening in mask.build() is right.
- From the film's rear and side angle (b_closeup_rear.png) the lens already reads as a manufactured raised part with a hot specular rim. Keep the raised frame, the coat and the small emission floor.
- The white in direct low sun is a convincing warm cream (a_turnaround.png back). That is the target for the shade side too.
- The gold ring at the glove top (e_details.png launcher_R) is clean, even and reads as real piping. Use it as the reference for every other border.
- The back kite's bevelled rim catches light and reads as a solid applied piece.
- Body silhouettes are smooth with no faceting. Shoulders, hips and knees hold up at film distance in every pose that is readable at preview size (flip_tuck is not), and the motion blur in d_swing.png is clean.
- Black soles and launchers give useful dark accents in the dive poses, and the thin line reads correctly.
- Emission sampling is disabled on all hero materials and the shaders use no image textures. Keep it that cheap.
