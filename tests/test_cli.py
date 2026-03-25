"""CLI smoke tests via subprocess."""

import subprocess
import sys
from pathlib import Path


def run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agent_lut.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_init_lookup_dump(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(
        "def hello():\n    pass\nclass World:\n    pass\n",
        encoding="utf-8",
    )
    r = run_cli(tmp_path, "init", "--repo-root", ".", "--no-gitignore", "--output", "map.json")
    assert r.returncode == 0, r.stderr

    r2 = run_cli(tmp_path, "lookup", "--map", "map.json", "--format", "json", "hello")
    assert r2.returncode == 0
    assert "sample.py" in r2.stdout

    r3 = run_cli(tmp_path, "dump", "--map", "map.json", "--top", "5")
    assert r3.returncode == 0
    assert "hello" in r3.stderr or "hello" in r3.stdout


def test_update_changes_index(tmp_path: Path) -> None:
    mod = tmp_path / "m.py"
    mod.write_text("def a():\n    pass\n", encoding="utf-8")
    r = run_cli(tmp_path, "init", "--repo-root", ".", "--no-gitignore")
    assert r.returncode == 0

    mod.write_text("def b():\n    pass\n", encoding="utf-8")
    r2 = run_cli(tmp_path, "update", "--repo-root", ".", "--", "m.py")
    assert r2.returncode == 0, r2.stderr

    r3 = run_cli(tmp_path, "lookup", "--map", "map.json", "b")
    assert r3.returncode == 0
    assert "m.py" in r3.stdout
    r4 = run_cli(tmp_path, "lookup", "--map", "map.json", "a")
    assert r4.returncode == 0
    assert r4.stdout.strip() == ""
