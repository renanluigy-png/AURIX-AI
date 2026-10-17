"""A premium, lightweight floating HUD for AURIX AI."""

from __future__ import annotations

import html
import math
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QPoint
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class CoreWidget(QWidget):
    """A restrained animated holographic core, designed to stay inexpensive to paint."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._angle = 0.0
        self._mode = "idle"
        self.setFixedSize(158, 158)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._advance)

    def set_mode(self, mode: str) -> None:
        if mode not in {"idle", "listening", "thinking", "warning", "speaking"}:
            mode = "idle"
        if self._mode != mode:
            self._mode = mode
            self.update()

    def _advance(self) -> None:
        self._angle = (self._angle + (1.0 if self._mode == "idle" else 2.0)) % 360
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center = self.rect().center()
        cx, cy = float(center.x()), float(center.y())
        radius = min(self.width(), self.height()) * 0.40

        if self._mode == "warning":
            accent = QColor(255, 178, 110)
        elif self._mode == "thinking":
            accent = QColor(164, 153, 255)
        else:
            accent = QColor(92, 226, 255)

        glow = QRadialGradient(cx, cy, radius * 1.48)
        glow.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 42))
        glow.setColorAt(0.52, QColor(24, 117, 158, 23))
        glow.setColorAt(1.0, QColor(4, 14, 27, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(cx - radius * 1.48, cy - radius * 1.48, radius * 2.96, radius * 2.96))

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(86, 197, 224, 100), 1.0))
        painter.drawEllipse(QRectF(cx - radius * 1.12, cy - radius * 1.12, radius * 2.24, radius * 2.24))
        painter.setPen(QPen(QColor(83, 204, 232, 70), 1.0))
        painter.drawEllipse(QRectF(cx - radius * 0.92, cy - radius * 0.92, radius * 1.84, radius * 1.84))

        # One rotation and twelve ticks are enough for a precise, understated HUD look.
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._angle)
        for index in range(12):
            major = index % 3 == 0
            painter.setPen(
                QPen(
                    QColor(accent.red(), accent.green(), accent.blue(), 185 if major else 75),
                    1.5 if major else 0.8,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )
            painter.drawLine(0, -int(radius * 1.03), 0, -int(radius * (0.91 if major else 0.96)))
            painter.rotate(30)
        painter.restore()

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self._angle * 0.7)
        painter.setPen(
            QPen(
                QColor(accent.red(), accent.green(), accent.blue(), 190),
                2.0,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        painter.drawArc(
            QRectF(-radius * 0.80, -radius * 0.80, radius * 1.60, radius * 1.60),
            18 * 16,
            112 * 16,
        )
        painter.drawArc(
            QRectF(-radius * 0.80, -radius * 0.80, radius * 1.60, radius * 1.60),
            205 * 16,
            58 * 16,
        )
        painter.restore()

        lens_radius = radius * 0.62
        lens = QRadialGradient(cx - lens_radius * 0.28, cy - lens_radius * 0.32, lens_radius * 1.45)
        lens.setColorAt(0.0, QColor(176, 250, 255, 238))
        lens.setColorAt(0.20, QColor(59, 185, 221, 243))
        lens.setColorAt(0.68, QColor(8, 54, 82, 248))
        lens.setColorAt(1.0, QColor(4, 17, 31, 252))
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 220), 1.1))
        painter.setBrush(lens)
        painter.drawEllipse(QRectF(cx - lens_radius, cy - lens_radius, lens_radius * 2, lens_radius * 2))

        painter.setPen(QPen(QColor(219, 255, 255, 225), 1.25, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if self._mode in {"listening", "speaking"}:
            width = radius * 0.42
            points = []
            for index in range(13):
                x = cx - width + (2 * width * index / 12)
                envelope = 0.30 + 0.70 * abs(math.sin(index * 0.38 + 0.4))
                y = cy + math.sin(index * 0.87 + self._angle * 0.11) * radius * 0.17 * envelope
                points.append((int(x), int(y)))
            for first, second in zip(points, points[1:]):
                painter.drawLine(first[0], first[1], second[0], second[1])
        else:
            painter.drawLine(int(cx - radius * 0.18), int(cy), int(cx + radius * 0.18), int(cy))
            painter.drawLine(int(cx), int(cy - radius * 0.18), int(cx), int(cy + radius * 0.18))
        painter.end()


class HUDWindow(QMainWindow):
    """Frameless assistant window. Closing it hides the HUD but keeps AURIX running."""

    command_submitted = Signal(str, bool)
    settings_requested = Signal()
    voice_toggle_requested = Signal()
    listen_once_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AURIX AI")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(790, 660)
        self.resize(900, 720)
        self._drag_position: QPoint | None = None
        self._voice_enabled = False
        self._message_count = 0
        self.status_label_text = "Pronto para ajudar."
        self._quick_buttons: list[QPushButton] = []

        shell = QFrame()
        shell.setObjectName("shell")
        root = QVBoxLayout(shell)
        root.setContentsMargins(23, 20, 23, 17)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(11)
        self.brand_mark = QLabel("A")
        self.brand_mark.setObjectName("brandMark")
        self.brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_mark.setFixedSize(38, 38)
        header.addWidget(self.brand_mark)

        brand_stack = QVBoxLayout()
        brand_stack.setSpacing(1)
        brand = QLabel("AURIX")
        brand.setObjectName("brand")
        tagline = QLabel("PERSONAL INTELLIGENCE")
        tagline.setObjectName("tagline")
        brand_stack.addWidget(brand)
        brand_stack.addWidget(tagline)
        header.addLayout(brand_stack)
        header.addStretch(1)

        self.status_pill = QLabel("●  ONLINE")
        self.status_pill.setObjectName("statusPill")
        self.status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.status_pill)

        self.settings_button = QPushButton("⚙")
        self.settings_button.setObjectName("iconButton")
        self.settings_button.setToolTip("Configurar inteligência e voz")
        self.settings_button.setAccessibleName("Configurações do AURIX")
        self.settings_button.clicked.connect(self.settings_requested.emit)
        header.addWidget(self.settings_button)

        self.hide_button = QPushButton("—")
        self.hide_button.setObjectName("iconButton")
        self.hide_button.setToolTip("Ocultar a interface; AURIX continua em segundo plano")
        self.hide_button.setAccessibleName("Ocultar AURIX")
        self.hide_button.clicked.connect(self.hide)
        header.addWidget(self.hide_button)
        root.addLayout(header)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        root.addWidget(divider)

        hero_panel = QFrame()
        hero_panel.setObjectName("heroPanel")
        hero = QHBoxLayout(hero_panel)
        hero.setContentsMargins(18, 14, 22, 14)
        hero.setSpacing(19)
        hero.addWidget(CoreWidget(), 0, Qt.AlignmentFlag.AlignVCenter)
        self.core = hero.itemAt(0).widget()

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(7)
        eyebrow = QLabel("SEU COPILOTO PARA DESKTOP")
        eyebrow.setObjectName("eyebrow")
        hero_copy.addWidget(eyebrow)

        self.hero_title = QLabel("O que vamos fazer hoje?")
        self.hero_title.setObjectName("heroTitle")
        self.hero_title.setWordWrap(True)
        hero_copy.addWidget(self.hero_title)

        self.hero_description = QLabel(
            "Converse normalmente. AURIX entende o pedido, decide quando usar ferramentas "
            "e informa o resultado sem inventar ações."
        )
        self.hero_description.setObjectName("heroDescription")
        self.hero_description.setWordWrap(True)
        hero_copy.addWidget(self.hero_description)

        capability_row = QHBoxLayout()
        capability_row.setSpacing(7)
        for caption in ("IA GENERATIVA", "AÇÕES VALIDADAS", "VOZ OPCIONAL"):
            chip = QLabel(caption)
            chip.setObjectName("capabilityChip")
            capability_row.addWidget(chip)
        capability_row.addStretch(1)
        hero_copy.addLayout(capability_row)

        self.engine_value = QLabel("MODELO PRONTO QUANDO CONFIGURADO")
        self.engine_value.setObjectName("engineLabel")
        hero_copy.addWidget(self.engine_value)
        hero.addLayout(hero_copy, 1)
        root.addWidget(hero_panel)

        section_row = QHBoxLayout()
        section_title = QLabel("ATALHOS")
        section_title.setObjectName("sectionTitle")
        section_row.addWidget(section_title)
        section_row.addStretch(1)
        section_hint = QLabel("UMA AÇÃO SIMPLES, SEM ESPERAR O MODELO")
        section_hint.setObjectName("sectionHint")
        section_row.addWidget(section_hint)
        root.addLayout(section_row)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        for caption, request in (
            ("♫  Spotify", "Abra o Spotify"),
            ("▣  WhatsApp", "Abra o WhatsApp"),
            ("⌕  Pesquisar", "Pesquise na web por assuntos atuais"),
            ("▤  Documentos", "Abra a pasta de documentos"),
        ):
            button = QPushButton(caption)
            button.setObjectName("quickButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, prompt=request: self.command_submitted.emit(prompt, False)
            )
            actions.addWidget(button, 1)
            self._quick_buttons.append(button)
        root.addLayout(actions)

        conversation_header = QHBoxLayout()
        conversation_title = QLabel("CONVERSA")
        conversation_title.setObjectName("sectionTitle")
        conversation_header.addWidget(conversation_title)
        conversation_header.addStretch(1)
        self.session_label = QLabel("HISTÓRICO DESTA SESSÃO")
        self.session_label.setObjectName("sectionHint")
        conversation_header.addWidget(self.session_label)
        root.addLayout(conversation_header)

        self.chat = QTextBrowser()
        self.chat.setObjectName("chatHistory")
        self.chat.setOpenExternalLinks(False)
        self.chat.setFrameShape(QFrame.Shape.NoFrame)
        self.chat.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat.document().setMaximumBlockCount(500)
        root.addWidget(self.chat, 1)

        composer_frame = QFrame()
        composer_frame.setObjectName("composerFrame")
        composer = QHBoxLayout(composer_frame)
        composer.setContentsMargins(8, 7, 8, 7)
        composer.setSpacing(7)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("commandInput")
        self.input_field.setPlaceholderText("Peça algo, faça uma pergunta ou descreva uma tarefa…")
        self.input_field.setClearButtonEnabled(True)
        self.input_field.returnPressed.connect(self._submit_typed)
        composer.addWidget(self.input_field, 1)

        self.voice_button = QPushButton("◉  FALAR")
        self.voice_button.setObjectName("listenButton")
        self.voice_button.setToolTip("Ditar um pedido agora, sem precisar dizer Hey Jarvis")
        self.voice_button.clicked.connect(self.listen_once_requested.emit)
        composer.addWidget(self.voice_button)

        self.wake_button = QPushButton("HEY JARVIS · OFF")
        self.wake_button.setObjectName("voiceButton")
        self.wake_button.setToolTip("Ativar ou pausar a palavra de ativação em segundo plano")
        self.wake_button.clicked.connect(self.voice_toggle_requested.emit)
        composer.addWidget(self.wake_button)

        self.send_button = QPushButton("ENVIAR  ↗")
        self.send_button.setObjectName("sendButton")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.clicked.connect(self._submit_typed)
        composer.addWidget(self.send_button)
        root.addWidget(composer_frame)

        footer = QHBoxLayout()
        footer_left = QLabel("AURIX CORE  ·  CONTROLE LOCAL VALIDADO")
        footer_left.setObjectName("footer")
        footer_key = QLabel("CTRL  +  ALT  +  ESPAÇO")
        footer_key.setObjectName("footer")
        footer.addWidget(footer_left)
        footer.addStretch(1)
        footer.addWidget(footer_key)
        root.addLayout(footer)

        self.setCentralWidget(shell)
        shell.mousePressEvent = self._shell_mouse_press
        shell.mouseMoveEvent = self._shell_mouse_move
        shell.mouseReleaseEvent = self._shell_mouse_release

        self.setStyleSheet(
            """
            QFrame#shell {
                background: #07121f;
                border: 1px solid #214053;
                border-radius: 20px;
            }
            QLabel { color: #dcecf5; background: transparent; }
            QLabel#brandMark {
                color: #081723; background: #8deaff; border: 1px solid #bcf6ff;
                border-radius: 12px; font-size: 22px; font-weight: 800;
            }
            QLabel#brand {
                color: #e9f7fb; font-family: "Segoe UI"; font-size: 19px;
                font-weight: 700; letter-spacing: 4px;
            }
            QLabel#tagline { color: #648398; font-size: 8px; letter-spacing: 2px; }
            QLabel#statusPill {
                color: #8eeaff; background: #0d2636;
                border: 1px solid #244c60; border-radius: 10px;
                padding: 7px 11px; font-size: 9px; font-weight: 700; letter-spacing: 1px;
            }
            QLabel#statusPill[state="listening"] {
                color: #a5f8e5; background: #0e302e; border-color: #28675e;
            }
            QLabel#statusPill[state="thinking"] {
                color: #d5cbff; background: #211f3a; border-color: #49436d;
            }
            QLabel#statusPill[state="warning"] {
                color: #ffd0a2; background: #35251b; border-color: #76513a;
            }
            QPushButton#iconButton {
                min-width: 34px; max-width: 34px; min-height: 33px; max-height: 33px;
                color: #a8bfcb; background: #0b1c2a; border: 1px solid #233b4b;
                border-radius: 9px; font-size: 15px;
            }
            QPushButton#iconButton:hover {
                color: #effcff; background: #15374a; border-color: #478ba4;
            }
            QFrame#divider { background: #1c3445; border: 0; }
            QFrame#heroPanel {
                background: #0a1a29; border: 1px solid #1b394c; border-radius: 16px;
            }
            QLabel#eyebrow {
                color: #66bed3; font-size: 9px; font-weight: 700; letter-spacing: 2px;
            }
            QLabel#heroTitle {
                color: #f0f8fc; font-size: 24px; font-weight: 600; letter-spacing: -0.3px;
            }
            QLabel#heroDescription { color: #9bb4c3; font-size: 11px; }
            QLabel#capabilityChip {
                color: #84c8d9; background: #102839; border: 1px solid #214658;
                border-radius: 6px; padding: 5px 7px; font-size: 7px;
                font-weight: 700; letter-spacing: 0.6px;
            }
            QLabel#engineLabel { color: #5d899e; font-size: 8px; letter-spacing: 1px; }
            QLabel#sectionTitle {
                color: #c2dfe9; font-size: 9px; font-weight: 700; letter-spacing: 2px;
            }
            QLabel#sectionHint { color: #5d8193; font-size: 8px; letter-spacing: 0.7px; }
            QTextBrowser#chatHistory {
                background: #081520; color: #d3e6ee; border: 1px solid #193343;
                border-radius: 12px; padding: 9px; selection-background-color: #176681;
                font-family: "Segoe UI"; font-size: 12px;
            }
            QFrame#composerFrame {
                background: #091a28; border: 1px solid #234a5d; border-radius: 13px;
            }
            QLineEdit#commandInput {
                min-height: 24px; background: transparent; color: #e6f4f8;
                border: 0; padding: 8px 9px; selection-background-color: #087fa5;
                font-size: 11px;
            }
            QPushButton#quickButton {
                color: #b1d0dc; background: #0b1e2c; border: 1px solid #203c4d;
                border-radius: 9px; padding: 10px 11px; font-size: 10px; font-weight: 600;
            }
            QPushButton#quickButton:hover {
                color: #f0fcff; background: #103347; border-color: #3d8198;
            }
            QPushButton#quickButton:disabled { color: #4e7181; background: #0b1924; }
            QPushButton#listenButton {
                color: #061824; background: #8ce9fb; border: 1px solid #b8f5ff;
                border-radius: 9px; padding: 10px 12px; font-size: 9px; font-weight: 800;
            }
            QPushButton#listenButton:hover { background: #b5f4ff; }
            QPushButton#listenButton:disabled {
                color: #65818e; background: #17303d; border-color: #254452;
            }
            QPushButton#voiceButton {
                color: #9dc5d3; background: #102433; border: 1px solid #254759;
                border-radius: 9px; padding: 10px 10px; font-size: 8px; font-weight: 700;
            }
            QPushButton#voiceButton[enabled="true"] {
                color: #a6f7e4; background: #12352f; border-color: #2b786c;
            }
            QPushButton#sendButton {
                color: #e6f8fc; background: #123c51; border: 1px solid #367b96;
                border-radius: 9px; padding: 10px 13px; font-size: 9px; font-weight: 700;
            }
            QPushButton#sendButton:hover { background: #19556e; border-color: #56bbd6; }
            QPushButton#sendButton:disabled {
                color: #65818e; background: #102432; border-color: #213a49;
            }
            QLabel#footer { color: #496b7d; font-size: 8px; letter-spacing: 0.8px; }
            """
        )

        self.set_status("Pronto para ajudar.")
        self.set_voice_enabled(False)
        self.append_message(
            "AURIX",
            "Olá. Sou sua assistente de desktop. Peça algo em linguagem natural; quando uma ação "
            "não estiver disponível, vou explicar o limite em vez de fingir que a executei.",
        )

    def _shell_mouse_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 60:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            event.ignore()

    def _shell_mouse_move(self, event) -> None:
        if self._drag_position is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
        else:
            event.ignore()

    def _shell_mouse_release(self, event) -> None:
        self._drag_position = None
        event.accept()

    def show_hud(self) -> None:
        screen = QApplication.primaryScreen()
        if screen and not self.isVisible():
            area = screen.availableGeometry()
            self.move(area.center().x() - self.width() // 2, area.center().y() - self.height() // 2)
        self.show()
        self.raise_()
        self.activateWindow()
        self.input_field.setFocus()

    def set_status(self, text: str) -> None:
        self.status_label_text = text
        lower = text.casefold()
        if any(word in lower for word in ("ouvindo", "ativado", "transcrevendo", "capturando")):
            state, label, mode = "listening", "●  OUVINDO", "listening"
        elif any(word in lower for word in ("processando", "pensando", "baixando", "verificando modelo", "preparando ia", "modelo pronto")):
            state, label, mode = "thinking", "◌  PROCESSANDO", "thinking"
        elif any(word in lower for word in ("erro", "falha", "não consegui", "nao consegui", "recusada", "não foi possível")):
            state, label, mode = "warning", "●  ATENÇÃO", "warning"
        else:
            state, label, mode = "ready", "●  ONLINE", "idle"

        self.status_pill.setText(label)
        self.status_pill.setProperty("state", state)
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)
        self.core.set_mode(mode)

        if state == "listening":
            self.hero_title.setText("Estou ouvindo você.")
            self.engine_value.setText("CANAL DE VOZ ATIVO")
        elif state == "thinking":
            self.hero_title.setText("Estou cuidando disso.")
            self.engine_value.setText(text.upper()[:100])
        elif state == "warning":
            self.hero_title.setText("Preciso conferir algo.")
            self.engine_value.setText("VEJA O STATUS OU A RESPOSTA")
        else:
            self.hero_title.setText("O que vamos fazer hoje?")
            self.engine_value.setText("IA GENERATIVA · FERRAMENTAS CONTROLADAS")

    def set_response(self, text: str) -> None:
        self.append_message("AURIX", text)

    def append_message(self, speaker: str, text: str) -> None:
        safe_text = html.escape(str(text)).replace("\n", "<br>")
        is_user = speaker.casefold() == "você"
        bubble_color = "#102a3a" if is_user else "#0d202d"
        border_color = "#2c6176" if is_user else "#1d3c4c"
        title_color = "#9adff0" if is_user else "#83dce9"
        alignment = "right" if is_user else "left"
        label = "VOCÊ" if is_user else (speaker.upper() if speaker else "AURIX")
        timestamp = datetime.now().strftime("%H:%M")
        self.chat.append(
            f'<div style="margin:7px 3px 12px 3px; text-align:{alignment};">'
            f'<div style="color:{title_color}; font-size:9px; font-weight:700; letter-spacing:1px; '
            f'margin-bottom:4px;">{html.escape(label)} <span style="color:#527386; font-weight:400;">· {timestamp}</span></div>'
            f'<div style="display:inline-block; max-width:94%; background:{bubble_color}; '
            f'border:1px solid {border_color}; border-radius:11px; padding:9px 12px; '
            f'color:#d7e8ef; font-size:11px; line-height:1.45;">{safe_text}</div></div>'
        )
        self._message_count += 1
        self.session_label.setText(f"{self._message_count:02d} MENSAGENS NESTA SESSÃO")
        bar = self.chat.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_voice_enabled(self, enabled: bool) -> None:
        self._voice_enabled = enabled
        self.wake_button.setText("HEY JARVIS · ON" if enabled else "HEY JARVIS · OFF")
        self.wake_button.setProperty("enabled", "true" if enabled else "false")
        self.wake_button.style().unpolish(self.wake_button)
        self.wake_button.style().polish(self.wake_button)
        self.wake_button.setToolTip(
            "Pausar a palavra de ativação em segundo plano"
            if enabled else "Ativar a palavra de ativação em segundo plano"
        )

    def set_busy(self, busy: bool) -> None:
        self.send_button.setEnabled(not busy)
        self.input_field.setEnabled(not busy)
        self.voice_button.setEnabled(not busy)
        for button in self._quick_buttons:
            button.setEnabled(not busy)
        self.send_button.setText("AGUARDE…" if busy else "ENVIAR  ↗")
        if busy:
            self.set_status("Processando solicitação…")

    def _submit_typed(self) -> None:
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.command_submitted.emit(text, False)

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
