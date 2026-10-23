"""Smart file naming engine for sloth-sorter.

Generates descriptive filenames from:
- File modification timestamp (YYYY-MM)
- 2 to 3 representative TF-IDF keywords extracted from text
- Strict sanitization of symbols and spaces
- Preserving original extension
- Capping total length to at most 80 characters
- Resolving collisions with " (1)", " (2)" while preserving max length limit
- Files without extractable text retain their original filename
"""

from collections import Counter
from datetime import datetime, timezone
import math
from pathlib import Path
import re
from typing import List, Optional, Set

MAX_NAME_LENGTH: int = 80

# Common English stopwords to filter out of keywords
STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "did",
    "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is",
    "it", "its", "itself", "just", "me", "more", "most", "my", "myself", "no",
    "nor", "not", "now", "of", "off", "on", "once", "only", "or", "other",
    "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should",
    "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "wasn", "we", "were",
    "what", "when", "where", "which", "while", "who", "whom", "why", "will",
    "with", "would", "you", "your", "yours", "yourself", "yourselves",
    # Document filler words
    "page", "file", "document", "total", "amount", "number", "date", "copyright",
    "rights", "reserved", "author", "version", "www", "http", "https", "com", "org",
}


def extract_keywords_tfidf(text: str, top_k: int = 3) -> List[str]:
    """Extract top 2-3 salient keywords from text using a lightweight built-in TF-IDF algorithm.

    No external libraries (no scikit-learn, no yake) to keep installation tiny.
    """
    if not text or not text.strip():
        return []

    # Tokenize words containing 3-20 letters
    tokens = re.findall(r"\b[a-zA-Z]{3,20}\b", text.lower())
    if not tokens:
        return []

    # Filter stop words and pure numbers
    valid_tokens = [w for w in tokens if w not in STOP_WORDS]
    if not valid_tokens:
        return []

    total_words = len(valid_tokens)
    term_counts = Counter(valid_tokens)

    # Calculate TF and position-adjusted IDF score
    scores = {}
    for word, count in term_counts.items():
        # Term frequency with sublinear scaling
        tf = 1.0 + math.log(count)

        # First occurrence index (earlier words like titles get higher weight)
        first_pos = tokens.index(word)
        pos_weight = 1.5 if first_pos < 15 else (1.2 if first_pos < 50 else 1.0)

        # Longer words are generally more descriptive than short 3-letter words
        len_weight = 1.0 + min(len(word) / 10.0, 0.5)

        # Frequency penalty for words that appear excessively
        freq_ratio = count / total_words
        freq_penalty = 0.8 if freq_ratio > 0.3 else 1.0

        scores[word] = tf * pos_weight * len_weight * freq_penalty

    # Select top_k words with highest scores, maintaining uniqueness
    sorted_words = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    keywords = [word for word, _ in sorted_words[:top_k]]
    return keywords


def sanitize_name_component(component: str) -> str:
    """Sanitize a name component: lowercase, replace spaces/symbols with underscores."""
    # Replace any non-alphanumeric character (except -) with underscore
    cleaned = re.sub(r"[^a-zA-Z0-9\-]+", "_", component.lower())
    # Collapse multiple underscores
    cleaned = re.sub(r"_+", "_", cleaned)
    # Strip leading and trailing underscores and hyphens
    return cleaned.strip("_-")


def generate_smart_name(
    original_name: str,
    text: str,
    mtime: float,
    max_length: int = MAX_NAME_LENGTH,
) -> str:
    """Generate a clean, standardized filename based on date + TF-IDF keywords.

    If text is empty or produces no keywords, returns original_name unchanged.

    Args:
        original_name: Current filename including extension.
        text: Extracted text content.
        mtime: File modification timestamp.
        max_length: Maximum allowed total filename length (default: 80).

    Returns:
        Formatted filename like '2024-03_electricity_invoice.pdf'.
    """
    if not text or not text.strip():
        return original_name

    keywords = extract_keywords_tfidf(text, top_k=3)
    if not keywords:
        return original_name

    # Determine date prefix from mtime (UTC)
    dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
    date_prefix = dt.strftime("%Y-%m")

    keywords_part = "_".join(sanitize_name_component(k) for k in keywords)
    base_stem = f"{date_prefix}_{keywords_part}"
    base_stem = sanitize_name_component(base_stem)

    ext = Path(original_name).suffix.lower()
    max_stem_length = max_length - len(ext)

    if len(base_stem) > max_stem_length:
        base_stem = base_stem[:max_stem_length].rstrip("_-")

    return f"{base_stem}{ext}"


def resolve_smart_collision(
    dest_dir: Path,
    candidate_name: str,
    src_path: Path,
    claimed_destinations: Set[str],
    normalize_key_fn,
    max_length: int = MAX_NAME_LENGTH,
) -> Path:
    """Resolve destination collisions with ' (1)', ' (2)' while respecting max_length limit."""
    initial_path = dest_dir / candidate_name
    initial_key = normalize_key_fn(initial_path)
    src_key = normalize_key_fn(src_path)

    if not initial_path.exists() and initial_key not in claimed_destinations:
        return initial_path

    if initial_key == src_key and initial_key not in claimed_destinations:
        return initial_path

    ext = Path(candidate_name).suffix
    stem = Path(candidate_name).stem

    counter = 1
    while True:
        suffix_str = f" ({counter})"
        allowed_stem_len = max_length - len(ext) - len(suffix_str)
        curr_stem = stem[:allowed_stem_len].rstrip("_-") if len(stem) > allowed_stem_len else stem
        candidate = f"{curr_stem}{suffix_str}{ext}"
        candidate_path = dest_dir / candidate
        candidate_key = normalize_key_fn(candidate_path)

        if candidate_key == src_key:
            return candidate_path

        if not candidate_path.exists() and candidate_key not in claimed_destinations:
            return candidate_path

        counter += 1
