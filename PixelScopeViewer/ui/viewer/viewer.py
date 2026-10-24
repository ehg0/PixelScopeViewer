"""メインの画像ビューア window。"""

import contextlib
import json
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

import numpy as np
from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QGuiApplication,
    QIcon,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QStatusBar,
    QTabWidget,
    QWidget,
)

from PixelScopeViewer.core.colormap import apply_jet_colormap, flow_to_hsv_rgb
from PixelScopeViewer.core.constants import STANDARD_IMAGE_EXTENSIONS
from PixelScopeViewer.core.image_io import ImageLoaderRegistry, is_image_file, load_image
from PixelScopeViewer.ui.analysis import AnalysisDialog
from PixelScopeViewer.ui.annotations import AnnotationsDialog
from PixelScopeViewer.ui.annotations.model import AnnotationStore
from PixelScopeViewer.ui.common import defaults, theme
from PixelScopeViewer.ui.common.channel_display import MODE_1CH_JET, MODE_2CH_FLOW_HSV, ChannelDisplay
from PixelScopeViewer.ui.common.qt_image import numpy_to_qimage
from PixelScopeViewer.ui.common.state_dump import to_jsonable
from PixelScopeViewer.ui.diff import DiffDialog
from PixelScopeViewer.ui.tiling import TilingDialog
from PixelScopeViewer.ui.viewer.brightness_manager import BrightnessManager
from PixelScopeViewer.ui.viewer.help_dialog import HelpDialog
from PixelScopeViewer.ui.viewer.menu_builder import create_menus
from PixelScopeViewer.ui.viewer.state import ViewerState
from PixelScopeViewer.ui.viewer.status_updater import StatusUpdater
from PixelScopeViewer.ui.viewer.widgets import DisplayInfoWidget, ImageLabel, NavigatorWidget, ROIInfoWidget
from PixelScopeViewer.ui.viewer.zoom_manager import ZoomManager


class ImageViewer(QMainWindow):
    """画像の表示・切り替え・ROI 操作と、各解析 dialog の起動を行うメイン window。

    Attributes:
        images: 読み込んだ画像の dict（path, array, base_array, thumbnail_pixmap）のリスト。
        current_index: 表示中の画像の index。
        scale: 現在の zoom 倍率。
    """

    scale_changed = Signal()
    image_changed = Signal()
    roi_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PixelScopeViewer")
        self.resize(*defaults.MAIN_WINDOW_SIZE)
        self.setMouseTracking(True)

        self.images = []
        self.state = ViewerState()

        # window 状態（最小化など）を同期する子 dialog
        self._child_dialogs = []

        # zoom の中心に使うマウス位置（画像座標）
        self.current_mouse_image_coords = None

        # brightness 調整後の表示用配列の cache
        self._cached_display_array = None
        self._cached_display_params = None

        central = QWidget(self)
        self.setCentralWidget(central)
        h_layout = QHBoxLayout(central)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.image_label = ImageLabel(self, self)
        self.scroll_area.setWidget(self.image_label)
        h_layout.addWidget(self.scroll_area)
        self.image_label.installEventFilter(self)

        # 左側の dock
        self.navigator_dock = QDockWidget("Navigator")
        self.navigator_dock.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)
        self.navigator_widget = NavigatorWidget(self)
        self.navigator_dock.setWidget(self.navigator_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.navigator_dock)

        self.info_dock = QDockWidget("Info")
        self.info_dock.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)

        self.info_tabs = QTabWidget()

        display_info_widget = DisplayInfoWidget(self)
        self.info_tabs.addTab(display_info_widget, "Display Area")

        roi_info_widget = ROIInfoWidget(self)
        self.info_tabs.addTab(roi_info_widget, "ROI Area")

        self.info_dock.setWidget(self.info_tabs)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.info_dock)

        # status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.statusBar().setStyleSheet("font-size: 11pt;")
        self.status_pixel = QLabel()
        self.status_roi_area = QLabel()
        self.status_brightness = QLabel()
        self.status_scale = QLabel()

        left_container = QWidget()
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(15, 0, 15, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(self.status_pixel)
        left_layout.addWidget(QLabel("|"))
        left_layout.addWidget(self.status_roi_area)
        self.status.addWidget(left_container)

        right_container = QWidget()
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(15, 0, 15, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(QLabel("|"))
        right_layout.addWidget(self.status_brightness)
        right_layout.addWidget(QLabel("|"))
        right_layout.addWidget(self.status_scale)
        self.status.addPermanentWidget(right_container)

        self.help_dialog = HelpDialog(self)
        self.brightness_dialog = None  # 必要になったときに作成する

        self.zoom_manager = ZoomManager(self)
        self.brightness_manager = BrightnessManager(self)
        self.status_updater = StatusUpdater(self)

        self.annotations = AnnotationStore()
        self._annotations_dialog = None

        # channel の色・表示 ON/OFF・表示モードの唯一の持ち主。dialog にはこの instance を渡す
        self.channel_display = ChannelDisplay(self)
        self.channel_display.colors_changed.connect(self._on_channel_display_changed)
        self.channel_display.checks_changed.connect(self._on_channel_display_changed)
        self.channel_display.modes_changed.connect(self._on_channel_display_changed)

        create_menus(self)
        self.setAcceptDrops(True)
        # modeless dialog が GC されないよう参照を保持する
        self._analysis_dialog = None

    # channel の表示設定（channel_display から表示中の画像の channel 数に対応する値を読む）
    def _current_n_channels(self) -> int:
        if self.state.current_index is None:
            return 0
        arr = self.images[self.state.current_index]["array"]
        return arr.shape[2] if arr.ndim >= 3 else 0

    @property
    def channel_colors(self) -> list[QColor]:
        return self.channel_display.colors(self._current_n_channels())

    @property
    def channel_checks(self) -> list[bool]:
        return self.channel_display.checks(self._current_n_channels())

    def _on_channel_display_changed(self, *_):
        self._cached_display_array = None
        self._cached_display_params = None
        if self.state.current_index is not None:
            self.display_image(self.images[self.state.current_index]["array"])

    # zoom_manager への委譲
    def set_zoom(self, scale: float):
        self.zoom_manager.set_zoom(scale)

    def set_zoom_at_status_coords(self, scale: float):
        self.zoom_manager.set_zoom_at_status_coords(scale)

    def set_zoom_at_coords(self, scale: float, image_coords: tuple[float, float]):
        self.zoom_manager.set_zoom_at_coords(scale, image_coords)

    def fit_to_window(self):
        self.zoom_manager.fit_to_window()

    def toggle_fit_zoom(self):
        self.zoom_manager.toggle_fit_zoom()

    # brightness_manager への委譲
    def show_brightness_dialog(self):
        self.brightness_manager.show_brightness_dialog()

    def reset_brightness_settings(self):
        self.brightness_manager.reset_brightness_settings()

    def adjust_gain_step(self, amount):
        self.brightness_manager.adjust_gain_step(amount)

    def apply_brightness_adjustment(self, arr: np.ndarray) -> np.ndarray:
        return self.brightness_manager.apply_brightness_adjustment(arr)

    # status_updater への委譲
    def update_mouse_status(self, pos):
        self.status_updater.update_mouse_status(pos)

    def update_status(self):
        self.status_updater.update_status()

    def update_brightness_status(self):
        self.status_updater.update_brightness_status()

    # 画像の読み込みと切り替え
    def show_analysis_dialog(self, tab: str | None = None):
        """表示中の画像と ROI の解析 dialog を表示する。

        Args:
            tab: 表示する tab 名（前方一致）または index。
        """
        # QAction.triggered(bool) から渡される bool は無視する
        if isinstance(tab, bool):
            tab = None
        if self.state.current_index is None:
            QMessageBox.information(self, "解析", "画像が選択されていません。")
            return

        # 既に開いている場合は前面に出す
        if self._analysis_dialog is not None:
            if self._analysis_dialog.isMinimized():
                self._analysis_dialog.showNormal()
            self._analysis_dialog.raise_()
            self._analysis_dialog.activateWindow()
            if tab is not None:
                with contextlib.suppress(Exception):
                    self._analysis_dialog.set_current_tab(tab)
            return

        img = self.images[self.state.current_index]
        arr = img.get("base_array", img.get("array"))
        sel = self.state.roi
        img_path = img.get("path")
        dlg = AnalysisDialog(
            self, image_array=arr, image_rect=sel, image_path=img_path, channel_display=self.channel_display
        )
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        self._analysis_dialog = dlg
        self._child_dialogs.append(dlg)

        def on_closed():
            if dlg in self._child_dialogs:
                self._child_dialogs.remove(dlg)
            self._analysis_dialog = None

        dlg.finished.connect(on_closed)
        if tab is not None:
            with contextlib.suppress(Exception):
                dlg.set_current_tab(tab)

    def open_files(self):
        """ファイル選択 dialog から画像を読み込む。"""
        registry = ImageLoaderRegistry.get_instance()
        custom_exts, has_wildcard = registry.get_supported_extensions()

        exts = [*STANDARD_IMAGE_EXTENSIONS, *sorted(set(custom_exts) - set(STANDARD_IMAGE_EXTENSIONS))]
        all_exts = " ".join(f"*{ext}" for ext in exts)

        # wildcard loader がある場合は "All Files" を既定の filter にする
        if has_wildcard:
            filter_str = f"All Files (*.*);;Images ({all_exts})"
        else:
            filter_str = f"Images ({all_exts});;All Files (*.*)"

        files, _ = QFileDialog.getOpenFileNames(self, "画像を開く", "", filter_str)
        new_count = self._add_images(files)
        self._finalize_image_addition(new_count)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls()]
        image_files = [f for f in files if is_image_file(f)]
        annotation_files = [f for f in files if Path(f).suffix.lower() in (".json", ".csv")]

        new_count = self._add_images(image_files)
        self._finalize_image_addition(new_count)
        self.activateWindow()

        if annotation_files:
            try:
                self.annotations.load_annotation_files(annotation_files)
                # 特徴量 dialog を開き（既に開いていれば前面に出し）内容を反映する
                self.show_annotations_dialog()
                if self._annotations_dialog is not None:
                    with contextlib.suppress(Exception):
                        self._annotations_dialog.refresh_from_manager()
            except Exception:
                pass

    def _prepare_thumbnail_array(self, arr: np.ndarray) -> np.ndarray:
        """現在の 1ch/2ch 表示モードに合わせた thumbnail 用の配列を返す。"""
        if arr.ndim == 2 or (arr.ndim == 3 and arr.shape[2] == 1):
            # メイン表示と揃えるため brightness を適用する
            adj = self.apply_brightness_adjustment(arr)
            if self.channel_display.mode_1ch == MODE_1CH_JET:
                if adj.ndim == 3 and adj.shape[2] == 1:
                    adj = adj[..., 0]
                return apply_jet_colormap(adj)
            else:
                if adj.ndim == 3 and adj.shape[2] == 1:
                    adj = adj[..., 0]
                return adj

        if arr.ndim == 3 and arr.shape[2] == 2:
            if self.channel_display.mode_2ch == MODE_2CH_FLOW_HSV:
                # flow-hsv は brightness を適用せず元データから変換する
                rgb = flow_to_hsv_rgb(arr)
                return rgb
            else:
                # composite: brightness 適用後、channel の表示 ON/OFF と色で合成する
                adj = self.apply_brightness_adjustment(arr)
                h, w, c = adj.shape
                n = c
                checks = self.channel_display.checks(n)
                colors = self.channel_display.colors(n)
                selected = [i for i, ck in enumerate(checks) if ck]
                if not selected:
                    return np.zeros((h, w, 3), dtype=np.uint8)
                comp = np.zeros((h, w, 3), dtype=np.float32)
                for idx in selected:
                    if idx < n and idx < len(colors):
                        col = colors[idx]
                        r = col.red() / 255.0
                        g = col.green() / 255.0
                        b = col.blue() / 255.0
                        ch = adj[:, :, idx].astype(np.float32) / 255.0
                        comp[:, :, 0] += ch * r
                        comp[:, :, 1] += ch * g
                        comp[:, :, 2] += ch * b
                return np.clip(comp * 255.0, 0, 255).astype(np.uint8)

        return arr

    def _show_load_error(self, path: str, arr=None, error_msg: str = ""):
        """ファイルの詳細を添えて読み込みエラーを表示する。"""
        filename = Path(path).name
        details = f"ファイル名: {filename}"
        if arr is not None:
            details += f"\n配列形状: {arr.shape}\nデータ型: {arr.dtype}"
        elif Path(path).suffix.lower() == ".npy":
            try:
                arr = np.load(path)
                details += f"\n配列形状: {arr.shape}\nデータ型: {arr.dtype}"
            except Exception:
                pass
        if error_msg:
            details += f"\n\nエラー: {error_msg}"
        QMessageBox.warning(self, "画像読み込みエラー", details)

    def _show_bulk_load_errors(self, failed_files):
        """複数ファイルの読み込みエラーをまとめて表示する。"""
        if len(failed_files) == 1:
            path, error = failed_files[0]
            self._show_load_error(path, error_msg=error)
            return

        msg = f"{len(failed_files)}個のファイルの読み込みに失敗しました:\n\n"
        for path, error in failed_files[:5]:  # 先頭 5 件のみ表示する
            filename = Path(path).name
            error_short = error if len(error) < 60 else error[:57] + "..."
            msg += f"• {filename}\n  {error_short}\n\n"

        if len(failed_files) > 5:
            msg += f"... 他 {len(failed_files) - 5} 件\n\n"

        msg += "\nヒント: カスタムローダーを登録することで対応できる可能性があります。\n"
        msg += "詳細は custom_loaders/README.md を参照してください。"

        QMessageBox.warning(self, "画像読み込みエラー", msg)

    def _create_img_data(self, path: str, arr: np.array, failed_files: list) -> dict:
        """images に追加する dict を作成する。対応しない shape の場合は failed_files に追加して None を返す。"""
        if arr.ndim < 2 or arr.ndim > 3:
            failed_files.append((path, "2次元または3次元の配列が必要です"))
            return None
        if arr.ndim == 3 and arr.shape[2] not in [1, 2, 3, 4]:
            failed_files.append((path, "チャンネル数は1, 2, 3, または4である必要があります"))
            return None

        thumb_arr = self._prepare_thumbnail_array(arr)
        thumb_qimg = numpy_to_qimage(thumb_arr)
        thumb_pixmap = QPixmap.fromImage(thumb_qimg).scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        img_data = {
            "path": path,
            "array": arr,
            "base_array": arr.copy(),
            "thumbnail_pixmap": thumb_pixmap,
        }
        return img_data

    def _add_images(self, paths: Iterable[str]) -> int:
        """画像ファイルを読み込んで images に追加する。

        loader が dict を返した場合は、各値を別の画像として追加する。

        Returns:
            追加した画像の数。
        """
        new_images = []
        failed_files = []

        for path in paths or []:
            if not path:
                continue
            try:
                load_data = load_image(path)

                # custom loader が対応できなかった場合
                if load_data is None:
                    failed_files.append((path, "カスタムローダーで処理できませんでした"))
                    continue

                if not isinstance(load_data, dict):
                    arr = load_data
                    path_str = str(Path(path).resolve())
                    img_data = self._create_img_data(path_str, arr, failed_files)
                    if img_data is not None:
                        new_images.append(img_data)
                else:
                    for key, value in load_data.items():
                        arr = value
                        path_str = str(Path(path).resolve())
                        if key not in ("ORIGINAL", "ORIG", "SOURCE", "SRC"):
                            path_str += f"_{key}"
                        img_data = self._create_img_data(path_str, arr, failed_files)
                        if img_data is not None:
                            new_images.append(img_data)

            except Exception as e:
                failed_files.append((path, str(e)))
                continue

        if failed_files:
            self._show_bulk_load_errors(failed_files)

        if not new_images:
            return 0

        self.images.extend(new_images)
        return len(new_images)

    def _finalize_image_addition(self, new_count: int) -> None:
        """追加した画像の先頭を表示し、画像 menu を更新する。"""
        if new_count <= 0:
            return
        if self.state.current_index is None:
            self.state.current_index = 0
        else:
            self.state.current_index = len(self.images) - new_count
        self.show_current_image()
        self.update_image_list_menu()

    # ------------------------
    # 特徴量
    # ------------------------

    def show_annotations_dialog(self):
        if self._annotations_dialog is not None:
            # 最後に読み込んだファイルを title に反映する
            title = "特徴量表示"
            last_path = self.annotations.get_last_loaded_path()
            if last_path:
                title = f"特徴量表示 - {last_path}"
            self._annotations_dialog.setWindowTitle(title)
            if self._annotations_dialog.isMinimized():
                self._annotations_dialog.showNormal()
            self._annotations_dialog.raise_()
            self._annotations_dialog.activateWindow()
            return
        dlg = AnnotationsDialog(self, self.annotations)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        self._annotations_dialog = dlg
        self._child_dialogs.append(dlg)

        def on_closed():
            if dlg in self._child_dialogs:
                self._child_dialogs.remove(dlg)
            self._annotations_dialog = None

        dlg.finished.connect(on_closed)

    def update_image_list_menu(self):
        """画像 menu を読み込み済みの画像一覧で更新する。"""
        self.img_menu.clear()
        self.img_menu.addAction(self.next_image_action)
        self.img_menu.addAction(self.prev_image_action)
        self.img_menu.addSeparator()

        group = QActionGroup(self)
        group.setExclusive(True)
        for i, info in enumerate(self.images):
            act = QAction(info["path"], self)
            act.setCheckable(True)
            # triggered が発火しないよう、connect の前に check 状態と icon を設定する
            if i == self.state.current_index:
                act.setChecked(True)
                pix = QPixmap(12, 12)
                pix.fill(Qt.transparent)
                p = QPainter(pix)
                p.setBrush(QColor(theme.CURRENT_IMAGE_MARKER_COLOR))
                p.drawEllipse(2, 2, 8, 8)
                p.end()
                act.setIcon(QIcon(pix))
            act.triggered.connect(self.make_show_callback(i))
            group.addAction(act)
            self.img_menu.addAction(act)

    def make_show_callback(self, idx):
        """idx 番目の画像を表示する callback を返す。"""

        def fn(checked=None):
            self.state.current_index = idx
            if 0 <= idx < len(self.images):
                self.show_current_image()
            else:
                # 画像一覧が変わっている場合は menu を更新する
                self.update_image_list_menu()

        return fn

    def show_current_image(self):
        """current_index の画像を表示し、関連する widget と dialog を更新する。"""
        if self.state.current_index is None or not self.images:
            self.image_label.clear()
            self.update_status()
            return

        # 画像を切り替えたら fit zoom の状態と表示 cache を破棄する
        self.state.fit_zoom_scale = None
        self.state.original_zoom_scale = 1.0
        self.state.original_center_coords = None

        self._cached_display_array = None
        self._cached_display_params = None

        img = self.images[self.state.current_index]
        arr = img["array"]
        # dtype が切り替わった場合のみ、その dtype で保存した brightness を読み込む
        try:
            dtype_key = self.brightness_manager._dtype_key(arr.dtype)
            stored_params = self.state.brightness_by_dtype.get(dtype_key)

            if stored_params and stored_params != self.state.brightness:
                self.state.brightness = replace(stored_params)
                self.update_brightness_status()
        except Exception:
            pass
        self.display_image(arr)
        self.image_changed.emit()
        self.update_image_list_menu()

        # 非表示でも表示設定 dialog が存在すれば新しい画像に更新する
        if self.brightness_dialog is not None:
            img = self.images[self.state.current_index]
            arr_for_brightness = img.get("base_array", img.get("array"))
            img_path = img.get("path", None)
            self.brightness_dialog.update_for_new_image(
                arr_for_brightness,
                img_path,
                keep_settings=True,
                channel_checks=self.channel_checks,
                channel_colors=self.channel_colors,
                initial_mode_1ch=self.channel_display.mode_1ch,
                initial_mode_2ch=self.channel_display.mode_2ch,
            )

        try:
            img = self.images[self.state.current_index]
            arr_for_analysis = img.get("base_array", img.get("array"))
            img_path = img.get("path", None)
            if self._analysis_dialog:
                with contextlib.suppress(Exception):
                    self._analysis_dialog.set_image_and_rect(arr_for_analysis, self.state.roi, img_path)
        except Exception:
            pass

        if self.state.roi:
            s = self.state.scale
            rect = QRect(
                int(self.state.roi.x() * s),
                int(self.state.roi.y() * s),
                int(self.state.roi.width() * s),
                int(self.state.roi.height() * s),
            )
            self.image_label.roi_rect = rect
            self.image_label.update()

        if self._analysis_dialog:
            img = self.images[self.state.current_index] if self.state.current_index is not None else None
            if img:
                arr = img.get("base_array", img.get("array"))
                img_path = img.get("path")
                with contextlib.suppress(Exception):
                    self._analysis_dialog.set_image_and_rect(arr, self.state.roi, img_path)

    def _get_displayed_array(self) -> np.ndarray | None:
        """brightness・channel 合成・colormap を適用した表示用の配列を返す。"""
        if self.state.current_index is None:
            return None

        arr = self.images[self.state.current_index]["array"]

        # 表示に影響する parameter をすべて cache の key にする
        cache_key = (
            self.state.current_index,
            self.state.brightness.offset,
            self.state.brightness.gain,
            self.state.brightness.upper_level,
            tuple(self.channel_checks) if self.channel_checks else None,
            tuple(c.name() for c in self.channel_colors) if self.channel_colors else None,
            self.channel_display.mode_1ch,
            self.channel_display.mode_2ch,
        )

        if self._cached_display_params == cache_key and self._cached_display_array is not None:
            return self._cached_display_array

        # 疑似カラー表示（1ch の JET、2ch の flow-hsv）
        try:
            if arr.ndim == 2 or (arr.ndim == 3 and arr.shape[2] == 1):
                if self.channel_display.mode_1ch == MODE_1CH_JET:
                    adj = self.apply_brightness_adjustment(arr)
                    if adj.ndim == 3 and adj.shape[2] == 1:
                        adj = adj[..., 0]
                    result = apply_jet_colormap(adj)
                    self._cached_display_array = result
                    self._cached_display_params = cache_key
                    return result
            elif arr.ndim == 3 and arr.shape[2] == 2 and self.channel_display.mode_2ch == MODE_2CH_FLOW_HSV:
                result = flow_to_hsv_rgb(arr)
                self._cached_display_array = result
                self._cached_display_params = cache_key
                return result
        except Exception:
            # 通常の処理に fallback する
            pass

        apply_adjust = False
        if (
            np.issubdtype(arr.dtype, np.floating)
            or self.state.brightness.offset != 0
            or self.state.brightness.gain != 1.0
            or self.state.brightness.upper_level != 255
        ):
            apply_adjust = True

        if apply_adjust:
            arr = self.apply_brightness_adjustment(arr)

        # 表示する channel を選択した色で合成する
        channel_checks = self.channel_checks
        channel_colors = self.channel_colors
        if arr.ndim >= 3 and channel_checks:
            selected_channels = [i for i, checked in enumerate(channel_checks) if checked]
            if not selected_channels:
                return np.zeros((arr.shape[0], arr.shape[1], 3), dtype=np.uint8)

            composite = np.zeros((arr.shape[0], arr.shape[1], 3), dtype=np.float32)
            for channel_idx in selected_channels:
                if channel_idx < len(channel_colors):
                    color = channel_colors[channel_idx]
                    r, g, b = color.red() / 255.0, color.green() / 255.0, color.blue() / 255.0
                    channel_data = arr[:, :, channel_idx].astype(np.float32)
                    if arr.dtype == np.uint8:
                        channel_data /= 255.0
                    elif np.issubdtype(arr.dtype, np.floating):
                        channel_data = np.clip(channel_data, 0, 1)
                    elif np.issubdtype(arr.dtype, np.integer):
                        max_val = np.iinfo(arr.dtype).max
                        channel_data /= max_val
                    composite[:, :, 0] += channel_data * r
                    composite[:, :, 1] += channel_data * g
                    composite[:, :, 2] += channel_data * b
            result = (np.clip(composite, 0, 1) * 255).astype(np.uint8)
            self._cached_display_array = result
            self._cached_display_params = cache_key
            return result

        self._cached_display_array = arr
        self._cached_display_params = cache_key
        return arr

    def display_image(self, arr):
        """現在の zoom 倍率と表示設定で画像を表示する。"""
        processed_arr = self._get_displayed_array()
        if processed_arr is None:
            processed_arr = arr

        qimg = numpy_to_qimage(processed_arr)
        self.image_label.set_image(qimg, self.state.scale)
        self.update_status()

    def next_image(self):
        if not self.images:
            return
        self.state.current_index = (self.state.current_index + 1) % len(self.images)
        self.show_current_image()

    def prev_image(self):
        if not self.images:
            return
        self.state.current_index = (self.state.current_index - 1) % len(self.images)
        self.show_current_image()

    def close_current_image(self):
        """表示中の画像を閉じる。"""
        if self.state.current_index is None:
            return
        # memory を解放するため配列を明示的に削除する
        img_data = self.images[self.state.current_index]
        if "array" in img_data:
            del img_data["array"]
        if "base_array" in img_data:
            del img_data["base_array"]
        del self.images[self.state.current_index]
        if not self.images:
            self.state.current_index = None
            self.image_label.clear()
        else:
            self.state.current_index = min(self.state.current_index, len(self.images) - 1)
        self.show_current_image()

    def close_all_images(self):
        """すべての画像を閉じる。"""
        # memory を解放するため配列を明示的に削除する
        for img_data in self.images:
            if "array" in img_data:
                del img_data["array"]
            if "base_array" in img_data:
                del img_data["base_array"]
        self.images.clear()
        self.state.current_index = None
        self.image_label.clear()
        with contextlib.suppress(Exception):
            self.show_current_image()
        with contextlib.suppress(Exception):
            self.update_image_list_menu()
        if self._analysis_dialog:
            with contextlib.suppress(Exception):
                self._analysis_dialog.set_image_and_rect(None, None)

    def collect_state(self) -> dict:
        """viewer・channel 表示設定と、開いている解析 dialog・複数画像比較の現在値を集める。"""
        state = {
            "viewer": self.state,
            "channel_display": self.channel_display.snapshot(),
        }
        if self._analysis_dialog is not None:
            state["analysis"] = self._analysis_dialog.settings
        tiling = getattr(self, "_tiling_dialog", None)
        if tiling is not None and hasattr(tiling, "state"):
            state["tiling"] = tiling.state
        return to_jsonable(state)

    def copy_state_to_clipboard(self):
        """現在値を JSON で clipboard にコピーする。"""
        text = json.dumps(self.collect_state(), ensure_ascii=False, indent=2)
        QGuiApplication.clipboard().setText(text)
        self.statusBar().showMessage("現在の状態を clipboard にコピーしました", 3000)

    def reboot(self):
        # app が viewer を import しているため、循環 import を避けて関数内で import する
        from PixelScopeViewer.app import RESTART_EXIT_CODE

        QApplication.exit(RESTART_EXIT_CODE)

    def show_diff_dialog(self):
        """2 枚の画像の差分画像を作成して追加する。"""
        if len(self.images) < 2:
            QMessageBox.information(self, "差分", "比較する画像が2枚必要です。")
            return
        dlg = DiffDialog(self, image_list=self.images, default_offset=127)
        if dlg.exec() != QDialog.Accepted:
            return
        a_idx, b_idx, offset = dlg.get_result()
        if a_idx is None or b_idx is None:
            return
        a = self.images[a_idx]["array"]
        b = self.images[b_idx]["array"]
        try:
            diff = a - b + offset
            diff[diff < 0] = 0
        except Exception:
            QMessageBox.information(self, "差分", "差分の作成に失敗しました。画像サイズや型を確認してください。")
            return

        thumb_arr = self._prepare_thumbnail_array(diff)
        thumb_qimg = numpy_to_qimage(thumb_arr)
        thumb_pixmap = QPixmap.fromImage(thumb_qimg).scaled(
            self.navigator_widget.thumbnail_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        img_data = {
            "path": f"diff:{a_idx + 1}-{b_idx + 1}",
            "array": diff,
            "base_array": diff.copy(),
            "thumbnail_pixmap": thumb_pixmap,
        }
        self.images.append(img_data)
        self.state.current_index = len(self.images) - 1
        self.show_current_image()

    def show_tiling_comparison_dialog(self):
        """複数画像比較 dialog を表示する。"""
        if len(self.images) < 2:
            QMessageBox.information(self, "複数画像比較", "比較する画像が2枚以上必要です。")
            return
        # modeless で開き、GC されないよう参照を保持する
        if not hasattr(self, "_tiling_dialog") or self._tiling_dialog is None:
            self._tiling_dialog = TilingDialog(self, image_list=self.images)
            self._tiling_dialog.finished.connect(lambda: setattr(self, "_tiling_dialog", None))

        self._tiling_dialog.show()
        self._tiling_dialog.raise_()
        self._tiling_dialog.activateWindow()

    # ROI 操作
    def select_all(self):
        """画像全体を ROI にする。"""
        if self.state.current_index is None or not self.images:
            return
        self.image_label.set_roi_full()
        if self.image_label.roi_rect:
            self.on_roi_changed(self.image_label.roi_rect)

    def on_roi_changed(self, rect: QRect):
        """widget 座標の ROI を画像座標に変換して保存し、関連する widget と dialog に通知する。"""
        s = self.state.scale
        self.state.roi = QRect(
            int(rect.x() / s),
            int(rect.y() / s),
            int(rect.width() / s),
            int(rect.height() / s),
        )
        self.status_updater.update_roi_status()
        if self._analysis_dialog:
            img = self.images[self.state.current_index] if self.state.current_index is not None else None
            if img:
                arr = img.get("base_array", img.get("array"))
                img_path = img.get("path")
                with contextlib.suppress(Exception):
                    self._analysis_dialog.set_image_and_rect(arr, self.state.roi, img_path)

        self.roi_changed.emit()

    def copy_roi_to_clipboard(self):
        """表示中の画像の ROI（ROI がなければ全体）を表示倍率で clipboard にコピーする。"""
        if self.state.current_index is None:
            QMessageBox.information(self, "コピー", "画像がありません。")
            return

        displayed_arr = self._get_displayed_array()
        if displayed_arr is None:
            QMessageBox.information(self, "コピー", "表示されている画像データを取得できません。")
            return

        sel = self.state.roi
        if sel and not sel.isEmpty():
            x, y, w, h = sel.x(), sel.y(), sel.width(), sel.height()
            h_arr, w_arr = displayed_arr.shape[:2]
            if x < w_arr and y < h_arr:
                sub_arr = displayed_arr[y : y + h, x : x + w]
                qimg = numpy_to_qimage(sub_arr)
            else:
                qimg = None  # ROI が画像の範囲外
        else:
            qimg = numpy_to_qimage(displayed_arr)

        if qimg and not qimg.isNull():
            # viewer の表示倍率に nearest neighbor で拡大縮小する
            scaled_qimg = qimg.scaled(
                int(qimg.width() * self.state.scale),
                int(qimg.height() * self.state.scale),
                Qt.KeepAspectRatio,
                Qt.FastTransformation,
            )
            QGuiApplication.clipboard().setImage(scaled_qimg)
        else:
            QMessageBox.information(self, "コピー", "クリップボードにコピーする画像を作成できませんでした。")

    def set_roi_from_image_rect(self, rect_img: QRect):
        """画像座標で ROI を設定する。

        widget 座標を経由しないため、zoom 中でも丸め誤差なく反映される。
        """
        try:
            self.state.roi = rect_img
            s = self.state.scale
            rect_label = QRect(
                int(rect_img.x() * s),
                int(rect_img.y() * s),
                int(rect_img.width() * s),
                int(rect_img.height() * s),
            )
            self.image_label.roi_rect = rect_label
            self.image_label.update()

            if self._analysis_dialog:
                img = self.images[self.state.current_index] if self.state.current_index is not None else None
                if img:
                    arr = img.get("base_array", img.get("array"))
                    img_path = img.get("path")
                    with contextlib.suppress(Exception):
                        self._analysis_dialog.set_image_and_rect(arr, self.state.roi, img_path)
            self.roi_changed.emit()
        except Exception:
            self.roi_changed.emit()

    # event handler
    def changeEvent(self, event):
        # 最小化・復元を子 dialog にも反映する
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                for dlg in self._child_dialogs:
                    try:
                        if dlg.isVisible() and not dlg.isMinimized():
                            dlg.showMinimized()
                    except RuntimeError:
                        pass  # dialog は削除済み
            elif event.oldState() & Qt.WindowMinimized:
                for dlg in self._child_dialogs:
                    try:
                        if dlg.isMinimized():
                            dlg.showNormal()
                    except RuntimeError:
                        pass  # dialog は削除済み
        super().changeEvent(event)

    def mousePressEvent(self, event):
        # クリック時に子 dialog も前面に出す
        for dlg in self._child_dialogs:
            try:
                if dlg.isVisible() and not dlg.isMinimized():
                    dlg.raise_()
            except RuntimeError:
                pass  # dialog は削除済み
        super().mousePressEvent(event)

    def eventFilter(self, obj, event):
        if obj is self.image_label and event.type() == QEvent.MouseMove:
            self.update_mouse_status(event.position().toPoint())
            return False
        return super().eventFilter(obj, event)

    def keyPressEvent(self, e):
        # Esc で ROI を解除する
        if e.key() == Qt.Key_Escape:
            self.image_label.roi_rect = None
            self.image_label.update()
            return

        super().keyPressEvent(e)

    def closeEvent(self, event):
        # 子 window が残って操作不能にならないよう、modeless dialog をすべて閉じる
        try:
            if hasattr(self, "_tiling_dialog") and self._tiling_dialog is not None:
                self._tiling_dialog.close()
        except RuntimeError:
            pass  # Qt 側で削除済み

        try:
            if self.brightness_dialog and self.brightness_dialog.isVisible():
                self.brightness_dialog.close()
        except RuntimeError:
            pass

        try:
            if self._annotations_dialog and self._annotations_dialog.isVisible():
                self._annotations_dialog.close()
        except RuntimeError:
            pass

        try:
            if self._analysis_dialog and self._analysis_dialog.isVisible():
                self._analysis_dialog.close()
        except RuntimeError:
            pass

        try:
            if self.help_dialog and self.help_dialog.isVisible():
                self.help_dialog.close()
        except RuntimeError:
            pass

        event.accept()
