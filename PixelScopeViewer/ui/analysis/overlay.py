"""重ね描きの曲線の色（複数画像比較の tile と、解析 dialog の登録 ROI で共通）。"""

from PySide6.QtGui import QColor

from PixelScopeViewer.ui.common import theme
from PixelScopeViewer.ui.common.channel_display import to_plot_color


def overlay_color(group_num: int, ch_index: int, overrides: dict[str, str], label: str) -> QColor:
    """重ね描きの曲線の色を返す。

    個別設定があればそのまま、なければ group 番号（1 始まり）と channel から決まる theme.OVERLAY_PALETTE の色
    （灰色系は黒）を使う。

    Args:
        group_num: tile 番号や ROI の id（1 始まり）。
        ch_index: channel の index。
        overrides: curve label から hex 文字列への個別設定。
        label: 個別設定を探す curve label。
    """
    if label in overrides:
        return QColor(overrides[label])
    idx = ((group_num - 1) * 8 + ch_index) % len(theme.OVERLAY_PALETTE)
    return to_plot_color(QColor(theme.OVERLAY_PALETTE[idx]))


def roi_curve_label(roi_id: int, ch_index: int) -> str:
    """登録 ROI の曲線の label（R{id} C{k}）を返す。1ch も C0 にする。"""
    return f"R{roi_id} C{ch_index}"


def roi_color(roi_id: int, ch_index: int, overrides: dict[str, str]) -> QColor:
    """登録 ROI の曲線の色を返す。画像上の ROI の枠は C0 の色にする。"""
    return overlay_color(roi_id, ch_index, overrides, roi_curve_label(roi_id, ch_index))
