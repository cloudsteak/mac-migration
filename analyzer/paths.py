"""Bilingual output path helpers."""

from __future__ import annotations

from pathlib import Path

SUPPORTED_LANGS = ("en", "hu")


def hu_path(path: Path) -> Path:
    """Return Hungarian variant: report.md -> report_HU.md"""
    return path.with_name(f"{path.stem}_HU{path.suffix}")


def report_paths(base: Path) -> dict[str, Path]:
    return {"en": base, "hu": hu_path(base)}
