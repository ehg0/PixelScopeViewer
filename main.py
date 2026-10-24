"""Lightweight runner for the PixelScopeViewer package."""

import os
import sys

from PixelScopeViewer.app import RESTART_EXIT_CODE, main

if __name__ == "__main__":
    ret = main()

    if ret == RESTART_EXIT_CODE:
        os.execv(sys.executable, [sys.executable] + sys.argv)

    sys.exit(ret)
