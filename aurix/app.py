"""Desktop application lifecycle, tray menu, hotkey, and request routing."""

from __future__ import annotations

import hashlib
import logging
import sys
import threading

from PySide6.QtCore import QObject, QRunnable, QThread, QThreadPool, Signal, Slot, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from aurix.brain import AssistantBrain
from aurix.commands import parse_command
from aurix.config import (
    APP_DATA_DIR,
    LOG_PATH,
    Settings,
    configure_runtime_settings,
    is_start_with_windows_enabled,
    set_start_with_windows,
)
from aurix.onboarding import SetupDialog
from aurix.hud import HUDWindow
from aurix.voice import VoiceService


def _configure_logging() -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
    )


def _instance_server_name() -> str:
    identity = str(APP_DATA_DIR.resolve()).casefold().encode("utf-8")
    return "aurix-ai-" + hashlib.sha256(identity).hexdigest()[:16]


def _notify_existing_instance(name: str) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(300):
        socket.abort()
        return False
    socket.write(b"show\n")
    socket.flush()
    socket.waitForBytesWritten(300)
    socket.disconnectFromServer()
    return True


def _create_instance_server(app: QApplication) -> tuple[QLocalServer | None, str]:
    name = _instance_server_name()
    if _notify_existing_instance(name):
        return None, name
    server = QLocalServer(app)
    if server.listen(name):
        return server, name
    if _notify_existing_instance(name):
        return None, name
    QLocalServer.removeServer(name)
    if not server.listen(name):
        logging.error("Could not create single-instance IPC endpoint: %s", server.errorString())
    return server, name


def _make_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QColor(82, 239, 255, 240))
    painter.setBrush(QColor(5, 24, 44, 250))
    painter.drawEllipse(4, 4, 56, 56)
    painter.setPen(QColor(85, 225, 255, 240))
    painter.drawEllipse(12, 12, 40, 40)
    painter.setPen(QColor(200, 253, 255, 255))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "A")
    painter.end()
    return QIcon(pixmap)


class WorkerSignals(QObject):
    finished = Signal(str, bool)


class RequestWorker(QRunnable):
    def __init__(self, text: str, speak_result: bool, brain: AssistantBrain) -> None:
        super().__init__()
        self.text = text
        self.speak_result = speak_result
        self.brain = brain
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            # The selected model chooses whether to converse or call one of the tools.
            result = self.brain.respond(self.text)
        except Exception:
            logging.exception("Unhandled error while processing a request")
            result = "Ocorreu um erro inesperado ao processar o pedido. Veja o log local do AURIX."
        self.signals.finished.emit(result, self.speak_result)


class HotkeyService(QThread):
    activated = Signal()
    error = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._stop_event = threading.Event()
        self._listener = None

    def stop(self) -> None:
        self._stop_event.set()
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass

    def run(self) -> None:
        try:
            from pynput import keyboard
        except ImportError:
            self.error.emit("Atalho global indisponível: instale pynput. O ícone da bandeja continua disponível.")
            return

        try:
            self._listener = keyboard.GlobalHotKeys({"<ctrl>+<alt>+space": self.activated.emit})
            self._listener.start()
            while not self._stop_event.wait(0.25):
                if not self._listener.is_alive():
                    break
            self._listener.stop()
            self._listener.join(timeout=2)
        except Exception as exc:
            if not self._stop_event.is_set():
                self.error.emit(f"Não consegui registrar Ctrl+Alt+Espaço: {exc}")


class AurixController(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self.app = app
        self.settings = Settings.load()
        configure_runtime_settings(self.settings)
        self.brain = AssistantBrain()
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(2)
        self._request_in_flight = False
        self._active_worker = None

        self.window = HUDWindow()
        self.window.command_submitted.connect(self.handle_request)
        self.window.settings_requested.connect(self._open_setup_dialog)
        self.window.voice_toggle_requested.connect(self._toggle_voice_from_hud)
        self.window.listen_once_requested.connect(self._listen_once_from_hud)
        self.window.set_voice_enabled(self.settings.wake_word_enabled)

        self.voice = VoiceService(threshold=self.settings.wake_threshold)
        self.voice.wake_detected.connect(self.on_wake_detected)
        self.voice.transcript_ready.connect(self.on_voice_transcript)
        self.voice.status_changed.connect(self.window.set_status)
        self.voice.error.connect(self.on_voice_error)
        self.voice.set_enabled(self.settings.wake_word_enabled)

        self.hotkey = HotkeyService()
        self.hotkey.activated.connect(self.window.show_hud)
        self.hotkey.error.connect(self.window.set_status)

        self.tray = QSystemTrayIcon(_make_icon(), self)
        self.tray.setToolTip("AURIX AI — assistente pessoal")
        self._build_tray_menu()
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        self.voice.start()
        self.hotkey.start()
        logging.info("AURIX desktop process started")

        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.window.show_hud()
            QMessageBox.information(
                self.window,
                "AURIX AI",
                "A bandeja do sistema não está disponível. A interface foi aberta para você continuar.",
            )

    def _build_tray_menu(self) -> None:
        menu = QMenu()
        show_action = QAction("Abrir HUD  ·  Ctrl+Alt+Espaço", menu)
        show_action.triggered.connect(self.window.show_hud)
        menu.addAction(show_action)

        self.voice_action = QAction("Escuta de ativação por voz", menu)
        self.voice_action.setCheckable(True)
        self.voice_action.setChecked(self.settings.wake_word_enabled)
        self.voice_action.toggled.connect(self._toggle_voice)
        menu.addAction(self.voice_action)

        setup_action = QAction("Configurar IA e voz…", menu)
        setup_action.triggered.connect(self._open_setup_dialog)
        menu.addAction(setup_action)

        self.autostart_action = QAction("Iniciar com o Windows", menu)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(is_start_with_windows_enabled())
        self.autostart_action.toggled.connect(self._toggle_autostart)
        menu.addAction(self.autostart_action)

        menu.addSeparator()
        exit_action = QAction("Sair do AURIX", menu)
        exit_action.triggered.connect(self.shutdown)
        menu.addAction(exit_action)
        self.tray.setContextMenu(menu)

    @Slot()
    def on_wake_detected(self) -> None:
        self.window.show_hud()
        self.window.set_status("Ativado · ouvindo seu pedido…")
        self.window.set_response("Estou ouvindo. Diga o que você precisa.")

    @Slot(str)
    def on_voice_transcript(self, text: str) -> None:
        self.window.show_hud()
        self.voice.set_enabled(False)
        self.handle_request(text, True)

    @Slot(str)
    def on_voice_error(self, message: str) -> None:
        logging.warning(message)
        self.window.set_status(message)
        self.tray.setToolTip("AURIX AI — verifique o status da voz")
        lowered = message.casefold()
        if "hey jarvis não foi inicializado" in lowered or "não consegui acessar o microfone" in lowered:
            self.settings.wake_word_enabled = False
            self.settings.save()
            if hasattr(self, "voice_action"):
                self.voice_action.blockSignals(True)
                self.voice_action.setChecked(False)
                self.voice_action.blockSignals(False)
            self.window.set_voice_enabled(False)
            self.tray.showMessage(
                "AURIX AI · voz",
                "A ativação contínua foi pausada. Você ainda pode tentar o botão FALAR.",
                QSystemTrayIcon.MessageIcon.Warning,
                4500,
            )

    @Slot(str, bool)
    def handle_request(self, text: str, speak_result: bool = False) -> None:
        if self._request_in_flight:
            self.window.set_response("Ainda estou processando o pedido anterior. Tente novamente em instantes.")
            if speak_result and self.settings.wake_word_enabled:
                self.voice.set_enabled(True)
            return
        self._request_in_flight = True
        self.window.append_message("Você", text)
        self.window.set_busy(True)
        self.window.set_status("Processando solicitação…")
        worker = RequestWorker(text, speak_result, self.brain)
        worker.signals.finished.connect(self._on_request_finished)
        self._active_worker = worker
        self.thread_pool.start(worker)

    @Slot(str, bool)
    def _on_request_finished(self, result: str, speak_result: bool) -> None:
        self._request_in_flight = False
        self.window.set_busy(False)
        self.window.set_status("Concluído · aguardando próximo comando")
        self.window.set_response(result)
        self._active_worker = None
        logging.info("Request completed")
        if speak_result and self.settings.tts_enabled:
            threading.Thread(target=self._speak_and_resume, args=(result,), daemon=True).start()
        elif speak_result and self.settings.wake_word_enabled:
            self.voice.set_enabled(True)

    def _speak_and_resume(self, text: str) -> None:
        try:
            self._speak(text)
        finally:
            if self.settings.wake_word_enabled:
                self.voice.set_enabled(True)

    @staticmethod
    def _speak(text: str) -> None:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", 178)
            for voice in engine.getProperty("voices"):
                name = (getattr(voice, "name", "") or "").casefold()
                language = " ".join(str(item) for item in getattr(voice, "languages", [])).casefold()
                if "brazil" in name or "portugu" in name or "pt_br" in language:
                    engine.setProperty("voice", voice.id)
                    break
            engine.say(text[:1200])
            engine.runAndWait()
            engine.stop()
        except Exception:
            logging.exception("Text-to-speech failed")

    @Slot()
    def _listen_once_from_hud(self) -> None:
        """Start direct push-to-talk capture; no wake word is needed."""
        if getattr(self, "_shutdown_started", False):
            return
        try:
            if not self.voice.isRunning():
                self.voice.start()
            self.voice.request_listen_once()
            self.window.set_status("Ouvindo você · fale seu pedido agora")
        except RuntimeError:
            logging.exception("Could not start direct voice capture")
            self.window.set_status("Não consegui iniciar o microfone. Tente novamente.")

    @Slot()
    def _toggle_voice_from_hud(self) -> None:
        self.voice_action.setChecked(not self.voice_action.isChecked())

    @Slot(bool)
    def _toggle_voice(self, enabled: bool) -> None:
        self.settings.wake_word_enabled = enabled
        self.settings.save()
        self.voice.set_enabled(enabled)
        if enabled and not self.voice.isRunning():
            try:
                self.voice.start()
            except RuntimeError:
                logging.exception("Could not restart the voice worker")
        self.window.set_voice_enabled(enabled)
        self.window.set_status(
            "Escuta de ativação ativa." if enabled else "Escuta pausada. O microfone será fechado."
        )

    @Slot(bool)
    def _toggle_autostart(self, enabled: bool) -> None:
        ok, message = set_start_with_windows(enabled)
        if not ok:
            self.autostart_action.blockSignals(True)
            self.autostart_action.setChecked(not enabled)
            self.autostart_action.blockSignals(False)
            self.window.set_status(message)
            self.tray.showMessage("AURIX AI", message, QSystemTrayIcon.MessageIcon.Warning, 4000)
            return
        self.settings.start_with_windows = enabled
        self.settings.save()
        self.tray.showMessage("AURIX AI", message, QSystemTrayIcon.MessageIcon.Information, 2500)

    @Slot()
    def _open_setup_dialog(self) -> None:
        dialog = SetupDialog(self.settings, self.window)
        if dialog.exec() != SetupDialog.DialogCode.Accepted:
            return
        self.settings = Settings.load()
        configure_runtime_settings(self.settings)
        self.brain = AssistantBrain()
        self.voice.threshold = self.settings.wake_threshold
        self.voice.set_enabled(self.settings.wake_word_enabled)
        if self.settings.wake_word_enabled and not self.voice.isRunning():
            try:
                self.voice.start()
            except RuntimeError:
                logging.exception("Could not restart the voice worker after setup")
        self.window.set_voice_enabled(self.settings.wake_word_enabled)
        if self.settings.start_with_windows:
            ok, message = set_start_with_windows(True)
            if not ok:
                self.window.set_status(message)
        else:
            set_start_with_windows(False)
        self.voice_action.blockSignals(True)
        self.voice_action.setChecked(self.settings.wake_word_enabled)
        self.voice_action.blockSignals(False)
        self.autostart_action.blockSignals(True)
        self.autostart_action.setChecked(self.settings.start_with_windows)
        self.autostart_action.blockSignals(False)
        self.window.set_response("Configurações atualizadas.")
        self.window.set_status("Pronto para ajudar.")

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.window.show_hud()

    @Slot()
    def shutdown(self) -> None:
        if getattr(self, "_shutdown_started", False):
            return
        self._shutdown_started = True
        logging.info("Shutting down AURIX")
        self.voice.stop()
        self.hotkey.stop()
        self.voice.wait(2500)
        self.hotkey.wait(2500)
        self.tray.hide()
        self.app.quit()


def main() -> None:
    _configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("AURIX AI")
    app.setOrganizationName("AURIX")
    app.setQuitOnLastWindowClosed(False)

    instance_server, instance_name = _create_instance_server(app)
    if instance_server is None:
        return

    instance_state: dict[str, object] = {"controller": None, "pending_show": False}

    def handle_connection() -> None:
        while instance_server.hasPendingConnections():
            client = instance_server.nextPendingConnection()

            def show_existing(socket=client) -> None:
                try:
                    socket.readAll()
                    controller = instance_state.get("controller")
                    if controller is not None:
                        controller.window.show_hud()
                    else:
                        instance_state["pending_show"] = True
                except Exception:
                    logging.exception("Failed to handle activation request")
                finally:
                    socket.disconnectFromServer()

            client.readyRead.connect(show_existing)
            client.disconnected.connect(client.deleteLater)
            if client.bytesAvailable():
                show_existing()

    instance_server.newConnection.connect(handle_connection)

    first_launch = not Settings.load().first_run_complete
    initial_settings = Settings.load()
    background_start = "--background" in sys.argv[1:]
    if first_launch:
        SetupDialog(initial_settings).exec()
        initial_settings = Settings.load()
    configure_runtime_settings(initial_settings)
    if initial_settings.start_with_windows:
        ok, message = set_start_with_windows(True)
        if not ok:
            logging.warning(message)
    controller = AurixController(app)
    instance_state["controller"] = controller

    if first_launch or not background_start:
        controller.window.show_hud()
    if instance_state["pending_show"]:
        controller.window.show_hud()

    if first_launch:
        if initial_settings.first_run_complete:
            controller.window.set_response(
                "AURIX iniciado. Clique em FALAR para ditar um pedido, diga “Hey Jarvis” "
                "se a ativação contínua estiver ligada, ou escreva no campo de conversa."
            )
        else:
            controller.window.set_response(
                "AURIX iniciado sem concluir a configuração. Abra o menu da bandeja e selecione "
                "Configurar IA e voz para começar."
            )

    app.aboutToQuit.connect(controller.shutdown)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
