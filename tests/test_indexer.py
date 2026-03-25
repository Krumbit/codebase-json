"""Indexer symbol extraction tests."""

from pathlib import Path

from agent_lut.indexer import build_index_for_files, extract_symbols_from_file, extract_symbols_from_source


def test_extract_classes_and_defs() -> None:
    src = '''
# comment
class Foo:
    def inner(self):
        pass

async def bar(x):
    pass

def baz():
    """doc"""
    pass
'''
    names = extract_symbols_from_source(src)
    assert names == {"Foo", "bar", "baz", "inner"}


def test_skips_comment_line() -> None:
    src = "# def fake()\nclass Real:\n    pass\n"
    assert extract_symbols_from_source(src) == {"Real"}


def test_build_index_for_files(tmp_path: Path) -> None:
    root = tmp_path
    (root / "a.py").write_text("def alpha():\n    pass\n", encoding="utf-8")
    (root / "sub").mkdir()
    (root / "sub" / "b.py").write_text("class Beta:\n    pass\n", encoding="utf-8")
    files = [root / "a.py", root / "sub" / "b.py"]
    idx = build_index_for_files(root, files)
    assert idx["alpha"] == {"a.py"}
    assert idx["beta"] == {"sub/b.py"}


def test_extract_from_file(tmp_path: Path) -> None:
    p = tmp_path / "m.py"
    p.write_text("def x():\n  pass\n", encoding="utf-8")
    assert extract_symbols_from_file(p) == {"x"}
