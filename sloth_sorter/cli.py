"""Command-line interface for sloth-sorter.

Provides:
- tidy: preview or execute file reorganization
- scan: list files and their classifications
- undo: safely revert previous sorting batches
- history: view past sorting batches
"""

import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path
import sys
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

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

    skipped_errors: List[str] = []

    def on_error(p: Path, e: Exception) -> None:
        skipped_errors.append(f"{p.name}: {e}")

    files = scan_directory(target, recursive=args.recursive, on_error=on_error)

    if not files:
        console.print("[yellow]No eligible files found to organize.[/yellow]")
        return 0

    table = Table(title=f"Discovered Files ({len(files)})", show_lines=False)
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Size", justify="right", style="magenta")
    table.add_column("Category", style="green")
    table.add_column("Confidence", style="yellow")
    table.add_column("Reason", style="dim")

    for f in files:
        cls_res = classify(f)
        table.add_row(
            f.name,
            format_size(f.size),
            cls_res.category,
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

    scan_errors: List[str] = []

    def on_scan_error(p: Path, e: Exception) -> None:
        scan_errors.append(f"{p.name}: {e}")

    files = scan_directory(target, recursive=args.recursive, on_error=on_scan_error)
    moves = build_plan(files, target)

    if not moves:
        console.print("[bold green]Folder is already organized! No moves needed.[/bold green]")
        return 0

    # 1. Preview Table: File | Category | Destination
    preview_table = Table(
        title=f"Plan Preview ({len(moves)} file{'s' if len(moves) != 1 else ''})",
        show_lines=False,
    )
    preview_table.add_column("File", style="cyan", no_wrap=True)
    preview_table.add_column("Category", style="green")
    preview_table.add_column("Destination", style="blue")
    preview_table.add_column("Notes", style="yellow")

    for m in moves:
        # Display destination relative to target folder for readability
        try:
            rel_dest = m.dest.relative_to(target)
        except ValueError:
            rel_dest = m.dest
        notes = "[bold yellow]renamed (collision)[/bold yellow]" if m.collision_resolved else ""
        preview_table.add_row(m.src.name, m.category, str(rel_dest), notes)

    console.print(preview_table)

    # 2. Summary count by category
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

    # 3. Execution / Dry-Run report
    if not apply:
        console.print(
            Panel(
                "[bold yellow]DRY-RUN ONLY[/bold yellow]: No files were moved.\n"
                "To execute these moves safely, re-run with [bold cyan]--apply[/bold cyan]:\n"
                f"  python -m sloth_sorter tidy \"{args.folder}\" --apply",
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
