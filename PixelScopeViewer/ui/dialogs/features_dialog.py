"""Dialog window to display and edit feature tables.

Shows a merged, editable table of features loaded via FeaturesManager.
Provides sorting, basic filtering, double-click to open image, and save.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QPushButton,
    QLineEdit,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QTabWidget,
    QWidget,
    QCheckBox,
    QStyledItemDelegate,
    QLineEdit as QLineEditWidget,
)

from ..utils.features_manager import FeaturesManager


class _PlainTextDelegate(QStyledItemDelegate):
    """Custom delegate that always uses plain text editing (no spinbox for numeric values)."""

    def createEditor(self, parent, option, index):
        """Create a simple QLineEdit for all editable cells."""
        editor = QLineEditWidget(parent)
        return editor


class _LoadedOnlyProxyModel(QSortFilterProxyModel):
    """Proxy model that can filter to show only loaded images."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._viewer = None
        self._loaded_only = False

    def set_viewer(self, viewer):
        self._viewer = viewer

    def set_loaded_only(self, enabled: bool):
        self._loaded_only = enabled

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        # Base acceptance from parent (text filter)
        if not super().filterAcceptsRow(source_row, source_parent):
            return False
        # Additional filter: loaded only
        if not self._loaded_only or not self._viewer:
            return True
        src_model = self.sourceModel()
        if not hasattr(src_model, "manager"):
            return True
        fp = src_model.manager.get_value(source_row, "fullfilepath")
        if not fp:
            return False
        try:
            p = Path(str(fp)).resolve()
            for info in self._viewer.images:
                if Path(info.get("path", "")).resolve() == p:
                    return True
        except Exception:
            pass
        return False


class _FeaturesTableModel(QAbstractTableModel):
    def __init__(self, viewer, manager: FeaturesManager):
        super().__init__()
        self.viewer = viewer
        self.manager = manager
        self._columns = self.manager.get_columns()

    # Utilities
    def refresh(self):
        self.beginResetModel()
        self._columns = self.manager.get_columns()
        self.endResetModel()

    # Model impl
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else self.manager.row_count()

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(self._columns):
                return self._columns[section]
        else:
            return section + 1
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        col_name = self._columns[col]
        value = self.manager.get_value(row, col_name)

        if role == Qt.DisplayRole or role == Qt.EditRole:
            return "" if value is None else value

        if role == Qt.TextAlignmentRole:
            # Right-align numeric data
            if isinstance(value, (int, float)):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        if role == Qt.ToolTipRole:
            # Show full text as tooltip if value is non-empty
            if value is not None and str(value).strip():
                return str(value)
            return None

        if role == Qt.ForegroundRole:
            # Grey out when the image is not currently loaded in the viewer
            fp = self.manager.get_value(row, "fullfilepath")
            is_loaded = False
            if fp:
                try:
                    p = Path(str(fp)).resolve()
                    for info in self.viewer.images:
                        if Path(info.get("path", "")).resolve() == p:
                            is_loaded = True
                            break
                except Exception:
                    is_loaded = False
            return QBrush(QColor("black" if is_loaded else "gray"))

        if role == Qt.BackgroundRole:
            # Highlight current displayed image with light yellow background
            try:
                cur_img = (
                    self.viewer.images[self.viewer.current_index] if self.viewer.current_index is not None else None
                )
                cur_path = Path(cur_img["path"]).resolve() if cur_img else None
            except Exception:
                cur_path = None
            fp = self.manager.get_value(row, "fullfilepath")
            if cur_path is not None and fp:
                try:
                    if Path(str(fp)).resolve() == cur_path:
                        return QBrush(QColor(255, 255, 200))  # Light yellow
                except Exception:
                    pass
            return None

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemIsEnabled
        col_name = self._columns[index.column()]
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled
        if self.manager.column_is_editable(col_name):
            flags |= Qt.ItemIsEditable
        return flags

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False
        col_name = self._columns[index.column()]

        # Preserve original type when editing
        original = self.manager.get_value(index.row(), col_name)
        if isinstance(original, float):
            try:
                value = float(value)
            except (ValueError, TypeError):
                return False
        elif isinstance(original, int):
            try:
                value = int(value)
            except (ValueError, TypeError):
                return False

        self.manager.set_value(index.row(), col_name, value)
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        return True


class FeaturesDialog(QDialog):
    def __init__(self, viewer, manager: FeaturesManager):
        super().__init__(viewer)
        self.viewer = viewer
        self.manager = manager

        # Set window title with loaded file path if available
        title = "特徴量表示"
        last_path = self.manager.get_last_loaded_path()
        if last_path:
            title = f"特徴量表示 - {last_path}"
        self.setWindowTitle(title)

        self.resize(900, 600)

        layout = QVBoxLayout(self)

        # Controls
        ctrl = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("フィルタ文字列を入力…")
        self.filter_column = QComboBox()

        self.btn_add_col = QPushButton("列を追加")
        self.btn_save = QPushButton("保存…")
        self.btn_toggle_cols = QPushButton("列表示...")
        self.chk_load_unloaded = QCheckBox("未読み込みをロード")
        self.chk_load_unloaded.setChecked(True)
        self.chk_show_loaded_only = QCheckBox("読込済のみ")
        self.chk_show_loaded_only.setChecked(False)
        ctrl.addWidget(self.filter_column)
        ctrl.addWidget(self.filter_edit, 1)
        ctrl.addStretch(1)
        ctrl.addWidget(self.chk_show_loaded_only)
        ctrl.addWidget(self.chk_load_unloaded)
        ctrl.addWidget(self.btn_toggle_cols)
        ctrl.addWidget(self.btn_add_col)
        ctrl.addWidget(self.btn_save)
        layout.addLayout(ctrl)

        # Tabs: Images / Categories / Annotations
        from PySide6.QtCore import QSortFilterProxyModel

        self.tabs = QTabWidget(self)

        # Images tab
        self.model_images = _FeaturesTableModel(self.viewer, self.manager)
        # Custom proxy for "loaded only" filter
        self.proxy_images = _LoadedOnlyProxyModel(self)
        self.proxy_images.setSourceModel(self.model_images)
        self.proxy_images.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_images.set_viewer(self.viewer)
        self.table_images = QTableView(self)
        self.table_images.setModel(self.proxy_images)
        self.table_images.setSortingEnabled(True)
        self.table_images.doubleClicked.connect(self._on_double_clicked)
        self.table_images.setSelectionBehavior(QTableView.SelectRows)
        self.table_images.setAlternatingRowColors(True)
        # Use plain text delegate to disable spinbox for numeric cells
        self.table_images.setItemDelegate(_PlainTextDelegate(self.table_images))
        # Hide vertical header (row numbers)
        self.table_images.verticalHeader().setVisible(False)
        # Show horizontal header for all columns
        self.table_images.horizontalHeader().setVisible(True)
        # Set minimum width for id column if exists
        cols = self.manager.get_columns()
        if "id" in cols:
            id_idx = cols.index("id")
            self.table_images.setColumnWidth(id_idx, 50)  # Minimum width for id
        # Enable tooltips for truncated text
        self.table_images.setMouseTracking(True)
        w_images = QWidget(self)
        v_images = QVBoxLayout(w_images)
        v_images.setContentsMargins(0, 0, 0, 0)
        v_images.addWidget(self.table_images)
        self.tabs.addTab(w_images, "Images")

        # Categories tab (read-only)
        self.model_categories = _SimpleDictTableModel(
            self.manager.get_categories_rows, self.manager.get_categories_columns, editable=False
        )
        self.proxy_categories = QSortFilterProxyModel(self)
        self.proxy_categories.setSourceModel(self.model_categories)
        self.proxy_categories.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.table_categories = QTableView(self)
        self.table_categories.setModel(self.proxy_categories)
        self.table_categories.setSortingEnabled(True)
        self.table_categories.setAlternatingRowColors(True)
        self.table_categories.verticalHeader().setVisible(False)
        self.table_categories.setMouseTracking(True)
        w_cat = QWidget(self)
        v_cat = QVBoxLayout(w_cat)
        v_cat.setContentsMargins(0, 0, 0, 0)
        v_cat.addWidget(self.table_categories)
        self.tabs.addTab(w_cat, "Categories")

        # Annotations tab (read-only)
        self.model_annotations = _AnnotationsTableModel(self.manager)
        self.proxy_annotations = QSortFilterProxyModel(self)
        self.proxy_annotations.setSourceModel(self.model_annotations)
        self.proxy_annotations.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.table_annotations = QTableView(self)
        self.table_annotations.setModel(self.proxy_annotations)
        self.table_annotations.setSortingEnabled(True)
        self.table_annotations.setAlternatingRowColors(True)
        self.table_annotations.verticalHeader().setVisible(False)
        self.table_annotations.setMouseTracking(True)
        w_ann = QWidget(self)
        v_ann = QVBoxLayout(w_ann)
        v_ann.setContentsMargins(0, 0, 0, 0)
        v_ann.addWidget(self.table_annotations)
        self.tabs.addTab(w_ann, "Annotations")

        layout.addWidget(self.tabs, 1)

        # Wire up
        self.filter_edit.textChanged.connect(self._on_filter_changed)
        self.filter_column.currentIndexChanged.connect(self._on_filter_col_changed)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.btn_add_col.clicked.connect(self._on_add_column)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_toggle_cols.clicked.connect(self._on_toggle_columns)
        self.chk_show_loaded_only.toggled.connect(self._on_loaded_only_toggled)

        # Listen to image change to refresh row highlighting
        self.viewer.image_changed.connect(self.refresh_roles)

        # Initialize filter
        self.refresh_filter_columns()
        self._on_filter_col_changed()
        # Initialize button states based on initial tab
        self._on_tab_changed(0)

        # Apply initial sort on Images tab by 'id' column in ascending order
        cols = self.manager.get_columns()
        if "id" in cols:
            id_idx = cols.index("id")
            self.table_images.sortByColumn(id_idx, Qt.AscendingOrder)

        # Apply initial sort on Categories tab by 'id' column in ascending order
        cat_cols = self.manager.get_categories_columns()
        if "id" in cat_cols:
            cat_id_idx = cat_cols.index("id")
            self.table_categories.sortByColumn(cat_id_idx, Qt.AscendingOrder)

        # Apply initial sort on Annotations tab by 'image_id' column in ascending order
        ann_cols = self.model_annotations.get_columns()
        if "image_id" in ann_cols:
            ann_id_idx = ann_cols.index("image_id")
            self.table_annotations.sortByColumn(ann_id_idx, Qt.AscendingOrder)

    # ----- UI handlers -----
    def refresh_from_manager(self):
        self.model_images.refresh()
        self.model_categories.refresh()
        self.model_annotations.refresh()
        self.refresh_filter_columns()
        self.refresh_roles()

    def refresh_filter_columns(self):
        # Columns are based on current tab
        cols = self._current_columns()
        self.filter_column.blockSignals(True)
        self.filter_column.clear()
        self.filter_column.addItems(cols)
        self.filter_column.blockSignals(False)

    def refresh_roles(self):
        # Trigger repaint of DisplayRole/BackgroundRole/ForegroundRole for images table only
        r = self.model_images.rowCount()
        c = self.model_images.columnCount()
        if r > 0 and c > 0:
            tl = self.model_images.index(0, 0)
            br = self.model_images.index(r - 1, c - 1)
            self.model_images.dataChanged.emit(tl, br, [Qt.DisplayRole, Qt.BackgroundRole, Qt.ForegroundRole])

    def _on_loaded_only_toggled(self, checked: bool):
        self.proxy_images.set_loaded_only(checked)
        self.proxy_images.invalidateFilter()

    def _on_toggle_columns(self):
        # Show dialog with checkboxes for each column (except fixed ones)
        cols = self.manager.get_columns()
        fixed = {"id", "file_name"}
        available = [c for c in cols if c not in fixed]
        if not available:
            QMessageBox.information(self, "列表示", "表示切替可能な列がありません。")
            return
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QDialogButtonBox, QPushButton

        dlg = QDialog(self)
        dlg.setWindowTitle("列表示設定")
        v = QVBoxLayout(dlg)
        checks = {}
        for c in available:
            chk = QCheckBox(c)
            chk.setChecked(not self.table_images.isColumnHidden(cols.index(c)))
            checks[c] = chk
            v.addWidget(chk)

        # Reset button
        reset_btn = QPushButton("リセット（全列表示）")

        def on_reset():
            for chk in checks.values():
                chk.setChecked(True)

        reset_btn.clicked.connect(on_reset)
        v.addWidget(reset_btn)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        v.addWidget(btns)
        if dlg.exec() == QDialog.Accepted:
            for c, chk in checks.items():
                idx = cols.index(c)
                self.table_images.setColumnHidden(idx, not chk.isChecked())

    def _on_filter_changed(self, text: str):
        from PySide6.QtCore import QRegularExpression

        self._current_proxy().setFilterRegularExpression(QRegularExpression(text))

    def _on_filter_col_changed(self):
        self._current_proxy().setFilterKeyColumn(self.filter_column.currentIndex())

    def _on_tab_changed(self, idx: int):
        # Update filter column candidates and reset filter column index to 0
        self.refresh_filter_columns()
        self._on_filter_col_changed()
        # Enable/disable buttons based on tab
        is_images = idx == 0
        self.btn_add_col.setEnabled(is_images)
        self.btn_toggle_cols.setEnabled(is_images)
        self.chk_show_loaded_only.setEnabled(is_images)
        self.chk_load_unloaded.setEnabled(is_images)

    def _on_add_column(self):
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "列を追加", "列名")
        if not ok or not name.strip():
            return
        if name in self.manager.get_columns():
            QMessageBox.information(self, "列を追加", "同名の列が既に存在します。")
            return
        self.manager.add_column(name, None)
        self.refresh_from_manager()

    def _on_save(self):
        # Start in last loaded directory if available
        start_dir = self.manager.get_last_loaded_directory() or ""
        # JSON first in filter list
        path, sel = QFileDialog.getSaveFileName(self, "保存", start_dir, "JSON (*.json);;CSV (*.csv)")
        if not path:
            return
        try:
            if path.lower().endswith(".csv"):
                self.manager.save_to_csv(path)
            elif path.lower().endswith(".json"):
                self.manager.save_to_json(path)
            else:
                # Default to JSON if no extension
                path_json = str(Path(path).with_suffix(".json"))
                self.manager.save_to_json(path_json)
            QMessageBox.information(self, "保存", "保存しました。")
        except Exception as e:
            QMessageBox.critical(self, "保存エラー", str(e))

    def _on_double_clicked(self, proxy_index: QModelIndex):
        # Only images tab supports double-click actions
        if self.tabs.currentIndex() != 0:
            return
        if not proxy_index.isValid():
            return
        # Resolve current FP from index and defer action to avoid re-entrancy
        src_index = self.proxy_images.mapToSource(proxy_index)
        row = src_index.row()
        fp = self.manager.get_value(row, "fullfilepath")
        if not fp:
            return
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, lambda fp=fp: self._open_image_by_fullpath(fp))

    def _open_image_by_fullpath(self, fp: str):
        p = Path(str(fp))
        if not p.exists():
            QMessageBox.information(self, "画像を開く", "ファイルが存在しません。")
            return
        # Check if loaded
        match_idx = None
        try:
            for i, info in enumerate(self.viewer.images):
                if Path(info.get("path", "")).resolve() == p.resolve():
                    match_idx = i
                    break
        except Exception:
            match_idx = None

        if match_idx is not None:
            self.viewer.current_index = match_idx
            self.viewer.show_current_image()
            return

        # Not loaded yet
        if not self.chk_load_unloaded.isChecked():
            return
        try:
            n = self.viewer._add_images([str(p)])
            self.viewer._finalize_image_addition(n)
        except Exception as e:
            QMessageBox.critical(self, "画像を開く", f"読み込みに失敗しました:\n{e}")

    # Helpers for current tab
    def _current_proxy(self):
        i = self.tabs.currentIndex()
        return [self.proxy_images, self.proxy_categories, self.proxy_annotations][i]

    def _current_columns(self) -> List[str]:
        i = self.tabs.currentIndex()
        if i == 0:
            return self.manager.get_columns()
        elif i == 1:
            return self.manager.get_categories_columns() or []
        else:
            return self.model_annotations.get_columns()

    def keyPressEvent(self, event):
        """Handle ESC key to clear selection instead of closing dialog."""
        if event.key() == Qt.Key_Escape:
            # Clear selection on current table
            i = self.tabs.currentIndex()
            if i == 0:
                self.table_images.clearSelection()
            elif i == 1:
                self.table_categories.clearSelection()
            else:
                self.table_annotations.clearSelection()
            event.accept()  # Consume event to prevent dialog close
        else:
            super().keyPressEvent(event)


class _SimpleDictTableModel(QAbstractTableModel):
    def __init__(self, rows_fn, cols_fn, editable: bool = False):
        super().__init__()
        self._rows_fn = rows_fn
        self._cols_fn = cols_fn
        self._editable = editable
        self._columns = self._cols_fn() or []

    def refresh(self):
        self.beginResetModel()
        self._columns = self._cols_fn() or []
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows_fn() or [])

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(self._columns):
                return self._columns[section]
        else:
            return section + 1
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        rows = self._rows_fn() or []
        row = index.row()
        col_name = self._columns[index.column()]
        value = rows[row].get(col_name)
        if role == Qt.DisplayRole:
            return value
        if role == Qt.TextAlignmentRole:
            # Right-align numeric data
            if isinstance(value, (int, float)):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        if role == Qt.ToolTipRole:
            if value is not None and str(value).strip():
                return str(value)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemIsEnabled
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if self._editable:
            flags |= Qt.ItemIsEditable
        return flags


class _AnnotationsTableModel(QAbstractTableModel):
    def __init__(self, manager: FeaturesManager):
        super().__init__()
        self.manager = manager
        self._columns = ["image_id", "category_id", "bbox_x", "bbox_y", "bbox_w", "bbox_h"]

    def refresh(self):
        self.beginResetModel()
        self.endResetModel()

    def get_columns(self) -> List[str]:
        return list(self._columns)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.manager.get_annotations_rows())

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(self._columns):
                return self._columns[section]
        else:
            return section + 1
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        a = self.manager.get_annotations_rows()[row]
        col = self._columns[index.column()]

        value = None
        if col == "image_id":
            value = a.get("image_id")
        elif col == "category_id":
            value = a.get("category_id")
        elif col.startswith("bbox_"):
            i = {"bbox_x": 0, "bbox_y": 1, "bbox_w": 2, "bbox_h": 3}[col]
            bbox = a.get("bbox") or [None, None, None, None]
            value = bbox[i]

        if role == Qt.DisplayRole:
            return value
        if role == Qt.TextAlignmentRole:
            # Right-align numeric data
            if isinstance(value, (int, float)):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        if role == Qt.ToolTipRole:
            if value is not None and str(value).strip():
                return str(value)
        return None
