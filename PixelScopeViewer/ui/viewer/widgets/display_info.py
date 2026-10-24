"""表示領域の情報を表示する widget。"""

import contextlib

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QGroupBox, QMenu, QTableWidget, QTableWidgetItem, QVBoxLayout


class DisplayInfoWidget(QGroupBox):
    """現在の表示領域の画像座標・サイズを表示する widget。"""

    def __init__(self, viewer):
        super().__init__()  # title は dock 側で表示する
        self.viewer = viewer

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Property", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setVisible(False)
        self.table.setRowCount(8)
        # 小さめの font と行高にして縦 scroll を出さない
        font = self.table.font()
        with contextlib.suppress(Exception):
            font.setPointSize(max(font.pointSize() - 1, 9))
        self.table.setFont(font)
        self.table.verticalHeader().setDefaultSectionSize(18)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.verticalHeader().setVisible(False)

        properties = ["X Start", "Y Start", "X End", "Y End", "Width", "Height", "Diagonal", "Pixel Count"]
        for i, prop in enumerate(properties):
            item = QTableWidgetItem(prop)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, item)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addStretch()

        self._fit_table_height()

        self.viewer.scale_changed.connect(self.update_info)
        self.viewer.image_changed.connect(self.update_info)
        # scroll や viewport の resize でも更新する
        sa = self.viewer.scroll_area
        sa.horizontalScrollBar().valueChanged.connect(self.update_info)
        sa.verticalScrollBar().valueChanged.connect(self.update_info)
        sa.viewport().installEventFilter(self)

        self.update_info()

    def _fit_table_height(self):
        try:
            vh = self.table.verticalHeader()
            hh = self.table.horizontalHeader()
            frame = 2 * self.table.frameWidth()
            total = hh.height() + (vh.defaultSectionSize() * self.table.rowCount()) + frame
            self.table.setMinimumHeight(total)
            self.table.setMaximumHeight(total)
        except Exception:
            pass

    def eventFilter(self, obj, event):
        try:
            if obj is self.viewer.scroll_area.viewport() and event.type() == QEvent.Resize:
                self.update_info()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def update_info(self):
        """表示領域の情報を更新する。"""
        if self.viewer.current_index is None or not self.viewer.images:
            for i in range(8):
                self.table.setItem(i, 1, QTableWidgetItem(""))
            return

        scroll_area = self.viewer.scroll_area
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()
        h_scroll = scroll_area.horizontalScrollBar().value()
        v_scroll = scroll_area.verticalScrollBar().value()

        # 画像座標に変換する
        scale = self.viewer.scale
        x_start = int(h_scroll / scale)
        y_start = int(v_scroll / scale)
        x_end = int((h_scroll + viewport_width) / scale)
        y_end = int((v_scroll + viewport_height) / scale)

        img = self.viewer.images[self.viewer.current_index]["array"]
        img_h, img_w = img.shape[:2]
        x_end = min(x_end, img_w - 1)
        y_end = min(y_end, img_h - 1)

        width = x_end - x_start + 1
        height = y_end - y_start + 1
        diagonal = (width**2 + height**2) ** 0.5
        pixel_count = width * height

        values = [
            str(x_start),
            str(y_start),
            str(x_end),
            str(y_end),
            str(width),
            str(height),
            f"{diagonal:.2f}",
            f"{pixel_count:,}",
        ]
        for i, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 1, item)

    def _show_context_menu(self, pos):
        menu = QMenu()
        copy_action = menu.addAction("コピー")
        action = menu.exec_(self.table.mapToGlobal(pos))
        if action == copy_action:
            self._copy_selection()

    def _copy_selection(self):
        """選択中のセルをカンマ区切りで clipboard にコピーする。"""
        selection = self.table.selectedRanges()
        if not selection:
            return

        rows = []
        for sel_range in selection:
            for row in range(sel_range.topRow(), sel_range.bottomRow() + 1):
                cols = []
                for col in range(sel_range.leftColumn(), sel_range.rightColumn() + 1):
                    item = self.table.item(row, col)
                    cols.append(item.text() if item else "")
                rows.append(",".join(cols))

        text = "\n".join(rows)
        QGuiApplication.clipboard().setText(text)
