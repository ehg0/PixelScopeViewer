"""brightness の値の変換と表示用の整形。"""

import math


def clamp_value(value, min_val, max_val):
    return max(min_val, min(max_val, value))


def slider_to_value(slider_value, is_float, multiplier=10):
    """slider の位置を値に変換する。float の場合は multiplier で割る。"""
    if is_float:
        return slider_value / multiplier
    return slider_value


def value_to_slider(value, is_float, multiplier=10):
    """値を slider の位置に変換する。float の場合は multiplier を掛ける。"""
    if is_float:
        return int(value * multiplier)
    return int(value)


def round_to_power_of_2(value, log2_min=-7, log2_max=10):
    """2^log2_min 〜 2^log2_max の範囲で、最も近い 2 の累乗に丸める。"""
    if value <= 0:
        return 1.0

    log2_val = math.log2(value)
    nearest_log2 = round(log2_val)
    clamped_log2 = clamp_value(nearest_log2, log2_min, log2_max)
    return 2**clamped_log2


def format_value_label(value, is_float):
    if is_float:
        return f"{value:.5f}"
    return f"{int(value)}"


def format_gain_label(gain):
    """gain を表示用に整形する。値が小さいほど小数桁を増やす。"""
    if gain < 0.01:
        return f"{gain:.6f}"
    elif gain < 0.1:
        return f"{gain:.5f}"
    elif gain >= 100:
        return f"{gain:.1f}"
    else:
        return f"{gain:.2f}"
