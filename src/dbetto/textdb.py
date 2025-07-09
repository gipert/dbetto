# Copyright (C) 2022 Luigi Pertoldi <gipert@pm.me>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import yaml

from . import utils
from .attrsdict import AttrsDict
from .catalog import Catalog, Props

log = logging.getLogger(__name__)


class TextDB:
    """A simple text file database.

    The database is represented on disk by a collection of text files
    arbitrarily scattered in a filesystem. Subdirectories are also
    :class:`.TextDB` objects. In memory, the database is represented as an
    :class:`~.attrsdict.AttrsDict`.

    Currently supported file formats are JSON and YAML.

    Tip
    ---
    For large databases, a basic "lazy" mode is available. In this case, no
    global scan of the filesystem is performed at initialization time. Once a
    file is queried, it is also cached in the internal store for faster access.
    Caution, this option is for advanced use (see warning message below).

    Warning
    -------
    A manual call to :meth:`scan` is needed before most class methods (e.g.
    iterating on the database files) can be properly used.

    Examples
    --------
    >>> from dbetto import TextDB
    >>> jdb = TextDB("path/to/dir")
    >>> jdb["file1.json"]  # is a dict
    >>> jdb["file1.yaml"]  # is a dict
    >>> jdb["file1"]  # also works
    >>> jdb["dir1"]  # TextDB instance
    >>> jdb["dir1"]["file1"]  # nested file
    >>> jdb["dir1/file1"]  # also works
    >>> jdb.dir1.file # keys can be accessed as attributes
    """

    def __init__(
        self, path: str | Path, lazy: str | bool = False, hidden: bool = False
    ) -> None:
        """Construct a :class:`.TextDB` object.

        Parameters
        ----------
        path
            path to the directory containing the database.
        lazy
            whether a database scan should be performed at initialization time.
            if ``auto``, be non-lazy only if working in a python interactive
            session.
        hidden
            ignore hidden (i.e. starting with ".") files of directories.
        """
        if isinstance(lazy, bool):
            self.__lazy__ = lazy
        elif lazy == "auto":
            self.__lazy__ = not hasattr(sys, "ps1")
        else:
            msg = f"unrecognized value {lazy=}"
            raise ValueError(msg)

        self.__hidden__ = hidden
        self.__path__ = Path(path).expanduser().resolve()

        if not self.__path__.is_dir():
            msg = "input path is not a valid directory"
            raise ValueError(msg)

        self.__store__ = AttrsDict()
        self.__ftypes__ = {"json", "yaml"}

        if not self.__lazy__:
            self.scan()

    @property
    def __extensions__(self) -> set:
        # determine list of supported file extensions
        return set().union(
            *[
                exts
                for ft, exts in utils.__file_extensions__.items()
                if ft in self.__ftypes__
            ]
        )

    def reset(self, rescan: bool = True) -> None:
        """Reset this database instance.

        Reinstantiates the internal :class:`~.attrsdict.AttrsDict` store and
        re-scans the database, if non-lazy. Useful if the database states
        changes at runtime.
        """
        self.__store__ = AttrsDict()

        if rescan and not self.__lazy__:
            self.scan()

    def scan(self, recursive: bool = True, subdir: str = ".") -> None:
        """Populate the database by walking the filesystem.

        Parameters
        ----------
        recursive
            if ``True``, recurse subdirectories.
        subdir
            restrict scan to path relative to the database location.
        """
        # recursive search or not?
        _fcn = self.__path__.rglob if recursive else self.__path__.glob
        # build file list
        flist = (
            p for p in _fcn(str(Path(subdir) / "*")) if p.suffix in self.__extensions__
        )

        for j in flist:
            try:
                self[j.with_suffix("")]
            except (json.JSONDecodeError, yaml.YAMLError, ValueError) as e:
                msg = f"could not scan file {j}, reason: {e!r}"
                log.warning(msg)

    def keys(self) -> list[str]:
        return self.__store__.keys()

    def items(self) -> Iterator[(str, TextDB | AttrsDict | list)]:
        return self.__store__.items()

    def on(
        self, timestamp: str | datetime, pattern: str | None = None, system: str = "all"
    ) -> AttrsDict | list:
        """Query database in `time[, file pattern, system]`.

        A (only one) valid validity file (YAML, JSON, JSONL and other file
        types supported) must exist in the directory to specify a validity
        mapping. This functionality relies on the :class:`.catalog.Catalog`
        class.

        The YAML specification is documented at `this link
        <https://legend-exp.github.io/legend-data-format-specs/dev/metadata/#Specifying-metadata-validity-in-time-(and-system)>`_.

        The special ``$_`` string is expanded to the directory containing the
        text files.

        Parameters
        ----------
        timestamp
            a :class:`~datetime.datetime` object or a string matching the
            pattern ``YYYYmmddTHHMMSSZ``.
        pattern
            query by filename pattern.
        system
            query only a data taking "system" (e.g. 'all', 'phy', 'cal', 'lar', ...)
        """
        _extensions = [*list(self.__extensions__), ".jsonl"]
        validity_file = None
        for ext in _extensions:
            candidate = self.__path__ / f"validity{ext}"
            if candidate.is_file():
                if validity_file is not None:
                    msg = (
                        "multiple supported validity files found, "
                        "will use the first on of {_extensions}"
                    )
                    log.warning(msg)
                    break
                validity_file = candidate

        if validity_file is None:
            msg = f"no validity.* file found in {self.__path__!s}"
            raise RuntimeError(msg)

        # parse validity file and return requested files
        file_list = Catalog.get_files(str(validity_file), timestamp, system)

        # select only files matching pattern, if specified
        if pattern is not None:
            c = re.compile(pattern)
            out_files = []
            for file in file_list:
                if c.match(file):
                    out_files.append(file)
            files = out_files
        else:
            files = file_list

        # sanitize
        if not isinstance(files, list):
            files = [files]

        # read files in and combine as necessary
        result = AttrsDict()

        for file in files:
            # absolute path
            file_abs = list(self.__path__.rglob(file))

            if not file_abs:
                msg = f"{file} not found in the database root path {self.__path__!s}"
                raise RuntimeError(msg)

            # combine dictionaries
            for f in file_abs:
                Props.add_to(result, self[f])

        # substitute $_ with path to the file
        Props.subst_vars(result, var_values={"_": self.__path__})

        return result

    def map(self, label: str, unique: bool = True) -> AttrsDict:
        """Remap dictionary according to a second unique `label`.

        See Also
        --------
        .attrsdict.AttrsDict.map

        Warning
        -------
        If the database is lazy, you must call :meth:`.scan` in advance to
        populate it, otherwise mappings cannot be created.
        """
        return self.__store__.map(label, unique=unique)

    def group(self, label: str) -> AttrsDict:
        """Group dictionary according to a second unique `label`.

        See Also
        --------
        .attrsdict.AttrsDict.group

        Warning
        -------
        If the database is lazy, you must call :meth:`.scan` in advance to
        populate it, otherwise groupings cannot be created.
        """
        return self.__store__.group(label)

    def __getitem__(self, item: str | Path) -> TextDB | AttrsDict | list | None:
        """Access files or directories in the database."""
        # resolve relative paths / links, but keep it relative to self.__path__
        item = Path(item)

        if item.is_absolute() and item.is_relative_to(self.__path__):
            item = item.expanduser().resolve().relative_to(self.__path__)
        elif not item.is_absolute():
            item = (
                (self.__path__ / item).expanduser().resolve().relative_to(self.__path__)
            )
        else:
            msg = f"{item} lies outside the database root path {self.__path__!s}"
            raise ValueError(msg)

        ext_list = "[" + "|".join(self.__extensions__) + "]"
        msg = f"parsing directory or file{ext_list}: {item}"
        log.debug(msg)

        # now call this very function recursively to walk the directories to the file
        db_ptr = self
        for d in item.parts[:-1]:
            db_ptr = db_ptr[d]
            # check if we encountered hidden directory (must skip)
            if not self.__hidden__ and db_ptr is None:
                return None

        # item_id should not contain any / at this point
        # store file names without extension
        item_id = item.stem
        # skip if object is already in the store
        if item_id not in db_ptr.__store__:
            obj = db_ptr.__path__ / item.name

            # do not consider hidden files
            if not self.__hidden__ and obj.name.startswith("."):
                return None

            # if directory, construct another TextDB object
            if obj.is_dir():
                db_ptr.__store__[item_id] = TextDB(obj, lazy=self.__lazy__)

            else:
                # try to attach an extension if file cannot be found
                # but check if there are multiple files that only differ in extension (unsupported)
                found = True
                if not obj.is_file():
                    found = False
                    for ext in self.__extensions__:
                        if obj.with_suffix(ext).is_file():
                            if found:
                                msg = "the database cannot contain files that differ only in the extension"
                                raise RuntimeError(msg)

                            obj = obj.with_suffix(ext)
                            found = True

                if not found:
                    msg = f"{obj.with_stem(ext_list)} is not a valid file or directory"
                    raise FileNotFoundError(msg)

                # if it's a valid file, construct an AttrsDict object
                loaded = utils.load_dict(obj)
                if isinstance(loaded, dict):
                    loaded = AttrsDict(loaded)
                    Props.subst_vars(loaded, var_values={"_": self.__path__})
                else:  # must be a list, check if there are dicts inside to convert
                    for i, el in enumerate(loaded):
                        if isinstance(el, dict):
                            loaded[i] = AttrsDict(el)
                            Props.subst_vars(loaded[i], var_values={"_": self.__path__})

                db_ptr.__store__[item_id] = loaded

            # set also an attribute, if possible
            if item_id.isidentifier():
                db_ptr.__setattr__(item_id, db_ptr.__store__[item_id])

        return db_ptr.__store__[item_id]

    def __getattr__(self, name: str) -> TextDB | AttrsDict | list:
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            try:
                return self.__getitem__(name)
            except AttributeError as exc:
                msg = f"file database does not contain '{name}'"
                raise AttributeError(msg) from exc

    # NOTE: self cannot stay a TextDB, since the class is characterized by a
    # (unique) root directory. What would be the root directory of the merged
    # TextDB?
    def __ior__(self, other: TextDB) -> AttrsDict:
        msg = "cannot merge TextDB in-place"
        raise TypeError(msg)

    # NOTE: returning a TextDB does not make much sense, see above
    def __or__(self, other: TextDB) -> AttrsDict:
        if isinstance(other, TextDB):
            return self.__store__ | other.__store__

        return self.__store__ | other

    def __contains__(self, value: str) -> bool:
        return self.__store__.__contains__(value)

    def __len__(self) -> int:
        return len(self.__store__)

    def __iter__(self) -> Iterator:
        return iter(self.__store__)

    def __str__(self) -> str:
        return str(self.__store__)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.__path__!s}')"
