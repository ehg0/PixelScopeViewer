import numpy as np

from PixelScopeViewer.core.statistics import histogram_step_edges


def test_step_edges_uniform_bins():
    edges, keep = histogram_step_edges(np.array([0.0, 1.0, 2.0]), 1.0)
    assert edges.tolist() == [-0.5, 0.5, 1.5, 2.5]
    assert keep.all()


def test_step_edges_single_bin_draws_one_interval():
    edges, keep = histogram_step_edges(np.array([5.0]), 2.0)
    assert edges.tolist() == [4.0, 6.0] and keep.tolist() == [True]


def test_step_edges_uneven_bins_use_midpoints():
    edges, _ = histogram_step_edges(np.array([0.0, 1.0, 3.0]), 1.0)
    assert edges.tolist() == [-0.5, 0.5, 2.0, 3.5]


def test_step_edges_log_x_drops_nonpositive_and_mirrors_left_edge():
    edges, keep = histogram_step_edges(np.array([0.0, 1.0, 2.0]), 1.0, log_x=True)
    assert keep.tolist() == [False, True, True]
    # x=1 の左端 0.5 は正なのでそのまま
    assert edges.tolist() == [0.5, 1.5, 2.5]
    edges, keep = histogram_step_edges(np.array([0.25, 0.75]), 1.0, log_x=True)
    # 左端 -0.25 は log にできないため、0.25 を中心に右端 0.5 を log 上で鏡映する
    assert np.allclose(np.log10(edges), [2 * np.log10(0.25) - np.log10(0.5), np.log10(0.5), np.log10(1.25)])
    assert (edges > 0).all()


def test_step_edges_log_x_without_positive_bins():
    edges, keep = histogram_step_edges(np.array([-1.0, 0.0]), 1.0, log_x=True)
    assert edges.size == 0 and not keep.any()


def test_hist_bins_single_value_makes_one_bin():
    from PixelScopeViewer.core.statistics import determine_hist_bins, histogram_series

    a = np.array([[7]], dtype=np.uint16)
    xs, ys = histogram_series(a, bins=determine_hist_bins(a, 1.0))["I"]
    assert xs.tolist() == [7.0] and ys.tolist() == [1]
    f = np.array([[0.5]], dtype=np.float32)
    xs, ys = histogram_series(f, bins=determine_hist_bins(f, 1.0))["I"]
    assert ys.tolist() == [1]


def test_hist_bins_max_value_has_own_bin():
    from PixelScopeViewer.core.statistics import determine_hist_bins, histogram_series

    a = np.arange(20, dtype=np.uint8).reshape(4, 5)
    xs, ys = histogram_series(a, bins=determine_hist_bins(a, 1.0))["I"]
    assert xs.tolist() == list(range(20)) and ys.tolist() == [1] * 20
    xs, ys = histogram_series(a, bins=determine_hist_bins(a, 4.0))["I"]
    assert xs.tolist() == [0, 4, 8, 12, 16] and ys.tolist() == [4] * 5
    f = np.array([0.0, 0.25, 1.0], dtype=np.float32)
    bins = determine_hist_bins(f, 0.1)
    assert np.isclose(bins[-1], 1.1)


def test_merge_hist_series_pads_by_bin_step():
    from PixelScopeViewer.core.statistics import merge_hist_series

    series = {"R0 C0": (np.array([0.15]), np.array([1])), "R1 C0": (np.array([0.15, 0.25]), np.array([2, 3]))}
    merged = merge_hist_series(series, "Histogram", 0.1)
    xs, ys = merged["R0 C0"]
    assert np.allclose(xs, [0.05, 0.15, 0.25, 0.35]) and ys.tolist() == [0, 1, 0, 0]
    assert merged["R1 C0"][1].tolist() == [0, 2, 3, 0]
    # step を渡さない場合は従来どおり（1 点だけなら 1.0）
    assert np.allclose(
        merge_hist_series({"a": (np.array([0.15]), np.array([1]))}, "Histogram")["a"][0], [-0.85, 0.15, 1.15]
    )


def test_histogram_series_channels_and_visible_channels():
    from PixelScopeViewer.core.statistics import determine_hist_bins, histogram_series, visible_channels

    a = np.dstack([np.full((2, 2), 0.05), np.full((2, 2), 0.95)]).astype(np.float32)
    checks = [True, False]
    bins = determine_hist_bins(visible_channels(a, checks), 0.1)
    s = histogram_series(a, bins=bins, channels=checks)
    assert list(s) == ["C0"]
    xs, ys = s["C0"]
    # 非表示の C1（0.95）に引っ張られず、C0 の 1 bin だけになる
    assert np.allclose(xs, [0.05]) and ys.tolist() == [4]
    # 表示 ON がない・全 ON・channels なしは元の配列
    assert visible_channels(a, [False, False]) is a and visible_channels(a, [True, True]) is a
    assert visible_channels(a, None) is a
    # 1ch は channels に関わらず計算する
    assert list(histogram_series(a[..., 0], bins=bins, channels=[False])) == ["I"]


def test_histogram_series_int_bins_count_uses_common_range():
    from PixelScopeViewer.core.statistics import histogram_series

    a = np.dstack([np.array([[0, 1]]), np.array([[2, 3]])]).astype(np.uint8)
    s = histogram_series(a, bins=4)
    assert s["C0"][0].tolist() == [0, 1, 2, 3] and s["C0"][1].tolist() == [1, 1, 0, 0]


def test_calc_stats_zero_mean_without_warning():
    import warnings

    from PixelScopeViewer.core.statistics import calc_stats

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        zeros = calc_stats(np.zeros(4))
        signed = calc_stats(np.array([-1.0, 1.0]))
    assert np.isnan(zeros[5])
    assert np.isinf(signed[5])
