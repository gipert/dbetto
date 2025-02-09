from __future__ import annotations

import logging
import math
from datetime import datetime
from pathlib import Path

import pytest

from dbetto.catalog import Catalog
from dbetto.time import datetime_to_str, str_to_datetime, unix_time

log = logging.getLogger(__name__)


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


def test_catalog_build_list():
    catalog = [
        {"apply": ["file1.json"], "valid_from": "20220628T221955Z"},
        {"apply": ["file2.json"], "valid_from": "20220629T221955Z"},
    ]
    catalog = Catalog.get(catalog)
    assert catalog.valid_for("20220628T221955Z") == ["file1.json"]
    assert catalog.valid_for("20220629T221955Z") == ["file1.json", "file2.json"]


def test_catalog_build_tuple():
    catalog = (
        {"apply": ["file1.json"], "valid_from": "20220628T221955Z"},
        {"apply": ["file2.json"], "valid_from": "20220629T221955Z"},
    )
    catalog = Catalog.get(catalog)
    assert catalog.valid_for("20220628T221955Z") == ["file1.json"]
    assert catalog.valid_for("20220629T221955Z") == ["file1.json", "file2.json"]


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


def test_catalog_errors():
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
    catalog = {
        "apply": ["file1.json"],
        "valid_from": "20220628T221955Z",
        "mode": "test",
    }
    with pytest.raises(ValueError):
        catalog = Catalog.get(catalog)
    # multiple entries with same timestam
    catalog = (
        {"apply": ["file1.json"], "valid_from": "20220628T221955Z"},
        {"apply": ["file2.json"], "valid_from": "20220628T221955Z"},
    )
    with pytest.raises(ValueError):
        catalog = Catalog.get(catalog)


def test_catalog_write(tmpdir):
    catalog = (
        {"apply": ["file1.json"], "valid_from": "20220628T221955Z"},
        {"apply": ["file2.json"], "valid_from": "20220629T221955Z"},
    )
    catalog = Catalog.get(catalog)
    assert catalog.valid_for("20220628T221955Z") == ["file1.json"]
    assert catalog.valid_for("20220629T221955Z") == ["file1.json", "file2.json"]
    catalog.write_to(Path(tmpdir) / "test.jsonl")
    catalog = Catalog.get(Path(tmpdir) / "test.jsonl")
    assert catalog.valid_for("20220628T221955Z") == ["file1.json"]
    assert catalog.valid_for("20220629T221955Z") == ["file1.json", "file2.json"]
    catalog.write_to(Path(tmpdir) / "test.yaml")
    catalog = Catalog.get(Path(tmpdir) / "test.yaml")
    log.debug(catalog.valid_for("20220629T221955Z"))
    assert catalog.valid_for("20220628T221955Z") == ["file1.json"]
    assert catalog.valid_for("20220629T221955Z") == ["file1.json", "file2.json"]
