# マルチフレーム画像（4次元配列）の扱い方

PixelScopeViewerで4次元配列 `(H, W, C, N)` を扱う方法を説明します。

## 概要

4次元配列（例: ビデオフレーム、時系列画像データ）は、以下の手順で扱います:

1. **事前展開**: 4D配列を個別のフレームファイルに分割
2. **一括読み込み**: すべてのフレームをPixelScopeViewerで開く
3. **フレーム移動**: `n`/`b`キーでフレーム間を移動

## 手順

### 1. サンプルデータの生成（オプション）

テスト用の4D配列を生成します:

```powershell
python generate_sample_multiframe.py
```

これにより`sample/`ディレクトリに以下のファイルが作成されます:
- `sample_video.npy` (256×256×3×30フレーム)
- `sample_sequence.npy` (128×128×1×20フレーム)
- `sample_large_video.npy` (512×512×3×100フレーム)

### 2. フレームの展開

4D配列を個別のフレームファイルに展開します:

```powershell
python expand_multiframe.py input.npy [output_dir]
```

**例:**

```powershell
# 基本的な使い方
python expand_multiframe.py sample/sample_video.npy

# 出力先を指定
python expand_multiframe.py sample/sample_video.npy frames/

# 既存の4Dファイルを展開
python expand_multiframe.py your_data.npy my_frames/
```

実行すると、以下のようなファイルが生成されます:

```
sample_video_frames/
├── frame_0000.npy
├── frame_0001.npy
├── frame_0002.npy
├── ...
└── frame_0029.npy
```

### 3. PixelScopeViewerで表示

1. PixelScopeViewerを起動:
   ```powershell
   python main.py
   ```

2. フレームファイルをすべて開く:
   - `Ctrl+O` でファイル選択ダイアログを開く
   - 展開したフレームのディレクトリに移動
   - `Ctrl+A` ですべてのフレームを選択
   - 「開く」をクリック

3. フレーム間を移動:
   - `n`: 次のフレーム
   - `b`: 前のフレーム
   - または画像メニューから選択

## スクリプトから使用する

Pythonスクリプト内で展開機能を使用できます:

```python
from expand_multiframe import expand_multiframe

# 4D配列を展開
expand_multiframe(
    input_path='video.npy',
    output_dir='frames/',
    prefix='video_frame'
)
```

詳細は `example_expand_multiframe.py` を参照してください。

## カスタムローダーでの対応（非推奨）

カスタムローダーで4D配列を直接扱うこともできますが、以下の制限があります:

- **最初のフレームのみ表示**: Viewerは1ファイル=1画像の設計
- **手動での切り替え不可**: すべてのフレームを見るには別の方法が必要

このため、**事前展開方式を推奨**します。

カスタムローダーの実装例は `custom_loaders/_example_multiframe_loader.py` を参照してください。

## トラブルシューティング

### Q: "Expected 4D array" エラーが出る

A: 入力ファイルが4次元配列でない可能性があります。以下で確認してください:

```python
import numpy as np
data = np.load('your_file.npy')
print(f"Shape: {data.shape}, ndim: {data.ndim}")
```

4次元でない場合は、データの形状を変更するか、標準の読み込みを使用してください。

### Q: メモリ不足エラーが出る

A: 大きな4D配列の場合、メモリを大量に消費します。以下を試してください:

1. **部分的に展開**: 必要なフレームのみ展開
   ```python
   data = np.load('large_file.npy')
   for i in range(0, 100, 10):  # 10フレームごと
       np.save(f'frame_{i:04d}.npy', data[:, :, :, i])
   ```

2. **メモリマップ使用**: 大きなファイルはメモリマップで読む
   ```python
   data = np.load('large_file.npy', mmap_mode='r')
   ```

### Q: 展開に時間がかかる

A: これは正常です。大きな配列の場合、展開には時間がかかります。

- 512×512×3×1000フレーム: 約30秒～1分
- プログレス表示で進捗を確認できます

## まとめ

4次元配列の推奨ワークフロー:

1. ✅ `generate_sample_multiframe.py` でテストデータ生成（任意）
2. ✅ `expand_multiframe.py` でフレームを展開
3. ✅ PixelScopeViewerで一括読み込み
4. ✅ `n`/`b`キーでフレーム移動

この方法により、すべてのフレームを簡単に閲覧できます！
