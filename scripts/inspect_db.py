r"""D:\MyActivity\MyInfoBusiness\MyPythonApps\10 Typical_infrastructure\scripts\inspect_db.py"""

import sqlite3


def main() -> None:
    con = sqlite3.connect("app.db")
    cur = con.cursor()
    rows = cur.execute(
        "select name from sqlite_master where type='table' order by name"
    ).fetchall()
    tables = [r[0] for r in rows]
    print("tables:", tables)
    for t in tables:
        cols = cur.execute(f"pragma table_info({t})").fetchall()
        # cols: cid, name, type, notnull, dflt_value, pk
        print()
        print(t)
        for _, name, ctype, notnull, dflt, pk in cols:
            print(f"  - {name} {ctype} notnull={bool(notnull)} pk={bool(pk)} default={dflt}")


if __name__ == "__main__":
    main()

