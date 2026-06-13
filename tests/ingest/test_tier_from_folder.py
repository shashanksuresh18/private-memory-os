from __future__ import annotations

from pathlib import Path

from scripts.ingest_new import tier_for_raw_source


def _raw_tree(tmp_path: Path) -> Path:
    """Build a raw/ tree with s1/s2/s3 tier subfolders under tmp_path."""
    raw = tmp_path / "raw"
    for sub in ("s1", "s2", "s3"):
        (raw / sub).mkdir(parents=True)
    return raw


def test_s1_folder_gives_s1_tier(tmp_path):
    raw = _raw_tree(tmp_path)
    src = raw / "s1" / "public_filing.txt"
    src.write_text("Public 10-K filing.", encoding="utf-8")

    assert tier_for_raw_source(src, raw_root=raw) == "S1"


def test_s2_folder_gives_s2_tier(tmp_path):
    raw = _raw_tree(tmp_path)
    src = raw / "s2" / "meeting_notes.txt"
    src.write_text("Internal meeting notes.", encoding="utf-8")

    assert tier_for_raw_source(src, raw_root=raw) == "S2"


def test_s3_folder_gives_s3_tier(tmp_path):
    raw = _raw_tree(tmp_path)
    src = raw / "s3" / "board_memo.txt"
    src.write_text("Confidential board memo.", encoding="utf-8")

    assert tier_for_raw_source(src, raw_root=raw) == "S3"


def test_root_raw_defaults_to_s3(tmp_path):
    # A file dropped in raw/ root (no tier folder) must fail closed to S3.
    raw = _raw_tree(tmp_path)
    src = raw / "loose_drop.txt"
    src.write_text("Dropped without a tier folder.", encoding="utf-8")

    assert tier_for_raw_source(src, raw_root=raw) == "S3"
