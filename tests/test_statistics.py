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
