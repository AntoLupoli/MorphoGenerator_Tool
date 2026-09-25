"""
Settings view for MorphoGenerator Tool.
"""

import json
import os
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog
from app.theme import COLORS, FONTS, PAD_SM, PAD_MD, PAD_LG, PAD_XL, CORNER_RADIUS
from app.core import image_loader

SETTINGS_FILE = image_loader.get_data_root() / "app_settings.json"

DEFAULT_SETTINGS = {
    "appearance": {
        "theme_mode": "Dark",
        "accent_color": "Blue",
        "font_scale": "1.0",
        "language": "English"
    },
    "data_path": str(image_loader.get_data_root()),
    "plot": {
        "font_family": "Segoe UI",
        "font_size": 12,
        "dpi": "300",
        "export_format": "PNG",
        "figure_width": "8",
        "figure_height": "6"
    }
}

def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
                # Merge with defaults
                merged = DEFAULT_SETTINGS.copy()
                for k, v in settings.items():
                    if isinstance(v, dict) and k in merged:
                        merged[k].update(v)
                    else:
                        merged[k] = v
                return merged
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")

class SettingsView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self.settings = load_settings()

        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=PAD_LG, pady=PAD_LG)
        self.scroll.grid_columnconfigure(0, weight=1)

        self._build_appearance_section()
        self._build_data_section()
        self._build_plot_section()
        self._build_about_section()

    def _create_section_card(self, title):
        card = ctk.CTkFrame(self.scroll, fg_color=COLORS["bg_secondary"], corner_radius=CORNER_RADIUS)
        card.grid_columnconfigure(1, weight=1)
        
        lbl_title = ctk.CTkLabel(card, text=title, font=FONTS["heading"], text_color=COLORS["text_primary"])
        lbl_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM))
        
        sep = ctk.CTkFrame(card, fg_color=COLORS["separator"], height=1)
        sep.grid(row=1, column=0, columnspan=2, sticky="ew", padx=PAD_MD, pady=(0, PAD_SM))
        
        return card

    def _build_appearance_section(self):
        card = self._create_section_card("Appearance")
        card.grid(row=0, column=0, sticky="ew", pady=(0, PAD_MD))

        # Accent color
        lbl_accent = ctk.CTkLabel(card, text="Accent Color", font=FONTS["body"])
        lbl_accent.grid(row=3, column=0, sticky="w", padx=PAD_MD, pady=PAD_SM)

        colors_frame = ctk.CTkFrame(card, fg_color="transparent")
        colors_frame.grid(row=3, column=1, sticky="e", padx=PAD_MD, pady=PAD_SM)

        preset_colors = {
            "Blue": "#0A84FF",
            "Purple": "#BF5AF2",
            "Green": "#30D158",
            "Orange": "#FF9F0A",
            "Red": "#FF453A"
        }

        for i, (name, hex_val) in enumerate(preset_colors.items()):
            btn = ctk.CTkButton(
                colors_frame, text="", width=24, height=24, corner_radius=12,
                fg_color=hex_val, hover_color=hex_val,
                command=lambda n=name: self._set_accent(n)
            )
            btn.grid(row=0, column=i, padx=4)

        self.lbl_selected_color = ctk.CTkLabel(card, text=f"Selected: {self.settings['appearance']['accent_color']}", font=FONTS["caption"], text_color=COLORS["text_secondary"])
        self.lbl_selected_color.grid(row=4, column=1, sticky="e", padx=PAD_MD, pady=(0, PAD_SM))

        # Font Scale (Number List from 1.0 to 3.0 with step 0.5)
        lbl_font = ctk.CTkLabel(card, text="UI Font Size", font=FONTS["body"])
        lbl_font.grid(row=5, column=0, sticky="w", padx=PAD_MD, pady=PAD_SM)
        
        self.font_scale_options = ["1.0x", "1.5x", "2.0x", "2.5x", "3.0x"]
        curr_val = str(self.settings["appearance"].get("font_scale", "1.0")).rstrip("x")
        try:
            curr_f = float(curr_val)
            # Find closest option in font_scale_options
            closest = min(self.font_scale_options, key=lambda opt: abs(float(opt.rstrip("x")) - curr_f))
            initial_choice = closest
        except (ValueError, TypeError):
            initial_choice = "1.0x"
        
        self.font_scale_var = ctk.StringVar(value=initial_choice)
        self.font_menu = ctk.CTkOptionMenu(
            card,
            values=self.font_scale_options,
            variable=self.font_scale_var,
            command=self._set_font_scale,
            font=FONTS["body"],
            dropdown_font=FONTS["body"],
            fg_color=COLORS["bg_tertiary"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"],
            width=130,
        )
        self.font_menu.grid(row=5, column=1, sticky="e", padx=PAD_MD, pady=PAD_SM)

    def _set_accent(self, name):
        self.settings["appearance"]["accent_color"] = name
        self.lbl_selected_color.configure(text=f"Selected: {name}")
        self._save_all()

    def _set_font_scale(self, choice):
        scale_val = choice.rstrip("x")
        self.settings["appearance"]["font_scale"] = scale_val
        self._save_all()

    def _build_data_section(self):
        card = self._create_section_card("Data Configuration")
        card.grid(row=1, column=0, sticky="ew", pady=(0, PAD_MD))

        lbl_path = ctk.CTkLabel(card, text="Data Directory", font=FONTS["body"])
        lbl_path.grid(row=2, column=0, sticky="w", padx=PAD_MD, pady=PAD_SM)

        path_frame = ctk.CTkFrame(card, fg_color="transparent")
        path_frame.grid(row=2, column=1, sticky="e", padx=PAD_MD, pady=PAD_SM)
        path_frame.grid_columnconfigure(0, weight=1)

        self.path_var = ctk.StringVar(value=self.settings["data_path"])
        entry = ctk.CTkEntry(path_frame, textvariable=self.path_var, width=300)
        entry.grid(row=0, column=0, padx=(0, PAD_SM))
        
        btn_browse = ctk.CTkButton(path_frame, text="Browse", width=80, command=self._browse_path)
        btn_browse.grid(row=0, column=1)

        self.lbl_status = ctk.CTkLabel(card, text="● Status unknown", font=FONTS["caption"])
        self.lbl_status.grid(row=3, column=1, sticky="e", padx=PAD_MD, pady=(0, PAD_SM))
        self._update_path_status()

    def _browse_path(self):
        folder = filedialog.askdirectory(initialdir=self.path_var.get())
        if folder:
            self.path_var.set(folder)
            self.settings["data_path"] = folder
            image_loader.set_data_root(folder)
            self._update_path_status()
            self._save_all()

    def _update_path_status(self):
        path = Path(self.path_var.get())
        if path.exists() and path.is_dir():
            # Check if any streamline folders exist
            has_data = any(path.glob(".prev/M2_N*_streamline"))
            if has_data:
                self.lbl_status.configure(text="● Valid data directory found", text_color=COLORS["success"])
            else:
                self.lbl_status.configure(text="● Directory exists but no streamline data found", text_color=COLORS["warning"])
        else:
            self.lbl_status.configure(text="● Directory does not exist", text_color=COLORS["error"])

    def _build_plot_section(self):
        card = self._create_section_card("Default Plot Settings")
        card.grid(row=2, column=0, sticky="ew", pady=(0, PAD_MD))

        def add_row(row, label_text, var_name, options, is_entry=False):
            lbl = ctk.CTkLabel(card, text=label_text, font=FONTS["body"])
            lbl.grid(row=row, column=0, sticky="w", padx=PAD_MD, pady=PAD_SM)
            
            var = ctk.StringVar(value=str(self.settings["plot"][var_name]))
            if is_entry:
                widget = ctk.CTkEntry(card, textvariable=var, width=140)
            else:
                widget = ctk.CTkOptionMenu(card, variable=var, values=options, command=lambda v: self._update_plot_setting(var_name, v))
            widget.grid(row=row, column=1, sticky="e", padx=PAD_MD, pady=PAD_SM)
            
            if is_entry:
                var.trace_add("write", lambda *args: self._update_plot_setting(var_name, var.get()))
            return var

        add_row(2, "Font Family", "font_family", ["Segoe UI", "Arial", "Times New Roman", "Consolas"])
        add_row(3, "Font Size", "font_size", ["8", "10", "12", "14", "16", "18"])
        add_row(4, "DPI", "dpi", ["72", "150", "300", "600"])
        add_row(5, "Export Format", "export_format", ["PNG", "SVG", "PDF"])
        add_row(6, "Figure Width (in)", "figure_width", [], is_entry=True)
        add_row(7, "Figure Height (in)", "figure_height", [], is_entry=True)

    def _update_plot_setting(self, key, value):
        self.settings["plot"][key] = value
        self._save_all()

    def _build_about_section(self):
        card = self._create_section_card("About")
        card.grid(row=3, column=0, sticky="ew", pady=(0, PAD_MD))

        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=2, column=0, columnspan=2, padx=PAD_MD, pady=PAD_MD, sticky="ew")

        ctk.CTkLabel(info_frame, text="MorphoGenerator Tool", font=FONTS["heading"], text_color=COLORS["text_primary"]).pack(anchor="center", pady=(0, 4))
        ctk.CTkLabel(info_frame, text="Version: 1.0", font=FONTS["caption"], text_color=COLORS["accent"]).pack(anchor="center", pady=(0, 10))
        ctk.CTkLabel(info_frame, text="Developed at Università di Napoli Federico II — Department of Chemical Engineering.", font=FONTS["body"], text_color=COLORS["text_secondary"]).pack(anchor="center", pady=(4, 0))

    def _save_all(self):
        save_settings(self.settings)
        # Schedule theme reload on the main app window (increased delay to allow animations to finish)
        self.after(300, lambda: self.winfo_toplevel().reload_theme())
