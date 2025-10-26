"""Diff dialog for creating difference images.

This module provides a dialog for selecting two images from the
loaded image list and creating a difference image with configurable offset.
"""

from typing import Optional
import numpy as np
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QPushButton,
    QMessageBox,
)


class DiffDialog(QDialog):
    """Dialog for creating difference images between two images.

    Allows user to select two images from the loaded list and specify
    an offset value for the difference calculation.
    """

    def __init__(self, parent=None, image_list=None, default_offset: int = 256):
        super().__init__(parent)
        self.setWindowTitle("差分画像作成")
        self.resize(400, 120)
        self.image_list = image_list or []

        layout = QVBoxLayout(self)

        h1 = QHBoxLayout()
        h1.addWidget(QLabel("画像 A:"))
        self.combo_a = QComboBox()
        for i, info in enumerate(self.image_list):
            self.combo_a.addItem(f"{i+1}: {info.get('path','(untitled)')}")
        h1.addWidget(self.combo_a)
        layout.addLayout(h1)

        h2 = QHBoxLayout()
        h2.addWidget(QLabel("画像 B:"))
        self.combo_b = QComboBox()
        for i, info in enumerate(self.image_list):
            self.combo_b.addItem(f"{i+1}: {info.get('path','(untitled)')}")
        self.combo_b.setCurrentIndex(1)
        h2.addWidget(self.combo_b)
        layout.addLayout(h2)

        h3 = QHBoxLayout()
        h3.addWidget(QLabel("オフセット:"))
        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(0, 65535)
        self.offset_spin.setValue(default_offset)
        h3.addWidget(self.offset_spin)
        layout.addLayout(h3)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.ok_btn = QPushButton("作成")
        self.ok_btn.clicked.connect(self._on_ok)
        btns.addWidget(self.ok_btn)
        self.cancel_btn = QPushButton("キャンセル")
        self.cancel_btn.clicked.connect(self.reject)
        btns.addWidget(self.cancel_btn)
        layout.addLayout(btns)

    def _on_ok(self):
        a_idx = self.combo_a.currentIndex()
        b_idx = self.combo_b.currentIndex()
        if a_idx == b_idx:
            QMessageBox.information(self, "差分", "異なる2枚の画像を選んでください。")
            return
        self.selected_a = a_idx
        self.selected_b = b_idx
        self.offset = int(self.offset_spin.value())
        self.accept()

    def get_result(self):
        """選択結果を返します。

        戻り値:
            tuple: (image_a_index, image_b_index, offset) - 未選択時は各要素が None になります。
        """
        return (
            getattr(self, "selected_a", None),
            getattr(self, "selected_b", None),
            getattr(self, "offset", None),
        )
