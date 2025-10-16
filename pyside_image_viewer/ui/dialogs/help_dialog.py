"""Help dialog showing keyboard shortcuts."""

from PySide6.QtWidgets import QDialog, QTextEdit, QVBoxLayout


class HelpDialog(QDialog):
    """Dialog showing keyboard shortcuts and usage help."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(480, 320)
        text = QTextEdit(self)
        text.setReadOnly(True)
        content = """Keyboard shortcuts:
- 全選択 : Ctrl + A
- 選択領域をコピー : Ctrl + C
- 次の画像 : n
- 前の画像 : b
- 拡大 : +
- 縮小 : -
- 左ビットシフト : <
- 右ビットシフト : >
- 選択解除 : ESC
"""
        text.setPlainText(content)
        layout = QVBoxLayout(self)
        layout.addWidget(text)
