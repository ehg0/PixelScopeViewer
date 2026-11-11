"""viewer の brightness・channel 表示設定で、表示用の画像と thumbnail を作る。"""

from collections.abc import Hashable

import numpy as np
from PySide6.QtGui import QPixmap

from PixelScopeViewer.core.brightness import BrightnessParams, apply_brightness_adjustment
from PixelScopeViewer.core.render import render_display, render_thumbnail
from PixelScopeViewer.ui.common import defaults
from PixelScopeViewer.ui.common.channel_display import MODE_1CH_JET, MODE_2CH_FLOW_HSV, ChannelDisplay
from PixelScopeViewer.ui.common.qt_image import numpy_to_qimage
from PixelScopeViewer.ui.viewer.display_cache import DisplayCache
from PixelScopeViewer.ui.viewer.state import ViewerState


class DisplayRenderer:
    """brightness（state.brightness_by_dtype の画像に対応する値）と channel の表示設定を画像に適用する。

    表示用の QPixmap は画像 id ごとに cache し、表示設定が同じなら作り直さない。
    """

    def __init__(self, state: ViewerState, channel_display: ChannelDisplay):
        self._state = state
        self._channel_display = channel_display
        self.cache = DisplayCache(defaults.TILE_DISPLAY_CACHE_MB)

    def _params(self, arr: np.ndarray) -> BrightnessParams:
        return self._state.brightness_by_dtype[self._state.brightness_key(arr)]

    def _options(self, arr: np.ndarray) -> dict:
        """表示モードと、arr の channel 数に対応する channel の表示 ON/OFF・色を返す。"""
        n = arr.shape[2] if arr.ndim >= 3 else 0
        d = self._channel_display
        return {
            "jet": d.mode_1ch == MODE_1CH_JET,
            "flow_hsv": d.mode_2ch == MODE_2CH_FLOW_HSV,
            "checks": d.checks(n),
            "colors_rgb": [c.getRgb()[:3] for c in d.colors(n)],
        }

    @staticmethod
    def _adjust(b: BrightnessParams):
        return lambda a: apply_brightness_adjustment(a, b.offset, b.gain, b.upper_level)

    def _render(self, arr: np.ndarray, b: BrightnessParams, opts: dict) -> np.ndarray:
        return render_display(
            arr,
            self._adjust(b),
            brightness_changed=(b.offset, b.gain, b.upper_level) != (0, 1.0, 255),
            **opts,
        )

    def array(self, arr: np.ndarray) -> np.ndarray:
        """表示用の配列を返す（cache しない）。"""
        return self._render(arr, self._params(arr), self._options(arr))

    def pixmap(self, img: dict) -> QPixmap:
        """画像の dict の表示用 QPixmap を返す。表示設定が同じなら cache を使う。"""
        arr = img["array"]
        b = self._params(arr)
        opts = self._options(arr)
        key: Hashable = (
            b.offset,
            b.gain,
            b.upper_level,
            opts["jet"],
            opts["flow_hsv"],
            tuple(opts["checks"]),
            tuple(tuple(c) for c in opts["colors_rgb"]),
        )
        pixmap = self.cache.get(img["id"], key)
        if pixmap is None:
            pixmap = QPixmap.fromImage(numpy_to_qimage(self._render(arr, b, opts)))
            self.cache.put(img["id"], key, pixmap)
        return pixmap

    def thumbnail_array(self, arr: np.ndarray) -> np.ndarray:
        """今の 1ch/2ch 表示モードに合わせた thumbnail 用の配列を返す。"""
        return render_thumbnail(arr, self._adjust(self._params(arr)), **self._options(arr))
