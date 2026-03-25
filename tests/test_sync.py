"""Incremental sync (cleanup-then-add) tests."""

from pathlib import Path

from agent_lut.indexer import build_index_for_files, iter_python_files
from agent_lut.store import load_map, save_map
from agent_lut.sync import cleanup_paths_from_keywords, update_index


def test_cleanup_removes_paths() -> None:
    kw = {"a": {"f1.py", "f2.py"}, "b": {"f1.py"}}
    out = cleanup_paths_from_keywords(kw, {"f1.py"})
    assert out == {"a": {"f2.py"}}


def test_update_reindexes_after_edit(tmp_path: Path) -> None:
    root = tmp_path
    p = root / "mod.py"
    p.write_text("def one():\n    pass\n", encoding="utf-8")
    map_path = root / "map.json"
    files = iter_python_files(root, respect_gitignore=False)
    idx = build_index_for_files(root, files)
    save_map(map_path, idx, root)

    kw, _ = load_map(map_path)
    assert "one" in kw

    p.write_text("def two():\n    pass\n", encoding="utf-8")
    merged, _warn = update_index(root, kw, [str(p)])
    assert "one" not in merged
    assert "two" in merged
    assert merged["two"] == {"mod.py"}


def test_update_removes_missing_file_from_index(tmp_path: Path) -> None:
    root = tmp_path
    map_path = root / "map.json"
    save_map(
        map_path,
        {"gone": {"missing.py"}, "stay": {"keep.py"}},
        root,
    )
    kw, _ = load_map(map_path)
    merged, warns = update_index(root, kw, ["missing.py"])
    assert "gone" not in merged
    assert merged.get("stay") == {"keep.py"}
    assert any("missing" in w for w in warns)
