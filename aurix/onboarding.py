"""First-run onboarding: provider choice, voice consent, and local preferences."""

from __future__ import annotations

import os
import shutil

from PySide6.QtCore import QProcess, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from aurix.config import Settings


class SetupDialog(QDialog):
    """Configure AI provider and microphone behavior before starting the assistant."""

    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._ollama_process: QProcess | None = None
        self._ollama_output = ""
        self.setWindowTitle("Configuração inicial · AURIX AI")
        self.setMinimumWidth(580)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 22)
        root.setSpacing(13)

        title = QLabel("Vamos preparar o AURIX")
        title.setFont(QFont("Segoe UI", 19, QFont.Weight.DemiBold))
        title.setStyleSheet("color: #80f0ff;")
        root.addWidget(title)

        intro = QLabel(
            "Escolha o provedor de IA e configure a voz. Para IA local, o Qwen 2.5 7B oferece "
            "respostas e uso de ferramentas geralmente melhores que o modelo pequeno anterior, "
            "mas baixa vários GB na primeira conversa. O microfone só será usado conforme sua escolha."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #b8cedb;")
        root.addWidget(intro)

        form = QFormLayout()
        form.setSpacing(10)
        self.provider = QComboBox()
        self.provider.addItem("Ollama · IA local no computador", "ollama")
        self.provider.addItem("OpenAI API · IA online", "openai")
        self.provider.addItem("Configurar depois · sem conversa com IA", "none")
        index = self.provider.findData(settings.llm_provider)
        self.provider.setCurrentIndex(index if index >= 0 else 0)
        self.provider.currentIndexChanged.connect(self._update_provider_ui)
        form.addRow("Inteligência", self.provider)

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Cole sua chave da OpenAI API")
        form.addRow("Chave da API", self.api_key)

        self.key_help = QPushButton("Como obter uma chave")
        self.key_help.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://platform.openai.com/api-keys"))
        )
        form.addRow("", self.key_help)

        self.ollama_model = QLineEdit(settings.ollama_model or "qwen2.5:7b")
        self.ollama_model.setPlaceholderText("Ex.: qwen2.5:7b")
        form.addRow("Modelo local", self.ollama_model)

        self.ollama_install = QPushButton("Instalar Ollama neste computador")
        self.ollama_install.clicked.connect(self._install_ollama)
        form.addRow("", self.ollama_install)

        self.ollama_status = QLabel("")
        self.ollama_status.setWordWrap(True)
        self.ollama_status.setStyleSheet("color: #84c3d9;")
        form.addRow("", self.ollama_status)

        self.speech_provider = QComboBox()
        self.speech_provider.addItem("Local · baixar modelo de português (~31 MB)", "vosk")
        self.speech_provider.addItem("Online · Google transcreve o pedido de voz", "google")
        speech_index = self.speech_provider.findData(settings.speech_provider)
        self.speech_provider.setCurrentIndex(speech_index if speech_index >= 0 else 0)
        form.addRow("Reconhecimento de voz", self.speech_provider)
        root.addLayout(form)

        self.wake_word = QCheckBox("Concordo em deixar o AURIX ouvir “Hey Jarvis” em segundo plano")
        self.wake_word.setChecked(settings.wake_word_enabled)
        root.addWidget(self.wake_word)

        self.start_windows = QCheckBox("Iniciar o AURIX automaticamente com o Windows")
        self.start_windows.setChecked(settings.start_with_windows)
        root.addWidget(self.start_windows)

        privacy = QLabel(
            "Privacidade: a ativação por voz começa desativada. Ao habilitá-la, o detector "
            "processa o áudio localmente; com transcrição local, o pedido não é enviado a um "
            "serviço de reconhecimento. Se escolher Google, o áudio do pedido é enviado ao "
            "serviço para transcrição. O acesso ao microfone depende das configurações do Windows."
        )
        privacy.setWordWrap(True)
        privacy.setStyleSheet(
            "color: #8da9ba; background: #0a1c2b; border: 1px solid #1b4e64; "
            "border-radius: 8px; padding: 10px;"
        )
        root.addWidget(privacy)

        permissions = QPushButton("Abrir configurações de privacidade do microfone do Windows")
        permissions.clicked.connect(self._open_microphone_settings)
        root.addWidget(permissions)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        later = QPushButton("Continuar sem IA")
        later.clicked.connect(self._continue_without_ai)
        buttons.addWidget(later)
        save = QPushButton("Salvar e iniciar AURIX")
        save.setDefault(True)
        save.setStyleSheet(
            "QPushButton { background: #087b9b; color: white; border: 1px solid #4ddbf5; "
            "border-radius: 7px; padding: 9px 15px; font-weight: 600; } "
            "QPushButton:hover { background: #0c93b4; }"
        )
        save.clicked.connect(self._save)
        buttons.addWidget(save)
        root.addLayout(buttons)

        self.setStyleSheet(
            "QDialog { background: #071523; color: #d5f6ff; } "
            "QLabel { color: #cfe8f2; } "
            "QComboBox, QLineEdit { background: #081e30; color: #e6fbff; "
            "border: 1px solid #275a70; border-radius: 6px; padding: 8px; } "
            "QPushButton { background: #102a3b; color: #c8edf7; border: 1px solid #28586d; "
            "border-radius: 6px; padding: 7px 10px; } "
            "QPushButton:hover { background: #163c52; } "
            "QCheckBox { spacing: 8px; color: #d5f6ff; }"
        )
        self._update_provider_ui()

    @staticmethod
    def _ollama_locations() -> list[str]:
        local = os.getenv("LOCALAPPDATA", "")
        program_files = os.getenv("PROGRAMFILES", r"C:\Program Files")
        candidates = [
            shutil.which("ollama") or "",
            os.path.join(local, "Programs", "Ollama", "ollama.exe") if local else "",
            os.path.join(program_files, "Ollama", "ollama.exe"),
        ]
        return [path for path in candidates if path and os.path.isfile(path)]

    def _is_ollama_installed(self) -> bool:
        return bool(self._ollama_locations())

    def _update_provider_ui(self, *_args) -> None:
        provider = self.provider.currentData()
        self.api_key.setVisible(provider == "openai")
        self.key_help.setVisible(provider == "openai")
        self.ollama_model.setVisible(provider == "ollama")
        self.ollama_install.setVisible(provider == "ollama")
        self.ollama_status.setVisible(provider == "ollama")
        if provider == "ollama":
            self.ollama_status.setText(
                "Ollama detectado neste PC." if self._is_ollama_installed()
                else "O runtime de IA local precisa ser instalado uma vez. Você pode autorizar a instalação aqui."
            )

    def _install_ollama(self) -> None:
        if self._is_ollama_installed():
            QMessageBox.information(
                self, "Ollama encontrado",
                "O Ollama já está instalado. O AURIX verificará o modelo na primeira conversa."
            )
            self.ollama_status.setText("Ollama detectado neste PC.")
            return

        winget = shutil.which("winget")
        if not winget:
            self.ollama_status.setText(
                "O gerenciador winget não está disponível. Vou abrir o site oficial para você instalar."
            )
            QDesktopServices.openUrl(QUrl("https://ollama.com/download/windows"))
            QMessageBox.information(
                self, "Instalação do Ollama",
                "Não encontrei o winget neste Windows. O site oficial foi aberto; instale o Ollama "
                "e volte a esta janela. O AURIX não instala softwares externos sem sua autorização."
            )
            return

        answer = QMessageBox.question(
            self,
            "Autorizar instalação do Ollama",
            "O AURIX vai executar o gerenciador de pacotes do Windows para instalar "
            "Ollama.Ollama, necessário para usar uma IA local. O instalador oficial poderá "
            "mostrar permissões adicionais. Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._ollama_process = QProcess(self)
        self._ollama_process.setProgram(winget)
        self._ollama_process.setArguments([
            "install", "--id", "Ollama.Ollama", "--exact",
            "--accept-package-agreements", "--accept-source-agreements",
        ])
        self._ollama_process.readyReadStandardOutput.connect(self._read_ollama_output)
        self._ollama_process.readyReadStandardError.connect(self._read_ollama_output)
        self._ollama_process.finished.connect(self._ollama_finished)
        self.ollama_install.setEnabled(False)
        self.ollama_status.setText("Instalando Ollama pelo winget… Você pode continuar acompanhando aqui.")
        self._ollama_process.start()

    def _read_ollama_output(self) -> None:
        if not self._ollama_process:
            return
        output = bytes(self._ollama_process.readAllStandardOutput()).decode("utf-8", "replace")
        output += bytes(self._ollama_process.readAllStandardError()).decode("utf-8", "replace")
        if output.strip():
            self._ollama_output = (self._ollama_output + "\n" + output.strip())[-5000:]

    def _ollama_finished(self, exit_code: int, _exit_status) -> None:
        self.ollama_install.setEnabled(True)
        if exit_code == 0 and self._is_ollama_installed():
            self.ollama_status.setText("Instalação concluída. O AURIX poderá baixar o modelo de IA ao iniciar uma conversa.")
            QMessageBox.information(
                self, "Ollama instalado",
                "O runtime Ollama foi instalado. O AURIX tentará usar esse serviço e buscar "
                "o modelo escolhido quando você iniciar uma conversa."
            )
        else:
            self.ollama_status.setText("A instalação não foi confirmada. Confira a conexão e tente novamente.")
            QMessageBox.warning(
                self, "Instalação do Ollama",
                "Não consegui confirmar que o Ollama foi instalado. Se o instalador do Ollama "
                "abriu uma janela do Windows, conclua-a e clique em Instalar novamente.\n\n"
                + self._ollama_output[-1200:]
            )

    def _open_microphone_settings(self) -> None:
        if not QDesktopServices.openUrl(QUrl("ms-settings:privacy-microphone")):
            QMessageBox.information(
                self,
                "Permissão de microfone",
                "Abra Configurações do Windows → Privacidade e segurança → Microfone e "
                "permita o acesso para aplicativos da área de trabalho.",
            )

    def _persist(self, provider: str) -> bool:
        if provider == "openai":
            api_key = self.api_key.text().strip()
            if not api_key:
                try:
                    import keyring
                    api_key = keyring.get_password("AURIX AI", "openai_api_key") or ""
                except Exception:
                    api_key = ""
            if not api_key:
                QMessageBox.warning(
                    self, "Chave necessária",
                    "Cole uma chave da OpenAI API ou escolha Ollama para usar um modelo local. "
                    "A API pode gerar custos conforme o seu uso.",
                )
                return False
            try:
                import keyring
                keyring.set_password("AURIX AI", "openai_api_key", api_key)
            except Exception as exc:
                QMessageBox.critical(
                    self, "Não foi possível proteger a chave",
                    "O AURIX não vai gravar sua chave em texto puro. Verifique o Gerenciador "
                    f"de Credenciais do Windows e tente novamente.\n\nDetalhe: {exc}",
                )
                return False

        if provider == "ollama" and not self._is_ollama_installed():
            QMessageBox.warning(
                self, "Ollama não instalado",
                "Clique em “Instalar Ollama neste computador” e conclua a instalação antes de salvar."
            )
            return False

        self.settings.llm_provider = provider
        self.settings.ollama_model = self.ollama_model.text().strip() or "llama3.2"
        self.settings.speech_provider = str(self.speech_provider.currentData())
        self.settings.wake_word_enabled = self.wake_word.isChecked()
        self.settings.start_with_windows = self.start_windows.isChecked()
        self.settings.first_run_complete = True
        self.settings.save()
        self.accept()
        return True

    def _save(self) -> None:
        self._persist(str(self.provider.currentData()))

    def _continue_without_ai(self) -> None:
        self.settings.wake_word_enabled = self.wake_word.isChecked()
        self.settings.start_with_windows = self.start_windows.isChecked()
        self.settings.speech_provider = str(self.speech_provider.currentData())
        self.settings.llm_provider = "none"
        self.settings.first_run_complete = True
        self.settings.save()
        self.accept()
