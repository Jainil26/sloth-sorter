"""Safe move execution engine for sloth-sorter.

Executes planned moves with collision protection, error recovery,
and SQLite transaction logging for complete undoability.
Never deletes user files.
"""

from dataclasses import dataclass, field
import logging
from pathlib import Path
import shutil
from typing import List, Optional

from sloth_sorter.planner import PlannedMove
from sloth_sorter.undo_log import (
    compute_sha256,
    create_batch,
    get_db_path,
    record_move,
    update_batch_status,
)

logger = logging.getLogger(__name__)


@dataclass
class MoveResult:
    """Outcome of attempting a single planned move."""

    move: PlannedMove
    success: bool
    error: Optional[str] = None
    sha256: Optional[str] = None


@dataclass
class ExecutionReport:
    """Summary of batch execution."""

    target_dir: Path
    applied: bool
    batch_id: Optional[int] = None
    successful: List[MoveResult] = field(default_factory=list)
    failed: List[MoveResult] = field(default_factory=list)

    @property
    def total_planned(self) -> int:
        return len(self.successful) + len(self.failed)


def execute_plan(
    moves: List[PlannedMove],
    target_dir: Path,
    apply: bool = False,
    db_path: Optional[Path] = None,
) -> ExecutionReport:
    """Execute a list of planned moves safely.

    Args:
        moves: List of PlannedMove items to execute.
        target_dir: Root target directory.
        apply: If True, execute moves on disk and log to DB.
               If False (default), perform dry-run only.
        db_path: Optional override for database path (useful for testing).

    Returns:
        ExecutionReport detailing successful and failed moves.
    """
    target_dir = Path(target_dir).resolve()
    report = ExecutionReport(target_dir=target_dir, applied=apply)

    if not apply:
        # Dry-run: nothing moves, no DB changes
        for m in moves:
            report.successful.append(MoveResult(move=m, success=True))
        return report

    if not moves:
        return report

    actual_db_path = db_path or get_db_path(target_dir)
    batch_id = create_batch(actual_db_path, target_dir)
    report.batch_id = batch_id

    for m in moves:
        src = m.src.resolve()
        dest = m.dest.resolve()

        # Safety check 1: Source must exist
        if not src.exists():
            msg = f"Source file does not exist: {src}"
            logger.warning(msg)
            report.failed.append(MoveResult(move=m, success=False, error=msg))
            continue

        # Safety check 2: Destination must not already exist (never overwrite!)
        if dest.exists() and dest != src:
            msg = f"Destination already exists unexpectedly: {dest}"
            logger.warning(msg)
            report.failed.append(MoveResult(move=m, success=False, error=msg))
            continue

        try:
            # Ensure destination category folder exists
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Compute sha256 before moving
            file_hash = compute_sha256(src)

            # Safely move the file
            shutil.move(str(src), str(dest))

            # Record in undo database
            record_move(
                db_path=actual_db_path,
                batch_id=batch_id,
                src=src,
                dest=dest,
                size=m.size,
                sha256=file_hash,
                original_name=getattr(m, "original_name", src.name),
                new_name=getattr(m, "new_name", dest.name),
            )

            report.successful.append(
                MoveResult(move=m, success=True, sha256=file_hash)
            )
        except (PermissionError, OSError, shutil.Error, Exception) as e:
            err_msg = f"Failed to move {src.name} -> {dest}: {e}"
            logger.error(err_msg)
            report.failed.append(
                MoveResult(move=m, success=False, error=str(e))
            )

    # Update batch status if some or all moves failed
    if not report.successful:
        update_batch_status(actual_db_path, batch_id, "failed")
    elif report.failed:
        update_batch_status(actual_db_path, batch_id, "partially_applied")

    return report
