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

from PixelScopeViewer.core.image_io import is_image_file
from PixelScopeViewer.ui.analysis import AnalysisDialog, AnalysisSource
from PixelScopeViewer.ui.annotations import AnnotationsDialog
from PixelScopeViewer.ui.annotations.model import AnnotationStore
from PixelScopeViewer.ui.common import defaults
from PixelScopeViewer.ui.common.channel_display import ChannelDisplay
from PixelScopeViewer.ui.common.qt_image import numpy_to_qimage
from PixelScopeViewer.ui.common.state_dump import to_jsonable
from PixelScopeViewer.ui.common.window import ChildDialogs, bring_to_front
from PixelScopeViewer.ui.viewer.brightness_manager import BrightnessManager
from PixelScopeViewer.ui.viewer.display_renderer import DisplayRenderer
from PixelScopeViewer.ui.viewer.help_dialog import HelpDialog
from PixelScopeViewer.ui.viewer.image_list import ImageListManager
from PixelScopeViewer.ui.viewer.menu_builder import create_menus
from PixelScopeViewer.ui.viewer.roi_list import RoiListManager
from PixelScopeViewer.ui.viewer.state import ViewerState
from PixelScopeViewer.ui.viewer.status_updater import StatusUpdater
from PixelScopeViewer.ui.viewer.tile_mode import TileModeManager
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
        # 表示用の画像と thumbnail を作る。表示用 QPixmap の cache を持つ
        self.renderer = DisplayRenderer(self.state, self.channel_display)

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
        """画像表示 widget 上のマウス位置（widget 座標）を受け取る。widget の外に出た場合は None。

        画像の下のステータス行（タイル比較モードでは全タイル）にその座標の pixel 値を出し、
        status bar には座標だけを出す。
        """
        if self.state.tile_mode:
            point = self.tiles.show_pixel_values(pos)
            self.current_mouse_image_coords = point
            self.status_updater.show_mouse_point(point)
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
            self.notify_active_image_changed(render=True)
            return

        if self.state.current_index is None or not self.images:
            self.active_pane.show_image(None, None, self.state.scale)
            self.status_updater.update_status()
            self.image_changed.emit()
            return

        # 画像を切り替えたら fit zoom の状態を破棄する
        self.state.fit_zoom_scale = None
        self.state.original_zoom_scale = 1.0
        self.state.original_center_coords = None

        arr = self.images[self.state.current_index]["array"]
        # dtype が切り替わった場合のみ、その dtype で保存した brightness を読み込む
        stored_params = self.state.brightness_by_dtype[self.state.brightness_key(arr)]
        if stored_params != self.state.brightness:
            self.state.brightness = replace(stored_params)
            self.status_updater.update_brightness_status()
        self.notify_active_image_changed(render=True)

    def notify_active_image_changed(self, render: bool = False):
        """current_index の画像が変わったことを表示設定 dialog・navigator・画像 menu・解析 dialog に伝える。

        表示設定 dialog の auto scale を描画の前に済ませ、表示中の画像（タイル比較モードでは全タイル）を
        新しい brightness で 1 回だけ描き直す。active でないタイルの明るさが遅れて変わるのを防ぐため。

        Args:
            render: brightness が変わらなくても描き直すか（表示する画像が変わった場合）。
        """
        before = replace(self.state.brightness)
        with self.brightness_manager.render_held():
            self._update_brightness_dialog()
        if render or self.state.brightness != before:
            self.refresh_display()

        self.image_changed.emit()
        self.image_list.update_menu()
        self.status_updater.update_status()
        self.status_updater.update_roi_status()
        self._update_analysis_dialog()

    def _update_brightness_dialog(self):
        """表示設定 dialog が存在すれば（非表示でも）current_index の画像に更新する。"""
        if self.brightness_dialog is None:
            return
        if self.state.current_index is None:
            # 空欄のタイルが active の場合は auto scale の対象をなくす
            self.brightness_dialog.update_for_new_image(None, None)
            return
        img = self.images[self.state.current_index]
        self.brightness_dialog.update_for_new_image(
            img.get("base_array", img["array"]),
            img.get("path"),
            keep_settings=True,
            channel_checks=self.channel_checks,
            channel_colors=self.channel_colors,
            initial_mode_1ch=self.channel_display.mode_1ch,
            initial_mode_2ch=self.channel_display.mode_2ch,
        )

    def _get_displayed_array(self) -> np.ndarray | None:
        """current_index の画像の表示用の配列を返す。"""
        if self.state.current_index is None:
            return None
        return self.renderer.array(self.images[self.state.current_index]["array"])

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
            img = self.images[self.state.current_index]
            self.active_pane.show_image(img, self.renderer.pixmap(img), self.state.scale)
        self.status_updater.update_status()

    # 子 dialog の起動
    def show_analysis_dialog(self, tab: str | None = None):
        """表示中の画像と ROI の解析 dialog を表示する。

        Args:
            tab: 表示する tab 名（前方一致）または index。
        """
        # QAction.triggered(bool) から渡される bool は無視する
        if isinstance(tab, bool):
            tab = None
        if not self.has_image():
            QMessageBox.information(self, "解析", "画像が選択されていません。")
            return

        # 既に開いている場合は前面に出す
        if self._analysis_dialog is not None:
            bring_to_front(self._analysis_dialog)
            self._analysis_dialog.set_current_tab(tab)
            return

        arr, img_path = None, None
        if self.state.current_index is not None:
            img = self.images[self.state.current_index]
            arr = img.get("base_array", img.get("array"))
            img_path = img.get("path")
        dlg = AnalysisDialog(
            self,
            image_array=arr,
            image_rect=self.state.roi,
            image_path=img_path,
            channel_display=self.channel_display,
            rois=self.roi_list.enabled_rois(),
            sources=self._analysis_sources(),
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
        sources = self._analysis_sources()
        if self.state.current_index is None:
            self._analysis_dialog.set_image_and_rect(None, self.state.roi, rois=rois, sources=sources)
            return
        img = self.images[self.state.current_index]
        self._analysis_dialog.set_image_and_rect(
            img.get("base_array", img["array"]), self.state.roi, img.get("path"), rois=rois, sources=sources
        )

    def _analysis_sources(self) -> list[AnalysisSource]:
        """解析 dialog に渡すタイル比較モードの全タイルの画像を返す（空欄のタイルは除く）。1 枚表示では空。"""
        if not self.state.tile_mode:
            return []
        layout = self.state.tile_layout
        return [
            AnalysisSource(f"T{layout.tile_number(cell)}", img.get("base_array", img["array"]), img.get("path"))
            for cell, img in self.tiles.visible_images()
            if img is not None
        ]

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
