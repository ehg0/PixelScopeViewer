"""Custom widgets for analysis dialogs.

This module provides specialized widgets used in analysis dialogs,
including copyable tables and channel control dialogs.
"""

from .tables import CopyableTableWidget
from .controls import ChannelsDialog

__all__ = [
    "CopyableTableWidget",
    "ChannelsDialog",
]
