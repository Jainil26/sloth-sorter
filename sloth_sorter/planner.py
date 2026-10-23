"""Move planner for sloth-sorter.

Determines destination paths for files based on Tier 1 (rules) and optional
Tier 2 (Model2Vec smart embeddings) classification.
Handles intelligent renaming with TF-IDF keywords and date prefixes.
Resolves filename collisions safely by appending " (1)", " (2)", etc.
Ensures no file is ever overwritten.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sloth_sorter.config import get_default_config
from sloth_sorter.extractor import extract_text
from sloth_sorter.namer import generate_smart_name
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
    original_name: Optional[str] = None
    new_name: Optional[str] = None
    tier: str = "rule"
    score: Optional[float] = None


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
    max_length: int = 80,
) -> Path:
    """Find a non-colliding destination path.

    If dest already exists on disk (and isn't src) or is claimed by another move
    in the current plan, appends ' (1)', ' (2)', etc. before the extension while
    preserving the max_length limit.
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
        suffix_str = f" ({counter})"
        allowed_stem = max_length - len(suffix) - len(suffix_str)
        curr_stem = stem[:allowed_stem].rstrip("_-") if len(stem) > allowed_stem else stem
        candidate_name = f"{curr_stem}{suffix_str}{suffix}"
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
    smart: bool = False,
    rename: bool = False,
    model_path: Optional[str] = None,
    classifier: Optional[Any] = None,
) -> List[PlannedMove]:
    """Build a list of planned moves for the scanned files.

    Args:
        files: List of FileInfo objects to organize.
        target_dir: Target directory where category folders will live.
        config: Optional configuration dict.
        smart: If True, refine ambiguous or broad document categories using Tier 2 embeddings.
        rename: If True, rename files using date prefix and TF-IDF keywords.
        model_path: Custom path or repo ID for Model2Vec model.
        classifier: Optional custom or mocked classifier instance (useful for testing).

    Returns:
        List of PlannedMove objects ready for execution.
    """
    cfg = config or get_default_config()
    target_dir = Path(target_dir).resolve()

    moves: List[PlannedMove] = []
    claimed_destinations: Set[str] = set()

    for file_info in files:
        # Tier 1: Rules classification
        classification: ClassificationResult = classify(file_info, config=cfg)
        category = classification.category
        confidence = classification.confidence
        reason = classification.reason
        tier = "rule"
        score: Optional[float] = None
        extracted_text: Optional[str] = None

        # Tier 2: Smart embedding refinement
        # Runs on (a) confidence="low"/"Other", or
        # (b) broad "Documents" category if text is extractable
        if smart and (confidence == "low" or category in ("Other", "Documents")):
            extracted_text = extract_text(file_info.path)
            if extracted_text and extracted_text.strip():
                if classifier is not None:
                    clf = classifier
                else:
                    from sloth_sorter.classifier import get_smart_classifier

                    m_path = model_path or cfg.get("default_model", "minishlab/potion-base-8M")
                    sim_th = cfg.get("similarity_threshold", 0.35)
                    clf = get_smart_classifier(
                        model_name_or_path=m_path,
                        threshold=sim_th,
                        prototypes=cfg.get("prototypes"),
                    )

                smart_res = clf.classify_text(extracted_text)
                if smart_res is not None:
                    if smart_res.category != "Other" or category == "Other":
                        category = smart_res.category
                        confidence = smart_res.confidence
                        reason = smart_res.reason
                        tier = "embedding"
                        score = smart_res.score

        # Smart renaming
        if rename:
            if extracted_text is None:
                extracted_text = extract_text(file_info.path)
            target_filename = generate_smart_name(file_info.name, extracted_text, file_info.mtime)
        else:
            target_filename = file_info.name

        dest_dir = target_dir / category
        src_path = file_info.path.resolve()
        dest_path = resolve_collision(
            dest_dir=dest_dir,
            original_name=target_filename,
            src_path=src_path,
            claimed_destinations=claimed_destinations,
        ).resolve()

        # If src is already at dest, skip it
        if _normalize_path_key(src_path) == _normalize_path_key(dest_path):
            continue

        collision_resolved = dest_path.name != target_filename
        claimed_destinations.add(_normalize_path_key(dest_path))

        moves.append(
            PlannedMove(
                src=src_path,
                dest=dest_path,
                category=category,
                size=file_info.size,
                mtime=file_info.mtime,
                confidence=confidence,
                reason=reason,
                collision_resolved=collision_resolved,
                original_name=file_info.name,
                new_name=dest_path.name,
                tier=tier,
                score=score,
            )
        )

    return moves
