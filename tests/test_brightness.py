import numpy as np

from PixelScopeViewer.core.brightness import autoscale_range


def test_whole_image():
    arr = np.array([[1, 5], [3, 9]], dtype=np.uint8)
    assert autoscale_range(arr) == (1.0, 9.0)


def test_roi_inside():
    arr = np.arange(16, dtype=np.uint16).reshape(4, 4)
    assert autoscale_range(arr, (1, 1, 2, 2)) == (5.0, 10.0)


def test_roi_partially_outside_uses_inside_part():
    arr = np.arange(16, dtype=np.uint16).reshape(4, 4)
    assert autoscale_range(arr, (2, 2, 10, 10)) == (10.0, 15.0)
    assert autoscale_range(arr, (-3, -3, 4, 4)) == (0.0, 0.0)


def test_roi_outside_returns_none():
    arr = np.zeros((4, 4), dtype=np.uint8)
    assert autoscale_range(arr, (10, 10, 5, 5)) is None
    assert autoscale_range(arr, (4, 0, 2, 2)) is None
    assert autoscale_range(arr, (-5, -5, 2, 2)) is None


def test_empty_roi_returns_none():
    arr = np.zeros((4, 4), dtype=np.uint8)
    assert autoscale_range(arr, (1, 1, 0, 0)) is None


def test_channel_checks():
    arr = np.stack([np.full((2, 2), 1), np.full((2, 2), 50), np.full((2, 2), 9)], axis=2).astype(np.uint8)
    assert autoscale_range(arr, None, [True, False, True]) == (1.0, 9.0)
    assert autoscale_range(arr, None, [False, False, False]) is None
    # channel 数と長さが違っても落ちない
    assert autoscale_range(arr, None, [False, True]) == (50.0, 50.0)
    assert autoscale_range(arr, None, [False, False, False, True]) is None


def test_float_ignores_nan_and_inf():
    arr = np.array([[np.nan, 0.5], [np.inf, 0.25]], dtype=np.float32)
    assert autoscale_range(arr) == (0.25, 0.5)
    assert autoscale_range(np.full((2, 2), np.nan, dtype=np.float32)) is None


def test_merged_dtype_defaults():
    from PixelScopeViewer.core.brightness import merged_dtype_defaults

    merged = merged_dtype_defaults(["uint8", "float", "uint16"])
    assert merged["initial_upper_level"] == 255
    assert merged["is_float_type"] is True
    assert merged["offset_range"] == (-32768, 1e5)
    assert merged["upper_level_range"] == (0, 1e5)
    single = merged_dtype_defaults(["uint16"])
    assert single["is_float_type"] is False
    assert single["upper_level_range"] == (1, 65535)
    assert merged_dtype_defaults([])["initial_upper_level"] == 255


def test_apply_brightness_with_zero_span():
    import warnings

    from PixelScopeViewer.core.brightness import apply_brightness_adjustment

    arr = np.array([[5, 6]], dtype=np.uint16)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = apply_brightness_adjustment(arr, 5, 1.0, 5)
    assert out.tolist() == [[0, 255]]
