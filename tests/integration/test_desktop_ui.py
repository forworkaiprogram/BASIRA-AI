"""Desktop UI smoke tests (offscreen Qt platform).

These instantiate the real main window with the real core (models load
lazily, so these run without model files) and verify navigation, theming,
language switching and safe shutdown.
"""
import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from basira.config import AppSettings
from basira.db.database import Database
from basira.desktop.i18n import I18n
from basira.desktop.main_window import MainWindow
from basira.desktop.theme import build_stylesheet
from basira.hardware.device_manager import DeviceManager
from basira.intelligence.orchestrator import BASIRACore


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def window(tmp_home, qapp):
    settings = AppSettings()
    db = Database(tmp_home / "ui.db")
    core = BASIRACore(db, settings)
    devices = DeviceManager()
    win = MainWindow(core, settings, devices)
    yield win
    win.close()
    devices.shutdown()
    core.shutdown()
    db.close()


def test_main_window_builds_all_pages(window):
    assert window.stack.count() == 9
    for key, page in window.pages.items():
        assert page is not None


def test_sidebar_navigation(window):
    window.sidebar.setCurrentRow(1)  # BASIRA VISION
    assert window.page_title.text() == window.i18n("vision")
    window.sidebar.setCurrentRow(4)  # BASIRA CONNECT
    assert window.page_title.text() == window.i18n("connect")


def test_mode_shortcuts_registered(window):
    shortcuts = [a.shortcut().toString() for a in window.actions()]
    assert "Ctrl+1" in shortcuts
    assert "Ctrl+4" in shortcuts
    assert "Ctrl+Q" in shortcuts
    assert "F1" in shortcuts


def test_theme_stylesheets_valid():
    for theme in ["dark", "light", "high_contrast"]:
        css = build_stylesheet(theme, 1.0)
        assert "{fs}" not in css and "{fs_title}" not in css
        assert len(css) > 500


def test_i18n_arabic_english():
    ar = I18n("ar")
    en = I18n("en")
    assert ar("vision") == "بصيرة VISION"
    assert en("vision") == "BASIRA VISION"
    assert ar.rtl is True and en.rtl is False
    assert ar("missing_key") == "missing_key"


def test_window_resizable_and_min_size(window):
    assert window.minimumSize().width() >= 900
    window.resize(1400, 900)
    assert window.size().width() == 1400


def test_status_chips_present(window):
    assert window.camera_chip.text() == window.i18n("camera_off")
    assert window.privacy_chip.text() == window.i18n("local_processing")


def test_settings_page_roundtrip(window, tmp_home):
    from basira.config import load_settings

    page = window.pages["settings"]
    page.lang_combo.setCurrentIndex(1)  # English
    page.save()
    assert window.settings.language == "en"
    loaded = load_settings()
    assert loaded.language == "en"


def test_offscreen_app_run(qapp, tmp_home, monkeypatch):
    """Full app.main() smoke test with the existing QApplication."""
    import basira.desktop.app as app_module

    monkeypatch.setattr(app_module, "QApplication",
                        lambda *a, **k: qapp)
    monkeypatch.setattr(type(qapp), "exec", lambda self: 0)
    rc = app_module.main([])
    assert rc == 0
