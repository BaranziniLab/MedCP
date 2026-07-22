#!/usr/bin/env python3
"""Load the sham OMOP SQLite dataset (./sqlite/) into a MySQL or SQL Server DB.

Usage:
    python load_omop.py mysql HOST USER PASSWORD DBNAME [PORT]
    python load_omop.py mssql HOST USER PASSWORD DBNAME [PORT]

The MySQL/MariaDB path needs `pymysql`; the SQL Server path needs `pymssql`.
Each table is dropped and recreated with mapped column types, then bulk-loaded
with multi-row INSERTs (fast on both engines). Idempotent — safe to re-run.
"""
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SQLITE = os.path.join(HERE, "sqlite", "sham_mimic_omop.sqlite")
BATCH = 1000  # SQL Server caps a single VALUES clause at 1000 rows


def map_type(sqlite_type: str, engine: str) -> str:
    t = (sqlite_type or "").upper()
    if "INT" in t:
        return "BIGINT"
    if any(k in t for k in ("REAL", "FLOA", "DOUB", "NUM", "DEC")):
        return "DOUBLE" if engine == "mysql" else "FLOAT"
    return "LONGTEXT" if engine == "mysql" else "NVARCHAR(MAX)"


def quote(ident: str, engine: str) -> str:
    return f"`{ident}`" if engine == "mysql" else f"[{ident}]"


def connect(engine, host, user, pwd, db, port):
    if engine == "mysql":
        import pymysql
        return pymysql.connect(host=host, user=user, password=pwd, database=db,
                               port=int(port or 3306), charset="utf8mb4", autocommit=False)
    import pymssql
    return pymssql.connect(server=host, user=user, password=pwd, database=db,
                           port=str(port or 1433), autocommit=False)


def ensure_database(engine, host, user, pwd, db, port):
    """MySQL auto-creates via connection; SQL Server needs an explicit CREATE."""
    if engine != "mssql":
        return
    import pymssql
    conn = pymssql.connect(server=host, user=user, password=pwd, database="master",
                           port=str(port or 1433), autocommit=True)
    cur = conn.cursor()
    cur.execute(f"IF DB_ID('{db}') IS NULL CREATE DATABASE [{db}]")
    cur.close()
    conn.close()
    print(f"  ensured database {db} exists")


def main():
    if len(sys.argv) < 6:
        print(__doc__)
        sys.exit(2)
    engine = sys.argv[1]
    host, user, pwd, db = sys.argv[2:6]
    port = sys.argv[6] if len(sys.argv) > 6 else None
    assert engine in ("mysql", "mssql"), "engine must be 'mysql' or 'mssql'"
    if not os.path.exists(SQLITE):
        sys.exit(f"dataset not found: {SQLITE}")

    ensure_database(engine, host, user, pwd, db, port)

    src = sqlite3.connect(SQLITE)
    tables = [r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    dst = connect(engine, host, user, pwd, db, port)
    dcur = dst.cursor()

    total = 0
    for t in tables:
        cols = src.execute(f"PRAGMA table_info('{t}')").fetchall()
        colnames = [c[1] for c in cols]
        coldefs = ", ".join(f"{quote(c[1], engine)} {map_type(c[2], engine)}" for c in cols)
        dcur.execute(f"DROP TABLE IF EXISTS {quote(t, engine)}" if engine == "mysql"
                     else f"IF OBJECT_ID('{t}','U') IS NOT NULL DROP TABLE {quote(t, engine)}")
        dcur.execute(f"CREATE TABLE {quote(t, engine)} ({coldefs})")
        dst.commit()

        collist = ", ".join(quote(c, engine) for c in colnames)
        one = "(" + ", ".join(["%s"] * len(colnames)) + ")"

        def flush(buf):
            if not buf:
                return 0
            dcur.execute(f"INSERT INTO {quote(t, engine)} ({collist}) VALUES " +
                         ", ".join([one] * len(buf)), [v for row in buf for v in row])
            dst.commit()
            return len(buf)

        n, buf = 0, []
        for row in src.execute(f"SELECT * FROM {quote(t, 'mysql')}"):
            buf.append(tuple(row))
            if len(buf) >= BATCH:
                n += flush(buf); buf = []
        n += flush(buf)
        total += n
        print(f"  {t:28s} {n:>10,} rows", flush=True)

    dcur.close(); dst.close(); src.close()
    print(f"DONE: {total:,} rows across {len(tables)} tables into {engine}:{db}")


if __name__ == "__main__":
    main()
