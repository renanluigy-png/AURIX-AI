"""Background wake-word detection, audio capture, and speech transcription."""

from __future__ import annotations

import json
import os
import queue
import threading
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from aurix.config import APP_DATA_DIR

from aurix.config import APP_DATA_DIR


class VoiceService(QThread):
    """Listen for the pre-trained 'Hey Jarvis' phrase and capture one request."""

    wake_detected = Signal()
    transcript_ready = Signal(str)
    status_changed = Signal(str)
    error = Signal(str)

    SAMPLE_RATE = 16000
    FRAME_SIZE = 1280
    MAX_CAPTURE_SECONDS = 12.0
    SILENCE_SECONDS = 1.0
    RMS_THRESHOLD = 420.0

    def __init__(self, threshold: float = 0.55, parent=None) -> None:
        super().__init__(parent)
        self.threshold = max(0.1, min(0.95, threshold))
        self._stop_event = threading.Event()
        self._enabled_event = threading.Event()
        self._enabled_event.set()
        self._queue: queue.Queue = queue.Queue(maxsize=32)
        self._enabled = True
        self._enabled_lock = threading.Lock()
        self._vosk_model = None

    def stop(self) -> None:
        self._stop_event.set()
        self._enabled_event.set()

    def set_enabled(self, enabled: bool) -> None:
        with self._enabled_lock:
            self._enabled = enabled
        if enabled:
            self._enabled_event.set()
        else:
            self._enabled_event.clear()

    def is_enabled(self) -> bool:
        with self._enabled_lock:
            return self._enabled

    def _audio_callback(self, indata, frames, timing, status) -> None:
        if self._stop_event.is_set():
            return
        try:
            self._queue.put_nowait(indata.copy().reshape(-1))
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(indata.copy().reshape(-1))
            except queue.Full:
                pass

    def run(self) -> None:
        try:
            import numpy as np
            import openwakeword
            import sounddevice as sd
            from openwakeword import utils as wakeword_utils
            from openwakeword.model import Model
        except ImportError as exc:
            self.error.emit(
                "Dependências de voz ausentes. Instale requirements.txt; "
                f"Ctrl+Alt+Espaço continua disponível. ({exc})"
            )
            return

        try:
            # Store downloaded models in the user's profile, not inside site-packages.
            model_dir = APP_DATA_DIR / "models" / "openwakeword"
            model_dir.mkdir(parents=True, exist_ok=True)
            model_path = model_dir / "hey_jarvis_v0.1.onnx"
            if not model_path.exists():
                self.status_changed.emit("Baixando o modelo de ativação pela primeira vez…")
                wakeword_utils.download_models(
                    model_names=["hey_jarvis_v0.1"],
                    target_directory=str(model_dir),
                )
            if not model_path.exists():
                candidates = list(model_dir.rglob("*hey*jarvis*.onnx"))
                if candidates:
                    model_path = candidates[0]
            if not model_path.exists():
                raise FileNotFoundError(
                    "Não encontrei o modelo ONNX Hey Jarvis após o download."
                )
            model = Model(
                wakeword_models=[str(model_path)],
                inference_framework="onnx",
                melspec_model_path=str(model_dir / "melspectrogram.onnx"),
                embedding_model_path=str(model_dir / "embedding_model.onnx"),
            )
        except Exception as exc:
            self.error.emit(
                "Não consegui inicializar a ativação por voz. Confira a conexão na primeira "
                f"execução e use o atalho global enquanto isso. ({exc})"
            )
            return

        paused_message_sent = False
        self.status_changed.emit("Voz inicializada · aguardando “Hey Jarvis”")
        while not self._stop_event.is_set():
            if not self.is_enabled():
                if not paused_message_sent:
                    self.status_changed.emit("Escuta pausada · microfone fechado")
                    paused_message_sent = True
                self._enabled_event.wait(0.25)
                continue

            paused_message_sent = False
            self._clear_queue()
            capturing = False
            captured_frames: list[bytes] = []
            capture_started = 0.0
            last_voice_at = 0.0
            has_voice = False

            try:
                with sd.InputStream(
                    samplerate=self.SAMPLE_RATE,
                    blocksize=self.FRAME_SIZE,
                    channels=1,
                    dtype="int16",
                    callback=self._audio_callback,
                ):
                    self.status_changed.emit("Em segundo plano · aguardando “Hey Jarvis”")
                    while not self._stop_event.is_set() and self.is_enabled():
                        try:
                            frame = self._queue.get(timeout=0.2)
                        except queue.Empty:
                            continue

                        now = time.monotonic()
                        audio = np.asarray(frame, dtype=np.int16).reshape(-1)
                        if capturing:
                            captured_frames.append(audio.tobytes())
                            rms = float(np.sqrt(np.mean(np.square(audio.astype(np.float32)))))
                            if rms >= self.RMS_THRESHOLD:
                                has_voice = True
                                last_voice_at = now

                            elapsed = now - capture_started
                            silence_finished = has_voice and now - last_voice_at >= self.SILENCE_SECONDS
                            no_speech_timeout = not has_voice and elapsed >= 3.0
                            if silence_finished or no_speech_timeout or elapsed >= self.MAX_CAPTURE_SECONDS:
                                capturing = False
                                if has_voice and captured_frames:
                                    self.status_changed.emit("Transcrevendo seu pedido…")
                                    raw_audio = b"".join(captured_frames)
                                    self._clear_queue()
                                    try:
                                        text = self._transcribe(raw_audio)
                                    except Exception as exc:
                                        self.error.emit(self._friendly_transcription_error(exc))
                                        text = ""
                                    self._clear_queue()
                                    if text:
                                        self.transcript_ready.emit(text)
                                else:
                                    self.status_changed.emit("Não ouvi um pedido. Diga “Hey Jarvis” para tentar de novo.")
                                captured_frames = []
                                has_voice = False
                                self.status_changed.emit("Em segundo plano · aguardando “Hey Jarvis”")
                            continue

                        prediction = model.predict(audio)
                        score = max(prediction.values(), default=0.0)
                        if float(score) >= self.threshold:
                            capturing = True
                            captured_frames = []
                            capture_started = now
                            last_voice_at = now
                            has_voice = False
                            self.wake_detected.emit()
                            self.status_changed.emit("Ativado · ouvindo seu pedido…")
            except Exception as exc:
                if not self._stop_event.is_set() and self.is_enabled():
                    self.error.emit(
                        "Não consegui acessar o microfone. Confira as permissões do Windows e "
                        f"o dispositivo de entrada. ({exc})"
                    )
                    time.sleep(1.0)

    def _clear_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def _transcribe(self, raw_audio: bytes) -> str:
        provider = os.getenv("AURIX_SPEECH_PROVIDER", "google").strip().lower()
        if provider == "vosk":
            return self._transcribe_vosk(raw_audio)

        import speech_recognition as sr

        audio = sr.AudioData(raw_audio, self.SAMPLE_RATE, 2)
        recognizer = sr.Recognizer()
        recognizer.operation_timeout = 10
        return recognizer.recognize_google(audio, language="pt-BR").strip()

    def _ensure_vosk_model(self) -> Path:
        """Download the small Brazilian Portuguese model into the user data folder."""
        import shutil
        import zipfile
        from urllib.request import urlopen

        configured = os.getenv("AURIX_VOSK_MODEL_PATH", "").strip()
        if configured and Path(configured).is_dir():
            return Path(configured)

        model_name = "vosk-model-small-pt-0.3"
        root = APP_DATA_DIR / "models" / "vosk"
        model_path = root / model_name
        if model_path.is_dir():
            return model_path

        root.mkdir(parents=True, exist_ok=True)
        archive = root / (model_name + ".zip")
        url = "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"
        self.status_changed.emit("Baixando modelo de português (~31 MB) para reconhecimento local…")
        try:
            with urlopen(url, timeout=45) as response, archive.open("wb") as output:
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > 100 * 1024 * 1024:
                    raise RuntimeError("O tamanho do modelo recebido excede o limite esperado.")
                shutil.copyfileobj(response, output)
            with zipfile.ZipFile(archive) as compressed:
                root_resolved = root.resolve()
                for member in compressed.infolist():
                    destination = (root / member.filename).resolve()
                    if destination != root_resolved and root_resolved not in destination.parents:
                        raise RuntimeError("O arquivo de modelo contém um caminho inválido.")
                compressed.extractall(root)
        except Exception:
            try:
                archive.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        finally:
            try:
                archive.unlink(missing_ok=True)
            except OSError:
                pass
        if not model_path.is_dir():
            raise FileNotFoundError("O download terminou, mas a pasta do modelo não foi encontrada.")
        os.environ["AURIX_VOSK_MODEL_PATH"] = str(model_path)
        return model_path

    def _transcribe_vosk(self, raw_audio: bytes) -> str:
        import vosk

        model_path = self._ensure_vosk_model()
        if self._vosk_model is None:
            self._vosk_model = vosk.Model(str(model_path))
        recognizer = vosk.KaldiRecognizer(self._vosk_model, self.SAMPLE_RATE)
        recognizer.AcceptWaveform(raw_audio)
        result = json.loads(recognizer.FinalResult())
        return str(result.get("text", "")).strip()

    @staticmethod
    def _friendly_transcription_error(exc: Exception) -> str:
        name = exc.__class__.__name__
        if name == "UnknownValueError":
            return "Não entendi a fala. Tente falar um pouco mais perto do microfone."
        if name == "RequestError":
            return "A transcrição online não respondeu. Verifique a internet ou configure Vosk local."
        return f"Falha na transcrição: {exc}"
