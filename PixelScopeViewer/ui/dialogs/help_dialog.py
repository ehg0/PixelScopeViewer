"""Help dialog showing keyboard shortcuts."""

from PySide6.QtWidgets import QDialog, QTextEdit, QVBoxLayout


class HelpDialog(QDialog):
    """Dialog showing keyboard shortcuts and usage help.

    Displays a read-only text widget with all available keyboard
    shortcuts in Japanese.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ヘルプ / キーボードショートカット")
        self.resize(640, 520)

        text = QTextEdit(self)
        text.setReadOnly(True)

        content = (
            "PixelScopeViewer ヘルプ\n"
            "================================\n\n"
            "[基本操作]\n"
            "  Ctrl+O : 画像を開く\n"
            "  n / b  : 次 / 前 の画像\n"
            "  + / - / Ctrl+ホイール : ズームイン / ズームアウト\n"
            "  f      : Fit / 直前ズーム率トグル\n"
            "  < / >  : ゲイン 0.5x / 2x (表示輝度)\n"
            "  Ctrl+R : 明るさリセット\n"
            "  Ctrl+A : 画像全域をROIに設定\n"
            "  Ctrl+C : ROI矩形をコピー\n"
            "  矢印キー / Shift+矢印 : ROIを1px / 10px移動\n\n"
            "  Ctrl+W : 現在画像を閉じる / Ctrl+Shift+W : 全画像閉じる\n"
            "[ダイアログ表示]\n"
            "  D : 表示設定 (チャンネル毎の色/表示ゲイン・オフセット)\n"
            "  A : 解析ビュー (単一画像: メタデータ/プロファイル/ヒスト)\n"
            "  T : 特徴量表示\n"
            "  Shift+T : 複数画像比較\n\n"
            "[注意点]\n"
            "  - 詳しい使い方はREADMEを参照してください。\n\n"
        )
        text.setPlainText(content)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
