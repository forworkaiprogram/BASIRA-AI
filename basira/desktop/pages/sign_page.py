"""BASIRA SIGN page: live tracking, translation, enrollment, corrections."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout,
    QWidget,
)

from ...config import AppSettings, app_home
from ...engines.sign.dataset_tools import SignDatasetWriter
from ...hardware.device_manager import DeviceManager
from ...intelligence.orchestrator import BASIRACore
from ..i18n import I18n
from ...worker.workers import SignWorker, run_in_thread
from .common import card, frame_to_pixmap
import os


class SignPage(QWidget):
    def __init__(self, core: BASIRACore, settings: AppSettings,
                 devices: DeviceManager, i18n: I18n):
        super().__init__()
        self.core, self.settings, self.devices, self.i18n = \
            core, settings, devices, i18n
        self._recording: list[np.ndarray] | None = None
        self._collecting = False
        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(120)

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        left, left_lay = card()
        self.preview = QLabel(self.i18n("camera_off"))
        self.preview.setMinimumSize(440, 330)
        self.preview.setAlignment(Qt.AlignCenter)
        left_lay.addWidget(self.preview, 1)
        controls = QHBoxLayout()
        self.camera_btn = QPushButton(self.i18n("start_camera"))
        self.camera_btn.clicked.connect(self.toggle_camera)
        self.record_btn = QPushButton(self.i18n("enroll"))
        self.record_btn.setObjectName("secondary")
        self.record_btn.clicked.connect(self.toggle_enroll)
        controls.addWidget(self.camera_btn)
        controls.addWidget(self.record_btn)
        controls.addStretch(1)
        left_lay.addLayout(controls)
        lay.addWidget(left, 3)

        right, right_lay = card()
        right_lay.addWidget(QLabel(self.i18n("sign_text")))
        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setAccessibleName(self.i18n("sign_text"))
        self.text_view.setMinimumHeight(140)
        right_lay.addWidget(self.text_view)
        self.conf_label = QLabel(f"{self.i18n('confidence')}: —")
        right_lay.addWidget(self.conf_label)

        right_lay.addWidget(QLabel(self.i18n("enroll_label")))
        self.enroll_input = QLineEdit()
        self.enroll_input.setAccessibleName(self.i18n("enroll_label"))
        right_lay.addWidget(self.enroll_input)

        correct_btn = QPushButton(self.i18n("clear"))
        correct_btn.setObjectName("secondary")
        correct_btn.clicked.connect(self.text_view.clear)
        right_lay.addWidget(correct_btn)
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

    def toggle_enroll(self) -> None:
        if not self._collecting:
            label = self.enroll_input.text().strip()
            if not label:
                self.text_view.setPlainText(self.i18n("enroll_label") + ": ?")
                return
            self._collecting = True
            self._recording = []
            self.record_btn.setText("● REC")
        else:
            self._collecting = False
            self.record_btn.setText(self.i18n("enroll"))
            self._save_enrollment()

    def _save_enrollment(self) -> None:
        if not self._recording or len(self._recording) < 6:
            self.text_view.setPlainText("…")
            self._recording = None
            return
        label = self.enroll_input.text().strip()
        frames = np.stack(self._recording).reshape(len(self._recording), -1)
        consent = os.environ.get("BASIRA_CONSENT_ID", "local-user-consent")
        try:
            self.core.sign.enroll_sequence(label, frames, consent)
            self.text_view.setPlainText(
                f"{label}: OK ({len(self._recording)} frames)")
        except Exception as e:
            self.text_view.setPlainText(f"ERROR: {e}")
        self._recording = None

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
        if self._collecting:
            # collect landmarks only (never store video)
            try:
                hands = self.core.sign.tracker.track(frame)
                if hands:
                    from ...engines.sign.recognizer import normalize_landmarks
                    self._recording.append(normalize_landmarks(hands[0].landmarks))
            except Exception:
                pass
            return
        worker = SignWorker(self.core.sign, frame.copy(), self.settings.language)
        self._thread = run_in_thread(worker, self._show_result)

    def _show_result(self, res) -> None:
        if res.text:
            self.text_view.setPlainText(res.text)
            self.conf_label.setText(
                f"{self.i18n('confidence')}: {res.confidence:.0%}")
        else:
            self.conf_label.setText(f"{self.i18n('confidence')}: —")

    def retranslate(self, i18n: I18n) -> None:
        self.i18n = i18n
        self.camera_btn.setText(self.i18n("start_camera"))
        self.record_btn.setText(self.i18n("enroll"))
