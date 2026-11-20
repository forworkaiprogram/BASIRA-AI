"""BASIRA CONNECT page: two-panel deaf/hearing conversation."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QListWidget, QPushButton, QVBoxLayout, QWidget,
)

from ...config import AppSettings
from ...hardware.device_manager import DeviceManager
from ...intelligence.orchestrator import BASIRACore
from ..i18n import I18n
from ...worker.workers import FunctionWorker, SignWorker, run_in_thread
from .common import card, frame_to_pixmap


class ConnectPage(QWidget):
    def __init__(self, core: BASIRACore, settings: AppSettings,
                 devices: DeviceManager, i18n: I18n):
        super().__init__()
        self.core, self.settings, self.devices, self.i18n = \
            core, settings, devices, i18n
        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(150)

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        left, left_lay = card(self.i18n("connect_sign"))
        self.preview = QLabel = getattr(self, "preview", None)
        from PySide6.QtWidgets import QLabel
        self.preview = QLabel(self.i18n("camera_off"))
        self.preview.setMinimumSize(360, 270)
        self.preview.setAlignment(Qt.AlignCenter)
        left_lay.addWidget(self.preview, 1)
        self.camera_btn = QPushButton(self.i18n("start_camera"))
        self.camera_btn.clicked.connect(self.toggle_camera)
        left_lay.addWidget(self.camera_btn)
        lay.addWidget(left, 2)

        right, right_lay = card(self.i18n("connect_voice"))
        self.transcript_list = QListWidget()
        self.transcript_list.setAccessibleName(self.i18n("transcript"))
        right_lay.addWidget(self.transcript_list, 1)
        controls = QHBoxLayout()
        self.mic_btn = QPushButton(self.i18n("start_listen"))
        self.mic_btn.setObjectName("secondary")
        self.mic_btn.clicked.connect(self.toggle_mic)
        clear_btn = QPushButton(self.i18n("clear"))
        clear_btn.setObjectName("secondary")
        clear_btn.clicked.connect(self.clear_conversation)
        controls.addWidget(self.mic_btn)
        controls.addWidget(clear_btn)
        controls.addStretch(1)
        right_lay.addLayout(controls)
        lay.addWidget(right, 2)

    def toggle_camera(self) -> None:
        cam = self.devices.camera()
        if cam.status["running"]:
            cam.stop()
            self.camera_btn.setText(self.i18n("start_camera"))
            self.preview.setText(self.i18n("camera_off"))
            return
        try:
            cam.start()
            self.camera_btn.setText(self.i18n("stop_camera"))
        except Exception as e:
            self.preview.setText(f"{self.i18n('not_available')}: {e}")

    def toggle_mic(self) -> None:
        mic = self.devices.microphone()
        if mic.status["running"]:
            mic.stop()
            self.mic_btn.setText(self.i18n("start_listen"))
            return
        try:
            mic.start()
            self.mic_btn.setText(self.i18n("stop_listen"))
        except Exception as e:
            self.transcript_list.addItem(f"{self.i18n('not_available')}: {e}")

    def _tick(self) -> None:
        cam = self.devices._camera
        if cam is None or not cam.status["running"]:
            return
        frame = cam.latest_frame()
        if frame is None:
            return
        self.preview.setPixmap(
            frame_to_pixmap(frame).scaled(
                self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        worker = SignWorker(self.core.sign, frame.copy(), self.settings.language)
        self._thread = run_in_thread(worker, self._on_sign_result)

    def _on_sign_result(self, res) -> None:
        if not res.text:
            return
        use_tts = res.confidence >= 0.5 and self.settings.tts_enabled
        who = "TTS" if use_tts else "SIG"
        self.transcript_list.addItem(f"{who}: {res.text} ({res.confidence:.0%})")
        self.transcript_list.scrollToBottom()
        if use_tts:
            # Piper synthesis blocks — move it off the GUI thread.
            text = res.text
            worker = FunctionWorker(lambda: self.core.speak_text(
                text, self.devices.speaker()))
            self._tts_thread = run_in_thread(worker, lambda _r: None)

    def clear_conversation(self) -> None:
        self.transcript_list.clear()

    def retranslate(self, i18n: I18n) -> None:
        self.i18n = i18n
        self.camera_btn.setText(self.i18n("start_camera"))
        self.mic_btn.setText(self.i18n("start_listen"))
