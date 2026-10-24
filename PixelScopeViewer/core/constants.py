"""アプリケーション全体で共有する定数。"""

# 標準 loader が対応する拡張子
OIIO_EXTENSIONS: tuple[str, ...] = (".exr", ".hdr")
OPENCV_EXTENSIONS: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp")
STANDARD_IMAGE_EXTENSIONS: tuple[str, ...] = (*OPENCV_EXTENSIONS, *OIIO_EXTENSIONS, ".npy", ".bin")

# zoom 倍率の範囲と、1 操作あたりの倍率
MIN_ZOOM_SCALE: float = 1.0 / 32.0
MAX_ZOOM_SCALE: float = 32.0
ZOOM_STEP: float = 2.0

# brightness gain の範囲と、1 操作あたりの倍率
MIN_BRIGHTNESS_GAIN: float = 1.0 / 128.0
MAX_BRIGHTNESS_GAIN: float = 128.0
GAIN_STEP: float = 2.0


# dtype ごとの brightness 初期値と入力範囲
DTYPE_DEFAULTS = {
    "float": {
        "dtype_key": "float",
        "is_float_type": True,
        "initial_offset": 0.0,
        "initial_gain": 1.0,
        "initial_upper_level": 1.0,
        "offset_range": (0.0, 1e5),
        "upper_level_range": (0.0, 1e5),
    },
    "uint8": {
        "dtype_key": "uint8",
        "is_float_type": False,
        "initial_offset": 0,
        "initial_gain": 1.0,
        "initial_upper_level": 255,
        "offset_range": (-255, 255),
        "upper_level_range": (0, 255),
    },
    "uint16": {
        "dtype_key": "uint16",
        "is_float_type": False,
        "initial_offset": 0,
        "initial_gain": 1.0,
        "initial_upper_level": 1023,
        "offset_range": (-32768, 32768),
        "upper_level_range": (1, 65535),
    },
}


def get_dtype_defaults(dtype_key: str) -> dict:
    """dtype の brightness 初期設定を返す。該当しない dtype は uint8 の設定を返す。"""
    return DTYPE_DEFAULTS.get(dtype_key, DTYPE_DEFAULTS["uint8"]).copy()
