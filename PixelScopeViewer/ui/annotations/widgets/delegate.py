"""特徴量 table の編集用 delegate。"""

from PySide6.QtWidgets import QLineEdit, QStyledItemDelegate


class PlainTextDelegate(QStyledItemDelegate):
    """数値の列でも spin box ではなく QLineEdit で編集する delegate。"""

    def createEditor(self, parent, option, index):
        return QLineEdit(parent)
