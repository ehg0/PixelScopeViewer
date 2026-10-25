"""ROI 一覧の table と操作 button。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.ui.analysis.overlay import roi_color

_HEADERS = ["", "Name", "X", "Y", "W", "H"]


class RoiListWidget(QWidget):
    """ROI 一覧を表示し、登録・削除・保存・読み込み・☑・選択（編集中 ROI との連動）を viewer.roi_list に伝える。"""

    def __init__(self, viewer):
        super().__init__()
        self.viewer = viewer
        self._updating = False  # 再入防止の flag

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        title = QLabel("ROI一覧")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        self.add_btn = QPushButton("登録(R)")
        self.add_btn.setToolTip("編集中ROIを一覧の末尾に登録")
        self.add_btn.clicked.connect(lambda: viewer.roi_list.add_current())
        self.remove_btn = QPushButton("削除")
        self.remove_btn.setToolTip("選択中のROIを一覧から削除")
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn = QPushButton("全削除")
        self.clear_btn.clicked.connect(self._clear)
        self.save_btn = QPushButton("保存...")
        self.save_btn.clicked.connect(lambda: viewer.roi_list.save_dialog())
        self.load_btn = QPushButton("読込...")
        self.load_btn.clicked.connect(lambda: viewer.roi_list.load_dialog())
        for buttons in ((self.add_btn, self.remove_btn, self.clear_btn), (self.save_btn, self.load_btn)):
            row = QHBoxLayout()
            for b in buttons:
                row.addWidget(b)
            row.addStretch()
            layout.addLayout(row)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(18)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setToolTip("選択した ROI は編集中ROIと連動します。☑ は解析ビューの「登録ROI」表示の対象です")
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)

        viewer.rois_changed.connect(self.refresh)
        # 連動中の ROI の座標を更新する
        viewer.roi_changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        """viewer.state.rois の内容で table を作り直し、連動中の ROI の行を選択する。"""
        state = self.viewer.state
        self._updating = True
        try:
            self.table.setRowCount(len(state.rois))
            linked_row = None
            for row, entry in enumerate(state.rois):
                check = QTableWidgetItem()
                check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                check.setCheckState(Qt.Checked if entry.enabled else Qt.Unchecked)
                check.setData(Qt.UserRole, entry.id)
                pix = QPixmap(12, 12)
                pix.fill(QColor(roi_color(entry.id, 0, state.roi_color_overrides)))
                check.setIcon(QIcon(pix))
                self.table.setItem(row, 0, check)
                r = entry.rect
                for col, value in enumerate((entry.name, r.x(), r.y(), r.width(), r.height()), start=1):
                    item = QTableWidgetItem(str(value))
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    if col > 1:
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.table.setItem(row, col, item)
                if entry.id == state.linked_roi_id:
                    linked_row = row
            self.table.clearSelection()
            if linked_row is not None:
                self.table.selectRow(linked_row)
        finally:
            self._updating = False
        self.remove_btn.setEnabled(linked_row is not None)
        self.clear_btn.setEnabled(bool(state.rois))
        self.save_btn.setEnabled(bool(state.rois))

    def _row_id(self, row: int) -> int:
        return self.table.item(row, 0).data(Qt.UserRole)

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._updating or item.column() != 0:
            return
        self.viewer.roi_list.set_enabled(self._row_id(item.row()), item.checkState() == Qt.Checked)

    def _on_selection_changed(self):
        if self._updating:
            return
        rows = self.table.selectionModel().selectedRows()
        self.viewer.roi_list.link(self._row_id(rows[0].row()) if rows else None)

    def _remove_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.viewer.roi_list.remove(self._row_id(rows[0].row()))

    def _clear(self):
        answer = QMessageBox.question(self, "ROI一覧", "ROI一覧をすべて削除します。よろしいですか？")
        if answer == QMessageBox.Yes:
            self.viewer.roi_list.clear()
