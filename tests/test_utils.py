from __future__ import annotations

from pathlib import Path

from dbetto.catalog import Props


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
