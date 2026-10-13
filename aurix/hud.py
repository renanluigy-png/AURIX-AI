"""Premium floating HUD for AURIX AI.

Visual direction: restrained cinematic sci-fi, inspired by holographic control
interfaces without copying protected movie assets. The HUD stays lightweight,
frameless, readable, and usable as a conversation window.
"""

from __future__ import annotations

import html
import math
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QPoint
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
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
    """Slow animated cyan core with orbit rings, ticks, and a quiet center glow."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._angle = 0.0
        self._mode = "idle"
        self.setMinimumSize(172, 172)
        self.setMaximumSize(190, 190)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._timer = QTimer(self)
        self._timer.setInterval(42)
        self._timer.timeout.connect(self._advance)

    def set_mode(self, mode: str) -> None:
        if mode not in {"idle", "listening", "thinking", "speaking", "warning"}:
            mode = "idle"
        if self._mode != mode:
            self._mode = mode
            self.update()

    def _advance(self) -> None:
        step = 1.15 if self._mode == "idle" else 2.4
        self._angle = (self._angle + step) % 360
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
        radius = min(self.width(), self.height()) * 0.405

        # The glow intensifies while the assistant listens or thinks.
        intensity = 88 if self._mode in {"listening", "thinking", "speaking"} else 48
        if self._mode == "warning":
            accent = QColor(255, 177, 96)
        else:
            accent = QColor(82, 225, 255)

        glow = QRadialGradient(cx, cy, radius * 1.5)
        glow.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), intensity))
        glow.setColorAt(0.46, QColor(12, 127, 181, 34))
        glow.setColorAt(1.0, QColor(3, 14, 28, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(
            QRectF(cx - radius * 1.5, cy - radius * 1.5, radius * 3, radius * 3)
        )

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(68, 199, 232, 135), 1.0))
        painter.drawEllipse(QRectF(cx - radius * 1.10, cy - radius * 1.10, radius * 2.20, radius * 2.20))
        painter.setPen(QPen(QColor(86, 222, 249, 95), 1.0))
        painter.drawEllipse(QRectF(cx - radius * 0.91, cy - radius * 0.91, radius * 1.82, radius * 1.82))

        # Segmented outer orbit.
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._angle)
        for start, span, width, alpha in (
            (12, 76, 2.2, 220),
            (112, 34, 1.5, 130),
            (174, 54, 2.0, 190),
            (256, 46, 1.5, 150),
        ):
            painter.setPen(
                QPen(
                    QColor(accent.red(), accent.green(), accent.blue(), alpha),
                    width,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )
            painter.drawArc(
                QRectF(-radius, -radius, radius * 2, radius * 2),
                start * 16,
                span * 16,
            )
        painter.restore()

        # Fine calibration ticks.
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self._angle * 0.35)
        for angle in range(0, 360, 15):
            painter.save()
            painter.rotate(angle)
            long_tick = angle % 45 == 0
            painter.setPen(
                QPen(
                    QColor(125, 229, 249, 165 if long_tick else 78),
                    1.2 if long_tick else 0.8,
                )
            )
            painter.drawLine(0, int(-radius * 0.99), 0, int(-radius * (0.92 if long_tick else 0.95)))
            painter.restore()
        painter.restore()

        # Central glass-like lens.
        lens_radius = radius * 0.59
        lens = QRadialGradient(cx - lens_radius * 0.22, cy - lens_radius * 0.28, lens_radius * 1.35)
        lens.setColorAt(0.0, QColor(123, 248, 255, 238))
        lens.setColorAt(0.18, QColor(37, 176, 220, 238))
        lens.setColorAt(0.64, QColor(9, 56, 91, 247))
        lens.setColorAt(1.0, QColor(3, 15, 30, 250))
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 205), 1.2))
        painter.setBrush(lens)
        painter.drawEllipse(QRectF(cx - lens_radius, cy - lens_radius, lens_radius * 2, lens_radius * 2))

        # A restrained waveform / crosshair in the core.
        painter.setPen(QPen(QColor(202, 255, 255, 235), 1.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        wave_width = radius * 0.43
        if self._mode in {"listening", "speaking"}:
            points = []
            for index in range(17):
                x = cx - wave_width + (2 * wave_width * index / 16)
                wave = math.sin(index * 0.82 + self._angle * 0.10)
                envelope = 0.35 + 0.65 * abs(math.sin(index * 0.32 + 0.5))
                y = cy + wave * radius * 0.19 * envelope
                points.append((int(x), int(y)))
            for first, second in zip(points, points[1:]):
                painter.drawLine(first[0], first[1], second[0], second[1])
        else:
            painter.drawLine(int(cx - radius * 0.17), int(cy), int(cx + radius * 0.17), int(cy))
            painter.drawLine(int(cx), int(cy - radius * 0.17), int(cx), int(cy + radius * 0.17))
        painter.end()


class HUDWindow(QMainWindow):
    """Frameless premium chat/HUD window; closing it only hides the assistant."""

    command_submitted = Signal(str, bool)
    settings_requested = Signal()
    voice_toggle_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AURIX AI")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(720, 600)
        self.resize(820, 680)
        self._drag_position: QPoint | None = None
        self._voice_enabled = False
        self._message_count = 0

        shell = QFrame()
        shell.setObjectName("shell")
        root = QVBoxLayout(shell)
        root.setContentsMargins(27, 23, 27, 20)
        root.setSpacing(15)

        # Top brand bar.
        header = QHBoxLayout()
        header.setSpacing(12)
        brand_stack = QVBoxLayout()
        brand_stack.setSpacing(1)
        brand = QLabel("A U R I X")
        brand.setObjectName("brand")
        tagline = QLabel("PERSONAL INTELLIGENCE")
        tagline.setObjectName("tagline")
        brand_stack.addWidget(brand)
        brand_stack.addWidget(tagline)
        header.addLayout(brand_stack)
        header.addStretch(1)

        self.status_pill = QLabel("●  STANDBY")
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
        self.hide_button.setToolTip("Ocultar interface; AURIX continua em segundo plano")
        self.hide_button.setAccessibleName("Ocultar AURIX")
        self.hide_button.clicked.connect(self.hide)
        header.addWidget(self.hide_button)
        root.addLayout(header)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        root.addWidget(divider)

        # Hero: orb + generous negative space and a concise system message.
        hero = QHBoxLayout()
        hero.setSpacing(22)
        self.core = CoreWidget()
        hero.addWidget(self.core, 0, Qt.AlignmentFlag.AlignVCenter)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(8)
        eyebrow = QLabel("DESKTOP INTELLIGENCE  /  01")
        eyebrow.setObjectName("eyebrow")
        hero_copy.addWidget(eyebrow)

        self.hero_title = QLabel("Pronto para pensar com você.")
        self.hero_title.setObjectName("heroTitle")
        self.hero_title.setWordWrap(True)
        hero_copy.addWidget(self.hero_title)

        self.hero_description = QLabel(
            "Converse normalmente. Quando uma tarefa exigir ação, eu escolho uma ferramenta "
            "disponível e retorno com o resultado."
        )
        self.hero_description.setObjectName("heroDescription")
        self.hero_description.setWordWrap(True)
        hero_copy.addWidget(self.hero_description)

        meta = QHBoxLayout()
        meta.setSpacing(7)
        for label in ("NATURAL LANGUAGE", "LOCAL TOOLS", "PRIVATE BY DESIGN"):
            chip = QLabel(label)
            chip.setObjectName("metaChip")
            meta.addWidget(chip)
        meta.addStretch(1)
        hero_copy.addLayout(meta)
        hero_copy.addStretch(1)
        hero.addLayout(hero_copy, 1)
        root.addLayout(hero)

        session_header = QHBoxLayout()
        session_title = QLabel("CONVERSA")
        session_title.setObjectName("sectionTitle")
        session_header.addWidget(session_title)
        session_header.addStretch(1)
        self.session_label = QLabel("SESSÃO LOCAL")
        self.session_label.setObjectName("sectionMeta")
        session_header.addWidget(self.session_label)
        root.addLayout(session_header)

        self.chat = QTextBrowser()
        self.chat.setObjectName("chatHistory")
        self.chat.setOpenExternalLinks(False)
        self.chat.setFrameShape(QFrame.Shape.NoFrame)
        self.chat.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat.setPlaceholderText("Sua conversa aparecerá aqui.")
        root.addWidget(self.chat, 1)

        composer = QHBoxLayout()
        composer.setSpacing(9)
        self.input_field = QLineEdit()
        self.input_field.setObjectName("commandInput")
        self.input_field.setPlaceholderText("Peça qualquer coisa…")
        self.input_field.setClearButtonEnabled(True)
        self.input_field.returnPressed.connect(self._submit_typed)
        composer.addWidget(self.input_field, 1)

        self.voice_button = QPushButton("VOZ OFF")
        self.voice_button.setObjectName("voiceButton")
        self.voice_button.setToolTip("Ativar ou pausar a palavra de ativação")
        self.voice_button.clicked.connect(self.voice_toggle_requested.emit)
        composer.addWidget(self.voice_button)

        self.send_button = QPushButton("ENVIAR  ↗")
        self.send_button.setObjectName("sendButton")
        self.send_button.clicked.connect(self._submit_typed)
        composer.addWidget(self.send_button)
        root.addLayout(composer)

        footer = QHBoxLayout()
        footer_left = QLabel("AURIX AI  ·  PERSONAL DESKTOP ASSISTANT")
        footer_left.setObjectName("footer")
        footer_key = QLabel("CTRL  +  ALT  +  SPACE")
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
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #06111f, stop:0.52 #081a2b, stop:1 #040b14);
                border: 1px solid rgba(86, 207, 238, 150);
                border-radius: 20px;
            }
            QLabel { color: #d8f5fc; background: transparent; }
            QLabel#brand {
                color: #9af3ff; font-family: "Segoe UI"; font-size: 19px;
                font-weight: 700; letter-spacing: 5px;
            }
            QLabel#tagline { color: #648ca3; font-size: 8px; letter-spacing: 2px; }
            QLabel#statusPill {
                color: #77e9ff; background: rgba(30, 126, 154, 28);
                border: 1px solid rgba(80, 208, 235, 92); border-radius: 11px;
                padding: 7px 11px; font-size: 9px; font-weight: 700; letter-spacing: 1px;
            }
            QLabel#statusPill[state="listening"] {
                color: #a7fff0; background: rgba(29, 154, 123, 35);
                border-color: rgba(91, 245, 203, 140);
            }
            QLabel#statusPill[state="thinking"] {
                color: #d0c0ff; background: rgba(110, 75, 171, 35);
                border-color: rgba(178, 148, 255, 120);
            }
            QLabel#statusPill[state="warning"] {
                color: #ffcc9d; background: rgba(160, 83, 31, 35);
                border-color: rgba(255, 168, 94, 140);
            }
            QPushButton#iconButton {
                min-width: 34px; max-width: 34px; min-height: 32px; max-height: 32px;
                color: #8ab9c9; background: rgba(32, 90, 111, 28);
                border: 1px solid rgba(75, 146, 168, 70); border-radius: 9px; font-size: 15px;
            }
            QPushButton#iconButton:hover {
                color: #efffff; background: rgba(64, 180, 211, 52);
                border-color: rgba(96, 224, 246, 145);
            }
            QFrame#divider { background: rgba(70, 168, 200, 76); border: 0; }
            QLabel#eyebrow {
                color: #66bed3; font-size: 9px; font-weight: 700; letter-spacing: 2px;
            }
            QLabel#heroTitle {
                color: #e4faff; font-size: 25px; font-weight: 600; letter-spacing: -0.4px;
            }
            QLabel#heroDescription { color: #91b2c4; font-size: 11px; line-height: 1.4; }
            QLabel#metaChip {
                color: #6394a9; background: rgba(25, 73, 92, 34);
                border: 1px solid rgba(58, 124, 149, 70); border-radius: 6px;
                padding: 5px 7px; font-size: 7px; letter-spacing: 0.7px;
            }
            QLabel#sectionTitle {
                color: #85ddef; font-size: 9px; font-weight: 700; letter-spacing: 2px;
            }
            QLabel#sectionMeta { color: #4f7d91; font-size: 8px; letter-spacing: 1px; }
            QTextBrowser#chatHistory {
                background: rgba(2, 11, 20, 150); color: #c9e6f0;
                border: 1px solid rgba(44, 108, 132, 84); border-radius: 12px;
                padding: 10px; selection-background-color: #0d6684;
                font-family: "Segoe UI"; font-size: 11px;
            }
            QLineEdit#commandInput {
                min-height: 22px; background: rgba(3, 14, 25, 230); color: #e4faff;
                border: 1px solid rgba(56, 137, 163, 125); border-radius: 10px;
                padding: 11px 13px; selection-background-color: #087fa5;
            }
            QLineEdit#commandInput:focus { border: 1px solid #5bdcf7; }
            QPushButton#voiceButton {
                color: #9bdbea; background: rgba(24, 79, 99, 55);
                border: 1px solid rgba(74, 157, 181, 110); border-radius: 9px;
                padding: 10px 11px; font-size: 9px; font-weight: 700; letter-spacing: 0.5px;
            }
            QPushButton#voiceButton[enabled="true"] {
                color: #a6fff1; background: rgba(23, 132, 109, 60);
                border-color: rgba(95, 241, 203, 140);
            }
            QPushButton#sendButton {
                color: #f0fdff; background: #0a6d8a; border: 1px solid #52d7ef;
                border-radius: 9px; padding: 10px 15px; font-size: 9px;
                font-weight: 700; letter-spacing: 1px;
            }
            QPushButton#sendButton:hover { background: #0d86a8; }
            QPushButton#sendButton:disabled { color: #547b8c; background: #102736; border-color: #24485a; }
            QLabel#footer { color: #456f82; font-size: 8px; letter-spacing: 1px; }
            """
        )

        self.set_status("Pronto para ajudar.")
        self.set_voice_enabled(False)
        self.append_message(
            "AURIX",
            "Olá. Estou aqui. Diga o que você quer fazer ou pergunte qualquer coisa.",
        )

    def _shell_mouse_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 62:
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
        if screen:
            area = screen.availableGeometry()
            # Center only the first time; preserve the user's chosen position afterward.
            if not self.isVisible():
                self.move(area.center().x() - self.width() // 2, area.center().y() - self.height() // 2)
        self.show()
        self.raise_()
        self.activateWindow()
        self.input_field.setFocus()

    def set_status(self, text: str) -> None:
        self.status_label_text = text
        lower = text.casefold()
        if any(word in lower for word in ("ouvindo", "ativado", "transcrevendo", "voz inicializada")):
            state, label, mode = "listening", "●  LISTENING", "listening"
        elif any(word in lower for word in ("processando", "pensando", "baixando modelo")):
            state, label, mode = "thinking", "◌  THINKING", "thinking"
        elif any(word in lower for word in ("erro", "falha", "não consegui", "nao consegui", "recusada")):
            state, label, mode = "warning", "●  ATTENTION", "warning"
        else:
            state, label, mode = "ready", "●  STANDBY", "idle"
        self.status_pill.setText(label)
        self.status_pill.setProperty("state", state)
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)
        self.core.set_mode(mode)
        if state == "listening":
            self.hero_title.setText("Estou ouvindo.")
        elif state == "thinking":
            self.hero_title.setText("Pensando com você.")
        elif state == "warning":
            self.hero_title.setText("Preciso da sua atenção.")
        else:
            self.hero_title.setText("Pronto para pensar com você.")

    def set_response(self, text: str) -> None:
        # Assistant responses are appended to the session timeline.
        self.append_message("AURIX", text)

    def append_message(self, speaker: str, text: str) -> None:
        safe_text = html.escape(str(text)).replace("\n", "<br>")
        if speaker.casefold() == "você":
            bubble_color = "#102b3d"
            title_color = "#8ddcf0"
            alignment = "right"
            label = "VOCÊ"
        else:
            bubble_color = "#0b1d2d"
            title_color = "#70dced"
            alignment = "left"
            label = speaker.upper() if speaker else "AURIX"

        timestamp = datetime.now().strftime("%H:%M")
        self.chat.append(
            f'<div style="margin: 7px 2px 12px 2px; text-align: {alignment};">'
            f'<span style="color:{title_color}; font-size:9px; letter-spacing:1px; font-weight:700;">'
            f'{html.escape(label)}  /  {timestamp}</span><br>'
            f'<span style="display:inline-block; max-width:92%; background:{bubble_color}; '
            f'border:1px solid #1d475b; border-radius:10px; padding:9px 11px; '
            f'color:#d0e9f2; font-size:11px; line-height:1.5;">{safe_text}</span>'
            '</div>'
        )
        self._message_count += 1
        self.session_label.setText(f"SESSÃO LOCAL  ·  {self._message_count:02d} MENSAGENS")
        bar = self.chat.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_voice_enabled(self, enabled: bool) -> None:
        self._voice_enabled = enabled
        self.voice_button.setText("VOZ ON" if enabled else "VOZ OFF")
        self.voice_button.setProperty("enabled", "true" if enabled else "false")
        self.voice_button.style().unpolish(self.voice_button)
        self.voice_button.style().polish(self.voice_button)
        self.voice_button.setToolTip(
            "Pausar a escuta da palavra de ativação" if enabled
            else "Ativar a escuta da palavra de ativação"
        )

    def set_busy(self, busy: bool) -> None:
        self.send_button.setEnabled(not busy)
        self.input_field.setEnabled(not busy)
        self.send_button.setText("PROCESSANDO…" if busy else "ENVIAR  ↗")
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
