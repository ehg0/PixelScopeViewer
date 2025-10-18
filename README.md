# PySide6 Image Viewer

PySide6 (Qt6) で作られた、科学技術画像向けの画像ビューアです。

## 特徴

- 複数画像の読み込みとナビゲーション
- ピクセル単位の選択範囲作成編集
- ズーム機能 (+/- キー)
- ビットシフト表示 (RAWデータ可視化用、</> キー)
- 解析機能
  - ヒストグラム (線形/対数表示切替)
  - プロファイル (水平/垂直/対角、相対/絶対座標)
  - メタデータ表示 (EXIF等の画像埋め込み情報)
  - 差分画像作成
- CSV形式でのデータエクスポート

## インストール

### 必要要件

- Python 3.8 以上

### セットアップ

```powershell
# 依存パッケージのインストール
pip install -r requirements.txt
```

必須パッケージ:
- PySide6 (Qt for Python)
- numpy (配列処理)
- Pillow (画像読み込み)
- exifread (完全なEXIF情報読み取り)
- pyqtgraph (高速グラフ描画、ヒストグラム・プロファイル表示)

## 使い方

### 起動

```powershell
python main.py
```

### 基本操作

1. **画像を開く**: `Ctrl+O` または メニュー > ファイル > 読み込み
2. **画像の切替**: `n` (次) / `b` (前)
3. **選択範囲作成**: マウス左ドラッグ
4. **選択範囲移動**: 選択範囲内で右ドラッグ
5. **選択範囲リサイズ**: 選択範囲の枠を左ドラッグ (角・辺をつかむ)
6. **選択範囲編集**: 矢印キー (画像1px移動)、Shift+矢印 (画像10px移動)
7. **解析表示**: メニュー > 解析 > Show Analysis

### キーボードショートカット

| キー | 動作 |
|------|------|
| `Ctrl+O` | 画像を開く |
| `Ctrl+A` | 画像全体を選択 |
| `Ctrl+C` | 選択範囲をコピー |
| `Ctrl+W` | 現在の画像を閉じる |
| `Ctrl+Shift+W` | すべての画像を閉じる |
| `矢印キー` | 選択範囲を画像1px移動 |
| `Shift+矢印` | 選択範囲を画像10px移動 |
| `n` | 次の画像 |
| `b` | 前の画像 |
| `+` | ズームイン (表示中心を保持) |
| `-` | ズームアウト (表示中心を保持) |
| `<` | 左ビットシフト (暗く) |
| `>` | 右ビットシフト (明るく) |
| `ESC` | 選択解除 |

### 解析機能

#### ヒストグラム
- 各チャンネルの輝度分布を表示
- **左ダブルクリック**: 線形/対数スケール切替
- **Channels...**: 表示するチャンネルを選択
- **Axis ranges...**: 軸範囲を手動設定
- **Copy data**: CSV形式でクリップボードにコピー

#### プロファイル
- 選択範囲の平均輝度プロファイルを表示
- **左ダブルクリック**: 水平/垂直/対角 方向切替
- **右ダブルクリック**: 相対座標/絶対座標切替
- **Channels...**: 表示するチャンネルを選択
- **Axis ranges...**: 軸範囲を手動設定
- **Copy data**: CSV形式でクリップボードにコピー

#### メタデータ
- 画像ファイルの埋め込み情報を**表形式**で表示
- 基本情報: フォーマット、サイズ、カラーモード
- **完全なEXIF情報**: exifreadライブラリで包括的に読み取り
  - カメラ設定 (ISO, 絞り, シャッター速度など)
  - 撮影日時、GPS情報
  - レンズ情報、ホワイトバランス
  - Makernote以外のすべてのタグ
- その他のフォーマット固有情報
- 文字化けを防ぐエンコーディング処理 (UTF-8/Shift-JIS/CP932/Latin-1)
- **データコピー機能**:
  - **Ctrl+C**: 選択したセル/行/範囲をカンマ区切りでコピー
  - **「クリップボードにコピー」ボタン**: 全データをコピー
  - Excel/Google Spreadsheetsに貼り付け可能
- テキストブラウザでコピー&ペースト可能

#### 差分画像
- 2枚の画像の差分を計算
- オフセット値を指定可能 (デフォルト: 256)
- 計算式: `差分 = (画像A - 画像B) + オフセット`

## プロジェクト構造

```
pyside_image_viewer/
 core/                   # UI非依存のユーティリティ
    image_io.py        # 画像I/O、変換処理
 ui/                     # UIコンポーネント
    viewer.py          # メインウィンドウ
    widgets.py         # カスタムウィジェット
    dialogs/           # ダイアログ
        help_dialog.py     # ヘルプ
        diff_dialog.py     # 差分画像
        analysis/          # 解析ダイアログ
            analysis_dialog.py  # メインダイアログ
            controls.py         # 設定ダイアログ
 __init__.py            # パッケージエントリーポイント
 main.py                # アプリケーション起動
```

## プログラムから使う

```python
from pyside_image_viewer import main

# アプリケーションを起動
main()
```

または

```python
from pyside_image_viewer import ImageViewer
from pyside_image_viewer.core import pil_to_numpy, numpy_to_qimage
from PySide6.QtWidgets import QApplication

# 画像を読み込んでNumPy配列に変換
arr = pil_to_numpy("image.png")

# QImageに変換
qimg = numpy_to_qimage(arr)

# ビューアを起動
app = QApplication([])
viewer = ImageViewer()
viewer.show()
app.exec()
```

## 技術仕様

### ビットシフト機能
- 左シフト (`<`): 値を2で割る (暗く表示)
- 右シフト (`>`): 値を2倍する (明るく表示)
- ステータスバーには常に元の値を表示
- 解析は表示中(シフト後)のデータで実行

### 選択範囲
- 現在のズームレベルに基づいてピクセル境界にスナップ
- 座標は画像空間で保持 (ウィジェット空間ではない)
- ズーム変更時も選択範囲を維持

### 対応画像形式
- PNG
- JPEG
- TIFF
- BMP

## トラブルシューティング

### matplotlibがインストールされていない
ヒストグラムとプロファイルタブが空になります。

```powershell
pip install matplotlib
```

### 画像が読み込めない
- Pillowがインストールされているか確認
- 対応形式か確認 (PNG, JPEG, TIFF, BMP)
- ファイルのパーミッションを確認

### 動作が重い
- 大きい画像の場合はズームを使用
- 解析は小さい選択範囲で実行
- 非常に大きい画像は事前にダウンサンプリング

## アーキテクチャ

### コード構造 (2025年10月リファクタリング)

保守性向上のため、長大なファイルをモジュール化しました。

#### ディレクトリ構造

```
pyside6_imageViewer/
├── main.py                        # エントリーポイント
├── legacy/                        # 旧バージョン (gitignore対象)
├── tests/                         # テストファイル
│   └── test_exif_metadata.py
└── pyside_image_viewer/           # メインパッケージ
    ├── app.py                     # アプリケーション起動
    ├── core/                      # UI非依存ユーティリティ
    │   ├── __init__.py
    │   └── image_io.py            # 画像I/O、EXIF読み取り (236行)
    └── ui/                        # UIコンポーネント
        ├── __init__.py
        ├── viewer.py              # メインビューアウィンドウ (525行)
        ├── widgets/               # カスタムウィジェット
        │   ├── __init__.py
        │   ├── base_image_label.py      # 基底クラス (165行)
        │   ├── selection_manager.py     # 選択管理Mixin (327行)
        │   ├── selection_editor.py      # キーボード編集Mixin (76行)
        │   └── image_label.py           # 統合クラス (97行)
        └── dialogs/               # ダイアログウィンドウ
            ├── __init__.py
            ├── help_dialog.py     # ヘルプ (169行)
            ├── diff_dialog.py     # 差分表示 (109行)
            └── analysis/          # 解析ダイアログ (サブパッケージ)
                ├── __init__.py
                ├── analysis_dialog.py  # メインダイアログ (575行)
                ├── controls.py         # 設定ダイアログ (104行)
                └── widgets.py          # カスタムウィジェット (63行)
```

**設計原則**:
- **core/**: UI非依存の再利用可能なユーティリティ
- **ui/widgets/**: 画像表示専用ウィジェット (Mixinパターン)
- **ui/dialogs/**: 各種ダイアログウィンドウ
- **ui/dialogs/analysis/**: 解析機能のサブパッケージ (密結合したコンポーネント群)

#### pyside_image_viewer/ui/widgets/ (439行 → 4ファイルに分割)

**分割前**: `widgets.py` (439行) - 画像表示と選択機能が混在

**分割後**:
- `base_image_label.py` (165行) - 基底クラス
  - 画像表示とズーム
  - 座標変換ユーティリティ
- `selection_manager.py` (327行) - 選択管理Mixin
  - マウスによる選択作成・移動・リサイズ
  - 8つのグラブポイント (4隅 + 4辺)
  - カーソル形状フィードバック
- `selection_editor.py` (76行) - キーボード編集Mixin
  - 矢印キーによる1ピクセル移動
  - Shift+矢印で10ピクセル移動
- `image_label.py` (97行) - 統合クラス
  - 全機能を継承して提供

**設計パターン**: Mixin + 多重継承による機能分離

**メリット**:
- 単一責任の原則に準拠
- 各機能の独立したテスト・拡張が容易
- 選択機能を他のウィジェットに再利用可能

#### 今後の拡張指針

**analysis_dialog.py (575行)** は現時点で分割不要:
- 600行前後は許容範囲内
- 既に論理的にタブ単位で分離されている
- CopyableTableWidgetを分離済み (analysis/widgets.py)
- 複雑な状態管理 (matplotlib連携) を分割するとかえって複雑化

**拡張が必要になった場合の分割案**:
1. タブごとにクラス化 (InfoTab, HistogramTab, ProfileTab)
2. matplotlib描画ロジックを別モジュール化
3. データ処理 (_compute_profile等) をutilsに抽出

#### カスタムウィジェット

**ui/dialogs/analysis/widgets.py** (63行):
- `CopyableTableWidget`: Ctrl+Cコピー対応のテーブルウィジェット
  - カンマ区切り形式でクリップボードにコピー
  - 複数セル/行の選択に対応
  - メタデータ表示に使用

**ui/dialogs/analysis/controls.py** (104行):
- `ChannelsDialog`: チャンネル選択ダイアログ
- `RangesDialog`: 軸範囲設定ダイアログ

#### ファイル行数の目安

| 範囲 | 評価 | 対応 |
|------|------|------|
| ~300行 | ✅ 理想的 | そのまま |
| 300-500行 | ⚠️ 許容範囲 | 機能が増えたら分割検討 |
| 500行~ | ❌ 分割推奨 | モジュール化・Mixin化 |

## ライセンス

MIT License

## バージョン履歴

### 2.3.0 (2025年10月)
- **コード最適化とディレクトリ構造整理**
  - image_io.py: ヘルパー関数抽出 (_is_binary_tag, _is_printable_text, _decode_bytes)
  - analysis_dialog.py: numpy操作による配列処理高速化
  - viewer.py: 冗長な条件チェック削減
  - selection_manager.py: 重複チェックを統合、不要なtry-except削除
  - base_image_label.py: ゼロチェックの簡略化
  - tests/test_exif_metadata.py: インポートパスとファイルパス修正
  - ui/__init__.py: 重複したエクスポート定義を修正
  - .gitignore: legacy/ディレクトリを追加
  - README.md: ディレクトリ構造の詳細ドキュメント追加

### 2.2.0 (2025年10月)
- **プロジェクト構造リファクタリング**
  - analysis_dialog.py (638行→575行): CopyableTableWidgetを分離
  - 新規ファイル: `ui/dialogs/analysis/widgets.py` (カスタムウィジェット用)
  - 不要なファイルを削除: `ui/widgets_old.py` (バックアップ), `test_exif.py` (重複)
  - テストファイルを整理: `tests/test_exif_metadata.py` に移動
- **メタデータタブ機能強化**
  - 表形式表示に変更 (QTableWidget)
  - Ctrl+Cで選択範囲をコピー
  - 「クリップボードにコピー」ボタンで全データをコピー
  - CSV互換のカンマ区切り形式
  - セル/行/範囲の自由な選択が可能

### 2.1.0 (2025年10月)
- widgets.pyをモジュール化 (保守性向上)
- 選択範囲のエッジ・コーナーリサイズ対応
- 対角プロファイル表示追加
- 表示中心を保持するズーム機能
- Ctrl+A選択時の自動通知
- 矢印キーでの画像ピクセル単位移動
- **メタデータタブ追加** (exifreadによる完全なEXIF情報表示、文字化け対策済み)

### 2.0.0
- core/ui階層にリファクタリング
- 包括的なdocstring追加
- ダブルクリックによる解析ダイアログ操作
- ビットシフト可視化機能
- キーボードによる選択範囲編集強化

### 1.0.0
- 初回リリース
