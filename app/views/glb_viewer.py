"""
Visualize Morphogenerator – interactive 3-D GLB viewer.

Rendering backend: pure Python / PIL software rasterizer.
  - No OpenGL, no browser, no GPU required.
  - Scroll wheel  → zoom
  - Left drag     → rotate
  - Right drag    → pan
  - Meshes are decimated to ~12 000 faces for interactive frame rates.
  - Loaded meshes are cached; switching N / streamline is instant on revisit.

File naming convention (inside the .glb/ folder):
  N{n}.glb    – morphogenerator WITH  streamline, n blades
  N{n}_0.glb  – morphogenerator WITHOUT streamline, n blades
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from typing import Optional, Tuple

import customtkinter as ctk
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk

from app.theme import (
    COLORS, FONTS, PAD_SM, PAD_MD, PAD_LG,
    CORNER_RADIUS, CORNER_RADIUS_SM, get_color,
)
from app.core import image_loader
import app.i18n as i18n

import sys

# Path helpers

def _glb_folder() -> Path:
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass and (Path(meipass) / ".glb").is_dir():
            return Path(meipass) / ".glb"
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / ".glb").is_dir():
            return exe_dir / ".glb"
        if meipass:
            return Path(meipass) / ".glb"
    here = Path(__file__).resolve()
    for parent in [here.parent, here.parent.parent,
                   here.parent.parent.parent, here.parent.parent.parent.parent]:
        candidate = parent / ".glb"
        if candidate.is_dir():
            return candidate
    return Path(__file__).resolve().parents[2] / ".glb"


def _discover_blades(folder: Path) -> list[int]:
    """Blade counts that have a WITH-streamline file (N{n}.glb)."""
    blades = set()
    for f in folder.glob("N*.glb"):
        stem = f.stem
        if "_0" not in stem:
            try:
                blades.add(int(stem[1:]))
            except ValueError:
                pass
    return sorted(blades)


def _glb_path(folder: Path, n: int) -> Optional[Path]:
    candidate = folder / f"N{n}.glb"
    return candidate if candidate.exists() else None


# Mesh cache

_MESH_CACHE: dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
_MESH_LOCK = threading.Lock()
_TARGET_FACES = 12_000   # faces kept after decimation


def _load_mesh(path: Path):
    """
    Load a GLB file, decimate to _TARGET_FACES, centre+scale to unit sphere.
    Returns (vertices (N,3), faces (M,3), face_normals (M,3)) as float32.
    Raises on error.
    """
    import trimesh

    key = str(path)
    with _MESH_LOCK:
        if key in _MESH_CACHE:
            return _MESH_CACHE[key]

    raw = trimesh.load(str(path), force="scene")
    meshes: list[trimesh.Trimesh] = []
    if isinstance(raw, trimesh.Scene):
        for g in raw.geometry.values():
            if isinstance(g, trimesh.Trimesh):
                meshes.append(g)
    elif isinstance(raw, trimesh.Trimesh):
        meshes.append(raw)

    if not meshes:
        raise ValueError("No mesh geometry found in file.")

    try:
        mesh = trimesh.util.concatenate(meshes)
    except Exception:
        mesh = meshes[0]

    # Decimate if too large
    n_faces = len(mesh.faces)
    if n_faces > _TARGET_FACES:
        try:
            mesh = mesh.simplify_quadric_decimation(_TARGET_FACES)
        except Exception:
            # Fallback: uniform sub-sampling
            step = max(1, n_faces // _TARGET_FACES)
            sub_faces = mesh.faces[::step]
            mesh = trimesh.Trimesh(vertices=mesh.vertices, faces=sub_faces,
                                   process=False)

    mesh.merge_vertices()

    # Feature edge detection
    faces = mesh.faces.astype(np.int32)
    face_edge_flags = np.zeros((len(faces), 3), dtype=bool)
    try:
        angles = mesh.face_adjacency_angles
        adj_edges = mesh.face_adjacency_edges
        sharp = adj_edges[angles > np.radians(20)]
        bounds = mesh.edges_unique[mesh.edges_unique_length == 1]
        feat_edges = np.vstack((sharp, bounds)) if len(bounds) > 0 else sharp
        
        feat_set = {tuple(sorted(e)) for e in feat_edges}
        for i, f in enumerate(faces):
            e0, e1, e2 = tuple(sorted((f[0], f[1]))), tuple(sorted((f[1], f[2]))), tuple(sorted((f[2], f[0])))
            if e0 in feat_set: face_edge_flags[i, 0] = True
            if e1 in feat_set: face_edge_flags[i, 1] = True
            if e2 in feat_set: face_edge_flags[i, 2] = True
    except Exception:
        pass

    # Normals are computed on first access in trimesh 4.x
    normals = mesh.face_normals.astype(np.float32)

    # Centre and normalise to unit bounding box diagonal
    verts = mesh.vertices.astype(np.float32)
    mn, mx = verts.min(0), verts.max(0)
    centre = (mn + mx) / 2.0
    scale  = float(np.linalg.norm(mx - mn)) or 1.0
    verts  = (verts - centre) / scale

    # Walls (outer casing) mask: faces near the convex-hull surface.
    # Drives the Display "Show Walls (Casing)" toggle.
    wall_mask = np.zeros(len(faces), dtype=bool)
    try:
        hm = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
        hull = hm.convex_hull
        hv = hull.vertices
        hf = hull.faces
        hn = np.cross(hv[hf[:, 1]] - hv[hf[:, 0]],
                      hv[hf[:, 2]] - hv[hf[:, 0]])
        hn /= np.linalg.norm(hn, axis=1, keepdims=True)
        cks = np.einsum("ij,ij->i", hn, hv[hf[:, 0]])
        t0 = verts[faces[:, 0]]; t1 = verts[faces[:, 1]]; t2 = verts[faces[:, 2]]
        cent = (t0 + t1 + t2) / 3.0
        d = np.clip((cks[:, None] - hn @ cent.T).min(axis=0), 0.0, None)
        area = 0.5 * np.linalg.norm(np.cross(t1 - t0, t2 - t0), axis=1)
        med = float(np.median(area))
        wall_mask = (d < 0.012) & (area > 2.0 * med)
    except Exception:
        wall_mask = np.zeros(len(faces), dtype=bool)

    result = (verts, faces, normals, face_edge_flags, wall_mask)
    with _MESH_LOCK:
        _MESH_CACHE[key] = result
    return result


# Interactive 3-D viewport

class _Viewport(tk.Frame):
    """
    Tkinter frame containing a PIL-rendered interactive 3-D view.

    Controls
    --------
    Left-drag   → rotate (azimuth + elevation)
    Right-drag  → pan
    Scroll      → zoom
    """

    def __init__(self, master, on_status=None, **kwargs):
        bg = kwargs.pop("bg", "#191919")
        super().__init__(master, bg=bg, **kwargs)
        self._on_status = on_status   # callable(str)

        self._canvas = tk.Canvas(
            self, bg="#191919", highlightthickness=0, cursor="fleur",
        )
        self._canvas.pack(fill="both", expand=True)

        # View parameters
        self._azimuth   = -30.0
        self._elevation =  20.0
        self._zoom      =   1.0
        self._pan_x     =   0.0
        self._pan_y     =   0.0
        self._bg        = "#191919"
        self._show_edges = True
        self._exposure  = 1.0
        self._opacity   = 1.0
        self._cad_color = np.array([0.20, 0.50, 0.90], dtype=np.float32)
        
        self._clip_enabled = False
        self._clip_axis    = "Z"
        self._clip_z       = 0.0
        self._clip_keep    = "Top"

        # second clip plane (quick-view presets can need two at once)
        self._clip2_enabled = False
        self._clip2_axis    = "Y"
        self._clip2_z       = 0.0
        self._clip2_keep    = "Top"
        self._wall_mask      = None
        self._show_walls     = True

        # background image cache (key, image)
        self._bg_img_cache = None

        # Mesh data (set by load_async)
        self._verts:   Optional[np.ndarray] = None
        self._faces:   Optional[np.ndarray] = None
        self._normals: Optional[np.ndarray] = None
        self._face_edge_flags: Optional[np.ndarray] = None
        self._fname    = ""

        # Interaction
        self._drag_xy  = None
        self._drag_btn = None
        self._photo    = None          # keep reference to avoid GC
        self._render_pending = False
        self._loading  = False

        # Bind mouse events
        c = self._canvas
        c.bind("<ButtonPress-1>",   self._press)
        c.bind("<ButtonPress-3>",   self._press)
        c.bind("<B1-Motion>",       self._drag)
        c.bind("<B3-Motion>",       self._drag)
        c.bind("<ButtonRelease-1>", self._release)
        c.bind("<ButtonRelease-3>", self._release)
        c.bind("<MouseWheel>",      self._scroll)
        c.bind("<Configure>",       lambda _e: self._schedule_render())

    # Public API

    def load_async(self, path: Optional[Path]):
        """Load *path* in a background thread; update viewport when done."""
        if path is None or not path.exists():
            self._verts = None
            self._set_status("No model file found.")
            self._draw_placeholder("No file found.")
            return

        self._loading = True
        size_mb = path.stat().st_size / 1e6
        self._set_status(f"Loading {path.name}  ({size_mb:.1f} MB)…")
        self._draw_placeholder(f"Loading {path.name}…")

        def worker():
            try:
                result = _load_mesh(path)
            except Exception as exc:
                # NB: the message must be captured HERE, in the except block.
                # On Python 3.13+ the exception variable is disassociated from
                # its value once the handler ends, so a deferred closure that
                # reads `exc` raises NameError (this used to swallow every
                # load error and leave the viewport stuck on "Loading ...").
                self.after(0, self._report_error, (str(exc),))
            else:
                self.after(0, self._report_loaded, (result, path.name))

        threading.Thread(target=worker, daemon=True).start()

    def set_options(
        self, bg: str = "#191919", show_edges: bool = True,
        exposure: float = 1.0, cad_color: str = "#3380E6",
        opacity: float = 1.0, clip_enabled: bool = False,
        clip_axis: str = "Z", clip_z: float = 0.0, clip_keep: str = "Top",
        clip2_enabled: bool = False, clip2_axis: str = "Y",
        clip2_z: float = 0.0, clip2_keep: str = "Top",
        show_walls: bool = True,
    ):
        self._bg = bg
        self._show_edges = show_edges
        self._exposure = exposure
        self._opacity = opacity
        self._clip_enabled = clip_enabled
        self._clip_axis = clip_axis
        self._clip_z = clip_z
        self._clip_keep = clip_keep
        self._clip2_enabled = clip2_enabled
        self._clip2_axis = clip2_axis
        self._clip2_z = clip2_z
        self._clip2_keep = clip2_keep
        self._show_walls = bool(show_walls)
        self._bg_img_cache = None
        
        c = cad_color.lstrip("#")
        if len(c) == 6:
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            self._cad_color = np.array([r/255.0, g/255.0, b/255.0], dtype=np.float32)

        self._canvas.configure(bg=bg)
        self._schedule_render()

    # Internal loading callbacks

    def _on_loaded(self, verts, faces, normals, edge_flags, wall_mask, fname):
        self._verts   = verts
        self._faces   = faces
        self._normals = normals
        self._face_edge_flags = edge_flags
        self._wall_mask = wall_mask
        self._fname   = fname
        self._loading = False
        self._set_status(
            f"{fname}  ·  {len(faces):,} faces  "
            f"│  Scroll=Zoom  Left=Rotate  Right=Pan"
        )
        self._schedule_render()

    def _on_error(self, msg):
        self._loading = False
        self._set_status(f"Error: {msg}")
        self._draw_placeholder(f"⚠  {msg}", color="#E08080", size=14)

    def _report_loaded(self, payload):
        """Main-thread callback queued by the loader thread."""
        result, fname = payload
        self._on_loaded(result[0], result[1], result[2], result[3], result[4], fname)

    def _report_error(self, payload):
        """Main-thread callback queued by the loader thread."""
        msg = payload[0]
        if "No module named" in msg:
            mod = msg.split("No module named")[-1].strip().strip("'\"")
            msg = f"{msg}   (fix with:  pip install {mod.split('.')[0]})"
        self._on_error(msg)

    # Rotation matrix

    def _rotation_matrix(self) -> np.ndarray:
        az = np.radians(self._azimuth)
        el = np.radians(self._elevation)
        ca, sa = float(np.cos(az)), float(np.sin(az))
        ce, se = float(np.cos(el)), float(np.sin(el))
        Ry = np.array([[ca, 0, sa], [0, 1, 0], [-sa, 0, ca]], dtype=np.float32)
        Rx = np.array([[1, 0, 0], [0, ce, -se], [0, se, ce]], dtype=np.float32)
        return Rx @ Ry

    # Rendering

    def _schedule_render(self):
        if not self._render_pending:
            self._render_pending = True
            self.after(1, self._do_render)   # ~60 fps cap

    def _do_render(self):
        self._render_pending = False
        if self._verts is None:
            return
        self._render_frame()

    def _render_frame(self):
        full_w = self._canvas.winfo_width()
        full_h = self._canvas.winfo_height()
        if full_w < 4 or full_h < 4:
            return

        # While the mouse is dragging, render at a fraction of the
        # resolution (PIL upscales before display) so the frame loop
        # stays responsive; when idle the full-detail pass replaces it.
        scale = 1   # always native resolution: crisp while rotating
        W = (full_w + scale - 1) // scale
        H = (full_h + scale - 1) // scale
        show_edges = self._show_edges

        R = self._rotation_matrix()
        v = self._verts  @ R.T   # (N, 3) rotated vertices
        n = self._normals @ R.T  # (M, 3) rotated face normals

        # Perspective projection
        z_eye  = 2.0 / self._zoom
        z_cam  = v[:, 2] + z_eye
        z_cam  = np.where(z_cam < 1e-4, 1e-4, z_cam)
        fov_scale = (W / 2.0) / 0.6              # field-of-view factor
        cx = W / 2.0 + self._pan_x
        cy = H / 2.0 + self._pan_y

        x2 = v[:, 0] / z_cam * fov_scale + cx   # (N,)
        y2 = -v[:, 1] / z_cam * fov_scale + cy  # (N,)

        # Depth + back-face cull
        f0, f1, f2 = self._faces[:, 0], self._faces[:, 1], self._faces[:, 2]
        face_z  = (z_cam[f0] + z_cam[f1] + z_cam[f2]) / 3.0

        vis_mask = n[:, 2] < 0.1           # front-facing faces
        if not self._show_walls and self._wall_mask is not None:
            vis_mask = vis_mask & ~self._wall_mask
        
        if self._clip_enabled:
            axis_idx = 0 if self._clip_axis == "X" else (1 if self._clip_axis == "Y" else 2)
            orig_c = self._verts[:, axis_idx]
            face_orig_c = (orig_c[f0] + orig_c[f1] + orig_c[f2]) / 3.0
            if self._clip_keep == "Top":
                vis_mask = vis_mask & (face_orig_c >= self._clip_z)
            else:
                vis_mask = vis_mask & (face_orig_c <= self._clip_z)

        if self._clip2_enabled:
            axis_idx2 = (0 if self._clip2_axis == "X"
                         else 1 if self._clip2_axis == "Y" else 2)
            orig_c2 = self._verts[:, axis_idx2]
            face_orig_c2 = (orig_c2[f0] + orig_c2[f1] + orig_c2[f2]) / 3.0
            if self._clip2_keep == "Top":
                vis_mask = vis_mask & (face_orig_c2 >= self._clip2_z)
            else:
                vis_mask = vis_mask & (face_orig_c2 <= self._clip2_z)

        vis_idx  = np.where(vis_mask)[0]
        order    = vis_idx[np.argsort(-face_z[vis_idx])]   # back→front

        # Diffuse shading
        key_dir  = np.array([ 0.4,  0.6,  1.0], dtype=np.float32)
        key_dir /= np.linalg.norm(key_dir)
        fill_dir = np.array([-0.5,  0.3,  0.5], dtype=np.float32)
        fill_dir /= np.linalg.norm(fill_dir)
        back_dir = np.array([ 0.0, -0.2, -1.0], dtype=np.float32)
        back_dir /= np.linalg.norm(back_dir)

        kd = np.clip(n @ key_dir,  0, 1)    # (M,)
        fd = np.clip(n @ fill_dir, 0, 1)    # (M,)
        bd = np.clip(n @ back_dir, 0, 1)    # (M,)
        
        ambient = 0.25
        brightness = (ambient + kd * 0.9 + fd * 0.4 + bd * 0.3) * self._exposure
        brightness = np.clip(brightness, 0, 1)

        col = (self._cad_color[None, :] * brightness[:, None]).clip(0, 1)
        col_u8 = (col * 255).astype(np.uint8)   # (M, 3)

        # Pre-fetch vertex coords for draw loop
        ox0 = x2[f0[order]];  oy0 = y2[f0[order]]
        ox1 = x2[f1[order]];  oy1 = y2[f1[order]]
        ox2 = x2[f2[order]];  oy2 = y2[f2[order]]
        or_  = col_u8[order, 0]
        og_  = col_u8[order, 1]
        ob_  = col_u8[order, 2]

        # Draw
        if self._opacity < 0.99:
            img = self._bg_image(W, H, "RGBA")
            draw = ImageDraw.Draw(img, "RGBA")
            alpha = int(self._opacity * 255)
        else:
            img = self._bg_image(W, H, "RGB")
            draw = ImageDraw.Draw(img)
            alpha = 255

        if show_edges and self._face_edge_flags is not None:
            out_r = int(self._cad_color[0] * 255 * 0.4)
            out_g = int(self._cad_color[1] * 255 * 0.4)
            out_b = int(self._cad_color[2] * 255 * 0.4)
            out_col = (out_r, out_g, out_b, max(alpha, 100))
            
            flags_ordered = self._face_edge_flags[order]

            for i in range(len(order)):
                p0 = (float(ox0[i]), float(oy0[i]))
                p1 = (float(ox1[i]), float(oy1[i]))
                p2 = (float(ox2[i]), float(oy2[i]))
                
                draw.polygon([p0, p1, p2], fill=(int(or_[i]), int(og_[i]), int(ob_[i]), alpha))
                
                f_flags = flags_ordered[i]
                if f_flags[0]: draw.line([p0, p1], fill=out_col, width=1)
                if f_flags[1]: draw.line([p1, p2], fill=out_col, width=1)
                if f_flags[2]: draw.line([p2, p0], fill=out_col, width=1)
        else:
            for i in range(len(order)):
                pts = [
                    (float(ox0[i]), float(oy0[i])),
                    (float(ox1[i]), float(oy1[i])),
                    (float(ox2[i]), float(oy2[i])),
                ]
                draw.polygon(pts, fill=(int(or_[i]), int(og_[i]), int(ob_[i]), alpha))

        if self._opacity < 0.99:
            bg_img = self._bg_image(W, H, "RGB")
            bg_img.paste(img, (0, 0), img)
            img = bg_img

        if scale > 1:
            img = img.resize((full_w, full_h), Image.BILINEAR)

        photo = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=photo)
        self._photo = photo

    def _bg_image(self, W: int, H: int, mode: str = "RGB") -> Image.Image:
        """Soft vertical gradient derived from the current background color
        (lighter on top, a touch deeper at the bottom) instead of a flat
        fill. A clean master is cached per size/mode/color; every caller
        gets its own private copy."""
        key = (W, H, mode, self._bg)
        if self._bg_img_cache is not None and self._bg_img_cache[0] == key:
            return self._bg_img_cache[1].copy()   # private copy: callers draw on it
        try:
            c = self._bg.lstrip("#")
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        except Exception:
            img = Image.new(mode, (W, H), self._bg)
            self._bg_img_cache = (key, img)
            return img.copy()
        top = np.array([min(255, r + 26), min(255, g + 26), min(255, b + 26)],
                       dtype=np.float32)
        bot = np.array([max(0, r - 38), max(0, g - 38), max(0, b - 38)],
                       dtype=np.float32)
        mix = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None]
        rows = (top[None, :] * (1.0 - mix) + bot[None, :] * mix).astype(np.uint8)
        arr = np.broadcast_to(rows[:, None, :], (H, W, 3)).copy()   # (H, W, 3)
        if mode == "RGBA":
            arr = np.dstack([arr, np.full((H, W), 255, dtype=np.uint8)])
        img = Image.fromarray(arr, mode)
        self._bg_img_cache = (key, img)
        return img.copy()   # keep the cached master pristine

    def _draw_placeholder(self, msg: str, color: str = "#555555", size: int = 13):
        W = max(self._canvas.winfo_width(),  400)
        H = max(self._canvas.winfo_height(), 300)
        img = self._bg_image(W, H, "RGB")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("segoeui.ttf", int(size))
        except Exception:
            font = ImageFont.load_default()
        # naive word-wrap so long error messages stay inside the canvas
        max_chars = max(8, int((W - 80) / (size * 0.6)))
        lines, cur = [], ""
        for word in msg.split():
            t = (cur + " " + word).strip()
            if len(t) > max_chars and cur:
                lines.append(cur); cur = word
            else:
                cur = t
        if cur:
            lines.append(cur)
        y0 = H // 2 - 8 * len(lines)
        for i, line in enumerate(lines):
            draw.text((W // 2, y0 + i * (size + 6)), line,
                      fill=color, anchor="mm", font=font)
        photo = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=photo)
        self._photo = photo

    # Mouse callbacks

    def _press(self, event):
        self._drag_xy  = (event.x, event.y)
        self._drag_btn = event.num

    def _drag(self, event):
        if self._drag_xy is None:
            return
        dx = event.x - self._drag_xy[0]
        dy = event.y - self._drag_xy[1]
        self._drag_xy = (event.x, event.y)
        if self._drag_btn == 1:                              # left → rotate
            self._azimuth   += dx * 0.40
            self._elevation  = max(-88.0, min(88.0, self._elevation + dy * 0.40))
        elif self._drag_btn == 3:                            # right → pan
            self._pan_x += dx
            self._pan_y += dy
        self._schedule_render()

    def _release(self, event):
        self._drag_xy = None

    def _scroll(self, event):
        factor = 1.10 if event.delta > 0 else 0.909
        self._zoom = max(0.05, min(40.0, self._zoom * factor))
        self._schedule_render()

    def _set_status(self, msg: str):
        if self._on_status:
            self._on_status(msg)


# Small UI helpers

def _section_label(parent, text: str):
    ctk.CTkLabel(
        parent, text=f"  {text}",
        font=FONTS["subheading"], text_color=COLORS["text_secondary"], anchor="w",
    ).pack(fill="x", padx=PAD_SM, pady=(PAD_MD, 2))
    ctk.CTkFrame(parent, fg_color=COLORS["separator"], height=1).pack(
        fill="x", padx=PAD_LG, pady=(0, PAD_SM),
    )


def _row(parent) -> ctk.CTkFrame:
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=PAD_LG, pady=2)
    # label on the left, control pushed to the right edge of the card
    row.grid_columnconfigure(0, weight=1)
    row.grid_columnconfigure(1, weight=0)
    return row


def _prop_label(parent, text: str):
    ctk.CTkLabel(
        parent, text=text,
        font=FONTS["body"], text_color=COLORS["text_secondary"], anchor="w",
    ).grid(row=0, column=0, sticky="w", padx=(0, PAD_SM))


# Main view

class GLBViewerView(ctk.CTkFrame):
    """
    Full-screen interactive 3-D GLB viewer.

    Left  : software-rendered interactive 3-D viewport.
    Right : display / lighting settings panel.
    """

    # Quick-view clip presets (applied simultaneously):
    # preset name -> list of (axis, keep, normalized_height) clip planes
    PRESET_NAMES = ("Blades", "Distribution Chamber", "Nozzle", "Morphogenerator")
    PRESET_PLANES = {
        "Blades": [("Y", "Top", -0.20), ("Y", "Bottom", 0.02)],
        "Distribution Chamber": [("Y", "Top", 0.02), ("Y", "Bottom", 0.18)],
        "Nozzle": [("Y", "Bottom", -0.20)],
        "Morphogenerator": [],
    }

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)

        # Discover GLB files
        self._glb_folder   = _glb_folder()
        self._blades_sl    = _discover_blades(self._glb_folder)
        if not self._blades_sl:    self._blades_sl    = [2, 3, 4, 5, 6]

        # State variables
        self._n_blades    = ctk.IntVar(value=self._blades_sl[0])

        # Display settings
        self._show_edges     = ctk.BooleanVar(value=True)
        self._show_walls   = ctk.BooleanVar(value=True)
        self._clip_enabled   = ctk.BooleanVar(value=False)
        self._clip_axis      = ctk.StringVar(value="Z")
        self._clip_z         = ctk.DoubleVar(value=0.0)
        self._clip_keep      = ctk.StringVar(value="Top")
        
        self._bg_color_name  = ctk.StringVar(value="Light Gray")
        self._cad_color_name = ctk.StringVar(value="Steel")
        
        self._bg_custom_hex  = "#E0E0E0"
        self._cad_custom_hex = "#A0A0A0"
        
        self._bg_map = {
            "Dark Gray": "#191919", "Light Gray": "#E0E0E0", "White": "#FFFFFF",
            "Slate Blue": "#1E293B", "Dark Navy": "#0F172A", "Custom...": ""
        }
        self._cad_map = {
            "Blue": "#3380E6", "Red": "#E63333", "Green": "#33E65C", 
            "Gold": "#E6B833", "Purple": "#9933E6", "Steel": "#A0A0A0", "Custom...": ""
        }

        # Lighting settings
        self._exposure       = ctk.DoubleVar(value=1.6)
        self._opacity        = ctk.DoubleVar(value=1.0)

        # Layout
        # Column 0 : 3-D viewport (full height, grows with the window)
        # Column 1 : thin drag-grip to resize the cards (hover → sizing cursor)
        # Column 2 : blade selector + Display/Clipping/Lighting cards
        self._COL_VIEWER = 0
        self._COL_GRIP   = 1
        self._COL_CARD   = 2
        self._CARD_WIDTH_MIN = 210
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=8)
        self.grid_columnconfigure(2, weight=0, minsize=270)
        self.grid_rowconfigure(1, weight=1)
        self._panel_resized_w: Optional[int] = None

        self._build_blade_selector()
        self._build_viewer()
        self._build_settings_panel()
        self._build_card_grip()

        # Load initial model after UI is ready
        self.after(100, self._reload_model)

    # Blade selector (top of the right column)

    def _build_blade_selector(self):
        """Blade-count selector, placed above the Display/Clipping/Lighting
        column so it stays grouped with the viewer settings."""
        frame = ctk.CTkFrame(
            self, fg_color=COLORS["bg_secondary"], corner_radius=CORNER_RADIUS,
        )
        frame.grid(row=0, column=self._COL_CARD, sticky="ew",
                   padx=(4, PAD_LG), pady=(PAD_SM, PAD_SM // 2))

        # Header row: section title + help button
        head = ctk.CTkFrame(frame, fg_color="transparent")
        head.pack(fill="x", padx=PAD_MD, pady=(PAD_MD, 0))
        ctk.CTkLabel(
            head, text="Select Number of Blades",
            font=FONTS["heading"], text_color=COLORS["text_primary"],
        ).pack(side="left")
        ctk.CTkButton(
            head, text=i18n.t("btn_help"), font=FONTS["body"],
            fg_color=COLORS["bg_tertiary"], hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"], width=80,
            command=self._show_info_modal,
        ).pack(side="right", padx=(PAD_SM, 0))

        # Quick views: named clip presets for the selected geometry
        _section_label(frame, "Quick Views")
        self._preset = ctk.StringVar(value="Morphogenerator")
        self._preset_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._preset_frame.pack(fill="x", padx=PAD_MD, pady=(0, PAD_MD))
        _row = 0
        for name in self.PRESET_NAMES:
            ctk.CTkRadioButton(
                self._preset_frame, text=name,
                variable=self._preset, value=name,
                font=FONTS["body"], text_color=COLORS["text_primary"],
                fg_color=COLORS["accent"], border_color=COLORS["border"],
                hover_color=COLORS["accent_hover"], width=26,
                command=self._preset_changed,
            ).grid(row=_row, column=0, sticky="w", pady=1)
            _row += 1
            if name == "Blades":
                # blade count nested as a sub-paragraph under the Blades view
                sub = ctk.CTkFrame(self._preset_frame, fg_color="transparent")
                sub.grid(row=_row, column=0, sticky="w", padx=(30, 4), pady=(0, PAD_SM))
                ctk.CTkLabel(
                    sub, text="N :", font=FONTS["caption"],
                    text_color=COLORS["text_secondary"],
                ).pack(side="left")
                self._radio_frame = ctk.CTkFrame(sub, fg_color="transparent")
                self._radio_frame.pack(side="left", padx=(4, 0))
                self._rebuild_blade_radios()
                _row += 1

    def _rebuild_blade_radios(self):
        for w in self._radio_frame.winfo_children():
            w.destroy()
        blades = self._blades_sl
        if self._n_blades.get() not in blades:
            self._n_blades.set(blades[0] if blades else 2)
        for col, n in enumerate(blades):
            ctk.CTkRadioButton(
                self._radio_frame, text=str(n),
                variable=self._n_blades, value=n,
                font=FONTS["caption"], text_color=COLORS["text_primary"],
                fg_color=COLORS["accent"], border_color=COLORS["border"],
                hover_color=COLORS["accent_hover"],
                width=34,            # default 100 px balloons the whole card
                command=self._on_blade_change,
            ).grid(row=0, column=col, padx=(0, PAD_SM))

    # Viewer

    def _build_viewer(self):
        viewer_frame = ctk.CTkFrame(
            self, fg_color=COLORS["bg_secondary"], corner_radius=CORNER_RADIUS,
        )
        viewer_frame.grid(row=0, column=0, rowspan=2, sticky="nsew",
                          padx=(PAD_LG, PAD_SM // 2), pady=(PAD_SM, PAD_LG))
        viewer_frame.grid_rowconfigure(0, weight=1)
        viewer_frame.grid_columnconfigure(0, weight=1)

        self._viewport = _Viewport(
            viewer_frame,
            on_status=self._set_status,
            bg="#191919",
        )
        self._viewport.grid(row=0, column=0, sticky="nsew",
                            padx=2, pady=(2, 0))

        self._status_var = ctk.StringVar(value="Loading…")
        ctk.CTkLabel(
            viewer_frame,
            textvariable=self._status_var,
            font=FONTS["caption"],
            text_color=COLORS["text_tertiary"],
        ).grid(row=1, column=0, pady=(0, PAD_SM))

        self._viewer_frame = viewer_frame

    def _set_status(self, msg: str):
        self._status_var.set(msg)

    # Settings panel

    def _build_settings_panel(self):
        panel = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg_secondary"], corner_radius=CORNER_RADIUS,
            scrollbar_button_color=COLORS["bg_tertiary"],
            scrollbar_button_hover_color=COLORS["accent"],
            label_text="",
        )
        panel.grid(row=1, column=self._COL_CARD, sticky="nsew",
                   padx=(4, PAD_LG), pady=(PAD_SM // 2, PAD_LG))
        panel.grid_columnconfigure(0, weight=1)
        self._settings_panel = panel

        def _make_section_card(title: str) -> ctk.CTkFrame:
            card = ctk.CTkFrame(
                panel, fg_color=COLORS["bg_primary"],
                corner_radius=CORNER_RADIUS_SM,
                border_width=1, border_color=COLORS["border"],
            )
            card.pack(fill="x", padx=PAD_SM, pady=(PAD_SM // 2, PAD_SM // 2))
            
            head = ctk.CTkFrame(card, fg_color="transparent")
            head.pack(fill="x", padx=PAD_MD, pady=(PAD_SM, 4))
            ctk.CTkLabel(
                head, text=title, font=FONTS["subheading"],
                text_color=COLORS["accent"], anchor="w",
            ).pack(side="left")
            return card

        # Display section
        disp_card = _make_section_card("Display")
        self._add_checkbox_row(disp_card, "Show Edges", self._show_edges)
        self._add_checkbox_row(disp_card, "Show Walls (Casing)", self._show_walls)

        # bgColor
        bc_row = _row(disp_card)
        _prop_label(bc_row, "Background")
        bc_inner = ctk.CTkFrame(bc_row, fg_color="transparent")
        bc_inner.grid(row=0, column=1, sticky="e")
        self._bg_swatch = ctk.CTkFrame(
            bc_inner, width=22, height=22,
            fg_color=self._bg_map["Light Gray"], corner_radius=4,
        )
        self._bg_swatch.pack(side="right", padx=(4, 0))
        
        ctk.CTkOptionMenu(
            bc_inner, variable=self._bg_color_name,
            values=list(self._bg_map.keys()),
            width=110, height=26, font=FONTS["mono_sm"],
            fg_color=COLORS["bg_tertiary"], button_color=COLORS["bg_hover"],
            button_hover_color=COLORS["accent"], text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["bg_hover"],
            dropdown_text_color=COLORS["text_primary"],
            corner_radius=CORNER_RADIUS_SM,
            command=self._on_color_change,
        ).pack(side="right")

        # cadColor
        cc_row = _row(disp_card)
        _prop_label(cc_row, "CAD Color")
        cc_inner = ctk.CTkFrame(cc_row, fg_color="transparent")
        cc_inner.grid(row=0, column=1, sticky="e")
        self._cad_swatch = ctk.CTkFrame(
            cc_inner, width=22, height=22,
            fg_color=self._cad_map["Steel"], corner_radius=4,
        )
        self._cad_swatch.pack(side="right", padx=(4, 0))
        
        ctk.CTkOptionMenu(
            cc_inner, variable=self._cad_color_name,
            values=list(self._cad_map.keys()),
            width=110, height=26, font=FONTS["mono_sm"],
            fg_color=COLORS["bg_tertiary"], button_color=COLORS["bg_hover"],
            button_hover_color=COLORS["accent"], text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["bg_hover"],
            dropdown_text_color=COLORS["text_primary"],
            corner_radius=CORNER_RADIUS_SM,
            command=self._on_color_change,
        ).pack(side="right")
        
        # opacity
        op_row = _row(disp_card)
        _prop_label(op_row, "Opacity")
        op_inner = ctk.CTkFrame(op_row, fg_color="transparent")
        op_inner.grid(row=0, column=1, sticky="e")
        self._op_val = ctk.CTkLabel(
            op_inner, text="100%",
            font=FONTS["mono_sm"], text_color=COLORS["accent"], width=35,
        )
        self._op_val.pack(side="right", padx=(2, 0))
        ctk.CTkSlider(
            op_inner, from_=0.1, to=1.0, number_of_steps=90, width=72,
            variable=self._opacity,
            button_color=COLORS["accent"], button_hover_color=COLORS["accent_hover"],
            progress_color=COLORS["accent"], fg_color=COLORS["bg_tertiary"],
            command=lambda v: (
                self._op_val.configure(text=f"{int(v*100)}%"),
                self._apply_display_options(),
            ),
        ).pack(side="right", pady=(0, PAD_SM))

        # Clipping section
        clip_card = _make_section_card("Clipping")
        
        self._add_checkbox_row(clip_card, "Enable Clipping", self._clip_enabled,
                               command=self._on_manual_clip)
        
        # clip axis
        ca_row = _row(clip_card)
        _prop_label(ca_row, "Axis")
        ctk.CTkSegmentedButton(
            ca_row, values=["X", "Y", "Z"],
            variable=self._clip_axis,
            command=self._on_manual_clip,
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["bg_tertiary"],
            unselected_hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=1, sticky="e")
        
        # clip keep direction
        clip_row = _row(clip_card)
        _prop_label(clip_row, "Keep")
        ctk.CTkSegmentedButton(
            clip_row, values=["Top", "Bottom"],
            variable=self._clip_keep,
            command=self._on_manual_clip,
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["bg_tertiary"],
            unselected_hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=1, sticky="e")
        
        # clip Z slider
        cz_row = _row(clip_card)
        _prop_label(cz_row, "Height")
        cz_inner = ctk.CTkFrame(cz_row, fg_color="transparent")
        cz_inner.grid(row=0, column=1, sticky="e")
        self._cz_val = ctk.CTkLabel(
            cz_inner, text="0.00",
            font=FONTS["mono_sm"], text_color=COLORS["accent"], width=35,
        )
        self._cz_val.pack(side="right", padx=(2, 0))
        ctk.CTkSlider(
            cz_inner, from_=-0.5, to=0.5, number_of_steps=100, width=80,
            variable=self._clip_z,
            button_color=COLORS["accent"], button_hover_color=COLORS["accent_hover"],
            progress_color=COLORS["accent"], fg_color=COLORS["bg_tertiary"],
            command=lambda v: (
                self._cz_val.configure(text=f"{v:.2f}"),
                self._on_manual_clip(),
            ),
        ).pack(side="right", pady=(0, PAD_SM))

        # Lighting section
        light_card = _make_section_card("Lighting")

        # exposure
        exp_row = _row(light_card)
        _prop_label(exp_row, "Brightness")
        exp_inner = ctk.CTkFrame(exp_row, fg_color="transparent")
        exp_inner.grid(row=0, column=1, sticky="e")
        self._exp_val = ctk.CTkLabel(
            exp_inner, text="1.0",
            font=FONTS["mono_sm"], text_color=COLORS["accent"], width=28,
        )
        self._exp_val.pack(side="right", padx=(2, 0))
        ctk.CTkSlider(
            exp_inner, from_=0.1, to=3.0, number_of_steps=29, width=72,
            variable=self._exposure,
            button_color=COLORS["accent"], button_hover_color=COLORS["accent_hover"],
            progress_color=COLORS["accent"], fg_color=COLORS["bg_tertiary"],
            command=lambda v: (
                self._exp_val.configure(text=f"{v:.1f}"),
                self._apply_display_options(),
            ),
        ).pack(side="right", pady=(0, PAD_SM))

        # Controls hint
        ctrl_card = _make_section_card("Controls")
        for hint in [
            "🖱  Scroll       → Zoom",
            "🖱  Left drag    → Rotate",
            "🖱  Right drag   → Pan",
        ]:
            ctk.CTkLabel(
                ctrl_card, text=hint, font=FONTS["caption"],
                text_color=COLORS["text_secondary"], anchor="w",
            ).pack(anchor="w", padx=PAD_MD, pady=(0, 4))


    # Card drag grip

    def _build_card_grip(self):
        """8-px strip between viewport and cards: hovering it turns the
        cursor into a resize grip; dragging left/right resizes the cards.
        The viewport (col 0, weight=1) absorbs the rest of the width."""
        # plain Tk frame: needs a *resolved* color (customtkinter pairs don't
        # work outside CTk widgets). Also probe for a cursor name this Tk
        # build actually supports as a horizontal resize grip.
        cursor = "sizing"
        for cand in ("sb_h_double_arrow", "sizing_w", "sizing_w_e", "sizing"):
            try:
                probe = tk.Frame(self, width=1, cursor=cand)
                probe.destroy()
                cursor = cand
                break
            except tk.TclError:
                continue
        strip = tk.Frame(
            self, width=8, bg=get_color("bg_primary"),
            cursor=cursor, highlightthickness=0,
        )
        strip.grid(row=0, column=self._COL_GRIP, rowspan=2, sticky="ns")
        # faint seam so the handle is discoverable
        tk.Frame(strip, width=2, bg=get_color("separator")).place(
            relx=0.5, rely=0.5, anchor="center")
        strip.bind("<ButtonPress-1>", self._card_resize_start)
        strip.bind("<B1-Motion>",     self._card_resize_drag)
        self._card_grip = strip

    def _card_resize_start(self, event):
        self._resize_x0 = event.x_root
        self._resize_w0 = (self._panel_resized_w
                           if self._panel_resized_w is not None
                           else max(self._settings_panel.winfo_width(), 100))

    def _card_resize_drag(self, event):
        if not hasattr(self, "_resize_x0"):
            return
        # drag pointer to the left → cards grow wider (viewport shrinks)
        new_w = (self._resize_w0 or 270) + (self._resize_x0 - event.x_root)
        hi = max(self._CARD_WIDTH_MIN, self.winfo_width() - 480)
        new_w = max(self._CARD_WIDTH_MIN, min(hi, new_w))
        self._set_card_width(int(new_w))

    def _set_card_width(self, w: int):
        self._panel_resized_w = w
        # Tk grid has no maxsize: the column settles at max(minsize, content
        # width). So dragging wider grows the cards, and dragging back nar
        # collapses them to exactly the space their content occupies.
        self.grid_columnconfigure(self._COL_CARD, minsize=int(w))

    # Row helpers

    def _add_checkbox_row(self, parent, label: str, var: ctk.BooleanVar, command=None):
        row = _row(parent)
        _prop_label(row, label)
        ctk.CTkCheckBox(
            row, text="", variable=var, onvalue=True, offvalue=False,
            width=22, height=22, fg_color=COLORS["accent"],
            border_color=COLORS["border"], hover_color=COLORS["accent_hover"],
            corner_radius=4, command=(command or self._apply_display_options),
        ).grid(row=0, column=1, sticky="e", padx=(0, PAD_SM))

    # Quick views + manual clip wiring

    def _preset_changed(self, *_):
        """Apply the clip planes of the selected quick view, and keep the
        manual clip controls in sync with its first plane."""
        planes = self.PRESET_PLANES.get(self._preset.get(), [])
        c1 = planes[0] if planes else None
        if c1 is not None:
            self._clip_enabled.set(True)
            self._clip_axis.set(c1[0])
            self._clip_keep.set(c1[1])
            self._clip_z.set(c1[2])
            self._cz_val.configure(text=f"{c1[2]:.2f}")
        else:
            self._clip_enabled.set(False)
        self._apply_display_options()

    def _on_manual_clip(self, *_):
        """User touched the manual clip controls: void the quick-view preset
        and apply the single plane the user just configured."""
        if self._preset.get() != "Morphogenerator":
            self._preset.set("Morphogenerator")
        self._apply_display_options()

    # Callbacks

    def _on_blade_change(self):
        self._update_file_info()
        self._reload_model()

    def _on_color_change(self, *_):
        bg_name = self._bg_color_name.get()
        if bg_name == "Custom...":
            dialog = ctk.CTkInputDialog(text="Enter HEX color (e.g. #FF0000):", title="Custom Background")
            val = dialog.get_input()
            if val: self._bg_custom_hex = val
            
        cad_name = self._cad_color_name.get()
        if cad_name == "Custom...":
            dialog = ctk.CTkInputDialog(text="Enter HEX color (e.g. #00FF00):", title="Custom CAD Color")
            val = dialog.get_input()
            if val: self._cad_custom_hex = val
            
        self._apply_display_options()

    def _apply_display_options(self, *_):
        bg_name = self._bg_color_name.get()
        cad_name = self._cad_color_name.get()
        
        bg = self._bg_map.get(bg_name, self._bg_custom_hex) or self._bg_custom_hex
        cad = self._cad_map.get(cad_name, self._cad_custom_hex) or self._cad_custom_hex

        try:
            int(bg.lstrip("#"), 16)
            self._bg_swatch.configure(fg_color=bg)
        except ValueError:
            pass
            
        try:
            int(cad.lstrip("#"), 16)
            self._cad_swatch.configure(fg_color=cad)
        except ValueError:
            pass

        # second clip plane from the active quick-view preset (if any)
        planes = self.PRESET_PLANES.get(self._preset.get(), []) if hasattr(self, "_preset") else []
        c2 = planes[1] if len(planes) >= 2 else None

        self._viewport.set_options(
            bg=bg, 
            show_edges=self._show_edges.get(),
            show_walls=self._show_walls.get(),
            exposure=self._exposure.get(),
            cad_color=cad,
            opacity=self._opacity.get(),
            clip_enabled=self._clip_enabled.get(),
            clip_axis=self._clip_axis.get(),
            clip_z=self._clip_z.get(),
            clip_keep=self._clip_keep.get(),
            clip2_enabled=(c2 is not None),
            clip2_axis=(c2[0] if c2 else "Y"),
            clip2_z=float(c2[2]) if c2 else 0.0,
            clip2_keep=(c2[1] if c2 else "Top"),
        )

    # Model loading

    def _current_glb_path(self) -> Optional[Path]:
        return _glb_path(self._glb_folder, self._n_blades.get())

    def _update_file_info(self):
        pass

    def _reload_model(self):
        self._update_file_info()
        p = self._current_glb_path()
        self._apply_display_options()
        self._viewport.load_async(p)

    def _show_info_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title(i18n.t("modal_glb_title"))
        modal.geometry("400x300")
        modal.transient(self.winfo_toplevel())
        modal.grab_set()
        
        modal.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() - 400) // 2
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() - 300) // 2
        modal.geometry(f"+{x}+{y}")
        
        frame = ctk.CTkFrame(modal, fg_color=COLORS["bg_primary"])
        frame.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_MD)
        
        ctk.CTkLabel(
            frame, text=i18n.t("modal_glb_title"), font=FONTS["subheading"], text_color=COLORS["text_primary"]
        ).pack(anchor="w", pady=(0, PAD_MD))
        
        ctk.CTkLabel(
            frame, text=i18n.t("modal_glb_text"), font=FONTS["body"], text_color=COLORS["text_secondary"],
            justify="left", wraplength=350
        ).pack(anchor="w")
        
        ctk.CTkButton(
            frame, text="Close", command=modal.destroy, fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"], text_color=COLORS["text_on_accent"]
        ).pack(side="bottom", pady=PAD_MD)
