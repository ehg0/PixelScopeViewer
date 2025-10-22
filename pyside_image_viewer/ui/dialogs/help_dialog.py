"""Help dialog showing keyboard shortcuts."""

from PySide6.QtWidgets import QDialog, QTextEdit, QVBoxLayout


class HelpDialog(QDialog):
    """Help dialog showing keyboard shortcuts.

    This module provides a simple dialog displaying all available
    keyboard shortcuts for the image viewer.
    """


from PySide6.QtWidgets import QDialog, QTextEdit, QVBoxLayout


class HelpDialog(QDialog):
    """Dialog showing keyboard shortcuts and usage help.

    Displays a read-only text widget with all available keyboard
    shortcuts in Japanese. Modal dialog that closes when user
    clicks outside or presses ESC.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(480, 320)
        text = QTextEdit(self)
        text.setReadOnly(True)
        content = """Keyboard shortcuts:
- 読み込み : Ctrl + O
- 画像全体をROI : Ctrl + A
- ROI領域の画像をコピー : Ctrl + C
- 閉じる : Ctrl + W
- すべて閉じる : Ctrl + Shift + W
- 次の画像 : n
- 前の画像 : b
- 拡大 : +
- 縮小 : -
- 左ビットシフト : <
- 右ビットシフト : >
- ROI解除 : ESC
"""
        text.setPlainText(content)
        layout = QVBoxLayout(self)
        layout.addWidget(text)
