"""
Plot Correlation view for MorphoGenerator Tool.
"""

import numpy as np
import customtkinter as ctk
from tkinter import filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from mpl_toolkits.mplot3d import Axes3D

from app.theme import COLORS, FONTS, PAD_SM, PAD_MD, PAD_LG, CORNER_RADIUS, apply_mpl_light_theme, chart_color, get_color
from app.core import correlations
from app.core import statistics
from app.views.settings import load_settings
import app.i18n as i18n
import csv

class PlotCorrelationView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.settings = load_settings()
        self.data_points = None

        # Layout: Left control panel (width ~300), Center plot
        self.grid_columnconfigure(0, weight=0, minsize=320)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_control_panel()
        self._build_plot_area()
        self._generate_plot()

    def _build_control_panel(self):
        # Scrollable control panel on the left
        self.controls = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.controls.grid(row=0, column=0, sticky="nsew", padx=PAD_MD, pady=PAD_MD)
        self.controls.grid_columnconfigure(0, weight=1)

        # Top Bar (Help)
        top_bar = ctk.CTkFrame(self.controls, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, PAD_MD))
        
        btn_help = ctk.CTkButton(
            top_bar, text=i18n.t("btn_help"), font=FONTS["body"],
            fg_color=COLORS["bg_tertiary"], hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"], width=80,
            command=self._show_info_modal
        )
        btn_help.pack(side="right")

        # Metrics Selection
        metrics_card = ctk.CTkFrame(self.controls, fg_color=COLORS["bg_secondary"], corner_radius=CORNER_RADIUS)
        metrics_card.grid(row=1, column=0, sticky="ew", pady=(0, PAD_MD))
        ctk.CTkLabel(metrics_card, text="Metrics", font=FONTS["subheading"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM))
        
        self.metric_vars = {}
        for cat, metrics in correlations.CATEGORIES.items():
            ctk.CTkLabel(metrics_card, text=cat, font=FONTS["caption"], text_color=COLORS["text_secondary"]).pack(anchor="w", padx=PAD_MD)
            for m in metrics:
                if m in correlations.get_all_metrics():
                    var = ctk.BooleanVar(value=False)
                    self.metric_vars[m] = var
                    short_name = correlations.get_short_name(m)
                    cb = ctk.CTkCheckBox(metrics_card, text=short_name, variable=var, font=FONTS["body"])
                    cb.pack(anchor="w", padx=PAD_LG, pady=2)
        
        # Select first metric by default
        if self.metric_vars:
            list(self.metric_vars.values())[0].set(True)

        # N Selection
        n_card = ctk.CTkFrame(self.controls, fg_color=COLORS["bg_secondary"], corner_radius=CORNER_RADIUS)
        n_card.grid(row=2, column=0, sticky="ew", pady=(0, PAD_MD))
        ctk.CTkLabel(n_card, text="N Values (Petals)", font=FONTS["subheading"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM))
        
        self.n_vars = {}
        for n in correlations.VALID_N:
            var = ctk.BooleanVar(value=True)
            self.n_vars[n] = var
            cb = ctk.CTkCheckBox(n_card, text=f"N = {n}", variable=var, font=FONTS["body"])
            cb.pack(anchor="w", padx=PAD_MD, pady=2)

        self.plot_type_var = ctk.StringVar(value="2D")

        # Load Data Points Button
        btn_load_data = ctk.CTkButton(
            self.controls, text="Add/Remove Data Points", font=FONTS["body"], 
            fg_color=COLORS["bg_tertiary"], hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"], height=30,
            command=self._toggle_data_points
        )
        btn_load_data.grid(row=3, column=0, sticky="ew", pady=(0, PAD_SM))

        # Generate Button
        btn_gen = ctk.CTkButton(self.controls, text="Generate Plot", font=FONTS["body_bold"], height=40, command=self._generate_plot)
        btn_gen.grid(row=4, column=0, sticky="ew", pady=(0, PAD_MD))

        # Customization
        cust_card = ctk.CTkFrame(self.controls, fg_color=COLORS["bg_secondary"], corner_radius=CORNER_RADIUS)
        cust_card.grid(row=5, column=0, sticky="ew", pady=(0, PAD_MD))
        ctk.CTkLabel(cust_card, text="Customization", font=FONTS["subheading"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM))

        def add_control(parent, label_text, widget_class, **kwargs):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(fill="x", padx=PAD_MD, pady=2)
            ctk.CTkLabel(frame, text=label_text, font=FONTS["caption"], width=100, anchor="w").pack(side="left")
            w = widget_class(frame, **kwargs)
            w.pack(side="right", fill="x", expand=True)
            return w

        plot_settings = self.settings.get("plot", {})
        
        self.font_var = ctk.StringVar(value=plot_settings.get("font_family", "Segoe UI"))
        add_control(cust_card, "Font", ctk.CTkOptionMenu, variable=self.font_var, values=["Segoe UI", "Arial", "Times New Roman"])
        
        self.marker_var = ctk.StringVar(value="None")
        add_control(cust_card, "Marker", ctk.CTkOptionMenu, variable=self.marker_var, values=["None", "o", "s", "^", "D", "x"])
        
        self.linestyle_var = ctk.StringVar(value="-")
        add_control(cust_card, "Line Style", ctk.CTkOptionMenu, variable=self.linestyle_var, values=["-", "--", "-.", ":"])
        
        self.grid_var = ctk.BooleanVar(value=True)
        cb_grid = ctk.CTkCheckBox(cust_card, text="", variable=self.grid_var)
        f = ctk.CTkFrame(cust_card, fg_color="transparent")
        f.pack(fill="x", padx=PAD_MD, pady=2)
        ctk.CTkLabel(f, text="Show Grid", font=FONTS["caption"], width=100, anchor="w").pack(side="left")
        cb_grid.pack(side="right", anchor="e")

        # Export
        export_card = ctk.CTkFrame(self.controls, fg_color=COLORS["bg_secondary"], corner_radius=CORNER_RADIUS)
        export_card.grid(row=6, column=0, sticky="ew", pady=(0, PAD_MD))
        ctk.CTkLabel(export_card, text="Export", font=FONTS["subheading"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM))

        self.format_var = ctk.StringVar(value=plot_settings.get("export_format", "PNG"))
        add_control(export_card, "Format", ctk.CTkOptionMenu, variable=self.format_var, values=["PNG", "SVG", "PDF"])
        
        self.dpi_var = ctk.StringVar(value=str(plot_settings.get("dpi", "300")))
        add_control(export_card, "DPI", ctk.CTkOptionMenu, variable=self.dpi_var, values=["72", "150", "300", "600"])

        btn_save = ctk.CTkButton(export_card, text="Save Plot", fg_color="transparent", border_width=1, command=self._save_plot)
        btn_save.pack(fill="x", padx=PAD_MD, pady=(PAD_MD, PAD_SM))
        
        btn_save_light = ctk.CTkButton(export_card, text="Save Plot (Light Mode)", fg_color=COLORS["bg_tertiary"], hover_color=COLORS["bg_hover"], text_color=COLORS["text_primary"], border_width=0, command=self._export_light_mode)
        btn_save_light.pack(fill="x", padx=PAD_MD, pady=(0, PAD_MD))

    def _build_plot_area(self):
        self.right_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=PAD_MD, pady=PAD_MD)
        self.right_panel.grid_rowconfigure(0, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)

        # Plot Canvas
        self.plot_frame = ctk.CTkFrame(self.right_panel, fg_color=COLORS["bg_secondary"], corner_radius=CORNER_RADIUS)
        self.plot_frame.grid(row=0, column=0, sticky="nsew", pady=(0, PAD_MD))
        
        self.fig = plt.Figure(figsize=(8, 6), dpi=100, facecolor='white')
        self.mpl_canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.mpl_canvas.get_tk_widget().configure(background='white')
        self.mpl_canvas.get_tk_widget().pack(fill="both", expand=True, padx=PAD_SM, pady=PAD_SM)
        
        self.toolbar_frame = ctk.CTkFrame(self.plot_frame, fg_color="transparent", height=40)
        self.toolbar_frame.pack(fill="x", padx=PAD_SM, pady=(0, PAD_SM))
        self.toolbar = NavigationToolbar2Tk(self.mpl_canvas, self.toolbar_frame)
        self.toolbar.update()


    def _get_selected_metrics(self):
        return [m for m, var in self.metric_vars.items() if var.get()]

    def _get_selected_n(self):
        return [n for n, var in self.n_vars.items() if var.get()]

    def _generate_plot(self):
        metrics = self._get_selected_metrics()
        n_values = self._get_selected_n()
        plot_type = self.plot_type_var.get()
        
        if not metrics or not n_values:
            return

        # Clear existing figure and enforce light theme with white background
        self.fig.clf()
        self.fig.patch.set_facecolor('white')
        apply_mpl_light_theme()
        
        # Apply customization
        plt.rcParams["font.family"] = self.font_var.get()
        marker = self.marker_var.get()
        if marker == "None": marker = ""
        ls = self.linestyle_var.get()
        show_grid = self.grid_var.get()

        Q_range = np.linspace(correlations.Q_MIN, correlations.Q_MAX, 200)

        if plot_type == "2D":
            # Grid of subplots
            num_metrics = len(metrics)
            cols = 2 if num_metrics > 1 else 1
            rows = (num_metrics + 1) // 2
            
            axes = self.fig.subplots(rows, cols, squeeze=False)
            
            for idx, metric in enumerate(metrics):
                r, c = idx // cols, idx % cols
                ax = axes[r, c]
                ax.set_facecolor('white')
                
                valid_n = [n for n in n_values if n in correlations.get_available_N(metric)]
                
                for i, n in enumerate(valid_n):
                    color = chart_color(i, force_mode="light")
                    y = correlations.evaluate_range(metric, n, Q_range)
                    ax.plot(Q_range, y, color=color, linestyle=ls, marker=marker, markevery=20, label=f"N={n}")
                    
                    if self.data_points and metric in self.data_points and n in self.data_points[metric]:
                        pts = self.data_points[metric][n]
                        ax.scatter(pts['Q'], pts['Y'], color=color, marker='o', s=40, alpha=0.8, edgecolor='black', linewidth=0.5)
                
                title_text = correlations.get_short_name(metric)
                ax.set_title(title_text, color="#000000", fontsize=11, fontweight="bold")
                ax.set_xlabel("Flow Ratio Q", color="#000000")
                unit = correlations.get_unit(metric)
                ylabel = f"{title_text} [{unit}]" if unit != "–" else title_text
                ax.set_ylabel(ylabel, color="#000000")
                ax.tick_params(colors="#333333")
                for spine in ax.spines.values():
                    spine.set_color("#C6C6C8")
                if show_grid:
                    ax.grid(True, alpha=0.5, color="#E5E5EA")
                
                leg = ax.legend(facecolor='white', edgecolor='#C6C6C8')
                if leg:
                    leg.get_frame().set_facecolor('white')
                    leg.get_frame().set_edgecolor('#C6C6C8')
                    for text in leg.get_texts():
                        text.set_color('#000000')
            
            # Hide empty subplots
            for idx in range(num_metrics, rows * cols):
                r, c = idx // cols, idx % cols
                axes[r, c].set_visible(False)
                
            self.fig.tight_layout()

        elif plot_type == "3D":
            # Just plot the first selected metric for 3D
            metric = metrics[0]
            ax = self.fig.add_subplot(111, projection='3d')
            ax.set_facecolor('white')
            
            valid_n = [n for n in n_values if n in correlations.get_available_N(metric)]
            if valid_n:
                # Create meshgrid
                Q_mesh, N_mesh = np.meshgrid(Q_range, valid_n)
                Z_mesh = np.zeros_like(Q_mesh)
                
                for i, n in enumerate(valid_n):
                    Z_mesh[i, :] = correlations.evaluate_range(metric, n, Q_range)
                
                surf = ax.plot_surface(Q_mesh, N_mesh, Z_mesh, cmap='viridis', edgecolor='none', alpha=0.8)
                
                ax.set_xlabel('Flow Ratio Q', color='#000000')
                ax.set_ylabel('Number of Petals N', color='#000000')
                ax.set_zlabel(correlations.get_short_name(metric), color='#000000')
                ax.set_title(f"3D Surface: {correlations.get_short_name(metric)}", color='#000000', fontweight="bold")
                ax.tick_params(colors='#333333')
                ax.xaxis.pane.fill = False
                ax.yaxis.pane.fill = False
                ax.zaxis.pane.fill = False
                ax.xaxis.pane.set_edgecolor('#C6C6C8')
                ax.yaxis.pane.set_edgecolor('#C6C6C8')
                ax.zaxis.pane.set_edgecolor('#C6C6C8')

        self.mpl_canvas.draw()
        


    def _save_plot(self):
        import os
        fmt = self.format_var.get().lower()
        dpi = int(self.dpi_var.get())
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}",
            filetypes=[(f"{fmt.upper()} Image", f"*.{fmt}")]
        )
        
        if filepath:
            try:
                self.fig.savefig(filepath, format=fmt, dpi=dpi, bbox_inches="tight", facecolor='white')
            except Exception as e:
                print(f"Error saving plot: {e}")

    def _export_light_mode(self):
        self._save_plot()

    def _toggle_data_points(self):
        if self.data_points is not None:
            self.data_points = None
            self._generate_plot()
            return

        from app.core import image_loader
        filepath = image_loader.get_data_root() / ".prev" / "metrics.csv"
        
        if not filepath.exists():
            print(f"File not found: {filepath}")
            return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                data = list(reader)
            
            parsed = {}
            for row in data:
                try:
                    n = int(row['N'])
                    q = float(row['Q'])
                    
                    perimeter_petal_mm = float(row.get('perimeter_petal_mm', 0))
                    external_boundary = float(row.get('external_boundary', 0))
                    area_petal_mm2 = float(row.get('area_petal_mm2', 0))
                    
                    vals = {
                        "Internal Petal Perimeter": perimeter_petal_mm - external_boundary,
                        "External Petal Perimeter": external_boundary,
                        "Total Petal Area": area_petal_mm2,
                        "Total Petal Perimeter": perimeter_petal_mm,
                        "DSI Internal": (perimeter_petal_mm - external_boundary) * n / np.pi,
                        "DSI External": external_boundary * n / np.pi,
                        "DSI Total": perimeter_petal_mm * n / np.pi
                    }
                    
                    for m_ui, val in vals.items():
                        if m_ui not in parsed:
                            parsed[m_ui] = {}
                        if n not in parsed[m_ui]:
                            parsed[m_ui][n] = {'Q': [], 'Y': []}
                        parsed[m_ui][n]['Q'].append(q)
                        parsed[m_ui][n]['Y'].append(val)
                except ValueError:
                    continue
                    
            self.data_points = parsed
            self._generate_plot()
        except Exception as e:
            print(f"Error loading CSV: {e}")

    def _show_info_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title(i18n.t("modal_plots_title"))
        modal.geometry("450x300")
        modal.transient(self.winfo_toplevel())
        modal.grab_set()
        
        modal.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() - 450) // 2
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() - 300) // 2
        modal.geometry(f"+{x}+{y}")
        
        frame = ctk.CTkFrame(modal, fg_color=COLORS["bg_primary"])
        frame.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_MD)
        
        ctk.CTkLabel(
            frame, text=i18n.t("modal_plots_title"), font=FONTS["subheading"], text_color=COLORS["text_primary"]
        ).pack(anchor="w", pady=(0, PAD_MD))
        
        ctk.CTkLabel(
            frame, text=i18n.t("modal_plots_text"), font=FONTS["body"], text_color=COLORS["text_secondary"],
            justify="left", wraplength=400
        ).pack(anchor="w")
        
        ctk.CTkButton(
            frame, text="Close", command=modal.destroy, fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"], text_color=COLORS["text_on_accent"]
        ).pack(side="bottom", pady=PAD_MD)
