"""
Guide / Help View.
Displays the full documentation of the application.
"""

import customtkinter as ctk
from app.theme import COLORS, FONTS, PAD_SM, PAD_MD, PAD_LG, PAD_XL, CORNER_RADIUS
import app.i18n as i18n


class GuideView(ctk.CTkFrame):
    """View to display application documentation."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=PAD_LG, pady=PAD_LG)
        self.scroll.grid_columnconfigure(0, weight=1)

        # Title
        title_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, PAD_LG))
        
        ctk.CTkLabel(
            title_frame, text=i18n.t("guide_title"),
            font=FONTS["title"], text_color=COLORS["text_primary"]
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame, text=i18n.t("guide_intro"),
            font=FONTS["body"], text_color=COLORS["text_secondary"]
        ).pack(anchor="w", pady=(PAD_SM, 0))

        self._build_section(1, "guide_glb_title", "guide_glb_text")
        self._build_section(2, "guide_params_title", "guide_params_text")
        self._build_section(3, "guide_plots_title", "guide_plots_text")
        self._build_section(4, "guide_settings_title", "guide_settings_text")

    def _build_section(self, row: int, title_key: str, text_key: str):
        card = ctk.CTkFrame(self.scroll, fg_color=COLORS["bg_secondary"], corner_radius=CORNER_RADIUS)
        card.grid(row=row, column=0, sticky="ew", pady=(0, PAD_MD))
        
        ctk.CTkLabel(
            card, text=i18n.t(title_key),
            font=FONTS["heading"], text_color=COLORS["text_primary"]
        ).pack(anchor="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM))
        
        sep = ctk.CTkFrame(card, fg_color=COLORS["separator"], height=1)
        sep.pack(fill="x", padx=PAD_MD)
        
        ctk.CTkLabel(
            card, text=i18n.t(text_key),
            font=FONTS["body"], text_color=COLORS["text_secondary"],
            justify="left", wraplength=700
        ).pack(anchor="w", padx=PAD_MD, pady=PAD_MD)
