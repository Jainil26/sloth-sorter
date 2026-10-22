"""Tests for dry-run, apply execution, and undo / revert behavior."""

import hashlib
from pathlib import Path
import pytest

from sloth_sorter.cli import main
from sloth_sorter.mover import execute_plan
from sloth_sorter.planner import build_plan
from sloth_sorter.scanner import scan_directory
from sloth_sorter.undo_log import (
    compute_sha256,
    get_db_path,
    list_batches,
    revert_batch,
)


def test_dry_run_moves_nothing(tmp_path):
    """Dry-run must not move files or create category folders."""
    target = tmp_path / "downloads"
    target.mkdir()

    f1 = target / "test_doc.pdf"
    f1.write_text("important document")
    f2 = target / "test_img.png"
    f2.write_bytes(b"\x89PNG\r\n\x1a\n")

    files = scan_directory(target)
    plan = build_plan(files, target)
    assert len(plan) == 2

    # Execute with apply=False (dry-run)
    report = execute_plan(plan, target, apply=False)

    assert not report.applied
    # Files must still exist in original locations
    assert f1.exists()
    assert f2.exists()
    # Category folders must NOT have been created
    assert not (target / "Documents").exists()
    assert not (target / "Images").exists()
    # Database must NOT have been created
    assert not get_db_path(target).exists()


def test_apply_moves_and_undo_restores_everything(tmp_path):
    """Applying moves must safely categorize files, and undo must restore them identically."""
    target = tmp_path / "downloads"
    target.mkdir()

    file_specs = [
        ("contract.pdf", "Original contract text content 12345"),
        ("vacation.jpg", "Image binary dummy data 67890"),
        ("setup.exe", "Executable dummy binary abcdef"),
    ]

    for name, content in file_specs:
        (target / name).write_text(content)

    # Record initial states
    initial_hashes = {name: hashlib.sha256(content.encode()).hexdigest() for name, content in file_specs}

    # 1. Scan and plan
    files = scan_directory(target)
    assert len(files) == 3

    plan = build_plan(files, target)
    assert len(plan) == 3

    # 2. Apply moves
    report = execute_plan(plan, target, apply=True)
    assert report.applied
    assert len(report.successful) == 3
    assert len(report.failed) == 0
    assert report.batch_id is not None

    # Files should no longer be at root
    for name, _ in file_specs:
        assert not (target / name).exists()

    # Files must be in category folders
    assert (target / "Documents" / "contract.pdf").exists()
    assert (target / "Images" / "vacation.jpg").exists()
    assert (target / "Installers" / "setup.exe").exists()

    # Database must exist and record 1 batch
    db_path = get_db_path(target)
    assert db_path.exists()
    batches = list_batches(db_path)
    assert len(batches) == 1
    assert batches[0].file_count == 3
    assert batches[0].status == "applied"

    # 3. Undo / revert
    revert_report = revert_batch(db_path, report.batch_id)
    assert len(revert_report.restored) == 3
    assert len(revert_report.skipped) == 0

    # Files must be back in original locations with identical content
    for name, content in file_specs:
        restored_file = target / name
        assert restored_file.exists(), f"File {name} was not restored"
        assert restored_file.read_text() == content
        assert compute_sha256(restored_file) == initial_hashes[name]

    # Batch status should be marked reverted
    batches_after = list_batches(db_path)
    assert batches_after[0].status == "reverted"
    assert batches_after[0].reverted_count == 3


def test_undo_skips_when_dest_file_is_modified(tmp_path):
    """If a file was modified at its destination, undo skips it to avoid data corruption."""
    target = tmp_path / "downloads"
    target.mkdir()

    f = target / "notes.txt"
    f.write_text("Initial notes version 1")

    files = scan_directory(target)
    plan = build_plan(files, target)
    report = execute_plan(plan, target, apply=True)

    dest_file = target / "Documents" / "notes.txt"
    assert dest_file.exists()

    # User modifies destination file
    dest_file.write_text("Modified notes version 2 - user added content!")

    # Attempt undo
    db_path = get_db_path(target)
    revert_report = revert_batch(db_path, report.batch_id)

    # Should skip due to hash mismatch
    assert len(revert_report.restored) == 0
    assert len(revert_report.skipped) == 1
    assert revert_report.skipped[0].status == "hash_mismatch"

    # Destination file is preserved
    assert dest_file.exists()
    assert dest_file.read_text() == "Modified notes version 2 - user added content!"
    # Original location is not overwritten with stale data
    assert not (target / "notes.txt").exists()


def test_undo_skips_when_src_already_exists(tmp_path):
    """If source location has already been recreated by the user, undo must never overwrite it."""
    target = tmp_path / "downloads"
    target.mkdir()

    orig_file = target / "draft.txt"
    orig_file.write_text("Version 1 content")

    files = scan_directory(target)
    plan = build_plan(files, target)
    report = execute_plan(plan, target, apply=True)

    # Now simulate user creating a new draft.txt at the original root location
    orig_file.write_text("Completely new draft written after tidy!")

    db_path = get_db_path(target)
    revert_report = revert_batch(db_path, report.batch_id)

    # Must be skipped due to conflict
    assert len(revert_report.restored) == 0
    assert len(revert_report.skipped) == 1
    assert revert_report.skipped[0].status == "src_conflict"

    # User's new file is preserved untouched
    assert orig_file.read_text() == "Completely new draft written after tidy!"
    # Categorized file is also preserved untouched
    assert (target / "Documents" / "draft.txt").exists()


def test_cli_integration(tmp_path, capsys):
    """Test CLI commands: tidy (dry-run and apply), history, and undo."""
    target = tmp_path / "cli_test"
    target.mkdir()

    (target / "doc.pdf").write_text("CLI test pdf")
    (target / "music.mp3").write_text("CLI test mp3")

    # 1. Dry run CLI
    exit_code = main(["tidy", str(target)])
    assert exit_code == 0
    assert (target / "doc.pdf").exists()
    assert not (target / "Documents").exists()

    # 2. Apply CLI
    exit_code = main(["tidy", str(target), "--apply"])
    assert exit_code == 0
    assert not (target / "doc.pdf").exists()
    assert (target / "Documents" / "doc.pdf").exists()

    # 3. History CLI
    exit_code = main(["history", str(target)])
    assert exit_code == 0

    # 4. Undo CLI
    exit_code = main(["undo", str(target)])
    assert exit_code == 0
    assert (target / "doc.pdf").exists()
    assert (target / "music.mp3").exists()
