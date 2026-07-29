from pathlib import Path

import pytest

from medcp.server import ClinicalRecordsConfig, create_medcp_server, MedCPConfig


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SHAM_SQLITE = (
    REPOSITORY_ROOT
    / "benchmarks"
    / "sham-dataset"
    / "sqlite"
    / "sham_mimic_omop.sqlite"
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def sham_sqlite_path() -> Path:
    assert SHAM_SQLITE.is_file(), f"Missing sham SQLite fixture: {SHAM_SQLITE}"
    return SHAM_SQLITE


@pytest.fixture
def medcp_server(sham_sqlite_path: Path):
    config = MedCPConfig(
        clinical_records=ClinicalRecordsConfig(
            backend="sqlite",
            sqlite_path=str(sham_sqlite_path),
        ),
        namespace="MedCP",
        log_level="ERROR",
    )
    return create_medcp_server(config)
