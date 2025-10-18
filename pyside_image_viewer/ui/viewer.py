"""Main image viewer application window.

This module provides the ImageViewer class, which is the main window
for displaying and navigating images with analysis tools.

Features:
- Multi-image loading and navigation
- Zoom in/out with keyboard shortcuts
- Pixel-aligned selection with keyboard editing
- Bit-shift operations for raw/scientific images
- Analysis dialogs (histogram, profile, info)
- Difference image creation
- Status bar showing pixel values and coordinates
"""

import os
from typing import Optional
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QStatusBar,
    QLabel,
    QFileDialog,
    QMessageBox,
    QDialog,
)
from PySide6.QtGui import QPixmap, QPainter, QIcon, QGuiApplication, QAction, QActionGroup
from PySide6.QtCore import Qt, QRect, QEvent

from ..core.image_io import numpy_to_qimage, pil_to_numpy, is_image_file
from .widgets import ImageLabel
from .dialogs import HelpDialog, DiffDialog, AnalysisDialog


class ImageViewer(QMainWindow):
    """Main application window for image viewing and analysis.

    The ImageViewer provides a complete interface for:
    - Loading and displaying images (single or multiple files)
    - Navigating between images with keyboard shortcuts (n/b)
    - Zooming with +/- keys
    - Creating and editing pixel-aligned selections
    - Bit-shifting for viewing raw/scientific data (</> keys)
    - Analysis tools (histogram, profile plots)
    - Creating difference images

    Keyboard Shortcuts:
        - Ctrl+A: Select entire image
        - Ctrl+C: Copy selection to clipboard
        - n: Next image
        - b: Previous image
        - +: Zoom in
        - -: Zoom out
        - <: Left bit shift (darker)
        - >: Right bit shift (brighter)
        - ESC: Clear selection

    Attributes:
        images: List of loaded image dictionaries with keys:
                'path', 'array', 'base_array', 'bit_shift'
        current_index: Index of currently displayed image
        scale: Current zoom scale factor
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Image Viewer")
        self.resize(1000, 700)
        self.setMouseTracking(True)

        self.images = []
        self.current_index = None
        self.scale = 1.0

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.current_selection_rect: Optional[QRect] = None

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.image_label = ImageLabel(self, self)
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area)
        self.image_label.installEventFilter(self)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_filename = QLabel()
        self.status_index = QLabel()
        self.status_pixel = QLabel()
        self.status_selection = QLabel()
        self.status_shift = QLabel()
        self.status_scale = QLabel()
        self.status.addWidget(self.status_filename, 2)
        self.status.addWidget(self.status_index, 1)
        self.status.addPermanentWidget(self.status_pixel, 3)
        self.status.addPermanentWidget(self.status_selection, 2)
        self.status.addPermanentWidget(self.status_shift, 1)
        self.status.addPermanentWidget(self.status_scale, 1)

        self.help_dialog = HelpDialog(self)

        self.create_menus()
        self.setAcceptDrops(True)
        # keep references to modeless dialogs so they don't get GC'd
        self._analysis_dialogs = []

    def create_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("ファイル")
        file_menu.addAction(QAction("読み込み...", self, shortcut="Ctrl+O", triggered=self.open_files))
        file_menu.addSeparator()
        file_menu.addAction(QAction("画像全体を選択", self, shortcut="Ctrl+A", triggered=self.select_all))
        file_menu.addAction(
            QAction("選択範囲をコピー", self, shortcut="Ctrl+C", triggered=self.copy_selection_to_clipboard)
        )
        file_menu.addSeparator()
        file_menu.addAction(QAction("閉じる", self, shortcut="Ctrl+W", triggered=self.close_current_image))
        file_menu.addAction(QAction("すべて閉じる", self, shortcut="Ctrl+Shift+W", triggered=self.close_all_images))

        self.img_menu = menubar.addMenu("画像")
        self.update_image_list_menu()

        view_menu = menubar.addMenu("表示")
        view_menu.addAction(QAction("拡大", self, shortcut="+", triggered=lambda: self.set_zoom(self.scale * 2)))
        view_menu.addAction(
            QAction("縮小", self, shortcut="-", triggered=lambda: self.set_zoom(max(0.125, self.scale / 2)))
        )
        view_menu.addSeparator()
        view_menu.addAction(QAction("左ビットシフト", self, shortcut="<", triggered=lambda: self.bit_shift(-1)))
        view_menu.addAction(QAction("右ビットシフト", self, shortcut=">", triggered=lambda: self.bit_shift(1)))
        view_menu.addSeparator()
        view_menu.addAction(QAction("差分画像表示", self, triggered=lambda: self.show_diff_dialog()))

        analysis = menubar.addMenu("解析")
        analysis.addAction(QAction("プロファイル", self, triggered=lambda: self.show_analysis_dialog(tab="Profile")))
        analysis.addAction(QAction("ヒストグラム", self, triggered=lambda: self.show_analysis_dialog(tab="Histogram")))
        analysis.addSeparator()
        analysis.addAction(QAction("メタデータ", self, triggered=lambda: self.show_analysis_dialog(tab="Metadata")))

        help_menu = menubar.addMenu("ヘルプ")
        help_menu.addAction(QAction("キーボードショートカット", self, triggered=self.help_dialog.show))

    def show_analysis_dialog(self, tab: Optional[str] = None):
        # open analysis dialog for current image and current selection
        if self.current_index is None:
            QMessageBox.information(self, "解析", "画像が選択されていません。")
            return
        img = self.images[self.current_index]
        arr = img.get("base_array", img.get("array"))
        sel = self.current_selection_rect
        img_path = img.get("path")
        dlg = AnalysisDialog(self, image_array=arr, image_rect=sel, image_path=img_path)
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
        files, _ = QFileDialog.getOpenFileNames(self, "画像を開く", "", "Images (*.png *.jpg *.tif *.bmp *.jpeg)")
        if files:
            for f in files:
                arr = pil_to_numpy(f)
                img_data = {"path": os.path.abspath(f), "array": arr, "base_array": arr.copy(), "bit_shift": 0}
                self.images.append(img_data)
            if self.current_index is None:
                self.current_index = 0
            self.show_current_image()
            self.update_image_list_menu()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls()]
        image_files = [f for f in files if is_image_file(f)]
        if image_files:
            for f in image_files:
                arr = pil_to_numpy(f)
                img_data = {"path": os.path.abspath(f), "array": arr, "base_array": arr.copy(), "bit_shift": 0}
                self.images.append(img_data)
            if self.current_index is None:
                self.current_index = 0
            self.show_current_image()
            self.update_image_list_menu()

    def update_image_list_menu(self):
        self.img_menu.clear()
        self.img_menu.addAction(QAction("次の画像", self, shortcut="n", triggered=self.next_image))
        self.img_menu.addAction(QAction("前の画像", self, shortcut="b", triggered=self.prev_image))
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
        arr = self.images[self.current_index]["array"]
        self.display_image(arr)
        self.update_image_list_menu()

        # notify open analysis dialogs about new image
        try:
            img = self.images[self.current_index]
            arr_for_analysis = img.get("base_array", img.get("array"))
            img_path = img.get("path", None)
            for dlg in list(self._analysis_dialogs):
                try:
                    dlg.set_image_and_rect(arr_for_analysis, self.current_selection_rect, img_path)
                except Exception:
                    pass
        except Exception:
            pass

        if self.current_selection_rect:
            s = self.scale
            rect = QRect(
                int(self.current_selection_rect.x() * s),
                int(self.current_selection_rect.y() * s),
                int(self.current_selection_rect.width() * s),
                int(self.current_selection_rect.height() * s),
            )
            self.image_label.selection_rect = rect
            self.image_label.update()
            self.update_selection_status(rect)

    def display_image(self, arr):
        """Display an image array in the viewer.

        Args:
            arr: NumPy array of the image to display
        """
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
        dlg = DiffDialog(self, image_list=self.images, default_offset=256)
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
        img_data = {"path": f"diff:{a_idx}-{b_idx}", "array": diff, "base_array": diff.copy(), "bit_shift": 0}
        self.images.append(img_data)
        # switch to the new image
        self.current_index = len(self.images) - 1
        self.show_current_image()

    def set_zoom(self, scale: float):
        """Set the zoom scale, preserving the center of the visible viewport.

        Args:
            scale: New zoom scale factor (1.0 = original size)

        The zoom operation calculates the current viewport center point in
        image coordinates, applies the new scale, then adjusts scroll position
        to keep the same center point visible.
        """
        if self.current_index is None:
            self.scale = scale
            return

        # Get current viewport center in image coordinates before zoom
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

        # Apply new zoom
        self.scale = scale
        arr = self.images[self.current_index]["array"]
        self.display_image(arr)

        # Calculate new scroll position to keep same center
        new_center_x = img_center_x * scale
        new_center_y = img_center_y * scale

        new_h_scroll = int(new_center_x - viewport_width / 2.0)
        new_v_scroll = int(new_center_y - viewport_height / 2.0)

        # Apply new scroll position
        scroll_area.horizontalScrollBar().setValue(new_h_scroll)
        scroll_area.verticalScrollBar().setValue(new_v_scroll)

    def bit_shift(self, amount):
        if self.current_index is None:
            return
        img = self.images[self.current_index]
        base = img["base_array"]
        new_shift = img.get("bit_shift", 0) + amount
        if new_shift >= 0:
            shifted = np.clip(base.astype(np.int32) << new_shift, 0, 255).astype(np.uint8)
        else:
            shifted = np.clip(base.astype(np.int32) >> (-new_shift), 0, 255).astype(np.uint8)

        img["array"] = shifted
        img["bit_shift"] = new_shift
        self.display_image(shifted)
        self.status_shift.setText(f"Shift: {new_shift:+d}")

    def select_all(self):
        """Select the entire image."""
        if self.current_index is None or not self.images:
            return
        self.image_label.set_selection_full()
        # Notify that selection changed (same as manual selection)
        if self.image_label.selection_rect:
            self.on_selection_changed(self.image_label.selection_rect)

    def on_selection_changed(self, rect: QRect):
        s = self.scale
        self.current_selection_rect = QRect(
            int(rect.x() / s),
            int(rect.y() / s),
            int(rect.width() / s),
            int(rect.height() / s),
        )
        self.update_selection_status(rect)
        # notify any open modeless AnalysisDialogs so they can refresh for new selection
        if self._analysis_dialogs:
            # Get current image data
            img = self.images[self.current_index] if self.current_index is not None else None
            if img:
                arr = img.get("base_array", img.get("array"))
                img_path = img.get("path")
                for dlg in list(self._analysis_dialogs):
                    try:
                        dlg.set_image_and_rect(arr, self.current_selection_rect, img_path)
                    except Exception:
                        # ignore dialog-specific errors and continue notifying others
                        pass

    def copy_selection_to_clipboard(self):
        sel = self.current_selection_rect
        if not sel or self.current_index is None:
            QMessageBox.information(self, "コピー", "選択領域がありません。")
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
        else:
            self.status_pixel.setText("")

    def update_status(self):
        if self.current_index is None:
            self.status_filename.setText("No image")
            self.status_index.setText("")
            # still update scale display
            self.status_scale.setText(f"Scale: {self.scale:.2f}x")
            # clear shift when no image
            self.status_shift.setText("")
            return
        p = self.images[self.current_index]["path"]
        self.status_filename.setText(p)
        self.status_index.setText(f"{self.current_index+1}/{len(self.images)}")
        # display current scale
        try:
            self.status_scale.setText(f"Scale: {self.scale:.2f}x")
        except Exception:
            self.status_scale.setText("")
        # display current bit shift for the current image
        try:
            img_info = self.images[self.current_index]
            shift = img_info.get("bit_shift", 0)
            self.status_shift.setText(f"Shift: {shift:+d}")
        except Exception:
            self.status_shift.setText("")

    def update_selection_status(self, rect=None):
        if rect is None or rect.isNull():
            self.status_selection.setText("")
            return
        s = self.scale if hasattr(self, "scale") else 1.0
        x0 = int(rect.left() / s)
        y0 = int(rect.top() / s)
        x1 = int(rect.right() / s)
        y1 = int(rect.bottom() / s)
        w = x1 - x0 + 1
        h = y1 - y0 + 1
        self.status_selection.setText(f"({x0}, {y0}) - ({x1}, {y1}), w: {w}, h: {h}")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.image_label.selection_rect = None
            self.image_label.update()
            self.status_selection.setText("")
            return
        super().keyPressEvent(e)
