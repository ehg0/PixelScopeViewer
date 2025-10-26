"""Core computation functions for analysis (Qt-independent).

This module provides pure computation functions for histogram/profile
generation and statistical calculations.
"""

from .compute import (
    determine_hist_bins,
    histogram_series,
    profile_series,
    compute_profile_1d,
    get_profile_offset,
    histogram_stats,
    profile_stats,
)

__all__ = [
    "determine_hist_bins",
    "histogram_series",
    "profile_series",
    "compute_profile_1d",
    "get_profile_offset",
    "histogram_stats",
    "profile_stats",
]
