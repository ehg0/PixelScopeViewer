# Custom Image Loaders (Plugins)

このディレクトリは、PixelScopeViewerがネイティブにサポートしていない画像フォーマットを読み込むためのカスタムローダー（プラグイン）を配置する場所です。

## 概要

カスタムローダーを使用することで、以下のような独自フォーマットに対応できます：

- 独自のバイナリ形式（.dat, .raw など）
- カスタム構造のNPZファイル
- Pickleで保存された画像データ
- その他の非標準フォーマット

## クイックスタート

1. **サンプルをコピー**
   ```bash
   cp _example_loader.py my_custom_loader.py
   ```

2. **ローダー関数を実装**
   ```python
   def my_loader(path: str) -> Optional[np.ndarray]:
       # あなたのフォーマットを読み込む処理
       if path.endswith('.myformat'):
           data = load_my_format(path)
           return data
       return None  # 処理できない場合
   ```

3. **ローダーを登録**
   ```python
   from PixelScopeViewer.core.image_io import ImageLoaderRegistry
   
   registry = ImageLoaderRegistry.get_instance()
   registry.register(my_loader, extensions=['.myformat'], priority=10)
   ```

4. **アプリを起動**
   - カスタムローダーは自動的に読み込まれます
   - `.myformat`ファイルが開けるようになります

## ローダー関数の仕様

### 基本構造

```python
from typing import Optional
import numpy as np

def my_loader_function(path: str) -> Optional[np.ndarray]:
    """カスタム画像ローダー
    
    Args:
        path: ファイルパス（文字列）
    
    Returns:
        np.ndarray: 画像データ（H, W）または（H, W, C）
        None: このファイルを処理できない場合
    """
    # 1. 拡張子をチェック
    if not path.lower().endswith('.myext'):
        return None
    
    # 2. ファイルを読み込む
    try:
        # あなたの読み込み処理
        data = load_your_format(path)
        
        # 3. NumPy配列として返す
        return data
        
    except Exception:
        # エラー時はNoneを返す（他のローダーが試行される）
        return None
```

### 配列の要件

返却するNumPy配列は以下の条件を満たす必要があります：

- **形状**: `(H, W)` または `(H, W, C)`
  - `H`: 高さ（行数）
  - `W`: 幅（列数）
  - `C`: チャンネル数（1, 2, 3, または 4）

- **データ型**: 推奨は `np.uint8`、`np.uint16`、`np.float32`
  - `uint8`: 0-255の整数値
  - `uint16`: 0-65535の整数値
  - `float32`: 0.0-1.0の浮動小数点数（またはHDR範囲）

### 例：NPZファイル

```python
def npz_custom_loader(path: str) -> Optional[np.ndarray]:
    if not path.endswith('.npz'):
        return None
    
    try:
        data = np.load(path)
        
        # キー 'image_data' を探す
        if 'image_data' in data:
            return data['image_data']
        
        # デフォルトキーを試す
        if 'arr_0' in data:
            return data['arr_0']
        
        return None
    except Exception:
        return None

# 登録
from PixelScopeViewer.core.image_io import ImageLoaderRegistry
ImageLoaderRegistry.get_instance().register(
    npz_custom_loader, 
    extensions=['.npz'], 
    priority=10
)
```

### 例：固定サイズのバイナリファイル

```python
def binary_loader(path: str) -> Optional[np.ndarray]:
    if not path.endswith('.dat'):
        return None
    
    try:
        # 固定サイズ: 512x512, uint8
        width, height = 512, 512
        
        with open(path, 'rb') as f:
            data = np.fromfile(f, dtype=np.uint8)
        
        # サイズチェック
        if len(data) != width * height:
            return None
        
        # リシェイプ
        img = data.reshape((height, width))
        return img
        
    except Exception:
        return None

# 登録
ImageLoaderRegistry.get_instance().register(
    binary_loader,
    extensions=['.dat'],
    priority=10
)
```

### 例：ワイルドカードローダー（すべてのファイルを試行）

```python
def wildcard_loader(path: str) -> Optional[np.ndarray]:
    """すべてのファイルに対して試行されるフォールバックローダー"""
    
    # 方法1: Pickleとして読み込む
    try:
        import pickle
        with open(path, 'rb') as f:
            data = pickle.load(f)
        if isinstance(data, np.ndarray):
            return data
    except:
        pass
    
    # 方法2: 他の手法...
    
    return None

# ワイルドカードとして登録（低優先度）
ImageLoaderRegistry.get_instance().register(
    wildcard_loader,
    extensions=['*'],  # すべての拡張子
    priority=-100      # 他のローダーの後に試行
)
```

## 登録オプション

### `register(loader_func, extensions, priority)`

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `loader_func` | `Callable[[str], Optional[np.ndarray]]` | ローダー関数 |
| `extensions` | `List[str]` または `None` | 対応する拡張子リスト（例: `['.dat', '.raw']`）<br>`['*']` または `None` でワイルドカード |
| `priority` | `int` | 優先度<br>デフォルト: `0` |

### 優先度の仕組み

**標準ローダー（.npy, .exr, .png など）は優先度 0 として扱われます。**

| 優先度 | タイミング | 用途 |
|--------|-----------|------|
| **> 0** | 標準ローダーより**先**に試行 | 既存フォーマットの上書き |
| **= 0** | 標準ローダーと**同等**または**後**に試行 | 新しいフォーマットの追加（デフォルト） |
| **< 0** | すべてのローダーの**後**に試行 | フォールバック・ワイルドカード |

### 優先度の具体例

#### 例1: .npy ファイルの標準動作を上書き

```python
def custom_npy_loader(path: str) -> Optional[np.ndarray]:
    if not path.endswith('.npy'):
        return None
    
    # カスタムunpack処理
    data = np.load(path)
    return data['my_custom_key']  # 特定のキーを取り出す

# priority >= 1 で標準の .npy ローダーより優先される
ImageLoaderRegistry.get_instance().register(
    custom_npy_loader,
    extensions=['.npy'],
    priority=1  # 標準ローダー(0)より優先
)
```

#### 例2: 新しいフォーマットの追加（標準を上書きしない）

```python
def dat_loader(path: str) -> Optional[np.ndarray]:
    if not path.endswith('.dat'):
        return None
    # ... 読み込み処理 ...

# priority=0 (デフォルト) で標準ローダーと共存
ImageLoaderRegistry.get_instance().register(
    dat_loader,
    extensions=['.dat'],
    priority=0  # または省略可能（デフォルト値）
)
```

#### 例3: フォールバックローダー

```python
def fallback_loader(path: str) -> Optional[np.ndarray]:
    # すべてのフォーマットで試行錯誤
    try:
        return np.load(path)
    except:
        pass
    
    try:
        import pickle
        with open(path, 'rb') as f:
            return pickle.load(f)
    except:
        pass
    
    return None

# priority < 0 で最後の手段として試行
ImageLoaderRegistry.get_instance().register(
    fallback_loader,
    extensions=['*'],  # すべてのファイル
    priority=-100  # すべてのローダーの後
)
```

### 優先度の推奨値

| 用途 | 推奨値 | 説明 |
|------|--------|------|
| 標準フォーマットを上書き | `1` ～ `10` | .npy, .png などを独自実装で置き換え |
| 新フォーマット追加 | `0` | 既存動作に影響なし（デフォルト） |
| 実験的なローダー | `-1` ～ `-10` | 他のローダー失敗時のみ試行 |
| ワイルドカードフォールバック | `-100` | 最後の手段 |

## 実装パターン

### パターン1: 単一フォーマット専用

```python
def my_format_loader(path: str) -> Optional[np.ndarray]:
    if not path.endswith('.myext'):
        return None
    # ... 読み込み処理 ...

ImageLoaderRegistry.get_instance().register(
    my_format_loader,
    extensions=['.myext'],
    priority=10
)
```

### パターン2: 複数フォーマット対応

```python
def multi_format_loader(path: str) -> Optional[np.ndarray]:
    ext = Path(path).suffix.lower()
    
    if ext == '.format1':
        return load_format1(path)
    elif ext == '.format2':
        return load_format2(path)
    else:
        return None

ImageLoaderRegistry.get_instance().register(
    multi_format_loader,
    extensions=['.format1', '.format2'],
    priority=10
)
```

### パターン3: ヘッダー付きフォーマット

```python
def header_based_loader(path: str) -> Optional[np.ndarray]:
    try:
        with open(path, 'rb') as f:
            # ヘッダーを読む（例: 最初の12バイト）
            magic = f.read(4)
            width = int.from_bytes(f.read(4), 'little')
            height = int.from_bytes(f.read(4), 'little')
            
            # マジックナンバーをチェック
            if magic != b'MYIM':
                return None
            
            # 画像データを読む
            data = np.fromfile(f, dtype=np.uint8)
            img = data.reshape((height, width))
            return img
            
    except Exception:
        return None
```

### パターン4: マルチフレーム（4次元配列）

**4次元配列 (H, W, C, N) のファイルを扱う場合:**

```python
def multiframe_loader(path: str) -> Optional[np.ndarray]:
    """4D array (H, W, C, N) の最初のフレームを返す
    
    制限: 現在のViewerは1ファイル=1画像の設計のため、
    すべてのフレームを自動展開することはできません。
    
    回避策:
    1. 最初のフレームのみ表示（このサンプル）
    2. 手動で各フレームを別ファイルに保存
    3. 仮想パスを使った高度な実装（後述）
    """
    if not path.endswith('.npy'):
        return None
    
    try:
        data = np.load(path)
        
        # 4次元配列のみ処理
        if data.ndim != 4:
            return None  # 標準ローダーに任せる
        
        H, W, C, N = data.shape
        
        if C not in [1, 2, 3, 4]:
            return None
        
        # 最初のフレームを返す
        print(f"4D array loaded: {data.shape}, showing frame 0/{N-1}")
        return data[:, :, :, 0]
        
    except Exception:
        return None

# 登録（標準.npyローダーを上書き）
ImageLoaderRegistry.get_instance().register(
    multiframe_loader,
    extensions=['.npy'],
    priority=1
)
```

**すべてのフレームをロードする方法:**

```bash
# Python スクリプトで事前に展開
import numpy as np

data = np.load('multiframe.npy')  # shape: (H, W, C, N)
for i in range(data.shape[3]):
    np.save(f'frame_{i:03d}.npy', data[:, :, :, i])
```

その後、Viewerで`frame_000.npy`, `frame_001.npy`, ...を開く。

**詳細な実装例は `_example_multiframe_loader.py` を参照してください。**
            img = data.reshape((height, width))
            return img
            
    except Exception:
        return None
```

## デバッグ

### ローダーが呼ばれているか確認

```python
def my_loader(path: str) -> Optional[np.ndarray]:
    print(f"DEBUG: my_loader called with {path}")  # デバッグ出力
    
    if not path.endswith('.myext'):
        print("DEBUG: Extension mismatch")
        return None
    
    try:
        data = load_data(path)
        print(f"DEBUG: Loaded shape={data.shape}, dtype={data.dtype}")
        return data
    except Exception as e:
        print(f"DEBUG: Error - {e}")
        return None
```

### よくある問題

1. **ローダーが呼ばれない**
   - ファイル名が `_` で始まっていないか確認
   - `__init__.py` に読み込みコードがあるか確認
   - 拡張子が正しく登録されているか確認

2. **画像が表示されない**
   - 配列の形状を確認: `print(arr.shape)`
   - データ型を確認: `print(arr.dtype)`
   - 値の範囲を確認: `print(arr.min(), arr.max())`

3. **エラーメッセージ**
   - エラーダイアログに表示されるメッセージを確認
   - コンソール出力を確認

## ベストプラクティス

1. **エラーハンドリング**
   - 常に try-except でラップ
   - 処理できないファイルは `None` を返す

2. **パフォーマンス**
   - 拡張子チェックは最初に行う（高速）
   - ファイルを開く前に可能な限りフィルタリング

3. **互換性**
   - 標準ライブラリを優先
   - 外部ライブラリは `try-except` でインポート

4. **ドキュメント**
   - ローダー関数に docstring を書く
   - サポートするフォーマットを明記

## ファイルの無効化

カスタムローダーを一時的に無効にするには：

1. **ファイル名を変更**: `my_loader.py` → `_my_loader.py`
2. **または削除**: ファイルを削除する
3. **アプリを再起動**

## トラブルシューティング

### Q: ローダーが登録されない

A: 以下を確認してください：
- ファイルが `custom_loaders/` ディレクトリにあるか
- ファイル名が `_` で始まっていないか
- Python構文エラーがないか

### Q: ファイルダイアログに拡張子が表示されない

A: `registry.register()` の `extensions` パラメータを確認してください。

### Q: エラーメッセージ「カスタムローダーで処理できませんでした」

A: ローダー関数が `None` を返しています。以下を確認：
- 拡張子が正しいか
- ファイル形式が想定通りか
- デバッグ出力を追加して原因を特定

## 参考

- サンプルコード: `_example_loader.py`
- API ドキュメント: `PixelScopeViewer/core/image_io.py`
- メイン README: `../README.md`
