# sqlite-schema

Author-adapted operational skill, based only on the versioned pre-2020 public documentation below. Not an independently authored external package.

Use for SQLite column, foreign-key or index changes. Inspect the existing schema before mutation, apply only the requested operation in a disposable reproduction, then check schema and preserved rows. These APIs require a writable SQLite database; they do not describe CSV formatting.

## Versioned reference

.. _python_api_add_column:

Adding columns
==============

You can add a new column to a table using the ``.add_column(col_name, col_type)`` method:

.. code-block:: python

    db["dogs"].add_column("instagram", str)
    db["dogs"].add_column("weight", float)
    db["dogs"].add_column("dob", datetime.date)
    db["dogs"].add_column("image", "BLOB")
    db["dogs"].add_column("website") # str by default

You can specify the ``col_type`` argument either using a SQLite type as a string, or by directly passing a Python type e.g. ``str`` or ``float``.

The ``col_type`` is optional - if you omit it the type of ``TEXT`` will be used.

SQLite types you can specify are ``"TEXT"``, ``"INTEGER"``, ``"FLOAT"`` or ``"BLOB"``.

If you pass a Python type, it will be mapped to SQLite types as shown here::

    float: "FLOAT"
    int: "INTEGER"
    bool: "INTEGER"
    str: "TEXT"
    bytes: "BLOB"
    datetime.datetime: "TEXT"
    datetime.date: "TEXT"
    datetime.time: "TEXT"

    # If numpy is installed
    np.int8: "INTEGER"
    np.int16: "INTEGER"
    np.int32: "INTEGER"
    np.int64: "INTEGER"
    np.uint8: "INTEGER"
    np.uint16: "INTEGER"
    np.uint32: "INTEGER"
    np.uint64: "INTEGER"
    np.float16: "FLOAT"
    np.float32: "FLOAT"
    np.float64: "FLOAT"

You can also add a column that is a foreign key reference to another table using the ``fk`` parameter:

.. code-block:: python

    db["dogs"].add_column("species_id", fk="species")

This will automatically detect the name of the primary key on the species table and use that (and its type) for the new column.

You can explicitly specify the column you wish to reference using ``fk_col``:

.. code-block:: python

    db["dogs"].add_column("species_id", fk="species", fk_col="ref")

You can set a ``NOT NULL DEFAULT 'x'`` constraint on the new column using ``not_null_default``:

.. code-block:: python

    db["dogs"].add_column("friends_count", int, not_null_default=0)

.. _python_api_add_foreign_key:

Adding foreign key constraints
==============================

The SQLite ``ALTER TABLE`` statement doesn't have the ability to add foreign key references to an existing column.

It's possible to add these references through very careful manipulation of SQLite's ``sqlite_master`` table, using ``PRAGMA writable_schema``.

``sqlite-utils`` can do this for you, though there is a significant risk of data corruption if something goes wrong so it is advisable to create a fresh copy of your database file before attempting this.

Here's an example of this mechanism in action:

.. code-block:: python

    db["authors"].insert_all([
        {"id": 1, "name": "Sally"},
        {"id": 2, "name": "Asheesh"}
    ], pk="id")
    db["books"].insert_all([
        {"title": "Hedgehogs of the world", "author_id": 1},
        {"title": "How to train your wolf", "author_id": 2},
    ])
    db["books"].add_foreign_key("author_id", "authors", "id")

The ``table.add_foreign_key(column, other_table, other_column)`` method takes the name of the column, the table that is being referenced and the key column within that other table. If you ommit the ``other_column`` argument the primary key from that table will be used automatically. If you omit the ``other_table`` argument the table will be guessed based on some simple rules:

- If the column is of format ``author_id``, look for tables called ``author`` or ``authors``
- If the column does not end in ``_id``, try looking for a table with the exact name of the column or that name with an added ``s``

.. _python_api_index_foreign_keys:

Adding indexes for all foreign keys
-----------------------------------

If you want to ensure that every foreign key column in your database has a corresponding index, you can do so like this:

.. code-block:: python

    db.index_foreign_keys()
