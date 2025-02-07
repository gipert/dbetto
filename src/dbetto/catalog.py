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
import types
from collections import namedtuple
from pathlib import Path
from string import Template

from . import time, utils


class PropsStream:
    """Simple class to control loading of validity files"""

    @staticmethod
    def get(value):
        if isinstance(value, (str, Path)):
            return PropsStream.read_from(value)

        if isinstance(value, (collections.abc.Sequence, types.GeneratorType)):
            return value

        msg = f"Can't get PropsStream from value of type {type(value)}"
        raise ValueError(msg)

    @staticmethod
    def read_from(file_name):
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

    @staticmethod
    def get(value):
        if isinstance(value, Catalog):
            return value

        if isinstance(value, (str, Path)):
            return Catalog.read_from(value)

        msg = f"Can't get Catalog from value of type {type(value)}"
        raise ValueError(msg)

    @staticmethod
    def read_from(file_name):
        """Read from a valdiity file and build a Catalog object"""
        ext = Path(file_name).suffix
        entries = {}
        for props in PropsStream.get(file_name):
            timestamp = props["valid_from"]
            system = props.get("category", "all")
            if not isinstance(system, list):
                system = [system]
            file_key = props["apply"]
            for syst in system:
                if syst not in entries:
                    entries[syst] = []

                # support for legacy JSONL format
                if ext == "jsonl":
                    entries[system].append(
                        Catalog.Entry(time.unix_time(timestamp), file_key)
                    )

                else:
                    mode = props.get("mode", "append")
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

                    if time.unix_time(timestamp) in [
                        entry.valid_from for entry in entries[syst]
                    ]:
                        msg = f"Duplicate timestamp: {timestamp}, use reset mode instead with a single entry"
                        raise ValueError(msg)
                    entries[syst].append(Catalog.Entry(time.unix_time(timestamp), new))

        for system, value in entries.items():
            entries[system] = sorted(value, key=lambda entry: entry.valid_from)
        return Catalog(entries)

    def valid_for(self, timestamp, system="all", allow_none=False):
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
    def get_files(catalog_file, timestamp, category="all"):
        """Helper function to get the files for a given timestamp and category"""
        catalog = Catalog.read_from(catalog_file)
        return Catalog.valid_for(catalog, timestamp, category)


class Props:
    """Class to handle overwriting of dictionaries in cascade order"""

    @staticmethod
    def read_from(sources, subst_pathvar=False, trim_null=False):
        def read_impl(sources):
            if isinstance(sources, str):
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
