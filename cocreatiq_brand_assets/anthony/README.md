# Anthony's Brand Asset Library (Face 0)

This folder is the bridge between your Figma/AE designs and the video rendering pipeline.
Drop files here with the exact names below. Remotion + the video operator read from `manifest.json`.

---

## Priority 1: Drop Now (Blocks First Render)

### `fonts/`
- `Montage-Black.ttf` (or .otf) — hero punch text ("20 YEARS" style)
- `Montage-Bold.ttf` — titles, subjects
- `Montage-Regular.ttf` — body text
- `LemonTuesday.ttf` — script accents

### `accents/` (PNG with alpha channel)
- `yellow_brush_long.png` — 2000×400 min
- `yellow_brush_short.png` — 1200×300 min

### `textures/` (PNG)
- `notebook_lined.png` — 2727×4096 (lined paper)
- `crumpled_paper.png` — 2655×3722 (crumpled texture)
- `grid_black.png` — 2160×3840 (black grid overlay)

### `motion_bg/` (PNG or MOV if looping)
- `golden_light_leak.png` — 2000×1333 min
- `amber_cinematic_glow.png` — 3000×2000 min

### `face_references/` (for AI gen via Freepik/ComfyUI)
- `anthony_main.jpg` — primary face reference (high res, front-facing)
- `anthony_side.jpg` — side angle
- `anthony_smiling.jpg` — smiling expression
- `anthony_neutral.jpg` — neutral expression
- `anthony_full_body.jpg` — full body shot
- Drop 5-10 photos total, variety of angles + lighting

---

## Priority 2: When Ready (AE Exports)

### `logo/`
- `logo_light.svg` — vector, for dark backgrounds
- `logo_dark.svg` — vector, for light backgrounds
- `logo_white.png` — 2000px, transparent bg

### `intros/` (MOV with alpha — ProRes 4444)
- `cocreatiq_logo_reveal.mov` — 1.5 seconds

### `outros/` (MOV with alpha — ProRes 4444)
- `cta_dm_operator.mov` — 3 seconds
- `cta_create_keyword.mov` — 3 seconds
- `cta_link_in_bio.mov` — 3 seconds
- `cta_follow_for_more.mov` — 3 seconds

### `transitions/` (MOV with alpha)
- `signature_wipe.mov` — 0.5-1s
- `glitch_cut.mov` — 0.3-0.5s
- `flash_white.mov` — 0.3s

### `overlays/` (MOV with alpha — caption style templates)
- `caption_highlight.mov` — word-by-word highlight (Contrarian, Proof)
- `caption_phrase.mov` — phrase-by-phrase (Education)
- `caption_sentence.mov` — full sentence (BTS)
- `caption_typewriter.mov` — typewriter reveal (Origin, Adversity)

### `color_grades/`
- `cocreatiq_main.cube` — LUT from Premiere

### `music/` (MP3, 128kbps+)
- `upbeat_business.mp3` — hype/high-energy
- `chill_creative.mp3` — thoughtful/BTS
- `cinematic_dramatic.mp3` — serious/Origin

### `sfx/` (WAV)
- `whoosh.wav`
- `ding.wav`
- `glitch.wav`
- `click.wav`

---

## Export Settings (From Figma)

- PNG format, **3x scale** for crispness
- **Transparent background ON** for all accents/overlays/logos
- Filename must match exactly what's listed above

## Export Settings (From AE)

- Codec: **Apple ProRes 4444** (preserves alpha channel)
- Resolution: 1920×1080 minimum
- Frame rate: 30fps
- Duration: exact as specified above

---

## After Drops: What Happens

1. You confirm files are in
2. I generate `manifest.json` mapping role → filename
3. I generate `colors.json` with your hex palette
4. Remotion components reference by ROLE, not filename
5. First render becomes possible

---

## Missing an Asset?

That's fine — drop what you have. The manifest tracks what's ready vs what's pending.
The video operator will use fallbacks or mark scripts as "pending asset" until ready.
