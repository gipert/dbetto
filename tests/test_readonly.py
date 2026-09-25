from __future__ import annotations

import copy
import json
import pickle
from pathlib import Path

import pytest
import yaml

from dbetto import AttrsDict, TextDB
from dbetto.attrsdict import ReadOnlyList
from dbetto.catalog import Props

testdb = Path(__file__).parent / "testdb"
T1, T2 = "20230101T000000Z", "20230102T000000Z"

DICT_MUTATIONS = [
    lambda d: d.__setitem__("new", 1),
    lambda d: setattr(d, "new", 1),
    lambda d: d.__delitem__("label"),
    lambda d: delattr(d, "label"),
    lambda d: d.pop("label"),
    lambda d: d.popitem(),
    lambda d: d.clear(),
    lambda d: d.update({"label": 0}),
    lambda d: d.setdefault("new", 1),
    lambda d: d.__ior__({"label": 0}),
]

LIST_MUTATIONS = [
    lambda x: x.append(5),
    lambda x: x.extend([5]),
    lambda x: x.insert(0, 5),
    lambda x: x.remove(1),
    lambda x: x.pop(),
    lambda x: x.clear(),
    lambda x: x.sort(reverse=True),
    lambda x: x.reverse(),
    lambda x: x.__setitem__(0, 5),
    lambda x: x.__delitem__(0),
    lambda x: x.__iadd__([5]),
    lambda x: x.__imul__(2),
]


@pytest.mark.parametrize("mutate", DICT_MUTATIONS)
def test_on_dict_mutations_raise(mutate):
    db = TextDB(testdb / "dir4")
    key2 = db.on(T1).group.key2
    with pytest.raises(TypeError):
        mutate(key2)
    assert db.on(T2).group.key2 == {"label": "b", "data": 2}


@pytest.mark.parametrize("mutate", LIST_MUTATIONS)
def test_on_list_mutations_raise(mutate):
    db = TextDB(testdb / "dir4")
    array = db.on(T1).array
    assert isinstance(array, ReadOnlyList)
    with pytest.raises(TypeError):
        mutate(array)
    assert db.on(T1).array == [1, 2, 3, 4]


def test_cache_readonly_independent_of_call_order():
    db = TextDB(testdb / "dir4")
    assert db["file1.json"].group.__readonly__  # before any on()
    db.on(T1)
    assert db["file1.json"].group.__readonly__


def test_map_does_not_unfreeze_cache():
    db = TextDB(testdb / "dir4", lazy=False)
    db.map("data")
    assert db["file1.json"].__readonly__
    assert db["file1.json"].group.__readonly__


def test_constructor_does_not_unfreeze():
    frozen = TextDB(testdb / "dir4").on(T1)
    AttrsDict({"x": frozen.group})
    assert frozen.group.__readonly__


def test_pickle_keeps_readonly():
    frozen = TextDB(testdb / "dir4").on(T1)
    thawed = pickle.loads(pickle.dumps(frozen))
    assert thawed == frozen
    assert thawed.__readonly__
    assert thawed.group.key1.__readonly__
    assert isinstance(thawed.array, ReadOnlyList)


def test_copies_are_writable():
    frozen = TextDB(testdb / "dir4").on(T1)

    deep = copy.deepcopy(frozen)
    assert deep == frozen
    deep.group.key1["label"] = "z"
    deep.array.append(5)
    assert type(deep.array) is list
    assert frozen.group.key1.label == "a"
    assert frozen.array == [1, 2, 3, 4]

    shallow = copy.copy(frozen)
    shallow["new"] = 1
    assert "new" not in frozen


def test_readonly_data_still_usable():
    frozen = TextDB(testdb / "dir4").on(T2)
    assert frozen.array + [0] == [-1, -2, -3, -4, 0]
    assert sorted(frozen.array) == [-4, -3, -2, -1]
    assert json.loads(json.dumps(frozen.array)) == [-1, -2, -3, -4]
    assert yaml.safe_dump({"a": frozen.array}) == yaml.safe_dump({"a": [-1, -2, -3, -4]})
    assert yaml.dump({"a": frozen.array}) == yaml.dump({"a": [-1, -2, -3, -4]})
    assert frozen.to_dict()["array"] == [-1, -2, -3, -4]
    assert frozen.group.map("label")["a"].data == -1

    merged = Props.add_to(frozen, {"array": [0], "extra": 1})
    assert merged.array == [0]
    assert merged.extra == 1
    assert frozen.array == [-1, -2, -3, -4]
