#!/bin/bash
# Gateway-Prasena Installation Script
# For Raspberry Pi Zero 2W (Debian/Raspbian)

set -e  # Exit on error

echo "======================================"
echo "Gateway-Prasena Installation"
echo "======================================"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "ERROR: Do not run as root. Run as normal user with sudo access."
    exit 1
fi

# Variables
INSTALL_DIR="/home/$USER/Gateway-Prasena"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_USER="$USER"

# Step 1: Update system
echo ""
echo "[1/8] Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Step 2: Install system dependencies
echo ""
echo "[2/8] Installing system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    pigpio \
    git \
    sqlite3

# Step 3: Enable and start pigpiod (for battery sensors)
echo ""
echo "[3/8] Setting up pigpiod..."
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
echo "pigpiod status:"
sudo systemctl status pigpiod --no-pager | head -5

# Step 4: Create installation directory
echo ""
echo "[4/8] Creating installation directory..."
if [ -d "$INSTALL_DIR" ]; then
    echo "WARNING: Directory $INSTALL_DIR already exists"
    read -p "Remove existing directory? (y/N): " confirm
    if [ "$confirm" = "y" ]; then
        rm -rf "$INSTALL_DIR"
    else
        echo "Installation cancelled"
        exit 1
    fi
fi

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Step 5: Clone repository
echo ""
echo "[5/8] Cloning repository..."
# Copy files from current directory
if [ -d "/Users/maulanaahmad/Documents/Gateway-Prasena" ]; then
    echo "Copying from development directory..."
    cp -r /Users/maulanaahmad/Documents/Gateway-Prasena/* "$INSTALL_DIR/"
else
    # Or clone from git
    read -p "Enter git repository URL: " repo_url
    git clone "$repo_url" "$INSTALL_DIR"
fi

# Step 6: Create virtual environment
echo ""
echo "[6/8] Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Step 7: Install Python dependencies
echo ""
echo "[7/8] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Step 8: Create data and log directories
echo ""
echo "[8/9] Creating data and log directories..."
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/logs"

# Set permissions
chmod 755 "$INSTALL_DIR"
chmod 755 "$INSTALL_DIR/data"
chmod 755 "$INSTALL_DIR/logs"

# Step 9: Generate configuration file
echo ""
echo "[9/9] Configuring system..."
CONFIG_FILE="$INSTALL_DIR/weatherstation/config/system_config.yaml"
EXAMPLE_FILE="$INSTALL_DIR/weatherstation/config/system_config.yaml.example"

if [ -f "$CONFIG_FILE" ]; then
    echo "✓ Config file already exists: $CONFIG_FILE"

    # Validate existing config
    echo "  Validating existing configuration..."
    if python3 -c "import yaml; yaml.safe_load(open('$CONFIG_FILE'))" 2>/dev/null; then
        echo "  ✓ Config valid, keeping existing settings"
        CONFIG_NEEDS_EDIT=0
    else
        echo "  ⚠️  WARNING: Existing config has YAML syntax errors!"
        echo "  Creating backup: $CONFIG_FILE.backup"
        cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
        echo "  Regenerating config..."
        REGENERATE_CONFIG=1
    fi
else
    echo "Config not found, generating new configuration..."
    REGENERATE_CONFIG=1
fi

if [ "${REGENERATE_CONFIG:-0}" -eq 1 ]; then
    # Generate config via Python
    if python3 -m weatherstation.config.config_generator "$CONFIG_FILE" 2>&1; then
        echo "✓ Config generated successfully: $CONFIG_FILE"
        CONFIG_NEEDS_EDIT=1
    else
        echo "❌ ERROR: Config generation failed"
        echo ""
        echo "Fallback option:"
        echo "  cp $EXAMPLE_FILE $CONFIG_FILE"
        echo "  nano $CONFIG_FILE"
        echo ""
        exit 1
    fi
fi

echo ""
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""

if [ "${CONFIG_NEEDS_EDIT:-0}" -eq 1 ]; then
    echo "⚠️  IMPORTANT: Edit configuration before starting:"
    echo ""
    echo "  nano $CONFIG_FILE"
    echo ""
    echo "  Required changes:"
    echo "    1. mqtt.password (currently: CHANGE_ME)"
    echo "    2. upload.api_key (currently: CHANGE_ME)"
    echo ""
    echo "  Optional changes:"
    echo "    - system.location (physical location)"
    echo ""
fi

echo "Next steps:"
echo "1. Edit configuration (if needed): nano $CONFIG_FILE"
echo "2. Validate configuration: $VENV_DIR/bin/python3 -m weatherstation.config.config_validator $CONFIG_FILE"
echo "3. Initialize database: cd $INSTALL_DIR && $VENV_DIR/bin/python3 -m weatherstation.main --init-db"
echo "4. Register devices: cd $INSTALL_DIR && $VENV_DIR/bin/python3 -m weatherstation.main --register-device"
echo "5. Install systemd service: sudo bash $INSTALL_DIR/scripts/setup_systemd.sh"
echo ""
echo "Installation directory: $INSTALL_DIR"
echo "Virtual environment: $VENV_DIR"
echo "Configuration: $CONFIG_FILE"
echo ""
