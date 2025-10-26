"""Analysis dialog package.

Public API:
- AnalysisDialog: Main analysis dialog with histogram, profile, and metadata tabs
- CopyableTableWidget: Table widget with Ctrl+C copy support

Internal structure:
- dialog: Main dialog implementation
- tabs/: Tab widgets (histogram, profile, metadata)
- core/: Pure computation functions (Qt-independent)
- plotting/: pyqtgraph-specific utilities
- exporting/: CSV export functions
- widgets/: Custom widgets (tables, controls)
"""

from .dialog import AnalysisDialog
from .widgets import CopyableTableWidget

__all__ = ["AnalysisDialog", "CopyableTableWidget"]
