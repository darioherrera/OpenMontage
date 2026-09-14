---
name: apimart
description: Generate video or images through the APIMart gateway. Use for APIMart-hosted Sora 2, Veo 3.1, Kling v3 / Kling v3 Omni, Seedance 2.0 / 2.5, Gemini Omni 1.1 Flash, FLUX.2, or FLUX Kontext, or when one APIMART_API_KEY should access several model families.
---

# APIMart

Route complete productions through `video_selector` or `image_selector`. Call
`apimart_video` or `apimart_image` directly when the user names APIMart or an
exact APIMart model id. Never substitute a direct vendor endpoint for an APIMart request.

Set `APIMART_API_KEY` (get one at https://apimart.ai/keys).

## Preflight every paid call

1. Read `tool.get_info()["model_catalog"]` — pick an exact model id and an
   operation it lists. Do not invent ids.
2. Pricing is **not** cataloged in the tool (`estimate_cost` returns 0). Check the
   model page on https://apimart.ai before quoting, then announce tool, model,
   request count, and that price before submitting. The finished task reports the
   real USD charge, returned as `ToolResult.cost_usd`.
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

## Image models (`apimart_image`)

| Model | Size control | References |
|---|---|---|
| `flux-2-flex` / `flux-2-pro` / `flux-2-max` | exact `width`+`height` (≤4MP), or `aspect_ratio` + `resolution` 1MP–4MP | ≤8 |
| `flux-kontext-pro` / `flux-kontext-max` | aspect ratio only (width/height snap to nearest ratio), ~1MP | ≤4 |

`steps`/`guidance` are flex-only. Set `generation_mode: "edit"` with
`image_path(s)`/`image_url(s)` for edits. One image per request.

## Failure contract

A missing key, unsupported model/operation, invalid enum, local video/audio,
failed task (message from `data.error.message`), timeout, or download failure
returns a failed `ToolResult` without switching providers.
