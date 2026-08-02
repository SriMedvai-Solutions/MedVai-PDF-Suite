# ----------------------------------------------------------------------
# Portable import shim: keep this first for PyInstaller builds.
import os
import sys
if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(sys.executable)))
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# ----------------------------------------------------------------------

"""MedVai PDF Suite GUI."""


import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from typing import Any, Optional
from uuid import uuid4

import customtkinter as ctk
import fitz
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import colorchooser, filedialog, messagebox, ttk

from gui_common import center_window, create_header, load_logo, resource_path, set_theme, set_window_icon
from medvai_core.models import BatesQueueItem, NumberingConfig, PDFFileInfo
from medvai_core.processing import PDFProcessor, STATUS_COULD_NOT_COMPLETE, STATUS_REVIEW, STATUS_VERIFIED
from medvai_core.settings import SettingsManager
from medvai_core.utils import (
    get_pdf_page_count,
    is_valid_hex_color,
    natural_sort_key,
    safe_filename_component,
    validate_readable_pdf,
)

__version__ = "3.0.5-beta"
__build_id__ = "MEDVAI_PDF_SUITE_CLEAN_ARRANGE_WINDOW_FIX_20260803"
PLACEMENTS = [
    "Top-Left", "Top-Center", "Top-Right",
    "Middle-Left", "Middle-Center", "Middle-Right",
    "Bottom-Left", "Bottom-Center", "Bottom-Right", "Custom",
]
FONTS = ["Helvetica", "Times-Roman", "Courier"]
NUMBERING_PATTERN_OPTIONS = [
    ("{n}  →  1", "{n}"),
    ("Page {n}  →  Page 1", "Page {n}"),
    ("Page-{n}  →  Page-1", "Page-{n}"),
    ("Page #{n}  →  Page #1", "Page #{n}"),
    ("Pg. {n}  →  Pg. 1", "Pg. {n}"),
    ("[{n}]  →  [1]", "[{n}]"),
    ("({n})  →  (1)", "({n})"),
    ("-{n}-  →  -1-", "-{n}-"),
    ("PAGE {n}  →  PAGE 1", "PAGE {n}"),
    ("P-{n}  →  P-1", "P-{n}"),
]
NUMBERING_DISPLAY_TO_PATTERN = dict(NUMBERING_PATTERN_OPTIONS)
NUMBERING_CUSTOM_DISPLAY = "Custom  →  type your own pattern using {n}"
PREVIEW_BUTTON_COLOR = "#5CB7BC"
PREVIEW_BUTTON_HOVER = "#459EA3"


class PlacementPreviewDialog(ctk.CTkToplevel):
    """Preview one real PDF page and save visual Bates/numbering placement."""

    def __init__(
        self,
        parent: "MedVaiPDFSuite",
        pdf_path: str,
        show_bates: bool,
        show_numbering: bool,
        bates_values: Optional[dict[str, Any]],
        numbering_values: Optional[dict[str, Any]],
        on_save,
    ):
        super().__init__(parent)
        self.parent = parent
        self.pdf_path = pdf_path
        self.show_bates = show_bates
        self.show_numbering = show_numbering
        self.on_save = on_save
        self.doc = fitz.open(pdf_path)
        self.page_index = 0
        self.zoom = 1.0
        self.preview_rotation = 0
        self.preview_page_size = (1.0, 1.0)
        self.photo = None
        self.image_origin = (0.0, 0.0)
        self.image_scale = 1.0
        self.drag_target: Optional[str] = None
        self.drag_offset = (0.0, 0.0)
        self.processor = PDFProcessor(parent.settings)
        self._normal_geometry = "1280x820"
        self._preview_maximized = False

        if show_bates and not show_numbering:
            self.title("Preview & Set Bates Position")
        elif show_numbering and not show_bates:
            self.title("Preview & Set Numbering Position")
        else:
            self.title("Preview Settings")
        self.geometry(self._normal_geometry)
        self.minsize(1120, 720)
        set_window_icon(self, resource_path("assets"))
        self.transient(parent)
        self.grab_set()

        self.bates = self._make_vars(bates_values or {}, is_bates=True)
        self.numbering = self._make_vars(numbering_values or {}, is_bates=False)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        left = ctk.CTkFrame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(left)
        toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        ctk.CTkButton(toolbar, text="◀ Previous", width=100, command=self._previous_page).pack(side="left", padx=4)
        ctk.CTkLabel(toolbar, text="Page").pack(side="left", padx=(12, 4))
        self.page_entry = ctk.CTkEntry(toolbar, width=65)
        self.page_entry.pack(side="left", padx=4)
        self.page_entry.insert(0, "1")
        ctk.CTkLabel(toolbar, text=f"of {len(self.doc)}").pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text="Go", width=55, command=self._go_page).pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text="Next ▶", width=100, command=self._next_page).pack(side="left", padx=4)
        ctk.CTkLabel(toolbar, text="Test view").pack(side="left", padx=(10, 3))
        self.preview_rotation_var = tk.StringVar(value="0°")
        ctk.CTkComboBox(
            toolbar,
            variable=self.preview_rotation_var,
            values=["0°", "90°", "180°", "270°"],
            width=72,
            command=self._change_preview_rotation,
        ).pack(side="left", padx=3)
        self.page_info_label = ctk.CTkLabel(toolbar, text="")
        self.page_info_label.pack(side="left", padx=8)
        ctk.CTkButton(toolbar, text="Zoom −", width=80, command=lambda: self._change_zoom(-0.15)).pack(side="right", padx=4)
        ctk.CTkButton(toolbar, text="Zoom +", width=80, command=lambda: self._change_zoom(0.15)).pack(side="right", padx=4)
        self.maximize_button = ctk.CTkButton(
            toolbar,
            text="Maximize",
            width=90,
            command=self._toggle_maximize,
        )
        self.maximize_button.pack(side="right", padx=4)

        self.canvas = tk.Canvas(left, background="#606060", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.canvas.bind("<Configure>", lambda _event: self._render())
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)

        right = ctk.CTkScrollableFrame(self, width=470)
        right.grid(row=0, column=1, sticky="ns", padx=(6, 12), pady=12)
        right.grid_columnconfigure(0, weight=1)

        row = 0
        ctk.CTkLabel(
            right,
            text="Drag the coloured Bates or numbering box on the actual PDF page.\n"
                 "The saved visual position follows every page rotation and size.",
            justify="left",
            wraplength=420,
        ).grid(row=row, column=0, sticky="ew", padx=8, pady=(8, 12))
        row += 1

        if show_bates:
            self._build_bates_controls(right, row)
            row += 1
        if show_numbering:
            self._build_numbering_controls(right, row)
            row += 1

        action = ctk.CTkFrame(right)
        action.grid(row=row, column=0, sticky="ew", padx=8, pady=12)
        ctk.CTkButton(action, text="Save Settings", fg_color="green", command=self._save).pack(side="left", padx=6, pady=8)
        ctk.CTkButton(action, text="Cancel", command=self._close).pack(side="left", padx=6, pady=8)

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._render)

    def _make_vars(self, values: dict[str, Any], *, is_bates: bool) -> dict[str, Any]:
        defaults = {
            "placement": "Bottom-Right" if is_bates else "Bottom-Center",
            "color": "#000000",
            "font_name": "Helvetica",
            "font_size": 11 if is_bates else 10,
            "bold": False,
            "opacity": 1.0,
            "offset_x": 32,
            "offset_y": 24,
            "position_x_ratio": None,
            "position_y_ratio": None,
        }
        if is_bates:
            defaults.update({
                "prefix": "",
                "symbol": "",
                "start_number": "",
                "padding": 6,
                "suffix": "",
            })
        else:
            defaults.update({"pattern": "{n}", "start_number": 1})
        defaults.update(values)
        result: dict[str, Any] = {
            "placement": tk.StringVar(value=str(defaults["placement"])),
            "color": tk.StringVar(value=str(defaults["color"])),
            "font_name": tk.StringVar(value=str(defaults["font_name"])),
            "font_size": tk.StringVar(value=str(defaults["font_size"])),
            "bold": tk.BooleanVar(value=bool(defaults["bold"])),
            "opacity": tk.StringVar(value=str(defaults["opacity"])),
            "offset_x": tk.StringVar(value=str(defaults["offset_x"])),
            "offset_y": tk.StringVar(value=str(defaults["offset_y"])),
            "position_x_ratio": defaults.get("position_x_ratio"),
            "position_y_ratio": defaults.get("position_y_ratio"),
        }
        if is_bates:
            result.update({
                "prefix": tk.StringVar(value=str(defaults["prefix"])),
                "symbol": tk.StringVar(value=str(defaults["symbol"])),
                "start_number": tk.StringVar(value=str(defaults["start_number"])),
                "padding": tk.StringVar(value=str(defaults["padding"])),
                "suffix": tk.StringVar(value=str(defaults["suffix"])),
            })
        else:
            result.update({
                "pattern": tk.StringVar(value=str(defaults["pattern"])),
                "start_number": tk.StringVar(value=str(defaults["start_number"])),
            })
        return result

    def _build_bates_controls(self, parent, row: int) -> None:
        frame = ctk.CTkFrame(parent)
        frame.grid(row=row, column=0, sticky="ew", padx=8, pady=6)
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="Bates Settings", font=("Segoe UI", 15, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(10, 4)
        )
        self.bates_preview_text_label = ctk.CTkLabel(
            frame,
            text="Bates preview: Enter the Bates details below",
            font=("Segoe UI", 13, "bold"),
            anchor="w",
            justify="left",
            wraplength=400,
        )
        self.bates_preview_text_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 8))

        self._entry_row(frame, "Prefix", self.bates["prefix"], 2, placeholder="Up to 6 letters")
        self._combo_row(frame, "Separator", self.bates["symbol"], ["", "-", "_", "/", "@"], 3)
        self._entry_row(frame, "Starting number", self.bates["start_number"], 4, placeholder="Required, for example 1")
        self._entry_row(frame, "Number digits", self.bates["padding"], 5, placeholder="6")
        self._entry_row(frame, "Suffix", self.bates["suffix"], 6, placeholder="Optional numbers or symbols")
        ctk.CTkLabel(
            frame,
            text="Prefix: up to 6 letters. Separator and suffix are optional. The same or different Bates details may be used for duplicate PDF entries.",
            justify="left",
            wraplength=400,
            text_color=("#555555", "#bbbbbb"),
        ).grid(row=7, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 8))

        self._combo_row(
            frame, "Placement", self.bates["placement"], PLACEMENTS, 8,
            command=lambda _v: self._preset_changed("bates"),
        )
        self._combo_row(frame, "Font", self.bates["font_name"], FONTS, 9)
        self._entry_row(frame, "Font size", self.bates["font_size"], 10)
        ctk.CTkCheckBox(frame, text="Bold", variable=self.bates["bold"], command=self._render).grid(
            row=11, column=1, padx=8, pady=6, sticky="w"
        )
        self._color_row(frame, "Colour", self.bates["color"], 12)
        self._entry_row(frame, "Opacity", self.bates["opacity"], 13)
        self._entry_row(frame, "X offset", self.bates["offset_x"], 14)
        self._entry_row(frame, "Y offset", self.bates["offset_y"], 15)
        self._bind_render_vars(self.bates)
        self._update_bates_preview_label()

    def _build_numbering_controls(self, parent, row: int) -> None:
        frame = ctk.CTkFrame(parent)
        frame.grid(row=row, column=0, sticky="ew", padx=8, pady=6)
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="Page Number Settings", font=("Segoe UI", 15, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(10, 6)
        )
        self.numbering_preview_text_label = ctk.CTkLabel(
            frame, text="", font=("Segoe UI", 13, "bold"), anchor="w", justify="left", wraplength=400
        )
        self.numbering_preview_text_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 8))
        current_pattern = self.numbering["pattern"].get()
        current_display = next(
            (display for display, pattern in NUMBERING_PATTERN_OPTIONS if pattern == current_pattern),
            NUMBERING_CUSTOM_DISPLAY,
        )
        self.numbering_pattern_choice = tk.StringVar(value=current_display)
        ctk.CTkLabel(frame, text="Pattern option").grid(row=2, column=0, padx=10, pady=6, sticky="w")
        self.numbering_pattern_combo = ctk.CTkComboBox(
            frame,
            variable=self.numbering_pattern_choice,
            values=[display for display, _pattern in NUMBERING_PATTERN_OPTIONS] + [NUMBERING_CUSTOM_DISPLAY],
            command=self._select_numbering_pattern,
        )
        self.numbering_pattern_combo.grid(row=2, column=1, padx=10, pady=6, sticky="ew")
        self._entry_row(frame, "Pattern", self.numbering["pattern"], 3, placeholder="Must contain {n}")
        self._entry_row(frame, "Starting number", self.numbering["start_number"], 4)
        ctk.CTkLabel(
            frame,
            text="Choose a ready pattern above or type your own. Use {n} where the page number should appear.\n"
                 "For merged PDFs, numbering always continues through the complete merged PDF.",
            justify="left", wraplength=400, text_color=("#555555", "#bbbbbb")
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 8))
        self._combo_row(
            frame, "Placement", self.numbering["placement"], PLACEMENTS, 6,
            command=lambda _v: self._preset_changed("numbering"),
        )
        self._combo_row(frame, "Font", self.numbering["font_name"], FONTS, 7)
        self._entry_row(frame, "Font size", self.numbering["font_size"], 8)
        ctk.CTkCheckBox(frame, text="Bold", variable=self.numbering["bold"], command=self._render).grid(
            row=9, column=1, padx=8, pady=6, sticky="w"
        )
        self._color_row(frame, "Colour", self.numbering["color"], 10)
        self._entry_row(frame, "Opacity", self.numbering["opacity"], 11)
        self._entry_row(frame, "X offset", self.numbering["offset_x"], 12)
        self._entry_row(frame, "Y offset", self.numbering["offset_y"], 13)
        self._bind_render_vars(self.numbering)
        self._update_numbering_preview_label()

    @staticmethod
    def _entry_row(parent, label, variable, row, placeholder=""):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=10, pady=6, sticky="w")
        entry = ctk.CTkEntry(parent, textvariable=variable, placeholder_text=placeholder)
        entry.grid(row=row, column=1, padx=10, pady=6, sticky="ew")
        return entry

    @staticmethod
    def _combo_row(parent, label, variable, values, row, command=None):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=10, pady=6, sticky="w")
        combo = ctk.CTkComboBox(parent, variable=variable, values=values, command=command)
        combo.grid(row=row, column=1, padx=10, pady=6, sticky="ew")
        return combo

    def _color_row(self, parent, label, variable, row):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=10, pady=6, sticky="w")
        holder = ctk.CTkFrame(parent, fg_color="transparent")
        holder.grid(row=row, column=1, padx=10, pady=6, sticky="ew")
        holder.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(holder, textvariable=variable).grid(row=0, column=0, sticky="ew")
        swatch = ctk.CTkLabel(holder, text="", width=28, height=24, corner_radius=4)
        swatch.grid(row=0, column=1, padx=(6, 3))
        ctk.CTkButton(holder, text="Pick Colour", width=92, command=lambda: self._pick_color(variable)).grid(
            row=0, column=2, padx=(3, 0)
        )

        def update_swatch(*_args):
            value = variable.get()
            colour = value if is_valid_hex_color(value) else "#808080"
            swatch.configure(fg_color=colour)

        variable.trace_add("write", update_swatch)
        update_swatch()
        return holder

    def _bind_render_vars(self, variables: dict[str, Any]) -> None:
        for value in variables.values():
            if isinstance(value, (tk.StringVar, tk.BooleanVar)):
                value.trace_add("write", lambda *_args: self.after_idle(self._live_preview_update))

    def _live_preview_update(self) -> None:
        if self.show_bates:
            self._update_bates_preview_label()
        if self.show_numbering:
            self._update_numbering_preview_label()
        self._render()

    def _update_bates_preview_label(self) -> None:
        label = getattr(self, "bates_preview_text_label", None)
        if label is None:
            return
        text = self._sample_bates_text()
        if not self.bates["start_number"].get().strip():
            label.configure(text="Bates preview: Enter a starting number")
        else:
            label.configure(text=f"Bates preview: {text}")

    def _update_numbering_preview_label(self) -> None:
        label = getattr(self, "numbering_preview_text_label", None)
        if label is not None:
            label.configure(text=f"Page-number preview: {self._sample_number_text()}")

    def _pick_color(self, variable: tk.StringVar) -> None:
        selected = colorchooser.askcolor(title="Choose colour", parent=self)[1]
        if selected:
            variable.set(selected)

    def _select_numbering_pattern(self, display_value: str) -> None:
        pattern = NUMBERING_DISPLAY_TO_PATTERN.get(display_value)
        if pattern is not None:
            self.numbering["pattern"].set(pattern)

    def _toggle_maximize(self) -> None:
        """Maximize or restore the preview without changing the main application."""
        try:
            if not self._preview_maximized:
                self._normal_geometry = self.geometry()
                try:
                    self.state("zoomed")
                except tk.TclError:
                    width = self.winfo_screenwidth()
                    height = self.winfo_screenheight()
                    self.geometry(f"{width}x{height}+0+0")
                self._preview_maximized = True
                self.maximize_button.configure(text="Restore")
            else:
                try:
                    self.state("normal")
                except tk.TclError:
                    pass
                self.geometry(self._normal_geometry)
                self._preview_maximized = False
                self.maximize_button.configure(text="Maximize")
            self.after(100, self._render)
        except Exception as exc:
            messagebox.showwarning("Preview size needs review", str(exc), parent=self)

    def _sample_bates_text(self) -> str:
        start_text = self.bates["start_number"].get().strip()
        try:
            start = int(start_text)
            padding = int(self.bates["padding"].get())
        except ValueError:
            return "Enter Bates details"
        return (
            f"{self.bates['prefix'].get()}"
            f"{self.bates['symbol'].get()}"
            f"{str(start).zfill(padding)}"
            f"{self.bates['suffix'].get()}"
        )

    def _sample_number_text(self) -> str:
        try:
            number = int(self.numbering["start_number"].get()) + self.page_index
        except ValueError:
            number = self.page_index + 1
        return self.numbering["pattern"].get().replace("{n}", str(number)).replace("{total}", str(len(self.doc)))

    def _stamp_config(self, variables: dict[str, Any]) -> dict[str, Any]:
        return {
            "placement": variables["placement"].get(),
            "font_name": variables["font_name"].get(),
            "bold": variables["bold"].get(),
            "font_size": int(variables["font_size"].get()),
            "offset_x": int(variables["offset_x"].get()),
            "offset_y": int(variables["offset_y"].get()),
            "position_x_ratio": variables["position_x_ratio"],
            "position_y_ratio": variables["position_y_ratio"],
        }

    def _render(self) -> None:
        if not self.winfo_exists() or self.canvas.winfo_width() < 20:
            return
        try:
            page = self.doc[self.page_index]
            available_w = max(self.canvas.winfo_width() - 30, 100)
            available_h = max(self.canvas.winfo_height() - 30, 100)
            view_width = float(page.rect.width)
            view_height = float(page.rect.height)
            if self.preview_rotation in (90, 270):
                view_width, view_height = view_height, view_width
            base_scale = min(available_w / view_width, available_h / view_height)
            scale = max(0.15, base_scale * self.zoom)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, annots=True)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            if self.preview_rotation:
                image = image.rotate(-self.preview_rotation, expand=True)
            self.preview_page_size = (view_width, view_height)
            self.page_info_label.configure(
                text=f"PDF rotation {page.rotation}° • {int(page.rect.width)} × {int(page.rect.height)} pt"
            )
            self.photo = ImageTk.PhotoImage(image)
            self.canvas.delete("all")
            rendered_width, rendered_height = image.size
            origin_x = (self.canvas.winfo_width() - rendered_width) / 2
            origin_y = (self.canvas.winfo_height() - rendered_height) / 2
            self.image_origin = (origin_x, origin_y)
            self.image_scale = scale
            self.canvas.create_image(origin_x, origin_y, anchor="nw", image=self.photo, tags=("page",))
            self.canvas.create_rectangle(
                origin_x + 4, origin_y + 4, origin_x + rendered_width - 4, origin_y + rendered_height - 4,
                outline="#00a8a8", width=2, dash=(5, 3), tags=("safe",),
            )
            if self.show_bates:
                self._draw_stamp("bates", self._sample_bates_text(), self.bates, "#d7191c")
            if self.show_numbering:
                self._draw_stamp("numbering", self._sample_number_text(), self.numbering, "#1a53ff")
        except Exception as exc:
            self.canvas.delete("all")
            self.canvas.create_text(20, 20, anchor="nw", fill="white", text=f"Preview needs review:\n{exc}")

    def _draw_stamp(self, tag: str, text: str, variables: dict[str, Any], outline: str) -> None:
        source_page = self.doc[self.page_index]
        view_width, view_height = self.preview_page_size
        preview_page = SimpleNamespace(rect=fitz.Rect(0, 0, view_width, view_height), number=source_page.number)
        config = self._stamp_config(variables)
        rect, used_size, _adjustments = self.processor._calculate_visual_rect(preview_page, text, **config)
        ox, oy = self.image_origin
        scale = self.image_scale
        page_left = ox + 8
        page_top = oy + 8
        page_right = ox + view_width * scale - 8
        page_bottom = oy + view_height * scale - 8
        desired_x = ox + ((rect.x0 + rect.x1) / 2) * scale
        desired_y = oy + ((rect.y0 + rect.y1) / 2) * scale
        try:
            font_size = max(10, int(round(used_size * scale)))
        except Exception:
            font_size = 10
        font_spec = (
            variables["font_name"].get(),
            font_size,
            "bold" if variables["bold"].get() else "normal",
        )
        text_colour = variables["color"].get() if is_valid_hex_color(variables["color"].get()) else "#000000"
        text_id = self.canvas.create_text(
            desired_x,
            desired_y,
            text=text,
            fill=text_colour,
            font=font_spec,
            anchor="center",
            tags=(tag, f"{tag}_text"),
        )
        bbox = self.canvas.bbox(text_id) or (desired_x - 20, desired_y - 8, desired_x + 20, desired_y + 8)
        padding = 6
        available_box_width = max(page_right - page_left, 40)
        measured_width = (bbox[2] - bbox[0]) + padding * 2
        if measured_width > available_box_width and font_size > 8:
            fitted_size = max(8, int(font_size * available_box_width / measured_width))
            self.canvas.itemconfigure(
                text_id,
                font=(variables["font_name"].get(), fitted_size, "bold" if variables["bold"].get() else "normal"),
            )
            bbox = self.canvas.bbox(text_id) or bbox
        half_w = min(max((bbox[2] - bbox[0]) / 2 + padding, 22), available_box_width / 2)
        half_h = max((bbox[3] - bbox[1]) / 2 + padding, 12)
        center_x = min(max(desired_x, page_left + half_w), page_right - half_w)
        center_y = min(max(desired_y, page_top + half_h), page_bottom - half_h)
        self.canvas.coords(text_id, center_x, center_y)
        if variables["placement"].get() == "Custom":
            variables["position_x_ratio"] = min(max((center_x - ox) / max(view_width * scale, 1), 0.0), 1.0)
            variables["position_y_ratio"] = min(max((center_y - oy) / max(view_height * scale, 1), 0.0), 1.0)
        box = (center_x - half_w, center_y - half_h, center_x + half_w, center_y + half_h)
        self.canvas.create_rectangle(
            *box,
            outline=outline,
            width=4,
            tags=(tag, f"{tag}_box"),
        )
        self.canvas.tag_raise(text_id)

    def _start_drag(self, event) -> None:
        current = self.canvas.find_withtag("current")
        if not current:
            return
        tags = self.canvas.gettags(current[0])
        for target in ("bates", "numbering"):
            if target in tags:
                self.drag_target = target
                bbox = self.canvas.bbox(target)
                if bbox:
                    center_x = (bbox[0] + bbox[2]) / 2
                    center_y = (bbox[1] + bbox[3]) / 2
                    self.drag_offset = (event.x - center_x, event.y - center_y)
                return

    def _drag(self, event) -> None:
        if not self.drag_target:
            return
        variables = self.bates if self.drag_target == "bates" else self.numbering
        ox, oy = self.image_origin
        view_width, view_height = self.preview_page_size
        center_x = event.x - self.drag_offset[0]
        center_y = event.y - self.drag_offset[1]
        ratio_x = min(max((center_x - ox) / max(view_width * self.image_scale, 1), 0.0), 1.0)
        ratio_y = min(max((center_y - oy) / max(view_height * self.image_scale, 1), 0.0), 1.0)
        variables["position_x_ratio"] = ratio_x
        variables["position_y_ratio"] = ratio_y
        variables["placement"].set("Custom")
        self._render()

    def _end_drag(self, _event) -> None:
        self.drag_target = None

    def _preset_changed(self, target: str) -> None:
        variables = self.bates if target == "bates" else self.numbering
        if variables["placement"].get() != "Custom":
            variables["position_x_ratio"] = None
            variables["position_y_ratio"] = None
        self._render()

    def _previous_page(self) -> None:
        if self.page_index > 0:
            self.page_index -= 1
            self._sync_page_entry()
            self._render()

    def _next_page(self) -> None:
        if self.page_index < len(self.doc) - 1:
            self.page_index += 1
            self._sync_page_entry()
            self._render()

    def _go_page(self) -> None:
        try:
            page_number = int(self.page_entry.get())
            if not 1 <= page_number <= len(self.doc):
                raise ValueError
            self.page_index = page_number - 1
            self._render()
        except ValueError:
            messagebox.showwarning("Page", f"Enter a page from 1 to {len(self.doc)}.", parent=self)
            self._sync_page_entry()

    def _sync_page_entry(self) -> None:
        self.page_entry.delete(0, "end")
        self.page_entry.insert(0, str(self.page_index + 1))

    def _change_zoom(self, amount: float) -> None:
        self.zoom = min(max(self.zoom + amount, 0.35), 3.0)
        self._render()

    def _change_preview_rotation(self, value: str) -> None:
        try:
            self.preview_rotation = int(value.rstrip("°")) % 360
        except (TypeError, ValueError):
            self.preview_rotation = 0
        self._render()

    def _collect(self, variables: dict[str, Any], *, is_bates: bool) -> dict[str, Any]:
        result = {
            "placement": variables["placement"].get(),
            "color": variables["color"].get(),
            "font_name": variables["font_name"].get(),
            "font_size": int(variables["font_size"].get()),
            "bold": variables["bold"].get(),
            "opacity": float(variables["opacity"].get()),
            "offset_x": int(variables["offset_x"].get()),
            "offset_y": int(variables["offset_y"].get()),
            "position_x_ratio": variables["position_x_ratio"],
            "position_y_ratio": variables["position_y_ratio"],
        }
        if is_bates:
            prefix = variables["prefix"].get().strip()
            if prefix and (len(prefix) > 6 or not prefix.isalpha()):
                raise ValueError("Bates prefix may contain up to 6 letters only.")
            start_text = variables["start_number"].get().strip()
            if not start_text:
                raise ValueError("Enter the Bates starting number.")
            result.update({
                "prefix": prefix,
                "symbol": variables["symbol"].get(),
                "start_number": int(start_text),
                "padding": int(variables["padding"].get()),
                "suffix": variables["suffix"].get(),
            })
        else:
            result.update({
                "pattern": variables["pattern"].get(),
                "start_number": int(variables["start_number"].get()),
            })
        return result

    def _save(self) -> None:
        try:
            bates_result = self._collect(self.bates, is_bates=True) if self.show_bates else None
            numbering_result = self._collect(self.numbering, is_bates=False) if self.show_numbering else None
            if bates_result:
                dummy = BatesQueueItem(
                    file_path=self.pdf_path,
                    filename=Path(self.pdf_path).name,
                    pages_in_source=len(self.doc),
                    **bates_result,
                )
                self.processor._validate_bates_item(dummy)
            if numbering_result:
                dummy_num = NumberingConfig(enabled=True, **numbering_result)
                self.processor._validate_numbering_config(dummy_num)
            self.on_save(bates_result, numbering_result)
            self._close()
        except Exception as exc:
            messagebox.showwarning("Settings need review", str(exc), parent=self)

    def _close(self) -> None:
        try:
            self.doc.close()
        finally:
            self.destroy()


class PDFArrangeDialog(ctk.CTkToplevel):
    """Select, review and arrange the PDFs without crowding the main screen."""

    def __init__(
        self,
        parent: "MedVaiPDFSuite",
        pdf_files: list[PDFFileInfo],
        selected_folder: str,
        on_save,
    ):
        super().__init__(parent)
        self.parent = parent
        self.items = deepcopy(pdf_files)
        self.selected_folder = selected_folder
        self.on_save = on_save

        self.title("Preview & Arrange PDFs")
        self.geometry("1040x680")
        self.minsize(900, 560)
        set_window_icon(self, resource_path("assets"))
        self.transient(parent)
        self.grab_set()

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Selected folder:").grid(row=0, column=0, padx=6, pady=8, sticky="w")
        self.folder_entry = ctk.CTkEntry(top)
        self.folder_entry.grid(row=0, column=1, padx=6, pady=8, sticky="ew")
        self.folder_entry.insert(0, selected_folder)
        ctk.CTkButton(top, text="Browse Folder", width=110, command=self._browse_folder).grid(
            row=0, column=2, padx=5, pady=8
        )
        ctk.CTkButton(top, text="Add PDFs", width=90, command=self._add_pdfs).grid(
            row=0, column=3, padx=5, pady=8
        )

        table_frame = ctk.CTkFrame(self)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            table_frame,
            columns=("order", "file", "pages", "status"),
            show="headings",
            selectmode="extended",
        )
        for key, title, width in (
            ("order", "Order", 60),
            ("file", "PDF", 560),
            ("pages", "Pages", 80),
            ("status", "Status", 180),
        ):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w" if key in {"file", "status"} else "center")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        scroll = ctk.CTkScrollbar(table_frame, command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)
        self.tree.configure(yscrollcommand=scroll.set)

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="ew", padx=12, pady=4)
        for label, command in (
            ("Remove", self._remove),
            ("Duplicate", self._duplicate),
            ("Move Up", lambda: self._move(-1)),
            ("Move Down", lambda: self._move(1)),
            ("Natural Sort", self._natural_sort),
        ):
            ctk.CTkButton(controls, text=label, width=105, command=command).pack(
                side="left", padx=(0, 6), pady=4
            )

        self.summary_label = ctk.CTkLabel(self, text="", anchor="w")
        self.summary_label.grid(row=3, column=0, sticky="ew", padx=18, pady=(2, 4))

        bottom = ctk.CTkFrame(self)
        bottom.grid(row=4, column=0, sticky="ew", padx=12, pady=(6, 12))
        ctk.CTkButton(
            bottom,
            text="Save Arrangement",
            width=150,
            fg_color="green",
            command=self._save,
        ).pack(side="left", padx=8, pady=10)
        ctk.CTkButton(bottom, text="Cancel", width=110, command=self.destroy).pack(
            side="left", padx=8, pady=10
        )

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._refresh()

    @staticmethod
    def _read_pdf(path: str) -> PDFFileInfo:
        try:
            pages = validate_readable_pdf(path)
            status = "OK"
        except Exception as exc:
            pages = 0
            status = f"Needs review: {exc}"
        return PDFFileInfo(path=path, filename=Path(path).name, pages=pages, status=status)

    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, item in enumerate(self.items, 1):
            self.tree.insert(
                "",
                "end",
                iid=item.entry_id,
                values=(index, item.filename, item.pages, item.status),
            )
        total_pages = sum(item.pages for item in self.items if item.status == "OK")
        self.summary_label.configure(
            text=f"{len(self.items)} PDF(s) selected — {total_pages} total page(s). The order shown here is the merge order."
        )

    def _browse_folder(self) -> None:
        folder = filedialog.askdirectory(
            title="Select folder containing PDFs",
            initialdir=self.selected_folder or self.parent.settings.get("last_folder_path", ""),
            parent=self,
        )
        if not folder:
            return
        names = sorted(
            [name for name in os.listdir(folder) if name.lower().endswith(".pdf")],
            key=natural_sort_key,
        )
        if self.items and not messagebox.askyesno(
            "Replace PDF selection",
            "Replace the current PDF list with all PDFs from the selected folder?",
            parent=self,
        ):
            return
        self.selected_folder = folder
        self.folder_entry.delete(0, "end")
        self.folder_entry.insert(0, folder)
        self.items = [self._read_pdf(os.path.join(folder, name)) for name in names]
        self._refresh()

    def _add_pdfs(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Add PDF files",
            filetypes=[("PDF files", "*.pdf")],
            initialdir=self.selected_folder or self.parent.settings.get("last_file_path", ""),
            parent=self,
        )
        for path in sorted(paths, key=lambda value: natural_sort_key(Path(value).name)):
            duplicate = any(Path(item.path).resolve() == Path(path).resolve() for item in self.items)
            if duplicate and not messagebox.askyesno(
                "Add duplicate PDF",
                f"{Path(path).name} is already selected. Add another occurrence?",
                parent=self,
            ):
                continue
            self.items.append(self._read_pdf(path))
        if paths and not self.selected_folder:
            self.selected_folder = str(Path(paths[0]).parent)
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, self.selected_folder)
        self._refresh()

    def _selected_indices(self) -> list[int]:
        selected_ids = set(self.tree.selection())
        return [index for index, item in enumerate(self.items) if item.entry_id in selected_ids]

    def _remove(self) -> None:
        indices = self._selected_indices()
        if not indices:
            messagebox.showinfo("Remove PDFs", "Select one or more PDFs first.", parent=self)
            return
        for index in reversed(indices):
            del self.items[index]
        self._refresh()

    def _duplicate(self) -> None:
        indices = self._selected_indices()
        if len(indices) != 1:
            messagebox.showinfo("Duplicate PDF", "Select one PDF first.", parent=self)
            return
        source = self.items[indices[0]]
        if not messagebox.askyesno(
            "Add duplicate PDF",
            f"Add another occurrence of {source.filename}?",
            parent=self,
        ):
            return
        duplicate = replace(source, entry_id=uuid4().hex)
        self.items.insert(indices[0] + 1, duplicate)
        self._refresh()
        self.tree.selection_set(duplicate.entry_id)

    def _move(self, direction: int) -> None:
        indices = self._selected_indices()
        if len(indices) != 1:
            messagebox.showinfo("Arrange PDFs", "Select one PDF to move.", parent=self)
            return
        index = indices[0]
        new_index = index + direction
        if not 0 <= new_index < len(self.items):
            return
        item = self.items.pop(index)
        self.items.insert(new_index, item)
        self._refresh()
        self.tree.selection_set(item.entry_id)
        self.tree.focus(item.entry_id)
        self.tree.see(item.entry_id)

    def _natural_sort(self) -> None:
        self.items.sort(key=lambda item: natural_sort_key(item.filename))
        self._refresh()

    def _save(self) -> None:
        if not self.items:
            messagebox.showwarning("PDF selection needs review", "Add at least one PDF.", parent=self)
            return
        self.on_save(deepcopy(self.items), self.selected_folder)
        self.destroy()


class MedVaiPDFSuite(ctk.CTk):
    def __init__(self):
        super().__init__()
        set_theme()
        self.settings = SettingsManager()
        self.title("MedVai PDF Suite")
        self.geometry(self.settings.get("geometry", "1240x920"))
        self.minsize(1080, 760)
        set_window_icon(self, resource_path("assets"))

        self.pdf_files: list[PDFFileInfo] = []
        self.bates_queue: list[BatesQueueItem] = []
        self.selected_folder = ""
        self.selected_file = ""
        self.simple_bates_values: dict[str, Any] = self._blank_bates_values()
        self.simple_bates_configured = False
        self.bates_mode_var = ctk.StringVar(value="continuous")
        self._last_bates_mode = "continuous"
        self.continuous_bates_values: dict[str, Any] = self._blank_bates_values()
        self.continuous_bates_configured = False
        self.numbering_values_store: dict[str, Any] = self._default_numbering_values()
        self.numbering_configured = False

        self._create_widgets()
        self._load_defaults()
        self._refresh_mode_ui()
        center_window(self)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Main layout
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        # Keep the logo fully visible while reclaiming only a small amount of height.
        logo = load_logo(resource_path("assets"), height=88)
        # New gui_common supports compact-header options. The fallback keeps the
        # application compatible if a user accidentally has an older gui_common.py.
        try:
            create_header(self, "MedVai PDF Suite", logo, height=128, vertical_padding=14)
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            create_header(self, "MedVai PDF Suite", logo)
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=8)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.tab1 = self.tabview.add("Merge / Bates / Numbering")
        self.tab2 = self.tabview.add("Split PDF")
        self._create_tab1()
        self._create_tab2()

    def _create_tab1(self) -> None:
        """Build a clean main page; PDF selection and ordering live in a separate window."""
        self.tab1.grid_rowconfigure(0, weight=0)
        self.tab1.grid_rowconfigure(1, weight=1)
        self.tab1.grid_rowconfigure(2, weight=0)
        self.tab1.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self.tab1)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=5)
        top.grid_columnconfigure(0, weight=1)

        ops = ctk.CTkFrame(top)
        ops.grid(row=0, column=0, sticky="ew", padx=6, pady=(5, 3))
        self.merge_var = ctk.BooleanVar(value=True)
        self.bates_var = ctk.BooleanVar(value=False)
        self.numbering_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            ops, text="Merge PDFs", variable=self.merge_var, command=self._refresh_mode_ui
        ).grid(row=0, column=0, padx=10, pady=4, sticky="w")
        ctk.CTkCheckBox(
            ops, text="Apply Bates", variable=self.bates_var, command=self._refresh_mode_ui
        ).grid(row=0, column=1, padx=10, pady=4, sticky="w")
        ctk.CTkCheckBox(
            ops, text="Apply Numbering", variable=self.numbering_var, command=self._refresh_mode_ui
        ).grid(row=0, column=2, padx=10, pady=4, sticky="w")

        self.merge_input_frame = ctk.CTkFrame(top)
        self.merge_input_frame.grid(row=1, column=0, sticky="ew", padx=6, pady=3)
        self.merge_input_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.merge_input_frame, text="Select Folder:").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.folder_entry = ctk.CTkEntry(self.merge_input_frame)
        self.folder_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(
            self.merge_input_frame, text="Browse Folder", command=self._browse_folder, width=110
        ).grid(row=0, column=2, padx=5, pady=5)

        arrange_row = ctk.CTkFrame(self.merge_input_frame, fg_color="transparent")
        arrange_row.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=(2, 5))
        arrange_row.grid_columnconfigure(1, weight=1)
        self.arrange_pdfs_button = ctk.CTkButton(
            arrange_row,
            text="Preview & Arrange PDFs",
            width=260,
            height=38,
            fg_color=PREVIEW_BUTTON_COLOR,
            hover_color=PREVIEW_BUTTON_HOVER,
            text_color="white",
            command=self._open_pdf_arrangement,
        )
        self.arrange_pdfs_button.grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.pdf_summary_label = ctk.CTkLabel(
            arrange_row,
            text="No PDFs selected.",
            anchor="w",
            justify="left",
        )
        self.pdf_summary_label.grid(row=0, column=1, sticky="ew")

        self.single_input_frame = ctk.CTkFrame(top)
        self.single_input_frame.grid(row=1, column=0, sticky="ew", padx=6, pady=3)
        self.single_input_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.single_input_frame, text="Select File:").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.file_entry = ctk.CTkEntry(self.single_input_frame)
        self.file_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(
            self.single_input_frame, text="Browse", command=self._browse_file, width=100
        ).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkLabel(
            self.single_input_frame,
            text="Output is saved automatically in a MedVai_Output subfolder beside the input PDF.",
            anchor="w",
        ).grid(row=1, column=0, columnspan=3, padx=5, pady=(0, 4), sticky="w")

        self.config_scroll = ctk.CTkScrollableFrame(self.tab1, height=430)
        self.config_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=5)
        self.config_scroll.grid_columnconfigure(0, weight=1)

        self.numbering_frame = ctk.CTkFrame(self.config_scroll)
        self.numbering_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        self._create_numbering_panel()

        self.bates_merge_frame = ctk.CTkFrame(self.config_scroll)
        self.bates_merge_frame.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        self._create_bates_merge_panel()

        self.bates_simple_frame = ctk.CTkFrame(self.config_scroll)
        self.bates_simple_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=4)
        self._create_bates_simple_panel()

        self.validation_label = ctk.CTkLabel(self.config_scroll, text="")
        self.validation_label.grid(row=3, column=0, sticky="ew", padx=6, pady=4)

        actions = ctk.CTkFrame(self.tab1, height=58)
        actions.grid(row=2, column=0, sticky="ew", padx=8, pady=6)
        actions.grid_propagate(False)
        ctk.CTkButton(actions, text="Validate", width=120, height=35, command=self._validate_tab1).grid(
            row=0, column=0, padx=10, pady=10
        )
        ctk.CTkButton(actions, text="Run", width=120, height=35, fg_color="green", command=self._run_tab1).grid(
            row=0, column=1, padx=10, pady=10
        )
        ctk.CTkButton(actions, text="Clear All", width=120, height=35, command=self._clear_tab1).grid(
            row=0, column=2, padx=10, pady=10
        )

    def _create_numbering_panel(self) -> None:
        frame = self.numbering_frame
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Page Numbering", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(7, 2)
        )
        self.numbering_summary_label = ctk.CTkLabel(
            frame,
            text="Not configured. Open the preview to choose the numbering format and position.",
            justify="left",
            wraplength=1000,
        )
        self.numbering_summary_label.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 4))
        self.numbering_preview_button = ctk.CTkButton(
            frame,
            text="Preview & Set Numbering",
            width=260,
            height=38,
            fg_color=PREVIEW_BUTTON_COLOR,
            hover_color=PREVIEW_BUTTON_HOVER,
            text_color="white",
            command=self._open_numbering_preview,
        )
        self.numbering_preview_button.grid(row=2, column=0, sticky="w", padx=10, pady=(1, 8))

    def _create_bates_merge_panel(self) -> None:
        frame = self.bates_merge_frame
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Bates Settings", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(7, 2)
        )

        mode_frame = ctk.CTkFrame(frame, fg_color="transparent")
        mode_frame.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 2))
        ctk.CTkLabel(mode_frame, text="Bates mode:").pack(side="left", padx=(0, 8))
        ctk.CTkRadioButton(
            mode_frame,
            text="Continuous Bates across all PDFs",
            variable=self.bates_mode_var,
            value="continuous",
            command=self._on_bates_mode_change,
        ).pack(side="left", padx=6)
        ctk.CTkRadioButton(
            mode_frame,
            text="Separate Bates settings for each PDF",
            variable=self.bates_mode_var,
            value="separate",
            command=self._on_bates_mode_change,
        ).pack(side="left", padx=6)

        self.bates_mode_note_label = ctk.CTkLabel(
            frame,
            text="",
            wraplength=1050,
            justify="left",
        )
        self.bates_mode_note_label.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 4))

        self.continuous_bates_summary_frame = ctk.CTkFrame(frame)
        self.continuous_bates_summary_frame.grid(row=3, column=0, sticky="ew", padx=8, pady=(2, 4))
        self.continuous_bates_summary_frame.grid_columnconfigure(0, weight=1)
        self.continuous_bates_summary_label = ctk.CTkLabel(
            self.continuous_bates_summary_frame,
            text="Choose the continuous Bates settings. Every PDF in the merge list will receive Bates.",
            justify="left",
            wraplength=1000,
        )
        self.continuous_bates_summary_label.grid(row=0, column=0, sticky="w", padx=10, pady=7)

        self.separate_bates_frame = ctk.CTkFrame(frame)
        self.separate_bates_frame.grid(row=3, column=0, sticky="ew", padx=6, pady=(2, 4))
        self.separate_bates_frame.grid_columnconfigure(0, weight=1)
        self.separate_bates_frame.grid_columnconfigure(2, weight=1)

        left = ctk.CTkFrame(self.separate_bates_frame)
        left.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="Available PDFs / Merge Order").grid(
            row=0, column=0, columnspan=2, pady=(3, 1)
        )
        self.available_tree = ttk.Treeview(
            left,
            columns=("order", "file", "pages"),
            show="headings",
            height=4,
            selectmode="extended",
        )
        for key, title, width in (("order", "Order", 55), ("file", "File", 300), ("pages", "Pages", 65)):
            self.available_tree.heading(key, text=title)
            self.available_tree.column(key, width=width, anchor="w" if key == "file" else "center")
        self.available_tree.grid(row=1, column=0, sticky="nsew", padx=(4, 0), pady=3)
        available_scroll = ctk.CTkScrollbar(left, command=self.available_tree.yview)
        available_scroll.grid(row=1, column=1, sticky="ns", padx=(0, 4), pady=3)
        self.available_tree.configure(yscrollcommand=available_scroll.set)
        order_buttons = ctk.CTkFrame(left, fg_color="transparent")
        order_buttons.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 3))
        ctk.CTkButton(
            order_buttons, text="Move PDF Up", width=105, command=lambda: self._move_available_pdf(-1)
        ).pack(side="left", padx=(0, 3))
        ctk.CTkButton(
            order_buttons, text="Move PDF Down", width=115, command=lambda: self._move_available_pdf(1)
        ).pack(side="left", padx=3)

        middle = ctk.CTkFrame(self.separate_bates_frame)
        middle.grid(row=0, column=1, padx=5, pady=4, sticky="ns")
        self.add_selected_bates_button = ctk.CTkButton(
            middle, text="Add Selected →", width=125, command=self._add_to_bates_queue
        )
        self.add_selected_bates_button.pack(pady=(12, 4))
        ctk.CTkButton(
            middle, text="← Remove Bates", width=125, command=self._remove_from_bates_queue
        ).pack(pady=4)
        ctk.CTkButton(
            middle, text="Duplicate PDF", width=125, command=self._duplicate_bates_queue
        ).pack(pady=4)
        ctk.CTkButton(
            middle, text="Clear Bates", width=125, command=self._clear_bates_queue
        ).pack(pady=4)

        right = ctk.CTkFrame(self.separate_bates_frame)
        right.grid(row=0, column=2, sticky="nsew", padx=4, pady=4)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(right, text="Bates Settings").grid(
            row=0, column=0, columnspan=2, pady=(3, 1)
        )
        self.queue_tree = ttk.Treeview(
            right,
            columns=("order", "file", "bates", "position", "pages"),
            show="headings",
            height=4,
        )
        for key, title, width in (
            ("order", "#", 35),
            ("file", "PDF", 180),
            ("bates", "Saved Bates", 150),
            ("position", "Position", 100),
            ("pages", "Pages", 55),
        ):
            self.queue_tree.heading(key, text=title)
            self.queue_tree.column(key, width=width, anchor="w" if key in {"file", "bates"} else "center")
        self.queue_tree.grid(row=1, column=0, sticky="nsew", padx=(4, 0), pady=3)
        queue_scroll = ctk.CTkScrollbar(right, command=self.queue_tree.yview)
        queue_scroll.grid(row=1, column=1, sticky="ns", padx=(0, 4), pady=3)
        self.queue_tree.configure(yscrollcommand=queue_scroll.set)
        self.queue_tree.bind("<Double-1>", lambda _event: self._open_merge_bates_preview())

        self.merge_bates_preview_button = ctk.CTkButton(
            frame,
            text="Preview & Set Continuous Bates",
            width=260,
            height=38,
            fg_color=PREVIEW_BUTTON_COLOR,
            hover_color=PREVIEW_BUTTON_HOVER,
            text_color="white",
            command=self._open_merge_bates_preview,
        )
        self.merge_bates_preview_button.grid(row=4, column=0, sticky="w", padx=10, pady=(2, 6))

        self.bates_validation_label = ctk.CTkLabel(frame, text="", text_color="red")
        self.bates_validation_label.grid(row=5, column=0, sticky="w", padx=10, pady=(0, 5))
        self._update_bates_mode_controls()

    def _create_bates_simple_panel(self) -> None:
        frame = self.bates_simple_frame
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Bates", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(7, 2)
        )
        self.bates_simple_summary_label = ctk.CTkLabel(
            frame,
            text="Not configured. Open the preview to enter the Bates details and choose the position.",
            justify="left",
            wraplength=1000,
        )
        self.bates_simple_summary_label.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 4))
        self.bates_simple_preview_button = ctk.CTkButton(
            frame,
            text="Preview & Set Bates",
            width=260,
            height=38,
            fg_color=PREVIEW_BUTTON_COLOR,
            hover_color=PREVIEW_BUTTON_HOVER,
            text_color="white",
            command=self._open_bates_preview,
        )
        self.bates_simple_preview_button.grid(row=2, column=0, sticky="w", padx=10, pady=(1, 6))
        self.bates_simple_validation_label = ctk.CTkLabel(frame, text="", text_color="red")
        self.bates_simple_validation_label.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 5))

    def _create_tab2(self) -> None:
        self.tab2.grid_columnconfigure(0, weight=1)
        input_frame = ctk.CTkFrame(self.tab2)
        input_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        input_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(input_frame, text="PDF to split:").grid(row=0, column=0, padx=5, pady=5)
        self.split_input = ctk.CTkEntry(input_frame)
        self.split_input.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ctk.CTkButton(input_frame, text="Browse", command=self._browse_split_file).grid(row=0, column=2, padx=5, pady=5)

        mode = ctk.CTkFrame(self.tab2)
        mode.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        mode.grid_columnconfigure(1, weight=1)
        self.split_mode = ctk.StringVar(value="ranges")
        ctk.CTkRadioButton(mode, text="By ranges", variable=self.split_mode, value="ranges", command=self._split_mode_change).grid(row=0, column=0, padx=8, pady=5, sticky="w")
        self.split_ranges = ctk.CTkEntry(mode, placeholder_text="1-12, 15, 20-25")
        self.split_ranges.grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        ctk.CTkRadioButton(mode, text="Pages per file", variable=self.split_mode, value="pages", command=self._split_mode_change).grid(row=1, column=0, padx=8, pady=5, sticky="w")
        self.split_pages = ctk.CTkEntry(mode, width=100, placeholder_text="25")
        self.split_pages.grid(row=1, column=1, sticky="w", padx=8, pady=5)
        self.split_pages.configure(state="disabled")

        output = ctk.CTkFrame(self.tab2)
        output.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        output.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(output, text="Output folder:").grid(row=0, column=0, padx=5, pady=5)
        self.split_output = ctk.CTkEntry(output)
        self.split_output.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ctk.CTkButton(output, text="Browse", command=self._browse_split_output).grid(row=0, column=2, padx=5, pady=5)
        self.split_subfolder_var = ctk.BooleanVar(value=self.settings.get("auto_subfolder", True))
        ctk.CTkCheckBox(output, text="Create case subfolder", variable=self.split_subfolder_var).grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        actions = ctk.CTkFrame(self.tab2)
        actions.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(actions, text="Split PDF", fg_color="green", command=self._run_split).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(actions, text="Clear", command=self._clear_tab2).pack(side="left", padx=8, pady=8)

    # ------------------------------------------------------------------
    # Small widget builders
    # ------------------------------------------------------------------
    @staticmethod
    def _add_entry(parent, label, row, column, width=100):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=column, padx=5, pady=5, sticky="w")
        entry = ctk.CTkEntry(parent, width=width)
        entry.grid(row=row, column=column + 1, padx=5, pady=5, sticky="w")
        return entry

    @staticmethod
    def _add_combo(parent, label, values, row, column, width=120):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=column, padx=5, pady=5, sticky="w")
        combo = ctk.CTkComboBox(parent, values=values, width=width)
        combo.grid(row=row, column=column + 1, padx=5, pady=5, sticky="w")
        return combo

    def _add_color(self, parent, label, row, column):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=column, padx=5, pady=5, sticky="w")
        holder = ctk.CTkFrame(parent, fg_color="transparent")
        holder.grid(row=row, column=column + 1, padx=5, pady=5, sticky="w")
        entry = ctk.CTkEntry(holder, width=85)
        entry.pack(side="left")
        ctk.CTkButton(holder, text="Pick", width=45, command=lambda: self._pick_color(entry)).pack(side="left", padx=3)
        return entry

    @staticmethod
    def _set_entry(entry, value) -> None:
        entry.delete(0, "end")
        entry.insert(0, str(value))

    def _pick_color(self, entry) -> None:
        selected = colorchooser.askcolor(title="Choose colour", parent=self)[1]
        if selected:
            self._set_entry(entry, selected)

    # ------------------------------------------------------------------
    # Input list handling
    # ------------------------------------------------------------------
    def _pdf_info_from_path(self, path: str) -> PDFFileInfo:
        try:
            pages = validate_readable_pdf(path)
            status = "OK"
        except Exception as exc:
            pages = 0
            status = f"Needs review: {exc}"
        return PDFFileInfo(path=path, filename=Path(path).name, pages=pages, status=status)

    def _open_pdf_arrangement(self) -> None:
        if not self.merge_var.get():
            messagebox.showinfo("Preview & Arrange PDFs", "Select Merge PDFs first.", parent=self)
            return
        PDFArrangeDialog(
            self,
            self.pdf_files,
            self.selected_folder or self.folder_entry.get().strip(),
            self._apply_pdf_arrangement,
        )

    def _apply_pdf_arrangement(
        self,
        arranged_files: list[PDFFileInfo],
        selected_folder: str,
    ) -> None:
        valid_ids = {item.entry_id for item in arranged_files}
        self.pdf_files = arranged_files
        self.selected_folder = selected_folder or self.selected_folder
        if self.selected_folder:
            self._set_entry(self.folder_entry, self.selected_folder)
            self.settings.set("last_folder_path", self.selected_folder)
        self.bates_queue = [
            item for item in self.bates_queue if item.source_entry_id in valid_ids
        ]
        self._refresh_pdf_tree()
        if self.bates_mode_var.get() == "continuous":
            self._recalculate_continuous_bates_queue()
        else:
            self._sort_bates_queue_by_merge_order()
            self._refresh_queue_tree()

    def _update_pdf_summary(self) -> None:
        if not hasattr(self, "pdf_summary_label"):
            return
        total_pages = sum(item.pages for item in self.pdf_files if item.status == "OK")
        if not self.pdf_files:
            text = "No PDFs selected. Choose a folder, then open Preview & Arrange PDFs if needed."
        else:
            text = f"{len(self.pdf_files)} PDF(s) selected — {total_pages} total page(s)."
        self.pdf_summary_label.configure(text=text)

    def _automatic_output_base(self, merge: bool) -> str:
        if merge:
            folder = self.selected_folder or self.folder_entry.get().strip()
            if folder:
                return folder
            if self.pdf_files:
                return str(Path(self.pdf_files[0].path).parent)
            raise ValueError("Select a folder containing PDFs.")
        path = self.file_entry.get().strip()
        if not path:
            raise ValueError("Select a PDF file.")
        return str(Path(path).parent)

    def _browse_folder(self) -> None:
        folder = filedialog.askdirectory(
            title="Select folder containing PDFs",
            initialdir=self.settings.get("last_folder_path", ""),
        )
        if not folder:
            return
        self.selected_folder = folder
        self.settings.set("last_folder_path", folder)
        self._set_entry(self.folder_entry, folder)
        files = sorted(
            [name for name in os.listdir(folder) if name.lower().endswith(".pdf")],
            key=natural_sort_key,
        )
        self.pdf_files = [
            self._pdf_info_from_path(os.path.join(folder, name)) for name in files
        ]
        self.bates_queue.clear()
        self._refresh_pdf_tree()
        if self.bates_mode_var.get() == "continuous":
            self._recalculate_continuous_bates_queue()
        else:
            self._sort_bates_queue_by_merge_order()
            self._refresh_queue_tree()

    def _add_pdf_files(self) -> None:
        """Compatibility helper; normal additions are made in Preview & Arrange PDFs."""
        paths = filedialog.askopenfilenames(
            filetypes=[("PDF files", "*.pdf")],
            initialdir=self.settings.get("last_file_path", ""),
        )
        for path in sorted(paths, key=lambda item: natural_sort_key(Path(item).name)):
            if any(Path(item.path).resolve() == Path(path).resolve() for item in self.pdf_files):
                if not messagebox.askyesno(
                    "Add duplicate PDF",
                    f"{Path(path).name} is already selected. Add another occurrence?",
                    parent=self,
                ):
                    continue
            self._append_pdf(path)
        if paths:
            self.settings.set("last_file_path", str(Path(paths[0]).parent))
            if not self.selected_folder:
                self.selected_folder = str(Path(paths[0]).parent)
                self._set_entry(self.folder_entry, self.selected_folder)
        self._refresh_pdf_tree()
        if self.bates_mode_var.get() == "continuous":
            self._recalculate_continuous_bates_queue()
        else:
            self._sort_bates_queue_by_merge_order()
            self._refresh_queue_tree()

    def _append_pdf(self, path: str) -> None:
        try:
            pages = validate_readable_pdf(path)
            status = "OK"
        except Exception as exc:
            pages = 0
            status = f"Needs review: {exc}"
        self.pdf_files.append(PDFFileInfo(path=path, filename=Path(path).name, pages=pages, status=status))

    def _refresh_pdf_tree(self) -> None:
        if hasattr(self, "pdf_tree"):
            self.pdf_tree.delete(*self.pdf_tree.get_children())
        if hasattr(self, "available_tree"):
            self.available_tree.delete(*self.available_tree.get_children())
        for index, item in enumerate(self.pdf_files, 1):
            iid = item.entry_id
            if hasattr(self, "pdf_tree"):
                self.pdf_tree.insert(
                    "", "end", iid=iid, values=(index, item.filename, item.pages, item.status)
                )
            if hasattr(self, "available_tree") and item.status == "OK":
                self.available_tree.insert(
                    "", "end", iid=iid, values=(index, item.filename, item.pages)
                )
        self._update_pdf_summary()

    def _selected_pdf_index(self) -> Optional[int]:
        if not hasattr(self, "pdf_tree"):
            return None
        selection = self.pdf_tree.selection()
        if not selection:
            return None
        return next((i for i, item in enumerate(self.pdf_files) if item.entry_id == selection[0]), None)

    def _remove_pdf(self) -> None:
        index = self._selected_pdf_index()
        if index is not None:
            removed_id = self.pdf_files[index].entry_id
            del self.pdf_files[index]
            self.bates_queue = [
                item for item in self.bates_queue if item.source_entry_id != removed_id
            ]
            self._refresh_pdf_tree()
            if self.bates_mode_var.get() == "continuous":
                self._recalculate_continuous_bates_queue()
            else:
                self._sort_bates_queue_by_merge_order()
                self._refresh_queue_tree()

    def _duplicate_source_occurrence(self, source: PDFFileInfo) -> PDFFileInfo:
        index = next(
            (i for i, item in enumerate(self.pdf_files) if item.entry_id == source.entry_id),
            len(self.pdf_files) - 1,
        )
        duplicate = replace(source, entry_id=uuid4().hex)
        self.pdf_files.insert(index + 1, duplicate)
        self._refresh_pdf_tree()
        if self.bates_mode_var.get() == "continuous":
            self._recalculate_continuous_bates_queue()
        else:
            self._sort_bates_queue_by_merge_order()
            self._refresh_queue_tree()
        return duplicate

    def _duplicate_pdf(self) -> None:
        index = self._selected_pdf_index()
        if index is None:
            messagebox.showinfo("Duplicate PDF", "Select a PDF first.", parent=self)
            return
        source = self.pdf_files[index]
        if not messagebox.askyesno(
            "Add duplicate PDF",
            f"Add another occurrence of {source.filename}?",
            parent=self,
        ):
            return
        duplicate = self._duplicate_source_occurrence(source)
        self.pdf_tree.selection_set(duplicate.entry_id)

    def _move_pdf_entry(self, entry_id: str, direction: int) -> Optional[str]:
        index = next((i for i, item in enumerate(self.pdf_files) if item.entry_id == entry_id), None)
        if index is None:
            return None
        new_index = index + direction
        if not 0 <= new_index < len(self.pdf_files):
            return entry_id
        item = self.pdf_files.pop(index)
        self.pdf_files.insert(new_index, item)
        self._refresh_pdf_tree()
        if self.bates_mode_var.get() == "continuous":
            self._recalculate_continuous_bates_queue()
        else:
            self._sort_bates_queue_by_merge_order()
            self._refresh_queue_tree()
        return item.entry_id

    def _move_pdf(self, direction: int) -> None:
        index = self._selected_pdf_index()
        if index is None:
            return
        entry_id = self.pdf_files[index].entry_id
        moved = self._move_pdf_entry(entry_id, direction)
        if moved:
            self.pdf_tree.selection_set(moved)

    def _move_available_pdf(self, direction: int) -> None:
        selection = self.available_tree.selection()
        if not selection:
            messagebox.showinfo("Merge order", "Select a PDF from Available PDFs first.", parent=self)
            return
        moved = self._move_pdf_entry(selection[0], direction)
        if moved:
            self.available_tree.selection_set(moved)
            self.available_tree.focus(moved)

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("PDF files", "*.pdf")],
            initialdir=self.settings.get("last_file_path", ""),
        )
        if path:
            self.selected_file = path
            self._set_entry(self.file_entry, path)
            self.settings.set("last_file_path", str(Path(path).parent))

    def _browse_output(self) -> None:
        messagebox.showinfo(
            "Automatic output folder",
            "Output is created automatically inside a MedVai_Output subfolder beside the input PDF(s).",
            parent=self,
        )

    # ------------------------------------------------------------------
    # Bates queue handling
    # ------------------------------------------------------------------
    @staticmethod
    def _blank_bates_values() -> dict[str, Any]:
        return {
            "prefix": "",
            "symbol": "",
            "start_number": "",
            "padding": 6,
            "suffix": "",
            "placement": "Bottom-Right",
            "color": "#000000",
            "font_name": "Helvetica",
            "font_size": 11,
            "bold": False,
            "opacity": 1.0,
            "offset_x": 32,
            "offset_y": 24,
            "position_x_ratio": None,
            "position_y_ratio": None,
        }

    @staticmethod
    def _default_numbering_values() -> dict[str, Any]:
        return {
            "pattern": "{n}",
            "start_number": 1,
            "placement": "Bottom-Center",
            "color": "#000000",
            "font_name": "Helvetica",
            "font_size": 10,
            "bold": False,
            "opacity": 1.0,
            "offset_x": 32,
            "offset_y": 24,
            "position_x_ratio": None,
            "position_y_ratio": None,
        }

    @staticmethod
    def _bates_item_values(item: BatesQueueItem) -> dict[str, Any]:
        return {
            "prefix": item.prefix,
            "symbol": item.symbol,
            "start_number": item.start_number,
            "padding": item.padding,
            "suffix": item.suffix,
            "placement": item.placement,
            "color": item.color,
            "font_name": item.font_name,
            "font_size": item.font_size,
            "bold": item.bold,
            "opacity": item.opacity,
            "offset_x": item.offset_x,
            "offset_y": item.offset_y,
            "position_x_ratio": item.position_x_ratio,
            "position_y_ratio": item.position_y_ratio,
        }

    def _open_new_bates_item(
        self,
        source: PDFFileInfo,
        *,
        insert_index: Optional[int] = None,
        after_save=None,
    ) -> None:
        """Open blank Bates settings for one separate per-file queue occurrence."""
        values = self._blank_bates_values()

        def save_callback(saved_bates, _saved_numbering):
            if not saved_bates:
                return
            item = BatesQueueItem(
                file_path=source.path,
                filename=source.filename,
                pages_in_source=source.pages,
                source_entry_id=source.entry_id,
                entry_id=uuid4().hex,
                **saved_bates,
            )
            PDFProcessor(self.settings)._validate_bates_item(item)
            if insert_index is None:
                self.bates_queue.append(item)
            else:
                self.bates_queue.insert(insert_index, item)
            self.bates_validation_label.configure(text="")
            self._sort_bates_queue_by_merge_order()
            self._refresh_queue_tree()
            self.queue_tree.selection_set(item.entry_id)
            if after_save is not None:
                after_save()

        PlacementPreviewDialog(self, source.path, True, False, values, None, save_callback)

    def _continuous_item_from_source(
        self,
        source: PDFFileInfo,
        *,
        entry_id: Optional[str] = None,
    ) -> BatesQueueItem:
        if not self.continuous_bates_configured:
            raise ValueError("Open Preview & Set Continuous Bates and save the Bates settings first.")
        values = dict(self.continuous_bates_values)
        values["start_number"] = int(values["start_number"])
        return BatesQueueItem(
            file_path=source.path,
            filename=source.filename,
            pages_in_source=source.pages,
            source_entry_id=source.entry_id,
            entry_id=entry_id or uuid4().hex,
            **values,
        )

    def _recalculate_continuous_bates_queue(self) -> None:
        """Build one uninterrupted Bates sequence through every PDF in merge order."""
        if self.bates_mode_var.get() != "continuous":
            return
        if not self.continuous_bates_configured:
            self.bates_queue = []
            self._refresh_queue_tree()
            if hasattr(self, "continuous_bates_summary_label"):
                self.continuous_bates_summary_label.configure(
                    text="Choose the continuous Bates settings. Every PDF in the merge list will receive Bates."
                )
            return

        next_number = int(self.continuous_bates_values["start_number"])
        common_values = dict(self.continuous_bates_values)
        common_values.pop("start_number", None)
        old_ids = {
            item.source_entry_id: item.entry_id
            for item in self.bates_queue
            if item.source_entry_id
        }
        updated_queue: list[BatesQueueItem] = []
        for source in self.pdf_files:
            if source.status != "OK":
                continue
            item = BatesQueueItem(
                file_path=source.path,
                filename=source.filename,
                pages_in_source=source.pages,
                source_entry_id=source.entry_id,
                entry_id=old_ids.get(source.entry_id, uuid4().hex),
                start_number=next_number,
                **common_values,
            )
            PDFProcessor(self.settings)._validate_bates_item(item)
            updated_queue.append(item)
            next_number += source.pages
        self.bates_queue = updated_queue
        self._refresh_queue_tree()

        if self.bates_queue:
            first = self.bates_queue[0].format_number(self.bates_queue[0].start_number)
            last_item = self.bates_queue[-1]
            last = last_item.format_number(last_item.start_number + last_item.pages_in_source - 1)
            summary = (
                f"All {len(self.bates_queue)} PDFs will receive continuous Bates: "
                f"{first} through {last}."
            )
            self.bates_validation_label.configure(text=summary, text_color="green")
            if hasattr(self, "continuous_bates_summary_label"):
                self.continuous_bates_summary_label.configure(text=summary)
        else:
            self.bates_validation_label.configure(
                text="Add PDFs to the merge list before running.", text_color="red"
            )
            if hasattr(self, "continuous_bates_summary_label"):
                self.continuous_bates_summary_label.configure(
                    text="Continuous Bates is configured, but there are no PDFs in the merge list."
                )

    def _set_continuous_bates_values(self, values: dict[str, Any]) -> None:
        self.continuous_bates_values = dict(values)
        self.continuous_bates_configured = True
        self._recalculate_continuous_bates_queue()

    def _sample_source_for_merge_bates(self) -> PDFFileInfo:
        queue_index = self._selected_bates_index()
        if queue_index is not None:
            item = self.bates_queue[queue_index]
            return PDFFileInfo(
                path=item.file_path,
                filename=item.filename,
                pages=item.pages_in_source,
                entry_id=item.source_entry_id or uuid4().hex,
            )
        selection = self.available_tree.selection()
        if selection:
            source = next((item for item in self.pdf_files if item.entry_id == selection[0]), None)
            if source is not None:
                return source
        source = next((item for item in self.pdf_files if item.status == "OK"), None)
        if source is None:
            raise ValueError("Select a folder or add a PDF before opening the Bates preview.")
        return source

    def _open_continuous_bates_preview(self, *, after_save=None) -> None:
        source = self._sample_source_for_merge_bates()
        values = (
            dict(self.continuous_bates_values)
            if self.continuous_bates_configured
            else self._blank_bates_values()
        )

        def save_callback(saved_bates, _saved_numbering):
            if not saved_bates:
                return
            self._set_continuous_bates_values(saved_bates)
            if after_save is not None:
                after_save()

        PlacementPreviewDialog(self, source.path, True, False, values, None, save_callback)

    def _add_to_bates_queue(self) -> None:
        if self.bates_mode_var.get() == "continuous":
            self._open_continuous_bates_preview()
            return

        selected_ids = set(self.available_tree.selection())
        if not selected_ids:
            self.bates_validation_label.configure(
                text="Select one or more PDFs from Available PDFs.", text_color="red"
            )
            return
        sources = [item for item in self.pdf_files if item.entry_id in selected_ids and item.status == "OK"]

        def open_next(index: int) -> None:
            if index >= len(sources):
                self.bates_validation_label.configure(
                    text=f"Bates settings saved for {len(sources)} selected PDF(s).",
                    text_color="green",
                )
                return
            source = sources[index]
            if any(item.source_entry_id == source.entry_id for item in self.bates_queue):
                if not messagebox.askyesno(
                    "Add duplicate PDF",
                    f"{source.filename} already has Bates settings. Add another occurrence to the merged PDF?",
                    parent=self,
                ):
                    open_next(index + 1)
                    return
                source = self._duplicate_source_occurrence(source)
            self._open_new_bates_item(source, after_save=lambda: open_next(index + 1))

        open_next(0)

    def _add_all_to_bates_queue(self) -> None:
        """Backward-compatible helper: continuous mode always includes every merge PDF."""
        if self.bates_mode_var.get() != "continuous":
            messagebox.showinfo(
                "Continuous Bates",
                "Select Continuous Bates to apply one sequence across every PDF.",
                parent=self,
            )
            return
        if self.continuous_bates_configured:
            self._recalculate_continuous_bates_queue()
        else:
            self._open_continuous_bates_preview()

    def _sort_bates_queue_by_merge_order(self) -> None:
        positions = {item.entry_id: index for index, item in enumerate(self.pdf_files)}
        self.bates_queue.sort(
            key=lambda item: positions.get(item.source_entry_id, len(positions) + 1)
        )

    def _refresh_queue_tree(self) -> None:
        self.queue_tree.delete(*self.queue_tree.get_children())
        for index, item in enumerate(self.bates_queue, 1):
            sample = item.format_number(item.start_number)
            self.queue_tree.insert(
                "",
                "end",
                iid=item.entry_id,
                values=(index, item.filename, sample, item.placement, item.pages_in_source),
            )

    def _selected_bates_index(self) -> Optional[int]:
        selection = self.queue_tree.selection()
        if not selection:
            return None
        return next((i for i, item in enumerate(self.bates_queue) if item.entry_id == selection[0]), None)

    def _remove_from_bates_queue(self) -> None:
        index = self._selected_bates_index()
        if index is None:
            messagebox.showinfo("Bates Settings", "Select a Bates Settings entry first.", parent=self)
            return
        del self.bates_queue[index]
        if self.bates_mode_var.get() == "continuous":
            self._recalculate_continuous_bates_queue()
        else:
            self._refresh_queue_tree()

    def _load_selected_bates(self) -> None:
        if self.bates_mode_var.get() == "continuous":
            self._open_continuous_bates_preview()
            return
        index = self._selected_bates_index()
        if index is None:
            messagebox.showinfo("Bates Settings", "Select a Bates Settings entry to preview or edit.", parent=self)
            return
        item = self.bates_queue[index]

        def save_callback(saved_bates, _saved_numbering):
            if not saved_bates:
                return
            updated = replace(item, **saved_bates)
            PDFProcessor(self.settings)._validate_bates_item(updated)
            self.bates_queue[index] = updated
            self._refresh_queue_tree()
            self.queue_tree.selection_set(updated.entry_id)

        PlacementPreviewDialog(
            self,
            item.file_path,
            True,
            False,
            self._bates_item_values(item),
            None,
            save_callback,
        )

    def _save_selected_bates(self) -> None:
        self._load_selected_bates()

    def _duplicate_bates_queue(self) -> None:
        if self.bates_mode_var.get() == "continuous":
            messagebox.showinfo(
                "Continuous Bates",
                "Continuous Bates already includes every PDF in the merge list.",
                parent=self,
            )
            return
        index = self._selected_bates_index()
        if index is None:
            messagebox.showinfo("Duplicate PDF", "Select a Bates Settings entry first.", parent=self)
            return
        source_item = self.bates_queue[index]
        if not messagebox.askyesno(
            "Add duplicate PDF",
            f"Add another occurrence of {source_item.filename} to the merged PDF?\n\n"
            "You may enter the same or different Bates details.",
            parent=self,
        ):
            return
        source = next(
            (item for item in self.pdf_files if item.entry_id == source_item.source_entry_id),
            None,
        )
        if source is None:
            source = PDFFileInfo(
                path=source_item.file_path,
                filename=source_item.filename,
                pages=source_item.pages_in_source,
            )
            self.pdf_files.append(source)
            self._refresh_pdf_tree()
        duplicate_source = self._duplicate_source_occurrence(source)
        self._open_new_bates_item(duplicate_source, insert_index=index + 1)

    def _move_bates(self, direction: int) -> None:
        index = self._selected_bates_index()
        if index is None:
            return
        new_index = index + direction
        if 0 <= new_index < len(self.bates_queue):
            item = self.bates_queue.pop(index)
            self.bates_queue.insert(new_index, item)
            if self.bates_mode_var.get() == "continuous":
                self._recalculate_continuous_bates_queue()
            else:
                self._refresh_queue_tree()
            self.queue_tree.selection_set(item.entry_id)

    def _clear_bates_queue(self) -> None:
        self.bates_queue.clear()
        self._refresh_queue_tree()
        if self.bates_mode_var.get() == "continuous" and self.continuous_bates_configured:
            self._set_continuous_bates_values(self.continuous_bates_values)
        else:
            self.bates_validation_label.configure(text="")

    def _open_merge_bates_preview(self) -> None:
        """Open the clearly separated Bates preview button action."""
        try:
            if self.bates_mode_var.get() == "continuous":
                self._open_continuous_bates_preview()
            else:
                self._load_selected_bates()
        except Exception as exc:
            messagebox.showwarning("Bates preview needs review", str(exc), parent=self)

    def _on_bates_mode_change(self) -> None:
        new_mode = self.bates_mode_var.get()
        if new_mode == self._last_bates_mode:
            self._update_bates_mode_controls()
            return
        if self.bates_queue and not messagebox.askyesno(
            "Change Bates mode",
            "Changing Bates mode will clear the current Bates Settings. Continue?",
            parent=self,
        ):
            self.bates_mode_var.set(self._last_bates_mode)
            return
        self.bates_queue.clear()
        self._last_bates_mode = new_mode
        self.bates_validation_label.configure(text="")
        self._refresh_queue_tree()
        self._update_bates_mode_controls()

    def _update_bates_mode_controls(self) -> None:
        if not hasattr(self, "bates_mode_note_label"):
            return
        continuous = self.bates_mode_var.get() == "continuous"
        if continuous:
            self.bates_mode_note_label.configure(
                text="All PDFs in the arranged merge list receive one continuous Bates sequence."
            )
            self.separate_bates_frame.grid_remove()
            self.continuous_bates_summary_frame.grid()
            self.merge_bates_preview_button.configure(text="Preview & Set Continuous Bates")
            self._recalculate_continuous_bates_queue()
        else:
            self.bates_mode_note_label.configure(
                text="Only PDFs listed in Bates Settings receive Bates. All arranged PDFs still remain in the merged output."
            )
            self.continuous_bates_summary_frame.grid_remove()
            self.separate_bates_frame.grid()
            self.merge_bates_preview_button.configure(text="Preview & Edit Selected Bates")
            self._sort_bates_queue_by_merge_order()
            self._refresh_queue_tree()

    def _numbering_values(self) -> dict[str, Any]:
        return dict(self.numbering_values_store)

    def _set_numbering_values(self, values: dict[str, Any]) -> None:
        self.numbering_values_store = dict(values)
        self.numbering_configured = True
        pattern = values.get("pattern", "{n}")
        start = values.get("start_number", 1)
        position = values.get("placement", "Custom")
        self.numbering_summary_label.configure(
            text=f"Saved: {pattern.replace('{n}', str(start))}  |  Position: {position}  |  Colour: {values.get('color', '#000000')}"
        )

    def _set_simple_bates_values(self, values: dict[str, Any]) -> None:
        self.simple_bates_values = dict(values)
        self.simple_bates_configured = True
        try:
            sample = BatesQueueItem(
                file_path="",
                filename="",
                pages_in_source=1,
                **values,
            ).format_number(int(values["start_number"]))
        except Exception:
            sample = "Saved"
        self.bates_simple_summary_label.configure(
            text=f"Saved Bates: {sample}  |  Position: {values.get('placement', 'Custom')}  |  Colour: {values.get('color', '#000000')}"
        )

    def _build_numbering_config(self) -> NumberingConfig:
        if not self.numbering_configured:
            raise ValueError("Open Preview & Set Numbering, then save the numbering settings.")
        return NumberingConfig(enabled=True, **self._numbering_values())

    def _build_simple_bates_item(self) -> BatesQueueItem:
        if not self.simple_bates_configured:
            raise ValueError("Open Preview & Set Bates, then save the Bates settings.")
        path = self.file_entry.get().strip()
        pages = validate_readable_pdf(path)
        return BatesQueueItem(
            file_path=path,
            filename=Path(path).name,
            pages_in_source=pages,
            **self.simple_bates_values,
        )

    def _sample_pdf_for_bates_preview(self) -> str:
        path = self.file_entry.get().strip()
        validate_readable_pdf(path)
        return path

    def _open_bates_preview(self) -> None:
        if not self.bates_var.get():
            messagebox.showinfo("Bates Preview", "Select Apply Bates first.", parent=self)
            return
        if self.merge_var.get():
            self._load_selected_bates()
            return
        try:
            path = self._sample_pdf_for_bates_preview()
            values = dict(self.simple_bates_values) if self.simple_bates_configured else self._blank_bates_values()

            def save_callback(saved_bates, _saved_numbering):
                if saved_bates:
                    self._set_simple_bates_values(saved_bates)
                    self.bates_simple_validation_label.configure(text="")

            PlacementPreviewDialog(self, path, True, False, values, None, save_callback)
        except Exception as exc:
            messagebox.showwarning("Bates preview needs review", str(exc), parent=self)

    def _sample_pdf_for_numbering_preview(self) -> str:
        if self.merge_var.get():
            source = next((item for item in self.pdf_files if item.status == "OK"), None)
            if source is None:
                raise ValueError("Select a folder or add a PDF before opening the numbering preview.")
            return source.path
        path = self.file_entry.get().strip()
        validate_readable_pdf(path)
        return path

    def _open_numbering_preview(self) -> None:
        if not self.numbering_var.get():
            messagebox.showinfo("Numbering Preview", "Select Apply Numbering first.", parent=self)
            return
        try:
            path = self._sample_pdf_for_numbering_preview()
            values = dict(self.numbering_values_store)

            def save_callback(_saved_bates, saved_numbering):
                if saved_numbering:
                    self._set_numbering_values(saved_numbering)

            PlacementPreviewDialog(self, path, False, True, None, values, save_callback)
        except Exception as exc:
            messagebox.showwarning("Numbering preview needs review", str(exc), parent=self)

    def _validate_tab1(self, show_message: bool = True) -> bool:
        try:
            merge = self.merge_var.get()
            bates = self.bates_var.get()
            numbering = self.numbering_var.get()
            if not any((merge, bates, numbering)):
                raise ValueError("Select at least one operation.")
            if merge:
                if not self.pdf_files:
                    raise ValueError("Select a folder containing at least one PDF.")
                for info in self.pdf_files:
                    validate_readable_pdf(info.path)
                if bates:
                    if self.bates_mode_var.get() == "continuous":
                        if not self.continuous_bates_configured:
                            raise ValueError("Open Preview & Set Continuous Bates, then save the Bates settings.")
                        self._recalculate_continuous_bates_queue()
                    if not self.bates_queue:
                        raise ValueError("Add Bates settings for at least one PDF.")
                    valid_source_ids = {info.entry_id for info in self.pdf_files}
                    for item in self.bates_queue:
                        if item.source_entry_id and item.source_entry_id not in valid_source_ids:
                            raise ValueError(f"Bates settings refer to a PDF that is no longer in the arranged list: {item.filename}.")
                        validate_readable_pdf(item.file_path)
                        PDFProcessor(self.settings)._validate_bates_item(item)
            else:
                validate_readable_pdf(self.file_entry.get().strip())
                if bates:
                    PDFProcessor(self.settings)._validate_bates_item(self._build_simple_bates_item())
            if numbering:
                PDFProcessor(self.settings)._validate_numbering_config(self._build_numbering_config())
            self._automatic_output_base(merge)
            self.validation_label.configure(text="✓ All checks passed.", text_color="green")
            if show_message:
                messagebox.showinfo("Validation", "All checks passed.", parent=self)
            return True
        except Exception as exc:
            self.validation_label.configure(text=f"Needs review: {exc}", text_color="red")
            if show_message:
                messagebox.showwarning("Validation needs review", str(exc), parent=self)
            return False

    def _run_tab1(self) -> None:
        if not self._validate_tab1(show_message=False):
            messagebox.showwarning("Validation needs review", self.validation_label.cget("text"), parent=self)
            return

        merge = bool(self.merge_var.get())
        bates = bool(self.bates_var.get())
        numbering = bool(self.numbering_var.get())
        pdf_files = deepcopy(self.pdf_files) if merge else []
        if bates and not merge:
            bates_queue = [self._build_simple_bates_item()]
        else:
            bates_queue = deepcopy(self.bates_queue)
        config = self._build_numbering_config() if numbering else None
        single_file = "" if merge else self.file_entry.get().strip()
        output_folder = self._automatic_output_base(merge)
        busy = self._show_busy_dialog("Processing PDF", "Processing and verifying every selected page…")

        def work() -> None:
            try:
                result = PDFProcessor(self.settings).process_tab1(
                    merge_enabled=merge,
                    bates_enabled=bates,
                    numbering_enabled=numbering,
                    pdf_files=pdf_files,
                    single_file=single_file,
                    bates_queue=bates_queue,
                    numbering_config=config,
                    output_folder=output_folder,
                    auto_subfolder=True,
                    output_base_name="",
                )
                self.after(0, lambda: self._finish_background_run(busy, result=result))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: self._finish_background_run(busy, error=message))

        Thread(target=work, daemon=True).start()

    def _show_busy_dialog(self, title: str, message: str):
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("480x180")
        dialog.resizable(False, False)
        set_window_icon(dialog, resource_path("assets"))
        dialog.transient(self)
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        ctk.CTkLabel(dialog, text=message, font=("Segoe UI", 14, "bold"), wraplength=420).pack(pady=(32, 18))
        progress = ctk.CTkProgressBar(dialog, mode="indeterminate", width=380)
        progress.pack(pady=8)
        progress.start()
        center_window(dialog)
        return dialog

    def _finish_background_run(
        self,
        busy,
        *,
        result: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        try:
            if busy.winfo_exists():
                busy.grab_release()
                busy.destroy()
        except Exception:
            pass
        if error is not None:
            messagebox.showwarning("Could Not Complete — Needs Review", error, parent=self)
        elif result is not None:
            self._show_completion(result)

    def _show_completion(self, result: dict[str, Any]) -> None:
        status = result.get("status", STATUS_REVIEW)
        dialog = ctk.CTkToplevel(self)
        dialog.title(status)
        dialog.geometry("650x430")
        dialog.minsize(600, 380)
        set_window_icon(dialog, resource_path("assets"))
        dialog.transient(self)
        dialog.grab_set()
        colour = "green" if status == STATUS_VERIFIED else "#c57c00"
        ctk.CTkLabel(dialog, text=status, font=("Segoe UI", 20, "bold"), text_color=colour).pack(pady=(20, 10))
        ctk.CTkLabel(dialog, text=f"Issue source: {result.get('issue_source', 'None identified')}").pack(pady=4)
        outputs = result.get("output_files") or []
        if outputs:
            ctk.CTkLabel(dialog, text=f"Main output: {Path(outputs[0]).name}", wraplength=580).pack(pady=4)
        else:
            ctk.CTkLabel(dialog, text="No usable PDF was created.").pack(pady=4)

        stats = result.get("stamp_stats") or {}
        lines = []
        for key, label in (("bates", "Bates"), ("numbering", "Numbering")):
            data = stats.get(key, {})
            if data.get("expected", 0):
                lines.append(
                    f"{label}: expected {data.get('expected', 0)}, verified {data.get('verified', 0)}, "
                    f"hard-stamped {data.get('hard_stamp', 0)}, needs review {data.get('needs_review', 0)}"
                )
        if lines:
            ctk.CTkLabel(dialog, text="\n".join(lines), justify="left").pack(pady=10)
        review_items = result.get("review_items") or []
        warnings = result.get("warnings") or []
        if review_items or warnings:
            box = ctk.CTkTextbox(dialog, height=130, width=580)
            box.pack(padx=20, pady=8, fill="both", expand=True)
            for item in warnings:
                box.insert("end", f"Warning: {item}\n")
            for item in review_items:
                box.insert("end", f"Needs review: {item}\n")
            box.configure(state="disabled")
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(pady=14)
        if result.get("output_folder"):
            ctk.CTkButton(buttons, text="Open Folder", fg_color="green", command=lambda: self._open_folder(result["output_folder"])).pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="Close", command=dialog.destroy).pack(side="left", padx=8)

    @staticmethod
    def _open_folder(folder: str) -> None:
        import platform
        import subprocess
        if platform.system() == "Windows":
            os.startfile(folder)
        elif platform.system() == "Darwin":
            subprocess.run(["open", folder], check=False)
        else:
            subprocess.run(["xdg-open", folder], check=False)

    # ------------------------------------------------------------------
    # Split
    # ------------------------------------------------------------------
    def _browse_split_file(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")], initialdir=self.settings.get("last_file_path", ""))
        if path:
            self._set_entry(self.split_input, path)
            if not self.split_output.get().strip():
                self._set_entry(self.split_output, str(Path(path).parent))

    def _browse_split_output(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.settings.get("last_output_path", ""))
        if folder:
            self._set_entry(self.split_output, folder)

    def _split_mode_change(self) -> None:
        ranges = self.split_mode.get() == "ranges"
        self.split_ranges.configure(state="normal" if ranges else "disabled")
        self.split_pages.configure(state="disabled" if ranges else "normal")

    def _run_split(self) -> None:
        try:
            input_path = self.split_input.get().strip()
            output_folder = self.split_output.get().strip()
            mode = self.split_mode.get()
            ranges = self.split_ranges.get().strip()
            pages_per_file = self.split_pages.get().strip()
            auto_subfolder = bool(self.split_subfolder_var.get())
            validate_readable_pdf(input_path)
            if mode == "pages":
                pages_per_file = int(pages_per_file)
            busy = self._show_busy_dialog("Splitting PDF", "Creating and checking every split output…")
        except Exception as exc:
            messagebox.showwarning("Split needs review", str(exc), parent=self)
            return

        def work() -> None:
            try:
                processor = PDFProcessor(self.settings)
                if mode == "ranges":
                    result = processor.split_by_ranges(
                        input_path, output_folder, ranges, auto_subfolder
                    )
                else:
                    result = processor.split_by_pages(
                        input_path, output_folder, pages_per_file, auto_subfolder
                    )
                self.after(0, lambda: self._finish_background_run(busy, result=result))
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: self._finish_background_run(busy, error=message))

        Thread(target=work, daemon=True).start()

    def _clear_tab2(self) -> None:
        for entry in (self.split_input, self.split_output, self.split_ranges, self.split_pages):
            entry.delete(0, "end")

    # ------------------------------------------------------------------
    # Mode, defaults and cleanup
    # ------------------------------------------------------------------
    def _refresh_mode_ui(self) -> None:
        merge = self.merge_var.get()
        bates = self.bates_var.get()
        numbering = self.numbering_var.get()

        if merge:
            self.merge_input_frame.grid()
            self.single_input_frame.grid_remove()
        else:
            self.merge_input_frame.grid_remove()
            self.single_input_frame.grid()

        if numbering:
            self.numbering_frame.grid()
        else:
            self.numbering_frame.grid_remove()

        if bates and merge:
            self.bates_merge_frame.grid()
            self.bates_simple_frame.grid_remove()
            self._update_bates_mode_controls()
        elif bates:
            self.bates_merge_frame.grid_remove()
            self.bates_simple_frame.grid()
        else:
            self.bates_merge_frame.grid_remove()
            self.bates_simple_frame.grid_remove()

        self.validation_label.configure(text="")

    def _load_defaults(self) -> None:
        self.simple_bates_values = self._blank_bates_values()
        self.simple_bates_configured = False
        self.bates_mode_var.set("continuous")
        self._last_bates_mode = "continuous"
        self.continuous_bates_values = self._blank_bates_values()
        self.continuous_bates_configured = False
        self.numbering_values_store = self._default_numbering_values()
        self.numbering_configured = False
        self.numbering_summary_label.configure(
            text="Not configured. Open the preview to choose the numbering format and position."
        )
        self.bates_simple_summary_label.configure(
            text="Not configured. Open the preview to enter the Bates details and choose the position."
        )
        self._update_bates_mode_controls()

    def _clear_tab1(self) -> None:
        for entry in (self.folder_entry, self.file_entry):
            entry.delete(0, "end")
        self.selected_folder = ""
        self.selected_file = ""
        self.pdf_files.clear()
        self.bates_queue.clear()
        self.simple_bates_values = self._blank_bates_values()
        self.simple_bates_configured = False
        self.bates_mode_var.set("continuous")
        self._last_bates_mode = "continuous"
        self.continuous_bates_values = self._blank_bates_values()
        self.continuous_bates_configured = False
        self.numbering_values_store = self._default_numbering_values()
        self.numbering_configured = False
        self.numbering_summary_label.configure(
            text="Not configured. Open the preview to choose the numbering format and position."
        )
        self.bates_simple_summary_label.configure(
            text="Not configured. Open the preview to enter the Bates details and choose the position."
        )
        self._refresh_pdf_tree()
        self._refresh_queue_tree()
        self._update_bates_mode_controls()
        self.validation_label.configure(text="")

    def _on_close(self) -> None:
        self.settings.set("geometry", self.geometry())
        self.settings.save()
        self.destroy()

if __name__ == "__main__":
    app = MedVaiPDFSuite()
    app.mainloop()
