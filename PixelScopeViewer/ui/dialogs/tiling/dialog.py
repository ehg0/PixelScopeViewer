"""複数画像を grid に並べて比較する dialog。"""

import numpy as np
from PySide6.QtCore import QEvent, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QLabel,
    QMenuBar,
    QMessageBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.ui import defaults

from ..analysis.dialog import AnalysisDialog
from .brightness_dialog import TilingBrightnessDialog
from .comparison_dialog import TilingAnalysisDialog
from .core import (
    BrightnessManager,
    ROIManager,
    ScrollManager,
    TileManager,
    ZoomManager,
)
from .help_dialog import TilingHelpDialog
from .selection_dialog import TileSelectionDialog
from .tile_widget import TileWidget


class TilingDialog(QDialog):
    """複数画像を grid に並べ、scroll・zoom・ROI を同期して比較する dialog。

    Args:
        parent: 親の ImageViewer。
        image_list: ImageViewer の画像の dict のリスト。
    """

    common_roi_changed = Signal(QRect)

    def __init__(self, parent, image_list: list[dict]):
        super().__init__(None)
        self.setWindowTitle("複数画像比較")
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setFocusPolicy(Qt.StrongFocus)
        self.parent_viewer = parent
        self.all_images = image_list

        # AnalysisDialog から参照できるよう親の channel の色を保持する
        self.channel_colors = None
        if hasattr(parent, "channel_colors"):
            self.channel_colors = parent.channel_colors

        # window 状態（最小化など）を同期する子 dialog
        self._brightness_dialog = None
        self._help_dialog = None
        self._analysis_dialog = None
        self._comparison_dialog = None
        self._child_dialogs = []

        # 最初に比較する画像を選択させる
        selection_dialog = TileSelectionDialog(self, image_list)
        if selection_dialog.exec() != QDialog.Accepted:
            self.reject()
            return

        grid_size, selected_indices = selection_dialog.get_selection()
        if not selected_indices:
            QMessageBox.warning(self, "複数画像比較", "画像が選択されていません。")
            self.reject()
            return

        self.grid_size = grid_size
        self.selected_indices = selected_indices

        # GC されないよう shortcut の参照を保持する
        self.shortcuts = []

        self.current_mouse_coords = None

        # UI（grid_layout）→ tile → manager の順に作成する
        self._build_ui()

        self.tile_manager = TileManager(self.grid_layout)
        self.brightness_manager = None
        self.scroll_manager = None
        self.zoom_manager = None
        self.roi_manager = None

        self._rebuild_tiles()

        self._initialize_managers()

        # manager の作成後に dtype ごとの初期値で描画する
        if self.brightness_manager:
            self.brightness_manager.refresh_all_tiles()

        self.common_roi_changed.connect(self.roi_manager.sync_roi_to_all_tiles)

        if self.tile_manager.get_tiles():
            self.tile_manager.set_active_tile(0)

        self.resize(*defaults.TILING_DIALOG_SIZE)

        self.setFocus()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        menu_bar = QMenuBar(self)

        file_menu = menu_bar.addMenu("ファイル")
        change_images_action = file_menu.addAction("比較画像変更...")
        change_images_action.triggered.connect(self.change_comparison_images)

        view_menu = menu_bar.addMenu("表示")
        brightness_action = view_menu.addAction("表示設定")
        brightness_action.setShortcut("D")
        brightness_action.setShortcutContext(Qt.WindowShortcut)
        self.addAction(brightness_action)
        brightness_action.triggered.connect(self.show_brightness_dialog)

        # 解析メニュー（並び順はメインビューアに合わせる）
        analysis_menu = menu_bar.addMenu("解析")
        analysis_dialog_action = analysis_menu.addAction("解析ビュー(単一画像)")
        analysis_dialog_action.setShortcut("A")
        analysis_dialog_action.setShortcutContext(Qt.WindowShortcut)
        self.addAction(analysis_dialog_action)
        analysis_dialog_action.triggered.connect(lambda: self.show_analysis_dialog())

        comparison_table_action = analysis_menu.addAction("解析ビュー(複数画像)")
        comparison_table_action.setShortcut("Shift+A")
        comparison_table_action.setShortcutContext(Qt.WindowShortcut)
        self.addAction(comparison_table_action)
        comparison_table_action.triggered.connect(lambda: self.show_comparison_dialog())

        help_menu = menu_bar.addMenu("ヘルプ")
        help_action = help_menu.addAction("ヘルプ / ショートカット")
        help_action.triggered.connect(self.show_help)
        layout.setMenuBar(menu_bar)

        grid_widget = QWidget()
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setSpacing(4)

        layout.addWidget(grid_widget, 1)

        # status bar（左: マウス座標と ROI、右: brightness と zoom 倍率）
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("font-size: 11pt;")
        self.mouse_coords_label = QLabel()
        self.roi_info_label = QLabel()
        self.brightness_label = QLabel()
        self.scale_label = QLabel()

        self.status_bar.addWidget(self.mouse_coords_label)
        self.status_bar.addWidget(self.roi_info_label)
        self.status_bar.addWidget(QLabel(""), 1)
        self.status_bar.addPermanentWidget(self.brightness_label)
        self.status_bar.addPermanentWidget(self.scale_label)
        layout.addWidget(self.status_bar)

        self._setup_shortcuts()

    def _initialize_managers(self):
        tiles = self.tile_manager.get_tiles()
        tile_dtype_groups = self.tile_manager.get_tile_dtype_groups()

        self.brightness_manager = BrightnessManager(tiles, tile_dtype_groups)
        self.scroll_manager = ScrollManager(tiles)
        self.zoom_manager = ZoomManager(tiles, self.tile_manager.get_active_tile_index)
        self.roi_manager = ROIManager(tiles, self.tile_manager.get_active_tile_index, self.common_roi_changed)

    def _rebuild_tiles(self):
        self.tile_manager.rebuild_tiles(
            self.all_images,
            self.selected_indices,
            self.grid_size,
            self,
            TileWidget,
            self.set_active_tile,
            self._on_tile_roi_changed,
            self._on_mouse_coords_changed,
            self._on_scroll,
        )

        self.update_status_bar()

    def change_comparison_images(self):
        """状態の不整合を避けるため、この dialog を閉じて新しい比較 dialog を開き直す。"""
        if self.parent_viewer:
            # この dialog が閉じた後に開く
            QTimer.singleShot(0, self.parent_viewer.show_tiling_comparison_dialog)

        self.close()

    def _on_scroll(self, source_index: int, direction: str, value: int, signal_name: str):
        if self.scroll_manager:
            self.scroll_manager.sync_scroll(source_index, direction, value, self.zoom_manager.get_scale())

    def _on_hover_info(self, tile_idx: int, ix: int, iy: int, value_text: str):
        """全 tile の (ix, iy) の pixel 値を表示し、status bar に座標を表示する。"""
        displayed_image_data = self.tile_manager.get_displayed_image_data()
        tiles = self.tile_manager.get_tiles()

        for i, data in enumerate(displayed_image_data):
            arr = data.get("base_array", data.get("array"))
            if arr is None:
                tiles[i].update_status("")
                continue
            h, w = arr.shape[:2]
            if 0 <= ix < w and 0 <= iy < h:
                try:
                    v = arr[iy, ix]
                    if hasattr(v, "shape") and len(getattr(v, "shape", ())) > 0:
                        flat = np.array(v).ravel().tolist()
                        preview = ", ".join(str(x) for x in flat[:4])
                        txt = f"[{preview}{', …' if len(flat) > 4 else ''}]"
                    else:
                        txt = str(v)
                    if len(txt) > 50:
                        txt = txt[:47] + "…"
                except Exception:
                    txt = "NA"
            else:
                txt = ""
            tiles[i].update_status(txt)

        self.mouse_coords_label.setText(f"({ix}, {iy})")

    def _setup_shortcuts(self):
        """競合しないよう WindowShortcut の context で keyboard shortcut を登録する。"""
        self.shortcuts.clear()

        def add_shortcut(key_seq, callback):
            shortcut = QShortcut(QKeySequence(key_seq), self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

        add_shortcut("F1", self.show_help)

        add_shortcut("+", lambda: self.adjust_zoom(2.0))
        add_shortcut("-", lambda: self.adjust_zoom(0.5))
        add_shortcut("f", self.toggle_fit_zoom)

        add_shortcut("<", lambda: self.adjust_gain(0.5))
        add_shortcut(">", lambda: self.adjust_gain(2.0))

        # 表示設定・解析の shortcut は menu の action で登録している

        add_shortcut("Ctrl+R", self.reset_brightness)

        add_shortcut("Ctrl+A", self.select_all_roi)
        add_shortcut("Esc", self.clear_roi)

        # 矢印キーで全 tile を scroll する
        add_shortcut("Left", lambda: self._scroll_by_key(-10, 0, False))
        add_shortcut("Right", lambda: self._scroll_by_key(10, 0, False))
        add_shortcut("Up", lambda: self._scroll_by_key(0, -10, False))
        add_shortcut("Down", lambda: self._scroll_by_key(0, 10, False))
        add_shortcut("Shift+Left", lambda: self._scroll_by_key(-50, 0, True))
        add_shortcut("Shift+Right", lambda: self._scroll_by_key(50, 0, True))
        add_shortcut("Shift+Up", lambda: self._scroll_by_key(0, -50, True))
        add_shortcut("Shift+Down", lambda: self._scroll_by_key(0, 50, True))
        add_shortcut("Ctrl+C", self.copy_active_tile_roi)
        add_shortcut("Ctrl+Shift+C", self.copy_all_tiles_roi_as_grid)

    def adjust_zoom(self, factor, tile_index=None, mouse_pos=None):
        """全 tile の zoom 倍率に factor を掛ける。

        Args:
            factor: 倍率（2.0 で拡大、0.5 で縮小）。
            tile_index: zoom の基準にする tile の index。None の場合は active な tile。
            mouse_pos: 基準にする viewport 上のマウス位置。None の場合は viewport の中心。
        """
        if not self.zoom_manager or not self.scroll_manager:
            return

        new_scroll_x, new_scroll_y = self.zoom_manager.adjust_zoom(factor, tile_index, mouse_pos)

        self.scroll_manager.apply_scroll_position(new_scroll_x, new_scroll_y)
        QApplication.processEvents()

        self.update_status_bar()

    def toggle_fit_zoom(self):
        if not self.zoom_manager or not self.scroll_manager:
            return

        self.zoom_manager.toggle_fit_zoom(
            lambda idx, dir, val: self.scroll_manager.sync_scroll(idx, dir, val, self.zoom_manager.get_scale())
        )
        self.update_status_bar()

    def adjust_gain(self, factor):
        if self.brightness_manager:
            self.brightness_manager.adjust_gain(factor)
            self.update_status_bar()

    def reset_brightness(self):
        if self.brightness_manager:
            self.brightness_manager.reset_brightness()
            self.update_status_bar()

    def refresh_all_tiles(self):
        if self.brightness_manager:
            self.brightness_manager.refresh_all_tiles()

    def show_brightness_dialog(self):
        if not self.brightness_manager:
            return

        if self._brightness_dialog is None:
            params = self.brightness_manager.get_brightness_params()
            self._brightness_dialog = TilingBrightnessDialog(self, params["params_by_dtype"], params["gain"])
            self._brightness_dialog.brightness_changed.connect(self.on_brightness_dialog_changed)
            self._child_dialogs.append(self._brightness_dialog)

            def on_closed():
                if self._brightness_dialog in self._child_dialogs:
                    self._child_dialogs.remove(self._brightness_dialog)
                self._brightness_dialog = None

            self._brightness_dialog.finished.connect(on_closed)

        if self._brightness_dialog.isMinimized():
            self._brightness_dialog.showNormal()
        self._brightness_dialog.show()
        self._brightness_dialog.raise_()
        self._brightness_dialog.activateWindow()

    def show_help(self):
        if self._help_dialog is None:
            self._help_dialog = TilingHelpDialog(self)
            self._child_dialogs.append(self._help_dialog)

            def on_closed():
                if self._help_dialog in self._child_dialogs:
                    self._child_dialogs.remove(self._help_dialog)
                self._help_dialog = None

            self._help_dialog.finished.connect(on_closed)

        if self._help_dialog.isMinimized():
            self._help_dialog.showNormal()
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

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
        # click 時に子 dialog も前面に出す
        for dlg in self._child_dialogs:
            try:
                if dlg.isVisible() and not dlg.isMinimized():
                    dlg.raise_()
            except RuntimeError:
                pass  # dialog は削除済み
        super().mousePressEvent(event)

    def closeEvent(self, event):
        # 子 dialog も閉じる
        if self._brightness_dialog is not None:
            self._brightness_dialog.close()
            self._brightness_dialog = None
        if self._help_dialog is not None:
            self._help_dialog.close()
            self._help_dialog = None
        if self._analysis_dialog is not None:
            self._analysis_dialog.close()
            self._analysis_dialog = None
        if self._comparison_dialog is not None:
            self._comparison_dialog.close()
            self._comparison_dialog = None

        super().closeEvent(event)

    def on_brightness_dialog_changed(self, full_params: dict):
        if self.brightness_manager:
            self.brightness_manager.on_brightness_dialog_changed(full_params)
            self.update_status_bar()

    def set_active_tile(self, tile_index: int):
        """active な tile を切り替え、ROI と解析 dialog の表示を更新する。"""
        if self.tile_manager:
            self.tile_manager.set_active_tile(tile_index)

            if self.roi_manager and self.roi_manager.common_roi_rect:
                self.roi_manager.sync_roi_to_all_tiles(self.roi_manager.common_roi_rect)

            if self._analysis_dialog and self._analysis_dialog.isVisible():
                image_array, roi_rect, file_path = self.get_active_tile_image_and_rect()
                if image_array is not None:
                    self._analysis_dialog.set_image_and_rect(image_array, roi_rect, file_path)

    def _on_mouse_coords_changed(self, coords):
        """いずれかの tile のマウス座標 (ix, iy)（または None）の変更時に、全 tile の pixel 値の表示を更新する。"""
        self.current_mouse_coords = coords
        self.update_status_bar()

        if not self.tile_manager:
            return

        tiles = self.tile_manager.get_tiles()

        if coords is not None:
            ix, iy = coords
            for tile in tiles:
                arr = tile.get_base_array()
                if arr is not None:
                    try:
                        val = arr[iy, ix]

                        is_float_dtype = np.issubdtype(arr.dtype, np.floating)

                        def _fmt(v, is_float_dtype=is_float_dtype):
                            try:
                                if isinstance(v, (np.floating, float)):
                                    return f"{float(v):.3f}" if is_float_dtype else str(v)
                                if isinstance(v, (np.integer, int)):
                                    return str(int(v))
                                return (
                                    f"{float(v):.3f}"
                                    if (is_float_dtype and isinstance(v, (int, float, np.number)))
                                    else str(v)
                                )
                            except Exception:
                                return str(v)

                        if isinstance(val, np.ndarray) or (
                            hasattr(val, "shape") and len(getattr(val, "shape", ())) > 0
                        ):
                            flat = np.array(val).ravel().tolist()
                            preview = ", ".join(_fmt(x) for x in flat[:4])
                            text = f"[{preview}{', …' if len(flat) > 4 else ''}]"
                        else:
                            text = _fmt(val)
                        if len(text) > 60:
                            text = text[:57] + "…"
                        tile.update_status(text)
                    except Exception:
                        tile.update_status("")
                else:
                    tile.update_status("")
        else:
            for tile in tiles:
                tile.update_status("")

    def _on_tile_roi_changed(self, roi_rect):
        """tile の ROI [x, y, w, h]（または None）の変更を共通 ROI と解析 dialog に反映する。"""
        if self.roi_manager:
            self.roi_manager.on_tile_roi_changed_list(roi_rect)
            self.update_status_bar()

            if self._analysis_dialog and self._analysis_dialog.isVisible():
                image_array, roi_rect_qrect, file_path = self.get_active_tile_image_and_rect()
                if image_array is not None:
                    self._analysis_dialog.set_image_and_rect(image_array, roi_rect_qrect, file_path)
            self._refresh_comparison_dialog_for_roi()

    def get_active_tile_image_and_rect(self):
        """active な tile の画像を返す。

        Returns:
            (brightness 適用前の画像配列, 画像座標の ROI, ファイルパス)。取得できない場合は (None, None, None)。
        """
        if not self.tile_manager:
            return None, None, None

        active_index = self.tile_manager.get_active_tile_index()
        tiles = self.tile_manager.get_tiles()

        if active_index < 0 or active_index >= len(tiles):
            return None, None, None

        active_tile = tiles[active_index]

        image_array = active_tile.get_base_array()

        if image_array is None:
            return None, None, None

        if image_array.size == 0:
            return None, None, None

        roi_rect = None
        if self.roi_manager:
            roi_rect = self.roi_manager.common_roi_rect

        file_path = None
        if hasattr(active_tile, "image_data") and active_tile.image_data:
            file_path = active_tile.image_data.get("path")

        return image_array, roi_rect, file_path

    def get_all_tiles_data(self):
        """全 tile の比較用データを返す。

        Returns:
            array, rect（ROI）, path, index を持つ dict のリスト。
        """
        if not self.tile_manager:
            return []

        tiles = self.tile_manager.get_tiles()
        tiles_data = []

        roi_rect = None
        if self.roi_manager:
            roi_rect = self.roi_manager.common_roi_rect

        for i, tile in enumerate(tiles):
            image_array = tile.get_base_array()

            if image_array is None or image_array.size == 0:
                continue

            file_path = None
            if hasattr(tile, "image_data") and tile.image_data:
                file_path = tile.image_data.get("path")

            tiles_data.append({"array": image_array, "rect": roi_rect, "path": file_path, "index": i})

        return tiles_data

    def _refresh_comparison_dialog_for_roi(self):
        """表示中の複数画像の解析 dialog を現在の ROI で更新する。"""
        if self._comparison_dialog is not None and self._comparison_dialog.isVisible():
            try:
                updated = self.get_all_tiles_data()
                self._comparison_dialog.update_tiles_data(updated)
            except Exception:
                pass

    def show_analysis_dialog(self, tab=None):
        """active な tile の解析 dialog（単一画像）を表示する。

        Args:
            tab: 表示する tab 名（'Histogram', 'Profile', 'Metadata'）。
        """
        # 複数画像の解析 dialog とは同時に開かない
        if self._comparison_dialog is not None and self._comparison_dialog.isVisible():
            self._comparison_dialog.close()
            self._comparison_dialog = None

        image_array, roi_rect, file_path = self.get_active_tile_image_and_rect()

        if image_array is None:
            QMessageBox.warning(self, "解析", "解析する画像がありません。")
            return

        if self._analysis_dialog is None or not self._analysis_dialog.isVisible():
            self._analysis_dialog = AnalysisDialog(
                parent=self,
                image_array=image_array,
                image_rect=roi_rect,
                image_path=file_path,
            )

            # メインビューアの解析 dialog と区別できる title にする
            self._analysis_dialog.setWindowTitle("複数画像比較 - 解析ビュー(単一画像)")

            self._child_dialogs.append(self._analysis_dialog)

            def on_closed():
                if self._analysis_dialog in self._child_dialogs:
                    self._child_dialogs.remove(self._analysis_dialog)
                self._analysis_dialog = None

            self._analysis_dialog.finished.connect(on_closed)

            if tab:
                self._analysis_dialog.set_current_tab(tab)

            self._analysis_dialog.show()
            self._analysis_dialog.raise_()
            self._analysis_dialog.activateWindow()
        else:
            if self._analysis_dialog.isMinimized():
                self._analysis_dialog.showNormal()

            self._analysis_dialog.set_image_and_rect(image_array, roi_rect, file_path)

            if tab:
                self._analysis_dialog.set_current_tab(tab)

            self._analysis_dialog.raise_()
            self._analysis_dialog.activateWindow()

    def show_comparison_dialog(self, tab=None):
        """全 tile の解析 dialog（複数画像）を表示する。

        Args:
            tab: 表示する tab 名（'Histogram', 'Profile', 'Metadata'）。
        """
        # 単一画像の解析 dialog とは同時に開かない
        if self._analysis_dialog is not None and self._analysis_dialog.isVisible():
            self._analysis_dialog.close()
            self._analysis_dialog = None

        tiles_data = self.get_all_tiles_data()

        if not tiles_data:
            QMessageBox.warning(self, "比較", "比較する画像がありません。")
            return

        if self._comparison_dialog is None or not self._comparison_dialog.isVisible():
            self._comparison_dialog = TilingAnalysisDialog(parent=self, tiles_data=tiles_data)

            self._child_dialogs.append(self._comparison_dialog)

            def on_closed():
                if self._comparison_dialog in self._child_dialogs:
                    self._child_dialogs.remove(self._comparison_dialog)
                self._comparison_dialog = None

            self._comparison_dialog.finished.connect(on_closed)

            if tab:
                self._comparison_dialog.set_current_tab(tab)

            self._comparison_dialog.show()
            self._comparison_dialog.raise_()
            self._comparison_dialog.activateWindow()
        else:
            if self._comparison_dialog.isMinimized():
                self._comparison_dialog.showNormal()

            self._comparison_dialog.update_tiles_data(tiles_data)

            if tab:
                self._comparison_dialog.set_current_tab(tab)

            self._comparison_dialog.raise_()
            self._comparison_dialog.activateWindow()

    def sync_scroll(self, source_index: int, direction: str, value: int):
        """source の tile の scroll 位置を他の tile に同期する。"""
        if self.scroll_manager:
            self.scroll_manager.sync_scroll(
                source_index, direction, value, self.zoom_manager.get_scale() if self.zoom_manager else 1.0
            )

    def sync_roi_to_all_tiles(self, roi_rect: QRect):
        if self.roi_manager:
            self.roi_manager.sync_roi_to_all_tiles(roi_rect)

    def select_all_roi(self):
        """active な tile の画像全体を ROI にする。"""
        if self.roi_manager:
            self.roi_manager.select_all_roi()
            self._refresh_comparison_dialog_for_roi()

    def clear_roi(self):
        if self.roi_manager:
            self.roi_manager.clear_roi()
            self._refresh_comparison_dialog_for_roi()

    def copy_active_tile_roi(self):
        """active な tile の ROI の表示画像を clipboard にコピーする。"""
        if self.roi_manager:
            self.roi_manager.copy_active_tile_roi()

    def copy_all_tiles_roi_as_grid(self):
        """全 tile の ROI の表示画像を grid に並べて clipboard にコピーする。"""
        if self.roi_manager:
            self.roi_manager.copy_all_tiles_roi_as_grid(self.grid_size)

    def update_status_bar(self):
        if self.current_mouse_coords:
            ix, iy = self.current_mouse_coords
            self.mouse_coords_label.setText(f"x={ix} y={iy}")
        else:
            self.mouse_coords_label.setText("")

        if self.roi_manager:
            roi_text = self.roi_manager.get_roi_status()
            self.roi_info_label.setText(roi_text)
        else:
            self.roi_info_label.setText("")

        if self.brightness_manager:
            brightness_text = self.brightness_manager.get_brightness_status()
            self.brightness_label.setText(brightness_text)
        else:
            self.brightness_label.setText("")

        if self.zoom_manager:
            scale = self.zoom_manager.get_scale()
            self.scale_label.setText(f" | Scale: {scale:.2f}x")
        else:
            self.scale_label.setText("")

    def _scroll_by_key(self, dx: int, dy: int, is_shift: bool):
        if self.scroll_manager and self.tile_manager:
            active_idx = self.tile_manager.get_active_tile_index()
            self.scroll_manager.scroll_by_key(active_idx, dx, dy)
