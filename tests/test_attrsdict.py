from __future__ import annotations

from copy import deepcopy

import pytest

from dbetto.attrsdict import AttrsDict, AttrsDict_RO


def test_to_dict_recursively_converts_nested_values():
    nested = AttrsDict({"inner": {"value": 1}})
    nested["items"] = [
        {"name": "first", "payload": {"value": 2}},
        AttrsDict({"name": "second", "payload": {"value": 3}}),
    ]

    plain = nested.to_dict()

    assert plain == {
        "inner": {"value": 1},
        "items": [
            {"name": "first", "payload": {"value": 2}},
            {"name": "second", "payload": {"value": 3}},
        ],
    }
    assert isinstance(plain, dict)
    assert all(isinstance(item, dict) for item in plain["items"])
    assert all(
        isinstance(item, AttrsDict) for item in nested["items"]
    )  # sanity check original list still uses AttrsDict wrappers


def test_to_dict_does_not_mutate_original_structure():
    source = AttrsDict({"values": [{"a": 1}]})
    original_list = source["values"]

    converted = source.to_dict()

    assert isinstance(converted["values"], list)
    assert isinstance(converted["values"][0], dict)
    # ensure the AttrsDict list in the source still contains AttrsDict entries
    assert isinstance(original_list[0], AttrsDict)
    # ensure the converted structure no longer has AttrsDict wrappers
    assert not isinstance(converted["values"][0], AttrsDict)


def test_attrsdict_ro():
    d = AttrsDict_RO({"a": 1, "b": {"c": 2}})
    assert d["a"] == 1
    assert d["b"]["c"] == 2
    assert d.a == 1
    assert d.b.c == 2
    assert isinstance(d, AttrsDict)
    assert isinstance(d.b, AttrsDict_RO)
    d_copy = deepcopy(d)
    assert isinstance(d_copy, AttrsDict)
    assert not isinstance(d_copy, AttrsDict_RO)

    with pytest.raises(TypeError):
        d["a"] = 10
    with pytest.raises(TypeError):
        d["b"]["c"] = 20
    with pytest.raises(TypeError):
        d.a = 10
    with pytest.raises(TypeError):
        d.b.c = 20
