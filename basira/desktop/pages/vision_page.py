"""BASIRA VISION page: live camera, scene analysis, VQA, spoken answers."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout,
    QWidget,
)

from ...config import AppSettings
from ...hardware.device_manager import DeviceManager
from ...intelligence.orchestrator import BASIRACore, CoreResponse
from ...logging_setup import get_logger
from ..i18n import I18n
from ...worker.workers import CameraOpenerWorker, FunctionWorker, VisionWorker, run_in_thread
from .common import card, frame_to_pixmap

log = get_logger("desktop.vision")


class VisionPage(QWidget):
    answerReady = Signal(object)

    def __init__(self, core: BASIRACore, settings: AppSettings,
                 devices: DeviceManager, i18n: I18n):
        super().__init__()
        self.core, self.settings, self.devices, self.i18n = \
            core, settings, devices, i18n
        self._thread: QThread | None = None
        self._cam_thread: QThread | None = None
        self._tts_thread: QThread | None = None
        self._camera_opening = False
        self._last_response: CoreResponse | None = None
        self._build()
        self.answerReady.connect(self._show_result)
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start(100)

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        # left: camera preview + controls
        left, left_lay = card()
        self.preview = QLabel(self.i18n("camera_off"))
        self.preview.setMinimumSize(480, 360)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setAccessibleName(self.i18n("camera"))
        left_lay.addWidget(self.preview, 1)
        controls = QHBoxLayout()
        self.camera_btn = QPushButton(self.i18n("start_camera"))
        self.camera_btn.clicked.connect(self.toggle_camera)
        self.analyze_btn = QPushButton(self.i18n("analyze"))
        self.analyze_btn.clicked.connect(lambda: self.ask(""))
        controls.addWidget(self.camera_btn)
        controls.addWidget(self.analyze_btn)
        controls.addStretch(1)
        left_lay.addLayout(controls)
        lay.addWidget(left, 3)

        # right: question + answer
        right, right_lay = card()
        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText(self.i18n("ask_placeholder"))
        self.question_input.setAccessibleName(self.i18n("ask"))
        self.question_input.returnPressed.connect(self._ask_from_input)
        right_lay.addWidget(self.question_input)
        ask_btn = QPushButton(self.i18n("ask"))
        ask_btn.setObjectName("secondary")
        ask_btn.clicked.connect(self._ask_from_input)
        right_lay.addWidget(ask_btn)
        right_lay.addWidget(QLabel(self.i18n("answer")))
        self.answer_view = QTextEdit()
        self.answer_view.setReadOnly(True)
        self.answer_view.setAccessibleName(self.i18n("answer"))
        self.answer_view.setMinimumHeight(220)
        right_lay.addWidget(self.answer_view, 1)
        self.repeat_btn = QPushButton(self.i18n("repeat"))
        self.repeat_btn.setObjectName("secondary")
        self.repeat_btn.clicked.connect(self.repeat_answer)
        right_lay.addWidget(self.repeat_btn)
        lay.addWidget(right, 2)

    # -- camera ----------------------------------------------------------------
    def toggle_camera(self) -> None:
        cam = self.devices.camera()
        if cam.status["running"]:
            cam.stop()
            self.camera_btn.setText(self.i18n("start_camera"))
            self.preview.setText(self.i18n("camera_off"))
            return
        if self._camera_opening:
            return  # open already in progress
        self._camera_opening = True
        self.camera_btn.setEnabled(False)
        self.preview.setText(self.i18n("camera_starting"))
        worker = CameraOpenerWorker(cam)

        def on_ok(cam_result) -> None:
            self._camera_opening = False
            self.camera_btn.setEnabled(True)
            self.camera_btn.setText(self.i18n("stop_camera"))

        def on_err(message: str) -> None:
            self._camera_opening = False
            self.camera_btn.setEnabled(True)
            self.preview.setText(f"{self.i18n('not_available')}: {message}")

        self._cam_thread = run_in_thread(worker, on_ok, on_err)

    def _update_preview(self) -> None:
        cam = self.devices._camera
        if cam is None or not cam.status["running"]:
            return
        frame = cam.latest_frame()
        if frame is not None:
            self._last_frame = frame
            self.preview.setPixmap(
                frame_to_pixmap(frame).scaled(
                    self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # -- analysis -----------------------------------------------------------------
    def _ask_from_input(self) -> None:
        self.ask(self.question_input.text().strip())

    def ask(self, question: str) -> None:
        frame = getattr(self, "_last_frame", None)
        if frame is None:
            cam = self.devices._camera
            if cam is not None and cam.status["running"]:
                try:
                    frame = cam.capture_still()
                except Exception as e:
                    self.answer_view.setPlainText(
                        f"{self.i18n('not_available')}: {e}")
                    return
            else:
                self.answer_view.setPlainText(self.i18n("camera_off"))
                return
        # Show busy state; first analysis loads the model (seconds).
        self.analyze_btn.setEnabled(False)
        self.question_input.setEnabled(False)
        self.answer_view.setPlainText(self.i18n("analyzing"))
        worker = VisionWorker(self.core.vision, frame.copy(),
                              question or None, self.settings.language)
        self._thread = run_in_thread(worker, self.answerReady.emit,
                                     self._on_ask_error)

    def _on_ask_error(self, message: str) -> None:
        self.analyze_btn.setEnabled(True)
        self.question_input.setEnabled(True)
        self.answer_view.setPlainText(message)
        log.error("vision analysis failed: %s", message)

    def _speak_async(self, text: str) -> None:
        """Synthesize+play TTS off the GUI thread (Piper synthesis blocks)."""
        def _work() -> bool:
            return self.core.speak_text(text, self.devices.speaker())
        worker = FunctionWorker(_work)
        self._tts_thread = run_in_thread(worker, lambda _r: None)

    def _show_result(self, result) -> None:
        self.analyze_btn.setEnabled(True)
        self.question_input.setEnabled(True)
        text = result.answer or result.description
        self.answer_view.setPlainText(text)
        self._last_response = CoreResponse("vision", "describe", text,
                                           result.answer_confidence)
        if self.settings.prefer_voice_output and self.settings.tts_enabled:
            self._speak_async(text)

    def repeat_answer(self) -> None:
        if self._last_response:
            self._speak_async(self._last_response.text)

    def retranslate(self, i18n: I18n) -> None:
        self.i18n = i18n
        self.camera_btn.setText(self.i18n("start_camera"))
        self.analyze_btn.setText(self.i18n("analyze"))
        self.repeat_btn.setText(self.i18n("repeat"))
        self.question_input.setPlaceholderText(self.i18n("ask_placeholder"))
