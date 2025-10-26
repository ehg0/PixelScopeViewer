"""Custom widgets for analysis dialogs.

This module provides specialized widgets used in analysis dialogs:
- CopyableTableWidget: Table widget with Ctrl+C copy support
"""

from PySide6.QtWidgets import QTableWidget
from PySide6.QtGui import QGuiApplication, QKeySequence


class CopyableTableWidget(QTableWidget):
    """QTableWidget with Ctrl+C copy support for selected cells.

    This widget extends QTableWidget to support copying selected cells
    to the clipboard in comma-separated format when the user presses Ctrl+C.

    Features:
        - Ctrl+C keyboard shortcut support
        - Comma-separated value format (CSV-compatible)
        - Handles multiple cell selection
        - No quotes around values
    """

    def keyPressEvent(self, event):
        """Handle key press events, specifically Ctrl+C for copying.

        Args:
            event: QKeyEvent from Qt
        """
        if event.matches(QKeySequence.Copy):
            self.copy_selection_to_clipboard()
        else:
            super().keyPressEvent(event)

    def copy_selection_to_clipboard(self):
        """Copy selected cells to clipboard in comma-separated format.

        Copies the currently selected range to the system clipboard.
        Multiple cells are separated by commas, rows by newlines.
        Empty cells are represented as empty strings.
        """
        selection = self.selectedRanges()
        if not selection:
            return

        # Get the selected range (use first range if multiple)
        selected_range = selection[0]

        # Build comma-separated data
        rows = []
        for row in range(selected_range.topRow(), selected_range.bottomRow() + 1):
            row_data = []
            for col in range(selected_range.leftColumn(), selected_range.rightColumn() + 1):
                item = self.item(row, col)
                if item:
                    row_data.append(item.text())
                else:
                    row_data.append("")
            rows.append(",".join(row_data))

        text = "\n".join(rows)
        QGuiApplication.clipboard().setText(text)
