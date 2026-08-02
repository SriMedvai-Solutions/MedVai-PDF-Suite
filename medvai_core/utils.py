"""Utility functions for MedVai PDF Suite."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Iterable


def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def is_valid_hex_color(color: str) -> bool:
    return bool(color and re.fullmatch(r"#[0-9A-Fa-f]{6}", color))


def hex_to_rgb_normalized(hex_color: str) -> tuple[float, float, float]:
    if not is_valid_hex_color(hex_color):
        raise ValueError("Colour must use the format #RRGGBB.")
    value = hex_color.lstrip("#")
    return tuple(int(value[index:index + 2], 16) / 255.0 for index in (0, 2, 4))


def get_pdf_page_count(filepath: str) -> int:
    try:
        import fitz
        with fitz.open(filepath) as doc:
            if doc.needs_pass:
                return 0
            return len(doc)
    except Exception:
        return 0


def is_pdf_encrypted(filepath: str) -> bool:
    try:
        import fitz
        with fitz.open(filepath) as doc:
            return bool(doc.needs_pass)
    except Exception:
        return False


def validate_readable_pdf(filepath: str) -> int:
    """Return page count or raise a clear user-facing validation message."""
    import fitz

    if not filepath:
        raise ValueError("Select a PDF file.")
    if not os.path.isfile(filepath):
        raise ValueError(f"The PDF does not exist: {filepath}")
    if Path(filepath).suffix.lower() != ".pdf":
        raise ValueError(f"This is not a PDF file: {filepath}")

    try:
        with fitz.open(filepath) as doc:
            if doc.needs_pass:
                raise ValueError(
                    f"This PDF is password-protected: {Path(filepath).name}. "
                    "Please unlock it and try again."
                )
            if len(doc) < 1:
                raise ValueError(f"This PDF has no pages: {Path(filepath).name}")
            for page_index in range(len(doc)):
                try:
                    doc.load_page(page_index)
                except Exception as exc:
                    raise ValueError(
                        f"{Path(filepath).name} needs review because page {page_index + 1} "
                        f"could not be opened: {exc}"
                    ) from exc
            return len(doc)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            f"This PDF could not be opened and needs review: {Path(filepath).name}. {exc}"
        ) from exc


def natural_sort_key(value: str) -> list[object]:
    return [int(text) if text.isdigit() else text.casefold() for text in re.split(r"(\d+)", value)]


def ensure_unique_filename(filepath: str) -> str:
    if not os.path.exists(filepath):
        return filepath
    path = Path(filepath)
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return str(candidate)
        counter += 1


def reserve_run_suffix(output_folder: str, filenames: Iterable[str]) -> tuple[str, list[str]]:
    """Choose one shared suffix for every output in a run."""
    names = list(filenames)
    counter = 0
    while True:
        suffix = "" if counter == 0 else f"_{counter}"
        candidates = []
        for name in names:
            path = Path(name)
            candidates.append(str(Path(output_folder) / f"{path.stem}{suffix}{path.suffix}"))
        if not any(os.path.exists(candidate) for candidate in candidates):
            return suffix, candidates
        counter += 1


def create_output_folder(base_folder: str, auto_subfolder: bool, input_name: str = "") -> str:
    if not base_folder:
        raise ValueError("Select an output folder.")
    if auto_subfolder and input_name:
        output_folder = os.path.join(base_folder, f"MedVai_Output_{safe_filename_component(input_name)}")
    else:
        output_folder = base_folder
    try:
        os.makedirs(output_folder, exist_ok=True)
        probe = Path(output_folder) / ".medvai_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as exc:
        raise ValueError(f"The output folder is not writable: {output_folder}. {exc}") from exc
    return output_folder


def safe_filename_component(value: str, fallback: str = "Output") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip().rstrip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or fallback


def common_input_name(paths: Iterable[str]) -> str:
    path_list = [Path(path).resolve() for path in paths]
    if not path_list:
        return "Selected_PDFs"
    parents = {str(path.parent).casefold() for path in path_list}
    if len(parents) == 1:
        return safe_filename_component(path_list[0].parent.name, "Selected_PDFs")
    return "Selected_PDFs"


def parse_page_ranges(ranges_str: str, page_count: int | None = None) -> list[tuple[int, int]]:
    """Parse and fully validate ranges before any output is created."""
    if not ranges_str or not ranges_str.strip():
        raise ValueError("Enter at least one page or page range.")

    ranges: list[tuple[int, int]] = []
    for raw_part in ranges_str.split(","):
        part = raw_part.strip()
        if not part:
            raise ValueError("A page range is blank. Remove the extra comma.")
        if not re.fullmatch(r"\d+(?:\s*-\s*\d+)?", part):
            raise ValueError(f"Invalid page range: {part}. Use a format such as 1-12, 15, 20-25.")

        if "-" in part:
            start_text, end_text = re.split(r"\s*-\s*", part, maxsplit=1)
            start, end = int(start_text), int(end_text)
        else:
            start = end = int(part)

        if start < 1 or end < 1:
            raise ValueError("Page numbers must start from 1.")
        if end < start:
            raise ValueError(
                f"The ending page cannot be smaller than the starting page: {start}-{end}."
            )
        if page_count is not None and end > page_count:
            raise ValueError(
                f"This PDF contains only {page_count} pages. Page {end} does not exist."
            )
        ranges.append((start, end))

    return ranges


def get_placement_coords(
    placement: str,
    page_width: float,
    page_height: float,
    margin_x: float = 32.0,
    margin_y: float = 24.0,
) -> tuple[float, float]:
    placement_map = {
        "Top-Left": (margin_x, margin_y),
        "Top-Center": (page_width / 2, margin_y),
        "Top-Right": (page_width - margin_x, margin_y),
        "Middle-Left": (margin_x, page_height / 2),
        "Middle-Center": (page_width / 2, page_height / 2),
        "Middle-Right": (page_width - margin_x, page_height / 2),
        "Bottom-Left": (margin_x, page_height - margin_y),
        "Bottom-Center": (page_width / 2, page_height - margin_y),
        "Bottom-Right": (page_width - margin_x, page_height - margin_y),
    }
    return placement_map.get(placement, (page_width / 2, page_height / 2))
