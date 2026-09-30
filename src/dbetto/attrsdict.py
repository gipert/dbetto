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

import copy
import logging
from collections.abc import Hashable
from typing import Any

import yaml

log = logging.getLogger(__name__)


class ReadOnlyList(list):
    """A :class:`list` that cannot be modified in place.

    Lists inside a read-only :class:`AttrsDict` are converted to this type.
    Non-mutating operations (indexing, iteration, ``+``, :func:`sorted`, JSON
    or YAML serialization) behave like a plain list; copies are plain lists.
    """

    def _read_only(self, *_, **__):
        msg = "this list is read-only"
        raise TypeError(msg)

    append = extend = insert = remove = pop = clear = sort = reverse = _read_only
    __setitem__ = __delitem__ = __iadd__ = __imul__ = _read_only

    def __reduce__(self):
        return (ReadOnlyList, (list(self),))

    def __copy__(self) -> list:
        return list(self)

    def __deepcopy__(self, memo: dict) -> list:
        new = []
        memo[id(self)] = new
        new.extend(copy.deepcopy(v, memo) for v in self)
        return new


# dump ReadOnlyList like a plain list
for _dumper in (
    yaml.representer.SafeRepresenter,
    yaml.representer.Representer,
    yaml.Dumper,
    yaml.SafeDumper,
):
    _dumper.add_representer(
        ReadOnlyList, yaml.representer.SafeRepresenter.represent_list
    )


def _set_readonly(obj: Any, flag: bool) -> Any:
    """Propagate the read-only `flag` into `obj`, return the object to store."""
    if isinstance(obj, AttrsDict):
        if obj.__readonly__ != flag:
            AttrsDict.__setattr__(obj, "__readonly__", flag, suppress_warning=True)
        return obj
    if isinstance(obj, list):
        if flag == isinstance(obj, ReadOnlyList):  # already in the right state
            return obj
        items = [_set_readonly(v, flag) for v in obj]
        return ReadOnlyList(items) if flag else items
    return obj


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

    def __new__(cls, *_, **__) -> AttrsDict:
        """Create a new instance of AttrsDict."""
        instance = super().__new__(cls)
        super(AttrsDict, instance).__setattr__("__readonly__", False)
        super(AttrsDict, instance).__setattr__("__cached_remaps__", {})
        return instance

    def __init__(self, value: dict | None = None, readonly: bool = False) -> None:
        """Construct an :class:`.AttrsDict` object.

        Note
        ----
        The input dictionary is copied.

        Parameters
        ----------
        value
            a :class:`dict` object to initialize the instance with.
        readonly
            if ``True``, fields will be read-only
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

        # only propagate True: never unfreeze shared read-only children
        if readonly:
            self.__readonly__ = True

    def _check_writable(self) -> None:
        if self.__readonly__:
            msg = "this AttrsDict is read-only"
            raise TypeError(msg)

    def __setitem__(self, key: str | int | float, value: Any) -> Any:
        AttrsDict._check_writable(self)

        # convert dicts to AttrsDicts
        if not isinstance(value, AttrsDict):
            if isinstance(value, dict):
                value = AttrsDict(value)  # this should make it recursive
            # recurse lists
            elif isinstance(value, list):
                for i, el in enumerate(value):
                    if isinstance(el, dict) and not isinstance(el, AttrsDict):
                        value[i] = AttrsDict(el)  # this should make it recursive

        super().__setitem__(key, value)

        # if the key is a valid attribute name, create a new attribute
        if isinstance(key, str) and key.isidentifier():
            super().__setattr__(key, value)

        # reset special __cached_remaps__ private attribute -- see map()
        super().__setattr__("__cached_remaps__", {})

    def __setattr__(
        self, name: str, value: Any, suppress_warning: bool = False
    ) -> None:
        if name == "__readonly__":
            if not suppress_warning and self.__readonly__ and not value:
                log.warning(
                    "toggling AttrsDict from read-only to writable is not recommended; instead consider deepcopying"
                )
            for key, val in list(dict.items(self)):
                new = _set_readonly(val, value)
                if new is not val:  # list converted to/from ReadOnlyList
                    dict.__setitem__(self, key, new)
                    if isinstance(key, str) and key.isidentifier():
                        object.__setattr__(self, key, new)
            super().__setattr__(name, value)
        else:
            self.__setitem__(name, value)

    def __delattr__(self, name: str) -> None:
        AttrsDict._check_writable(self)
        super().__delattr__(name)

    def __delitem__(self, key: Any) -> None:
        AttrsDict._check_writable(self)
        super().__delitem__(key)

    def pop(self, *args: Any) -> Any:
        AttrsDict._check_writable(self)
        return super().pop(*args)

    def popitem(self) -> tuple:
        AttrsDict._check_writable(self)
        return super().popitem()

    def clear(self) -> None:
        AttrsDict._check_writable(self)
        super().clear()

    def update(self, *args: Any, **kwargs: Any) -> None:
        AttrsDict._check_writable(self)
        super().update(*args, **kwargs)

    def setdefault(self, key: Any, default: Any = None) -> Any:
        AttrsDict._check_writable(self)
        return super().setdefault(key, default)

    def __copy__(self) -> AttrsDict:
        """Writable shallow copy."""
        new = AttrsDict()
        for key, val in dict.items(self):
            new[key] = val
        return new

    def __deepcopy__(self, memo: dict) -> AttrsDict:
        """Writable deep copy."""
        new = AttrsDict()
        memo[id(self)] = new
        for key, val in dict.items(self):
            new[key] = copy.deepcopy(val, memo)
        return new

    def to_dict(self) -> dict:
        """Return a plain :class:`dict` representation of the object.

        Nested :class:`AttrsDict` instances and lists are recursively
        converted to built-in containers to ensure the result is fully
        serialisable by callers expecting standard dictionaries.
        """

        def _convert(value: Any) -> Any:
            if isinstance(value, AttrsDict):
                return {key: _convert(val) for key, val in dict.items(value)}
            if isinstance(value, list):
                return [_convert(item) for item in value]
            return value

        return {key: _convert(val) for key, val in dict.items(self)}

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

        # cache it; only propagate True, never unfreeze the (shared) values
        self.__cached_remaps__[label] = newmap
        if self.__readonly__:
            newmap.__readonly__ = True
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
        AttrsDict._check_writable(self)
        return AttrsDict(super().__ior__(other))

    # d1 | d2 should still produce a valid AttrsDict
    def __or__(self, other: dict | AttrsDict) -> AttrsDict:
        return AttrsDict(
            super().__or__(other),
            self.__readonly__
            | (other.__readonly__ if isinstance(other, AttrsDict) else False),
        )

    def reset(self) -> None:
        """Reset this instance by removing all cached data."""
        super().__setattr__("__cached_remaps__", {})

    # Make pickling safe by serializing only the internal cached state as attributes.
    def __getstate__(self) -> dict:
        """Return the instance-specific state for pickling."""
        try:
            cached = super().__getattribute__("__cached_remaps__")
        except AttributeError:
            cached = {}
        return {"__cached_remaps__": cached, "__readonly__": self.__readonly__}

    def __setstate__(self, state: dict) -> None:
        """Restore the instance-specific state during unpickling."""
        super().__setattr__("__cached_remaps__", state.get("__cached_remaps__", {}))
        super().__setattr__("__readonly__", state.get("__readonly__", False))
