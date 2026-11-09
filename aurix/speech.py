"""Local Brazilian Portuguese speech synthesis for AURIX.

Piper Plus runs on the CPU and keeps the voice model on the user's machine.
The voice is downloaded on first use and verified before it is loaded.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
import wave
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

from aurix.config import APP_DATA_DIR

_LOGGER = logging.getLogger(__name__)

VOICE_REVISION = "4ddc3e5fe132918785d98c0c8c7d6ca295c0034c"
VOICE_BASE_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/"
    + VOICE_REVISION
    + "/pt/pt_BR/faber/medium"
)
MODEL_FILENAME = "pt_BR-faber-medium.onnx"
CONFIG_FILENAME = MODEL_FILENAME + ".json"
MODEL_SHA256 = "858555e3a064209c57088fe6bd70c4c3dc54d03eaa00c45d5ecaf43a33f95aa7"
MODEL_MAX_BYTES = 80 * 1024 * 1024
CONFIG_MAX_BYTES = 32 * 1024

_voice_lock = threading.RLock()
_voice_instance = None


def normalize_speech_text(text: str, limit: int = 1200) -> str:
    """Normalize whitespace and bound the amount of text sent to the TTS engine."""
    normalized = " ".join(str(text or "").split())
    return normalized[: max(0, int(limit))]


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest without loading the file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_valid_voice_config(path: Path) -> bool:
    """Check the small Piper config before handing it to the inference runtime."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False
        audio = data.get("audio") or {}
        phonemes = data.get("phoneme_id_map") or {}
        language = data.get("language") or {}
        return (
            int(audio.get("sample_rate", 0)) == 22050
            and isinstance(phonemes, dict)
            and bool(phonemes)
            and language.get("code") == "pt_BR"
        )
    except (OSError, ValueError, TypeError):
        return False


def _download_file(
    url: str,
    destination: Path,
    *,
    max_bytes: int,
    expected_sha256: str | None = None,
) -> None:
    """Download to a temporary file and atomically publish only verified bytes."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    digest = hashlib.sha256()
    downloaded = 0
    request = Request(
        url,
        headers={
            "User-Agent": "AURIX-AI/0.4.0",
            "Accept": "application/octet-stream",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) > max_bytes:
                raise RuntimeError("O arquivo da voz excede o limite de tamanho permitido.")
            with temporary.open("wb") as output:
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        raise RuntimeError("O download da voz excedeu o limite de tamanho permitido.")
                    digest.update(chunk)
                    output.write(chunk)

        if downloaded == 0:
            raise RuntimeError("O servidor retornou um arquivo de voz vazio.")
        if expected_sha256 and digest.hexdigest().casefold() != expected_sha256.casefold():
            raise RuntimeError("A verificação SHA-256 do modelo de voz falhou.")
        os.replace(temporary, destination)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            _LOGGER.debug("Não foi possível remover o arquivo temporário %s", temporary)


def _voice_paths() -> tuple[Path, Path]:
    directory = APP_DATA_DIR / "models" / "piper"
    return directory / MODEL_FILENAME, directory / CONFIG_FILENAME


def _ensure_voice_files(status_callback: Callable[[str], None] | None = None) -> tuple[Path, Path]:
    model_path, config_path = _voice_paths()
    model_path.parent.mkdir(parents=True, exist_ok=True)

    if model_path.is_file():
        try:
            if sha256_file(model_path).casefold() != MODEL_SHA256:
                model_path.unlink(missing_ok=True)
        except OSError:
            model_path.unlink(missing_ok=True)

    if not model_path.is_file():
        if status_callback:
            status_callback("Baixando voz neural pt-BR pela primeira vez (~64 MB)…")
        _download_file(
            f"{VOICE_BASE_URL}/{MODEL_FILENAME}",
            model_path,
            max_bytes=MODEL_MAX_BYTES,
            expected_sha256=MODEL_SHA256,
        )

    if not is_valid_voice_config(config_path):
        config_path.unlink(missing_ok=True)
        _download_file(
            f"{VOICE_BASE_URL}/{CONFIG_FILENAME}",
            config_path,
            max_bytes=CONFIG_MAX_BYTES,
        )
    if not is_valid_voice_config(config_path):
        raise RuntimeError("O arquivo de configuração da voz Piper está inválido.")

    return model_path, config_path


def _load_voice(status_callback: Callable[[str], None] | None = None):
    global _voice_instance
    if _voice_instance is not None:
        return _voice_instance

    model_path, config_path = _ensure_voice_files(status_callback)
    from piper_plus import PiperVoice

    _voice_instance = PiperVoice.load(str(model_path), config_path=str(config_path))
    return _voice_instance


def _play_wav(path: Path) -> None:
    """Play a synthesized WAV without requiring a cloud service or extra codec."""
    if os.name == "nt":
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME)
        return

    import numpy as np
    import sounddevice as sd

    with wave.open(str(path), "rb") as audio_file:
        channels = audio_file.getnchannels()
        sample_width = audio_file.getsampwidth()
        sample_rate = audio_file.getframerate()
        frame_count = audio_file.getnframes()
        raw_audio = audio_file.readframes(frame_count)

    if sample_width != 2:
        raise RuntimeError("A voz local retornou um formato de áudio não suportado.")
    samples = np.frombuffer(raw_audio, dtype=np.int16)
    if channels > 1:
        samples = samples.reshape(-1, channels)
    sd.play(samples, samplerate=sample_rate, blocking=True)


def _speak_with_system_voice(text: str) -> None:
    """Fallback local using a voice installed in Windows (or the host OS)."""
    import pyttsx3

    engine = pyttsx3.init()
    try:
        engine.setProperty("rate", 178)
        for voice in engine.getProperty("voices"):
            name = str(getattr(voice, "name", "") or "").casefold()
            languages = " ".join(str(item) for item in getattr(voice, "languages", []))
            languages = languages.casefold()
            if any(token in name or token in languages for token in ("brazil", "portugu", "pt_br", "pt-br")):
                engine.setProperty("voice", voice.id)
                break
        engine.say(text)
        engine.runAndWait()
    finally:
        engine.stop()


def speak_text(
    text: str,
    status_callback: Callable[[str], None] | None = None,
) -> None:
    """Speak a response with a cached local neural voice; fall back to system TTS."""
    normalized = normalize_speech_text(text)
    if not normalized:
        return

    audio_path: Path | None = None
    try:
        with _voice_lock:
            voice = _load_voice(status_callback)
            APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                prefix="aurix-voice-",
                suffix=".wav",
                dir=APP_DATA_DIR,
                delete=False,
            ) as temporary:
                audio_path = Path(temporary.name)
            with wave.open(str(audio_path), "wb") as wav_file:
                voice.synthesize(normalized, wav_file)
            _play_wav(audio_path)
    except Exception:
        _LOGGER.exception("A voz neural local falhou; tentando a voz instalada no sistema.")
        if status_callback:
            status_callback("Voz neural indisponível · usando a voz local do Windows…")
        try:
            _speak_with_system_voice(normalized)
        except Exception:
            _LOGGER.exception("A voz do sistema também não pôde ser iniciada.")
    finally:
        if audio_path is not None:
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                _LOGGER.debug("Não foi possível remover o áudio temporário %s", audio_path)
