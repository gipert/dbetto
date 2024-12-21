Quick start
===========

|dbetto| exposes the |TextDB| object, which implements a convenient Python
interface to a database of text files arbitrary scattered in a filesystem.
|TextDB| does not assume any particular directory structure or file naming.

.. note::

   Currently supported file formats are `JSON <https://json.org>`_ and `YAML
   <https://yaml.org>`_.

Access
------

Let's consider the following database:

.. code::

   data
    ├── dir1
    │   └── file1.json
    ├── file2.json
    ├── file3.yaml
    └── validity.yaml

With:

.. code-block::
   :caption: ``dir1/file1.json``

   {
     "value": 1
   }

and similarly ``file2.json`` and ``file3.yaml``.

Let's declare a |TextDB| object and point it to the ``data`` folder:

>>> from dbetto import TextDB
>>> db = TextDB("/home/vighi/data")
>>> db
TextDB('home/vighi/data')

|TextDB| treats directories, files and JSON/YAML keys at the same semantic
level.  Internally, the database is represented as a :class:`dict`\ -like
object, and can be therefore accessed with the same syntax:

>>> db["dir1"] # a dict
>>> db["file2.json"] # a dict
>>> db["dir1"]["file1.json"] # nested file
>>> db["dir1"]["file1"] # .json extension not strictly needed
>>> db["dir1/file1"] # can use a filesystem path
>>> db["dir1"]["file1"]["value"] # == 1

To save some typing, a fancy attribute-style access mode is
available (try tab-completion in IPython!):

>>> db.dir1
TextDB('home/vighi/data/dir1')
>>> db.dir1.file1
{'value': 1}
>>> type(db.dir1.file1)
<class 'dbetto.textdb.AttrsDict'>
>>> lmeta.dir1.file1.value
1

|TextDB| offers this functionality through the |AttrsDict| object, which is
just a superset of :class:`dict` that implements attribute-style access.

.. warning::

   The attribute-style access syntax cannot be used to query field names that
   cannot be parsed to valid Python variable names. For those, the classic
   dict-style access works.

.. tip::

   For large databases, a basic “lazy” mode is available by supplying
   ``lazy=True`` to the |TextDB| constructor. In this case, no global scan of
   the filesystem is performed at initialization time. Once a file is queried,
   it is also cached in the internal store for faster access.  Caution, this
   option is for advanced use!

Data validity
-------------

Mappings of data to time periods are specified through YAML validity files
(`specification
<https://legend-exp.github.io/legend-data-format-specs/dev/metadata>`_).  If a
``validity.yaml`` file is present in a directory, |TextDB| automatically
detects it and exposes the :meth:`~.textdb.TextDB.on` interface to perform a
query.

Let's assume the ``data`` directory from the example above contains
the following ``validity.yaml`` file:

.. code-block:: yaml
   :caption: ``validity.yaml``

   - valid_from: 20230101T000000Z
     category: all
     apply:
       - file3.yaml

   - valid_from: 20230102T000000Z
     category: all
     mode: append
     apply:
       - file2.yaml

where time points must be specified as strings formatted as ``%Y%m%dT%H%M%SZ`` (can
use :func:`~.time.str_to_datetime` to convert to a :class:`~datetime.datetime`
object).

The content of the files listed under ``apply`` is:

>>> db.file3
{'value': 2}
>>> db.file2.value
{'value': 3}

The implemented validity is:

  data in ``file3`` should be used from January the 1st (year 2023), while data
  in ``file3`` should be used from January the 2nd on.

|TextDB| makes it easy to automatically obtain the correct data, by specifying
a time point:

>>> from datetime import datetime, timezone
>>> db.on(datetime(2023, 1, 1, 14, 35, 00)).value
2
>>> db.on("20230110T095300Z").value
3

The content of the files in the database can, of course, be arbitrarily
complex.

Remapping and grouping data
---------------------------

A second important method of |TextDB| is :meth:`~.textdb.TextDB.map`, which
allows to query ``(key, value)`` dictionaries with an alternative unique key
defined in ``value``. Imagine a dictionary of properties of particle detectors
(also called channel map), keyed by the detector name:

>>> chmap.V05266A
{'name': 'V05266A',
 'system': 'geds',
 'location': {'string': 1, 'position': 4},
 'daq': {'crate': 0,
  'card': {'id': 1, 'serialno': None, 'address': '0x410'},
  'rawid': 1104003,
 ...

:meth:`~.textdb.TextDB.map` lets us retrieve the properties of the same
detector ``V05266A`` by using the numeric identifier assigned by the data
acquisition system, stored under "daq" > "id":

>>> chmap.map("daq.rawid")[1104003]
{'name': 'V05266A',
 'system': 'geds',
 'location': {'string': 1, 'position': 4},
 'daq': {'crate': 0,
  'card': {'id': 1, 'serialno': None, 'address': '0x410'},
  'rawid': 1104003,
 ...

If the requested key is not unique, an exception will be raised.
:meth:`~.textdb.TextDB.map` can, however, handle non-unique keys too and return a
dictionary of matching entries instead, keyed by an arbitrary integer to allow
further :meth:`~.textdb.TextDB.map` calls. The behavior is achieved by using
:meth:`~.textdb.TextDB.group` or by setting the ``unique`` argument flag. A typical
application is retrieving, in the same channel map, all detectors attached to
the same readout card (identifier stored in "electronics" > "cc4" > "id"):

>>> chmap.group("electronics.cc4.id")["C3"]
{0: {'name': 'V02160A',
  'system': 'geds',
  'location': {'string': 1, 'position': 1},
  'daq': {'crate': 0,
   'card': {'id': 1, 'address': '0x410', 'serialno': None},
   'channel': 0,

>>> chmap.group("electronics.cc4.id")["C3"].map("name").keys()
dict_keys(['V02160A', 'V02160B', 'V05261B', 'V05266A', 'V05266B', 'V05268B', 'V05612A'])

For further details, have a look at the documentation for :meth:`.attrsdict.AttrsDict.map`.
