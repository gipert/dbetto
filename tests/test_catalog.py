from __future__ import annotations

import logging
import math
from datetime import datetime
from pathlib import Path

import pytest

from dbetto import utils
from dbetto.catalog import Catalog, PropsStream
from dbetto.time import datetime_to_str, str_to_datetime, unix_time

log = logging.getLogger(__name__)

testolddb = Path(__file__).parent / "test_validities"


def test_to_datetime():
    assert str_to_datetime("20230501T205951Z") == datetime(2023, 5, 1, 20, 59, 51)


def test_from_datetime():
    assert datetime_to_str(datetime(2023, 5, 1, 20, 59, 51)) == "20230501T205951Z"
    assert (
        datetime_to_str(datetime.timestamp(datetime(2023, 5, 1, 20, 59, 51)))
        == "20230501T205951Z"
    )


def test_unix_time():
    now = datetime.now()
    assert unix_time(datetime_to_str(datetime.now())) == math.floor(now.timestamp())
    assert unix_time(now) == now.timestamp()
    with pytest.raises(ValueError):
        unix_time(21)


def test_propsstream():
    with pytest.raises(ValueError):
        PropsStream.get(None)

    def test_generator():
        yield {"apply": ["file1.json"], "valid_from": "20220628T221955Z"}
        yield {"apply": ["file2.json"], "valid_from": "20220629T221955Z"}

    gen = PropsStream.get(test_generator())
    assert gen.__next__() == {"apply": ["file1.json"], "valid_from": "20220628T221955Z"}


def test_catalog_build():
    catalog = [
        {"apply": ["file1.json"], "valid_from": "20220628T221955Z"},
        {"apply": "file2.json", "valid_from": "20220629T221955Z"},
    ]
    catalog = Catalog.get(catalog)
    assert catalog.valid_for("20220628T221955Z") == ["file1.json"]
    assert catalog.valid_for("20220629T221955Z") == ["file1.json", "file2.json"]
    catalog = (
        {"apply": ["file1.json"], "valid_from": "20220628T221955Z"},
        {"apply": ["file2.json"], "valid_from": "20220629T221955Z"},
    )
    catalog = Catalog.get(catalog)
    assert catalog.valid_for("20220628T221955Z") == ["file1.json"]
    assert catalog.valid_for("20220629T221955Z") == ["file1.json", "file2.json"]
    # test catalog already as catalog
    catalog = Catalog.get(catalog)
    assert catalog.valid_for("20220628T221955Z") == ["file1.json"]
    # invalid type
    with pytest.raises(ValueError):
        catalog = Catalog.get({})
    # replace too many entries
    catalog = (
        {"apply": ["file1.json"], "valid_from": "20220628T221955Z"},
        {
            "apply": ["file2.json", "file3.json", "file4.json"],
            "valid_from": "20220629T221955Z",
            "mode": "replace",
        },
    )
    with pytest.raises(ValueError):
        catalog = Catalog.get(catalog)
    # invalid mode
    catalog = [
        {"apply": ["file1.json"], "valid_from": "20220628T221955Z"},
        {
            "apply": ["file2.json", "file3.json"],
            "valid_from": "20220629T221955Z",
            "mode": "test",
        },
    ]
    with pytest.raises(ValueError):
        catalog = Catalog.get(catalog)
    # multiple entries with same timestamp
    catalog = (
        {"apply": ["file1.json"], "valid_from": "20220628T221955Z"},
        {"apply": ["file2.json"], "valid_from": "20220628T221955Z"},
    )
    with pytest.raises(ValueError):
        catalog = Catalog.get(catalog)
    # multiple entries with same timestamp warning suppressed
    catalog = Catalog.build_catalog(
        PropsStream.get(catalog), suppress_duplicate_check=True
    )
    assert catalog.valid_for("20220628T221955Z") == ["file1.json", "file2.json"]


def test_catalog_valid_for():
    catalog = (
        {"apply": ["file1.json"], "valid_from": "20220628T221955Z"},
        {"apply": ["file2.json"], "valid_from": "20220629T221955Z"},
    )
    catalog = Catalog.get(catalog)
    # test system falls back to default
    assert catalog.valid_for("20220628T221955Z", system="test") == ["file1.json"]
    # test allow none
    assert catalog.valid_for("20220627T233502Z", allow_none=True) is None
    # no entries for timestamp
    with pytest.raises(RuntimeError):
        catalog.valid_for("20220627T233502Z")
    catalog = (
        {"apply": ["file1.json"], "valid_from": "20220628T221955Z", "category": "test"},
        {"apply": ["file2.json"], "valid_from": "20220629T221955Z", "category": "test"},
    )
    catalog = Catalog.get(catalog)
    # test system not present
    with pytest.raises(RuntimeError):
        catalog.valid_for("20220628T221955Z", system="test2")
    # test system not present and allow_none
    assert (
        catalog.valid_for("20220628T221955Z", system="test2", allow_none=True) is None
    )
    # test fallback to default for earlier timestamps
    catalog = (
        {"apply": ["file1.json"], "valid_from": "20220628T221955Z"},
        {"apply": ["file2.json"], "valid_from": "20220630T221955Z", "category": "test"},
    )
    catalog = Catalog.get(catalog)
    assert catalog.valid_for("20220629T221955Z", system="test") == ["file1.json"]


def test_catalog_write(tmpdir):
    catalog = (
        {"apply": ["file1.json"], "valid_from": "20220628T221955Z"},
        {"apply": ["file2.json"], "valid_from": "20220629T221955Z"},
    )
    # test jsonl format
    catalog = Catalog.get(catalog)
    assert catalog.valid_for("20220628T221955Z") == ["file1.json"]
    assert catalog.valid_for("20220629T221955Z") == ["file1.json", "file2.json"]
    catalog.write_to(Path(tmpdir) / "test.jsonl")
    catalog = Catalog.get(Path(tmpdir) / "test.jsonl")
    assert catalog.valid_for("20220628T221955Z") == ["file1.json"]
    assert catalog.valid_for("20220629T221955Z") == ["file1.json", "file2.json"]
    # test yaml format
    catalog = (
        {"apply": ["file1.json"], "valid_from": "20220101T221955Z"},
        {"apply": ["file2.json"], "valid_from": "20220102T221955Z"},
        {"apply": ["file2.json"], "valid_from": "20220103T221955Z", "mode": "remove"},
        {
            "apply": ["file1.json", "file2.json"],
            "valid_from": "20220104T221955Z",
            "mode": "replace",
        },
        {
            "apply": ["file1.json", "file2.json", "file3.json"],
            "valid_from": "20220105T221955Z",
            "mode": "reset",
        },
        {
            "apply": ["file3.json", "file4.json"],
            "valid_from": "20220106T221955Z",
            "mode": "replace",
        },
    )
    catalog = Catalog.get(catalog)
    catalog.write_to(Path(tmpdir) / "test.yaml")
    catalog = Catalog.get(Path(tmpdir) / "test.yaml")
    assert catalog.valid_for("20220101T221955Z") == ["file1.json"]
    assert catalog.valid_for("20220102T221955Z") == ["file1.json", "file2.json"]
    # test yaml formatting
    dic = utils.load_dict(Path(tmpdir) / "test.yaml")
    assert "mode" not in dic[0]
    assert dic[1]["mode"] == "append"
    assert dic[1]["apply"] == ["file2.json"]
    assert dic[2]["mode"] == "remove"
    assert dic[2]["apply"] == ["file2.json"]
    assert dic[3]["mode"] == "reset"
    assert dic[3]["apply"] == ["file2.json"]
    assert dic[5]["mode"] == "replace"
    assert dic[5]["apply"] == ["file3.json", "file4.json"]


def test_validity_files():
    # test jsonl duplicates
    cat = Catalog.read_from(testolddb / "validity_duplicates.jsonl")
    assert cat.valid_for("20230101T000000Z") == ["file2.json"]
    # test yaml duplicates
    with pytest.raises(ValueError):
        Catalog.read_from(testolddb / "validity_duplicates.yaml")
    # test yaml default to append
    cat = Catalog.read_from(testolddb / "validity_append.yaml")
    assert cat.valid_for("20230101T000000Z") == ["file1.json"]
    assert cat.valid_for("20230102T000000Z") == ["file1.json", "file2.json"]
    # test jsonl default to reset
    cat = Catalog.read_from(testolddb / "validity_reset.jsonl")
    assert cat.valid_for("20230101T000000Z") == ["file1.json"]
    assert cat.valid_for("20230102T000000Z") == ["file2.json"]
