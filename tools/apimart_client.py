"""Shared APIMart API plumbing for the image and video provider tools.

APIMart (https://apimart.ai) is a multi-model gateway: one key in front of Sora,
Veo, Kling, Seedance, Gemini Omni, FLUX and more. Every media generation is async:

    POST /v1/videos/generations  ->  {"code": 200, "data": [{"task_id": ...}]}
    POST /v1/images/generations  ->  {"code": 200, "data": [{"task_id": ...}]}
    GET  /v1/tasks/{task_id}     ->  {"code": 200, "data": {"status", "result", "cost", "error"}}

`requests` is imported lazily inside functions so registry discovery stays fast
(see tests/contracts — the lazy-import convention is enforced by the suite).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

# APIMART_BASE_URL overrides the host (e.g. a proxy); read at import, after the registry loads .env.
BASE_URL = (os.environ.get("APIMART_BASE_URL") or "https://api.apimart.ai").rstrip("/") + "/v1"

VIDEO_ENDPOINT = f"{BASE_URL}/videos/generations"
IMAGE_ENDPOINT = f"{BASE_URL}/images/generations"
TASK_ENDPOINT = f"{BASE_URL}/tasks"
UPLOAD_IMAGE_ENDPOINT = f"{BASE_URL}/uploads/images"

# `submitted`/`pending`/`processing` are in-flight. Unknown statuses are treated as
# in-flight so a new intermediate state can't be mistaken for a failure.
TERMINAL_SUCCESS = {"completed"}
TERMINAL_FAILURE = {"failed", "cancelled", "canceled"}

ENV_KEYS = ("APIMART_API_KEY",)

INSTALL_INSTRUCTIONS = (
    "Set APIMART_API_KEY to your APIMart API key.\n"
    "  Get one at https://apimart.ai/keys"
)


class ApimartError(RuntimeError):
    """Raised for any APIMart API or transport failure."""


def get_api_key() -> str | None:
    for key in ENV_KEYS:
        value = os.environ.get(key)
        if value:
            return value
    return None


def is_remote(value: str) -> bool:
    return str(value).strip().lower().startswith(("http://", "https://", "asset://"))


def _headers(api_key: str, json_body: bool = True) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {api_key}"}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _body(response: Any, context: str) -> dict[str, Any]:
    """Parse an APIMart response, raising ApimartError on HTTP or envelope errors.

    Errors arrive as {"error": {"message", "type"}}; a non-200 `code` can also
    ride along with HTTP 200, so both are checked.
    """
    status = getattr(response, "status_code", 200)
    text = getattr(response, "text", "")
    try:
        body = response.json()
    except Exception:  # noqa: BLE001 - surface the raw text, not a parse trace
        body = None

    error = body.get("error") if isinstance(body, dict) else None
    if status >= 400 or error:
        message = error.get("message") if isinstance(error, dict) else error
        raise ApimartError(f"{context} failed (HTTP {status}): {message or text[:500]}")
    if not isinstance(body, dict):
        raise ApimartError(f"{context} returned a non-JSON response: {text[:500]}")

    code = body.get("code")
    if code is not None and str(code) != "200":
        raise ApimartError(f"{context} failed (code {code}): {body.get('message') or str(body)[:500]}")
    return body


def submit(endpoint: str, payload: dict[str, Any], api_key: str, timeout: int = 60) -> str:
    """Submit a generation request and return its task id."""
    import requests

    try:
        response = requests.post(endpoint, headers=_headers(api_key), json=payload, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        raise ApimartError(f"Could not reach APIMart at {endpoint}: {exc}") from exc

    data = _body(response, "APIMart submission").get("data")
    item = data[0] if isinstance(data, list) and data else data
    task_id = item.get("task_id") or item.get("id") if isinstance(item, dict) else None
    if not task_id:
        raise ApimartError(f"APIMart did not return a task id: {str(data)[:500]}")
    return str(task_id)


def result_urls(data: dict[str, Any]) -> list[str]:
    """Flatten `result.videos[].url[]` / `result.images[].url[]` into a URL list."""
    result = data.get("result") or {}
    urls: list[str] = []
    for key in ("videos", "images"):
        for item in result.get(key) or []:
            url = item.get("url") if isinstance(item, dict) else item
            urls.extend(url if isinstance(url, list) else [url] if url else [])
    return urls


def poll(
    task_id: str,
    api_key: str,
    interval: float = 5.0,
    timeout: float = 1200.0,
    request_timeout: int = 30,
) -> dict[str, Any]:
    """Poll a task until it terminates. Returns the final `data` object."""
    import requests

    url = f"{TASK_ENDPOINT}/{task_id}"
    elapsed = 0.0
    last_status = "unknown"
    transport_errors = 0

    while elapsed < timeout:
        try:
            response = requests.get(url, headers=_headers(api_key, json_body=False), timeout=request_timeout)
        except Exception as exc:  # noqa: BLE001
            transport_errors += 1
            if transport_errors >= 5:
                raise ApimartError(
                    f"Polling task {task_id} failed after {transport_errors} consecutive transport errors: {exc}"
                ) from exc
            time.sleep(interval)
            elapsed += interval
            continue

        transport_errors = 0
        data = _body(response, f"APIMart poll for {task_id}").get("data") or {}
        last_status = str(data.get("status", "unknown")).lower()

        if last_status in TERMINAL_SUCCESS:
            if not result_urls(data):
                raise ApimartError(f"Task {task_id} completed but returned no output URLs.")
            return data
        if last_status in TERMINAL_FAILURE:
            error = data.get("error") or {}
            message = error.get("message") if isinstance(error, dict) else error
            raise ApimartError(f"APIMart task {task_id} {last_status}: {message or 'no error detail provided'}")

        time.sleep(interval)
        elapsed += interval

    raise ApimartError(
        f"Task {task_id} did not finish within {timeout:.0f}s (last status: {last_status}). "
        f"The job may still complete — check {url}"
    )


def upload_image(file_path: str | Path, api_key: str, timeout: int = 120) -> str:
    """Upload a local image (jpeg/png/webp/gif, ≤20MB) and return its 72h hosted URL."""
    import requests

    path = Path(file_path)
    if not path.exists():
        raise ApimartError(f"Cannot upload — file not found: {path}")

    try:
        with path.open("rb") as handle:
            response = requests.post(
                UPLOAD_IMAGE_ENDPOINT,
                headers=_headers(api_key, json_body=False),
                files={"file": (path.name, handle)},
                timeout=timeout,
            )
    except Exception as exc:  # noqa: BLE001
        raise ApimartError(f"Uploading {path.name} to APIMart failed: {exc}") from exc

    url = _body(response, "APIMart image upload").get("url")
    if not url:
        raise ApimartError(f"APIMart upload returned no URL for {path.name}")
    return str(url)


def hosted_image(value: str, api_key: str) -> str:
    """Return a remote image reference as-is, uploading local paths first."""
    return value if is_remote(value) else upload_image(value, api_key)


def download(url: str, output_path: str | Path, timeout: int = 300) -> Path:
    """Download a generated asset to disk. APIMart output links expire in ~24h."""
    import requests

    try:
        response = requests.get(url, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        raise ApimartError(f"Downloading APIMart output failed: {exc}") from exc

    status = getattr(response, "status_code", 200)
    if status >= 400:
        raise ApimartError(f"APIMart output download failed with HTTP {status}: {getattr(response, 'text', '')[:500]}")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path
