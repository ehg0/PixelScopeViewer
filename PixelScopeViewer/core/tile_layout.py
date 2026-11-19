"""タイル比較モードの登録内容（マスごとの画像 id のリスト）とグリッド・表示位置（Qt 非依存）。"""

from dataclasses import dataclass, field

Cell = tuple[int, int]


@dataclass
class TileLayout:
    """最大グリッド分のマスの登録リストと、表示するグリッド・表示位置 frame を持つ。

    登録はマスの位置 (行, 列) で持ち、グリッドを小さくしても外れたマスの登録は残す。

    Attributes:
        max_rows: 行数の上限。
        max_cols: 列数の上限。
        rows: 表示する行数。
        cols: 表示する列数。
        frame: 全タイル共通の表示位置（n / b で進める index）。
        stacks: 行優先で並べた、マスごとの画像 id のリスト。
    """

    max_rows: int = 4
    max_cols: int = 4
    rows: int = 2
    cols: int = 2
    frame: int = 0
    stacks: list[list[int]] = field(default_factory=list)

    def __post_init__(self):
        n = self.max_rows * self.max_cols
        self.stacks = [list(s) for s in self.stacks[:n]] + [[] for _ in range(n - len(self.stacks))]
        self.set_grid(self.rows, self.cols)

    def _index(self, cell: Cell) -> int:
        r, c = cell
        if not (0 <= r < self.max_rows and 0 <= c < self.max_cols):
            raise IndexError(f"cell {cell} is outside {self.max_rows}x{self.max_cols}")
        return r * self.max_cols + c

    # --- グリッド ---
    def set_grid(self, rows: int, cols: int):
        """表示するグリッドを変える。表示位置は新しいグリッドの範囲に収める。"""
        if not (1 <= rows <= self.max_rows and 1 <= cols <= self.max_cols):
            raise ValueError(f"grid {rows}x{cols} is outside 1..{self.max_rows}x1..{self.max_cols}")
        self.rows, self.cols = rows, cols
        self._clamp_frame()

    def visible_cells(self) -> list[Cell]:
        """表示中のマスを行優先で返す。"""
        return [(r, c) for r in range(self.rows) for c in range(self.cols)]

    def is_visible(self, cell: Cell) -> bool:
        return 0 <= cell[0] < self.rows and 0 <= cell[1] < self.cols

    def tile_number(self, cell: Cell) -> int:
        """今のグリッドでの行優先の番号（1 始まり）を返す。"""
        return cell[0] * self.cols + cell[1] + 1

    # --- 登録 ---
    def stack(self, cell: Cell) -> list[int]:
        """マスの登録リスト（copy）を返す。"""
        return list(self.stacks[self._index(cell)])

    def set_stack(self, cell: Cell, image_ids: list[int]):
        self.stacks[self._index(cell)] = list(image_ids)
        self._clamp_frame()

    def append(self, cell: Cell, image_ids: list[int]):
        """マスの登録リストの末尾に追加する。"""
        self.stacks[self._index(cell)].extend(image_ids)

    def clear_cell(self, cell: Cell):
        self.set_stack(cell, [])

    def clear_all(self):
        for s in self.stacks:
            s.clear()
        self.frame = 0

    def hidden_cells(self) -> list[Cell]:
        """表示していないマスのうち、登録があるマスを返す。"""
        return [
            (r, c)
            for r in range(self.max_rows)
            for c in range(self.max_cols)
            if not self.is_visible((r, c)) and self.stacks[self._index((r, c))]
        ]

    def clear_hidden(self):
        """表示していないマスの登録を消す。"""
        for cell in self.hidden_cells():
            self.stacks[self._index(cell)].clear()

    def remove_image(self, image_id: int):
        """全マスの登録リストから画像 id を消す。"""
        self.remove_images([image_id])

    def remove_images(self, image_ids):
        """全マスの登録リストから画像 id を消す。"""
        removed = set(image_ids)
        for s in self.stacks:
            s[:] = [i for i in s if i not in removed]
        self._clamp_frame()

    def retain_images(self, image_ids):
        """全マスの登録リストから、image_ids にない画像 id を消す。"""
        kept = set(image_ids)
        for s in self.stacks:
            s[:] = [i for i in s if i in kept]
        self._clamp_frame()

    def has_visible_images(self) -> bool:
        return self.frame_count() > 0

    # --- 表示位置 ---
    def frame_count(self) -> int:
        """表示中のマスの登録リストのうち、一番長いものの長さを返す。"""
        return max((len(self.stacks[self._index(cell)]) for cell in self.visible_cells()), default=0)

    def image_at(self, cell: Cell) -> int | None:
        """マスに表示する画像 id を返す。登録リストが表示位置に届かない場合は None。"""
        s = self.stacks[self._index(cell)]
        return s[self.frame] if self.frame < len(s) else None

    def visible_image_ids(self) -> list[int]:
        """表示中のタイルの画像 id を行優先で返す（空欄は除き、重複は残す）。"""
        return [i for cell in self.visible_cells() if (i := self.image_at(cell)) is not None]

    def step(self, delta: int):
        """表示位置を delta だけ進める。一番長い登録リストを基準に一周する。"""
        n = self.frame_count()
        self.frame = (self.frame + delta) % n if n else 0

    def _clamp_frame(self):
        n = self.frame_count()
        self.frame = min(self.frame, n - 1) if n else 0
