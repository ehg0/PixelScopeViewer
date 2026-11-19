"""metadata tab。"""

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.ui.common import theme


class MetadataTab(QWidget):
    """metadata の table とコピー button を持つ tab。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.metadata_table = QTableWidget()
        self.metadata_table.setColumnCount(2)
        self.metadata_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.metadata_table.horizontalHeader().setStretchLastSection(True)
        self.metadata_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.metadata_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.metadata_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.metadata_table.setSelectionBehavior(QAbstractItemView.SelectItems)

        self.metadata_table.setWordWrap(False)
        # tooltip をスムーズに表示する
        self.metadata_table.setMouseTracking(True)

        layout.addWidget(self.metadata_table)

        # click 時の処理は親 dialog で接続する
        self.copy_btn = QPushButton("クリップボードにコピー")
        self.copy_btn.setToolTip("表示中のメタデータ一覧をクリップボードにコピーします")
        layout.addWidget(self.copy_btn)

    def _set_columns(self, headers: list[str]):
        table = self.metadata_table
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for i in range(1, len(headers)):
            header.setSectionResizeMode(i, QHeaderView.Stretch if len(headers) > 2 else QHeaderView.Interactive)
        header.setStretchLastSection(True)

    def set_rows(self, rows: list[tuple[str, str]]):
        """metadata の table を (key, value) のリストで更新する。"""
        self._set_columns(["Key", "Value"])
        # sort 有効時のちらつきを防ぐ
        self.metadata_table.setSortingEnabled(False)
        self.metadata_table.setRowCount(len(rows))

        for i, (key, value) in enumerate(rows):
            key_str = str(key)
            val_str = str(value)

            key_item = QTableWidgetItem(key_str)
            key_item.setToolTip(key_str)
            self.metadata_table.setItem(i, 0, key_item)

            # 長い値も tooltip で全体を確認できるようにする
            val_item = QTableWidgetItem(val_str)
            val_item.setToolTip(val_str)
            self.metadata_table.setItem(i, 1, val_item)

    def set_comparison(self, columns: list[tuple[str, list[tuple[str, str]]]]):
        """列ごとの metadata を横に並べ、空でない値が列の間で異なる行を強調表示する。

        Args:
            columns: (列の見出し, (key, value) のリスト) のリスト。行は最初に現れた順に並べる。
        """
        keys: list[str] = []
        values_by_column = []
        for _, rows in columns:
            values = {}
            for key, value in rows:
                if key not in values:
                    values[key] = str(value)
                if key not in keys:
                    keys.append(key)
            values_by_column.append(values)

        self._set_columns(["Key", *(title for title, _ in columns)])
        table = self.metadata_table
        table.setSortingEnabled(False)
        table.setRowCount(len(keys))
        diff_brush = QBrush(QColor(theme.HIGHLIGHT_BACKGROUND))
        for i, key in enumerate(keys):
            key_item = QTableWidgetItem(key)
            key_item.setToolTip(key)
            table.setItem(i, 0, key_item)
            values = [v.get(key, "") for v in values_by_column]
            differs = len({v for v in values if v}) > 1
            for j, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if differs and value:
                    item.setBackground(diff_brush)
                table.setItem(i, j + 1, item)
