"""全 tile の histogram・profile を重ねて表示する、複数画像の解析 dialog。"""

import contextlib
from pathlib import Path

import numpy as np
from PySide6.QtGui import QBrush, QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidgetItem,
    QWidget,
)

from PixelScopeViewer.core.image_io import get_image_metadata

from ..analysis.core import determine_hist_bins
from ..analysis.core.compute import ecdf_series, get_profile_offset, histogram_series, histogram_stats, profile_series
from ..analysis.dialog import AnalysisDialog

try:
    import pyqtgraph as pg

    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False


class TilingComparisonDialog(AnalysisDialog):
    """全 tile の histogram・profile を色分けして重ね、metadata を比較表示する AnalysisDialog。

    Args:
        parent: 親の TilingComparisonDialog。
        tiles_data: array, rect（ROI）, path, index, color を持つ tile ごとの dict のリスト。
    """

    def __init__(self, parent=None, tiles_data: list[dict] | None = None):
        self.tiles_data = tiles_data or []

        # 基底クラスの __init__ が update_contents() を呼ぶため、使用する属性は super().__init__ の前に用意する
        self.overlay_channel_visibility: dict[int, list[bool]] = {}

        # 基底クラスには先頭の tile を渡す。ROI は update_contents() で適用するため image_rect は None にする
        if self.tiles_data:
            first_tile = self.tiles_data[0]
            image_array = first_tile["array"]
            image_path = first_tile.get("path")
        else:
            image_array = None
            image_path = None

        # 重ね描きの色（Tableau 20）
        self.TABLEAU20: list[tuple[int, int, int]] = [
            (31, 119, 180),
            (174, 199, 232),
            (255, 127, 14),
            (255, 187, 120),
            (44, 160, 44),
            (152, 223, 138),
            (214, 39, 40),
            (255, 152, 150),
            (148, 103, 189),
            (197, 176, 213),
            (140, 86, 75),
            (196, 156, 148),
            (227, 119, 194),
            (247, 182, 210),
            (127, 127, 127),
            (199, 199, 199),
            (188, 189, 34),
            (219, 219, 141),
            (23, 190, 207),
            (158, 218, 229),
        ]
        self.overlay_color_map: dict[str, tuple[int, int, int]] = {}
        self.hist_plot_items: dict[str, object] = {}
        self.profile_plot_items: dict[str, object] = {}

        super().__init__(parent=parent, image_array=image_array, image_rect=None, image_path=image_path)

        self.setWindowTitle("複数画像比較 - 解析ビュー(複数画像)")

        # tab の channel の checkbox を tile ごとの checkbox に置き換える
        self._setup_overlay_channel_checkboxes()

    # ---- 色 ----
    def _assign_overlay_colors(self, labels: list[str]):
        """'Tile {n} C{k}' 形式の label に、tile 番号と channel から決まる Tableau 20 の色を割り当てる。"""
        for lbl in labels:
            if lbl in self.overlay_color_map:
                continue
            parts = lbl.split()
            tile_num = 1
            ch_index = 0
            try:
                if len(parts) >= 3 and parts[0] == "Tile":
                    tile_num = int(parts[1])
                    ch_code = parts[2]
                    ch_index = int(ch_code[1:]) if ch_code.startswith("C") else 0
                else:
                    # 形式が異なる場合は数字と C{k} を探す
                    for p in parts:
                        if p.isdigit():
                            tile_num = int(p)
                            break
                    for p in parts:
                        if p.startswith("C") and p[1:].isdigit():
                            ch_index = int(p[1:])
                            break
            except Exception:
                tile_num = 1
                ch_index = 0
            idx = ((tile_num - 1) * 8 + ch_index) % len(self.TABLEAU20)
            self.overlay_color_map[lbl] = self.TABLEAU20[idx]
        return {lbl: self.overlay_color_map[lbl] for lbl in labels}

    def _make_pen(self, rgb: tuple[int, int, int], *, width: int = 2, alpha: int = 255):
        r, g, b = rgb
        return pg.mkPen(color=(r, g, b, alpha), width=width)

    def update_tiles_data(self, tiles_data: list[dict]):
        """tile のデータを更新して表示を作り直す。"""
        self.tiles_data = tiles_data

        if self.tiles_data:
            first_tile = self.tiles_data[0]
            self.set_image_and_rect(first_tile["array"], first_tile.get("rect"), first_tile.get("path"))
        else:
            self.set_image_and_rect(None, None, None)

    def _update_metadata(self):
        """全 tile の metadata を比較する table を表示する。"""
        if not hasattr(self, "metadata_table"):
            return

        if not self.tiles_data:
            self.meta_tab.update([("Info", "No tiles available")])
            return

        all_metadata = []
        for tile_data in self.tiles_data:
            path = tile_data.get("path")
            arr = tile_data.get("array")

            metadata = {}

            if path:
                with contextlib.suppress(Exception):
                    metadata = get_image_metadata(path, arr) or {}

            # 基本情報は配列から必ず設定する
            if arr is not None:
                h, w = arr.shape[:2]
                metadata["Size"] = f"{w} x {h}"
                if arr.ndim == 3:
                    metadata["Channels"] = arr.shape[2]
                elif arr.ndim == 2:
                    metadata["Channels"] = 1
                metadata["DataType"] = str(arr.dtype)

            all_metadata.append({"index": tile_data["index"], "path": path, "metadata": metadata})

        if not all_metadata:
            self.meta_tab.update([("Info", "No metadata available")])
            return

        self._build_comparison_table(all_metadata)

    def _build_comparison_table(self, all_metadata: list[dict]):
        """tile ごとの metadata を列に並べ、値が異なる行を強調表示する。"""
        all_keys = set()
        for tile_meta in all_metadata:
            all_keys.update(tile_meta["metadata"].keys())

        # メインビューアと同じく基本情報、EXIF の順に並べる
        basic_keys = ["Filepath", "Format", "FileSize", "Size", "Channels", "DataType"]
        sorted_keys = [k for k in basic_keys if k in all_keys]
        exif_keys = sorted([k for k in all_keys if k not in basic_keys])
        sorted_keys.extend(exif_keys)

        num_tiles = len(all_metadata)
        num_rows = len(sorted_keys)

        self.metadata_table.setColumnCount(1 + num_tiles)

        headers = ["Property"]
        for tile_meta in all_metadata:
            tile_idx = tile_meta["index"] + 1
            path = tile_meta["path"]
            if path:
                filename = Path(path).name
                headers.append(f"Tile {tile_idx}\n{filename}")
            else:
                headers.append(f"Tile {tile_idx}\n(no file)")

        self.metadata_table.setHorizontalHeaderLabels(headers)
        self.metadata_table.setRowCount(num_rows)
        self.metadata_table.setMouseTracking(True)

        diff_color = QColor(255, 255, 200)

        for row_idx, key in enumerate(sorted_keys):
            prop_item = QTableWidgetItem(key)
            self.metadata_table.setItem(row_idx, 0, prop_item)

            values = []
            for tile_meta in all_metadata:
                value = tile_meta["metadata"].get(key, "")
                values.append(str(value) if value else "")

            # 空でない値が tile 間で異なる行を強調表示する
            unique_values = {v for v in values if v}
            has_difference = len(unique_values) > 1

            should_highlight = has_difference

            for col_idx, value in enumerate(values):
                value_item = QTableWidgetItem(value)

                if should_highlight and value:
                    value_item.setBackground(QBrush(diff_color))

                value_item.setToolTip(str(value))
                self.metadata_table.setItem(row_idx, col_idx + 1, value_item)

        header = self.metadata_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for i in range(1, 1 + num_tiles):
            header.setSectionResizeMode(i, QHeaderView.Stretch)

    def update_contents(self):
        """全 tile の ROI のデータを集計して重ね描きする。"""
        self._update_metadata()

        if not self.tiles_data:
            return
        if not PYQTGRAPH_AVAILABLE:
            return

        # ROI を適用した tile ごとの配列
        valid_tiles = []
        for tile_data in self.tiles_data:
            arr = tile_data["array"]
            if arr is None:
                continue

            roi_rect = tile_data.get("rect")
            if roi_rect is not None:
                x, y, w, h = (
                    int(roi_rect.x()),
                    int(roi_rect.y()),
                    int(roi_rect.width()),
                    int(roi_rect.height()),
                )
                arr = arr[y : y + h, x : x + w]
            else:
                arr = arr[0:1, 0:1]

            if arr.size == 0:
                continue

            valid_tiles.append(
                {
                    "array": arr,
                    "index": tile_data["index"],
                    "color": tile_data["color"],
                    "rect": roi_rect,
                }
            )

        if not valid_tiles:
            return

        # 基底クラスの処理用に先頭の tile の配列を設定する
        self.image_array = valid_tiles[0]["array"]
        self.image_rect = None  # ROI は適用済み

        first_arr = valid_tiles[0]["array"]
        if first_arr.ndim == 3 and first_arr.shape[2] > 1:
            nch = first_arr.shape[2]
            if not self.channel_checks:
                self.channel_checks = [True] * nch
            elif len(self.channel_checks) < nch:
                self.channel_checks.extend([True] * (nch - len(self.channel_checks)))

        self._ensure_overlay_channel_visibility(valid_tiles)

        self._update_histogram_overlay(valid_tiles)
        self._update_profile_overlay(valid_tiles)

        self._setup_overlay_channel_checkboxes()

    def _update_histogram_overlay(self, valid_tiles):
        """全 tile の histogram を共通の x 軸に揃えて重ね描きする。"""
        if not valid_tiles:
            return

        all_hist_series = {}  # tile index -> {label -> (xs, ys)}
        all_stats = []  # 表示 ON の channel の統計量

        for tile in valid_tiles:
            arr = tile["array"]
            tile_idx = tile["index"]
            visibility = self.overlay_channel_visibility.get(tile_idx)

            if self.hist_config_mode == "Histogram":
                bins = determine_hist_bins(arr, self.spinbox_value)
                hist_series = histogram_series(arr, bins=bins)
            elif self.hist_config_mode == "ECDF":
                hist_series = ecdf_series(arr)
            stats = histogram_stats(arr, self.channel_checks)

            tile_hist_series = {}
            for label, (xs, ys) in hist_series.items():
                channel_code = label
                ch_visible = True
                if visibility is not None:
                    if label.startswith("C"):
                        try:
                            cindex = int(label[1:])
                            if cindex < len(visibility):
                                ch_visible = visibility[cindex]
                        except Exception:
                            ch_visible = True
                    elif label == "I" and len(visibility) > 0:
                        ch_visible = visibility[0]
                if ch_visible:
                    new_label = f"Tile {tile_idx + 1} {channel_code}"
                    tile_hist_series[new_label] = (xs, ys)
            all_hist_series[tile_idx] = tile_hist_series

            for stat in stats:
                stat_ch_index = 0
                try:
                    stat_ch_index = int(stat["ch"])
                except Exception:
                    stat_ch_index = 0
                stat_visible = True
                if visibility is not None and stat_ch_index < len(visibility):
                    stat_visible = visibility[stat_ch_index]
                if stat_visible:
                    stat_copy = stat.copy()
                    # label は常に C{index}（1ch は C0）
                    stat_label = f"C{stat_ch_index}"
                    curve_label = f"Tile {tile_idx + 1} {stat_label}"
                    stat_copy["ch"] = f"T{tile_idx + 1}_C{stat_ch_index}"
                    stat_copy["curve_label"] = curve_label
                    all_stats.append(stat_copy)

        # 全 tile の x の和集合（前後 1 step を含む）を共通の x 軸にする
        all_xs = []
        for series in all_hist_series.values():
            for xs, _ in series.values():
                xs = np.asarray(xs)
                dx = xs[1] - xs[0] if len(xs) > 1 else 1.0
                xs_extended = np.concatenate([xs, xs - dx, xs + dx])
                all_xs.append(xs_extended)
        x_common = np.array([]) if len(all_xs) == 0 else np.unique(np.concatenate(all_xs))

        merged_series = {}
        for series in all_hist_series.values():
            for label, data in series.items():
                xs, ys = data
                if self.hist_config_mode == "ECDF":
                    # ECDF は np.interp で欠けている x を前後の累積確率で補間する
                    if len(xs) > 0:
                        ys_new = np.interp(x_common, xs, ys, left=0.0, right=1.0)
                    else:
                        ys_new = np.zeros_like(x_common, dtype=float)
                else:
                    ys_new = np.zeros_like(x_common, dtype=ys.dtype)
                    indices = np.searchsorted(x_common, xs)
                    valid = (indices >= 0) & (indices < len(x_common))
                    ys_new[indices[valid]] = ys[valid]
                merged_series[label] = (x_common, ys_new)

        ordered_labels = list(merged_series.keys())
        palette_map = self._assign_overlay_colors(ordered_labels)

        apply_log = self.plot_settings.get("hist", {}).get("log", False)

        if self.hist_tab.hist_widget:
            self.hist_tab.hist_widget.clear()
            self.hist_plot_items.clear()
            if merged_series:
                for label, (xs, ys) in merged_series.items():
                    yplot = np.array(ys, dtype=float)
                    if apply_log:
                        # 0 を 0.1 に置き換え、log10(0.1) = -1 として下端に表示する
                        yplot[yplot == 0] = 0.1
                        self.hist_tab.hist_widget.setLimits(yMin=-1)

                    rgb = palette_map.get(label, (127, 127, 127))
                    if self.hist_chart_kind == "Line":
                        pen = self._make_pen(rgb, width=2, alpha=255)
                        item = self.hist_tab.hist_widget.plot(xs, yplot, pen=pen, name=label)

                    if self.hist_chart_kind == "Bar":
                        pen = self._make_pen(rgb, width=2, alpha=self.spinbox_bar_alpha_value)
                        item = pg.BarGraphItem(
                            x=xs, height=yplot, width=self.spinbox_value, brush=pen.color(), pen=None, name=label
                        )
                        self.hist_tab.hist_widget.addItem(item)
                    self.hist_plot_items[label] = item
                self.hist_tab.hist_widget.setTitle(
                    f"{self.hist_config_mode} Overlay (All Tiles)", color="#2c3e50", size="12pt"
                )
            else:
                self.hist_tab.hist_widget.setTitle(
                    f"{self.hist_config_mode} Overlay (No channels visible)", color="#7f8c8d", size="11pt"
                )

        self.hist_tab._populate_stats_table(all_stats)

        # コピー用（表示中の系列のみ）
        self.last_hist_data = merged_series

    def _update_profile_overlay(self, valid_tiles):
        """全 tile の profile を重ね描きする。"""
        all_prof_series = {}  # tile index -> {label -> (xs, ys)}
        all_profile_stats = []

        for tile in valid_tiles:
            arr = tile["array"]
            tile_idx = tile["index"]
            roi_rect = tile.get("rect")
            visibility = self.overlay_channel_visibility.get(tile_idx)

            pseries = profile_series(arr, orientation=self.profile_orientation, method=self.profile_compute_method)

            tile_prof_series = {}
            for label, prof in pseries.items():
                if self.x_mode == "absolute" and roi_rect is not None:
                    offset = get_profile_offset(roi_rect, self.profile_orientation)
                    xs = np.arange(prof.size) + offset
                else:
                    xs = np.arange(prof.size)

                ch_visible = True
                if visibility is not None:
                    if label.startswith("C"):
                        try:
                            cindex = int(label[1:])
                            if cindex < len(visibility):
                                ch_visible = visibility[cindex]
                        except Exception:
                            ch_visible = True
                    elif label == "I" and len(visibility) > 0:
                        ch_visible = visibility[0]

                if ch_visible:
                    channel_code = label
                    new_label = f"Tile {tile_idx + 1} {channel_code}"
                    tile_prof_series[new_label] = (xs, prof)
                    is_int = np.issubdtype(prof.dtype, np.integer)
                    all_profile_stats.append(
                        {
                            "ch": f"T{tile_idx + 1}_C{0 if label == 'I' else int(label[1:])}",
                            "mean": float(prof.mean()) if prof.size else 0.0,
                            "std": float(prof.std()) if prof.size else 0.0,
                            "median": float(np.median(prof)) if prof.size else 0.0,
                            "min": float(prof.min()) if prof.size else 0.0,
                            "max": float(prof.max()) if prof.size else 0.0,
                            "fano": float(prof.std() ** 2 / prof.mean()) if prof.size else 0.0,
                            "is_int": bool(is_int),
                            "curve_label": new_label,
                        }
                    )

            all_prof_series[tile_idx] = tile_prof_series

        merged_series = {}
        for series in all_prof_series.values():
            for label, data in series.items():
                merged_series[label] = data

        ordered_prof_labels = list(merged_series.keys())
        prof_palette_map = self._assign_overlay_colors(ordered_prof_labels)

        if hasattr(self, "prof_widget") and self.prof_widget:
            self.prof_widget.clear()
            self.profile_plot_items.clear()
            orientation_label = {"h": "Horizontal", "v": "Vertical"}[self.profile_orientation]
            mode_label = "Absolute" if self.x_mode == "absolute" else "Relative"
            method_label = {
                "mean": "Mean",
                "std": "Std",
                "max": "Max",
                "min": "Min",
                "p2p": "Peak-to-Peak",
                "median": "Median",
            }[self.profile_compute_method]
            if merged_series:
                for label, (xs, ys) in merged_series.items():
                    rgb = prof_palette_map.get(label, (127, 127, 127))
                    pen = self._make_pen(rgb, width=2, alpha=255)
                    item = self.prof_widget.plot(xs, ys, pen=pen, name=label)
                    self.profile_plot_items[label] = item
                self.prof_widget.setTitle(
                    f"Profile Overlay (All Tiles) - {orientation_label} / {mode_label} / {method_label}",
                    color="#2c3e50",
                    size="12pt",
                )
            else:
                self.prof_widget.setTitle(
                    f"Profile Overlay (No channels visible)  - {orientation_label} / {mode_label} / {method_label}",
                    color="#7f8c8d",
                    size="11pt",
                )

        if hasattr(self, "profile_tab"):
            self.profile_tab._populate_stats_table(all_profile_stats)

        self.last_profile_data = merged_series

    # ---- tile ごとの channel の表示 ON/OFF ----
    def _ensure_overlay_channel_visibility(self, valid_tiles):
        for tile in valid_tiles:
            idx = tile["index"]
            arr = tile["array"]
            if idx not in self.overlay_channel_visibility:
                if arr.ndim == 3:
                    self.overlay_channel_visibility[idx] = [True] * arr.shape[2]
                else:
                    self.overlay_channel_visibility[idx] = [True]

    def _setup_overlay_channel_checkboxes(self):
        """histogram・profile tab の channel の checkbox を、tile ごとの checkbox に置き換える。"""
        if hasattr(self, "hist_tab"):
            self._replace_tab_channel_ui(self.hist_tab)

        if hasattr(self, "profile_tab"):
            self._replace_tab_channel_ui(self.profile_tab)

    def _replace_tab_channel_ui(self, tab):
        """tab の scroll area の中身を tile ごとの checkbox にし、その上に全選択・全解除の button を置く。"""
        # 削除済みの widget を参照しないよう、毎回 tab から探す
        scroll_area = tab.findChild(QScrollArea)
        if scroll_area is None:
            return
        scroll_widget = scroll_area.widget()
        if scroll_widget is None:
            return

        parent_layout = scroll_area.parent().layout() if scroll_area.parent() else None
        if parent_layout is None:
            return

        btn_row_name = "overlay_btn_row_hist" if tab is getattr(self, "hist_tab", None) else "overlay_btn_row_prof"

        btn_row_widget = None
        for idx in range(parent_layout.count()):
            item = parent_layout.itemAt(idx)
            w = item.widget()
            if w is not None and w.objectName() == btn_row_name:
                btn_row_widget = w
                break
        if btn_row_widget is None:
            btn_row_widget = QWidget(scroll_area.parent())
            btn_row_widget.setObjectName(btn_row_name)
            btn_layout = QHBoxLayout(btn_row_widget)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            select_all_btn = QPushButton("全選択", btn_row_widget)
            select_all_btn.setObjectName(btn_row_name + "_select")
            clear_all_btn = QPushButton("全解除", btn_row_widget)
            clear_all_btn.setObjectName(btn_row_name + "_clear")
            select_all_btn.setMaximumWidth(80)
            clear_all_btn.setMaximumWidth(80)
            btn_layout.addWidget(select_all_btn)
            btn_layout.addWidget(clear_all_btn)

            insert_index = 0
            for idx in range(parent_layout.count()):
                if parent_layout.itemAt(idx).widget() == scroll_area:
                    insert_index = idx
                    break
            parent_layout.insertWidget(insert_index, btn_row_widget)

        layout = scroll_widget.layout()
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        checkbox_meta = []
        for tile_idx, vis_list in sorted(self.overlay_channel_visibility.items()):
            tile_label = QLabel(f"Tile {tile_idx + 1}")
            tile_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
            layout.addWidget(tile_label)
            for ch_idx, enabled in enumerate(vis_list):
                if len(vis_list) > 1:
                    channel_code = f"C{ch_idx}"
                    label_text = f"{channel_code}"
                else:
                    channel_code = "I"
                    label_text = "Intensity"
                curve_label = f"Tile {tile_idx + 1} {channel_code}"
                self._assign_overlay_colors([curve_label])
                rgb = self.overlay_color_map.get(curve_label, (127, 127, 127))
                cbx = QCheckBox(label_text)
                pix = QPixmap(14, 14)
                pix.fill(QColor(*rgb))
                cbx.setIcon(pix)
                cbx.setIconSize(pix.size())
                cbx.setChecked(enabled)
                cbx.toggled.connect(
                    lambda checked, t=tile_idx, c=ch_idx: self._on_overlay_channel_toggled(t, c, checked)
                )
                layout.addWidget(cbx)
                checkbox_meta.append((tile_idx, ch_idx, cbx))

        layout.addStretch()

        select_btn = btn_row_widget.findChild(QPushButton, btn_row_name + "_select")
        clear_btn = btn_row_widget.findChild(QPushButton, btn_row_name + "_clear")
        if select_btn is not None and clear_btn is not None and not btn_row_widget.property("wired"):
            select_btn.clicked.connect(lambda: self._apply_all_in_tab(tab, True))
            clear_btn.clicked.connect(lambda: self._apply_all_in_tab(tab, False))
            btn_row_widget.setProperty("wired", True)

    def _apply_all_in_tab(self, tab, value: bool):
        scroll_area = tab.findChild(QScrollArea)
        if scroll_area is None:
            return
        sw = scroll_area.widget()
        if sw is None:
            return
        for cb in sw.findChildren(QCheckBox):
            if cb.isChecked() != value:
                cb.setChecked(value)

    def _on_overlay_channel_toggled(self, tile_idx: int, ch_idx: int, checked: bool):
        vis = self.overlay_channel_visibility.get(tile_idx)
        if vis is None or ch_idx < 0 or ch_idx >= len(vis):
            return
        vis[ch_idx] = bool(checked)
        self.update_contents()
