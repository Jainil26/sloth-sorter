"""Benchmark script for sloth-sorter Day 2 Smart Pipeline.

Measures:
- Model load time (seconds)
- Files / second throughput
- Peak RAM usage (MB)
- Total virtualenv disk size (MB)
- Classification accuracy against ground-truth labels

Outputs a clean Markdown table ready for blog post publication.
"""

import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import tracemalloc
import psutil

from sloth_sorter.classifier import get_smart_classifier
from sloth_sorter.config import DEFAULT_MODEL_NAME
from sloth_sorter.planner import build_plan
from sloth_sorter.scanner import scan_directory
from sample_data.make_samples import SAMPLES_DATA, generate_samples


def get_dir_size_mb(path: Path) -> float:
    """Calculate the total size of a directory in Megabytes."""
    total_bytes = 0
    if not path.exists():
        return 0.0
    for entry in path.rglob("*"):
        if entry.is_file():
            try:
                total_bytes += entry.stat().st_size
            except (OSError, PermissionError):
                pass
    return total_bytes / (1024 * 1024)


def run_benchmark() -> None:
    # 1. Setup isolated test folder with the 30 realistic samples
    temp_dir = Path(tempfile.mkdtemp(prefix="sloth_bench_"))
    try:
        ground_truth = generate_samples(temp_dir)
        total_files = len(ground_truth)

        # Track memory
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / (1024 * 1024)
        tracemalloc.start()

        # 2. Measure Model Load Time
        t_model_start = time.perf_counter()
        clf = get_smart_classifier(model_name_or_path=DEFAULT_MODEL_NAME)
        # Trigger centroid computation
        clf._ensure_loaded()
        t_model_end = time.perf_counter()
        model_load_time_sec = t_model_end - t_model_start

        # 3. Measure Pipeline Execution Time (Scan + Extract + Classify + Rename)
        t_pipeline_start = time.perf_counter()
        scanned_files = scan_directory(temp_dir)
        moves = build_plan(
            files=scanned_files,
            target_dir=temp_dir,
            smart=True,
            rename=True,
            classifier=clf,
        )
        t_pipeline_end = time.perf_counter()
        pipeline_time_sec = t_pipeline_end - t_pipeline_start
        files_per_sec = total_files / pipeline_time_sec if pipeline_time_sec > 0 else 0.0

        # Memory tracking
        current_mem, peak_tracemalloc = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        mem_after = process.memory_info().rss / (1024 * 1024)
        peak_rss_mb = max(mem_after, mem_before + (peak_tracemalloc / (1024 * 1024)))

        # 4. Measure Virtualenv Size
        venv_path = Path(".venv").resolve()
        venv_size_mb = get_dir_size_mb(venv_path)

        # 5. Measure Accuracy
        correct = 0
        category_stats = {}
        for expected_cat in set(ground_truth.values()):
            category_stats[expected_cat] = {"total": 0, "correct": 0}

        results_list = []
        for m in moves:
            orig_name = m.original_name or m.src.name
            expected = ground_truth.get(orig_name, "Unknown")
            predicted = m.category
            is_correct = (predicted.lower() == expected.lower())
            if is_correct:
                correct += 1
                if expected in category_stats:
                    category_stats[expected]["correct"] += 1
            if expected in category_stats:
                category_stats[expected]["total"] += 1

            results_list.append({
                "file": orig_name,
                "new_name": m.new_name or m.dest.name,
                "expected": expected,
                "predicted": predicted,
                "tier": m.tier,
                "score": f"{m.score:.2f}" if m.score is not None else "-",
                "match": "PASS" if is_correct else "FAIL",
            })

        accuracy_pct = (correct / total_files) * 100.0 if total_files > 0 else 0.0

        # Output Markdown Report
        print("\n# Sloth Sorter Benchmark Report (Day 2: Smart Pipeline)\n")
        print("### Executive Performance Summary\n")
        print("| Metric | Value | Notes |")
        print("| :--- | :--- | :--- |")
        print(f"| **Dataset Size** | {total_files} files | 15 .txt, 15 .docx with realistic content |")
        print(f"| **Model Load Time** | {model_load_time_sec:.3f} s | Model2Vec `minishlab/potion-base-8M` |")
        print(f"| **Processing Speed** | **{files_per_sec:.1f} files/s** | {pipeline_time_sec:.3f} s total for 30 files |")
        print(f"| **Peak RAM** | **{peak_rss_mb:.1f} MB** | RSS delta +{mem_after - mem_before:.1f} MB |")
        print(f"| **Total .venv Size** | **{venv_size_mb:.1f} MB** | Python 3.14 + numpy + docx + pymupdf + model2vec |")
        print(f"| **Classification Accuracy** | **{accuracy_pct:.1f}%** ({correct}/{total_files}) | Tier 2 Cosine Similarity Centroids |")

        print("\n### Category Breakdown\n")
        print("| Category | Total Samples | Correct | Accuracy |")
        print("| :--- | :---: | :---: | :---: |")
        for cat, stats in sorted(category_stats.items()):
            c_acc = (stats["correct"] / stats["total"] * 100.0) if stats["total"] > 0 else 0.0
            print(f"| {cat} | {stats['total']} | {stats['correct']} | {c_acc:.1f}% |")

        print("\n### Sample File Results Preview\n")
        print("| Original File | Smart New Name | Category | Tier | Score | Match |")
        print("| :--- | :--- | :--- | :---: | :---: | :---: |")
        for r in results_list[:12]:
            print(f"| `{r['file']}` | `{r['new_name']}` | **{r['predicted']}** | {r['tier']} | {r['score']} | {r['match']} |")
        if len(results_list) > 12:
            print(f"| *... and {len(results_list) - 12} more* | | | | | |")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_benchmark()
