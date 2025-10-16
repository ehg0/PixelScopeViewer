# PySide6 Image Viewer

PySide6 (Qt6) で作られた、科学技術画像向けの画像ビューアです。

## 特徴

- 複数画像の読み込みとナビゲーション
- ピクセル単位の選択範囲作成編集
- ズーム機能 (+/- キー)
- ビットシフト表示 (RAWデータ可視化用、</> キー)
- 解析機能
  - ヒストグラム (線形/対数表示切替)
  - プロファイル (水平/垂直、相対/絶対座標)
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

オプション:
- matplotlib (ヒストグラムプロファイル表示に必要)

## 使い方

### 起動

```powershell
python app_2.py
```

### 基本操作

1. **画像を開く**: `Ctrl+O` または メニュー > ファイル > 読み込み
2. **画像の切替**: `n` (次) / `b` (前)
3. **選択範囲作成**: マウス左ドラッグ
4. **選択範囲移動**: 選択範囲内で右ドラッグ
5. **解析表示**: メニュー > 解析 > Show Analysis

### キーボードショートカット

| キー | 動作 |
|------|------|
| `Ctrl+A` | 全選択 |
| `Ctrl+C` | 選択範囲をコピー |
| `n` | 次の画像 |
| `b` | 前の画像 |
| `+` | ズームイン |
| `-` | ズームアウト |
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
- **左ダブルクリック**: 水平/垂直切替
- **右ダブルクリック**: 相対座標/絶対座標切替
- **Channels...**: 表示するチャンネルを選択
- **Axis ranges...**: 軸範囲を手動設定
- **Copy data**: CSV形式でクリップボードにコピー

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

## ライセンス

MIT License

## バージョン履歴

### 2.0.0
- core/ui階層にリファクタリング
- 包括的なdocstring追加
- ダブルクリックによる解析ダイアログ操作
- ビットシフト可視化機能
- キーボードによる選択範囲編集強化

### 1.0.0
- 初回リリース
