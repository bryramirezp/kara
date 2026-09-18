"""Automatic dictation: compatibility, mixed text, errors and paste integration."""
import json

import pytest

import karai18n


def test_new_settings_and_installer_seed(kara):
    assert kara.load_settings()["language"] == "auto"
    for ui in kara.LANGUAGE_CODES:
        with open(kara.SETTINGS_FILE, "w") as f:
            json.dump({"ui_language": ui}, f)
        settings = kara.load_settings()
        assert settings["language"] == "auto"
        assert settings["ui_language"] == ui


@pytest.mark.parametrize("language", ["auto", "es", "en", "pt", "fr", "de", "it"])
def test_language_and_text_preferences_round_trip(kara, language):
    settings = dict(kara.DEFAULT_SETTINGS, language=language, numbers="words", commands="all")
    kara.save_settings(settings)
    loaded = kara.load_settings()
    assert loaded["language"] == language
    assert (loaded["numbers"], loaded["commands"]) == ("words", "all")


@pytest.mark.parametrize("language", [None, "unknown", "", "AUTO"])
def test_invalid_dictation_setting_defaults_to_auto(kara, language):
    assert kara._migrate(dict(kara.DEFAULT_SETTINGS, language=language))["language"] == "auto"


@pytest.mark.parametrize("ui", [None, "auto", "unknown"])
def test_automatic_never_becomes_ui_language(kara, ui):
    settings = kara._migrate(dict(kara.DEFAULT_SETTINGS, language="auto", ui_language=ui))
    assert settings["ui_language"] == "es"
    settings = kara._migrate(dict(kara.DEFAULT_SETTINGS, language="en", ui_language=ui))
    assert settings["ui_language"] == "en"
    assert "auto" not in kara.LANGUAGE_CODES


def test_all_ui_languages_have_translated_auto_and_help(kara):
    keys = set(karai18n.STRINGS["en"])
    for ui, strings in karai18n.STRINGS.items():
        assert set(strings) == keys
        karai18n.set_language(ui)
        label = kara.language_name("auto")
        assert label == strings["language_auto"]
        assert kara.language_code(label) == "auto"
        assert strings["hint_text_auto"]
    karai18n.set_language("es")


def test_auto_redetects_each_recording_without_changing_settings(pipeline):
    p = pipeline
    for detected in ("es", "en", "es"):
        events = p.run("A test sentence.", detected)
        opts = p.model.transcribe.call_args.kwargs
        assert opts["language"] is None
        assert opts["multilingual"] is True
        assert opts["task"] == "transcribe"
        assert opts["initial_prompt"] is None
        assert opts["vad_filter"] is True
        assert opts["beam_size"] == 1
        assert p.app.app_settings["language"] == "auto"
        p.app.trace.set.assert_any_call(initial_lang=detected, initial_lang_probability=0.91)
        assert ("log", "A test sentence.", "said") in events


@pytest.mark.parametrize("text", [
    "¿Puedes revisar el deploy? Can you check the logs?",
    "Puedes revisar el deploy? Can you check the logs?",
    "Te debo veinte pesos. Send me twenty dollars.",
    "Nueva línea, new paragraph. Ese es el punto de partida.",
    "¡Funciona! It works!",
])
def test_auto_preserves_mixed_punctuation_numbers_and_command_words(pipeline, text):
    pipeline.app.app_settings.update(numbers="digits", commands="all")
    events = pipeline.run(text)
    assert ("log", text, "said") in events
    assert pipeline.app.pyperclip.copy.call_args_list[0].args == (text,)
    assert pipeline.app.pyperclip.copy.call_args_list[-1].args == ("previous clipboard",)
    pipeline.app.pyautogui.hotkey.assert_called_once_with("ctrl", "v")


@pytest.mark.parametrize("language,said,expected", [
    ("es", "cómo estás?", "¿Cómo estás?"),
    ("es", "te debo veinte pesos punto y aparte listo", "Te debo 20 pesos\n\nListo"),
    ("en", "twenty dollars new paragraph ready", "20 dollars\n\nReady"),
])
def test_fixed_language_retains_prompt_and_polish(pipeline, language, said, expected):
    pipeline.app.app_settings["language"] = language
    events = pipeline.run(said, language)
    opts = pipeline.model.transcribe.call_args.kwargs
    assert opts["language"] == language
    assert opts["multilingual"] is False
    assert opts["initial_prompt"] == pipeline.app.karatext.style_prompt(language)
    assert ("log", expected, "said") in events


def test_fixed_short_clip_has_no_prompt(pipeline):
    pipeline.app.app_settings["language"] = "es"
    pipeline.run("hola", duration=1)
    assert pipeline.model.transcribe.call_args.kwargs["initial_prompt"] is None


def test_silence_and_empty_results_do_not_paste(pipeline):
    p = pipeline
    p.app._transcribe(p.app.np.zeros(p.app.SAMPLE_RATE, dtype="float32"), p.app.SAMPLE_RATE)
    p.model.transcribe.assert_not_called()
    p.run("")
    p.app.pyperclip.copy.assert_not_called()
    p.app.pyautogui.hotkey.assert_not_called()


def test_model_error_releases_lock_and_next_dictation_works(pipeline):
    p = pipeline
    events = p.run("", fail=RuntimeError("test model failure"))
    assert any(event[0] == "log" and event[-1] == "error" for event in events)
    p.app.pyperclip.copy.assert_not_called()
    assert not p.app.model_lock.locked()
    assert ("log", "Recovered.", "said") in p.run("Recovered.", "en")


def test_generator_error_releases_lock_without_pasting(pipeline):
    def broken_segments():
        raise RuntimeError("decode failure")
        yield

    from types import SimpleNamespace
    p = pipeline
    p.model.transcribe.return_value = (broken_segments(), SimpleNamespace(language="es"))
    p.app._transcribe(p.app.np.ones(p.app.SAMPLE_RATE, dtype="float32"), p.app.SAMPLE_RATE)
    assert not p.app.model_lock.locked()
    p.app.pyautogui.hotkey.assert_not_called()


def test_settings_change_during_decode_does_not_reformat_current_dictation(pipeline):
    from types import SimpleNamespace
    p = pipeline
    p.app.app_settings.update(language="es", numbers="words", commands="off")

    def segments():
        p.app.app_settings.update(language="auto", numbers="digits", commands="all")
        yield SimpleNamespace(text="veinte pesos punto y aparte listo")

    p.model.transcribe.return_value = (segments(), SimpleNamespace(language="es"))
    p.app._transcribe(p.app.np.ones(4 * p.app.SAMPLE_RATE, dtype="float32"), p.app.SAMPLE_RATE)
    assert p.app.pyperclip.copy.call_args_list[0].args == ("Veinte pesos punto y aparte listo",)


def test_resampling_and_gpu_beam_are_preserved(pipeline, monkeypatch):
    from types import SimpleNamespace
    p = pipeline
    monkeypatch.setattr(p.app, "model_device", "cuda")
    p.model.transcribe.return_value = (
        iter([SimpleNamespace(text="Ready.")]),
        SimpleNamespace(language="en", language_probability=0.99),
    )
    p.app._transcribe(p.app.np.ones(48000, dtype="float32") * .1, 48000)
    assert len(p.model.transcribe.call_args.args[0]) == p.app.SAMPLE_RATE
    assert p.model.transcribe.call_args.kwargs["beam_size"] == 5
    assert p.model.transcribe.call_args.kwargs["language"] is None


def test_diagnostics_record_initial_language_without_transcript(pipeline, monkeypatch, tmp_path):
    p = pipeline
    monkeypatch.setattr(p.app, "TRACE_FILE", str(tmp_path / "trace.jsonl"))
    monkeypatch.setattr(p.app, "trace", p.app._Trace())
    p.app.trace.start()
    p.run("Private test words. Palabras de prueba.", "en")
    with open(p.app.TRACE_FILE, encoding="utf-8") as f:
        serialized = f.read()
    row = json.loads(serialized)
    assert row["lang"] == "auto"
    assert row["initial_lang"] == "en"
    assert row["initial_lang_probability"] == .91
    assert "Private" not in serialized and "Palabras" not in serialized
