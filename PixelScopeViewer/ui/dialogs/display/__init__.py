"""Display settings dialog package.

Public API:
- BrightnessDialog: Main display settings dialog with brightness and channel tabs

Internal structure:
- dialog: Main dialog implementation
- tabs/: Tab widgets (brightness adjustment, channel selection)
- core/: Pure computation functions (brightness calculation)
"""

from .dialog import BrightnessDialog

__all__ = ["BrightnessDialog"]
