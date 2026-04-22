from __future__ import annotations

from pathlib import Path

from dbetto import AttrsDict
from dbetto.catalog import Props
from dbetto.utils import load_attrs_dict, load_dict


def test_catalog_write(tmpdir):
    # test write_to with float
    test_dict = {
        "a": 5.1e-6,  # test standard float
        "b": 5e-6,  # test float without decimal point
        "c": float("nan"),  # test nan
        "d": float("inf"),  # test inf
        "e": float("-inf"),  # test -inf
    }
    Props.write_to(Path(tmpdir) / "test.yaml", test_dict)
    test_dict = Props.read_from(Path(tmpdir) / "test.yaml")
    assert isinstance(test_dict["a"], float)
    assert isinstance(test_dict["b"], float)
    assert isinstance(test_dict["c"], float)
    assert isinstance(test_dict["d"], float)
    assert isinstance(test_dict["e"], float)


def test_load_attrs_dict():
    testdb = Path(__file__).parent / "testdb"
    for fname in (testdb / "file1.json", testdb / "file2.yaml"):
        result = load_attrs_dict(fname)
        assert isinstance(result, AttrsDict)
        plain = load_dict(fname)
        assert result == plain
