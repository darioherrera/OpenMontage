---
workflow: general-video
flow: companion
storyboard: no
message: "Optimy te deja 6 anuncios nuevos al mes con IA para que no te quedes sin repuesto"
destination: meta-reels
aspect: 1080x1920
language: es-ES
length: ~29s
---

# Optimy — "Cuelgo" (main edit)

Vertical Meta Reels ad for the Spanish agency Optimy, cut from three AI avatar clips plus a B-roll slot.

## Structure (global timeline v7, hard cuts, 29.30 s)

| t (s)       | Segment                   | Notes |
| ----------- | ------------------------- | ----- |
| 0.00–7.00   | clip1_hook                | "¿Tres mil euros y dos semanas de rodaje? ¿Por un anuncio? … Ni de coña." Black-and-white from "Ni de coña" (5.66) and "NI DE COÑA" slams in. |
| 7.00–13.30  | clip2_dolor_v3            | "Tu anuncio ganador se quema en semanas. Sube la frecuencia. Baja el CTR. Y no tienes nada para sustituirlo." 4 jump-cut pieces (media 0.28–2.44 → 7.00, 3.20–4.34 → 9.16, 5.00–6.10 → 10.30, 6.70–8.60 → 11.40). Framing: wide / close SE QUEMA 8.02 / medium FRECUENCIA 9.16 / close CTR 10.30 / `#adslot` insert 11.40–12.40 / x1.1 SUSTITUIRLO 12.40. |
| 13.30–19.30 | B-roll Andrómeda (6 s)    | `assets/broll/broll-andromeda.mp4` (own narration + on-screen text, PiP face centred); no captions here. |
| 19.30–27.30 | clip3_mecanismo_cta_v2    | "En Optimy te hacemos seis anuncios nuevos al mes, con IA. Primero apruebas uno. Déjame tu marca y te envío seis ángulos nuevos que podríamos trabajar." 3 jump-cut pieces (media 0.30–3.46 → 19.30, 4.02–5.26 → 22.46, 6.02–9.62 → 23.70). Framing: wide / full-frame 6-creative grid cutaway 19.96–21.62 (hides the raised open hand during "hacemos seis") / close CON IA / medium PRIMERO APRUEBAS UNO 22.46 / wide DÉJAME TU MARCA 23.70 / close 6 ÁNGULOS NUEVOS 24.64 / medium on the pointing "QUE PODRÍAMOS TRABAJAR" 26.14. |
| 27.30–29.30 | End card                  | Navy #0A1E30, inverted Optimy mark + "Optimy" wordmark, "Creatividades para tu marca todos los meses", "optimy.es". |

## Captions

Word-synced two-tier kinetic captions (Whisper word text, onsets re-aligned to the RMS envelope), lower-middle third above the ~260 px Reels safe zone: small white Inter 600 uppercase lead-ins + one big Inter 700 keyword per phrase in action blue #1D4ED8 on a white pill. Keywords: 3.000 €, RODAJE, NI DE COÑA, SE QUEMA, FRECUENCIA, CTR, SUSTITUIRLO, 6 ANUNCIOS, CON IA, APRUEBAS UNO, TU MARCA, 6 ÁNGULOS, TRABAJAR.

## Audio

Voice + light SFX (whooshes at 6.80 / 13.10 / 19.10, impact 5.64, pops 19.98–20.26 on the grid). Muted `<video>` + separate `<audio id>` per piece; gain chain + -1 dB limiter, then a two-pass ffmpeg loudnorm on the render (I=-14, TP=-1.5) → `renders/draft-v7-loudnorm.mp4`.

## Brand rules

No superlatives, no ROAS promises, no fake scarcity. Spanish from Spain.

## Status

Draft `renders/draft-v7-loudnorm.mp4` (scene 3 swapped to clip3_mecanismo_cta_v2) awaiting approval.
