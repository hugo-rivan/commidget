#!/bin/bash
# Launch commidget using its venv.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/.venv/bin/python" "$DIR/commidget.py"
