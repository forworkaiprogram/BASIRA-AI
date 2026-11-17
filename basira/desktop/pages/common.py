"""Shared helpers for pages."""
from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


def frame_to_pixmap(frame_bgr: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(img)


def card(title: str = "") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(10)
    if title:
        lbl = QLabel(title)
        lbl.setStyleSheet("font-weight: bold;")
        lbl.setAccessibleName(title)
        lay.addWidget(lbl)
    return frame, lay


def make_label(text: str = "", accessible: str = "", object_name: str = "") -> QLabel:
    lbl = QLabel(text)
    if accessible:
        lbl.setAccessibleName(accessible)
    if object_name:
        lbl.setObjectName(object_name)
    return lbl
