import sqlite3

conn = sqlite3.connect("app.db")
for table in ("position_regulations", "regulation_kpis", "regulation_instructions", "kpi_templates"):
    print("===", table)
    for row in conn.execute(f"SELECT sql FROM sqlite_master WHERE name='{table}'"):
        print(row[0])
conn.close()
