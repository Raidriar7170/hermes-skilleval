# sqlite-fulltext

Author-adapted operational skill, based only on the versioned pre-2020 public documentation below. Not an independently authored external package.

Use for configuring or maintaining SQLite full-text indexes. Check available FTS version, indexed columns and trigger policy. Verify search against indexed records. Index creation and population mutate the database; do not assume it is a generic SQL or CSV text-search procedure.

## Versioned reference

.. _python_api_fts:

Enabling full-text search
=========================

You can enable full-text search on a table using ``.enable_fts(columns)``:

.. code-block:: python

    dogs.enable_fts(["name", "twitter"])

You can then run searches using the ``.search()`` method:

.. code-block:: python

    rows = dogs.search("cleo")

If you insert additional records into the table you will need to refresh the search index using ``populate_fts()``:

.. code-block:: python

    dogs.insert({
        "id": 2,
        "name": "Marnie",
        "twitter": "MarnieTheDog",
        "age": 16,
        "is_good_dog": True,
    }, pk="id")
    dogs.populate_fts(["name", "twitter"])

A better solution is to use database triggers. You can set up database triggers to automatically update the full-text index using ``create_triggers=True``:

.. code-block:: python

    dogs.enable_fts(["name", "twitter"], create_triggers=True)

``.enable_fts()`` defaults to using `FTS5 <https://www.sqlite.org/fts5.html>`__. If you wish to use `FTS4 <https://www.sqlite.org/fts3.html>`__ instead, use the following:

.. code-block:: python

    dogs.enable_fts(["name", "twitter"], fts_version="FTS4")

Optimizing a full-text search table
===================================

Once you have populated a FTS table you can optimize it to dramatically reduce its size like so:

.. code-block:: python

    dogs.optimize()

This runs the following SQL::

    INSERT INTO dogs_fts (dogs_fts) VALUES ("optimize");

Creating indexes
================

You can create an index on a table using the ``.create_index(columns)`` method. The method takes a list of columns:

.. code-block:: python

    dogs.create_index(["is_good_dog"])

By default the index will be named ``idx_{table-name}_{columns}`` - if you want to customize the name of the created index you can pass the ``index_name`` parameter:

.. code-block:: python

    dogs.create_index(
        ["is_good_dog", "age"],
        index_name="good_dogs_by_age"
    )

You can create a unique index by passing ``unique=True``:

.. code-block:: python

    dogs.create_index(["name"], unique=True)

Use ``if_not_exists=True`` to do nothing if an index with that name already exists.

Vacuum
======

You can optimize your database by running VACUUM against it like so:

.. code-block:: python

    Database("my_database.db").vacuum()
