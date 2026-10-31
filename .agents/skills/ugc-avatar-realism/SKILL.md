---
name: ugc-avatar-realism
description: Prompt-building rules for realistic AI UGC avatar ads — identity-locked image edits (outfit, background, angle, product in hand, character sheet) and image-to-video prompts (camera move, micro-gesture, script, voice line, Spanish accent line, no-cut guard). Use before any apimart_image / apimart_video call (or other image-to-video model) that animates a person talking to camera, a podcast/dualcast, a product demo, skincare/fashion action, or silent B-roll for voice-over.
---

# UGC avatar realism

Distilled techniques (own wording) from studying the Avatar Hype Academy "Biblioteca de prompts"
(UGC realista course). Not a copy of that library — templates below are rewritten.
Pipeline: **A. still image** (approve first — see memory rule) → **B. image-to-video** → **C. format/edit**.

**Original prompts:** if `references/avatarhype-biblioteca.md` exists next to this file, it holds the course's
exact prompts, pasted in by the user (a licensed course resource, gitignored and never published). Read it first and
prefer its wording; use the rules below to assemble and check the prompts.

**Default for every UGC video (user decision 2026-09-14):** build each clip prompt with the reference file's
structure. Order: camera line → gesture + `says: "<script>"` → `Voice:` preset → accent line. Use its camera, gesture,
voice and accent presets verbatim, and fill in only the brackets. Start from its "UGC completo" format. Pick one voice
preset per avatar and freeze it for the whole campaign.

## A. Image edits — keep the person, change one thing

Every edit prompt has three parts:
1. **Identity lock** — "Use the reference image. Keep the same person: face, hair, skin tone, body, age, pose, framing and lighting unchanged."
2. **One change only** — "Change ONLY <outfit | background | camera angle | expression>." Name what must stay.
3. **Realism tail** — "Photorealistic, natural skin texture with visible pores, no beauty filter, no skin smoothing. No text, no watermark. Single image."

Rules:
- **Two references → say who is who.** "Image 1 is the person; image 2 is only the <outfit | background | product>. Do not take the face or body from image 2." Without this the model blends identities.
- **Backgrounds:** describe place + light ("small home office, window light from the left") and ask for natural integration; the person's lighting must match the new scene.
- **Angles:** request one named angle per generation — front to camera, 3/4, profile, high angle, low angle, full body, top-down, worm's-eye, backlit silhouette, dutch angle, lying down, wide environmental. Keep outfit/hair explicitly identical.
- **Character sheet (for consistency across many clips):** ask for a 3×3 grid of the same person — front, both profiles, both 3/4, gaze up/down, neutral and serious — on a flat light-grey background, same lens/distance/light in every cell, "identity reference sheet, no stylization". Use it as the reference for later edits.
- **Product in hand:** person ref + product ref; "the label and packaging stay unchanged and readable"; demand realistic hands ("two natural hands, correct number of fingers").
- **Apps / digital product:** put the screen content on a phone/laptop the person holds; keep UI legible; don't let the model invent UI text — composite real screenshots in the edit when exact UI matters.

## B. Image-to-video prompt — assemble in this order

| # | Piece | Notes |
|---|-------|-------|
| 1 | **Camera** | One move or explicitly static. |
| 2 | **Action** (optional) | A gesture, not dialogue. |
| 3 | **Script** | `says: "<exact line in Spanish>"` |
| 4 | **Voice** | Same `Voice:` line for every clip of that character. |
| 5 | **Accent** | Required when not English. |

### 1. Camera
- Default that works best for talking heads: **static camera + realistic arm movements and subtle micro-movements**.
- Other single moves: locked-off tripod, slow push-in to the face (start on frame 1, then hold), fast punch-in on the first word, slow lateral travel, gentle orbit, light handheld, slow motion.
- **Always append the no-cut guard**, or the model inserts a scene cut mid-sentence:
  `Single continuous take, no cuts or scene changes; after the move the camera holds on the framing.`
- One move per clip. Build shot variety in the edit (punch-ins/jump cuts in HyperFrames), not by stacking moves in one prompt.

### 2. Micro-action placement (gives realism)
- Gesture **before** speaking → put it before `says:` — `The person <gesture>, then looks at the camera and says: "<line>"`
- Gesture **while/after** speaking → put it after the quote — `The person says: "<line>" <gesture>`
- Write gestures in English, concrete and small: adjusts cap, sips coffee and sets the cup down, tucks hair behind ear, raises an eyebrow, shrugs, counts on fingers, leans toward camera, holds the product up next to the face.

### 3. Script
- Exact words in quotes; Spanish from Spain for Optimy. Keep each clip to what fits the model's duration (≈2.5 words/s). Tone cue before the quote: "direct, clear influencer energy" / "casual, like talking to a friend".

### 4. Voice line (character consistency)
Pattern: `Voice: <timbre adjectives> <gender> voice — <age range>, <pitch>, <texture>, <pace>, <attitude>.`
Example (own): `Voice: a clear, warm female voice — a woman in her late 20s, medium pitch, relaxed conversational pace, confident and friendly.`
Reuse it verbatim in every clip of the same avatar, same session.

### 5. Accent line (append at the end)
- Spain: `Spanish with a neutral Peninsular Spanish (Madrid) accent, informal and conversational.`
- Also possible: Rioplatense (Buenos Aires, "sh" for ll/y), Bogotá neutral, Mexico City, neutral Latin American.

### Special actions (no dialogue)
- Mark with `no talking, mouth closed`.
- **Skincare/hair product:** "the visible product decreases continuously through the clip until fully absorbed, no residue or streaks" — otherwise cream stays on the skin.
- **Fashion:** full-body, keep same person + same location; one movement (turn, walk toward camera, adjust garment).
- Always restate "same person, same location and lighting as the reference" for action clips.

## C. Formats

- **UGC, 1 person to camera:** static camera + arm movements + tone + script, then voice + accent (+ optional micro-action). Product in hand: generate the still with the product first (A), then "holds/points at the product, label stays visible and unchanged".
- **Podcast (2 people):** generate each speaker separately — static camera, "single speaker: only the person in the reference talks", eyes to the side ("looking toward the left/right of frame as if talking to someone next to them"), their own voice line. Cut between them in the edit. For the second guest, generate a new person on the opposite side of the same set using guest 1's image as a *setting-only* reference (mirroring the image makes the background look copied).
- **Dualcast (2 people in one shot):** one image with both; in the video prompt state who speaks and that the other listens silently with small reactions.
- **Voice-over B-roll:** avatar never talks — every clip `no talking, mouth closed`; still template: same person + `<action>` + `<place + light>` + `<shot size>` + realism tail. Add narration in the edit (voice + accent rules from B still apply to the TTS/VO clip).
- **Trends:** short native clips without talking to camera (no templates yet).

## Checklist before a paid call
- [ ] Still image approved by the user (never animate an unapproved frame).
- [ ] Identity lock + "change ONLY" (image) / camera → action → script → voice → accent (video).
- [ ] No-cut guard present.
- [ ] Same `Voice:` line as the other clips of this character.
- [ ] Realism tail: pores/no smoothing (image); natural gestures, correct fingers, label unchanged (product).
- [ ] Duration vs. script length checked.
