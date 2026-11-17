"""Dashboard: device/engine status + mode shortcuts."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget,
)

from ...hardware.device_manager import DeviceManager
from ...intelligence.orchestrator import BASIRACore
from ...config import AppSettings
from ..i18n import I18n
from .common import card


class DashboardPage(QWidget):
    def __init__(self, core: BASIRACore, settings: AppSettings,
                 devices: DeviceManager, i18n: I18n):
        super().__init__()
        self.core, self.settings, self.devices, self.i18n = \
            core, settings, devices, i18n
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        grid = QGridLayout()
        grid.setSpacing(12)

        cam_card, cam_lay = card(self.i18n("camera"))
        self.camera_status = QLabel("…")
        cam_lay.addWidget(self.camera_status)

        mic_card, mic_lay = card(self.i18n("microphone"))
        self.mic_status = QLabel("…")
        mic_lay.addWidget(self.mic_status)

        eng_card, eng_lay = card(self.i18n("engines"))
        self.engine_status = QLabel("…")
        eng_lay.addWidget(self.engine_status)

        net_card, net_lay = card(self.i18n("internet"))
        self.net_status = QLabel(self.i18n("offline_ready"))
        net_lay.addWidget(self.net_status)

        grid.addWidget(cam_card, 0, 0)
        grid.addWidget(mic_card, 0, 1)
        grid.addWidget(eng_card, 1, 0)
        grid.addWidget(net_card, 1, 1)
        lay.addLayout(grid)

        modes_card, modes_lay = card()
        shortcuts = QHBoxLayout()
        shortcuts.setSpacing(10)
        self.mode_buttons = {}
        for i, mode in enumerate(["vision", "sign", "hear", "connect"]):
            btn = QPushButton(self.i18n(mode))
            btn.setAccessibleName(self.i18n(mode))
            btn.setAccessibleDescription(f"Ctrl+{i + 1}")
            btn.setMinimumHeight(52)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(self._go_mode)
            self.mode_buttons[mode] = btn
            shortcuts.addWidget(btn)
        modes_lay.addLayout(shortcuts)
        lay.addWidget(modes_card)

        safety = QLabel(self.i18n("safety_note"))
        safety.setObjectName("alert")
        safety.setWordWrap(True)
        lay.addWidget(safety)
        lay.addStretch(1)
        self.refresh()

    def _go_mode(self) -> None:
        btn = self.sender()
        window = self.window()
        if hasattr(window, "pages"):
            for row, key in enumerate(window.pages.keys()):
                pass
            mapping = {"vision": 1, "sign": 2, "hear": 3, "connect": 4}
            if btn in self.mode_buttons.values():
                mode = [k for k, v in self.mode_buttons.items() if v is btn][0]
                window.sidebar.setCurrentRow(mapping[mode])

    def refresh(self) -> None:
        report = self.devices.scan()
        self.camera_status.setText(
            f"{len(report.cameras)} {self.i18n('available')}"
            if report.cameras else self.i18n("no_devices"))
        self.mic_status.setText(
            f"{len(report.microphones)} {self.i18n('available')}"
            if report.microphones else self.i18n("no_devices"))
        lines = []
        for st in self.core.registry.all_status():
            lines.append(f"{st.name}: {st.state.value}")
        self.engine_status.setText("\n".join(lines) or "—")

    def retranslate(self, i18n: I18n) -> None:
        self.i18n = i18n
        self._build()
