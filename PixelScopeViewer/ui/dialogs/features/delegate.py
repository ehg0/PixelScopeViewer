from PySide6.QtWidgets import QStyledItemDelegate, QLineEdit


class PlainTextDelegate(QStyledItemDelegate):
    """Delegate that always uses a plain QLineEdit for editing (no spinbox)."""

    def createEditor(self, parent, option, index):
        return QLineEdit(parent)
