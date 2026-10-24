"""ROI の情報を表示・編集する widget。"""

import contextlib

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QMenu,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ROIInfoWidget(QGroupBox):
    """ROI の座標・サイズを表示し、編集内容を即座に ROI へ反映する widget。"""

    def __init__(self, viewer):
        super().__init__()  # title は dock 側で表示する
        self.viewer = viewer
        self._updating = False  # 再入防止の flag

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Property", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setVisible(False)
        self.table.setRowCount(8)
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

        # Diagonal と Pixel Count 以外は spin box で編集可能にする
        self.spin_boxes = {}
        editable_rows = [0, 1, 2, 3, 4, 5]

        for row in editable_rows:
            spin_box = QSpinBox()
            spin_box.setMinimum(0)
            spin_box.setMaximum(100000)
            spin_box.setSingleStep(1)
            spin_box.valueChanged.connect(lambda value, r=row: self.on_spin_changed(r, value))
            spin_box.setFont(font)
            self.spin_boxes[row] = spin_box

            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.addWidget(spin_box)
            layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 1, widget)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addStretch()

        self._fit_table_height()

        self.viewer.roi_changed.connect(self.update_info)
        self.viewer.image_changed.connect(self.update_info)

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

    def on_spin_changed(self, row, value):
        """spin box の変更を画像範囲内に収めて ROI へ反映する。"""
        # プログラムからの更新は無視する
        if self._updating:
            return
        if self.viewer.state.current_index is None:
            return

        img = self.viewer.images[self.viewer.state.current_index]["array"]
        img_h, img_w = img.shape[:2]

        current_rect = self.viewer.state.roi
        if current_rect is None:
            return

        x, y, w, h = current_rect.x(), current_rect.y(), current_rect.width(), current_rect.height()

        if row == 0:  # X Start
            x = max(0, min(value, img_w - w))
            self.spin_boxes[0].blockSignals(True)
            self.spin_boxes[0].setValue(x)
            self.spin_boxes[0].blockSignals(False)
        elif row == 1:  # Y Start
            y = max(0, min(value, img_h - h))
            self.spin_boxes[1].blockSignals(True)
            self.spin_boxes[1].setValue(y)
            self.spin_boxes[1].blockSignals(False)
        elif row == 2:  # X End
            x_end = max(x, min(value, img_w - 1))
            w = x_end - x + 1
            self.spin_boxes[2].blockSignals(True)
            self.spin_boxes[2].setValue(x_end)
            self.spin_boxes[2].blockSignals(False)
            self.spin_boxes[4].blockSignals(True)
            self.spin_boxes[4].setValue(w)
            self.spin_boxes[4].blockSignals(False)
        elif row == 3:  # Y End
            y_end = max(y, min(value, img_h - 1))
            h = y_end - y + 1
            self.spin_boxes[3].blockSignals(True)
            self.spin_boxes[3].setValue(y_end)
            self.spin_boxes[3].blockSignals(False)
            self.spin_boxes[5].blockSignals(True)
            self.spin_boxes[5].setValue(h)
            self.spin_boxes[5].blockSignals(False)
        elif row == 4:  # Width
            w = max(1, min(value, img_w - x))
            self.spin_boxes[4].blockSignals(True)
            self.spin_boxes[4].setValue(w)
            self.spin_boxes[4].blockSignals(False)
            x_end = x + w - 1
            self.spin_boxes[2].blockSignals(True)
            self.spin_boxes[2].setValue(x_end)
            self.spin_boxes[2].blockSignals(False)
        elif row == 5:  # Height
            h = max(1, min(value, img_h - y))
            self.spin_boxes[5].blockSignals(True)
            self.spin_boxes[5].setValue(h)
            self.spin_boxes[5].blockSignals(False)
            y_end = y + h - 1
            self.spin_boxes[3].blockSignals(True)
            self.spin_boxes[3].setValue(y_end)
            self.spin_boxes[3].blockSignals(False)

        # 倍率による丸め誤差を避けるため画像座標で ROI を設定する
        new_rect_img = QRect(x, y, w, h)
        self.viewer.set_roi_from_image_rect(new_rect_img)

    def update_info(self):
        """ROI の情報を更新する。"""
        # setMaximum/setValue の clamp による valueChanged の連鎖を防ぐ
        self._updating = True
        try:
            if self.viewer.state.current_index is None or not self.viewer.images:
                for spin_box in self.spin_boxes.values():
                    spin_box.setValue(0)
                self.table.setItem(6, 1, QTableWidgetItem(""))
                self.table.setItem(7, 1, QTableWidgetItem(""))
                return

            img = self.viewer.images[self.viewer.state.current_index]["array"]
            img_h, img_w = img.shape[:2]

            current_rect = self.viewer.state.roi
            if current_rect is None or current_rect.isNull():
                for spin_box in self.spin_boxes.values():
                    spin_box.setValue(0)
                self.table.setItem(6, 1, QTableWidgetItem(""))
                self.table.setItem(7, 1, QTableWidgetItem(""))
                return

            x = current_rect.x()
            y = current_rect.y()
            w = current_rect.width()
            h = current_rect.height()
            x_end = current_rect.right()
            y_end = current_rect.bottom()

            # 画像サイズに合わせて入力範囲を設定する
            self.spin_boxes[0].setMinimum(0)  # X Start
            self.spin_boxes[0].setMaximum(img_w - 1)
            self.spin_boxes[1].setMinimum(0)  # Y Start
            self.spin_boxes[1].setMaximum(img_h - 1)
            self.spin_boxes[2].setMinimum(0)  # X End
            self.spin_boxes[2].setMaximum(img_w - 1)
            self.spin_boxes[3].setMinimum(0)  # Y End
            self.spin_boxes[3].setMaximum(img_h - 1)
            self.spin_boxes[4].setMinimum(1)  # Width
            self.spin_boxes[4].setMaximum(img_w)
            self.spin_boxes[5].setMinimum(1)  # Height
            self.spin_boxes[5].setMaximum(img_h)

            values = [x, y, x_end, y_end, w, h]
            for i, value in enumerate(values):
                self.spin_boxes[i].blockSignals(True)
                self.spin_boxes[i].setValue(value)
                self.spin_boxes[i].blockSignals(False)

            diagonal = (w**2 + h**2) ** 0.5
            diagonal_item = QTableWidgetItem(f"{diagonal:.2f}")
            diagonal_item.setFlags(diagonal_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(6, 1, diagonal_item)

            pixel_count = w * h if 0 <= x < img_w and 0 <= y < img_h else 0
            pixel_count_item = QTableWidgetItem(f"{pixel_count:,}")
            pixel_count_item.setFlags(pixel_count_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(7, 1, pixel_count_item)
        finally:
            self._updating = False

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
                    # spin box の行は spin box の値を使う
                    if row in self.spin_boxes:
                        widget = self.table.cellWidget(row, col)
                        if widget and col == 1:
                            cols.append(str(self.spin_boxes[row].value()))
                        else:
                            item = self.table.item(row, col)
                            cols.append(item.text() if item else "")
                    else:
                        item = self.table.item(row, col)
                        cols.append(item.text() if item else "")
                rows.append(",".join(cols))

        text = "\n".join(rows)
        QGuiApplication.clipboard().setText(text)
