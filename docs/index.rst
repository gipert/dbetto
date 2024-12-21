dbetto
======

|dbetto| is a lightweight Python library that enables seamless access and
management of text-based databases (JSON/YAML) scattered across your
filesystem. Whether you're handling nested data structures or querying data by
validity periods, |dbetto| simplifies it all with an intuitive interface.

|dbetto| was originally developed to efficiently manage metadata for the LEGEND
physics experiment.

Getting started
---------------

|dbetto| is published on the `Python Package Index
<https://pypi.org/project/dbetto>`_. Install on local systems with `pip
<https://pip.pypa.io/en/stable/getting-started>`_:

.. tab:: Stable release

    .. code-block:: console

        $ pip install dbetto

.. tab:: Unstable (``main`` branch)

    .. code-block:: console

        $ pip install dbetto@git+https://github.com/gipert/dbetto@main

Next steps
----------

.. toctree::
   :maxdepth: 2

   tutorial

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Reference

   attrsdict
   textdb
   Full API reference <api/dbetto>
