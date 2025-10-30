import pickle
from pathlib import Path

from dbetto import AttrsDict, TextDB


def test_attrsdict_pickle_roundtrip():
    d = AttrsDict(
        {
            "a": {"id": 1, "group": {"id": 3}, "data": "x"},
            "b": {"id": 2, "group": {"id": 4}, "data": "y"},
        }
    )

    # Warm up cache to ensure it serializes/restores safely
    m1 = d.map("id")
    assert m1[1].data == "x"
    assert m1[2].data == "y"

    blob = pickle.dumps(d)
    d2 = pickle.loads(blob)

    # Basic structure and attribute access preserved
    assert isinstance(d2, AttrsDict)
    assert d2.a.data == "x"
    assert d2.b.group.id == 4

    # Mapping still works after unpickling
    m2 = d2.map("id")
    assert set(m2.keys()) == {1, 2}


def test_textdb_pickle_roundtrip(tmp_path: Path):
    # Create a small database
    (tmp_path / "file1.json").write_text(
        '{"id": 1, "name": "alpha"}', encoding="utf-8"
    )
    (tmp_path / "file2.yaml").write_text("id: 2\nname: beta\n", encoding="utf-8")
    sub = tmp_path / "dir1"
    sub.mkdir()
    (sub / "file3.yaml").write_text("value: 42\n", encoding="utf-8")

    db = TextDB(tmp_path, lazy=False)

    # Ensure access works before pickling
    f1 = db["file1"]
    assert isinstance(f1, AttrsDict)
    assert f1.id == 1
    assert f1.name == "alpha"

    blob = pickle.dumps(db)
    db2 = pickle.loads(blob)

    # Path type restored, access still works
    assert isinstance(db2, TextDB)
    assert isinstance(db2.__path__, Path)

    f1_b = db2["file1"]
    assert f1_b.id == 1
    assert f1_b.name == "alpha"

    f2 = db2.file2
    assert f2.id == 2
    assert f2.name == "beta"

    d1 = db2["dir1"]
    assert isinstance(d1, TextDB)
    f3 = d1["file3"]
    assert f3.value == 42
