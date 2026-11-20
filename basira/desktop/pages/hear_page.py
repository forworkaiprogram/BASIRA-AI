"""BASIRA HEAR page: live speech-to-text + sound alerts."""
from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QListWidget, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from ...config import AppSettings
from ...hardware.device_manager import DeviceManager
from ...intelligence.orchestrator import BASIRACore
from ...worker.workers import FunctionWorker, run_in_thread
from ..i18n import I18n
from .common import card


class HearPage(QWidget):
    def __init__(self, core: BASIRACore, settings: AppSettings,
                 devices: DeviceManager, i18n: I18n):
        super().__init__()
        self.core, self.settings, self.devices, self.i18n = \
            core, settings, devices, i18n
        self._audio_buffer: list[np.ndarray] = []
        self._transcribing = False
        self._empty_notice_shown = False
        self._stt_thread = None
        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_audio)
        self._stt_timer = QTimer(self)
        self._stt_timer.timeout.connect(self._transcribe_buffer)

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        left, left_lay = card(self.i18n("transcript"))
        self.transcript_view = QTextEdit()
        self.transcript_view.setReadOnly(True)
        self.transcript_view.setAccessibleName(self.i18n("transcript"))
        self.transcript_view.setMinimumHeight(240)
        left_lay.addWidget(self.transcript_view, 1)
        controls = QHBoxLayout()
        self.listen_btn = QPushButton(self.i18n("start_listen"))
        self.listen_btn.clicked.connect(self.toggle_listening)
        controls.addWidget(self.listen_btn)
        clear_btn = QPushButton(self.i18n("clear"))
        clear_btn.setObjectName("secondary")
        clear_btn.clicked.connect(self.transcript_view.clear)
        controls.addWidget(clear_btn)
        controls.addStretch(1)
        left_lay.addLayout(controls)
        lay.addWidget(left, 2)

        right, right_lay = card(self.i18n("sound_alerts"))
        self.alerts_list = QListWidget()
        self.alerts_list.setAccessibleName(self.i18n("sound_alerts"))
        right_lay.addWidget(self.alerts_list, 1)
        self.core.audio.alerts.subscribe(self._on_alert)
        lay.addWidget(right, 1)

    def toggle_listening(self) -> None:
        mic = self.devices.microphone()
        if mic.status["running"]:
            mic.stop()
            self._stt_timer.stop()
            self._timer.stop()
            self.listen_btn.setText(self.i18n("start_listen"))
            return
        try:
            mic.start()
        except Exception as e:
            self.transcript_view.setPlainText(f"{self.i18n('not_available')}: {e}")
            return
        self.listen_btn.setText(self.i18n("stop_listen"))
        self._timer.start(100)
        self._stt_timer.start(4000)

    def _poll_audio(self) -> None:
        mic = self.devices._mic
        if mic is None:
            return
        frames = mic.read_frames(50)
        if not frames:
            return
        self._audio_buffer.extend(frames)
        chunk = np.concatenate(frames)
        res = self.core.audio.process_audio_chunk(chunk, mic.sample_rate,
                                                  time.time())
        if res.alert is not None:
            self._on_alert(res.alert)

    def _transcribe_buffer(self) -> None:
        if not self._audio_buffer or self._transcribing:
            return
        pcm = np.concatenate(self._audio_buffer)
        self._audio_buffer.clear()
        if pcm.size < 8000:
            return
        # Whisper transcription takes seconds — run it off the GUI thread.
        self._transcribing = True
        lang = self.settings.stt_language
        worker = FunctionWorker(lambda: self.core.audio.transcribe_pcm(pcm, 16000, lang))

        def on_done(t) -> None:
            self._transcribing = False
            if t is not None and t.is_empty:
                # One-time notice; cleared when real speech is recognized.
                if not self._empty_notice_shown:
                    self._empty_notice_shown = True
                    self.transcript_view.append(
                        f"[STT] {self.i18n('no_speech')}")
                return
            if t is not None:
                self._empty_notice_shown = False
                self.transcript_view.append(t.text)

        def on_fail(message: str) -> None:
            self._transcribing = False
            self.transcript_view.append(f"[STT] {message}")

        self._stt_thread = run_in_thread(worker, on_done, on_fail)

    def _on_alert(self, alert) -> None:
        if alert is None:
            return
        self.alerts_list.insertItem(0, f"{alert.title} — {alert.body}")

    def retranslate(self, i18n: I18n) -> None:
        self.i18n = i18n
        self.listen_btn.setText(self.i18n("start_listen"))
