"""Help dialog showing keyboard shortcuts."""

from PySide6.QtWidgets import QDialog, QTextEdit, QVBoxLayout


class HelpDialog(QDialog):
    """Dialog showing keyboard shortcuts and usage help.

    Displays a read-only text widget with all available keyboard
    shortcuts in Japanese.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("キーボードショートカット")
        self.resize(520, 360)

        text = QTextEdit(self)
        text.setReadOnly(True)

        content = """- ゲイン0.5（暗く） : <
- ゲイン2（明るく） : >
- ROI解除 : ESC
- Fit / 直前の拡大率をトグル : f
"""
        text.setPlainText(content)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
