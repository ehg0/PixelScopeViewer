"""複数画像比較の共通処理。"""

import numpy as np


def determine_dtype_group(arr: np.ndarray) -> str:
    """brightness の設定を共有する dtype の group（'uint8', 'uint16', 'float'）を返す。"""
    dtype = arr.dtype

    if np.issubdtype(dtype, np.floating):
        return "float"
    elif np.issubdtype(dtype, np.integer):
        try:
            max_val = np.iinfo(dtype).max
            if max_val <= 255:
                return "uint8"
            else:
                return "uint16"
        except Exception:
            return "uint8"
    else:
        return "uint8"
