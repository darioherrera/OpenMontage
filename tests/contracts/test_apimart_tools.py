"""Contract, schema, and faked-transport tests for the APIMart gateway tools.

No network access and no API key required (tests/conftest.py blocks sockets).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from tools import apimart_client
from tools.base_tool import BaseTool, ToolStatus, ToolTier
from tools.graphics.apimart_image import IMAGE_MODELS, ApimartImage
from tools.video.apimart_video import VIDEO_MODELS, ApimartVideo

TOOLS = [ApimartImage, ApimartVideo]
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for key in apimart_client.ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


class FakeResponse:
    def __init__(self, payload=None, content=b"", status_code=200):
        self._payload = payload if payload is not None else {}
        self.content = content
        self.status_code = status_code
        self.text = str(self._payload)

    def json(self):
        return self._payload


@pytest.fixture
def fake_requests(monkeypatch):
    calls = {"post": [], "get": []}
    queues = {"post": [], "get": []}

    def record(method):
        def handler(url, **kwargs):
            calls[method].append({"url": url, **kwargs})
            if not queues[method]:
                raise AssertionError(f"Unexpected {method.upper()} to {url}")
            return queues[method].pop(0)
        return handler

    module = types.ModuleType("requests")
    module.post = record("post")
    module.get = record("get")
    monkeypatch.setitem(sys.modules, "requests", module)
    monkeypatch.setenv("APIMART_API_KEY", "test-key")
    monkeypatch.setattr(apimart_client.time, "sleep", lambda _s: None)
    return types.SimpleNamespace(calls=calls, queues=queues)


SUBMITTED = FakeResponse({"code": 200, "data": [{"status": "submitted", "task_id": "task_1"}]})


def completed(kind: str, url: str, cost: float = 0.5) -> FakeResponse:
    return FakeResponse({"code": 200, "data": {
        "id": "task_1", "status": "completed", "cost": cost,
        "result": {kind: [{"url": [url], "expires_at": 1}]},
    }})


# ------------------------------------------------------------------ contract

@pytest.mark.parametrize("cls", TOOLS, ids=lambda cls: cls.name)
class TestContract:
    def test_identity(self, cls):
        tool = cls()
        assert issubclass(cls, BaseTool)
        assert tool.provider == "apimart"
        assert tool.tier == ToolTier.GENERATE
        assert "prompt" in tool.input_schema["required"]
        assert "apimart" in tool.agent_skills
        assert "env:APIMART_API_KEY" in tool.dependencies

    def test_status_follows_key(self, cls, monkeypatch):
        assert cls().get_status() == ToolStatus.UNAVAILABLE
        monkeypatch.setenv("APIMART_API_KEY", "x")
        assert cls().get_status() == ToolStatus.AVAILABLE

    def test_no_key_fails_before_network(self, cls):
        result = cls().execute({"prompt": "p"})
        assert not result.success
        assert "APIMART_API_KEY" in result.error

    def test_catalog_exposed(self, cls):
        assert cls().get_info()["model_catalog"]


def test_skill_exists():
    skill = PROJECT_ROOT / ".agents" / "skills" / "apimart" / "SKILL.md"
    assert "APIMART_API_KEY" in skill.read_text(encoding="utf-8")


def test_registry_discovers_tools(isolated_tool_registry):
    isolated_tool_registry.discover()
    assert isolated_tool_registry.get("apimart_video") is not None
    assert isolated_tool_registry.get("apimart_image") is not None


def test_requested_families_cataloged():
    assert {
        "sora-2", "sora-2-pro", "veo3.1-fast", "veo3.1-quality", "veo3.1-lite", "kling-v3",
        "kling-v3-omni", "seedance-2.0", "seedance-2.5", "gemini-omni-1.1-flash",
    } <= set(VIDEO_MODELS)
    assert {"flux-2-pro", "flux-2-max", "flux-kontext-pro"} <= set(IMAGE_MODELS)


# ------------------------------------------------------------------ video payloads

class TestVideoPayloads:
    build = staticmethod(lambda inputs, model: ApimartVideo()._build_payload(inputs, model))

    def test_sora_image_to_video(self):
        payload = self.build({"prompt": "p", "operation": "image_to_video", "image_url": "https://x/a.png"}, "sora-2")
        assert payload == {
            "model": "sora-2", "prompt": "p", "duration": 8, "aspect_ratio": "16:9",
            "resolution": "720p", "image_urls": ["https://x/a.png"],
        }

    def test_veo_first_last_and_reference_modes(self):
        frames = self.build(
            {"prompt": "p", "operation": "image_to_video", "image_url": "https://x/a.png", "last_image_url": "https://x/b.png"},
            "veo3.1-fast",
        )
        assert frames["image_urls"] == ["https://x/a.png", "https://x/b.png"]
        assert frames["generation_type"] == "frame"
        refs = self.build(
            {"prompt": "p", "operation": "reference_to_video", "reference_images": ["https://x/a.png"]}, "veo3.1-fast"
        )
        assert refs["generation_type"] == "reference"
        with pytest.raises(ValueError, match="at most 0 images"):
            self.build({"prompt": "p", "image_url": "https://x/a.png"}, "veo3.1-lite")

    def test_kling_maps_resolution_to_mode_and_audio(self):
        payload = self.build({"prompt": "p", "resolution": "1080p", "duration": 10, "generate_audio": True}, "kling-v3")
        assert payload["mode"] == "pro"
        assert "resolution" not in payload
        assert payload["audio"] is True

    def test_kling_omni_roles_and_video_edit(self):
        payload = self.build(
            {"prompt": "p", "operation": "video_edit", "video_url": "https://x/v.mp4", "generate_audio": True},
            "kling-v3-omni",
        )
        assert payload["video_list"] == [{"video_url": "https://x/v.mp4", "refer_type": "base"}]
        assert "audio" not in payload  # mutually exclusive with video_list

    def test_seedance_25_first_last_forces_adaptive(self):
        payload = self.build(
            {"prompt": "p", "operation": "image_to_video", "aspect_ratio": "16:9",
             "image_url": "https://x/a.png", "last_image_url": "https://x/b.png"},
            "seedance-2.5",
        )
        assert payload["image_with_roles"] == [
            {"url": "https://x/a.png", "role": "first_frame"},
            {"url": "https://x/b.png", "role": "last_frame"},
        ]
        assert payload["size"] == "adaptive"
        assert "image_urls" not in payload

    def test_seedance_25_edit_and_audio_only(self):
        edit = self.build({"prompt": "remove people", "operation": "video_edit", "video_url": "https://x/v.mp4"}, "seedance-2.5")
        assert edit["video_urls"] == ["https://x/v.mp4"]
        assert edit["duration"] == -1 and edit["omni_reference_task_type"] == "edit"
        audio = self.build({"prompt": "p", "operation": "reference_to_video", "reference_audios": ["https://x/a.mp3"]}, "seedance-2.5")
        assert audio["audio_urls"] == ["https://x/a.mp3"]

    def test_seedance_20_limits(self):
        with pytest.raises(ValueError, match="paired"):
            self.build({"prompt": "p", "operation": "reference_to_video", "reference_audios": ["https://x/a.mp3"]}, "seedance-2.0")
        with pytest.raises(ValueError, match="at most 9"):
            self.build({"prompt": "p", "reference_images": [f"https://x/{i}.png" for i in range(10)]}, "seedance-2.0")
        with pytest.raises(ValueError, match="resolution"):
            self.build({"prompt": "p", "resolution": "4k"}, "seedance-2.0-fast")

    def test_gemini_omni_has_no_duration(self):
        payload = self.build(
            {"prompt": "p", "duration": 10, "resolution": "4k", "image_url": "https://x/a.png", "last_image_url": "https://x/b.png"},
            "gemini-omni-1.1-flash",
        )
        assert "duration" not in payload
        assert payload["first_frame_image"] == "https://x/a.png"
        assert payload["last_frame_image"] == "https://x/b.png"

    def test_invalid_inputs_fail_loudly(self):
        with pytest.raises(ValueError, match="duration"):
            self.build({"prompt": "p", "duration": 20}, "kling-v3")
        with pytest.raises(ValueError, match="operation"):
            self.build({"prompt": "p", "operation": "video_edit"}, "sora-2")
        with pytest.raises(ValueError, match="reference-image mode"):
            self.build({"prompt": "p", "reference_images": ["https://x/a.png"]}, "kling-v3")


# ------------------------------------------------------------------ image payloads

class TestImagePayloads:
    def test_flux2_exact_dimensions(self):
        payload = ApimartImage()._build_payload({"prompt": "p", "width": 1920, "height": 1080}, "flux-2-pro")
        assert (payload["width"], payload["height"]) == (1920, 1080)
        assert "size" not in payload

    def test_flux2_ratio_uses_resolution_tier(self):
        payload = ApimartImage()._build_payload({"prompt": "p", "aspect_ratio": "9:16", "resolution": "4MP"}, "flux-2-max")
        assert payload["size"] == "9:16" and payload["resolution"] == "4MP"

    def test_flux2_over_4mp_rejected(self):
        with pytest.raises(ValueError, match="4MP"):
            ApimartImage()._build_payload({"prompt": "p", "width": 4096, "height": 4096}, "flux-2-pro")

    def test_kontext_snaps_to_ratio_without_dimensions(self):
        payload = ApimartImage()._build_payload({"prompt": "p", "width": 1920, "height": 1080}, "flux-kontext-pro")
        assert payload["size"] == "16:9"
        assert "width" not in payload and "resolution" not in payload

    def test_kontext_reference_cap(self):
        with pytest.raises(ValueError, match="at most 4"):
            ApimartImage()._build_payload(
                {"prompt": "p", "image_urls": [f"https://x/{i}.png" for i in range(5)]}, "flux-kontext-max"
            )


# ------------------------------------------------------------------ faked transport

class TestExecute:
    def test_video_round_trip_reports_actual_cost(self, fake_requests, tmp_path):
        out = tmp_path / "clip.mp4"
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [
            FakeResponse({"code": 200, "data": {"status": "processing"}}),
            completed("videos", "https://cdn.apimart.ai/clip.mp4", cost=1.2),
            FakeResponse(content=b"MP4DATA"),
        ]
        result = ApimartVideo().execute({"prompt": "rocket", "model": "veo3.1-fast", "output_path": str(out)})

        assert result.success is True, result.error
        assert out.read_bytes() == b"MP4DATA"
        assert result.cost_usd == pytest.approx(1.2)
        assert result.data["task_id"] == "task_1"
        submit = fake_requests.calls["post"][0]
        assert submit["url"] == apimart_client.VIDEO_ENDPOINT
        assert submit["headers"]["Authorization"] == "Bearer test-key"
        assert fake_requests.calls["get"][0]["url"].endswith("/tasks/task_1")

    def test_image_edit_uploads_local_file(self, fake_requests, tmp_path):
        source = tmp_path / "src.png"
        source.write_bytes(b"PNG")
        fake_requests.queues["post"] = [FakeResponse({"url": "https://upload.apimart.ai/f/image/src.png"}), SUBMITTED]
        fake_requests.queues["get"] = [completed("images", "https://upload.apimart.ai/f/image/out.png"), FakeResponse(content=b"IMG")]

        result = ApimartImage().execute({
            "prompt": "make it dusk", "model": "flux-kontext-pro", "generation_mode": "edit",
            "image_path": str(source), "output_path": str(tmp_path / "out.png"),
        })

        assert result.success is True, result.error
        upload, submit = fake_requests.calls["post"]
        assert upload["url"] == apimart_client.UPLOAD_IMAGE_ENDPOINT and "files" in upload
        assert submit["json"]["image_urls"] == ["https://upload.apimart.ai/f/image/src.png"]

    def test_local_reference_video_rejected_before_any_call(self, fake_requests, tmp_path):
        result = ApimartVideo().execute({
            "prompt": "p", "model": "seedance-2.5", "operation": "reference_to_video",
            "reference_videos": [str(tmp_path / "ref.mp4")], "image_path": str(tmp_path / "a.png"),
        })
        assert result.success is False
        assert "public URL" in result.error
        assert not fake_requests.calls["post"]

    def test_failed_task_surfaces_message(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [SUBMITTED]
        fake_requests.queues["get"] = [FakeResponse({"code": 200, "data": {
            "status": "failed", "error": {"code": "task_failed", "message": "`steps` must be between 1 and 50"},
        }})]
        result = ApimartImage().execute({"prompt": "p", "output_path": str(tmp_path / "i.png")})
        assert result.success is False
        assert "steps" in result.error

    def test_http_error_envelope(self, fake_requests, tmp_path):
        fake_requests.queues["post"] = [FakeResponse(
            {"error": {"code": 402, "message": "Insufficient balance", "type": "payment_required"}}, status_code=402,
        )]
        result = ApimartVideo().execute({"prompt": "p", "output_path": str(tmp_path / "o.mp4")})
        assert result.success is False
        assert "402" in result.error and "Insufficient balance" in result.error


# ------------------------------------------------------------------ carried over from the Kling/Veo tool

class TestKlingVeoCompat:
    def test_cost_estimate_uses_published_rates(self):
        tool = ApimartVideo()
        assert tool.estimate_cost({"prompt": "x", "duration": 5}) == pytest.approx(0.336)
        assert tool.estimate_cost({"prompt": "x", "duration": 10, "mode": "pro"}) == pytest.approx(0.896)
        assert tool.estimate_cost({"prompt": "x", "duration": 10, "resolution": "1080p"}) == pytest.approx(0.896)
        assert tool.estimate_cost({"prompt": "x", "duration": 10, "mode": "pro", "audio": True}) == pytest.approx(1.12)
        # Veo is fixed at 8 seconds regardless of the duration hint.
        assert tool.estimate_cost({"prompt": "x", "model": "veo3.1-fast", "duration": 5}) == pytest.approx(1.2)
        assert tool.estimate_cost({"prompt": "x", "model": "sora-2", "duration": 8}) == 0.0

    def test_kling_mode_and_audio_aliases(self):
        payload = ApimartVideo()._build_payload({"prompt": "p", "mode": "4k", "audio": True}, "kling-v3")
        assert payload["mode"] == "4k" and payload["audio"] is True

    def test_omni_prompt_referencing_missing_image_is_rejected(self):
        with pytest.raises(ValueError, match="<<<image_2>>>"):
            ApimartVideo()._build_payload(
                {"prompt": "<<<image_2>>> waves", "operation": "reference_to_video",
                 "reference_images": ["https://x/a.png"]},
                "kling-v3-omni",
            )

    def test_base_url_override(self, monkeypatch):
        import importlib

        monkeypatch.setenv("APIMART_BASE_URL", "https://proxy.example.com/")
        try:
            assert importlib.reload(apimart_client).VIDEO_ENDPOINT == "https://proxy.example.com/v1/videos/generations"
        finally:
            monkeypatch.delenv("APIMART_BASE_URL")
            importlib.reload(apimart_client)

    def test_video_selector_can_route_to_apimart(self, monkeypatch):
        from tools.video.video_selector import VideoSelector

        monkeypatch.setenv("APIMART_API_KEY", "sk-test")
        assert "apimart_video" in [tool.name for tool in VideoSelector()._providers()]
