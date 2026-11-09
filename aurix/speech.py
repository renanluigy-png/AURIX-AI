"""Offline Brazilian Portuguese neural speech for AURIX.

Kokoro v1.0 provides neural speech; TugaPhone supplies pt-BR IPA. Model files
are fetched on demand, SHA-256 verified, and cached under the current user.
The ONNX session is released after a short idle period to limit RAM residency.
"""
from __future__ import annotations

import gc
import hashlib
import json
import logging
import os
import tempfile
import threading
import unicodedata
import wave
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

_LOGGER = logging.getLogger(__name__)

MODEL_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.1/kokoro-v1.0.fp16.onnx"
)
VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.1/voices-v1.0.bin"
)
MODEL_FILENAME = "kokoro-v1.0.fp16.onnx"
VOICES_FILENAME = "voices-v1.0.bin"
MODEL_SHA256 = "f3a290d384fbb27966d462905c71a46cef9e5fd00516b40df32a0b4afe77ac96"
VOICES_SHA256 = "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"
MODEL_MAX_BYTES = 190 * 1024 * 1024
VOICES_MAX_BYTES = 40 * 1024 * 1024
SAMPLE_RATE = 24000
MAX_PHONEMES = 510
VOICE_ID = "pf_dora"
DEFAULT_SPEED = 1.0
ENGINE_KEEP_ALIVE_SECONDS = 60

_download_lock = threading.RLock()
_engine_lock = threading.RLock()
_synthesis_lock = threading.RLock()
_engine = None
_engine_release_timer: threading.Timer | None = None
_phonemizer = None
_phonemizer_lock = threading.Lock()


def _app_data_dir() -> Path:
    """Resolve the user data directory only when speech is actually used."""
    from aurix.config import APP_DATA_DIR

    return APP_DATA_DIR


def normalize_speech_text(text: str, limit: int = 1200) -> str:
    """Normalize whitespace and bound the amount of text sent to the TTS engine."""
    normalized = " ".join(str(text or "").split())
    return normalized[: max(0, int(limit))]


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest without loading a model into RAM."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def filter_supported_ipa(phonemes: str, vocab: dict[str, int]) -> str:
    """Normalize IPA and keep only symbols supported by the Kokoro vocabulary."""
    normalized = unicodedata.normalize("NFD", str(phonemes or "")).replace("·", "")
    return "".join(character for character in normalized if character in vocab)


def build_phoneme_chunks(
    phonemes: str,
    vocab: dict[str, int],
    max_tokens: int = MAX_PHONEMES,
) -> list[list[int]]:
    """Convert space-separated IPA words into bounded token sequences."""
    if max_tokens < 1:
        raise ValueError("max_tokens precisa ser maior que zero.")

    space_id = vocab.get(" ")
    chunks: list[list[int]] = []
    current: list[int] = []

    for raw_word in str(phonemes or "").split():
        word_ids = [int(vocab[char]) for char in raw_word if char in vocab]
        if not word_ids:
            continue

        # Extremely long tokens are split safely rather than overflowing ONNX.
        segments = [
            word_ids[index : index + max_tokens]
            for index in range(0, len(word_ids), max_tokens)
        ]
        for segment in segments:
            separator = [int(space_id)] if current and space_id is not None else []
            if current and len(current) + len(separator) + len(segment) > max_tokens:
                chunks.append(current)
                current = []
                separator = []
            current.extend(separator)
            current.extend(segment)

    if current:
        chunks.append(current)
    return chunks


def _download_verified(
    url: str,
    destination: Path,
    *,
    max_bytes: int,
    expected_sha256: str,
    label: str,
    status_callback: Callable[[str], None] | None = None,
) -> None:
    """Download into a .part file, verify checksum, then atomically publish."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    digest = hashlib.sha256()
    downloaded = 0
    last_reported = -1
    request = Request(
        url,
        headers={
            "User-Agent": "AURIX-AI/0.4.0",
            "Accept": "application/octet-stream",
        },
    )
    try:
        with urlopen(request, timeout=90) as response:
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > max_bytes:
                raise RuntimeError(f"O arquivo {label} excede o limite de tamanho.")
            total = int(declared) if declared and declared.isdigit() else 0
            with temporary.open("wb") as output:
                while True:
                    chunk = response.read(512 * 1024)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        raise RuntimeError(f"O download de {label} excedeu o limite de tamanho.")
                    digest.update(chunk)
                    output.write(chunk)
                    if status_callback and total > 0:
                        percent = min(100, int(downloaded * 100 / total))
                        if percent // 5 > last_reported // 5:
                            status_callback(f"Baixando {label} localmente… {percent}%")
                            last_reported = percent

        if downloaded == 0:
            raise RuntimeError(f"O servidor retornou o arquivo {label} vazio.")
        if digest.hexdigest().casefold() != expected_sha256.casefold():
            raise RuntimeError(f"A verificação SHA-256 de {label} falhou.")
        os.replace(temporary, destination)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            _LOGGER.debug("Não foi possível remover o arquivo temporário %s", temporary)


def _model_paths() -> tuple[Path, Path]:
    root = _app_data_dir() / "models" / "kokoro"
    return root / MODEL_FILENAME, root / VOICES_FILENAME


def _ensure_model_files(
    status_callback: Callable[[str], None] | None = None,
) -> tuple[Path, Path]:
    model_path, voices_path = _model_paths()
    model_path.parent.mkdir(parents=True, exist_ok=True)

    with _download_lock:
        for path, digest, size_limit, url, label in (
            (model_path, MODEL_SHA256, MODEL_MAX_BYTES, MODEL_URL, "modelo neural Kokoro"),
            (voices_path, VOICES_SHA256, VOICES_MAX_BYTES, VOICES_URL, "vozes Kokoro"),
        ):
            if path.is_file():
                try:
                    if sha256_file(path).casefold() != digest.casefold():
                        path.unlink(missing_ok=True)
                except OSError:
                    path.unlink(missing_ok=True)

            if not path.is_file():
                if status_callback:
                    status_callback(
                        "Preparando voz neural pt-BR Kokoro (download único de aproximadamente 182 MB)…"
                    )
                _download_verified(
                    url,
                    path,
                    max_bytes=size_limit,
                    expected_sha256=digest,
                    label=label,
                    status_callback=status_callback,
                )

    return model_path, voices_path


def _numpy_dtype(type_name: str, np):
    """Map an ONNX tensor type to its NumPy dtype."""
    types = {
        "tensor(float)": np.float32,
        "tensor(float16)": np.float16,
        "tensor(double)": np.float64,
        "tensor(int64)": np.int64,
        "tensor(int32)": np.int32,
    }
    if type_name not in types:
        raise RuntimeError(f"Tipo de entrada ONNX não suportado: {type_name}")
    return types[type_name]


def _load_engine(status_callback: Callable[[str], None] | None = None):
    """Load Kokoro, the Brazilian voice style, and the model's embedded vocabulary."""
    global _engine
    with _engine_lock:
        if _engine is not None:
            return _engine

        model_path, voices_path = _ensure_model_files(status_callback)
        if status_callback:
            status_callback("Carregando a voz neural brasileira na memória…")

        import numpy as np
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.intra_op_num_threads = max(1, min(4, os.cpu_count() or 1))
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(
            str(model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )

        metadata = session.get_modelmeta().custom_metadata_map
        config_text = metadata.get("kokoro_config")
        if not config_text:
            raise RuntimeError("O modelo Kokoro não contém o vocabulário esperado.")
        try:
            vocab = json.loads(config_text)["vocab"]
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("O vocabulário do modelo Kokoro está inválido.") from exc
        if not isinstance(vocab, dict) or " " not in vocab:
            raise RuntimeError("O vocabulário do modelo Kokoro está incompleto.")

        inputs = {item.name: item for item in session.get_inputs()}
        token_name = "input_ids" if "input_ids" in inputs else "tokens" if "tokens" in inputs else None
        if token_name is None or "style" not in inputs or "speed" not in inputs:
            raise RuntimeError("O modelo Kokoro possui entradas ONNX incompatíveis.")

        with np.load(str(voices_path), allow_pickle=False) as voice_bank:
            if VOICE_ID not in voice_bank.files:
                raise RuntimeError(f"A voz brasileira {VOICE_ID} não está no pacote de vozes.")
            voice_style = np.array(voice_bank[VOICE_ID], copy=True)

        _engine = {
            "session": session,
            "vocab": vocab,
            "voice_style": voice_style,
            "token_name": token_name,
            "token_dtype": _numpy_dtype(inputs[token_name].type, np),
            "style_dtype": _numpy_dtype(inputs["style"].type, np),
            "speed_dtype": _numpy_dtype(inputs["speed"].type, np),
        }
        return _engine


def _release_engine() -> None:
    """Release the ONNX session after an idle window to reduce memory usage."""
    global _engine, _engine_release_timer
    with _engine_lock:
        _engine = None
        _engine_release_timer = None
    gc.collect()
    _LOGGER.info("Kokoro neural voice released from memory after idle timeout.")


def _schedule_engine_release() -> None:
    global _engine, _engine_release_timer
    try:
        keep_alive = max(
            0,
            min(600, int(os.getenv("AURIX_TTS_KEEP_ALIVE_SECONDS", str(ENGINE_KEEP_ALIVE_SECONDS)))),
        )
    except ValueError:
        keep_alive = ENGINE_KEEP_ALIVE_SECONDS

    with _engine_lock:
        if _engine_release_timer is not None:
            _engine_release_timer.cancel()
            _engine_release_timer = None
        if keep_alive == 0:
            _engine = None
            threading.Thread(target=gc.collect, daemon=True).start()
            return

        timer = threading.Timer(keep_alive, _release_engine)
        timer.daemon = True
        _engine_release_timer = timer
        timer.start()


def _get_phonemizer():
    """Create the light rule-based Portuguese phonemizer once per process."""
    global _phonemizer
    with _phonemizer_lock:
        if _phonemizer is None:
            from tugaphone import TugaPhonemizer

            # Avoid loading heavyweight spaCy/Brill POS models in the desktop app.
            _phonemizer = TugaPhonemizer(postag_engine="dummy")
        return _phonemizer


def _make_audio(text: str, status_callback: Callable[[str], None] | None = None):
    """Generate float PCM arrays using Kokoro's local ONNX model."""
    import numpy as np

    engine = _load_engine(status_callback)
    if status_callback:
        status_callback("Convertendo português brasileiro em fonemas…")

    phonemizer = _get_phonemizer()
    ipa = phonemizer.phonemize_sentence(text, "pt-BR")
    normalized_ipa = filter_supported_ipa(ipa, engine["vocab"])
    chunks = build_phoneme_chunks(normalized_ipa, engine["vocab"])
    if not chunks:
        raise RuntimeError("Não consegui converter o texto em fonemas reconhecidos pela voz Kokoro.")

    audio_parts = []
    for token_ids in chunks:
        token_array = np.asarray(
            [[0, *token_ids, 0]],
            dtype=engine["token_dtype"],
        )
        style_index = min(len(token_ids), len(engine["voice_style"])) - 1
        if style_index < 0:
            continue
        style_array = np.asarray(
            engine["voice_style"][style_index],
            dtype=engine["style_dtype"],
        ).reshape(1, -1)
        speed_array = np.asarray([DEFAULT_SPEED], dtype=engine["speed_dtype"])

        generated = engine["session"].run(
            None,
            {
                engine["token_name"]: token_array,
                "style": style_array,
                "speed": speed_array,
            },
        )[0]
        samples = np.asarray(generated, dtype=np.float32).reshape(-1)
        if samples.size:
            peak = float(np.max(np.abs(samples)))
            if peak > 1e-8:
                threshold = max(0.002, peak * 0.02)
                active = np.flatnonzero(np.abs(samples) >= threshold)
                if active.size:
                    padding = int(SAMPLE_RATE * 0.04)
                    start = max(0, int(active[0]) - padding)
                    end = min(samples.size, int(active[-1]) + padding + 1)
                    samples = samples[start:end]
            audio_parts.append(samples)

    if not audio_parts:
        raise RuntimeError("O modelo Kokoro não gerou áudio.")
    if len(audio_parts) == 1:
        return audio_parts[0]

    silence = np.zeros(int(SAMPLE_RATE * 0.08), dtype=np.float32)
    combined: list = []
    for index, part in enumerate(audio_parts):
        if index:
            combined.append(silence)
        combined.append(part)
    return np.concatenate(combined)


def synthesize_to_wav(
    text: str,
    destination: str | Path,
    status_callback: Callable[[str], None] | None = None,
) -> Path:
    """Generate a WAV file without playing it (used by CI and diagnostics)."""
    normalized = normalize_speech_text(text)
    if not normalized:
        raise ValueError("O texto para sintetizar está vazio.")

    import numpy as np

    with _synthesis_lock:
        samples = _make_audio(normalized, status_callback)
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
        samples = np.clip(samples, -1.0, 1.0)
        pcm = (samples * 32767.0).astype(np.int16)

        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".part")
        try:
            with wave.open(str(temporary), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(SAMPLE_RATE)
                output.writeframes(pcm.tobytes())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    _schedule_engine_release()
    return target


def _play_wav(path: Path) -> None:
    """Play a synthesized WAV locally, without a cloud service."""
    if os.name == "nt":
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME)
        return

    import numpy as np
    import sounddevice as sd

    with wave.open(str(path), "rb") as audio_file:
        if audio_file.getsampwidth() != 2:
            raise RuntimeError("A voz local retornou um formato de áudio não suportado.")
        channels = audio_file.getnchannels()
        sample_rate = audio_file.getframerate()
        samples = np.frombuffer(
            audio_file.readframes(audio_file.getnframes()),
            dtype=np.int16,
        )
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
    """Speak with a local pt-BR neural voice; use system speech as a fallback."""
    normalized = normalize_speech_text(text)
    if not normalized:
        return

    app_data_dir = _app_data_dir()
    app_data_dir.mkdir(parents=True, exist_ok=True)
    audio_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="aurix-voice-",
            suffix=".wav",
            dir=app_data_dir,
            delete=False,
        ) as temporary:
            audio_path = Path(temporary.name)
        synthesize_to_wav(normalized, audio_path, status_callback)
        _play_wav(audio_path)
    except Exception:
        _LOGGER.exception("A voz neural Kokoro falhou; tentando a voz instalada no sistema.")
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
