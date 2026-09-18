"""Import the Windows app against isolated settings, without acquiring its mutex."""
import importlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def kara_app(tmp_path_factory):
    if sys.platform != "win32":
        pytest.skip("Kara app integration requires Windows")
    import ctypes

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("LOCALAPPDATA", str(tmp_path_factory.mktemp("kara-settings")))
        patch.setenv("HF_HUB_OFFLINE", "1")
        patch.setattr(ctypes.windll.kernel32, "CreateMutexW", lambda *args: 0)
        patch.setattr(ctypes.windll.kernel32, "GetLastError", lambda: 0)
        app = importlib.import_module("kara")
    yield app


@pytest.fixture
def kara(kara_app, monkeypatch, tmp_path):
    import queue
    from unittest.mock import Mock

    app = kara_app
    monkeypatch.setattr(app, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(app, "app_settings", dict(app.DEFAULT_SETTINGS))
    monkeypatch.setattr(app, "ui_queue", queue.Queue())
    monkeypatch.setattr(app, "trace", Mock())
    monkeypatch.setattr(app, "_CAPTURE_DEMO_PATH", None)
    app.karai18n.set_language("es")
    yield app


@pytest.fixture
def pipeline(kara, monkeypatch):
    """Exercise real _transcribe; only the model and external paste are mocked."""
    from contextlib import nullcontext
    from types import SimpleNamespace
    from unittest.mock import Mock

    kara.trace.span.side_effect = lambda name: nullcontext()
    monkeypatch.setattr(kara, "model_device", "cpu")
    monkeypatch.setattr(kara, "model_threads", 4)
    monkeypatch.setattr(kara, "_clipboard_has_text", lambda: True)
    monkeypatch.setattr(kara.pyperclip, "paste", Mock(return_value="previous clipboard"))
    monkeypatch.setattr(kara.pyperclip, "copy", Mock())
    monkeypatch.setattr(kara.pyautogui, "hotkey", Mock())
    monkeypatch.setattr(kara.time, "sleep", lambda seconds: None)
    model = Mock()
    monkeypatch.setattr(kara, "model_obj", model)

    def run(text, detected="es", duration=4, fail=None):
        model.transcribe.side_effect = fail
        model.transcribe.return_value = (
            iter([SimpleNamespace(text=text)]),
            SimpleNamespace(language=detected, language_probability=0.91),
        )
        # A voiced-level waveform, with the actual preprocessing and text path.
        audio = kara.np.full(int(duration * kara.SAMPLE_RATE), 0.1, dtype="float32")
        kara._transcribe(audio, kara.SAMPLE_RATE)
        events = []
        while not kara.ui_queue.empty():
            events.append(kara.ui_queue.get_nowait())
        return events

    return SimpleNamespace(app=kara, model=model, run=run)
