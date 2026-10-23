"""Tests for the integrated smart pipeline:
- Tier 1 only behaviour unchanged when --smart is not passed
- Smart Tier 2 classification and refinement of Documents / Other
- Smart renaming with modified date + TF-IDF keywords
- Undo of rename + move operations restoring original file names and locations
"""

from pathlib import Path
import pytest

from sloth_sorter.classifier import SmartClassifier
from sloth_sorter.mover import execute_plan
from sloth_sorter.planner import build_plan
from sloth_sorter.scanner import scan_directory
from sloth_sorter.undo_log import get_db_path, list_batches, revert_batch
from tests.test_classifier import MockStaticModel


def test_tier1_unchanged_when_smart_not_passed(tmp_path):
    """When --smart is False, behavior must match Day 1 exact rules."""
    target = tmp_path / "downloads"
    target.mkdir()

    # Generic doc that has invoice content inside, but filename is generic
    f = target / "generic_doc.pdf"
    f.write_text("Invoice for consulting services total payment due $500")

    files = scan_directory(target)
    plan = build_plan(files, target, smart=False, rename=False)

    assert len(plan) == 1
    move = plan[0]
    # Tier 1 places .pdf into "Documents", not "Invoices"
    assert move.category == "Documents"
    assert move.tier == "rule"
    assert move.score is None
    assert move.dest.name == "generic_doc.pdf"


def test_tier2_refines_documents_when_smart_passed(tmp_path):
    """When --smart is True, Tier 2 refines Documents into Invoices using content."""
    target = tmp_path / "downloads"
    target.mkdir()

    f = target / "generic_doc.txt"
    f.write_text("Invoice for consulting services total payment due $500")

    mock_clf = SmartClassifier(
        prototypes={
            "Invoices": ["invoice billing payment statement"],
            "Resumes": ["curriculum vitae work experience education"],
        },
        threshold=0.3,
        model_instance=MockStaticModel(),
    )

    files = scan_directory(target)
    plan = build_plan(files, target, smart=True, rename=False, classifier=mock_clf)

    assert len(plan) == 1
    move = plan[0]
    assert move.category == "Invoices"
    assert move.tier == "embedding"
    assert move.score is not None
    assert move.score > 0.5
    assert move.dest == (target / "Invoices" / "generic_doc.txt").resolve()


def test_rename_and_move_with_undo(tmp_path):
    """Test full pipeline: smart renaming + move + undo restoring original name."""
    target = tmp_path / "downloads"
    target.mkdir()

    f = target / "statement_file.txt"
    content = "Electric utility invoice statement total due $85.00 billing payment"
    f.write_text(content)

    mock_clf = SmartClassifier(
        prototypes={
            "Invoices": ["invoice billing payment statement electric utility"],
        },
        threshold=0.3,
        model_instance=MockStaticModel(),
    )

    files = scan_directory(target)
    plan = build_plan(files, target, smart=True, rename=True, classifier=mock_clf)

    assert len(plan) == 1
    move = plan[0]
    assert move.category == "Invoices"
    # Destination name should have date prefix and tf-idf keywords
    assert move.dest.name.endswith(".txt")
    assert move.dest.name != "statement_file.txt"
    assert move.original_name == "statement_file.txt"
    assert move.new_name == move.dest.name

    # 1. Apply move
    report = execute_plan(plan, target, apply=True)
    assert report.applied
    assert len(report.successful) == 1
    assert not f.exists()
    assert move.dest.exists()
    assert move.dest.read_text() == content

    # 2. Undo move
    db_path = get_db_path(target)
    revert_report = revert_batch(db_path, report.batch_id)
    assert len(revert_report.restored) == 1
    assert len(revert_report.skipped) == 0

    # File must be restored back to root with its ORIGINAL filename
    assert f.exists()
    assert f.name == "statement_file.txt"
    assert f.read_text() == content
    assert not move.dest.exists()
