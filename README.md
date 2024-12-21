# 📂 dbetto

A tiny text-based database.

[![PyPI](https://img.shields.io/pypi/v/dbetto?logo=pypi)](https://pypi.org/project/dbetto/)
![GitHub tag (latest by date)](https://img.shields.io/github/v/tag/gipert/dbetto?logo=git)
[![GitHub Workflow Status](https://img.shields.io/github/checks-status/gipert/dbetto/main?label=main%20branch&logo=github)](https://github.com/gipert/dbetto/actions)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Codecov](https://img.shields.io/codecov/c/github/gipert/dbetto?logo=codecov)](https://app.codecov.io/gh/gipert/dbetto)
![GitHub issues](https://img.shields.io/github/issues/gipert/dbetto?logo=github)
![GitHub pull requests](https://img.shields.io/github/issues-pr/gipert/dbetto?logo=github)
![License](https://img.shields.io/github/license/gipert/dbetto)
[![Read the Docs](https://img.shields.io/readthedocs/dbetto?logo=readthedocs)](https://dbetto.readthedocs.io)

_dbetto_ is a lightweight Python library that enables seamless access and
management of **text-based databases** (JSON/YAML) scattered across your
filesystem. Whether you're handling nested data structures or querying data by
validity periods, _dbetto_ simplifies it all with an intuitive interface.

The project was originally developed to efficiently manage metadata for the
LEGEND experiment.

### Key Features

- Access JSON/YAML files like a Python dictionary
- Attribute-style access with tab-completion for rapid query
- Time-sensitive data querying with validity rules
- Data remapping and grouping functionalities

## Showcase

Install from PyPI:

```bash
pip install dbetto
```

Access data arbitrarily structured as JSON or YAML files:

```python
>>> from dbetto import TextDB
>>> db = TextDB("/path/to/data/folder")
>>> db["dir1"]["file1.json"]["value"]
1
>>> db.dir1.file1.value
1
```

Query data valid on a given time period:

```python
>>> from datetime import datetime
>>> db.on(datetime(2023, 1, 10, 9, 53, 0)).value
3
```

Map data according to alternative keys:

```python
>>> chmap = db["detectors.yaml"]
>>> chmap.V05266A
{'name': 'V05266A',
 'location': {'string': 1, 'position': 4},
 'daq': {'crate': 0,
  'rawid': 1104003,
 ...
>>> chmap.map("daq.rawid")[1104003]
{'name': 'V05266A',
 'location': {'string': 1, 'position': 4},
 'daq': {'crate': 0,
  'rawid': 1104003}}
>>> grouped = chmap.group("electronics.cc4.id")["C3"]
>>> grouped.map("name").keys()
dict_keys(['V02160A', 'V02160B', 'V05261B', 'V05266A', 'V05266B', 'V05268B', 'V05612A'])
```

Have a look at the [docs](https://dbetto.readthedocs.io) for more!
