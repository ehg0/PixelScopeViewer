"""metadata tab。"""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


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

    def set_rows(self, rows: list[tuple[str, str]]):
        """metadata の table を (key, value) のリストで更新する。"""
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
