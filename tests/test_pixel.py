import numpy as np

from PixelScopeViewer.core.pixel import pixel_value_text


def test_pixel_value_text():
    assert pixel_value_text(np.array([[3]], dtype=np.uint16), 0, 0) == "3"
    assert pixel_value_text(np.array([[0.5]], dtype=np.float32), 0, 0) == "0.500"
    assert pixel_value_text(np.ones((1, 1, 3), dtype=np.uint8), 0, 0) == "(1,1,1)"
    assert pixel_value_text(np.zeros((2, 2)), 2, 0) is None
    assert pixel_value_text(np.zeros((2, 2)), 0, -1) is None
