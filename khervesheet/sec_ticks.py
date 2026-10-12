"""Ticks on the opposite (top/right) edge with their own direction.

Matplotlib keeps one tick direction per axis, so "out at the bottom, in
at the top" — the usual journal style for spectra — cannot be set with
``tick_params`` alone. When an axis state asks for ``sec_tick_dir``, the
opposite edge's ticks are drawn on a linked secondary axis instead, with
the same locators and no labels.
"""
from __future__ import annotations

import matplotlib.ticker as mticker

_DIRS = ["out", "in", "inout"]


def apply_sec_tick_dir(ax, ax_str: str, sec_key: str, st: dict) -> None:
    attr = f"_ks_sec_ticks_{ax_str}"
    old = getattr(ax, attr, None)
    if old is not None:
        try:
            old.remove()
        except (ValueError, AttributeError):
            pass
        setattr(ax, attr, None)

    idx = st.get("sec_tick_dir")
    if idx is None or not st.get("sec_tick_show", False):
        return
    direction = _DIRS[int(idx)] if isinstance(idx, int) else str(idx)

    # Hide the main axis's own ticks on that edge; the twin draws them.
    ax.tick_params(axis=ax_str, which="both", **{sec_key: False})
    sec = (ax.secondary_xaxis(sec_key) if ax_str == "x"
           else ax.secondary_yaxis(sec_key))
    sec.spines[sec_key].set_visible(False)      # the frame stays ax's own
    mpl_axis = sec.xaxis if ax_str == "x" else sec.yaxis
    label_kw = {f"label{sec_key}": False}

    if st.get("major_show", True):
        mpl_axis.set_major_locator(
            mticker.MaxNLocator(nbins=st.get("major_count", 6)))
        sec.tick_params(which="major", direction=direction,
                        length=st.get("major_length", 3.5),
                        width=st.get("major_width", 1.0),
                        color=st.get("major_color", "#000000"), **label_kw)
    else:
        sec.tick_params(which="major", length=0, **label_kw)
    if st.get("minor_show", False):
        mpl_axis.set_minor_locator(
            mticker.AutoMinorLocator(st.get("minor_count", 5)))
        sec.tick_params(which="minor", direction=direction,
                        length=st.get("minor_length", 2.0),
                        width=st.get("minor_width", 1.0),
                        color=st.get("minor_color", "#000000"))
    setattr(ax, attr, sec)
