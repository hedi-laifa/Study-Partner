#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/backend"

if [ -x ".venv/bin/python" ]; then
  .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
else
  python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
fi
