"""現在値（state の dataclass）を JSON にできる形へ変換する。"""

import dataclasses

import numpy as np
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor


def to_jsonable(obj):
    """dataclass・QRect・QColor・numpy の値を、json.dumps できる値に再帰的に変換する。

    QRect は [x, y, w, h]、QColor は hex 文字列にする。
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, QRect):
        return [obj.x(), obj.y(), obj.width(), obj.height()]
    if isinstance(obj, QColor):
        return obj.name()
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return obj
