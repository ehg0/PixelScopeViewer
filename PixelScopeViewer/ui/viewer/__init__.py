"""Image viewer package with modular components.

This package provides the main ImageViewer window split into logical components:
- viewer.py: Main ImageViewer class coordinating all components
- menu_builder.py: Menu and keyboard shortcut setup
- zoom_manager.py: Zoom and viewport control operations
- brightness_manager.py: Brightness/channel adjustment management
- status_updater.py: Status bar update logic
"""

from .viewer import ImageViewer

__all__ = ["ImageViewer"]
