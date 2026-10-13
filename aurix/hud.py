"""Floating holographic HUD interface built with PySide6."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CoreWidget(QWidget):
    """Animated circular core inspired by futuristic sci-fi HUDs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._angle = 0.0
        self.setMinimumSize(144, 144)
        self.setMaximumSize(168, 168)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(33)

    def _advance(self) -> None:
        self._angle = (self._angle + 1.6) % 360
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center = self.rect().center()
        cx, cy = float(center.x()), float(center.y())
        radius = min(self.width(), self.height()) * 0.43

        glow = QRadialGradient(cx, cy, radius * 1.35)
        glow.setColorAt(0.0, QColor(18, 178, 230, 65))
        glow.setColorAt(0.48, QColor(10, 112, 166, 28))
        glow.setColorAt(1.0, QColor(3, 14, 32, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(cx - radius * 1.35, cy - radius * 1.35, radius * 2.7, radius * 2.7))

        painter.setBrush(Qt.BrushStyle.NoBrush)
        for scale, alpha, width in ((1.0, 210, 1.3), (0.83, 105, 1.0), (0.63, 150, 1.0)):
            painter.setPen(QPen(QColor(83, 223, 255, alpha), width))
            painter.drawEllipse(QRectF(cx - radius * scale, cy - radius * scale, radius * 2 * scale, radius * 2 * scale))

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._angle)
        painter.setPen(QPen(QColor(86, 230, 255, 220), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(-radius, -radius, radius * 2, radius * 2), 16 * 25, 16 * 102)
        painter.setPen(QPen(QColor(40, 159, 220, 190), 1.5))
        painter.drawArc(QRectF(-radius * 0.83, -radius * 0.83, radius * 1.66, radius * 1.66), 16 * 185, 16 * 110)
        for angle in range(0, 360, 30):
            painter.save()
            painter.rotate(angle)
            painter.setPen(QPen(QColor(73, 225, 255, 160), 1.0))
            painter.drawLine(0, int(-radius * 0.92), 0, int(-radius * 0.82))
            painter.restore()
        painter.restore()

        inner = QRadialGradient(cx - radius * 0.15, cy - radius * 0.18, radius * 0.75)
        inner.setColorAt(0.0, QColor(120, 249, 255, 245))
        inner.setColorAt(0.22, QColor(26, 168, 222, 240))
        inner.setColorAt(0.72, QColor(9, 48, 87, 245))
        inner.setColorAt(1.0, QColor(3, 13, 29, 235))
        painter.setPen(QPen(QColor(122, 248, 255, 225), 1.4))
        painter.setBrush(inner)
        painter.drawEllipse(QRectF(cx - radius * 0.46, cy - radius * 0.46, radius * 0.92, radius * 0.92))
        painter.setPen(QPen(QColor(197, 255, 255, 235), 1.1))
        painter.drawLine(int(cx - radius * 0.18), int(cy), int(cx + radius * 0.18), int(cy))
        painter.drawLine(int(cx), int(cy - radius * 0.18), int(cx), int(cy + radius * 0.18))


class HUDWindow(QMainWindow):
    """A compact, always-on-top HUD that hides instead of closing the process."""

    command_submitted = Signal(str, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AURIX AI")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(540, 420)

        shell = QFrame()
        shell.setObjectName("shell")
        root = QVBoxLayout(shell)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(8)

        header = QHBoxLayout()
        brand = QLabel("A U R I X")
        brand.setObjectName("brand")
        tagline = QLabel("PERSONAL INTELLIGENCE SYSTEM")
        tagline.setObjectName("tagline")
        header.addWidget(brand)
        header.addStretch(1)
        header.addWidget(tagline)
        self.hide_button = QPushButton("—")
        self.hide_button.setObjectName("hideButton")
        self.hide_button.setToolTip("Ocultar interface; AURIX continua em segundo plano")
        self.hide_button.clicked.connect(self.hide)
        header.addWidget(self.hide_button)
        root.addLayout(header)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        root.addWidget(divider)

        center = QHBoxLayout()
        center.setSpacing(14)
        self.core = CoreWidget()
        center.addWidget(self.core, 0, Qt.AlignmentFlag.AlignCenter)
        side = QVBoxLayout()
        side.setSpacing(6)
        eyebrow = QLabel("SYSTEM ONLINE")
        eyebrow.setObjectName("eyebrow")
        side.addWidget(eyebrow)
        self.status_label = QLabel("Pronto para ajudar.")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        side.addWidget(self.status_label)
        telemetry = QLabel("VOICE LINK   •   LOCAL ACTIONS   •   AI")
        telemetry.setObjectName("telemetry")
        telemetry.setWordWrap(True)
        side.addWidget(telemetry)
        side.addStretch(1)
        center.addLayout(side, 1)
        root.addLayout(center)

        self.response_label = QLabel("Diga “Hey Jarvis” ou escreva um comando abaixo.")
        self.response_label.setObjectName("response")
        self.response_label.setWordWrap(True)
        self.response_label.setMinimumHeight(66)
        self.response_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self.response_label)

        entry_row = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setObjectName("commandInput")
        self.input_field.setPlaceholderText("Fale ou digite um comando…")
        self.input_field.returnPressed.connect(self._submit_typed)
        entry_row.addWidget(self.input_field, 1)
        self.send_button = QPushButton("ENVIAR  ↗")
        self.send_button.setObjectName("sendButton")
        self.send_button.clicked.connect(self._submit_typed)
        entry_row.addWidget(self.send_button)
        root.addLayout(entry_row)

        footer = QHBoxLayout()
        footer_label = QLabel("AURIX AI   /   DESKTOP ASSISTANT")
        footer_label.setObjectName("footer")
        footer_hint = QLabel("CTRL + ALT + SPACE")
        footer_hint.setObjectName("footer")
        footer.addWidget(footer_label)
        footer.addStretch(1)
        footer.addWidget(footer_hint)
        root.addLayout(footer)

        self.setCentralWidget(shell)
        self.setStyleSheet(
            """
            QFrame#shell {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #071525, stop:0.55 #081c2e, stop:1 #040b16);
                border: 1px solid rgba(67, 218, 255, 175);
                border-radius: 18px;
            }
            QLabel { color: #d5f6ff; background: transparent; }
            QLabel#brand { color: #80f0ff; font-size: 17px; font-weight: 700; letter-spacing: 4px; }
            QLabel#tagline { color: #5b91a9; font-size: 8px; letter-spacing: 1px; }
            QLabel#eyebrow { color: #60e7ff; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
            QLabel#status { color: #d2faff; font-size: 15px; font-weight: 600; }
            QLabel#telemetry { color: #4d8298; font-size: 8px; letter-spacing: 1px; }
            QLabel#response {
                color: #c3e4f3; font-size: 12px; padding: 10px 12px;
                background: rgba(4, 19, 34, 180);
                border: 1px solid rgba(46, 137, 169, 100); border-radius: 9px;
            }
            QLabel#footer { color: #477990; font-size: 8px; letter-spacing: 1px; }
            QFrame#divider { background: rgba(69, 197, 230, 85); border: 0; }
            QLineEdit#commandInput {
                background: rgba(3, 14, 26, 230); color: #e2fbff;
                border: 1px solid #1a6785; border-radius: 8px; padding: 11px;
                selection-background-color: #087fa5;
            }
            QLineEdit#commandInput:focus { border: 1px solid #5eeaff; }
            QPushButton#sendButton {
                background: #0b7899; color: #f2fdff; border: 1px solid #48cee9;
                border-radius: 8px; padding: 9px 12px; font-size: 10px; font-weight: 700;
            }
            QPushButton#sendButton:hover { background: #1197b7; }
            QPushButton#hideButton {
                background: transparent; color: #7ab4c8; border: 0; font-size: 17px;
                padding: 1px 7px; border-radius: 5px;
            }
            QPushButton#hideButton:hover { background: rgba(77, 203, 234, 40); color: white; }
            """
        )

    def show_hud(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(
                area.center().x() - self.width() // 2,
                area.center().y() - self.height() // 2,
            )
        self.show()
        self.raise_()
        self.activateWindow()
        self.input_field.setFocus()

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_response(self, text: str) -> None:
        self.response_label.setText(text)

    def set_busy(self, busy: bool) -> None:
        self.send_button.setEnabled(not busy)
        self.input_field.setEnabled(not busy)
        self.send_button.setText("PROCESSANDO…" if busy else "ENVIAR  ↗")

    def _submit_typed(self) -> None:
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.command_submitted.emit(text, False)

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
