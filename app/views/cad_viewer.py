"""
Manage CAD – Parametric 2D schematic of the Morphogenerator device.

Draws an interactive, parametric visualisation of a circular chamber with
N radial channels and petal-shaped flow regions whose size is governed by Q.
A side panel shows the corresponding COMSOL streamline image.
"""

import math
import customtkinter
import numpy as np
from PIL import Image, ImageTk

import matplotlib
matplotlib.use("Agg")                                    # headless backend
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import (
    Circle, Wedge, FancyBboxPatch, PathPatch,
)
from matplotlib.path import Path as MplPath

from app.theme import (
    COLORS, FONTS, PAD_SM, PAD_MD, PAD_LG, CORNER_RADIUS, apply_mpl_theme, get_color
)
from app.core.image_loader import streamline_image_path


# Constants

_CHAMBER_RADIUS = 3.0          # mm – outer chamber
_INLET_RADIUS   = 0.45         # mm – central inlet
_CHANNEL_HALF_W = 0.18         # mm – half-width of a radial channel
# These will be fetched dynamically via get_color() where needed for matplotlib


# Helper: build a petal patch between two adjacent channels

def _petal_path(theta_start: float, theta_end: float, Q: float,
                r_inner: float, r_outer: float, pts: int = 80):
    """Return a matplotlib Path for a single petal region.

    The petal is bounded by:
    • an inner arc at *r_inner*
    • an outer arc whose radius modulates with Q (larger Q → bigger petal)
    • two straight channel walls at *theta_start* and *theta_end*
    """
    # Petal "bulge" radius scales with Q
    r_bulge = r_inner + (r_outer - r_inner) * Q * 0.92

    theta_mid = (theta_start + theta_end) / 2
    d_theta   = (theta_end - theta_start) / 2

    # Outer boundary: a smooth cosine-modulated curve
    angles_out = np.linspace(theta_start, theta_end, pts)
    r_out = np.empty_like(angles_out)
    for i, a in enumerate(angles_out):
        frac = (a - theta_start) / (theta_end - theta_start)  # 0→1
        # bell-shaped bulge (cosine)
        bulge = 0.5 * (1 - math.cos(2 * math.pi * frac))
        r_out[i] = r_inner + (r_bulge - r_inner) * bulge

    # Inner boundary (simple arc at r_inner)
    angles_in = np.linspace(theta_end, theta_start, pts)

    # Build path vertices
    verts = []
    codes = []

    # Outer arc  (forward)
    for i, (a, r) in enumerate(zip(angles_out, r_out)):
        verts.append((r * math.cos(a), r * math.sin(a)))
        codes.append(MplPath.LINETO if i else MplPath.MOVETO)

    # Inner arc  (reverse)
    for a in angles_in:
        verts.append((r_inner * math.cos(a), r_inner * math.sin(a)))
        codes.append(MplPath.LINETO)

    verts.append(verts[0])
    codes.append(MplPath.CLOSEPOLY)

    return MplPath(verts, codes)


# Main View

class CADViewerView(customtkinter.CTkFrame):
    """'Manage CAD' panel – parametric 2D device schematic + streamline image."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color=COLORS["bg_primary"])

        # State
        self._N = 4
        self._Q = 0.50

        # Controls bar (top)
        ctrl = customtkinter.CTkFrame(self, fg_color=COLORS["bg_secondary"],
                                      corner_radius=CORNER_RADIUS)
        ctrl.pack(fill="x", padx=PAD_LG, pady=(PAD_LG, PAD_SM))

        # N slider
        customtkinter.CTkLabel(
            ctrl, text="Channels  N", font=FONTS["subheading"],
            text_color=COLORS["text_primary"],
        ).pack(side="left", padx=(PAD_LG, PAD_SM), pady=PAD_MD)

        self._n_label = customtkinter.CTkLabel(
            ctrl, text=str(self._N), font=FONTS["mono"],
            text_color=COLORS["accent"], width=28,
        )
        self._n_label.pack(side="left", padx=(0, PAD_SM))

        self._n_slider = customtkinter.CTkSlider(
            ctrl, from_=2, to=6, number_of_steps=4, width=160,
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            progress_color=COLORS["accent"],
            fg_color=COLORS["bg_tertiary"],
            command=self._on_n_change,
        )
        self._n_slider.set(self._N)
        self._n_slider.pack(side="left", padx=(0, PAD_LG), pady=PAD_MD)

        # Separator
        sep = customtkinter.CTkFrame(ctrl, width=1, fg_color=COLORS["separator"])
        sep.pack(side="left", fill="y", padx=PAD_SM, pady=PAD_SM)

        # Q slider
        customtkinter.CTkLabel(
            ctrl, text="Flow ratio  Q", font=FONTS["subheading"],
            text_color=COLORS["text_primary"],
        ).pack(side="left", padx=(PAD_LG, PAD_SM), pady=PAD_MD)

        self._q_label = customtkinter.CTkLabel(
            ctrl, text=f"{self._Q:.2f}", font=FONTS["mono"],
            text_color=COLORS["accent"], width=44,
        )
        self._q_label.pack(side="left", padx=(0, PAD_SM))

        self._q_slider = customtkinter.CTkSlider(
            ctrl, from_=0.05, to=0.95, number_of_steps=18, width=220,
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            progress_color=COLORS["accent"],
            fg_color=COLORS["bg_tertiary"],
            command=self._on_q_change,
        )
        self._q_slider.set(self._Q)
        self._q_slider.pack(side="left", padx=(0, PAD_LG), pady=PAD_MD)

        # Content area (bottom): two panels side-by-side
        content = customtkinter.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=PAD_LG,
                     pady=(PAD_SM, PAD_LG))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        # Left: matplotlib CAD
        cad_frame = customtkinter.CTkFrame(
            content, fg_color=COLORS["bg_secondary"],
            corner_radius=CORNER_RADIUS,
        )
        cad_frame.grid(row=0, column=0, sticky="nsew",
                       padx=(0, PAD_SM // 2), pady=0)

        customtkinter.CTkLabel(
            cad_frame, text="Parametric Schematic",
            font=FONTS["subheading"], text_color=COLORS["text_secondary"],
        ).pack(pady=(PAD_MD, 0))

        apply_mpl_theme()
        self._fig, self._ax = plt.subplots(figsize=(4.6, 4.6), dpi=100)
        self._fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
        self.mpl_canvas = FigureCanvasTkAgg(self._fig, master=cad_frame)
        self.mpl_canvas.get_tk_widget().pack(fill="both", expand=True,
                                          padx=PAD_SM, pady=(PAD_SM, PAD_MD))

        # Right: streamline image
        img_frame = customtkinter.CTkFrame(
            content, fg_color=COLORS["bg_secondary"],
            corner_radius=CORNER_RADIUS,
        )
        img_frame.grid(row=0, column=1, sticky="nsew",
                       padx=(PAD_SM // 2, 0), pady=0)

        customtkinter.CTkLabel(
            img_frame, text="COMSOL Streamline",
            font=FONTS["subheading"], text_color=COLORS["text_secondary"],
        ).pack(pady=(PAD_MD, 0))

        self._img_label = customtkinter.CTkLabel(img_frame, text="",
                                                  fg_color="transparent")
        self._img_label.pack(fill="both", expand=True,
                             padx=PAD_SM, pady=(PAD_SM, PAD_MD))

        self._photo_ref = None  # prevent GC

        # Initial draw
        self._redraw()

    # Slider callbacks

    def _on_n_change(self, value):
        n = int(round(value))
        if n != self._N:
            self._N = n
            self._n_label.configure(text=str(n))
            self._redraw()

    def _on_q_change(self, value):
        q = round(value, 2)
        # snap to 0.05 steps
        q = round(round(q / 0.05) * 0.05, 2)
        if q != self._Q:
            self._Q = q
            self._q_label.configure(text=f"{q:.2f}")
            self._redraw()

    # Drawing

    def _redraw(self):
        """Redraw both the parametric CAD and the streamline image."""
        self._draw_cad()
        self._load_streamline()

    def _draw_cad(self):
        ax = self._ax
        ax.clear()

        N = self._N
        Q = self._Q
        R = _CHAMBER_RADIUS
        R_in = _INLET_RADIUS
        hw = _CHANNEL_HALF_W

        # Background – outer chamber fill
        chamber = Circle((0, 0), R, fc=get_color("bg_secondary"), ec=get_color("border"),
                         lw=1.2, zorder=0)
        ax.add_patch(chamber)

        # Petal regions
        angle_step = 2 * math.pi / N
        for i in range(N):
            theta_start = i * angle_step + hw / R_in
            theta_end   = (i + 1) * angle_step - hw / R_in
            path = _petal_path(theta_start, theta_end, Q, R_in, R)
            patch = PathPatch(path, fc=get_color("accent"), ec="none",
                              alpha=0.55 + 0.35 * Q, zorder=2)
            ax.add_patch(patch)

        # Radial channel walls (thin wedges)
        for i in range(N):
            angle_deg = math.degrees(i * angle_step)
            wedge = Wedge(
                (0, 0), R, angle_deg - math.degrees(hw / R_in),
                angle_deg + math.degrees(hw / R_in),
                width=R - R_in, fc=get_color("bg_tertiary"), ec=get_color("border"),
                lw=0.8, zorder=13,
            )
            ax.add_patch(wedge)

        # Central inlet
        inlet = Circle((0, 0), R_in, fc=get_color("accent"), ec=get_color("border"),
                       lw=0.8, zorder=2)
        ax.add_patch(inlet)

        # Dimensional labels
        label_kw = dict(fontsize=8, color=get_color("text_secondary"), ha="center",
                        va="center", zorder=10,
                        bbox=dict(boxstyle="round,pad=0.15",
                                  fc=get_color("bg_primary"), ec="none",
                                  alpha=0.85))

        # Outer radius
        ax.annotate(
            "", xy=(R, 0), xytext=(0, 0),
            arrowprops=dict(arrowstyle="<->", color=get_color("text_secondary"), lw=0.8),
            zorder=9,
        )
        ax.text(R / 2, -0.35, f"R = {R} mm", **label_kw)

        # Inlet radius
        ax.text(0, R_in + 0.35, f"r = {R_in} mm", fontsize=7,
                color=get_color("text_secondary"), ha="center", va="center", zorder=10,
                bbox=dict(boxstyle="round,pad=0.12",
                          fc=get_color("bg_primary"), ec="none", alpha=0.85))

        # N / Q readout
        ax.text(0, -R - 0.55, f"N = {N}    Q = {Q:.2f}",
                fontsize=9, color=get_color("text_primary"),
                ha="center", va="center", weight="bold", zorder=10)

        # Axes settings
        margin = R * 1.35
        ax.set_xlim(-margin, margin)
        ax.set_ylim(-margin, margin)
        ax.set_aspect("equal")
        ax.axis("off")

        self.mpl_canvas.draw_idle()

    def _load_streamline(self):
        """Load and display the COMSOL streamline image for current (N, Q)."""
        path = streamline_image_path(self._N, self._Q, view="central")

        if path is None:
            self._img_label.configure(
                image=None,
                text="No image available\nfor this configuration",
                font=FONTS["body"],
                text_color=COLORS["text_tertiary"],
            )
            self._photo_ref = None
            return

        try:
            pil_img = Image.open(path)
            # Resize to fit panel (max 440 px)
            pil_img.thumbnail((440, 440), Image.LANCZOS)
            photo = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
            self._img_label.configure(image=photo, text="")
            self._photo_ref = photo          # prevent garbage collection
        except Exception:
            self._img_label.configure(
                image=None,
                text="Error loading image",
                font=FONTS["body"],
                text_color=COLORS["error"],
            )
            self._photo_ref = None
