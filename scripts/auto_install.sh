#!/bin/bash
# =============================================================================
# Gateway-Prasena Auto Installer
# =============================================================================
# Script untuk install dan setup sistem weatherstation secara otomatis
#
# Usage:
#   curl -sSL <url>/auto_install.sh | bash
#   atau
#   bash auto_install.sh
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="$HOME/Gateway-Prasena"
REPO_URL="https://github.com/TensaiProject/Gateway-Prasena.git"

# Functions
print_header() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}→ $1${NC}"
}

# Check if running as root
check_not_root() {
    if [ "$EUID" -eq 0 ]; then
        print_error "Jangan jalankan script ini sebagai root!"
        print_info "Jalankan sebagai user biasa: bash auto_install.sh"
        exit 1
    fi
}

# =============================================================================
# CLEANUP: Remove development files for production
# =============================================================================
cleanup_for_production() {
    print_header "Cleanup for Production"

    echo "Ini akan menghapus file-file development yang tidak diperlukan:"
    echo ""
    echo "  - node_modules/ dan npm packages"
    echo "  - .npm/ cache"
    echo "  - Claude CLI dan config"
    echo "  - Folder WS1, WS2, WS3 (backup lama)"
    echo "  - __pycache__ dan .pyc files"
    echo "  - .git/ folder (opsional)"
    echo "  - Temporary files"
    echo ""

    read -p "Jalankan cleanup untuk production? (y/N): " do_cleanup

    if [ "$do_cleanup" != "y" ] && [ "$do_cleanup" != "Y" ]; then
        print_info "Cleanup dilewati"
        return
    fi

    print_info "Starting cleanup..."

    # Calculate initial disk usage
    INITIAL_USAGE=$(df -h ~ | awk 'NR==2 {print $3}')

    # Remove Node.js/npm related
    if [ -d "$HOME/node_modules" ]; then
        print_info "Removing ~/node_modules..."
        rm -rf "$HOME/node_modules"
        print_success "Removed node_modules"
    fi

    if [ -d "$HOME/.npm" ]; then
        print_info "Removing ~/.npm cache..."
        rm -rf "$HOME/.npm"
        print_success "Removed .npm cache"
    fi

    if [ -d "$HOME/.nvm" ]; then
        print_info "Removing ~/.nvm..."
        rm -rf "$HOME/.nvm"
        print_success "Removed .nvm"
    fi

    # Remove Claude CLI related
    if [ -d "$HOME/.claude" ]; then
        print_info "Removing ~/.claude..."
        rm -rf "$HOME/.claude"
        print_success "Removed .claude"
    fi

    if [ -f "$HOME/.claude.json" ]; then
        rm -f "$HOME/.claude.json"
        print_success "Removed .claude.json"
    fi

    # Remove old WS folders (backup/test folders)
    for ws_folder in WS1 WS2 WS3; do
        if [ -d "$HOME/$ws_folder" ]; then
            print_info "Removing ~/$ws_folder..."
            rm -rf "$HOME/$ws_folder"
            print_success "Removed $ws_folder"
        fi
    done

    # Remove Python cache files
    print_info "Removing Python cache files..."
    find "$HOME" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$HOME" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$HOME" -type f -name "*.pyo" -delete 2>/dev/null || true
    print_success "Removed Python cache"

    # Remove temporary files
    print_info "Removing temporary files..."
    find "$HOME" -type f -name "*.tmp" -delete 2>/dev/null || true
    find "$HOME" -type f -name "*.log" -path "*/logs/*" -mtime +7 -delete 2>/dev/null || true
    print_success "Removed temporary files"

    # Optional: Remove .git folder
    if [ -d "$INSTALL_DIR/.git" ]; then
        echo ""
        read -p "Hapus .git folder? (tidak bisa git pull lagi) (y/N): " remove_git
        if [ "$remove_git" = "y" ] || [ "$remove_git" = "Y" ]; then
            rm -rf "$INSTALL_DIR/.git"
            print_success "Removed .git folder"
        fi
    fi

    # Remove apt cache
    print_info "Cleaning apt cache..."
    sudo apt clean
    sudo apt autoremove -y
    print_success "Cleaned apt cache"

    # Calculate final disk usage
    FINAL_USAGE=$(df -h ~ | awk 'NR==2 {print $3}')

    echo ""
    print_success "Cleanup complete!"
    echo ""
    echo "  Disk usage before: $INITIAL_USAGE"
    echo "  Disk usage after:  $FINAL_USAGE"
    echo ""
}

# =============================================================================
# STEP 1: System Update & Dependencies
# =============================================================================
install_dependencies() {
    print_header "Step 1/8: Installing System Dependencies"

    print_info "Updating package list..."
    sudo apt update

    print_info "Installing required packages..."
    sudo apt install -y \
        python3-pip \
        python3-venv \
        pigpio \
        git \
        sqlite3 \
        curl

    print_info "Enabling pigpiod service..."
    sudo systemctl enable pigpiod
    sudo systemctl start pigpiod

    print_success "Dependencies installed"
}

# =============================================================================
# STEP 2: Set Hostname
# =============================================================================
setup_hostname() {
    print_header "Step 2/8: Setting Hostname"

    current_hostname=$(hostname)
    print_info "Current hostname: $current_hostname"

    echo ""
    echo -e "${YELLOW}Hostname harus UNIK untuk setiap Raspi!${NC}"
    echo "Contoh: weatherstation1, weatherstation2, weatherstation3"
    echo ""
    read -p "Masukkan hostname baru (atau tekan Enter untuk skip): " new_hostname

    if [ -n "$new_hostname" ]; then
        print_info "Setting hostname to: $new_hostname"
        sudo hostnamectl set-hostname "$new_hostname"

        # Update /etc/hosts
        sudo sed -i "s/127.0.1.1.*/127.0.1.1\t$new_hostname/g" /etc/hosts

        print_success "Hostname set to: $new_hostname"
        print_warning "Reboot diperlukan untuk apply hostname"
        NEED_REBOOT=true
    else
        print_info "Hostname tidak diubah"
    fi
}

# =============================================================================
# STEP 3: Clone/Update Repository
# =============================================================================
setup_repository() {
    print_header "Step 3/8: Setting Up Repository"

    if [ -d "$INSTALL_DIR" ]; then
        print_info "Directory exists, checking for updates..."
        cd "$INSTALL_DIR"

        if [ -d ".git" ]; then
            print_info "Pulling latest changes..."
            git pull origin main || git pull origin master || true
        else
            print_warning "Not a git repository, skipping update"
        fi
    else
        print_info "Cloning repository..."
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi

    cd "$INSTALL_DIR"
    print_success "Repository ready at: $INSTALL_DIR"
}

# =============================================================================
# STEP 4: Setup Virtual Environment
# =============================================================================
setup_venv() {
    print_header "Step 4/8: Setting Up Python Virtual Environment"

    cd "$INSTALL_DIR"

    if [ -d "venv" ]; then
        print_info "Virtual environment exists, checking..."

        # Check if venv is valid
        if [ -f "venv/bin/python3" ]; then
            print_success "Virtual environment valid"
        else
            print_warning "Virtual environment corrupted, recreating..."
            rm -rf venv
            python3 -m venv venv
        fi
    else
        print_info "Creating virtual environment..."
        python3 -m venv venv
    fi

    # Activate and install requirements
    print_info "Installing Python packages..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate

    print_success "Virtual environment ready"
}

# =============================================================================
# STEP 5: Create Data Directories
# =============================================================================
setup_directories() {
    print_header "Step 5/8: Creating Data Directories"

    cd "$INSTALL_DIR"

    mkdir -p data logs

    print_success "Directories created: data/, logs/"
}

# =============================================================================
# STEP 6: Configure System
# =============================================================================
configure_system() {
    print_header "Step 6/8: System Configuration"

    CONFIG_FILE="$INSTALL_DIR/weatherstation/config/system_config.yaml"

    print_info "Current configuration file: $CONFIG_FILE"
    echo ""

    # Get system name
    current_hostname=$(hostname)
    default_name="Weatherstation $current_hostname"

    read -p "Nama sistem [$default_name]: " system_name
    system_name=${system_name:-$default_name}

    read -p "Lokasi sistem [Your Location]: " system_location
    system_location=${system_location:-"Your Location"}

    # Update config using sed
    if [ -f "$CONFIG_FILE" ]; then
        print_info "Updating configuration..."

        # Update system name
        sed -i "s/name: .*/name: \"$system_name\"/" "$CONFIG_FILE"

        # Update location
        sed -i "s/location: .*/location: \"$system_location\"/" "$CONFIG_FILE"

        print_success "Configuration updated"
    else
        print_error "Config file not found: $CONFIG_FILE"
        exit 1
    fi
}

# =============================================================================
# STEP 7: Initialize Database
# =============================================================================
init_database() {
    print_header "Step 7/8: Initializing Database"

    cd "$INSTALL_DIR"

    if [ -f "data/weatherstation.db" ]; then
        print_info "Database already exists"
        read -p "Reset database? (y/N): " reset_db

        if [ "$reset_db" = "y" ] || [ "$reset_db" = "Y" ]; then
            rm -f data/weatherstation.db
            print_info "Database removed, will be recreated"
        fi
    fi

    print_info "Initializing database..."
    source venv/bin/activate

    # Run briefly to initialize database
    timeout 5 python3 -m weatherstation.main --service all \
        --config weatherstation/config/system_config.yaml || true

    deactivate

    if [ -f "data/weatherstation.db" ]; then
        print_success "Database initialized"
    else
        print_warning "Database may not be initialized, will be created on first run"
    fi
}

# =============================================================================
# STEP 8: Setup Systemd Services
# =============================================================================
setup_systemd() {
    print_header "Step 8/8: Setting Up Systemd Services"

    cd "$INSTALL_DIR/scripts"

    # Setup main service
    print_info "Setting up main weatherstation service..."
    sudo bash setup_systemd.sh

    # Setup web admin socket
    if [ -f "setup_web_admin_socket.sh" ]; then
        print_info "Setting up web admin socket activation..."
        sudo bash setup_web_admin_socket.sh
    fi

    print_success "Systemd services configured"
}

# =============================================================================
# STEP 9: Register Sensors (Interactive)
# =============================================================================
register_sensors() {
    print_header "Register Sensors"

    echo "Apakah kamu ingin mendaftarkan sensor sekarang?"
    echo ""
    echo "1) Ya, daftarkan via command line"
    echo "2) Tidak, nanti saja via web admin"
    echo ""
    read -p "Pilihan [2]: " register_choice
    register_choice=${register_choice:-2}

    if [ "$register_choice" = "1" ]; then
        cd "$INSTALL_DIR"

        # Register battery sensors
        echo ""
        read -p "Jumlah sensor PZEM (0-10): " pzem_count
        pzem_count=${pzem_count:-0}

        for ((i=1; i<=pzem_count; i++)); do
            read -p "  PZEM $i - Nama [PZEM_$i]: " pzem_name
            pzem_name=${pzem_name:-"PZEM_$i"}

            read -p "  PZEM $i - Modbus Address [$i]: " pzem_addr
            pzem_addr=${pzem_addr:-$i}

            # Generate ULID-like ID
            sensor_id="PZEM_$(hostname)_$(printf '%02d' $i)"

            sqlite3 data/weatherstation.db "INSERT INTO sensors (sensor_id, sensor_type, sensor_name, modbus_address, enabled) VALUES ('$sensor_id', 'battery', '$pzem_name', $pzem_addr, 1);"

            print_success "Registered: $sensor_id (address: $pzem_addr)"
        done

        # Register weather station
        echo ""
        read -p "Daftarkan Weather Station? (y/N): " register_weather

        if [ "$register_weather" = "y" ] || [ "$register_weather" = "Y" ]; then
            read -p "  Nama Weather Station [Weather Station]: " weather_name
            weather_name=${weather_name:-"Weather Station"}

            sensor_id="WEATHER_$(hostname)"

            sqlite3 data/weatherstation.db "INSERT INTO sensors (sensor_id, sensor_type, sensor_name, enabled) VALUES ('$sensor_id', 'weather', '$weather_name', 1);"

            print_success "Registered: $sensor_id"
        fi

        # Show registered sensors
        echo ""
        print_info "Registered sensors:"
        sqlite3 data/weatherstation.db "SELECT sensor_id, sensor_type, sensor_name, modbus_address FROM sensors;"
    else
        print_info "Kamu bisa daftarkan sensor nanti via web admin"
        print_info "Akses: http://$(hostname -I | awk '{print $1}'):8080/devices"
    fi
}

# =============================================================================
# Final Summary
# =============================================================================
print_summary() {
    print_header "Installation Complete!"

    IP_ADDR=$(hostname -I | awk '{print $1}')

    echo -e "${GREEN}Gateway-Prasena berhasil diinstall!${NC}"
    echo ""
    echo "============================================"
    echo "INFORMASI SISTEM"
    echo "============================================"
    echo "  Hostname     : $(hostname)"
    echo "  IP Address   : $IP_ADDR"
    echo "  Install Dir  : $INSTALL_DIR"
    echo ""
    echo "============================================"
    echo "COMMANDS"
    echo "============================================"
    echo "  Start service    : sudo systemctl start weatherstation"
    echo "  Stop service     : sudo systemctl stop weatherstation"
    echo "  View logs        : sudo journalctl -u weatherstation -f"
    echo "  Service status   : sudo systemctl status weatherstation"
    echo ""
    echo "  Web Admin        : http://$IP_ADDR:8080"
    echo "  (start socket)   : sudo systemctl start web-admin.socket"
    echo ""
    echo "============================================"
    echo "NEXT STEPS"
    echo "============================================"

    if [ "$NEED_REBOOT" = true ]; then
        echo -e "  ${YELLOW}1. Reboot untuk apply hostname baru${NC}"
        echo "     sudo reboot"
        echo ""
        echo "  2. Setelah reboot, start service:"
        echo "     sudo systemctl start weatherstation"
    else
        echo "  1. Daftarkan sensor (jika belum):"
        echo "     sudo systemctl start web-admin.socket"
        echo "     Buka http://$IP_ADDR:8080/devices"
        echo ""
        echo "  2. Start service:"
        echo "     sudo systemctl start weatherstation"
    fi

    echo ""
    echo "  3. Monitor logs:"
    echo "     sudo journalctl -u weatherstation -f"
    echo ""
    echo "============================================"
    echo ""

    if [ "$NEED_REBOOT" = true ]; then
        read -p "Reboot sekarang? (y/N): " do_reboot
        if [ "$do_reboot" = "y" ] || [ "$do_reboot" = "Y" ]; then
            sudo reboot
        fi
    else
        read -p "Start service sekarang? (Y/n): " start_now
        start_now=${start_now:-Y}

        if [ "$start_now" = "y" ] || [ "$start_now" = "Y" ]; then
            sudo systemctl start weatherstation
            sudo systemctl start web-admin.socket
            echo ""
            print_success "Services started!"
            echo ""
            sudo systemctl status weatherstation --no-pager
        fi
    fi
}

# =============================================================================
# Main Installation Flow
# =============================================================================
main() {
    clear

    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                            ║${NC}"
    echo -e "${BLUE}║   ${GREEN}Gateway-Prasena Auto Installer${BLUE}          ║${NC}"
    echo -e "${BLUE}║                                            ║${NC}"
    echo -e "${BLUE}║   Weather Station Gateway System           ║${NC}"
    echo -e "${BLUE}║                                            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
    echo ""

    check_not_root

    echo "Script ini akan:"
    echo "  0. Cleanup files development (npm, claude cli, dll) - OPSIONAL"
    echo "  1. Install system dependencies"
    echo "  2. Set hostname unik"
    echo "  3. Clone/update repository"
    echo "  4. Setup Python virtual environment"
    echo "  5. Create data directories"
    echo "  6. Configure system"
    echo "  7. Initialize database"
    echo "  8. Setup systemd services"
    echo "  9. Register sensors (optional)"
    echo ""

    read -p "Lanjutkan instalasi? (Y/n): " confirm
    confirm=${confirm:-Y}

    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "Instalasi dibatalkan"
        exit 0
    fi

    NEED_REBOOT=false

    # Cleanup for production (optional)
    cleanup_for_production

    # Run installation steps
    install_dependencies
    setup_hostname
    setup_repository
    setup_venv
    setup_directories
    configure_system
    init_database
    setup_systemd
    register_sensors
    print_summary
}

# Run main function
main "$@"
