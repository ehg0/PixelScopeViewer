"""brightness の計算と dtype ごとの初期設定（Qt 非依存）。"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from PixelScopeViewer.core.constants import get_dtype_defaults


@dataclass
class BrightnessParams:
    """brightness の offset・gain・upper level。"""

    offset: float
    gain: float
    upper_level: float

    @classmethod
    def for_dtype(cls, dtype_key: str) -> "BrightnessParams":
        """dtype の初期設定から作る。"""
        d = get_dtype_defaults(dtype_key)
        return cls(d["initial_offset"], d["initial_gain"], d["initial_upper_level"])


def apply_brightness_adjustment(arr: np.ndarray, offset: float, gain: float, upper_level: float) -> np.ndarray:
    """画像配列に brightness 調整を適用する。

    変換式: gain * (x - offset) / (upper_level - offset) * 255

    Args:
        arr: 画像配列（dtype は任意）。
        offset: 黒レベル（負の値も可）。
        gain: 増幅率。
        upper_level: 白レベル。

    Returns:
        [0, 255] に clip した uint8 の配列。upper_level が 0 の場合は arr をそのまま返す。
        upper_level と offset が等しい場合（一様な領域の auto scale など）は、幅を 1 として計算する。
    """
    # 0 除算を避ける
    if upper_level == 0:
        return arr

    span = upper_level - offset
    if span == 0:
        span = 1
    adjusted = gain * (arr.astype(np.float32) - offset) / span * 255

    return np.clip(adjusted, 0, 255).astype(np.uint8)


def autoscale_range(
    arr: np.ndarray,
    roi: tuple[int, int, int, int] | None = None,
    channel_checks: Sequence[bool] | None = None,
) -> tuple[float, float] | None:
    """auto scale の (最小値, 最大値) を返す。計算できない場合は None。

    Args:
        arr: 画像配列。
        roi: 画像座標の (x, y, w, h)。None の場合は画像全体。画像の範囲内の部分だけを使う。
        channel_checks: 3 次元配列で使う channel の表示 ON/OFF。None の場合は全 channel。

    Returns:
        ROI が画像の範囲外・表示 ON の channel がない・有限の値がない場合は None。
    """
    data = arr
    if roi is not None:
        x, y, w, h = (int(v) for v in roi)
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(arr.shape[1], x + w), min(arr.shape[0], y + h)
        if x1 <= x0 or y1 <= y0:
            return None
        data = data[y0:y1, x0:x1]
    if data.ndim == 3 and channel_checks is not None:
        indices = [i for i, checked in enumerate(channel_checks) if checked and i < data.shape[2]]
        if not indices:
            return None
        data = data[..., indices]
    if np.issubdtype(data.dtype, np.floating):
        data = data[np.isfinite(data)]
    if data.size == 0:
        return None
    return float(np.min(data)), float(np.max(data))


def merged_dtype_defaults(dtype_keys: Sequence[str]) -> dict:
    """複数の dtype の入力範囲をすべて含む brightness の設定を返す。

    初期値は先頭の dtype のものにする。小数の入力は、どれかが float なら有効にする。

    Args:
        dtype_keys: get_dtype_defaults の key（'float', 'uint8', 'uint16'）。空の場合は uint8 とみなす。
    """
    all_defaults = [get_dtype_defaults(k) for k in dtype_keys] or [get_dtype_defaults("uint8")]
    result = dict(all_defaults[0])
    result["is_float_type"] = any(d["is_float_type"] for d in all_defaults)
    for key in ("offset_range", "upper_level_range"):
        result[key] = (min(d[key][0] for d in all_defaults), max(d[key][1] for d in all_defaults))
    return result


def determine_dtype_defaults(image_array=None, image_path=None):
    """画像の dtype に応じた brightness の初期設定を返す。

    Returns:
        float の画像は "float"、それ以外は "uint8" の get_dtype_defaults の戻り値。
    """
    if image_array is None:
        return get_dtype_defaults("uint8")

    dtype = "float" if np.issubdtype(image_array.dtype, np.floating) else "uint8"
    return get_dtype_defaults(dtype)


def determine_dtype_group(arr: np.ndarray) -> str:
    """brightness の設定を共有する dtype の group（'uint8', 'uint16', 'float'）を返す。"""
    if np.issubdtype(arr.dtype, np.floating):
        return "float"
    if np.issubdtype(arr.dtype, np.integer) and np.iinfo(arr.dtype).max > 255:
        return "uint16"
    return "uint8"
