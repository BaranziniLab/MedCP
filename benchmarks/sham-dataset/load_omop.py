#!/usr/bin/env python3
"""Load the sham OMOP SQLite dataset into MySQL or SQL Server.

The administrative and reader passwords are accepted only through environment
variables so they do not appear in process arguments:

    MEDCP_DB_ADMIN_PASSWORD=... MEDCP_DB_READER_PASSWORD=... \
      python load_omop.py mysql HOST ADMIN_USER DBNAME [PORT]
    MEDCP_DB_ADMIN_PASSWORD=... MEDCP_DB_READER_PASSWORD=... \
      python load_omop.py mssql HOST ADMIN_USER DBNAME [PORT]

``DB_PASSWORD`` and ``DB_READER_PASSWORD`` remain supported as environment-only
compatibility aliases. After loading, the script replaces ``--reader-user``
with a login that has SELECT access to the target database and no write grants.

The MySQL/MariaDB path needs `pymysql`; the SQL Server path needs `pymssql`.
Each table is dropped and recreated with mapped column types, then bulk-loaded
with multi-row INSERTs (fast on both engines). Idempotent — safe to re-run.
"""
import argparse
import os
import re
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
SQLITE = os.path.join(HERE, "sqlite", "sham_mimic_omop.sqlite")
BATCH = 1000  # SQL Server caps a single VALUES clause at 1000 rows
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_identifier(value: str, label: str, max_length: int = 128) -> str:
    """Reject identifiers that would be unsafe to interpolate into DDL."""
    if len(value) > max_length or not IDENTIFIER.fullmatch(value):
        raise ValueError(
            f"{label} must be 1-{max_length} ASCII letters, digits, or "
            "underscores and may not start with a digit"
        )
    return value


def map_type(sqlite_type: str, engine: str) -> str:
    t = (sqlite_type or "").upper()
    if "INT" in t:
        return "BIGINT"
    if any(k in t for k in ("REAL", "FLOA", "DOUB", "NUM", "DEC")):
        return "DOUBLE" if engine == "mysql" else "FLOAT"
    return "LONGTEXT" if engine == "mysql" else "NVARCHAR(MAX)"


def quote(ident: str, engine: str) -> str:
    validate_identifier(ident, "SQL identifier")
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
    validate_identifier(db, "database name")
    conn = pymssql.connect(server=host, user=user, password=pwd, database="master",
                           port=str(port or 1433), autocommit=True)
    cur = conn.cursor()
    cur.execute(
        f"IF DB_ID(%s) IS NULL CREATE DATABASE {quote(db, engine)}",
        (db,),
    )
    cur.close()
    conn.close()
    print(f"  ensured database {db} exists")


def create_reader(engine, host, admin_user, admin_pwd, db, port,
                  reader_user, reader_pwd):
    """Replace the benchmark reader with a SELECT-only database principal."""
    validate_identifier(db, "database name")
    validate_identifier(
        reader_user,
        "reader username",
        32 if engine == "mysql" else 128,
    )
    if admin_user.casefold() == reader_user.casefold():
        raise ValueError("reader username must differ from the admin username")
    if not reader_pwd:
        raise ValueError("reader password may not be empty")
    if engine == "mssql" and len(reader_pwd) > 128:
        raise ValueError("SQL Server reader password may not exceed 128 characters")

    if engine == "mysql":
        conn = connect(engine, host, admin_user, admin_pwd, db, port)
        cur = conn.cursor()
        try:
            account = (reader_user, "%")
            cur.execute("DROP USER IF EXISTS %s@%s", account)
            cur.execute("CREATE USER %s@%s IDENTIFIED BY %s", (*account, reader_pwd))
            cur.execute(
                f"GRANT SELECT ON {quote(db, engine)}.* TO %s@%s",
                account,
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()
    else:
        # Remove the database user before replacing its server-level login.
        conn = connect(engine, host, admin_user, admin_pwd, db, port)
        cur = conn.cursor()
        try:
            cur.execute(
                f"IF DATABASE_PRINCIPAL_ID(%s) IS NOT NULL "
                f"DROP USER {quote(reader_user, engine)}",
                (reader_user,),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

        import pymssql
        conn = pymssql.connect(
            server=host,
            user=admin_user,
            password=admin_pwd,
            database="master",
            port=str(port or 1433),
            autocommit=True,
        )
        cur = conn.cursor()
        try:
            cur.execute(
                f"IF SUSER_ID(%s) IS NOT NULL "
                f"DROP LOGIN {quote(reader_user, engine)}",
                (reader_user,),
            )
            # SQL Server does not accept a bind parameter directly in CREATE
            # LOGIN. Build the DDL server-side from bound values; QUOTENAME
            # safely delimits both the validated login and the password literal.
            cur.execute(
                """
                DECLARE @reader sysname = %s;
                DECLARE @password nvarchar(128) = %s;
                DECLARE @statement nvarchar(max);
                SET @statement = N'CREATE LOGIN ' + QUOTENAME(@reader)
                    + N' WITH PASSWORD = ' + QUOTENAME(@password, '''');
                EXEC(@statement);
                """,
                (reader_user, reader_pwd),
            )
        finally:
            cur.close()
            conn.close()

        conn = connect(engine, host, admin_user, admin_pwd, db, port)
        cur = conn.cursor()
        try:
            cur.execute(
                f"CREATE USER {quote(reader_user, engine)} "
                f"FOR LOGIN {quote(reader_user, engine)}"
            )
            cur.execute(f"GRANT SELECT TO {quote(reader_user, engine)}")
            conn.commit()
        finally:
            cur.close()
            conn.close()

    print(f"  replaced reader {reader_user} with SELECT-only access")


def password_from_environment(primary: str, compatibility: str) -> str:
    password = os.environ.get(primary) or os.environ.get(compatibility)
    if not password:
        raise ValueError(
            f"set {primary} (or compatibility alias {compatibility}) "
            "in the environment"
        )
    return password


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", choices=("mysql", "mssql"))
    parser.add_argument("host")
    parser.add_argument("admin_user")
    parser.add_argument("database")
    parser.add_argument("port", nargs="?", type=int)
    parser.add_argument(
        "--reader-user",
        default=os.environ.get("DB_READER_USER", "medcpreader"),
    )
    parser.add_argument(
        "--reader-only",
        action="store_true",
        help="replace the SELECT-only reader without reloading any tables",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    engine = args.engine
    host = args.host
    user = args.admin_user
    db = validate_identifier(args.database, "database name")
    validate_identifier(
        user,
        "admin username",
        32 if engine == "mysql" else 128,
    )
    reader_user = args.reader_user
    port = args.port or (3306 if engine == "mysql" else 1433)
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    pwd = password_from_environment("MEDCP_DB_ADMIN_PASSWORD", "DB_PASSWORD")
    reader_pwd = password_from_environment(
        "MEDCP_DB_READER_PASSWORD",
        "DB_READER_PASSWORD",
    )
    if args.reader_only:
        create_reader(
            engine,
            host,
            user,
            pwd,
            db,
            port,
            reader_user,
            reader_pwd,
        )
        print(f"DONE: SELECT-only reader configured for {engine}:{db}")
        return
    if not os.path.exists(SQLITE):
        raise FileNotFoundError(f"dataset not found: {SQLITE}")

    ensure_database(engine, host, user, pwd, db, port)

    src = sqlite3.connect(SQLITE)
    tables = [r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    dst = connect(engine, host, user, pwd, db, port)
    dcur = dst.cursor()

    total = 0
    for t in tables:
        validate_identifier(t, "source table name")
        cols = src.execute(f"PRAGMA table_info({quote(t, 'mysql')})").fetchall()
        colnames = [c[1] for c in cols]
        coldefs = ", ".join(f"{quote(c[1], engine)} {map_type(c[2], engine)}" for c in cols)
        dcur.execute(f"DROP TABLE IF EXISTS {quote(t, engine)}" if engine == "mysql"
                     else f"IF OBJECT_ID(%s,'U') IS NOT NULL DROP TABLE {quote(t, engine)}",
                     () if engine == "mysql" else (f"dbo.{t}",))
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
    create_reader(
        engine,
        host,
        user,
        pwd,
        db,
        port,
        reader_user,
        reader_pwd,
    )
    print(f"DONE: {total:,} rows across {len(tables)} tables into {engine}:{db}")


if __name__ == "__main__":
    main()
