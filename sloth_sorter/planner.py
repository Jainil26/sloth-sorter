"""Move planner for sloth-sorter.

Determines destination paths for files based on classification,
resolving filename collisions by appending " (1)", " (2)", etc.
Ensures no file is ever overwritten.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sloth_sorter.config import get_default_config
from sloth_sorter.rules import ClassificationResult, classify
from sloth_sorter.scanner import FileInfo


@dataclass(frozen=True)
class PlannedMove:
    """Represents a planned move operation."""

    src: Path
    dest: Path
    category: str
    size: int
    mtime: float
    confidence: str
    reason: str
    collision_resolved: bool = False


def _normalize_path_key(path: Path) -> str:
    """Return a comparable string key for a path (case-folded on Windows)."""
    resolved = path.resolve()
    if os.name == "nt":
        return str(resolved).lower()
    return str(resolved)


def resolve_collision(
    dest_dir: Path,
    original_name: str,
    src_path: Path,
    claimed_destinations: Set[str],
) -> Path:
    """Find a non-colliding destination path.

    If dest already exists on disk (and isn't src) or is claimed by another move
    in the current plan, appends ' (1)', ' (2)', etc. before the extension.
    """
    initial_path = dest_dir / original_name
    initial_key = _normalize_path_key(initial_path)
    src_key = _normalize_path_key(src_path)

    # If the file does not exist on disk and is not yet claimed, it's safe
    if not initial_path.exists() and initial_key not in claimed_destinations:
        return initial_path

    # If it points to the exact same file on disk, return initial_path
    if initial_key == src_key and initial_key not in claimed_destinations:
        return initial_path

    # We have a collision on disk or in the plan
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix

    counter = 1
    while True:
        candidate_name = f"{stem} ({counter}){suffix}"
        candidate_path = dest_dir / candidate_name
        candidate_key = _normalize_path_key(candidate_path)

        if candidate_key == src_key:
            return candidate_path

        if not candidate_path.exists() and candidate_key not in claimed_destinations:
            return candidate_path

        counter += 1


def build_plan(
    files: List[FileInfo],
    target_dir: Path,
    config: Optional[Dict[str, Any]] = None,
) -> List[PlannedMove]:
    """Build a list of planned moves for the scanned files.

    Args:
        files: List of FileInfo objects to organize.
        target_dir: Target directory where category folders will live.
        config: Optional configuration dict.

    Returns:
        List of PlannedMove objects ready for execution.
    """
    cfg = config or get_default_config()
    target_dir = Path(target_dir).resolve()

    moves: List[PlannedMove] = []
    claimed_destinations: Set[str] = set()

    for file_info in files:
        classification: ClassificationResult = classify(file_info, config=cfg)
        category = classification.category
        dest_dir = target_dir / category

        src_path = file_info.path.resolve()
        dest_path = resolve_collision(
            dest_dir=dest_dir,
            original_name=file_info.name,
            src_path=src_path,
            claimed_destinations=claimed_destinations,
        ).resolve()

        # If src is already at dest, skip it
        if _normalize_path_key(src_path) == _normalize_path_key(dest_path):
            continue

        collision_resolved = dest_path.name != file_info.name
        claimed_destinations.add(_normalize_path_key(dest_path))

        moves.append(
            PlannedMove(
                src=src_path,
                dest=dest_path,
                category=category,
                size=file_info.size,
                mtime=file_info.mtime,
                confidence=classification.confidence,
                reason=classification.reason,
                collision_resolved=collision_resolved,
            )
        )

    return moves
