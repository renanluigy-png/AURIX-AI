"""Audio capture for direct voice requests and the optional Hey Jarvis wake word."""

from __future__ import annotations

import json
import os
import queue
import shutil
import threading
import time
import zipfile
from pathlib import Path
from urllib.request import urlopen

from PySide6.QtCore import QThread, Signal

from aurix.config import APP_DATA_DIR


class VoiceService(QThread):
    """Runs direct one-shot recording and optional background wake-word detection."""

    wake_detected = Signal()
    transcript_ready = Signal(str)
    status_changed = Signal(str)
    error = Signal(str)

    SAMPLE_RATE = 16000
    FRAME_SIZE = 1280
    MAX_CAPTURE_SECONDS = 18.0
    SILENCE_SECONDS = 1.15
    RMS_THRESHOLD = 300.0
    NO_SPEECH_TIMEOUT = 6.0

    def __init__(self, threshold: float = 0.55, parent=None) -> None:
        super().__init__(parent)
        self.threshold = max(0.1, min(0.95, threshold))
        self._stop_event = threading.Event()
        self._activity_event = threading.Event()
        self._manual_event = threading.Event()
        self._queue: queue.Queue = queue.Queue(maxsize=64)
        self._enabled = False
        self._enabled_lock = threading.Lock()
        self._vosk_model = None

    def stop(self) -> None:
        self._stop_event.set()
        self._activity_event.set()
        self._manual_event.set()

    def set_enabled(self, enabled: bool) -> None:
        with self._enabled_lock:
            self._enabled = bool(enabled)
        self._activity_event.set()

    def is_enabled(self) -> bool:
        with self._enabled_lock:
            return self._enabled

    def request_listen_once(self) -> None:
        """Record a single spoken request without requiring the wake phrase."""
        if self._stop_event.is_set():
            return
        self._manual_event.set()
        self._activity_event.set()

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

    def _load_wakeword_model(self):
        """Load the wake detector only when the user has enabled Hey Jarvis."""
        from openwakeword import utils as wakeword_utils
        from openwakeword.model import Model

        model_dir = APP_DATA_DIR / "models" / "openwakeword"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / "hey_jarvis_v0.1.onnx"
        if not model_path.exists():
            self.status_changed.emit("Preparando Hey Jarvis pela primeira vez…")
            wakeword_utils.download_models(
                model_names=["hey_jarvis_v0.1"],
                target_directory=str(model_dir),
            )
        if not model_path.exists():
            candidates = list(model_dir.rglob("*hey*jarvis*.onnx"))
            if candidates:
                model_path = candidates[0]
        if not model_path.exists():
            raise FileNotFoundError("O modelo ONNX Hey Jarvis não foi encontrado após o download.")
        return Model(
            wakeword_models=[str(model_path)],
            inference_framework="onnx",
            melspec_model_path=str(model_dir / "melspectrogram.onnx"),
            embedding_model_path=str(model_dir / "embedding_model.onnx"),
        )

    def run(self) -> None:
        try:
            import numpy as np
            import sounddevice as sd
        except ImportError as exc:
            self.error.emit(
                "O módulo de áudio não foi carregado. Reinstale a versão mais recente do AURIX. "
                f"Detalhe: {exc}"
            )
            return

        wake_model = None
        idle_status_sent = False
        self.status_changed.emit("Voz pronta · clique em FALAR ou ative Hey Jarvis")

        while not self._stop_event.is_set():
            manual_requested = self._manual_event.is_set()
            wake_enabled = self.is_enabled()

            if not wake_enabled and not manual_requested:
                if not idle_status_sent:
                    self.status_changed.emit("Voz pronta · clique em FALAR ou ative Hey Jarvis")
                    idle_status_sent = True
                self._activity_event.clear()
                if self.is_enabled() or self._manual_event.is_set() or self._stop_event.is_set():
                    continue
                self._activity_event.wait(0.35)
                continue

            idle_status_sent = False

            if wake_enabled and wake_model is None:
                try:
                    wake_model = self._load_wakeword_model()
                    self.status_changed.emit("Hey Jarvis ativado · aguardando a palavra de ativação")
                except Exception as exc:
                    self.set_enabled(False)
                    self.error.emit(
                        "Hey Jarvis não foi inicializado. Você ainda pode usar o botão FALAR. "
                        f"Detalhe: {str(exc).splitlines()[0][:180]}"
                    )
                    continue

            manual_capture = self._manual_event.is_set()
            if manual_capture:
                self._manual_event.clear()

            self._clear_queue()
            capturing = manual_capture
            captured_frames: list[bytes] = []
            capture_started = time.monotonic() if manual_capture else 0.0
            last_voice_at = capture_started
            has_voice = False
            should_leave_stream = False

            if manual_capture:
                self.status_changed.emit("Ouvindo você · fale seu pedido agora")

            try:
                with sd.InputStream(
                    samplerate=self.SAMPLE_RATE,
                    blocksize=self.FRAME_SIZE,
                    channels=1,
                    dtype="int16",
                    callback=self._audio_callback,
                ):
                    if not manual_capture:
                        self.status_changed.emit("Em segundo plano · aguardando Hey Jarvis")

                    while not self._stop_event.is_set():
                        if not capturing and self._manual_event.is_set():
                            self._manual_event.clear()
                            manual_capture = True
                            capturing = True
                            captured_frames = []
                            capture_started = time.monotonic()
                            last_voice_at = capture_started
                            has_voice = False
                            self._clear_queue()
                            self.status_changed.emit("Ouvindo você · fale seu pedido agora")

                        if not capturing and not self.is_enabled():
                            break

                        try:
                            frame = self._queue.get(timeout=0.15)
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
                            no_speech_timeout = not has_voice and elapsed >= self.NO_SPEECH_TIMEOUT
                            time_limit = elapsed >= self.MAX_CAPTURE_SECONDS

                            if silence_finished or no_speech_timeout or time_limit:
                                if has_voice and captured_frames:
                                    self.status_changed.emit("Transcrevendo seu pedido…")
                                    raw_audio = b"".join(captured_frames)
                                    try:
                                        text = self._transcribe(raw_audio)
                                    except Exception as exc:
                                        self.error.emit(self._friendly_transcription_error(exc))
                                        text = ""
                                    self._clear_queue()
                                    if text:
                                        self.set_enabled(False)
                                        self.transcript_ready.emit(text)
                                        should_leave_stream = True
                                    else:
                                        self.status_changed.emit(
                                            "Não consegui reconhecer as palavras. Fale mais perto do microfone e tente novamente."
                                        )
                                        if manual_capture:
                                            should_leave_stream = True
                                        else:
                                            capturing = False
                                            captured_frames = []
                                            has_voice = False
                                else:
                                    self.status_changed.emit(
                                        "Não captei voz. Clique em FALAR e tente novamente."
                                        if manual_capture
                                        else "Não ouvi um pedido. Diga Hey Jarvis e tente novamente."
                                    )
                                    if manual_capture:
                                        should_leave_stream = True
                                    else:
                                        capturing = False
                                        captured_frames = []
                                        has_voice = False

                                if should_leave_stream:
                                    break
                                continue
                            continue

                        if self.is_enabled() and wake_model is not None:
                            prediction = wake_model.predict(audio)
                            score = max(prediction.values(), default=0.0)
                            if float(score) >= self.threshold:
                                capturing = True
                                manual_capture = False
                                captured_frames = []
                                capture_started = now
                                last_voice_at = now
                                has_voice = False
                                self.wake_detected.emit()
                                self.status_changed.emit("Hey Jarvis detectado · ouvindo seu pedido…")

            except Exception as exc:
                if not self._stop_event.is_set():
                    self.error.emit(
                        "Não consegui acessar o microfone. Verifique o dispositivo de entrada "
                        "e as permissões de microfone do Windows. "
                        f"Detalhe: {str(exc).splitlines()[0][:180]}"
                    )
                    if self.is_enabled():
                        self.set_enabled(False)
                continue

    def _clear_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def _transcribe(self, raw_audio: bytes) -> str:
        provider = os.getenv("AURIX_SPEECH_PROVIDER", "vosk").strip().lower()
        if provider == "vosk":
            return self._transcribe_vosk(raw_audio)

        import speech_recognition as sr

        audio = sr.AudioData(raw_audio, self.SAMPLE_RATE, 2)
        recognizer = sr.Recognizer()
        recognizer.operation_timeout = 10
        return recognizer.recognize_google(audio, language="pt-BR").strip()

    def _ensure_vosk_model(self) -> Path:
        """Download the small Brazilian Portuguese model into the user data folder."""
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
        self.status_changed.emit("Baixando o modelo de português (~31 MB) para reconhecimento local…")
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
        recognizer.SetWords(False)
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
        return f"Falha na transcrição: {str(exc).splitlines()[0][:180]}"
