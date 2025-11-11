"""ROI info widget showing and editing ROI information."""

from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QSpinBox,
    QHBoxLayout,
    QWidget,
    QMenu,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


class ROIInfoWidget(QGroupBox):
    """ROI info widget showing and editing ROI information.

    Shows x start, y start, x end, y end, width, height, pixel count.
    Editable fields update the ROI in real-time.
    """

    def __init__(self, viewer):
        super().__init__()  # No title, title is in dock
        self.viewer = viewer
        self._updating = False  # guard for re-entrant updates

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Property", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setVisible(False)  # Hide header
        self.table.setRowCount(8)
        # Compact table and editors
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
        properties = ["X Start", "Y Start", "X End", "Y End", "Width", "Height", "Diagonal", "Pixel Count"]
        for i, prop in enumerate(properties):
            item = QTableWidgetItem(prop)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, item)

        # Create spin boxes for editable fields
        self.spin_boxes = {}
        editable_rows = [0, 1, 2, 3, 4, 5]  # All except diagonal and pixel count

        for row in editable_rows:
            spin_box = QSpinBox()
            spin_box.setMinimum(0)
            spin_box.setMaximum(100000)  # Large enough
            spin_box.setSingleStep(1)  # Increment/decrement by 1
            spin_box.valueChanged.connect(lambda value, r=row: self.on_spin_changed(r, value))
            spin_box.setFont(font)
            self.spin_boxes[row] = spin_box

            # Create widget to hold spin box
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.addWidget(spin_box)
            layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 1, widget)

        # Enable context menu for copying
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins to pack tightly
        layout.addWidget(self.table)
        layout.addStretch()  # Add stretch to push table to top

        # Fix table height to avoid vertical scrolling
        self._fit_table_height()

        # Connect to viewer signals
        self.viewer.roi_changed.connect(self.update_info)
        self.viewer.image_changed.connect(self.update_info)

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

    def on_spin_changed(self, row, value):
        """Handle spin box value changes."""
        # Ignore programmatic updates
        if self._updating:
            return
        if self.viewer.current_index is None:
            return

        img = self.viewer.images[self.viewer.current_index]["array"]
        img_h, img_w = img.shape[:2]

        # Get current ROI
        current_rect = self.viewer.current_roi_rect
        if current_rect is None:
            return

        x, y, w, h = current_rect.x(), current_rect.y(), current_rect.width(), current_rect.height()

        # Update based on which field changed
        if row == 0:  # X Start
            x = max(0, min(value, img_w - w))  # Ensure x + w <= img_w
            self.spin_boxes[0].blockSignals(True)
            self.spin_boxes[0].setValue(x)
            self.spin_boxes[0].blockSignals(False)
        elif row == 1:  # Y Start
            y = max(0, min(value, img_h - h))  # Ensure y + h <= img_h
            self.spin_boxes[1].blockSignals(True)
            self.spin_boxes[1].setValue(y)
            self.spin_boxes[1].blockSignals(False)
        elif row == 2:  # X End
            x_end = max(x, min(value, img_w - 1))  # Ensure x_end >= x and <= img_w - 1
            w = x_end - x + 1
            self.spin_boxes[2].blockSignals(True)
            self.spin_boxes[2].setValue(x_end)
            self.spin_boxes[2].blockSignals(False)
            self.spin_boxes[4].blockSignals(True)
            self.spin_boxes[4].setValue(w)
            self.spin_boxes[4].blockSignals(False)
        elif row == 3:  # Y End
            y_end = max(y, min(value, img_h - 1))  # Ensure y_end >= y and <= img_h - 1
            h = y_end - y + 1
            self.spin_boxes[3].blockSignals(True)
            self.spin_boxes[3].setValue(y_end)
            self.spin_boxes[3].blockSignals(False)
            self.spin_boxes[5].blockSignals(True)
            self.spin_boxes[5].setValue(h)
            self.spin_boxes[5].blockSignals(False)
        elif row == 4:  # Width
            w = max(1, min(value, img_w - x))  # Ensure w >= 1 and x + w <= img_w
            self.spin_boxes[4].blockSignals(True)
            self.spin_boxes[4].setValue(w)
            self.spin_boxes[4].blockSignals(False)
            x_end = x + w - 1
            self.spin_boxes[2].blockSignals(True)
            self.spin_boxes[2].setValue(x_end)
            self.spin_boxes[2].blockSignals(False)
        elif row == 5:  # Height
            h = max(1, min(value, img_h - y))  # Ensure h >= 1 and y + h <= img_h
            self.spin_boxes[5].blockSignals(True)
            self.spin_boxes[5].setValue(h)
            self.spin_boxes[5].blockSignals(False)
            y_end = y + h - 1
            self.spin_boxes[3].blockSignals(True)
            self.spin_boxes[3].setValue(y_end)
            self.spin_boxes[3].blockSignals(False)

        # Update ROI using image coordinates to avoid rounding issues at various scales
        from PySide6.QtCore import QRect

        new_rect_img = QRect(x, y, w, h)
        self.viewer.set_roi_from_image_rect(new_rect_img)

    def update_info(self):
        """Update the ROI information."""
        # Prevent valueChanged loops caused by setMaximum/setValue clamping
        self._updating = True
        try:
            if self.viewer.current_index is None or not self.viewer.images:
                for spin_box in self.spin_boxes.values():
                    spin_box.setValue(0)
                self.table.setItem(6, 1, QTableWidgetItem(""))
                self.table.setItem(7, 1, QTableWidgetItem(""))
                return

            img = self.viewer.images[self.viewer.current_index]["array"]
            img_h, img_w = img.shape[:2]

            current_rect = self.viewer.current_roi_rect
            if current_rect is None or current_rect.isNull():
                for spin_box in self.spin_boxes.values():
                    spin_box.setValue(0)
                self.table.setItem(6, 1, QTableWidgetItem(""))
                self.table.setItem(7, 1, QTableWidgetItem(""))
                return

            x = current_rect.x()
            y = current_rect.y()
            w = current_rect.width()
            h = current_rect.height()
            x_end = current_rect.right()
            y_end = current_rect.bottom()

            # Set ranges based on image size
            self.spin_boxes[0].setMinimum(0)  # X Start
            self.spin_boxes[0].setMaximum(img_w - 1)
            self.spin_boxes[1].setMinimum(0)  # Y Start
            self.spin_boxes[1].setMaximum(img_h - 1)
            self.spin_boxes[2].setMinimum(0)  # X End
            self.spin_boxes[2].setMaximum(img_w - 1)
            self.spin_boxes[3].setMinimum(0)  # Y End
            self.spin_boxes[3].setMaximum(img_h - 1)
            self.spin_boxes[4].setMinimum(1)  # Width
            self.spin_boxes[4].setMaximum(img_w)
            self.spin_boxes[5].setMinimum(1)  # Height
            self.spin_boxes[5].setMaximum(img_h)

            # Update spin boxes
            values = [x, y, x_end, y_end, w, h]
            for i, value in enumerate(values):
                self.spin_boxes[i].blockSignals(True)
                self.spin_boxes[i].setValue(value)
                self.spin_boxes[i].blockSignals(False)

            # Update diagonal (read-only)
            diagonal = (w**2 + h**2) ** 0.5
            diagonal_item = QTableWidgetItem(f"{diagonal:.2f}")
            diagonal_item.setFlags(diagonal_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(6, 1, diagonal_item)

            # Update pixel count (read-only)
            pixel_count = w * h if 0 <= x < img_w and 0 <= y < img_h else 0
            pixel_count_item = QTableWidgetItem(f"{pixel_count:,}")
            pixel_count_item.setFlags(pixel_count_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(7, 1, pixel_count_item)
        finally:
            self._updating = False

    def _show_context_menu(self, pos):
        """Show context menu with copy option."""
        menu = QMenu()
        copy_action = menu.addAction("コピー")
        action = menu.exec_(self.table.mapToGlobal(pos))
        if action == copy_action:
            self._copy_selection()

    def _copy_selection(self):
        """Copy selected cells to clipboard in comma-separated format."""
        selection = self.table.selectedRanges()
        if not selection:
            return

        rows = []
        for sel_range in selection:
            for row in range(sel_range.topRow(), sel_range.bottomRow() + 1):
                cols = []
                for col in range(sel_range.leftColumn(), sel_range.rightColumn() + 1):
                    # For rows with spin boxes, get the spin box value
                    if row in self.spin_boxes:
                        widget = self.table.cellWidget(row, col)
                        if widget and col == 1:  # Value column with spin box
                            cols.append(str(self.spin_boxes[row].value()))
                        else:
                            item = self.table.item(row, col)
                            cols.append(item.text() if item else "")
                    else:
                        item = self.table.item(row, col)
                        cols.append(item.text() if item else "")
                rows.append(",".join(cols))

        text = "\n".join(rows)
        QGuiApplication.clipboard().setText(text)
