"""
coaxial_renderer.py
==============================
Visualization tool for the morphogenerator microfluidic system with COAXIAL FLUID injection.

Features:
- Simulates flow ratio Q and calculates the physical core radius R_Q at the inlet.
- Central core fluid is preserved in RED (CENTRAL_COLOR = #EF4444) for r <= R_Q.
- The peripheral space (R_Q < r <= R_inlet_max = 6.25 mm) represents COAXIAL FLUIDS:
    * Supports 2 coaxial streams (default: Inner Blue and Outer Orange) or N coaxial layers.
    * Color options:
        1. 'alternating': Alternates between 2 colors (e.g. Blue and Orange, or custom 2 colors).
        2. 'distinct': Each coaxial layer has a distinct, contrasting color from the vibrant palette.
        3. Custom user sequence: Specify exact colors in sequence for each layer via --colors.
    * Partitioning modes: 'equal_area' (default, equal flow/cross-sectional area),
      'equal_width' (equal radial thickness), or custom split radius R_split.
- Top view morphogen (inlet view) displays directly the input streamline coordinates without blade overlays,
  distribution chamber circles (R=12.5), or outer peripheral inlet holes.
- Outlet plane displays the resulting radial-swirl morphogenetic pattern at the nozzle.
"""

from __future__ import annotations

import argparse
import math
import os
import io
import re
from PIL import Image as PILImage
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Arc, Circle, Wedge
from matplotlib.lines import Line2D
import numpy as np

try:
    from app.core.flow_sync import DataProcessor, get_synced_streamlines, _find_cache_file
except ImportError:
    from flow_sync import DataProcessor, get_synced_streamlines, _find_cache_file

import sys
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Color palette for distinct radial concentric rings (vibrant, high contrast)
RADIAL_PALETTE = [
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
    "#3F51B5",  # 11. Indigo
    "#8D6E63",  # 12. Cocoa Brown
    "#78909C",  # 13. Blue Grey
    "#FDD835",  # 14. Canary Yellow
    "#4ADE80",  # 15. Bright Emerald
]

COAXIAL_COLOR_INNER = "#2563EB"    # Inner Coaxial Fluid (Vibrant Blue)
COAXIAL_COLOR_OUTER = "#F59E0B"    # Outer Coaxial Fluid (Warm Amber/Orange)
CENTRAL_COLOR = "#EF4444"          # Central Fluid Core (Red)
UNASSIGNED_COLOR = "#B0BEC5"       # Unassigned / background region (Light Grey)
WALL_COLOR = "#111827"             # Chamber / nozzle walls
BLADE_DOWN_COLOR = "#2563EB"       # Blade down indicator (Vibrant Blue)
BLADE_UP_COLOR = "#D97706"         # Blade up indicator (Warm Amber/Orange)


def genera_blades(n_blades: int) -> List[dict]:
    """Generate alternating up/down blade configurations.

    Args:
        n_blades: Total number of blade pairs (down + up).
                  Produces 2 * n_blades sectors of angular width 360 / (2 * n_blades).
    """
    if n_blades <= 0:
        return []

    step = 360.0 / (2 * n_blades)
    blades = []

    for k in range(2 * n_blades):
        start = k * step
        end = (k + 1) * step
        tipo = "down" if (k % 2 == 0) else "up"
        blades.append(
            {
                "index": k,
                "start_deg": start,
                "end_deg": end,
                "tipo": tipo,
            }
        )

    return blades


def calculate_physical_radius(q_ratio: float, r_total: float = 6.25) -> float:
    """Calculate the physical inner core radius (r_Q) enclosing a given flow ratio Q.

    Formula derived from parabolic/Poiseuille flow integration:
    r_Q = r_total * sqrt(1 - sqrt(1 - Q))
    """
    if not (0.0 <= q_ratio <= 1.0):
        raise ValueError(f"Flow ratio Q must be between 0.0 and 1.0, got: {q_ratio}")

    radial_fraction = math.sqrt(1.0 - math.sqrt(1.0 - q_ratio))
    return r_total * radial_fraction


class CoaxialLayer:
    """Represents a concentric coaxial fluid layer (annulus) in the peripheral region."""

    def __init__(self, index: int, r_inner: float, r_outer: float, color: str, name: Optional[str] = None):
        self.index = index
        self.r_inner = float(r_inner)
        self.r_outer = float(r_outer)
        self.color = color
        self.name = name or f"Peripheral {index + 1}"

    def contains(self, r: np.ndarray, is_outermost: bool = False) -> np.ndarray:
        """Check if radii r fall within this coaxial layer [r_inner, r_outer)."""
        if is_outermost:
            return (r >= self.r_inner) & (r <= self.r_outer + 1e-9)
        return (r >= self.r_inner) & (r < self.r_outer)

    def __repr__(self) -> str:
        return f"{self.name} [r={self.r_inner:.2f}mm - {self.r_outer:.2f}mm, Δr={self.r_outer - self.r_inner:.2f}mm]"


def resolve_layer_colors(
    n_layers: int,
    color_mode: str = "alternating",
    colors: Optional[Sequence[str]] = None,
) -> List[str]:
    """Resolve the list of colors for n_layers based on color_mode and user colors list.

    Modes:
    - 'alternating': Alternates between two colors (e.g. Blue & Orange, or the two colors in `colors`).
    - 'distinct': Each layer gets a distinct color from RADIAL_PALETTE (or `colors`).
    If custom `colors` are provided:
    - If len(colors) >= n_layers: uses the exact sequence given by the user.
    - If len(colors) < n_layers:
        * In alternating mode, cycles through the given colors.
        * In distinct mode, fills remaining with RADIAL_PALETTE.
    """
    if colors is not None and len(colors) > 0:
        resolved_user: List[str] = []
        for c in colors:
            try:
                resolved_user.append(mcolors.to_hex(c))
            except ValueError:
                resolved_user.append(c)

        if len(resolved_user) >= n_layers:
            return resolved_user[:n_layers]
        elif color_mode == "alternating":
            return [resolved_user[i % len(resolved_user)] for i in range(n_layers)]
        else:
            # distinct mode with fewer custom colors: fill remainder from RADIAL_PALETTE
            out = list(resolved_user)
            pal_idx = 0
            while len(out) < n_layers:
                candidate = RADIAL_PALETTE[pal_idx % len(RADIAL_PALETTE)]
                if candidate not in out:
                    out.append(candidate)
                pal_idx += 1
            return out[:n_layers]

    # No custom colors provided
    if color_mode == "distinct":
        return [RADIAL_PALETTE[i % len(RADIAL_PALETTE)] for i in range(n_layers)]
    else:
        # alternating mode
        return [COAXIAL_COLOR_INNER if (i % 2 == 0) else COAXIAL_COLOR_OUTER for i in range(n_layers)]


def build_coaxial_layers(
    r_inner_bound: float,
    r_outer_bound: float = 6.25,
    n_layers: int = 2,
    mode: str = "equal_area",
    r_split: Optional[float] = None,
    custom_radii: Optional[Sequence[float]] = None,
    color_mode: str = "alternating",
    colors: Optional[Sequence[str]] = None,
) -> List[CoaxialLayer]:
    """Build a list of CoaxialLayer objects between r_inner_bound (R_Q) and r_outer_bound (6.25 mm).

    Args:
        r_inner_bound: Inner radius of peripheral coaxial zone (typically R_Q).
        r_outer_bound: Outer radius of inlet chamber (typically 6.25 mm).
        n_layers: Number of coaxial layers (default: 2, Inner and Outer).
        mode: Division method:
              - 'equal_area': Equal annular cross-sectional area per coaxial stream.
              - 'equal_width': Equal radial thickness.
        r_split: Optional explicit split radius between inner and outer coaxial fluid (for n_layers=2).
        custom_radii: Optional explicit list of intermediate boundary radii.
        color_mode: 'alternating' (default) or 'distinct' (all colors different).
        colors: Optional user-defined list of colors in sequence.
    """
    if r_inner_bound >= r_outer_bound - 1e-6:
        return []

    # 1. Custom radii list provided
    if custom_radii is not None and len(custom_radii) > 0:
        boundaries = [r_inner_bound] + [r for r in custom_radii if r_inner_bound < r < r_outer_bound] + [r_outer_bound]
        boundaries = sorted(list(set(boundaries)))
        actual_layers = len(boundaries) - 1
        layer_colors = resolve_layer_colors(actual_layers, color_mode=color_mode, colors=colors)
        layers: List[CoaxialLayer] = []
        for i in range(actual_layers):
            r_in = boundaries[i]
            r_out = boundaries[i + 1]
            color = layer_colors[i]
            name = f"Peripheral {i + 1}"
            layers.append(CoaxialLayer(i, r_in, r_out, color, name=name))
        return layers

    # 2. Standard 2-fluid coaxial system (Inner and Outer coaxial fluid)
    if n_layers == 2:
        if r_split is not None and r_inner_bound < r_split < r_outer_bound:
            split = float(r_split)
        elif mode == "equal_width":
            split = (r_inner_bound + r_outer_bound) / 2.0
        else:
            # Default: equal_area split
            split = math.sqrt(0.5 * (r_inner_bound**2 + r_outer_bound**2))

        layer_colors = resolve_layer_colors(2, color_mode=color_mode, colors=colors)
        layers = [
            CoaxialLayer(0, r_inner_bound, split, layer_colors[0], name="Peripheral 1 (Inner)"),
            CoaxialLayer(1, split, r_outer_bound, layer_colors[1], name="Peripheral 2 (Outer)"),
        ]
        return layers

    # 3. N coaxial layers (n_layers > 2)
    actual_layers = max(1, n_layers)
    layer_colors = resolve_layer_colors(actual_layers, color_mode=color_mode, colors=colors)
    layers = []

    if mode == "equal_area":
        r_sq_in = r_inner_bound ** 2
        r_sq_out = r_outer_bound ** 2
        step_sq = (r_sq_out - r_sq_in) / actual_layers
        for i in range(actual_layers):
            r_in = math.sqrt(r_sq_in + i * step_sq)
            r_out = math.sqrt(r_sq_in + (i + 1) * step_sq)
            color = layer_colors[i]
            name = f"Peripheral {i + 1}"
            layers.append(CoaxialLayer(i, r_in, r_out, color, name=name))
    else:
        # equal_width
        dr = (r_outer_bound - r_inner_bound) / actual_layers
        for i in range(actual_layers):
            r_in = r_inner_bound + i * dr
            r_out = r_inner_bound + (i + 1) * dr
            color = layer_colors[i]
            name = f"Peripheral {i + 1}"
            layers.append(CoaxialLayer(i, r_in, r_out, color, name=name))

    return layers


class MorphoVisualizerRadially:
    """Class to load and visualize streamlines with COAXIAL FLUID distribution."""

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

        # Auto-detect number of blades from filename for metadata
        match = re.search(r'N(\d+)', Path(self.filepath).name)
        self.n_blades = int(match.group(1)) if match else 4

        # Load once and store in memory (uses persistent cache)
        self.processor = DataProcessor(self.filepath, z_bottom_target=z_bottom, z_inlet_target=z_inlet)
        self.inlet_coords, self.bottom_coords, self.sync_ids = self.processor.get_synced_coords(
            r_inlet_max=r_inlet_max,
            r_bottom_max=r_bottom_max,
        )

        self.z_inlet = self.processor.z_inlet_target
        self.z_bottom = self.processor.z_bottom_target
        self.r_bottom = self.processor.r_bottom_detected or r_bottom_max
        self.n_points = len(self.inlet_coords)

        # Pre-compute polar radii at inlet
        self.inlet_r = np.sqrt(self.inlet_coords[:, 0] ** 2 + self.inlet_coords[:, 1] ** 2)

    def classify_streamlines(
        self,
        q_ratio: float,
        n_layers: int = 2,
        mode: str = "equal_area",
        r_split: Optional[float] = None,
        custom_radii: Optional[Sequence[float]] = None,
        color_mode: str = "alternating",
        colors: Optional[Sequence[str]] = None,
    ) -> Tuple[np.ndarray, List[CoaxialLayer], float]:
        """Classify each streamline into Central (0), Coaxial Layer k (k+1), or Unassigned (-1).

        Returns:
            Tuple[np.ndarray, List[CoaxialLayer], float]:
                - labels: integer array of shape (N,) indicating zone assignment
                - layers: list of configured CoaxialLayer objects
                - r_q: the computed physical core radius (in mm)
        """
        r_q = calculate_physical_radius(q_ratio, r_total=self.r_inlet_max)
        layers = build_coaxial_layers(
            r_inner_bound=r_q,
            r_outer_bound=self.r_inlet_max,
            n_layers=n_layers,
            mode=mode,
            r_split=r_split,
            custom_radii=custom_radii,
            color_mode=color_mode,
            colors=colors,
        )

        labels = np.full(self.n_points, -1, dtype=int)

        # Central core points (r <= r_q) -> always RED (label 0)
        is_central = self.inlet_r <= r_q
        labels[is_central] = 0

        # Peripheral coaxial points (r_q < r <= r_inlet_max)
        for i, layer in enumerate(layers):
            is_outermost = (i == len(layers) - 1)
            mask_in_layer = layer.contains(self.inlet_r, is_outermost=is_outermost) & (~is_central)
            labels[mask_in_layer] = layer.index + 1

        return labels, layers, r_q

    def plot(
        self,
        q_ratio: float = 0.4,
        n_layers: int = 2,
        mode: str = "equal_area",
        r_split: Optional[float] = None,
        custom_radii: Optional[Sequence[float]] = None,
        color_mode: str = "alternating",
        colors: Optional[Sequence[str]] = None,
        top_view: str = "streamlines",
        point_size: float = 1.0,
        alpha: float = 0.70,
        figsize: Tuple[float, float] = (13.5, 6.5),
        save_path: Optional[Union[str, Path]] = None,
        show: bool = True,
    ) -> Tuple[plt.Figure, Tuple[plt.Axes, plt.Axes]]:
        """Generate and display/save the side-by-side Top View (Inlet) and Nozzle View (Outlet).

        Top View display mode is chosen via `top_view`:
        - 'streamlines' (default): Pure initial conditions before blades (streamline scatter without blade/chamber overlays).
        - 'morphogenerator': Physical device top view with blades, central inlet tube, and lateral peripheral inlets as shown in device cross-section.
        """
        labels, layers, r_q = self.classify_streamlines(
            q_ratio=q_ratio,
            n_layers=n_layers,
            mode=mode,
            r_split=r_split,
            custom_radii=custom_radii,
            color_mode=color_mode,
            colors=colors,
        )

        fig, (ax_inlet, ax_outlet) = plt.subplots(1, 2, figsize=figsize)
        is_morpho_device = str(top_view).lower() in ("morphogenerator", "device", "inlets", "blades")

        # --- LEFT PLOT: TOP VIEW (STREAMLINES OR MORPHOGENERATOR DEVICE) ---
        mask_unassigned = labels == -1
        mask_central = labels == 0
        cnt_central = np.sum(mask_central)
        pct_central = (cnt_central / self.n_points) * 100.0 if self.n_points > 0 else 0.0 #! percentage area occupied by central fluid in top view, you can add it on legend by {pct_central:.1f}%",

        if not is_morpho_device:
            # === MODE A: CLEAN STREAMLINE CONDITIONS BEFORE BLADES ===
            if np.any(mask_unassigned):
                ax_inlet.scatter(
                    self.inlet_coords[mask_unassigned, 0],
                    self.inlet_coords[mask_unassigned, 1],
                    c=UNASSIGNED_COLOR,
                    s=point_size,
                    alpha=alpha * 0.4,
                    label=f"Unassigned ({np.sum(mask_unassigned)})",
                    rasterized=True,
                )

            # Coaxial layers for peripheral fluid
            for layer in layers:
                mask_layer = labels == (layer.index + 1)
                cnt = np.sum(mask_layer)
                pct = (cnt / self.n_points) * 100.0 if self.n_points > 0 else 0.0
                ax_inlet.scatter(
                    self.inlet_coords[mask_layer, 0],
                    self.inlet_coords[mask_layer, 1],
                    c=layer.color,
                    s=point_size,
                    alpha=alpha,
                    #label=f"{layer.name}: [{layer.r_inner:.2f}-{layer.r_outer:.2f} mm] ({pct:.1f}%)",
                    rasterized=True,
                )

            # Central core points (RED)
            ax_inlet.scatter(
                self.inlet_coords[mask_central, 0],
                self.inlet_coords[mask_central, 1],
                c=CENTRAL_COLOR,
                s=point_size,
                alpha=alpha,
                label=f"Central Fluid (Q={q_ratio:.2f})",
                rasterized=True,
            )

            core_circle = Circle(
                (0, 0),
                radius=r_q,
                edgecolor=CENTRAL_COLOR,
                fill=False,
                linestyle="-",
                linewidth=1.8,
                #label=f"Core Radius R_Q={r_q:.2f} mm",
            )
            ax_inlet.add_patch(core_circle)

            for layer in layers:
                r_circle = Circle(
                    (0, 0),
                    radius=layer.r_outer,
                    edgecolor=layer.color,
                    fill=False,
                    linestyle="--",
                    linewidth=1.0,
                    alpha=0.8,
                )
                ax_inlet.add_patch(r_circle)

            inlet_boundary = Circle(
                (0, 0),
                radius=self.r_inlet_max,
                edgecolor=WALL_COLOR,
                fill=False,
                linestyle="-",
                linewidth=1.5,
                #label=f"Blades chamber (R={self.r_inlet_max:.2f} mm)",
            )
            ax_inlet.add_patch(inlet_boundary)

            ax_inlet.set_title(
                f"Top View Streamline before blades\n"
                f"Q = {q_ratio:.2f} "
                #f"R_Q = {r_q:.2f} mm)"
                f" | Concentric Rings = {len(layers)}",
                fontsize=10,
                fontweight="bold",
            )
            lim_inlet = self.r_inlet_max * 1.15
            ax_inlet.set_xlim([-lim_inlet, lim_inlet])
            ax_inlet.set_ylim([-lim_inlet, lim_inlet])
            ax_inlet.set_aspect("equal")
            ax_inlet.grid(True, linestyle="--", alpha=0.4)
            ax_inlet.set_xlabel("X (mm)", fontsize=9)
            ax_inlet.set_ylabel("Y (mm)", fontsize=9)

        else:
            # === MODE B: TOP VIEW MORPHOGENERATOR WITH BLADES & LATERAL INLETS ===
            # 1. Central Inlet Tube (R = 2.5 mm in the center, SEMPRE TUTTO ROSSO)
            central_tube_radius = 2.5
            central_inlet = Circle(
                (0, 0),
                radius=central_tube_radius,
                edgecolor="red",
                facecolor=CENTRAL_COLOR,
                alpha = 0.7,
                linestyle="-",
                linewidth=1.6,
                zorder=5,
                label=f"Central inlet (R={central_tube_radius:.1f} mm)",
            )
            ax_inlet.add_patch(central_inlet)

            # 2. Inner Chamber Wall & Blades boundary (R = 6.25 mm)
            chamber_boundary = Circle(
                (0, 0),
                radius=self.r_inlet_max,
                edgecolor=WALL_COLOR,
                fill=False,
                linestyle="--",
                linewidth=1.4,
                #label=f"Blades chamber (R={self.r_inlet_max:.2f} mm)",
            )
            ax_inlet.add_patch(chamber_boundary)

            # 3. Blades overlays (alternating down / up) - Triangoli colorati dello stesso colore del bordo
            blades_list = genera_blades(self.n_blades)
            r_blade_inner = central_tube_radius
            for b in blades_list:
                is_down = "down" in b["tipo"]
                b_color = BLADE_DOWN_COLOR if is_down else BLADE_UP_COLOR
                b_ls = "-" if is_down else "--"

                # Blade wedge ("triangolo") filled with the same color as the border
                blade_wedge = Wedge(
                    (0, 0),
                    r=self.r_inlet_max,
                    theta1=b["start_deg"],
                    theta2=b["end_deg"],
                    width=self.r_inlet_max - r_blade_inner,
                    facecolor=mcolors.to_rgba(b_color, alpha=0.4),
                    edgecolor=b_color,
                    linewidth=1.6,
                    linestyle=b_ls,
                    zorder=3,
                )
                ax_inlet.add_patch(blade_wedge)

            # 4. Outer Distribution Chambers and LATERAL INLETS (from device CAD cross-section)
            # Raggio dei peripheral inlet uguale al raggio del central inlet (R = 2.5 mm)
            n_coax = len(layers)
            chamber_dr = 6.5
            r_outer_chamber = self.r_inlet_max + n_coax * chamber_dr

            # Annular chamber boundaries
            for i in range(1, n_coax):
                r_div = self.r_inlet_max + i * chamber_dr
                ch_div = Circle((0, 0), radius=r_div, edgecolor=WALL_COLOR, fill=False, linestyle=":", linewidth=1.1, alpha=0.7)
                ax_inlet.add_patch(ch_div)

            outer_wall = Circle((0, 0), radius=r_outer_chamber, edgecolor=WALL_COLOR, fill=False, linestyle="-", linewidth=1.6)
            ax_inlet.add_patch(outer_wall)

            # Lateral Inlets along +X axis (y = 0) with radius = central_tube_radius = 2.5 mm
            r_tube = central_tube_radius
            for i, layer in enumerate(layers):
                r_ch_in = self.r_inlet_max + i * chamber_dr
                r_ch_out = self.r_inlet_max + (i + 1) * chamber_dr
                r_center = (r_ch_in + r_ch_out) / 2.0

                fc = mcolors.to_rgba(layer.color, alpha=0.6)
                ec = layer.color

                short_name = "Peripheral" if (n_coax == 2 and i == 0) else ("External" if (n_coax == 2 and i == 1) else layer.name)
                name = f"{short_name} inlet"
                inlet_tube = Circle(
                    (r_center, 0.0),
                    radius=r_tube,
                    facecolor=fc,
                    edgecolor=ec,
                    linewidth=2.2,
                    linestyle="-",
                    zorder=6,
                    label=f"{name} (R={r_tube:.1f} mm)",
                )
                ax_inlet.add_patch(inlet_tube)

            ax_inlet.set_title(
                f"Top View Morphogenerator\n"
                f"Q = {q_ratio:.2f}  |  Blades = {self.n_blades*2} |  $N_{{peripheral}}$ = {len(layers)}",
                fontsize=10,
                fontweight="bold",
            )
            lim_inlet = r_outer_chamber * 1.15
            ax_inlet.set_xlim([-lim_inlet, lim_inlet])
            ax_inlet.set_ylim([-lim_inlet, lim_inlet])
            ax_inlet.set_aspect("equal")
            ax_inlet.grid(True, linestyle="--", alpha=0.35)
            ax_inlet.set_xlabel("X (mm)", fontsize=9)
            ax_inlet.set_ylabel("Y (mm)", fontsize=9)

        # --- RIGHT PLOT: OUTLET PLANE (NOZZLE) ---
        if np.any(mask_unassigned):
            ax_outlet.scatter(
                self.bottom_coords[mask_unassigned, 0],
                self.bottom_coords[mask_unassigned, 1],
                c=UNASSIGNED_COLOR,
                s=point_size,
                alpha=alpha * 0.4,
                rasterized=True,
            )

        for layer in layers:
            mask_layer = labels == (layer.index + 1)
            cnt = np.sum(mask_layer)
            pct = (cnt / self.n_points) * 100.0 if self.n_points > 0 else 0.0
            ax_outlet.scatter(
                self.bottom_coords[mask_layer, 0],
                self.bottom_coords[mask_layer, 1],
                c=layer.color,
                s=point_size,
                alpha=alpha,
                #label=f"{layer.name}: [{layer.r_inner:.2f}-{layer.r_outer:.2f} mm] ({pct:.1f}%)",
                rasterized=True,
            )

        ax_outlet.scatter(
            self.bottom_coords[mask_central, 0],
            self.bottom_coords[mask_central, 1],
            c=CENTRAL_COLOR,
            s=point_size,
            alpha=alpha,
            #label=f"Central Fluid: [0.00-{r_q:.2f} mm] ({pct_central:.1f}%)",
            rasterized=True,
        )

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
            f"Outlet Plane (Nozzle, z = {self.z_bottom:.2f} mm)\n",
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

        # --- UNIFIED LEGEND: IN BASSO E AL CENTRO TRA LE 2 IMMAGINI ---
        handles_in, labels_in = ax_inlet.get_legend_handles_labels()
        handles_out, labels_out = ax_outlet.get_legend_handles_labels()

        if is_morpho_device:
            handles_in.append(Line2D([0], [0], color=BLADE_DOWN_COLOR, lw=2.5, linestyle="-", label="Blade down"))
            handles_in.append(Line2D([0], [0], color=BLADE_UP_COLOR, lw=2.5, linestyle="--", label="Blade up"))
            labels_in.append("Blade down")
            labels_in.append("Blade up")

        seen_labels = set()
        unified_handles = []
        unified_labels = []
        for h, l in zip(handles_in + handles_out, labels_in + labels_out):
            if l and l not in seen_labels and "coaxial" not in l.lower() and "central fluid" not in l.lower() and "peripheral" not in l.lower():
                seen_labels.add(l)
                unified_handles.append(h)
                unified_labels.append(l)

        n_items = len(unified_labels)
        ncol = min(n_items, 4 if n_items <= 8 else 5)
        fig.legend(
            handles=unified_handles,
            labels=unified_labels,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.015),
            ncol=ncol,
            fontsize=7.8,
            framealpha=0.9,
            edgecolor="#D1D5DB",
        )

        fig.suptitle(
            f"Radial Morphogenerator Visualization  |  {Path(self.filepath).name}\n",
            #f"Synced Streamlines: {self.n_points:,}  |  Rings: {len(layers)} ({mode})",
            fontsize=11,
            fontweight="bold",
            y=0.99,
        )
        plt.tight_layout(rect=[0, 0.09, 1, 0.95])

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

    def render_dual_pil(
        self,
        q_ratio: float = 0.4,
        n_layers: int = 2,
        mode: str = "equal_area",
        r_split: Optional[float] = None,
        custom_radii: Optional[Sequence[float]] = None,
        color_mode: str = "alternating",
        colors: Optional[Sequence[str]] = None,
        top_view: str = "streamlines",
        point_size: float = 1.0,
        alpha: float = 0.75,
        figsize: Tuple[float, float] = (9.2, 4.6),
        dpi: int = 110,
        bg_color: Optional[str] = None,
        show_nozzle_circle: bool = True,
        show_grid: bool = True,
        show_legend: bool = False,
    ) -> Tuple[PILImage.Image, List[CoaxialLayer], float]:
        """Render both Top View (Coaxial Inlet) and Outlet planes side-by-side as a PIL Image.

        Returns:
            Tuple of (pil_image, layers_list, r_q).
        """
        labels, layers, r_q = self.classify_streamlines(
            q_ratio=q_ratio,
            n_layers=n_layers,
            mode=mode,
            r_split=r_split,
            custom_radii=custom_radii,
            color_mode=color_mode,
            colors=colors,
        )

        fig, (ax_inlet, ax_outlet) = plt.subplots(1, 2, figsize=figsize, dpi=dpi)
        is_morpho_device = str(top_view).lower() in ("morphogenerator", "device", "inlets", "blades")

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

        # --- LEFT: TOP VIEW STREAMLINE BEFORE BLADES OR MORPHOGENERATOR ---
        mask_unassigned = labels == -1
        mask_central = labels == 0

        if not is_morpho_device:
            if np.any(mask_unassigned):
                ax_inlet.scatter(
                    self.inlet_coords[mask_unassigned, 0],
                    self.inlet_coords[mask_unassigned, 1],
                    c=UNASSIGNED_COLOR,
                    s=point_size,
                    alpha=alpha * 0.4,
                    rasterized=True,
                    label="Unassigned",
                )

            for layer in layers:
                mask_layer = labels == (layer.index + 1)
                ax_inlet.scatter(
                    self.inlet_coords[mask_layer, 0],
                    self.inlet_coords[mask_layer, 1],
                    c=layer.color,
                    s=point_size,
                    alpha=alpha,
                    rasterized=True,
                    label=layer.name,
                )

            ax_inlet.scatter(
                self.inlet_coords[mask_central, 0],
                self.inlet_coords[mask_central, 1],
                c=CENTRAL_COLOR,
                s=point_size,
                alpha=alpha,
                rasterized=True,
                label=f"Core (Q={q_ratio:.2f})",
            )

            # Core fluid boundary circle
            core_circle = Circle((0, 0), radius=r_q, edgecolor=CENTRAL_COLOR, fill=False, linestyle="-", linewidth=1.5)
            ax_inlet.add_patch(core_circle)

            # Concentric layer boundaries
            for layer in layers:
                r_circle = Circle(
                    (0, 0),
                    radius=layer.r_outer,
                    edgecolor=layer.color,
                    fill=False,
                    linestyle=":",
                    linewidth=1.0,
                    alpha=0.8,
                )
                ax_inlet.add_patch(r_circle)

            # Outer chamber boundary
            outer_circle = Circle(
                (0, 0),
                radius=self.r_inlet_max,
                edgecolor=WALL_COLOR,
                fill=False,
                linestyle="-",
                linewidth=1.2,
            )
            ax_inlet.add_patch(outer_circle)

            ax_inlet.set_title("Top View Streamline before blades", fontsize=10, fontweight="bold", color=text_color)
            lim_inlet = self.r_inlet_max * 1.15
        else:
            # Morphogenerator device view with blades and lateral inlets
            central_tube_radius = 2.5
            central_inlet = Circle(
                (0, 0),
                radius=central_tube_radius,
                edgecolor=WALL_COLOR,
                facecolor=CENTRAL_COLOR,
                linestyle="-",
                linewidth=1.5,
                zorder=5,
            )
            ax_inlet.add_patch(central_inlet)

            chamber_boundary = Circle(
                (0, 0),
                radius=self.r_inlet_max,
                edgecolor=WALL_COLOR,
                fill=False,
                linestyle="--",
                linewidth=1.2,
            )
            ax_inlet.add_patch(chamber_boundary)

            blades_list = genera_blades(self.n_blades)
            r_blade_inner = central_tube_radius
            for b in blades_list:
                is_down = "down" in b["tipo"]
                b_color = BLADE_DOWN_COLOR if is_down else BLADE_UP_COLOR
                b_ls = "-" if is_down else "--"
                blade_wedge = Wedge(
                    (0, 0),
                    r=self.r_inlet_max,
                    theta1=b["start_deg"],
                    theta2=b["end_deg"],
                    width=self.r_inlet_max - r_blade_inner,
                    facecolor=mcolors.to_rgba(b_color, alpha=0.55),
                    edgecolor=b_color,
                    linewidth=1.4,
                    linestyle=b_ls,
                    zorder=3,
                )
                ax_inlet.add_patch(blade_wedge)

            n_coax = len(layers)
            chamber_dr = 6.5
            r_outer_chamber = self.r_inlet_max + n_coax * chamber_dr
            for i in range(1, n_coax):
                r_div = self.r_inlet_max + i * chamber_dr
                ch_div = Circle((0, 0), radius=r_div, edgecolor=WALL_COLOR, fill=False, linestyle=":", linewidth=0.9, alpha=0.6)
                ax_inlet.add_patch(ch_div)

            outer_wall = Circle((0, 0), radius=r_outer_chamber, edgecolor=WALL_COLOR, fill=False, linestyle="-", linewidth=1.4)
            ax_inlet.add_patch(outer_wall)

            r_tube = central_tube_radius
            for i, layer in enumerate(layers):
                r_ch_in = self.r_inlet_max + i * chamber_dr
                r_ch_out = self.r_inlet_max + (i + 1) * chamber_dr
                r_center = (r_ch_in + r_ch_out) / 2.0

                inlet_tube = Circle(
                    (r_center, 0.0),
                    radius=r_tube,
                    facecolor=mcolors.to_rgba(layer.color, alpha=0.6),
                    edgecolor=layer.color,
                    linewidth=1.8,
                    zorder=6,
                )
                ax_inlet.add_patch(inlet_tube)

            ax_inlet.set_title("Top View Morphogenerator", fontsize=10, fontweight="bold", color=text_color)
            lim_inlet = r_outer_chamber * 1.15
        ax_inlet.set_xlabel("X (mm)", fontsize=8, color=text_color)
        ax_inlet.set_ylabel("Y (mm)", fontsize=8, color=text_color)
        ax_inlet.tick_params(colors=text_color, labelsize=7)
        ax_inlet.set_xlim([-lim_inlet, lim_inlet])
        ax_inlet.set_ylim([-lim_inlet, lim_inlet])
        ax_inlet.set_aspect("equal")
        if show_grid:
            ax_inlet.grid(True, linestyle="--", alpha=0.25, color=text_color)
        for spine in ax_inlet.spines.values():
            spine.set_color(spine_color)
            spine.set_linewidth(0.8)

        # --- RIGHT: OUTLET PLANE ---
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

        for layer in layers:
            mask_layer = labels == (layer.index + 1)
            ax_outlet.scatter(
                self.bottom_coords[mask_layer, 0],
                self.bottom_coords[mask_layer, 1],
                c=layer.color,
                s=point_size,
                alpha=alpha,
                rasterized=True,
                #label=layer.name,
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
        return PILImage.open(buf), layers, r_q

    def render_outlet_pil(
        self,
        q_ratio: float = 0.4,
        n_layers: int = 2,
        mode: str = "equal_area",
        r_split: Optional[float] = None,
        custom_radii: Optional[Sequence[float]] = None,
        color_mode: str = "alternating",
        colors: Optional[Sequence[str]] = None,
        point_size: float = 1.0,
        alpha: float = 0.75,
        figsize: Tuple[float, float] = (5.5, 5.5),
        dpi: int = 150,
        bg_color: Optional[str] = None,
        show_nozzle_circle: bool = True,
        show_grid: bool = True,
        show_legend: bool = True,
    ) -> PILImage.Image:
        """Render ONLY the Outlet plane as a PIL Image."""
        labels, layers, r_q = self.classify_streamlines(
            q_ratio=q_ratio,
            n_layers=n_layers,
            mode=mode,
            r_split=r_split,
            custom_radii=custom_radii,
            color_mode=color_mode,
            colors=colors,
        )

        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        if bg_color:
            fig.patch.set_facecolor(bg_color)
            ax.set_facecolor(bg_color)
        else:
            fig.patch.set_alpha(0.0)
            ax.set_facecolor("none")

        mask_unassigned = labels == -1
        mask_central = labels == 0

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

        for layer in layers:
            mask_layer = labels == (layer.index + 1)
            ax.scatter(
                self.bottom_coords[mask_layer, 0],
                self.bottom_coords[mask_layer, 1],
                c=layer.color,
                s=point_size,
                alpha=alpha,
                rasterized=True,
                label=layer.name,
            )

        ax.scatter(
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
            ax.add_patch(outlet_circle)

        ax.set_title("")
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
        f"M2_N{n}_er8.txt",
        f"M2_N{n}.txt",
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
    for name in candidates:
        virtual_cand = PROJECT_ROOT / ".cache" / name
        cache = _find_cache_file(virtual_cand)
        if cache is not None and cache.exists():
            return virtual_cand

    return None


_VISUALIZER_CACHE: dict[int, MorphoVisualizerRadially] = {}


def get_visualizer_for_n(n: int) -> Optional[MorphoVisualizerRadially]:
    """Get or create a cached MorphoVisualizerRadially instance for a given N."""
    if n in _VISUALIZER_CACHE:
        return _VISUALIZER_CACHE[n]
    filepath = resolve_streamline_file(n)
    if filepath is not None:
        viz = MorphoVisualizerRadially(filepath)
        _VISUALIZER_CACHE[n] = viz
        return viz
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Visualize morphogenerator streamline core and COAXIAL FLUID distribution."
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default="txt_to_image/streamline_without_Q/M2_N2.txt",
        help="Path to streamline simulation .txt file.",
    )
    parser.add_argument(
        "--q",
        "-q",
        type=float,
        default=0.4,
        help="Flow ratio Q in [0.0, 1.0] (default: 0.4).",
    )
    parser.add_argument(
        "--layers",
        "--rings",
        "-l",
        "-n",
        dest="layers",
        type=int,
        default=2,
        help="Number of coaxial fluid layers / concentric rings (default: 2).",
    )
    parser.add_argument(
        "--r-split",
        type=float,
        default=None,
        help="Explicit split radius between inner and outer coaxial fluid (in mm, e.g. --r-split 4.5).",
    )
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        choices=["equal_area", "equal_width"],
        default="equal_area",
        help="Coaxial layer partitioning mode: 'equal_area' (default) or 'equal_width'.",
    )
    parser.add_argument(
        "--color-mode",
        "-c",
        type=str,
        choices=["alternating", "distinct"],
        default="alternating",
        help="Color scheme: 'alternating' (alternates 2 colors) or 'distinct' (all colors different).",
    )
    parser.add_argument(
        "--colors",
        nargs="+",
        type=str,
        default=None,
        help="Custom sequence of colors for each layer (e.g. --colors blue orange green purple or hex '#2563EB' '#F59E0B').",
    )
    parser.add_argument(
        "--radii",
        nargs="+",
        type=float,
        default=None,
        help="Custom radial boundaries for coaxial layers (e.g. --radii 3.5 5.0).",
    )
    parser.add_argument(
        "--top-view",
        "--inlet-view",
        "-v",
        dest="top_view",
        type=str,
        choices=["streamlines", "morphogenerator", "initial", "device", "inlets"],
        default="streamlines",
        help="Top view visualization mode: 'streamlines' (initial conditions before blades) or 'morphogenerator' (device top view with blades and lateral inlets).",
    )
    parser.add_argument(
        "--show-blades",
        "--morpho-view",
        dest="morpho_view",
        action="store_true",
        help="Display the morphogenerator device top view with blades and lateral inlets.",
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Optional path to save output image (e.g. output/coaxial_morpho.png).",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not display interactive matplotlib window.",
    )

    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.exists():
        fallback = resolve_streamline_file(4) or resolve_streamline_file(6)
        if fallback is not None and fallback.exists():
            filepath = fallback
        else:
            raise FileNotFoundError(f"Streamline file not found: {args.file}")

    # If user provided a custom list of colors matching layers count, default mode is naturally sequence/distinct
    color_mode_to_use = args.color_mode
    if args.colors is not None and len(args.colors) > 0 and len(args.colors) == args.layers and args.color_mode == "alternating":
        color_mode_to_use = "distinct"

    top_view_mode = "morphogenerator" if args.morpho_view else args.top_view

    print(f"Loading streamline data from: {filepath}")
    viz = MorphoVisualizerRadially(filepath)
    print(f"Loaded {viz.n_points:,} synced streamlines successfully.")
    print(f"Generating coaxial visualization: Q={args.q}, Layers={args.layers}, Mode={args.mode}, ColorMode={color_mode_to_use}, TopView={top_view_mode}, Colors={args.colors}")

    viz.plot(
        q_ratio=args.q,
        n_layers=args.layers,
        mode=args.mode,
        r_split=args.r_split,
        custom_radii=args.radii,
        color_mode=color_mode_to_use,
        colors=args.colors,
        top_view=top_view_mode,
        save_path=args.save,
        show=not args.no_show,
    )


if __name__ == "__main__":
    main()

# Architectural aliases
CoaxialRenderer = MorphoVisualizerRadially
get_coaxial_renderer_for_n = get_visualizer_for_n
