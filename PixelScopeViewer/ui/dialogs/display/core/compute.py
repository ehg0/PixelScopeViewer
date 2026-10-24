"""brightness の計算（Qt 非依存）。"""

import numpy as np


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
