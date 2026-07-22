#!/usr/bin/env bash
# Register MedCP as an MCP server in the Codex CLI (~/.codex/config.toml).
#
# It reads MedCP's environment variables from the current shell (or an --env-file
# you point it at) and calls `codex mcp add`. The server launches the shared
# `medcp` core with uvx — identical to every other MedCP target.
#
# Usage:
#   ./install.sh                          # use env vars already exported
#   ./install.sh --env-file ../../.env    # load them from a .env file first
#   MEDCP_SOURCE=/path/to/MedCP ./install.sh   # run a local core instead of the pinned release
#
set -euo pipefail

NAME="medcp"
SOURCE="${MEDCP_SOURCE:-git+https://github.com/BaranziniLab/MedCP@v0.8.0}"

# Optionally load a .env file.
if [[ "${1:-}" == "--env-file" && -n "${2:-}" ]]; then
  echo "Loading environment from $2"
  set -a
  # shellcheck disable=SC1090
  source "$2"
  set +a
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "error: 'codex' CLI not found on PATH" >&2
  exit 1
fi
if ! command -v uvx >/dev/null 2>&1; then
  echo "error: 'uvx' (from uv) not found on PATH — install uv: https://docs.astral.sh/uv/" >&2
  exit 1
fi

# Collect the MedCP env vars that are actually set into --env KEY=VALUE flags.
ENV_FLAGS=()
for key in \
  CLINICAL_RECORDS_BACKEND CLINICAL_RECORDS_SQLITE_PATH \
  CLINICAL_RECORDS_SERVER CLINICAL_RECORDS_DATABASE \
  CLINICAL_RECORDS_USERNAME CLINICAL_RECORDS_PASSWORD CLINICAL_RECORDS_PORT \
  KNOWLEDGE_GRAPH_URI KNOWLEDGE_GRAPH_USERNAME KNOWLEDGE_GRAPH_PASSWORD KNOWLEDGE_GRAPH_DATABASE \
  MEDCP_NAMESPACE MEDCP_LOG_LEVEL
do
  if [[ -n "${!key:-}" ]]; then
    ENV_FLAGS+=(--env "${key}=${!key}")
  fi
done

echo "Registering Codex MCP server '${NAME}' (source: ${SOURCE})"
codex mcp remove "${NAME}" >/dev/null 2>&1 || true
codex mcp add "${NAME}" "${ENV_FLAGS[@]}" -- uvx --from "${SOURCE}" medcp

echo
echo "Done. Verify with:  codex mcp get ${NAME}"
echo "MedCP tools will be available the next time you start Codex."
