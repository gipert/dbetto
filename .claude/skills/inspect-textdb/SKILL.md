---
name: inspect-textdb
description: >-
  Load, query, and verify text-based databases (JSON/YAML files scattered across
  a directory tree, plus time-validity files) with the dbetto Python API:
  TextDB, AttrsDict, Catalog, Props, and the time utilities. Use this whenever
  someone points at a folder of JSON/YAML data or config and wants to read a
  value, walk the tree, resolve which files are valid at a given timestamp,
  remap/group entries by an inner key (e.g. a channel/detector map), merge
  cascading property files, or confirm that an edit to the data or to a
  validity.* file produces the intended behavior. Reach for it even when the
  user does not say "dbetto" by name: a data/config directory, a validity.yaml,
  channel maps, LEGEND metadata, "what applies on <date>", "did my validity
  change work", or attribute-style access to nested JSON/YAML are all triggers.
---

# Inspecting a dbetto text database

dbetto treats a directory of JSON/YAML files as a database. Directories, files,
and the keys inside a file all sit at the same semantic level, so you can walk
from the top folder down to a leaf value with one uniform syntax. In memory
every mapping becomes an `AttrsDict` (a `dict` you can also access with dot
notation). This skill is the map of what the API can do and which entry point
fits each question, including how to check that a change to the data behaves.

## Orient first

Before writing code, look at the data. The right API call depends on the shape
on disk, so check it:

- `find <dir> -maxdepth 2 -name '*.json' -o -name '*.yaml' -o -name '*.yml'` to
  see the file layout.
- Look for a `validity.yaml` / `validity.json` / `validity.jsonl` in a
  directory: its presence means the data is time-versioned and you should query
  it with `.on(timestamp)` rather than reading a fixed file.
- Peek at one file to learn whether the top level is a mapping (`{...}`) or a
  list (`[...]`), and whether entries carry an inner id worth remapping on (e.g.
  `daq.rawid`, `name`).

Everything is importable from the top package:

```python
from dbetto import TextDB, AttrsDict, Props, load_dict, load_attrs_dict, str_to_datetime
```

## Load a database

```python
from dbetto import TextDB

db = TextDB("/path/to/data")  # scans the tree immediately
```

- `lazy=True` skips the initial filesystem scan and caches files as you touch
  them. Cheap for huge trees, but `.map()`, `.group()`, iteration, and `.keys()`
  need a populated store, so call `db.scan()` first if you use them.
  `lazy="auto"` is lazy except in an interactive session.
- `hidden=True` includes dot-files/dot-dirs (ignored by default).
- To read a single file without a whole database: `load_dict(path)` returns a
  plain `dict`/`list`; `load_attrs_dict(path)` returns an `AttrsDict`. Both
  infer JSON vs YAML from the extension.

## Access files and values

Directories resolve to nested `TextDB` objects; files resolve to `AttrsDict` (or
a `list`). The extension is optional and path-style keys work:

```python
db["dir1"]["file1.json"]  # dict-style, explicit extension
db["dir1"]["file1"]  # extension omitted
db["dir1/file1"]  # filesystem-path key
db.dir1.file1.value  # attribute-style (tab-completes in IPython)
```

Attribute access only works for keys that are valid Python identifiers; for
anything else (dashes, leading digits, dots) use `db["odd-key"]`. Missing keys
raise `AttributeError` / `FileNotFoundError` / `ValueError`, so let those
surface rather than guessing at names.

A useful convenience inside data files: the string `$_` expands to the absolute
path of the directory containing the file when the file is loaded, so entries
can reference sibling paths.

## Query by time validity

If a directory holds a `validity.*` file, `db.on()` returns the merged content
of every file that is in force at a timestamp:

```python
from datetime import datetime

db.on(datetime(2023, 1, 10, 9, 53, 0)).value  # datetime object
db.on("20230110T095300Z").value  # YYYYmmddTHHMMSSZ string
db.on("20230110T095300Z", category="cal")  # restrict to a category/system
db.on("20230110T095300Z", pattern=r"geds/.*")  # keep only matching filenames
```

The result is a read-only `AttrsDict` built by cascading the applicable files in
order (later files override earlier keys). Timestamps are treated as UTC. If you
need a `datetime` from the string form, use `str_to_datetime(...)`.

The `category` argument selects a data-taking category (the `category` field in
the validity file, e.g. `phy`, `cal`, `lar`); a category with no entries of its
own falls back to the `all` entries, and a category that _does_ have its own
entries is resolved from those alone (it is not merged with `all`). Note the
naming: the validity-file key, the `.on()`/`.valid_for()` argument, and
`Catalog.get_files` all use `category`. (`system=` is still accepted as a
deprecated alias for `category` and emits a `DeprecationWarning`.)

The validity-file format (entries with `valid_from`, `category`, `apply`, and
`mode` = append/remove/replace/reset), the legacy JSONL variant, and the
lower-level `Catalog` API (`Catalog.read_from`, `.valid_for`,
`Catalog.get_files`) are documented in
[references/validity-files.md](references/validity-files.md). Read it whenever
you need to author a validity file, debug why a timestamp resolves to the wrong
files, or work with the catalog without a `TextDB`.

## Remap and group entries

When a file (or directory) maps arbitrary keys to records that each carry a
meaningful inner id, `.map()` re-keys by that id and `.group()` buckets by a
non-unique one. Both accept dotted paths to reach nested ids.

```python
chmap = db["channelmap.yaml"]  # {name -> record}
chmap.map("daq.rawid")[1104003]  # re-key by the DAQ id (must be unique)
chmap.group("electronics.cc4.id")["C3"]  # bucket detectors sharing a card
chmap.group("electronics.cc4.id")["C3"].map("name").keys()  # chain them
```

`.map()` raises if the id is not unique; use `.group()` (or
`.map(label, unique=False)`) when duplicates are expected. Results are cached
and share the read-only flag of the source. `TextDB` forwards
`.map()`/`.group()` to its store, so `db.map(...)` works too (populate a lazy db
with `scan()` first).

## Merge cascading property files (Props)

`Props` handles layered config where later sources override earlier ones, key by
key and recursing into nested dicts:

```python
from dbetto import Props

merged = Props.read_from([base_path, override_path])  # list = cascade, last wins
Props.add_to(a, b)  # merge b onto a (b wins; insertion order of a preserved)
Props.subst_vars(d, var_values={"_": some_dir})  # expand $_ / $var templates
Props.trim_null(d)  # drop keys whose value is None
```

`read_from` takes `subst_pathvar=True` (expand `$_` to each file's parent dir)
and `trim_null=True`. On overlap, `props_b` wins but the original key order of
`props_a` is preserved, which matters when downstream steps reference earlier
keys by name.

## Verify a data or validity-file change

A common reason to reach for dbetto is to confirm that an edit to the data (a
value, a file added to `apply`, a new `valid_from`) actually changes what a
query returns, and only where intended. Load the data and exercise the query
directly rather than reasoning about the files by eye.

- **Reload after editing on disk.** `TextDB` caches each file as it reads it, so
  a live instance will not see your edit. Construct a fresh `TextDB(dir)`, or
  call `db.reset()` (re-scans if non-lazy), before re-querying.
- **Probe the boundaries.** For a validity change, resolve `.on()` at timestamps
  just before and just after each relevant `valid_from` and check that the file
  set / values flip exactly there and nowhere else:

  ```python
  db = TextDB(dir)
  before = db.on("20230101T235959Z")  # last second of the old regime
  after = db.on("20230102T000000Z")  # first second of the new one
  ```

- **Diff old vs new.** Resolve the same timestamps against the pre-change and
  post-change data (e.g. two git checkouts, or a copy of the folder) and compare
  `to_dict()` outputs to see precisely what moved, instead of trusting that only
  the intended keys changed.
- **Inspect the low-level resolution** when `.on()` surprises you:
  `Catalog.read_from(path).valid_for(ts, category)` returns just the filename
  list and `.entries` shows the fully expanded per-category timeline (see
  [references/validity-files.md](references/validity-files.md)). This isolates
  whether a wrong result comes from the validity logic or from the file
  contents.
- **Catch broken invariants.** If downstream code relies on `.map("some.id")`,
  run it after the edit: a newly duplicated id raises `RuntimeError`, which is
  exactly the regression you want to surface early.

For a check you will repeat, wrap these as assertions in a short script or a
pytest under `tests/`, so the expected behavior is captured rather than
eyeballed once.

## AttrsDict notes

- `d.to_dict()` returns a plain nested `dict`/`list` (handy for JSON dumps,
  diffing, or passing to code that does strict `type(x) is dict` checks).
- `.on()` results are read-only; mutating them raises. `deepcopy` first if you
  need to edit, rather than flipping `__readonly__` back.
- The same object may be returned for several timestamps when it is valid across
  all of them, so an in-place edit would leak across queries: copy first.

## Quick recipes

- "What is `X` in file `Y`?" -> `TextDB(dir).Y.X` (or `load_attrs_dict`).
- "Which files/values apply on `<date>`?" -> `TextDB(dir).on("<ts>")`.
- "Did my validity edit work?" -> reload `TextDB`, `.on()` straddling the
  `valid_from` boundary, compare `to_dict()` before/after.
- "Give me detector `1104003`'s record" -> `chmap.map("daq.rawid")[1104003]`.
- "All channels on card `C3`" -> `chmap.group("electronics.cc4.id")["C3"]`.
- "Layer these config files" -> `Props.read_from([...], trim_null=True)`.

When you have run a query, show the actual returned structure (or a trimmed view
via `to_dict()`); do not paraphrase values you have not printed.
