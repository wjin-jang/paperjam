#!/bin/bash
# PaperJam Web — Local update script
# Pulls latest from GitHub and restarts the service.
#
# Usage: /opt/paperjam-web/update.sh

set -euo pipefail

REPO_DIR="/opt/paperjam-web"
WEB_DIR="${REPO_DIR}/web"
BRANCH="claude/paperjam-web-pwa-gWrkR"

echo "=== PaperJam Web Update ==="

cd "${REPO_DIR}"

echo "[1/3] Pulling latest from ${BRANCH}..."
git pull origin "${BRANCH}"

echo "[2/3] Installing dependencies..."
"${WEB_DIR}/venv/bin/pip" install -q -r "${WEB_DIR}/requirements.txt"

echo "[3/3] Restarting server..."
sudo systemctl restart paperjam-web

echo ""
echo "=== Update complete ==="
sudo systemctl status paperjam-web --no-pager -l || true