from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHeaderView
from PySide6.QtWidgets import QAbstractItemView, QTableWidget


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
        layout.addWidget(self.metadata_table)

        # Copy button (parent dialog connects the handler)
        self.copy_btn = QPushButton("クリップボードにコピー")
        layout.addWidget(self.copy_btn)

    def update(self, rows: list[tuple[str, str]]):
        """Update metadata table with key-value pairs.

        Parameters
        ----------
        rows: list[tuple[str, str]]
            List of (key, value) tuples to display
        """
        from PySide6.QtWidgets import QTableWidgetItem

        self.metadata_table.setRowCount(len(rows))
        for i, (key, value) in enumerate(rows):
            self.metadata_table.setItem(i, 0, QTableWidgetItem(key))
            self.metadata_table.setItem(i, 1, QTableWidgetItem(value))
