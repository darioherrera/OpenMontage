"""APIMart video generation: Sora 2, Veo 3.1, Kling v3, Seedance 2.x, Gemini Omni.

Every model shares one endpoint but has its own request schema, so each is
cataloged explicitly and validated before any paid call.
Source: https://docs.apimart.ai/_llms/en/api-manual.md
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from tools import apimart_client
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

_DEFAULT_MODEL = "kling-v3"
_OPERATIONS = ("text_to_video", "image_to_video", "reference_to_video", "video_edit")
_T2V, _I2V, _REF, _EDIT = _OPERATIONS

_SEEDANCE_RATIOS = ("16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive")
_KLING_MODES = {"720p": "std", "1080p": "pro", "4k": "4k"}
_KLING_OPTIONAL = ("negative_prompt", "watermark", "multi_shot", "shot_type", "multi_prompt", "element_list")
_SEEDANCE_OPTIONAL = ("seed", "return_last_frame", "tools")
_AUDIO_KEYS = {"kling": "audio", "kling_omni": "audio", "seedance": "generate_audio"}
_IMAGE_TAG = re.compile(r"<<<image_(\d+)>>>")

# USD per generated second. Kling: APIMart's published rate card (std 720p / pro 1080p /
# pro with audio / 4k). Veo: conservative upper-bound estimates. Other models are not
# cataloged; the finished task reports the actual charge either way.
_PRICE_PER_SECOND: dict[str, dict[str, float]] = {
    "kling-v3": {"std": 0.0672, "pro": 0.0896, "pro_audio": 0.112, "4k": 0.42856},
    "kling-v3-omni": {"std": 0.0672, "pro": 0.0896, "pro_audio": 0.112, "4k": 0.42856},
    "veo3.1-fast": {"720p": 0.15, "1080p": 0.20, "4k": 0.40},
    "veo3.1-quality": {"720p": 0.40, "1080p": 0.50, "4k": 0.80},
    "veo3.1-lite": {"720p": 0.05, "1080p": 0.08, "4k": 0.15},
}


def _spec(
    family: str,
    operations: tuple[str, ...],
    resolutions: tuple[str, ...],
    ratios: tuple[str, ...],
    *,
    durations: tuple[int, ...] | None = None,
    default_duration: int | None = None,
    default_ratio: str | None = None,
    ratio_key: str = "aspect_ratio",
    max_images: int | None = None,
    limits: dict[str, int] | None = None,
    optional: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "family": family,
        "operations": frozenset(operations),
        "resolutions": resolutions,
        "ratios": ratios,
        "default_ratio": default_ratio or ratios[0],
        "ratio_key": ratio_key,
        "durations": durations,
        "default_duration": default_duration,
        "max_images": max_images,
        # Reference videos/audios default to "not accepted".
        "limits": {"videos": 0, "audios": 0, **(limits or {})},
        "optional_fields": optional,
    }


_SORA_DURATIONS = (4, 8, 12, 16, 20)
_KLING_DURATIONS = tuple(range(3, 16))

VIDEO_MODELS: dict[str, dict[str, Any]] = {
    "sora-2": _spec("sora", (_T2V, _I2V), ("720p",), ("16:9", "9:16"),
                    durations=_SORA_DURATIONS, default_duration=8, max_images=1),
    "sora-2-pro": _spec("sora", (_T2V, _I2V), ("720p", "1024p", "1080p"), ("16:9", "9:16"),
                        durations=_SORA_DURATIONS, default_duration=8, max_images=1),
    "veo3.1-fast": _spec("veo", (_T2V, _I2V, _REF), ("720p", "1080p", "4k"), ("16:9", "9:16"),
                         durations=(8,), default_duration=8, max_images=3,
                         optional=("official_fallback", "enable_gif")),
    "veo3.1-quality": _spec("veo", (_T2V, _I2V), ("720p", "1080p", "4k"), ("16:9", "9:16"),
                            durations=(8,), default_duration=8, max_images=2,
                            optional=("official_fallback", "enable_gif")),
    "veo3.1-lite": _spec("veo", (_T2V,), ("720p", "1080p", "4k"), ("16:9", "9:16"),
                         durations=(8,), default_duration=8, max_images=0, optional=("enable_gif",)),
    "kling-v3": _spec("kling", (_T2V, _I2V), tuple(_KLING_MODES), ("16:9", "9:16", "1:1"),
                      durations=_KLING_DURATIONS, default_duration=5, max_images=2, optional=_KLING_OPTIONAL),
    "kling-v3-omni": _spec("kling_omni", _OPERATIONS, tuple(_KLING_MODES), ("16:9", "9:16", "1:1"),
                           durations=_KLING_DURATIONS, default_duration=5, limits={"videos": 1},
                           optional=_KLING_OPTIONAL),
    "seedance-2.0": _spec("seedance", (_T2V, _I2V, _REF), ("480p", "720p", "1080p", "4k"), _SEEDANCE_RATIOS,
                          durations=tuple(range(4, 16)), default_duration=5, ratio_key="size",
                          limits={"images": 9, "videos": 3, "audios": 3}, optional=_SEEDANCE_OPTIONAL),
    "seedance-2.0-fast": _spec("seedance", (_T2V, _I2V, _REF), ("480p", "720p"), _SEEDANCE_RATIOS,
                               durations=tuple(range(4, 16)), default_duration=5, ratio_key="size",
                               limits={"images": 9, "videos": 3, "audios": 3}, optional=_SEEDANCE_OPTIONAL),
    "seedance-2.0-mini": _spec("seedance", (_T2V, _I2V, _REF), ("480p", "720p"), _SEEDANCE_RATIOS,
                               durations=tuple(range(4, 16)), default_duration=5, ratio_key="size",
                               limits={"images": 9, "videos": 3, "audios": 3}, optional=_SEEDANCE_OPTIONAL),
    "seedance-2.5": _spec("seedance", _OPERATIONS, ("480p", "720p", "1080p"), _SEEDANCE_RATIOS,
                          durations=tuple(range(4, 31)) + (-1,), default_duration=5, default_ratio="adaptive",
                          ratio_key="size", limits={"images": 30, "videos": 10, "audios": 10},
                          optional=_SEEDANCE_OPTIONAL + ("watermark", "output_format", "omni_reference_task_type")),
    # No duration parameter: the model picks 3–10s from the prompt.
    "gemini-omni-1.1-flash": _spec("gemini_omni", _OPERATIONS, ("360p", "720p", "1080p", "4k"), ("16:9", "9:16"),
                                   max_images=10, limits={"videos": 1},
                                   optional=("extend_from_task_id", "metadata")),
}


def _choice(name: str, value: Any, allowed: tuple[Any, ...]) -> Any:
    if value not in allowed:
        raise ValueError(f"{name}={value!r} is not supported; choose one of {list(allowed)}")
    return value


def _remote_only(value: str, label: str) -> str:
    if not apimart_client.is_remote(value):
        raise ValueError(f"APIMart only hosts uploaded images; pass a public URL for the {label} ({value!r})")
    return value


def _merged(inputs: dict[str, Any], kind: str) -> list[str]:
    return [
        str(value)
        for key in (f"reference_{kind}s", f"reference_{kind}_urls", f"reference_{kind}_paths")
        for value in inputs.get(key) or []
    ]


class ApimartVideo(BaseTool):
    name = "apimart_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "apimart"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:APIMART_API_KEY"]
    install_instructions = apimart_client.INSTALL_INSTRUCTIONS
    agent_skills = ["apimart", "ai-video-gen", "seedance-2-0", "gemini-omni"]

    capabilities = list(_OPERATIONS)
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "video_edit": True,
        "first_last_frame": True,
        "mixed_media_references": True,
        "native_audio": True,
        "custom_duration": True,
        "aspect_ratio": True,
        "multi_model_gateway": True,
    }
    provider_matrix = {model: sorted(spec["operations"]) for model, spec in VIDEO_MODELS.items()}
    best_for = [
        "Sora 2 / Sora 2 Pro text and image to video through one APIMart key",
        "Veo 3.1 fast/quality/lite with first-last frame and reference images up to 4K",
        "Kling v3 and Kling v3 Omni (multi-shot, subjects, video edit) up to 4K",
        "Seedance 2.0/2.5 mixed image, video, and audio references; Gemini Omni 1.1 Flash edits",
    ]
    not_good_for = ["offline generation", "local reference video or audio files (APIMart only hosts images)"]
    fallback_tools = ["atlas_video", "kling_video", "veo_video", "seedance_video"]
    quality_score = 0.86

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {"type": "string", "default": _DEFAULT_MODEL, "enum": sorted(VIDEO_MODELS)},
            "operation": {"type": "string", "enum": list(_OPERATIONS), "default": _T2V},
            "duration": {"type": "integer", "description": "Seconds; allowed values depend on the model."},
            "aspect_ratio": {"type": "string"},
            "resolution": {"type": "string", "description": "e.g. 720p, 1080p, 4k (Kling maps to std/pro/4k)."},
            "generate_audio": {"type": "boolean"},
            "audio": {"type": "boolean", "description": "Alias for generate_audio."},
            "mode": {"type": "string", "enum": ["std", "pro", "4k"], "description": "Kling only; overrides resolution."},
            "seed": {"type": "integer"},
            "negative_prompt": {"type": "string"},
            "watermark": {"type": "boolean"},
            "output_format": {"type": "string", "enum": ["mp4", "mov"]},
            "image_url": {"type": "string", "description": "First frame."},
            "image_path": {"type": "string"},
            "reference_image_url": {"type": "string"},
            "reference_image_path": {"type": "string"},
            "last_image_url": {"type": "string"},
            "last_image_path": {"type": "string"},
            "end_image_url": {"type": "string"},
            "end_image_path": {"type": "string"},
            "reference_images": {"type": "array", "items": {"type": "string"}},
            "reference_videos": {"type": "array", "items": {"type": "string"}},
            "reference_audios": {"type": "array", "items": {"type": "string"}},
            "video_url": {"type": "string", "description": "Source video for video_edit (public URL)."},
            "video_path": {"type": "string"},
            "extra_params": {"type": "object"},
            "poll_interval": {"type": "number", "default": 5.0},
            "poll_timeout": {"type": "number", "default": 1200.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=500, network_required=True)
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "operation", "duration", "aspect_ratio"]
    side_effects = ["writes video file to output_path", "calls APIMart API"]
    user_visible_verification = ["Watch the generated clip for prompt fidelity, motion coherence, and audio quality"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if apimart_client.get_api_key() else ToolStatus.UNAVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["model_catalog"] = {
            model: {
                "family": spec["family"],
                "operations": sorted(spec["operations"]),
                "durations": list(spec["durations"]) if spec["durations"] else None,
                "resolutions": list(spec["resolutions"]),
                "aspect_ratios": list(spec["ratios"]),
                "max_images": spec["max_images"],
                "reference_limits": spec["limits"],
            }
            for model, spec in VIDEO_MODELS.items()
        }
        return info

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = str(inputs.get("model") or _DEFAULT_MODEL)
        rates = _PRICE_PER_SECOND.get(model)
        if not rates:
            return 0.0
        if model.startswith("veo"):
            seconds, tier = 8, inputs.get("resolution") or "720p"
        else:
            try:
                seconds = int(inputs.get("duration") or 5)
            except (TypeError, ValueError):
                seconds = 5
            tier = inputs.get("mode") or _KLING_MODES.get(inputs.get("resolution") or "720p", "std")
            if tier == "pro" and (inputs.get("generate_audio") or inputs.get("audio")):
                tier = "pro_audio"
        return round(seconds * rates.get(tier, 0.0), 3)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 180.0

    def is_operation_available(self, operation: str) -> bool:
        return operation in _OPERATIONS

    def _build_payload(self, inputs: dict[str, Any], model: str) -> dict[str, Any]:
        if model not in VIDEO_MODELS:
            raise ValueError(f"Unsupported APIMart video model {model!r}; choose one of {sorted(VIDEO_MODELS)}")
        spec = VIDEO_MODELS[model]
        family = spec["family"]
        operation = _choice("operation", str(inputs.get("operation") or _T2V), tuple(sorted(spec["operations"])))
        payload: dict[str, Any] = {"model": model, "prompt": inputs.get("prompt", "")}

        if spec["durations"]:
            duration = int(inputs.get("duration") or spec["default_duration"])
            payload["duration"] = _choice("duration", duration, spec["durations"])
        ratio = inputs.get("aspect_ratio") or spec["default_ratio"]
        payload[spec["ratio_key"]] = _choice("aspect_ratio", ratio, spec["ratios"])
        resolution = _choice("resolution", inputs.get("resolution") or "720p", spec["resolutions"])
        if family.startswith("kling"):
            # Kling's own `mode` vocabulary wins over the canonical resolution.
            payload["mode"] = _choice("mode", inputs.get("mode") or _KLING_MODES[resolution], tuple(_KLING_MODES.values()))
        else:
            payload["resolution"] = resolution

        first = inputs.get("image_url")
        last = inputs.get("last_image_url")
        images = list(inputs.get("reference_images") or [])
        videos = list(inputs.get("reference_videos") or [])
        audios = list(inputs.get("reference_audios") or [])
        video = inputs.get("video_url")

        if operation == _I2V and not first:
            raise ValueError("image_to_video requires image_url or image_path")
        if operation == _REF and not (images or videos or audios):
            raise ValueError("reference_to_video requires reference_images, reference_videos, or reference_audios")
        if operation == _EDIT and not video:
            raise ValueError("video_edit requires video_url or video_path")
        if last and not first:
            raise ValueError("a last frame requires a first frame (image_url or image_path)")
        if images and _REF not in spec["operations"]:
            raise ValueError(f"{model} has no reference-image mode; use image_url (+ last_image_url)")
        if video and _EDIT not in spec["operations"]:
            raise ValueError(f"{model} does not support video_edit")

        image_count = len(images) + sum(1 for frame in (first, last) if frame)
        if spec["max_images"] is not None and image_count > spec["max_images"]:
            raise ValueError(f"{model} accepts at most {spec['max_images']} images (got {image_count})")
        for kind, items in (("images", images), ("videos", videos + ([video] if video else [])), ("audios", audios)):
            cap = spec["limits"].get(kind)
            if cap is not None and len(items) > cap:
                raise ValueError(f"{model} accepts at most {cap} reference {kind} (got {len(items)})")

        if family in {"sora", "kling"}:
            if first:
                payload["image_urls"] = [frame for frame in (first, last) if frame]
        elif family == "veo":
            if first and images:
                raise ValueError("Veo cannot combine a first frame with reference images")
            if first:
                payload["image_urls"] = [frame for frame in (first, last) if frame]
                if last:
                    payload["generation_type"] = "frame"
            elif images:
                payload["image_urls"] = images
                payload["generation_type"] = "reference"
        elif family == "kling_omni":
            supplied = image_count
            missing = [n for n in map(int, _IMAGE_TAG.findall(str(payload["prompt"]))) if not 1 <= n <= supplied]
            if missing:
                raise ValueError(
                    f"prompt references <<<image_{missing[0]}>>> but only {supplied} image(s) were supplied"
                )
            if first:
                payload["image_with_roles"] = [
                    {"url": first, "role": "first_frame"},
                    *([{"url": last, "role": "last_frame"}] if last else []),
                    *({"url": url, "role": "reference"} for url in images),
                ]
            elif images:
                payload["image_urls"] = images
            if video or videos:
                payload["video_list"] = [
                    {"video_url": video, "refer_type": "base"} if video
                    else {"video_url": videos[0], "refer_type": "feature"}
                ]
        elif family == "seedance":
            if not model.startswith("seedance-2.5") and audios and not (images or videos or first):
                raise ValueError(f"{model} reference audio must be paired with reference images or videos")
            if first:
                # image_urls and image_with_roles are mutually exclusive, so references ride along as roles.
                payload["image_with_roles"] = [
                    {"url": first, "role": "first_frame"},
                    *([{"url": last, "role": "last_frame"}] if last else []),
                    *({"url": url, "role": "reference_image"} for url in images),
                ]
                if model == "seedance-2.5":
                    payload["size"] = "adaptive"  # API hard constraint for frame jobs
            elif images:
                payload["image_urls"] = images
            if video:
                payload["video_urls"] = [video, *videos]
                # API hard constraints for edit: adaptive size, output length follows the source.
                payload.update(omni_reference_task_type="edit", size="adaptive", duration=-1)
            elif videos:
                payload["video_urls"] = videos
            if audios:
                payload["audio_urls"] = audios
        elif family == "gemini_omni":
            if first:
                payload["first_frame_image"] = first
            if last:
                payload["last_frame_image"] = last
            if images:
                payload["image_urls"] = images
            if video or videos:
                payload["video_urls"] = [video] if video else videos

        audio_key = _AUDIO_KEYS.get(family)
        audio = inputs.get("generate_audio", inputs.get("audio"))
        if audio_key and audio is not None and "video_list" not in payload:
            payload[audio_key] = bool(audio)

        for field in spec["optional_fields"]:
            if inputs.get(field) is not None:
                payload[field] = inputs[field]

        extra = inputs.get("extra_params")
        if isinstance(extra, dict):
            payload.update(extra)
        return payload

    def _resolve_media(self, inputs: dict[str, Any], api_key: str) -> dict[str, Any]:
        """Normalize media aliases; upload local images; reject local video/audio before any upload."""
        resolved = dict(inputs)
        video = next((inputs[k] for k in ("video_url", "reference_video_url", "video_path", "reference_video_path") if inputs.get(k)), None)
        resolved["video_url"] = _remote_only(str(video), "source video") if video else None
        resolved["reference_videos"] = [_remote_only(value, "reference video") for value in _merged(inputs, "video")]
        resolved["reference_audios"] = [_remote_only(value, "reference audio") for value in _merged(inputs, "audio")]

        for target, sources in (
            ("image_url", ("image_url", "reference_image_url", "image_path", "reference_image_path")),
            ("last_image_url", ("last_image_url", "end_image_url", "last_image_path", "end_image_path")),
        ):
            value = next((inputs[k] for k in sources if inputs.get(k)), None)
            resolved[target] = apimart_client.hosted_image(str(value), api_key) if value else None
        resolved["reference_images"] = [apimart_client.hosted_image(value, api_key) for value in _merged(inputs, "image")]
        return resolved

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = apimart_client.get_api_key()
        if not api_key:
            return ToolResult(success=False, error="APIMART_API_KEY not set. " + self.install_instructions)

        started = time.time()
        model = str(inputs.get("model") or _DEFAULT_MODEL)
        try:
            if model not in VIDEO_MODELS:
                raise ValueError(f"Unsupported APIMart video model {model!r}; choose one of {sorted(VIDEO_MODELS)}")
            payload = self._build_payload(self._resolve_media(inputs, api_key), model)
            task_id = apimart_client.submit(apimart_client.VIDEO_ENDPOINT, payload, api_key)
            data = apimart_client.poll(
                task_id, api_key,
                interval=float(inputs.get("poll_interval", 5.0)),
                timeout=float(inputs.get("poll_timeout", 1200.0)),
            )
            source_url = apimart_client.result_urls(data)[0]
            suffix = str(payload.get("output_format", "mp4"))
            output_path = Path(inputs.get("output_path") or f"apimart_video.{suffix}")
            apimart_client.download(source_url, output_path)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=f"APIMart video generation failed: {exc}")

        from tools.video._shared import probe_output

        return ToolResult(
            success=True,
            data={
                "provider": "apimart", "model": model, "prompt": inputs.get("prompt", ""),
                "operation": payload.get("operation", inputs.get("operation", _T2V)),
                "output": str(output_path), "output_path": str(output_path),
                "task_id": task_id, "source_url": source_url,
                "format": output_path.suffix.lstrip("."), "request_params": payload,
                **probe_output(output_path),
            },
            artifacts=[str(output_path)],
            # APIMart reports the actual USD charge on the finished task.
            cost_usd=float(data.get("cost") or 0.0),
            duration_seconds=round(time.time() - started, 2),
            model=model,
        )
