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
