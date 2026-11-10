#!/usr/bin/env bash
# Deploy latest strategy to the running bot. Run this on the VM to push changes
# made locally (edit strategy.yaml / code -> git push -> ./deploy.sh here).
set -euo pipefail

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BOT_DIR"

echo "==> Pulling latest..."
git pull --ff-only

echo "==> Syncing dependencies..."
if [ -x venv/bin/pip ]; then
    venv/bin/pip install -q -r requirements.txt
else
    echo "    (no venv found; skipping pip)"
fi

echo "==> Restarting polybot..."
sudo systemctl restart polybot
sleep 2
sudo systemctl --no-pager --lines=8 status polybot || true

echo "==> Done. Live logs: journalctl -u polybot -f"
