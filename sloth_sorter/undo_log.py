"""SQLite-based undo logging for sloth-sorter.

Tracks batches and individual file moves with SHA-256 hashes to guarantee safe,
verifiable undos without risking data loss or overwrites.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import sqlite3
from typing import List, Optional

DB_FILENAME = ".sloth_sorter.db"


@dataclass(frozen=True)
class BatchRecord:
    """Represents a logged batch."""

    id: int
    timestamp: str
    target_dir: str
    status: str
    reverted_at: Optional[str] = None


@dataclass(frozen=True)
class BatchSummary:
    """Summary of a batch including move counts."""

    id: int
    timestamp: str
    target_dir: str
    status: str
    file_count: int
    reverted_count: int
    reverted_at: Optional[str] = None


@dataclass(frozen=True)
class MoveRecord:
    """Represents a logged move operation."""

    id: int
    batch_id: int
    src: str
    dest: str
    size: int
    sha256: str
    reverted: int
    timestamp: str
    original_name: Optional[str] = None
    new_name: Optional[str] = None


def compute_sha256(path: Path, chunk_size: int = 65536) -> str:
    """Compute the SHA-256 hash of a file using chunked reads for low memory."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def get_db_path(target_dir: Path) -> Path:
    """Return the SQLite database path inside the target directory."""
    return Path(target_dir).resolve() / DB_FILENAME


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Open or initialize the SQLite database connection with required schema."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                target_dir TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'applied',
                reverted_at TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                src TEXT NOT NULL,
                dest TEXT NOT NULL,
                size INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                original_name TEXT,
                new_name TEXT,
                reverted INTEGER NOT NULL DEFAULT 0,
                timestamp TEXT NOT NULL
            );
            """
        )
        # Check migrations for existing databases
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(moves);")
        existing_cols = [row[1] for row in cursor.fetchall()]
        if "original_name" not in existing_cols:
            conn.execute("ALTER TABLE moves ADD COLUMN original_name TEXT;")
        if "new_name" not in existing_cols:
            conn.execute("ALTER TABLE moves ADD COLUMN new_name TEXT;")
    return conn


def create_batch(db_path: Path, target_dir: Path) -> int:
    """Create a new batch record and return its ID."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO batches (timestamp, target_dir, status)
            VALUES (?, ?, 'applied');
            """,
            (now_iso, str(target_dir.resolve())),
        )
        return cursor.lastrowid  # type: ignore


def record_move(
    db_path: Path,
    batch_id: int,
    src: Path,
    dest: Path,
    size: int,
    sha256: str,
    original_name: Optional[str] = None,
    new_name: Optional[str] = None,
) -> int:
    """Record a single move in the database."""
    now_iso = datetime.now(timezone.utc).isoformat()
    orig = original_name or src.name
    newn = new_name or dest.name
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO moves (batch_id, src, dest, size, sha256, original_name, new_name, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (batch_id, str(src.resolve()), str(dest.resolve()), size, sha256, orig, newn, now_iso),
        )
        return cursor.lastrowid  # type: ignore


def get_batch(db_path: Path, batch_id: int) -> Optional[BatchRecord]:
    """Retrieve a batch by its ID."""
    if not db_path.exists():
        return None
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, timestamp, target_dir, status, reverted_at
            FROM batches WHERE id = ?;
            """,
            (batch_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return BatchRecord(
            id=row[0],
            timestamp=row[1],
            target_dir=row[2],
            status=row[3],
            reverted_at=row[4],
        )


def get_last_batch(db_path: Path) -> Optional[BatchRecord]:
    """Retrieve the most recent batch that is not fully reverted (or latest batch)."""
    if not db_path.exists():
        return None
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        # Prefer the most recent applied batch
        cursor.execute(
            """
            SELECT id, timestamp, target_dir, status, reverted_at
            FROM batches
            WHERE status != 'reverted'
            ORDER BY id DESC
            LIMIT 1;
            """
        )
        row = cursor.fetchone()
        if not row:
            # Fall back to latest batch overall
            cursor.execute(
                """
                SELECT id, timestamp, target_dir, status, reverted_at
                FROM batches
                ORDER BY id DESC
                LIMIT 1;
                """
            )
            row = cursor.fetchone()
        if not row:
            return None
        return BatchRecord(
            id=row[0],
            timestamp=row[1],
            target_dir=row[2],
            status=row[3],
            reverted_at=row[4],
        )


def list_batches(db_path: Path) -> List[BatchSummary]:
    """List all batches with their file counts and statuses."""
    if not db_path.exists():
        return []
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT b.id, b.timestamp, b.target_dir, b.status, b.reverted_at,
                   COUNT(m.id) as file_count,
                   SUM(CASE WHEN m.reverted = 1 THEN 1 ELSE 0 END) as reverted_count
            FROM batches b
            LEFT JOIN moves m ON b.id = m.batch_id
            GROUP BY b.id
            ORDER BY b.id DESC;
            """
        )
        rows = cursor.fetchall()
        return [
            BatchSummary(
                id=row[0],
                timestamp=row[1],
                target_dir=row[2],
                status=row[3],
                reverted_at=row[4],
                file_count=row[5] or 0,
                reverted_count=row[6] or 0,
            )
            for row in rows
        ]


def get_moves_for_batch(db_path: Path, batch_id: int) -> List[MoveRecord]:
    """Retrieve all move records for a given batch."""
    if not db_path.exists():
        return []
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, batch_id, src, dest, size, sha256, reverted, timestamp, original_name, new_name
            FROM moves
            WHERE batch_id = ?
            ORDER BY id ASC;
            """,
            (batch_id,),
        )
        rows = cursor.fetchall()
        return [
            MoveRecord(
                id=row[0],
                batch_id=row[1],
                src=row[2],
                dest=row[3],
                size=row[4],
                sha256=row[5],
                reverted=row[6],
                timestamp=row[7],
                original_name=row[8],
                new_name=row[9],
            )
            for row in rows
        ]


def mark_move_reverted(db_path: Path, move_id: int) -> None:
    """Mark an individual move as reverted."""
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE moves SET reverted = 1 WHERE id = ?;",
            (move_id,),
        )


def update_batch_status(db_path: Path, batch_id: int, status: str) -> None:
    """Update status of a batch (applied, reverted, partially_reverted)."""
    reverted_at = (
        datetime.now(timezone.utc).isoformat()
        if status in ("reverted", "partially_reverted")
        else None
    )
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE batches SET status = ?, reverted_at = ? WHERE id = ?;",
            (status, reverted_at, batch_id),
        )


@dataclass
class RevertItemResult:
    """Outcome of attempting to revert a single moved file."""

    src: Path
    dest: Path
    success: bool
    status: str  # "restored", "missing_dest", "hash_mismatch", "src_conflict", "error"
    error: Optional[str] = None


@dataclass
class RevertReport:
    """Summary of batch revert operation."""

    batch_id: int
    restored: List[RevertItemResult]
    skipped: List[RevertItemResult]


def revert_batch(db_path: Path, batch_id: int) -> RevertReport:
    """Revert moves from a batch.

    Verifies file still exists at dest and sha256 matches.
    Refuses to overwrite any file at original src location.
    Skips and reports conflicts rather than failing or overwriting.
    """
    moves = get_moves_for_batch(db_path, batch_id)
    report = RevertReport(batch_id=batch_id, restored=[], skipped=[])

    for m in reversed(moves):
        # If this move was already marked reverted, skip it
        if m.reverted == 1:
            continue

        src = Path(m.src)
        dest = Path(m.dest)

        # 1. Verify destination file exists
        if not dest.exists():
            report.skipped.append(
                RevertItemResult(
                    src=src,
                    dest=dest,
                    success=False,
                    status="missing_dest",
                    error=f"Destination file missing: {dest}",
                )
            )
            continue

        # 2. Verify sha256 still matches
        try:
            current_hash = compute_sha256(dest)
            if current_hash != m.sha256:
                report.skipped.append(
                    RevertItemResult(
                        src=src,
                        dest=dest,
                        success=False,
                        status="hash_mismatch",
                        error="File at destination was modified since move (hash mismatch)",
                    )
                )
                continue
        except Exception as e:
            report.skipped.append(
                RevertItemResult(
                    src=src,
                    dest=dest,
                    success=False,
                    status="error",
                    error=f"Could not hash destination file: {e}",
                )
            )
            continue

        # 3. Verify original source location does not exist (never overwrite!)
        if src.exists() and src.resolve() != dest.resolve():
            report.skipped.append(
                RevertItemResult(
                    src=src,
                    dest=dest,
                    success=False,
                    status="src_conflict",
                    error=f"Original source path already exists: {src}",
                )
            )
            continue

        # 4. Safely move back
        try:
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest), str(src))
            mark_move_reverted(db_path, m.id)
            report.restored.append(
                RevertItemResult(
                    src=src,
                    dest=dest,
                    success=True,
                    status="restored",
                )
            )
        except Exception as e:
            report.skipped.append(
                RevertItemResult(
                    src=src,
                    dest=dest,
                    success=False,
                    status="error",
                    error=f"Error restoring file: {e}",
                )
            )

    # Update overall batch status in DB
    all_reverted_now = True
    refreshed_moves = get_moves_for_batch(db_path, batch_id)
    for rm in refreshed_moves:
        if rm.reverted == 0:
            all_reverted_now = False
            break

    if all_reverted_now and refreshed_moves:
        update_batch_status(db_path, batch_id, "reverted")
    elif report.restored:
        update_batch_status(db_path, batch_id, "partially_reverted")

    return report

