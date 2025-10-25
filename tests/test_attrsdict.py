from __future__ import annotations

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
