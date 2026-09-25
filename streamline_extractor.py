"""
streamline_extractor.py
========================
Global module for extracting, interpolating, and synchronizing CFD streamline
IDs and coordinates between the top plane (Inlet) and the bottom plane (Outlet).

Provides:
- `DataProcessor`: Complete class with unit detection, radial bounding, and .npz disk/memory caching.
- `get_synced_streamlines()`: High-level standalone convenience function.
"""

from __future__ import annotations

import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
import pandas as pd

# Global cache directory located in txt_to_image/.cache/synced
PROJECT_ROOT = Path(__file__).resolve().parent

def _find_hash_index_file() -> Path:
    candidates = [
        PROJECT_ROOT / ".cache" / "file_hash_index.json",
        PROJECT_ROOT / "txt_to_image" / ".cache" / "file_hash_index.json",
        PROJECT_ROOT.parent / "txt_to_image" / ".cache" / "file_hash_index.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return PROJECT_ROOT / ".cache" / "file_hash_index.json"

HASH_INDEX_FILE = _find_hash_index_file()

def _find_cache_dir() -> Path:
    candidates = [
        PROJECT_ROOT / ".cache" / "synced",
        PROJECT_ROOT / ".cache",
        PROJECT_ROOT / "txt_to_image" / ".cache" / "synced",
        PROJECT_ROOT / "txt_to_image" / ".cache",
        PROJECT_ROOT.parent / "txt_to_image" / ".cache" / "synced",
        PROJECT_ROOT.parent / "txt_to_image" / ".cache",
    ]
    for c in candidates:
        if c.exists():
            return c
    return PROJECT_ROOT / ".cache" / "synced"

CACHE_DIR = _find_cache_dir()
_MEMORY_CACHE = {}


def _get_hash_index() -> dict:
    """Load the persistent file hash index to avoid re-hashing multi-gigabyte files."""
    hash_file = _find_hash_index_file()
    if hash_file.exists():
        try:
            with open(hash_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_hash_index(index: dict) -> None:
    """Save the persistent file hash index."""
    hash_file = _find_hash_index_file()
    try:
        hash_file.parent.mkdir(parents=True, exist_ok=True)
        with open(hash_file, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)
    except Exception:
        pass


def _hash_file(path: Union[str, Path]) -> str:
    """Return an 8-character SHA-256 hex digest of file contents for cache keying.
    Uses file_hash_index.json to avoid re-reading multi-gigabyte files when size and mtime match.
    Also looks up by filename for isolated environments.
    """
    path_obj = Path(path).resolve()
    path_str = str(path_obj)
    fname = path_obj.name

    # Check persistent index
    index = _get_hash_index()

    # Check exact path match
    if path_str in index:
        entry = index[path_str]
        if not path_obj.exists():
            return entry["hash"]
        file_size = path_obj.stat().st_size
        file_mtime = path_obj.stat().st_mtime
        if entry.get("size") == file_size and abs(entry.get("mtime", 0) - file_mtime) < 1e-4:
            return entry["hash"]

    # Check filename match (handles moved folders or isolated environments)
    for k, entry in index.items():
        if Path(k).name == fname:
            if not path_obj.exists():
                return entry["hash"]
            file_size = path_obj.stat().st_size
            file_mtime = path_obj.stat().st_mtime
            if entry.get("size") == file_size and abs(entry.get("mtime", 0) - file_mtime) < 1e-4:
                return entry["hash"]

    if not path_obj.exists():
        h = hashlib.sha256(fname.encode("utf-8"))
        return h.hexdigest()[:8]

    file_size = path_obj.stat().st_size
    file_mtime = path_obj.stat().st_mtime

    # Compute sha256
    h = hashlib.sha256()
    with open(path_obj, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()[:8]

    # Save to index
    index[path_str] = {"size": file_size, "mtime": file_mtime, "hash": digest}
    _save_hash_index(index)
    return digest


def _find_cache_file(source_file: Union[str, Path]) -> Optional[Path]:
    """Find existing .npz cache file across local and parent cache candidates."""
    h = _hash_file(source_file)
    candidates = [
        PROJECT_ROOT / ".cache" / "synced" / f"{h}.npz",
        PROJECT_ROOT / ".cache" / f"{h}.npz",
        PROJECT_ROOT / "txt_to_image" / ".cache" / "synced" / f"{h}.npz",
        PROJECT_ROOT / "txt_to_image" / ".cache" / f"{h}.npz",
        PROJECT_ROOT.parent / "txt_to_image" / ".cache" / "synced" / f"{h}.npz",
        PROJECT_ROOT.parent / "txt_to_image" / ".cache" / f"{h}.npz",
        CACHE_DIR / f"{h}.npz",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


class DataProcessor:
    """Class to process, interpolate, and synchronize streamline data from CFD .txt files."""

    def __init__(
        self,
        filepath: Union[str, Path],
        z_bottom_target: Optional[float] = None,
        z_inlet_target: Optional[float] = None,
        use_disk_cache: bool = True,
    ):
        self.filepath = str(filepath)
        self.z_bottom_target = z_bottom_target
        self.z_inlet_target = z_inlet_target
        self.use_disk_cache = use_disk_cache
        self.bottom_data: Optional[pd.DataFrame] = None
        self.inlet_data: Optional[pd.DataFrame] = None
        self.r_bottom_detected: Optional[float] = None

    def get_exact_plane_intersection(self, df: pd.DataFrame, z_target: float) -> pd.DataFrame:
        """Compute the exact linear intersection for each streamline with the target Z plane."""
        df_temp = df.copy()
        df_temp['dist'] = (df_temp['z'] - z_target).abs()
        df_sorted = df_temp.sort_values(by=['id', 'dist'], ascending=True)
        closest_two = df_sorted.groupby('id').head(2).copy()
        closest_two = closest_two.sort_values(by=['id', 'z'])

        p1 = closest_two.groupby('id').nth(0).set_index('id')
        p2 = closest_two.groupby('id').nth(1).set_index('id')

        valid_ids = p1.index.intersection(p2.index)
        p1 = p1.loc[valid_ids]
        p2 = p2.loc[valid_ids]

        dz = p2['z'] - p1['z']
        dz = dz.replace(0, np.nan)

        t = (z_target - p1['z']) / dz

        x_target = p1['x'] + t * (p2['x'] - p1['x'])
        y_target = p1['y'] + t * (p2['y'] - p1['y'])

        x_target = x_target.fillna(p1['x'])
        y_target = y_target.fillna(p1['y'])

        return pd.DataFrame({
            'id': valid_ids,
            'x': x_target.values,
            'y': y_target.values,
            'z': z_target
        })

    def get_synced_coords(
        self,
        r_inlet_max: float = 6.25,
        r_bottom_max: float = 1.0,
        edge_point_bottom: Optional[Tuple[float, float]] = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Extract top (Inlet) and bottom (Outlet) coordinates along with synchronized IDs.

        Returns:
            Tuple[np.ndarray, np.ndarray, np.ndarray]:
                - inlet_coords: array of shape (N, 2) containing [x, y] at the inlet plane
                - bottom_coords: array of shape (N, 2) containing [x, y] at the outlet plane
                - sync_ids: array of shape (N,) containing common streamline IDs present in both planes
        """
        # Memory cache check
        if self.filepath in _MEMORY_CACHE:
            cached = _MEMORY_CACHE[self.filepath]
            self.z_inlet_target = cached['z_inlet_target']
            self.z_bottom_target = cached['z_bottom_target']
            self.r_bottom_detected = cached['r_bottom_detected']
            self.inlet_data = cached['inlet_data'].copy()
            self.bottom_data = cached['bottom_data'].copy()
            return cached['inlet_coords'], cached['bottom_coords'], cached['sync_ids']

        # Disk cache check (.npz)
        if self.use_disk_cache:
            cache_path = _find_cache_file(self.filepath)
            if cache_path is not None and (
                not os.path.exists(self.filepath)
                or os.path.getmtime(self.filepath) < os.path.getmtime(cache_path)
            ):
                data = np.load(str(cache_path))
                inlet_coords = data["inlet_coords"]
                bottom_coords = data["bottom_coords"]
                sync_ids = data["sync_ids"]
                self.z_inlet_target = float(data["z_inlet_target"])
                self.z_bottom_target = float(data["z_bottom_target"]) if "z_bottom_target" in data else self.z_bottom_target
                self.r_bottom_detected = float(data["r_bottom_detected"])
                
                self.inlet_data = pd.DataFrame({"x": inlet_coords[:, 0], "y": inlet_coords[:, 1], "id": sync_ids})
                self.bottom_data = pd.DataFrame({"x": bottom_coords[:, 0], "y": bottom_coords[:, 1], "id": sync_ids})
                
                _MEMORY_CACHE[self.filepath] = {
                    'z_inlet_target': self.z_inlet_target,
                    'z_bottom_target': self.z_bottom_target,
                    'r_bottom_detected': self.r_bottom_detected,
                    'inlet_data': self.inlet_data,
                    'bottom_data': self.bottom_data,
                    'inlet_coords': inlet_coords,
                    'bottom_coords': bottom_coords,
                    'sync_ids': sync_ids,
                }
                return inlet_coords, bottom_coords, sync_ids

        # Load raw simulation file skipping header lines
        if not os.path.isfile(self.filepath):
            raise FileNotFoundError(f"File not found: {self.filepath}")

        df = pd.read_csv(self.filepath, sep=r'\s+', skiprows=8, names=['x', 'y', 'z', 'id'])

        # Auto-detect coordinate units: convert meters to millimeters if max Z is small
        max_z = df['z'].abs().max()
        factor = 1000.0 if max_z < 1.0 else 1.0
        if max_z < 1.0:
            df['x'] = df['x'] * factor
            df['y'] = df['y'] * factor
            df['z'] = df['z'] * factor

        # Auto-detect target Z planes if not explicitly specified
        if self.z_inlet_target is None:
            self.z_inlet_target = df.iloc[0]['z']
        if self.z_bottom_target is None:
            self.z_bottom_target = df['z'].min()

        # Compute plane intersections
        df_interp_inlet = self.get_exact_plane_intersection(df, self.z_inlet_target)
        df_interp_bottom = self.get_exact_plane_intersection(df, self.z_bottom_target)

        # Apply maximum radius bounding on the inlet plane
        df_interp_inlet['r'] = np.sqrt(df_interp_inlet['x'] ** 2 + df_interp_inlet['y'] ** 2)
        df_final_inlet = df_interp_inlet[df_interp_inlet['r'] <= r_inlet_max]

        # Determine bottom nozzle radius from edge point coordinates if provided
        if edge_point_bottom is not None:
            edge_x_mm = edge_point_bottom[0] * factor
            edge_y_mm = edge_point_bottom[1] * factor
            r_bottom_max = np.sqrt(edge_x_mm**2 + edge_y_mm**2)

        self.r_bottom_detected = r_bottom_max

        # Apply maximum radius bounding on the bottom plane
        df_interp_bottom['r'] = np.sqrt(df_interp_bottom['x'] ** 2 + df_interp_bottom['y'] ** 2)
        df_final_bottom = df_interp_bottom[df_interp_bottom['r'] <= r_bottom_max]

        # Synchronize streamlines: keep only IDs present in both planes
        common_ids = set(df_final_inlet['id']).intersection(set(df_final_bottom['id']))
        df_sync_inlet = df_final_inlet[df_final_inlet['id'].isin(common_ids)].sort_values('id')
        df_sync_bottom = df_final_bottom[df_final_bottom['id'].isin(common_ids)].sort_values('id')

        inlet_coords = df_sync_inlet[['x', 'y']].values
        bottom_coords = df_sync_bottom[['x', 'y']].values
        sync_ids = df_sync_inlet['id'].values

        self.inlet_data = df_sync_inlet.copy()
        self.bottom_data = df_sync_bottom.copy()

        # Save synchronized coordinates to disk cache in txt_to_image/.cache/synced
        if self.use_disk_cache:
            save_dir = PROJECT_ROOT / "txt_to_image" / ".cache" / "synced"
            save_dir.mkdir(parents=True, exist_ok=True)
            cache_path = save_dir / f"{_hash_file(self.filepath)}.npz"
            np.savez(
                str(cache_path),
                inlet_coords=inlet_coords,
                bottom_coords=bottom_coords,
                sync_ids=sync_ids,
                z_inlet_target=np.float64(self.z_inlet_target),
                z_bottom_target=np.float64(self.z_bottom_target),
                r_bottom_detected=np.float64(self.r_bottom_detected),
            )

        # Save synchronized coordinates to memory cache
        _MEMORY_CACHE[self.filepath] = {
            'z_inlet_target': self.z_inlet_target,
            'z_bottom_target': self.z_bottom_target,
            'r_bottom_detected': self.r_bottom_detected,
            'inlet_data': self.inlet_data,
            'bottom_data': self.bottom_data,
            'inlet_coords': inlet_coords,
            'bottom_coords': bottom_coords,
            'sync_ids': sync_ids,
        }

        return inlet_coords, bottom_coords, sync_ids


def get_synced_streamlines(
    filepath: Union[str, Path],
    z_inlet: Optional[float] = None,
    z_bottom: Optional[float] = None,
    r_inlet_max: float = 6.25,
    r_bottom_max: float = 1.0,
    edge_point_bottom: Optional[Tuple[float, float]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convenience function to retrieve synchronized coordinates and streamline IDs.

    Example:
    >>> from streamline_extractor import get_synced_streamlines
    >>> in_coords, bot_coords, ids = get_synced_streamlines("path/to/streamline.txt")
    >>> print(f"Found {len(ids)} synchronized streamlines.")
    """
    processor = DataProcessor(filepath, z_bottom_target=z_bottom, z_inlet_target=z_inlet)
    return processor.get_synced_coords(
        r_inlet_max=r_inlet_max,
        r_bottom_max=r_bottom_max,
        edge_point_bottom=edge_point_bottom,
    )


if __name__ == "__main__":
    print("Module 'streamline_extractor' is ready for use.")


