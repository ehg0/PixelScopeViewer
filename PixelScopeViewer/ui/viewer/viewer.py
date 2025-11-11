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
from PySide6.QtGui import QPixmap, QPainter, QIcon, QGuiApplication, QAction, QActionGroup, QPixmap
from PySide6.QtCore import Qt, QRect, QEvent, Signal

from ...core.image_io import numpy_to_qimage, load_image, is_image_file
from ..utils import (
    get_default_channel_colors,
    ChannelColorManager,
    MODE_1CH_GRAYSCALE,
    MODE_1CH_JET,
    MODE_2CH_COMPOSITE,
    MODE_2CH_FLOW_HSV,
    apply_jet_colormap,
    flow_to_hsv_rgb,
)
from ..widgets import ImageLabel, NavigatorWidget, DisplayInfoWidget, ROIInfoWidget
from ..dialogs import HelpDialog, DiffDialog, AnalysisDialog
from ..dialogs import FeaturesDialog
from ..utils.features_manager import FeaturesManager

from .menu_builder import create_menus
from .zoom_manager import ZoomManager
from .brightness_manager import BrightnessManager
from .status_updater import StatusUpdater
from ..dialogs.display.core.compute import apply_brightness_adjustment_float


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
                'path', 'array', 'base_array'
        current_index: Index of currently displayed image
        scale: Current zoom scale factor
    """

    # Signals for widget updates
    scale_changed = Signal()
    image_changed = Signal()
    roi_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PixelScopeViewer")
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

        # Channel selection parameters
        self.channel_checks = []
        self.channel_colors = []

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
        self.navigator_widget = NavigatorWidget(self)
        self.navigator_dock.setWidget(self.navigator_widget)
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

        # Initialize managers
        self.zoom_manager = ZoomManager(self)
        self.brightness_manager = BrightnessManager(self)
        self.status_updater = StatusUpdater(self)

        # Features manager / dialog
        self.features_manager = FeaturesManager()
        self._features_dialog = None

        # Centralized channel color/mode manager
        self.color_manager = ChannelColorManager()

        create_menus(self)
        self.setAcceptDrops(True)
        # keep references to modeless dialogs so they don't get GC'd
        self._analysis_dialog = None

    # Delegate zoom methods to zoom_manager
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

    # Delegate brightness methods to brightness_manager
    def show_brightness_dialog(self):
        self.brightness_manager.show_brightness_dialog()

    def reset_brightness_settings(self):
        self.brightness_manager.reset_brightness_settings()

    def adjust_gain_step(self, amount):
        self.brightness_manager.adjust_gain_step(amount)

    def apply_brightness_adjustment(self, arr: np.ndarray) -> np.ndarray:
        return self.brightness_manager.apply_brightness_adjustment(arr)

    # Delegate status update methods to status_updater
    def update_mouse_status(self, pos):
        self.status_updater.update_mouse_status(pos)

    def update_status(self):
        self.status_updater.update_status()

    def update_brightness_status(self):
        self.status_updater.update_brightness_status()

    def update_roi_status(self, rect=None):
        self.status_updater.update_roi_status(rect)

    # Image loading and navigation
    def show_analysis_dialog(self, tab: Optional[str] = None):
        """Show analysis dialog for current image and ROI."""
        # Ignore bool argument from QAction.triggered(bool) signal
        if isinstance(tab, bool):
            tab = None
        # open analysis dialog for current image and current ROI
        if self.current_index is None:
            QMessageBox.information(self, "解析", "画像が選択されていません。")
            return

        # If dialog already exists, bring it to front
        if self._analysis_dialog is not None:
            if self._analysis_dialog.isMinimized():
                self._analysis_dialog.showNormal()
            self._analysis_dialog.raise_()
            self._analysis_dialog.activateWindow()
            if tab is not None:
                try:
                    self._analysis_dialog.set_current_tab(tab)
                except Exception:
                    pass
            return

        img = self.images[self.current_index]
        arr = img.get("base_array", img.get("array"))
        sel = self.current_roi_rect
        img_path = img.get("path")
        dlg = AnalysisDialog(self, image_array=arr, image_rect=sel, image_path=img_path)
        dlg.show()
        # keep a reference until the dialog is closed
        self._analysis_dialog = dlg
        dlg.finished.connect(lambda: setattr(self, "_analysis_dialog", None))
        # if a tab was requested, set it
        if tab is not None:
            try:
                dlg.set_current_tab(tab)
            except Exception:
                pass

    def open_files(self):
        """Open file dialog to load image files."""
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
        feature_files = [f for f in files if Path(f).suffix.lower() in (".json", ".csv")]

        # Load images
        new_count = self._add_images(image_files)
        self._finalize_image_addition(new_count)

        # Load feature files
        if feature_files:
            try:
                self.features_manager.load_feature_files(feature_files)
                if self._features_dialog is not None:
                    self._features_dialog.refresh_from_manager()
            except Exception:
                # Non-fatal
                pass

    def _prepare_thumbnail_array(self, arr: np.ndarray) -> np.ndarray:
        """Prepare array for thumbnail display using current display modes.

        Returns an image array (grayscale or RGB) that matches the current
        Channel tab display settings for 1ch and 2ch images.
        """
        # 1ch image handling
        if arr.ndim == 2 or (arr.ndim == 3 and arr.shape[2] == 1):
            # Apply brightness for consistency with main view
            adj = self.apply_brightness_adjustment(arr)
            if self.color_manager.mode_1ch == MODE_1CH_JET:
                if adj.ndim == 3 and adj.shape[2] == 1:
                    adj = adj[..., 0]
                return apply_jet_colormap(adj)
            else:
                # Grayscale thumbnail
                if adj.ndim == 3 and adj.shape[2] == 1:
                    adj = adj[..., 0]
                return adj

        # 2ch image handling
        if arr.ndim == 3 and arr.shape[2] == 2:
            if self.color_manager.mode_2ch == MODE_2CH_FLOW_HSV:
                # サムネイルでは明るさ調整をスキップ（元データから直接HSV変換）
                rgb = flow_to_hsv_rgb(arr)
                return rgb
            else:
                # Composite mode: apply brightness then composite with current checks/colors
                adj = self.apply_brightness_adjustment(arr)
                h, w, c = adj.shape
                n = c
                # Align checks and colors
                checks = (self.channel_checks or [])[:]
                if len(checks) < n:
                    checks.extend([True] * (n - len(checks)))
                if len(self.channel_colors) != n:
                    colors = self.color_manager.get_colors(n)
                else:
                    colors = self.color_manager.resolve_with_existing(n, self.channel_colors)
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

        # For other cases, return original
        return arr

    def _show_load_error(self, path: str, arr=None, error_msg: str = ""):
        """Show error message with file details."""
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

    def _add_images(self, paths: Iterable[str]) -> int:
        """Load image files and append them to the viewer."""
        new_images = []
        for path in paths or []:
            if not path:
                continue
            try:
                arr = load_image(path)
                # Validate array shape
                if arr.ndim < 2 or arr.ndim > 3:
                    self._show_load_error(path, arr, "2次元または3次元の配列が必要です")
                    continue
                if arr.ndim == 3 and arr.shape[2] not in [1, 2, 3, 4]:
                    self._show_load_error(path, arr, "チャンネル数は1, 2, 3, または4である必要があります")
                    continue

                # Create and cache thumbnail pixmap on load
                thumb_arr = self._prepare_thumbnail_array(arr)
                thumb_qimg = numpy_to_qimage(thumb_arr)
                thumb_pixmap = QPixmap.fromImage(thumb_qimg).scaled(
                    250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            except Exception as e:
                self._show_load_error(path, error_msg=str(e))
                continue
            img_data = {
                "path": str(Path(path).resolve()),
                "array": arr,
                "base_array": arr.copy(),
                "thumbnail_pixmap": thumb_pixmap,  # Cache thumbnail
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

    # ------------------------
    # Features: load + dialog
    # ------------------------
    # Removed: feature file opening moved into FeaturesDialog menu

    def show_features_dialog(self):
        if self._features_dialog is not None:
            # Update title with latest loaded path
            title = "特徴量表示"
            last_path = self.features_manager.get_last_loaded_path()
            if last_path:
                title = f"特徴量表示 - {last_path}"
            self._features_dialog.setWindowTitle(title)
            if self._features_dialog.isMinimized():
                self._features_dialog.showNormal()
            self._features_dialog.raise_()
            self._features_dialog.activateWindow()
            return
        dlg = FeaturesDialog(self, self.features_manager)
        dlg.show()
        self._features_dialog = dlg
        dlg.finished.connect(lambda: setattr(self, "_features_dialog", None))

    def update_image_list_menu(self):
        """Update the image list menu with current loaded images."""
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
        """Create callback function to show image at specific index."""

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
        """Display the currently selected image."""
        if self.current_index is None or not self.images:
            self.image_label.clear()
            self.update_status()
            return

        # Reset zoom toggle state when switching images
        self.fit_zoom_scale = None
        self.original_zoom_scale = 1.0
        self.original_center_coords = None

        # Initialize channel checks and colors for new image
        img = self.images[self.current_index]
        arr = img["array"]
        if arr.ndim >= 3:
            n_channels = arr.shape[2]

            # Always load colors and checks for this channel count from the manager
            self.channel_colors = self.color_manager.get_colors(n_channels)
            self.channel_checks = self.color_manager.get_checks(n_channels)
        else:
            # For grayscale images, keep empty lists
            self.channel_checks = []
            self.channel_colors = []
            pass

        arr = img["array"]
        # Load per-dtype brightness parameters only if not already set by user
        # This preserves dialog adjustments while providing sensible defaults
        try:
            dtype_key = self.brightness_manager._dtype_key(arr.dtype)
            # Check if current params match this dtype's stored params
            stored_params = self.brightness_manager._params_by_dtype.get(dtype_key)
            current_params = (self.brightness_offset, self.brightness_gain, self.brightness_saturation)

            # Only load stored params if they differ (indicating a dtype switch)
            if stored_params and stored_params != current_params:
                self.brightness_offset, self.brightness_gain, self.brightness_saturation = stored_params
                self.update_brightness_status()
        except Exception:
            pass
        self.display_image(arr)
        self.image_changed.emit()
        self.update_image_list_menu()

        # Update brightness dialog if it exists (even if not visible)
        if self.brightness_dialog is not None:
            img = self.images[self.current_index]
            arr_for_brightness = img.get("base_array", img.get("array"))
            img_path = img.get("path", None)
            # Keep current brightness settings when switching images
            self.brightness_dialog.update_for_new_image(
                arr_for_brightness,
                img_path,
                keep_settings=True,
                channel_checks=self.channel_checks,
                channel_colors=self.channel_colors,
                initial_mode_1ch=self.color_manager.mode_1ch,
                initial_mode_2ch=self.color_manager.mode_2ch,
            )

        # notify open analysis dialogs about new image
        try:
            img = self.images[self.current_index]
            arr_for_analysis = img.get("base_array", img.get("array"))
            img_path = img.get("path", None)
            if self._analysis_dialog:
                try:
                    self._analysis_dialog.set_image_and_rect(arr_for_analysis, self.current_roi_rect, img_path)
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
        if self._analysis_dialog:
            img = self.images[self.current_index] if self.current_index is not None else None
            if img:
                arr = img.get("base_array", img.get("array"))
                img_path = img.get("path")
                try:
                    self._analysis_dialog.set_image_and_rect(arr, self.current_roi_rect, img_path)
                except Exception:
                    pass

    def _get_displayed_array(self) -> Optional[np.ndarray]:
        """Return the processed numpy array that is currently being displayed."""
        if self.current_index is None:
            return None

        arr = self.images[self.current_index]["array"]

        # The following logic is a copy of display_image, but returns the array
        # instead of setting it on the label.

        # Special pseudo-color modes
        try:
            if arr.ndim == 2 or (arr.ndim == 3 and arr.shape[2] == 1):
                if self.color_manager.mode_1ch == MODE_1CH_JET:
                    adj = self.apply_brightness_adjustment(arr)
                    if adj.ndim == 3 and adj.shape[2] == 1:
                        adj = adj[..., 0]
                    return apply_jet_colormap(adj)
            elif arr.ndim == 3 and arr.shape[2] == 2:
                if self.color_manager.mode_2ch == MODE_2CH_FLOW_HSV:
                    return flow_to_hsv_rgb(arr)
        except Exception:
            # Fallback to normal processing
            pass

        # Brightness adjustment
        apply_adjust = False
        if np.issubdtype(arr.dtype, np.floating):
            apply_adjust = True
        elif self.brightness_offset != 0 or self.brightness_gain != 1.0 or self.brightness_saturation != 255:
            apply_adjust = True

        if apply_adjust:
            arr = self.apply_brightness_adjustment(arr)

        # Channel selection and color synthesis
        if arr.ndim >= 3 and self.channel_checks:
            n_channels = arr.shape[2]
            if len(self.channel_checks) < n_channels:
                self.channel_checks.extend([True] * (n_channels - len(self.channel_checks)))
            if len(self.channel_colors) != n_channels:
                self.channel_colors = self.color_manager.get_colors(n_channels)
            else:
                self.channel_colors = self.color_manager.resolve_with_existing(n_channels, self.channel_colors)

            selected_channels = [i for i, checked in enumerate(self.channel_checks) if checked]
            if not selected_channels:
                return np.zeros((arr.shape[0], arr.shape[1], 3), dtype=np.uint8)

            composite = np.zeros((arr.shape[0], arr.shape[1], 3), dtype=np.float32)
            for channel_idx in selected_channels:
                if channel_idx < len(self.channel_colors):
                    color = self.channel_colors[channel_idx]
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
            return (np.clip(composite, 0, 1) * 255).astype(np.uint8)

        return arr

    def display_image(self, arr):
        """Display image array in the viewer with current zoom and adjustments.

        Args:
            arr: NumPy array (H,W[,C]) representing image data
        """
        processed_arr = self._get_displayed_array()
        if processed_arr is None:
            # Fallback for safety, though _get_displayed_array should handle it
            processed_arr = arr

        qimg = numpy_to_qimage(processed_arr)
        self.image_label.set_image(qimg, self.scale)
        self.update_status()

    def next_image(self):
        """Navigate to next image in the list."""
        if not self.images:
            return
        self.current_index = (self.current_index + 1) % len(self.images)
        self.show_current_image()

    def prev_image(self):
        """Navigate to previous image in the list."""
        if not self.images:
            return
        self.current_index = (self.current_index - 1) % len(self.images)
        self.show_current_image()

    def close_current_image(self):
        """Close the currently displayed image."""
        if self.current_index is None:
            return
        del self.images[self.current_index]
        if not self.images:
            self.current_index = None
        else:
            self.current_index = min(self.current_index, len(self.images) - 1)
        self.show_current_image()

    def close_all_images(self):
        """Close all loaded images."""
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
        if self._analysis_dialog:
            try:
                self._analysis_dialog.set_image_and_rect(None, None)
            except Exception:
                pass

    def show_diff_dialog(self):
        """Show difference image creation dialog."""
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

        # Create and cache thumbnail for the diff image
        thumb_arr = self._prepare_thumbnail_array(diff)
        thumb_qimg = numpy_to_qimage(thumb_arr)
        thumb_pixmap = QPixmap.fromImage(thumb_qimg).scaled(
            self.navigator_widget.thumbnail_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        img_data = {
            "path": f"diff:{a_idx+1}-{b_idx+1}",
            "array": diff,
            "base_array": diff.copy(),
            "thumbnail_pixmap": thumb_pixmap,
        }
        self.images.append(img_data)
        # switch to the new image
        self.current_index = len(self.images) - 1
        self.show_current_image()

    # ROI operations
    def select_all(self):
        """Set entire image as ROI and notify related dialogs."""
        if self.current_index is None or not self.images:
            return
        self.image_label.set_roi_full()
        # Notify that ROI changed (same as manual ROI)
        if self.image_label.roi_rect:
            self.on_roi_changed(self.image_label.roi_rect)

    def on_roi_changed(self, rect: QRect):
        """Handle ROI change events."""
        s = self.scale
        self.current_roi_rect = QRect(
            int(rect.x() / s),
            int(rect.y() / s),
            int(rect.width() / s),
            int(rect.height() / s),
        )
        self.update_roi_status(rect)
        # notify any open modeless AnalysisDialogs so they can refresh for new ROI
        if self._analysis_dialog:
            # Get current image data
            img = self.images[self.current_index] if self.current_index is not None else None
            if img:
                arr = img.get("base_array", img.get("array"))
                img_path = img.get("path")
                try:
                    self._analysis_dialog.set_image_and_rect(arr, self.current_roi_rect, img_path)
                except Exception:
                    # ignore dialog-specific errors and continue notifying others
                    pass

        self.roi_changed.emit()

    def copy_roi_to_clipboard(self):
        """Copy ROI region or the entire displayed image to clipboard."""
        if self.current_index is None:
            QMessageBox.information(self, "コピー", "画像がありません。")
            return

        # Get the currently displayed numpy array (with all adjustments)
        displayed_arr = self._get_displayed_array()
        if displayed_arr is None:
            QMessageBox.information(self, "コピー", "表示されている画像データを取得できません。")
            return

        sel = self.current_roi_rect
        if sel and not sel.isEmpty():
            # ROI is in original image coordinates, which matches the array coordinates
            x, y, w, h = sel.x(), sel.y(), sel.width(), sel.height()
            # Ensure ROI is within the array bounds before slicing
            h_arr, w_arr = displayed_arr.shape[:2]
            if x < w_arr and y < h_arr:
                sub_arr = displayed_arr[y : y + h, x : x + w]
                qimg = numpy_to_qimage(sub_arr)
            else:
                qimg = None  # ROI is outside the image
        else:
            # If no ROI, use the entire displayed array
            qimg = numpy_to_qimage(displayed_arr)

        if qimg and not qimg.isNull():
            QGuiApplication.clipboard().setImage(qimg)
        else:
            QMessageBox.information(self, "コピー", "クリップボードにコピーする画像を作成できませんでした。")

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
            if self._analysis_dialog:
                img = self.images[self.current_index] if self.current_index is not None else None
                if img:
                    arr = img.get("base_array", img.get("array"))
                    img_path = img.get("path")
                    try:
                        self._analysis_dialog.set_image_and_rect(arr, self.current_roi_rect, img_path)
                    except Exception:
                        pass
            # Emit ROI changed for dependent widgets (e.g., ROIInfo)
            self.roi_changed.emit()
        except Exception:
            # Best effort; avoid crashing on edge cases
            self.roi_changed.emit()

    # Event handlers
    def eventFilter(self, obj, event):
        """Filter events to update status on mouse move."""
        if obj is self.image_label and event.type() == QEvent.MouseMove:
            self.update_mouse_status(event.position().toPoint())
            return False
        return super().eventFilter(obj, event)

    def keyPressEvent(self, e):
        """Handle key press events (ESC to clear ROI)."""
        if e.key() == Qt.Key_Escape:
            self.image_label.roi_rect = None
            self.image_label.update()
            self.status_roi.setText("")
            return

        super().keyPressEvent(e)

    def closeEvent(self, event):
        """Handle window close event to ensure all child dialogs are closed."""
        # Close all modeless dialogs to ensure the application exits cleanly
        if self.brightness_dialog and self.brightness_dialog.isVisible():
            self.brightness_dialog.close()
        if self._features_dialog and self._features_dialog.isVisible():
            self._features_dialog.close()
        if self._analysis_dialog and self._analysis_dialog.isVisible():
            self._analysis_dialog.close()
        if self.help_dialog and self.help_dialog.isVisible():
            self.help_dialog.close()

        event.accept()
