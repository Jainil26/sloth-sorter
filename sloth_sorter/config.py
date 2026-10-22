"""Configuration defaults for sloth-sorter.

Contains default categories, extension mappings, filename patterns,
and ignore lists. Can later be extended to load from YAML/JSON files.
"""

from typing import Any, Dict, List

DEFAULT_CATEGORIES: List[str] = [
    "Images",
    "Documents",
    "Videos",
    "Audio",
    "Archives",
    "Installers",
    "Code",
    "Other",
]

# Case-insensitive extensions mapped to category
DEFAULT_EXTENSION_MAP: Dict[str, str] = {
    # Images
    ".jpg": "Images",
    ".jpeg": "Images",
    ".png": "Images",
    ".gif": "Images",
    ".bmp": "Images",
    ".webp": "Images",
    ".svg": "Images",
    ".tiff": "Images",
    ".tif": "Images",
    ".ico": "Images",
    ".heic": "Images",
    ".raw": "Images",
    # Documents
    ".pdf": "Documents",
    ".docx": "Documents",
    ".doc": "Documents",
    ".xlsx": "Documents",
    ".xls": "Documents",
    ".pptx": "Documents",
    ".ppt": "Documents",
    ".txt": "Documents",
    ".csv": "Documents",
    ".odt": "Documents",
    ".rtf": "Documents",
    ".md": "Documents",
    ".epub": "Documents",
    ".pages": "Documents",
    ".key": "Documents",
    ".numbers": "Documents",
    # Videos
    ".mp4": "Videos",
    ".mkv": "Videos",
    ".avi": "Videos",
    ".mov": "Videos",
    ".wmv": "Videos",
    ".flv": "Videos",
    ".webm": "Videos",
    ".m4v": "Videos",
    ".3gp": "Videos",
    # Audio
    ".mp3": "Audio",
    ".wav": "Audio",
    ".flac": "Audio",
    ".aac": "Audio",
    ".ogg": "Audio",
    ".m4a": "Audio",
    ".wma": "Audio",
    ".opus": "Audio",
    # Archives
    ".zip": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
    ".bz2": "Archives",
    ".xz": "Archives",
    ".7z": "Archives",
    ".rar": "Archives",
    ".tgz": "Archives",
    # Installers
    ".exe": "Installers",
    ".msi": "Installers",
    ".dmg": "Installers",
    ".pkg": "Installers",
    ".deb": "Installers",
    ".rpm": "Installers",
    ".iso": "Installers",
    ".appimage": "Installers",
    # Code
    ".py": "Code",
    ".js": "Code",
    ".ts": "Code",
    ".html": "Code",
    ".css": "Code",
    ".json": "Code",
    ".yaml": "Code",
    ".yml": "Code",
    ".sh": "Code",
    ".bat": "Code",
    ".ps1": "Code",
    ".c": "Code",
    ".cpp": "Code",
    ".h": "Code",
    ".java": "Code",
    ".rs": "Code",
    ".go": "Code",
    ".sql": "Code",
    ".php": "Code",
    ".rb": "Code",
}

# Regex patterns checked against the filename stem (case-insensitive)
DEFAULT_FILENAME_PATTERNS: List[Dict[str, str]] = [
    # Document patterns
    {
        "pattern": r"(^|[_\-\s])(invoice|receipt|bill|statement|paystub|w2|1099)([_\-\s\.]|$)",
        "category": "Documents",
        "description": "Financial documents",
    },
    {
        "pattern": r"(^|[_\-\s])(resume|cv)([_\-\s\.]|$)",
        "category": "Documents",
        "description": "Resumes and CVs",
    },
    {
        "pattern": r"(^|[_\-\s])(assignment|homework|syllabus|lecture|quiz|exam|thesis|paper|report|contract|agreement|tax)([_\-\s\.]|$)",
        "category": "Documents",
        "description": "Academic and business documents",
    },
    # Image patterns
    {
        "pattern": r"^(img|image|dsc|pxl)[_\-\s0-9]",
        "category": "Images",
        "description": "Camera image prefixes",
    },
    {
        "pattern": r"(^|[_\-\s])screenshot([_\-\s0-9]|$)",
        "category": "Images",
        "description": "Screenshots",
    },
    # Installer patterns
    {
        "pattern": r"(^|[_\-\s])(setup|installer)([_\-\s\.]|$)",
        "category": "Installers",
        "description": "Installer packages",
    },
]

# Extensions for partial/temporary downloads that must always be skipped
IGNORED_EXTENSIONS = {
    ".crdownload",
    ".part",
    ".tmp",
    ".download",
    ".aria2",
    ".partial",
}

# Names of files or directories to ignore
IGNORED_NAMES = {
    ".sloth_sorter.db",
    ".sloth_sorter.db-journal",
    ".sloth_sorter.db-wal",
    ".sloth_sorter.db-shm",
    ".git",
    ".venv",
    ".vscode",
    ".idea",
    "__pycache__",
}


def get_default_config() -> Dict[str, Any]:
    """Return a fresh copy of the default configuration."""
    return {
        "categories": list(DEFAULT_CATEGORIES),
        "extension_map": dict(DEFAULT_EXTENSION_MAP),
        "filename_patterns": list(DEFAULT_FILENAME_PATTERNS),
        "ignored_extensions": set(IGNORED_EXTENSIONS),
        "ignored_names": set(IGNORED_NAMES),
    }
