"""File scanner for sloth-sorter.

Walks a folder, filters out hidden files, partial downloads, and existing
category folders, returning FileInfo objects.
"""

from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Set

from sloth_sorter.config import get_default_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileInfo:
    """Represents a file discovered during scanning."""

    path: Path
    name: str
    ext: str
    size: int
    mtime: float


def is_hidden(path: Path) -> bool:
    """Check if a file or directory is hidden.

    Checks for leading dot and Windows hidden file attribute if available.
    """
    if path.name.startswith("."):
        return True
    try:
        # Check Windows hidden attribute on Windows platforms
        if os.name == "nt":
            import ctypes

            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            if attrs != -1 and (attrs & 2):  # 2 == FILE_ATTRIBUTE_HIDDEN
                return True
    except Exception:
        pass
    return False


def scan_directory(
    target_dir: Path,
    recursive: bool = False,
    config: Optional[Dict[str, Any]] = None,
    on_error: Optional[Callable[[Path, Exception], None]] = None,
    max_files: Optional[int] = None,
) -> List[FileInfo]:
    """Scan a target directory and return a list of FileInfo objects.

    Args:
        target_dir: Directory to scan.
        recursive: If True, recursively scan subdirectories (except category/ignored folders).
        config: Optional configuration dictionary. Uses defaults if None.
        on_error: Optional callback invoked when a file/dir cannot be accessed.
        max_files: Optional maximum number of files to discover.

    Returns:
        List of FileInfo objects for files matching criteria.
    """
    cfg = config or get_default_config()
    all_cats = set(cfg.get("categories", [])) | set(cfg.get("smart_categories", []))
    categories: Set[str] = {c.lower() for c in all_cats}
    ignored_exts: Set[str] = {
        e.lower() for e in cfg.get("ignored_extensions", set())
    }
    ignored_names: Set[str] = {
        n.lower() for n in cfg.get("ignored_names", set())
    }

    target_dir = Path(target_dir).resolve()
    if not target_dir.exists():
        raise FileNotFoundError(f"Target directory does not exist: {target_dir}")
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Target is not a directory: {target_dir}")

    results: List[FileInfo] = []

    def _should_skip_dir(dir_path: Path) -> bool:
        name_lower = dir_path.name.lower()
        if name_lower in ignored_names:
            return True
        if is_hidden(dir_path):
            return True
        # Do not scan inside existing category folders
        if name_lower in categories:
            return True
        return False

    def _process_dir(current_dir: Path, current_depth: int) -> None:
        if max_files is not None and len(results) >= max_files:
            return
        try:
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    if max_files is not None and len(results) >= max_files:
                        break
                    try:
                        entry_path = Path(entry.path)
                        name_lower = entry.name.lower()

                        if entry.is_dir(follow_symlinks=False):
                            if recursive and not _should_skip_dir(entry_path):
                                _process_dir(entry_path, current_depth + 1)
                            continue

                        # It's a file or symlink to file
                        if entry.is_file(follow_symlinks=False):
                            if name_lower in ignored_names:
                                continue
                            if is_hidden(entry_path):
                                continue

                            ext = entry_path.suffix.lower()
                            if ext in ignored_exts:
                                continue

                            stat_res = entry.stat(follow_symlinks=False)
                            results.append(
                                FileInfo(
                                    path=entry_path,
                                    name=entry.name,
                                    ext=ext,
                                    size=stat_res.st_size,
                                    mtime=stat_res.st_mtime,
                                )
                            )
                    except (PermissionError, FileNotFoundError, OSError) as e:
                        logger.warning("Skipping file %s: %s", entry.name, e)
                        if on_error:
                            on_error(Path(entry.path), e)
        except (PermissionError, FileNotFoundError, OSError) as e:
            logger.warning("Skipping directory %s: %s", current_dir, e)
            if on_error:
                on_error(current_dir, e)

    _process_dir(target_dir, current_depth=0)
    return results
