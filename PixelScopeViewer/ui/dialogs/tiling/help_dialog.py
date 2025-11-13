"""Help dialog for tiling comparison shortcuts."""

from PySide6.QtWidgets import QDialog, QTextEdit, QVBoxLayout


class TilingHelpDialog(QDialog):
    """Dialog showing keyboard shortcuts for tiling comparison.

    Displays a read-only text widget with all available keyboard
    shortcuts specific to the tiling comparison dialog.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("タイリング比較 - キーボードショートカット")
        self.resize(600, 500)

        text = QTextEdit(self)
        text.setReadOnly(True)

        content = """【表示操作】
- ズームイン : +
- ズームアウト : -
- Fit / 直前の拡大率をトグル : f

【スクロール（全タイル同期）】
- 上スクロール : ↑
- 下スクロール : ↓
- 左スクロール : ←
- 右スクロール : →
- 高速スクロール : Shift + 矢印キー

【明るさ調整】
- ゲイン0.5（暗く） : <
- ゲイン2（明るく） : >
- 明るさ調整ダイアログ : D
- 明るさリセット : Ctrl+R

【ROI操作】
- 全画像範囲を選択 : Ctrl+A
- ROI解除 : ESC
- ROI作成 : マウス左ボタンでドラッグ
- ROI移動 : マウス右ボタンでドラッグ
- ROIリサイズ : ROI端/角をドラッグ

【マウス操作】
- ズームイン : Ctrl + マウスホイール上
- ズームアウト : Ctrl + マウスホイール下
- スクロール（全タイル同期） : マウスホイール

【その他】
- アクティブタイル切り替え : タイルをクリック
- タイル間のスクロール、ズーム、ROIは自動的に同期されます
- 各タイルのdtypeごとに個別の明るさパラメータ（Offset/Saturation）を調整可能
- 共通のGainパラメータですべてのタイルの明るさを一括調整可能
"""
        text.setPlainText(content)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
