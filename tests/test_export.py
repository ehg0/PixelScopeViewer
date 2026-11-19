import numpy as np

from PixelScopeViewer.core.export import grouped_profile_csv, metadata_comparison_csv


def test_grouped_profile_csv_groups_by_label_before_channel():
    data = {
        "T1 R0 C0": (np.array([0, 1]), np.array([5, 6])),
        "T1 R0 C1": (np.array([0, 1]), np.array([7, 8])),
        "T2 R0 C0": (np.array([3]), np.array([9])),
    }
    lines = grouped_profile_csv(data, "h").splitlines()
    assert lines[0] == "T1 R0 x address,T1 R0 C0,T1 R0 C1,T2 R0 x address,T2 R0 C0"
    assert lines[2] == "1,6,8,,"


def test_grouped_profile_csv_single_mode_labels():
    data = {"R0 C0": (np.array([0]), np.array([1])), "R1 C0": (np.array([0]), np.array([2]))}
    assert grouped_profile_csv(data, "v").splitlines()[0] == "R0 y address,R0 C0,R1 y address,R1 C0"


def test_metadata_comparison_csv():
    text = metadata_comparison_csv([("T1: a", [("Size", "1 x 1"), ("Format", "PNG")]), ("T2: b", [("Size", "2 x 2")])])
    assert text.splitlines() == ["Key,T1: a,T2: b", "Size,1 x 1,2 x 2", "Format,PNG,"]
