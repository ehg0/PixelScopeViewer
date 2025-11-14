"""Help dialog for tiling comparison shortcuts."""

from PySide6.QtWidgets import QDialog, QTextEdit, QVBoxLayout


class TilingHelpDialog(QDialog):
    """タイリング比較用ヘルプ / ショートカット一覧.

    Phase 2 (マルチタイル比較オーバーレイ) の機能を含む操作ガイド。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ヘルプ / タイリング比較")
        self.resize(760, 640)

        text = QTextEdit(self)
        text.setReadOnly(True)

        content = (
            "PixelScopeViewer タイリング比較ヘルプ\n"
            "=====================================\n\n"
            "[表示 / ナビゲーション]\n"
            "  + / -        : ズームイン / ズームアウト (全タイル同期)\n"
            "  f            : Fit / 直前ズーム率トグル\n"
            "  矢印キー      : スクロール (上下左右) 全タイル同期\n"
            "  Shift+矢印    : 高速スクロール\n"
            "  マウスホイール : 垂直スクロール (全タイル)\n"
            "  Ctrl+ホイール : ズームイン/アウト\n"
            "  タイルクリック : アクティブタイル切替\n"
            "  Tab / Shift+Tab: 次 / 前 のタイルへアクティブ切替 (ローテーション)\n\n"
            "[明るさ / 表示調整]\n"
            "  < / >        : ゲイン 0.5x / 2x\n"
            "  D            : 明るさ調整ダイアログ (Gain/Offset/Saturation)\n"
            "  Ctrl+R       : 明るさリセット (Gain=1.0 他初期値)\n"
            "  個別Offset/Saturation : dtypeに応じタイル毎設定可能\n"
            "  Gain         : 全タイル共通係数\n\n"
            "[ROI操作 (共通ROI)]\n"
            "  Ctrl+A       : 全画像範囲をROI\n"
            "  ESC          : ROI解除\n"
            "  左ドラッグ    : ROI作成\n"
            "  右ドラッグ    : ROI移動\n"
            "  ROI端/角ドラッグ : ROIリサイズ\n"
            "  矢印 / Shift+矢印 : ROI 1px / 10px 移動\n"
            "  ROI変更で比較オーバーレイ (ヒスト/プロファイル) 自動更新\n\n"
            "[マルチタイル比較オーバーレイ]\n"
            "  チャンネル表示設定... : タイル×チャンネル単位の表示/非表示切替\n"
            "  統合ヒストグラム      : 全表示曲線で共通ビン採用 (コピー列長ズレ無し)\n"
            "  プロファイル          : ROI領域平均輝度の重ね合わせ。空ROIは安全スキップ\n"
            "  色割り当て            : Tableau 20 パレット (tile_index, channel_index) で決定的\n"
            "  ラベリング            : グレースケールは C0 / 統計行は Tn_Ck (例: T2_C1)\n"
            "  統計テーブル          : 比較ダイアログのみカラーセル表示\n"
            "  Copy data/stats       : 現在表示中(非表示除外)曲線のみをCSVコピー\n"
            "  非表示チャンネル      : 統計・コピー対象外 (オーバーレイも更新除外)\n\n"
            "[メタデータ比較]\n"
            "  ファイル/EXIFの差分行を淡黄色で強調 (FileSize, Filepath除外)\n\n"
            "[チャンネル表記]\n"
            "  単一画像: 元チャンネル記号 (R,G,B / C0)\n"
            "  タイリング比較オーバーレイ: すべて Tn_Ck\n\n"
            "[注意事項]\n"
            "  - ROI未設定時はプロファイル曲線生成をスキップ\n"
            "  - 空配列やサイズ0のタイルは自動的に除外\n"
            "  - グレースケール 'I' の内部処理は C0 に正規化\n"
            "  - パレットは決定的で再現性がありセッション差異なし\n"
        )

        text.setPlainText(content)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
