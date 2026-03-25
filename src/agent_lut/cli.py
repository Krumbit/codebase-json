"""codebase CLI: init, update, lookup, dump, agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from rich.console import Console
from rich.table import Table

from agent_lut.agent_runner import run_agent
from agent_lut.indexer import build_index_for_files, iter_python_files
from agent_lut.metrics import RunMetrics, format_metrics_report
from agent_lut.store import load_map, save_map
from agent_lut.sync import update_index

console = Console(stderr=True)


def _default_map_path(repo_root: Path) -> Path:
    return (repo_root / "map.json").resolve()


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    out = Path(args.output).resolve() if args.output else _default_map_path(root)
    respect = not args.no_gitignore
    files = iter_python_files(root, respect_gitignore=respect)
    kw_sets = build_index_for_files(root, files)
    save_map(out, kw_sets, root)
    console.print(f"[green]Wrote[/green] {out} ({len(kw_sets)} keywords, {len(files)} .py files)")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    map_path = Path(args.map).resolve() if args.map else _default_map_path(root)
    paths = list(args.paths or [])
    if args.files_from:
        extra = args.files_from.read().splitlines()
        paths.extend(extra)
        args.files_from.close()
    if not paths:
        console.print("[red]No paths given[/red] (pass paths or --files-from)", style="bold")
        return 2
    if not map_path.is_file():
        console.print(f"[red]map not found:[/red] {map_path}", style="bold")
        return 1
    current, _meta = load_map(map_path)
    merged, warnings = update_index(root, current, paths)
    for w in warnings:
        console.print(f"[yellow]warn:[/yellow] {w}")
    save_map(map_path, merged, root, preserve_metadata=_meta)
    console.print(f"[green]Updated[/green] {map_path}")
    return 0


def cmd_lookup(args: argparse.Namespace) -> int:
    map_path = Path(args.map).resolve()
    if not map_path.is_file():
        console.print(f"[red]map not found:[/red] {map_path}", style="bold")
        return 1
    keywords, _ = load_map(map_path)
    k = args.keyword.strip().lower()
    paths = keywords.get(k, [])
    if args.format == "json":
        print(json.dumps({"keyword": k, "paths": paths}))
    else:
        for p in paths:
            print(p)
    return 0


def cmd_dump(args: argparse.Namespace) -> int:
    map_path = Path(args.map).resolve()
    if not map_path.is_file():
        console.print(f"[red]map not found:[/red] {map_path}", style="bold")
        return 1
    keywords, meta = load_map(map_path)
    # Frequency = number of files per keyword (SRS: top keywords by footprint)
    ranked = sorted(
        keywords.items(),
        key=lambda kv: len(kv[1]),
        reverse=True,
    )[: args.top]
    table = Table(title=f"Top {args.top} keywords (by file count)")
    table.add_column("keyword", style="cyan")
    table.add_column("files", justify="right")
    table.add_column("paths", overflow="fold")
    for kw, ps in ranked:
        table.add_row(kw, str(len(ps)), ", ".join(ps[:5]) + ("…" if len(ps) > 5 else ""))
    console.print(table)
    if meta.get("last_sync"):
        console.print(f"[dim]last_sync:[/dim] {meta['last_sync']}")
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    map_path = Path(args.map).resolve() if args.map else _default_map_path(root)
    if not map_path.is_file():
        console.print(f"[red]map not found:[/red] {map_path}", style="bold")
        return 1
    text = args.message
    if not text.strip():
        console.print("[red]Message required[/red] (-m or positional)", style="bold")
        return 2
    model = args.model or (
        "gpt-4o" if args.provider == "openai" else "claude-sonnet-4-20250514"
    )
    metrics = RunMetrics()
    if args.compare_baseline is not None:
        metrics.record_baseline_n_file_reads(args.compare_baseline)
    try:
        reply = run_agent(
            provider=args.provider,
            model=model,
            map_path=map_path,
            user_message=text,
            max_turns=args.max_turns,
            metrics=metrics,
        )
    except SystemExit as e:
        code = int(e.code) if isinstance(e.code, int) else 1
        console.print(f"[red]{e}[/red]")
        return code
    print(reply)
    console.print("[dim]--- metrics ---[/dim]")
    console.print(format_metrics_report(metrics))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="codebase", description="Agent-LUT codebase index CLI")
    sub = p.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Scan repo and write map.json")
    p_init.add_argument("--repo-root", default=".", help="Repository root")
    p_init.add_argument("--output", default=None, help="Output map.json path (default: <repo-root>/map.json)")
    p_init.add_argument("--no-gitignore", action="store_true", help="Do not apply .gitignore")
    p_init.set_defaults(func=cmd_init)

    p_up = sub.add_parser("update", help="Incremental cleanup-then-add for listed files")
    p_up.add_argument("--repo-root", default=".", help="Repository root")
    p_up.add_argument("--map", default=None, help="Path to map.json")
    p_up.add_argument(
        "--files-from",
        type=argparse.FileType("r"),
        default=None,
        help="Read additional paths (one per line) from this file or stdin (-)",
    )
    p_up.add_argument("paths", nargs="*", help="Changed .py paths (relative or absolute)")
    p_up.set_defaults(func=cmd_update)

    p_lu = sub.add_parser("lookup", help="Lookup paths for a keyword")
    p_lu.add_argument("--map", default="map.json", help="Path to map.json")
    p_lu.add_argument(
        "--format",
        choices=("lines", "json"),
        default="lines",
        help="Output format",
    )
    p_lu.add_argument("keyword", help="Keyword (case-insensitive)")
    p_lu.set_defaults(func=cmd_lookup)

    p_du = sub.add_parser("dump", help="Print top keywords summary")
    p_du.add_argument("--map", default="map.json", help="Path to map.json")
    p_du.add_argument("--top", type=int, default=20, help="How many keywords to show")
    p_du.set_defaults(func=cmd_dump)

    p_ag = sub.add_parser("agent", help="Run LLM with lookup_files tool")
    p_ag.add_argument("--provider", choices=("openai", "anthropic"), required=True)
    p_ag.add_argument("--model", default=None, help="Model id (defaults: gpt-4o / claude-sonnet-4-20250514)")
    p_ag.add_argument("--repo-root", default=".", help="Repository root (for default map path)")
    p_ag.add_argument("--map", default=None, help="Path to map.json")
    p_ag.add_argument("--max-turns", type=int, default=16, help="Max model/tool iterations")
    p_ag.add_argument(
        "--compare-baseline",
        type=int,
        default=None,
        metavar="N",
        help="Show rough token estimate for N file reads without index (demo)",
    )
    p_ag.add_argument(
        "-m",
        "--message",
        default="",
        help="User task (if omitted, first positional is used)",
    )
    p_ag.add_argument("rest", nargs="*", help="Task text if -m not given")
    p_ag.set_defaults(func=cmd_agent)

    return p


def main(argv: list[str] | None = None) -> None:
    # Load .env from cwd or first parent directory that has one (does not override existing env).
    load_dotenv(find_dotenv(usecwd=True))
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "agent":
        if not args.message.strip() and args.rest:
            args.message = " ".join(args.rest)
    code = args.func(args)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
