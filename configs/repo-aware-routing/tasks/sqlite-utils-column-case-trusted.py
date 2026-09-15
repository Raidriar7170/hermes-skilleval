from sqlite_utils import Database

def test_target():
    db=Database(memory=True)
    t=db["books"]; t.create({"Id": int, "Title": str}, pk="Id")
    t.insert({"Id": 1,"Title":"One"},pk="id")
    assert t.last_pk == 1

def test_regression():
    db=Database(memory=True)
    t=db["books"]; t.insert({"Id":1,"Title":"One"},pk="Id")
    assert t.last_pk == 1
    assert list(t.rows)==[{"Id":1,"Title":"One"}]
