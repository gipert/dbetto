from __future__ import annotations
from dbetto.catalog import Props
from pathlib import Path

def test_catalog_write(tmpdir):
    # test write_to with float
    test_dict = {
                "a": 5.1e-6, # test standard float
                "b": 5e-6,  # test float without decimal point
                "c":float("nan"),  # test nan
                "d":float("inf"), # test inf
                "e":float("-inf") # test -inf
                }
    Props.write_to(Path(tmpdir) / "test.yaml", test_dict)
    test_dict = Props.read_from(Path(tmpdir) / "test.yaml")
    assert isinstance(float(test_dict["a"]))
    assert isinstance(float(test_dict["b"]))
    assert isinstance(float(test_dict["c"]))
    assert isinstance(float(test_dict["d"]))
    assert isinstance(float(test_dict["e"]))

    