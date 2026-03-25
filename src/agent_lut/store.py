"""Load/save map.json with atomic writes."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_metadata(repo_root: Path, keywords: dict[str, list[str]]) -> dict[str, Any]:
    all_files: set[str] = set()
    for paths in keywords.values():
        all_files.update(paths)
    return {
        "last_sync": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo_path": str(repo_root.resolve().as_posix()),
        "stats": {
            "total_keywords": len(keywords),
            "total_files": len(all_files),
        },
    }


def keywords_to_sorted_lists(keywords: dict[str, set[str]]) -> dict[str, list[str]]:
    return {k: sorted(v) for k, v in sorted(keywords.items())}


def _paths_from_keyword_value(v: Any) -> list[str] | None:
    """Accept legacy list of paths or {"weight": n, "paths": [...]}."""
    if isinstance(v, list):
        return [str(p) for p in v]
    if isinstance(v, dict):
        paths = v.get("paths")
        if isinstance(paths, list):
            return [str(p) for p in paths]
    return None


def weighted_keywords_for_json(lists: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    """
    Each keyword -> {"weight": file_count, "paths": [...]}.
    Keys are ordered by descending weight, then keyword (stable scan / eyeball).
    """
    rows: list[tuple[str, list[str], int]] = []
    for k, raw_paths in lists.items():
        paths = sorted(set(raw_paths))
        rows.append((k.lower(), paths, len(paths)))
    rows.sort(key=lambda t: (-t[2], t[0]))
    out: dict[str, dict[str, Any]] = {}
    for k, paths, w in rows:
        out[k] = {"weight": w, "paths": paths}
    return out


def load_map(path: Path) -> tuple[dict[str, list[str]], dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    keywords = raw.get("keywords") or {}
    meta = raw.get("metadata") or {}
    kw_out: dict[str, list[str]] = {}
    for k, v in keywords.items():
        paths = _paths_from_keyword_value(v)
        if paths is not None:
            kw_out[str(k).lower()] = paths
    return kw_out, meta


def save_map(
    path: Path,
    keywords: dict[str, set[str]] | dict[str, list[str]],
    repo_root: Path,
    preserve_metadata: dict[str, Any] | None = None,
) -> None:
    if not keywords:
        lists: dict[str, list[str]] = {}
    else:
        sample = next(iter(keywords.values()))
        if isinstance(sample, set):
            lists = keywords_to_sorted_lists(keywords)  # type: ignore[arg-type]
        else:
            lists = {k.lower(): sorted(set(v)) for k, v in keywords.items()}  # type: ignore[union-attr]

    meta = dict(preserve_metadata) if preserve_metadata else {}
    meta.update(default_metadata(repo_root, lists))
    ordered_kw = weighted_keywords_for_json(lists)
    payload = {"keywords": ordered_kw, "metadata": meta}
    write_json_atomic(path, payload)


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=path.parent,
        prefix=".map.",
        suffix=".json.tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=False)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def sets_from_lists(keywords: dict[str, list[str]]) -> dict[str, set[str]]:
    return {k: set(v) for k, v in keywords.items()}
