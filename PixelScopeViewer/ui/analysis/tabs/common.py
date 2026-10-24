"""histogram tab と profile tab で共通の部品（plot・統計量の table・右側の group）。"""

from collections.abc import Callable

import numpy as np
import pyqtgraph as pg
from pyqtgraph import PlotWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHeaderView,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.ui.analysis.tabs.channel_list import ChannelListWidget
from PixelScopeViewer.ui.common import theme

STATS_HEADERS = ["ch", "Mean", "Std", "Median", "Min", "Max", "Fano"]


def create_plot_widget(
    left_label: str,
    bottom_label: str,
    on_save_viewbox_state: Callable[[object], None] | None,
    on_connect_plot_controls: Callable[[object], None] | None,
    on_mouse_moved: Callable[[object], None],
) -> PlotWidget:
    """白背景・grid 付きで、mouse による拡大縮小を無効にした PlotWidget を作る。"""
    widget = PlotWidget()
    widget.setLabel("left", left_label)
    widget.setLabel("bottom", bottom_label)
    widget.setBackground(theme.PLOT_BACKGROUND)
    widget.showGrid(x=True, y=True, alpha=0.4)
    for axis in ("left", "bottom"):
        widget.getAxis(axis).setPen(pg.mkPen(color=theme.PLOT_AXIS_COLOR, width=1))
        widget.getAxis(axis).setTextPen(pg.mkPen(color=theme.PLOT_TEXT_COLOR))
    widget.setMenuEnabled(True)
    view_box = widget.getViewBox()
    view_box.setMouseEnabled(x=False, y=False)
    if on_save_viewbox_state is not None:
        view_box.sigStateChanged.connect(on_save_viewbox_state)
        on_save_viewbox_state(view_box)
    if on_connect_plot_controls is not None:
        on_connect_plot_controls(widget.getPlotItem())
    widget.scene().sigMouseMoved.connect(on_mouse_moved)
    return widget


def mouse_position_text(widget: PlotWidget, pos) -> str:
    """scene 座標 pos の plot 上の値を "X: .., Y: .." で返す。plot の外なら空文字。"""
    plot_item = widget.getPlotItem()
    if not plot_item.sceneBoundingRect().contains(pos):
        return ""
    point = plot_item.vb.mapSceneToView(pos)
    x_val, y_val = point.x(), point.y()
    # log 表示の場合は元の値に戻す
    log_x, log_y = plot_item.vb.getState().get("logMode", [False, False])
    if log_x:
        x_val = 10**x_val
    if log_y:
        y_val = 10**y_val
    return f"X: {x_val:.2f}, Y: {y_val:.2f}"


def label_color(label: str, color_by_label: dict[str, tuple[int, int, int]], alpha: int = 255) -> QColor:
    """curve label の色を返す。見つからない場合は PLOT_MUTED_COLOR。"""
    rgb = color_by_label.get(label)
    color = QColor(*rgb) if rgb else QColor(theme.PLOT_MUTED_COLOR)
    color.setAlpha(alpha)
    return color


def make_group_box(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    group = QGroupBox(title)
    group.setStyleSheet(theme.GROUP_BOX_STYLESHEET)
    layout = QVBoxLayout(group)
    layout.setContentsMargins(8, 5, 8, 8)
    return group, layout


def create_channel_group(on_checks_changed: Callable[[list], None]) -> tuple[QGroupBox, ChannelListWidget]:
    """scroll area の中に ChannelListWidget を置いた Channels group を作る。

    複数画像比較の解析 dialog は scroll area の中身を tile ごとの一覧に置き換えるため、この構造を保つ。
    """
    group, layout = make_group_box("Channels")
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setMinimumHeight(120)  # 4 channel までは scroll なしで表示する
    scroll.setMaximumHeight(300)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll_widget = QWidget()
    scroll_layout = QVBoxLayout(scroll_widget)
    scroll_layout.setContentsMargins(2, 2, 2, 2)
    scroll_layout.setSpacing(3)
    channel_list = ChannelListWidget()
    channel_list.checks_changed.connect(on_checks_changed)
    scroll_layout.addWidget(channel_list)
    scroll_layout.addStretch()
    scroll.setWidget(scroll_widget)
    layout.addWidget(scroll)
    return group, channel_list


def create_export_group() -> tuple[QGroupBox, QPushButton, QPushButton, QCheckBox]:
    """Copy data・Copy stats の button と「Target: All plane」の checkbox を持つ Export group を作る。"""
    group, layout = make_group_box("Export")
    copy_btn = QPushButton("Copy data")
    copy_stats_btn = QPushButton("Copy stats")
    all_plane = QCheckBox("Target: All plane")
    for w in (copy_btn, copy_stats_btn, all_plane):
        w.setMinimumWidth(100)
        layout.addWidget(w)
    return group, copy_btn, copy_stats_btn, all_plane


class StatsTable(QTableWidget):
    """channel ごとの統計量（mean, std, median, min, max, fano）の table。

    Args:
        int_format: 整数 dtype の行の median・min・max・fano を整数で表示するか。
    """

    def __init__(self, int_format: bool, parent=None):
        super().__init__(0, len(STATS_HEADERS), parent)
        self._int_format = int_format
        self.setHorizontalHeaderLabels(STATS_HEADERS)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionMode(QTableWidget.ExtendedSelection)
        self.setSelectionBehavior(QTableWidget.SelectItems)
        # 行が多い場合は切り詰めずに scroll させる
        self.setMaximumHeight(240)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        ch_w = 120
        other_w = max(60, (600 - ch_w) // (len(STATS_HEADERS) - 1))
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.setColumnWidth(0, ch_w)
        for c in range(1, len(STATS_HEADERS)):
            self.setColumnWidth(c, other_w)
        self.setFixedWidth(ch_w + other_w * (len(STATS_HEADERS) - 1) + 2)
        self.setStyleSheet("QTableWidget { font-size: 10pt; }")
        self.verticalHeader().setVisible(False)

    def set_rows(self, rows: list[dict], color_by_label: dict[str, tuple[int, int, int]]):
        """統計量の行を表示する。ch 列には curve_label の色見本を付ける。

        Args:
            rows: histogram_stats / profile_stats の戻り値。
            color_by_label: curve_label から RGB への dict。
        """
        self.setRowCount(len(rows))
        for row_idx, r in enumerate(rows):
            texts = [r["ch"], f"{r['mean']:.4f}", f"{r['std']:.4f}"]
            texts += [self._format(r[key], r["is_int"]) for key in ("median", "min", "max", "fano")]
            for col, text in enumerate(texts):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row_idx, col, item)
            rgb = color_by_label.get(r.get("curve_label"))
            if rgb:
                pix = QPixmap(12, 12)
                pix.fill(QColor(*rgb))
                self.item(row_idx, 0).setData(Qt.DecorationRole, pix)

    def _format(self, value, is_int: bool) -> str:
        # NaN（平均 0 の fano など）は整数にできないため小数の表記にする
        if self._int_format and is_int and np.isfinite(value):
            return f"{int(value)}"
        return f"{value:.4f}"
