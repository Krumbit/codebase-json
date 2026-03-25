"""Cleanup-then-add incremental index updates."""

from __future__ import annotations

from pathlib import Path

from agent_lut.indexer import build_index_for_files, merge_keyword_maps
from agent_lut.store import sets_from_lists


def normalize_changed_paths(
    repo_root: Path,
    paths: list[str],
) -> tuple[set[str], list[Path], list[str]]:
    """
    Returns (relative_paths_to_clean, existing_py_files_to_rescan, warnings).
    Missing files still contribute to cleanup paths so deleted files leave the index.
    """
    repo_root = repo_root.resolve()
    warnings: list[str] = []
    to_clean: set[str] = set()
    to_scan: list[Path] = []
    for raw in paths:
        raw = raw.strip()
        if not raw:
            continue
        p = Path(raw)
        if not p.is_absolute():
            p = (repo_root / p).resolve()
        else:
            p = p.resolve()
        try:
            rel = p.relative_to(repo_root).as_posix()
        except ValueError:
            warnings.append(f"outside repo: {raw}")
            continue
        if not rel.endswith(".py"):
            warnings.append(f"skip non-.py: {raw}")
            continue
        to_clean.add(rel)
        if not p.exists():
            warnings.append(f"missing (cleanup only): {raw}")
            continue
        to_scan.append(p)
    return to_clean, to_scan, warnings


def cleanup_paths_from_keywords(
    keywords: dict[str, set[str]],
    paths_to_remove: set[str],
) -> dict[str, set[str]]:
    """Remove any mention of paths_to_remove from every keyword; drop empty keywords."""
    out: dict[str, set[str]] = {}
    for kw, files in keywords.items():
        new_files = files - paths_to_remove
        if new_files:
            out[kw] = new_files
    return out


def update_index(
    repo_root: Path,
    current: dict[str, list[str]],
    changed_paths: list[str],
) -> tuple[dict[str, set[str]], list[str]]:
    """
    Load current as sets, remove all changed file paths from index, re-scan those files, merge.
    Returns (new_keywords_as_sets, warnings).
    """
    repo_root = repo_root.resolve()
    as_sets = sets_from_lists(current)
    rels, file_paths, warnings = normalize_changed_paths(repo_root, changed_paths)
    cleaned = cleanup_paths_from_keywords(as_sets, rels)
    new_contrib = build_index_for_files(repo_root, file_paths)
    merged = merge_keyword_maps(cleaned, new_contrib)
    return merged, warnings
