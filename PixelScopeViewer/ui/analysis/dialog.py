"""単一画像の解析 dialog（metadata・profile・histogram）。"""

import contextlib
from fractions import Fraction

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRect, QSignalBlocker, Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QColorDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.core.export import (
    grouped_profile_csv,
    histogram_csv,
    metadata_csv,
    multi_roi_stats_csv,
    profile_csv,
    roi_stats_csv,
)
from PixelScopeViewer.core.image_io import get_image_metadata
from PixelScopeViewer.core.statistics import (
    crop_roi,
    determine_hist_bins,
    ecdf_series,
    get_profile_offset,
    histogram_series,
    histogram_stats,
    merge_hist_series,
    profile_series,
    profile_stats,
)
from PixelScopeViewer.ui.analysis.overlay import roi_color, roi_curve_label
from PixelScopeViewer.ui.analysis.plotting import apply_plot_settings as pg_apply_plot_settings
from PixelScopeViewer.ui.analysis.plotting import connect_plot_controls as pg_connect_plot_controls
from PixelScopeViewer.ui.analysis.plotting import save_viewbox_state as pg_save_viewbox_state
from PixelScopeViewer.ui.analysis.state import AnalysisSettings
from PixelScopeViewer.ui.analysis.tabs.common import ROI_MODES, ROI_SPLIT_COLUMN_CHOICES
from PixelScopeViewer.ui.analysis.tabs.histogram_tab import HistogramTab
from PixelScopeViewer.ui.analysis.tabs.metadata_tab import MetadataTab
from PixelScopeViewer.ui.analysis.tabs.profile_tab import ProfileTab
from PixelScopeViewer.ui.common import defaults
from PixelScopeViewer.ui.common.channel_display import ChannelDisplay
from PixelScopeViewer.ui.common.window import ToolDialog
from PixelScopeViewer.ui.viewer.state import RoiEntry


def _channel_index(label: str) -> int:
    """series の label（C{k} / I）の channel の index を返す。"""
    return 0 if label == "I" else int(label[1:])


class AnalysisDialog(ToolDialog):
    """ROI の metadata・profile・histogram を表示する modeless dialog。

    親の ImageViewer から set_image_and_rect で画像と ROI が更新される。
    profile・histogram は編集中 ROI のほか、ROI 一覧で ☑ を付けた登録 ROI を重ねて（Overlay）
    または並べて（Split）表示できる。

    Args:
        parent: 親 widget（通常は ImageViewer）。
        image_array: 画像配列。
        image_rect: 画像座標の ROI（編集中 ROI）。
        image_path: metadata の取得に使う画像ファイルのパス。
        channel_display: グラフの色の持ち主。
        rois: 解析対象の登録 ROI。
    """

    window_key = "analysis"
    remember_geometry = True
    maximizable = True

    def __init__(
        self,
        parent=None,
        image_array: np.ndarray | None = None,
        image_rect: QRect | None = None,
        image_path: str | None = None,
        channel_display: ChannelDisplay | None = None,
        rois: list[RoiEntry] | None = None,
    ):
        super().__init__(parent)
        # グラフの色の持ち主。表示色・個別設定のどちらが変わっても再描画する。
        # None は色を自前で決める複数画像比較の解析 dialog（TilingAnalysisDialog）のみ
        self.channel_display = channel_display
        if channel_display is not None:
            channel_display.colors_changed.connect(self._on_channel_colors_changed)
            channel_display.plot_colors_changed.connect(self._on_channel_colors_changed)
        self.viewer = parent

        self.resize(*defaults.ANALYSIS_DIALOG_SIZE)

        self.image_array = image_array
        self.image_rect = image_rect
        self.image_path = image_path
        self.rois: list[RoiEntry] = list(rois or [])

        self.settings = AnalysisSettings()
        self.update_window_title()

        # 親で ROI が変わったら title を更新する
        if self.viewer and hasattr(self.viewer, "roi_changed"):
            self.viewer.roi_changed.connect(self.update_window_title)

        self.last_hist_data = {}
        self.last_metadata: list[tuple[str, str]] = []
        # 表示中の画像の channel 数（2 次元画像は 1）
        self._n_plot = 0
        # 全体表示の ViewBox の状態（初回描画後に保存される）
        self.viewbox_full_hist = None
        self.viewbox_full_prof = None
        self.last_profile_data = {}

        # 統計量 table の色見本に使う label から RGB への dict
        self.channel_color_map: dict[str, tuple[int, int, int]] = {}

        self._build_ui()

        # 前回の geometry を復元する
        self.restore_geometry()

        if self.image_array is not None:
            self.update_contents()

    def _build_ui(self):
        main = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main.addWidget(self.tabs)

        self.meta_tab = MetadataTab(self)
        self.meta_tab.copy_btn.clicked.connect(self.copy_metadata_to_clipboard)
        self.tabs.addTab(self.meta_tab, "Metadata")

        self.profile_tab = ProfileTab(
            on_save_viewbox_state=lambda vb: self._save_viewbox_state(vb, "prof"),
            on_connect_plot_controls=lambda plot_item: self._connect_plotitem_controls(plot_item, "prof"),
            on_channel_changed=lambda checks: self._on_channel_changed(checks),
            parent=self,
        )
        self.profile_tab.orientation_btn.clicked.connect(self._on_prof_orientation_toggle)
        self.profile_tab.xmode_btn.clicked.connect(self._on_prof_xmode_toggle)
        self.profile_tab.compute_method_combo.currentTextChanged.connect(self._on_prof_compute_method_combo)
        self.profile_tab.copy_btn.clicked.connect(self.copy_profile_to_clipboard)
        self.profile_tab.copy_stats_btn.clicked.connect(self.copy_prof_stats_to_clipboard)
        self.tabs.addTab(self.profile_tab, "Profile")
        self.profile_tab.channel_list.color_clicked.connect(self._on_plot_color_clicked)
        self.profile_tab.channel_list.reset_requested.connect(self._on_plot_color_reset)

        self.hist_tab = HistogramTab(
            on_save_viewbox_state=lambda vb: self._save_viewbox_state(vb, "hist"),
            on_connect_plot_controls=lambda plot_item: self._connect_plotitem_controls(plot_item, "hist"),
            on_channel_changed=lambda checks: self._on_channel_changed(checks),
            on_spinbox_changed=lambda new_value: self._on_spinbox_changed(new_value),
            on_spinbox_bar_alpha_changed=lambda new_value: self._on_spinbox_bar_alpha_changed(new_value),
            parent=self,
        )
        self.hist_tab.chart_kind_combo.currentTextChanged.connect(self._on_hist_chart_kind_combo)
        self.hist_tab.config_mode_btn.clicked.connect(self.hist_config_mode_toggle)
        self.hist_tab.config_reset_btn.clicked.connect(self.hist_config_reset)
        self.hist_tab.copy_btn.clicked.connect(self.copy_histogram_to_clipboard)
        self.hist_tab.copy_stats_btn.clicked.connect(self.copy_hist_stats_to_clipboard)
        self.tabs.addTab(self.hist_tab, "Histogram")
        self.hist_tab.channel_list.color_clicked.connect(self._on_plot_color_clicked)
        self.hist_tab.channel_list.reset_requested.connect(self._on_plot_color_reset)

        # status bar
        self.status = QStatusBar()
        self.status.setStyleSheet("QStatusBar, QLabel { font-size: 14px; }")
        main.addWidget(self.status)

        self.tabs_info = QLabel()
        left_container = QWidget()
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(15, 0, 15, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(self.tabs_info)
        self.status.addWidget(left_container)

        self.hist_tab.status_changed.connect(self.tabs_info.setText)
        self.profile_tab.status_changed.connect(self.tabs_info.setText)

        # ROI の表示方法と登録 ROI の channel の一覧は、profile・histogram tab で共通にする
        for tab in (self.profile_tab, self.hist_tab):
            tab.roi_mode_combo.currentIndexChanged.connect(self._on_roi_mode_changed)
            tab.link_axes_check.toggled.connect(self._on_link_axes_toggled)
            tab.split_columns_combo.currentIndexChanged.connect(self._on_split_columns_changed)
            panel = tab.roi_channel_panel
            panel.group_checks_changed.connect(self._on_roi_checks_changed)
            panel.group_color_clicked.connect(self._on_roi_color_clicked)
            panel.reset_requested.connect(lambda: self.viewer.roi_list.reset_color_overrides())
            panel.all_checks_requested.connect(self._on_roi_all_checks)

    def update_window_title(self, *args):
        """親の status bar の ROI 表示（登録 ROI の表示中は ROI の名前）を window title に反映する。"""
        base_title = "解析ビュー"

        if self._roi_mode_active():
            names = ",".join(e.name for e in self.rois)
            self.setWindowTitle(f"{base_title} | ROIs={names}")
            return

        # 複数画像比較の window が親の場合は status_updater がないため、既定の title にする
        if self.viewer and hasattr(self.viewer, "status_updater"):
            roi_text = self.viewer.status_updater.roi_label.text()
            if roi_text:
                self.setWindowTitle(f"{base_title} | ROI={roi_text}")
                return

        self.setWindowTitle(base_title)

    def set_image_and_rect(
        self,
        image_array: np.ndarray | None,
        image_rect: QRect | None,
        image_path: str | None = None,
        rois: list[RoiEntry] | None = None,
    ):
        """画像と ROI を更新して表示を作り直す。

        Args:
            image_array: 画像配列。
            image_rect: 画像座標の ROI（編集中 ROI）。
            image_path: 画像ファイルのパス。None の場合は前回の値を使う。
            rois: 解析対象の登録 ROI。None の場合は前回の値を使う。
        """
        self.image_array = image_array
        self.image_rect = image_rect
        if image_path is not None:
            self.image_path = image_path
        if rois is not None:
            self.rois = list(rois)

        self.update_contents()

    def set_current_tab(self, tab):
        """tab 名（前方一致）または index で tab を切り替える。"""
        if tab is None:
            return
        if isinstance(tab, int):
            if 0 <= tab < self.tabs.count():
                self.tabs.setCurrentIndex(tab)
            return
        t = str(tab).lower()
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).lower().startswith(t):
                self.tabs.setCurrentIndex(i)
                return

    def _on_channel_changed(self, new_checks: list[bool]):
        self.settings.channel_checks = new_checks
        self.update_contents()

    def _on_spinbox_changed(self, new_value: float):
        self.settings.hist_bin_step = new_value
        self.update_contents()

    def _on_spinbox_bar_alpha_changed(self, new_value: int):
        self.settings.hist_bar_alpha = new_value
        self.update_contents()

    def update_contents(self):
        """現在の画像・ROI・設定で全 tab を更新する。"""
        self._update_roi_controls()
        if self._roi_mode_active():
            self._update_contents_multi()
        else:
            self._update_contents_active()

    def _roi_mode_active(self) -> bool:
        """登録 ROI（Overlay / Split）を表示中か。"""
        return self.settings.roi_mode != "active" and bool(self.rois)

    def _update_contents_active(self):
        """編集中 ROI で profile・histogram を更新する。ROI がない場合は左上 1 pixel を対象にする。"""
        arr = self.image_array
        if arr is None:
            self._update_metadata()
            return
        arr = crop_roi(arr, self.image_rect.getRect() if self.image_rect is not None else None)

        self._update_metadata()

        # channel_checks の長さを channel 数に合わせる
        nch = arr.shape[2] if arr.ndim == 3 and arr.shape[2] > 1 else 1
        if nch > 1:
            self.settings.fit_channel_checks(nch)

        # histogram
        if self.settings.hist_mode == "Histogram":
            bins = determine_hist_bins(arr, self.settings.hist_bin_step)
            hist_series = histogram_series(arr, bins=bins)
        elif self.settings.hist_mode == "ECDF":
            hist_series = ecdf_series(arr)
        self.last_hist_data = hist_series  # コピー用に全 channel を保持する
        hist_stats = histogram_stats(arr.astype(np.float64), self.settings.channel_checks)
        apply_log = self.settings.plot_settings.get("hist", {}).get("log", False)
        is_integer_type = np.issubdtype(arr.dtype, np.integer)
        # グラフの色（2 次元画像は 1ch として扱う）
        n_plot = arr.shape[2] if arr.ndim == 3 else 1
        self._n_plot = n_plot
        channel_colors = self.channel_display.plot_colors(n_plot) if self.channel_display else []

        self.hist_tab.update_channel_checkboxes(nch, self.settings.channel_checks, channel_colors)
        self.profile_tab.update_channel_checkboxes(nch, self.settings.channel_checks, channel_colors)

        # 線と統計量 table の色見本に使う curve label（C{index}、1ch は I）から RGB への dict
        self.channel_color_map = {f"C{i}": c.getRgb()[:3] for i, c in enumerate(channel_colors)}
        if n_plot == 1 and channel_colors:
            self.channel_color_map["I"] = channel_colors[0].getRgb()[:3]
        self.hist_tab.update_plot(
            self._visible_series(hist_series),
            hist_stats,
            self.channel_color_map,
            apply_log=apply_log,
            is_integer_type=is_integer_type,
            chart_kind=self.settings.hist_chart_kind,
            bar_alpha=self.settings.hist_bar_alpha,
        )

        # profile
        pseries = profile_series(
            arr, orientation=self.settings.profile_orientation, method=self.settings.profile_method
        )
        # absolute 表示では x に ROI の開始座標を加える
        offset = 0
        if self.settings.profile_x_mode == "absolute" and self.image_rect is not None:
            offset = get_profile_offset(self.image_rect, self.settings.profile_orientation)
        # コピー用に全 channel の profile を保持する
        self.last_profile_data = {label: (np.arange(prof.size) + offset, prof) for label, prof in pseries.items()}
        prof_stats = profile_stats(
            arr,
            orientation=self.settings.profile_orientation,
            method=self.settings.profile_method,
            channel_checks=self.settings.channel_checks,
        )
        self.profile_tab.update_plot(
            self._visible_series(self.last_profile_data),
            prof_stats,
            self.settings.profile_orientation,
            self.settings.profile_x_mode,
            self.settings.profile_method,
            self.channel_color_map,
        )
        self._restore_main_plots()

    def _restore_main_plots(self):
        """編集中ROI・Overlay 用の plot の表示範囲と plot 設定を復元する。"""
        # 保存済みの ViewBox 状態がなければ、データに合わせて表示範囲を自動調整する
        for widget, saved in (
            (self.hist_tab.hist_widget, self.viewbox_full_hist),
            (self.profile_tab.prof_widget, self.viewbox_full_prof),
        ):
            if saved is None:
                widget.getViewBox().autoRange()
                widget.getViewBox().enableAutoRange(axis=pg.ViewBox.XYAxes)

        # 保存済みの plot 設定（grid、ViewBox 状態）を再適用する
        self._apply_plot_settings()

    # ---- 登録 ROI ----
    def _update_contents_multi(self):
        """☑ の付いた登録 ROI の profile・histogram を重ねて（Overlay）または並べて（Split）表示する。

        曲線の label は R{id} C{k}、統計量の行の ch は R{id}_C{k} にする。画像の範囲外の ROI は飛ばす。
        """
        self._update_metadata()
        arr = self.image_array
        if arr is None:
            return
        overrides = self._roi_color_overrides()
        targets = []  # (RoiEntry, 切り出した配列, channel の表示 ON/OFF)
        for entry in self.rois:
            sub = crop_roi(arr, entry.rect.getRect())
            if sub.size == 0:
                continue
            n = sub.shape[2] if sub.ndim == 3 else 1
            vis = self.settings.roi_channel_visibility.setdefault(entry.id, [])
            vis[:] = (vis + [True] * n)[:n]
            targets.append((entry, sub, vis))

        self.channel_color_map = {
            roi_curve_label(e.id, k): roi_color(e.id, k, overrides).getRgb()[:3]
            for e, _, vis in targets
            for k in range(len(vis))
        }
        groups = [
            (e.id, vis, [QColor(*self.channel_color_map[roi_curve_label(e.id, k)]) for k in range(len(vis))])
            for e, _, vis in targets
        ]
        for tab in (self.hist_tab, self.profile_tab):
            tab.roi_channel_panel.set_groups(groups)

        hist_series, hist_rows = self._multi_hist_series(targets)
        self.last_hist_data = merge_hist_series(hist_series, self.settings.hist_mode) if hist_series else {}
        prof_series, prof_rows = self._multi_profile_series(targets)
        self.last_profile_data = prof_series

        names = ",".join(e.name for e, _, _ in targets) or "No ROI in image"
        hist_kwargs = {
            "apply_log": self.settings.plot_settings.get("hist", {}).get("log", False),
            "is_integer_type": np.issubdtype(arr.dtype, np.integer),
            "chart_kind": self.settings.hist_chart_kind,
            "bar_alpha": self.settings.hist_bar_alpha,
        }
        if self.settings.roi_mode == "overlay":
            self.hist_tab.update_plot(
                self.last_hist_data,
                hist_rows,
                self.channel_color_map,
                title=f"{self.settings.hist_mode} Overlay ({names})",
                **hist_kwargs,
            )
            self.profile_tab.update_plot(
                prof_series,
                prof_rows,
                self.settings.profile_orientation,
                self.settings.profile_x_mode,
                self.settings.profile_method,
                self.channel_color_map,
                title_prefix=f"Profile Overlay ({names})",
            )
            self._restore_main_plots()
            return

        # Split: grid・log は編集中ROI 用の plot の設定を各グラフに揃えるため、先に plot 設定を適用する
        self._apply_plot_settings()
        link = self.settings.roi_link_axes
        n_cols = self.settings.roi_split_columns
        self.hist_tab.update_split_plots(
            self._split_groups(targets, self.last_hist_data, overrides),
            hist_rows,
            self.channel_color_map,
            link,
            n_cols,
            **hist_kwargs,
        )
        self.profile_tab.update_split_plots(
            self._split_groups(targets, prof_series, overrides),
            prof_rows,
            self.settings.profile_x_mode,
            self.channel_color_map,
            link,
            n_cols,
        )

    def _multi_hist_series(self, targets) -> tuple[dict, list[dict]]:
        """登録 ROI ごとの histogram（または ECDF）の表示 ON の系列と、統計量の行を返す。"""
        series = {}
        rows = []
        for entry, sub, vis in targets:
            if self.settings.hist_mode == "Histogram":
                s = histogram_series(sub, bins=determine_hist_bins(sub, self.settings.hist_bin_step))
            else:
                s = ecdf_series(sub)
            for label, data in s.items():
                if vis[_channel_index(label)]:
                    series[roi_curve_label(entry.id, _channel_index(label))] = data
            for row in histogram_stats(sub.astype(np.float64), vis):
                k = int(row["ch"])
                if vis[k]:
                    rows.append({**row, "ch": f"{entry.name}_C{k}", "curve_label": roi_curve_label(entry.id, k)})
        return series, rows

    def _multi_profile_series(self, targets) -> tuple[dict, list[dict]]:
        """登録 ROI ごとの profile の表示 ON の系列と、統計量の行を返す。

        absolute 表示では ROI ごとの開始座標を x に加える。
        """
        orientation = self.settings.profile_orientation
        method = self.settings.profile_method
        series = {}
        rows = []
        for entry, sub, vis in targets:
            offset = 0
            if self.settings.profile_x_mode == "absolute":
                offset = get_profile_offset(entry.rect, orientation)
            for label, prof in profile_series(sub, orientation=orientation, method=method).items():
                k = _channel_index(label)
                if vis[k]:
                    series[roi_curve_label(entry.id, k)] = (np.arange(prof.size) + offset, prof)
            for row in profile_stats(sub, orientation=orientation, method=method, channel_checks=vis):
                k = int(row["ch"])
                if vis[k]:
                    rows.append({**row, "ch": f"{entry.name}_C{k}", "curve_label": roi_curve_label(entry.id, k)})
        return series, rows

    @staticmethod
    def _split_groups(targets, series: dict, overrides: dict[str, str]) -> list[tuple[int, str, str, dict]]:
        """Split 表示の ROI ごとの (id, title, title の色, 系列) のリストを返す。"""
        groups = []
        for entry, _, _ in targets:
            r = entry.rect
            title = f"{entry.name} ({r.x()},{r.y()} {r.width()}×{r.height()})"
            prefix = f"{entry.name} "
            own = {label: data for label, data in series.items() if label.startswith(prefix)}
            groups.append((entry.id, title, roi_color(entry.id, 0, overrides).name(), own))
        return groups

    def _roi_color_overrides(self) -> dict[str, str]:
        return self.viewer.state.roi_color_overrides

    def _update_roi_controls(self):
        """ROI の combo・軸の連動・plot と channel 一覧の表示を、設定と登録 ROI の有無に合わせる。

        登録 ROI がなくなった場合は編集中 ROI の表示に戻す。
        """
        has_rois = bool(self.rois)
        if not has_rois:
            self.settings.roi_mode = "active"
        mode = self.settings.roi_mode
        index = next(i for i, (m, _) in enumerate(ROI_MODES) if m == mode)
        for tab in (self.profile_tab, self.hist_tab):
            model = tab.roi_mode_combo.model()
            for i, (m, _) in enumerate(ROI_MODES):
                if m != "active":
                    model.item(i).setEnabled(has_rois)
            with QSignalBlocker(tab.roi_mode_combo):
                tab.roi_mode_combo.setCurrentIndex(index)
            with QSignalBlocker(tab.link_axes_check):
                tab.link_axes_check.setChecked(self.settings.roi_link_axes)
            tab.link_axes_check.setEnabled(mode == "split")
            with QSignalBlocker(tab.split_columns_combo):
                tab.split_columns_combo.setCurrentIndex(
                    tab.split_columns_combo.findData(self.settings.roi_split_columns)
                )
            tab.split_columns_combo.setEnabled(mode == "split")
            tab.set_roi_view(mode)
        self.update_window_title()

    def _on_roi_mode_changed(self, index: int):
        mode = ROI_MODES[index][0]
        if mode == self.settings.roi_mode:
            return
        self.settings.roi_mode = mode
        self.update_contents()

    def _on_link_axes_toggled(self, checked: bool):
        self.settings.roi_link_axes = bool(checked)
        self.update_contents()

    def _on_split_columns_changed(self, index: int):
        self.settings.roi_split_columns = ROI_SPLIT_COLUMN_CHOICES[index]
        self.update_contents()

    def _on_roi_checks_changed(self, roi_id: int, checks: list[bool]):
        vis = self.settings.roi_channel_visibility.get(roi_id)
        if vis is None or vis == checks:
            return
        vis[:] = [bool(c) for c in checks[: len(vis)]]
        self.update_contents()

    def _on_roi_all_checks(self, value: bool):
        """全登録 ROI の全 channel の表示を value にする。"""
        visibility = [self.settings.roi_channel_visibility.get(e.id) for e in self.rois]
        visibility = [vis for vis in visibility if vis is not None]
        if all(v == value for vis in visibility for v in vis):
            return
        for vis in visibility:
            vis[:] = [value] * len(vis)
        self.update_contents()

    def _on_roi_color_clicked(self, roi_id: int, ch_idx: int):
        """色選択 dialog で選んだ色を、その ROI・channel の色として設定する。画像上の ROI の枠の色にも反映される。"""
        label = roi_curve_label(roi_id, ch_idx)
        current = roi_color(roi_id, ch_idx, self._roi_color_overrides())
        color = QColorDialog.getColor(current, self, f"{label} の色を選択")
        if color.isValid():
            self.viewer.roi_list.set_color_override(label, color.name())

    def _update_metadata(self):
        """画像ファイルの metadata を metadata tab に表示する。"""
        if self.image_path is None or not self.image_path:
            self.meta_tab.set_rows([("Error", "No file path available")])
            self.last_metadata = []
            return

        # 読み込みの失敗は get_image_metadata が Error の項目として返す
        metadata = get_image_metadata(self.image_path, self.image_array)
        if not metadata:
            self.meta_tab.set_rows([("Info", "No metadata available")])
            self.last_metadata = []
            return

        # 基本情報、EXIF の順に並べる
        basic_keys = ["Filepath", "Format", "FileSize", "Size", "Channels", "DataType"]
        rows = [(key, str(metadata[key])) for key in basic_keys if key in metadata]
        for key, value in metadata.items():
            if key in basic_keys:
                continue
            rows.append((key, str(value)))
            if key == "EXIF_ExposureTime":
                # 露光時間（"1/60" など）を秒で併記する。形式が崩れている場合は省略する
                with contextlib.suppress(ValueError, ZeroDivisionError):
                    rows.append((" -> (seconds)", f"{float(Fraction(str(value))):.3e}"))

        self.last_metadata = rows
        self.meta_tab.set_rows(rows)

    def hist_config_mode_toggle(self):
        if self.settings.hist_mode == "Histogram":
            self.settings.hist_mode = "ECDF"
            self.hist_tab.config_mode_btn.setText("ECDF")
        else:
            self.settings.hist_mode = "Histogram"
            self.hist_tab.config_mode_btn.setText("Histogram")
        self.update_contents()

    def _visible_series(self, series: dict) -> dict:
        """表示 ON の channel（C{index}）の series だけを返す。1ch（I）は常に表示する。"""
        checks = self.settings.channel_checks
        return {
            label: v
            for label, v in series.items()
            if not label.startswith("C") or int(label[1:]) >= len(checks) or checks[int(label[1:])]
        }

    def _on_plot_color_clicked(self, idx: int):
        """色選択 dialog で選んだ色を、この channel 数のグラフの色として設定する。"""
        if self.channel_display is None:
            return
        n = self._n_plot
        colors = self.channel_display.plot_colors(n)
        if not 0 <= idx < len(colors):
            return
        color = QColorDialog.getColor(colors[idx], self, f"チャンネル {idx} の色を選択")
        if color.isValid():
            self.channel_display.set_plot_color(n, idx, color)

    def _on_plot_color_reset(self):
        if self.channel_display is not None:
            self.channel_display.reset_plot_colors(self._n_plot)

    def _on_channel_colors_changed(self, _n_channels: int):
        self.update_contents()

    def hist_config_reset(self):
        self._on_spinbox_changed(defaults.HIST_BIN_STEP)
        self.hist_tab.bin_step_spin_box.setValue(defaults.HIST_BIN_STEP)

    def copy_metadata_to_clipboard(self):
        """metadata をカンマ区切りで clipboard にコピーする。"""
        if not self.last_metadata:
            QMessageBox.information(self, "Copy", "No metadata to copy.")
            return
        QGuiApplication.clipboard().setText(metadata_csv(self.last_metadata))

    def copy_histogram_to_clipboard(self):
        """histogram（または ECDF）のデータを CSV で clipboard にコピーする。"""
        if not self.last_hist_data:
            QMessageBox.information(self, "Copy", "No data.")
            return
        QGuiApplication.clipboard().setText(histogram_csv(self.last_hist_data, self.settings.hist_mode))

    def copy_profile_to_clipboard(self):
        """profile のデータを CSV で clipboard にコピーする。"""
        if not self.last_profile_data:
            QMessageBox.information(self, "Copy", "No data.")
            return
        # 登録 ROI は ROI ごとに長さが違うため、x の列も ROI ごとに出力する
        to_csv = grouped_profile_csv if self._roi_mode_active() else profile_csv
        QGuiApplication.clipboard().setText(to_csv(self.last_profile_data, self.settings.profile_orientation))

    def copy_hist_stats_to_clipboard(self):
        self._copy_roi_stats(self.hist_tab, None)

    def copy_prof_stats_to_clipboard(self):
        self._copy_roi_stats(self.profile_tab, (self.settings.profile_orientation, self.settings.profile_method))

    def _copy_roi_stats(self, tab, profile: tuple[str, str] | None):
        """ROI の統計量を CSV で clipboard にコピーする。

        "Target: All plane" の場合は全画像を対象にする。登録 ROI の表示中は ☑ の付いた全 ROI を対象にする。
        """
        imgs = self.viewer.images
        if not tab.get_all_plane_data.isChecked():
            imgs = [imgs[self.viewer.state.current_index]]
        images = [(img["path"], img["base_array"]) for img in imgs]
        if self._roi_mode_active():
            text = multi_roi_stats_csv(images, [(e.name, e.rect.getRect()) for e in self.rois], profile)
        else:
            text = roi_stats_csv(images, self.viewer.state.roi.getRect(), profile)
        QGuiApplication.clipboard().setText(text)

    def _on_prof_orientation_toggle(self):
        if self.settings.profile_orientation == "h":
            self.settings.profile_orientation = "v"
            self.profile_tab.orientation_btn.setText("Vertical")
        else:
            self.settings.profile_orientation = "h"
            self.profile_tab.orientation_btn.setText("Horizontal")
        self.update_contents()

    def _on_prof_xmode_toggle(self):
        if self.settings.profile_x_mode == "relative":
            self.settings.profile_x_mode = "absolute"
            self.profile_tab.xmode_btn.setText("Absolute")
        else:
            self.settings.profile_x_mode = "relative"
            self.profile_tab.xmode_btn.setText("Relative")
        self.update_contents()

    def _on_prof_compute_method_combo(self):
        self.settings.profile_method = self.profile_tab.compute_method_combo.currentText()
        self.update_contents()

    def _on_hist_chart_kind_combo(self):
        self.settings.hist_chart_kind = self.hist_tab.chart_kind_combo.currentText()
        if self.settings.hist_chart_kind == "Bar":
            self.hist_tab.bar_alpha_spin_box.setEnabled(True)
        else:
            self.hist_tab.bar_alpha_spin_box.setEnabled(False)
        self.update_contents()

    def _on_external_log_toggled(self, checked: bool):
        # pyqtgraph の menu で log Y が切り替えられたら設定を保存して再描画する
        self.settings.plot_settings.setdefault("hist", {})["log"] = bool(checked)
        self.update_contents()

    def _connect_plotitem_controls(self, plot_item, which: str):
        pg_connect_plot_controls(
            plot_item,
            which,
            self.settings.plot_settings,
            on_hist_log_changed=lambda: self._on_external_log_toggled(
                self.settings.plot_settings.get("hist", {}).get("log", False)
            ),
        )

    def _apply_plot_settings(self):
        pg_apply_plot_settings(self.hist_tab.hist_widget, "hist", self.settings.plot_settings, self.viewbox_full_hist)
        pg_apply_plot_settings(
            self.profile_tab.prof_widget, "prof", self.settings.plot_settings, self.viewbox_full_prof
        )

    def _save_viewbox_state(self, vb, which: str):
        setattr(self, f"viewbox_full_{which}", pg_save_viewbox_state(vb))

    def keyPressEvent(self, event):
        # Esc で dialog を閉じず、入力欄の focus を外すだけにする
        if event.key() == Qt.Key_Escape:
            focused_widget = self.focusWidget()
            if focused_widget and isinstance(focused_widget, (QSpinBox, QDoubleSpinBox, QLineEdit)):
                focused_widget.clearFocus()
                event.accept()
                return
            event.ignore()
            return
        super().keyPressEvent(event)
