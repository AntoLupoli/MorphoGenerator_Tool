"""
MorphoGenerator Tool — Main application window.

Implements the sidebar navigation and view switching logic.
The left sidebar (1/4 of window) contains navigation items;
the right area (3/4) displays the active view.

Navigation:
  - Visualize Morphogenerator : 3-D GLB viewer with settings panel
  - Select Parameters         : parametric design sliders
  - Plot Correlation          : data plots
  - Settings                  : app preferences"""

import sys
import os
from pathlib import Path

# Ensure project root is in sys.path for direct execution and IDE resolution
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import customtkinter as ctk

try:
    from app.theme import (
        COLORS, FONTS, SIDEBAR_WIDTH, PAD_MD, PAD_LG, PAD_XL, CORNER_RADIUS,
        apply_mpl_theme, apply_mpl_light_theme, update_theme_from_settings,
        get_colored_emoji_icon,
    )
    import app.i18n as i18n
except ImportError:
    from theme import (
        COLORS, FONTS, SIDEBAR_WIDTH, PAD_MD, PAD_LG, PAD_XL, CORNER_RADIUS,
        apply_mpl_theme, apply_mpl_light_theme, update_theme_from_settings,
        get_colored_emoji_icon,
    )
    import i18n


class SidebarButton(ctk.CTkButton):
    """A navigation button styled for the sidebar with full-color emoji icons."""

    def __init__(self, master, text, icon_text="", is_active=False, **kwargs):
        self._active = is_active
        self._icon_img = get_colored_emoji_icon(icon_text, size=22) if icon_text else None
        btn_h = 50 if "\n" in text else 44

        super().__init__(
            master,
            text=f"  {text}",
            image=self._icon_img,
            compound="left",
            font=FONTS["nav_active"] if is_active else FONTS["nav_item"],
            fg_color=COLORS["accent_muted"] if is_active else "transparent",
            hover_color=COLORS["bg_hover"],
            text_color=COLORS["accent"] if is_active else COLORS["text_primary"],
            anchor="w",
            height=btn_h,
            corner_radius=CORNER_RADIUS,
            **kwargs,
        )

    def set_active(self, active: bool):
        """Update visual state."""
        self._active = active
        self.configure(
            fg_color=COLORS["accent_muted"] if active else "transparent",
            text_color=COLORS["accent"] if active else COLORS["text_primary"],
            font=FONTS["nav_active"] if active else FONTS["nav_item"],
        )


class MorphoApp(ctk.CTk):
    """Main application window with sidebar navigation."""

    # Navigation items are now built dynamically in __init__ to support i18n

    def __init__(self):
        super().__init__()

        # Window setup
        self.title("MorphoGenerator Tool")
        self.geometry("1440x900")
        self.minsize(1100, 700)
        self.configure(fg_color=COLORS["bg_primary"])

        # Set window icon
        icon_path = Path(__file__).resolve().parent.parent / "app.ico"
        if not icon_path.exists():
            import sys
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass and (Path(meipass) / "app.ico").exists():
                icon_path = Path(meipass) / "app.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        # Apply matplotlib light theme globally (always light for clean white graphs)
        apply_mpl_light_theme()

        # Set appearance
        from app.views.settings import load_settings
        settings = load_settings()
        update_theme_from_settings(settings)
        ctk.set_appearance_mode("light")
        i18n.set_language(settings.get("appearance", {}).get("language", "English"))
        
        self.NAV_ITEMS = [
            ("Morphogenerator", "⚙️", "glb"),
            (i18n.t("nav_params"), "🎛️", "params"),
            (i18n.t("nav_plots"), "📊", "plot"),
            (i18n.t("nav_settings"), "🛠️", "settings"),
            (i18n.t("nav_guide"), "📖", "guide"),
        ]

        # Layout: sidebar + content
        self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self._build_sidebar()

        # Content area
        self.content_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_primary"],
            corner_radius=0,
        )
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Lazy-load views
        self._views = {}
        self._current_view = None

        # Show default view
        self._switch_view("glb")

    #
    #  Sidebar
    #

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_sidebar"],
            corner_radius=0,
            width=SIDEBAR_WIDTH,
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)

        # Crisp 1px right border separating sidebar from main content area
        vsep = ctk.CTkFrame(sidebar, fg_color=COLORS["border"], width=1)
        vsep.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")

        # Logo / Title
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=PAD_LG, pady=(PAD_XL, PAD_MD), sticky="ew")

        ctk.CTkLabel(
            logo_frame,
            text="◉",
            font=(_get_sans_font(), 36, "bold"),
            text_color=COLORS["accent"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            logo_frame,
            text="MorphoGenerator",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(4, 0))

        ctk.CTkLabel(
            logo_frame,
            text="Tool",
            font=FONTS["caption"],
            text_color=COLORS["accent"],
        ).pack(anchor="w")

        # Separator
        sep = ctk.CTkFrame(sidebar, fg_color=COLORS["separator"], height=1)
        sep.grid(row=1, column=0, padx=PAD_LG, pady=PAD_MD, sticky="ew")

        # Navigation buttons
        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.grid(row=2, column=0, padx=PAD_MD, pady=0, sticky="ew")
        nav_frame.grid_columnconfigure(0, weight=1)

        self._nav_buttons = {}
        for idx, (label, icon, key) in enumerate(self.NAV_ITEMS):
            btn = SidebarButton(
                nav_frame,
                text=label,
                icon_text=icon,
                is_active=(idx == 0),
                command=lambda k=key: self._switch_view(k),
            )
            btn.grid(row=idx, column=0, pady=4, sticky="ew")
            self._nav_buttons[key] = btn

        # Spacer
        sidebar.grid_rowconfigure(3, weight=1)

        # Language selector
        lang_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        lang_frame.grid(row=4, column=0, pady=(0, PAD_MD), padx=PAD_LG, sticky="ew")
        
        self.lang_var = ctk.StringVar(value=i18n.get_language())
        lang_menu = ctk.CTkOptionMenu(
            lang_frame,
            variable=self.lang_var,
            values=i18n.AVAILABLE_LANGUAGES,
            command=self._change_language,
            font=FONTS["small"],
            dropdown_font=FONTS["small"],
            fg_color=COLORS["bg_tertiary"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            dropdown_text_color=COLORS["text_primary"],
            height=28
        )
        lang_menu.pack(fill="x")

        # Version label at bottom
        ctk.CTkLabel(
            sidebar,
            text="v1.0",
            font=FONTS["small"],
            text_color=COLORS["text_tertiary"],
        ).grid(row=5, column=0, pady=(0, PAD_MD))

    def _change_language(self, choice):
        from app.views.settings import load_settings, save_settings
        settings = load_settings()
        if "appearance" not in settings:
            settings["appearance"] = {}
        settings["appearance"]["language"] = choice
        save_settings(settings)
        i18n.set_language(choice)
        self.reload_theme()

    #
    #  View switching
    #

    def _switch_view(self, key: str):
        """Switch the content area to the requested view."""
        if self._current_view == key:
            return

        # Update sidebar button states
        for k, btn in self._nav_buttons.items():
            btn.set_active(k == key)

        # Hide current view
        if self._current_view and self._current_view in self._views:
            self._views[self._current_view].grid_forget()

        # Lazy-create view if needed
        if key not in self._views:
            self._views[key] = self._create_view(key)

        # Show new view
        self._views[key].grid(row=0, column=0, sticky="nsew")
        self._current_view = key

    def _create_view(self, key: str) -> ctk.CTkFrame:
        """Instantiate a view by key. Import is deferred to avoid
        circular imports and speed up startup."""
        if key == "glb":
            from app.views.glb_viewer import GLBViewerView
            return GLBViewerView(self.content_frame)
        elif key == "params":
            from app.views.parameters import ParametersView
            return ParametersView(self.content_frame)
        elif key == "plot":
            from app.views.plot_correlation import PlotCorrelationView
            return PlotCorrelationView(self.content_frame)
        elif key == "settings":
            from app.views.settings import SettingsView
            return SettingsView(self.content_frame)
        elif key == "guide":
            from app.views.guide import GuideView
            return GuideView(self.content_frame)
        else:
            # Fallback: empty frame
            return ctk.CTkFrame(self.content_frame, fg_color=COLORS["bg_primary"])

    def reload_theme(self):
        """Reload theme settings and rebuild the UI."""
        from app.views.settings import load_settings
        
        settings = load_settings()
        update_theme_from_settings(settings)
        ctk.set_appearance_mode("light")
        i18n.set_language(settings.get("appearance", {}).get("language", "English"))
        self.NAV_ITEMS = [
            ("Morphogenerator", "⚙️", "glb"),
            (i18n.t("nav_params"), "🎛️", "params"),
            (i18n.t("nav_plots"), "📊", "plot"),
            (i18n.t("nav_settings"), "🛠️", "settings"),
            (i18n.t("nav_guide"), "📖", "guide"),
        ]
        apply_mpl_light_theme()

        # Destroy all current widgets
        for widget in self.winfo_children():
            widget.destroy()
            
        # Rebuild layout
        self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()

        self.content_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_primary"],
            corner_radius=0,
        )
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Clear views cache and recreate current view
        key = self._current_view
        self._current_view = None
        self._views.clear()
        self._switch_view(key)



def _get_sans_font():
    """Return the primary sans-serif font name."""
    import platform
    return "Segoe UI" if platform.system() == "Windows" else "SF Pro Display"
