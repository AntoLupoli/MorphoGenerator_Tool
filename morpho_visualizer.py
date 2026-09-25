"""
morpho_visualizer.py
====================
Global visualization tool for the morphogenerator microfluidic system.

Features:
- Simulates flow ratio Q and calculates the physical core radius R_Q at the inlet.
- Caches inlet and outlet streamline coordinates using the persistent cache
  in txt_to_image/.cache to avoid costly recalculations on multi-gigabyte files.
- Partitions the outer side annulus (r_Q < r <= r_inlet_max) into multiple side sectors
  using parameter Theta (single angle, equal division, or custom list per side).
- Assigns a distinct, contrasting color to each side sector and to the central core.
- Supports rotating the side annulus partition by an arbitrary angle (rotation_deg)
  to observe swirl deformation and where each colored fluid stream ends up at the outlet.
"""

from __future__ import annotations

import argparse
import math
import os
import io
from PIL import Image as PILImage
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D
from matplotlib.patches import Arc, Circle, Wedge
import numpy as np
import pandas as pd

from streamline_extractor import DataProcessor, get_synced_streamlines

PROJECT_ROOT = Path(__file__).resolve().parent

# Color palette for side sectors (distinct, high contrast, vibrant)
SIDE_PALETTE = [
    "#0088FE",  # 1. Vibrant Blue
    "#00C49F",  # 2. Teal / Jade Green
    "#FFBB28",  # 3. Warm Amber / Gold
    "#FF8042",  # 4. Coral / Orange
    "#8884D8",  # 5. Lavender / Violet
    "#E91E63",  # 6. Hot Pink / Magenta
    "#00E5FF",  # 7. Cyan
    "#76FF03",  # 8. Bright Lime
    "#AB47BC",  # 9. Purple
    "#26A69A",  # 10. Sea Green
    "#FF5252",  # 11. Light Red / Crimson
    "#3F51B5",  # 12. Indigo
    "#8D6E63",  # 13. Cocoa Brown
    "#78909C",  # 14. Blue Grey
    "#FDD835",  # 15. Canary Yellow
]

CENTRAL_COLOR = "#EF4444"      # Central Fluid Core (Red)
UNASSIGNED_COLOR = "#B0BEC5"   # Unassigned / background side region (Light Grey)
WALL_COLOR = "#111827"         # Chamber / nozzle walls
BLADE_DOWN_COLOR = "#2563EB"   # Blade down indicator (Vibrant Blue)
BLADE_UP_COLOR = "#D97706"     # Blade up indicator (Warm Amber/Orange)


def calculate_physical_radius(q_ratio: float, r_total: float = 6.25) -> float:
    """Calculate the physical inner core radius (r_Q) enclosing a given flow ratio Q.

    Formula derived from parabolic/Poiseuille flow integration:
    r_Q = r_total * sqrt(1 - sqrt(1 - Q))
    """
    if not (0.0 <= q_ratio <= 1.0):
        raise ValueError(f"Flow ratio Q must be between 0.0 and 1.0, got: {q_ratio}")

    radial_fraction = math.sqrt(1.0 - math.sqrt(1.0 - q_ratio))
    return r_total * radial_fraction


class SideSector:
    """Represents an angular side sector in the outer inlet annulus."""

    def __init__(self, index: int, angle_start: float, angle_width: float, color: str):
        self.index = index
        self.angle_start = angle_start % 360.0
        self.angle_width = angle_width
        self.angle_end = (angle_start + angle_width) % 360.0
        self.color = color
        self.name = f"Side {index + 1}"

    def contains(self, angle_deg: np.ndarray) -> np.ndarray:
        """Check if angles (in degrees, 0 to 360) fall inside this sector."""
        a = angle_deg % 360.0
        s = self.angle_start
        w = self.angle_width
        if w >= 360.0:
            return np.ones_like(a, dtype=bool)

        e = (s + w)
        if e <= 360.0:
            return (a >= s) & (a < e)
        else:
            # Sector crosses 360 / 0 degrees boundary
            return (a >= s) | (a < (e % 360.0))

    def __repr__(self) -> str:
        return f"{self.name} [{self.angle_start:.1f}°-{(self.angle_start + self.angle_width):.1f}°, width={self.angle_width:.1f}°]"


def build_side_sectors(
    n_sides: Optional[int] = None,
    theta: Optional[Union[float, int, Sequence[float]]] = None,
    rotation_deg: float = 0.0,
    spacing: str = "equispaced",
) -> List[SideSector]:
    """Build the list of SideSector objects based on user input parameters.

    Supports:
    1. Independent theta (e.g. theta = 90, n_sides = None):
       Divides the 360° circle into equal sectors of width theta (360/90 = 4 sides).
    2. Explicit n_sides without theta:
       Divides 360° into n_sides equal sectors (width = 360 / n_sides).
    3. Both n_sides and scalar theta provided:
       Creates n_sides sectors of width theta. If n_sides * theta < 360,
       they can be 'equispaced' (symmetrically distributed around 360°) or 'contiguous'.
    4. List/sequence of thetas:
       Creates len(thetas) sectors, each with its specified angular width.
    """
    sectors: List[SideSector] = []

    if n_sides == 0:
        return []

    actual_sides = n_sides if n_sides is not None and n_sides > 0 else 1

    # Contiguous mode with multiple inlets: at most actual_sides - 1 user values, last is auto-calculated
    if spacing == "contiguous" and actual_sides >= 2:
        if isinstance(theta, (list, tuple, np.ndarray)):
            user_thetas = [float(t) for t in theta if float(t) > 0][:actual_sides - 1]
        elif theta is not None and float(theta) > 0:
            user_thetas = [float(theta)]
        else:
            user_thetas = []

        # If fewer than actual_sides - 1 values provided, distribute remaining angle equally
        if len(user_thetas) < actual_sides - 1:
            missing = (actual_sides - 1) - len(user_thetas)
            curr_sum = sum(user_thetas)
            rem_avail = max(0.0, 360.0 - curr_sum)
            step_val = rem_avail / (missing + 1)
            user_thetas = user_thetas + [step_val] * missing

        # Ensure user sum leaves at least 1 degree for the final sector
        user_sum = sum(user_thetas)
        if user_sum >= 359.0:
            scale = 358.0 / user_sum
            user_thetas = [t * scale for t in user_thetas]
            user_sum = sum(user_thetas)

        last_theta = max(1.0, 360.0 - user_sum)
        final_thetas = user_thetas + [last_theta]

        curr_start = rotation_deg % 360.0
        for i, width in enumerate(final_thetas):
            color = SIDE_PALETTE[i % len(SIDE_PALETTE)]
            sectors.append(SideSector(i, curr_start, width, color))
            curr_start = (curr_start + width) % 360.0
        return sectors

    if isinstance(theta, (list, tuple, np.ndarray)):
        thetas_list = [float(t) for t in theta]
        if n_sides is not None and n_sides > 0:
            if len(thetas_list) < n_sides:
                last = thetas_list[-1] if thetas_list else 90.0
                thetas_list = thetas_list + [last] * (n_sides - len(thetas_list))
            elif len(thetas_list) > n_sides:
                thetas_list = thetas_list[:n_sides]

        if spacing == "contiguous":
            curr_start = rotation_deg % 360.0
            for i, width in enumerate(thetas_list):
                color = SIDE_PALETTE[i % len(SIDE_PALETTE)]
                sectors.append(SideSector(i, curr_start, width, color))
                curr_start = (curr_start + width) % 360.0
        else:
            # Equispaced placement of custom widths
            step = 360.0 / len(thetas_list)
            for i, width in enumerate(thetas_list):
                start = (rotation_deg + i * step) % 360.0
                color = SIDE_PALETTE[i % len(SIDE_PALETTE)]
                sectors.append(SideSector(i, start, width, color))
        return sectors

    theta_val = float(theta) if theta is not None else None

    # Case 1: Independent theta, n_sides not provided or 1 with theta < 360
    if theta_val is not None and (n_sides is None or n_sides <= 1 and theta_val < 360.0):
        if theta_val <= 0:
            raise ValueError("Theta must be greater than 0 degrees.")
        # Divide 360 degrees equally by theta
        calculated_sides = max(1, int(round(360.0 / theta_val)))
        if n_sides is not None and n_sides > 1:
            calculated_sides = n_sides

        for i in range(calculated_sides):
            start = (rotation_deg + i * theta_val) % 360.0
            color = SIDE_PALETTE[i % len(SIDE_PALETTE)]
            sectors.append(SideSector(i, start, theta_val, color))
        return sectors

    # Case 2: n_sides provided without theta
    if theta_val is None:
        width = 360.0 / actual_sides
        for i in range(actual_sides):
            start = (rotation_deg + i * width) % 360.0
            color = SIDE_PALETTE[i % len(SIDE_PALETTE)]
            sectors.append(SideSector(i, start, width, color))
        return sectors

    # Case 3: Both n_sides and scalar theta provided
    total_coverage = actual_sides * theta_val
    if total_coverage >= 360.0 or spacing == "contiguous":
        # Place sectors contiguously
        for i in range(actual_sides):
            start = (rotation_deg + i * theta_val) % 360.0
            color = SIDE_PALETTE[i % len(SIDE_PALETTE)]
            sectors.append(SideSector(i, start, theta_val, color))
    else:
        # Equispaced placement around 360°
        step = 360.0 / actual_sides
        for i in range(actual_sides):
            start = (rotation_deg + i * step) % 360.0
            color = SIDE_PALETTE[i % len(SIDE_PALETTE)]
            sectors.append(SideSector(i, start, theta_val, color))

    return sectors


def genera_blades(n_blades: int) -> List[dict]:
    """Generate blade angular sectors following alternating down/up logic.

    Args:
        n_blades: Total number of blade pairs (down + up).
                  Produces 2 * n_blades sectors of angular width 360 / (2 * n_blades).

    Returns:
        List of dicts with keys 'tipo', 'start_deg', 'end_deg'.
    """
    if n_blades <= 0:
        return []

    step = 360.0 / (2 * n_blades)
    blades = []

    for k in range(2 * n_blades):
        theta_start = k * step
        theta_end = (k + 1) * step
        tipo = "blade down" if k % 2 == 0 else "blade up"
        indice = (k // 2) + 1

        blades.append(
            {
                "tipo": f"{tipo} {indice}",
                "start_deg": theta_start,
                "end_deg": theta_end,
            }
        )

    return blades


class MorphoVisualizer:
    """Class to load, store, and visualize morphogenerator streamlines with arbitrary Q, theta, and rotation."""

    def __init__(
        self,
        filepath: Union[str, Path],
        z_bottom: Optional[float] = None,
        z_inlet: Optional[float] = None,
        r_inlet_max: float = 6.25,
        r_bottom_max: float = 1.0,
    ):
        self.filepath = str(filepath)
        self.r_inlet_max = r_inlet_max
        self.r_bottom_max = r_bottom_max

        # Auto-detect number of blades from filename (e.g. M2_N4... -> 4)
        import re
        match = re.search(r'N(\d+)', Path(self.filepath).name)
        self.n_blades = int(match.group(1)) if match else 4

        # Load once and store in memory (uses fast persistent cache in txt_to_image/.cache)
        self.processor = DataProcessor(self.filepath, z_bottom_target=z_bottom, z_inlet_target=z_inlet)
        self.inlet_coords, self.bottom_coords, self.sync_ids = self.processor.get_synced_coords(
            r_inlet_max=r_inlet_max,
            r_bottom_max=r_bottom_max,
        )

        self.z_inlet = self.processor.z_inlet_target
        self.z_bottom = self.processor.z_bottom_target
        self.r_bottom = self.processor.r_bottom_detected or r_bottom_max
        self.n_points = len(self.inlet_coords)

        # Pre-compute polar coordinates at the inlet for rapid re-filtering
        self.inlet_r = np.sqrt(self.inlet_coords[:, 0] ** 2 + self.inlet_coords[:, 1] ** 2)
        # Angles mapped to [0, 360) degrees
        raw_angles = np.degrees(np.arctan2(self.inlet_coords[:, 1], self.inlet_coords[:, 0]))
        self.inlet_theta = np.where(raw_angles < 0, raw_angles + 360.0, raw_angles)

    def classify_streamlines(
        self,
        q_ratio: float,
        n_sides: Optional[int] = None,
        theta: Optional[Union[float, int, Sequence[float]]] = None,
        rotation_deg: float = 0.0,
        spacing: str = "equispaced",
    ) -> Tuple[np.ndarray, List[SideSector], float]:
        """Classify each streamline into Central (0), Side Sector k (k+1), or Unassigned (-1).

        Returns:
            Tuple[np.ndarray, List[SideSector], float]:
                - labels: integer array of shape (N,) indicating zone assignment
                - sectors: list of configured SideSector objects
                - r_q: the computed physical core radius (in mm)
        """
        r_q = calculate_physical_radius(q_ratio, r_total=self.r_inlet_max)
        sectors = build_side_sectors(
            n_sides=n_sides,
            theta=theta,
            rotation_deg=rotation_deg,
            spacing=spacing,
        )

        labels = np.full(self.n_points, -1, dtype=int)

        # Central core points (r <= r_q)
        is_central = self.inlet_r <= r_q
        labels[is_central] = 0

        # Side annulus points (r_q < r <= r_inlet_max)
        is_side_annulus = (~is_central) & (self.inlet_r <= self.r_inlet_max)

        annulus_indices = np.where(is_side_annulus)[0]
        annulus_thetas = self.inlet_theta[annulus_indices]

        # Classify side points by angular sector
        for sector in sectors:
            mask_in_sector = sector.contains(annulus_thetas)
            # Sector indices mapped back to global labels
            matched_global = annulus_indices[mask_in_sector]
            # First sector gets precedence if overlaps occur
            unassigned_in_match = matched_global[labels[matched_global] == -1]
            labels[unassigned_in_match] = sector.index + 1

        return labels, sectors, r_q

    def plot(
        self,
        q_ratio: float = 0.5,
        n_sides: Optional[int] = None,
        theta: Optional[Union[float, int, Sequence[float]]] = 90.0,
        rotation_deg: float = 0.0,
        spacing: str = "equispaced",
        point_size: float = 1.0,
        alpha: float = 0.7,
        figsize: Tuple[float, float] = (13.5, 6.5),
        save_path: Optional[Union[str, Path]] = None,
        show: bool = True,
        n_blades: Optional[int] = None,
        show_blades: bool = True,
    ) -> Tuple[plt.Figure, Tuple[plt.Axes, plt.Axes]]:
        """Generate and display/save the side-by-side Inlet and Outlet visualization."""
        labels, sectors, r_q = self.classify_streamlines(
            q_ratio=q_ratio,
            n_sides=n_sides,
            theta=theta,
            rotation_deg=rotation_deg,
            spacing=spacing,
        )

        fig, (ax_inlet, ax_outlet) = plt.subplots(1, 2, figsize=figsize)

        # --- LEFT PLOT: INLET PLANE GEOMETRY & BOUNDARIES ---
        # Note: Streamline colors inside R = 6.25 mm are removed on inlet plane

        # Circle 3 (R = 12.5 mm): Distribution chamber outer boundary (solid black)
        circle_3 = Circle(
            (0, 0),
            radius=12.5,
            edgecolor=WALL_COLOR,
            fill=False,
            linestyle="-",
            linewidth=1.8,
            zorder=1,
        )
        ax_inlet.add_patch(circle_3)

        # Circle 2 (R = 6.25 mm): Blade perimeter / chamber boundary (dashed)
        circle_2 = Circle(
            (0, 0),
            radius=self.r_inlet_max,
            edgecolor=WALL_COLOR,
            fill=False,
            linestyle="--",
            linewidth=1.0,
            zorder=3,
        )
        ax_inlet.add_patch(circle_2)

        # Circle 1 (R = 2.5 mm): Central channel (inlet flow represented in red)
        circle_1 = Circle(
            (0, 0),
            radius=2.5,
            facecolor=mcolors.to_rgba(CENTRAL_COLOR, alpha=0.22),
            edgecolor=CENTRAL_COLOR,
            linestyle="-",
            linewidth=2.0,
            zorder=4,
        )
        ax_inlet.add_patch(circle_1)

        # Peripheral inlets: circle of radius 2.5 mm centered at R_mid = (6.25 + 12.5)/2 = 9.375 mm
        # positioned at the midpoint of each sector's angular width
        r_mid = (self.r_inlet_max + 12.5) / 2.0  # 9.375 mm
        for sector in sectors:
            mid_deg = (sector.angle_start + sector.angle_width / 2.0) % 360.0
            mid_rad = math.radians(mid_deg)
            cx = r_mid * math.cos(mid_rad)
            cy = r_mid * math.sin(mid_rad)
            fc = mcolors.to_rgba(sector.color, alpha=0.35)
            ec = mcolors.to_rgba(sector.color, alpha=0.95)
            inlet_hole = Circle(
                (cx, cy),
                radius=2.5,
                facecolor=fc,
                edgecolor=ec,
                linewidth=1.8,
                linestyle="-",
                zorder=5,
            )
            ax_inlet.add_patch(inlet_hole)

        # Blades overlay at Inlet: full blade slices in blue and orange
        if show_blades:
            blades_n = n_blades if n_blades is not None else getattr(self, "n_blades", 4)
            blades_list = genera_blades(blades_n)

            for b in blades_list:
                is_down = "down" in b["tipo"]
                b_color = BLADE_DOWN_COLOR if is_down else BLADE_UP_COLOR
                b_ls = "-" if is_down else "--"

                # Fill entire slice of the blade between R=2.5 and R=6.25 mm
                blade_wedge = Wedge(
                    (0, 0),
                    r=self.r_inlet_max,
                    theta1=b["start_deg"],
                    theta2=b["end_deg"],
                    width=(self.r_inlet_max - 2.5),
                    facecolor=mcolors.to_rgba(b_color, alpha=0.22),
                    edgecolor="none",
                    zorder=2,
                )
                ax_inlet.add_patch(blade_wedge)

                # Radial boundary lines across the annulus from R=2.5 to R=6.25 mm, colored with blade color
                for deg in [b["start_deg"], b["end_deg"]]:
                    rad = math.radians(deg)
                    ax_inlet.plot(
                        [2.5 * math.cos(rad), self.r_inlet_max * math.cos(rad)],
                        [2.5 * math.sin(rad), self.r_inlet_max * math.sin(rad)],
                        color=b_color,
                        linestyle=":",
                        linewidth=1.6,
                        alpha=0.95,
                        zorder=3,
                    )

                # Outer arc along the perimeter representing the blade
                arc_patch = Arc(
                    (0, 0),
                    width=self.r_inlet_max * 2,
                    height=self.r_inlet_max * 2,
                    angle=0,
                    theta1=b["start_deg"],
                    theta2=b["end_deg"],
                    color=b_color,
                    linewidth=2.8,
                    linestyle=b_ls,
                    zorder=4,
                )
                ax_inlet.add_patch(arc_patch)

        # Sector boundary lines across the distribution chamber (from R=6.25 to R=12.5 mm)
        for sector in sectors:
            for angle in [sector.angle_start, sector.angle_start + sector.angle_width]:
                rad = math.radians(angle)
                ax_inlet.plot(
                    [self.r_inlet_max * math.cos(rad), 12.5 * math.cos(rad)],
                    [self.r_inlet_max * math.sin(rad), 12.5 * math.sin(rad)],
                    color=sector.color,
                    linestyle=":",
                    linewidth=1.2,
                    zorder=2,
                )

        # Indicator arc for rotation angle if non-zero
        if abs(rotation_deg) > 1e-3:
            rot_arc_r = 13.1
            arc_patch = Arc(
                (0, 0),
                width=rot_arc_r * 2,
                height=rot_arc_r * 2,
                angle=0,
                theta1=0,
                theta2=rotation_deg % 360,
                color="#7C3AED",
                linewidth=2.0,
                linestyle="-",
            )
            ax_inlet.add_patch(arc_patch)
            # Arrow head
            end_rad = math.radians(rotation_deg % 360)
            ax_inlet.plot(rot_arc_r * math.cos(end_rad), rot_arc_r * math.sin(end_rad), marker=">", color="#7C3AED", markersize=6)

        blades_title_info = f"  |  Blades = {getattr(self, 'n_blades', 4)}" if show_blades else ""
        ax_inlet.set_title(
            f"Top View Morphogenerator\n"
            f"Central Fluid: Q = {q_ratio:.2f} (R_Q = {r_q:.2f} mm)  |  Rotation = {rotation_deg:.1f}°{blades_title_info}",
            fontsize=10,
            fontweight="bold",
        )
        ax_inlet.set_xlabel("X (mm)", fontsize=9)
        ax_inlet.set_ylabel("Y (mm)", fontsize=9)
        lim_inlet = 14.0
        ax_inlet.set_xlim([-lim_inlet, lim_inlet])
        ax_inlet.set_ylim([-lim_inlet, lim_inlet])
        ax_inlet.set_aspect("equal")
        ax_inlet.grid(True, linestyle="--", alpha=0.4)

        handles, leg_labels = ax_inlet.get_legend_handles_labels()
        if show_blades:
            handles.append(Line2D([0], [0], color=BLADE_DOWN_COLOR, lw=2.5, linestyle="-", label="Blade down"))
            handles.append(Line2D([0], [0], color=BLADE_UP_COLOR, lw=2.5, linestyle="--", label="Blade up"))
            leg_labels.append("Blade down")
            leg_labels.append("Blade up")
        ax_inlet.legend(handles=handles, labels=leg_labels, loc="upper right", fontsize=7.5, framealpha=0.85)

        # --- RIGHT PLOT: OUTLET PLANE ---
        mask_unassigned = labels == -1
        mask_central = labels == 0
        # Unassigned side points
        if np.any(mask_unassigned):
            ax_outlet.scatter(
                self.bottom_coords[mask_unassigned, 0],
                self.bottom_coords[mask_unassigned, 1],
                c=UNASSIGNED_COLOR,
                s=point_size,
                alpha=alpha * 0.4,
                rasterized=True,
            )

        # Side sectors points at outlet
        for sector in sectors:
            mask_sec = labels == (sector.index + 1)
            ax_outlet.scatter(
                self.bottom_coords[mask_sec, 0],
                self.bottom_coords[mask_sec, 1],
                c=sector.color,
                s=point_size,
                alpha=alpha,
                rasterized=True,
            )

        # Central core points at outlet
        ax_outlet.scatter(
            self.bottom_coords[mask_central, 0],
            self.bottom_coords[mask_central, 1],
            c=CENTRAL_COLOR,
            s=point_size,
            alpha=alpha,
            rasterized=True,
        )

        # Geometric overlay at Outlet
        outlet_circle = Circle(
            (0, 0),
            radius=self.r_bottom,
            edgecolor=WALL_COLOR,
            fill=False,
            linestyle="--",
            linewidth=1.2,
            label=f"Outlet Nozzle (R={self.r_bottom:.2f} mm)",
        )
        ax_outlet.add_patch(outlet_circle)

        ax_outlet.set_title(
            f"Nozzle Plane\n"
            f"Swirl Morphogenesis & Side Streamlines Trace",
            fontsize=10,
            fontweight="bold",
        )
        ax_outlet.set_xlabel("X (mm)", fontsize=9)
        ax_outlet.set_ylabel("Y (mm)", fontsize=9)
        lim_outlet = self.r_bottom * 1.25
        ax_outlet.set_xlim([-lim_outlet, lim_outlet])
        ax_outlet.set_ylim([-lim_outlet, lim_outlet])
        ax_outlet.set_aspect("equal")
        ax_outlet.grid(True, linestyle="--", alpha=0.4)
        ax_outlet.legend(loc="upper right", fontsize=7.5, framealpha=0.85)

        fig.suptitle(
            f"Morphogenerator Streamline Visualization  |  {Path(self.filepath).name}\n"
            f"Synced Streamlines: {self.n_points:,}  |  Sides: {len(sectors)}  |  Rotation: {rotation_deg:.1f}°",
            fontsize=11,
            fontweight="bold",
            y=0.99,
        )
        plt.tight_layout()

        if save_path:
            save_obj = Path(save_path)
            save_obj.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(str(save_obj), dpi=300, bbox_inches="tight")
            print(f"Visualization saved to: {save_obj.resolve()}")

        if show:
            plt.show()
        else:
            plt.close(fig)

        return fig, (ax_inlet, ax_outlet)

    def render_outlet_pil(
        self,
        q_ratio: float = 0.5,
        n_sides: Optional[int] = None,
        theta: Optional[Union[float, int, Sequence[float]]] = 90.0,
        rotation_deg: float = 0.0,
        spacing: str = "equispaced",
        point_size: float = 1.0,
        alpha: float = 0.75,
        figsize: Tuple[float, float] = (5.5, 5.5),
        dpi: int = 150,
        bg_color: Optional[str] = None,
        show_nozzle_circle: bool = True,
        show_grid: bool = True,
        show_legend: bool = True,
    ) -> PILImage.Image:
        """Render ONLY the Outlet plane as a PIL Image without any title."""
        labels, sectors, r_q = self.classify_streamlines(
            q_ratio=q_ratio,
            n_sides=n_sides,
            theta=theta,
            rotation_deg=rotation_deg,
            spacing=spacing,
        )

        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        if bg_color:
            fig.patch.set_facecolor(bg_color)
            ax.set_facecolor(bg_color)
        else:
            fig.patch.set_alpha(0.0)
            ax.set_facecolor("none")

        # Unassigned side points
        mask_unassigned = labels == -1
        if np.any(mask_unassigned):
            ax.scatter(
                self.bottom_coords[mask_unassigned, 0],
                self.bottom_coords[mask_unassigned, 1],
                c=UNASSIGNED_COLOR,
                s=point_size,
                alpha=alpha * 0.4,
                rasterized=True,
                label="Unassigned",
            )

        # Side sectors points at outlet
        for sector in sectors:
            mask_sec = labels == (sector.index + 1)
            ax.scatter(
                self.bottom_coords[mask_sec, 0],
                self.bottom_coords[mask_sec, 1],
                c=sector.color,
                s=point_size,
                alpha=alpha,
                rasterized=True,
                label=sector.name,
            )

        # Central core points at outlet
        mask_central = labels == 0
        ax.scatter(
            self.bottom_coords[mask_central, 0],
            self.bottom_coords[mask_central, 1],
            c=CENTRAL_COLOR,
            s=point_size,
            alpha=alpha,
            rasterized=True,
            label=f"Core (Q={q_ratio:.2f})",
        )

        # Geometric overlay: Outlet nozzle ring
        if show_nozzle_circle:
            circle_color = "#E5E7EB" if bg_color and bg_color not in ("white", "#FFFFFF") else WALL_COLOR
            outlet_circle = Circle(
                (0, 0),
                radius=self.r_bottom,
                edgecolor=circle_color,
                fill=False,
                linestyle="--",
                linewidth=1.2,
            )
            ax.add_patch(outlet_circle)

        # Explicitly NO title (as requested: "without title")
        ax.set_title("")

        # Axis labels and styling
        text_color = "#9CA3AF" if bg_color and bg_color not in ("white", "#FFFFFF") else "#4B5563"
        ax.set_xlabel("X (mm)", fontsize=8, color=text_color)
        ax.set_ylabel("Y (mm)", fontsize=8, color=text_color)
        ax.tick_params(colors=text_color, labelsize=7)

        lim_outlet = self.r_bottom * 1.2
        ax.set_xlim([-lim_outlet, lim_outlet])
        ax.set_ylim([-lim_outlet, lim_outlet])
        ax.set_aspect("equal")

        if show_grid:
            ax.grid(True, linestyle="--", alpha=0.25, color=text_color)
        else:
            ax.grid(False)

        spine_color = "#374151" if bg_color and bg_color not in ("white", "#FFFFFF") else "#D1D5DB"
        for spine in ax.spines.values():
            spine.set_color(spine_color)
            spine.set_linewidth(0.8)

        if show_legend:
            ax.legend(
                loc="upper right",
                fontsize=7,
                framealpha=0.75,
                facecolor=bg_color if bg_color else "white",
                edgecolor=spine_color,
                labelcolor=text_color,
            )

        plt.tight_layout(pad=0.5)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", transparent=(bg_color is None))
        plt.close(fig)
        buf.seek(0)
        return PILImage.open(buf)

    def render_dual_pil(
        self,
        q_ratio: float = 0.5,
        n_sides: Optional[int] = None,
        theta: Optional[Union[float, int, Sequence[float]]] = 90.0,
        rotation_deg: float = 0.0,
        spacing: str = "equispaced",
        point_size: float = 1.0,
        alpha: float = 0.75,
        figsize: Tuple[float, float] = (9.2, 4.6),
        dpi: int = 110,
        bg_color: Optional[str] = None,
        show_nozzle_circle: bool = True,
        show_grid: bool = True,
        show_legend: bool = False,
        n_blades: Optional[int] = None,
        show_blades: bool = True,
    ) -> Tuple[PILImage.Image, List[SideSector], float]:
        """Render both Inlet and Outlet planes side-by-side as a PIL Image without inside legends.

        Returns:
            Tuple of (pil_image, sectors_list, r_q).
        """
        labels, sectors, r_q = self.classify_streamlines(
            q_ratio=q_ratio,
            n_sides=n_sides,
            theta=theta,
            rotation_deg=rotation_deg,
            spacing=spacing,
        )

        fig, (ax_inlet, ax_outlet) = plt.subplots(1, 2, figsize=figsize, dpi=dpi)
        if bg_color:
            fig.patch.set_facecolor(bg_color)
            ax_inlet.set_facecolor(bg_color)
            ax_outlet.set_facecolor(bg_color)
        else:
            fig.patch.set_alpha(0.0)
            ax_inlet.set_facecolor("none")
            ax_outlet.set_facecolor("none")

        text_color = "#9CA3AF" if bg_color and bg_color not in ("white", "#FFFFFF") else "#4B5563"
        spine_color = "#374151" if bg_color and bg_color not in ("white", "#FFFFFF") else "#D1D5DB"

        # --- LEFT: INLET PLANE GEOMETRY & BOUNDARIES ---
        # Note: Streamline colors inside R = 6.25 mm are removed on inlet plane

        # Circle 3 (R = 12.5 mm): Distribution chamber outer boundary (solid black)
        circle_3 = Circle(
            (0, 0),
            radius=12.5,
            edgecolor=WALL_COLOR,
            fill=False,
            linestyle="-",
            linewidth=1.8,
            zorder=1,
        )
        ax_inlet.add_patch(circle_3)

        # Circle 2 (R = 6.25 mm): Blade perimeter / chamber boundary (dashed)
        circle_2 = Circle(
            (0, 0),
            radius=self.r_inlet_max,
            edgecolor=WALL_COLOR,
            fill=False,
            linestyle="--",
            linewidth=1.0,
            zorder=3,
        )
        ax_inlet.add_patch(circle_2)

        # Circle 1 (R = 2.5 mm): Central channel (inlet flow represented in red)
        circle_1 = Circle(
            (0, 0),
            radius=2.5,
            facecolor=mcolors.to_rgba(CENTRAL_COLOR, alpha=0.22),
            edgecolor=CENTRAL_COLOR,
            linestyle="-",
            linewidth=2.0,
            zorder=4,
        )
        ax_inlet.add_patch(circle_1)

        # Peripheral inlets: circle of radius 2.5 mm centered at R_mid = (6.25 + 12.5)/2 = 9.375 mm
        # positioned at the midpoint of each sector's angular width
        r_mid = (self.r_inlet_max + 12.5) / 2.0  # 9.375 mm
        for sector in sectors:
            mid_deg = (sector.angle_start + sector.angle_width / 2.0) % 360.0
            mid_rad = math.radians(mid_deg)
            cx = r_mid * math.cos(mid_rad)
            cy = r_mid * math.sin(mid_rad)
            fc = mcolors.to_rgba(sector.color, alpha=0.35)
            ec = mcolors.to_rgba(sector.color, alpha=0.95)
            inlet_hole = Circle(
                (cx, cy),
                radius=2.5,
                facecolor=fc,
                edgecolor=ec,
                linewidth=1.8,
                linestyle="-",
                zorder=5,
            )
            ax_inlet.add_patch(inlet_hole)

        # Blades overlay at Inlet: full blade slices in blue and orange
        if show_blades:
            blades_n = n_blades if n_blades is not None else getattr(self, "n_blades", 4)
            blades_list = genera_blades(blades_n)

            for b in blades_list:
                is_down = "down" in b["tipo"]
                b_color = BLADE_DOWN_COLOR if is_down else BLADE_UP_COLOR
                b_ls = "-" if is_down else "--"

                # Fill entire slice of the blade between R=2.5 and R=6.25 mm
                blade_wedge = Wedge(
                    (0, 0),
                    r=self.r_inlet_max,
                    theta1=b["start_deg"],
                    theta2=b["end_deg"],
                    width=(self.r_inlet_max - 2.5),
                    facecolor=mcolors.to_rgba(b_color, alpha=0.22),
                    edgecolor="none",
                    zorder=2,
                )
                ax_inlet.add_patch(blade_wedge)

                # Radial boundary lines across the annulus from R=2.5 to R=6.25 mm, colored with blade color
                for deg in [b["start_deg"], b["end_deg"]]:
                    rad = math.radians(deg)
                    ax_inlet.plot(
                        [2.5 * math.cos(rad), self.r_inlet_max * math.cos(rad)],
                        [2.5 * math.sin(rad), self.r_inlet_max * math.sin(rad)],
                        color=b_color,
                        linestyle=":",
                        linewidth=1.6,
                        alpha=0.95,
                        zorder=3,
                    )

                # Outer arc along the perimeter representing the blade
                arc_patch = Arc(
                    (0, 0),
                    width=self.r_inlet_max * 2,
                    height=self.r_inlet_max * 2,
                    angle=0,
                    theta1=b["start_deg"],
                    theta2=b["end_deg"],
                    color=b_color,
                    linewidth=2.5,
                    linestyle=b_ls,
                    zorder=4,
                )
                ax_inlet.add_patch(arc_patch)

        # Sector boundary lines across outer annulus up to Circle 3 (12.5 mm)
        for sector in sectors:
            for angle in [sector.angle_start, sector.angle_start + sector.angle_width]:
                rad = math.radians(angle)
                ax_inlet.plot(
                    [self.r_inlet_max * math.cos(rad), 12.5 * math.cos(rad)],
                    [self.r_inlet_max * math.sin(rad), 12.5 * math.sin(rad)],
                    color=sector.color,
                    linestyle=":",
                    linewidth=1.2,
                    zorder=2,
                )

        if abs(rotation_deg) > 1e-3:
            rot_arc_r = 13.1
            arc_patch = Arc(
                (0, 0),
                width=rot_arc_r * 2,
                height=rot_arc_r * 2,
                angle=0,
                theta1=0,
                theta2=rotation_deg % 360,
                color="#7C3AED",
                linewidth=1.8,
                linestyle="-",
            )
            ax_inlet.add_patch(arc_patch)
            end_rad = math.radians(rotation_deg % 360)
            ax_inlet.plot(rot_arc_r * math.cos(end_rad), rot_arc_r * math.sin(end_rad), marker=">", color="#7C3AED", markersize=5)

        ax_inlet.set_title("Top View Morphogenerator", fontsize=10, fontweight="bold", color=text_color)
        ax_inlet.set_xlabel("X (mm)", fontsize=8, color=text_color)
        ax_inlet.set_ylabel("Y (mm)", fontsize=8, color=text_color)
        ax_inlet.tick_params(colors=text_color, labelsize=7)
        lim_inlet = 14.0
        ax_inlet.set_xlim([-lim_inlet, lim_inlet])
        ax_inlet.set_ylim([-lim_inlet, lim_inlet])
        ax_inlet.set_aspect("equal")
        if show_grid:
            ax_inlet.grid(True, linestyle="--", alpha=0.25, color=text_color)
        for spine in ax_inlet.spines.values():
            spine.set_color(spine_color)
            spine.set_linewidth(0.8)

        # --- RIGHT: OUTLET PLANE ---
        mask_unassigned = labels == -1
        mask_central = labels == 0
        if np.any(mask_unassigned):
            ax_outlet.scatter(
                self.bottom_coords[mask_unassigned, 0],
                self.bottom_coords[mask_unassigned, 1],
                c=UNASSIGNED_COLOR,
                s=point_size,
                alpha=alpha * 0.4,
                rasterized=True,
                label="Unassigned",
            )

        for sector in sectors:
            mask_sec = labels == (sector.index + 1)
            ax_outlet.scatter(
                self.bottom_coords[mask_sec, 0],
                self.bottom_coords[mask_sec, 1],
                c=sector.color,
                s=point_size,
                alpha=alpha,
                rasterized=True,
                label=sector.name,
            )

        ax_outlet.scatter(
            self.bottom_coords[mask_central, 0],
            self.bottom_coords[mask_central, 1],
            c=CENTRAL_COLOR,
            s=point_size,
            alpha=alpha,
            rasterized=True,
            label=f"Core (Q={q_ratio:.2f})",
        )

        if show_nozzle_circle:
            circle_color = "#E5E7EB" if bg_color and bg_color not in ("white", "#FFFFFF") else WALL_COLOR
            outlet_circle = Circle(
                (0, 0),
                radius=self.r_bottom,
                edgecolor=circle_color,
                fill=False,
                linestyle="--",
                linewidth=1.2,
            )
            ax_outlet.add_patch(outlet_circle)

        ax_outlet.set_title("Nozzle Plane", fontsize=10, fontweight="bold", color=text_color)
        ax_outlet.set_xlabel("X (mm)", fontsize=8, color=text_color)
        ax_outlet.set_ylabel("Y (mm)", fontsize=8, color=text_color)
        ax_outlet.tick_params(colors=text_color, labelsize=7)
        lim_outlet = self.r_bottom * 1.25
        ax_outlet.set_xlim([-lim_outlet, lim_outlet])
        ax_outlet.set_ylim([-lim_outlet, lim_outlet])
        ax_outlet.set_aspect("equal")
        if show_grid:
            ax_outlet.grid(True, linestyle="--", alpha=0.25, color=text_color)
        for spine in ax_outlet.spines.values():
            spine.set_color(spine_color)
            spine.set_linewidth(0.8)

        if show_legend:
            ax_inlet.legend(loc="upper right", fontsize=7, framealpha=0.75, facecolor=bg_color or "white", edgecolor=spine_color, labelcolor=text_color)
            ax_outlet.legend(loc="upper right", fontsize=7, framealpha=0.75, facecolor=bg_color or "white", edgecolor=spine_color, labelcolor=text_color)

        plt.tight_layout(pad=0.8)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", transparent=(bg_color is None))
        plt.close(fig)
        buf.seek(0)
        return PILImage.open(buf), sectors, r_q


def resolve_streamline_file(n: int, base_dir: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Find the streamline simulation file for a given N (e.g. M2_N6_er10.txt or M2_N6.txt)."""
    search_dirs = []
    if base_dir is not None:
        search_dirs.append(Path(base_dir))
    search_dirs.extend([
        PROJECT_ROOT / "streamlines",
        PROJECT_ROOT / "txt_to_image" / "streamline_without_Q",
        PROJECT_ROOT.parent / "txt_to_image" / "streamline_without_Q",
    ])
    candidates = [
        f"M2_N{n}_er10.txt",
        f"M2_N{n}.txt",
        f"M2_N{n}_er8.txt",
        f"M2_N{n}_er15.txt",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for name in candidates:
            cand = d / name
            if cand.exists() and cand.stat().st_size > 0:
                return cand
        matches = list(d.glob(f"*N{n}*.txt"))
        for m in matches:
            if m.stat().st_size > 0:
                return m

    # Fallback for isolated environments with precomputed .cache:
    from streamline_extractor import _find_cache_file
    for name in candidates:
        virtual_cand = PROJECT_ROOT / ".cache" / name
        cache = _find_cache_file(virtual_cand)
        if cache is not None and cache.exists():
            return virtual_cand

    return None


_VISUALIZER_CACHE: dict[int, MorphoVisualizer] = {}


def get_visualizer_for_n(n: int) -> Optional[MorphoVisualizer]:
    """Get or create a cached MorphoVisualizer instance for a given N."""
    if n in _VISUALIZER_CACHE:
        return _VISUALIZER_CACHE[n]
    filepath = resolve_streamline_file(n)
    if filepath is not None:
        viz = MorphoVisualizer(filepath)
        _VISUALIZER_CACHE[n] = viz
        return viz
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Visualize morphogenerator streamline core and multi-sector side distribution."
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default="txt_to_image/streamline_without_Q/M2_N6_er10.txt",
        help="Path to streamline simulation .txt file.",
    )
    parser.add_argument(
        "--q",
        "-q",
        type=float,
        default=0.5,
        help="Flow ratio Q in [0.0, 1.0] (default: 0.5).",
    )
    parser.add_argument(
        "--sides",
        "-s",
        type=int,
        default=None,
        help="Number of side sectors (default: derived from theta or 1).",
    )
    parser.add_argument(
        "--theta",
        "-t",
        type=float,
        default=None,
        help="Angular width (in degrees) for side sectors. If provided without --sides, divides 360° equally.",
    )
    parser.add_argument(
        "--thetas",
        nargs="+",
        type=float,
        default=None,
        help="Custom list of angular widths for each side sector (e.g. --thetas 60 90 45).",
    )
    parser.add_argument(
        "--rotation",
        "-r",
        type=float,
        default=0.0,
        help="Rotation angle (in degrees) applied to the side annulus sectors (default: 0.0°).",
    )
    parser.add_argument(
        "--spacing",
        type=str,
        choices=["equispaced", "contiguous"],
        default="equispaced",
        help="Arrangement when sides * theta < 360° (default: equispaced).",
    )
    parser.add_argument(
        "--blades",
        "-b",
        type=int,
        default=None,
        help="Number of blades for inlet plane partition (default: auto-detected from filename or 4).",
    )
    parser.add_argument(
        "--no-blades",
        action="store_true",
        help="Disable drawing blade partition lines and labels on the inlet plane.",
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Optional path to save output image (e.g. output/morpho_view.png).",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not display interactive matplotlib window.",
    )

    args = parser.parse_args()

    # Determine theta argument
    theta_arg: Optional[Union[float, Sequence[float]]] = None
    if args.thetas is not None:
        theta_arg = args.thetas
    elif args.theta is not None:
        theta_arg = args.theta
    else:
        # Default: theta = 90° (4 equal sides)
        theta_arg = 90.0

    print(f"Loading streamline data from: {args.file}")
    viz = MorphoVisualizer(args.file)
    print(f"Loaded {viz.n_points:,} synced streamlines successfully.")
    print(f"Generating visualization: Q={args.q}, Sides={args.sides}, Theta={theta_arg}, Rotation={args.rotation}°, Blades={args.blades or viz.n_blades}")

    viz.plot(
        q_ratio=args.q,
        n_sides=args.sides,
        theta=theta_arg,
        rotation_deg=args.rotation,
        spacing=args.spacing,
        n_blades=args.blades,
        show_blades=not args.no_blades,
        save_path=args.save,
        show=not args.no_show,
    )


if __name__ == "__main__":
    main()