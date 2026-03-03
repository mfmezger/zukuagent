import pytest

import zukuagent.services.audio_service as audio_module
from zukuagent.services.audio_service import ParakeetTranscriptionService


def test_constructor_requires_onnx_asr(monkeypatch):
    monkeypatch.setattr(audio_module, "onnx_asr", None)

    with pytest.raises(RuntimeError, match="onnx_asr"):
        ParakeetTranscriptionService()


def test_constructor_loads_model(monkeypatch):
    class _FakeModel:
        def recognize(self, _path: str) -> str:
            return "ok"

    class _FakeOnnxAsr:
        def __init__(self) -> None:
            self.loaded_model_name = None

        def load_model(self, model_name: str):
            self.loaded_model_name = model_name
            return _FakeModel()

    fake_onnx = _FakeOnnxAsr()
    monkeypatch.setattr(audio_module, "onnx_asr", fake_onnx)

    service = ParakeetTranscriptionService(model_name="demo-model")

    assert fake_onnx.loaded_model_name == "demo-model"
    assert service.model_name == "demo-model"


def test_transcribe_missing_file(monkeypatch, tmp_path):
    class _FakeModel:
        def recognize(self, _path: str) -> str:
            return "ok"

    class _FakeOnnxAsr:
        def load_model(self, _model_name: str):
            return _FakeModel()

    monkeypatch.setattr(audio_module, "onnx_asr", _FakeOnnxAsr())
    service = ParakeetTranscriptionService(model_name="demo-model")

    with pytest.raises(FileNotFoundError, match="Audio file not found"):
        service.transcribe(str(tmp_path / "missing.wav"))


def test_transcribe_returns_text(monkeypatch, tmp_path):
    class _FakeModel:
        def recognize(self, _path: str) -> str:
            return "transcribed text"

    class _FakeOnnxAsr:
        def load_model(self, _model_name: str):
            return _FakeModel()

    monkeypatch.setattr(audio_module, "onnx_asr", _FakeOnnxAsr())
    service = ParakeetTranscriptionService(model_name="demo-model")

    audio_file = tmp_path / "audio.wav"
    audio_file.write_text("binary", encoding="utf-8")

    assert service.transcribe(str(audio_file)) == "transcribed text"


def test_transcribe_returns_empty_string_when_no_result(monkeypatch, tmp_path):
    class _FakeModel:
        def recognize(self, _path: str) -> str:
            return ""

    class _FakeOnnxAsr:
        def load_model(self, _model_name: str):
            return _FakeModel()

    monkeypatch.setattr(audio_module, "onnx_asr", _FakeOnnxAsr())
    service = ParakeetTranscriptionService(model_name="demo-model")

    audio_file = tmp_path / "audio.wav"
    audio_file.write_text("binary", encoding="utf-8")

    assert service.transcribe(str(audio_file)) == ""
