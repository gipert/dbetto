from __future__ import annotations

import importlib.metadata

import dbetto as m


def test_version():
    assert importlib.metadata.version("dbetto") == m.__version__
