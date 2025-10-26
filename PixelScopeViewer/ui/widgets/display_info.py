"""Display info widget showing current viewport information."""

from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt, QEvent


class DisplayInfoWidget(QGroupBox):
    """Display info widget showing current viewport coordinates and size.

    Shows x start, y start, x end, y end, width, height of the current viewport
    in image coordinates.
    """

    def __init__(self, viewer):
        super().__init__()  # No title, title is in dock
        self.viewer = viewer

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Property", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setVisible(False)  # Hide header
        self.table.setRowCount(7)
        # Compact table: smaller font/rows and no vertical scrollbar
        font = self.table.font()
        try:
            font.setPointSize(max(font.pointSize() - 1, 9))
        except Exception:
            pass
        self.table.setFont(font)
        self.table.verticalHeader().setDefaultSectionSize(18)  # Smaller row height
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.verticalHeader().setVisible(False)  # Hide row header

        # Set properties
        properties = ["X Start", "Y Start", "X End", "Y End", "Width", "Height", "Pixel Count"]
        for i, prop in enumerate(properties):
            item = QTableWidgetItem(prop)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, item)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins to pack tightly
        layout.addWidget(self.table)

        # Fix table height to avoid vertical scrolling
        self._fit_table_height()

        # Connect to viewer signals
        self.viewer.scale_changed.connect(self.update_info)
        self.viewer.image_changed.connect(self.update_info)
        # Update when scrolled or viewport resized
        sa = self.viewer.scroll_area
        sa.horizontalScrollBar().valueChanged.connect(self.update_info)
        sa.verticalScrollBar().valueChanged.connect(self.update_info)
        sa.viewport().installEventFilter(self)

        self.update_info()

    def _fit_table_height(self):
        try:
            vh = self.table.verticalHeader()
            hh = self.table.horizontalHeader()
            frame = 2 * self.table.frameWidth()
            total = hh.height() + (vh.defaultSectionSize() * self.table.rowCount()) + frame
            self.table.setMinimumHeight(total)
            self.table.setMaximumHeight(total)
        except Exception:
            pass

    def eventFilter(self, obj, event):
        try:
            if obj is self.viewer.scroll_area.viewport() and event.type() == QEvent.Resize:
                self.update_info()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def update_info(self):
        """Update the display information."""
        if self.viewer.current_index is None or not self.viewer.images:
            for i in range(7):
                self.table.setItem(i, 1, QTableWidgetItem(""))
            return

        # Get current viewport in image coordinates
        scroll_area = self.viewer.scroll_area
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()
        h_scroll = scroll_area.horizontalScrollBar().value()
        v_scroll = scroll_area.verticalScrollBar().value()

        # Convert to image coordinates
        scale = self.viewer.scale
        x_start = int(h_scroll / scale)
        y_start = int(v_scroll / scale)
        x_end = int((h_scroll + viewport_width) / scale)
        y_end = int((v_scroll + viewport_height) / scale)

        # Get image size and clamp coordinates
        img = self.viewer.images[self.viewer.current_index]["array"]
        img_h, img_w = img.shape[:2]
        x_end = min(x_end, img_w - 1)
        y_end = min(y_end, img_h - 1)

        width = x_end - x_start + 1
        height = y_end - y_start + 1
        pixel_count = width * height

        values = [str(x_start), str(y_start), str(x_end), str(y_end), str(width), str(height), f"{pixel_count:,}"]
        for i, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 1, item)
