#!/bin/bash
# ─── DX-APP Launcher ───
# Usage: ./run.sh [--port PORT]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SUITE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DX_APP_ROOT="${DX_APP_ROOT:-$SUITE_ROOT/dx-runtime/dx_app}"

PORT=8080
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --port|-p) PORT="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [--port PORT]"
      echo "  --port, -p   Server port (default: 8080)"
      exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

export DX_APP_ROOT
cd "$SCRIPT_DIR"

echo "═══════════════════════════════════════════"
echo "  DX-APP"
echo "  Root: $DX_APP_ROOT"
echo "  URL:  http://localhost:$PORT"
echo "═══════════════════════════════════════════"
echo ""

python3 "$SCRIPT_DIR/server.py" --port "$PORT"
