# PySide6 Image Viewer

**Version 0.0.1**

PySide6 (Qt6) で作られた、科学技術画像向けの画像ビューアです。

## 特徴

- 複数画像の読み込みとナビゲーション
- ピクセル単位のROI作成編集
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
3. **ROI作成**: マウス左ドラッグ
4. **ROI移動**: ROI内で右ドラッグ
5. **ROIリサイズ**: ROIの枠を左ドラッグ (角・辺をつかむ)
6. **ROI編集**: 矢印キー (画像1px移動)、Shift+矢印 (画像10px移動)
7. **解析表示**: メニュー > 解析 > Show Analysis

### キーボードショートカット

| キー | 動作 |
|------|------|
| `Ctrl+O` | 画像を開く |
| `Ctrl+A` | 画像全体をROI |
| `Ctrl+C` | ROIをコピー |
| `Ctrl+W` | 現在の画像を閉じる |
| `Ctrl+Shift+W` | すべての画像を閉じる |
| `矢印キー` | ROIを画像1px移動 |
| `Shift+矢印` | ROIを画像10px移動 |
| `n` | 次の画像 |
| `b` | 前の画像 |
| `+` | ズームイン (表示中心を保持) |
| `-` | ズームアウト (表示中心を保持) |
| `<` | 左ビットシフト (暗く) |
| `>` | 右ビットシフト (明るく) |
| `ESC` | ROI解除 |
| `f` | Fit / 直前の拡大率をトグル |
| `Ctrl+R` | 表示輝度をリセット (Offset/Gain/Saturation を初期値に戻す) |

#### 表示設定ダイアログのキー操作補足
- ダイアログ表示中でも `n`/`b` で画像切替が可能（アプリ全体ショートカット）。
- 数値入力中に `ESC` を押すと「入力のキャンセル（フォーカス解除）」を行い、ウィンドウは閉じません。
- `<`/`>` でゲインを 0.5x / 2x に変更できます（ゲインはスライダー範囲外の拡張値もスピンボックスで受け付け）。

### 解析機能

#### ヒストグラム
- 各チャンネルの輝度分布を表示
- **統計情報表示**: 平均値、標準偏差、最小値、最大値、中央値を各チャンネルごとに表示
- **左ダブルクリック**: 線形/対数スケール切替
- **Channels...**: 表示するチャンネルを選択
- **Axis ranges...**: 軸範囲を手動設定
- **Copy data**: CSV形式でクリップボードにコピー

#### プロファイル
- ROIの平均輝度プロファイルを表示
- **統計情報表示**: 平均値、標準偏差、最小値、最大値、中央値を各チャンネルごとに表示
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

### ROI
- 現在のズームレベルに基づいてピクセル境界にスナップ
- 座標は画像空間で保持 (ウィジェット空間ではない)
- ズーム変更時もROIを維持

### 対応画像形式
- PNG
- JPEG
- TIFF
- BMP

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
        │   ├── roi_manager.py     # ROI管理Mixin (327行)
        │   ├── roi_editor.py      # キーボード編集Mixin (76行)
        │   └── image_label.py           # 統合クラス (97行)
        └── dialogs/               # ダイアログウィンドウ
            ├── __init__.py
            ├── help_dialog.py     # ヘルプ (169行)
            ├── diff_dialog.py     # 差分表示 (109行)
            └── analysis/          # 解析ダイアログ (サブパッケージ)
                ├── __init__.py
        ├── analysis_dialog.py  # メインダイアログ (分割後: タブ管理が中心)
                ├── controls.py         # 設定ダイアログ (104行)
        ├── widgets.py          # カスタムウィジェット (63行)
        └── tabs/               # タブUIをモジュール化
          ├── metadata_tab.py     # メタデータ表
          ├── histogram_tab.py    # ヒストグラムUI
          └── profile_tab.py      # プロファイルUI
```

**設計原則**:
- **core/**: UI非依存の再利用可能なユーティリティ
- **ui/widgets/**: 画像表示専用ウィジェット (Mixinパターン)
- **ui/dialogs/**: 各種ダイアログウィンドウ
- **ui/dialogs/analysis/**: 解析機能のサブパッケージ (密結合したコンポーネント群)


## バージョン履歴
 
### 0.0.1 (2025年10月20日)
- **Refactor & release (version 0.0.1)**
  - 主要な変更点をこのリリースに統合し、今後の基準とする
  - Pathlib によるパス処理への統一
  - 不要 / 重複コードの削除と関数化（例: 画像読み込みの共通化）
  - 表示輝度ダイアログの改善（SpinBox 入力の即時反映 / Enter での反映対策）
  - モジュール分割とMixin化により UI コンポーネントの責務を分離
  - README・パッケージメタ情報の更新（`__version__ = "0.0.1"`）
  - テスト整備の準備（exif メタデータ関連のテスト調整）


### 輝度補正（dtype対応）
- オフセット・ゲイン・飽和（Saturation）は画像のデータ型（float/uint8/uint16 など）ごとに個別に保持されます。
- 画像切替時・dtype切替時は、それぞれの dtype に保存した値が自動で適用されます。
- 既定値（初期値）
  - float: offset=0, gain=1.0, saturation=1.0（表示の基準は [0,1]）
  - uint8: offset=0, gain=1.0, saturation=255
  - 高ビット深度整数（例: 10/12/16bit）: saturation=min(maxVal,4095)
- ダイアログ非表示時に float ⇔ 整数 を往復しても、型に合った飽和レベルが自動で選ばれ、過去の型の値が残らないようになっています。

