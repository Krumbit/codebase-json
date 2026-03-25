"""Extract Python symbols (class/def names) and discover indexable files."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pathspec

# Line-anchored: class Foo, def bar, async def baz (skip indented = nested inside blocks still match top-level in practice)
_CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z_]\w*)\s*(?:\(.*\))?\s*:")
_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")


def extract_symbols_from_source(source: str) -> set[str]:
    """Return unique symbol names from Python source (classes and defs)."""
    names: set[str] = set()
    for line in source.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        m = _CLASS_RE.match(line)
        if m:
            names.add(m.group(1))
            continue
        m = _DEF_RE.match(line)
        if m:
            names.add(m.group(1))
    return names


def extract_symbols_from_file(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return extract_symbols_from_source(text)


def load_gitignore_spec(repo_root: Path) -> pathspec.PathSpec | None:
    gi = repo_root / ".gitignore"
    if not gi.is_file():
        return None
    lines = gi.read_text(encoding="utf-8", errors="replace").splitlines()
    patterns = [ln for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    if not patterns:
        return None
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def iter_python_files(repo_root: Path, respect_gitignore: bool = True) -> list[Path]:
    """All .py files under repo_root, optionally filtered by .gitignore."""
    repo_root = repo_root.resolve()
    spec = load_gitignore_spec(repo_root) if respect_gitignore else None
    out: list[Path] = []
    for p in repo_root.rglob("*.py"):
        try:
            rel = p.relative_to(repo_root)
        except ValueError:
            continue
        rel_posix = rel.as_posix()
        if spec and spec.match_file(rel_posix):
            continue
        out.append(p)
    out.sort()
    return out


def path_to_repo_relative(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def build_index_for_files(
    repo_root: Path,
    file_paths: list[Path],
) -> dict[str, set[str]]:
    """
    Map lowercase keyword -> set of repo-relative posix paths.
    """
    repo_root = repo_root.resolve()
    keywords: dict[str, set[str]] = defaultdict(set)
    for fp in file_paths:
        fp = fp.resolve()
        if not fp.is_file() or fp.suffix != ".py":
            continue
        rel = path_to_repo_relative(fp, repo_root)
        for sym in extract_symbols_from_file(fp):
            keywords[sym.lower()].add(rel)
    return dict(keywords)


def merge_keyword_maps(
    *maps: dict[str, set[str]],
) -> dict[str, set[str]]:
    merged: dict[str, set[str]] = defaultdict(set)
    for m in maps:
        for k, paths in m.items():
            merged[k].update(paths)
    return {k: set(v) for k, v in merged.items()}
