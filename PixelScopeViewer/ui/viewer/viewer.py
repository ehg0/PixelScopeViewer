"""メインの画像ビューア window。"""

import contextlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QGridLayout,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.core.brightness import apply_brightness_adjustment as apply_brightness_core
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
from PixelScopeViewer.ui.viewer.brightness_manager import BrightnessManager
from PixelScopeViewer.ui.viewer.display_cache import DisplayCache
from PixelScopeViewer.ui.viewer.help_dialog import HelpDialog
from PixelScopeViewer.ui.viewer.image_list import ImageListManager
from PixelScopeViewer.ui.viewer.menu_builder import create_menus
from PixelScopeViewer.ui.viewer.roi_list import RoiListManager
from PixelScopeViewer.ui.viewer.state import ViewerState
from PixelScopeViewer.ui.viewer.status_updater import StatusUpdater
from PixelScopeViewer.ui.viewer.tile_mode import TILE_BRIGHTNESS_KEY, TileModeManager
from PixelScopeViewer.ui.viewer.tile_register_dialog import TileRegisterDialog
from PixelScopeViewer.ui.viewer.widgets import (
    DisplayInfoWidget,
    ImageLabel,
    ImagePane,
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
    # active な pane の scroll・viewport の resize
    view_changed = Signal()

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

        # 画像ごとの表示用 QPixmap の cache
        self.display_cache = DisplayCache(defaults.TILE_DISPLAY_CACHE_MB)

        central = QWidget(self)
        self.setCentralWidget(central)
        h_layout = QHBoxLayout(central)

        # 画像の表示枠。1 枚表示は 1 つ、タイル比較モードはタイルの数だけ並べる
        self.pane_area = QWidget()
        self.pane_grid = QGridLayout(self.pane_area)
        self.pane_grid.setContentsMargins(0, 0, 0, 0)
        self.panes = [ImagePane(self)]
        self.active_pane = self.panes[0]
        self.pane_grid.addWidget(self.active_pane, 0, 0)
        h_layout.addWidget(self.pane_area)
        self.tiles = TileModeManager(self)

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

        # 編集中 ROI の座標の下に、ROI 一覧への登録 button を置く
        roi_area = QWidget()
        roi_area_layout = QVBoxLayout(roi_area)
        roi_area_layout.setContentsMargins(0, 0, 0, 0)
        roi_area_layout.addWidget(ROIInfoWidget(self))
        add_roi_btn = QPushButton("ROI一覧に登録 (R)")
        add_roi_btn.setToolTip("編集中ROIを ROI List tab の一覧の末尾に登録")
        add_roi_btn.clicked.connect(lambda: self.roi_list.add_current())
        roi_area_layout.addWidget(add_roi_btn)
        roi_area_layout.addStretch(1)
        self.info_tabs.addTab(roi_area, "ROI Area")

        self.info_tabs.addTab(RoiListWidget(self), "ROI List")

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

    @property
    def scroll_area(self) -> QScrollArea:
        """active な pane の scroll area。"""
        return self.active_pane.scroll_area

    @property
    def image_label(self) -> ImageLabel:
        """active な pane の画像表示 widget。"""
        return self.active_pane.image_label

    def refresh_overlays(self):
        """全 pane の ROI の描画を更新する。"""
        for pane in self.panes:
            pane.image_label.update()

    def on_pane_view_changed(self, pane: ImagePane):
        if self.state.tile_mode:
            self.tiles.sync_from(pane)
        if pane is self.active_pane:
            self.view_changed.emit()

    def on_label_pressed(self, label: ImageLabel) -> bool:
        """画像表示 widget のクリックを受け取る。タイル比較モードではそのタイルを active にする。

        Returns:
            active タイルが変わったか。
        """
        return self.state.tile_mode and self.tiles.on_label_pressed(label)

    def on_label_mouse_moved(self, label: ImageLabel, pos: QPoint | None):
        """画像表示 widget 上のマウス位置（widget 座標）を受け取る。widget の外に出た場合は None。"""
        if self.state.tile_mode:
            self.status_updater.update_tile_mouse_status(pos)
        else:
            self.status_updater.update_mouse_status(pos)

    def has_image(self) -> bool:
        """表示中の画像があるか。タイル比較モードではどれかのタイルに画像があるか。"""
        if self.state.tile_mode:
            return self.tiles.canvas_size() is not None
        return self.state.current_index is not None and bool(self.images)

    def content_size(self) -> tuple[int, int] | None:
        """表示中の画像の幅・高さを返す。タイル比較モードでは全タイルの最大の幅・高さ。"""
        if self.state.tile_mode:
            return self.tiles.canvas_size()
        if self.state.current_index is None:
            return None
        h, w = self.images[self.state.current_index]["array"].shape[:2]
        return w, h

    def brightness_key(self, arr: np.ndarray) -> str:
        """arr の brightness を保存する brightness_by_dtype の key を返す。タイル比較モードでは dtype によらず共通。"""
        return TILE_BRIGHTNESS_KEY if self.state.tile_mode else determine_dtype_group(arr)

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
        self.refresh_display()

    # 表示
    def show_current_image(self):
        """current_index の画像（タイル比較モードでは全タイル）を表示し、関連する widget と dialog を更新する。"""
        if self.state.tile_mode:
            self.tiles.sync_current_index()
            self.refresh_display()
            self.notify_active_image_changed()
            return

        if self.state.current_index is None or not self.images:
            self.image_label.clear()
            self.status_updater.update_status()
            self.image_changed.emit()
            return

        # 画像を切り替えたら fit zoom の状態を破棄する
        self.state.fit_zoom_scale = None
        self.state.original_zoom_scale = 1.0
        self.state.original_center_coords = None

        arr = self.images[self.state.current_index]["array"]
        # dtype が切り替わった場合のみ、その dtype で保存した brightness を読み込む
        stored_params = self.state.brightness_by_dtype[self.brightness_key(arr)]
        if stored_params != self.state.brightness:
            self.state.brightness = replace(stored_params)
            self.status_updater.update_brightness_status()
        self.refresh_display()
        self.notify_active_image_changed()

    def notify_active_image_changed(self):
        """current_index の画像が変わったことを navigator・画像 menu・表示設定 dialog・解析 dialog に伝える。"""
        self.image_changed.emit()
        self.image_list.update_menu()
        self.status_updater.update_status()
        self.status_updater.update_roi_status()

        if self.state.current_index is None:
            # 空欄のタイルが active の場合は auto scale の対象をなくす
            if self.brightness_dialog is not None:
                self.brightness_dialog.update_for_new_image(None, None)
            self._update_analysis_dialog()
            return
        img = self.images[self.state.current_index]
        # 非表示でも表示設定 dialog が存在すれば新しい画像に更新する
        base_arr = img.get("base_array", img["array"])
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

        self._update_analysis_dialog()

    def _render_array(self, arr: np.ndarray) -> tuple[np.ndarray, tuple]:
        """brightness・channel 合成・colormap を適用した表示用の配列と、表示に影響する設定の tuple を返す。"""
        b = self.state.brightness_by_dtype[self.brightness_key(arr)]
        opts = self._render_options(arr)
        result = render_display(
            arr,
            lambda a: apply_brightness_core(a, b.offset, b.gain, b.upper_level),
            brightness_changed=(b.offset, b.gain, b.upper_level) != (0, 1.0, 255),
            **opts,
        )
        return result, self._render_key(arr)

    def _render_key(self, arr: np.ndarray) -> tuple:
        """arr の表示に影響する brightness・表示モード・channel の表示 ON/OFF と色の tuple を返す。"""
        b = self.state.brightness_by_dtype[self.brightness_key(arr)]
        opts = self._render_options(arr)
        return (
            b.offset,
            b.gain,
            b.upper_level,
            opts["jet"],
            opts["flow_hsv"],
            tuple(opts["checks"]),
            tuple(tuple(c) for c in opts["colors_rgb"]),
        )

    def _get_displayed_array(self) -> np.ndarray | None:
        """current_index の画像の表示用の配列を返す。"""
        if self.state.current_index is None:
            return None
        return self._render_array(self.images[self.state.current_index]["array"])[0]

    def display_pixmap(self, img: dict) -> QPixmap:
        """画像の表示用 QPixmap を返す。表示設定が同じなら cache を使う。"""
        arr = img["array"]
        key = self._render_key(arr)
        pixmap = self.display_cache.get(img["id"], key)
        if pixmap is None:
            result, key = self._render_array(arr)
            pixmap = QPixmap.fromImage(numpy_to_qimage(result))
            self.display_cache.put(img["id"], key, pixmap)
        return pixmap

    def refresh_display(self, defer_others: bool = False):
        """今の zoom 倍率と表示設定で、表示中の画像（タイル比較モードでは全タイル）を描き直す。

        Args:
            defer_others: タイル比較モードで、active 以外のタイルの描き直しを少し待つか（slider 操作中など）。
        """
        if self.state.tile_mode:
            if defer_others:
                self.tiles.render_active_first()
            else:
                self.tiles.render()
        elif self.state.current_index is not None and self.images:
            self.image_label.set_image(self.display_pixmap(self.images[self.state.current_index]), self.state.scale)
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

    # タイル比較モード
    def toggle_tile_mode(self):
        """タイル比較モードと 1 枚表示を切り替える。登録がない場合は先に登録 dialog を開く。"""
        if self.state.tile_mode:
            self.tiles.exit()
        elif self.state.tile_layout.has_visible_images() or self.show_tile_register_dialog(enter=False):
            self.tiles.enter()
        self.tile_mode_action.setChecked(self.state.tile_mode)

    def show_tile_register_dialog(self, enter: bool = True) -> bool:
        """タイルへの画像登録 dialog を開き、OK なら登録内容を反映する。

        Args:
            enter: OK のときタイル比較モードにするか。

        Returns:
            OK で閉じたか。
        """
        if not self.images:
            QMessageBox.information(self, "タイル比較", "画像が読み込まれていません。")
            return False
        dlg = TileRegisterDialog(self, self.images, self.state.tile_layout)
        if dlg.exec() != QDialog.Accepted or dlg.result_layout is None:
            return False
        self.state.tile_layout = dlg.result_layout
        if enter or self.state.tile_mode:
            self.tiles.enter()
            self.tile_mode_action.setChecked(True)
        return True

    # 現在値のコピーと再起動
    def collect_state(self) -> dict:
        """viewer・channel 表示設定と、開いている解析 dialog の現在値を集める。"""
        state = {
            "viewer": self.state,
            "channel_display": self.channel_display.snapshot(),
        }
        if self._analysis_dialog is not None:
            state["analysis"] = self._analysis_dialog.settings
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
        rect = self.image_label.full_image_rect()
        if rect is not None:
            self.set_roi_from_image_rect(rect)

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

    def set_roi_from_image_rect(self, rect_img: QRect | None):
        """画像座標で編集中 ROI を設定し、関連する widget と dialog に通知する。None の場合は ROI を解除する。"""
        if rect_img == self.state.roi:
            return
        self.state.roi = QRect(rect_img) if rect_img is not None else None
        self.roi_list.sync_linked()
        self.refresh_overlays()
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

        # タイル比較モードでタイルの上に drop した画像は、そのマスの登録リストの末尾にも追加する
        cell = self.tiles.cell_at(self, e.position().toPoint()) if self.state.tile_mode else None
        added = self.image_list.add_and_show(image_files)
        if cell is not None and added > 0:
            self.state.tile_layout.append(cell, [img["id"] for img in self.images[-added:]])
            self.show_current_image()
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

    def keyPressEvent(self, e):
        # Esc で ROI を解除する
        if e.key() == Qt.Key_Escape:
            self.set_roi_from_image_rect(None)
            return

        super().keyPressEvent(e)

    def closeEvent(self, event):
        # 子 window が残って操作不能にならないよう、modeless dialog をすべて閉じる
        self.child_dialogs.close_all()
        # help は最小化の連動の対象外のため、個別に閉じる
        with contextlib.suppress(RuntimeError):  # Qt 側で削除済み
            if self.help_dialog and self.help_dialog.isVisible():
                self.help_dialog.close()
        event.accept()
