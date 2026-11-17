"""Theme and accessibility styling: dark / light / high-contrast + text scale."""
from __future__ import annotations

DARK = """
QWidget { background-color: #12141a; color: #e8eaf0; font-size: {fs}px; }
QMainWindow, QDialog { background-color: #12141a; }
#sidebar { background-color: #1a1d26; border: none; }
#sidebar QPushButton {
    text-align: right; padding: 12px 14px; border: none; border-radius: 8px;
    color: #c7cbd6; font-size: {fs}px;
}
#sidebar QPushButton:hover { background-color: #242836; }
#sidebar QPushButton:checked { background-color: #2f6fed; color: white; font-weight: bold; }
#header { background-color: #1a1d26; border-bottom: 1px solid #262b38; }
QLabel#pageTitle { font-size: {fs_title}px; font-weight: bold; }
QLabel#statusChip { padding: 4px 10px; border-radius: 10px; background: #242836; }
QLabel#statusOn { background: #1e5c3a; color: #b8f5cd; }
QLabel#statusOff { background: #5c1e1e; color: #f5b8b8; }
QFrame#card { background: #1a1d26; border: 1px solid #262b38; border-radius: 10px; }
QPushButton {
    background: #2f6fed; color: white; border: none; border-radius: 8px;
    padding: 10px 18px; font-size: {fs}px;
}
QPushButton:hover { background: #4a83f2; }
QPushButton:disabled { background: #33384a; color: #7d8496; }
QPushButton#secondary { background: #242836; color: #e8eaf0; }
QPushButton#danger { background: #b03434; }
QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #161923; border: 1px solid #2b3040; border-radius: 6px;
    padding: 8px; font-size: {fs}px; color: #e8eaf0;
    selection-background-color: #2f6fed;
}
QListWidget { background: #161923; border: 1px solid #2b3040; border-radius: 6px; }
QSlider::groove:horizontal { height: 6px; background: #2b3040; border-radius: 3px; }
QSlider::handle:horizontal { width: 18px; margin: -7px 0; background: #2f6fed; border-radius: 9px; }
QLabel#alert { color: #ff9d9d; font-weight: bold; font-size: {fs}px; }
QLabel#success { color: #9de3b0; }
*:focus { border: 2px solid #ffd166; }
QToolTip { background: #242836; color: #e8eaf0; border: 1px solid #2f6fed; }
"""

LIGHT = """
QWidget { background-color: #f5f6fa; color: #1a1d26; font-size: {fs}px; }
QMainWindow, QDialog { background-color: #f5f6fa; }
#sidebar { background-color: #ffffff; border: none; }
#sidebar QPushButton {
    text-align: right; padding: 12px 14px; border: none; border-radius: 8px;
    color: #3a3f4d; font-size: {fs}px;
}
#sidebar QPushButton:hover { background-color: #eef1f8; }
#sidebar QPushButton:checked { background-color: #2f6fed; color: white; font-weight: bold; }
#header { background-color: #ffffff; border-bottom: 1px solid #e3e6ee; }
QLabel#pageTitle { font-size: {fs_title}px; font-weight: bold; }
QLabel#statusChip { padding: 4px 10px; border-radius: 10px; background: #eef1f8; }
QLabel#statusOn { background: #d9f2e3; color: #14683a; }
QLabel#statusOff { background: #f8d9d9; color: #831414; }
QFrame#card { background: #ffffff; border: 1px solid #e3e6ee; border-radius: 10px; }
QPushButton {
    background: #2f6fed; color: white; border: none; border-radius: 8px;
    padding: 10px 18px; font-size: {fs}px;
}
QPushButton:hover { background: #4a83f2; }
QPushButton:disabled { background: #c8cdd9; color: #7d8496; }
QPushButton#secondary { background: #eef1f8; color: #1a1d26; }
QPushButton#danger { background: #c0392b; color: white; }
QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #ffffff; border: 1px solid #d6dbe6; border-radius: 6px;
    padding: 8px; font-size: {fs}px;
    selection-background-color: #2f6fed;
}
QListWidget { background: #ffffff; border: 1px solid #d6dbe6; border-radius: 6px; }
QSlider::groove:horizontal { height: 6px; background: #d6dbe6; border-radius: 3px; }
QSlider::handle:horizontal { width: 18px; margin: -7px 0; background: #2f6fed; border-radius: 9px; }
QLabel#alert { color: #b03030; font-weight: bold; font-size: {fs}px; }
QLabel#success { color: #1e7a44; }
*:focus { border: 2px solid #b7791f; }
QToolTip { background: #ffffff; color: #1a1d26; border: 1px solid #2f6fed; }
"""

HIGH_CONTRAST = """
QWidget { background-color: #000000; color: #ffffff; font-size: {fs}px; }
QMainWindow, QDialog { background-color: #000000; }
#sidebar { background-color: #000000; border-right: 2px solid #ffffff; }
#sidebar QPushButton {
    text-align: right; padding: 12px 14px; border: 2px solid #ffffff;
    border-radius: 4px; color: #ffffff; background: #000000; font-size: {fs}px;
}
#sidebar QPushButton:checked { background: #ffff00; color: #000000; font-weight: bold; }
#header { background-color: #000000; border-bottom: 2px solid #ffffff; }
QLabel#pageTitle { font-size: {fs_title}px; font-weight: bold; color: #ffff00; }
QLabel#statusChip { padding: 4px 10px; border: 2px solid #ffffff; }
QLabel#statusOn { background: #00ff00; color: #000000; }
QLabel#statusOff { background: #ff0000; color: #ffffff; }
QFrame#card { background: #000000; border: 2px solid #ffffff; border-radius: 4px; }
QPushButton {
    background: #ffff00; color: #000000; border: 2px solid #ffffff;
    border-radius: 4px; padding: 10px 18px; font-size: {fs}px; font-weight: bold;
}
QPushButton:disabled { background: #555555; color: #bbbbbb; }
QPushButton#secondary { background: #000000; color: #ffffff; }
QPushButton#danger { background: #ff0000; color: #ffffff; }
QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #000000; border: 2px solid #ffffff; border-radius: 4px;
    padding: 8px; font-size: {fs}px; color: #ffffff;
}
QListWidget { background: #000000; border: 2px solid #ffffff; }
QLabel#alert { color: #ff5555; font-weight: bold; font-size: {fs}px; }
QLabel#success { color: #00ff00; }
*:focus { border: 3px solid #00ffff; }
QToolTip { background: #000000; color: #ffffff; border: 2px solid #ffff00; }
"""

THEMES = {"dark": DARK, "light": LIGHT, "high_contrast": HIGH_CONTRAST}


def build_stylesheet(theme: str = "dark", text_scale: float = 1.0) -> str:
    base = 14
    fs = max(10, round(base * text_scale))
    fs_title = max(14, round(19 * text_scale))
    return THEMES.get(theme, DARK).replace("{fs}", str(fs)).replace(
        "{fs_title}", str(fs_title))
