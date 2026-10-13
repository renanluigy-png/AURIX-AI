"""First-run onboarding: provider choice, voice consent, and local preferences."""

from __future__ import annotations

from PySide6.QtCore import QUrl
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
        self.setWindowTitle("Configuração inicial · AURIX AI")
        self.setMinimumWidth(560)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 22)
        root.setSpacing(13)

        title = QLabel("Vamos preparar o AURIX")
        title.setFont(QFont("Segoe UI", 19, QFont.Weight.DemiBold))
        title.setStyleSheet("color: #80f0ff;")
        root.addWidget(title)

        intro = QLabel(
            "O aplicativo já inclui o runtime e suas bibliotecas. Nesta etapa você escolhe "
            "como será a inteligência e o comportamento do microfone."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #b8cedb;")
        root.addWidget(intro)

        form = QFormLayout()
        form.setSpacing(10)
        self.provider = QComboBox()
        self.provider.addItem("OpenAI API · IA online", "openai")
        self.provider.addItem("Ollama · IA local no computador", "ollama")
        self.provider.addItem("Configurar depois · comandos básicos", "none")
        index = self.provider.findData(settings.llm_provider)
        self.provider.setCurrentIndex(index if index >= 0 else 0)
        self.provider.currentIndexChanged.connect(self._update_provider_ui)
        form.addRow("Inteligência", self.provider)

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Cole sua chave da OpenAI API")
        form.addRow("Chave da API", self.api_key)

        key_actions = QHBoxLayout()
        self.key_help = QPushButton("Como obter uma chave")
        self.key_help.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://platform.openai.com/api-keys"))
        )
        key_actions.addWidget(self.key_help)
        key_actions.addStretch(1)
        form.addRow("", key_actions)

        self.ollama_model = QLineEdit(settings.ollama_model or "llama3.2")
        self.ollama_model.setPlaceholderText("Ex.: llama3.2")
        form.addRow("Modelo local", self.ollama_model)

        self.ollama_help = QPushButton("Instalar / obter o Ollama")
        self.ollama_help.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://ollama.com/download/windows"))
        )
        form.addRow("", self.ollama_help)

        self.speech_provider = QComboBox()
        self.speech_provider.addItem("Local · baixar modelo de português (~31 MB)", "vosk")
        self.speech_provider.addItem("Online · Google transcreve o pedido de voz", "google")
        speech_index = self.speech_provider.findData(settings.speech_provider)
        self.speech_provider.setCurrentIndex(speech_index if speech_index >= 0 else 0)
        form.addRow("Reconhecimento de voz", self.speech_provider)
        root.addLayout(form)

        self.wake_word = QCheckBox("Ativar microfone para ouvir “Hey Jarvis”")
        self.wake_word.setChecked(settings.wake_word_enabled)
        root.addWidget(self.wake_word)

        self.start_windows = QCheckBox("Iniciar o AURIX automaticamente com o Windows")
        self.start_windows.setChecked(settings.start_with_windows)
        root.addWidget(self.start_windows)

        privacy = QLabel(
            "Privacidade: o detector da palavra de ativação processa o áudio localmente. "
            "Com reconhecimento local, o pedido continua no computador após a ativação; "
            "com Google, o áudio do pedido é enviado ao serviço para transcrição. "
            "Você pode pausar a escuta no menu do AURIX a qualquer momento."
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

    def _update_provider_ui(self, *_args) -> None:
        provider = self.provider.currentData()
        self.api_key.setVisible(provider == "openai")
        self.key_help.setVisible(provider == "openai")
        self.ollama_model.setVisible(provider == "ollama")
        self.ollama_help.setVisible(provider == "ollama")

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
                    self,
                    "Chave necessária",
                    "Cole uma chave da OpenAI API ou escolha Ollama para usar um modelo local. "
                    "A API pode gerar custos conforme o seu uso.",
                )
                return False
            try:
                import keyring

                keyring.set_password("AURIX AI", "openai_api_key", api_key)
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "Não foi possível proteger a chave",
                    "O AURIX não vai gravar sua chave em texto puro. Verifique o Gerenciador "
                    f"de Credenciais do Windows e tente novamente.\n\nDetalhe: {exc}",
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
