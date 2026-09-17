---
name: sqlite-ingest
description: Use for inserting JSON, CSV or TSV records into SQLite, including primary-key replacement and upsert.
---

# sqlite-ingest

Author-adapted operational skill, based only on the versioned pre-2020 public documentation below. Not an independently authored external package.

Use for inserting JSON, CSV or TSV records into SQLite, including primary-key replacement and upsert. Confirm input format and whether mutation is requested; these commands write a database. Compare stored rows to the input; do not use ingestion as a read-only inspection step.

## Versioned reference

.. _cli_inserting_data:

Inserting JSON data
===================

If you have data as JSON, you can use ``sqlite-utils insert tablename`` to insert it into a database. The table will be created with the correct (automatically detected) columns if it does not already exist.

You can pass in a single JSON object or a list of JSON objects, either as a filename or piped directly to standard-in (by using ``-`` as the filename).

Here's the simplest possible example::

    $ echo '{"name": "Cleo", "age": 4}' | sqlite-utils insert dogs.db dogs -

To specify a column as the primary key, use ``--pk=column_name``.

To create a compound primary key across more than one column, use ``--pk`` multiple times.

If you feed it a JSON list it will insert multiple records. For example, if ``dogs.json`` looks like this::

    [
        {
            "id": 1,
            "name": "Cleo",
            "age": 4
        },
        {
            "id": 2,
            "name": "Pancakes",
            "age": 2
        },
        {
            "id": 3,
            "name": "Toby",
            "age": 6
        }
    ]

You can import all three records into an automatically created ``dogs`` table and set the ``id`` column as the primary key like so::

    $ sqlite-utils insert dogs.db dogs dogs.json --pk=id

You can skip inserting any records that have a primary key that already exists using ``--ignore``::

    $ sqlite-utils insert dogs.db dogs dogs.json --ignore

You can also import newline-delimited JSON using the ``--nl`` option. Since `Datasette <https://datasette.readthedocs.io/>`__ can export newline-delimited JSON, you can combine the two tools like so::

    $ curl -L "https://latest.datasette.io/fixtures/facetable.json?_shape=array&_nl=on" \
        | sqlite-utils insert nl-demo.db facetable - --pk=id --nl

This also means you pipe ``sqlite-utils`` together to easily create a new SQLite database file containing the results of a SQL query against another database::

    $ sqlite-utils json sf-trees.db \
        "select TreeID, qAddress, Latitude, Longitude from Street_Tree_List" --nl \
      | sqlite-utils insert saved.db trees - --nl
    # This creates saved.db with a single table called trees:
    $ sqlite-utils csv saved.db "select * from trees limit 5"
    TreeID,qAddress,Latitude,Longitude
    141565,501X Baker St,37.7759676911831,-122.441396661871
    232565,940 Elizabeth St,37.7517102172731,-122.441498017841
    119263,495X Lakeshore Dr,,
    207368,920 Kirkham St,37.760210314285,-122.47073935813
    188702,1501 Evans Ave,37.7422086702947,-122.387293152263

Inserting CSV or TSV data
=========================

If your data is in CSV format, you can insert it using the ``--csv`` option::

    $ sqlite-utils insert dogs.db dogs docs.csv --csv

For tab-delimited data, use ``--tsv``::

    $ sqlite-utils insert dogs.db dogs docs.tsv --tsv

.. _cli_insert_replace:

Insert-replacing data
=====================

Insert-replacing works exactly like inserting, with the exception that if your data has a primary key that matches an already existing record that record will be replaced with the new data.

After running the above ``dogs.json`` example, try running this::

    $ echo '{"id": 2, "name": "Pancakes", "age": 3}' | \
        sqlite-utils insert dogs.db dogs - --pk=id --replace

This will replace the record for id=2 (Pancakes) with a new record with an updated age.

.. _cli_upsert:

Upserting data
==============

Upserting is update-or-insert. If a row exists with the specified primary key the provided columns will be updated. If no row exists that row will be created.

Unlike ``insert --replace``, an upsert will ignore any column values that exist but are not present in the upsert document.

For example::

    $ echo '{"id": 2, "age": 4}' | \
        sqlite-utils upsert dogs.db dogs - --pk=id

This will update the dog with id=2 to have an age of 4, creating a new record (with a null name) if one does not exist. If a row DOES exist the name will be left as-is.

The command will fail if you reference columns that do not exist on the table. To automatically create missing columns, use the ``--alter`` option.

.. note::
    ``upsert`` in sqlite-utils 1.x worked like ``insert ... --replace`` does in 2.x. See `issue #66 <https://github.com/simonw/sqlite-utils/issues/66>`__ for details of this change.
