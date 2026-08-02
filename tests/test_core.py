from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from pypdf import PdfReader, PdfWriter

from medvai_core.models import BatesQueueItem, NumberingConfig, PDFFileInfo
from medvai_core.processing import (
    PDFProcessor,
    STATUS_COULD_NOT_COMPLETE,
    STATUS_REVIEW,
    STATUS_VERIFIED,
)
from medvai_core.utils import natural_sort_key


class DummySettings:
    def get(self, _key, default=None):
        return default


def make_pdf(path: Path, labels: list[str], *, rotation: int = 0, size=(612, 792)) -> None:
    doc = fitz.open()
    for label in labels:
        page = doc.new_page(width=size[0], height=size[1])
        page.insert_text((72, 72), label, fontsize=18)
        if rotation:
            page.set_rotation(rotation)
    doc.save(path)
    doc.close()


def file_info(path: Path, entry_id: str | None = None) -> PDFFileInfo:
    with fitz.open(path) as doc:
        count = len(doc)
    return PDFFileInfo(str(path), path.name, count, entry_id=entry_id or path.stem)


def bates_item(
    path: Path,
    prefix: str,
    *,
    start: int = 1,
    entry_id: str | None = None,
    placement: str = "Bottom-Right",
    x_ratio: float | None = None,
    y_ratio: float | None = None,
    offset_x: int = 32,
) -> BatesQueueItem:
    with fitz.open(path) as doc:
        count = len(doc)
    return BatesQueueItem(
        file_path=str(path),
        filename=path.name,
        prefix=prefix,
        symbol="_",
        start_number=start,
        placement=placement,
        color="#000000",
        pages_in_source=count,
        offset_x=offset_x,
        offset_y=24,
        padding=6,
        font_name="Helvetica",
        font_size=11,
        bold=True,
        opacity=1.0,
        position_x_ratio=x_ratio,
        position_y_ratio=y_ratio,
        entry_id=entry_id or prefix,
    )


def numbering_config() -> NumberingConfig:
    return NumberingConfig(
        enabled=True,
        pattern="Page {n} of {total}",
        start_number=1,
        placement="Bottom-Center",
        color="#0000FF",
        font_size=10,
        offset_x=32,
        offset_y=24,
    )


def test_natural_sort() -> None:
    names = ["10.pdf", "2.pdf", "1.pdf", "Record B.pdf", "Record A.pdf"]
    assert sorted(names, key=natural_sort_key) == [
        "1.pdf", "2.pdf", "10.pdf", "Record A.pdf", "Record B.pdf"
    ]


@pytest.mark.parametrize("value", ["0", "2-10", "2-1", "x", "-1"])
def test_invalid_split_ranges_create_nothing(tmp_path: Path, value: str) -> None:
    source = tmp_path / "Medical.pdf"
    make_pdf(source, ["ONE", "TWO"])
    output = tmp_path / "out"
    output.mkdir()
    with pytest.raises(ValueError):
        PDFProcessor(DummySettings()).split_by_ranges(str(source), str(output), value, False)
    assert list(output.iterdir()) == []


def test_valid_split_names_keep_input_name(tmp_path: Path) -> None:
    source = tmp_path / "Medical Records.pdf"
    make_pdf(source, ["ONE", "TWO", "THREE"])
    output = tmp_path / "out"
    output.mkdir()
    result = PDFProcessor(DummySettings()).split_by_ranges(
        str(source), str(output), "1-2,3", False
    )
    assert result["status"] == STATUS_VERIFIED
    assert sorted(path.name for path in output.iterdir()) == [
        "Medical Records_Split_1-2.pdf",
        "Medical Records_Split_3-3.pdf",
        "Medical Records_Split_Summary.docx",
        "Technical_Audit_Files",
    ]
    technical = output / "Technical_Audit_Files"
    assert sorted(path.name for path in technical.iterdir()) == [
        "Medical Records_Split_Process_Log.txt",
    ]


def test_same_pdf_twice_keeps_separate_bates_settings(tmp_path: Path) -> None:
    source = tmp_path / "Document.pdf"
    make_pdf(source, ["SOURCE"])
    output = tmp_path / "out"
    output.mkdir()
    queue = [
        bates_item(source, "FIRST", start=1, entry_id="one"),
        bates_item(source, "SECOND", start=500, entry_id="two"),
    ]
    result = PDFProcessor(DummySettings()).process_tab1(
        True, True, False, [], "", queue, None, str(output), False
    )
    assert result["status"] == STATUS_VERIFIED
    with fitz.open(result["output_files"][0]) as doc:
        assert len(doc) == 2
        assert "FIRST_000001" in doc[0].get_text()
        assert "SECOND_000500" in doc[1].get_text()


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_custom_visual_position_is_verified_on_rotated_pages(tmp_path: Path, rotation: int) -> None:
    source = tmp_path / f"rotated_{rotation}.pdf"
    make_pdf(source, [f"ROTATION {rotation}"], rotation=rotation)
    output = tmp_path / f"out_{rotation}"
    output.mkdir()
    item = bates_item(
        source,
        "ROTATE",
        entry_id=f"r{rotation}",
        placement="Custom",
        x_ratio=0.90,
        y_ratio=0.90,
    )
    result = PDFProcessor(DummySettings()).process_tab1(
        False, True, False, [], str(source), [item], None, str(output), False
    )
    assert result["status"] == STATUS_VERIFIED
    with fitz.open(result["output_files"][0]) as doc:
        assert item.format_number(1) in doc[0].get_text()


def test_output_names_keep_folder_name_and_selected_operations(tmp_path: Path) -> None:
    input_folder = tmp_path / "John Smith Records"
    input_folder.mkdir()
    first = input_folder / "1.pdf"
    second = input_folder / "2.pdf"
    make_pdf(first, ["ONE"])
    make_pdf(second, ["TWO"])
    files = [file_info(first), file_info(second)]
    output = tmp_path / "out"
    output.mkdir()
    result = PDFProcessor(DummySettings()).process_tab1(
        True, False, True, files, "", [], numbering_config(), str(output), False
    )
    assert result["status"] == STATUS_VERIFIED
    assert Path(result["output_files"][0]).name == "John Smith Records_Merged_Numbered.pdf"


def test_off_page_offset_is_needs_review_not_verified(tmp_path: Path) -> None:
    source = tmp_path / "Document.pdf"
    make_pdf(source, ["SOURCE"])
    output = tmp_path / "out"
    output.mkdir()
    item = bates_item(source, "OUT", offset_x=10000)
    result = PDFProcessor(DummySettings()).process_tab1(
        False, True, False, [], str(source), [item], None, str(output), False
    )
    assert result["status"] == STATUS_REVIEW
    assert result["output_files"]
    assert "_NEEDS_REVIEW.pdf" in Path(result["output_files"][0]).name
    assert result["stamp_stats"]["bates"]["verified"] == 0
    assert result["review_items"]


def test_password_protected_pdf_is_plain_review_result(tmp_path: Path) -> None:
    source = tmp_path / "plain.pdf"
    encrypted = tmp_path / "locked.pdf"
    make_pdf(source, ["SOURCE"])
    reader = PdfReader(str(source))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("secret")
    with encrypted.open("wb") as handle:
        writer.write(handle)
    output = tmp_path / "out"
    output.mkdir()
    result = PDFProcessor(DummySettings()).process_tab1(
        False, False, True, [], str(encrypted), [], numbering_config(), str(output), False
    )
    assert result["status"] == STATUS_COULD_NOT_COMPLETE
    assert result["issue_source"] == "Input PDF issue"
    assert result["output_files"] == []
    assert "password-protected" in result["review_items"][0].casefold()


class ForceHardStampProcessor(PDFProcessor):
    """Force the first two insertion attempts to test the disclosed fallback."""

    def __init__(self, settings):
        super().__init__(settings)
        self._forced_failures = 0

    def _insert_stamp(self, *args, **kwargs):
        if self._forced_failures < 2:
            self._forced_failures += 1
            # Return plausible geometry but intentionally insert no text.
            page = args[0]
            text = args[1]
            rect, size, adjustments = self._calculate_visual_rect(
                page,
                text,
                placement=kwargs["placement"],
                font_name=kwargs["font_name"],
                bold=kwargs["bold"],
                font_size=kwargs["font_size"],
                offset_x=kwargs["offset_x"],
                offset_y=kwargs["offset_y"],
                position_x_ratio=kwargs["position_x_ratio"],
                position_y_ratio=kwargs["position_y_ratio"],
            )
            physical = self._visual_rect_to_physical(page, rect)
            return {
                "visual_rect": list(rect),
                "physical_rect": list(physical),
                "used_font_size": size,
                "adjustments": adjustments,
            }
        return super()._insert_stamp(*args, **kwargs)


def test_hard_stamp_fallback_is_verified_and_disclosed(tmp_path: Path) -> None:
    source = tmp_path / "Difficult.pdf"
    make_pdf(source, ["SOURCE"])
    output = tmp_path / "out"
    output.mkdir()
    item = bates_item(source, "HARD")
    result = ForceHardStampProcessor(DummySettings()).process_tab1(
        False, True, False, [], str(source), [item], None, str(output), False
    )
    assert result["status"] == STATUS_REVIEW
    assert result["stamp_stats"]["bates"]["verified"] == 1
    assert result["stamp_stats"]["bates"]["hard_stamp"] == 1
    assert "_NEEDS_REVIEW.pdf" in Path(result["output_files"][0]).name
    with fitz.open(result["output_files"][0]) as doc:
        assert item.format_number(1) in doc[0].get_text()


def test_repeated_run_uses_one_coordinated_suffix(tmp_path: Path) -> None:
    source = tmp_path / "Medical.pdf"
    make_pdf(source, ["SOURCE"])
    output = tmp_path / "out"
    output.mkdir()
    item_one = bates_item(source, "RUN")
    first = PDFProcessor(DummySettings()).process_tab1(
        False, True, False, [], str(source), [item_one], None, str(output), False
    )
    item_two = bates_item(source, "RUN")
    second = PDFProcessor(DummySettings()).process_tab1(
        False, True, False, [], str(source), [item_two], None, str(output), False
    )
    assert Path(first["output_files"][0]).name == "Medical_Bates.pdf"
    assert Path(second["output_files"][0]).name == "Medical_Bates_1.pdf"
    second_names = {Path(path).name for path in second["audit_files"]}
    second_names.add(Path(second["log_file"]).name)
    assert second_names == {
        "Medical_Bates_1_Audit.docx",
        "Medical_Bates_1_Page_Map.csv",
        "Medical_Bates_1_Bates_Map.csv",
        "Medical_Bates_1_Stamp_Verification.csv",
        "Medical_Bates_1_Process_Log.txt",
    }
    audit_doc = next(Path(path) for path in second["audit_files"] if path.endswith("_Audit.docx"))
    assert audit_doc.parent == output
    technical_paths = [
        Path(path) for path in second["audit_files"] if not path.endswith("_Audit.docx")
    ] + [Path(second["log_file"])]
    assert all(path.parent == output / "Technical_Audit_Files" for path in technical_paths)


def test_repeated_split_run_uses_one_shared_suffix(tmp_path: Path) -> None:
    source = tmp_path / "Medical.pdf"
    make_pdf(source, ["ONE", "TWO"])
    output = tmp_path / "out"
    output.mkdir()
    first = PDFProcessor(DummySettings()).split_by_ranges(
        str(source), str(output), "1-2", False
    )
    second = PDFProcessor(DummySettings()).split_by_ranges(
        str(source), str(output), "1-2", False
    )
    assert Path(first["output_files"][0]).name == "Medical_Split_1-2.pdf"
    assert Path(second["output_files"][0]).name == "Medical_Split_1-2_1.pdf"
    assert Path(second["audit_files"][0]).name == "Medical_Split_Summary_1.docx"
    assert Path(second["audit_files"][0]).parent == output
    assert Path(second["log_file"]).name == "Medical_Split_Process_Log_1.txt"
    assert Path(second["log_file"]).parent == output / "Technical_Audit_Files"



def test_main_output_folder_keeps_only_pdf_and_audit_docx(tmp_path: Path) -> None:
    source = tmp_path / "Medical.pdf"
    make_pdf(source, ["SOURCE"])
    output = tmp_path / "out_clean"
    output.mkdir()
    item = bates_item(source, "CLEAN")

    result = PDFProcessor(DummySettings()).process_tab1(
        False, True, False, [], str(source), [item], None, str(output), False
    )

    root_names = sorted(path.name for path in output.iterdir())
    assert root_names == [
        "Medical_Bates.pdf",
        "Medical_Bates_Audit.docx",
        "Technical_Audit_Files",
    ]
    technical_names = sorted(
        path.name for path in (output / "Technical_Audit_Files").iterdir()
    )
    assert technical_names == [
        "Medical_Bates_Bates_Map.csv",
        "Medical_Bates_Page_Map.csv",
        "Medical_Bates_Process_Log.txt",
        "Medical_Bates_Stamp_Verification.csv",
    ]
    assert Path(result["output_files"][0]).parent == output


def test_bates_prefix_is_optional_but_limited_to_six_letters(tmp_path: Path) -> None:
    source = tmp_path / "Document.pdf"
    make_pdf(source, ["SOURCE"])
    processor = PDFProcessor(DummySettings())
    valid = bates_item(source, "ABCDEF")
    processor._validate_bates_item(valid)
    blank = bates_item(source, "")
    processor._validate_bates_item(blank)
    with pytest.raises(ValueError, match="up to 6 letters"):
        processor._validate_bates_item(bates_item(source, "ABCDEFG"))
    with pytest.raises(ValueError, match="up to 6 letters"):
        processor._validate_bates_item(bates_item(source, "ABC123"))


def test_duplicate_pdf_may_use_the_same_bates_details(tmp_path: Path) -> None:
    source = tmp_path / "Same.pdf"
    make_pdf(source, ["SOURCE"])
    output = tmp_path / "out_same"
    output.mkdir()
    queue = [
        bates_item(source, "MED", start=1, entry_id="same-one"),
        bates_item(source, "MED", start=1, entry_id="same-two"),
    ]
    result = PDFProcessor(DummySettings()).process_tab1(
        True, True, False, [], "", queue, None, str(output), False
    )
    assert result["status"] == STATUS_VERIFIED
    with fitz.open(result["output_files"][0]) as doc:
        assert len(doc) == 2
        assert "MED_000001" in doc[0].get_text()
        assert "MED_000001" in doc[1].get_text()


def test_continuous_bates_across_three_pdfs(tmp_path: Path) -> None:
    first = tmp_path / "1.pdf"
    second = tmp_path / "2.pdf"
    third = tmp_path / "3.pdf"
    make_pdf(first, ["A1", "A2"])
    make_pdf(second, ["B1"])
    make_pdf(third, ["C1", "C2"])
    output = tmp_path / "out_continuous"
    output.mkdir()

    queue = [
        bates_item(first, "MED", start=1, entry_id="one"),
        bates_item(second, "MED", start=3, entry_id="two"),
        bates_item(third, "MED", start=4, entry_id="three"),
    ]
    result = PDFProcessor(DummySettings()).process_tab1(
        True, True, False, [], "", queue, None, str(output), False
    )
    assert result["status"] == STATUS_VERIFIED
    with fitz.open(result["output_files"][0]) as doc:
        assert len(doc) == 5
        expected = [
            "MED_000001",
            "MED_000002",
            "MED_000003",
            "MED_000004",
            "MED_000005",
        ]
        for page, text in zip(doc, expected):
            assert text in page.get_text()


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        ("{n}", "1"),
        ("Page {n}", "Page 1"),
        ("Page-{n}", "Page-1"),
        ("Page #{n}", "Page #1"),
        ("Pg. {n}", "Pg. 1"),
        ("[{n}]", "[1]"),
        ("({n})", "(1)"),
        ("-{n}-", "-1-"),
        ("PAGE {n}", "PAGE 1"),
        ("P-{n}", "P-1"),
    ],
)
def test_numbering_patterns_are_applied_continuously(
    tmp_path: Path,
    pattern: str,
    expected: str,
) -> None:
    source = tmp_path / f"pattern_{abs(hash(pattern))}.pdf"
    make_pdf(source, ["ONE", "TWO"])
    output = tmp_path / f"out_{abs(hash(pattern))}"
    output.mkdir()
    config = NumberingConfig(
        enabled=True,
        pattern=pattern,
        start_number=1,
        placement="Bottom-Center",
        color="#000000",
        font_size=10,
        offset_x=32,
        offset_y=24,
    )
    result = PDFProcessor(DummySettings()).process_tab1(
        False, False, True, [], str(source), [], config, str(output), False
    )
    assert result["status"] == STATUS_VERIFIED
    with fitz.open(result["output_files"][0]) as doc:
        assert expected in doc[0].get_text()


def test_all_seven_operation_combinations(tmp_path: Path) -> None:
    first = tmp_path / "1.pdf"
    second = tmp_path / "2.pdf"
    make_pdf(first, ["ONE", "TWO"])
    make_pdf(second, ["THREE"])
    files = [file_info(first, "f1"), file_info(second, "f2")]

    combinations = [
        (True, False, False, files, "", [], None, "merge"),
        (False, True, False, [], str(first), [bates_item(first, "B", entry_id="b1")], None, "bates"),
        (False, False, True, [], str(first), [], numbering_config(), "numbering"),
        (
            True,
            True,
            False,
            [],
            "",
            [
                bates_item(first, "M", start=1, entry_id="m1"),
                bates_item(second, "M", start=3, entry_id="m2"),
            ],
            None,
            "merge_bates",
        ),
        (True, False, True, files, "", [], numbering_config(), "merge_numbering"),
        (
            False,
            True,
            True,
            [],
            str(first),
            [bates_item(first, "BN", entry_id="bn1")],
            numbering_config(),
            "bates_numbering",
        ),
        (
            True,
            True,
            True,
            [],
            "",
            [
                bates_item(first, "ALL", start=1, entry_id="a1"),
                bates_item(second, "ALL", start=3, entry_id="a2"),
            ],
            numbering_config(),
            "all",
        ),
    ]

    for merge, bates, numbering, input_files, single, queue, number_config, name in combinations:
        output = tmp_path / f"out_{name}"
        output.mkdir()
        result = PDFProcessor(DummySettings()).process_tab1(
            merge,
            bates,
            numbering,
            input_files,
            single,
            queue,
            number_config,
            str(output),
            False,
        )
        assert result["status"] == STATUS_VERIFIED, (name, result)
        assert result["output_files"], name
        with fitz.open(result["output_files"][0]) as doc:
            assert len(doc) == (3 if merge else 2)


def test_merge_keeps_unselected_pdfs_when_only_some_receive_bates(tmp_path: Path) -> None:
    first = tmp_path / "1.pdf"
    second = tmp_path / "2.pdf"
    third = tmp_path / "3.pdf"
    make_pdf(first, ["FIRST SOURCE"])
    make_pdf(second, ["SECOND SOURCE"])
    make_pdf(third, ["THIRD SOURCE"])
    files = [
        file_info(first, "source-1"),
        file_info(second, "source-2"),
        file_info(third, "source-3"),
    ]
    first_bates = bates_item(first, "ONE", start=1, entry_id="bates-1")
    first_bates.source_entry_id = "source-1"
    third_bates = bates_item(third, "THREE", start=100, entry_id="bates-3")
    third_bates.source_entry_id = "source-3"
    output = tmp_path / "out_selective"
    output.mkdir()

    result = PDFProcessor(DummySettings()).process_tab1(
        True,
        True,
        False,
        files,
        "",
        [first_bates, third_bates],
        None,
        str(output),
        False,
    )

    assert result["status"] == STATUS_VERIFIED
    with fitz.open(result["output_files"][0]) as doc:
        assert len(doc) == 3
        assert "FIRST SOURCE" in doc[0].get_text()
        assert "ONE_000001" in doc[0].get_text()
        assert "SECOND SOURCE" in doc[1].get_text()
        assert "ONE_" not in doc[1].get_text()
        assert "THREE_" not in doc[1].get_text()
        assert "THIRD SOURCE" in doc[2].get_text()
        assert "THREE_000100" in doc[2].get_text()

    unselected = result.get("warnings", [])
    assert not unselected
    audit_doc = next(path for path in result["audit_files"] if path.endswith("_Audit.docx"))
    assert Path(audit_doc).exists()


def test_merge_continuous_bates_uses_main_pdf_order(tmp_path: Path) -> None:
    first = tmp_path / "1.pdf"
    second = tmp_path / "2.pdf"
    third = tmp_path / "10.pdf"
    make_pdf(first, ["A1", "A2"])
    make_pdf(second, ["B1"])
    make_pdf(third, ["C1", "C2"])
    files = [
        file_info(first, "source-a"),
        file_info(second, "source-b"),
        file_info(third, "source-c"),
    ]
    queue = []
    next_number = 10
    for info, source in zip(files, (first, second, third)):
        item = bates_item(source, "MED", start=next_number, entry_id=f"bates-{info.entry_id}")
        item.source_entry_id = info.entry_id
        queue.append(item)
        next_number += info.pages
    output = tmp_path / "out_main_order"
    output.mkdir()

    result = PDFProcessor(DummySettings()).process_tab1(
        True, True, False, files, "", queue, None, str(output), False
    )

    assert result["status"] == STATUS_VERIFIED
    with fitz.open(result["output_files"][0]) as doc:
        expected = [
            "MED_000010",
            "MED_000011",
            "MED_000012",
            "MED_000013",
            "MED_000014",
        ]
        assert len(doc) == len(expected)
        for page, stamp in zip(doc, expected):
            assert stamp in page.get_text()
