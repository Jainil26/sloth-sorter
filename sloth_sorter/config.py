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

# Smart categories refined from Documents / Other by Tier 2
SMART_CATEGORIES: List[str] = [
    "Invoices",
    "Resumes",
    "Assignments",
    "Reports",
    "Study Material",
    "Notes",
    "Other",
]

# Prototype phrases for Model2Vec embedding centroids
DEFAULT_PROTOTYPES: Dict[str, List[str]] = {
    "Invoices": [
        "invoice payment due total amount billing account receipt",
        "electric utility bill payment due date invoice number total due",
        "invoice for professional consulting services rendered hourly rate bill to customer",
        "receipt of purchase payment confirmation order total credit card payment",
        "monthly subscription statement billing balance due remittance",
        "tax invoice commercial sales receipt items quantity unit price subtotal",
        "final invoice overdue payment notification account summary please pay immediately",
        "billing receipt customer invoice purchase order charges fee statement",
    ],
    "Resumes": [
        "resume curriculum vitae work experience education skills employment history",
        "software engineer resume technical skills python projects work experience bachelors",
        "professional summary work history education certifications contact information",
        "curriculum vitae research publications academic experience references skills",
        "experience senior developer achievements qualifications education university degree",
        "job application resume candidate profile skills summary career background",
        "technical resume software developer experience programming languages education",
        "curriculum vitae qualifications objective professional employment summary",
    ],
    "Assignments": [
        "homework assignment problem set due date submission guidelines course",
        "computer science programming assignment exercise question solutions score",
        "student assignment project prompt grading rubric submission instructions",
        "weekly homework assignment exercises answer sheet due next monday",
        "final course project assignment problem statement deliverables rubric",
        "lab assignment instructions exercise questions report submission",
        "midterm assignment questions instructions student submission course",
        "academic coursework assignment problem description due date syllabus",
    ],
    "Reports": [
        "annual quarterly financial performance business report summary analysis",
        "market research report executive summary findings data analysis conclusion",
        "project progress status report milestone completion metrics overview",
        "technical evaluation report investigation findings recommendations",
        "audit report compliance review executive overview methodology results",
        "monthly business operational performance report key metrics analysis",
        "formal report research findings conclusions recommendations executive summary",
        "annual company performance report strategic overview financial highlights",
    ],
    "Study Material": [
        "lecture notes chapter slides presentation course study guide textbook",
        "introduction to algorithms course syllabus reading material review notes",
        "exam revision study notes key concepts formulas definitions guide",
        "class lecture summary chapter outline study notes exam preparation",
        "university course lecture slides topic overview study material",
        "revision guide key terms concepts formulas practice questions",
        "study notes syllabus exam review lecture summary course concepts",
        "academic study guide lecture slides chapter summary key terms",
    ],
    "Notes": [
        "meeting notes discussion action items summary key takeaways next steps",
        "personal notes thoughts ideas todo list quick reminder draft",
        "quick scratch notes brainstorming ideas thoughts outline",
        "team sync meeting notes attendees action items decisions made",
        "daily standup notes updates blockers todo list tasks",
        "project planning notes ideas discussion bullet points draft",
        "scratchpad informal notes thoughts todo list reminders draft",
        "quick thoughts memo meeting summary action items follow up",
    ],
    "Other": [
        "miscellaneous random file generic text unknown contents",
        "temporary scratchpad undefined general note",
        "unclassified content random words generic document",
        "system log output debugging trace errors events",
        "plain text snippet uncategorized data information",
        "various notes and general documents with mixed topics",
    ],
}

DEFAULT_SIMILARITY_THRESHOLD: float = 0.35
DEFAULT_MODEL_NAME: str = "minishlab/potion-base-8M"

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
        "smart_categories": list(SMART_CATEGORIES),
        "extension_map": dict(DEFAULT_EXTENSION_MAP),
        "filename_patterns": list(DEFAULT_FILENAME_PATTERNS),
        "ignored_extensions": set(IGNORED_EXTENSIONS),
        "ignored_names": set(IGNORED_NAMES),
        "prototypes": {k: list(v) for k, v in DEFAULT_PROTOTYPES.items()},
        "similarity_threshold": DEFAULT_SIMILARITY_THRESHOLD,
        "default_model": DEFAULT_MODEL_NAME,
    }
