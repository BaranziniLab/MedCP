import json
import sqlite3

import pytest
from mcp import Client

from medcp._version import __version__
from medcp.server import (
    LONGEST_TOOL_NAME,
    MAX_TOOL_NAME_LENGTH,
    _format_namespace,
)


EXPECTED_TOOL_NAMES = [
    "MedCP-query_clinical_records",
    "MedCP-list_clinical_tables",
]


@pytest.mark.anyio
async def test_modern_discovery_and_tool_list_metadata(medcp_server) -> None:
    async with Client(
        medcp_server,
        mode="auto",
        cache=None,
        raise_exceptions=True,
    ) as client:
        assert client.protocol_version == "2026-07-28"

        discovery = client.session.discover_result
        assert discovery is not None
        assert discovery.supported_versions == ["2026-07-28"]
        assert client.server_info.name == "MedCP"
        assert client.server_info.version == __version__
        assert discovery.result_type == "complete"
        assert discovery.ttl_ms == 300_000
        assert discovery.cache_scope == "private"

        listed = await client.list_tools(cache_mode="refresh")
        assert [tool.name for tool in listed.tools] == EXPECTED_TOOL_NAMES
        assert listed.result_type == "complete"
        assert listed.ttl_ms == 300_000
        assert listed.cache_scope == "private"


@pytest.mark.anyio
async def test_legacy_initialize_and_tool_order(medcp_server) -> None:
    async with Client(medcp_server, mode="legacy", cache=None) as client:
        assert client.protocol_version == "2025-11-25"
        assert client.session.discover_result is None
        assert client.server_info.name == "MedCP"
        assert client.server_info.version == __version__

        listed = await client.list_tools()
        assert [tool.name for tool in listed.tools] == EXPECTED_TOOL_NAMES


@pytest.mark.anyio
async def test_sqlite_list_query_and_write_guard(
    medcp_server,
    sham_sqlite_path,
) -> None:
    with sqlite3.connect(
        f"file:{sham_sqlite_path}?mode=ro",
        uri=True,
    ) as connection:
        initial_count = connection.execute("SELECT COUNT(*) FROM person").fetchone()[0]

    async with Client(
        medcp_server,
        mode="auto",
        cache=None,
        raise_exceptions=True,
    ) as client:
        listed = await client.call_tool("MedCP-list_clinical_tables", {})
        assert listed.is_error is False
        tables = json.loads(listed.content[0].text)
        table_names = [table["table_name"] for table in tables]
        assert "person" in table_names
        assert table_names == sorted(table_names)

        queried = await client.call_tool(
            "MedCP-query_clinical_records",
            {"sql_query": "SELECT COUNT(*) AS person_count FROM person"},
        )
        assert queried.is_error is False
        assert queried.content[0].text.splitlines() == ["person_count", str(initial_count)]

        rejected = await client.call_tool(
            "MedCP-query_clinical_records",
            {"sql_query": "UPDATE person SET year_of_birth = 1900"},
        )
        assert rejected.is_error is True
        assert "Only SELECT queries are allowed" in rejected.content[0].text

    with sqlite3.connect(
        f"file:{sham_sqlite_path}?mode=ro",
        uri=True,
    ) as connection:
        final_count = connection.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    assert final_count == initial_count


@pytest.mark.parametrize(
    ("namespace", "expected"),
    [
        ("", ""),
        ("MedCP", "MedCP-"),
        ("MedCP-", "MedCP-"),
        ("med.cp_v2", "med.cp_v2-"),
    ],
)
def test_namespace_formatting(namespace: str, expected: str) -> None:
    assert _format_namespace(namespace) == expected


@pytest.mark.parametrize(
    "namespace",
    [
        "has space",
        "has/slash",
        "has:colon",
        "has,comma",
        "médcp",
    ],
)
def test_namespace_rejects_invalid_characters(namespace: str) -> None:
    with pytest.raises(ValueError):
        _format_namespace(namespace)


def test_namespace_length_reserves_room_for_longest_tool_name() -> None:
    maximum_namespace_length = (
        MAX_TOOL_NAME_LENGTH - len(LONGEST_TOOL_NAME) - 1
    )
    namespace = "n" * maximum_namespace_length

    formatted = _format_namespace(namespace)
    assert len(f"{formatted}{LONGEST_TOOL_NAME}") == MAX_TOOL_NAME_LENGTH

    with pytest.raises(ValueError):
        _format_namespace(f"{namespace}n")
