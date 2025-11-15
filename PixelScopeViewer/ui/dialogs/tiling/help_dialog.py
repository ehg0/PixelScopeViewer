"""Help dialog for tiling comparison shortcuts."""

from PySide6.QtWidgets import QDialog, QTextEdit, QVBoxLayout


class TilingHelpDialog(QDialog):
    """複数画像比較用ヘルプ / ショートカット一覧."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ヘルプ / 複数画像比較")
        self.resize(760, 640)

        text = QTextEdit(self)
        text.setReadOnly(True)

        content = (
            "PixelScopeViewer 複数画像比較ヘルプ\n"
            "=====================================\n\n"
            "[基本操作]\n"
            "  + / - /Ctrl+ホイール : ズームイン / ズームアウト\n"
            "  f            : Fit / 直前ズーム率トグル\n"
            "  < / >        : ゲイン 0.5x / 2x (表示輝度)\n"
            "  矢印キー / Shift+矢印 : 表示位置移動\n"
            "  タイルクリック : アクティブタイル切替\n\n\n"
            "  Ctrl+A       : 全画像範囲をROI\n"
            "  Ctrl+C       : アクティブタイルのROI矩形をコピー\n"
            "  Ctrl+Shift+C : 全タイルのROI矩形をコピー\n"
            "  Ctrl+R       : 明るさリセット (Gain=1.0 他初期値)\n"
            "[ダイアログ表示]\n"
            "  D            : 表示設定(輝度調整のみ)\n"
            "  A            : 解析ビュー (単一画像: メタデータ/プロファイル/ヒスト)\n"
            "  Ctrl+Shift+A : 解析ビュー (複数画像: メタデータ/プロファイル/ヒスト)\n\n"
            "[注意事項]\n"
            "  - 全タイル同期動作\n"
            "  - 解析ビュー (単一画像)の色割り当てはチャンネル数毎の初期配色固定\n"
            "  - 解析ビュー (複数画像)の色割り当てはTableau 20 パレット\n"
            "  - 詳しい使い方はREADMEを参照してください。\n\n"
        )

        text.setPlainText(content)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
