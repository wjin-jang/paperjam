#!/usr/bin/env bash
# PaperJam Web — Deployment script
# Deploys to music.jangnet.cc via SSH as woojin
#
# Usage: ./deploy.sh [--setup]
#   --setup    First-time setup (install deps, create venv, configure nginx)
#   (no args)  Update deployment with latest code

set -euo pipefail

REMOTE_USER="woojin"
REMOTE_HOST="ssh.jangnet.cc"
REMOTE_PORT=2222
REMOTE_DIR="/opt/paperjam-web"
SSH_CMD="ssh -p ${REMOTE_PORT} ${REMOTE_USER}@${REMOTE_HOST}"
SCP_CMD="scp -P ${REMOTE_PORT}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== PaperJam Web Deploy ==="
echo "Target: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PORT}"
echo ""

# Test SSH connection
echo "[1/5] Testing SSH connection..."
if ! ${SSH_CMD} "echo 'Connected'" 2>/dev/null; then
    echo "ERROR: Cannot connect to ${REMOTE_HOST}:${REMOTE_PORT}"
    echo "Make sure you have SSH key access configured:"
    echo "  ssh -p ${REMOTE_PORT} ${REMOTE_USER}@${REMOTE_HOST}"
    exit 1
fi

if [[ "${1:-}" == "--setup" ]]; then
    echo ""
    echo "=== First-time Setup ==="
    echo ""

    # Install system dependencies
    echo "[2/5] Installing system dependencies..."
    ${SSH_CMD} "sudo apt update && sudo apt install -y \
        python3 python3-venv python3-pip \
        ffmpeg \
        nginx \
        certbot python3-certbot-nginx"

    # Create application directory
    echo "[3/5] Creating application directory..."
    ${SSH_CMD} "sudo mkdir -p ${REMOTE_DIR} && sudo chown ${REMOTE_USER}:${REMOTE_USER} ${REMOTE_DIR}"

    # Upload code
    echo "[4/5] Uploading code..."
    rsync -avz --exclude '__pycache__' --exclude '*.pyc' --exclude 'data/' \
        -e "ssh -p ${REMOTE_PORT}" \
        "${SCRIPT_DIR}/" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

    # Setup virtual environment and install dependencies
    echo "[5/5] Setting up Python environment..."
    ${SSH_CMD} << 'SETUP_EOF'
        cd /opt/paperjam-web
        python3 -m venv venv
        ./venv/bin/pip install --upgrade pip
        ./venv/bin/pip install -r requirements.txt

        # Generate secret key
        SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

        # Install systemd service
        sudo cp systemd/paperjam-web.service /etc/systemd/system/
        sudo sed -i "s/CHANGE_ME_TO_A_RANDOM_SECRET/${SECRET}/" /etc/systemd/system/paperjam-web.service
        sudo systemctl daemon-reload
        sudo systemctl enable paperjam-web

        # Install nginx config
        sudo cp nginx/music.jangnet.cc.conf /etc/nginx/sites-available/music.jangnet.cc
        sudo ln -sf /etc/nginx/sites-available/music.jangnet.cc /etc/nginx/sites-enabled/

        # Get SSL certificate
        echo ""
        echo "Attempting to get SSL certificate..."
        sudo certbot --nginx -d music.jangnet.cc --non-interactive --agree-tos --email admin@jangnet.cc || {
            echo "WARNING: certbot failed. You may need to run it manually:"
            echo "  sudo certbot --nginx -d music.jangnet.cc"
        }

        sudo nginx -t && sudo systemctl reload nginx

        # Start service
        sudo systemctl start paperjam-web

        echo ""
        echo "=== Setup Complete ==="
        echo "PaperJam Web is running at https://music.jangnet.cc"
        echo "Default login: admin / admin"
        echo "** Change the admin password immediately! **"
SETUP_EOF

else
    # Update deployment
    echo "[2/5] Uploading updated code..."
    rsync -avz --exclude '__pycache__' --exclude '*.pyc' --exclude 'data/' \
        -e "ssh -p ${REMOTE_PORT}" \
        "${SCRIPT_DIR}/" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

    echo "[3/5] Updating dependencies..."
    ${SSH_CMD} "cd ${REMOTE_DIR} && ./venv/bin/pip install -r requirements.txt -q"

    echo "[4/5] Restarting service..."
    ${SSH_CMD} "sudo systemctl restart paperjam-web"

    echo "[5/5] Checking status..."
    ${SSH_CMD} "sudo systemctl status paperjam-web --no-pager -l" || true

    echo ""
    echo "=== Deploy Complete ==="
    echo "PaperJam Web updated at https://music.jangnet.cc"
fi
