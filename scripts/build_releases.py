#!/usr/bin/env python3
"""
Build MedCP's official integration artifacts from the shared core.

Single source of truth is ``src/medcp/``. This script copies that core into the
targets that need a self-contained package, then zips each artifact into
``releases/MedCP v<major.minor>/``:

  * MedCP.brxt                       Biorouter extension
  * medcp-claude-code-plugin.zip     Claude Code plugin
  * medcp-codex.zip                  Codex CLI MCP server (config + installer)
  * INSTALL.md                       per-OS install instructions
  * checksums.txt                    sha256 of the artifacts above

Usage:
    python3 scripts/build_releases.py                # build everything
    python3 scripts/build_releases.py --only biorouter
    python3 scripts/build_releases.py --skip-lock    # don't run `uv lock`
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORE = REPO / "src" / "medcp"
INTEGRATIONS = REPO / "integrations"

# Read the version from the core package so it stays in lock-step.
def _version() -> str:
    text = (CORE / "__init__.py").read_text()
    for line in text.splitlines():
        if line.strip().startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("could not determine __version__ from src/medcp/__init__.py")


VERSION = _version()
RELEASE_DIR = REPO / "releases" / f"MedCP v{'.'.join(VERSION.split('.')[:2])}"

EXCLUDE_DIRS = {".venv", "__pycache__", ".git", ".mypy_cache", ".pytest_cache"}
EXCLUDE_SUFFIXES = {".pyc"}


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
    shutil.copyfile(CORE / "server.py", dest)
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


def write_checksums(artifacts) -> None:
    lines = []
    for art in artifacts:
        if art and art.exists():
            digest = hashlib.sha256(art.read_bytes()).hexdigest()
            size_mb = art.stat().st_size / 1_048_576
            lines.append(f"{digest}  {art.name}  ({size_mb:.2f} MiB)")
    (RELEASE_DIR / "checksums.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--only",
        choices=["biorouter", "claude-code", "codex", "all"],
        default="all",
    )
    ap.add_argument("--skip-lock", action="store_true", help="skip `uv lock` for the brxt")
    args = ap.parse_args()

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Building MedCP v{VERSION} artifacts into: {RELEASE_DIR}\n")

    # Always keep the Claude Desktop bundle's server/main.py in sync with the core.
    sync_claude_desktop_server()

    artifacts = []
    if args.only in ("all", "biorouter"):
        artifacts.append(build_biorouter(args.skip_lock))
    if args.only in ("all", "claude-code"):
        artifacts.append(build_claude_code())
    if args.only in ("all", "codex"):
        artifacts.append(build_codex())

    print("\nchecksums:")
    write_checksums(artifacts)
    print(f"\nDone. Artifacts in: {RELEASE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
