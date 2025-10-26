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

        content = """Keyboard shortcuts:
- 読み込み : Ctrl + O
- 画像全体をROI : Ctrl + A
- ROI領域の画像をコピー : Ctrl + C
- 閉じる : Ctrl + W
- すべて閉じる : Ctrl + Shift + W
- 表示設定ダイアログを開く : D
- 解析ダイアログを開く : A
- 次の画像 : n
- 前の画像 : b
- 拡大 : +
- 縮小 : -
- ゲイン0.5（暗く） : <
- ゲイン2（明るく） : >
- ROI解除 : ESC
- Fit / 直前の拡大率をトグル : f
"""
        text.setPlainText(content)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
