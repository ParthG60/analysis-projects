#!/usr/bin/env bash
set -e

echo "=== Polymarket Autotrader VPS Setup ==="

# 1. Update system and install Python + venv
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv

# 2. Setup virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Installing python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Test IP safety preflight
echo "Running IP jurisdiction preflight..."
python3 -c "
import config
res = config.verify_public_ip()
print('IP Safety Check:', res['msg'])
if not res['safe']:
    print('WARNING: Server IP is in a RESTRICTED country!')
    exit(1)
print('SUCCESS: Server IP is in an UNRESTRICTED country.')
"

# 4. Configure systemd service
SERVICE_PATH="/etc/systemd/system/polybot.service"
CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)

echo "Configuring systemd service at $SERVICE_PATH..."
cat <<EOF | sudo tee $SERVICE_PATH > /dev/null
[Unit]
Description=Polymarket Soccer Quantitative Autotrader
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python run.py --live --interval 900
Restart=always
RestartSec=30

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable polybot

echo ""
echo "=== Setup Complete! ==="
echo "To start the bot 24/7:     sudo systemctl start polybot"
echo "To view live logs:         journalctl -u polybot -f"
echo "To check status:           sudo systemctl status polybot"
echo "To stop the bot:           sudo systemctl stop polybot"
