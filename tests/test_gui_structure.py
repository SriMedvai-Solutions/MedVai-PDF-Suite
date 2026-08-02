from __future__ import annotations

import ast
from pathlib import Path


GUI_PATH = Path(__file__).resolve().parents[1] / "pdf_suite_gui.py"
SOURCE = GUI_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def class_method_names(class_name: str) -> set[str]:
    for node in TREE.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    raise AssertionError(f"Class not found: {class_name}")


def test_main_title_has_no_version_text() -> None:
    assert 'self.title("MedVai PDF Suite")' in SOURCE
    assert 'create_header(self, "MedVai PDF Suite", logo, height=128, vertical_padding=14)' in SOURCE
    assert 'create_header(self, "MedVai PDF Suite", logo)' in SOURCE
    assert 'except TypeError as exc:' in SOURCE
    assert 'self.title(f"MedVai PDF Suite v{__version__}")' not in SOURCE
    assert "MedVai PDF Suite  •  v" not in SOURCE


def test_main_page_is_clean_and_settings_live_in_preview() -> None:
    assert "Not configured. Open the preview" in SOURCE
    assert "Preview & Arrange PDFs" in SOURCE
    assert "Preview & Set Bates" in SOURCE
    assert "Preview & Set Numbering" in SOURCE
    assert "class PDFArrangeDialog" in SOURCE
    assert "Save Arrangement" in SOURCE
    assert "Natural Sort" in SOURCE
    for stale in (
        "Fill the settings, then click Add",
        "Save Changes",
        "self.bates_prefix =",
        "self.numbering_pattern =",
        "self.bates_simple_prefix =",
        'text="Output Folder:"',
        'text="Output base name (optional):"',
    ):
        assert stale not in SOURCE


def test_bates_panel_has_two_clear_modes_and_compact_selective_controls() -> None:
    for text in (
        "Continuous Bates across all PDFs",
        "Separate Bates settings for each PDF",
        "Add Selected →",
        "Available PDFs / Merge Order",
        "Bates Settings",
        "Saved Bates",
        "Duplicate PDF",
        "Move PDF Up",
        "Move PDF Down",
        "Clear Bates",
    ):
        assert text in SOURCE
    assert "Add All PDFs →" not in SOURCE
    assert "Bates Queue / Final Merge Order" not in SOURCE

def test_bates_and_numbering_preview_buttons_match_header_turquoise() -> None:
    assert 'text="Preview & Set Continuous Bates"' in SOURCE
    assert 'text="Preview & Set Numbering"' in SOURCE
    assert 'PREVIEW_BUTTON_COLOR = "#5CB7BC"' in SOURCE
    assert SOURCE.count('fg_color=PREVIEW_BUTTON_COLOR') >= 3
    assert SOURCE.count('width=260') >= 3
    assert SOURCE.count('height=38') >= 3
    assert 'command=self._open_merge_bates_preview' in SOURCE
    assert 'command=self._open_numbering_preview' in SOURCE

def test_duplicate_requires_permission_and_allows_same_or_different_details() -> None:
    assert "askyesno" in SOURCE
    assert "already has Bates settings. Add another occurrence to the merged PDF?" in SOURCE
    assert "You may enter the same or different Bates details." in SOURCE
    assert '"start_number": ""' in SOURCE
    assert '"prefix": ""' in SOURCE
    assert '"symbol": ""' in SOURCE

def test_continuous_bates_uses_every_pdf_in_main_merge_order() -> None:
    assert "def _recalculate_continuous_bates_queue" in SOURCE
    assert "for source in self.pdf_files" in SOURCE
    assert "next_number += source.pages" in SOURCE
    assert "All PDFs in the arranged merge list receive one continuous Bates sequence." in SOURCE
    assert "self.separate_bates_frame.grid_remove()" in SOURCE
    
def test_numbering_patterns_show_the_pattern_and_result() -> None:
    for option in (
        "{n}  →  1",
        "Page {n}  →  Page 1",
        "Page-{n}  →  Page-1",
        "Page #{n}  →  Page #1",
        "Pg. {n}  →  Pg. 1",
        "[{n}]  →  [1]",
        "({n})  →  (1)",
        "-{n}-  →  -1-",
        "PAGE {n}  →  PAGE 1",
        "P-{n}  →  P-1",
    ):
        assert option in SOURCE
    assert "For merged PDFs, numbering always continues through the complete merged PDF." in SOURCE


def test_preview_has_maximize_restore_colour_picker_and_exact_text_box() -> None:
    assert 'text="Maximize"' in SOURCE
    assert 'self.maximize_button.configure(text="Restore")' in SOURCE
    assert "Pick Colour" in SOURCE
    assert "Bates preview:" in SOURCE
    assert "Page-number preview:" in SOURCE
    assert "fg_color=colour" in SOURCE
    assert 'outline=outline' in SOURCE
    assert 'width=4' in SOURCE


def test_preview_guidance_and_prefix_rule_are_present() -> None:
    assert "Prefix: up to 6 letters" in SOURCE
    assert "Optional numbers or symbols" in SOURCE
    assert "Bates prefix may contain up to 6 letters only." in SOURCE



def test_arrangement_button_and_preview_buttons_use_matching_turquoise_left_flow() -> None:
    assert SOURCE.count('fg_color=PREVIEW_BUTTON_COLOR') >= 4
    assert 'self.arrange_pdfs_button.grid(row=0, column=0, sticky="w"' in SOURCE
    assert 'self.numbering_preview_button.grid(row=2, column=0, sticky="w"' in SOURCE
    assert 'self.merge_bates_preview_button.grid(row=4, column=0, sticky="w"' in SOURCE
    assert 'output_folder = self._automatic_output_base(merge)' in SOURCE
    assert 'auto_subfolder=True' in SOURCE
    assert 'output_base_name=""' in SOURCE

def test_all_gui_callbacks_exist() -> None:
    methods = class_method_names("MedVaiPDFSuite")
    expected = {
        "_refresh_mode_ui",
        "_add_to_bates_queue",
        "_add_all_to_bates_queue",
        "_remove_from_bates_queue",
        "_load_selected_bates",
        "_duplicate_bates_queue",
        "_move_bates",
        "_move_available_pdf",
        "_clear_bates_queue",
        "_open_merge_bates_preview",
        "_open_bates_preview",
        "_open_numbering_preview",
        "_recalculate_continuous_bates_queue",
        "_on_bates_mode_change",
        "_run_tab1",
        "_run_split",
    }
    assert expected <= methods


def test_no_duplicate_methods_or_multiple_main_blocks() -> None:
    for node in TREE.body:
        if isinstance(node, ast.ClassDef):
            names = [item.name for item in node.body if isinstance(item, ast.FunctionDef)]
            assert len(names) == len(set(names))
    main_guards = [
        node
        for node in TREE.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    ]
    assert len(main_guards) == 1
