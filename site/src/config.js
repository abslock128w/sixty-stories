// Every tunable in one place. Effect strengths are deliberately low: if an effect reads as an
// effect, it is too strong. "v" below means scrub speed in frames per second.
export const CONFIG = {
  scroll: {
    framesPerVh: 20,      // film frames advanced per viewport-height of scroll
    introHoldVh: 1.0,     // scroll spent on the opening title over frame 0
    cutHoldVh: 0.32,      // hold on the first frame after each cut (title moment)
    creditsVh: 3.0,       // scroll spent on the end plate + credits roll
    smoothing: 6.5,       // 1/s exponential follow of the playhead toward scroll (inertia)
    smoothingReduced: 30, // with prefers-reduced-motion
  },
  frames: {
    slots: 22,            // GPU texture pairs (colour + depth) kept around the playhead
    aheadShare: 0.68,     // share of the window spent ahead in the scrub direction
    maxDecodes: 3,        // concurrent createImageBitmap decodes
    uploadsPerFrame: 1,   // texture pair uploads per animation frame
    uploadBudgetMs: 9,    // ...or stop once this many ms were spent uploading
    packConcurrency: 2,   // packs fetched at once during the overture
  },
  view: {
    maxDpr: 2,
    // picture window aspect = clamp(viewportAspect * landscapeFactor, portraitAspect, film aspect)
    landscapeFactor: 1.6,
    portraitAspect: 0.75, // tall screens: cover-fit into a 3:4 window and pan with tilt/drag
  },
  look: {
    parallax: 0.011,      // uv shift per unit depth difference at full pointer deflection
    parallaxFocus: 0.24,  // depth value (0 sky .. 1 lens) that stays put
    pointerEase: 3.2,     // 1/s smoothing of the pointer
    overscan: 1.028,      // zoom so parallax / weave never reveal an edge
    grain: 0.034,         // grain amplitude (mid-tones; shadows/highlights get less)
    grainFps: 24,
    halation: 0.20,
    halationThreshold: 0.74,
    streak: 0.085,        // anamorphic horizontal streak on the hottest pixels
    vignette: 0.20,
    weavePx: 0.35,        // gate weave amplitude in image pixels
    vFloor: 30,           // below this scrub speed, velocity effects are exactly zero
    vMax: 260,            // speed at which velocity effects saturate
    smear: 0.03,          // vertical "film slipping in the gate" smear length (uv) at vMax
    breathing: 0.012,     // lens breathing zoom at vMax
    rgbSplit: 0.0015,     // radial channel separation at vMax
    cutFlash: 0.28,       // exposure flash on a cut
    dust: 110,            // number of motes
    dustStrength: 0.42,
  },
  curtain: { mattesMs: 2400, exposureMs: 3800, titleDelayMs: 1200 },
  ui: { idleMs: 2800 },
  audio: { master: 0.72 },
};

export const SHOT_COPY = {
  s1: { line: 'A city poured in amber, one minute before the lights come on.', side: 'left' },
  s2: { line: 'Two hundred and twenty-eight metres up, on a stone eagle, Vesper waits.', side: 'right' },
  s3: { line: 'Then he lets go.', side: 'left' },
  s4: { line: 'One line, fired across the avenue, snaps taut above the traffic.', side: 'right' },
  s5: { line: 'Release. Tuck. Through a gap barely wider than a bus.', side: 'left' },
  s6: { line: 'For one frame, nothing pulls in any direction.', side: 'right' },
};

export const REDUCED = (() => {
  try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return false; }
})();
