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
            "  + / -  : ズームイン / ズームアウト\n"
            "  f      : Fit / 直前ズーム率トグル\n"
            "  < / >  : ゲイン 0.5x / 2x (表示輝度)\n"
            "  ESC    : ROI解除 (または入力キャンセル)\n"
            "  Ctrl+A : 画像全域をROIに設定\n"
            "  Ctrl+C : ROI矩形をコピー\n"
            "  Ctrl+W : 現在画像を閉じる / Ctrl+Shift+W : 全画像閉じる\n"
            "  矢印キー / Shift+矢印 : ROIを1px / 10px移動\n\n"
            "[解析 / 表示ダイアログ]\n"
            "  A : 解析ダイアログ (単一画像: ヒスト/プロファイル/メタデータ)\n"
            "  D : 表示設定ダイアログ (ゲイン/オフセット等)\n"
            "  T : 特徴量表示ダイアログ\n\n"
            "[マルチタイル比較]\n"
            "  メニュー > 解析 > タイリング比較 から比較ダイアログを開く\n"
            "  共通ROIを変更するとヒストグラム/プロファイルオーバーレイが自動更新\n"
            "  'チャンネル表示設定...' で タイル×チャンネル単位の表示/非表示を切替\n"
            "  色割り当て: Tableau 20 パレットを (タイル番号, チャンネル番号) から決定的に生成\n"
            "  グレースケールは C0 として扱い、統計行ラベルは Tn_Ck 形式 (例: T2_C1)\n"
            "  統合ヒストグラム: 全表示曲線で共通ビン (Copy で同一列長のCSV)\n"
            "  Copy data/stats は現在表示中の曲線のみが対象\n\n"
            "[注意点]\n"
            "  - ROIなしの場合、プロファイル曲線は空データをスキップ\n"
            "  - 非表示にしたチャンネルはコピー/統計にも含まれません\n"
            "  - 比較ダイアログのみ統計テーブルにカラーセルが表示されます\n\n"
            "[チャンネル表記]\n"
            "  単一画像: 元のチャンネル記号 (例: R,G,B) / グレースケールは C0\n"
            "  比較オーバーレイ: 全て Tn_Ck 形式 (タイル n / チャンネル k)\n"
        )
        text.setPlainText(content)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
