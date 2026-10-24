"""Core computation functions for analysis (Qt-independent).

This module provides pure computation functions for histogram/profile
generation and statistical calculations.
"""

from .compute import (
    calc_stats,
    compute_profile_1d,
    determine_hist_bins,
    ecdf_series,
    get_profile_offset,
    histogram_series,
    histogram_stats,
    profile_series,
    profile_stats,
)

__all__ = [
    "calc_stats",
    "compute_profile_1d",
    "determine_hist_bins",
    "ecdf_series",
    "get_profile_offset",
    "histogram_series",
    "histogram_stats",
    "profile_series",
    "profile_stats",
]
