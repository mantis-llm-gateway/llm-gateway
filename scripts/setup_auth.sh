#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

exec uv --directory "$ROOT_DIR/gateway" run python "$SCRIPT_DIR/setup_auth.py" "$@"
