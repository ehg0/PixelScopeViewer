"""表示用・thumbnail 用の配列を作る（Qt 非依存）。"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

from PixelScopeViewer.core.colormap import apply_jet_colormap, flow_to_hsv_rgb

# brightness を適用して uint8 の配列を返す関数
AdjustFn = Callable[[np.ndarray], np.ndarray]


def compose_channels(arr: np.ndarray, checks: Sequence[bool], colors_rgb: Sequence[tuple[int, int, int]]) -> np.ndarray:
    """表示 ON の channel を、それぞれの色で加算合成した RGB の uint8 配列を返す。

    各 channel は dtype に応じて [0, 1] に正規化する（uint8 は /255、float は clip、その他の整数は /最大値）。
    """
    h, w = arr.shape[:2]
    composite = np.zeros((h, w, 3), dtype=np.float32)
    for idx, checked in enumerate(checks):
        if not checked or idx >= len(colors_rgb):
            continue
        channel = arr[:, :, idx].astype(np.float32)
        if arr.dtype == np.uint8:
            channel /= 255.0
        elif np.issubdtype(arr.dtype, np.floating):
            channel = np.clip(channel, 0, 1)
        elif np.issubdtype(arr.dtype, np.integer):
            channel /= np.iinfo(arr.dtype).max
        r, g, b = (c / 255.0 for c in colors_rgb[idx])
        composite[:, :, 0] += channel * r
        composite[:, :, 1] += channel * g
        composite[:, :, 2] += channel * b
    return (np.clip(composite, 0, 1) * 255).astype(np.uint8)


def _is_1ch(arr: np.ndarray) -> bool:
    return arr.ndim == 2 or (arr.ndim == 3 and arr.shape[2] == 1)


def _is_2ch(arr: np.ndarray) -> bool:
    return arr.ndim == 3 and arr.shape[2] == 2


def _squeeze_1ch(arr: np.ndarray) -> np.ndarray:
    return arr[..., 0] if arr.ndim == 3 else arr


def render_display(
    arr: np.ndarray,
    adjust: AdjustFn,
    *,
    brightness_changed: bool,
    jet: bool,
    flow_hsv: bool,
    checks: Sequence[bool],
    colors_rgb: Sequence[tuple[int, int, int]],
) -> np.ndarray:
    """メイン表示用の配列を返す。

    Args:
        arr: 元の画像配列。
        adjust: brightness を適用して uint8 を返す関数。
        brightness_changed: brightness が初期値から変わっているか。float の画像は常に適用する。
        jet: 1ch を JET で表示するか。
        flow_hsv: 2ch を flow-hsv で表示するか。
        checks: channel の表示 ON/OFF。空の場合は合成しない。
        colors_rgb: channel の色。
    """
    if _is_1ch(arr) and jet:
        return apply_jet_colormap(_squeeze_1ch(adjust(arr)))
    if _is_2ch(arr) and flow_hsv:
        return flow_to_hsv_rgb(arr)

    if brightness_changed or np.issubdtype(arr.dtype, np.floating):
        arr = adjust(arr)
    if arr.ndim >= 3 and checks:
        return compose_channels(arr, checks, colors_rgb)
    return arr


def render_thumbnail(
    arr: np.ndarray,
    adjust: AdjustFn,
    *,
    jet: bool,
    flow_hsv: bool,
    checks: Sequence[bool],
    colors_rgb: Sequence[tuple[int, int, int]],
) -> np.ndarray:
    """thumbnail 用の配列を返す。

    1ch と 2ch（合成）は brightness を常に適用し、表示モードに合わせる。3ch 以上は元の配列のまま返す。
    """
    if _is_1ch(arr):
        adj = _squeeze_1ch(adjust(arr))
        return apply_jet_colormap(adj) if jet else adj
    if _is_2ch(arr):
        # flow-hsv は brightness を適用せず元データから変換する
        return flow_to_hsv_rgb(arr) if flow_hsv else compose_channels(adjust(arr), checks, colors_rgb)
    return arr
