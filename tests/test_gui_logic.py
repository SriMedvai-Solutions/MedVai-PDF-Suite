from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from medvai_core.models import BatesQueueItem, PDFFileInfo


class _DummyWidget:
    pass


class _Var:
    def __init__(self, value: str):
        self.value = value

    def get(self) -> str:
        return self.value


class _Label:
    def __init__(self):
        self.values = {}

    def configure(self, **kwargs):
        self.values.update(kwargs)


class _Tree:
    def __init__(self):
        self.rows = []

    def get_children(self):
        return []

    def delete(self, *_args):
        self.rows = []

    def insert(self, *_args, **kwargs):
        self.rows.append(kwargs)


def _load_gui_module():
    fake_ctk = types.ModuleType("customtkinter")
    fake_ctk.CTk = _DummyWidget
    fake_ctk.CTkToplevel = _DummyWidget
    previous = sys.modules.get("customtkinter")
    sys.modules["customtkinter"] = fake_ctk
    try:
        path = Path(__file__).resolve().parents[1] / "pdf_suite_gui.py"
        spec = importlib.util.spec_from_file_location("medvai_gui_logic_test", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            sys.modules.pop("customtkinter", None)
        else:
            sys.modules["customtkinter"] = previous


def test_continuous_queue_recalculates_start_numbers_after_each_pdf() -> None:
    gui = _load_gui_module()
    app = gui.MedVaiPDFSuite.__new__(gui.MedVaiPDFSuite)
    app.bates_mode_var = _Var("continuous")
    app.continuous_bates_configured = True
    app.continuous_bates_values = {
        "prefix": "MED",
        "symbol": "-",
        "start_number": 10,
        "padding": 4,
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
    app.pdf_files = [
        PDFFileInfo("a.pdf", "a.pdf", 2, entry_id="src-a"),
        PDFFileInfo("b.pdf", "b.pdf", 3, entry_id="src-b"),
        PDFFileInfo("c.pdf", "c.pdf", 1, entry_id="src-c"),
    ]
    app.bates_queue = []
    app.queue_tree = _Tree()
    app.bates_validation_label = _Label()
    app.settings = object()

    app._recalculate_continuous_bates_queue()

    assert [item.start_number for item in app.bates_queue] == [10, 12, 15]
    assert [item.prefix for item in app.bates_queue] == ["MED", "MED", "MED"]
    assert app.bates_validation_label.values["text"] == (
        "All 3 PDFs will receive continuous Bates: MED-0010 through MED-0015."
    )
