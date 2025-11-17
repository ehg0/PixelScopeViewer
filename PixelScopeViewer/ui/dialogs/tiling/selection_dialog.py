"""Image selection dialog for tiling comparison."""

from pathlib import Path
from typing import List, Dict, Tuple, Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QMessageBox,
)
from PySide6.QtCore import Qt


class DraggableListWidget(QListWidget):
    """List widget with drag-and-drop reordering support."""

    def __init__(self):
        super().__init__()
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDefaultDropAction(Qt.MoveAction)


class TileSelectionDialog(QDialog):
    """Dialog for selecting images and grid size for tiling comparison."""

    def __init__(self, parent, image_list: List[Dict]):
        """Initialize selection dialog.

        Args:
            parent: Parent widget
            image_list: List of image dictionaries from ImageViewer
        """
        super().__init__(parent)
        self.setWindowTitle("複数画像比較 - 画像選択")
        self.resize(500, 600)

        self.image_list = image_list
        self.grid_size = (2, 2)
        self.selected_indices = []

        self._build_ui()

        # Auto-select first 4 images by default
        self._auto_select_default()

    def _build_ui(self):
        """Build the user interface."""
        layout = QVBoxLayout(self)

        # Grid size selection
        grid_layout = QHBoxLayout()
        grid_layout.addWidget(QLabel("グリッドサイズ (h, w):"))

        self.grid_combo = QComboBox()
        self.grid_combo.addItem("1x2 (2枚)", (1, 2))
        self.grid_combo.addItem("1x3 (3枚)", (1, 3))
        self.grid_combo.addItem("1x4 (4枚)", (1, 4))
        self.grid_combo.addItem("2x1 (2枚)", (2, 1))
        self.grid_combo.addItem("2x2 (4枚)", (2, 2))
        self.grid_combo.addItem("2x3 (6枚)", (2, 3))
        self.grid_combo.addItem("2x4 (8枚)", (2, 4))
        self.grid_combo.addItem("3x2 (6枚)", (3, 2))
        self.grid_combo.addItem("3x3 (9枚)", (3, 3))
        self.grid_combo.setCurrentIndex(8)  # Default to 3x3
        self.grid_combo.currentIndexChanged.connect(self._on_grid_changed)

        grid_layout.addWidget(self.grid_combo)
        grid_layout.addStretch()
        layout.addLayout(grid_layout)

        # Image list
        label = QLabel("画像を選択 (ドラッグで並び替え):")
        layout.addWidget(label)

        self.image_list_widget = DraggableListWidget()

        # Populate list
        for i, img_info in enumerate(self.image_list):
            path = img_info.get("path", f"Image {i+1}")
            filename = Path(path).name if path else f"Image {i+1}"

            # Get dtype info
            arr = img_info.get("base_array", img_info.get("array"))
            dtype_str = f"({arr.dtype.name})" if arr is not None else ""

            item_text = f"{i+1}: {filename} {dtype_str}"
            item = QListWidgetItem(item_text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, i)

            self.image_list_widget.addItem(item)

        layout.addWidget(self.image_list_widget)

        # Status label
        self.status_label = QLabel("最大4枚まで選択可能")
        layout.addWidget(self.status_label)

        # Ensure internal state reflects default selection (after status_label exists)
        self._on_grid_changed()

        # Selection buttons
        btn_layout = QHBoxLayout()

        select_all_btn = QPushButton("すべて選択")
        select_all_btn.clicked.connect(self._select_all)
        btn_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("選択解除")
        deselect_all_btn.clicked.connect(self._deselect_all)
        btn_layout.addWidget(deselect_all_btn)

        clear_btn = QPushButton("クリア")
        clear_btn.clicked.connect(self._deselect_all)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Dialog buttons
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
        """Handle grid size change."""
        self.grid_size = self.grid_combo.currentData()
        max_tiles = self.grid_size[0] * self.grid_size[1]
        self.status_label.setText(f"最大{max_tiles}枚まで選択可能")

    def _select_all(self):
        """Select all images (up to max)."""
        max_tiles = self.grid_size[0] * self.grid_size[1]

        for i in range(self.image_list_widget.count()):
            item = self.image_list_widget.item(i)
            if i < max_tiles:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

    def _deselect_all(self):
        """Deselect all images."""
        for i in range(self.image_list_widget.count()):
            item = self.image_list_widget.item(i)
            item.setCheckState(Qt.Unchecked)

    def _auto_select_default(self):
        """Auto-select first N images based on grid size."""
        max_tiles = self.grid_size[0] * self.grid_size[1]
        count = min(max_tiles, self.image_list_widget.count())

        for i in range(count):
            item = self.image_list_widget.item(i)
            item.setCheckState(Qt.Checked)

    def _on_compare(self):
        """Handle compare button click."""
        # Collect selected indices in list order
        selected = []
        for i in range(self.image_list_widget.count()):
            item = self.image_list_widget.item(i)
            if item.checkState() == Qt.Checked:
                original_idx = item.data(Qt.UserRole)
                selected.append(original_idx)

        # Validate selection
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

    def get_selection(self) -> Tuple[Tuple[int, int], List[int]]:
        """Get grid size and selected image indices.

        Returns:
            Tuple of (grid_size, selected_indices)
            grid_size: (rows, cols)
            selected_indices: List of image indices in display order
        """
        return (self.grid_size, self.selected_indices)
