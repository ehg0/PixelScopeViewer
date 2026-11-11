"""タイル比較モードのタイルへの画像登録 dialog。"""

import json
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.core.tile_layout import Cell, TileLayout
from PixelScopeViewer.ui.common import defaults, theme

IMAGE_IDS_MIME = "application/x-pixelscope-image-ids"
_ID_ROLE = Qt.UserRole


def _item(img: dict) -> QListWidgetItem:
    item = QListWidgetItem(Path(img["path"]).name)
    item.setData(_ID_ROLE, img["id"])
    item.setToolTip(img["path"])
    thumb = img.get("thumbnail_pixmap")
    if thumb is not None:
        item.setIcon(QIcon(thumb))
    return item


def _ids_of(items) -> list[int]:
    return [item.data(_ID_ROLE) for item in items]


class _ImageSourceList(QListWidget):
    """読み込み済みの画像の一覧。選んだ画像の id を drag で渡す。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setDefaultDropAction(Qt.CopyAction)

    def mimeData(self, items):
        data = QMimeData()
        data.setData(IMAGE_IDS_MIME, json.dumps(_ids_of(items)).encode())
        return data

    def mimeTypes(self):
        return [IMAGE_IDS_MIME]


class _CellList(QListWidget):
    """マスの登録リスト。画像一覧からの drop で追加し、drag で並べ替え、Delete キーで削除する。"""

    def __init__(self, images_by_id: dict[int, dict], parent=None):
        super().__init__(parent)
        self._images_by_id = images_by_id
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAcceptDrops(True)

    def set_ids(self, image_ids: list[int]):
        self.clear()
        for image_id in image_ids:
            self.addItem(_item(self._images_by_id[image_id]))

    def ids(self) -> list[int]:
        return _ids_of(self.item(i) for i in range(self.count()))

    def remove_selected(self):
        for item in self.selectedItems():
            self.takeItem(self.row(item))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.remove_selected()
            return
        super().keyPressEvent(event)

    def _is_external(self, event) -> bool:
        return event.mimeData().hasFormat(IMAGE_IDS_MIME) and event.source() is not self

    def dragEnterEvent(self, event):
        if self._is_external(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._is_external(event):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if not self._is_external(event):
            super().dropEvent(event)
            return
        ids = json.loads(bytes(event.mimeData().data(IMAGE_IDS_MIME)).decode())
        target = self.itemAt(event.position().toPoint())
        row = self.row(target) if target is not None else self.count()
        for offset, image_id in enumerate(ids):
            if image_id in self._images_by_id:
                self.insertItem(row + offset, _item(self._images_by_id[image_id]))
        event.setDropAction(Qt.CopyAction)
        event.accept()


class TileRegisterDialog(QDialog):
    """グリッドの大きさと、各マスに登録する画像（n / b で送る順）を決める dialog。

    渡された TileLayout の copy を編集し、OK で result_layout に入れる。
    グリッドから外れたマスの登録は残し、その数を警告として表示する。
    """

    def __init__(self, parent, images: list[dict], layout: TileLayout):
        super().__init__(parent)
        self.setWindowTitle("タイルへの画像登録")
        self.resize(*defaults.TILE_REGISTER_DIALOG_SIZE)
        self._layout = deepcopy(layout)
        self._images_by_id = {img["id"]: img for img in images}
        # 閉じた画像の id は登録から外す
        for stack_index, stack in enumerate(self._layout.stacks):
            self._layout.stacks[stack_index] = [i for i in stack if i in self._images_by_id]
        self._cells: dict[Cell, tuple[QGroupBox, _CellList]] = {}
        self.result_layout: TileLayout | None = None

        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("画像一覧（タイルへ drag & drop）"))
        self.source_list = _ImageSourceList()
        for img in images:
            self.source_list.addItem(_item(img))
        left_layout.addWidget(self.source_list)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        top.addWidget(QLabel("グリッド:"))
        self.grid_combo = QComboBox()
        for rows, cols in defaults.TILE_GRID_SIZES:
            self.grid_combo.addItem(f"{rows}×{cols}", (rows, cols))
        self.grid_combo.setCurrentIndex(self.grid_index(self._layout.rows, self._layout.cols))
        self.grid_combo.currentIndexChanged.connect(self._on_grid_changed)
        top.addWidget(self.grid_combo)
        top.addStretch()
        self.clear_all_btn = QPushButton("全リセット")
        self.clear_all_btn.setToolTip("全タイルの登録を消す")
        self.clear_all_btn.clicked.connect(self._clear_all)
        top.addWidget(self.clear_all_btn)
        right_layout.addLayout(top)

        self.cell_area = QWidget()
        self.cell_grid = QGridLayout(self.cell_area)
        self.cell_grid.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.cell_area, 1)

        hidden_row = QHBoxLayout()
        self.hidden_label = QLabel()
        self.hidden_label.setStyleSheet(f"color: {theme.TEXT_MUTED_COLOR};")
        hidden_row.addWidget(self.hidden_label)
        self.clear_hidden_btn = QPushButton("表示していないタイルの登録を消す")
        self.clear_hidden_btn.clicked.connect(self._clear_hidden)
        hidden_row.addWidget(self.clear_hidden_btn)
        hidden_row.addStretch()
        right_layout.addLayout(hidden_row)

        hint = QLabel("タイル内は drag で並べ替え、Delete キーで選んだ画像を外します。n / b で上から順に送ります。")
        hint.setStyleSheet(f"color: {theme.TEXT_HINT_COLOR};")
        right_layout.addWidget(hint)
        splitter.addWidget(right)
        splitter.setSizes([280, 720])

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._build_cells()

    def grid_index(self, rows: int, cols: int) -> int:
        """グリッドの選択肢の index を返す。ない場合は -1。"""
        # tuple の data は findData で見つからないことがあるため、自前で探す
        return next((i for i in range(self.grid_combo.count()) if self.grid_combo.itemData(i) == (rows, cols)), -1)

    # --- マス ---
    def _build_cells(self):
        for box, _ in self._cells.values():
            self.cell_grid.removeWidget(box)
            box.deleteLater()
        self._cells.clear()
        layout = self._layout
        for cell in layout.visible_cells():
            box = QGroupBox()
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(4, 4, 4, 4)
            cell_list = _CellList(self._images_by_id)
            cell_list.set_ids(layout.stack(cell))
            cell_list.model().rowsInserted.connect(self._update_titles)
            cell_list.model().rowsRemoved.connect(self._update_titles)
            box_layout.addWidget(cell_list)
            reset_btn = QPushButton("リセット")
            reset_btn.setToolTip("このタイルの登録を消す")
            reset_btn.clicked.connect(cell_list.clear)
            box_layout.addWidget(reset_btn)
            self.cell_grid.addWidget(box, *cell)
            self._cells[cell] = (box, cell_list)
        for r in range(layout.max_rows):
            self.cell_grid.setRowStretch(r, 1 if r < layout.rows else 0)
        for c in range(layout.max_cols):
            self.cell_grid.setColumnStretch(c, 1 if c < layout.cols else 0)
        self._update_titles()
        self._update_hidden()

    def _update_titles(self, *_):
        for cell, (box, cell_list) in self._cells.items():
            box.setTitle(f"T{self._layout.tile_number(cell)}（{cell_list.count()} 枚）")

    def _store_cells(self):
        """表示中のマスの登録リストを編集中の TileLayout に書き戻す。"""
        for cell, (_, cell_list) in self._cells.items():
            self._layout.set_stack(cell, cell_list.ids())

    def _update_hidden(self):
        n = len(self._layout.hidden_cells())
        self.hidden_label.setText(f"表示していないタイルに登録があります（{n} 個）" if n else "")
        self.clear_hidden_btn.setVisible(bool(n))

    def _on_grid_changed(self, index: int):
        self._store_cells()
        self._layout.set_grid(*self.grid_combo.itemData(index))
        self._build_cells()

    def _clear_hidden(self):
        self._layout.clear_hidden()
        self._update_hidden()

    def _clear_all(self):
        for _, cell_list in self._cells.values():
            cell_list.clear()
        self._layout.clear_all()
        self._update_hidden()

    def cell_list(self, cell: Cell) -> _CellList:
        return self._cells[cell][1]

    def accept(self):
        self._store_cells()
        if not self._layout.has_visible_images():
            QMessageBox.information(self, "タイルへの画像登録", "表示するタイルに画像が登録されていません。")
            return
        self._layout.frame = min(self._layout.frame, self._layout.frame_count() - 1)
        self.result_layout = self._layout
        super().accept()
