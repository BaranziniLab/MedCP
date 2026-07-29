#!/usr/bin/env python3
"""
Build MedCP's official integration artifacts from the shared core.

Single source of truth is ``src/medcp/``. This script copies that core into the
targets that need a self-contained package, then zips each artifact into
``releases/MedCP v<version>/``:

  * MedCP.brxt                       Biorouter extension
  * medcp-claude-code-plugin.zip     Claude Code plugin
  * medcp-codex.zip                  Codex CLI MCP server (config + installer)
  * MedCP.mcpb                       Claude Desktop bundle (macOS arm64)
  * INSTALL.md                       per-OS install instructions
  * checksums.txt                    sha256 of the artifacts above

Usage:
    python3 scripts/build_releases.py                # build everything
    python3 scripts/build_releases.py --only biorouter
    python3 scripts/build_releases.py --only mcpb
    python3 scripts/build_releases.py --skip-lock    # don't run `uv lock`
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORE = REPO / "src" / "medcp"
INTEGRATIONS = REPO / "integrations"
INSTALL_TEMPLATE = REPO / "scripts" / "INSTALL.md.in"
MCPB_PYTHON = REPO / ".python" / "bin" / "python3.12"

# Read the version from the core package so it stays in lock-step.
def _version() -> str:
    text = (CORE / "_version.py").read_text()
    for line in text.splitlines():
        if line.strip().startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("could not determine __version__ from src/medcp/_version.py")


VERSION = _version()
RELEASE_DIR = REPO / "releases" / f"MedCP v{VERSION}"

RELEASE_ARTIFACT_NAMES = (
    "MedCP.brxt",
    "medcp-claude-code-plugin.zip",
    "medcp-codex.zip",
    "MedCP.mcpb",
)

EXCLUDE_DIRS = {".venv", "__pycache__", ".git", ".mypy_cache", ".pytest_cache"}
EXCLUDE_SUFFIXES = {".pyc"}


def _project_version(path: Path) -> str:
    try:
        value = tomllib.loads(path.read_text())["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        raise SystemExit(f"could not read project.version from {path.relative_to(REPO)}: {exc}") from exc
    if not isinstance(value, str):
        raise SystemExit(f"project.version in {path.relative_to(REPO)} must be a string")
    return value


def _json_version(path: Path, *keys: str | int) -> str:
    try:
        value = json.loads(path.read_text())
        for key in keys:
            value = value[key]
    except (OSError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"could not read version from {path.relative_to(REPO)}: {exc}") from exc
    if not isinstance(value, str):
        raise SystemExit(f"version in {path.relative_to(REPO)} must be a string")
    return value


def validate_version_consistency() -> None:
    sources = {
        CORE / "_version.py": VERSION,
        REPO / "pyproject.toml": _project_version(REPO / "pyproject.toml"),
        INTEGRATIONS / "biorouter" / "pyproject.toml": _project_version(
            INTEGRATIONS / "biorouter" / "pyproject.toml"
        ),
        REPO / "manifest.json": _json_version(REPO / "manifest.json", "version"),
        INTEGRATIONS / "biorouter" / "manifest.json": _json_version(
            INTEGRATIONS / "biorouter" / "manifest.json", "version"
        ),
        INTEGRATIONS / "claude-code" / ".claude-plugin" / "plugin.json": _json_version(
            INTEGRATIONS / "claude-code" / ".claude-plugin" / "plugin.json",
            "version",
        ),
        INTEGRATIONS / ".claude-plugin" / "marketplace.json": _json_version(
            INTEGRATIONS / ".claude-plugin" / "marketplace.json",
            "plugins",
            0,
            "version",
        ),
    }
    mismatches = {path: value for path, value in sources.items() if value != VERSION}
    if mismatches:
        details = "\n".join(
            f"  {path.relative_to(REPO)}: {value!r}" for path, value in mismatches.items()
        )
        raise SystemExit(
            f"version mismatch: expected {VERSION!r} from src/medcp/_version.py, found:\n{details}"
        )


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if any(part in EXCLUDE_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix in EXCLUDE_SUFFIXES:
            continue
        yield path


def _zip(out: Path, base: Path, files) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, f.relative_to(base).as_posix())


def _copy_core_into(dest_pkg: Path) -> None:
    """Copy src/medcp into <dest>/medcp (overwriting)."""
    if dest_pkg.exists():
        shutil.rmtree(dest_pkg)
    dest_pkg.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        CORE,
        dest_pkg,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def sync_claude_desktop_server() -> None:
    """Regenerate the Claude Desktop bundle's standalone server/main.py from the core.

    The .mcpb bundle runs server/main.py with its own embedded Python runtime, so
    it can't import the installed `medcp` package — it needs a self-contained copy
    of the server module. Keeping it a generated mirror avoids drift. (The .mcpb
    itself is packaged separately with `mcpb pack`.)
    """
    dest = REPO / "server" / "main.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = (CORE / "server.py").read_text()
    version_import = "from medcp._version import __version__"
    if version_import not in source:
        raise SystemExit("could not find MedCP version import in src/medcp/server.py")
    # The MCPB runs server/main.py as a standalone module and deliberately does
    # not install the MedCP package. Embed the same single-source version literal
    # while generating that mirror.
    source = source.replace(version_import, f'__version__ = "{VERSION}"', 1)
    dest.write_text(source)
    print(f"[claude-desktop] synced {dest.relative_to(REPO)} from core")


def build_biorouter(skip_lock: bool) -> Path:
    src_dir = INTEGRATIONS / "biorouter"
    print(f"[biorouter] copying core → {src_dir / 'src' / 'medcp'}")
    _copy_core_into(src_dir / "src" / "medcp")

    if not skip_lock and shutil.which("uv"):
        print("[biorouter] uv lock (verifying dependency resolution)…")
        subprocess.run(["uv", "lock"], cwd=src_dir, check=True)
    elif not skip_lock:
        print("[biorouter] WARNING: uv not found; skipping uv lock")

    include = ["manifest.json", "README.md", "pyproject.toml", "src", "skills"]
    if (src_dir / "uv.lock").exists():
        include.append("uv.lock")
    files = []
    for name in include:
        p = src_dir / name
        if p.is_dir():
            files.extend(_iter_files(p))
        elif p.exists():
            files.append(p)
    out = RELEASE_DIR / "MedCP.brxt"
    _zip(out, src_dir, files)
    print(f"[biorouter] → {out}")
    return out


def build_claude_code() -> Path:
    src_dir = INTEGRATIONS / "claude-code"
    files = list(_iter_files(src_dir))
    out = RELEASE_DIR / "medcp-claude-code-plugin.zip"
    _zip(out, src_dir, files)
    print(f"[claude-code] → {out}")
    return out


def build_codex() -> Path:
    src_dir = INTEGRATIONS / "codex"
    files = list(_iter_files(src_dir))
    out = RELEASE_DIR / "medcp-codex.zip"
    _zip(out, src_dir, files)
    print(f"[codex] → {out}")
    return out


def build_mcpb() -> Path:
    """Synchronize the embedded runtime and build the Claude Desktop bundle.

    The checked-in runtime is intentionally a macOS Apple-silicon CPython
    distribution. Other platforms must build and publish their own native MCPB
    artifact instead of relabeling this one.
    """
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise SystemExit(
            "MedCP.mcpb must be built on macOS arm64 for the bundled runtime"
        )
    if not MCPB_PYTHON.is_file():
        raise SystemExit(f"embedded Python not found: {MCPB_PYTHON.relative_to(REPO)}")
    for command in ("uv", "mcpb"):
        if not shutil.which(command):
            raise SystemExit(f"{command!r} is required to build MedCP.mcpb")

    with tempfile.TemporaryDirectory(prefix="medcp-mcpb-") as temp_dir:
        requirements = Path(temp_dir) / "requirements.txt"
        print("[claude-desktop] exporting locked production dependencies…")
        subprocess.run(
            [
                "uv",
                "export",
                "--quiet",
                "--frozen",
                "--no-dev",
                "--no-emit-project",
                "--no-header",
                "--no-annotate",
                "--format",
                "requirements.txt",
                "--output-file",
                str(requirements),
            ],
            cwd=REPO,
            check=True,
        )
        print("[claude-desktop] synchronizing embedded Python runtime…")
        subprocess.run(
            [
                "uv",
                "pip",
                "sync",
                "--python",
                str(MCPB_PYTHON),
                str(requirements),
            ],
            cwd=REPO,
            check=True,
        )

    subprocess.run(
        [
            str(MCPB_PYTHON),
            "-c",
            (
                "import importlib.util; "
                "from mcp.server import MCPServer; "
                "from mcp.types import CallToolResult; "
                "assert importlib.util.find_spec('fastmcp') is None"
            ),
        ],
        cwd=REPO,
        check=True,
    )
    subprocess.run(["mcpb", "validate", "manifest.json"], cwd=REPO, check=True)

    out = RELEASE_DIR / "MedCP.mcpb"
    if out.exists():
        out.unlink()
    subprocess.run(["mcpb", "pack", ".", str(out)], cwd=REPO, check=True)
    subprocess.run(["mcpb", "info", str(out)], cwd=REPO, check=True)
    print(f"[claude-desktop] → {out}")
    return out


def write_install_guide() -> None:
    if not INSTALL_TEMPLATE.is_file():
        raise SystemExit(f"install guide template not found: {INSTALL_TEMPLATE.relative_to(REPO)}")
    text = INSTALL_TEMPLATE.read_text().replace("@VERSION@", VERSION)
    (RELEASE_DIR / "INSTALL.md").write_text(text)


def write_checksums() -> None:
    artifacts = [
        RELEASE_DIR / name
        for name in RELEASE_ARTIFACT_NAMES
        if (RELEASE_DIR / name).is_file()
    ]
    lines = []
    for art in artifacts:
        digest = hashlib.sha256(art.read_bytes()).hexdigest()
        lines.append(f"{digest}  {art.name}")
    (RELEASE_DIR / "checksums.txt").write_text("\n".join(lines) + "\n")
    for line, art in zip(lines, artifacts):
        size_mb = art.stat().st_size / 1_048_576
        print(f"{line}  ({size_mb:.2f} MiB)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--only",
        choices=["biorouter", "claude-code", "codex", "mcpb", "all"],
        default="all",
    )
    ap.add_argument("--skip-lock", action="store_true", help="skip `uv lock` for the brxt")
    args = ap.parse_args()

    validate_version_consistency()
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Building MedCP v{VERSION} artifacts into: {RELEASE_DIR}\n")

    # Always keep the Claude Desktop bundle's server/main.py in sync with the core.
    sync_claude_desktop_server()

    if args.only in ("all", "biorouter"):
        build_biorouter(args.skip_lock)
    if args.only in ("all", "claude-code"):
        build_claude_code()
    if args.only in ("all", "codex"):
        build_codex()
    if args.only in ("all", "mcpb"):
        build_mcpb()

    write_install_guide()
    print("\nchecksums:")
    write_checksums()
    print(f"\nDone. Artifacts in: {RELEASE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
