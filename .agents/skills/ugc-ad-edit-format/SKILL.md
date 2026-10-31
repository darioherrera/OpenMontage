---
name: ugc-ad-edit-format
description: House edit format for vertical UGC / AI-avatar ads (Meta Reels, TikTok) in HyperFrames, proven on the Optimy "Ni de coña" ad. Use when assembling or re-cutting any avatar/talking-head ad from generated clips — fake multi-cam punch-ins, jump cuts on pauses, zoom-blur handoffs, two-tier kinetic captions, full-frame cutaways, animated B-roll with circular PiP, SFX, end card, and the mandatory loudnorm post-step. Includes a working template composition.
---

# UGC ad edit format (HyperFrames)

Reference build: `template/index.html` (Optimy v7, 29.4 s, 1080x1920, approved by the user 2026-09-15),
`template/captions.json`, `template/BRIEF.example.md`, `template/broll.html` (6 s animated B-roll with PiP).
**Copy the template and swap clips, timings, copy and brand tokens — don't rebuild from scratch.**
Generate clips first with `ugc-avatar-realism` (image approved → video with the Avatar Hype prompt structure).

## 1. Structure (≈25–35 s)

| Block | Length | Content |
|---|---|---|
| Hook | 0–7 s | Avatar clip. Pattern interrupt on frame 1 (open CLOSE), punchline slam with B&W grade + shake |
| Pain | ~6 s | Avatar, phrases jump-cut back to back, 1 full-frame cutaway (e.g. empty ad slot) |
| B-roll | 6 s | Animated explainer (HyperFrames) with the avatar's VO and a circular PiP of her face |
| Solution + CTA | ~8 s | Avatar, full-frame grid cutaway of creatives, CTA phrases, points at camera at the end |
| End card | 2 s | Navy, logo, wordmark, rule, one-line promise, URL |

Ratio of avatar talking vs. graphics ≈ 60/40. Remove every pause >0.3 s; nothing holds longer than ~2.5 s without a framing change.

## 2. Cutting the avatar clips

1. `silencedetect=n=-35dB:d=0.2` → speech segments. Whisper `whisper-1` word timestamps for text; **re-align onsets to the RMS envelope** (Whisper drifts up to 1.5 s).
2. One `<video>` + one `<audio>` per kept phrase (same `data-media-start`), back to back. Pads: ~0.04 s before onset, 0.08–0.10 s after tail. Merge pieces shorter than ~0.5 s with a neighbour.
3. Verify no clipped words: RMS of the last 40 ms of each piece ≤ −35 dB, and no silence >0.35 s inside a scene.
4. Check for repeated phrases in the transcript (models sometimes say a line twice) — cut the duplicate.

## 3. Fake multi-cam (the thing that makes it not boring)

- Each clip sits in an **untimed wrapper** (`#cam1`, `#cam2`…); animate the wrapper, never the timed `<video>`. `transform-origin` on the face (measure from a still, ≈50% 36–38%).
- Shot list `[start, end, scale, driftX]`: alternate **WIDE 1.0 / MEDIUM 1.1 / CLOSE 1.22–1.27** on phrase/keyword boundaries (hard `tl.set` = a cut). Cap ≈1.3 (720p sources).
- Inside every shot: slow push `scale × 1.04`, `ease: none`; drift ±10–14 px only when scale ≥ 1.1.
- Every jump cut between pieces must also change framing.
- Framing that keeps hands in: pointing / shrugging moments at 1.0–1.1, no drift. Fingers near the source edge can't be saved above 1.0.
- Segment handoffs (avatar ↔ B-roll ↔ avatar): zoom-through, `TX = 0.14 s` each side — outgoing `scale × 1.35` + `blur(10px)` power3.in, incoming from `× 1.3` + blur, power3.out.
- Punchline slam: B&W via `data-color-grading` intensity set at the slam, 5-frame decaying shake on the wrapper, CLOSE 1.27.
- **A CLOSE does not hide a bad gesture under the chin — it enlarges it.** Cover it with a full-frame cutaway instead.

## 4. Captions — two-tier kinetic

- Container `top: 1120px; height: 520px` (lower-middle third, above the ~260 px Reels UI).
- **Lead words**: Inter 600, 52 px, uppercase, paper `#f7f9fc` on navy pill `rgba(10,30,48,.9)`, radius 12, word-synced pop (`y 26 → 0`, scale .9→1, 0.18 s).
- **Keyword** (one per phrase): Inter 700, 140 px (fit 80–140 with `__hyperframes.fitTextFontSize`, maxWidth 820), brand blue on paper pill, radius 26, shadow. Entrance rotates between blur-scale-in, rise, slide-from-left.
- **Slam** keyword (hook punchline): 168 px, from `scale 2.3, rotate −9°, blur 18px` → rotate −3°, 0.34 s power4.out.
- Group = `lead` (+ `key`) (+ `tail`); fade out 0.12 s at group end, **never overlap the next group**. Numbers as digits ("6 ANUNCIOS", "3.000 €"), brand names spelled right (fix Whisper).
- No captions over the B-roll (it has its own headlines).

## 5. Cutaways & inserts

- **Full-frame navy cutaway** (voice continues): e.g. dashed empty ad slot with "+" (pain), 3×2 grid of real creatives 300×400 tiles popping on the spoken number (solution). Snap in 0.2 s, slow creep ×1.04. Tiles above captions, never over the face.
- Use cutaways to hide generation defects (odd hand signs, glitches).

## 6. B-roll explainer (template/broll.html)

- 6 s max, navy bg + subtle grid, big Inter headline with one word in accent, 2 beats synced to VO, final hold (no exit mid-motion).
- Circular PiP bottom-right: 320 px circle, 5 px blue border + glow ring; video inside sized so the **face is centred** (e.g. 560×996 at left −112 / top −220 for a face at 48.6%/36.7%). PiP video cut exactly like its audio (lip sync).
- Render it separately, drop into the main edit slot, no push/crop on it.

## 7. Audio

- Voice only + light SFX (bundled media-use library, Pixabay licence): short whoosh 0.2 s before each segment handoff (vol 0.25), bass impact on the slam (0.1), pops on grid tiles (0.35, 3 max).
- Per-clip gain chain (`gain` nodes + `limiter −1 dB`) to roughly even the clips.
- **Mandatory post-step:** HyperFrames' `amix` divides by the active inputs, so mixer gain can't reach −14 LUFS. After rendering, two-pass ffmpeg loudnorm: pass 1 `loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json`, pass 2 with measured values + `linear=true`, `-c:v copy -c:a aac -b:a 192k -ar 48000`. Target −14 ±0.5 LUFS, peak ≤ −1 dBFS.

## 8. End card

Navy `#0A1E30`, radial blue glow, logo 200 px pop, wordmark 128 px, blue rule, one-line promise 60 px (balanced wrap, max 820 px), URL 40 px muted; staggered 0–0.55 s. Promise copy is per client (Optimy: "Creatividades para tu marca todos los meses").

## 9. Brand tokens (swap per client)

`--navy #0a1e30`, `--blue #1d4ed8`, `--paper #f7f9fc`, accent for negative words (B-roll) `#E5533D`, Inter 400/600/700 local woff2. Optimy rules: no superlatives, no ROAS promises, AI said openly, Spanish from Spain.

## 10. Workflow & gotchas

1. Brief → first frames (approve) → clips (review transcript, repetition, pitch vs. other clips, gestures) → edit.
2. Backups in `versions/index.vN.html` (a second root HTML breaks `check`).
3. `npx hyperframes check` after every change.
4. **Never `hyperframes snapshot`** — it sends frames to Gemini (paid) using the repo `.env` key. Render and pull frames with `ffmpeg -ss T -frames:v 1`.
5. Render with `--experimental-fast-capture=false` (fast capture drops transform tweens); drafts at default quality, final `-q high`; then loudnorm.
6. Show the user a draft MP4 (pacing can't be judged from stills) before the final render.
