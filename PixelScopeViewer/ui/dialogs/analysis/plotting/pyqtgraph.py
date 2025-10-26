"""Plotting helpers for pyqtgraph integration in Analysis dialogs.

This module isolates pyqtgraph-specific interactions: saving/restoring
ViewBox state, connecting control panel toggles, applying grid/log settings,
and showing default context menus. It does not depend on Qt Widgets beyond
what pyqtgraph provides.
"""

from __future__ import annotations

from typing import Optional, Dict


def _import_pg():  # lazy import to avoid hard dependency
    try:
        import pyqtgraph as pg  # type: ignore

        return pg
    except Exception:  # pragma: no cover - optional
        return None


def save_viewbox_state(vb) -> Optional[dict]:
    """Return full ViewBox state if available."""
    try:
        return vb.getState(copy=True)
    except Exception:
        return None


def apply_plot_settings(widget, which: str, plot_settings: Dict[str, dict], saved_full_state: Optional[dict] = None):
    """Apply grid settings and restore saved ViewBox state if provided."""
    pg = _import_pg()
    try:
        s = plot_settings.get(which, {})
        widget.showGrid(x=bool(s.get("grid", True)), y=bool(s.get("grid", True)))
    except Exception:
        pass

    if saved_full_state is not None:
        try:
            vb = widget.getViewBox()
            vb.setState(saved_full_state)
        except Exception:
            pass


def connect_plot_controls(plot_item, which: str, plot_settings: Dict[str, dict], on_hist_log_changed=None):
    """Connect PlotItem.ctrl toggles to persist grid/log settings.

    For 'hist', also persists LogY and calls on_hist_log_changed when toggled.
    """
    if not hasattr(plot_item, "ctrl"):
        return
    c = plot_item.ctrl
    # initial grid sync
    try:
        gval = False
        try:
            gval = bool(c.xGridCheck.isChecked() or c.yGridCheck.isChecked())
        except Exception:
            pass
        plot_settings.setdefault(which, {})["grid"] = gval
    except Exception:
        pass

    # connect grid toggles
    try:
        if hasattr(c, "xGridCheck"):
            c.xGridCheck.toggled.connect(lambda checked: _on_grid_toggled(which, plot_settings, checked))
        if hasattr(c, "yGridCheck"):
            c.yGridCheck.toggled.connect(lambda checked: _on_grid_toggled(which, plot_settings, checked))
    except Exception:
        pass

    if which == "hist":
        try:
            if hasattr(c, "logYCheck"):
                # initial sync
                try:
                    plot_settings.setdefault("hist", {})["log"] = bool(c.logYCheck.isChecked())
                except Exception:
                    pass
                c.logYCheck.toggled.connect(
                    lambda checked: _on_log_toggled(plot_settings, bool(checked), on_hist_log_changed)
                )
        except Exception:
            pass


def _on_grid_toggled(which: str, plot_settings: Dict[str, dict], checked: bool):
    try:
        plot_settings.setdefault(which, {})["grid"] = bool(checked)
    except Exception:
        pass


def _on_log_toggled(plot_settings: Dict[str, dict], checked: bool, on_hist_log_changed=None):
    try:
        plot_settings.setdefault("hist", {})["log"] = bool(checked)
        if on_hist_log_changed is not None:
            on_hist_log_changed()
    except Exception:
        pass


def show_default_context_menu(widget, pos):
    """Show pyqtgraph's default PlotItem/ViewBox menus at the given position."""
    pg = _import_pg()
    if pg is None:
        return
    # Prefer PlotItem's ctrlMenu, then ViewBox menu
    try:
        plot_item = widget.getPlotItem()
    except Exception:
        plot_item = None

    menus = []
    if plot_item is not None:
        try:
            m = plot_item.getMenu()
        except Exception:
            m = None
        if m is not None:
            menus.append(m)

    try:
        vb = widget.getViewBox()
        if hasattr(vb, "menu") and vb.menu is not None:
            menus.append(vb.menu)
    except Exception:
        vb = None

    try:
        gpos = widget.mapToGlobal(pos)
    except Exception:
        gpos = widget.mapToGlobal(widget.rect().center())

    try:
        if plot_item is not None and hasattr(plot_item, "ctrlMenu") and plot_item.ctrlMenu is not None:
            plot_item.ctrlMenu.exec_(gpos)
    except Exception:
        pass

    try:
        if vb is not None and hasattr(vb, "menu") and vb.menu is not None:
            from PySide6.QtCore import QPoint

            try:
                vb.menu.exec_(gpos + QPoint(8, 8))
            except Exception:
                vb.menu.exec_(gpos)
    except Exception:
        pass
