"""Main image viewer application window.

This module provides the ImageViewer class, which is the main window
for displaying and navigating images with analysis tools.

Features:
- Multi-image loading and navigation
- Zoom in/out with keyboard shortcuts and Ctrl+mouse wheel
- Pixel-aligned ROI with keyboard editing
- Bit-shift operations for raw/scientific images
- Analysis dialogs (histogram, profile, info)
- Difference image creation
- Status bar showing pixel values and coordinates
- Title bar showing current filename and image index
"""

from pathlib import Path
from typing import Iterable, Optional
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QStatusBar,
    QLabel,
    QFileDialog,
    QMessageBox,
    QDialog,
    QDockWidget,
)
from PySide6.QtGui import QPixmap, QPainter, QIcon, QGuiApplication, QAction, QActionGroup
from PySide6.QtCore import Qt, QRect, QEvent, Signal

from ..core.image_io import numpy_to_qimage, pil_to_numpy, is_image_file
from .widgets import ImageLabel, NavigatorWidget, DisplayInfoWidget, ROIInfoWidget
from .dialogs import HelpDialog, DiffDialog, AnalysisDialog, BrightnessDialog


class ImageViewer(QMainWindow):
    """Main application window for image viewing and analysis.

    The ImageViewer provides a complete interface for:
    - Loading and displaying images (single or multiple files)
    - Navigating between images with keyboard shortcuts (n/b)
    - Zooming with +/- keys and mouse wheel
    - Creating and editing pixel-aligned ROIs
    - Bit-shifting for viewing raw/scientific data (</> keys)
    - Analysis tools (histogram, profile plots)
    - Creating difference images

    Keyboard Shortcuts:
        - Ctrl+A: Select entire image as ROI
        - Ctrl+C: Copy ROI to clipboard
        - n: Next image
        - b: Previous image
        - +: Zoom in (2x)
        - -: Zoom out (0.5x)
        - <: Left bit shift (darker)
        - >: Right bit shift (brighter)
        - ESC: Clear ROI
        - f: Toggle fit to window / original zoom (previous zoom level)

    Mouse Controls:
        - Ctrl + Mouse wheel: Zoom in/out (binary steps: 2x/0.5x, centered on status bar coordinates)
        - Left-drag: Create new ROI rectangle
        - Right-drag: Move existing ROI
        - Left-drag on edges/corners: Resize ROI

    Attributes:
        images: List of loaded image dictionaries with keys:
                'path', 'array', 'base_array', 'bit_shift'
        current_index: Index of currently displayed image
        scale: Current zoom scale factor
    """

    # Signals for widget updates
    scale_changed = Signal()
    image_changed = Signal()
    roi_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Image Viewer")
        self.resize(1000, 700)
        self.setMouseTracking(True)

        self.images = []
        self.current_index = None
        self.scale = 1.0

        # Zoom toggle state
        self.fit_zoom_scale = None
        self.original_zoom_scale = 1.0
        self.original_center_coords = None

        # Track current mouse position in image coordinates for zoom centering
        self.current_mouse_image_coords = None

        # Brightness adjustment parameters
        self.brightness_offset = 0
        self.brightness_gain = 1.0
        self.brightness_saturation = 255

        central = QWidget(self)
        self.setCentralWidget(central)
        h_layout = QHBoxLayout(central)

        self.current_roi_rect: Optional[QRect] = None

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.image_label = ImageLabel(self, self)
        self.scroll_area.setWidget(self.image_label)
        h_layout.addWidget(self.scroll_area)
        self.image_label.installEventFilter(self)

        # Right docks
        # Navigator dock
        self.navigator_dock = QDockWidget("Navigator")
        self.navigator_dock.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)
        navigator_widget = NavigatorWidget(self)
        self.navigator_dock.setWidget(navigator_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.navigator_dock)

        # Info dock with tabs
        from PySide6.QtWidgets import QTabWidget
        self.info_dock = QDockWidget("Info")
        self.info_dock.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)
        
        # Create tab widget
        self.info_tabs = QTabWidget()
        
        # Display info tab
        display_info_widget = DisplayInfoWidget(self)
        self.info_tabs.addTab(display_info_widget, "Display Area")
        
        # ROI info tab
        roi_info_widget = ROIInfoWidget(self)
        self.info_tabs.addTab(roi_info_widget, "ROI Area")
        
        self.info_dock.setWidget(self.info_tabs)
        self.addDockWidget(Qt.RightDockWidgetArea, self.info_dock)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.statusBar().setStyleSheet("font-size: 11pt;")
        self.status_pixel = QLabel()
        self.status_roi = QLabel()
        self.status_brightness = QLabel()  # Changed from status_shift to status_brightness
        self.status_scale = QLabel()
        self.status.addPermanentWidget(self.status_pixel, 2)
        self.status.addPermanentWidget(self.status_roi, 3)
        self.status.addPermanentWidget(self.status_brightness, 2)  # Display brightness params
        self.status.addPermanentWidget(self.status_scale, 1)

        self.help_dialog = HelpDialog(self)
        self.brightness_dialog = None  # Will be created when needed

        self.create_menus()
        self.setAcceptDrops(True)
        # keep references to modeless dialogs so they don't get GC'd
        self._analysis_dialogs = []

    def create_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("ファイル")
        file_menu.addAction(QAction("読み込み...", self, shortcut="Ctrl+O", triggered=self.open_files))
        file_menu.addSeparator()
        file_menu.addAction(QAction("画像全体をROI", self, shortcut="Ctrl+A", triggered=self.select_all))
        file_menu.addAction(
            QAction("ROI領域の画像をコピー", self, shortcut="Ctrl+C", triggered=self.copy_roi_to_clipboard)
        )
        file_menu.addSeparator()
        file_menu.addAction(QAction("閉じる", self, shortcut="Ctrl+W", triggered=self.close_current_image))
        file_menu.addAction(QAction("すべて閉じる", self, shortcut="Ctrl+Shift+W", triggered=self.close_all_images))

        self.img_menu = menubar.addMenu("画像")
        self.update_image_list_menu()

        view_menu = menubar.addMenu("表示")
        view_menu.addAction(QAction("表示輝度調整", self, triggered=self.show_brightness_dialog))
        view_menu.addSeparator()
        view_menu.addAction(QAction("拡大", self, triggered=lambda: self.set_zoom(min(self.scale * 2, 128.0))))
        view_menu.addAction(QAction("縮小", self, triggered=lambda: self.set_zoom(max(self.scale / 2, 0.125))))

        analysis = menubar.addMenu("解析")
        analysis.addAction(QAction("メタデータ", self, triggered=lambda: self.show_analysis_dialog(tab="Metadata")))
        analysis.addSeparator()
        analysis.addAction(QAction("プロファイル", self, triggered=lambda: self.show_analysis_dialog(tab="Profile")))
        analysis.addAction(QAction("ヒストグラム", self, triggered=lambda: self.show_analysis_dialog(tab="Histogram")))
        analysis.addSeparator()
        analysis.addAction(QAction("差分画像表示", self, triggered=lambda: self.show_diff_dialog()))

        help_menu = menubar.addMenu("ヘルプ")
        help_menu.addAction(QAction("キーボードショートカット", self, triggered=self.help_dialog.show))

        # Add global shortcuts
        # Next/Prev image as application-level shortcuts so they work even when dialogs are focused
        self.next_image_action = QAction(self)
        self.next_image_action.setShortcut("n")
        self.next_image_action.setShortcutContext(Qt.ApplicationShortcut)
        self.next_image_action.triggered.connect(self.next_image)
        self.addAction(self.next_image_action)

        self.prev_image_action = QAction(self)
        self.prev_image_action.setShortcut("b")
        self.prev_image_action.setShortcutContext(Qt.ApplicationShortcut)
        self.prev_image_action.triggered.connect(self.prev_image)
        self.addAction(self.prev_image_action)

        self.reset_brightness_action = QAction(self)
        self.reset_brightness_action.setShortcut("Ctrl+R")
        self.reset_brightness_action.setShortcutContext(Qt.ApplicationShortcut)
        self.reset_brightness_action.triggered.connect(self.reset_brightness_settings)
        self.addAction(self.reset_brightness_action)

        self.left_bit_shift_action = QAction(self)
        self.left_bit_shift_action.setShortcut("<")
        self.left_bit_shift_action.setShortcutContext(Qt.ApplicationShortcut)
        self.left_bit_shift_action.triggered.connect(lambda: self.bit_shift(-1))
        self.addAction(self.left_bit_shift_action)

        self.right_bit_shift_action = QAction(self)
        self.right_bit_shift_action.setShortcut(">")
        self.right_bit_shift_action.setShortcutContext(Qt.ApplicationShortcut)
        self.right_bit_shift_action.triggered.connect(lambda: self.bit_shift(1))
        self.addAction(self.right_bit_shift_action)

        self.fit_toggle_action = QAction(self)
        self.fit_toggle_action.setShortcut("f")
        self.fit_toggle_action.setShortcutContext(Qt.ApplicationShortcut)
        self.fit_toggle_action.triggered.connect(self.toggle_fit_zoom)
        self.addAction(self.fit_toggle_action)

        # Zoom shortcuts as application-level shortcuts so they work even when dialogs are focused
        self.zoom_in_action = QAction(self)
        self.zoom_in_action.setShortcut("+")
        self.zoom_in_action.setShortcutContext(Qt.ApplicationShortcut)
        self.zoom_in_action.triggered.connect(lambda: self.set_zoom(min(self.scale * 2, 128.0)))
        self.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction(self)
        self.zoom_out_action.setShortcut("-")
        self.zoom_out_action.setShortcutContext(Qt.ApplicationShortcut)
        self.zoom_out_action.triggered.connect(lambda: self.set_zoom(max(self.scale / 2, 0.125)))
        self.addAction(self.zoom_out_action)

    def show_brightness_dialog(self):
        """表示輝度調整ダイアログを表示します。

        現在選択中の画像が存在しない場合は情報ダイアログを表示して終了します。

        このメソッドはダイアログを初めて作成する際にダイアログを生成し、
        ダイアログからのシグナルを購読してビューア側の輝度パラメータを同期します。

        例外やエラーは GUI 内でユーザ向けに通知されます。
        """
        if self.current_index is None:
            QMessageBox.information(self, "表示輝度調整", "画像が選択されていません。")
            return

        img = self.images[self.current_index]
        arr = img.get("base_array", img.get("array"))
        img_path = img.get("path")

        # Create dialog if it doesn't exist
        if self.brightness_dialog is None:
            self.brightness_dialog = BrightnessDialog(self, arr, img_path)
            self.brightness_dialog.brightness_changed.connect(self.on_brightness_changed)
            # Initialize status bar with current parameters
            params = self.brightness_dialog.get_parameters()
            self.brightness_offset = params[0]
            self.brightness_gain = params[1]
            self.brightness_saturation = params[2]
            self.update_brightness_status()
        else:
            # Update dialog for new image
            self.brightness_dialog.update_for_new_image(arr, img_path)
            # Note: update_for_new_image will emit brightness_changed signal
            # which will update the status bar through on_brightness_changed

        self.brightness_dialog.show()

    def reset_brightness_settings(self):
        """輝度設定を初期値に戻します（Ctrl+R 等から呼び出されます）。

        動作:
        - 現在画像のビットシフトを 0 に戻す
        - 表示配列を base_array に復元する
        - 輝度ダイアログが開いている場合はダイアログ側のリセット処理に委譲し、
          ダイアログが閉じている場合はビューア側でパラメータを手動でリセットします。
        """
        handled_by_dialog = False

        # Reset bit shift to 0 and restore base array
        if self.current_index is not None:
            img = self.images[self.current_index]
            img["bit_shift"] = 0
            img["array"] = img["base_array"].copy()

        if self.brightness_dialog is not None:
            # Let the dialog emit the reset signal so the viewer stays in sync
            self.brightness_dialog.reset_parameters()
            handled_by_dialog = True
        else:
            # Reset brightness parameters manually when dialog is closed
            self.brightness_offset = 0
            self.brightness_gain = 1.0
            self.brightness_saturation = 255
            self.update_brightness_status()

        # Refresh display if the dialog didn't already trigger it
        if not handled_by_dialog and self.current_index is not None:
            self.display_image(self.images[self.current_index]["array"])

    def on_brightness_changed(self, offset, gain, saturation):
        """Handle brightness parameter changes.

        Args:
            offset: Offset value
            gain: Gain value
            saturation: Saturation level
        """
        self.brightness_offset = offset
        self.brightness_gain = gain
        self.brightness_saturation = saturation

        # Update status bar
        self.update_brightness_status()

        # Refresh display with new brightness settings
        if self.current_index is not None:
            self.display_image(self.images[self.current_index]["array"])

    def apply_brightness_adjustment(self, arr: np.ndarray) -> np.ndarray:
        """画像配列に対して輝度補正を適用して新しい配列を返します。

        使用する式:
            yout = gain * (yin - offset) / saturation * 255

        パラメータ:
            arr: 入力画像の NumPy 配列（任意の dtype を受け付けます）

        戻り値:
            uint8 にクリップ/変換された補正後の配列を返します。

        注意:
            saturation が 0 の場合はゼロ除算を避けるため元配列をそのまま返します。
        """
        # Avoid division by zero
        if self.brightness_saturation == 0:
            return arr

        # Apply formula with proper type conversion
        adjusted = (
            self.brightness_gain * (arr.astype(np.float32) - self.brightness_offset) / self.brightness_saturation * 255
        )

        # Clip to valid range and convert back to uint8
        return np.clip(adjusted, 0, 255).astype(np.uint8)

    def show_analysis_dialog(self, tab: Optional[str] = None):
        # open analysis dialog for current image and current ROI
        if self.current_index is None:
            QMessageBox.information(self, "解析", "画像が選択されていません。")
            return
        img = self.images[self.current_index]
        arr = img.get("base_array", img.get("array"))
        sel = self.current_roi_rect
        img_path = img.get("path")
        pil_img = img.get("pil_image")  # Get cached PIL image
        dlg = AnalysisDialog(self, image_array=arr, image_rect=sel, image_path=img_path, pil_image=pil_img)
        dlg.show()
        # keep a reference until the dialog is closed
        self._analysis_dialogs.append(dlg)
        dlg.finished.connect(lambda _: self._analysis_dialogs.remove(dlg) if dlg in self._analysis_dialogs else None)
        # if a tab was requested, set it
        if tab is not None:
            try:
                dlg.set_current_tab(tab)
            except Exception:
                pass

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "画像を開く", "", "Images (*.png *.jpg *.tif *.bmp *.jpeg *.exr *.npy)"
        )
        new_count = self._add_images(files)
        self._finalize_image_addition(new_count)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls()]
        image_files = [f for f in files if is_image_file(f)]
        new_count = self._add_images(image_files)
        self._finalize_image_addition(new_count)

    def _add_images(self, paths: Iterable[str]) -> int:
        """Load image files and append them to the viewer."""
        new_images = []
        for path in paths or []:
            if not path:
                continue
            try:
                arr, pil_img = pil_to_numpy(path)
            except Exception:
                continue
            img_data = {
                "path": str(Path(path).resolve()),
                "array": arr,
                "base_array": arr.copy(),
                "bit_shift": 0,
                "pil_image": pil_img,  # Store PIL image for metadata extraction
            }
            new_images.append(img_data)

        if not new_images:
            return 0

        self.images.extend(new_images)
        return len(new_images)

    def _finalize_image_addition(self, new_count: int) -> None:
        """Select the newly added images and refresh UI state."""
        if new_count <= 0:
            return
        if self.current_index is None:
            self.current_index = 0
        else:
            self.current_index = len(self.images) - new_count
        self.show_current_image()
        self.update_image_list_menu()

    def update_image_list_menu(self):
        self.img_menu.clear()
        # Menu entries for navigation (shortcuts are provided as application-level actions)
        self.img_menu.addAction(QAction("次の画像", self, triggered=self.next_image))
        self.img_menu.addAction(QAction("前の画像", self, triggered=self.prev_image))
        self.img_menu.addSeparator()

        group = QActionGroup(self)
        group.setExclusive(True)
        for i, info in enumerate(self.images):
            act = QAction(info["path"], self)
            act.setCheckable(True)
            # set checked state/icons first to avoid emitting triggered during setup
            if i == self.current_index:
                act.setChecked(True)
                pix = QPixmap(12, 12)
                pix.fill(Qt.transparent)
                p = QPainter(pix)
                p.setBrush(Qt.black)
                p.drawEllipse(2, 2, 8, 8)
                p.end()
                act.setIcon(QIcon(pix))
            # connect after initial state is configured
            act.triggered.connect(self.make_show_callback(i))
            group.addAction(act)
            self.img_menu.addAction(act)

    def make_show_callback(self, idx):
        def fn(checked=None):
            # QAction.triggered may send a checked argument; accept it but ignore
            self.current_index = idx
            # guard: ensure index still valid
            if 0 <= idx < len(self.images):
                self.show_current_image()
            else:
                # if images changed, refresh menu
                self.update_image_list_menu()

        return fn

    def show_current_image(self):
        if self.current_index is None or not self.images:
            self.image_label.clear()
            self.update_status()
            return

        # Reset zoom toggle state when switching images
        self.fit_zoom_scale = None
        self.original_zoom_scale = 1.0
        self.original_center_coords = None

        # Reset bit shift when switching images and restore base array
        img = self.images[self.current_index]
        if "bit_shift" not in img or img["bit_shift"] != 0:
            img["bit_shift"] = 0
            if "base_array" in img:
                img["array"] = img["base_array"].copy()

        arr = img["array"]
        self.display_image(arr)
        self.image_changed.emit()
        self.update_image_list_menu()

        # Update brightness dialog if it's open
        if self.brightness_dialog is not None and self.brightness_dialog.isVisible():
            img = self.images[self.current_index]
            arr_for_brightness = img.get("base_array", img.get("array"))
            img_path = img.get("path", None)
            # Keep current brightness settings when switching images
            self.brightness_dialog.update_for_new_image(arr_for_brightness, img_path, keep_settings=True)

        # notify open analysis dialogs about new image
        try:
            img = self.images[self.current_index]
            arr_for_analysis = img.get("base_array", img.get("array"))
            img_path = img.get("path", None)
            pil_img = img.get("pil_image")
            for dlg in list(self._analysis_dialogs):
                try:
                    dlg.set_image_and_rect(arr_for_analysis, self.current_selection_rect, img_path, pil_img)
                except Exception:
                    pass
        except Exception:
            pass

        if self.current_roi_rect:
            s = self.scale
            rect = QRect(
                int(self.current_roi_rect.x() * s),
                int(self.current_roi_rect.y() * s),
                int(self.current_roi_rect.width() * s),
                int(self.current_roi_rect.height() * s),
            )
            self.image_label.roi_rect = rect
            self.image_label.update()
            self.update_roi_status(rect)

        # notify any open modeless AnalysisDialogs so they can refresh for new image
        if self._analysis_dialogs:
            img = self.images[self.current_index] if self.current_index is not None else None
            if img:
                arr = img.get("base_array", img.get("array"))
                img_path = img.get("path")
                pil_img = img.get("pil_image")
                for dlg in list(self._analysis_dialogs):
                    try:
                        dlg.set_image_and_rect(arr, self.current_roi_rect, img_path, pil_img)
                    except Exception:
                        pass

    def display_image(self, arr):
        """指定した画像配列をビューアに表示します。

        引数で渡された配列に対して現在の輝度パラメータがデフォルトでない場合は
        apply_brightness_adjustment を経由して補正を行い、QImage に変換して `ImageLabel` に渡します。

        パラメータ:
            arr: NumPy 配列（H,W[,C]）で表された画像データ
        """
        # Apply brightness adjustment if parameters are not default
        if self.brightness_offset != 0 or self.brightness_gain != 1.0 or self.brightness_saturation != 255:
            arr = self.apply_brightness_adjustment(arr)

        qimg = numpy_to_qimage(arr)
        self.image_label.set_image(qimg, self.scale)
        self.update_status()

    def next_image(self):
        if not self.images:
            return
        self.current_index = (self.current_index + 1) % len(self.images)
        self.show_current_image()

    def prev_image(self):
        if not self.images:
            return
        self.current_index = (self.current_index - 1) % len(self.images)
        self.show_current_image()

    def close_current_image(self):
        if self.current_index is None:
            return
        del self.images[self.current_index]
        if not self.images:
            self.current_index = None
        else:
            self.current_index = min(self.current_index, len(self.images) - 1)
        self.show_current_image()

    def close_all_images(self):
        self.images.clear()
        self.current_index = None
        # update UI and image menu
        try:
            self.show_current_image()
        except Exception:
            pass
        # ensure image menu is cleared
        try:
            self.update_image_list_menu()
        except Exception:
            pass
        # notify analysis dialogs that there's no image now
        for dlg in list(self._analysis_dialogs):
            try:
                dlg.set_image_and_rect(None, None)
            except Exception:
                pass

    def show_diff_dialog(self):
        if len(self.images) < 2:
            QMessageBox.information(self, "差分", "比較する画像が2枚必要です。")
            return
        dlg = DiffDialog(self, image_list=self.images, default_offset=127)
        if dlg.exec() != QDialog.Accepted:
            return
        a_idx, b_idx, offset = dlg.get_result()
        if a_idx is None or b_idx is None:
            return
        a = self.images[a_idx]["array"].astype(int)
        b = self.images[b_idx]["array"].astype(int)
        # compute diff with offset and clip
        try:
            diff = (a - b + int(offset)).clip(0, 255).astype("uint8")
        except Exception:
            QMessageBox.information(self, "差分", "差分の作成に失敗しました。画像サイズや型を確認してください。")
            return
        img_data = {"path": f"diff:{a_idx+1}-{b_idx+1}", "array": diff, "base_array": diff.copy(), "bit_shift": 0}
        self.images.append(img_data)
        # switch to the new image
        self.current_index = len(self.images) - 1
        self.show_current_image()

    def _apply_zoom_and_update_display(self, scale: float):
        """Apply zoom scale and update display. Common logic for all zoom methods.

        Args:
            scale: New zoom scale factor (1.0 = original size)
        """
        self.scale = scale
        arr = self.images[self.current_index]["array"]
        self.display_image(arr)

    def _calculate_viewport_center_in_image_coords(self) -> tuple[float, float]:
        """Calculate current viewport center in image coordinates.

        Returns:
            (img_x, img_y) tuple of center point in image coordinates
        """
        scroll_area = self.scroll_area
        old_h_scroll = scroll_area.horizontalScrollBar().value()
        old_v_scroll = scroll_area.verticalScrollBar().value()
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()

        # Calculate center point in widget coordinates
        old_center_x = old_h_scroll + viewport_width / 2.0
        old_center_y = old_v_scroll + viewport_height / 2.0

        # Convert to image coordinates (independent of scale)
        old_scale = self.scale
        if old_scale > 0:
            img_center_x = old_center_x / old_scale
            img_center_y = old_center_y / old_scale
        else:
            img_center_x = old_center_x
            img_center_y = old_center_y

        return (img_center_x, img_center_y)

    def _set_scroll_to_keep_image_point_at_position(
        self, img_coords: tuple[float, float], target_pos: tuple[float, float]
    ):
        """Set scroll position to keep an image point at a target widget position.

        Args:
            img_coords: (x, y) in image coordinates
            target_pos: (x, y) in widget coordinates where the image point should appear
        """
        img_x, img_y = img_coords
        target_x, target_y = target_pos

        # Calculate where the image point appears in the new scale
        new_widget_x = img_x * self.scale
        new_widget_y = img_y * self.scale

        # Calculate required scroll position
        scroll_area = self.scroll_area
        new_h_scroll = int(new_widget_x - target_x)
        new_v_scroll = int(new_widget_y - target_y)

        # Apply new scroll position
        scroll_area.horizontalScrollBar().setValue(new_h_scroll)
        scroll_area.verticalScrollBar().setValue(new_v_scroll)

    def set_zoom(self, scale: float):
        """ズーム倍率を設定し、可視領域の中心位置を維持します。

        パラメータ:
            scale: 新しい倍率（1.0 が原寸）

        このメソッドは表示中の画像がない場合は単に scale を設定して終了します。
        """
        if self.current_index is None:
            self.scale = scale
            return

        # Get current viewport center in image coordinates
        img_center = self._calculate_viewport_center_in_image_coords()

        # Apply new zoom
        self._apply_zoom_and_update_display(scale)

        # Calculate viewport center position for target
        scroll_area = self.scroll_area
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()
        center_pos = (viewport_width / 2.0, viewport_height / 2.0)

        # Keep center point at viewport center
        self._set_scroll_to_keep_image_point_at_position(img_center, center_pos)

        self.scale_changed.emit()

    def set_zoom_at_status_coords(self, scale: float):
        """ステータスバーに表示している座標（マウス位置）をビュー中心に固定してズームします。

        マウス位置が未取得（None）の場合は通常の center ベースの `set_zoom` にフォールバックします。
        """
        if self.current_index is None:
            self.scale = scale
            return

        if self.current_mouse_image_coords is None:
            # If no valid mouse coordinates, fall back to center zoom
            self.set_zoom(scale)
            return

        # Apply new zoom
        self._apply_zoom_and_update_display(scale)

        # Get viewport center for positioning
        scroll_area = self.scroll_area
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()
        center_pos = (viewport_width / 2.0, viewport_height / 2.0)

        # Place the status coordinates at the center of the viewport
        self._set_scroll_to_keep_image_point_at_position(self.current_mouse_image_coords, center_pos)

        self.scale_changed.emit()

    def set_zoom_at_coords(self, scale: float, image_coords: tuple[float, float]):
        """指定した画像座標をビューポート中心に維持してズーム倍率を設定します。

        パラメータ:
            scale: 新しい倍率（1.0 が原寸）
            image_coords: (x, y) 維持する画像座標

        このメソッドは表示中の画像がない場合は単に scale を設定して終了します。
        """
        if self.current_index is None:
            self.scale = scale
            return

        # Apply new zoom
        self._apply_zoom_and_update_display(scale)

        # Get viewport center for positioning
        scroll_area = self.scroll_area
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()
        center_pos = (viewport_width / 2.0, viewport_height / 2.0)

        # Place the image_coords at the center of the viewport
        self._set_scroll_to_keep_image_point_at_position(image_coords, center_pos)

        self.scale_changed.emit()

    def fit_to_window(self):
        """画像をウィンドウにフィットさせるズーム倍率を設定します。

        画像のアスペクト比を維持して、ウィンドウのサイズに合わせてスケールを計算し、
        最も近いバイナリ倍率（2の累乗）にスナップします。
        """
        if self.current_index is None:
            return
        img = self.images[self.current_index]["array"]
        h, w = img.shape[:2]
        viewport = self.scroll_area.viewport()
        vh = viewport.height()
        wh = viewport.width()
        scale_h = vh / h
        scale_w = wh / w
        fit_scale = min(scale_h, scale_w)
        # Clamp to valid zoom range
        fit_scale = max(0.125, min(128.0, fit_scale))
        # Snap to nearest power of 2
        power = round(np.log2(fit_scale))
        snapped_scale = 2.0**power
        self.set_zoom(snapped_scale)

    def toggle_fit_zoom(self):
        """Fitと直前の拡大率をトグルします。

        現在のスケールがfitスケールに近い場合は直前の拡大率に戻し、
        そうでなければ現在のスケールを記憶してfitにします。
        """
        if self.current_index is None:
            return
        if self.fit_zoom_scale is not None and abs(self.scale - self.fit_zoom_scale) < 1e-6:
            # Currently at fit zoom, go back to original zoom, maintaining the original center
            if self.original_center_coords is not None:
                self.set_zoom_at_coords(self.original_zoom_scale, self.original_center_coords)
            else:
                self.set_zoom(self.original_zoom_scale)
        else:
            # Not at fit zoom, remember current center and scale as original, go to fit
            self.original_zoom_scale = self.scale
            self.original_center_coords = self._calculate_viewport_center_in_image_coords()
            self.fit_to_window()
            self.fit_zoom_scale = self.scale

    def bit_shift(self, amount):
        """ビットシフト（表示の明るさ操作）を行います。

        説明:
            - amount が負の場合は左シフト（暗くする）
            - amount が正の場合は右シフト（明るくする）
            - シフトに合わせて内部の gain を 2 倍/半分に調整し、
              近い 2^n 値にスナップします。

        制限:
            - uint8 データは左シフト最大 -7 ビットに制限しています（値の破綻を防ぐため）。
            - 右シフトは最大 +10 ビットまで許容します。
        """
        if self.current_index is None:
            return
        img = self.images[self.current_index]
        base = img["base_array"]
        current_shift = img.get("bit_shift", 0)
        new_shift = current_shift + amount

        # Apply limits based on data type
        dtype = base.dtype
        if np.issubdtype(dtype, np.uint8):
            # For uint8, left shift max is 7 bits (since we have 8 bits total)
            max_left_shift = -7
        else:
            # For other types, use same limit
            max_left_shift = -7

        # Right shift max is 10 bits (1024x)
        max_right_shift = 10

        # Clamp shift amount
        new_shift = max(max_left_shift, min(max_right_shift, new_shift))

        # If shift didn't change (already at limit), do nothing
        if new_shift == current_shift:
            return

        if new_shift >= 0:
            shifted = np.clip(base.astype(np.int32) << new_shift, 0, 255).astype(np.uint8)
        else:
            shifted = np.clip(base.astype(np.int32) >> (-new_shift), 0, 255).astype(np.uint8)

        img["array"] = shifted
        img["bit_shift"] = new_shift

        # Update gain: left shift -> darker (gain /= 2), right shift -> brighter (gain *= 2)
        current_gain = self.brightness_gain

        if amount < 0:  # Left shift - darker
            new_gain = current_gain * 0.5
        else:  # Right shift - brighter
            new_gain = current_gain * 2.0

        # Snap to nearest power of 2 or 0.5
        # Valid values: ..., 0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, ...
        if new_gain >= 1.0:
            # Round to nearest power of 2
            power = round(np.log2(new_gain))
            snapped_gain = 2.0**power
        else:
            # Round to nearest power of 0.5 (which is 2^-n)
            power = round(np.log2(new_gain))
            snapped_gain = 2.0**power

        # Don't clamp - allow values outside normal range for extreme bit shifts
        # The UI will handle display appropriately

        # Update brightness_gain property
        self.brightness_gain = snapped_gain

        # Update dialog if it exists
        if self.brightness_dialog is not None:
            self.brightness_dialog.set_gain(snapped_gain)

        # Update status bar
        self.update_brightness_status()

        self.display_image(shifted)

    def select_all(self):
        """画像全体をROI状態にします。

        選択が更新された場合は on_roi_changed を経由して関連ダイアログに通知します。
        """
        if self.current_index is None or not self.images:
            return
        self.image_label.set_roi_full()
        # Notify that ROI changed (same as manual ROI)
        if self.image_label.roi_rect:
            self.on_roi_changed(self.image_label.roi_rect)

    def on_roi_changed(self, rect: QRect):
        s = self.scale
        self.current_roi_rect = QRect(
            int(rect.x() / s),
            int(rect.y() / s),
            int(rect.width() / s),
            int(rect.height() / s),
        )
        self.update_roi_status(rect)
        # notify any open modeless AnalysisDialogs so they can refresh for new ROI
        if self._analysis_dialogs:
            # Get current image data
            img = self.images[self.current_index] if self.current_index is not None else None
            if img:
                arr = img.get("base_array", img.get("array"))
                img_path = img.get("path")
                pil_img = img.get("pil_image")
                for dlg in list(self._analysis_dialogs):
                    try:
                        dlg.set_image_and_rect(arr, self.current_roi_rect, img_path, pil_img)
                    except Exception:
                        # ignore dialog-specific errors and continue notifying others
                        pass

        self.roi_changed.emit()

    def copy_roi_to_clipboard(self):
        sel = self.current_roi_rect
        if not sel or self.current_index is None:
            QMessageBox.information(self, "コピー", "ROI領域がありません。")
            return

        arr = self.images[self.current_index]["array"]
        x, y, w, h = sel.x(), sel.y(), sel.width(), sel.height()
        sub = arr[y : y + h, x : x + w]
        QGuiApplication.clipboard().setImage(numpy_to_qimage(sub))

    def eventFilter(self, obj, event):
        if obj is self.image_label and event.type() == QEvent.MouseMove:
            self.update_mouse_status(event.position().toPoint())
            return False
        return super().eventFilter(obj, event)

    def update_mouse_status(self, pos):
        if self.current_index is None or not self.images:
            self.status_pixel.setText("")
            self.current_mouse_image_coords = None
            return
        img = self.images[self.current_index]
        # prefer base_array (unshifted) for status display when available
        arr = img.get("base_array", img.get("array"))
        s = self.scale if self.scale > 0 else 1.0
        ix = int(pos.x() / s)
        iy = int(pos.y() / s)
        h, w = arr.shape[:2]
        if 0 <= iy < h and 0 <= ix < w:
            v = arr[iy, ix]
            if np.ndim(v) == 0:
                val_str = str(int(v))
            else:
                val_str = "(" + ",".join(str(int(x)) for x in np.ravel(v)) + ")"
            self.status_pixel.setText(f"x={ix} y={iy} val={val_str}")
            # Store current image coordinates for zoom centering
            self.current_mouse_image_coords = (ix, iy)
        else:
            self.status_pixel.setText("")
            self.current_mouse_image_coords = None

    def update_status(self):
        """Update status bar with current image info and brightness parameters."""
        if self.current_index is None:
            # Update title bar to show no image
            self.setWindowTitle("PySide6 Image Viewer")
            # still update scale display
            self.status_scale.setText(f"Scale: {self.scale:.2f}x")
            # clear brightness when no image
            self.status_brightness.setText("")
            return
        p = self.images[self.current_index]["path"]

        # Update title bar with filename and index
        filename = Path(p).name
        title = f"{filename} ({self.current_index+1}/{len(self.images)})"
        self.setWindowTitle(title)

        # display current scale
        try:
            self.status_scale.setText(f"Scale: {self.scale:.2f}x")
        except Exception:
            self.status_scale.setText("")

        # Display brightness parameters instead of bit shift
        self.update_brightness_status()

    def update_brightness_status(self):
        """ステータスバーに現在の輝度パラメータを表示用に整形して設定します。

        表示用の文字列整形は値の大きさに応じて桁数を調整します（小さい値は小数点以下を多く表示）。
        """
        try:
            # Format offset
            if isinstance(self.brightness_offset, (int, np.integer)):
                offset_str = str(self.brightness_offset)
            else:
                offset_str = f"{self.brightness_offset:.1f}"

            # Format gain - use more decimals for small values, fewer for large values
            if self.brightness_gain < 0.01:
                gain_str = f"{self.brightness_gain:.6f}"
            elif self.brightness_gain < 0.1:
                gain_str = f"{self.brightness_gain:.5f}"
            elif self.brightness_gain >= 100:
                gain_str = f"{self.brightness_gain:.1f}"
            else:
                gain_str = f"{self.brightness_gain:.2f}"

            # Format saturation
            if isinstance(self.brightness_saturation, (int, np.integer)):
                sat_str = str(self.brightness_saturation)
            else:
                sat_str = f"{self.brightness_saturation:.1f}"

            brightness_text = f"Offset: {offset_str}, Gain: {gain_str}, Sat: {sat_str}"
            self.status_brightness.setText(brightness_text)
        except Exception as e:
            self.status_brightness.setText("")

    def update_roi_status(self, rect=None):
        # Prefer the canonical image-coordinate ROI for consistent display
        if self.current_roi_rect is not None and not self.current_roi_rect.isNull():
            x0 = self.current_roi_rect.x()
            y0 = self.current_roi_rect.y()
            w = self.current_roi_rect.width()
            h = self.current_roi_rect.height()
            x1 = x0 + w - 1
            y1 = y0 + h - 1
            self.status_roi.setText(f"({x0}, {y0}) - ({x1}, {y1}), w: {w}, h: {h}")
            return
        # Fallback: derive from provided label-rect when current ROI is missing
        if rect is None or rect.isNull():
            self.status_roi.setText("")
            return
        s = self.scale if hasattr(self, "scale") else 1.0
        x0 = int(rect.left() / s)
        y0 = int(rect.top() / s)
        x1 = int(rect.right() / s)
        y1 = int(rect.bottom() / s)
        w = x1 - x0 + 1
        h = y1 - y0 + 1
        self.status_roi.setText(f"({x0}, {y0}) - ({x1}, {y1}), w: {w}, h: {h}")

    def set_roi_from_image_rect(self, rect_img: QRect):
        """Set ROI using image coordinates and update label, status, and listeners.

        This avoids lossy roundtrip via label coordinates when zoomed, ensuring
        spin box edits map 1:1 to the internal ROI regardless of scale.
        """
        try:
            self.current_roi_rect = rect_img
            # Project to label/widget coordinates for display
            s = self.scale if hasattr(self, "scale") else 1.0
            rect_label = QRect(
                int(rect_img.x() * s),
                int(rect_img.y() * s),
                int(rect_img.width() * s),
                int(rect_img.height() * s),
            )
            self.image_label.roi_rect = rect_label
            self.image_label.update()
            # Update status based on canonical image ROI
            self.update_roi_status()

            # Notify any open modeless AnalysisDialogs
            if self._analysis_dialogs:
                img = self.images[self.current_index] if self.current_index is not None else None
                if img:
                    arr = img.get("base_array", img.get("array"))
                    img_path = img.get("path")
                    pil_img = img.get("pil_image")
                    for dlg in list(self._analysis_dialogs):
                        try:
                            dlg.set_image_and_rect(arr, self.current_roi_rect, img_path, pil_img)
                        except Exception:
                            pass
            # Emit ROI changed for dependent widgets (e.g., ROIInfo)
            self.roi_changed.emit()
        except Exception:
            # Best effort; avoid crashing on edge cases
            self.roi_changed.emit()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.image_label.roi_rect = None
            self.image_label.update()
            self.status_roi.setText("")
            return
        super().keyPressEvent(e)
