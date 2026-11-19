import pytest

from PixelScopeViewer.core.tile_layout import TileLayout


def test_initial_state():
    layout = TileLayout()
    assert len(layout.stacks) == 16
    assert layout.visible_cells() == [(0, 0), (0, 1), (1, 0), (1, 1)]
    assert layout.frame_count() == 0
    assert layout.image_at((0, 0)) is None
    assert not layout.has_visible_images()


def test_step_wraps_by_longest_stack():
    layout = TileLayout()
    layout.set_stack((0, 0), [1, 2, 3])
    layout.set_stack((0, 1), [4])
    assert layout.frame_count() == 3
    assert [layout.image_at((0, 0)), layout.image_at((0, 1))] == [1, 4]
    layout.step(1)
    assert [layout.image_at((0, 0)), layout.image_at((0, 1))] == [2, None]
    layout.step(2)
    assert layout.frame == 0
    layout.step(-1)
    assert layout.frame == 2
    assert layout.visible_image_ids() == [3]


def test_step_without_images():
    layout = TileLayout()
    layout.step(1)
    assert layout.frame == 0


def test_grid_shrink_keeps_hidden_registration_by_position():
    layout = TileLayout(rows=3, cols=3)
    layout.set_stack((1, 0), [5])
    layout.set_stack((2, 2), [6, 7])
    layout.set_grid(2, 2)
    assert layout.hidden_cells() == [(2, 2)]
    # 2×2 の左下は位置で持つので残る
    assert layout.image_at((1, 0)) == 5
    assert layout.tile_number((1, 0)) == 3
    layout.set_grid(3, 3)
    assert layout.stack((2, 2)) == [6, 7]
    assert layout.tile_number((1, 0)) == 4


def test_grid_shrink_clamps_frame():
    layout = TileLayout(rows=1, cols=2)
    layout.set_stack((0, 0), [1])
    layout.set_stack((0, 1), [2, 3, 4])
    layout.step(2)
    layout.set_grid(1, 1)
    assert layout.frame == 0


def test_clear_hidden_and_cell():
    layout = TileLayout(rows=2, cols=2)
    layout.set_stack((3, 3), [1])
    layout.set_stack((0, 0), [2])
    layout.clear_hidden()
    assert layout.hidden_cells() == []
    layout.clear_cell((0, 0))
    assert layout.stack((0, 0)) == []


def test_append_and_duplicates():
    layout = TileLayout()
    layout.append((0, 0), [1, 1])
    layout.append((1, 1), [1])
    assert layout.stack((0, 0)) == [1, 1]
    assert layout.visible_image_ids() == [1, 1]


def test_remove_image_clamps_frame():
    layout = TileLayout()
    layout.set_stack((0, 0), [1, 2])
    layout.set_stack((0, 1), [2])
    layout.step(1)
    layout.remove_image(2)
    assert layout.stack((0, 0)) == [1]
    assert layout.stack((0, 1)) == []
    assert layout.frame == 0


def test_clear_all():
    layout = TileLayout()
    layout.set_stack((0, 0), [1, 2])
    layout.step(1)
    layout.clear_all()
    assert layout.frame == 0 and not layout.has_visible_images()


def test_invalid_grid_and_cell():
    layout = TileLayout()
    with pytest.raises(ValueError):
        layout.set_grid(5, 1)
    with pytest.raises(IndexError):
        layout.stack((4, 0))


def test_remove_and_retain_images():
    layout = TileLayout()
    layout.set_stack((0, 0), [1, 2, 3])
    layout.set_stack((3, 3), [2, 4])
    layout.step(2)
    layout.remove_images([3, 4])
    assert layout.stack((0, 0)) == [1, 2] and layout.stack((3, 3)) == [2]
    assert layout.frame == 1
    layout.retain_images({2})
    assert layout.stack((0, 0)) == [2] and layout.frame == 0
