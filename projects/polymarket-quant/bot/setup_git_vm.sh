#!/usr/bin/env bash
# One-time VM migration: move the bot from manual tarball uploads to a git
# checkout so future changes are just `git pull` (or ./deploy.sh).
#
# Run ON THE VM, as the normal user (it calls sudo internally):
#     bash setup_git_vm.sh
#
# It preserves your existing .env (secrets) and trades.db.
set -euo pipefail

REPO_URL="https://github.com/ParthG60/analysis-projects.git"
SPARSE_PATH="projects/polymarket-quant/bot"
REPO_DIR="$HOME/polybot-repo"
BOT_DIR="$REPO_DIR/$SPARSE_PATH"

echo "==> Stopping existing service (if any)..."
sudo systemctl stop polybot 2>/dev/null || true

echo "==> Installing git + python tooling..."
sudo apt-get update -y -qq
sudo apt-get install -y -qq git python3 python3-venv python3-pip

# Preserve secrets / ledger from the old flat layout (~/config.py, ~/.env, ...)
OLD_ENV="$HOME/.env"
OLD_DB="$HOME/trades.db"

if [ ! -d "$REPO_DIR/.git" ]; then
    echo "==> Cloning repo (sparse: $SPARSE_PATH)..."
    git clone --filter=blob:none --no-checkout "$REPO_URL" "$REPO_DIR"
    git -C "$REPO_DIR" sparse-checkout init --cone
    git -C "$REPO_DIR" sparse-checkout set "$SPARSE_PATH"
    DEFAULT_BRANCH="$(git -C "$REPO_DIR" remote show origin | sed -n 's/.*HEAD branch: //p')"
    [ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=main
    git -C "$REPO_DIR" checkout "$DEFAULT_BRANCH"
else
    echo "==> Updating existing checkout..."
    git -C "$REPO_DIR" sparse-checkout set "$SPARSE_PATH"
    git -C "$REPO_DIR" pull --ff-only
fi

cd "$BOT_DIR"

echo "==> Setting up venv + deps..."
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt

echo "==> Restoring secrets / ledger from old layout..."
if [ -f "$OLD_ENV" ]; then cp -n "$OLD_ENV" .env; fi
if [ -f "$OLD_DB" ];  then cp -n "$OLD_DB" trades.db; fi
chmod 600 .env 2>/dev/null || true

echo "==> Writing systemd service..."
sudo tee /etc/systemd/system/polybot.service > /dev/null <<EOF
[Unit]
Description=Polymarket Soccer Quantitative Autotrader
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$BOT_DIR
ExecStart=$BOT_DIR/venv/bin/python run.py --live --interval 900
Restart=always
RestartSec=30

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable polybot
sudo systemctl restart polybot
sleep 2
sudo systemctl --no-pager --lines=10 status polybot || true

echo ""
echo "================ Git deploy ready ================"
echo " Bot dir:    $BOT_DIR"
echo " Tune:       edit $BOT_DIR/strategy.yaml, then: cd $BOT_DIR && ./deploy.sh"
echo " Live logs:  journalctl -u polybot -f"
echo "=================================================="
