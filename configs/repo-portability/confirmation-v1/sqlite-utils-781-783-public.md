# Regression: rowid primary key rejected by upsert(pk=)

Source: https://github.com/simonw/sqlite-utils/issues/781

Refs:
- https://github.com/simonw/sqlite-utils/issues/769#issuecomment-4900585395

STR:
```python
import sqlite_utils
db = sqlite_utils.Database(memory=True)
db["t"].insert({"title": "Hello"})     # rowid table, columns = ['title']
db["t"].pks                             # -> ['rowid']
db["t"].upsert({"rowid": 1, "title": "x"}, pk="rowid")
# 4.0rc4: InvalidColumns: Invalid primary key column ['rowid'] for table t with columns ['title']
# 3.39:   works


Public replay combines issues #781 and #783 as one repair family, never as independent tasks. Rowid aliases must be usable as primary keys on rowid tables; ignored inserts must report the existing row identifiers when resolvable, including compound keys/list mode/hash IDs. Unresolvable conflicts leave identifiers unset.

## Related public issue #783

Regression: last_rowid is None after an ignored insert

```python
db.execute("create table docs (id integer primary key, title text)")
t = db["docs"]
t.insert({"id": 1, "title": "Exists"}, pk="id")
r = t.insert({"id": 1, "title": "One"}, ignore=True)   # datasette passes no pk=
r.last_rowid    # 4.0rc4: None   |  3.39: 1
```
