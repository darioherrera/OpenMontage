"""Contract coverage for the APIMart unified video gateway provider.

These tests inject a fake ``requests`` module so no network call is ever made
(the session-wide socket guard would block it anyway).
"""

from __future__ import annotations

import json
import sys
import types

import pytest

from tools.base_tool import ToolStatus


class _FakeResponse:
    def __init__(self, json_data=None, content=b"", ok=True, status_code=200):
        self._json = json_data
        self.content = content
        self.ok = ok
        self.status_code = status_code
        self.text = json.dumps(json_data) if json_data is not None else ""

    def json(self):
        return self._json

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


def _install_fake_requests(monkeypatch, post_responses, get_responses):
    calls = {"post": [], "get": []}
    fake = types.ModuleType("requests")

    def fake_post(url, headers=None, json=None, files=None, timeout=None, params=None, data=None):
        calls["post"].append({"url": url, "headers": headers, "json": json, "files": files})
        return post_responses.pop(0)

    def fake_get(url, headers=None, timeout=None, params=None):
        calls["get"].append({"url": url, "headers": headers, "params": params})
        return get_responses.pop(0)

    fake.post = fake_post
    fake.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake)
    return calls


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    monkeypatch.delenv("APIMART_API_KEY", raising=False)
    monkeypatch.delenv("APIMART_BASE_URL", raising=False)


def _submit_ok(task_id="task_01TEST"):
    return _FakeResponse({"code": 200, "data": [{"status": "submitted", "task_id": task_id}]})


def _task(status, task_id="task_01TEST", url="https://upload.apimart.ai/f/video/clip.mp4", cost=None, error=None):
    data = {"id": task_id, "status": status, "progress": 100 if status == "completed" else 40}
    if status == "completed":
        data["result"] = {"videos": [{"url": [url], "expires_at": 1}]}
    if cost is not None:
        data["cost"] = cost
    if error:
        data["error"] = error
    return _FakeResponse({"code": 200, "data": data})


def test_apimart_video_is_discovered_as_video_provider():
    from tools.tool_registry import ToolRegistry
    from tools.video.apimart_video import DEFAULT_MODEL, MODELS

    registry = ToolRegistry()
    registry.discover()
    tool = registry.get("apimart_video")
    assert tool is not None
    assert tool.provider == "apimart"
    assert tool.capability == "video_generation"
    assert tool.dependencies == ["env:APIMART_API_KEY"]
    assert "apimart-video" in tool.agent_skills
    assert DEFAULT_MODEL == "kling-v3"
    assert MODELS == ["kling-v3", "kling-v3-omni", "veo3.1-fast", "veo3.1-quality", "veo3.1-lite"]
    assert tool.supports["image_to_video"] is True
    assert tool.supports["reference_to_video"] is True


def test_apimart_video_unavailable_without_key(monkeypatch):
    from tools.video.apimart_video import ApimartVideo

    assert ApimartVideo().get_status() == ToolStatus.UNAVAILABLE
    monkeypatch.setenv("APIMART_API_KEY", "sk-test")
    assert ApimartVideo().get_status() == ToolStatus.AVAILABLE


def test_execute_without_key_fails_without_network(tmp_path):
    from tools.video.apimart_video import ApimartVideo

    result = ApimartVideo().execute({"prompt": "never sent", "output_path": str(tmp_path / "x.mp4")})
    assert result.success is False
    assert "APIMART_API_KEY" in result.error
    assert result.cost_usd == 0.0


def test_cost_estimate_uses_published_kling_rates():
    from tools.video.apimart_video import ApimartVideo

    tool = ApimartVideo()
    assert tool.estimate_cost({"prompt": "x", "duration": 5}) == pytest.approx(0.336)
    assert tool.estimate_cost({"prompt": "x", "duration": 10, "mode": "pro"}) == pytest.approx(0.896)
    assert tool.estimate_cost({"prompt": "x", "duration": 10, "resolution": "1080p"}) == pytest.approx(0.896)
    assert tool.estimate_cost({"prompt": "x", "duration": 10, "mode": "pro", "audio": True}) == pytest.approx(1.12)
    # Veo is fixed at 8 seconds regardless of the duration hint
    assert tool.estimate_cost({"prompt": "x", "model": "veo3.1-fast", "duration": 5}) == pytest.approx(1.2)


def test_kling_text_to_video_round_trip(monkeypatch, tmp_path):
    from tools.video.apimart_video import ApimartVideo

    monkeypatch.setenv("APIMART_API_KEY", "sk-test")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[_submit_ok()],
        get_responses=[_task("processing"), _task("completed", cost=0.4), _FakeResponse(content=b"MP4DATA")],
    )
    out = tmp_path / "clip.mp4"
    result = ApimartVideo().execute({
        "prompt": "A yellow Mustang on a desert highway at golden hour",
        "duration": 6,
        "mode": "pro",
        "aspect_ratio": "16:9",
        "poll_interval_seconds": 0.01,
        "output_path": str(out),
    })
    assert result.success is True, result.error
    assert out.read_bytes() == b"MP4DATA"
    assert result.cost_usd == pytest.approx(0.4)
    assert result.data["cost_source"] == "provider"
    assert result.data["task_id"] == "task_01TEST"

    submit = calls["post"][0]
    assert submit["url"] == "https://api.apimart.ai/v1/videos/generations"
    assert submit["headers"]["Authorization"] == "Bearer sk-test"
    assert submit["json"] == {
        "model": "kling-v3",
        "prompt": "A yellow Mustang on a desert highway at golden hour",
        "aspect_ratio": "16:9",
        "duration": 6,
        "mode": "pro",
    }
    assert calls["get"][0]["url"] == "https://api.apimart.ai/v1/tasks/task_01TEST"
    assert calls["get"][-1]["url"] == "https://upload.apimart.ai/f/video/clip.mp4"


def test_local_reference_is_uploaded_and_bound_for_omni(monkeypatch, tmp_path):
    from tools.video.apimart_video import ApimartVideo

    monkeypatch.setenv("APIMART_API_KEY", "sk-test")
    ref = tmp_path / "mustang.png"
    ref.write_bytes(b"PNG")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[
            _FakeResponse({"url": "https://upload.apimart.ai/f/image/mustang.png"}),
            _submit_ok(),
        ],
        get_responses=[_task("completed"), _FakeResponse(content=b"MP4")],
    )
    result = ApimartVideo().execute({
        "prompt": "The car in <<<image_1>>> drives along the coast",
        "model": "kling-v3-omni",
        "operation": "reference_to_video",
        "reference_image_paths": [str(ref)],
        "duration": 5,
        "poll_interval_seconds": 0.01,
        "output_path": str(tmp_path / "out.mp4"),
    })
    assert result.success is True, result.error
    upload, submit = calls["post"]
    assert upload["url"] == "https://api.apimart.ai/v1/uploads/images"
    assert "file" in upload["files"]
    assert submit["json"]["image_urls"] == ["https://upload.apimart.ai/f/image/mustang.png"]
    assert submit["json"]["model"] == "kling-v3-omni"
    assert result.data["uploaded_reference_urls"] == ["https://upload.apimart.ai/f/image/mustang.png"]


def test_omni_prompt_referencing_missing_image_is_rejected(monkeypatch, tmp_path):
    from tools.video.apimart_video import ApimartVideo

    monkeypatch.setenv("APIMART_API_KEY", "sk-test")
    _install_fake_requests(monkeypatch, post_responses=[], get_responses=[])
    result = ApimartVideo().execute({
        "prompt": "<<<image_2>>> waves",
        "model": "kling-v3-omni",
        "reference_image_urls": ["https://example.com/a.png"],
        "output_path": str(tmp_path / "out.mp4"),
    })
    assert result.success is False
    assert "<<<image_2>>>" in result.error


def test_multi_shot_payload_and_duration_validation(monkeypatch, tmp_path):
    from tools.video.apimart_video import ApimartVideo

    monkeypatch.setenv("APIMART_API_KEY", "sk-test")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[_submit_ok()],
        get_responses=[_task("completed"), _FakeResponse(content=b"MP4")],
    )
    shots = [{"prompt": "inspector", "duration": 3}, {"prompt": "crane", "duration": 3}, {"prompt": "mechanic", "duration": 4}]
    result = ApimartVideo().execute({
        "prompt": "Three beats",
        "duration": 10,
        "multi_shot": shots,
        "poll_interval_seconds": 0.01,
        "output_path": str(tmp_path / "out.mp4"),
    })
    assert result.success is True, result.error
    body = calls["post"][0]["json"]
    assert body["multi_shot"] is True
    assert body["shot_type"] == "customize"
    assert [s["index"] for s in body["multi_prompt"]] == [1, 2, 3]

    bad = ApimartVideo().execute({"prompt": "x", "duration": 10, "multi_shot": shots[:2], "output_path": str(tmp_path / "bad.mp4")})
    assert bad.success is False
    assert "sum to 6s" in bad.error


def test_veo_payload_forces_8s_and_reference_mode(monkeypatch, tmp_path):
    from tools.video.apimart_video import ApimartVideo

    monkeypatch.setenv("APIMART_API_KEY", "sk-test")
    calls = _install_fake_requests(
        monkeypatch,
        post_responses=[_submit_ok()],
        get_responses=[_task("completed"), _FakeResponse(content=b"MP4")],
    )
    result = ApimartVideo().execute({
        "prompt": "Dolphins",
        "model": "veo3.1-fast",
        "operation": "reference_to_video",
        "reference_image_urls": ["https://example.com/a.png"],
        "resolution": "1080p",
        "duration": 5,
        "poll_interval_seconds": 0.01,
        "output_path": str(tmp_path / "out.mp4"),
    })
    assert result.success is True, result.error
    body = calls["post"][0]["json"]
    assert body["duration"] == 8
    assert body["resolution"] == "1080p"
    assert body["generation_type"] == "reference"
    assert "mode" not in body


def test_failed_task_surfaces_provider_message(monkeypatch, tmp_path):
    from tools.video.apimart_video import ApimartVideo

    monkeypatch.setenv("APIMART_API_KEY", "sk-test")
    _install_fake_requests(
        monkeypatch,
        post_responses=[_submit_ok()],
        get_responses=[_task("failed", error={"code": 500, "message": "content policy"})],
    )
    result = ApimartVideo().execute({"prompt": "x", "poll_interval_seconds": 0.01, "output_path": str(tmp_path / "o.mp4")})
    assert result.success is False
    assert "content policy" in result.error


def test_api_error_envelope_is_reported(monkeypatch, tmp_path):
    from tools.video.apimart_video import ApimartVideo

    monkeypatch.setenv("APIMART_API_KEY", "sk-test")
    _install_fake_requests(
        monkeypatch,
        post_responses=[_FakeResponse({"error": {"code": 402, "message": "Insufficient balance", "type": "payment_required"}})],
        get_responses=[],
    )
    result = ApimartVideo().execute({"prompt": "x", "output_path": str(tmp_path / "o.mp4")})
    assert result.success is False
    assert "402" in result.error and "Insufficient balance" in result.error


def test_video_selector_can_route_to_apimart(monkeypatch):
    from tools.video.video_selector import VideoSelector

    monkeypatch.setenv("APIMART_API_KEY", "sk-test")
    selector = VideoSelector()
    names = [t.name for t in selector._providers()]
    assert "apimart_video" in names
