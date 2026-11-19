"""pixel 値の表示用の文字列（Qt 非依存）。"""

import numpy as np


def _format_scalar(x, dtype) -> str:
    if np.issubdtype(dtype, np.floating):
        return f"{float(x):.3f}"
    # 整数と bool は整数で表示する（complex などはそのまま）
    return str(int(x)) if np.issubdtype(dtype, np.integer) or dtype == np.bool_ else str(x)


def pixel_value_text(arr: np.ndarray, ix: int, iy: int) -> str | None:
    """画像座標 (ix, iy) の pixel 値の表示用の文字列を返す。画像の範囲外の場合は None。

    複数 channel の場合は "(v0,v1,...)" にする。
    """
    h, w = arr.shape[:2]
    if not (0 <= iy < h and 0 <= ix < w):
        return None
    v = arr[iy, ix]
    if np.ndim(v) == 0:
        return _format_scalar(v, arr.dtype)
    return "(" + ",".join(_format_scalar(x, arr.dtype) for x in np.ravel(v)) + ")"
