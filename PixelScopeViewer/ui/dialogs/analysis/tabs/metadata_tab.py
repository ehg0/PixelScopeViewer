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
    """Metadata tab UI containing a copyable table and a copy button."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Table for metadata
        self.metadata_table = QTableWidget()
        self.metadata_table.setColumnCount(2)
        self.metadata_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.metadata_table.horizontalHeader().setStretchLastSection(True)
        self.metadata_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.metadata_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.metadata_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.metadata_table.setSelectionBehavior(QAbstractItemView.SelectItems)

        self.metadata_table.setWordWrap(False)
        # マウスホバー時のツールチップ表示をスムーズにする設定
        self.metadata_table.setMouseTracking(True)

        layout.addWidget(self.metadata_table)

        # Copy button (parent dialog connects the handler)
        self.copy_btn = QPushButton("クリップボードにコピー")
        # ボタンにもマウスホバー時の補足説明（ツールチップ）を追加
        self.copy_btn.setToolTip("表示中のメタデータ一覧をクリップボードにコピーします")
        layout.addWidget(self.copy_btn)

    def update(self, rows: list[tuple[str, str]]):
        """Update metadata table with key-value pairs.

        Parameters
        ----------
        rows: list[tuple[str, str]]
            List of (key, value) tuples to display
        """
        # ソート有効時のチラつき防止
        self.metadata_table.setSortingEnabled(False)
        self.metadata_table.setRowCount(len(rows))

        for i, (key, value) in enumerate(rows):
            # 文字列化して安全に扱う
            key_str = str(key)
            val_str = str(value)

            # Keyアイテムの設定
            key_item = QTableWidgetItem(key_str)
            key_item.setToolTip(key_str)  # ★ マウスオーバーで表示
            self.metadata_table.setItem(i, 0, key_item)

            # Valueアイテムの設定
            val_item = QTableWidgetItem(val_str)
            val_item.setToolTip(val_str)  # ★ 長文でもマウスオーバーで全体を表示
            self.metadata_table.setItem(i, 1, val_item)
