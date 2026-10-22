"""Rule-based classification engine (Tier 1) for sloth-sorter.

Classifies files based on filename patterns and extension mappings.
Returns category, confidence ("rule" or "low"), and explanation.
Exposes a clean classify(file_info) interface that Day 2 can extend or replace.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Tuple

from sloth_sorter.config import get_default_config
from sloth_sorter.scanner import FileInfo


@dataclass(frozen=True)
class ClassificationResult:
    """Outcome of file classification."""

    category: str
    confidence: str  # "rule" for pattern/extension matches, "low" for fallback
    reason: str  # human-readable rule or reason that matched


# Compiled pattern cache: (pattern_str, compiled_regex, category)
_COMPILED_PATTERNS_CACHE: Optional[List[Tuple[str, re.Pattern, str]]] = None


def _get_compiled_patterns(patterns: List[Dict[str, str]]) -> List[Tuple[str, re.Pattern, str]]:
    compiled = []
    for item in patterns:
        pat_str = item["pattern"]
        cat = item["category"]
        compiled.append((pat_str, re.compile(pat_str, re.IGNORECASE), cat))
    return compiled


def classify(
    file_info: FileInfo,
    config: Optional[Dict[str, Any]] = None,
) -> ClassificationResult:
    """Classify a FileInfo into a category using Tier 1 rules.

    Priority:
    1. Filename pattern matches (e.g. invoice, IMG_, Screenshot, resume)
    2. Extension matches (e.g. .pdf -> Documents, .jpg -> Images)
    3. Fallback to "Other" with "low" confidence (ready for Day 2 ML models)

    Args:
        file_info: FileInfo instance to classify.
        config: Optional configuration dict. Defaults to default config.

    Returns:
        ClassificationResult with category, confidence, and reason.
    """
    cfg = config or get_default_config()

    # 1. Check filename patterns
    patterns = cfg.get("filename_patterns", [])
    for item in patterns:
        pat_str = item["pattern"]
        category = item["category"]
        # Match against full name or stem
        if re.search(pat_str, file_info.name, re.IGNORECASE):
            return ClassificationResult(
                category=category,
                confidence="rule",
                reason=f"pattern:{item.get('description', pat_str)}",
            )

    # 2. Check extension map
    ext_map: Dict[str, str] = cfg.get("extension_map", {})
    ext_lower = file_info.ext.lower()
    if ext_lower and ext_lower in ext_map:
        category = ext_map[ext_lower]
        return ClassificationResult(
            category=category,
            confidence="rule",
            reason=f"extension:{ext_lower}",
        )

    # 3. Fallback
    return ClassificationResult(
        category="Other",
        confidence="low",
        reason="fallback:unmatched",
    )
