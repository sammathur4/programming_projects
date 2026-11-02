#!/usr/bin/env bash
# Start Mission 2026 — Django serves BOTH the REST API and the Flutter web app,
# so the whole site lives on one port and one origin (no CORS, no second server).
#
#   ./run_server.sh              # http://localhost:8000/
#   ./run_server.sh 9000         # http://localhost:9000/
#
# The Flutter build is read from mission_app/build/web. If you change the
# Flutter code, rebuild with:
#   cd mission_app && flutter build web --release
# then just reload the page — no server restart needed.
set -e
cd "$(dirname "$0")/server"
PORT="${1:-8000}"
WEB_DIR="$(cd .. && pwd)/mission_app/build/web"

if [ -f "$WEB_DIR/index.html" ]; then
  echo "Mission 2026"
  echo "  app  → http://localhost:${PORT}/"
  echo "  api  → http://localhost:${PORT}/api/"
  echo "  admin→ http://localhost:${PORT}/admin/"
  echo "  (flutter build: $WEB_DIR)"
else
  echo "Mission 2026 API only — no Flutter build at $WEB_DIR"
  echo "  build it with:  cd mission_app && flutter build web --release"
  echo "  api  → http://localhost:${PORT}/api/"
fi

exec ../.venv/bin/python manage.py runserver "0.0.0.0:${PORT}"
