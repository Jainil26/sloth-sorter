"""Tests for move planner and collision resolution."""

from pathlib import Path
from sloth_sorter.planner import build_plan, resolve_collision
from sloth_sorter.scanner import FileInfo


def create_file_info(path: Path) -> FileInfo:
    return FileInfo(
        path=path.resolve(),
        name=path.name,
        ext=path.suffix.lower(),
        size=path.stat().st_size if path.exists() else 100,
        mtime=path.stat().st_mtime if path.exists() else 1700000000.0,
    )


def test_plan_moves_basic(tmp_path):
    """Test standard move planning into category folders."""
    target_dir = tmp_path / "downloads"
    target_dir.mkdir()

    file1 = target_dir / "my_document.pdf"
    file1.write_text("sample pdf content")
    file2 = target_dir / "picture.jpg"
    file2.write_text("sample image content")

    files = [create_file_info(file1), create_file_info(file2)]
    plan = build_plan(files, target_dir)

    assert len(plan) == 2

    move_map = {m.src.name: m for m in plan}
    assert move_map["my_document.pdf"].dest == (target_dir / "Documents" / "my_document.pdf").resolve()
    assert move_map["my_document.pdf"].category == "Documents"
    assert not move_map["my_document.pdf"].collision_resolved

    assert move_map["picture.jpg"].dest == (target_dir / "Images" / "picture.jpg").resolve()
    assert move_map["picture.jpg"].category == "Images"
    assert not move_map["picture.jpg"].collision_resolved


def test_collision_renaming_existing_on_disk(tmp_path):
    """When a file already exists at the destination, rename with (1), (2), etc."""
    target_dir = tmp_path / "downloads"
    docs_dir = target_dir / "Documents"
    docs_dir.mkdir(parents=True)

    # Existing file already in Documents
    existing1 = docs_dir / "report.pdf"
    existing1.write_text("existing version 0")

    existing2 = docs_dir / "report (1).pdf"
    existing2.write_text("existing version 1")

    # New file at target root
    new_file = target_dir / "report.pdf"
    new_file.write_text("new incoming report")

    files = [create_file_info(new_file)]
    plan = build_plan(files, target_dir)

    assert len(plan) == 1
    move = plan[0]
    assert move.dest == (docs_dir / "report (2).pdf").resolve()
    assert move.collision_resolved is True


def test_internal_batch_collision(tmp_path):
    """When two files in the same batch share a name (e.g. from subdirectories), resolve collision."""
    target_dir = tmp_path / "downloads"
    sub1 = target_dir / "folder_a"
    sub2 = target_dir / "folder_b"
    sub1.mkdir(parents=True)
    sub2.mkdir(parents=True)

    f1 = sub1 / "notes.txt"
    f1.write_text("notes A")

    f2 = sub2 / "notes.txt"
    f2.write_text("notes B")

    files = [create_file_info(f1), create_file_info(f2)]
    plan = build_plan(files, target_dir)

    assert len(plan) == 2
    dests = [m.dest.name for m in plan]
    assert "notes.txt" in dests
    assert "notes (1).txt" in dests


def test_skip_file_already_in_destination(tmp_path):
    """If a file is already at its target category destination, skip planning a move for it."""
    target_dir = tmp_path / "downloads"
    docs_dir = target_dir / "Documents"
    docs_dir.mkdir(parents=True)

    already_sorted = docs_dir / "manual.pdf"
    already_sorted.write_text("manual content")

    files = [create_file_info(already_sorted)]
    plan = build_plan(files, target_dir)

    assert len(plan) == 0
