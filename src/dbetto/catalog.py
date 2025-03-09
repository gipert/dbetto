# Copyright (C) 2015 Oliver Schulz <oschulz@mpp.mpg.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import bisect
import collections
import copy
import json
import logging
import types
from collections import namedtuple
from collections.abc import Generator
from pathlib import Path
from string import Template

from . import time, utils

log = logging.getLogger(__name__)


class PropsStream:
    """Simple class to control loading of validity files"""

    @staticmethod
    def get(value: str | Path | list | Generator) -> Generator[dict, None, None]:
        if isinstance(value, (str, Path)):
            return PropsStream.read_from(value)
        if isinstance(value, collections.abc.Sequence):
            return PropsStream.yield_list(value)
        if isinstance(value, types.GeneratorType):
            return value
        msg = f"Can't get PropsStream from value of type {type(value)}"
        raise ValueError(msg)

    @staticmethod
    def yield_list(value: list) -> Generator[dict, None, None]:
        yield from value

    @staticmethod
    def read_from(file_name: str | Path) -> Generator[dict, None, None]:
        ext = Path(file_name).suffix
        # support for legacy JSONL format
        if ext == ".jsonl":
            with Path(file_name).open(encoding="utf-8") as file:
                for json_str in file:
                    yield json.loads(json_str)

        else:
            yield from sorted(
                utils.load_dict(file_name),
                key=lambda item: time.unix_time(item["valid_from"]),
            )


class Catalog(namedtuple("Catalog", ["entries"])):
    """Implementation of the `YAML metadata validity specification <https://legend-exp.github.io/legend-data-format-specs/dev/metadata/#Specifying-metadata-validity-in-time-(and-system)>`_.

    The legacy JSONL specification is also supported.
    """

    __slots__ = ()

    class Entry(namedtuple("Entry", ["valid_from", "file"])):
        """An entry in the validity file."""

        __slots__ = ()

        def asdict(self):
            return {"valid_from": self.valid_from, "apply": self.file}

        def save_format(self, system: str = "all"):
            dic = self.asdict()
            dic["category"] = system
            dic["valid_from"] = time.datetime_to_str(dic["valid_from"])
            return dic

    @staticmethod
    def get(value):
        if isinstance(value, Catalog):
            return value

        if isinstance(value, (str, Path)):
            return Catalog.read_from(value)

        if isinstance(value, collections.abc.Sequence):
            return Catalog.build_catalog(value)

        msg = f"Can't get Catalog from value of type {type(value)}"
        raise ValueError(msg)

    @staticmethod
    def build_catalog(
        propstream: str | Path | list | Generator,
        mode_default: str = "append",
        suppress_duplicate_check: bool = False,
    ) -> Catalog:
        """Build a Catalog object from a validity file/stream"""
        entries = {}
        for props in PropsStream.get(propstream):
            timestamp = props["valid_from"]
            system = props.get("category", "all")
            if not isinstance(system, list):
                system = [system]
            file_key = props["apply"]
            if isinstance(file_key, str):
                file_key = [file_key]
            for syst in system:
                if syst not in entries:
                    entries[syst] = []
                mode = props.get("mode", mode_default)
                mode = "reset" if len(entries[syst]) == 0 else mode
                if mode == "reset":
                    new = file_key
                elif mode == "append":
                    new = entries[syst][-1].file.copy() + file_key
                elif mode == "remove":
                    new = entries[syst][-1].file.copy()
                    for file in file_key:
                        new.remove(file)
                elif mode == "replace":
                    new = entries[syst][-1].file.copy()
                    if len(file_key) != 2:
                        msg = f"Invalid number of elements in replace mode: {len(file_key)}"
                        raise ValueError(msg)
                    new.remove(file_key[0])
                    new += [file_key[1]]
                else:
                    msg = f"Unknown mode for {timestamp}"
                    raise ValueError(msg)

                if (
                    time.unix_time(timestamp)
                    in [entry.valid_from for entry in entries[syst]]
                    and suppress_duplicate_check is False
                ):
                    msg = f"Duplicate timestamp: {timestamp}, use reset mode instead with a single entry"
                    raise ValueError(msg)
                entries[syst].append(Catalog.Entry(time.unix_time(timestamp), new))
        for system, value in entries.items():
            entries[system] = sorted(value, key=lambda entry: entry.valid_from)
        return Catalog(entries)

    @staticmethod
    def read_from(file_name: str | Path) -> Catalog:
        """Read from a validity file and build a Catalog object"""
        ext = Path(file_name).suffix
        return Catalog.build_catalog(
            file_name,
            mode_default="reset" if ext == ".jsonl" else "append",
            suppress_duplicate_check=bool(ext == ".jsonl"),
        )  # difference between old jsonl and new yaml is just the change of default mode from append to reset

    def valid_for(
        self, timestamp: str, system: str = "all", allow_none: bool = False
    ) -> list:
        """Get the valid entries for a given timestamp and system"""
        if system in self.entries:
            valid_from = [entry.valid_from for entry in self.entries[system]]
            pos = bisect.bisect_right(valid_from, time.unix_time(timestamp))
            if pos > 0:
                return self.entries[system][pos - 1].file

            if system != "all":
                return self.valid_for(timestamp, system="all", allow_none=allow_none)

            if allow_none:
                return None

            msg = f"No valid entries found for timestamp: {timestamp}, system: {system}"
            raise RuntimeError(msg)

        if system != "all":
            return self.valid_for(timestamp, system="all", allow_none=allow_none)

        if allow_none:
            return None

        msg = f"No entries found for system: {system}"
        raise RuntimeError(msg)

    @staticmethod
    def get_files(
        catalog_file: str | Path, timestamp: str, category: str = "all"
    ) -> list:
        """Helper function to get the files for a given timestamp and category"""
        catalog = Catalog.read_from(catalog_file)
        return catalog.valid_for(timestamp, category)

    def get_dict_format(self) -> list:
        write_list = []
        for system, entries in self.entries.items():
            for entry in entries:
                write_list.append(entry.save_format(system))
        current_files = []
        for entry in write_list:
            files = entry["apply"].copy()
            if len(current_files) > 0:
                set1 = set(current_files.copy())
                set2 = set(files)
                new_files = set2 - set1
                removed_files = set1 - set2

                if len(new_files) > 0 and len(removed_files) == 0:
                    entry["apply"] = list(new_files)
                    entry["mode"] = "append"
                elif len(new_files) == 0 and len(removed_files) > 0:
                    entry["apply"] = list(removed_files)
                    entry["mode"] = "remove"
                elif len(new_files) == 1 and len(removed_files) == 1 and len(files) > 1:
                    entry["apply"] = list(removed_files) + list(new_files)
                    entry["mode"] = "replace"
                else:
                    entry["mode"] = "reset"
            if entry["category"] == "all":
                entry.pop("category")
            current_files = files
        return write_list

    def write_to(self, file_name: str | Path) -> None:
        """Write a Catalog object to a validity file"""
        ext = Path(file_name).suffix
        if ext == ".jsonl":
            with Path(file_name).open("w", encoding="utf-8") as file:
                for system, entries in self.entries.items():
                    for entry in entries:
                        file.write(json.dumps(entry.save_format(system)) + "\n")
        else:
            utils.write_dict(file_name, self.get_dict_format())


class Props:
    """Class to handle overwriting of dictionaries in cascade order"""

    @staticmethod
    def read_from(sources, subst_pathvar=False, trim_null=False):
        def read_impl(sources):
            if isinstance(sources, (str, Path)):
                file_name = sources
                result = utils.load_dict(file_name)
                if subst_pathvar:
                    Props.subst_vars(
                        result,
                        var_values={"_": Path(file_name).parent},
                        ignore_missing=True,
                    )
                return result

            if isinstance(sources, list):
                result = {}
                for p in map(read_impl, sources):
                    Props.add_to(result, p)
                return result

            msg = f"Can't run Props.read_from on sources-value of type {type(sources)}"
            raise ValueError(msg)

        result = read_impl(sources)
        if trim_null:
            Props.trim_null(result)
        return result

    @staticmethod
    def write_to(file_name, obj, ftype: str | None = None):
        utils.write_dict(file_name, obj, ftype)

    @staticmethod
    def add_to(props_a, props_b):
        a = props_a
        b = props_b

        for key in b:
            if key in a:
                if isinstance(a[key], dict) and isinstance(b[key], dict):
                    Props.add_to(a[key], b[key])
                elif a[key] != b[key]:
                    a[key] = copy.deepcopy(b[key])
            else:
                a[key] = copy.deepcopy(b[key])

    @staticmethod
    def trim_null(props_a):
        a = props_a

        for key in list(a.keys()):
            if isinstance(a[key], dict):
                Props.trim_null(a[key])
            elif a[key] is None:
                del a[key]

    @staticmethod
    def subst_vars(props, var_values=None, ignore_missing=False):
        if not var_values:
            var_values = {}

        for key in props:
            value = props[key]
            if isinstance(value, str) and "$" in value:
                new_value = None
                if ignore_missing:
                    new_value = Template(value).safe_substitute(var_values)
                else:
                    new_value = Template(value).substitute(var_values)

                if new_value != value:
                    props[key] = new_value
            elif isinstance(value, list):
                new_values = []
                for val in value:
                    if isinstance(val, str) and "$" in val:
                        if ignore_missing:
                            new_value = Template(val).safe_substitute(var_values)
                        else:
                            new_value = Template(val).substitute(var_values)
                    else:
                        new_value = val
                    new_values.append(new_value)
                if new_values != value:
                    props[key] = new_values
            elif isinstance(value, dict):
                Props.subst_vars(value, var_values, ignore_missing)
