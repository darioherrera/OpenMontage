"""APIMart video generation (unified gateway for Kling v3, Kling v3 Omni, Veo 3.1).

APIMart exposes one OpenAI-style endpoint for many third-party video models:

    POST https://api.apimart.ai/v1/videos/generations   -> {"code": 200, "data": [{"task_id", "status"}]}
    GET  https://api.apimart.ai/v1/tasks/{task_id}       -> {"code": 200, "data": {"status", "result": {"videos": [...]}}}
    POST https://api.apimart.ai/v1/uploads/images        -> {"url": "https://upload.apimart.ai/..."}

Local reference images are uploaded first (APIMart no longer accepts base64
payloads in generation requests; uploaded URLs expire after 72 hours), then
bound into the generation payload according to the selected model:

- ``kling-v3``      : ``image_urls`` = [first_frame] or [first_frame, last_frame]
- ``kling-v3-omni`` : ``image_urls`` referenced from the prompt as ``<<<image_N>>>``
                      (N starts at 1), or ``image_with_roles`` for first/last frame
- ``veo3.1-*``      : ``image_urls`` (max 3) + ``generation_type`` frame|reference

Pricing is per generated second and depends on model and mode. Kling prices
come from APIMart's published rate card; Veo prices are conservative estimates
until confirmed on https://apimart.ai/model/veo — check ``result.data["cost"]``
returned by the task endpoint for the actual charge.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

DEFAULT_BASE_URL = "https://api.apimart.ai"

KLING_MODELS = ["kling-v3", "kling-v3-omni"]
VEO_MODELS = ["veo3.1-fast", "veo3.1-quality", "veo3.1-lite"]
MODELS = KLING_MODELS + VEO_MODELS
DEFAULT_MODEL = "kling-v3"

KLING_MODES = ["std", "pro", "4k"]
VEO_RESOLUTIONS = ["720p", "1080p", "4k"]
ASPECT_RATIOS = ["16:9", "9:16", "1:1"]

# USD per generated second. Kling values are APIMart's published rates
# (720p std / 1080p pro / 4k, plus the 1080p-with-audio tier). Veo values are
# upper-bound estimates; the task endpoint reports the real charge.
PRICE_PER_SECOND: dict[str, dict[str, float]] = {
    "kling-v3": {"std": 0.0672, "pro": 0.0896, "pro_audio": 0.112, "4k": 0.42856},
    "kling-v3-omni": {"std": 0.0672, "pro": 0.0896, "pro_audio": 0.112, "4k": 0.42856},
    "veo3.1-fast": {"720p": 0.15, "1080p": 0.20, "4k": 0.40},
    "veo3.1-quality": {"720p": 0.40, "1080p": 0.50, "4k": 0.80},
    "veo3.1-lite": {"720p": 0.05, "1080p": 0.08, "4k": 0.15},
}

_IN_PROGRESS = {"pending", "processing", "submitted", "queued", "running"}
_SUCCESS = {"completed", "succeeded", "success"}
_FAILURES = {"failed", "cancelled", "canceled", "error"}

_IMAGE_REF_RE = re.compile(r"<<<image_(\d+)>>>")


class ApimartVideo(BaseTool):
    name = "apimart_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "apimart"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API
    quality_score = 0.8

    dependencies = ["env:APIMART_API_KEY"]
    install_instructions = (
        "Set APIMART_API_KEY to your APIMart API key.\n"
        "  Create one at https://apimart.ai/keys (pay-as-you-go, one key for Kling v3, "
        "Kling v3 Omni and Veo 3.1).\n"
        "  Optionally set APIMART_BASE_URL to override https://api.apimart.ai."
    )
    agent_skills = ["apimart-video", "ai-video-gen"]

    capabilities = [
        "text_to_video",
        "image_to_video",
        "first_last_frame_to_video",
        "reference_to_video",
    ]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "first_last_frame_to_video": True,
        "reference_to_video": True,
        "reference_image": True,
        "negative_prompt": True,
        "native_audio": True,
        "multi_shot": True,
        "seed": False,
        "conversational_editing": False,
        "resolution_1080p": True,
    }
    best_for = [
        "Kling v3 cinematic clips at 720p/1080p/4K for 3-15 seconds with one gateway key",
        "reference-image-bound subjects via Kling v3 Omni <<<image_N>>> prompt tags",
        "multi-shot storytelling (up to 6 shots in one request) with Kling v3",
        "Veo 3.1 8-second clips (fast/quality/lite) through the same endpoint",
    ]
    not_good_for = [
        "editing an existing clip in place (use gemini_omni_video)",
        "seed-reproducible generations",
        "clips longer than 15 seconds",
    ]
    fallback_tools = ["gemini_omni_video", "kling_video", "veo_video", "minimax_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "English prompt. For kling-v3-omni bind uploaded/remote images with "
                    "<<<image_1>>>, <<<image_2>>> ... (1-based, in reference order)."
                ),
            },
            "negative_prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": [
                    "text_to_video",
                    "image_to_video",
                    "first_last_frame_to_video",
                    "reference_to_video",
                ],
                "default": "text_to_video",
            },
            "model": {"type": "string", "enum": MODELS, "default": DEFAULT_MODEL},
            "mode": {
                "type": "string",
                "enum": KLING_MODES,
                "default": "std",
                "description": "Kling only: std=720p, pro=1080p, 4k.",
            },
            "resolution": {
                "type": "string",
                "enum": VEO_RESOLUTIONS,
                "description": "Veo only: 720p (default), 1080p, 4k. For Kling, mapped onto mode.",
            },
            "duration": {
                "type": "integer",
                "description": "Seconds. Kling: 3-15 (default 5). Veo: fixed 8.",
            },
            "aspect_ratio": {"type": "string", "enum": ASPECT_RATIOS, "default": "16:9"},
            "audio": {
                "type": "boolean",
                "default": False,
                "description": "Kling only: synthesize audio with the clip.",
            },
            "reference_image_path": {
                "type": "string",
                "description": "Local image used as the first frame (image_to_video). Uploaded automatically.",
            },
            "reference_image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Local reference images, uploaded in order (kling-v3-omni: <<<image_N>>>; veo: reference/frame).",
            },
            "reference_image_url": {"type": "string", "description": "Remote first-frame image URL."},
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Remote reference image URLs (kept in order, after uploaded local paths).",
            },
            "last_frame_image_path": {"type": "string", "description": "Local last-frame image (first_last_frame_to_video)."},
            "last_frame_image_url": {"type": "string", "description": "Remote last-frame image URL."},
            "multi_shot": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "Kling only. List of {prompt, duration} shots (max 6). Durations must sum to "
                    "'duration'. Enables multi_shot=true with shot_type=customize."
                ),
            },
            "watermark": {"type": "boolean", "default": False},
            "nsfw_check": {"type": "boolean", "default": False},
            "poll_interval_seconds": {"type": "number", "default": 6},
            "timeout_seconds": {"type": "number", "default": 900},
            "output_path": {"type": "string"},
            "scene_id": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "operation", "mode", "duration", "aspect_ratio"]

    # ------------------------------------------------------------------ config
    def _get_api_key(self) -> str | None:
        return os.environ.get("APIMART_API_KEY") or None

    def _base_url(self) -> str:
        return (os.environ.get("APIMART_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    # ------------------------------------------------------------------ pricing
    @staticmethod
    def _coerce_duration(value: Any, default: int) -> int:
        if isinstance(value, bool):
            return default
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return default

    def _effective_tier(self, inputs: dict[str, Any], model: str) -> str:
        if model in KLING_MODELS:
            mode = inputs.get("mode")
            if not mode:
                resolution = inputs.get("resolution")
                mode = {"1080p": "pro", "4k": "4k"}.get(resolution, "std")
            if mode == "pro" and inputs.get("audio"):
                return "pro_audio"
            return mode if mode in KLING_MODES else "std"
        resolution = inputs.get("resolution") or "720p"
        return resolution if resolution in VEO_RESOLUTIONS else "720p"

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", DEFAULT_MODEL)
        if model not in MODELS:
            return 0.0
        seconds = 8 if model in VEO_MODELS else self._coerce_duration(inputs.get("duration"), 5)
        rate = PRICE_PER_SECOND[model].get(self._effective_tier(inputs, model), 0.0)
        return round(seconds * rate, 3)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", DEFAULT_MODEL)
        if model == "veo3.1-quality" or inputs.get("mode") == "4k":
            return 240.0
        return 120.0

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _error_from_payload(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return "APIMart returned a non-JSON response."
        err = payload.get("error")
        if isinstance(err, dict):
            code = err.get("code") or payload.get("code") or ""
            return f"APIMart error {code}: {err.get('message', 'unknown error')}".strip()
        code = payload.get("code")
        if isinstance(code, int) and code != 200:
            return f"APIMart error {code}: {payload.get('message') or payload.get('msg') or 'request failed'}"
        return None

    def _upload_image(self, requests_mod: Any, api_key: str, base_url: str, path_str: str) -> str:
        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"Reference image not found: {path}")
        with path.open("rb") as fh:
            resp = requests_mod.post(
                f"{base_url}/v1/uploads/images",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (path.name, fh)},
                timeout=120,
            )
        resp.raise_for_status()
        data = resp.json()
        err = self._error_from_payload(data)
        if err:
            raise RuntimeError(err)
        url = data.get("url") or (data.get("data") or {}).get("url")
        if not url:
            raise RuntimeError("APIMart upload did not return a URL.")
        return str(url)

    def _resolve_images(
        self, requests_mod: Any, api_key: str, base_url: str, inputs: dict[str, Any]
    ) -> tuple[list[str], str | None]:
        """Return (ordered reference URLs, last-frame URL). Local paths are uploaded."""
        refs: list[str] = []
        first_path = inputs.get("reference_image_path")
        if first_path:
            refs.append(self._upload_image(requests_mod, api_key, base_url, str(first_path)))
        for p in inputs.get("reference_image_paths") or []:
            if p:
                refs.append(self._upload_image(requests_mod, api_key, base_url, str(p)))
        if inputs.get("reference_image_url"):
            refs.append(str(inputs["reference_image_url"]))
        for u in inputs.get("reference_image_urls") or []:
            if u:
                refs.append(str(u))

        last: str | None = None
        if inputs.get("last_frame_image_path"):
            last = self._upload_image(requests_mod, api_key, base_url, str(inputs["last_frame_image_path"]))
        elif inputs.get("last_frame_image_url"):
            last = str(inputs["last_frame_image_url"])
        return refs, last

    def _build_payload(
        self, inputs: dict[str, Any], model: str, refs: list[str], last: str | None
    ) -> tuple[dict[str, Any] | None, str | None]:
        operation = inputs.get("operation", "text_to_video")
        prompt = str(inputs.get("prompt") or "").strip()
        if not prompt:
            return None, "apimart_video requires 'prompt'."
        aspect_ratio = inputs.get("aspect_ratio") or "16:9"
        if aspect_ratio not in ASPECT_RATIOS:
            return None, f"Unsupported aspect_ratio '{aspect_ratio}'. Use one of {ASPECT_RATIOS}."
        if model in VEO_MODELS and aspect_ratio == "1:1":
            return None, "Veo 3.1 only supports 16:9 or 9:16."

        payload: dict[str, Any] = {"model": model, "prompt": prompt, "aspect_ratio": aspect_ratio}
        if inputs.get("negative_prompt"):
            payload["negative_prompt"] = str(inputs["negative_prompt"])
        if inputs.get("nsfw_check"):
            payload["nsfw_check"] = True

        if operation in {"image_to_video", "first_last_frame_to_video"} and not refs:
            return None, f"{operation} requires a first-frame image (reference_image_path or reference_image_url)."
        if operation == "first_last_frame_to_video" and not last:
            return None, "first_last_frame_to_video requires last_frame_image_path or last_frame_image_url."
        if operation == "reference_to_video" and not refs:
            return None, "reference_to_video requires at least one reference image."

        if model in KLING_MODELS:
            duration = self._coerce_duration(inputs.get("duration"), 5)
            if not 3 <= duration <= 15:
                return None, "Kling v3 duration must be an integer between 3 and 15 seconds."
            payload["duration"] = duration
            payload["mode"] = self._effective_tier(inputs, model).replace("_audio", "")
            if inputs.get("audio"):
                payload["audio"] = True
            if inputs.get("watermark") is not None:
                payload["watermark"] = bool(inputs.get("watermark"))

            if model == "kling-v3":
                if operation == "first_last_frame_to_video":
                    payload["image_urls"] = [refs[0], last]
                elif operation == "image_to_video":
                    payload["image_urls"] = refs[:1]
                elif operation == "reference_to_video":
                    # kling-v3 has no free-form reference mode; the closest documented
                    # behaviour is first-frame conditioning on the first reference.
                    payload["image_urls"] = refs[:1]
            else:  # kling-v3-omni
                if operation == "first_last_frame_to_video":
                    payload["image_with_roles"] = [
                        {"url": refs[0], "role": "first_frame"},
                        {"url": last, "role": "last_frame"},
                    ]
                elif operation == "image_to_video":
                    payload["image_with_roles"] = [{"url": refs[0], "role": "first_frame"}]
                elif operation == "reference_to_video" or refs:
                    payload["image_urls"] = refs
                    max_ref = max((int(m) for m in _IMAGE_REF_RE.findall(prompt)), default=0)
                    if max_ref > len(refs):
                        return None, (
                            f"Prompt references <<<image_{max_ref}>>> but only {len(refs)} "
                            "reference images were supplied."
                        )

            shots = inputs.get("multi_shot")
            if shots:
                if not 1 <= len(shots) <= 6:
                    return None, "multi_shot supports 1 to 6 shots."
                total = sum(self._coerce_duration(s.get("duration"), 0) for s in shots)
                if total != duration:
                    return None, f"multi_shot durations sum to {total}s but duration is {duration}s."
                payload["multi_shot"] = True
                payload["shot_type"] = "customize"
                payload["multi_prompt"] = [
                    {
                        "index": i + 1,
                        "prompt": str(s.get("prompt") or "")[:512],
                        "duration": self._coerce_duration(s.get("duration"), 0),
                    }
                    for i, s in enumerate(shots)
                ]
        else:  # Veo 3.1
            payload["duration"] = 8
            resolution = inputs.get("resolution") or "720p"
            if resolution not in VEO_RESOLUTIONS:
                return None, f"Veo resolution must be one of {VEO_RESOLUTIONS}."
            payload["resolution"] = resolution
            if refs or last:
                if model == "veo3.1-lite":
                    return None, "veo3.1-lite does not support image inputs."
                if operation == "first_last_frame_to_video":
                    payload["image_urls"] = [refs[0], last]
                    payload["generation_type"] = "frame"
                elif operation == "image_to_video":
                    payload["image_urls"] = refs[:1]
                    payload["generation_type"] = "frame"
                else:
                    if model == "veo3.1-quality":
                        return None, "veo3.1-quality does not support reference mode; use veo3.1-fast."
                    payload["image_urls"] = refs[:3]
                    payload["generation_type"] = "reference"
        return payload, None

    @staticmethod
    def _extract_video_url(task: dict[str, Any]) -> str | None:
        result = task.get("result") or {}
        videos = result.get("videos") or result.get("video") or []
        if isinstance(videos, dict):
            videos = [videos]
        for item in videos:
            if isinstance(item, str):
                return item
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("video_url")
            if isinstance(url, list) and url:
                return str(url[0])
            if isinstance(url, str) and url:
                return url
        direct = result.get("video_url") or task.get("video_url")
        return str(direct) if direct else None

    # ------------------------------------------------------------------ execute
    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(success=False, error="APIMART_API_KEY not set. " + self.install_instructions)

        import requests

        start = time.time()
        base_url = self._base_url()
        model = inputs.get("model", DEFAULT_MODEL)
        if model not in MODELS:
            return ToolResult(success=False, error=f"Unsupported APIMart model '{model}'. Use one of {MODELS}.")

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        def _redact(text: str) -> str:
            return text.replace(api_key, "***")

        task_id: str | None = None
        task: dict[str, Any] = {}
        uploaded: list[str] = []
        try:
            refs, last = self._resolve_images(requests, api_key, base_url, inputs)
            uploaded = refs + ([last] if last else [])
            payload, validation_error = self._build_payload(inputs, model, refs, last)
            if validation_error:
                return ToolResult(success=False, error=validation_error)
            assert payload is not None

            submit = requests.post(
                f"{base_url}/v1/videos/generations", headers=headers, json=payload, timeout=60
            )
            submit.raise_for_status()
            submit_data = submit.json()
            err = self._error_from_payload(submit_data)
            if err:
                return ToolResult(success=False, error=err, model=model)
            entries = submit_data.get("data")
            first = entries[0] if isinstance(entries, list) and entries else (entries or {})
            task_id = first.get("task_id") or first.get("id")
            if not task_id:
                return ToolResult(success=False, error="APIMart did not return a task_id.", model=model)

            poll_interval = max(float(inputs.get("poll_interval_seconds", 6)), 0.1)
            timeout_seconds = max(float(inputs.get("timeout_seconds", 900)), 1.0)
            deadline = time.monotonic() + timeout_seconds
            video_url: str | None = None
            while True:
                if time.monotonic() >= deadline:
                    return ToolResult(
                        success=False,
                        error=(
                            f"APIMart task timed out after {timeout_seconds:g}s; the remote task may "
                            f"still complete. Inspect task_id '{task_id}'."
                        ),
                        data={"provider": self.provider, "model": model, "task_id": task_id, "status": "timeout"},
                        model=model,
                    )
                time.sleep(min(poll_interval, max(deadline - time.monotonic(), 0)))
                status_resp = requests.get(
                    f"{base_url}/v1/tasks/{task_id}", headers=headers, params={"language": "en"}, timeout=30
                )
                status_resp.raise_for_status()
                status_data = status_resp.json()
                err = self._error_from_payload(status_data)
                if err:
                    return ToolResult(success=False, error=err, data={"task_id": task_id}, model=model)
                task = status_data.get("data") or {}
                status = str(task.get("status") or "").lower()
                if status in _SUCCESS:
                    video_url = self._extract_video_url(task)
                    break
                if status in _FAILURES:
                    detail = task.get("error") or {}
                    message = detail.get("message") if isinstance(detail, dict) else str(detail)
                    return ToolResult(
                        success=False,
                        error=f"APIMart video generation {status}: {message or 'unknown error'}",
                        data={"task_id": task_id, "task": task},
                        model=model,
                    )
                if status and status not in _IN_PROGRESS:
                    return ToolResult(
                        success=False,
                        error=f"APIMart returned unknown task status '{status}'.",
                        data={"task_id": task_id, "task": task},
                        model=model,
                    )

            if not video_url:
                return ToolResult(
                    success=False,
                    error="APIMart task completed but no video URL was returned.",
                    data={"task_id": task_id, "task": task},
                    model=model,
                )
            video_resp = requests.get(video_url, timeout=300)
            video_resp.raise_for_status()
            output_path = Path(inputs.get("output_path", "apimart_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_resp.content)
        except Exception as e:  # noqa: BLE001 - surface a redacted error to the caller
            return ToolResult(
                success=False,
                error=f"APIMart video generation failed: {_redact(str(e))}",
                data={"provider": self.provider, "model": model, "task_id": task_id} if task_id else {},
                model=model,
            )

        actual_cost = task.get("cost")
        cost = float(actual_cost) if isinstance(actual_cost, (int, float)) else self.estimate_cost(inputs)
        data: dict[str, Any] = {
            "provider": self.provider,
            "model": model,
            "task_id": task_id,
            "prompt": inputs.get("prompt", ""),
            "output": str(output_path),
            "video_url": video_url,
            "uploaded_reference_urls": uploaded,
            "task": task,
            "cost_source": "provider" if isinstance(actual_cost, (int, float)) else "estimate",
        }
        return ToolResult(
            success=True,
            data=data,
            artifacts=[str(output_path)],
            cost_usd=round(cost, 4),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
