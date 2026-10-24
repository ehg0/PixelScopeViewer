from PySide6.QtWidgets import QLineEdit, QStyledItemDelegate


class PlainTextDelegate(QStyledItemDelegate):
    """Delegate that always uses a plain QLineEdit for editing (no spinbox)."""

    def createEditor(self, parent, option, index):
        return QLineEdit(parent)
