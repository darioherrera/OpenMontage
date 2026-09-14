"""APIMart image generation and editing: FLUX.2 (flex/pro/max) and FLUX Kontext (pro/max).

Source: https://docs.apimart.ai/_llms/en/api-manual.md
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools import apimart_client
from tools.atlas_client import aspect_ratio_from_size
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

_DEFAULT_MODEL = "flux-2-pro"
_RATIOS = ("1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "21:9", "9:21")
_FLUX2_RESOLUTIONS = ("1MP", "2MP", "3MP", "4MP")
_FLUX2_MAX_PIXELS = 4_194_304
_OPTIONAL = ("seed", "prompt_upsampling", "safety_tolerance")

IMAGE_MODELS: dict[str, dict[str, Any]] = {
    "flux-2-flex": {"family": "flux-2", "max_images": 8, "optional_fields": _OPTIONAL + ("steps", "guidance")},
    "flux-2-pro": {"family": "flux-2", "max_images": 8, "optional_fields": _OPTIONAL},
    "flux-2-max": {"family": "flux-2", "max_images": 8, "optional_fields": _OPTIONAL},
    # Kontext output is ~1MP at a ratio; width/height make the task fail.
    "flux-kontext-pro": {"family": "flux-kontext", "max_images": 4, "optional_fields": _OPTIONAL},
    "flux-kontext-max": {"family": "flux-kontext", "max_images": 4, "optional_fields": _OPTIONAL},
}


def _choice(name: str, value: Any, allowed: tuple[Any, ...]) -> Any:
    if value not in allowed:
        raise ValueError(f"{name}={value!r} is not supported; choose one of {list(allowed)}")
    return value


class ApimartImage(BaseTool):
    name = "apimart_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "apimart"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:APIMART_API_KEY"]
    install_instructions = apimart_client.INSTALL_INSTRUCTIONS
    agent_skills = ["apimart", "flux-best-practices"]

    capabilities = ["generate_image", "text_to_image", "image_edit"]
    supports = {
        "custom_size": True, "aspect_ratio": True, "image_edit": True,
        "multiple_reference_images": True, "multi_model_gateway": True,
    }
    provider_matrix = {model: spec["family"] for model, spec in IMAGE_MODELS.items()}
    best_for = [
        "FLUX.2 flex/pro/max generation with exact dimensions up to 4MP and up to 8 references",
        "FLUX Kontext pro/max context-aware edits with up to 4 reference images",
    ]
    not_good_for = ["offline generation", "more than one image per request"]
    fallback_tools = ["flux_image", "atlas_image", "google_imagen"]
    quality_score = 0.85

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {"type": "string", "default": _DEFAULT_MODEL, "enum": sorted(IMAGE_MODELS)},
            "generation_mode": {"type": "string", "enum": ["generate", "edit"], "default": "generate"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "aspect_ratio": {"type": "string", "enum": [*_RATIOS, "auto"]},
            "resolution": {"type": "string", "enum": list(_FLUX2_RESOLUTIONS), "description": "FLUX.2 only."},
            "seed": {"type": "integer"},
            "prompt_upsampling": {"type": "boolean"},
            "safety_tolerance": {"type": "integer"},
            "steps": {"type": "integer", "description": "flux-2-flex only (1-50)."},
            "guidance": {"type": "number", "description": "flux-2-flex only (1.5-10)."},
            "image_url": {"type": "string"},
            "image_path": {"type": "string"},
            "image_urls": {"type": "array", "items": {"type": "string"}},
            "image_paths": {"type": "array", "items": {"type": "string"}},
            "output_format": {"type": "string", "enum": ["png", "jpeg", "webp"], "default": "png"},
            "extra_params": {"type": "object"},
            "poll_interval": {"type": "number", "default": 3.0},
            "poll_timeout": {"type": "number", "default": 600.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=250, network_required=True)
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "generation_mode", "width", "height", "aspect_ratio"]
    side_effects = ["writes image files to output_path", "calls APIMart API"]
    user_visible_verification = ["Inspect generated images for prompt fidelity and edit consistency"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if apimart_client.get_api_key() else ToolStatus.UNAVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["model_catalog"] = {
            model: {"family": spec["family"], "max_images": spec["max_images"]}
            for model, spec in IMAGE_MODELS.items()
        }
        return info

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 30.0

    def _build_payload(self, inputs: dict[str, Any], model: str) -> dict[str, Any]:
        if model not in IMAGE_MODELS:
            raise ValueError(f"Unsupported APIMart image model {model!r}; choose one of {sorted(IMAGE_MODELS)}")
        spec = IMAGE_MODELS[model]
        payload: dict[str, Any] = {
            "model": model,
            "prompt": inputs.get("prompt", ""),
            "output_format": _choice("output_format", inputs.get("output_format") or "png", ("png", "jpeg", "webp")),
        }

        ratio = inputs.get("aspect_ratio")
        if ratio:
            _choice("aspect_ratio", ratio, (*_RATIOS, "auto"))
        width, height = inputs.get("width"), inputs.get("height")

        if spec["family"] == "flux-2":
            if ratio or not (width and height):
                payload["size"] = ratio or "1:1"
                payload["resolution"] = _choice("resolution", inputs.get("resolution") or "2MP", _FLUX2_RESOLUTIONS)
            elif int(width) * int(height) > _FLUX2_MAX_PIXELS:
                raise ValueError(f"FLUX.2 output is limited to 4MP; {width}x{height} is larger")
            else:
                payload["width"], payload["height"] = int(width), int(height)
        else:
            payload["size"] = ratio or (
                aspect_ratio_from_size(int(width), int(height), list(_RATIOS)) if width and height else "1:1"
            )

        mode = _choice("generation_mode", inputs.get("generation_mode") or "generate", ("generate", "edit"))
        images = list(inputs.get("image_urls") or [])
        if mode == "edit" and not images:
            raise ValueError("edit requires image_url, image_urls, image_path, or image_paths")
        if len(images) > spec["max_images"]:
            raise ValueError(f"{model} accepts at most {spec['max_images']} reference images (got {len(images)})")
        if images:
            payload["image_urls"] = images

        for field in spec["optional_fields"]:
            if inputs.get(field) is not None:
                payload[field] = inputs[field]
        extra = inputs.get("extra_params")
        if isinstance(extra, dict):
            payload.update(extra)
        return payload

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = apimart_client.get_api_key()
        if not api_key:
            return ToolResult(success=False, error="APIMART_API_KEY not set. " + self.install_instructions)

        started = time.time()
        model = str(inputs.get("model") or _DEFAULT_MODEL)
        try:
            sources = [
                *([inputs["image_url"]] if inputs.get("image_url") else []),
                *(inputs.get("image_urls") or []),
                *([inputs["image_path"]] if inputs.get("image_path") else []),
                *(inputs.get("image_paths") or []),
            ]
            if model in IMAGE_MODELS and len(sources) > IMAGE_MODELS[model]["max_images"]:
                raise ValueError(f"{model} accepts at most {IMAGE_MODELS[model]['max_images']} reference images")
            resolved = {**inputs, "image_urls": [apimart_client.hosted_image(str(s), api_key) for s in sources]}
            payload = self._build_payload(resolved, model)
            task_id = apimart_client.submit(apimart_client.IMAGE_ENDPOINT, payload, api_key)
            data = apimart_client.poll(
                task_id, api_key,
                interval=float(inputs.get("poll_interval", 3.0)),
                timeout=float(inputs.get("poll_timeout", 600.0)),
            )
            urls = apimart_client.result_urls(data)
            requested = Path(inputs.get("output_path") or f"apimart_image.{payload['output_format']}")
            output_paths: list[Path] = []
            for index, url in enumerate(urls):
                path = requested if index == 0 else requested.with_name(f"{requested.stem}_{index + 1}{requested.suffix}")
                apimart_client.download(url, path)
                output_paths.append(path)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=f"APIMart image generation failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": "apimart", "model": model, "prompt": inputs.get("prompt", ""),
                "generation_mode": inputs.get("generation_mode") or "generate",
                "output": str(output_paths[0]), "output_path": str(output_paths[0]),
                "outputs": [str(path) for path in output_paths],
                "task_id": task_id, "source_url": urls[0], "source_urls": urls,
                "request_params": payload,
            },
            artifacts=[str(path) for path in output_paths],
            cost_usd=float(data.get("cost") or 0.0),
            duration_seconds=round(time.time() - started, 2),
            model=model,
        )
