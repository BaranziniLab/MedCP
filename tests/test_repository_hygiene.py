from __future__ import annotations

import re
import subprocess
import unicodedata
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WINDOWS_RESERVED_NAME = re.compile(
    r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$",
    re.IGNORECASE,
)
WINDOWS_INVALID_CHARS = frozenset('<>:"\\|?*')


def _tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return [
        path
        for path in result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
        if path
    ]


def test_tracked_paths_are_portable_to_windows() -> None:
    violations: list[str] = []
    normalized_paths: dict[str, str] = {}

    for path in _tracked_paths():
        components = path.split("/")
        for component in components:
            windows_name = component.rstrip(" .")
            if windows_name != component:
                violations.append(f"{path}: component ends with a dot or space")
            if any(character in WINDOWS_INVALID_CHARS for character in component):
                violations.append(f"{path}: component contains a Windows-invalid character")
            if WINDOWS_RESERVED_NAME.fullmatch(windows_name):
                violations.append(f"{path}: component is a reserved Windows device name")

        collision_key = "/".join(
            unicodedata.normalize("NFC", component).rstrip(" .").casefold()
            for component in components
        )
        previous = normalized_paths.setdefault(collision_key, path)
        if previous != path:
            violations.append(
                f"{path}: collides with {previous!r} on a case-insensitive filesystem"
            )

    assert not violations, "Tracked paths are not Windows-portable:\n" + "\n".join(
        sorted(set(violations))
    )
