"""Safe text extraction module for sloth-sorter.

Extracts the first ~2000 characters of text from .txt, .md, .csv, .pdf, and .docx files.
Designed for high speed and low memory:
- Never loads entire huge files into memory.
- Enforces strict file size limits (default 10MB max).
- Returns empty string ("") on errors, corrupt files, or unsupported formats.
- Never crashes under any circumstance.
"""

from pathlib import Path
from typing import Union

MAX_EXTRACT_CHARS: int = 2000
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB cap


def _extract_text_file(path: Path, max_chars: int) -> str:
    """Extract text from plain text formats (.txt, .md, .csv)."""
    # Read at most max_chars * 4 bytes to handle multibyte UTF-8 safely
    read_byte_limit = max_chars * 4
    with open(path, "rb") as f:
        raw_bytes = f.read(read_byte_limit)

    # Attempt utf-8 decoding, fallback to latin-1 or lossy
    try:
        decoded = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            decoded = raw_bytes.decode("latin-1")
        except Exception:
            decoded = raw_bytes.decode("utf-8", errors="ignore")

    return decoded[:max_chars].strip()


def _extract_pdf(path: Path, max_chars: int) -> str:
    """Extract text from PDF using PyMuPDF."""
    import pymupdf  # lazy import

    text_parts = []
    total_len = 0
    doc = None
    try:
        doc = pymupdf.open(str(path))
        for page in doc:
            page_text = page.get_text()
            if page_text:
                text_parts.append(page_text)
                total_len += len(page_text)
                if total_len >= max_chars:
                    break
    finally:
        if doc is not None:
            doc.close()

    combined = "\n".join(text_parts)
    return combined[:max_chars].strip()


def _extract_docx(path: Path, max_chars: int) -> str:
    """Extract text from .docx using python-docx."""
    import docx  # lazy import

    doc = docx.Document(str(path))
    text_parts = []
    total_len = 0

    # Read paragraphs
    for p in doc.paragraphs:
        if p.text:
            text_parts.append(p.text)
            total_len += len(p.text)
            if total_len >= max_chars:
                break

    # If still below max_chars, check table cells
    if total_len < max_chars:
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text:
                        text_parts.append(cell.text)
                        total_len += len(cell.text)
                        if total_len >= max_chars:
                            break
                if total_len >= max_chars:
                    break
            if total_len >= max_chars:
                break

    combined = "\n".join(text_parts)
    return combined[:max_chars].strip()


def extract_text(
    file_path: Union[str, Path],
    max_chars: int = MAX_EXTRACT_CHARS,
    max_file_size: int = MAX_FILE_SIZE_BYTES,
) -> str:
    """Safely extract up to max_chars characters of text from a file.

    Supported extensions: .txt, .md, .csv, .pdf, .docx.
    Returns empty string ("") on unsupported types or on any error.

    Args:
        file_path: Path to the target file.
        max_chars: Maximum characters to extract (default ~2000).
        max_file_size: Max allowed file size in bytes to prevent OOM.

    Returns:
        Extracted text string or "" on error / unsupported.
    """
    try:
        path = Path(file_path).resolve()
        if not path.is_file():
            return ""

        # Check file size limit
        try:
            size = path.stat().st_size
            if size == 0 or size > max_file_size:
                return ""
        except (OSError, PermissionError):
            return ""

        ext = path.suffix.lower()

        if ext in (".txt", ".md", ".csv"):
            return _extract_text_file(path, max_chars)
        elif ext == ".pdf":
            return _extract_pdf(path, max_chars)
        elif ext == ".docx":
            return _extract_docx(path, max_chars)
        else:
            return ""

    except Exception:
        # Never crash on corrupt or problematic files
        return ""
