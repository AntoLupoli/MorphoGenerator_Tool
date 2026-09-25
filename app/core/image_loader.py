"""
Image loading utilities for the Morphogenerator.

Resolves file paths for streamline images stored under the data root
(default: the Morpho_tool/ workspace directory). All images are loaded
exclusively from the .prev/ directory. Image names follow
the pattern M2_N{N}_Q_{Q:.2f}.png (central view) and
M2_N{N}_side_Q_{Q:.2f}.png (side view).
"""

import sys
import os
from pathlib import Path
from typing import Optional

def _resolve_data_root() -> Path:
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass and (Path(meipass) / ".prev").exists():
            return Path(meipass)
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / ".prev").exists():
            return exe_dir
        if meipass:
            return Path(meipass)
        return exe_dir
    return Path(__file__).resolve().parent.parent.parent

# Default data root: the Morpho_tool/ directory (parent of app/)
_DATA_ROOT = _resolve_data_root()


def get_data_root() -> Path:
    """Return the current data root directory."""
    return _DATA_ROOT


def set_data_root(path: str) -> None:
    """Override the data root directory."""
    global _DATA_ROOT
    _DATA_ROOT = Path(path)


def streamline_image_path(
    N: int,
    Q: float,
    view: str = "central",
) -> Optional[Path]:
    """Return the path to a streamline image from .prev, or None if not found.

    Parameters
    ----------
    N : int
        Number of petals (2–6).
    Q : float
        Flow ratio.
    view : str
        "central" or "side".
    """
    # Primary location: .prev folder within data root
    folder = _DATA_ROOT / f".prev/M2_N{N}_streamline"
    if not folder.exists():
        return None

    if view == "side":
        filename = f"M2_N{N}_side_Q_{Q:.2f}.png"
    else:
        filename = f"M2_N{N}_Q_{Q:.2f}.png"

    path = folder / filename
    if path.exists():
        return path

    # Nearest neighbor Q search strictly within .prev/M2_N{N}_streamline
    prefix = f"M2_N{N}_side_Q_" if view == "side" else f"M2_N{N}_Q_"
    best_cand = None
    min_diff = float("inf")

    for f in folder.glob("*.png"):
        if f.stem.startswith(prefix):
            try:
                q_str = f.stem[len(prefix):]
                q_val = float(q_str)
                diff = abs(q_val - Q)
                if diff < min_diff:
                    min_diff = diff
                    best_cand = f
            except Exception:
                continue

    if best_cand is not None and min_diff <= 0.05:
        return best_cand

    return None


def list_available_Q(N: int, view: str = "central") -> list:
    """Return sorted list of Q values for which images exist in .prev."""
    folder = _DATA_ROOT / f".prev/M2_N{N}_streamline"
    if not folder.exists():
        return []

    prefix = f"M2_N{N}_side_Q_" if view == "side" else f"M2_N{N}_Q_"
    q_values = []
    for f in folder.glob("*.png"):
        name = f.stem
        if name.startswith(prefix):
            try:
                q_str = name[len(prefix):]
                q_values.append(float(q_str))
            except ValueError:
                continue
    return sorted(q_values)


def list_available_N() -> list:
    """Return sorted list of N values that have streamline folders in .prev."""
    available = []
    for n in range(2, 10):
        folder = _DATA_ROOT / f".prev/M2_N{n}_streamline"
        if folder.exists() and any(folder.glob("*.png")):
            available.append(n)
    return available
