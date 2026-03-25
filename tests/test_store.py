"""map.json weighted format and load compatibility."""

import json
from pathlib import Path

from agent_lut.store import load_map, save_map, weighted_keywords_for_json


def test_weighted_keywords_order() -> None:
    lists = {
        "low": ["a.py"],
        "high": ["a.py", "b.py"],
        "mid": ["c.py", "d.py"],
    }
    w = weighted_keywords_for_json(lists)
    assert list(w.keys()) == ["high", "mid", "low"]
    assert w["high"] == {"weight": 2, "paths": ["a.py", "b.py"]}
    assert w["low"] == {"weight": 1, "paths": ["a.py"]}


def test_load_legacy_list_format(tmp_path: Path) -> None:
    p = tmp_path / "map.json"
    p.write_text(
        json.dumps(
            {
                "keywords": {"foo": ["x.py"], "bar": ["y.py", "z.py"]},
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    kw, _ = load_map(p)
    assert kw["foo"] == ["x.py"]
    assert set(kw["bar"]) == {"y.py", "z.py"}


def test_load_weighted_format(tmp_path: Path) -> None:
    p = tmp_path / "map.json"
    p.write_text(
        json.dumps(
            {
                "keywords": {
                    "x": {"weight": 2, "paths": ["a.py", "b.py"]},
                },
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    kw, _ = load_map(p)
    assert kw["x"] == ["a.py", "b.py"]


def test_save_roundtrip_order(tmp_path: Path) -> None:
    root = tmp_path
    save_map(
        root / "m.json",
        {"z": {"a.py"}, "a": {"a.py", "b.py", "c.py"}},
        root,
    )
    raw = json.loads((root / "m.json").read_text(encoding="utf-8"))
    keys = list(raw["keywords"].keys())
    assert keys[0] == "a"
    assert raw["keywords"]["a"]["weight"] == 3
    kw, _ = load_map(root / "m.json")
    assert kw["a"] == ["a.py", "b.py", "c.py"]
