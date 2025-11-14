"""Brightness management for tiling comparison."""

import math
from typing import List, Dict

from PixelScopeViewer.core.constants import MIN_BRIGHTNESS_GAIN, MAX_BRIGHTNESS_GAIN
from PixelScopeViewer.ui.dialogs.display.tabs.logic import get_dtype_defaults


class BrightnessManager:
    """Manages brightness parameters for all tiles."""

    def __init__(self, tiles: List, tile_dtype_groups: List[str]):
        """Initialize brightness manager.

        Args:
            tiles: List of TileWidget instances
            tile_dtype_groups: List of dtype groups for each tile
        """
        self.tiles = tiles
        self.tile_dtype_groups = tile_dtype_groups
        self.brightness_gain = 1.0

        # Use centralized defaults from main viewer
        self.brightness_params_by_dtype = {}
        for dtype_key in ["uint8", "uint16", "float"]:
            defaults = get_dtype_defaults(dtype_key)
            self.brightness_params_by_dtype[dtype_key] = {
                "offset": defaults["initial_offset"],
                "saturation": defaults["initial_saturation"],
            }

    def adjust_gain(self, factor: float):
        """Adjust gain (all tiles) using binary steps (powers of 2).

        Args:
            factor: Multiplication factor (2.0 for increase, 0.5 for decrease)
        """
        # Apply factor
        self.brightness_gain *= factor

        # Snap to nearest power of 2 for clean binary steps
        if self.brightness_gain > 0:
            power = round(math.log2(self.brightness_gain))
            self.brightness_gain = 2.0**power

        # Clamp to reasonable range using centralized constants
        self.brightness_gain = max(MIN_BRIGHTNESS_GAIN, min(self.brightness_gain, MAX_BRIGHTNESS_GAIN))

        self.refresh_all_tiles()

    def reset_brightness(self):
        """Reset all brightness parameters."""
        self.brightness_gain = 1.0

        # Reset to centralized defaults
        for dtype_key in ["uint8", "uint16", "float"]:
            defaults = get_dtype_defaults(dtype_key)
            self.brightness_params_by_dtype[dtype_key] = {
                "offset": defaults["initial_offset"],
                "saturation": defaults["initial_saturation"],
            }

        self.refresh_all_tiles()

    def refresh_all_tiles(self):
        """Refresh display for all tiles."""
        for tile in self.tiles:
            tile.update_display()

    def refresh_tiles_by_dtype_group(self, dtype_group: str):
        """Refresh tiles of specific dtype group."""
        for i, tile in enumerate(self.tiles):
            if self.tile_dtype_groups[i] == dtype_group:
                tile.update_display()

    def on_brightness_dialog_changed(self, full_params: Dict):
        """Handle brightness change from dialog.

        Args:
            full_params: Dict mapping dtype groups to {gain, offset, saturation}
        """
        # Update gain from first entry (they're all the same)
        if full_params:
            first_group = list(full_params.keys())[0]
            self.brightness_gain = full_params[first_group]["gain"]

        # Update per-dtype params
        for dtype_group, params in full_params.items():
            self.brightness_params_by_dtype[dtype_group]["offset"] = params["offset"]
            self.brightness_params_by_dtype[dtype_group]["saturation"] = params["saturation"]

        self.refresh_all_tiles()

    def get_brightness_params(self) -> Dict:
        """Get current brightness parameters."""
        return {
            "gain": self.brightness_gain,
            "params_by_dtype": self.brightness_params_by_dtype,
        }

    def get_brightness_status(self) -> str:
        """Get brightness status text for status bar."""
        brightness_parts = [f"Gain: {self.brightness_gain:.2f}"]

        # Count tiles per dtype
        dtype_counts = {}
        for dtype_group in self.tile_dtype_groups:
            dtype_counts[dtype_group] = dtype_counts.get(dtype_group, 0) + 1

        # Add dtype info
        for dtype_group in sorted(dtype_counts.keys()):
            count = dtype_counts[dtype_group]
            params = self.brightness_params_by_dtype[dtype_group]
            if dtype_group == "float":
                brightness_parts.append(
                    f"{dtype_group}({count}): off={params['offset']:.2f} sat={params['saturation']:.2f}"
                )
            else:
                brightness_parts.append(f"{dtype_group}({count}): off={params['offset']} sat={params['saturation']}")

        return " | ".join(brightness_parts)
