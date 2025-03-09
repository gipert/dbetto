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
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

__file_extensions__ = {"json": [".json"], "yaml": [".yaml", ".yml"]}

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


# values without a decimal point e.g. 5e-6 will be read as a str and not a float
# this function will ensure that all floats are represented as floats
def float_representer(dumper, value):
    if str(value) == "nan":
        return dumper.represent_scalar("tag:yaml.org,2002:float", ".nan")
    if str(value) == "inf":
        return dumper.represent_scalar("tag:yaml.org,2002:float", ".inf")
    if str(value) == "-inf":
        return dumper.represent_scalar("tag:yaml.org,2002:float", "-.inf")
    if "." not in str(value):
        return dumper.represent_scalar("tag:yaml.org,2002:float", f"{value:.1e}")
    return dumper.represent_scalar("tag:yaml.org,2002:float", str(value))


yaml.add_representer(float, float_representer)


def load_dict(fname: str, ftype: str | None = None) -> dict:
    """Load a text file as a Python dict."""
    fname = Path(fname)

    # determine file type from extension
    if ftype is None:
        for _ftype, exts in __file_extensions__.items():
            if fname.suffix in exts:
                ftype = _ftype

    msg = f"reading {ftype} dict from: {fname}"
    log.debug(msg)

    with fname.open(encoding="utf-8") as f:
        if ftype == "json":
            return json.load(f)
        if ftype == "yaml":
            return yaml.load(f, Loader=Loader)

        msg = f"unsupported file format {ftype}"
        raise NotImplementedError(msg)


def write_dict(fname: str, obj: dict, ftype: str | None = None) -> dict:
    """Load a text file as a Python dict."""
    fname = Path(fname)

    # determine file type from extension
    if ftype is None:
        for _ftype, exts in __file_extensions__.items():
            if fname.suffix in exts:
                ftype = _ftype

    msg = f"writing {ftype} dict to: {fname}"
    log.debug(msg)

    with fname.open("w", encoding="utf-8") as f:
        if ftype == "json":
            separators = (",", ":")
            indent = 2
            json.dump(obj, f, indent=indent, separators=separators)
            f.write("\n")
        elif ftype == "yaml":
            yaml.dump(obj, f, sort_keys=False)

        else:
            msg = f"unsupported file format {ftype}"
            raise NotImplementedError(msg)
