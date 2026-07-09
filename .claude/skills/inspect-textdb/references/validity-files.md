# Validity files and the Catalog API

A validity file maps time points (and optionally data-taking "systems") to the
set of metadata files that are in force from then on. dbetto reads it to answer
"which files apply at timestamp T?". `TextDB.on()` is the high-level front door;
`Catalog` is the underlying machinery you can use standalone.

Official spec:
https://legend-exp.github.io/legend-data-format-specs/dev/metadata/#Specifying-metadata-validity-in-time-(and-system)

## File format (YAML/JSON)

A list of entries, each with:

- `valid_from` (required): timestamp string `YYYYmmddTHHMMSSZ` (UTC).
- `apply` (required): a filename or list of filenames, relative to the directory
  holding the validity file.
- `category` (optional, default `all`): the system/category this entry applies
  to, a string or list of strings (e.g. `all`, `phy`, `cal`, `lar`).
- `mode` (optional): how this entry's `apply` combines with the running set for
  its category. Default is `append` for YAML/JSON.

```yaml
- valid_from: 20230101T000000Z
  category: all
  apply:
    - file1.json # reset (first entry is always a reset)

- valid_from: 20230102T000000Z
  category: all
  mode: append
  apply:
    - file2.json # now {file1, file2} are in force
```

## Modes

The catalog keeps a running file list per category, ordered by `valid_from`.
Each entry transforms the previous list:

- `reset`: the new list _is_ `apply`. The first entry of a category is always
  treated as a reset regardless of the written mode.
- `append`: previous list + `apply`.
- `remove`: previous list with every filename in `apply` removed.
- `replace`: `apply` must be exactly `[old, new]`; swaps `old` for `new`.

Resolution at timestamp T (`Catalog.valid_for`) takes the most recent entry
whose `valid_from <= T` via a bisect. If the requested category has no matching
entry, it falls back to the `all` category; if still nothing, it raises unless
`allow_none=True`. A category that has its own entries is resolved from those
alone (not merged with `all`).

Duplicate `valid_from` values within a category raise (use a single `reset`
entry instead) unless duplicate checking is suppressed.

## Legacy JSONL

The old format is one JSON object per line (`.jsonl`). Two behavioral
differences are baked in for backward compatibility:

- default `mode` is `reset` (not `append`);
- duplicate-timestamp checking is suppressed.

```jsonl
{"valid_from":"20220628T221955Z","category":"all","apply":["file7.json"]}
{"valid_from":"20220629T221955Z","category":"all","apply":["file8.json"]}
```

## Catalog API (no TextDB needed)

```python
from dbetto.catalog import Catalog

cat = Catalog.read_from("validity.yaml")  # build from a file
cat.valid_for("20230102T120000Z")  # -> list of filenames for 'all'
cat.valid_for("20230102T120000Z", category="cal", allow_none=True)
Catalog.get_files("validity.yaml", "20230102T120000Z", "all")  # one-shot helper

cat.write_to("out.yaml")  # serialize back; re-derives compact modes
```

- `Catalog.read_from(path)` picks the right defaults from the extension
  (`.jsonl` -> reset/suppress-duplicates; otherwise append).
- `Catalog.build_catalog(stream, mode_default=..., suppress_duplicate_check=...)`
  builds from an already-loaded list/generator instead of a path.
- `valid_for(timestamp, category="all", allow_none=False)` returns the in-force
  filename list; timestamp is a string or `datetime`. (`system=` is a deprecated
  alias for `category`.)
- `write_to` collapses the internal per-category entries back into the compact
  append/remove/replace/reset representation and writes YAML/JSON (or JSONL if
  the target extension is `.jsonl`).

## PropsStream

`PropsStream.get(value)` normalizes a validity source (path, list, or generator)
into a generator of entry dicts, sorting file-backed sources by `valid_from`.
You rarely call it directly; `Catalog.build_catalog` uses it.

## Debugging "wrong files at timestamp T"

1. Confirm which validity file `.on()` picked: it looks for `validity` +
   `.yaml/.yml/.json/.jsonl` in the directory and warns if several exist.
2. Rebuild the catalog explicitly and inspect: `Catalog.read_from(path).entries`
   is a `{category: [Entry(valid_from_unix, [files]), ...]}` dict, sorted in
   time.
3. Remember category fallback: a query for `cal` that finds no `cal` entries
   silently uses `all`.
4. Check mode accumulation: an unexpected file usually means an earlier `append`
   left it in the running set; a `remove`/`replace` may be needed.
