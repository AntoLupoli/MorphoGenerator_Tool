"""
Apple-style dark theme configuration for MorphoGenerator Tool.
Inspired by macOS / iOS design language with a focus on
clean typography, subtle depth, and vibrant accent colors.
"""

# Color Palette

COLORS = {
    # Backgrounds (layered depth, darkest → lightest)
    "bg_primary":    ("#F5F6F8", "#1C1C1E"),      # Main background (clean soft canvas)
    "bg_secondary":  ("#FFFFFF", "#2C2C2E"),      # Cards, panels (crisp white)
    "bg_tertiary":   ("#EAEBED", "#3A3A3C"),      # Elevated surfaces, inputs
    "bg_sidebar":    ("#FFFFFF", "#141416"),      # Sidebar (crisp white in light)
    "bg_hover":      ("#EEF0F3", "#363638"),      # Hover state for list items

    # Accent (iOS Blue)
    "accent":        ("#007AFF", "#0A84FF"),
    "accent_hover":  ("#0051D5", "#409CFF"),
    "accent_pressed":("#0040B0", "#0071E3"),
    "accent_muted":  ("#EBF4FF", "#1E3A5F"),      # Subtle blue tint for active item

    # Text hierarchy
    "text_primary":  ("#1C1C1E", "#FFFFFF"),
    "text_secondary":("#6B7280", "#8E8E93"),
    "text_tertiary": ("#9CA3AF", "#636366"),
    "text_on_accent":("#FFFFFF", "#FFFFFF"),

    # Borders & separators
    "border":        ("#E2E4E9", "#38383A"),
    "separator":     ("#E5E7EB", "#48484A"),

    # Semantic
    "success":       ("#34C759", "#30D158"),
    "warning":       ("#FFCC00", "#FFD60A"),
    "error":         ("#FF3B30", "#FF453A"),
    "info":          ("#32ADE6", "#64D2FF"),

    # Chart / plot palette (up to 6 series)
    "chart": [
        ("#007AFF", "#0A84FF"),   # Blue
        ("#FF9500", "#FF9F0A"),   # Orange
        ("#34C759", "#30D158"),   # Green
        ("#FF3B30", "#FF453A"),   # Red
        ("#AF52DE", "#BF5AF2"),   # Purple
    ],
}


# Typography
# Windows → Segoe UI family;  macOS → SF Pro (if available)

import platform as _platform

_IS_WINDOWS = _platform.system() == "Windows"

_SANS  = "Segoe UI"      if _IS_WINDOWS else "SF Pro Display"
_TEXT  = "Segoe UI"      if _IS_WINDOWS else "SF Pro Text"
_MONO  = "Consolas"      if _IS_WINDOWS else "SF Mono"

# Public alias – lets other modules build custom font tuples with the same family
MONO_FAMILY = _MONO

BASE_FONTS = {
    "title_lg":   (_SANS, 32, "bold"),
    "title":      (_SANS, 24, "bold"),
    "heading":    (_SANS, 18, "bold"),
    "subheading": (_TEXT, 15, "bold"),
    "body":       (_TEXT, 13),
    "body_bold":  (_TEXT, 13, "bold"),
    "caption":    (_TEXT, 11),
    "small":      (_TEXT, 10),
    "mono":       (_MONO, 12),
    "mono_sm":    (_MONO, 10),
    # Sidebar navigation
    "nav_item":   (_TEXT, 14),
    "nav_active": (_TEXT, 14, "bold"),
    # DSI & synchronized legend fonts
    "dsi_value":  (_MONO, 15, "bold"),
    "dsi_label":  (_TEXT, 13, "bold"),
}

FONTS = BASE_FONTS.copy()


# Layout Constants

SIDEBAR_WIDTH    = 280       # px – fixed left‑side menu
CORNER_RADIUS    = 12        # px – card / button rounding
CORNER_RADIUS_SM = 8         # px – small widgets
BUTTON_HEIGHT    = 40        # px
ENTRY_HEIGHT     = 38        # px
PAD_XS           = 4
PAD_SM           = 8
PAD_MD           = 16
PAD_LG           = 24
PAD_XL           = 32


# Matplotlib Integration
# Styles applied to every embedded matplotlib figure so plots match the UI.




# Helpers

def get_color(key: str, force_mode: str = None) -> str:
    """Return the correct color string based on the current appearance mode or force_mode."""
    import customtkinter as ctk
    if force_mode is not None:
        mode = 0 if force_mode.lower() == "light" else 1
    else:
        mode = 0 if ctk.get_appearance_mode().lower() == "light" else 1
    val = COLORS[key]
    return val[mode] if isinstance(val, tuple) else val

def chart_color(index: int, force_mode: str = None) -> str:
    """Return a chart color by index, cycling if necessary."""
    import customtkinter as ctk
    if force_mode is not None:
        mode = 0 if force_mode.lower() == "light" else 1
    else:
        mode = 0 if ctk.get_appearance_mode().lower() == "light" else 1
    palette = COLORS["chart"]
    return palette[index % len(palette)][mode]


def apply_mpl_theme(force_mode: str = None):
    """Apply the appearance mode to matplotlib globally (supports 'light' or 'dark')."""
    import customtkinter as ctk
    import matplotlib as mpl
    if force_mode is not None:
        mode = 0 if force_mode.lower() == "light" else 1
    else:
        mode = 0 if ctk.get_appearance_mode().lower() == "light" else 1
    
    style = {
        "figure.facecolor":   "#FFFFFF" if mode == 0 else COLORS["bg_secondary"][mode],
        "axes.facecolor":     "#FFFFFF" if mode == 0 else COLORS["bg_primary"][mode],
        "axes.edgecolor":     COLORS["border"][mode],
        "axes.labelcolor":    COLORS["text_primary"][mode],
        "axes.titlecolor":    COLORS["text_primary"][mode],
        "axes.grid":          True,
        "grid.color":         COLORS["border"][mode],
        "grid.alpha":         0.4,
        "text.color":         COLORS["text_primary"][mode],
        "xtick.color":        COLORS["text_secondary"][mode],
        "ytick.color":        COLORS["text_secondary"][mode],
        "legend.facecolor":   "#FFFFFF" if mode == 0 else COLORS["bg_secondary"][mode],
        "legend.edgecolor":   COLORS["border"][mode],
        "legend.labelcolor":  COLORS["text_primary"][mode],
        "font.family":        "sans-serif",
        "font.sans-serif":    [_SANS, "Arial", "Helvetica"],
        "font.size":          11,
    }
    
    for key, val in style.items():
        mpl.rcParams[key] = val


def apply_mpl_light_theme():
    """Always apply clean white/light theme to matplotlib."""
    apply_mpl_theme(force_mode="light")

def update_theme_from_settings(settings):
    """Update global colors and fonts based on user settings."""
    # Update Accent Color
    preset_colors = {
        "Blue": ("#007AFF", "#0A84FF"),
        "Purple": ("#AF52DE", "#BF5AF2"),
        "Green": ("#34C759", "#30D158"),
        "Orange": ("#FF9500", "#FF9F0A"),
        "Red": ("#FF3B30", "#FF453A")
    }
    accent_name = settings.get("appearance", {}).get("accent_color", "Blue")
    if accent_name in preset_colors:
        COLORS["accent"] = preset_colors[accent_name]
        
    # Update Font Scale
    try:
        raw_scale = str(settings.get("appearance", {}).get("font_scale", "1.0")).rstrip("x")
        scale = float(raw_scale)
    except (ValueError, TypeError):
        scale = 1.0
        
    for key, val in BASE_FONTS.items():
        if len(val) == 2:
            FONTS[key] = (val[0], max(1, int(val[1] * scale)))
        elif len(val) == 3:
            FONTS[key] = (val[0], max(1, int(val[1] * scale)), val[2])


_EMOJI_CACHE = {}

def get_colored_emoji_icon(emoji: str, size: int = 22):
    """Render a vibrant full-color emoji as a CTkImage using Windows Segoe UI Emoji."""
    from PIL import Image, ImageDraw, ImageFont
    import customtkinter as ctk
    cache_key = (emoji, size)
    if cache_key in _EMOJI_CACHE:
        return _EMOJI_CACHE[cache_key]

    render_size = size * 2  # 2x for crisp rendering
    img = Image.new("RGBA", (render_size, render_size), (0, 0, 0, 0))
    try:
        font = ImageFont.truetype("seguiemj.ttf", int(render_size * 0.72))
        draw = ImageDraw.Draw(img)
        draw.text((int(render_size * 0.14), int(render_size * 0.08)), emoji, font=font, embedded_color=True)
    except Exception:
        pass

    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    _EMOJI_CACHE[cache_key] = ctk_img
    return ctk_img


_LINE_SAMPLE_CACHE = {}

def get_line_sample_icon(color, dark_color=None, style: str = "solid", width: int = 34, height: int = 14, stroke: int = 3):
    """Render a crisp sample line (solid, dashed, or dotted) as a CTkImage for legends."""
    import customtkinter as ctk
    from PIL import Image, ImageDraw

    if isinstance(color, tuple):
        light_c, dark_c = color[0], color[1]
    elif dark_color is not None:
        light_c, dark_c = color, dark_color
    else:
        light_c, dark_c = color, color

    cache_key = (light_c, dark_c, style, width, height, stroke)
    if cache_key in _LINE_SAMPLE_CACHE:
        return _LINE_SAMPLE_CACHE[cache_key]

    def _draw_line_img(col):
        scale = 2  # 2x for sharp rendering
        w, h = width * scale, height * scale
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        y = h // 2
        sw = max(2, stroke * scale)

        if style == "solid":
            draw.line([(0, y), (w, y)], fill=col, width=sw)
        elif style == "dashed":
            dash_len = 8 * scale
            gap_len = 5 * scale
            x = 0
            while x < w:
                draw.line([(x, y), (min(x + dash_len, w), y)], fill=col, width=sw)
                x += dash_len + gap_len
        elif style == "dotted":
            dot_d = max(3, int(sw * 0.9))
            gap = 3 * scale
            step = dot_d + gap
            x = dot_d // 2 + 1
            while x + dot_d // 2 <= w:
                draw.ellipse([(x - dot_d // 2, y - dot_d // 2), (x + dot_d // 2, y + dot_d // 2)], fill=col)
                x += step
        else:
            draw.line([(0, y), (w, y)], fill=col, width=sw)
        return img

    light_img = _draw_line_img(light_c)
    dark_img = _draw_line_img(dark_c)
    ctk_img = ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=(width, height))
    _LINE_SAMPLE_CACHE[cache_key] = ctk_img
    return ctk_img



