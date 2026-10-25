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
# Split のグラフの title。グラフが小さくなるため、編集中ROI・Overlay（12pt）より小さくする
SPLIT_TITLE_SIZE = "9pt"


def _style_plot_item(plot_item: pg.PlotItem, left_label: str, bottom_label: str):
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
    _style_plot_item(widget.getPlotItem(), left_label, bottom_label)
    view_box = widget.getViewBox()
    if on_save_viewbox_state is not None:
        view_box.sigStateChanged.connect(on_save_viewbox_state)
        on_save_viewbox_state(view_box)
    if on_connect_plot_controls is not None:
        on_connect_plot_controls(widget.getPlotItem())
    widget.scene().sigMouseMoved.connect(on_mouse_moved)
    return widget


class SplitPlotArea(pg.GraphicsLayoutWidget):
    """登録 ROI ごとの PlotItem を grid に並べる。

    PlotItem は ROI の id ごとに使い回し、ユーザーが設定した表示範囲を保つ。
    grid・log は source（編集中ROI・Overlay 用の PlotItem）の menu の設定に揃え、
    各 PlotItem の menu での変更は source に伝える。

    Args:
        source: grid・log の設定を共有する PlotItem。
        left_label: 縦軸の label。
        bottom_label: 横軸の label。
        on_status: マウス位置の値の文字列を受け取る callback。
    """

    _CTRL_CHECKS = ("xGridCheck", "yGridCheck", "logXCheck", "logYCheck")

    def __init__(self, source: pg.PlotItem, left_label: str, bottom_label: str, on_status: Callable[[str], None]):
        super().__init__()
        self.setBackground(theme.PLOT_BACKGROUND)
        self._source = source
        self._labels = (left_label, bottom_label)
        self._items: dict[int, pg.PlotItem] = {}
        self._order: list[int] = []
        self._n_cols = 0
        # None は軸の連動を設定し直す必要がある状態
        self._linked: bool | None = None
        self.scene().sigMouseMoved.connect(lambda pos: on_status(self._mouse_text(pos)))

    def plot_items(self, ids: list[int], n_cols: int) -> list[pg.PlotItem]:
        """ids の順に PlotItem を返す。

        ROI の増減か列数の変更があったときだけ、PlotItem を追加・削除して n_cols 列に並べ直す。
        """
        if ids != self._order or n_cols != self._n_cols:
            for item in list(self.ci.items):
                self.ci.removeItem(item)
            for roi_id in [r for r in self._items if r not in ids]:
                del self._items[roi_id]
            for n, roi_id in enumerate(ids):
                if roi_id not in self._items:
                    self._items[roi_id] = self._make_item()
                self.ci.addItem(self._items[roi_id], row=n // n_cols, col=n % n_cols)
            self._order = list(ids)
            self._n_cols = n_cols
            self._linked = None
        self.sync_controls()
        return [self._items[r] for r in ids]

    def _make_item(self) -> pg.PlotItem:
        item = pg.PlotItem()
        _style_plot_item(item, *self._labels)
        for name in self._CTRL_CHECKS:
            getattr(item.ctrl, name).toggled.connect(
                lambda checked, n=name: getattr(self._source.ctrl, n).setChecked(checked)
            )
        return item

    def sync_controls(self):
        """各 PlotItem の grid・log を source に揃える。"""
        for item in self._items.values():
            for name in self._CTRL_CHECKS:
                getattr(item.ctrl, name).setChecked(getattr(self._source.ctrl, name).isChecked())

    def set_linked(self, linked: bool, series: list[tuple[np.ndarray, np.ndarray]]):
        """軸の連動を設定する。描画の後に呼ぶ。

        連動中は先頭の PlotItem の auto range に全 ROI のデータが収まるよう、
        全データの範囲を覆う透明な線を先頭の PlotItem に加える。
        連動を切り替えたときは auto range を有効に戻す。連動中は先頭の PlotItem だけを auto range にする。
        """
        items = [self._items[r] for r in self._order]
        if not items:
            return
        first = items[0]
        if linked != self._linked:
            first.setXLink(None)
            first.setYLink(None)
            for item in items[1:]:
                item.setXLink(first if linked else None)
                item.setYLink(first if linked else None)
                # 連動先の auto range は自身のデータだけに合わせ、先頭の範囲を上書きしてしまう
                if linked:
                    item.disableAutoRange()
                else:
                    item.enableAutoRange()
            first.enableAutoRange()
            self._linked = linked
        if linked and len(items) > 1:
            bounds = self._data_bounds(series)
            if bounds is not None:
                x0, x1, y0, y1 = bounds
                first.addItem(pg.PlotDataItem([x0, x1], [y0, y1], pen=pg.mkPen((0, 0, 0, 0))))

    def _data_bounds(self, series) -> tuple[float, float, float, float] | None:
        """全系列の (x 最小, x 最大, y 最小, y 最大) を返す。log 表示の軸では正の値だけを使う。"""
        log_x = self._source.ctrl.logXCheck.isChecked()
        log_y = self._source.ctrl.logYCheck.isChecked()
        xs_all, ys_all = [], []
        for xs, ys in series:
            xs = np.asarray(xs, dtype=float)
            ys = np.asarray(ys, dtype=float)
            keep = np.isfinite(xs) & np.isfinite(ys)
            if log_x:
                keep &= xs > 0
            if log_y:
                keep &= ys > 0
            xs_all.append(xs[keep])
            ys_all.append(ys[keep])
        if not xs_all:
            return None
        xs_all = np.concatenate(xs_all)
        ys_all = np.concatenate(ys_all)
        if xs_all.size == 0:
            return None
        return float(xs_all.min()), float(xs_all.max()), float(ys_all.min()), float(ys_all.max())

    def _mouse_text(self, pos) -> str:
        for item in self._items.values():
            if item.sceneBoundingRect().contains(pos):
                return mouse_position_text(item, pos)
        return ""


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


def create_roi_group() -> tuple[QGroupBox, QComboBox, QCheckBox, QComboBox]:
    """解析対象の ROI を選ぶ group を作る。

    Returns:
        (group, ROI の表示方法（編集中ROI / 登録ROI の Overlay・Split）の combo, 軸の連動の checkbox,
        Split の列数の combo)。
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
    # dialog の高さを増やさないよう、軸の連動と同じ行に置く
    split_row = QHBoxLayout()
    split_row.addWidget(link_check)
    split_row.addStretch()
    split_row.addWidget(columns_combo)
    layout.addWidget(combo)
    layout.addLayout(split_row)
    return group, combo, link_check, columns_combo


def create_channel_group(
    on_checks_changed: Callable[[list], None],
) -> tuple[QGroupBox, ChannelListWidget, RoiChannelPanel]:
    """scroll area の中に ChannelListWidget と登録 ROI 用の RoiChannelPanel（初期は非表示）を置いた group を作る。

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
    roi_panel = RoiChannelPanel()
    roi_panel.setVisible(False)
    scroll_layout.addWidget(roi_panel)
    scroll_layout.addStretch()
    scroll.setWidget(scroll_widget)
    layout.addWidget(scroll)
    return group, channel_list, roi_panel


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
