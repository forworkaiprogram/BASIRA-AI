"""Main window: sidebar navigation, header, workspace, status bar."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget,
)

from ..config import AppSettings
from ..hardware.device_manager import DeviceManager
from ..intelligence.orchestrator import BASIRACore
from ..logging_setup import get_logger
from .i18n import I18n
from .pages.connect_page import ConnectPage
from .pages.dashboard_page import DashboardPage
from .pages.hear_page import HearPage
from .pages.help_page import HelpPage
from .pages.history_page import HistoryPage
from .pages.models_page import ModelsPage
from .pages.settings_page import SettingsPage
from .pages.sign_page import SignPage
from .pages.vision_page import VisionPage
from .theme import build_stylesheet

log = get_logger("desktop")


class MainWindow(QMainWindow):
    def __init__(self, core: BASIRACore, settings: AppSettings,
                 devices: DeviceManager):
        super().__init__()
        self.core = core
        self.settings = settings
        self.devices = devices
        self.i18n = I18n(settings.language)
        self.setWindowTitle(f"{self.i18n('app_name')} — {self.i18n('app_tagline')}")
        self.resize(1180, 760)
        self.setMinimumSize(900, 600)

        self._build_ui()
        self._apply_theme()
        self._add_shortcuts()
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status_chips)
        self._status_timer.start(2000)
        self._refresh_status_chips()

    # -- UI construction ------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # sidebar
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        self.sidebar.setAccessibleName(self.i18n("app_name"))
        keys = ["dashboard", "vision", "sign", "hear", "connect", "history",
                "models", "settings", "help"]
        for key in keys:
            QListWidgetItem(self.i18n(key), self.sidebar)
        root.addWidget(self.sidebar)

        # right side: header + stacked pages
        right = QWidget()
        right_col = QVBoxLayout(right)
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(0)

        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(64)
        header_l = QHBoxLayout(header)
        header_l.setContentsMargins(20, 8, 20, 8)
        self.page_title = QLabel(self.i18n("dashboard"))
        self.page_title.setObjectName("pageTitle")
        self.page_title.setAccessibleName(self.i18n("dashboard"))
        header_l.addWidget(self.page_title)
        header_l.addStretch(1)
        self.camera_chip = QLabel(self.i18n("camera_off"))
        self.camera_chip.setObjectName("statusChip")
        self.mic_chip = QLabel(self.i18n("mic_off"))
        self.mic_chip.setObjectName("statusChip")
        self.privacy_chip = QLabel(self.i18n("local_processing"))
        self.privacy_chip.setObjectName("statusChip")
        for chip in (self.camera_chip, self.mic_chip, self.privacy_chip):
            header_l.addWidget(chip)
        right_col.addWidget(header)

        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {
            "dashboard": DashboardPage(self.core, self.settings, self.devices, self.i18n),
            "vision": VisionPage(self.core, self.settings, self.devices, self.i18n),
            "sign": SignPage(self.core, self.settings, self.devices, self.i18n),
            "hear": HearPage(self.core, self.settings, self.devices, self.i18n),
            "connect": ConnectPage(self.core, self.settings, self.devices, self.i18n),
            "history": HistoryPage(self.core, self.i18n),
            "models": ModelsPage(self.core, self.i18n),
            "settings": SettingsPage(self.core, self.settings, self.i18n,
                                     on_changed=self.apply_language_and_theme),
            "help": HelpPage(self.i18n),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        right_col.addWidget(self.stack, 1)
        root.addWidget(right, 1)
        self.setCentralWidget(central)

        self.sidebar.currentRowChanged.connect(self._on_nav)
        self.sidebar.setCurrentRow(0)

    def _add_shortcuts(self) -> None:
        for i, key in enumerate(
                ["dashboard", "vision", "sign", "hear", "connect"], start=1):
            act = QAction(self)
            act.setShortcut(QKeySequence(f"Ctrl+{i}"))
            act.triggered.connect(
                lambda _=False, idx=i - 1: self.sidebar.setCurrentRow(idx))
            self.addAction(act)
        quit_act = QAction(self)
        quit_act.setShortcut(QKeySequence("Ctrl+Q"))
        quit_act.triggered.connect(self.close)
        self.addAction(quit_act)
        help_act = QAction(self)
        help_act.setShortcut(QKeySequence("F1"))
        help_act.triggered.connect(lambda: self.sidebar.setCurrentRow(8))
        self.addAction(help_act)

    # -- navigation ------------------------------------------------------------
    def _on_nav(self, row: int) -> None:
        keys = list(self.pages.keys())
        if 0 <= row < len(keys):
            key = keys[row]
            self.stack.setCurrentWidget(self.pages[key])
            self.page_title.setText(self.i18n(key))
            self.page_title.setAccessibleName(self.i18n(key))

    # -- status chips ------------------------------------------------------------
    def _refresh_status_chips(self) -> None:
        cam_on = self.devices._camera is not None and \
            self.devices._camera.status["running"]
        self.camera_chip.setText(self.i18n("camera_on") if cam_on
                                 else self.i18n("camera_off"))
        self.camera_chip.setObjectName("statusChip statusOn" if cam_on
                                       else "statusChip statusOff")
        mic_on = self.devices._mic is not None and self.devices._mic.status["running"]
        self.mic_chip.setText(self.i18n("mic_on") if mic_on
                              else self.i18n("mic_off"))
        self.mic_chip.setObjectName("statusChip statusOn" if mic_on
                                    else "statusChip statusOff")
        self.privacy_chip.setText(self.i18n("local_processing"))
        for chip in (self.camera_chip, self.mic_chip):
            chip.style().unpolish(chip)
            chip.style().polish(chip)

    # -- theming / language -------------------------------------------------------
    def apply_language_and_theme(self) -> None:
        """Called by the settings page after language/theme changes."""
        self.i18n = I18n(self.settings.language)
        self.setWindowTitle(f"{self.i18n('app_name')} — {self.i18n('app_tagline')}")
        direction = Qt.LayoutDirection.RightToLeft if self.i18n.rtl else Qt.LayoutDirection.LeftToRight
        QApplication.instance().setLayoutDirection(direction)
        self._apply_theme()
        row = self.sidebar.currentRow()
        keys = list(self.pages.keys())
        for i, key in enumerate(keys):
            self.sidebar.item(i).setText(self.i18n(key))
        self.page_title.setText(self.i18n(keys[row] if row >= 0 else "dashboard"))
        for page in self.pages.values():
            if hasattr(page, "retranslate"):
                page.retranslate(self.i18n)

    def _apply_theme(self) -> None:
        self.setStyleSheet(build_stylesheet(self.settings.theme,
                                            self.settings.text_scale))

    # -- accessibility: text scaling ----------------------------------------------
    def apply_text_scale(self, scale: float) -> None:
        self.settings.text_scale = scale
        self._apply_theme()

    # -- safe close -----------------------------------------------------------------
    def closeEvent(self, event) -> None:
        try:
            from ..worker.workers import wait_for_workers
            wait_for_workers()
            self.devices.shutdown()
            self.core.shutdown()
        except Exception as e:
            log.warning("shutdown error: %s", e)
        event.accept()
