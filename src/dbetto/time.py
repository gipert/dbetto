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

from datetime import datetime


def str_to_datetime(value):
    """Convert a string in the format %Y%m%dT%H%M%SZ to :class:`datetime.datetime`."""
    return datetime.strptime(value, "%Y%m%dT%H%M%SZ")


def datetime_to_str(value):
    """Convert a :class:`datetime.datetime` object to a string in the format %Y%m%dT%H%M%SZ."""
    if isinstance(value, float):
        value = datetime.fromtimestamp(value)
    return value.strftime("%Y%m%dT%H%M%SZ")


def unix_time(value):
    """Convert a string in the format %Y%m%dT%H%M%SZ or datetime object to Unix time value"""
    if isinstance(value, str):
        return datetime.timestamp(str_to_datetime(value))

    if isinstance(value, datetime):
        return datetime.timestamp(value)

    msg = f"Can't convert type {type(value)} to unix time"
    raise ValueError(msg)
