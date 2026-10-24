"""複数画像比較の brightness 管理。"""

import math

from PixelScopeViewer.core.constants import MAX_BRIGHTNESS_GAIN, MIN_BRIGHTNESS_GAIN, get_dtype_defaults


class BrightnessManager:
    """全 tile 共通の gain と、dtype group ごとの offset・upper level を管理する。"""

    def __init__(self, tiles: list, tile_dtype_groups: list[str]):
        self.tiles = tiles
        self.tile_dtype_groups = tile_dtype_groups
        self.brightness_gain = 1.0

        self.brightness_params_by_dtype = {}
        for dtype_key in ["uint8", "uint16", "float"]:
            defaults = get_dtype_defaults(dtype_key)
            self.brightness_params_by_dtype[dtype_key] = {
                "offset": defaults["initial_offset"],
                "upper_level": defaults["initial_upper_level"],
            }

    def adjust_gain(self, factor: float):
        """gain に factor を掛け、2 の累乗に丸めて全 tile に適用する。"""
        self.brightness_gain *= factor

        if self.brightness_gain > 0:
            power = round(math.log2(self.brightness_gain))
            self.brightness_gain = 2.0**power

        self.brightness_gain = max(MIN_BRIGHTNESS_GAIN, min(self.brightness_gain, MAX_BRIGHTNESS_GAIN))

        self.refresh_all_tiles()

    def reset_brightness(self):
        """brightness を初期値に戻す。"""
        self.brightness_gain = 1.0

        for dtype_key in ["uint8", "uint16", "float"]:
            defaults = get_dtype_defaults(dtype_key)
            self.brightness_params_by_dtype[dtype_key] = {
                "offset": defaults["initial_offset"],
                "upper_level": defaults["initial_upper_level"],
            }

        self.refresh_all_tiles()

    def refresh_all_tiles(self):
        for tile in self.tiles:
            tile.update_display()

    def refresh_tiles_by_dtype_group(self, dtype_group: str):
        for i, tile in enumerate(self.tiles):
            if self.tile_dtype_groups[i] == dtype_group:
                tile.update_display()

    def on_brightness_dialog_changed(self, full_params: dict):
        """表示設定 dialog の値を適用する。

        Args:
            full_params: dtype group から {gain, offset, upper_level} への dict。gain は全 group で共通。
        """
        if full_params:
            first_group = list(full_params.keys())[0]
            self.brightness_gain = full_params[first_group]["gain"]

        for dtype_group, params in full_params.items():
            self.brightness_params_by_dtype[dtype_group]["offset"] = params["offset"]
            self.brightness_params_by_dtype[dtype_group]["upper_level"] = params["upper_level"]

        self.refresh_all_tiles()

    def get_brightness_params(self) -> dict:
        return {
            "gain": self.brightness_gain,
            "params_by_dtype": self.brightness_params_by_dtype,
        }

    def get_brightness_status(self) -> str:
        """status bar に表示する brightness の文字列を返す。"""
        brightness_parts = [f"Gain: {self.brightness_gain:.2f}"]

        # dtype group ごとの tile 数
        dtype_counts = {}
        for dtype_group in self.tile_dtype_groups:
            dtype_counts[dtype_group] = dtype_counts.get(dtype_group, 0) + 1

        for dtype_group in sorted(dtype_counts.keys()):
            count = dtype_counts[dtype_group]
            params = self.brightness_params_by_dtype[dtype_group]
            if dtype_group == "float":
                brightness_parts.append(
                    f"{dtype_group}({count}): off={params['offset']:.2f} upper={params['upper_level']:.2f}"
                )
            else:
                brightness_parts.append(f"{dtype_group}({count}): off={params['offset']} upper={params['upper_level']}")

        return " | ".join(brightness_parts)
