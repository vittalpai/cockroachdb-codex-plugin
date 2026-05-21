#!/bin/sh
set -eu

if [ -f "./.env" ]; then
  set -a
  . "./.env"
  set +a
fi

if [ -x "./.venv/bin/python" ]; then
  exec "./.venv/bin/python" "scripts/cockroachdb_mcp_server.py"
fi

exec "python3" "scripts/cockroachdb_mcp_server.py"
