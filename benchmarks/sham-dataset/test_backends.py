#!/usr/bin/env python3
"""Verify MedCP against every configured backend using the sham OMOP dataset.

Always tests the local SQLite dataset and the default SPOKE knowledge graph.
Also tests MySQL and/or SQL Server when their connection details are supplied
via environment variables (e.g. by sourcing a `mysql/.dbenv` / `mssql/.dbenv`
written by the provision scripts):

    MYSQL_HOST, MSSQL_HOST      host of the MySQL / SQL Server instance
    MYSQL_USER / MSSQL_USER     backend-specific username (or DB_USER)
    MYSQL_PASSWORD / MSSQL_PASSWORD
                               backend-specific password (or DB_PASSWORD)
    MYSQL_DATABASE / MSSQL_DATABASE
                               backend-specific database (or DB_NAME / omop)
    MYSQL_PORT (3306), MSSQL_PORT (1433)

Run it with MedCP's locked environment from the repo root:

    uv run --locked python benchmarks/sham-dataset/test_backends.py
"""
import asyncio
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))

from mcp import Client  # noqa: E402
from medcp.server import MedCPConfig, create_medcp_server, _load_spoke_defaults  # noqa: E402

SQLITE = os.path.join(HERE, "sqlite", "sham_mimic_omop.sqlite")
EXPECTED_TABLES = 32
EXPECTED_PERSONS = 100


def _backend_env(backend, key, shared_key=None, default=""):
    """Read a backend-specific value, then its legacy shared equivalent."""
    value = os.environ.get(f"{backend.upper()}_{key}")
    if value is not None:
        return value
    if shared_key:
        return os.environ.get(shared_key, default)
    return default


def clinical_configs():
    cfgs = {"sqlite": {"backend": "sqlite", "sqlite_path": SQLITE}}
    if os.environ.get("MYSQL_HOST"):
        cfgs["mysql"] = {
            "backend": "mysql",
            "server": os.environ["MYSQL_HOST"],
            "database": _backend_env("mysql", "DATABASE", "DB_NAME", "omop"),
            "username": _backend_env("mysql", "USER", "DB_USER"),
            "password": _backend_env("mysql", "PASSWORD", "DB_PASSWORD"),
            "port": int(os.environ.get("MYSQL_PORT", 3306)),
        }
    if os.environ.get("MSSQL_HOST"):
        cfgs["mssql"] = {
            "backend": "mssql",
            "server": os.environ["MSSQL_HOST"],
            "database": _backend_env("mssql", "DATABASE", "DB_NAME", "omop"),
            "username": _backend_env("mssql", "USER", "DB_USER"),
            "password": _backend_env("mssql", "PASSWORD", "DB_PASSWORD"),
            "port": int(os.environ.get("MSSQL_PORT", 1433)),
        }
    return cfgs


def _text(result):
    if result.is_error:
        message = result.content[0].text if result.content else "unknown tool error"
        raise AssertionError(message)
    if not result.content or not hasattr(result.content[0], "text"):
        raise AssertionError("tool returned no text content")
    return result.content[0].text


def verify_reader_permissions(name, cfgdict):
    """Confirm hosted fixture credentials are database-enforced read-only."""
    if name == "sqlite":
        return

    if name == "mysql":
        import pymysql

        conn = pymysql.connect(
            host=cfgdict["server"],
            user=cfgdict["username"],
            password=cfgdict["password"],
            database=cfgdict["database"],
            port=cfgdict["port"],
            autocommit=False,
        )
        cursor = conn.cursor()
        try:
            cursor.execute("SHOW GRANTS FOR CURRENT_USER")
            grant_lines = [str(row[0]).upper() for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()

        granted = set()
        for line in grant_lines:
            match = re.fullmatch(r"GRANT (.+?) ON .+ TO .+", line)
            assert match, f"mysql: unexpected grant form for benchmark reader"
            granted.update(part.strip() for part in match.group(1).split(","))
        assert "SELECT" in granted, "mysql: benchmark reader lacks SELECT"
        assert granted <= {"SELECT", "USAGE"}, (
            f"mysql: benchmark reader has non-read grants: "
            f"{sorted(granted - {'SELECT', 'USAGE'})}"
        )
        return

    import pymssql

    conn = pymssql.connect(
        server=cfgdict["server"],
        user=cfgdict["username"],
        password=cfgdict["password"],
        database=cfgdict["database"],
        port=str(cfgdict["port"]),
        autocommit=False,
    )
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT permission_name FROM fn_my_permissions(NULL, 'DATABASE')"
        )
        permissions = {str(row[0]).upper() for row in cursor.fetchall()}
        cursor.execute(
            "SELECT roles.name "
            "FROM sys.database_role_members AS memberships "
            "JOIN sys.database_principals AS roles "
            "ON roles.principal_id = memberships.role_principal_id "
            "JOIN sys.database_principals AS members "
            "ON members.principal_id = memberships.member_principal_id "
            "WHERE members.name = USER_NAME()"
        )
        roles = {str(row[0]).lower() for row in cursor.fetchall()}
    finally:
        cursor.close()
        conn.close()

    write_permissions = {
        "ADMINISTER DATABASE BULK OPERATIONS",
        "ALTER",
        "BACKUP DATABASE",
        "BACKUP LOG",
        "CONTROL",
        "CREATE TABLE",
        "DELETE",
        "EXECUTE",
        "INSERT",
        "TAKE OWNERSHIP",
        "UPDATE",
    }
    assert "SELECT" in permissions, "mssql: benchmark reader lacks SELECT"
    assert not permissions & write_permissions, (
        f"mssql: benchmark reader has write-capable permissions: "
        f"{sorted(permissions & write_permissions)}"
    )
    assert roles <= {"db_datareader"}, (
        f"mssql: unexpected benchmark reader roles: {sorted(roles)}"
    )


async def test_clinical(name, cfgdict):
    verify_reader_permissions(name, cfgdict)
    mcp = create_medcp_server(MedCPConfig(clinical_records=cfgdict, namespace="MedCP", log_level="WARNING"))
    async with Client(mcp, mode="2026-07-28") as c:
        listing = await c.list_tools()
        tools = [t.name for t in listing.tools]
        lt = next(t for t in tools if t.endswith("list_clinical_tables"))
        q = next(t for t in tools if t.endswith("query_clinical_records"))
        ntab = len(json.loads(_text(await c.call_tool(lt, {}))))
        npers = int(
            _text(
                await c.call_tool(
                    q, {"sql_query": "SELECT COUNT(*) AS n FROM person"}
                )
            ).splitlines()[-1]
        )
        guard_result = await c.call_tool(q, {"sql_query": "DELETE FROM person"})

    assert ntab == EXPECTED_TABLES, f"{name}: expected {EXPECTED_TABLES} tables, got {ntab}"
    assert npers == EXPECTED_PERSONS, f"{name}: expected {EXPECTED_PERSONS} persons, got {npers}"
    assert guard_result.is_error, f"{name}: write query was not blocked"
    print(
        f"  [{name:6s}] tables={ntab:<4} persons={npers:<5} "
        f"validator=blocked permissions=read-only"
    )
    return ntab, npers


async def test_spoke():
    mcp = create_medcp_server(
        MedCPConfig(
            knowledge_graph=_load_spoke_defaults(),
            namespace="MedCP",
            log_level="WARNING",
        )
    )
    async with Client(mcp, mode="2026-07-28") as c:
        listing = await c.list_tools()
        tools = [t.name for t in listing.tools]
        schema_tool = next(t for t in tools if t.endswith("get_knowledge_graph_schema"))
        query_tool = next(t for t in tools if t.endswith("query_knowledge_graph"))

        schema = json.loads(_text(await c.call_tool(schema_tool, {})))
        result = json.loads(
            _text(
                await c.call_tool(
                    query_tool,
                    {
                        "cypher_query": "MATCH (d:Disease) RETURN count(d) AS n",
                        "parameters": {},
                    },
                )
            )
        )

    assert isinstance(schema, dict) and schema, "SPOKE schema was empty"
    disease_count = int(result[0]["n"])
    assert disease_count > 0, "SPOKE Disease count was not positive"
    print(
        f"  [spoke ] schema_entities={len(schema):<5} "
        f"diseases={disease_count}"
    )


async def main():
    print("MedCP backend verification (sham OMOP dataset)")
    results = {}
    for name, cfg in clinical_configs().items():
        results[name] = await test_clinical(name, cfg)
    assert len(set(results.values())) == 1, f"clinical backend results differ: {results}"
    await test_spoke()
    print("done.")


if __name__ == "__main__":
    asyncio.run(main())
