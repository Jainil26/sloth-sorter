"""Tests for Tier 1 rule-based classification."""

from pathlib import Path
from sloth_sorter.rules import classify
from sloth_sorter.scanner import FileInfo


def make_file_info(name: str, size: int = 100) -> FileInfo:
    """Helper to construct a FileInfo object."""
    p = Path("/fake/path") / name
    return FileInfo(
        path=p,
        name=name,
        ext=p.suffix.lower(),
        size=size,
        mtime=1700000000.0,
    )


def test_extension_mappings():
    """Verify that common extensions map to correct categories with rule confidence."""
    test_cases = [
        ("photo.jpg", "Images"),
        ("graphic.PNG", "Images"),
        ("vector.svg", "Images"),
        ("paper.pdf", "Documents"),
        ("notes.docx", "Documents"),
        ("data.csv", "Documents"),
        ("film.mp4", "Videos"),
        ("movie.mkv", "Videos"),
        ("track.mp3", "Audio"),
        ("song.flac", "Audio"),
        ("archive.zip", "Archives"),
        ("tarball.tar.gz", "Archives"),
        ("setup.exe", "Installers"),
        ("package.dmg", "Installers"),
        ("script.py", "Code"),
        ("app.ts", "Code"),
    ]
    for filename, expected_category in test_cases:
        res = classify(make_file_info(filename))
        assert res.category == expected_category, f"Failed for {filename}"
        assert res.confidence == "rule"


def test_pattern_matching_overrides():
    """Verify filename patterns take effect."""
    patterns_to_test = [
        ("IMG_20231015.raw", "Images"),
        ("Screenshot_2023-11-01.png", "Images"),
        ("invoice_1042.pdf", "Documents"),
        ("John_Doe_Resume.docx", "Documents"),
        ("math_assignment_2.txt", "Documents"),
        ("installer_win64.bin", "Installers"),
    ]
    for filename, expected_cat in patterns_to_test:
        res = classify(make_file_info(filename))
        assert res.category == expected_cat, f"Failed for {filename}"
        assert res.confidence == "rule"
        assert "pattern" in res.reason


def test_fallback_unmatched():
    """Verify unknown files fall back to 'Other' with 'low' confidence."""
    unknown_cases = [
        "weird_binary.xyz",
        "some_data.unknown",
        "README_NO_EXT",
    ]
    for filename in unknown_cases:
        res = classify(make_file_info(filename))
        assert res.category == "Other"
        assert res.confidence == "low"
        assert "fallback" in res.reason
