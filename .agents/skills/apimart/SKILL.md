---
name: apimart
description: Generate video or images through the APIMart gateway. Use for APIMart-hosted Sora 2, Veo 3.1, Kling v3 / Kling v3 Omni, Seedance 2.0 / 2.5, Gemini Omni 1.1 Flash, FLUX.2, or FLUX Kontext, or when one APIMART_API_KEY should access several model families.
---

# APIMart

Route complete productions through `video_selector` or `image_selector`. Call
`apimart_video` or `apimart_image` directly when the user names APIMart or an
exact APIMart model id. Never substitute a direct vendor endpoint for an APIMart request.

Set `APIMART_API_KEY` (get one at https://apimart.ai/keys). `APIMART_BASE_URL`
optionally overrides the host for proxies.

## Default model per use case

Unless the user names another model:

| Use case | Model |
|---|---|
| UGC and general video | `gemini-omni-1.1-flash-ext` (tool default) |
| Video with voiceover | `grok-imagine-1.5-video-ext` |
| High-quality video | `seedance-2.0` |
| Images | `gpt-image-2-ext` (tool default) or `nano-banana-pro-ext` |

## Preflight every paid call

1. Read `tool.get_info()["model_catalog"]` — pick an exact model id and an
   operation it lists. Do not invent ids.
2. Price it. `estimate_cost` covers Kling v3 / v3 Omni (published rates: std
   $0.0672/s, pro $0.0896/s, pro+audio $0.112/s, 4k $0.429/s) and Veo 3.1
   (estimates: fast 0.15/0.20/0.40, quality 0.40/0.50/0.80, lite 0.05/0.08/0.15
   $/s at 720p/1080p/4k, always 8 s). Other models return 0 — check
   https://apimart.ai before quoting. Announce tool, model, clip count, and
   estimate; sample one clip before batching. The finished task's real USD charge
   is returned as `ToolResult.cost_usd`.
3. Local **images** are uploaded automatically (jpeg/png/webp/gif ≤20MB, hosted 72h).
   Reference **videos/audios** and `video_url` must be public URLs — local files
   fail before any upload or billing.
4. Save outputs inside `projects/<project-id>/` and inspect them. Output links
   expire in ~24h; the tool downloads immediately.

## Video models (`apimart_video`)

| Model | Operations | Duration | Resolution | Notes |
|---|---|---|---|---|
| `sora-2`, `sora-2-pro` | text, image | 4/8/12/16/20 | 720p (pro: 1024p/1080p) | 1 image max; 16:9 / 9:16 |
| `veo3.1-fast` | text, image, reference | 8 | 720p/1080p/4k | first+last frame, or up to 3 reference images |
| `veo3.1-quality` | text, image | 8 | 720p/1080p/4k | first(+last) frame only |
| `veo3.1-lite` | text | 8 | 720p/1080p/4k | no images |
| `kling-v3` | text, image | 3–15 | 720p→std, 1080p→pro, 4k | first(+last) frame; `multi_shot`, `element_list` pass through |
| `kling-v3-omni` | text, image, reference, edit | 3–15 | 720p/1080p/4k | prompt refs `<<<image_1>>>`; 1 video (edit = base, reference = feature) |
| `seedance-2.0` (`-fast`, `-mini`) | text, image, reference | 4–15 | 480p/720p (+1080p/4k on 2.0) | ≤9 images, 3 videos, 3 audios; audio needs image/video |
| `seedance-2.5` | text, image, reference, edit | 4–30 or -1 | 480p/720p/1080p | ≤30 images, 10 videos, 10 audios; audio-only OK; frame/edit jobs force `size=adaptive` |
| `gemini-omni-1.1-flash` | text, image, reference, edit | model decides (3–10s) | 360p/720p/1080p/4k | ≤10 images; 1 video ≤10s for edit/extend |
| `gemini-omni-1.1-flash-ext` (default) | text, image, reference | 4/6/8/10 | 360p/720p/1080p/4k | 1 first frame, or 1 or 3 reference images; 1 motion `reference_videos` (drops duration); no last frame |
| `grok-imagine-1.5-video-ext` | text, image, reference | 6–15 | 480p/720p | ≤7 images; 16:9, 9:16, 1:1, 3:2, 2:3 |

Canonical fields: `image_url`/`image_path` (first frame), `last_image_url`/`last_image_path`,
`reference_images`, `reference_videos`, `reference_audios`, `video_url` (edit source),
`generate_audio`, `aspect_ratio`, `resolution`, `duration`. Model-specific fields
(`negative_prompt`, `multi_prompt`, `seed`, `extend_from_task_id`, …) pass through
when the model supports them; anything else goes in `extra_params`.

```python
tool.execute({
    "prompt": "The character in @图片1 walks toward the camera, @音频1 as BGM",
    "model": "seedance-2.5",
    "operation": "reference_to_video",
    "duration": 10,
    "resolution": "1080p",
    "reference_images": ["projects/demo/character.png"],
    "reference_audios": ["https://cdn.example.com/beat.mp3"],
    "output_path": "projects/demo/seedance.mp4",
})
```

Invalid duration, resolution, ratio, operation, or media counts fail before
billing with the supported choices in the error — never clamp silently.

## Prompting Kling v3

Write in English. Describe **subject + action + environment + camera + light +
style** in that order; Kling follows camera vocabulary literally.

> A yellow Ford Mustang GT with black racing stripes drives fast along an empty
> desert highway at golden hour. Low tracking shot from beside the rear wheel,
> heat haze, long shadows, warm orange sky. Cinematic 35mm, shallow background
> focus, smooth steady motion. No people, no text, no logos.

- Put exclusions in `negative_prompt` ("blurry, low quality, distorted text,
  extra wheels, watermark") instead of "no X" prose.
- `mode` (`std`/`pro`/`4k`) may be passed instead of `resolution`.
- One continuous shot per request unless you use multi-shot; say "single
  continuous shot" when the beat must not cut.
- `generate_audio` (alias `audio`) synthesizes ambience/music inside the clip.
  Leave it off when narration and music are mixed later; it raises the pro rate.
- Image-to-video: `image_path` is the first frame, `last_image_path` the last.
  The image ratio may override `aspect_ratio`.
- On-screen text is unreliable; render text in the composition, not the clip.
- Multi-shot: pass `multi_shot: true`, `shot_type: "customize"`, and
  `multi_prompt: [{"index": 1, "prompt": ..., "duration": n}, ...]` (1–6 shots,
  ≤512 chars each, index from 1). Shot durations must sum exactly to `duration`.

## Prompting Kling v3 Omni

Pass `reference_images` (local files are uploaded in order, URLs expire after
72 h) and bind them in the prompt with 1-based tags:

> The yellow Mustang in <<<image_1>>> drives along a Mediterranean seafront
> promenade with palm trees, golden light, tracking shot from the side.

- Without a tag, APIMart prepends `<<<image_1>>>` automatically.
- A tag beyond the supplied image count is rejected before submission.
- With a first frame (`image_path`) the tool sends `image_with_roles`
  (first/last frame + references) instead of `image_urls`.
- Reference images with baked-in text or logos leak into the output; use clean stills.

## Prompting Veo 3.1

Duration is always 8 s. `operation: "reference_to_video"` with up to 3
`reference_images` sends `generation_type: "reference"` (fast only); a first
frame (+ last frame) sends `generation_type: "frame"`. `veo3.1-lite` is text-only.

## Image models (`apimart_image`)

| Model | Size control | References |
|---|---|---|
| `flux-2-flex` / `flux-2-pro` / `flux-2-max` | exact `width`+`height` (≤4MP), or `aspect_ratio` + `resolution` 1MP–4MP | ≤8 |
| `flux-kontext-pro` / `flux-kontext-max` | aspect ratio only (width/height snap to nearest ratio), ~1MP | ≤4 |
| `gpt-image-2-ext` (default) | 15 ratios (incl. 2:1, 3:1, 1:3) + `resolution` 1k/2k/4k | ≤15 |
| `nano-banana-pro-ext` | 10 ratios + `resolution` 1K/2K/4K | ≤14 |

For GPT Image 2 and Nano Banana Pro, width/height snap to the nearest ratio;
pass `resolution` explicitly for 2K/4K (default is the 1K tier).

`steps`/`guidance` are flex-only. Set `generation_mode: "edit"` with
`image_path(s)`/`image_url(s)` for edits. One image per request.

## Failure contract

A missing key, unsupported model/operation, invalid enum, local video/audio,
failed task (message from `data.error.message`), timeout, or download failure
returns a failed `ToolResult` without switching providers.
