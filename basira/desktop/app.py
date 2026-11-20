"""Desktop application entry point (PySide6)."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap, QPainter
from PySide6.QtWidgets import QApplication, QSplashScreen

from ..config import APP_NAME, APP_VERSION, load_settings
from ..db.database import Database
from ..hardware.device_manager import DeviceManager
from ..intelligence.orchestrator import BASIRACore
from ..logging_setup import get_logger, setup_logging
from .main_window import MainWindow

log = get_logger("desktop.app")


def make_splash() -> QSplashScreen:
    pix = QPixmap(420, 260)
    pix.fill(QColor("#12141a"))
    painter = QPainter(pix)
    painter.setPen(QColor("#2f6fed"))
    painter.drawText(pix.rect().adjusted(0, -30, 0, -30), Qt.AlignCenter,
                     "BASIRA AI")
    painter.setPen(QColor("#e8eaf0"))
    painter.drawText(pix.rect().adjusted(0, 40, 0, 40), Qt.AlignCenter,
                     "Universal Multimodal Accessibility Intelligence")
    painter.end()
    return QSplashScreen(pix)


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    app = QApplication(argv or sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    settings = load_settings()
    splash = make_splash()
    splash.show()
    app.processEvents()

    db = Database(__import__("basira.config", fromlist=["database_path"]).database_path())
    core = BASIRACore(db, settings)
    devices = DeviceManager(
        camera_index=settings.camera_index or 0,
        mic_index=settings.microphone_index,
        speaker_index=settings.speaker_index,
    )
    core.load_lightweight()

    window = MainWindow(core, settings, devices)
    direction = Qt.LayoutDirection.RightToLeft if settings.language == "ar" else Qt.LayoutDirection.LeftToRight
    app.setLayoutDirection(direction)
    splash.finish(window)
    window.show()
    log.info("desktop app started (version %s)", APP_VERSION)
    rc = app.exec()
    from ..worker.workers import wait_for_workers
    wait_for_workers()
    devices.shutdown()
    core.shutdown()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
