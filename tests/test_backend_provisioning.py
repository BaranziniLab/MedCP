import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def loader_module():
    path = (
        Path(__file__).parents[1]
        / "benchmarks"
        / "sham-dataset"
        / "load_omop.py"
    )
    spec = importlib.util.spec_from_file_location("medcp_test_load_omop", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.closed = False

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.commits = 0
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    "identifier",
    [
        "",
        "starts-with-dash",
        "contains space",
        "1starts_with_digit",
        "name]; DROP TABLE person;--",
        "médcp",
    ],
)
def test_loader_rejects_unsafe_identifiers(loader_module, identifier):
    with pytest.raises(ValueError):
        loader_module.validate_identifier(identifier, "test identifier")


def test_mysql_reader_is_created_with_select_only_grant(
    loader_module,
    monkeypatch,
):
    connection = FakeConnection()
    connect_calls = []

    def fake_connect(**kwargs):
        connect_calls.append(kwargs)
        return connection

    monkeypatch.setitem(
        sys.modules,
        "pymysql",
        SimpleNamespace(connect=fake_connect),
    )
    password = "not-a-real-reader-secret"

    loader_module.create_reader(
        "mysql",
        "db.invalid",
        "admin",
        "not-a-real-admin-secret",
        "omop",
        3306,
        "medcpreader",
        password,
    )

    queries = connection.cursor_instance.executed
    assert [query.split()[0] for query, _ in queries] == [
        "DROP",
        "CREATE",
        "GRANT",
    ]
    assert queries[-1][0].startswith("GRANT SELECT ON `omop`.*")
    assert all(password not in query for query, _ in queries)
    assert queries[1][1] == ("medcpreader", "%", password)
    assert connect_calls[0]["autocommit"] is False
    assert connection.commits == 1
    assert connection.closed is True


def test_mssql_reader_is_created_with_select_only_grant(
    loader_module,
    monkeypatch,
):
    connections = [FakeConnection(), FakeConnection(), FakeConnection()]
    connect_calls = []

    def fake_connect(**kwargs):
        connect_calls.append(kwargs)
        return connections[len(connect_calls) - 1]

    monkeypatch.setitem(
        sys.modules,
        "pymssql",
        SimpleNamespace(connect=fake_connect),
    )
    password = "not-a-real-reader-secret"

    loader_module.create_reader(
        "mssql",
        "db.invalid",
        "admin",
        "not-a-real-admin-secret",
        "omop",
        1433,
        "medcpreader",
        password,
    )

    database_drop, master_login, database_grant = connections
    all_queries = [
        item
        for connection in connections
        for item in connection.cursor_instance.executed
    ]
    assert all(password not in query for query, _ in all_queries)
    assert master_login.cursor_instance.executed[1][1] == (
        "medcpreader",
        password,
    )
    assert database_grant.cursor_instance.executed[-1][0] == (
        "GRANT SELECT TO [medcpreader]"
    )
    assert database_drop.commits == 1
    assert database_grant.commits == 1
    assert connect_calls[1]["database"] == "master"
    assert connect_calls[1]["autocommit"] is True
    assert all(connection.closed for connection in connections)
