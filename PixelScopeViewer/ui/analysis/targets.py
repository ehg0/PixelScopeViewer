"""解析する (画像, ROI) の組と、その histogram・profile の系列と統計量の行。"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor

from PixelScopeViewer.core.statistics import (
    crop_roi,
    determine_hist_bins,
    ecdf_series,
    get_profile_offset,
    histogram_series,
    histogram_stats,
    profile_series,
    profile_stats,
    visible_channels,
)
from PixelScopeViewer.ui.analysis.overlay import overlay_color, roi_color
from PixelScopeViewer.ui.analysis.state import AnalysisSettings
from PixelScopeViewer.ui.common import theme
from PixelScopeViewer.ui.viewer.state import RoiEntry

# Split をタイルごとにするときのグラフの id（登録 ROI の id と重ならないようにする）
TILE_SPLIT_ID_OFFSET = 10_000


def channel_index(label: str) -> int:
    """series の label（C{k} / I）の channel の index を返す。"""
    return 0 if label == "I" else int(label[1:])


@dataclass
class AnalysisSource:
    """解析する画像。

    Attributes:
        label: タイル比較モードのタイルの名前（T1 など）。1 枚表示では None。
        array: 画像配列。
        path: 画像ファイルのパス。
    """

    label: str | None
    array: np.ndarray
    path: str | None = None


@dataclass
class Target:
    """解析する (画像, ROI) の組。key は曲線の label の channel より前の部分（R0、T1 R0、T1）。"""

    key: str
    entry: RoiEntry | None
    source: AnalysisSource
    rect: QRect | None
    sub: np.ndarray
    vis: list[bool]

    @property
    def row_name(self) -> str:
        return self.key.replace(" ", "_")


def collect_targets(
    sources: list[AnalysisSource], rois: list[RoiEntry], rect: QRect | None, settings: AnalysisSettings
) -> list[Target]:
    """解析する (画像, ROI) の組を、画像 → ROI 一覧の順に返す。画像の範囲外の ROI は飛ばす。

    Args:
        sources: 1 枚表示は画像 1 つ、タイル比較モードは全タイル。
        rois: 登録 ROI。roi_mode が active か空の場合は編集中 ROI（rect）を使う。
        rect: 編集中 ROI。
        settings: channel の表示 ON/OFF（roi_channel_visibility）を読み書きする。
    """
    rects = [(None, rect)] if settings.roi_mode == "active" or not rois else [(e, e.rect) for e in rois]
    targets = []
    for source in sources:
        for entry, r in rects:
            sub = crop_roi(source.array, r.getRect() if r is not None else None)
            if sub.size == 0:
                continue
            key = " ".join(part for part in (source.label, entry.name if entry else None) if part)
            n = sub.shape[2] if sub.ndim == 3 else 1
            vis = settings.roi_channel_visibility.setdefault(key, [])
            vis[:] = (vis + [True] * n)[:n]
            targets.append(Target(key, entry, source, r, sub, vis))
    return targets


def target_color(index: int, target: Target, ch: int, overrides: dict[str, str]) -> QColor:
    """曲線の色。1 枚表示は ROI の色、タイル比較モードはパレットを (タイル, ROI) の順に循環させる。"""
    if target.source.label is None:
        return roi_color(target.entry.id, ch, overrides)
    return overlay_color(index + 1, ch, overrides, f"{target.key} C{ch}")


def _stats_rows(target: Target, rows: list[dict]) -> list[dict]:
    """表示 ON の channel の統計量の行に、{row_name}_C{k} の ch と曲線の label を付ける。"""
    out = []
    for row in rows:
        k = int(row["ch"])
        if target.vis[k]:
            out.append({**row, "ch": f"{target.row_name}_C{k}", "curve_label": f"{target.key} C{k}"})
    return out


def hist_series_and_rows(targets: list[Target], settings: AnalysisSettings) -> tuple[dict, list[dict]]:
    """組ごとの histogram（または ECDF）の表示 ON の系列と、統計量の行を返す。"""
    series = {}
    rows = []
    for t in targets:
        if settings.hist_mode == "Histogram":
            # bin の範囲は表示中の channel だけで決める
            bins = determine_hist_bins(visible_channels(t.sub, t.vis), settings.hist_bin_step)
            s = histogram_series(t.sub, bins=bins, channels=t.vis)
        else:
            s = ecdf_series(t.sub)
        for label, data in s.items():
            k = channel_index(label)
            if t.vis[k]:
                series[f"{t.key} C{k}"] = data
        rows += _stats_rows(t, histogram_stats(t.sub, t.vis))
    return series, rows


def profile_series_and_rows(targets: list[Target], settings: AnalysisSettings) -> tuple[dict, list[dict]]:
    """組ごとの profile の表示 ON の系列と、統計量の行を返す。absolute 表示では ROI の開始座標を x に加える。"""
    orientation = settings.profile_orientation
    method = settings.profile_method
    series = {}
    rows = []
    for t in targets:
        offset = 0
        if settings.profile_x_mode == "absolute" and t.rect is not None:
            offset = get_profile_offset(t.rect, orientation)
        for label, prof in profile_series(t.sub, orientation=orientation, method=method).items():
            k = channel_index(label)
            if t.vis[k]:
                series[f"{t.key} C{k}"] = (np.arange(prof.size) + offset, prof)
        rows += _stats_rows(t, profile_stats(t.sub, orientation=orientation, method=method, channel_checks=t.vis))
    return series, rows


def split_groups(
    targets: list[Target], series: dict, by_tile: bool, overrides: dict[str, str]
) -> list[tuple[int, str, str, dict]]:
    """Split 表示のグラフごとの (id, title, title の色, 系列) のリストを返す。

    ROI ごとのグラフには全タイル分を、タイルごと（by_tile）のグラフにはそのタイルの全 ROI を重ねる。
    """
    groups: dict[int, tuple[str, str, dict]] = {}
    for t in targets:
        if by_tile:
            gid = TILE_SPLIT_ID_OFFSET + int(t.source.label[1:])
            title = f"{t.source.label}: {Path(t.source.path).name}" if t.source.path else t.source.label
            color = theme.PLOT_TEXT_COLOR
        else:
            gid = t.entry.id
            r = t.entry.rect
            title = f"{t.entry.name} ({r.x()},{r.y()} {r.width()}×{r.height()})"
            color = roi_color(t.entry.id, 0, overrides).name()
        own = groups.setdefault(gid, (title, color, {}))[2]
        prefix = f"{t.key} "
        own.update({label: data for label, data in series.items() if label.startswith(prefix)})
    return [(gid, title, color, own) for gid, (title, color, own) in groups.items()]
