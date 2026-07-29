# Release artifacts

The current checked-in release is
[MedCP v0.10.0](MedCP%20v0.10.0/), built against the official
`mcp==2.0.0` Python SDK.

Only the current release artifacts are kept in the working tree. Superseded
artifacts remain recoverable from the repository's Git history and, where
published, from the [GitHub Releases
page](https://github.com/BaranziniLab/MedCP/releases) and version tags.

Do not edit packaged artifacts by hand. Rebuild them from the canonical sources
with:

```bash
python3 scripts/build_releases.py
```

The bundled `MedCP.mcpb` contains a macOS Apple-silicon Python runtime. See the
current release's `INSTALL.md` for platform-specific installation guidance.
