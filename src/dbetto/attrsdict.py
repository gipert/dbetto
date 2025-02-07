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

import logging
from collections.abc import Hashable
from typing import Any

log = logging.getLogger(__name__)


class AttrsDict(dict):
    """Access dictionary items as attributes.

    Examples
    --------
    >>> d = AttrsDict({"key1": {"key2": 1}})
    >>> d.key1.key2
    1
    >>> d1 = AttrsDict()
    >>> d1["a"] = 1
    >>> d1.a
    1
    """

    def __init__(self, value: dict | None = None) -> None:
        """Construct an :class:`.AttrsDict` object.

        Note
        ----
        The input dictionary is copied.

        Parameters
        ----------
        value
            a :class:`dict` object to initialize the instance with.
        """
        if value is None:
            super().__init__()
        # can only be initialized with a dict
        elif isinstance(value, dict):
            for key in value:
                self.__setitem__(key, value[key])
        else:
            msg = "expected dict"
            raise TypeError(msg)

        # attribute that holds cached remappings -- see map()
        super().__setattr__("__cached_remaps__", {})

    def __setitem__(self, key: str | int | float, value: Any) -> Any:
        # convert dicts to AttrsDicts
        if not isinstance(value, AttrsDict):
            if isinstance(value, dict):
                value = AttrsDict(value)  # this should make it recursive
            # recurse lists
            elif isinstance(value, list):
                for i, el in enumerate(value):
                    if isinstance(el, dict):
                        value[i] = AttrsDict(el)  # this should make it recursive

        super().__setitem__(key, value)

        # if the key is a valid attribute name, create a new attribute
        if isinstance(key, str) and key.isidentifier():
            super().__setattr__(key, value)

        # reset special __cached_remaps__ private attribute -- see map()
        super().__setattr__("__cached_remaps__", {})

    __setattr__ = __setitem__

    def __getattr__(self, name: str) -> Any:
        try:
            super().__getattr__(name)
        except AttributeError as exc:
            msg = f"dictionary does not contain a '{name}' key"
            raise AttributeError(msg) from exc

    def map(self, label: str, unique: bool = True) -> AttrsDict:
        """Remap dictionary according to an alternative unique label.

        Loop over keys in the first level and search for key named `label` in
        their values. If `label` is found and its value `newid` is unique,
        create a mapping between `newid` and the first-level dictionary `obj`.
        If `label` is of the form ``key.label``, ``label`` will be searched in
        a dictionary keyed by ``key``. If the label is unique a dictionary of
        dictionaries will be returned, if not unique and `unique` is false, a
        dictionary will be returned where each entry is a dictionary of
        dictionaries keyed by an arbitrary integer.

        Parameters
        ----------
        label
            game (key) at which the new label can be found. If nested in
            dictionaries, use ``.`` to separate levels, e.g.
            ``level1.level2.label``.
        unique
            bool specifying whether only unique keys are allowed. If true
            will raise an error if the specified key is not unique.

        Examples
        --------
        >>> d = AttrsDict({
        ...   "a": {
        ...     "id": 1,
        ...     "group": {
        ...       "id": 3,
        ...     },
        ...     "data": "x"
        ...   },
        ...   "b": {
        ...     "id": 2,
        ...     "group": {
        ...       "id": 4,
        ...     },
        ...     "data": "y"
        ...   },
        ... })
        >>> d.map("id")[1].data == "x"
        True
        >>> d.map("group.id")[4].data == "y"
        True

        Note
        ----
        No copy is performed, the returned dictionary is made of references to
        the original objects.

        Warning
        -------
        The result is cached internally for fast access after the first call.
        If the dictionary is modified, the cache gets cleared.
        """
        # if this is a second call, return the cached result
        if label in self.__cached_remaps__:
            return self.__cached_remaps__[label]

        splitk = label.split(".")
        newmap = AttrsDict()
        unique_tracker = True
        # loop over values in the first level
        for v in self.values():
            # find the (nested) label value
            newid = v
            try:
                for k in splitk:
                    newid = newid[k]
            # just skip if the label is not there
            except (KeyError, TypeError, FileNotFoundError):
                continue

            if not isinstance(newid, Hashable):
                msg = f"'{label}' values are not all hashable"
                raise RuntimeError(msg)

            if newid in newmap:
                newkey = sorted(newmap[newid].keys())[-1] + 1
                newmap[newid].update({newkey: v})
                unique_tracker = False
            else:
                # add an item to the new dict with key equal to the value of the label
                newmap[newid] = {0: v}

        if unique is True and unique_tracker is False:
            # complain if a label with the same value was already found
            msg = f"'{label}' values are not unique"
            raise RuntimeError(msg)

        if unique_tracker is True:
            newmap = AttrsDict({entry: newmap[entry][0] for entry in newmap})

        if not newmap:
            msg = f"could not find '{label}' anywhere in the dictionary"
            raise ValueError(msg)

        # cache it
        self.__cached_remaps__[label] = newmap
        return newmap

    def group(self, label: str) -> AttrsDict:
        """Group dictionary according to a `label`.

        This is equivalent to :meth:`.map` with `unique` set to ``False``.

        Parameters
        ----------
        label
            name (key) at which the new label can be found. If nested in
            dictionaries, use ``.`` to separate levels, e.g.
            ``level1.level2.label``.

        Examples
        --------
        >>> d = AttrsDict({
        ...   "a": {
        ...     "type": "A",
        ...     "data": 1
        ...   },
        ...   "b": {
        ...     "type": "A",
        ...     "data": 2
        ...   },
        ...   "c": {
        ...     "type": "B",
        ...     "data": 3
        ...   },
        ... })
        >>> d.group("type").keys()
        dict_keys(['A', 'B'])
        >>> d.group("type").A.values()
        dict_values([{'type': 'A', 'data': 1}, {'type': 'A', 'data': 2}])
        >>> d.group("type").B.values()
        dict_values([{'type': 'B', 'data': 3}])
        >>> d.group("type").A.map("data")[1]
        {'type': 'A', 'data': 1}

        See Also
        --------
        map
        """
        return self.map(label, unique=False)

    # d |= other_d should still produce a valid AttrsDict
    def __ior__(self, other: dict | AttrsDict) -> AttrsDict:
        return AttrsDict(super().__ior__(other))

    # d1 | d2 should still produce a valid AttrsDict
    def __or__(self, other: dict | AttrsDict) -> AttrsDict:
        return AttrsDict(super().__or__(other))

    def reset(self) -> None:
        """Reset this instance by removing all cached data."""
        super().__setattr__("__cached_remaps__", {})
