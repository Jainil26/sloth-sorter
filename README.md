# 🦥 sloth-sorter

An offline, low-resource file organizer CLI in Python 3.14. Sorts, cleans, and categorizes messy folders (like `Downloads` or `Desktop`) with collision safety, dry-run by default, and cryptographically verified undos.

Designed specifically for low-end laptops with limited CPU, memory, and disk space:
- **Zero Heavy ML Dependencies**: No PyTorch, no HuggingFace downloads, no multi-gigabyte models.
- **Pure Day 1 Footprint**: Uses only `watchdog`, `rich`, `pytest`, and standard library (`sqlite3`, `pathlib`, `shutil`, `hashlib`, `argparse`).
- **Never Deletes User Files**: Moves and renames only.
- **Dry-Run by Default**: Nothing moves without explicit `--apply`.
- **Safe Undo with SHA-256**: SQLite-backed batch log verifies file hashes before reverting and refuses to overwrite if conflicts exist.

---

## 📦 Installation

Ensure you have Python 3.14 installed. Activate your virtual environment and install the pinned dependencies:

```bash
# Activate your venv
.venv\Scripts\activate      # Windows
# or: source .venv/bin/activate  # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

---

## 🚀 Usage

### 1. Dry-Run Preview (Default)
Running `tidy` without flags prints a rich preview table of all proposed moves and category counts. **No files are moved.**

```bash
python -m sloth_sorter tidy "C:\Users\username\Downloads"
```

Output preview:
- Discovered files, target categories, and destination paths
- Category breakdown with file counts and total sizes
- Clear prompt indicating dry-run status

### 2. Apply Moves
To execute the plan and organize files into category folders:

```bash
python -m sloth_sorter tidy "C:\Users\username\Downloads" --apply
```

Files are safely organized into subfolders:
- `Images/` (`.jpg`, `.png`, `.webp`, `.svg`, `IMG_*`, `Screenshot*`)
- `Documents/` (`.pdf`, `.docx`, `.xlsx`, `.csv`, `invoice*`, `resume*`, `assignment*`)
- `Videos/` (`.mp4`, `.mkv`, `.mov`, `.webm`, etc.)
- `Audio/` (`.mp3`, `.wav`, `.flac`, `.aac`, etc.)
- `Archives/` (`.zip`, `.tar.gz`, `.7z`, `.rar`, etc.)
- `Installers/` (`.exe`, `.msi`, `.dmg`, `.pkg`, etc.)
- `Code/` (`.py`, `.js`, `.ts`, `.html`, `.css`, `.json`, etc.)
- `Other/` (fallback for unrecognized extensions)

A batch ID is logged to `.sloth_sorter.db` inside the organized folder along with SHA-256 hashes of all moved files.

### 3. Collision Protection
If `report.pdf` already exists in `Documents/`, the new file is automatically renamed to `report (1).pdf`, `report (2).pdf`, etc. **Existing files are never overwritten.**

### 4. Undo a Batch
To revert the most recent organization run:

```bash
python -m sloth_sorter undo "C:\Users\username\Downloads"
```

To revert a specific batch ID:

```bash
python -m sloth_sorter undo "C:\Users\username\Downloads" --batch 1
```

**Safety Checks During Undo:**
- Verifies the file still exists at the destination.
- Computes SHA-256 to ensure the file was not modified since being sorted.
- Verifies the original source location is clear (never overwrites newly created files).
- Skips and reports any conflicts cleanly.

### 5. View History
Inspect all past organization runs:

```bash
python -m sloth_sorter history "C:\Users\username\Downloads"
```

### 6. Scan Directory
Inspect files and classification rules without generating a move plan:

```bash
python -m sloth_sorter scan "C:\Users\username\Downloads"
# Or recursively:
python -m sloth_sorter scan "C:\Users\username\Downloads" --recursive
```

---

## 🧪 Testing

Run the test suite with pytest:

```bash
pytest -v
```

All tests pass using `tmp_path` fixtures covering:
- Rule classifications and pattern overrides
- Collision renaming logic
- Dry-run non-destructive verification
- Apply execution and multi-file move verification
- Full undo restoration and SHA-256 hash preservation
- Conflict skipping (modified files, recreated source files)
- Directory scanner exclusion of hidden files, category folders, and partial downloads (`.crdownload`, `.part`, `.tmp`)

---

## 🗺️ Roadmap (Day 2)

- **Model2Vec Classification**: Ultra-fast, low-memory (~30MB) CPU embedding model for files categorized as `Other` (confidence `"low"`).
- **Keyword Renaming**: Intelligent name sanitization and date/topic prepending for generic filenames.
- **Background Watcher**: Auto-sorting daemon using `watchdog` to monitor folders in real time.
