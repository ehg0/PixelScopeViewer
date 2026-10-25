"""メインの画像ビューア window。"""

import contextlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
)
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.core.brightness import determine_dtype_group
from PixelScopeViewer.core.image_io import is_image_file
from PixelScopeViewer.core.render import render_display, render_thumbnail
from PixelScopeViewer.ui.analysis import AnalysisDialog
from PixelScopeViewer.ui.annotations import AnnotationsDialog
from PixelScopeViewer.ui.annotations.model import AnnotationStore
from PixelScopeViewer.ui.common import defaults
from PixelScopeViewer.ui.common.channel_display import MODE_1CH_JET, MODE_2CH_FLOW_HSV, ChannelDisplay
from PixelScopeViewer.ui.common.qt_image import numpy_to_qimage
from PixelScopeViewer.ui.common.state_dump import to_jsonable
from PixelScopeViewer.ui.common.window import ChildDialogs, bring_to_front
from PixelScopeViewer.ui.tiling import TilingDialog
from PixelScopeViewer.ui.viewer.brightness_manager import BrightnessManager
from PixelScopeViewer.ui.viewer.help_dialog import HelpDialog
from PixelScopeViewer.ui.viewer.image_list import ImageListManager
from PixelScopeViewer.ui.viewer.menu_builder import create_menus
from PixelScopeViewer.ui.viewer.roi_list import RoiListManager
from PixelScopeViewer.ui.viewer.state import ViewerState
from PixelScopeViewer.ui.viewer.status_updater import StatusUpdater
from PixelScopeViewer.ui.viewer.widgets import (
    DisplayInfoWidget,
    ImageLabel,
    NavigatorWidget,
    ROIInfoWidget,
    RoiListWidget,
)
from PixelScopeViewer.ui.viewer.zoom_manager import ZoomManager


class ImageViewer(QMainWindow):
    """画像の表示・切り替え・ROI 操作と、各解析 dialog の起動を行うメイン window。

    Attributes:
        images: 読み込んだ画像の dict（path, array, base_array, thumbnail_pixmap）のリスト。
        state: 表示中の画像の index・zoom 倍率・ROI・brightness などの現在値。
        image_list: 画像の読み込み・切り替え・閉じる操作。
        roi_list: ROI 一覧の登録・削除・連動・保存と読み込み。
        status_updater: status bar の作成と表示の更新。
    """

    scale_changed = Signal()
    image_changed = Signal()
    roi_changed = Signal()
    # ROI 一覧（登録・削除・☑・連動・色の個別設定）の変更
    rois_changed = Signal()

    def __init__(self):
        super().__init__()
        # 最小化・復元・前面表示・close を連動させる子 dialog。changeEvent は __init__ 中にも届くため最初に作る
        self.child_dialogs = ChildDialogs()
        self.setWindowTitle("PixelScopeViewer")
        self.resize(*defaults.MAIN_WINDOW_SIZE)
        self.setMouseTracking(True)

        self.images = []
        self.state = ViewerState()
        self.roi_list = RoiListManager(self)

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

        # 編集中 ROI の座標の下に ROI 一覧を並べる
        roi_area = QWidget()
        roi_area_layout = QVBoxLayout(roi_area)
        roi_area_layout.setContentsMargins(0, 0, 0, 0)
        roi_area_layout.addWidget(ROIInfoWidget(self))
        roi_area_layout.addWidget(RoiListWidget(self), 1)
        self.info_tabs.addTab(roi_area, "ROI Area")

        self.info_dock.setWidget(self.info_tabs)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.info_dock)

        # status bar（左: pixel 値・ROI、右: brightness・zoom 倍率）
        self.status_updater = StatusUpdater(self)

        self.help_dialog = HelpDialog(self)
        self.brightness_dialog = None  # 必要になったときに作成する

        self.zoom_manager = ZoomManager(self)
        self.brightness_manager = BrightnessManager(self)
        self.image_list = ImageListManager(self)

        self.annotations = AnnotationStore()
        self._annotations_dialog = None

        # channel の色・表示 ON/OFF・表示モードの唯一の持ち主。dialog にはこの instance を渡す
        self.channel_display = ChannelDisplay(self)
        self.channel_display.colors_changed.connect(self._on_channel_display_changed)
        self.channel_display.checks_changed.connect(self._on_channel_display_changed)
        self.channel_display.modes_changed.connect(self._on_channel_display_changed)

        self.rois_changed.connect(self._update_analysis_dialog)

        create_menus(self)
        self.setAcceptDrops(True)
        # modeless dialog が GC されないよう参照を保持する
        self._analysis_dialog = None
        self._tiling_dialog = None

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

    # 表示
    def show_current_image(self):
        """current_index の画像を表示し、関連する widget と dialog を更新する。"""
        if self.state.current_index is None or not self.images:
            self.image_label.clear()
            self.status_updater.update_status()
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
        stored_params = self.state.brightness_by_dtype[determine_dtype_group(arr)]
        if stored_params != self.state.brightness:
            self.state.brightness = replace(stored_params)
            self.status_updater.update_brightness_status()
        self.display_image(arr)
        self.image_changed.emit()
        self.image_list.update_menu()

        # 非表示でも表示設定 dialog が存在すれば新しい画像に更新する
        base_arr = img.get("base_array", arr)
        img_path = img.get("path")
        if self.brightness_dialog is not None:
            self.brightness_dialog.update_for_new_image(
                base_arr,
                img_path,
                keep_settings=True,
                channel_checks=self.channel_checks,
                channel_colors=self.channel_colors,
                initial_mode_1ch=self.channel_display.mode_1ch,
                initial_mode_2ch=self.channel_display.mode_2ch,
            )

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

        self._update_analysis_dialog()

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

        b = self.state.brightness
        result = render_display(
            arr,
            self.brightness_manager.apply_brightness_adjustment,
            brightness_changed=(b.offset, b.gain, b.upper_level) != (0, 1.0, 255),
            **self._render_options(arr),
        )
        self._cached_display_array = result
        self._cached_display_params = cache_key
        return result

    def display_image(self, arr):
        """現在の zoom 倍率と表示設定で画像を表示する。"""
        processed_arr = self._get_displayed_array()
        if processed_arr is None:
            processed_arr = arr

        qimg = numpy_to_qimage(processed_arr)
        self.image_label.set_image(qimg, self.state.scale)
        self.status_updater.update_status()

    def _render_options(self, arr: np.ndarray) -> dict:
        """表示モードと、arr の channel 数に対応する channel の表示 ON/OFF・色を返す。"""
        n = arr.shape[2] if arr.ndim >= 3 else 0
        d = self.channel_display
        return {
            "jet": d.mode_1ch == MODE_1CH_JET,
            "flow_hsv": d.mode_2ch == MODE_2CH_FLOW_HSV,
            "checks": d.checks(n),
            "colors_rgb": [c.getRgb()[:3] for c in d.colors(n)],
        }

    def prepare_thumbnail_array(self, arr: np.ndarray) -> np.ndarray:
        """現在の 1ch/2ch 表示モードに合わせた thumbnail 用の配列を返す。"""
        return render_thumbnail(arr, self.brightness_manager.apply_brightness_adjustment, **self._render_options(arr))

    # 子 dialog の起動
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
            bring_to_front(self._analysis_dialog)
            self._analysis_dialog.set_current_tab(tab)
            return

        img = self.images[self.state.current_index]
        arr = img.get("base_array", img.get("array"))
        sel = self.state.roi
        img_path = img.get("path")
        dlg = AnalysisDialog(
            self,
            image_array=arr,
            image_rect=sel,
            image_path=img_path,
            channel_display=self.channel_display,
            rois=self.roi_list.enabled_rois(),
        )
        bring_to_front(dlg)
        self._analysis_dialog = self.child_dialogs.track(dlg, lambda: setattr(self, "_analysis_dialog", None))
        dlg.set_current_tab(tab)

    def show_annotations_dialog(self):
        if self._annotations_dialog is not None:
            # 最後に読み込んだファイルを title に反映する
            self._annotations_dialog.update_title()
            bring_to_front(self._annotations_dialog)
            return
        dlg = AnnotationsDialog(self, self.annotations)
        bring_to_front(dlg)
        self._annotations_dialog = self.child_dialogs.track(dlg, lambda: setattr(self, "_annotations_dialog", None))

    def show_tiling_comparison_dialog(self):
        """複数画像比較 dialog を表示する。"""
        if len(self.images) < 2:
            QMessageBox.information(self, "複数画像比較", "比較する画像が2枚以上必要です。")
            return
        # modeless で開き、GC されないよう参照を保持する
        if self._tiling_dialog is None:
            self._tiling_dialog = TilingDialog(self, image_list=self.images)
            self._tiling_dialog.finished.connect(lambda: setattr(self, "_tiling_dialog", None))

        bring_to_front(self._tiling_dialog)

    # 現在値のコピーと再起動
    def collect_state(self) -> dict:
        """viewer・channel 表示設定と、開いている解析 dialog・複数画像比較の現在値を集める。"""
        state = {
            "viewer": self.state,
            "channel_display": self.channel_display.snapshot(),
        }
        if self._analysis_dialog is not None:
            state["analysis"] = self._analysis_dialog.settings
        tiling = self._tiling_dialog
        # 画像選択を cancel した dialog は state を持たない
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
        self.roi_list.sync_linked()
        self.status_updater.update_roi_status()
        self._update_analysis_dialog()

        self.roi_changed.emit()

    def _update_analysis_dialog(self):
        """表示中の画像・ROI・解析対象の ROI 一覧を解析 dialog に反映する。画像がない場合は解析 dialog を空にする。"""
        if self._analysis_dialog is None:
            return
        rois = self.roi_list.enabled_rois()
        if self.state.current_index is None:
            self._analysis_dialog.set_image_and_rect(None, None, rois=rois)
            return
        img = self.images[self.state.current_index]
        self._analysis_dialog.set_image_and_rect(
            img.get("base_array", img["array"]), self.state.roi, img.get("path"), rois=rois
        )

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
        self.state.roi = rect_img
        self.roi_list.sync_linked()
        s = self.state.scale
        self.image_label.roi_rect = QRect(
            int(rect_img.x() * s), int(rect_img.y() * s), int(rect_img.width() * s), int(rect_img.height() * s)
        )
        self.image_label.update()
        self.status_updater.update_roi_status()
        self._update_analysis_dialog()
        self.roi_changed.emit()

    # event handler
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls()]
        image_files = [f for f in files if is_image_file(f)]
        annotation_files = [f for f in files if Path(f).suffix.lower() in (".json", ".csv")]

        self.image_list.add_and_show(image_files)
        self.activateWindow()

        if annotation_files:
            try:
                self.annotations.load_annotation_files(annotation_files)
            except Exception as e:  # ユーザーのファイルの形式は様々なため、失敗はまとめて知らせる
                QMessageBox.warning(self, "特徴量ファイル", f"特徴量ファイルを読み込めませんでした。\n{e}")
                return
            # 特徴量 dialog を開き（既に開いていれば前面に出し）内容を反映する
            self.show_annotations_dialog()
            if self._annotations_dialog is not None:
                self._annotations_dialog.refresh_from_manager()

    def changeEvent(self, event):
        # 最小化・復元を子 dialog にも反映する
        self.child_dialogs.sync_window_state(self, event)
        super().changeEvent(event)

    def mousePressEvent(self, event):
        # クリック時に子 dialog も前面に出す
        self.child_dialogs.raise_visible()
        super().mousePressEvent(event)

    def eventFilter(self, obj, event):
        if obj is self.image_label and event.type() == QEvent.MouseMove:
            self.status_updater.update_mouse_status(event.position().toPoint())
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
        self.child_dialogs.close_all()
        # 複数画像比較と help は最小化の連動の対象外のため、個別に閉じる
        with contextlib.suppress(RuntimeError):  # Qt 側で削除済み
            if self._tiling_dialog is not None:
                self._tiling_dialog.close()
        with contextlib.suppress(RuntimeError):
            if self.help_dialog and self.help_dialog.isVisible():
                self.help_dialog.close()
        event.accept()
