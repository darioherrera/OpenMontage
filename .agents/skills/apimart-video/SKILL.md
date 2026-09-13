---
name: apimart-video
description: |
  Generate video through the APIMart unified gateway (`apimart_video` tool, `APIMART_API_KEY`): Kling v3 (cinematic 3-15 s clips at 720p/1080p/4K, multi-shot, elements), Kling v3 Omni (reference images bound with <<<image_N>>> tags, first/last frame roles) and Veo 3.1 fast/quality/lite (fixed 8 s). Use when the user wants one gateway key for several video models, 1080p output on a budget, or Kling-style prompt control. Not for in-place clip editing (use gemini-omni).
allowed-tools: Bash, Read, Write
metadata:
  openclaw:
    requires:
      env_any:
        - APIMART_API_KEY
---

# APIMart video gateway (Kling v3 / Kling v3 Omni / Veo 3.1)

APIMart resells third-party video models behind one OpenAI-style endpoint.
OpenMontage wraps it as `apimart_video` (`provider="apimart"`). The tool
submits `POST /v1/videos/generations`, polls `GET /v1/tasks/{task_id}` and
downloads the finished MP4 to `output_path`. Route generation through
`video_selector` with `preferred_provider="apimart"` or call the tool directly.

## Choose a model

| Model | Duration | Resolution (`mode` / `resolution`) | Price (USD/s, APIMart rate card) | Pick it for |
|---|---|---|---|---|
| `kling-v3` (default) | 3-15 s | `std` 720p · `pro` 1080p · `4k` | 0.0672 · 0.0896 (0.112 with audio) · 0.429 | Cinematic single shots, first/last-frame control, multi-shot sequences |
| `kling-v3-omni` | 3-15 s | same as above | same as above | Reference-image consistency (`<<<image_1>>>`), role-based first/last frames, `@element` subjects |
| `veo3.1-fast` | 8 s fixed | `720p` · `1080p` · `4k` | estimated 0.15 · 0.20 · 0.40 | Google look, quick iterations, up to 3 reference images |
| `veo3.1-quality` | 8 s fixed | same | estimated 0.40+ | Hero shots when Veo quality is required (no reference mode) |
| `veo3.1-lite` | 8 s fixed | same | estimated 0.05 | Cheap batch drafts, text-only (no image inputs) |

Veo prices are conservative estimates; the task endpoint returns the real
charge in `data.cost` and the tool reports it as `cost_usd` with
`cost_source="provider"`. Announce model, mode, clip count and estimate before
the first paid call; sample one clip before batching.

## Prompting Kling v3

Write in English. Describe **subject + action + environment + camera + light +
style** in that order; Kling follows camera vocabulary literally.

> A yellow Ford Mustang GT with black racing stripes drives fast along an empty
> desert highway at golden hour. Low tracking shot from beside the rear wheel,
> heat haze, long shadows, warm orange sky. Cinematic 35mm, shallow background
> focus, smooth steady motion. No people, no text, no logos.

- Put exclusions in `negative_prompt` ("blurry, low quality, distorted text,
  extra wheels, watermark") instead of "no X" prose; Kling supports it natively.
- Keep one continuous shot per request unless you use `multi_shot`. Say
  "single continuous shot" when the beat must not cut.
- `audio: true` synthesizes ambience/music inside the clip (Kling only). Leave it
  off when narration and music are mixed later; it raises the 1080p rate.
- Image-to-video: `reference_image_path` becomes the **first frame** for
  `kling-v3`; add `last_frame_image_path` with
  `operation="first_last_frame_to_video"` for interpolation. Aspect ratio may be
  overridden by the image ratio.
- Text on screen is unreliable; render text in the composition, not the clip.

### Multi-shot (Kling)

Pass `multi_shot=[{"prompt": ..., "duration": n}, ...]` (1-6 shots, each
prompt ≤ 512 chars). The shot durations **must sum exactly** to `duration`.
The tool sets `multi_shot=true` and `shot_type="customize"`. Use it for a
documentary beat sequence (inspector → crane → workshop) that must land in one
file with consistent grading.

## Prompting Kling v3 Omni (reference images)

Supply local files via `reference_image_paths` (uploaded to APIMart in order,
URLs expire after 72 h) or remote `reference_image_urls`. Bind them in the
prompt with 1-based tags:

> The yellow Mustang in <<<image_1>>> drives along a Mediterranean seafront
> promenade with palm trees, golden light, tracking shot from the side.

- If the prompt has no tag, APIMart prepends `<<<image_1>>>` automatically.
- Referencing `<<<image_N>>>` beyond the supplied count is rejected locally.
- For explicit first/last frames use `operation="image_to_video"` or
  `"first_last_frame_to_video"`; the tool sends `image_with_roles`.
- Reference images with baked-in text or logos leak into the output; crop or
  pick clean stills.

## Prompting Veo 3.1

Duration is always 8 s. `resolution` selects 720p/1080p/4k. Up to 3
`image_urls`: with `operation="reference_to_video"` the tool sends
`generation_type="reference"` (not supported by `veo3.1-quality`); with
`image_to_video` / `first_last_frame_to_video` it sends `generation_type="frame"`.
`veo3.1-lite` accepts text only.

## Operational notes

- Auth: `Authorization: Bearer $APIMART_API_KEY`. `APIMART_BASE_URL` overrides
  the host for proxies.
- Generated video links are valid for 24 hours; the tool downloads immediately.
- Errors arrive as `{"error": {"code", "message", "type"}}` (400 invalid
  params, 401 auth, 402 insufficient balance, 429 rate limit). Task failures
  arrive as `status="failed"` with `error.message`.
- No seed or system prompt controls. For iterative edits of an existing clip
  use `gemini_omni_video` instead.
- `nsfw_check=true` runs APIMart's moderation before submission (extra cost);
  off by default.

## Sources

- https://docs.apimart.ai/en/api-reference/videos/kling-v3/generation
- https://docs.apimart.ai/en/api-reference/videos/kling-v3-omni/generation
- https://docs.apimart.ai/en/api-reference/videos/veo3/generation
- https://docs.apimart.ai/en/api-reference/tasks/status
- https://docs.apimart.ai/en/api-reference/uploads/images
- https://apimart.ai/model/kling (rate card)
