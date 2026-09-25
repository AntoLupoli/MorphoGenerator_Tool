"""
Select Parameters – Calculate / Find Parameters view.

• Calculate:       Choose (N, Q) → display all output metrics in styled cards
                   alongside the corresponding streamline image.
• Find Parameters: Choose a target metric + value → find (N, Q) pairs that
                   match within a tolerance band, shown as a sorted table.
"""

import sys
from pathlib import Path
from typing import Optional, List, Union, Tuple
_TOOL_ROOT = Path(__file__).resolve().parents[2]
if str(_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(_TOOL_ROOT))

import customtkinter
from PIL import Image, ImageTk

from app.theme import (
    COLORS, FONTS, MONO_FAMILY as _MONO_FAMILY,
    PAD_SM, PAD_MD, PAD_LG, CORNER_RADIUS,
    get_line_sample_icon,
)
from app.core.solver import forward, inverse, parametric_sweep
from app.core import correlations
from app.core.image_loader import streamline_image_path
import app.i18n as i18n
from morpho_visualizer import (
    get_visualizer_for_n,
    calculate_physical_radius,
    CENTRAL_COLOR,
    BLADE_DOWN_COLOR,
    BLADE_UP_COLOR,
    WALL_COLOR,
)


# Main View

class ParametersView(customtkinter.CTkFrame):
    """'Select Parameters' panel with Calculate / Find Parameters modes."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color=COLORS["bg_primary"])

        self._photo_ref_central = None  # prevent GC for central PNG
        self._photo_ref_side = None     # prevent GC for side PNG
        self._photo_ref_dual = None     # prevent GC for dynamic dual visualization
        self._current_dual_pil = None   # raw PIL image for responsive resizing
        self._img_resize_timer = None   # debounce timer for configure resize
        self._panel_left_width = 320    # default left panel width (cards/legend)
        self._is_dragging_splitter = False
        self._drag_start_x = 0
        self._drag_start_w = 320
        self._rot_debounce_id = None    # timer ID for debounced slider update
        self._legend_frame = None       # reference to sectors legend frame under DSI cards
        self._legend_sector_labels = [] # references to sector labels in legend for in-place updates
        self._legend_core_label = None  # reference to core label in legend
        self._fwd_legend_start_row = 10 # row index under result cards for legend

        # Auto-rotation state
        self._is_autorotating = False
        self._autorot_timer_id = None
        self._in_autorot_step = False
        self._side_n_var = customtkinter.StringVar(value="2")

        # Mode selector (top)
        top_bar = customtkinter.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=PAD_LG, pady=(PAD_LG, PAD_SM))

        self._mode_btn = customtkinter.CTkSegmentedButton(
            top_bar,
            values=["Calculate", "Find Parameters"],
            command=self._on_mode_change,
            font=FONTS["subheading"],
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["bg_tertiary"],
            unselected_hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            text_color_disabled=COLORS["text_tertiary"],
            corner_radius=CORNER_RADIUS,
        )
        self._mode_btn.set("Calculate")
        self._mode_btn.pack(side="left")

        btn_help = customtkinter.CTkButton(
            top_bar, text=i18n.t("btn_help"), font=FONTS["body"],
            fg_color=COLORS["bg_tertiary"], hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"], width=80,
            command=self._show_info_modal
        )
        btn_help.pack(side="right")

        # Dynamic subtitle (description of the active mode)
        self._MODE_DESCS = {
            "Calculate":       "Select N and Q to compute all output metrics.",
            "Find Parameters": "Specify a target metric and value to find matching (N, Q) pairs.",
        }
        self._subtitle_label = customtkinter.CTkLabel(
            self,
            text=self._MODE_DESCS["Calculate"],
            font=FONTS["body"],
            text_color=COLORS["text_tertiary"],
            anchor="w",
        )
        self._subtitle_label.pack(fill="x", padx=PAD_LG, pady=(0, PAD_SM))

        # Container that swaps between calculate / find parameters
        self._container = customtkinter.CTkFrame(self, fg_color="transparent")
        self._container.pack(fill="both", expand=True,
                             padx=PAD_LG, pady=(0, PAD_LG))

        # Build both panels (only one visible at a time)
        self._fwd_frame = self._build_forward_panel(self._container)
        self._inv_frame = self._build_inverse_panel(self._container)

        # Show Calculate panel by default
        self._fwd_frame.pack(fill="both", expand=True)
        self.after(100, self._on_fwd_calculate)

    # ══════════════════════════════════════════════════════════════════════
    #  MODE SWITCH
    # ══════════════════════════════════════════════════════════════════════

    def _on_mode_change(self, mode: str):
        self._stop_autorotation()
        self._subtitle_label.configure(text=self._MODE_DESCS.get(mode, ""))
        if mode == "Calculate":
            self._inv_frame.pack_forget()
            self._fwd_frame.pack(fill="both", expand=True)
        else:
            self._fwd_frame.pack_forget()
            self._inv_frame.pack(fill="both", expand=True)

    def destroy(self):
        self._stop_autorotation()
        super().destroy()

    # ══════════════════════════════════════════════════════════════════════
    #  FORWARD MODE
    # ══════════════════════════════════════════════════════════════════════

    def _build_forward_panel(self, parent) -> customtkinter.CTkFrame:
        frame = customtkinter.CTkFrame(parent, fg_color="transparent")

        # Input controls bar
        ctrl = customtkinter.CTkFrame(frame, fg_color=COLORS["bg_secondary"],
                                      corner_radius=CORNER_RADIUS)
        ctrl.pack(fill="x", pady=(0, PAD_MD))

        # N dropdown
        customtkinter.CTkLabel(
            ctrl, text="N", font=FONTS["subheading"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=0, padx=(PAD_LG, PAD_SM), pady=(PAD_MD, 2),
               sticky="w")

        self._fwd_n_var = customtkinter.StringVar(value="4")
        customtkinter.CTkOptionMenu(
            ctrl,
            variable=self._fwd_n_var,
            values=[str(n) for n in correlations.VALID_N],
            font=FONTS["body"],
            dropdown_font=FONTS["body"],
            fg_color=COLORS["bg_tertiary"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"],
            width=80,
            command=lambda _: self._on_fwd_calculate(),
        ).grid(row=0, column=1, padx=(0, PAD_LG), pady=(PAD_MD, 2))

        # N info label
        customtkinter.CTkLabel(
            ctrl, text="number of blades",
            font=FONTS["caption"],
            text_color=COLORS["text_secondary"],
        ).grid(row=1, column=0, columnspan=2, padx=(PAD_LG, PAD_LG), pady=(0, PAD_SM), sticky="w")

        # Q entry + slider
        customtkinter.CTkLabel(
            ctrl, text="Q", font=FONTS["subheading"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=2, padx=(PAD_LG, PAD_SM), pady=(PAD_MD, 2),
               sticky="w")

        self._fwd_q_entry = customtkinter.CTkEntry(
            ctrl, width=72, font=FONTS["mono"],
            fg_color=COLORS["bg_tertiary"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            placeholder_text="0.50",
        )
        self._fwd_q_entry.insert(0, "0.50")
        self._fwd_q_entry.grid(row=0, column=3, padx=(0, PAD_SM), pady=(PAD_MD, 2))
        self._fwd_q_entry.bind("<KeyRelease>", self._on_fwd_q_entry_typed)

        self._fwd_q_slider = customtkinter.CTkSlider(
            ctrl, from_=0.01, to=0.99, number_of_steps=98, width=170,
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            progress_color=COLORS["accent"],
            fg_color=COLORS["bg_tertiary"],
            command=self._on_fwd_q_slider,
        )
        self._fwd_q_slider.set(0.50)
        self._fwd_q_slider.grid(row=0, column=4, padx=(0, PAD_SM), pady=(PAD_MD, 2))

        # Q info label
        customtkinter.CTkLabel(
            ctrl, text="flow ratio  (0.01 – 0.99)",
            font=FONTS["caption"],
            text_color=COLORS["text_secondary"],
        ).grid(row=1, column=2, columnspan=3, padx=(PAD_LG, PAD_SM), pady=(0, PAD_SM), sticky="w")

        # "Select the number of peripheral inlets:" control frame (non-clickable label + combo box)
        side_ctrl = customtkinter.CTkFrame(ctrl, fg_color="transparent")
        side_ctrl.grid(row=0, column=5, padx=(PAD_SM, PAD_LG), pady=(PAD_MD, 2))

        customtkinter.CTkLabel(
            side_ctrl,
            text="Select the number of peripheral inlets:",
            font=FONTS["body"],
            text_color=COLORS["text_primary"],
        ).pack(side="left", padx=(0, PAD_SM))

        self._side_inlet_box = customtkinter.CTkComboBox(
            side_ctrl,
            values=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
            width=68,
            height=34,
            font=FONTS["body"],
            dropdown_font=FONTS["body"],
            fg_color=COLORS["bg_tertiary"],
            border_color=COLORS["border"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"],
            command=self._on_side_inlet_box_changed,
        )
        self._side_inlet_box.set("1")
        self._side_inlet_box.pack(side="left")
        self._side_inlet_box.bind("<KeyRelease>", self._on_side_inlet_box_typed)

        # Collapsible Side Inlet Configuration Panel (only active for >= 2)
        self._side_inlet_frame = customtkinter.CTkFrame(
            frame, fg_color=COLORS["bg_secondary"],
            corner_radius=CORNER_RADIUS,
            border_width=1, border_color=COLORS["border"],
        )
        self._build_side_inlet_panel(self._side_inlet_frame)

        # Results area (Cards on LEFT, Draggable Splitter in MIDDLE, Images on RIGHT)
        self._fwd_results_area = customtkinter.CTkFrame(frame, fg_color="transparent")
        self._fwd_results_area.pack(fill="both", expand=True)
        self._fwd_results_area.columnconfigure(0, weight=0, minsize=self._panel_left_width)
        self._fwd_results_area.columnconfigure(1, weight=0, minsize=10)
        self._fwd_results_area.columnconfigure(2, weight=1)
        self._fwd_results_area.rowconfigure(0, weight=1)

        # LEFT: Results Cards Panel
        self._fwd_results_panel = customtkinter.CTkScrollableFrame(
            self._fwd_results_area, fg_color="transparent",
            scrollbar_button_color=COLORS["bg_tertiary"],
            scrollbar_button_hover_color=COLORS["bg_hover"],
            width=self._panel_left_width,
        )
        self._fwd_results_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        self._fwd_results_panel.columnconfigure(0, weight=1)

        # Metric cards container (shown for count <= 1, hidden for count >= 2)
        self._fwd_cards_frame = customtkinter.CTkFrame(self._fwd_results_panel, fg_color="transparent")
        self._fwd_cards_frame.pack(fill="x", pady=(0, PAD_SM // 2))
        self._fwd_cards_frame.columnconfigure(0, weight=1)
        self._fwd_cards_frame.columnconfigure(1, weight=1)

        # Legend container (always on the left, below cards when count<=1, top when count>=2)
        self._fwd_legend_container = customtkinter.CTkFrame(self._fwd_results_panel, fg_color="transparent")
        self._fwd_legend_container.pack(fill="x", pady=(0, PAD_SM // 2))

        # MIDDLE: Interactive Resize Splitter Handle
        self._resize_handle = customtkinter.CTkFrame(
            self._fwd_results_area,
            fg_color="transparent",
            width=10,
            cursor="sb_h_double_arrow",
        )
        self._resize_handle.grid(row=0, column=1, sticky="ns", padx=1)

        self._grip_line = customtkinter.CTkFrame(
            self._resize_handle,
            fg_color=COLORS["border"],
            width=3,
            corner_radius=1,
            cursor="sb_h_double_arrow",
        )
        self._grip_line.place(relx=0.5, rely=0.08, relheight=0.84, anchor="n")

        for w in (self._resize_handle, self._grip_line):
            w.bind("<Enter>", self._on_splitter_enter)
            w.bind("<Leave>", self._on_splitter_leave)
            w.bind("<Button-1>", self._on_splitter_press)
            w.bind("<B1-Motion>", self._on_splitter_motion)
            w.bind("<ButtonRelease-1>", self._on_splitter_release)

        # RIGHT / FULL: Streamline & Dual Visualization Panel
        self._img_panel = customtkinter.CTkScrollableFrame(
            self._fwd_results_area, fg_color=COLORS["bg_secondary"],
            corner_radius=CORNER_RADIUS,
            scrollbar_button_color=COLORS["bg_tertiary"],
            scrollbar_button_hover_color=COLORS["bg_hover"],
        )
        self._img_panel.grid(row=0, column=2, sticky="nsew", padx=(2, 0))
        self._img_panel.columnconfigure(0, weight=1)
        self._img_panel.bind("<Configure>", self._on_img_panel_configure)

        # Container 1: PNG Streamline previews (Central View & Side View)
        self._png_container = customtkinter.CTkFrame(self._img_panel, fg_color="transparent")
        self._png_container.pack(fill="both", expand=True, padx=PAD_SM, pady=PAD_MD)

        self._fwd_img_label_central = customtkinter.CTkLabel(
            self._png_container, text="Central View", fg_color="transparent",
            font=FONTS["caption"], text_color=COLORS["text_tertiary"]
        )
        self._fwd_img_label_central.pack(side="left", fill="both", expand=True,
                                         padx=(0, PAD_SM // 2))

        self._fwd_img_label_side = customtkinter.CTkLabel(
            self._png_container, text="Side View", fg_color="transparent",
            font=FONTS["caption"], text_color=COLORS["text_tertiary"]
        )
        self._fwd_img_label_side.pack(side="left", fill="both", expand=True,
                                      padx=(PAD_SM // 2, 0))

        # Container 2: Dynamic Dual Colored View (Inlet Plane + Outlet Plane)
        self._colored_container = customtkinter.CTkFrame(self._img_panel, fg_color="transparent")

        self._fwd_colored_image_label = customtkinter.CTkLabel(
            self._colored_container,
            text="Click 'Calculate' to render Visualization",
            fg_color="transparent",
            font=FONTS["body"],
            text_color=COLORS["text_tertiary"],
        )
        self._fwd_colored_image_label.pack(fill="both", expand=True, padx=PAD_MD, pady=(PAD_SM, 0))

        # Under-plot legend: Down blade, Upper blade, Central channel, Distribution chamber
        self._fwd_blade_legend_frame = customtkinter.CTkFrame(
            self._colored_container, fg_color="transparent"
        )
        self._fwd_blade_legend_frame.pack(fill="x", padx=PAD_MD, pady=(6, PAD_SM))

        blade_bar = customtkinter.CTkFrame(
            self._fwd_blade_legend_frame,
            fg_color=COLORS["bg_tertiary"],
            corner_radius=8,
        )
        blade_bar.pack(anchor="center")

        # Row 1: Blades (Font size synchronized with DSI number)
        row1 = customtkinter.CTkFrame(blade_bar, fg_color="transparent")
        row1.pack(anchor="center", padx=16, pady=(6, 3))

        customtkinter.CTkLabel(
            row1, image=get_line_sample_icon(BLADE_DOWN_COLOR, style="solid"), text=""
        ).pack(side="left", padx=(0, 6))
        customtkinter.CTkLabel(
            row1, text="Down blade", font=FONTS["dsi_value"], text_color=COLORS["text_primary"]
        ).pack(side="left", padx=(0, 24))

        customtkinter.CTkLabel(
            row1, image=get_line_sample_icon(BLADE_UP_COLOR, style="dotted"), text=""
        ).pack(side="left", padx=(0, 6))
        customtkinter.CTkLabel(
            row1, text="Upper blade", font=FONTS["dsi_value"], text_color=COLORS["text_primary"]
        ).pack(side="left", padx=(0, 0))

        # Row 2: Nozzle diameter and Distribution chamber boundaries (Font size synchronized with DSI number)
        row2 = customtkinter.CTkFrame(blade_bar, fg_color="transparent")
        row2.pack(anchor="center", padx=16, pady=(3, 6))

        customtkinter.CTkLabel(
            row2, image=get_line_sample_icon((WALL_COLOR, "#E5E7EB"), style="dashed"), text=""
        ).pack(side="left", padx=(0, 6))
        customtkinter.CTkLabel(
            row2, text="Nozzle diameter (R = 1.0 mm)", font=FONTS["dsi_value"], text_color=COLORS["text_primary"]
        ).pack(side="left", padx=(0, 24))

        customtkinter.CTkLabel(
            row2, image=get_line_sample_icon((WALL_COLOR, "#E5E7EB"), style="solid"), text=""
        ).pack(side="left", padx=(0, 6))
        customtkinter.CTkLabel(
            row2, text="Distribution chamber (R = 12.5 mm)", font=FONTS["dsi_value"], text_color=COLORS["text_primary"]
        ).pack(side="left", padx=(0, 0))

        return frame

    # Splitter drag & Image resize handlers

    def _on_splitter_enter(self, event=None):
        self._grip_line.configure(fg_color=COLORS["accent"])

    def _on_splitter_leave(self, event=None):
        if not self._is_dragging_splitter:
            self._grip_line.configure(fg_color=COLORS["border"])

    def _on_splitter_press(self, event):
        self._is_dragging_splitter = True
        self._drag_start_x = event.x_root
        self._drag_start_w = self._fwd_results_panel.winfo_width()
        self._grip_line.configure(fg_color=COLORS["accent"])

    def _on_splitter_motion(self, event):
        if not self._is_dragging_splitter:
            return
        delta = event.x_root - self._drag_start_x
        total_w = self._fwd_results_area.winfo_width()
        new_w = max(180, min(total_w - 280, self._drag_start_w + delta))
        self._panel_left_width = new_w
        self._fwd_results_area.columnconfigure(0, minsize=new_w)
        self._fwd_results_panel.configure(width=new_w)
        if self._img_resize_timer is not None:
            self.after_cancel(self._img_resize_timer)
        self._img_resize_timer = self.after(30, self._rescale_and_display_dual_image)

    def _on_splitter_release(self, event=None):
        self._is_dragging_splitter = False
        self._grip_line.configure(fg_color=COLORS["border"])
        self._rescale_and_display_dual_image()

    def _on_img_panel_configure(self, event=None):
        if self._img_resize_timer is not None:
            self.after_cancel(self._img_resize_timer)
        self._img_resize_timer = self.after(40, self._rescale_and_display_dual_image)

    def _build_side_inlet_panel(self, parent):
        """Build the configuration panel for multi-sector side inlets (without title banner)."""
        # Controls grid (header title eliminated per user request)
        grid_frame = customtkinter.CTkFrame(parent, fg_color="transparent")
        grid_frame.pack(fill="x", padx=PAD_LG, pady=(PAD_MD, PAD_MD))

        # Row 0: Theta Width, Rotation, Auto-rotate
        # Theta Width
        customtkinter.CTkLabel(
            grid_frame, text="θ Width (°)", font=FONTS["body"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=0, padx=(0, PAD_SM), pady=(PAD_SM, PAD_SM), sticky="w")

        self._side_theta_entry = customtkinter.CTkEntry(
            grid_frame, width=125, font=FONTS["mono"],
            fg_color=COLORS["bg_tertiary"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            placeholder_text="90 or 30, 45, 60",
        )
        self._side_theta_entry.insert(0, "90")
        self._side_theta_entry.grid(row=0, column=1, padx=(0, PAD_LG), pady=(PAD_SM, PAD_SM))
        self._side_theta_entry.bind("<KeyRelease>", self._on_side_param_changed)

        # Rotation (0 to 360 with step 1)
        customtkinter.CTkLabel(
            grid_frame, text="Rotation (°)", font=FONTS["body"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=2, padx=(0, PAD_SM), pady=(PAD_SM, PAD_SM), sticky="w")

        self._side_rot_entry = customtkinter.CTkEntry(
            grid_frame, width=54, font=FONTS["mono"],
            fg_color=COLORS["bg_tertiary"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            placeholder_text="0",
        )
        self._side_rot_entry.insert(0, "0")
        self._side_rot_entry.grid(row=0, column=3, padx=(0, PAD_SM), pady=(PAD_SM, PAD_SM))
        self._side_rot_entry.bind("<KeyRelease>", self._on_side_rot_entry)

        self._side_rot_slider = customtkinter.CTkSlider(
            grid_frame, from_=0, to=360, number_of_steps=360, width=130,
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            progress_color=COLORS["accent"],
            fg_color=COLORS["bg_tertiary"],
            command=self._on_side_rot_slider,
        )
        self._side_rot_slider.set(0)
        self._side_rot_slider.grid(row=0, column=4, padx=(0, PAD_SM), pady=(PAD_SM, PAD_SM))
        self._side_rot_slider.bind("<ButtonRelease-1>", self._on_side_rot_slider_release)

        # Auto-rotation button (automatically rotates 0° to 360°)
        self._btn_autorot = customtkinter.CTkButton(
            grid_frame,
            text="Auto-rotate",
            font=FONTS["body"],
            fg_color=COLORS["bg_tertiary"],
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            corner_radius=CORNER_RADIUS,
            height=32, width=100,
            command=self._toggle_autorotation,
        )
        self._btn_autorot.grid(row=0, column=5, padx=(0, PAD_SM), pady=(PAD_SM, PAD_SM))

        # Row 1: Spacing, Reset Defaults, Update View
        # Spacing
        customtkinter.CTkLabel(
            grid_frame, text="Spacing", font=FONTS["body"],
            text_color=COLORS["text_primary"],
        ).grid(row=1, column=0, padx=(0, PAD_SM), pady=(0, PAD_SM), sticky="w")

        self._side_spacing_var = customtkinter.StringVar(value="Equispaced")
        customtkinter.CTkSegmentedButton(
            grid_frame,
            values=["Equispaced", "Contiguous"],
            variable=self._side_spacing_var,
            command=self._on_spacing_segmented_changed,
            font=FONTS["body"],
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["bg_tertiary"],
            unselected_hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            corner_radius=CORNER_RADIUS,
            height=32,
        ).grid(row=1, column=1, columnspan=2, padx=(0, PAD_LG), pady=(0, PAD_SM), sticky="w")

        # Row 2: Spacing hint label with detailed examples & input formats
        self._spacing_hint_label = customtkinter.CTkLabel(
            grid_frame,
            text="",
            font=FONTS["caption"],
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
            wraplength=850,
        )
        self._spacing_hint_label.grid(row=2, column=0, columnspan=6, padx=(0, PAD_LG), pady=(0, 4), sticky="w")
        self._sync_theta_entry_for_spacing("Equispaced")

    def _get_selected_inlet_count(self) -> int:
        try:
            val = int(self._side_inlet_box.get().strip())
            return max(0, min(10, val))
        except (ValueError, TypeError):
            return 1

    def _sync_theta_entry_for_spacing(self, spacing_val: Optional[str] = None):
        """Update theta entry state and contents depending on Equispaced vs Contiguous."""
        if spacing_val is None:
            spacing_val = self._side_spacing_var.get()
        n_sides = self._get_selected_inlet_count()

        if spacing_val.lower() == "equispaced":
            val = 360.0 / n_sides if n_sides > 0 else 360.0
            val_str = f"{int(val)}" if val.is_integer() else f"{val:.1f}"
            self._side_theta_entry.configure(state="normal")
            self._side_theta_entry.delete(0, "end")
            self._side_theta_entry.insert(0, val_str)
            self._side_theta_entry.configure(state="disabled")
            self._spacing_hint_label.configure(
                text=f"Equispaced: distribuisce {n_sides} inlet in modo uniforme sui 360° con ampiezza fissa = {val_str}° (360° / {n_sides}). "
                     "Il valore è calcolato automaticamente e non modificabile."
            )
        else:
            self._side_theta_entry.configure(state="normal")
            max_user = max(1, n_sides - 1)
            raw = self._side_theta_entry.get().strip()
            try:
                parts = [float(x.strip()) for x in raw.split(",") if x.strip()][:max_user]
            except ValueError:
                parts = []
            if len(parts) != max_user:
                def_w = 360.0 / n_sides if n_sides > 0 else 120.0
                def_w_str = f"{int(def_w)}" if def_w.is_integer() else f"{def_w:.1f}"
                self._side_theta_entry.delete(0, "end")
                self._side_theta_entry.insert(0, ", ".join([def_w_str] * max_user))
            self._update_contiguous_hint()

    def _update_contiguous_hint(self):
        """Update hint in contiguous mode showing user values and the auto-determined last sector."""
        n_sides = self._get_selected_inlet_count()
        max_user = max(1, n_sides - 1)
        raw = self._side_theta_entry.get().strip()
        try:
            if "," in raw:
                vals = [float(x.strip()) for x in raw.split(",") if x.strip()][:max_user]
            else:
                vals = [float(raw)] if raw else []
        except ValueError:
            vals = []

        if vals:
            u_sum = sum(vals)
            auto_last = max(0.0, 360.0 - u_sum)
            auto_str = f"{int(auto_last)}" if auto_last.is_integer() else f"{auto_last:.1f}"
            vals_str = ", ".join(f"{v:.0f}°" for v in vals)
            self._spacing_hint_label.configure(
                text=f"Contiguous: per {n_sides} inlet puoi impostare fino a {max_user} ampiezze ({vals_str}). "
                     f"L'ultimo inlet è calcolato automaticamente = {auto_str}° per completare i 360°."
            )
        else:
            self._spacing_hint_label.configure(
                text=f"Contiguous: per {n_sides} inlet, imposta fino a {max_user} valori separati da virgola. "
                     "L'ultimo inlet è calcolato automaticamente = 360° - somma."
            )

    def _on_side_inlet_box_changed(self, value: str):
        """Called when user chooses a number (0..10) from the top-bar box."""
        try:
            val = int(value.strip())
            val = max(0, min(10, val))
        except (ValueError, TypeError):
            val = 1

        self._side_n_var.set(str(val))
        self._sync_theta_entry_for_spacing()
        self._update_display_mode()

    def _on_side_inlet_box_typed(self, event=None):
        """Handle typing directly into the combo box."""
        text = self._side_inlet_box.get().strip()
        if text.isdigit():
            val = int(text)
            if 0 <= val <= 10:
                self._on_side_inlet_box_changed(str(val))

    def _on_spacing_segmented_changed(self, value: str):
        """Update hint and entry for Spacing choice and trigger plot update."""
        self._sync_theta_entry_for_spacing(value)
        self._on_side_param_changed()

    def _update_display_mode(self, N: Optional[int] = None, Q: Optional[float] = None):
        """Route to dual visualization for all peripheral inlet counts (0..10).
        When count <= 1 (0 or 1 peripheral inlet):
            - Hide side inlet configuration panel.
            - Show metric calculation cards on the left (with legend below).
            - Load dynamic dual plot with default parameters:
                * count == 0: 0 peripheral inlets (central core only).
                * count == 1: 1 peripheral sheath covering 360°.
        When count >= 2 (2..10 peripheral inlets):
            - Show side inlet configuration panel at the top.
            - Hide metric calculation cards (only legend remains on the left).
            - Load dynamic dual plot with user-configured parameters.
        """
        if N is None:
            try:
                N = int(self._fwd_n_var.get())
            except (ValueError, TypeError):
                N = 4
        if Q is None:
            try:
                Q = float(self._fwd_q_entry.get().strip())
            except (ValueError, TypeError):
                Q = 0.50

        count = self._get_selected_inlet_count()

        # Always hide PNG container – dual plots are used for all counts
        self._png_container.pack_forget()

        # 3-column layout with draggable resize splitter:
        # Col 0: Left panel (metrics + legend for count<=1; legend only for count>=2)
        # Col 1: Resize handle
        # Col 2: Right panel (dual plots)
        self._fwd_results_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        self._resize_handle.grid(row=0, column=1, sticky="ns", padx=1)
        self._img_panel.grid(row=0, column=2, sticky="nsew", padx=(2, 0))
        self._fwd_results_area.columnconfigure(0, weight=0, minsize=self._panel_left_width)
        self._fwd_results_area.columnconfigure(1, weight=0, minsize=10)
        self._fwd_results_area.columnconfigure(2, weight=1)

        # Show colored container on right (dual plots)
        self._colored_container.pack(fill="both", expand=True, padx=PAD_SM, pady=(0, PAD_MD))

        if count <= 1:
            self._stop_autorotation()
            # Hide side inlet config panel
            self._side_inlet_frame.pack_forget()

            # Reset entry
            self._side_theta_entry.delete(0, "end")
            self._side_theta_entry.insert(0, "360" if count == 1 else "0")

            # Show metric cards frame (above legend)
            self._fwd_cards_frame.pack(fill="x", pady=(0, PAD_SM // 2), before=self._fwd_legend_container)

            # Load dynamic dual with fixed params
            if count == 0:
                self._load_dynamic_dual(N, Q, override_params=(0, 0.0, 0.0, "equispaced"))
            else:
                self._load_dynamic_dual(N, Q, override_params=(1, 360.0, 0.0, "equispaced"))
        else:
            # Count >= 2 (multiple peripheral inlets):
            # Show side inlet config panel at top
            self._side_inlet_frame.pack(fill="x", pady=(0, PAD_MD), before=self._fwd_results_area)

            # Hide metric cards frame (only legend remains on the left)
            self._fwd_cards_frame.pack_forget()

            # Load dynamic dual with configurable side inlet params
            self._load_dynamic_dual(N, Q)

    def _on_side_rot_slider(self, value):
        if self._is_autorotating and not self._in_autorot_step:
            self._stop_autorotation()
        val = int(round(float(value)))
        self._side_rot_entry.delete(0, "end")
        self._side_rot_entry.insert(0, str(val))
        if self._rot_debounce_id is not None:
            self.after_cancel(self._rot_debounce_id)
        self._rot_debounce_id = self.after(75, self._dynamic_update_dual)

    def _on_side_rot_slider_release(self, event=None):
        if self._is_autorotating and not self._in_autorot_step:
            self._stop_autorotation()
        if self._rot_debounce_id is not None:
            self.after_cancel(self._rot_debounce_id)
            self._rot_debounce_id = None
        self._dynamic_update_dual()

    def _on_side_rot_entry(self, event=None):
        if self._is_autorotating and not self._in_autorot_step:
            self._stop_autorotation()
        try:
            val = float(self._side_rot_entry.get().strip())
            clamped = max(0.0, min(360.0, val))
            self._side_rot_slider.set(clamped)
            if self._rot_debounce_id is not None:
                self.after_cancel(self._rot_debounce_id)
            self._rot_debounce_id = self.after(150, self._dynamic_update_dual)
        except ValueError:
            pass

    def _toggle_autorotation(self):
        """Toggle continuous 0° to 360° rotation animation."""
        if self._is_autorotating:
            self._stop_autorotation()
        else:
            self._start_autorotation()

    def _start_autorotation(self):
        self._is_autorotating = True
        if hasattr(self, "_btn_autorot") and self._btn_autorot.winfo_exists():
            self._btn_autorot.configure(
                text="Pause",
                fg_color="#D97706",
                hover_color="#B45309",
                text_color="#FFFFFF",
            )
        self._step_autorotation()

    def _stop_autorotation(self):
        self._is_autorotating = False
        if self._autorot_timer_id is not None:
            try:
                self.after_cancel(self._autorot_timer_id)
            except Exception:
                pass
            self._autorot_timer_id = None
        if hasattr(self, "_btn_autorot") and self._btn_autorot.winfo_exists():
            self._btn_autorot.configure(
                text="Auto-rotate",
                fg_color=COLORS["bg_tertiary"],
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_primary"],
            )

    def _step_autorotation(self):
        """Perform one increment step in auto-rotation loop."""
        if not self._is_autorotating:
            return

        try:
            curr_val = float(self._side_rot_slider.get())
        except (ValueError, TypeError):
            curr_val = 0.0

        # Step by 2° per frame, cycling 0 -> 360
        next_val = int(round(curr_val + 2)) % 360

        self._in_autorot_step = True
        try:
            self._side_rot_slider.set(next_val)
            self._side_rot_entry.delete(0, "end")
            self._side_rot_entry.insert(0, str(next_val))
            self._dynamic_update_dual()
        except Exception as e:
            print("Auto-rotation step error:", e)
            self._stop_autorotation()
            return
        finally:
            self._in_autorot_step = False

        if self._is_autorotating:
            self._autorot_timer_id = self.after(35, self._step_autorotation)

    def _on_side_param_changed(self, *args):
        if self._side_spacing_var.get().lower() == "contiguous":
            self._update_contiguous_hint()
        if self._rot_debounce_id is not None:
            self.after_cancel(self._rot_debounce_id)
        self._rot_debounce_id = self.after(150, self._dynamic_update_dual)

    def _reset_side_inlet_controls(self):
        self._stop_autorotation()
        self._side_inlet_box.set("1")
        self._side_n_var.set("1")
        self._side_rot_entry.delete(0, "end")
        self._side_rot_entry.insert(0, "0")
        self._side_rot_slider.set(0)
        self._side_spacing_var.set("Equispaced")
        self._sync_theta_entry_for_spacing("Equispaced")
        self._update_display_mode()

    def _parse_side_inlet_params(self):
        n_sides = self._get_selected_inlet_count()
        spacing = self._side_spacing_var.get().lower()

        if spacing == "equispaced":
            theta = 360.0 / n_sides if n_sides > 0 else 360.0
        else:
            # Contiguous: user can set at most n_sides - 1 values; last is automatically determined
            max_user = max(1, n_sides - 1)
            theta_text = self._side_theta_entry.get().strip()
            try:
                if "," in theta_text:
                    vals = [float(x.strip()) for x in theta_text.split(",") if x.strip()][:max_user]
                else:
                    vals = [float(theta_text)] if theta_text else []
            except ValueError:
                vals = []

            if not vals:
                def_w = 360.0 / n_sides if n_sides > 0 else 120.0
                vals = [def_w] * max_user

            if len(vals) < max_user:
                missing = max_user - len(vals)
                rem = max(0.0, 360.0 - sum(vals))
                step = rem / (missing + 1)
                vals = vals + [step] * missing

            s = sum(vals)
            if s >= 359.0:
                scale = 358.0 / s
                vals = [v * scale for v in vals]
                s = sum(vals)

            last_val = max(1.0, 360.0 - s)
            theta = vals + [last_val]

        # rotation
        try:
            rot_text = self._side_rot_entry.get().strip()
            rotation_deg = float(rot_text) if rot_text else 0.0
        except ValueError:
            rotation_deg = 0.0

        return n_sides, theta, rotation_deg, spacing

    def _dynamic_update_dual(self):
        self._rot_debounce_id = None
        try:
            N = int(self._fwd_n_var.get())
            Q = float(self._fwd_q_entry.get().strip())
            self._update_display_mode(N, Q)
        except (ValueError, TypeError):
            pass

    # Forward callbacks

    def _on_fwd_q_slider(self, value):
        q = round(value, 2)
        self._fwd_q_entry.delete(0, "end")
        self._fwd_q_entry.insert(0, f"{q:.2f}")
        if self._rot_debounce_id is not None:
            self.after_cancel(self._rot_debounce_id)
        self._rot_debounce_id = self.after(50, self._on_fwd_calculate)

    def _on_fwd_q_entry_typed(self, event=None):
        try:
            val = float(self._fwd_q_entry.get().strip())
            if 0.01 <= val <= 0.99:
                self._fwd_q_slider.set(val)
        except (ValueError, TypeError):
            pass
        if self._rot_debounce_id is not None:
            self.after_cancel(self._rot_debounce_id)
        self._rot_debounce_id = self.after(250, self._on_fwd_calculate)

    def _on_fwd_calculate(self):
        """Run forward solver and populate result cards + streamline image."""
        # Clear previous metric cards only
        for w in self._fwd_cards_frame.winfo_children():
            w.destroy()

        # Parse inputs
        try:
            N = int(self._fwd_n_var.get())
            q_text = self._fwd_q_entry.get().strip()
            Q = float(q_text)
        except (ValueError, TypeError):
            self._show_error_card(self._fwd_cards_frame,
                                  "Invalid input — enter numeric N and Q.")
            return

        # Forward computation
        results = forward(N, Q)
        if "error" in results:
            self._show_error_card(self._fwd_cards_frame, results["error"])
            self._clear_fwd_image()
            return

        # Render cards (compact, half-size)
        row = 0
        col = 0
        for metric, data in results.items():
            short = correlations.get_short_name(metric)
            if "Boundary petal" in short or "Boundary Petal" in short:
                continue
                
            value = data["value"]
            unit  = data["unit"]
            
            card = self._make_result_card(
                self._fwd_cards_frame, short, value, unit,
            )
            card.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)
            
            col += 1
            if col > 1:
                col = 0
                row += 1

        # Update streamline or dual colored view
        self._update_display_mode(N, Q)

    def _make_result_card(self, parent, name, value, unit):
        """Create a compact metric card with well-proportioned typography covering the box width."""
        card = customtkinter.CTkFrame(
            parent, fg_color=COLORS["bg_secondary"],
            corner_radius=8,
        )

        # Metric name – bold, wrapped and centered across the card
        customtkinter.CTkLabel(
            card, text=name, font=FONTS["dsi_label"],
            text_color=COLORS["text_secondary"],
            anchor="center", justify="center",
            wraplength=145,
        ).pack(fill="x", expand=True, padx=PAD_SM, pady=(6, 2))

        # Value – bold accent value (number in DSI)
        unit_str = f" {unit}" if unit else ""
        val_text = f"{value:.2f}{unit_str}"
        customtkinter.CTkLabel(
            card, text=val_text,
            font=FONTS["dsi_value"],
            text_color=COLORS["accent"],
            anchor="center",
        ).pack(fill="x", expand=True, padx=PAD_SM, pady=(2, 6))

        return card

    def _show_error_card(self, parent, message: str):
        card = customtkinter.CTkFrame(
            parent, fg_color=COLORS["bg_secondary"],
            corner_radius=CORNER_RADIUS,
        )
        card.grid(row=0, column=0, sticky="nsew", padx=PAD_SM//2, pady=PAD_SM//2)
        customtkinter.CTkLabel(
            card, text="⚠  " + message, font=FONTS["body"],
            text_color=COLORS["error"], wraplength=500,
        ).pack(padx=PAD_MD, pady=PAD_MD)

    def _load_single_image(self, path, label, default_text):
        if path is None:
            label.configure(
                image=None,
                text=default_text,
                font=FONTS["body"],
                text_color=COLORS["text_tertiary"],
            )
            return None
        try:
            pil = Image.open(path)
            # Reduced preview size by 20% (width 450 -> 360)
            pil.thumbnail((360, 256), Image.LANCZOS)
            photo = customtkinter.CTkImage(light_image=pil, dark_image=pil, size=pil.size)
            label.configure(image=photo, text="")
            return photo
        except Exception as e:
            print("Image load error:", e)
            label.configure(
                image=None, text="Error loading image",
                font=FONTS["body"], text_color=COLORS["error"],
            )
            return None

    def _load_png_streamlines(self, N: int, Q: float):
        """Load precomputed PNG streamline images (Central & Side views)."""
        q_exact = round(Q, 2)
        
        path_central = streamline_image_path(N, q_exact, view="central")
        if path_central is None:
            q_snap_02 = round(round(Q / 0.02) * 0.02, 2)
            path_central = streamline_image_path(N, q_snap_02, view="central")
        if path_central is None:
            q_snap_05 = max(0.01, round(round(Q / 0.05) * 0.05, 2))
            path_central = streamline_image_path(N, q_snap_05, view="central")

        self._photo_ref_central = self._load_single_image(
            path_central, self._fwd_img_label_central, "No central image available"
        )
        
        path_side = streamline_image_path(N, q_exact, view="side")
        if path_side is None:
            q_snap_02 = round(round(Q / 0.02) * 0.02, 2)
            path_side = streamline_image_path(N, q_snap_02, view="side")
        if path_side is None:
            q_snap_05 = max(0.01, round(round(Q / 0.05) * 0.05, 2))
            path_side = streamline_image_path(N, q_snap_05, view="side")

        self._photo_ref_side = self._load_single_image(
            path_side, self._fwd_img_label_side, "No side image available"
        )

    def _load_dynamic_dual(self, N: int, Q: float, override_params=None):
        """Generate and display both Inlet & Outlet planes without inside legends, and place legend under DSI cards.

        Args:
            override_params: optional tuple (n_sides, theta, rotation_deg, spacing) to bypass
                             the side inlet config panel (used when count == 2).
        """
        if override_params is not None:
            n_sides, theta, rotation_deg, spacing = override_params
        else:
            n_sides, theta, rotation_deg, spacing = self._parse_side_inlet_params()

        viz = get_visualizer_for_n(N)
        if viz is None:
            self._fwd_colored_image_label.configure(
                image=None,
                text=f"No streamline simulation file found for N = {N}.",
                font=FONTS["body"],
                text_color=COLORS["text_tertiary"],
            )
            self._fwd_colored_status_label.configure(text="")
            self._photo_ref_dual = None
            self._remove_sectors_legend()
            return

        try:
            # Always use white background for clean plots (light theme)
            bg_hex = "#FFFFFF"

            # Render dual image (Inlet on left, Outlet on right, inside legends disabled to save space)
            pil_img, sectors, r_q = viz.render_dual_pil(
                q_ratio=Q,
                n_sides=n_sides,
                theta=theta,
                rotation_deg=rotation_deg,
                spacing=spacing,
                point_size=1.0,
                alpha=0.75,
                figsize=(9.6, 4.8),
                dpi=120,
                bg_color=bg_hex,
                show_nozzle_circle=True,
                show_grid=True,
                show_legend=False,
                n_blades=viz.n_blades,
                show_blades=True,
            )

            # Store raw PIL image and rescale responsively to fit available width
            self._current_dual_pil = pil_img
            self._rescale_and_display_dual_image()

            # Render the external legend on the left panel (below cards if count<=1, top if count>=2)
            self._render_sectors_legend(sectors, r_q, Q, viz.n_blades)

        except Exception as e:
            print("Error rendering dual planes:", e)
            try:
                self._fwd_colored_image_label._label.configure(image="")
            except Exception:
                pass
            try:
                self._fwd_colored_image_label.configure(
                    image=None,
                    text=f"Error rendering dual visualization: {e}",
                    font=FONTS["body"],
                    text_color=COLORS["error"],
                )
            except Exception:
                pass
            self._photo_ref_dual = None
            self._remove_sectors_legend()

    def _rescale_and_display_dual_image(self):
        """Dynamically rescale the dual plot image to fit available width without clipping."""
        if self._current_dual_pil is None:
            return

        avail_w = self._img_panel.winfo_width()
        if avail_w <= 100:
            avail_w = max(350, self.winfo_width() - getattr(self, "_panel_left_width", 320) - 60)

        # Account for scrollbar and container padding
        usable_w = max(240, avail_w - 40)
        orig_w, orig_h = self._current_dual_pil.size
        scale = min(1.0, usable_w / orig_w)
        target_size = (max(240, int(orig_w * scale)), max(120, int(orig_h * scale)))

        if self._photo_ref_dual is not None and isinstance(self._photo_ref_dual, customtkinter.CTkImage):
            self._photo_ref_dual.configure(
                light_image=self._current_dual_pil,
                dark_image=self._current_dual_pil,
                size=target_size,
            )
        else:
            self._photo_ref_dual = customtkinter.CTkImage(
                light_image=self._current_dual_pil,
                dark_image=self._current_dual_pil,
                size=target_size,
            )

        try:
            self._fwd_colored_image_label.configure(image=self._photo_ref_dual, text="")
        except Exception:
            try:
                self._fwd_colored_image_label._label.configure(image="")
            except Exception:
                pass
            self._fwd_colored_image_label.configure(image=self._photo_ref_dual, text="")

    def _render_sectors_legend(self, sectors, r_q: float, Q: float, n_blades: int):
        """Render sector and central fluid legend on the LEFT panel (matching DSI font size)."""
        # In-place update to prevent flicker during slider drag and auto-rotation
        if (
            self._legend_frame is not None
            and self._legend_frame.winfo_exists()
            and hasattr(self, "_legend_sector_labels")
            and len(self._legend_sector_labels) == len(sectors)
            and all(lbl.winfo_exists() for lbl in self._legend_sector_labels)
        ):
            if hasattr(self, "_legend_core_label") and self._legend_core_label is not None and self._legend_core_label.winfo_exists():
                self._legend_core_label.configure(text=f"Central Fluid (Q={Q:.2f})")
            for lbl, sec in zip(self._legend_sector_labels, sectors):
                lbl.configure(text=f"{sec.name}: [{sec.angle_start:.0f}°–{sec.angle_start + sec.angle_width:.0f}°]")
            return

        # DESTROY all previous children in legend container to guarantee no duplicate legends ever
        self._remove_sectors_legend()

        self._legend_frame = customtkinter.CTkFrame(
            self._fwd_legend_container,
            fg_color=COLORS["bg_secondary"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
        )
        self._legend_frame.pack(fill="x", expand=True, padx=2, pady=(PAD_SM // 2, PAD_SM))

        header = customtkinter.CTkFrame(self._legend_frame, fg_color="transparent")
        header.pack(fill="x", padx=PAD_SM, pady=(PAD_SM // 2, 2))

        customtkinter.CTkLabel(
            header,
            text="Legend",
            font=FONTS["subheading"],
            text_color=COLORS["accent"],
            anchor="w",
        ).pack(side="left")

        items_frame = customtkinter.CTkFrame(self._legend_frame, fg_color="transparent")
        items_frame.pack(fill="x", expand=True, padx=PAD_SM, pady=(0, PAD_SM // 2))
        items_frame.columnconfigure(0, weight=1)
        items_frame.columnconfigure(1, weight=1)

        # Central Fluid (spanning 2 columns, synchronized with DSI number font)
        core_box = customtkinter.CTkFrame(items_frame, fg_color=COLORS["bg_tertiary"], corner_radius=6)
        core_box.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=3, pady=3)
        customtkinter.CTkLabel(
            core_box, text="●", font=FONTS["dsi_value"], text_color=CENTRAL_COLOR
        ).pack(side="left", padx=(8, 4), pady=5)
        self._legend_core_label = customtkinter.CTkLabel(
            core_box,
            text=f"Central Fluid (Q={Q:.2f})",
            font=FONTS["dsi_value"],
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self._legend_core_label.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=5)

        # Side sectors (each spanning full width so large DSI font is never cramped)
        for row_idx, sec in enumerate(sectors, start=1):
            sec_box = customtkinter.CTkFrame(items_frame, fg_color=COLORS["bg_tertiary"], corner_radius=6)
            sec_box.grid(row=row_idx, column=0, columnspan=2, sticky="nsew", padx=3, pady=2)
            customtkinter.CTkLabel(
                sec_box, text="●", font=FONTS["dsi_value"], text_color=sec.color
            ).pack(side="left", padx=(8, 4), pady=4)
            lbl = customtkinter.CTkLabel(
                sec_box,
                text=f"{sec.name}: [{sec.angle_start:.0f}°–{sec.angle_start + sec.angle_width:.0f}°]",
                font=FONTS["dsi_value"],
                text_color=COLORS["text_primary"],
                anchor="w",
            )
            lbl.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=4)
            self._legend_sector_labels.append(lbl)

    def _remove_sectors_legend(self):
        """Safely destroy all widgets inside the legend container to prevent duplicate legends."""
        if hasattr(self, "_fwd_legend_container") and self._fwd_legend_container is not None:
            for w in self._fwd_legend_container.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass
        self._legend_frame = None
        self._legend_sector_labels = []
        self._legend_core_label = None

    def _clear_fwd_image(self):
        self._stop_autorotation()
        for lbl in (self._fwd_img_label_central, self._fwd_img_label_side, self._fwd_colored_image_label):
            try:
                lbl._label.configure(image="")
            except Exception:
                pass
        try:
            self._fwd_img_label_central.configure(image=None, text="Central View")
            self._fwd_img_label_side.configure(image=None, text="Side View")
            self._fwd_colored_image_label.configure(image=None, text="Click 'Calculate' to render Visualization")
        except Exception:
            pass
        self._photo_ref_central = None
        self._photo_ref_side = None
        self._photo_ref_dual = None
        self._remove_sectors_legend()

    # ══════════════════════════════════════════════════════════════════════
    #  INVERSE MODE
    # ══════════════════════════════════════════════════════════════════════

    def _build_inverse_panel(self, parent) -> customtkinter.CTkFrame:
        frame = customtkinter.CTkFrame(parent, fg_color="transparent")

        # Input controls
        ctrl = customtkinter.CTkFrame(frame, fg_color=COLORS["bg_secondary"],
                                      corner_radius=CORNER_RADIUS)
        ctrl.pack(fill="x", pady=(0, PAD_MD))

        # Metric dropdown
        customtkinter.CTkLabel(
            ctrl, text="Metric", font=FONTS["subheading"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=0, padx=(PAD_LG, PAD_SM), pady=PAD_MD,
               sticky="w")

        all_metrics = correlations.get_all_metrics()
        self._inv_metric_var = customtkinter.StringVar(
            value=all_metrics[0] if all_metrics else "",
        )
        customtkinter.CTkOptionMenu(
            ctrl,
            variable=self._inv_metric_var,
            values=all_metrics,
            font=FONTS["body"],
            dropdown_font=FONTS["body"],
            fg_color=COLORS["bg_tertiary"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"],
            width=240,
        ).grid(row=0, column=1, padx=(0, PAD_LG), pady=PAD_MD)

        # Target value
        customtkinter.CTkLabel(
            ctrl, text="Value", font=FONTS["subheading"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=2, padx=(PAD_LG, PAD_SM), pady=PAD_MD,
               sticky="w")

        self._inv_target_entry = customtkinter.CTkEntry(
            ctrl, width=90, font=FONTS["mono"],
            fg_color=COLORS["bg_tertiary"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            placeholder_text="1.00",
        )
        self._inv_target_entry.grid(row=0, column=3, padx=(0, PAD_LG),
                                     pady=PAD_MD)

        # Tolerance
        customtkinter.CTkLabel(
            ctrl, text="Tolerance", font=FONTS["subheading"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=4, padx=(PAD_LG, PAD_SM), pady=PAD_MD,
               sticky="w")

        self._inv_tol_entry = customtkinter.CTkEntry(
            ctrl, width=72, font=FONTS["mono"],
            fg_color=COLORS["bg_tertiary"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            placeholder_text="0.05",
        )
        self._inv_tol_entry.insert(0, "0.05")
        self._inv_tol_entry.grid(row=0, column=5, padx=(0, PAD_LG),
                                  pady=PAD_MD)

        # N filter
        customtkinter.CTkLabel(
            ctrl, text="N", font=FONTS["subheading"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=6, padx=(PAD_LG, PAD_SM), pady=PAD_MD,
               sticky="w")

        self._inv_n_var = customtkinter.StringVar(value="All")
        customtkinter.CTkOptionMenu(
            ctrl,
            variable=self._inv_n_var,
            values=["All"] + [str(n) for n in correlations.VALID_N],
            font=FONTS["body"],
            dropdown_font=FONTS["body"],
            fg_color=COLORS["bg_tertiary"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"],
            width=80,
        ).grid(row=0, column=7, padx=(0, PAD_LG), pady=PAD_MD)

        # Find button
        customtkinter.CTkButton(
            ctrl, text="Find Parameters", font=FONTS["subheading"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["text_on_accent"],
            corner_radius=CORNER_RADIUS,
            height=36, width=150,
            command=self._on_inv_find,
        ).grid(row=0, column=8, padx=(PAD_SM, PAD_LG), pady=PAD_MD)

        # Results table
        self._inv_results_scroll = customtkinter.CTkScrollableFrame(
            frame, fg_color=COLORS["bg_primary"],
            corner_radius=CORNER_RADIUS,
            scrollbar_button_color=COLORS["bg_tertiary"],
            scrollbar_button_hover_color=COLORS["bg_hover"],
        )
        self._inv_results_scroll.pack(fill="both", expand=True)

        return frame

    # Inverse callbacks

    def _on_inv_find(self):
        """Run parametric sweep and display results as a sorted table."""
        # Clear previous results
        for w in self._inv_results_scroll.winfo_children():
            w.destroy()

        metric = self._inv_metric_var.get()
        try:
            target = float(self._inv_target_entry.get().strip())
        except (ValueError, TypeError):
            self._show_error_card(self._inv_results_scroll,
                                  "Enter a valid numeric target value.")
            return

        try:
            tol_text = self._inv_tol_entry.get().strip()
            tolerance = float(tol_text) if tol_text else 0.05
        except (ValueError, TypeError):
            tolerance = 0.05

        n_sel = self._inv_n_var.get()
        if n_sel == "All":
            n_values = None  # parametric_sweep defaults to all
        else:
            n_values = [int(n_sel)]

        try:
            results = parametric_sweep(
                metric=metric,
                target=target,
                tolerance=tolerance,
                N_values=n_values,
            )
        except Exception as exc:
            self._show_error_card(self._inv_results_scroll, str(exc))
            return

        if not results:
            self._show_error_card(
                self._inv_results_scroll,
                "No matching parameters found within tolerance.",
            )
            return

        if not hasattr(self, '_inv_photo_refs'):
            self._inv_photo_refs = []
        self._inv_photo_refs.clear()

        # Result cards (capped at 50 for performance)
        for i, row in enumerate(results[:50]):
            n_val = row["N"]
            q_val = row["Q"]

            card = customtkinter.CTkFrame(
                self._inv_results_scroll,
                fg_color=COLORS["bg_secondary"],
                corner_radius=8,
            )
            card.pack(fill="x", pady=(0, PAD_MD))

            txt_clr = COLORS["success"] if i == 0 else COLORS["text_primary"]
            
            # Title with N and Q
            title = customtkinter.CTkLabel(
                card, text=f"N = {n_val}   |   Q = {q_val:.2f}",
                font=FONTS["subheading"], text_color=txt_clr
            )
            title.pack(padx=PAD_MD, pady=(PAD_MD, PAD_SM), anchor="w")

            # Content frame (Metrics on left, Images on right)
            content_frame = customtkinter.CTkFrame(card, fg_color="transparent")
            content_frame.pack(fill="x", padx=PAD_MD, pady=(0, PAD_MD))
            
            # Left side: Metrics
            metrics_frame = customtkinter.CTkFrame(content_frame, fg_color="transparent")
            metrics_frame.pack(side="left", fill="y", padx=(0, PAD_MD))
            
            results_fwd = forward(n_val, q_val)
            if "error" not in results_fwd:
                for met, data in results_fwd.items():
                    short = correlations.get_short_name(met)
                    if "Boundary petal" in short or "Boundary Petal" in short:
                        continue
                    unit_str = f" {data['unit']}" if data['unit'] else ""
                    val_text = f"{data['value']:.2f}{unit_str}"
                    lbl = customtkinter.CTkLabel(
                        metrics_frame, text=f"• {short}: {val_text}",
                        font=FONTS["body"], text_color=COLORS["text_secondary"]
                    )
                    lbl.pack(anchor="w", pady=1)
            
            # Right side: Images
            img_frame = customtkinter.CTkFrame(content_frame, fg_color="transparent")
            img_frame.pack(side="left", fill="both", expand=True)
            
            lbl_central = customtkinter.CTkLabel(img_frame, text="")
            lbl_central.pack(side="left", padx=(0, PAD_MD))
            
            lbl_side = customtkinter.CTkLabel(img_frame, text="")
            lbl_side.pack(side="left")

            # Load images for matched N and Q (trying exact Q, 0.02 step, then 0.05 step)
            q_exact = round(q_val, 2)
            path_central = streamline_image_path(n_val, q_exact, view="central")
            if path_central is None:
                q_snap_02 = round(round(q_val / 0.02) * 0.02, 2)
                path_central = streamline_image_path(n_val, q_snap_02, view="central")
            if path_central is None:
                q_snap_05 = max(0.01, round(round(q_val / 0.05) * 0.05, 2))
                path_central = streamline_image_path(n_val, q_snap_05, view="central")

            photo_c = self._load_single_image(path_central, lbl_central, "Central View Not Available")
            if photo_c:
                self._inv_photo_refs.append(photo_c)
                
            path_side = streamline_image_path(n_val, q_exact, view="side")
            if path_side is None:
                q_snap_02 = round(round(q_val / 0.02) * 0.02, 2)
                path_side = streamline_image_path(n_val, q_snap_02, view="side")
            if path_side is None:
                q_snap_05 = max(0.01, round(round(q_val / 0.05) * 0.05, 2))
                path_side = streamline_image_path(n_val, q_snap_05, view="side")

            photo_s = self._load_single_image(path_side, lbl_side, "Side View Not Available")
            if photo_s:
                self._inv_photo_refs.append(photo_s)

        # Show count if truncated
        if len(results) > 50:
            customtkinter.CTkLabel(
                self._inv_results_scroll,
                text=f"Showing 50 of {len(results)} matches — "
                     "reduce tolerance for fewer results.",
                font=FONTS["caption"],
                text_color=COLORS["text_tertiary"],
            ).pack(pady=PAD_SM)

    def _show_info_modal(self):
        modal = customtkinter.CTkToplevel(self)
        modal.title(i18n.t("modal_params_title"))
        modal.geometry("450x300")
        modal.transient(self.winfo_toplevel())
        modal.grab_set()
        
        modal.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() - 450) // 2
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() - 300) // 2
        modal.geometry(f"+{x}+{y}")
        
        frame = customtkinter.CTkFrame(modal, fg_color=COLORS["bg_primary"])
        frame.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_MD)
        
        customtkinter.CTkLabel(
            frame, text=i18n.t("modal_params_title"), font=FONTS["subheading"], text_color=COLORS["text_primary"]
        ).pack(anchor="w", pady=(0, PAD_MD))
        
        customtkinter.CTkLabel(
            frame, text=i18n.t("modal_params_text"), font=FONTS["body"], text_color=COLORS["text_secondary"],
            justify="left", wraplength=400
        ).pack(anchor="w")
        
        customtkinter.CTkButton(
            frame, text="Close", command=modal.destroy, fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"], text_color=COLORS["text_on_accent"]
        ).pack(side="bottom", pady=PAD_MD)
