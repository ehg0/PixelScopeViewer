"""histogram tab。"""

from collections.abc import Callable

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.ui.analysis.tabs.common import (
    StatsTable,
    create_channel_group,
    create_export_group,
    create_plot_widget,
    label_color,
    make_group_box,
    mouse_position_text,
)
from PixelScopeViewer.ui.common import defaults, theme


def make_hist_bar_item(xs, heights, width: float, brush, name: str, log_x: bool, log_y: bool) -> pg.BarGraphItem:
    """histogram の BarGraphItem を作る。

    BarGraphItem は setLogMode を持たず PlotItem の log X/Y で変換されないため、座標を自前で log10 変換する。
    log Y の下端は 0 を 0.1 に置き換える既存の扱いに合わせて -1 にする。
    """
    xs = np.asarray(xs, dtype=float)
    heights = np.asarray(heights, dtype=float)
    left = xs - width / 2
    right = xs + width / 2
    y0 = np.zeros_like(heights)
    y1 = heights
    if log_x:
        # Line と同様に x <= 0 の bin は描かない
        keep = xs > 0
        xs, left, right, y0, y1 = xs[keep], left[keep], right[keep], y0[keep], y1[keep]
        log_xs = np.log10(xs)
        log_right = np.log10(right)
        # 0 始まりの bin は左端が log にできないため、中心で右端を鏡映する
        with np.errstate(divide="ignore", invalid="ignore"):
            log_left = np.where(left > 0, np.log10(np.where(left > 0, left, 1.0)), 2 * log_xs - log_right)
        left, right = log_left, log_right
    if log_y:
        y0 = np.full_like(y1, -1.0)
        with np.errstate(divide="ignore"):
            y1 = np.log10(y1)
    return pg.BarGraphItem(x0=left, x1=right, y0=y0, y1=y1, brush=brush, pen=None, name=name)


def plot_log_mode(plot_widget) -> tuple[bool, bool]:
    """PlotWidget の menu の log X/Y の状態を返す。"""
    ctrl = plot_widget.getPlotItem().ctrl
    return bool(ctrl.logXCheck.isChecked()), bool(ctrl.logYCheck.isChecked())


class HistogramTab(QWidget):
    """histogram の plot、統計量の table、設定 control を持つ tab。

    Args:
        on_save_viewbox_state: ViewBox の状態を保存する callback。
        on_connect_plot_controls: PlotItem の control を接続する callback。
        on_channel_changed: channel の表示 ON/OFF 変更時の callback。
        on_spinbox_changed: bin step 変更時の callback。
        on_spinbox_bar_alpha_changed: bar の alpha 変更時の callback。
        parent: 親 widget。
    """

    # status bar に表示する文字列
    status_changed = Signal(str)

    def __init__(
        self,
        on_save_viewbox_state: Callable[[object], None] | None = None,
        on_connect_plot_controls: Callable[[object], None] | None = None,
        on_channel_changed: Callable[[list], None] | None = None,
        on_spinbox_changed: Callable[[float], None] | None = None,
        on_spinbox_bar_alpha_changed: Callable[[int], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.on_channel_changed = on_channel_changed

        root = QHBoxLayout(self)

        # 左側: plot と統計量
        left = QVBoxLayout()
        self.hist_widget = create_plot_widget(
            "Count", "Intensity", on_save_viewbox_state, on_connect_plot_controls, self._on_mouse_over
        )
        left.addWidget(self.hist_widget, 3)
        self.stats_table = StatsTable(int_format=True)
        left.addWidget(self.stats_table, 0)
        root.addLayout(left, 1)

        # 右側の control
        right = QVBoxLayout()
        right.setContentsMargins(10, 10, 10, 10)
        right.setSpacing(8)

        channels_group, self.channel_list = create_channel_group(self._on_checkbox_changed)
        right.addWidget(channels_group)

        config_group, config_layout = make_group_box("Histgram config")
        self.config_mode_btn = QPushButton("Histogram")
        self.config_mode_btn.setMaximumWidth(100)
        config_layout.addWidget(self.config_mode_btn)
        self.chart_kind_combo = QComboBox()
        self.chart_kind_combo.addItems(["Line", "Bar"])
        self.chart_kind_combo.setMinimumWidth(100)
        config_layout.addWidget(self.chart_kind_combo)
        config_layout.addWidget(QLabel("color alpha:"))
        self.bar_alpha_spin_box = QSpinBox()
        self.bar_alpha_spin_box.setRange(0, 255)
        self.bar_alpha_spin_box.setSingleStep(10)
        self.bar_alpha_spin_box.setValue(defaults.HIST_BAR_ALPHA)
        if on_spinbox_bar_alpha_changed is not None:
            self.bar_alpha_spin_box.valueChanged.connect(on_spinbox_bar_alpha_changed)
        config_layout.addWidget(self.bar_alpha_spin_box)
        bin_step_layout = QHBoxLayout()
        self.config_reset_btn = QPushButton("Reset")
        self.config_reset_btn.setMaximumWidth(60)
        bin_step_layout.addWidget(QLabel("bin step:"))
        bin_step_layout.addWidget(self.config_reset_btn)
        config_layout.addLayout(bin_step_layout)
        self.bin_step_spin_box = QDoubleSpinBox()
        self.bin_step_spin_box.setRange(0.001, 100.0)
        self.bin_step_spin_box.setSingleStep(0.1)
        self.bin_step_spin_box.setDecimals(3)
        self.bin_step_spin_box.setValue(defaults.HIST_BIN_STEP)
        if on_spinbox_changed is not None:
            self.bin_step_spin_box.valueChanged.connect(on_spinbox_changed)
        config_layout.addWidget(self.bin_step_spin_box)
        right.addWidget(config_group)

        export_group, self.copy_btn, self.copy_stats_btn, self.get_all_plane_data = create_export_group()
        right.addWidget(export_group)

        right.addStretch(1)
        root.addLayout(right)

    def _on_checkbox_changed(self, checks: list[bool]):
        if self.on_channel_changed:
            self.on_channel_changed(checks)

    def update_channel_checkboxes(self, nch: int, checks: list[bool], channel_colors: list | None = None):
        """channel の行（checkbox・label・色ボタン）を更新する。"""
        self.channel_list.set_channels([f"C{i}" for i in range(nch)], checks, channel_colors or [])

    def update_plot(
        self,
        series: dict,
        stats_rows: list[dict],
        color_by_label: dict[str, tuple[int, int, int]],
        apply_log: bool = False,
        is_integer_type: bool = False,
        chart_kind: str = "Line",
        bar_alpha: int = 120,
    ):
        """計算済みのデータで histogram の plot と統計量の table を更新する。

        Args:
            series: label から (x, 度数) への dict。
            stats_rows: histogram_stats の戻り値。
            color_by_label: label（C{index} / I）から RGB への dict。
            apply_log: Y 軸を log 表示するか。
            is_integer_type: 整数 dtype か。
            chart_kind: "Line" または "Bar"。
            bar_alpha: Bar 表示時の alpha。
        """
        self.hist_widget.clear()
        log_x, log_y = plot_log_mode(self.hist_widget)
        for label, (xs, ys) in series.items():
            yplot = np.array(ys, dtype=float)
            if apply_log:
                # 0 を 0.1 に置き換え、log10(0.1) = -1 として下端に表示する
                yplot[yplot == 0] = 0.1
                self.hist_widget.setLimits(yMin=-1)
            if chart_kind == "Line":
                pen = pg.mkPen(color=label_color(label, color_by_label), width=2)
                self.hist_widget.plot(xs, yplot, pen=pen, name=label if label != "I" else "Intensity")
            else:
                brush = label_color(label, color_by_label, alpha=bar_alpha)
                item = make_hist_bar_item(xs, yplot, self.bin_step_spin_box.value(), brush, label, log_x, log_y)
                self.hist_widget.addItem(item)

        self.hist_widget.setTitle(f"Intensity {self.config_mode_btn.text()}", color=theme.PLOT_TEXT_COLOR, size="12pt")
        if is_integer_type:
            self.hist_widget.getAxis("bottom").setStyle(tickTextOffset=10)
        self.stats_table.set_rows(stats_rows, color_by_label)

    def _on_mouse_over(self, pos):
        self.status_changed.emit(mouse_position_text(self.hist_widget, pos))
