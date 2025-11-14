"""Tile widget for displaying individual images in tiling comparison."""

from typing import Optional
import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QPalette

from .tile_image_label import TileImageLabel


class TileWidget(QWidget):
    """Widget for displaying a single tile with image and status."""

    # Signals
    activated = Signal(int)  # Emitted when tile is clicked (passes tile index)
    roi_changed = Signal(object)  # Emitted when ROI changes (passes roi_rect as list or None)
    mouse_coords_changed = Signal(object)  # Emitted when mouse coordinates change (passes (ix, iy) or None)

    def __init__(self, image_data: dict, parent_dialog, tile_index: int):
        """Initialize tile widget.

        Args:
            image_data: Image data dictionary
            parent_dialog: Parent TilingComparisonDialog
            tile_index: Index of this tile in the grid
        """
        super().__init__()

        self.image_data = image_data
        self.parent_dialog = parent_dialog
        self.tile_index = tile_index
        self.is_active = False

        self._build_ui()

    def _build_ui(self):
        """Build the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # Frame for visual feedback
        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.Box)
        self.frame.setLineWidth(2)
        self._update_frame_style()

        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # Status bar at top with filename (left) and pixel value (right)
        status_widget = QWidget()
        status_widget.setMaximumHeight(24)
        status_widget.setStyleSheet(
            """
            QWidget {
                background-color: rgba(50, 50, 50, 200);
            }
        """
        )
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(4, 4, 4, 4)
        status_layout.setSpacing(8)

        # Filename label (left-aligned)
        self.filename_label = QLabel("")
        self.filename_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.filename_label.setStyleSheet(
            """
            QLabel {
                color: white;
                font-size: 11pt;
                font-weight: bold;
                background-color: transparent;
            }
        """
        )
        status_layout.addWidget(self.filename_label, 1)

        # Pixel value label (right-aligned)
        self.pixel_value_label = QLabel("")
        self.pixel_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.pixel_value_label.setMinimumWidth(100)  # Reserve space for pixel values
        self.pixel_value_label.setStyleSheet(
            """
            QLabel {
                color: white;
                font-size: 11pt;
                background-color: transparent;
            }
        """
        )
        status_layout.addWidget(self.pixel_value_label, 0)

        frame_layout.addWidget(status_widget)

        # Scroll area + Image label
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.image_label = TileImageLabel()
        self.image_label.roi_changed.connect(self._on_roi_changed)
        # Activate on click inside image
        self.image_label.clicked.connect(lambda: self.activated.emit(self.tile_index))
        # Ctrl+wheel zoom request from label
        self.image_label.zoom_requested.connect(self._on_zoom_requested)
        # Connect hover info to display pixel value
        self.image_label.hover_info.connect(self._on_hover_info)
        self.scroll_area.setWidget(self.image_label)
        # Catch wheel events from multiple surfaces to ensure sync
        self.image_label.installEventFilter(self)
        self.scroll_area.viewport().installEventFilter(self)
        self.scroll_area.installEventFilter(self)
        frame_layout.addWidget(self.scroll_area)

        layout.addWidget(self.frame)

        # Make widget clickable
        self.setFocusPolicy(Qt.ClickFocus)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and (
            obj is self.scroll_area.viewport() or obj is self.scroll_area or obj is self.image_label
        ):
            # Ctrl+wheel => zoom handled here
            if event.modifiers() & Qt.ControlModifier:
                dy = event.pixelDelta().y() if not event.pixelDelta().isNull() else event.angleDelta().y()
                if dy != 0:
                    factor = 2.0 if dy > 0 else 0.5
                    # Get mouse position in viewport coordinates
                    # Event position is relative to the object that received it, so convert to viewport coords
                    event_pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                    if obj is self.scroll_area.viewport():
                        mouse_pos = event_pos
                    elif obj is self.image_label:
                        # Convert from image_label coordinates to viewport coordinates
                        mouse_pos = self.image_label.mapTo(self.scroll_area.viewport(), event_pos)
                    elif obj is self.scroll_area:
                        # Convert from scroll_area coordinates to viewport coordinates
                        mouse_pos = self.scroll_area.mapTo(self.scroll_area.viewport(), event_pos)
                    else:
                        mouse_pos = event_pos
                    self._on_zoom_requested(factor, mouse_pos)
                    return True
            # No Ctrl => allow default scrolling, then trigger sync manually
            vsb = self.scroll_area.verticalScrollBar()
            hsb = self.scroll_area.horizontalScrollBar()

            # Store current scroll positions before event
            old_v = vsb.value() if vsb else 0
            old_h = hsb.value() if hsb else 0

            # Let the event propagate to trigger actual scrolling
            # Don't accept it here, so it reaches the scroll area
            result = False  # Let event continue to be processed

            # Use a timer to check after the event has been fully processed
            from PySide6.QtCore import QTimer

            def check_and_sync():
                # After wheel scroll, manually trigger sync ONLY if scrollbar actually moved
                if vsb and vsb.value() != old_v:
                    try:
                        self.parent_dialog.sync_scroll(self.tile_index, "v", vsb.value())
                    except Exception:
                        pass
                if hsb and hsb.value() != old_h:
                    try:
                        self.parent_dialog.sync_scroll(self.tile_index, "h", hsb.value())
                    except Exception:
                        pass

            QTimer.singleShot(0, check_and_sync)
            return result
        return super().eventFilter(obj, event)

    def _on_zoom_requested(self, factor: float, mouse_pos=None):
        # Delegate to parent dialog to keep all tiles in sync
        try:
            self.parent_dialog.adjust_zoom(factor, tile_index=self.tile_index, mouse_pos=mouse_pos)
        except Exception:
            pass

    def mousePressEvent(self, event):
        """Handle mouse press to activate tile."""
        if event.button() == Qt.LeftButton:
            self.activated.emit(self.tile_index)
        super().mousePressEvent(event)

    def set_active(self, active: bool):
        """Set active state of the tile.

        Args:
            active: Whether this tile is active
        """
        self.is_active = active
        self._update_frame_style()

        # Enable/disable ROI editing
        self.image_label.set_roi_editable(active)

    def _update_frame_style(self):
        """Update frame style based on active state."""
        if self.is_active:
            # Active tile: blue border
            self.frame.setStyleSheet(
                """
                QFrame {
                    border: 2px solid #0078d4;
                    background-color: palette(window);
                }
            """
            )
        else:
            # Inactive tile: gray border
            self.frame.setStyleSheet(
                """
                QFrame {
                    border: 2px solid #cccccc;
                    background-color: palette(window);
                }
            """
            )

    def _on_roi_changed(self, roi_rect):
        """Handle ROI change from image label."""
        self.roi_changed.emit(roi_rect)

    def _on_hover_info(self, ix: int, iy: int, value_text: str):
        """Handle hover info from image label and notify parent dialog.

        Args:
            ix: Image x coordinate
            iy: Image y coordinate
            value_text: Formatted pixel value text (not used, parent handles display)
        """
        # Only notify parent dialog of coordinates, let parent update all tiles
        if value_text:
            self.mouse_coords_changed.emit((ix, iy))
        else:
            self.mouse_coords_changed.emit(None)

    def set_image(self, array: np.ndarray, gain: float, offset: float, saturation: float):
        """Set image data with brightness parameters.

        Args:
            array: Image array to display
            gain: Brightness gain
            offset: Brightness offset
            saturation: Saturation value
        """
        self.image_label.set_image(array, gain, offset, saturation)

    def set_image_data(self, image_data: dict):
        """Set new image data for this tile.

        Args:
            image_data: Image data dictionary
        """
        self.image_data = image_data
        self.update_display()

    def update_display(self):
        """Update display with current brightness parameters."""
        arr = self.image_data.get("base_array")
        if arr is None:
            return

        # Get brightness parameters from parent dialog
        dtype_group = self.parent_dialog.tile_dtype_groups[self.tile_index]
        params = self.parent_dialog.brightness_params_by_dtype[dtype_group]
        gain = self.parent_dialog.brightness_gain

        self.image_label.set_image(arr, gain, params["offset"], params["saturation"])

        # Update filename display
        path = self.image_data.get("path", f"Image {self.tile_index + 1}")
        from pathlib import Path

        filename = Path(path).name if path else f"Image {self.tile_index + 1}"
        self.filename_label.setText(filename)

    def get_displayed_array(self) -> np.ndarray:
        """Get currently displayed array.

        Returns:
            Image array
        """
        return self.image_data.get("base_array")

    def update_status(self, text: str):
        """Update pixel value display.

        Args:
            text: Pixel value text to display
        """
        self.pixel_value_label.setText(text)

    def set_roi(self, roi_rect: Optional[list]):
        """Set ROI rectangle.

        Args:
            roi_rect: ROI rectangle [x, y, w, h] or None
        """
        self.image_label.set_roi(roi_rect)

    def set_roi_from_image_coords(self, roi_rect, is_active: bool):
        """Set ROI from QRect in image coordinates.

        Args:
            roi_rect: QRect in image coordinates or None
            is_active: Whether this tile is active
        """
        if roi_rect and not roi_rect.isEmpty():
            self.image_label.set_roi([roi_rect.x(), roi_rect.y(), roi_rect.width(), roi_rect.height()])
        else:
            self.image_label.set_roi(None)

    def get_roi(self) -> Optional[list]:
        """Get current ROI rectangle.

        Returns:
            ROI rectangle [x, y, w, h] or None
        """
        return self.image_label.get_roi()

    def clear_roi(self):
        """Clear ROI."""
        self.image_label.clear_roi()

    def select_all_roi(self, array_shape: tuple):
        """Select entire image as ROI.

        Args:
            array_shape: Shape of the image array (H, W) or (H, W, C)
        """
        h, w = array_shape[:2]
        self.image_label.set_roi([0, 0, w, h])

    def get_zoom_factor(self) -> float:
        """Get current zoom factor.

        Returns:
            Zoom factor
        """
        return self.image_label.zoom_factor

    def set_zoom(self, factor: float):
        """Set zoom factor.

        Args:
            factor: Zoom factor
        """
        self.image_label.set_zoom(factor)

    def fit_to_view(self):
        """Fit image to view."""
        self.image_label.fit_to_view()
