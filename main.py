"""PixelScopeViewer の起動 script。再起動用の終了コードを受け取った場合は自身を再実行する。"""

import os
import sys

from PixelScopeViewer.app import RESTART_EXIT_CODE, main

if __name__ == "__main__":
    ret = main()

    if ret == RESTART_EXIT_CODE:
        os.execv(sys.executable, [sys.executable] + sys.argv)

    sys.exit(ret)
