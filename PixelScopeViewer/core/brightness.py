"""brightness の計算と dtype ごとの初期設定（Qt 非依存）。"""

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
    """
    # 0 除算を避ける
    if upper_level == 0:
        return arr

    adjusted = gain * (arr.astype(np.float32) - offset) / (upper_level - offset) * 255

    return np.clip(adjusted, 0, 255).astype(np.uint8)


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
