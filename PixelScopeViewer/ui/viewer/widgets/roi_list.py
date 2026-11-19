"""ROI 一覧の table と操作 button。"""

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.ui.analysis.overlay import roi_color

_HEADERS = ["", "Name", "X", "Y", "W", "H"]
# 編集できる X・Y・W・H の列と、その最小値
_RECT_COLUMNS = {2: 0, 3: 0, 4: 1, 5: 1}
_MAX_COORD = 100000


class _IntDelegate(QStyledItemDelegate):
    """X・Y・W・H の cell を spin box で編集する。"""

    def createEditor(self, parent, option, index):
        editor = QSpinBox(parent)
        editor.setRange(_RECT_COLUMNS[index.column()], _MAX_COORD)
        editor.setFrame(False)
        editor.setButtonSymbols(QSpinBox.NoButtons)
        editor.setAlignment(Qt.AlignRight)
        return editor

    def setEditorData(self, editor, index):
        editor.setValue(int(index.data()))
        editor.selectAll()

    def setModelData(self, editor, model, index):
        editor.interpretText()
        model.setData(index, str(editor.value()))


class RoiListWidget(QWidget):
    """ROI 一覧を表示し、削除・保存・読み込み・☑・選択（編集中 ROI との連動）を viewer.roi_list に伝える。

    登録は ROI Area tab の button と R キーで行う。
    """

    def __init__(self, viewer):
        super().__init__()
        self.viewer = viewer
        self._updating = False  # 再入防止の flag

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)

        self.remove_btn = QPushButton("削除")
        self.remove_btn.setToolTip("選択中のROIを一覧から削除")
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn = QPushButton("全削除")
        self.clear_btn.clicked.connect(self._clear)
        self.save_btn = QPushButton("保存...")
        self.save_btn.setToolTip("ROI一覧を CSV ファイルに保存")
        self.save_btn.clicked.connect(lambda: viewer.roi_list.save_dialog())
        self.load_btn = QPushButton("読込...")
        self.load_btn.setToolTip("CSV ファイルの ROI一覧で今の一覧を置き換える")
        self.load_btn.clicked.connect(lambda: viewer.roi_list.load_dialog())
        # 1 行に並べると Info dock の幅が広がるため、2 行に分ける
        buttons = QGridLayout()
        for i, b in enumerate((self.remove_btn, self.clear_btn, self.save_btn, self.load_btn)):
            buttons.addWidget(b, i // 2, i % 2)
        layout.addLayout(buttons)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(18)
        # X・Y・W・H は double click で編集する
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self._delegate = _IntDelegate(self.table)
        for col in _RECT_COLUMNS:
            self.table.setItemDelegateForColumn(col, self._delegate)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setToolTip(
            "選択した ROI は編集中ROIと連動します。☑ は解析ビューの「登録ROI」表示の対象です。"
            "X・Y・W・H は double click で編集できます"
        )
        # ☑・Name は内容に合わせ、X・Y・W・H は残りの幅を等分して水平 scroll bar を出さない
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for col in range(len(_HEADERS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents if col < 2 else QHeaderView.Stretch)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)

        viewer.rois_changed.connect(self.refresh)
        # 連動中の ROI の座標を更新する
        viewer.roi_changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        """viewer.state.rois の内容を table に反映し、連動中の ROI の行を選択する。

        cell の item は使い回し、値が変わった cell だけを書き換える（編集中の editor を閉じないため）。
        """
        state = self.viewer.state
        self._updating = True
        try:
            self.table.setRowCount(len(state.rois))
            linked_row = None
            for row, entry in enumerate(state.rois):
                check = self._item(row, 0, Qt.ItemIsUserCheckable)
                check.setCheckState(Qt.Checked if entry.enabled else Qt.Unchecked)
                check.setData(Qt.UserRole, entry.id)
                color = roi_color(entry.id, 0, state.roi_color_overrides).name()
                if check.data(Qt.UserRole + 1) != color:
                    pix = QPixmap(12, 12)
                    pix.fill(QColor(color))
                    check.setIcon(QIcon(pix))
                    check.setData(Qt.UserRole + 1, color)
                r = entry.rect
                for col, value in enumerate((entry.name, r.x(), r.y(), r.width(), r.height()), start=1):
                    item = self._item(row, col, Qt.ItemIsEditable if col in _RECT_COLUMNS else Qt.NoItemFlags)
                    if item.text() != str(value):
                        item.setText(str(value))
                if entry.id == state.linked_roi_id:
                    linked_row = row
            selected = [i.row() for i in self.table.selectionModel().selectedRows()]
            if selected != ([linked_row] if linked_row is not None else []):
                self.table.clearSelection()
                if linked_row is not None:
                    self.table.selectRow(linked_row)
        finally:
            self._updating = False
        self.remove_btn.setEnabled(linked_row is not None)
        self.clear_btn.setEnabled(bool(state.rois))
        self.save_btn.setEnabled(bool(state.rois))

    def _item(self, row: int, col: int, extra_flags) -> QTableWidgetItem:
        """cell の item を返す。なければ作る。"""
        item = self.table.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | extra_flags)
            if col in _RECT_COLUMNS:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, col, item)
        return item

    def _row_id(self, row: int) -> int:
        return self.table.item(row, 0).data(Qt.UserRole)

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._updating:
            return
        roi_id = self._row_id(item.row())
        if item.column() == 0:
            self.viewer.roi_list.set_enabled(roi_id, item.checkState() == Qt.Checked)
        elif item.column() in _RECT_COLUMNS:
            x, y, w, h = (int(self.table.item(item.row(), col).text()) for col in _RECT_COLUMNS)
            # 編集の確定処理の途中で table を作り直さないよう、反映は event loop に戻ってから行う
            QTimer.singleShot(0, lambda: self.viewer.roi_list.set_rect(roi_id, QRect(x, y, w, h)))

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
