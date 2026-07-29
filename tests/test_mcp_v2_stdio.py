import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
from typing import Any, AsyncIterator

import pytest

from medcp._version import __version__


EXPECTED_TOOL_NAMES = [
    "MedCP-query_clinical_records",
    "MedCP-list_clinical_tables",
]
MODERN_META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientInfo": {
        "name": "medcp-tests",
        "version": "1.0",
    },
    "io.modelcontextprotocol/clientCapabilities": {},
}


class StdioPeer:
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process
        self.raw_lines: list[bytes] = []
        self.trailing_stdout = b""
        self.stderr = b""

    async def send(self, message: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        frame = json.dumps(message, separators=(",", ":")).encode() + b"\n"
        self.process.stdin.write(frame)
        await self.process.stdin.drain()

    async def exchange(self, message: dict[str, Any]) -> dict[str, Any]:
        await self.send(message)
        assert self.process.stdout is not None
        raw = await asyncio.wait_for(self.process.stdout.readline(), timeout=10)
        assert raw, "MCP server exited before returning a response"
        assert raw.endswith(b"\n"), f"Response was not newline-delimited: {raw!r}"
        self.raw_lines.append(raw)
        decoded = json.loads(raw)
        assert isinstance(decoded, dict)
        return decoded


@asynccontextmanager
async def running_stdio_server(
    sham_sqlite_path: Path,
) -> AsyncIterator[StdioPeer]:
    repository_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment.update(
        {
            "MEDCP_DISABLE_KNOWLEDGE_GRAPH": "true",
            "CLINICAL_RECORDS_BACKEND": "sqlite",
            "CLINICAL_RECORDS_SQLITE_PATH": str(sham_sqlite_path),
            "MEDCP_NAMESPACE": "MedCP",
            "MEDCP_LOG_LEVEL": "ERROR",
            "PYTHONUNBUFFERED": "1",
        }
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "medcp",
        cwd=repository_root,
        env=environment,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    peer = StdioPeer(process)
    try:
        yield peer
    finally:
        if process.stdin is not None:
            process.stdin.close()
            try:
                await process.stdin.wait_closed()
            except (BrokenPipeError, ConnectionResetError):
                pass
        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except TimeoutError:
            process.terminate()
            await process.wait()
        assert process.stdout is not None
        assert process.stderr is not None
        peer.trailing_stdout = await process.stdout.read()
        peer.stderr = await process.stderr.read()


def assert_successful_response(response: dict[str, Any], request_id: int) -> Any:
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == request_id
    assert "error" not in response
    return response["result"]


def assert_clean_shutdown(peer: StdioPeer) -> None:
    assert peer.process.returncode == 0, peer.stderr.decode(errors="replace")
    assert peer.trailing_stdout == b"", (
        "Unexpected non-protocol output on stdout: "
        f"{peer.trailing_stdout.decode(errors='replace')}"
    )


@pytest.mark.anyio
async def test_modern_stdio_discover_list_and_call_are_pure_json_lines(
    sham_sqlite_path: Path,
) -> None:
    async with running_stdio_server(sham_sqlite_path) as peer:
        discovered_response = await peer.exchange(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "server/discover",
                "params": {"_meta": MODERN_META},
            }
        )
        discovered = assert_successful_response(discovered_response, 1)
        assert discovered["supportedVersions"] == ["2026-07-28"]
        assert discovered["resultType"] == "complete"
        assert discovered["ttlMs"] == 300_000
        assert discovered["cacheScope"] == "private"
        server_info = discovered["_meta"]["io.modelcontextprotocol/serverInfo"]
        assert server_info["name"] == "MedCP"
        assert server_info["version"] == __version__

        listed_response = await peer.exchange(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {"_meta": MODERN_META},
            }
        )
        listed = assert_successful_response(listed_response, 2)
        assert [tool["name"] for tool in listed["tools"]] == EXPECTED_TOOL_NAMES
        assert listed["resultType"] == "complete"
        assert listed["ttlMs"] == 300_000
        assert listed["cacheScope"] == "private"

        called_response = await peer.exchange(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "MedCP-list_clinical_tables",
                    "arguments": {},
                    "_meta": MODERN_META,
                },
            }
        )
        called = assert_successful_response(called_response, 3)
        assert called["resultType"] == "complete"
        assert called["isError"] is False
        tables = json.loads(called["content"][0]["text"])
        assert "person" in [table["table_name"] for table in tables]

        missing_meta = await peer.exchange(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/list",
                "params": {},
            }
        )
        assert missing_meta["id"] == 4
        assert missing_meta["error"]["code"] == -32602

        unsupported_meta = {
            **MODERN_META,
            "io.modelcontextprotocol/protocolVersion": "2099-01-01",
        }
        unsupported_version = await peer.exchange(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/list",
                "params": {"_meta": unsupported_meta},
            }
        )
        assert unsupported_version["id"] == 5
        assert unsupported_version["error"]["code"] == -32022

    assert len(peer.raw_lines) == 5
    assert_clean_shutdown(peer)


@pytest.mark.anyio
async def test_legacy_stdio_initialize_list_and_call_omit_modern_result_fields(
    sham_sqlite_path: Path,
) -> None:
    async with running_stdio_server(sham_sqlite_path) as peer:
        initialized_response = await peer.exchange(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "medcp-legacy-tests",
                        "version": "1.0",
                    },
                },
            }
        )
        initialized = assert_successful_response(initialized_response, 1)
        assert initialized["protocolVersion"] == "2025-11-25"
        assert initialized["serverInfo"]["name"] == "MedCP"
        assert initialized["serverInfo"]["version"] == __version__

        await peer.send(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )

        listed_response = await peer.exchange(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            }
        )
        listed = assert_successful_response(listed_response, 2)
        assert [tool["name"] for tool in listed["tools"]] == EXPECTED_TOOL_NAMES
        assert "resultType" not in listed
        assert "ttlMs" not in listed
        assert "cacheScope" not in listed

        called_response = await peer.exchange(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "MedCP-list_clinical_tables",
                    "arguments": {},
                },
            }
        )
        called = assert_successful_response(called_response, 3)
        assert called["isError"] is False
        tables = json.loads(called["content"][0]["text"])
        assert "person" in [table["table_name"] for table in tables]
        assert "resultType" not in called
        assert "ttlMs" not in called
        assert "cacheScope" not in called

    assert len(peer.raw_lines) == 3
    assert_clean_shutdown(peer)
