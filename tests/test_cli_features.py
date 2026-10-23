"""Tests for CLI tidy features:
- Long filename truncation and column width preservation
- Compact preview fallback for narrow terminals (< 100 cols)
- Row pagination: default 25 limit, --limit N, and --all
- CSV plan export via --report
- Apply hint preserving exact command flags
- Needs Review section for borderline embedding scores
- --max-files cap support
"""

import csv
from pathlib import Path
import pytest
from rich.console import Console

from sloth_sorter.cli import main, truncate_filename_str
from sloth_sorter.planner import PlannedMove, build_plan
from sloth_sorter.scanner import scan_directory


def test_truncate_filename_str():
    # Short name unchanged
    assert truncate_filename_str("short.pdf", max_chars=40) == "short.pdf"

    # Long name truncated preserving extension
    long_name = "this_is_an_extremely_long_filename_that_exceeds_forty_characters.pdf"
    truncated = truncate_filename_str(long_name, max_chars=40)
    assert len(truncated) <= 40
    assert truncated.endswith(".pdf")
    assert "..." in truncated


def test_cli_preview_row_limit_and_all(tmp_path, capsys):
    target = tmp_path / "many_files"
    target.mkdir()

    # Create 35 dummy files
    for i in range(35):
        (target / f"file_{i:03d}.txt").write_text("sample content")

    # 1. Default limit is 25: output should mention "... and 10 more"
    main(["tidy", str(target)])
    captured = capsys.readouterr().out
    assert "... and 10 more" in captured

    # 2. Custom --limit 10: output should mention "... and 25 more"
    main(["tidy", str(target), "--limit", "10"])
    captured = capsys.readouterr().out
    assert "... and 25 more" in captured

    # 3. --all flag: shows all, no "... and X more"
    main(["tidy", str(target), "--all"])
    captured = capsys.readouterr().out
    assert "... and " not in captured


def test_cli_report_csv_export(tmp_path):
    target = tmp_path / "report_test"
    target.mkdir()

    for i in range(5):
        (target / f"doc_{i}.txt").write_text("report test content")

    csv_path = tmp_path / "plan_output.csv"
    exit_code = main(["tidy", str(target), "--report", str(csv_path)])
    assert exit_code == 0
    assert csv_path.exists()

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = list(csv.reader(f))

    # Header + 5 file rows
    assert len(reader) == 6
    header = reader[0]
    assert header[:5] == ["File", "New Name", "Category", "Tier", "Score"]


def test_apply_hint_echoes_exact_flags(tmp_path, capsys):
    target = tmp_path / "flags"
    target.mkdir()
    (target / "test.txt").write_text("content")

    main(["tidy", str(target), "--smart", "--rename"])
    captured = capsys.readouterr().out

    # The dry-run hint panel should contain the tidy command with both flags echoed
    assert "python -m sloth_sorter tidy" in captured
    assert "--smart" in captured
    assert "--rename" in captured
    assert "--apply" in captured


def test_needs_review_section(tmp_path, capsys):
    target = tmp_path / "review_test"
    target.mkdir()
    (target / "borderline_file.txt").write_text("ambiguous text content")

    from sloth_sorter.classifier import SmartClassificationResult, SmartClassifier

    class MockBorderlineClassifier(SmartClassifier):
        def classify_text(self, text):
            # Return borderline score 0.38 near default threshold 0.35
            return SmartClassificationResult(
                category="Invoices",
                score=0.38,
                confidence="embedding",
                reason="embedding:Invoices:0.38",
            )

    from unittest.mock import patch

    with patch("sloth_sorter.classifier.get_smart_classifier", return_value=MockBorderlineClassifier()):
        main(["tidy", str(target), "--smart"])
        captured = capsys.readouterr().out
        assert "Needs Review" in captured
        assert "borderline_file.txt" in captured


def test_scanner_max_files(tmp_path):
    target = tmp_path / "cap_test"
    target.mkdir()
    for i in range(15):
        (target / f"file_{i:02d}.txt").write_text("data")

    # Without max_files
    all_files = scan_directory(target)
    assert len(all_files) == 15

    # With max_files cap
    capped_files = scan_directory(target, max_files=8)
    assert len(capped_files) == 8


def test_compact_mode_under_100_cols(tmp_path, capsys):
    target = tmp_path / "compact_test"
    target.mkdir()
    (target / "small_doc.txt").write_text("compact mode data")

    from unittest.mock import PropertyMock, patch

    # Mock Console.width < 100
    with patch.object(Console, "width", new_callable=PropertyMock, return_value=80):
        main(["tidy", str(target)])
        captured = capsys.readouterr().out
        assert "• small_doc.txt -> small_doc.txt" in captured
