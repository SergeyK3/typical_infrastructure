import sqlite3

conn = sqlite3.connect("app.db")
for row in conn.execute("SELECT sql FROM sqlite_master WHERE name='position_regulations'"):
    print(row[0])
for row in conn.execute("PRAGMA index_list('position_regulations')"):
    print("index", row)
    for col in conn.execute(f"PRAGMA index_info('{row[1]}')"):
        print("  ", col)
conn.close()
