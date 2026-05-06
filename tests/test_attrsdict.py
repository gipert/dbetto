from __future__ import annotations

import logging
from copy import deepcopy

import pytest

from dbetto.attrsdict import AttrsDict


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


def test_readonly(caplog):
    d = AttrsDict({"a": 1, "b": {"c": 2}}, readonly=True)

    # d and any children should be read-only
    assert isinstance(d, AttrsDict)
    assert d.__readonly__
    assert isinstance(d.b, AttrsDict)
    assert d.b.__readonly__

    # TypeError raised when trying to modify read-only AttrsDict
    with pytest.raises(TypeError):
        d.a = 10
    with pytest.raises(TypeError):
        d.b.c = 20

    # deep copy should return writable copy
    d_copy = deepcopy(d)
    assert isinstance(d_copy, AttrsDict)
    assert not d_copy.__readonly__
    d_copy.a = 2
    d_copy.b.c = 3
    assert d_copy == {"a": 2, "b": {"c": 3}}

    # Test | and |=
    d_or = d | {"d": 4}
    assert isinstance(d_or, AttrsDict)
    assert d_or.__readonly__

    with pytest.raises(TypeError):
        d |= {"d": 4}

    # changing __readonly__ should log a warning and propagate to children
    with caplog.at_level(logging.WARNING):
        d.__readonly__ = False
    assert (
        "toggling AttrsDict from read-only to writable is not recommended; instead consider deepcopying"
        in caplog.text
    )
    assert not d.__readonly__
    assert not d.b.__readonly__

    # changing __readonly__ back to True should not log a warning and should propagate to children
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        d.__readonly__ = True
    assert caplog.text == ""
    assert d.__readonly__
    assert d.b.__readonly__

    # map should be read-only
    mapped = d.map("c")
    assert mapped.__readonly__
    assert mapped[2].__readonly__
