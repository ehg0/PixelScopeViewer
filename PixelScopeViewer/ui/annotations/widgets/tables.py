"""特徴量 dialog の table model。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QBrush, QColor

from PixelScopeViewer.ui.annotations.model import AnnotationStore
from PixelScopeViewer.ui.common import theme


def resolve_path(path) -> str | None:
    """パスを絶対パスの文字列にする。OS が扱えないパスの場合は None。"""
    try:
        return str(Path(str(path)).resolve())
    except OSError:
        return None


def _summarize_long(value, max_len: int) -> str | None:
    """長さが max_len を超える配列などを "<型 len=n>" に要約する。要約しない場合は None。"""
    if isinstance(value, (str, bytes, bytearray, dict)):
        return None
    try:
        length = len(value)
    except TypeError:  # __len__ を持たない値や 0 次元の numpy 配列
        return None
    return f"<{type(value).__name__} len={length}>" if length > max_len else None


class ImageAnnotationsTableModel(QAbstractTableModel):
    """特徴量の行を表示・編集する model。読み込み済みの画像の行は黒、表示中の画像の行は黄色で示す。"""

    def __init__(self, viewer, manager: AnnotationStore):
        super().__init__()
        self.viewer = viewer
        self.manager = manager
        self._columns = self.manager.get_columns()
        # 描画のたびにパスを解決しないよう、読み込み済み・表示中の画像のパスを cache する
        self._loaded_paths = set()
        self._current_path = None
        # 画像の追加・削除時に cache を再構築する
        if self.viewer is not None:
            self.viewer.image_changed.connect(self._rebuild_loaded_cache)
        self._rebuild_loaded_cache()

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
            # 描画を軽くするため、長い配列は要約して返す
            if value is None:
                return ""
            summary = _summarize_long(value, 20)
            if summary is not None:
                return summary
            return value

        if role == Qt.TextAlignmentRole:
            if isinstance(value, (int, float)):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        if role == Qt.ToolTipRole:
            # 長い配列は tooltip でも要約する
            if value is None:
                return None
            summary = _summarize_long(value, 100)
            if summary is not None:
                return summary
            s = str(value).strip()
            return s if s else None

        if role == Qt.ForegroundRole:
            fp = self.manager.get_value(row, "fullfilepath")
            is_loaded = bool(fp) and resolve_path(fp) in self._loaded_paths
            return QBrush(QColor(theme.TEXT_COLOR if is_loaded else theme.TEXT_MUTED_COLOR))

        if role == Qt.BackgroundRole:
            fp = self.manager.get_value(row, "fullfilepath")
            if fp and self._current_path is not None and resolve_path(fp) == self._current_path:
                return QBrush(QColor(theme.HIGHLIGHT_BACKGROUND))
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

    # ---- cache ----
    def _rebuild_loaded_cache(self):
        """読み込み済みの画像と表示中の画像のパスの cache を作り直す。"""
        imgs = self.viewer.images if self.viewer is not None else []
        self._loaded_paths = {resolve_path(info.get("path", "")) for info in imgs} - {None}
        self._current_path = None
        if self.viewer is not None and self.viewer.state.current_index is not None:
            self._current_path = resolve_path(imgs[self.viewer.state.current_index].get("path", ""))
        # 文字色と背景色の更新を view に通知する
        r, c = self.rowCount(), self.columnCount()
        if r > 0 and c > 0:
            self.dataChanged.emit(self.index(0, 0), self.index(r - 1, c - 1), [Qt.BackgroundRole, Qt.ForegroundRole])


class SimpleDictTableModel(QAbstractTableModel):
    """rows_fn と cols_fn が返す dict のリストを表示する model。"""

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
        if role == Qt.ToolTipRole and value is not None and str(value).strip():
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
    """annotation（image_id, category_id, bbox）を表示する model。"""

    def __init__(self, manager: AnnotationStore):
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

    def get_columns(self) -> list[str]:
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
