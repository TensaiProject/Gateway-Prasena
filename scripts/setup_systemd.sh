#!/bin/bash
# Setup systemd service for Gateway-Prasena
# Run with: sudo bash setup_systemd.sh

set -e

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo bash setup_systemd.sh)"
    exit 1
fi

# Get actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
INSTALL_DIR="/home/$ACTUAL_USER/Gateway-Prasena"

echo "======================================"
echo "Gateway-Prasena Systemd Setup"
echo "======================================"
echo "Install directory: $INSTALL_DIR"
echo "Service user: $ACTUAL_USER"
echo ""

# Check if installation directory exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo "ERROR: Installation directory not found: $INSTALL_DIR"
    echo "Run install.sh first!"
    exit 1
fi

# Step 1: Update systemd service file
echo "[1/4] Creating systemd service file..."

cat > /etc/systemd/system/weatherstation.service <<EOF
[Unit]
Description=Weather Station Gateway (All Services)
Documentation=https://github.com/TensaiProject/Gateway-Prasena
After=network.target pigpiod.service
Requires=pigpiod.service

[Service]
Type=simple
User=$ACTUAL_USER
Group=$ACTUAL_USER
WorkingDirectory=$INSTALL_DIR

# Environment
Environment="PATH=$INSTALL_DIR/venv/bin"
Environment="PYTHONUNBUFFERED=1"

# Run all services in single process (multi-threaded)
ExecStart=$INSTALL_DIR/venv/bin/python3 -m weatherstation.main --service all --config $INSTALL_DIR/weatherstation/config/system_config.yaml

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=0

# Resource limits (for Pi Zero 2W - 512MB RAM, 4 cores)
MemoryLimit=384M
CPUQuota=400%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=weatherstation

# Security
NoNewPrivileges=true
PrivateTmp=true

# Graceful shutdown
TimeoutStopSec=30
KillMode=mixed
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
EOF

echo "Created: /etc/systemd/system/weatherstation.service"

# Step 2: Create cleanup service and timer
echo ""
echo "[2/4] Creating cleanup service..."

cat > /etc/systemd/system/weatherstation-cleanup.service <<EOF
[Unit]
Description=Weather Station Data Cleanup Service
After=network.target

[Service]
Type=oneshot
User=$ACTUAL_USER
Group=$ACTUAL_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python3 -m weatherstation.main --service cleanup --config $INSTALL_DIR/weatherstation/config/system_config.yaml

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=weatherstation-cleanup

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/weatherstation-cleanup.timer <<EOF
[Unit]
Description=Weather Station Cleanup Timer (Daily)

[Timer]
OnCalendar=daily
OnBootSec=10min
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo "Created: /etc/systemd/system/weatherstation-cleanup.service"
echo "Created: /etc/systemd/system/weatherstation-cleanup.timer"

# Step 3: Reload systemd
echo ""
echo "[3/4] Reloading systemd daemon..."
systemctl daemon-reload

# Step 4: Enable services
echo ""
echo "[4/4] Enabling services..."
systemctl enable weatherstation.service
systemctl enable weatherstation-cleanup.timer

echo ""
echo "======================================"
echo "Systemd Setup Complete!"
echo "======================================"
echo ""
echo "Services installed:"
echo "  - weatherstation.service (main gateway)"
echo "  - weatherstation-cleanup.service (cleanup)"
echo "  - weatherstation-cleanup.timer (daily cleanup)"
echo ""
echo "Commands:"
echo "  Start:   sudo systemctl start weatherstation"
echo "  Stop:    sudo systemctl stop weatherstation"
echo "  Status:  sudo systemctl status weatherstation"
echo "  Logs:    sudo journalctl -u weatherstation -f"
echo "  Restart: sudo systemctl restart weatherstation"
echo ""
echo "Auto-start on boot: ENABLED"
echo ""
