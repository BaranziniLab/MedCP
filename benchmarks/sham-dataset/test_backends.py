#!/usr/bin/env python3
"""Verify MedCP against every configured backend using the sham OMOP dataset.

Always tests the local SQLite dataset and the default SPOKE knowledge graph.
Also tests MySQL and/or SQL Server when their connection details are supplied
via environment variables (e.g. by sourcing a `mysql/.dbenv` / `mssql/.dbenv`
written by the provision scripts):

    MYSQL_HOST, MSSQL_HOST      host of the MySQL / SQL Server instance
    DB_USER, DB_PASSWORD        credentials for those instances
    DB_NAME                     database name (default: omop)
    MYSQL_PORT (3306), MSSQL_PORT (1433)

Run it with a Python that has MedCP's dependencies, e.g. from the repo root:

    uv run --with fastmcp --with neo4j --with pymysql --with pymssql \
        python benchmarks/sham-dataset/test_backends.py
"""
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))

from fastmcp import Client  # noqa: E402
from medcp.server import MedCPConfig, create_medcp_server, _load_spoke_defaults  # noqa: E402

SQLITE = os.path.join(HERE, "sqlite", "sham_mimic_omop.sqlite")
DB_NAME = os.environ.get("DB_NAME", "omop")
DB_USER = os.environ.get("DB_USER", "")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")


def clinical_configs():
    cfgs = {"sqlite": {"backend": "sqlite", "sqlite_path": SQLITE}}
    if os.environ.get("MYSQL_HOST"):
        cfgs["mysql"] = {"backend": "mysql", "server": os.environ["MYSQL_HOST"],
                         "database": DB_NAME, "username": DB_USER, "password": DB_PASSWORD,
                         "port": int(os.environ.get("MYSQL_PORT", 3306))}
    if os.environ.get("MSSQL_HOST"):
        cfgs["mssql"] = {"backend": "mssql", "server": os.environ["MSSQL_HOST"],
                         "database": DB_NAME, "username": DB_USER, "password": DB_PASSWORD,
                         "port": int(os.environ.get("MSSQL_PORT", 1433))}
    return cfgs


async def test_clinical(name, cfgdict):
    mcp = create_medcp_server(MedCPConfig(clinical_records=cfgdict, namespace="MedCP", log_level="WARNING"))
    async with Client(mcp) as c:
        tools = [t.name for t in await c.list_tools()]
        lt = next(t for t in tools if t.endswith("list_clinical_tables"))
        q = next(t for t in tools if t.endswith("query_clinical_records"))
        import json
        ntab = len(json.loads((await c.call_tool(lt, {})).content[0].text))
        npers = (await c.call_tool(q, {"sql_query": "SELECT COUNT(*) AS n FROM person"})).content[0].text.splitlines()[-1]
        try:
            await c.call_tool(q, {"sql_query": "DELETE FROM person"}); guard = "NOT BLOCKED!"
        except Exception:
            guard = "blocked"
    print(f"  [{name:6s}] tables={ntab:<4} persons={npers:<5} write={guard}")


async def test_spoke():
    try:
        mcp = create_medcp_server(MedCPConfig(knowledge_graph=_load_spoke_defaults(), namespace="MedCP", log_level="WARNING"))
        async with Client(mcp) as c:
            tools = [t.name for t in await c.list_tools()]
            q = next(t for t in tools if t.endswith("query_knowledge_graph"))
            r = await c.call_tool(q, {"cypher_query": "MATCH (d:Disease) RETURN count(d) AS n"})
        print(f"  [spoke ] default KG reachable -> Disease count {r.content[0].text}")
    except Exception as e:
        print(f"  [spoke ] SKIPPED (network/APOC?): {str(e)[:80]}")


async def main():
    print("MedCP backend verification (sham OMOP dataset)")
    for name, cfg in clinical_configs().items():
        await test_clinical(name, cfg)
    await test_spoke()
    print("done.")


if __name__ == "__main__":
    asyncio.run(main())
