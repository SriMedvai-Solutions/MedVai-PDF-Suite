"""Shared GUI helpers for MedVai PDF Suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from PIL import Image


def resource_path(relative_path: str) -> str:
    """Resolve an asset in source runs and PyInstaller builds."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent
    return str(base_path / relative_path)


def set_theme() -> None:
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")


def load_logo(assets_dir: str, height: int = 110):
    logo_path = Path(assets_dir) / "logo.png"
    if not logo_path.exists():
        return None
    with Image.open(logo_path) as source:
        image = source.convert("RGBA")
    ratio = height / max(image.height, 1)
    width = max(1, int(image.width * ratio))
    image = image.resize((width, height))
    return ctk.CTkImage(light_image=image, dark_image=image, size=(width, height))


def set_window_icon(window, assets_dir: Optional[str] = None) -> bool:
    """Apply the bundled icon when the platform supports it."""
    import tkinter as tk

    asset_root = Path(assets_dir or resource_path("assets"))
    candidates = [asset_root / name for name in ("logo.ico", "logo.png")]
    icon_path = next((path for path in candidates if path.exists()), None)
    if icon_path is None:
        return False

    if icon_path.suffix.casefold() == ".ico" and sys.platform.startswith("win"):
        try:
            window.iconbitmap(str(icon_path))
            window._medvai_icon_path = str(icon_path)
            return True
        except Exception:
            pass

    try:
        image = tk.PhotoImage(file=str(icon_path))
        window.iconphoto(True, image)
        window._medvai_icon_image = image
        return True
    except Exception:
        return False


def create_header(parent, title: str, logo_img=None):
    header = ctk.CTkFrame(parent, height=150, fg_color="#5CB7BC")
    header.grid(row=0, column=0, sticky="ew")
    header.grid_propagate(False)
    header.grid_columnconfigure(1, weight=1)
    if logo_img is not None:
        ctk.CTkLabel(header, image=logo_img, text="").grid(row=0, column=0, padx=20, pady=20)
    ctk.CTkLabel(
        header,
        text=title,
        font=("Segoe UI", 18, "bold"),
        text_color="white",
    ).grid(row=0, column=1, padx=20, pady=20, sticky="w")
    return header


def center_window(window) -> None:
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    x = max(0, (window.winfo_screenwidth() - width) // 2)
    y = max(0, (window.winfo_screenheight() - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def create_labeled_entry(parent, label: str, row: int, column: int = 0, width: int = 200, **kwargs):
    ctk.CTkLabel(parent, text=label).grid(row=row, column=column, padx=5, pady=5, sticky="w")
    entry = ctk.CTkEntry(parent, width=width, **kwargs)
    entry.grid(row=row, column=column + 1, padx=5, pady=5, sticky="ew")
    return entry


def create_labeled_combobox(parent, label: str, values: list[str], row: int, column: int = 0, width: int = 200, **kwargs):
    ctk.CTkLabel(parent, text=label).grid(row=row, column=column, padx=5, pady=5, sticky="w")
    combo = ctk.CTkComboBox(parent, values=values, width=width, **kwargs)
    combo.grid(row=row, column=column + 1, padx=5, pady=5, sticky="ew")
    return combo


def show_info(message: str, title: str = "Information") -> None:
    from tkinter import messagebox
    messagebox.showinfo(title, message)


def show_warning(message: str, title: str = "Warning") -> None:
    from tkinter import messagebox
    messagebox.showwarning(title, message)


def show_error(message: str, title: str = "Error") -> None:
    from tkinter import messagebox
    messagebox.showerror(title, message)


def ask_yes_no(message: str, title: str = "Confirm") -> bool:
    from tkinter import messagebox
    return messagebox.askyesno(title, message)


def create_scrollable_frame(parent, **kwargs):
    return ctk.CTkScrollableFrame(parent, **kwargs)


def create_progress_dialog(parent, title: str = "Processing…"):
    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    dialog.geometry("400x150")
    dialog.transient(parent)
    dialog.grab_set()
    center_window(dialog)
    ctk.CTkLabel(dialog, text=title, font=("Segoe UI", 14, "bold")).pack(pady=(25, 10))
    progress = ctk.CTkProgressBar(dialog, mode="indeterminate", width=320)
    progress.pack(pady=10)
    progress.start()
    dialog.progress_bar = progress
    return dialog
