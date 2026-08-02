"""Data models for MedVai PDF Suite."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class PDFFileInfo:
    path: str
    filename: str
    pages: int
    status: str = "OK"
    entry_id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class BatesQueueItem:
    file_path: str
    filename: str
    prefix: str
    symbol: str
    start_number: int
    placement: str
    color: str
    pages_in_source: int
    offset_x: int = 32
    offset_y: int = 24
    suffix: str = ""
    padding: int = 6
    font_name: str = "Helvetica"
    font_size: int = 11
    bold: bool = False
    opacity: float = 1.0
    position_x_ratio: Optional[float] = None
    position_y_ratio: Optional[float] = None
    source_entry_id: str = ""
    entry_id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def margin_x(self) -> int:
        return self.offset_x

    @margin_x.setter
    def margin_x(self, value: int) -> None:
        self.offset_x = int(value)

    @property
    def margin_y(self) -> int:
        return self.offset_y

    @margin_y.setter
    def margin_y(self, value: int) -> None:
        self.offset_y = int(value)

    def format_number(self, number: int) -> str:
        return f"{self.prefix}{self.symbol}{str(number).zfill(self.padding)}{self.suffix}"


@dataclass
class NumberingConfig:
    enabled: bool
    pattern: str
    start_number: int
    placement: str
    color: str
    adjust: int = 0
    font_size: int = 10
    offset_x: int = 32
    offset_y: int = 24
    font_name: str = "Helvetica"
    bold: bool = False
    opacity: float = 1.0
    position_x_ratio: Optional[float] = None
    position_y_ratio: Optional[float] = None

    @property
    def margin_x(self) -> int:
        return self.offset_x

    @margin_x.setter
    def margin_x(self, value: int) -> None:
        self.offset_x = int(value)

    @property
    def margin_y(self) -> int:
        return self.offset_y

    @margin_y.setter
    def margin_y(self, value: int) -> None:
        self.offset_y = int(value)


@dataclass
class PageRangeMap:
    file_path: str
    filename: str
    start_page_in_merged: int
    end_page_in_merged: int
    pages_in_source: int
    entry_id: str = ""
    occurrence: int = 1


@dataclass
class RunSummary:
    input_files: List[str] = field(default_factory=list)
    merged_pages: int = 0
    bates_applied: int = 0
    split_outputs: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    output_path: Optional[str] = None
    timestamp: Optional[datetime] = None
    output_files: List[str] = field(default_factory=list)
    operation_type: Optional[str] = None
    success: bool = False
    status: str = "Completed — Needs Review"
    issue_source: str = "None identified"
    settings: Dict[str, Any] = field(default_factory=dict)
    page_mapping: Optional[List[PageRangeMap]] = None

    def __init__(
        self,
        input_files: Optional[List[str]] = None,
        merged_pages: int = 0,
        bates_applied: int = 0,
        split_outputs: int = 0,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        output_path: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        output_files: Optional[List[str]] = None,
        operation_type: Optional[str] = None,
        success: bool = False,
        status: str = "Completed — Needs Review",
        issue_source: str = "None identified",
        settings: Optional[Dict[str, Any]] = None,
        page_mapping: Optional[List[PageRangeMap]] = None,
        **_ignore: Any,
    ) -> None:
        self.input_files = list(input_files) if input_files else []
        self.merged_pages = merged_pages
        self.bates_applied = bates_applied
        self.split_outputs = split_outputs
        self.errors = list(errors) if errors else []
        self.warnings = list(warnings) if warnings else []
        self.output_path = output_path
        self.timestamp = timestamp
        self.output_files = list(output_files) if output_files else []
        self.operation_type = operation_type
        self.success = success
        self.status = status
        self.issue_source = issue_source
        self.settings = dict(settings) if settings else {}
        self.page_mapping = list(page_mapping) if page_mapping else None
