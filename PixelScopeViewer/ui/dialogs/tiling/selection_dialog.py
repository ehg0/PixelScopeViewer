"""複数画像比較の画像と grid サイズの選択 dialog。"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from PixelScopeViewer.ui import defaults


class DraggableListWidget(QListWidget):
    """drag & drop で項目を並べ替えられる QListWidget。"""

    def __init__(self):
        super().__init__()
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDefaultDropAction(Qt.MoveAction)


class TileSelectionDialog(QDialog):
    """比較する画像（表示順）と grid サイズを選択する dialog。"""

    def __init__(self, parent, image_list: list[dict]):
        super().__init__(parent)
        self.setWindowTitle("複数画像比較 - 画像選択")
        self.resize(*defaults.TILE_SELECTION_DIALOG_SIZE)

        self.image_list = image_list
        self.grid_size = defaults.TILE_GRID_SIZE
        self.selected_indices = []

        self._build_ui()

        # grid に収まる枚数だけ先頭から選択しておく
        self._auto_select_default()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        grid_layout = QHBoxLayout()
        grid_layout.addWidget(QLabel("グリッドサイズ (h, w):"))

        self.grid_combo = QComboBox()
        for rows, cols in defaults.TILE_GRID_SIZES:
            self.grid_combo.addItem(f"{rows}x{cols} ({rows * cols}枚)", (rows, cols))
        # findData は tuple を比較できないため index を直接求める
        self.grid_combo.setCurrentIndex(defaults.TILE_GRID_SIZES.index(defaults.TILE_GRID_SIZE))
        self.grid_combo.currentIndexChanged.connect(self._on_grid_changed)

        grid_layout.addWidget(self.grid_combo)
        grid_layout.addStretch()
        layout.addLayout(grid_layout)

        label = QLabel("画像を選択 (ドラッグで並び替え):")
        layout.addWidget(label)

        self.image_list_widget = DraggableListWidget()

        for i, img_info in enumerate(self.image_list):
            path = img_info.get("path", f"Image {i + 1}")
            filename = Path(path).name if path else f"Image {i + 1}"

            arr = img_info.get("base_array", img_info.get("array"))
            dtype_str = f"({arr.dtype.name})" if arr is not None else ""

            item_text = f"{i + 1}: {filename} {dtype_str}"
            item = QListWidgetItem(item_text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, i)

            self.image_list_widget.addItem(item)

        layout.addWidget(self.image_list_widget)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # status_label の作成後に grid サイズを反映する
        self._on_grid_changed()

        btn_layout = QHBoxLayout()

        select_all_btn = QPushButton("すべて選択")
        select_all_btn.clicked.connect(self._select_all)
        btn_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("選択解除")
        deselect_all_btn.clicked.connect(self._deselect_all)
        btn_layout.addWidget(deselect_all_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        dialog_btn_layout = QHBoxLayout()
        dialog_btn_layout.addStretch()

        compare_btn = QPushButton("比較")
        compare_btn.setDefault(True)
        compare_btn.clicked.connect(self._on_compare)
        dialog_btn_layout.addWidget(compare_btn)

        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)
        dialog_btn_layout.addWidget(cancel_btn)

        layout.addLayout(dialog_btn_layout)

    def _on_grid_changed(self):
        self.grid_size = self.grid_combo.currentData()
        max_tiles = self.grid_size[0] * self.grid_size[1]
        self.status_label.setText(f"最大{max_tiles}枚まで選択可能")

    def _select_all(self):
        """grid に収まる枚数まで先頭から選択する。"""
        max_tiles = self.grid_size[0] * self.grid_size[1]

        for i in range(self.image_list_widget.count()):
            item = self.image_list_widget.item(i)
            if i < max_tiles:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

    def _deselect_all(self):
        for i in range(self.image_list_widget.count()):
            item = self.image_list_widget.item(i)
            item.setCheckState(Qt.Unchecked)

    def _auto_select_default(self):
        """grid に収まる枚数だけ先頭から選択する。"""
        max_tiles = self.grid_size[0] * self.grid_size[1]
        count = min(max_tiles, self.image_list_widget.count())

        for i in range(count):
            item = self.image_list_widget.item(i)
            item.setCheckState(Qt.Checked)

    def _on_compare(self):
        """選択を検証し、選択した画像の index を list の表示順で保存して閉じる。"""
        selected = []
        for i in range(self.image_list_widget.count()):
            item = self.image_list_widget.item(i)
            if item.checkState() == Qt.Checked:
                original_idx = item.data(Qt.UserRole)
                selected.append(original_idx)

        max_tiles = self.grid_size[0] * self.grid_size[1]

        if len(selected) < 2:
            QMessageBox.warning(self, "複数画像比較", "2枚以上の画像を選択してください。")
            return

        if len(selected) > max_tiles:
            QMessageBox.warning(
                self,
                "複数画像比較",
                f"選択できる画像は最大{max_tiles}枚です。\n現在{len(selected)}枚選択されています。",
            )
            return

        self.selected_indices = selected
        self.accept()

    def get_selection(self) -> tuple[tuple[int, int], list[int]]:
        """選択結果を返す。

        Returns:
            ((行数, 列数), 表示順の画像 index のリスト)。
        """
        return (self.grid_size, self.selected_indices)
