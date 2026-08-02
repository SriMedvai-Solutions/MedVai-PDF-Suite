"""Persistent settings for MedVai PDF Suite."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def _deep_merge(defaults: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    """Merge saved settings without losing newly added nested defaults."""
    result = deepcopy(defaults)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class SettingsManager:
    """Manage application settings with JSON persistence."""

    def __init__(self) -> None:
        self.settings_dir = Path.home() / ".medvai"
        self.settings_file = self.settings_dir / "medvai_pdf_suite.json"
        self.settings = self._load_settings()

    @staticmethod
    def _defaults() -> dict[str, Any]:
        return {
            "geometry": "1240x920",
            "last_file_path": "",
            "last_folder_path": "",
            "last_output_path": "",
            "edge_padding_x": 32,
            "edge_padding_y": 24,
            "auto_subfolder": True,
            "replace_if_exists": False,
            "numbering": {
                "pattern": "{n}",
                "start_number": 1,
                "adjust": 0,
                "placement": "Bottom-Center",
                "font_name": "Helvetica",
                "font_size": 10,
                "bold": False,
                "opacity": 1.0,
                "color": "#000000",
                "offset_x": 32,
                "offset_y": 24,
                "position_x_ratio": None,
                "position_y_ratio": None,
            },
            "bates_defaults": {
                "prefix": "",
                "symbol": "_",
                "start_number": 1,
                "padding": 6,
                "suffix": "",
                "placement": "Bottom-Right",
                "font_name": "Helvetica",
                "font_size": 11,
                "bold": False,
                "opacity": 1.0,
                "color": "#000000",
                "offset_x": 32,
                "offset_y": 24,
                "position_x_ratio": None,
                "position_y_ratio": None,
            },
        }

    def _load_settings(self) -> dict[str, Any]:
        defaults = self._defaults()
        if not self.settings_file.exists():
            return defaults
        try:
            with self.settings_file.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, dict):
                return defaults
            return _deep_merge(defaults, loaded)
        except (OSError, ValueError, TypeError):
            return defaults

    def save(self) -> None:
        try:
            self.settings_dir.mkdir(parents=True, exist_ok=True)
            with self.settings_file.open("w", encoding="utf-8") as handle:
                json.dump(self.settings, handle, indent=2)
        except OSError as exc:
            print(f"Could not save settings: {exc}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.settings[key] = value

    def get_nested(self, *keys: str, default: Any = None) -> Any:
        current: Any = self.settings
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    def set_nested(self, *keys: str, value: Any) -> None:
        if not keys:
            raise ValueError("At least one settings key is required.")
        current = self.settings
        for key in keys[:-1]:
            child = current.get(key)
            if not isinstance(child, dict):
                child = {}
                current[key] = child
            current = child
        current[keys[-1]] = value
