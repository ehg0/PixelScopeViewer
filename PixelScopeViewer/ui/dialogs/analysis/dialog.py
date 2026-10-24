"""単一画像の解析 dialog（metadata・profile・histogram）。"""

import contextlib

import numpy as np
from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
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

from ....core.image_io import get_image_metadata

try:
    import pyqtgraph as pg
    from pyqtgraph import PlotWidget

    PYQTGRAPH_AVAILABLE = True

except ImportError:
    pg = None
    PlotWidget = None
    PYQTGRAPH_AVAILABLE = False

from ...utils.color_utils import get_default_channel_colors
from .core import (
    calc_stats,
    compute_profile_1d,
    determine_hist_bins,
    ecdf_series,
    get_profile_offset,
    histogram_series,
    histogram_stats,
    profile_series,
    profile_stats,
)
from .exporting import series_to_csv
from .plotting import apply_plot_settings as pg_apply_plot_settings
from .plotting import connect_plot_controls as pg_connect_plot_controls
from .plotting import save_viewbox_state as pg_save_viewbox_state
from .tabs.histogram_tab import HistogramTab
from .tabs.metadata_tab import MetadataTab
from .tabs.profile_tab import ProfileTab


class AnalysisDialog(QDialog):
    """ROI の metadata・profile・histogram を表示する modeless dialog。

    親の ImageViewer から set_image_and_rect で画像と ROI が更新される。

    Args:
        parent: 親 widget（通常は ImageViewer）。
        image_array: 画像配列。
        image_rect: 画像座標の ROI。
        image_path: metadata の取得に使う画像ファイルのパス。
    """

    # 開き直したときに位置が変わらないよう geometry を class で保持する
    _saved_geometry = None
    # 最小化からの復元時に元の位置へ戻すため保持する
    _position_before_minimize = None

    def __init__(
        self,
        parent=None,
        image_array: np.ndarray | None = None,
        image_rect: QRect | None = None,
        image_path: str | None = None,
    ):
        super().__init__(parent)
        self.viewer = parent
        self.update_window_title()

        # 親で ROI が変わったら title を更新する
        if self.viewer and hasattr(self.viewer, "roi_changed"):
            self.viewer.roi_changed.connect(self.update_window_title)

        self.resize(900, 600)

        # 最小化を許可し、最前面に固定しない
        flags = Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.image_array = image_array
        self.image_rect = image_rect
        self.image_path = image_path

        self.profile_orientation = "h"  # "h", "v"
        self.x_mode = "relative"  # "relative", "absolute"
        self.profile_compute_method = "mean"  # "mean", "std", "max", "min", "p2p", "median"
        self.hist_config_mode = "Histogram"  # "Histogram", "ECDF"
        self.hist_yscale = "linear"
        self.channel_checks: list[bool] = []
        self.spinbox_value: float = 1.0
        self.hist_chart_kind = "Line"
        self.spinbox_bar_alpha_value: int = 120

        self.last_hist_data = {}
        self.last_profile_data = {}

        # 統計量 table の色見本に使う label から RGB への dict
        self.channel_color_map: dict[str, tuple[int, int, int]] = {}

        # 画像を切り替えても保持する plot 設定
        self.plot_settings = {
            "hist": {"grid": True, "log": False, "auto_range": True},
            "prof": {"grid": True, "auto_range": True},
        }

        self._build_ui()

        # 前回の geometry を復元する
        try:
            if AnalysisDialog._saved_geometry:
                self.restoreGeometry(AnalysisDialog._saved_geometry)
        except Exception:
            pass

        if self.image_array is not None:
            self.update_contents()

    def _build_ui(self):
        main = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main.addWidget(self.tabs)

        self.meta_tab = MetadataTab(self)
        self.metadata_table = self.meta_tab.metadata_table
        self.metadata_copy_btn = self.meta_tab.copy_btn
        self.metadata_copy_btn.clicked.connect(self.copy_metadata_to_clipboard)
        self.tabs.addTab(self.meta_tab, "Metadata")

        self.profile_tab = ProfileTab(
            PYQTGRAPH_AVAILABLE,
            on_save_viewbox_state=lambda vb: self._save_viewbox_state(vb, "prof"),
            on_connect_plot_controls=lambda plot_item: self._connect_plotitem_controls(plot_item, "prof"),
            on_channel_changed=lambda checks: self._on_channel_changed(checks),
            parent=self,
        )
        self.prof_widget = self.profile_tab.prof_widget
        self.prof_stats_table = self.profile_tab.prof_stats_table
        self.prof_orientation_btn = self.profile_tab.orientation_btn
        self.prof_xmode_btn = self.profile_tab.xmode_btn
        self.prof_compute_method_combo = self.profile_tab.compute_method_combo
        self.prof_copy_btn = self.profile_tab.copy_btn
        self.prof_copy_stats_btn = self.profile_tab.copy_stats_btn
        self.prof_get_all_plane_data = self.profile_tab.get_all_plane_data
        self.prof_orientation_btn.clicked.connect(self._on_prof_orientation_toggle)
        self.prof_xmode_btn.clicked.connect(self._on_prof_xmode_toggle)
        self.prof_compute_method_combo.currentTextChanged.connect(self._on_prof_compute_method_combo)
        self.prof_copy_btn.clicked.connect(self.copy_profile_to_clipboard)
        self.prof_copy_stats_btn.clicked.connect(self.copy_prof_stats_to_clipboard)
        self.tabs.addTab(self.profile_tab, "Profile")

        self.hist_tab = HistogramTab(
            PYQTGRAPH_AVAILABLE,
            on_save_viewbox_state=lambda vb: self._save_viewbox_state(vb, "hist"),
            on_connect_plot_controls=lambda plot_item: self._connect_plotitem_controls(plot_item, "hist"),
            on_channel_changed=lambda checks: self._on_channel_changed(checks),
            on_spinbox_changed=lambda new_value: self._on_spinbox_changed(new_value),
            on_spinbox_bar_alpha_changed=lambda new_value: self._on_spinbox_bar_alpha_changed(new_value),
            parent=self,
        )
        self.hist_widget = self.hist_tab.hist_widget
        self.hist_stats_table = self.hist_tab.stats_table
        self.hist_config_mode_btn = self.hist_tab.config_mode_btn
        self.hist_config_reset_btn = self.hist_tab.config_reset_btn
        self.hist_chart_kind_combo = self.hist_tab.chart_kind_combo
        self.hist_bar_alpha_spin_box = self.hist_tab.bar_alpha_spin_box
        self.hist_copy_btn = self.hist_tab.copy_btn
        self.hist_copy_stats_btn = self.hist_tab.copy_stats_btn
        self.hist_get_all_plane_data = self.hist_tab.get_all_plane_data
        self.hist_chart_kind_combo.currentTextChanged.connect(self._on_hist_chart_kind_combo)
        self.hist_config_mode_btn.clicked.connect(self.hist_config_mode_toggle)
        self.hist_config_reset_btn.clicked.connect(self.hist_config_reset)
        self.hist_copy_btn.clicked.connect(self.copy_histogram_to_clipboard)
        self.hist_copy_stats_btn.clicked.connect(self.copy_hist_stats_to_clipboard)
        self.tabs.addTab(self.hist_tab, "Histogram")

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

    def update_window_title(self, *args):
        """親の status bar の ROI 表示を window title に反映する。"""
        base_title = "解析ビュー"

        if self.viewer and hasattr(self.viewer, "status_roi_area"):
            roi_text = self.viewer.status_roi_area.text()
            if roi_text:
                self.setWindowTitle(f"{base_title} | ROI={roi_text}")
                return

        self.setWindowTitle(base_title)

    def changeEvent(self, event):
        # 最小化前の位置を保存し、復元時に戻す
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                AnalysisDialog._position_before_minimize = self.pos()
            elif event.oldState() & Qt.WindowMinimized and AnalysisDialog._position_before_minimize is not None:
                self.move(AnalysisDialog._position_before_minimize)
        super().changeEvent(event)

    def moveEvent(self, event):
        with contextlib.suppress(Exception):
            AnalysisDialog._saved_geometry = self.saveGeometry()
        super().moveEvent(event)

    def resizeEvent(self, event):
        with contextlib.suppress(Exception):
            AnalysisDialog._saved_geometry = self.saveGeometry()
        super().resizeEvent(event)

    def set_image_and_rect(
        self,
        image_array: np.ndarray | None,
        image_rect: QRect | None,
        image_path: str | None = None,
    ):
        """画像と ROI を更新して表示を作り直す。

        Args:
            image_array: 画像配列。
            image_rect: 画像座標の ROI。
            image_path: 画像ファイルのパス。None の場合は前回の値を使う。
        """
        self.image_array = image_array
        self.image_rect = image_rect
        if image_path is not None:
            self.image_path = image_path

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
        self.channel_checks = new_checks
        self.update_contents()

    def _on_spinbox_changed(self, new_value: float):
        self.spinbox_value = new_value
        self.update_contents()

    def _on_spinbox_bar_alpha_changed(self, new_value: int):
        self.spinbox_bar_alpha_value = new_value
        self.update_contents()

    def update_contents(self):
        """現在の画像・ROI・設定で全 tab を更新する。ROI がない場合は左上 1 pixel を対象にする。"""
        arr = self.image_array
        if arr is None:
            self._update_metadata()
            return
        if self.image_rect is not None:
            x, y, w, h = (
                int(self.image_rect.x()),
                int(self.image_rect.y()),
                int(self.image_rect.width()),
                int(self.image_rect.height()),
            )
            arr = arr[y : y + h, x : x + w]
        else:
            arr = arr[0:1, 0:1]

        self._update_metadata()

        if not PYQTGRAPH_AVAILABLE:
            return

        # channel_checks の長さを channel 数に合わせる
        if arr.ndim == 3 and arr.shape[2] > 1:
            nch = arr.shape[2]
            if not self.channel_checks:
                self.channel_checks = [True] * nch
            elif len(self.channel_checks) < nch:
                self.channel_checks.extend([True] * (nch - len(self.channel_checks)))
        else:
            nch = 1

        # histogram
        if self.hist_config_mode == "Histogram":
            bins = determine_hist_bins(arr, self.spinbox_value)
            hist_series = histogram_series(arr, bins=bins)
        elif self.hist_config_mode == "ECDF":
            hist_series = ecdf_series(arr)
        # 表示 ON の channel のみ plot する
        visible_hist_series = {}
        for label, (xs, ys) in hist_series.items():
            visible = True
            if label.startswith("C"):
                try:
                    cindex = int(label[1:])
                    visible = self.channel_checks[cindex]
                except Exception:
                    visible = True
            if visible:
                visible_hist_series[label] = (xs, ys)
        self.last_hist_data = hist_series  # コピー用に全 channel を保持する
        hist_stats = histogram_stats(arr.astype(np.float64), self.channel_checks)
        apply_log = self.plot_settings.get("hist", {}).get("log", False)
        is_integer_type = np.issubdtype(arr.dtype, np.integer)
        # channel の色の優先順位:
        # 1) self.channel_colors
        # 2) 親が複数画像比較の場合は既定の色（1ch は黒）
        # 3) 親の channel_colors
        channel_colors = getattr(self, "channel_colors", None)
        if not channel_colors:
            is_tiling_parent = False
            try:
                p = self.parent()
                if p is not None:
                    cls = type(p)
                    mod = getattr(cls, "__module__", "").lower()
                    name = getattr(cls, "__name__", "").lower()
                    if "tiling" in mod or "tiling" in name:
                        is_tiling_parent = True
            except Exception:
                is_tiling_parent = False

            if is_tiling_parent:
                try:
                    nch_local = int(arr.shape[2]) if arr.ndim == 3 and arr.shape[2] > 1 else 1
                    colors = get_default_channel_colors(nch_local)
                    if nch_local == 1:
                        colors = [QColor(0, 0, 0)]
                    channel_colors = colors
                except Exception:
                    channel_colors = None
            if not channel_colors:
                try:
                    if hasattr(self.parent(), "channel_colors"):
                        channel_colors = self.parent().channel_colors
                except Exception:
                    channel_colors = None

        try:
            self.hist_tab.update_channel_checkboxes(nch, self.channel_checks, channel_colors)
            self.profile_tab.update_channel_checkboxes(nch, self.channel_checks, channel_colors)
        except Exception:
            pass

        # 統計量 table の色見本用の channel_color_map を作る
        self.channel_color_map = {}
        if channel_colors:
            nch_local = arr.shape[2] if arr.ndim == 3 and arr.shape[2] > 1 else 1
            for cindex in range(nch_local):
                if cindex < len(channel_colors):
                    color = channel_colors[cindex]
                    try:
                        r, g, b, _ = color.getRgb()
                    except Exception:
                        r, g, b = (127, 127, 127)
                    # 番号と C{index} の両方を key にする
                    self.channel_color_map[f"C{cindex}"] = (r, g, b)
                    self.channel_color_map[str(cindex)] = (r, g, b)
            # 1ch は常に黒
            if nch_local == 1:
                self.channel_color_map["I"] = (0, 0, 0)
                self.channel_color_map["0"] = (0, 0, 0)
                self.channel_color_map["C0"] = (0, 0, 0)
        else:
            # 既定の色
            default_palette = [
                (255, 0, 0),
                (0, 200, 0),
                (0, 102, 255),
                (127, 127, 127),
            ]
            nch_local = arr.shape[2] if arr.ndim == 3 and arr.shape[2] > 1 else 1
            for cindex in range(nch_local):
                rgb = default_palette[cindex] if cindex < len(default_palette) else (127, 127, 127)
                self.channel_color_map[f"C{cindex}"] = rgb
                self.channel_color_map[str(cindex)] = rgb
            if nch_local == 1:
                # 1ch は常に黒
                self.channel_color_map["I"] = (0, 0, 0)
                self.channel_color_map["0"] = (0, 0, 0)
                self.channel_color_map["C0"] = (0, 0, 0)
        self.hist_tab.update(
            visible_hist_series,
            hist_stats,
            apply_log=apply_log,
            is_integer_type=is_integer_type,
            channel_colors=channel_colors,
            chart_kind=self.hist_chart_kind,
            bar_alpha=self.spinbox_bar_alpha_value,
        )

        # profile
        pseries = profile_series(arr, orientation=self.profile_orientation, method=self.profile_compute_method)
        visible_prof_series = {}
        for label, prof in pseries.items():
            if self.x_mode == "absolute" and self.image_rect is not None:
                offset = get_profile_offset(self.image_rect, self.profile_orientation)
                xs2 = np.arange(prof.size) + offset
            else:
                xs2 = np.arange(prof.size)
            visible = True
            if label.startswith("C"):
                try:
                    cindex = int(label[1:])
                    visible = self.channel_checks[cindex]
                except Exception:
                    visible = True
            if visible:
                visible_prof_series[label] = (xs2, prof)
        # コピー用に全 channel の profile を保持する
        self.last_profile_data = {}
        for label, prof in pseries.items():
            if self.x_mode == "absolute" and self.image_rect is not None:
                offset = get_profile_offset(self.image_rect, self.profile_orientation)
                xs2 = np.arange(prof.size) + offset
            else:
                xs2 = np.arange(prof.size)
            self.last_profile_data[label] = (xs2, prof)
        prof_stats = profile_stats(
            arr,
            orientation=self.profile_orientation,
            method=self.profile_compute_method,
            channel_checks=self.channel_checks,
        )
        self.profile_tab.update(
            visible_prof_series,
            prof_stats,
            self.profile_orientation,
            self.x_mode,
            self.profile_compute_method,
            channel_colors=channel_colors,
        )

        # 保存済みの ViewBox 状態がなければ、データに合わせて表示範囲を自動調整する
        if PYQTGRAPH_AVAILABLE:
            try:
                if not hasattr(self, "viewbox_full_hist"):
                    hist_vb = self.hist_widget.getViewBox()
                    hist_vb.autoRange()
                    hist_vb.enableAutoRange(axis=pg.ViewBox.XYAxes)
                if not hasattr(self, "viewbox_full_prof"):
                    prof_vb = self.prof_widget.getViewBox()
                    prof_vb.autoRange()
                    prof_vb.enableAutoRange(axis=pg.ViewBox.XYAxes)
            except Exception:
                pass

        # 保存済みの plot 設定（grid、ViewBox 状態）を再適用する
        self._apply_plot_settings()

    def _update_metadata(self):
        """画像ファイルの metadata を metadata tab に表示する。"""
        if not hasattr(self, "metadata_table"):
            return

        if self.image_path is None or not self.image_path:
            self.meta_tab.update([("Error", "No file path available")])
            self.last_metadata = []
            return

        try:
            metadata = get_image_metadata(self.image_path, self.image_array)

            if not metadata:
                self.meta_tab.update([("Info", "No metadata available")])
                self.last_metadata = []
                return

            # 基本情報、EXIF の順に並べる
            rows = []

            basic_keys = ["Filepath", "Format", "FileSize", "Size", "Channels", "DataType"]
            for key in basic_keys:
                if key in metadata:
                    value_str = str(metadata[key])
                    rows.append((key, value_str))

            exif_items = [(k, v) for k, v in metadata.items() if k not in basic_keys]
            for key, value in exif_items:
                value_str = str(value)
                rows.append((key, value_str))
                if key == "EXIF_ExposureTime":
                    # 露光時間を秒で併記する
                    exposure_time = eval(value)
                    rows.append((" -> (seconds)", f"{exposure_time:.3e}"))

            self.last_metadata = rows
            self.meta_tab.update(rows)

        except Exception as e:
            self.meta_tab.update([("Error", f"Error reading metadata: {e!s}")])
            self.last_metadata = []

    def hist_config_mode_toggle(self):
        if self.hist_config_mode == "Histogram":
            self.hist_config_mode = "ECDF"
            self.hist_config_mode_btn.setText("ECDF")
        else:
            self.hist_config_mode = "Histogram"
            self.hist_config_mode_btn.setText("Histogram")
        self.update_contents()

    def hist_config_reset(self):
        self._on_spinbox_changed(self.hist_tab.bin_step_spin_box_init)
        self.hist_tab.bin_step_spin_box.setValue(self.hist_tab.bin_step_spin_box_init)

    def copy_metadata_to_clipboard(self):
        """metadata をカンマ区切りで clipboard にコピーする。"""
        if not hasattr(self, "last_metadata") or not self.last_metadata:
            QMessageBox.information(self, "Copy", "No metadata to copy.")
            return

        lines = ["Key,Value"]
        for key, value in self.last_metadata:
            lines.append(f"{key},{value}")

        text = "\n".join(lines)
        QGuiApplication.clipboard().setText(text)

    def copy_histogram_to_clipboard(self):
        """histogram（または ECDF）のデータを CSV で clipboard にコピーする。"""
        if not getattr(self, "last_hist_data", None):
            QMessageBox.information(self, "Copy", "No data.")
            return

        keys = list(self.last_hist_data.keys())

        # 先頭の系列の x（bin の中心）を共通の x 軸として使う
        xs = np.array(self.last_hist_data[keys[0]][0]).flatten()

        if self.hist_config_mode == "Histogram":
            # bin 幅から各 bin の開始・終了位置を求める
            bin_width = np.diff(xs)[0] if len(xs) > 1 else 1.0
            bin_starts = xs - (bin_width / 2)
            bin_ends = xs + (bin_width / 2)

            csv_data = {"bin_start": bin_starts, "bin_end": bin_ends, "bin_center": xs}
            cast_int_keys = keys  # 度数は int で出力する

        elif self.hist_config_mode == "ECDF":
            csv_data = {"value": xs}
            cast_int_keys = None

        # 各系列の y を列として追加する
        for k in keys:
            csv_data[k] = np.array(self.last_hist_data[k][1]).flatten()

        text = series_to_csv(csv_data, cast_int_keys=cast_int_keys)
        QGuiApplication.clipboard().setText(text)

    def copy_profile_to_clipboard(self):
        """profile のデータを CSV で clipboard にコピーする。"""
        if not getattr(self, "last_profile_data", None):
            QMessageBox.information(self, "Copy", "No data.")
            return

        keys = list(self.last_profile_data.keys())
        xs = self.last_profile_data[keys[0]][0]

        csv_data = {"x address": xs} if self.profile_orientation == "h" else {"y address": xs}

        for k in keys:
            csv_data[k] = self.last_profile_data[k][1]

        text = series_to_csv(csv_data)
        QGuiApplication.clipboard().setText(text)

    def copy_hist_stats_to_clipboard(self):
        """ROI の統計量を CSV で clipboard にコピーする。"Target: All plane" の場合は全画像を対象にする。"""
        if not hasattr(self, "hist_stats_table"):
            QMessageBox.information(self, "Copy", "No histogram stats to copy.")
            return
        imgs = self.viewer.images
        current_id = self.viewer.current_index
        x, y, w, h = self.viewer.current_roi_rect.getRect()
        text = "path,ch,x_sta,y_sta,width,hight,mean,std,median,min,max,fano\n"

        targets = imgs if self.hist_get_all_plane_data.isChecked() else [imgs[current_id]]

        for img in targets:
            path = img.get("path")
            arr = img.get("base_array")
            height, width = arr.shape[:2]
            # ROI が画像の範囲外の場合は skip する
            if x > width or (x + w) > width or y > height or (y + h) > height:
                continue

            if arr.ndim == 2:
                arr = arr[:, :, np.newaxis]

            for ch in range(arr.shape[2]):
                data = arr[:, :, ch]
                data_roi = data[y : y + h, x : x + w]
                mean, std, median, min, max, fano = calc_stats(data_roi)
                text += f"{path},{ch},{x},{y},{w},{h},{mean},{std},{median},{min},{max},{fano}\n"
        QGuiApplication.clipboard().setText(text)

    def copy_prof_stats_to_clipboard(self):
        """ROI の profile の統計量を CSV で clipboard にコピーする。"Target: All plane" の場合は全画像を対象にする。"""
        if not hasattr(self, "prof_stats_table"):
            QMessageBox.information(self, "Copy", "No profile stats to copy.")
            return
        imgs = self.viewer.images
        current_id = self.viewer.current_index
        x, y, w, h = self.viewer.current_roi_rect.getRect()
        orientation = self.profile_orientation
        method = self.profile_compute_method
        text = "path,ch,x_sta,y_sta,width,hight,orientation,method,mean,std,median,min,max,fano\n"

        targets = imgs if self.prof_get_all_plane_data.isChecked() else [imgs[current_id]]

        for img in targets:
            path = img.get("path")
            arr = img.get("base_array")
            height, width = arr.shape[:2]
            # ROI が画像の範囲外の場合は skip する
            if x > width or (x + w) > width or y > height or (y + h) > height:
                continue

            if arr.ndim == 2:
                arr = arr[:, :, np.newaxis]

            for ch in range(arr.shape[2]):
                data = arr[:, :, ch]
                data_roi = data[y : y + h, x : x + w]
                prof_roi = compute_profile_1d(data_roi, orientation, method)
                mean, std, median, min, max, fano = calc_stats(prof_roi)
                text += f"{path},{ch},{x},{y},{w},{h},{orientation},{method},{mean},{std},{median},{min},{max},{fano}\n"
        QGuiApplication.clipboard().setText(text)

    def _on_prof_orientation_toggle(self):
        if self.profile_orientation == "h":
            self.profile_orientation = "v"
            self.prof_orientation_btn.setText("Vertical")
        else:
            self.profile_orientation = "h"
            self.prof_orientation_btn.setText("Horizontal")
        self.update_contents()

    def _on_prof_xmode_toggle(self):
        if self.x_mode == "relative":
            self.x_mode = "absolute"
            self.prof_xmode_btn.setText("Absolute")
        else:
            self.x_mode = "relative"
            self.prof_xmode_btn.setText("Relative")
        self.update_contents()

    def _on_prof_compute_method_combo(self):
        self.profile_compute_method = self.prof_compute_method_combo.currentText()
        self.update_contents()

    def _on_hist_chart_kind_combo(self):
        self.hist_chart_kind = self.hist_chart_kind_combo.currentText()
        if self.hist_chart_kind == "Bar":
            self.hist_bar_alpha_spin_box.setEnabled(True)
        else:
            self.hist_bar_alpha_spin_box.setEnabled(False)
        self.update_contents()

    def _on_external_log_toggled(self, checked: bool):
        # pyqtgraph の menu で log Y が切り替えられたら設定を保存して再描画する
        try:
            self.plot_settings.setdefault("hist", {})["log"] = bool(checked)
            self.update_contents()
        except Exception:
            pass

    def _connect_plotitem_controls(self, plot_item, which: str):
        pg_connect_plot_controls(
            plot_item,
            which,
            self.plot_settings,
            on_hist_log_changed=lambda: self._on_external_log_toggled(
                self.plot_settings.get("hist", {}).get("log", False)
            ),
        )

    def _apply_plot_settings(self):
        try:
            if hasattr(self, "hist_widget") and self.hist_widget is not None:
                pg_apply_plot_settings(
                    self.hist_widget, "hist", self.plot_settings, getattr(self, "viewbox_full_hist", None)
                )
            if hasattr(self, "prof_widget") and self.prof_widget is not None:
                pg_apply_plot_settings(
                    self.prof_widget, "prof", self.plot_settings, getattr(self, "viewbox_full_prof", None)
                )
        except Exception:
            pass

    def _save_viewbox_state(self, vb, which: str):
        try:
            full_state = pg_save_viewbox_state(vb)
            if full_state is not None:
                setattr(self, f"viewbox_full_{which}", full_state)
        except Exception:
            pass

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
