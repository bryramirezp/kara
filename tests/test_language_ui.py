"""Opt-in real Tk widget checks: set KARA_TEST_UI=1 on an interactive desktop."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("KARA_TEST_UI") != "1",
                                reason="Opt-in Windows UI tests")


def state(segmented):
    # CTk 5.2 supports configure(state=...), but not cget('state') on the
    # container. Verify the actual clickable buttons instead.
    states = {button.cget("state") for button in segmented._buttons_dict.values()}
    assert len(states) == 1
    return states.pop()


def test_settings_widgets_save_reload_and_localize(kara, monkeypatch):
    # No microphone, global listeners, tray, real model or user settings.
    monkeypatch.setattr(kara, "list_input_devices", lambda: [])
    monkeypatch.setattr(kara, "current_mic_name", lambda: "Test microphone")
    monkeypatch.setattr(kara.KaraApp, "_fill_hw_info", lambda self: None)
    monkeypatch.setattr(kara.KaraApp, "_reload_model", lambda self: None)
    windows = []
    try:
        app = kara.KaraApp()
        windows.append(app)
        app.update()
        app._show_settings()
        assert app._lang_var.get() == "Automático"
        assert state(app._numbers_seg) == "disabled"
        assert state(app._commands_seg) == "disabled"
        assert "Automático" not in app._ui_lang_menu.cget("values")

        app._lang_var.set("Spanish")
        app.update()
        assert state(app._numbers_seg) == "normal"
        app._numbers_var.set("words")
        app._commands_var.set("all")
        app._lang_var.set("Automático")
        app._apply_settings()
        assert kara.load_settings()["language"] == "auto"
        assert kara.load_settings()["numbers"] == "words"
        assert kara.load_settings()["commands"] == "all"

        app._on_ui_language_change("English")
        app.update()
        assert app._lang_var.get() == "Automatic"
        assert state(app._numbers_seg) == "disabled"
        assert state(app._commands_seg) == "disabled"
        app._on_theme_change("light")
        app.update()
        assert app._lang_var.get() == "Automatic"

        for ui in kara.LANGUAGE_CODES:
            app._on_ui_language_change(kara.LANGUAGE_NAMES[ui])
            app.update()
            assert app._lang_var.get() == kara.karai18n.STRINGS[ui]["language_auto"]
            assert app._lang_var.get() not in app._ui_lang_menu.cget("values")
            assert state(app._numbers_seg) == "disabled"

        app._lang_var.set("English")
        assert state(app._numbers_seg) == "normal"
        assert app._numbers_var.get() == "words"
        assert app._commands_var.get() == "all"
        app._apply_settings()
        assert kara.load_settings()["language"] == "en"
        # Reload from disk and rebuild the settings widgets in the same Tcl
        # interpreter. Tk image objects cannot cross interpreter lifetimes.
        app._settings = kara.load_settings()
        app._rebuild_ui()
        app.update()
        assert app._lang_var.get() == "English"
        assert app._numbers_var.get() == "words"
        assert app._commands_var.get() == "all"
        assert state(app._numbers_seg) == "normal"
    finally:
        for window in windows:
            window.destroy()
        kara._mark_cache.clear()
        kara.karai18n.set_language("es")


@pytest.mark.parametrize("language", ["auto", "en"])
def test_settings_in_fresh_app_process(kara, language, tmp_path):
    kara.save_settings(dict(kara.DEFAULT_SETTINGS, language=language,
                            ui_language="en", numbers="words", commands="all"))
    env = dict(os.environ, LOCALAPPDATA=str(tmp_path / "appdata"), HF_HUB_OFFLINE="1",
               KARA_TEST_SETTINGS=kara.SETTINGS_FILE, KARA_TEST_LANGUAGE=language)
    code = '''
import ctypes, os
from unittest.mock import patch
with patch.object(ctypes.windll.kernel32, "CreateMutexW", return_value=0), \\
     patch.object(ctypes.windll.kernel32, "GetLastError", return_value=0):
    import kara
kara.SETTINGS_FILE = os.environ["KARA_TEST_SETTINGS"]
kara.karai18n.set_language("en")
kara.list_input_devices = lambda: []
kara.KaraApp._fill_hw_info = lambda self: None
app = kara.KaraApp()
try:
    app.update()
    automatic = os.environ["KARA_TEST_LANGUAGE"] == "auto"
    assert app._lang_var.get() == ("Automatic" if automatic else "English")
    assert app._numbers_var.get() == "words"
    assert app._commands_var.get() == "all"
    assert app._ui_lang_var.get() == "English"
    assert all(b.cget("state") == ("disabled" if automatic else "normal")
               for b in app._numbers_seg._buttons_dict.values())
finally:
    app.destroy()
'''
    result = subprocess.run([sys.executable, "-c", code], env=env,
                            cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stdout + result.stderr
