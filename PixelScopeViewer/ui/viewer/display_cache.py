"""画像ごとの表示用 QPixmap の cache。"""

from collections import OrderedDict
from collections.abc import Hashable

from PySide6.QtGui import QPixmap


class DisplayCache:
    """画像 id ごとに、表示設定を key にした QPixmap を 1 つずつ持つ LRU cache。

    合計の大きさ（幅 × 高さ × 4 byte）が上限を超えたら、古く使ったものから捨てる。
    """

    def __init__(self, limit_mb: int):
        self.limit_bytes = limit_mb * 1024 * 1024
        self._entries: OrderedDict[int, tuple[Hashable, QPixmap, int]] = OrderedDict()
        self._total = 0

    def get(self, image_id: int, key: Hashable) -> QPixmap | None:
        """表示設定 key で作った QPixmap を返す。ない場合や key が違う場合は None。"""
        entry = self._entries.get(image_id)
        if entry is None or entry[0] != key:
            return None
        self._entries.move_to_end(image_id)
        return entry[1]

    def put(self, image_id: int, key: Hashable, pixmap: QPixmap):
        self.drop(image_id)
        size = pixmap.width() * pixmap.height() * 4
        self._entries[image_id] = (key, pixmap, size)
        self._total += size
        # 今入れたものは上限を超えても残す
        while self._total > self.limit_bytes and len(self._entries) > 1:
            _, (_, _, old_size) = self._entries.popitem(last=False)
            self._total -= old_size

    def drop(self, image_id: int):
        entry = self._entries.pop(image_id, None)
        if entry is not None:
            self._total -= entry[2]

    def clear(self):
        self._entries.clear()
        self._total = 0

    @property
    def total_bytes(self) -> int:
        return self._total
