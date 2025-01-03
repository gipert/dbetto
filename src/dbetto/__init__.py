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

from ._version import version as __version__
from .attrsdict import AttrsDict
from .catalog import Props
from .textdb import TextDB
from .time import str_to_datetime

__all__ = [
    "AttrsDict",
    "Props",
    "TextDB",
    "__version__",
    "str_to_datetime",
]
