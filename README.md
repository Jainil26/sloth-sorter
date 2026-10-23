# 🦥 sloth-sorter

An offline, low-resource file organizer CLI in Python 3.14. Sorts, cleans, and categorizes messy folders (like `Downloads` or `Desktop`) with collision safety, dry-run by default, intelligent embedding-based document classification, smart keyword renaming, and cryptographically verified undos.

Designed specifically for low-end laptops with limited CPU, memory, and disk space:
- **Zero Heavy ML Bloat**: No PyTorch, no sentence-transformers, no LLMs. Uses Model2Vec static embeddings (`minishlab/potion-base-8M`, ~30MB).
- **Tiny Install Footprint**: Total virtual environment disk space is only ~303MB.
- **Lazy Loaded**: Runs without `--smart` never import or load Model2Vec.
- **Never Deletes User Files**: Moves and renames only.
- **Dry-Run by Default**: Nothing moves without explicit `--apply`.
- **Safe Undo with SHA-256**: SQLite-backed batch log tracks moves and renames, verifies hashes before reverting, and prevents overwriting conflicts.

---

## 🏗️ How It Works: 3 Tiers

Sloth Sorter uses a fast, hierarchical, multi-tiered approach:

```
                      [ Incoming File ]
                              │
                              ▼
            ┌───────────────────────────────────┐
            │      Tier 1: Rules & Regex        │
            │  Filename patterns & extensions   │
            └─────────────────┬─────────────────┘
                              │
          ┌───────────────────┴───────────────────┐
          │                                       │
Specific Match (Images, Code,              Broad match ("Documents")
Audio, Videos, Archives, Installers)       or Low confidence ("Other")
          │                                       │
          │                                       ▼
          │                         ┌───────────────────────────┐
          │                         │ Extract text (first 2KB)  │
          │                         │ .txt, .md, .csv, .pdf,    │
          │                         │ .docx (capped, safe)      │
          │                         └─────────────┬─────────────┘
          │                                       │
          │                       Is --smart flag enabled?
          │                             ├── No ──> Keep Tier 1 category
          │                             └── Yes ─┐
          │                                      ▼
          │                         ┌───────────────────────────┐
          │                         │ Tier 2: Model2Vec Embed   │
          │                         │ Cosine sim vs Centroids:  │
          │                         │ Invoices, Resumes, Notes, │
          │                         │ Reports, Assignments, etc │
          │                         └─────────────┬─────────────┘
          │                                       │
          └───────────────────┬───────────────────┘
                              │
                              ▼
                    Is --rename enabled?
                        ├── No ──> Keep original filename
                        └── Yes ─┐
                                 ▼
                    ┌───────────────────────────┐
                    │  Tier 3: Smart Renaming   │
                    │  YYYY-MM + TF-IDF keywords│
                    │  e.g. 2024-03_invoice.pdf │
                    └────────────┬──────────────┘
                                 │
                                 ▼
                    ┌───────────────────────────┐
                    │   Collision Resolution    │
                    │   Appends (1), (2), etc.  │
                    │   Max 80 chars cap        │
                    └────────────┬──────────────┘
                                 │
                                 ▼
                    ┌───────────────────────────┐
                    │    Execution & Undo Log   │
                    │    Dry-run preview        │
                    │    SHA-256 + SQLite log   │
                    └───────────────────────────┘
```

1. **Tier 1 (Instant Rules)**: Evaluates file extensions and filename regexes (e.g. `.png` -> `Images`, `.zip` -> `Archives`).
2. **Tier 2 (Smart Embeddings with `--smart`)**: For generic documents and unclassified files with extractable text, extracts the first ~2000 characters and computes cosine similarity against category prototype centroids using `model2vec`. Refines broad "Documents" into `Invoices`, `Resumes`, `Assignments`, `Reports`, `Study Material`, or `Notes`.
3. **Tier 3 (Intelligent Renaming with `--rename`)**: Generates clean, standardized filenames composed of the file's modified date (`YYYY-MM`) plus 2-3 salient keywords extracted via a small built-in TF-IDF algorithm (no external NLP libraries required).

---

## 📊 Benchmark Results

Benchmarked on Python 3.14 on a standard laptop running the smart pipeline over 30 realistic multi-paragraph sample documents (invoices, resumes, assignments, reports, and study guides in `.txt` and `.docx` formats):

| Metric | Value | Notes |
| :--- | :--- | :--- |
| **Dataset Size** | 30 files | 15 `.txt`, 15 `.docx` with realistic content |
| **Model Load Time** | **5.13 s** | Model2Vec `minishlab/potion-base-8M` |
| **Processing Speed** | **18.1 files/s** | 1.65 s total for 30 full files (extract + embed + TF-IDF) |
| **Peak RAM** | **191.5 MB** | Lightweight RSS memory footprint |
| **Virtualenv Size** | **303.4 MB** | Complete `.venv` including all dependencies |
| **Classification Accuracy** | **100.0%** (30/30) | Ground-truth evaluated across 5 categories |

### Category Breakdown

| Category | Total Samples | Correct | Accuracy |
| :--- | :---: | :---: | :---: |
| **Assignments** | 6 | 6 | **100.0%** |
| **Invoices** | 6 | 6 | **100.0%** |
| **Reports** | 6 | 6 | **100.0%** |
| **Resumes** | 6 | 6 | **100.0%** |
| **Study Material** | 6 | 6 | **100.0%** |

To reproduce these benchmarks on your machine:
```bash
python benchmark.py
```

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

### 2. Smart Classification & Renaming (`--smart` & `--rename`)
Enable Tier 2 embedding classification and intelligent TF-IDF renaming:

```bash
# Preview smart classification and renaming
python -m sloth_sorter tidy "C:\Users\username\Downloads" --smart --rename

# Execute moves safely to disk
python -m sloth_sorter tidy "C:\Users\username\Downloads" --smart --rename --apply
```

The Rich preview table displays:
- **File**: Original filename
- **New Name**: Proposed standardized filename (`YYYY-MM_keyword1_keyword2.ext`)
- **Category**: Destination folder (e.g. `Invoices`, `Resumes`)
- **Tier**: Classification method (`rule` or `embedding`)
- **Score**: Embedding cosine similarity score (e.g. `0.70`)

### 3. Fully Offline / Air-Gapped Mode (`--model-path`)
The Model2Vec model (`minishlab/potion-base-8M`, ~30MB) is downloaded once from Hugging Face and cached locally. You can also specify a local directory:

```bash
python -m sloth_sorter tidy "C:\Users\username\Downloads" --smart --model-path "C:\models\potion-base-8M"
```

### 4. Reversible Undo (Including Renames)
Undo operations restore files back to their original root locations **and** restore their original filenames.

```bash
python -m sloth_sorter undo "C:\Users\username\Downloads"
```

**Safety Checks During Undo:**
- Verifies destination file exists.
- Compares SHA-256 hash to guarantee the file was not modified after sorting.
- Verifies original source filename and location are clear (never overwrites newly created files).
- Skips and reports any conflicts cleanly.

### 5. View History
Inspect all past organization runs:

```bash
python -m sloth_sorter history "C:\Users\username\Downloads"
```

### 6. Scan Directory
Scan files and classifications without generating a move plan:

```bash
python -m sloth_sorter scan "C:\Users\username\Downloads" --smart
```

---

## 🧪 Testing

Run the full automated test suite with pytest:

```bash
pytest -v
```

All 37 unit and integration tests pass, covering:
- Tier 1 rule classifications and regex overrides
- Tier 2 Model2Vec embedding classifier (with offline mock support)
- Safe text extractor on `.txt`, `.md`, `.csv`, `.pdf`, `.docx` (capping, corrupt file resilience)
- TF-IDF keyword extraction, sanitization, 80-character capping, and collision resolution
- Undo of combined rename + move operations with SHA-256 hash verification
- Backward compatibility ensuring Tier 1 behavior is unchanged when `--smart` is omitted

---

## 🗺️ Roadmap (Day 3)

- **Background Watcher**: Auto-sorting daemon using `watchdog` to monitor folders in real time.
- **Custom Config & User Overrides**: Custom YAML/JSON config file support for user-defined categories and prototype keywords.
