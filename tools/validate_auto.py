"""Reproducible, local-only audio evaluation; artifacts stay in ignored build/.

Prerequisite (test tooling ONLY, never an app dependency):
  python -m pip install --target build/validation/tts --no-deps piper-tts==1.4.2
  python tools/validate_auto.py --prepare
  python tools/validate_auto.py --device cpu --model small
  python tools/validate_auto.py --device cuda --model large-v3-turbo

--prepare downloads two public Piper voices and synthesizes scripted speech.
Evaluation only uses cached Whisper models. No microphone, clipboard, desktop
input, telemetry upload or changes to the user's Kara settings. Mixed clips
join two synthetic speakers; they do NOT prove natural single-speaker switching.
"""
import argparse
import ctypes
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
import urllib.request
import wave
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "validation"
VOICES = {"es": "es_ES-davefx-medium", "en": "en_US-lessac-medium"}
VOICE_DIRS = {"es": "es/es_ES/davefx/medium", "en": "en/en_US/lessac/medium"}

ES = "¿Puedes revisar el informe? La reunión empieza mañana a las tres. Necesitamos veinte copias para el equipo."
EN = "Can you check the logs? The meeting starts tomorrow at three. We need twenty copies for the team."
ES_LONG = ("Hoy vamos a revisar el informe del proyecto y preparar la reunión de mañana. "
           "El equipo necesita confirmar los resultados antes de enviar el mensaje. "
           "Primero comprobaremos los datos y después hablaremos de los siguientes pasos. "
           "Todavía tenemos tiempo para corregir los errores y escuchar las propuestas. "
           "¿Puedes revisar también las preguntas que llegaron esta mañana?")
EN_LONG = ("Today we will review the project report and prepare for tomorrow's meeting. "
           "The team needs to confirm the results before sending the message. "
           "First we will check the data and then discuss the next steps. "
           "We still have time to correct the errors and listen to the proposals. "
           "Can you also review the questions that arrived this morning?")


def cases():
    return [
        ("es", [("es", ES)], 0),
        ("en", [("en", EN)], 0),
        ("anglicisms", [("es", "Voy a hacer el deploy después del meeting. ¿Puedes revisar el software y el marketing?")], 0),
        ("es_en_pause", [("es", ES), ("en", EN)], 0.5),
        ("en_es_pause", [("en", EN), ("es", ES)], 0.5),
        ("es_en_no_pause", [("es", ES), ("en", EN)], 0),
        ("en_es_no_pause", [("en", EN), ("es", ES)], 0),
        ("es_en_long", [("es", ES_LONG), ("en", EN_LONG)], 0.5),
        ("en_es_long", [("en", EN_LONG), ("es", ES_LONG)], 0.5),
        ("short_es", [("es", "Hola, gracias.")], 0),
        ("short_en", [("en", "Yes, thanks.")], 0),
        ("silence", [], 0),
        ("distinct_es_en", [("es", "¿Dónde está mi teléfono? Lo dejé sobre la mesa de la cocina."),
                            ("en", "Please send the weekly report before Friday. The server needs a restart.")], 0.5),
        ("distinct_en_es", [("en", "Please send the weekly report before Friday. The server needs a restart."),
                            ("es", "¿Dónde está mi teléfono? Lo dejé sobre la mesa de la cocina.")], 0),
        ("deploy_question", [("es", "¿Puedes revisar el deploy?"),
                             ("en", "Can you check the logs?")], 0.2),
        ("late_switch", [("es", ES_LONG + " " +
            "La semana pasada encontramos varios problemas en las pruebas de instalación. "
            "Algunos usuarios no podían abrir la ventana y otros necesitaban cambiar el micrófono. "
            "Ya corregimos esos problemas y ahora estamos evaluando los nuevos idiomas. "
            "Es importante conservar las preferencias y comprobar que los números se escriban bien. "
            "Cuando terminemos las pruebas vamos a preparar el instalador y actualizar la documentación."),
            ("en", "Please send the weekly report before Friday. The server needs a restart. "
             "Our customers are waiting for the update. We should test the backup before we begin. "
             "Where did you put the latest log files? I need them to investigate the error.")], 0.5),
    ]


def prepare():
    import numpy as np

    sys.path.insert(0, str(OUT / "tts"))
    from piper import PiperVoice

    voices = {}
    voice_meta = {}
    for lang, name in VOICES.items():
        for suffix in (".onnx", ".onnx.json"):
            dest = OUT / (name + suffix)
            if not dest.exists():
                url = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/"
                       + VOICE_DIRS[lang] + "/" + name + suffix)
                print("Downloading", dest.name, flush=True)
                urllib.request.urlretrieve(url, dest)
        path = OUT / (name + ".onnx")
        voices[lang] = PiperVoice.load(str(path))
        voice_meta[lang] = {"name": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    previous = (json.loads((OUT / "corpus.json").read_text(encoding="utf-8"))
                if (OUT / "corpus.json").exists() else {"cases": []})
    existing = {c["name"]: c for c in previous["cases"]}
    manifest = {"source": "Piper 1.4.2 synthetic speech; two speakers for mixed clips",
                "voices": voice_meta, "cases": []}
    for name, parts, pause in cases():
        if name in existing and (OUT / (name + ".wav")).exists():
            manifest["cases"].append(existing[name])
            continue
        audio_parts = []
        part_rate = None
        for lang, text in parts:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wav:
                voices[lang].synthesize_wav(text, wav)
            buf.seek(0)
            with wave.open(buf, "rb") as wav:
                sr = wav.getframerate()
                audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").copy()
            if part_rate is not None and sr != part_rate:
                raise ValueError("Corpus voices must have the same sample rate")
            part_rate = sr
            if audio_parts:
                audio_parts.append(np.zeros(int(pause * sr), dtype="int16"))
            # Remove only digital trailing/leading silence for no-pause cases.
            if pause == 0 and len(parts) > 1:
                audible = np.flatnonzero(np.abs(audio.astype("int32")) > 100)
                if len(audible):
                    audio = audio[max(0, audible[0] - int(sr * .02)):audible[-1] + int(sr * .02)]
            audio_parts.append(audio)
        if not parts:
            sr = 22050
            audio_parts = [np.zeros(sr * 3, dtype="int16")]
        audio = np.concatenate(audio_parts)
        dest = OUT / (name + ".wav")
        with wave.open(str(dest), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sr)
            wav.writeframes(audio.tobytes())
        manifest["cases"].append({"name": name, "expected": " ".join(t for _, t in parts),
                                  "seconds": round(len(audio) / sr, 2),
                                  "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()})
    (OUT / "corpus.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Corpus prepared:", [(c["name"], c["seconds"]) for c in manifest["cases"]], flush=True)


def normalized_words(text):
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"\w+", text)


def word_errors(reference, hypothesis):
    # Lexical WER only: punctuation/case/accents ignored, number spellings NOT
    # normalized ("twenty" -> "20" counts as one edit). Inspect punctuation and
    # semantic errors in the stored transcripts rather than this metric alone.
    a, b = normalized_words(reference), normalized_words(hypothesis)
    prev = list(range(len(b) + 1))
    for i, word in enumerate(a, 1):
        cur = [i]
        for j, other in enumerate(b, 1):
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j-1] + (word != other)))
        prev = cur
    return {"word_edits": prev[-1], "reference_words": len(a),
            "wer": round(prev[-1] / max(1, len(a)), 3)}


def load_app():
    sys.path.insert(0, str(ROOT))
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["LOCALAPPDATA"] = str(OUT / "appdata")
    with patch.object(ctypes.windll.kernel32, "CreateMutexW", return_value=0), \
         patch.object(ctypes.windll.kernel32, "GetLastError", return_value=0):
        import kara
    return kara


def evaluate(args):
    import numpy as np
    kara = load_app()
    model = kara.WhisperModel(args.model, device=args.device,
                             compute_type="int8" if args.device == "cpu" else "float16",
                             cpu_threads=kara.cpu_thread_count(), local_files_only=True)
    kara.model_obj = model
    kara.model_device = args.device
    kara.model_threads = kara.cpu_thread_count()
    corpus = json.loads((OUT / "corpus.json").read_text(encoding="utf-8"))
    report = {"device": args.device, "model": args.model,
              "versions": {p: importlib.metadata.version(p) for p in ("faster-whisper", "ctranslate2", "numpy")},
              "corpus_source": corpus["source"], "results": []}
    # Warm up both inference/VAD paths; excluded from timings.
    from faster_whisper.audio import decode_audio
    warm = decode_audio(str(OUT / "es.wav"))
    list(model.transcribe(warm, language="es", vad_filter=True, beam_size=1)[0])
    suffix = "-extra" if args.case else ""
    if args.no_vad:
        suffix += "-no-vad"
    dest = OUT / f"audio-{args.device}-{args.model}{suffix}.json"
    for case in corpus["cases"]:
        if args.case and case["name"] not in args.case:
            continue
        audio = decode_audio(str(OUT / (case["name"] + ".wav")))
        for mode in ("initial", "multilingual"):
            kara.app_settings = dict(kara.DEFAULT_SETTINGS, language="auto")
            captured = []
            detected = {}
            real_transcribe = model.transcribe

            def transcribe(*a, **kw):
                kw["multilingual"] = mode == "multilingual"
                if args.no_vad:
                    kw["vad_filter"] = False
                segments, info = real_transcribe(*a, **kw)
                detected.update(initial_lang=info.language,
                                duration_after_vad=info.duration_after_vad)
                return segments, info

            # Run Kara's real preprocessing, inference, cleanup and queue path.
            # Only replace the external clipboard/keyboard side effects.
            with patch.object(model, "transcribe", side_effect=transcribe), \
                 patch.object(kara, "_clipboard_has_text", return_value=False), \
                 patch.object(kara.pyperclip, "copy", side_effect=captured.append), \
                 patch.object(kara.pyautogui, "hotkey"), \
                 patch.object(kara.time, "sleep"):
                kara.trace.start()
                start = time.perf_counter()
                kara._transcribe(np.array(audio, copy=True), 16000)
                elapsed = time.perf_counter() - start
            events = []
            while not kara.ui_queue.empty():
                events.append(kara.ui_queue.get_nowait())
            text = captured[0] if captured else ""
            row = {"case": case["name"], "mode": mode, "audio_s": case["seconds"],
                   "elapsed_s": round(elapsed, 3), "expected": case["expected"], "text": text,
                   "errors": [e[1] for e in events if e[0] == "log" and e[-1] == "error"],
                   **detected,
                   **word_errors(case["expected"], text)}
            report["results"].append(row)
            dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(row, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--model", default="small")
    parser.add_argument("--case", action="append")
    parser.add_argument("--no-vad", action="store_true", help="Diagnostic only; disable VAD")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    prepare() if args.prepare else evaluate(args)
