"""Command-line interface for sloth-sorter.

Provides:
- tidy: preview or execute file reorganization
- scan: list files and their classifications
- undo: safely revert previous sorting batches
- history: view past sorting batches
"""

import argparse
from collections import Counter
import csv
from datetime import datetime
from pathlib import Path
import sys
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sloth_sorter.config import DEFAULT_SIMILARITY_THRESHOLD
from sloth_sorter.mover import ExecutionReport, execute_plan
from sloth_sorter.planner import PlannedMove, build_plan
from sloth_sorter.rules import classify
from sloth_sorter.scanner import FileInfo, scan_directory
from sloth_sorter.undo_log import (
    get_batch,
    get_db_path,
    get_last_batch,
    list_batches,
    revert_batch,
)

console = Console()


def truncate_filename_str(text: str, max_chars: int = 40) -> str:
    """Truncate a filename to max_chars with an ellipsis preserving the extension."""
    if len(text) <= max_chars:
        return text
    dot_pos = text.rfind(".")
    if dot_pos > 0 and len(text) - dot_pos <= 10:
        ext = text[dot_pos:]
        stem = text[:dot_pos]
        allowed_stem = max_chars - len(ext) - 3
        if allowed_stem > 3:
            return f"{stem[:allowed_stem]}...{ext}"
    return f"{text[:max_chars - 3]}..."


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_iso_time(iso_str: str) -> str:
    """Format ISO timestamp into clean local/readable string."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_str


def handle_scan(args: argparse.Namespace) -> int:
    """Handle the 'scan' subcommand."""
    target = Path(args.folder).resolve()
    if not target.exists() or not target.is_dir():
        console.print(f"[bold red]Error:[/bold red] '{target}' is not a valid directory.")
        return 1

    console.print(f"[bold]Scanning:[/bold] {target} {'(recursive)' if args.recursive else ''}")

    max_files = getattr(args, "max_files", None)
    files = scan_directory(target, recursive=args.recursive, on_error=on_error, max_files=max_files)
    if max_files is not None and len(files) >= max_files:
        console.print(
            f"[bold yellow]Warning:[/bold yellow] Reached file limit of {max_files} files. "
            "Additional files were not scanned. (Use --max-files N to adjust limit)\n"
        )

    if not files:
        console.print("[yellow]No eligible files found to organize.[/yellow]")
        return 0

    smart = getattr(args, "smart", False)
    table = Table(title=f"Discovered Files ({len(files)})", show_lines=False)
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Size", justify="right", style="magenta")
    table.add_column("Category", style="green")
    table.add_column("Confidence", style="yellow")
    table.add_column("Reason", style="dim")
    if smart:
        table.add_column("Tier", style="yellow")
        table.add_column("Score", justify="right", style="magenta")

    clf = None
    if smart:
        from sloth_sorter.classifier import get_smart_classifier
        from sloth_sorter.extractor import extract_text

        model_p = getattr(args, "model_path", None) or "minishlab/potion-base-8M"
        clf = get_smart_classifier(model_name_or_path=model_p)

    for f in files:
        cls_res = classify(f)
        cat = cls_res.category
        tier = "rule"
        score_disp = "-"
        if smart and (cls_res.confidence == "low" or cat in ("Other", "Documents")):
            text = extract_text(f.path)
            if text and text.strip() and clf is not None:
                sm = clf.classify_text(text)
                if sm is not None:
                    if sm.category != "Other" or cat == "Other":
                        cat = sm.category
                        tier = "embedding"
                        score_disp = f"{sm.score:.2f}"

        if smart:
            table.add_row(
                f.name,
                format_size(f.size),
                cat,
                cls_res.confidence,
                cls_res.reason,
                tier,
                score_disp,
            )
        else:
            table.add_row(
                f.name,
                format_size(f.size),
                cat,
                cls_res.confidence,
                cls_res.reason,
            )

    console.print(table)

    if skipped_errors:
        console.print(f"\n[yellow]Skipped {len(skipped_errors)} inaccessible items:[/yellow]")
        for err in skipped_errors[:5]:
            console.print(f"  [dim]- {err}[/dim]")
        if len(skipped_errors) > 5:
            console.print(f"  [dim]... and {len(skipped_errors) - 5} more[/dim]")

    return 0


def handle_tidy(args: argparse.Namespace) -> int:
    """Handle the 'tidy' subcommand."""
    target = Path(args.folder).resolve()
    if not target.exists() or not target.is_dir():
        console.print(f"[bold red]Error:[/bold red] '{target}' is not a valid directory.")
        return 1

    apply = getattr(args, "apply", False)
    max_files = getattr(args, "max_files", None)

    scan_errors: List[str] = []

    def on_scan_error(p: Path, e: Exception) -> None:
        scan_errors.append(f"{p.name}: {e}")

    files = scan_directory(target, recursive=args.recursive, on_error=on_scan_error, max_files=max_files)
    if max_files is not None and len(files) >= max_files:
        console.print(
            f"[bold yellow]Warning:[/bold yellow] Reached file limit of {max_files} files. "
            "Additional files were not scanned. (Use --max-files N to adjust limit)\n"
        )

    moves = build_plan(
        files=files,
        target_dir=target,
        smart=getattr(args, "smart", False),
        rename=getattr(args, "rename", False),
        model_path=getattr(args, "model_path", None),
    )

    if not moves:
        console.print("[bold green]Folder is already organized! No moves needed.[/bold green]")
        return 0

    # Export full plan to CSV if --report is specified
    report_arg = getattr(args, "report", None)
    if report_arg:
        report_path = Path(report_arg).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["File", "New Name", "Category", "Tier", "Score", "Original Path", "Destination Path", "Notes"])
            for m in moves:
                orig = m.original_name or m.src.name
                newn = m.new_name or m.dest.name
                writer.writerow([
                    orig,
                    newn,
                    m.category,
                    m.tier,
                    f"{m.score:.2f}" if m.score is not None else "",
                    str(m.src),
                    str(m.dest),
                    "renamed (collision)" if m.collision_resolved else "",
                ])
        console.print(f"[bold green]Plan Report exported ({len(moves)} items):[/bold green] {report_path}\n")

    # 1. Preview Table: Row limiting (--limit and --all)
    show_all = getattr(args, "all", False)
    row_limit = getattr(args, "limit", 25)
    display_limit = len(moves) if show_all else max(0, row_limit)
    displayed_moves = moves[:display_limit]
    remaining_count = len(moves) - len(displayed_moves)

    # Check terminal width: compact format if width < 100
    terminal_width = console.width
    is_compact = terminal_width < 100

    if is_compact:
        console.print(f"[bold]Plan Preview ({len(moves)} file{'s' if len(moves) != 1 else ''}):[/bold]")
        for m in displayed_moves:
            orig = truncate_filename_str(m.original_name or m.src.name, 35)
            newn = truncate_filename_str(m.new_name or m.dest.name, 35)
            coll_note = " *(renamed)*" if m.collision_resolved else ""
            score_note = f": {m.score:.2f}" if m.score is not None else ""
            console.print(
                f" • [cyan]{orig}[/cyan] -> [bright_cyan]{newn}[/bright_cyan]{coll_note} "
                f"[[green]{m.category}[/green] | [yellow]{m.tier}{score_note}[/yellow]]"
            )
        if remaining_count > 0:
            console.print(
                f" [dim]... and {remaining_count} more files (use --all to show all, or --report plan.csv to export)[/dim]"
            )
        console.print()
    else:
        preview_table = Table(
            title=f"Plan Preview ({len(moves)} file{'s' if len(moves) != 1 else ''})",
            show_lines=False,
        )
        preview_table.add_column("File", style="cyan", no_wrap=True, min_width=18, max_width=40, overflow="ellipsis")
        preview_table.add_column("New Name", style="bright_cyan", no_wrap=True, min_width=18, max_width=40, overflow="ellipsis")
        preview_table.add_column("Category", style="green", no_wrap=True, min_width=12)
        preview_table.add_column("Tier", style="yellow", no_wrap=True, min_width=8)
        preview_table.add_column("Score", justify="right", style="magenta", no_wrap=True, min_width=6)

        for m in displayed_moves:
            orig = truncate_filename_str(m.original_name or m.src.name, 40)
            newn = truncate_filename_str(m.new_name or m.dest.name, 40)
            if m.collision_resolved:
                newn = f"{newn} [yellow](renamed)[/yellow]"
            score_disp = f"{m.score:.2f}" if m.score is not None else "-"
            preview_table.add_row(
                orig,
                newn,
                m.category,
                m.tier,
                score_disp,
            )

        console.print(preview_table)
        if remaining_count > 0:
            console.print(
                f"[dim]... and {remaining_count} more (use --all to show all, or --report plan.csv to export)[/dim]\n"
            )

    # 2. "Needs review" section: embedding files with scores close to threshold (max 15 rows)
    threshold = DEFAULT_SIMILARITY_THRESHOLD
    borderline_moves = [
        m for m in moves
        if m.tier == "embedding" and m.score is not None and m.score <= (threshold + 0.10)
    ]
    if borderline_moves:
        borderline_moves.sort(key=lambda m: m.score)
        displayed_review = borderline_moves[:15]
        if is_compact:
            console.print(
                f"[bold yellow]⚠️ Needs Review ({len(borderline_moves)} borderline file{'s' if len(borderline_moves) != 1 else ''} near threshold {threshold:.2f}):[/bold yellow]"
            )
            for rm in displayed_review:
                orig = truncate_filename_str(rm.original_name or rm.src.name, 35)
                console.print(
                    f" ? [cyan]{orig}[/cyan] -> [green]{rm.category}[/green] "
                    f"([magenta]{rm.score:.2f}[/magenta] vs threshold {threshold:.2f})"
                )
            if len(borderline_moves) > 15:
                console.print(f" [dim]... and {len(borderline_moves) - 15} more borderline files[/dim]")
            console.print()
        else:
            review_table = Table(
                title=f"⚠️ Needs Review ({len(borderline_moves)} borderline file{'s' if len(borderline_moves) != 1 else ''} near threshold {threshold:.2f})",
                show_lines=False,
                border_style="yellow",
            )
            review_table.add_column("File", style="cyan", no_wrap=True, min_width=18, max_width=40, overflow="ellipsis")
            review_table.add_column("Assigned Category", style="bold green", min_width=14)
            review_table.add_column("Score", justify="right", style="bold magenta", min_width=8)
            review_table.add_column("Threshold", justify="right", style="dim", min_width=8)
            review_table.add_column("Status", style="yellow", min_width=10)

            for rm in displayed_review:
                orig = truncate_filename_str(rm.original_name or rm.src.name, 40)
                review_table.add_row(
                    orig,
                    rm.category,
                    f"{rm.score:.2f}",
                    f"{threshold:.2f}",
                    "Borderline",
                )
            console.print(review_table)
            if len(borderline_moves) > 15:
                console.print(f"[dim]... and {len(borderline_moves) - 15} more borderline files needing review.[/dim]\n")

    # 3. Summary count by category
    category_counts = Counter(m.category for m in moves)
    category_sizes = Counter()
    for m in moves:
        category_sizes[m.category] += m.size

    summary_table = Table(title="Summary by Category", show_lines=False)
    summary_table.add_column("Category", style="bold green")
    summary_table.add_column("Count", justify="right", style="cyan")
    summary_table.add_column("Total Size", justify="right", style="magenta")

    for cat in sorted(category_counts.keys()):
        summary_table.add_row(
            cat,
            str(category_counts[cat]),
            format_size(category_sizes[cat]),
        )

    console.print(summary_table)

    if scan_errors:
        console.print(f"[yellow]Skipped {len(scan_errors)} files due to access permissions.[/yellow]")

    # 4. Execution / Dry-Run report
    if not apply:
        cmd_tokens = ["python -m sloth_sorter tidy", f'"{args.folder}"']
        if getattr(args, "recursive", False):
            cmd_tokens.append("--recursive")
        if getattr(args, "smart", False):
            cmd_tokens.append("--smart")
        if getattr(args, "rename", False):
            cmd_tokens.append("--rename")
        if getattr(args, "model_path", None):
            cmd_tokens.append(f'--model-path "{args.model_path}"')
        if getattr(args, "max_files", None):
            cmd_tokens.append(f"--max-files {args.max_files}")
        cmd_tokens.append("--apply")
        apply_command = " ".join(cmd_tokens)

        console.print(
            Panel(
                "[bold yellow]DRY-RUN ONLY[/bold yellow]: No files were moved.\n"
                "To execute these moves safely, re-run with [bold cyan]--apply[/bold cyan]:\n"
                f"  {apply_command}",
                title="Status",
                border_style="yellow",
            )
        )
        return 0

    # Execute with apply
    console.print("[bold cyan]Applying moves...[/bold cyan]")
    report: ExecutionReport = execute_plan(moves, target, apply=True)

    if report.successful:
        console.print(
            Panel(
                f"[bold green]Success![/bold green] Moved [bold]{len(report.successful)}[/bold] file(s) into category folders.\n"
                f"Batch ID: [bold cyan]#{report.batch_id}[/bold cyan] (logged to .sloth_sorter.db)\n"
                f"To undo this operation at any time, run:\n"
                f"  python -m sloth_sorter undo \"{args.folder}\"",
                title="Applied",
                border_style="green",
            )
        )

    if report.failed:
        console.print(f"[bold red]Warning: {len(report.failed)} move(s) could not be completed:[/bold red]")
        for f in report.failed:
            console.print(f"  [red]- {f.move.src.name} -> {f.move.dest}: {f.error}[/red]")

    return 0


def handle_undo(args: argparse.Namespace) -> int:
    """Handle the 'undo' subcommand."""
    target = Path(args.folder).resolve()
    db_path = get_db_path(target)

    if not db_path.exists():
        console.print(
            f"[bold red]No undo history found in:[/bold red] {target}\n"
            f"Expected database file [cyan]{db_path.name}[/cyan] does not exist."
        )
        return 1

    batch_to_revert = None
    if args.batch is not None:
        batch_to_revert = get_batch(db_path, args.batch)
        if not batch_to_revert:
            console.print(f"[bold red]Batch #{args.batch} not found.[/bold red]")
            return 1
    else:
        batch_to_revert = get_last_batch(db_path)
        if not batch_to_revert:
            console.print("[yellow]No batches found to undo.[/yellow]")
            return 0

    if batch_to_revert.status == "reverted":
        console.print(f"[yellow]Batch #{batch_to_revert.id} was already reverted.[/yellow]")
        return 0

    console.print(
        f"[bold]Reverting Batch #{batch_to_revert.id}[/bold] "
        f"applied at {format_iso_time(batch_to_revert.timestamp)}..."
    )

    report = revert_batch(db_path, batch_to_revert.id)

    if report.restored:
        restored_table = Table(title=f"Restored Files ({len(report.restored)})", show_lines=False)
        restored_table.add_column("File", style="cyan")
        restored_table.add_column("Restored To", style="green")

        for r in report.restored:
            try:
                rel = r.src.relative_to(target)
            except ValueError:
                rel = r.src
            restored_table.add_row(r.dest.name, str(rel))

        console.print(restored_table)
        console.print(f"[bold green]Successfully restored {len(report.restored)} file(s).[/bold green]")

    if report.skipped:
        skipped_table = Table(
            title=f"Skipped / Conflict Items ({len(report.skipped)})",
            show_lines=False,
            style="red",
        )
        skipped_table.add_column("File", style="yellow")
        skipped_table.add_column("Status", style="red")
        skipped_table.add_column("Reason", style="dim")

        for s in report.skipped:
            skipped_table.add_row(s.dest.name, s.status, s.error or "")

        console.print(skipped_table)
        console.print(
            "[yellow]Note: Sloth Sorter will never overwrite files during undo. "
            "Conflicting files were kept in their categorized locations.[/yellow]"
        )

    if not report.restored and not report.skipped:
        console.print("[yellow]No eligible moves found to revert for this batch.[/yellow]")

    return 0


def handle_history(args: argparse.Namespace) -> int:
    """Handle the 'history' subcommand."""
    target = Path(args.folder).resolve()
    db_path = get_db_path(target)

    if not db_path.exists():
        console.print(f"[yellow]No history database found in {target}.[/yellow]")
        return 0

    batches = list_batches(db_path)
    if not batches:
        console.print(f"[yellow]No sorting history recorded for {target}.[/yellow]")
        return 0

    table = Table(title=f"Sorting History for {target.name}", show_lines=False)
    table.add_column("Batch ID", justify="center", style="cyan")
    table.add_column("Timestamp", style="magenta")
    table.add_column("Files Moved", justify="right", style="green")
    table.add_column("Reverted", justify="right", style="yellow")
    table.add_column("Status", style="bold")

    status_styles = {
        "applied": "[green]Applied[/green]",
        "reverted": "[dim]Reverted[/dim]",
        "partially_reverted": "[yellow]Partially Reverted[/yellow]",
        "partially_applied": "[yellow]Partially Applied[/yellow]",
        "failed": "[red]Failed[/red]",
    }

    for b in batches:
        status_disp = status_styles.get(b.status, b.status)
        table.add_row(
            str(b.id),
            format_iso_time(b.timestamp),
            str(b.file_count),
            str(b.reverted_count),
            status_disp,
        )

    console.print(table)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="sloth-sorter",
        description="Offline, low-resource file organizer CLI with dry-run and undo.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scan
    scan_parser = subparsers.add_parser("scan", help="Scan and list files with classification")
    scan_parser.add_argument("folder", nargs="?", default=".", help="Target folder to scan (default: current directory)")
    scan_parser.add_argument(
        "-r", "--recursive", action="store_true", help="Recursively scan subdirectories"
    )
    scan_parser.add_argument(
        "--smart",
        action="store_true",
        default=False,
        help="Enable Tier 2 embedding classification for ambiguous documents",
    )
    scan_parser.add_argument(
        "--model-path",
        type=str,
        default=None,
        help="Path or HuggingFace ID for Model2Vec model (default: minishlab/potion-base-8M)",
    )
    scan_parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Maximum number of files to discover",
    )

    # tidy
    tidy_parser = subparsers.add_parser("tidy", help="Organize files into category folders")
    tidy_parser.add_argument("folder", nargs="?", default=".", help="Target folder to organize (default: current directory)")
    tidy_parser.add_argument(
        "-r", "--recursive", action="store_true", help="Recursively organize subdirectories"
    )
    tidy_parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Execute moves (default is dry-run preview)",
    )
    tidy_parser.add_argument(
        "--smart",
        action="store_true",
        default=False,
        help="Enable Tier 2 embedding classification for ambiguous documents",
    )
    tidy_parser.add_argument(
        "--rename",
        action="store_true",
        default=False,
        help="Intelligently rename files using modified date prefix and TF-IDF keywords",
    )
    tidy_parser.add_argument(
        "--model-path",
        type=str,
        default=None,
        help="Path or HuggingFace ID for Model2Vec model (default: minishlab/potion-base-8M)",
    )
    tidy_parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of rows to preview in table (default: 25)",
    )
    tidy_parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Show all rows in preview without truncation",
    )
    tidy_parser.add_argument(
        "--report",
        type=str,
        default=None,
        metavar="PLAN.CSV",
        help="Export full organization plan to a CSV file (e.g. plan.csv)",
    )
    tidy_parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Maximum number of files to process",
    )

    # undo
    undo_parser = subparsers.add_parser("undo", help="Revert a previous sorting batch")
    undo_parser.add_argument("folder", nargs="?", default=".", help="Target folder (default: current directory)")
    undo_parser.add_argument(
        "-b", "--batch", type=int, default=None, help="Specific batch ID to undo (default: latest active batch)"
    )

    # history
    hist_parser = subparsers.add_parser("history", help="List past sorting batches")
    hist_parser.add_argument("folder", nargs="?", default=".", help="Target folder (default: current directory)")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "scan":
        return handle_scan(args)
    elif args.command == "tidy":
        return handle_tidy(args)
    elif args.command == "undo":
        return handle_undo(args)
    elif args.command == "history":
        return handle_history(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
