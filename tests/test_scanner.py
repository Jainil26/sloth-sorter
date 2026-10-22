"""Tests for directory scanning and filtering."""

from pathlib import Path
from sloth_sorter.scanner import scan_directory


def test_scanner_filters_hidden_and_temp(tmp_path):
    """Ensure scanner skips hidden files, .sloth_sorter.db, and partial downloads."""
    target = tmp_path / "downloads"
    target.mkdir()

    # Normal files
    (target / "report.pdf").write_text("pdf content")
    (target / "photo.jpg").write_text("image content")

    # Partial / temp downloads
    (target / "movie.mp4.crdownload").write_text("partial chrome download")
    (target / "archive.zip.part").write_text("partial firefox download")
    (target / "cache.tmp").write_text("temp file")

    # Hidden files and internal DB
    (target / ".hidden_file.txt").write_text("secret")
    (target / ".sloth_sorter.db").write_text("sqlite database dummy")

    files = scan_directory(target)
    names = {f.name for f in files}

    assert names == {"report.pdf", "photo.jpg"}


def test_scanner_skips_category_folders(tmp_path):
    """Ensure scanner skips category folders themselves so already-sorted files aren't re-scanned."""
    target = tmp_path / "downloads"
    target.mkdir()

    # Normal file at root
    (target / "new_doc.pdf").write_text("new pdf")

    # Category folders
    docs = target / "Documents"
    docs.mkdir()
    (docs / "already_sorted.pdf").write_text("sorted pdf")

    images = target / "Images"
    images.mkdir()
    (images / "already_sorted.png").write_text("sorted png")

    # Non-recursive
    files_non_rec = scan_directory(target, recursive=False)
    names_non_rec = {f.name for f in files_non_rec}
    assert names_non_rec == {"new_doc.pdf"}

    # Recursive
    files_rec = scan_directory(target, recursive=True)
    names_rec = {f.name for f in files_rec}
    assert names_rec == {"new_doc.pdf"}
