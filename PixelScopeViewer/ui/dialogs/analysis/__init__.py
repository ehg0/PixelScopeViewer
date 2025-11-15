"""Analysis dialog package.

Public API:
- AnalysisDialog: Main analysis dialog with histogram, profile, and metadata tabs

Internal structure:
- dialog: Main dialog implementation
- tabs/: Tab widgets (histogram, profile, metadata)
- core/: Pure computation functions (Qt-independent)
- plotting/: pyqtgraph-specific utilities
- exporting/: CSV export functions
"""

from .dialog import AnalysisDialog

__all__ = ["AnalysisDialog"]
