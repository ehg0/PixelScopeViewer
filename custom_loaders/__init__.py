"""Custom image loaders for PixelScopeViewer.

This directory is for user-defined custom image loaders (plugins).
Place your custom loader files here and they will be automatically
loaded when the application starts.

See README.md in this directory for detailed instructions on how to
create and register custom loaders.
"""

import sys
from pathlib import Path
from importlib import import_module

# Get the path to this directory
CUSTOM_LOADERS_DIR = Path(__file__).parent


def load_custom_loaders():
    """Automatically load all custom loader modules in this directory.

    This function imports all Python files (except __init__.py and files
    starting with underscore or dot) in the custom_loaders directory.

    Custom loaders should register themselves using:
        from PixelScopeViewer.core.image_io import ImageLoaderRegistry
        ImageLoaderRegistry.get_instance().register(my_loader_func, ...)
    """
    # Add custom_loaders directory to Python path if not already there
    custom_loaders_str = str(CUSTOM_LOADERS_DIR)
    if custom_loaders_str not in sys.path:
        sys.path.insert(0, custom_loaders_str)

    # Import all Python files in this directory
    for py_file in CUSTOM_LOADERS_DIR.glob("*.py"):
        # Skip special files
        if py_file.name.startswith(("_", ".")):
            continue
        if py_file.name == "__init__.py":
            continue

        # Import the module
        module_name = py_file.stem
        try:
            import_module(module_name)
            print(f"Loaded custom loader: {module_name}")
        except Exception as e:
            print(f"Failed to load custom loader {module_name}: {e}")
