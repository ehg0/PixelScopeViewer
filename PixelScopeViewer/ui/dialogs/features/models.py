from __future__ import annotations

from pathlib import Path
from typing import Any, List

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QBrush, QColor
from PySide6.QtCore import QSortFilterProxyModel

from ...utils.features_manager import FeaturesManager


class FeaturesTableModel(QAbstractTableModel):
    def __init__(self, viewer, manager: FeaturesManager):
        super().__init__()
        self.viewer = viewer
        self.manager = manager
        self._columns = self.manager.get_columns()

    def refresh(self):
        self.beginResetModel()
        self._columns = self.manager.get_columns()
        self.endResetModel()

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
            if isinstance(value, (int, float)):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        if role == Qt.ToolTipRole:
            if value is not None and str(value).strip():
                return str(value)
            return None

        if role == Qt.ForegroundRole:
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
                        return QBrush(QColor(255, 255, 200))
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


class SimpleDictTableModel(QAbstractTableModel):
    def __init__(self, rows_fn, cols_fn, editable: bool = False):
        super().__init__()
        self._rows_fn = rows_fn
        self._cols_fn = cols_fn
        self._editable = editable
        self._columns = self._cols_fn() or []
        self.proxy: QSortFilterProxyModel | None = None

    def as_proxy(self, parent) -> QSortFilterProxyModel:
        proxy = QSortFilterProxyModel(parent)
        proxy.setSourceModel(self)
        proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy = proxy
        return proxy

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


class AnnotationsTableModel(QAbstractTableModel):
    def __init__(self, manager: FeaturesManager):
        super().__init__()
        self.manager = manager
        self._columns = ["image_id", "category_id", "bbox_x", "bbox_y", "bbox_w", "bbox_h"]
        self.proxy: QSortFilterProxyModel | None = None

    def as_proxy(self, parent) -> QSortFilterProxyModel:
        proxy = QSortFilterProxyModel(parent)
        proxy.setSourceModel(self)
        proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy = proxy
        return proxy

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
            if isinstance(value, (int, float)):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        return None
