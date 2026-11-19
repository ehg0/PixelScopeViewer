"""histogram tab と profile tab で共通の部品（plot・統計量の table・右側の group）。"""

from collections.abc import Callable

import numpy as np
import pyqtgraph as pg
from pyqtgraph import PlotWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.ui.analysis.tabs.channel_list import ChannelListWidget, RoiChannelPanel
from PixelScopeViewer.ui.common import theme

STATS_HEADERS = ["ch", "Mean", "Std", "Median", "Min", "Max", "Fano"]

ROI_MODES = (("active", "編集中ROI"), ("overlay", "登録ROI - Overlay"), ("split", "登録ROI - Split"))
ROI_SPLIT_COLUMN_CHOICES = (1, 2, 3, 4, 5, 6)
ROI_SPLIT_UNITS = (("roi", "ROIごと"), ("tile", "タイルごと"))


def style_plot_item(plot_item: pg.PlotItem, left_label: str, bottom_label: str):
    """軸の label・色と grid を設定し、mouse による拡大縮小を無効にする。"""
    plot_item.setLabel("left", left_label)
    plot_item.setLabel("bottom", bottom_label)
    plot_item.showGrid(x=True, y=True, alpha=0.4)
    for axis in ("left", "bottom"):
        plot_item.getAxis(axis).setPen(pg.mkPen(color=theme.PLOT_AXIS_COLOR, width=1))
        plot_item.getAxis(axis).setTextPen(pg.mkPen(color=theme.PLOT_TEXT_COLOR))
    plot_item.setMenuEnabled(True)
    plot_item.getViewBox().setMouseEnabled(x=False, y=False)


def create_plot_widget(
    left_label: str,
    bottom_label: str,
    on_save_viewbox_state: Callable[[object], None] | None,
    on_connect_plot_controls: Callable[[object], None] | None,
    on_mouse_moved: Callable[[object], None],
) -> PlotWidget:
    """白背景・grid 付きで、mouse による拡大縮小を無効にした PlotWidget を作る。"""
    widget = PlotWidget()
    widget.setBackground(theme.PLOT_BACKGROUND)
    style_plot_item(widget.getPlotItem(), left_label, bottom_label)
    view_box = widget.getViewBox()
    if on_save_viewbox_state is not None:
        view_box.sigStateChanged.connect(on_save_viewbox_state)
        on_save_viewbox_state(view_box)
    if on_connect_plot_controls is not None:
        on_connect_plot_controls(widget.getPlotItem())
    widget.scene().sigMouseMoved.connect(on_mouse_moved)
    return widget


def mouse_position_text(plot_item: pg.PlotItem, pos) -> str:
    """scene 座標 pos の plot 上の値を "X: .., Y: .." で返す。plot の外なら空文字。"""
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


def create_roi_group() -> tuple[QGroupBox, QComboBox, QCheckBox, QComboBox, QComboBox]:
    """解析対象の ROI を選ぶ group を作る。

    Returns:
        (group, ROI の表示方法（編集中ROI / 登録ROI の Overlay・Split）の combo, 軸の連動の checkbox,
        Split の列数の combo, タイル比較モードの Split の単位の combo)。
    """
    group, layout = make_group_box("ROI")
    combo = QComboBox()
    for mode, text in ROI_MODES:
        combo.addItem(text, mode)
    combo.setToolTip("登録ROIはメイン画面の Info > ROI List で ☑ を付けた ROI です")
    combo.setMinimumWidth(100)
    link_check = QCheckBox("軸を連動")
    link_check.setToolTip(
        "Split 表示で、全グラフの表示範囲を揃えます。OFF にすると各グラフの右クリックで個別に設定できます"
    )
    columns_combo = QComboBox()
    for n in ROI_SPLIT_COLUMN_CHOICES:
        columns_combo.addItem(f"{n}列", n)
    columns_combo.setToolTip("Split 表示で横に並べるグラフの数")
    unit_combo = QComboBox()
    for unit, text in ROI_SPLIT_UNITS:
        unit_combo.addItem(text, unit)
    unit_combo.setToolTip("タイル比較モードで、ROI ごとのグラフに全タイルを重ねるか、タイルごとのグラフに並べるか")
    unit_combo.setVisible(False)
    # dialog の高さを増やさないよう、軸の連動と同じ行に置く
    split_row = QHBoxLayout()
    split_row.addWidget(link_check)
    split_row.addStretch()
    split_row.addWidget(unit_combo)
    split_row.addWidget(columns_combo)
    layout.addWidget(combo)
    layout.addLayout(split_row)
    return group, combo, link_check, columns_combo, unit_combo


def create_channel_group(
    on_checks_changed: Callable[[list], None],
) -> tuple[QGroupBox, QScrollArea, ChannelListWidget, RoiChannelPanel]:
    """scroll area の中に ChannelListWidget と登録 ROI 用の RoiChannelPanel（初期は非表示）を置いた group を作る。

    Returns:
        (group, scroll area, ChannelListWidget, RoiChannelPanel)。
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
    roi_panel = RoiChannelPanel()
    roi_panel.setVisible(False)
    scroll_layout.addWidget(roi_panel)
    scroll_layout.addStretch()
    scroll.setWidget(scroll_widget)
    layout.addWidget(scroll)
    return group, scroll, channel_list, roi_panel


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
