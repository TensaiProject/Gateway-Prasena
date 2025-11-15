# Installation Guide - Gateway Prasena

Quick deployment guide for Raspberry Pi Zero 2W.

## Prerequisites

- Raspberry Pi Zero 2W with Raspbian/Debian
- Internet connection
- SSH access or direct console
- sudo privileges

## Quick Install (One Command)

```bash
curl -sSL https://raw.githubusercontent.com/TensaiProject/Gateway-Prasena/main/scripts/deploy.sh | bash
```

## Manual Installation

### 1. Clone Repository

```bash
cd ~
git clone https://github.com/TensaiProject/Gateway-Prasena.git gateway-prasena
cd gateway-prasena
```

### 2. Run Installation Script

```bash
bash scripts/install.sh
```

This will:
- Update system packages
- Install dependencies (Python, pigpio, etc.)
- Create virtual environment
- Install Python packages
- Create data/log directories

### 3. Configure System

Edit configuration file:

```bash
nano weatherstation/config/system_config.yaml
```

Key settings:
- `mqtt.broker_url`: MQTT broker address
- `mqtt.username`: MQTT credentials
- `upload.main_server_url`: Upload endpoint
- `upload.api_key`: API key for server
- `weather_station.sensor_id`: Weather station ID

### 4. Initialize Database

```bash
cd ~/gateway-prasena
source venv/bin/activate
python -m weatherstation.main --init-db
```

### 5. Register Devices

Register battery sensor:

```bash
python -m weatherstation.main --register-device
```

Example:
```
Sensor ID: SENSOR-BATTERY-001
Sensor Type: battery
Sensor Name: Battery Sensor 1
Modbus Address: 1
```

### 6. Setup Systemd (Auto-start)

```bash
sudo bash scripts/setup_systemd.sh
```

### 7. Start Service

```bash
sudo systemctl start weatherstation
```

Check status:

```bash
sudo systemctl status weatherstation
```

View logs:

```bash
sudo journalctl -u weatherstation -f
```

## Ecowitt Weather Station Setup

Configure Ecowitt station to send data to gateway:

1. Open Ecowitt app
2. Go to Settings → Custom Server
3. Set:
   - **Protocol**: Ecowitt
   - **Server**: `http://<raspi_ip>:5001/data/report/`
   - **Interval**: 60 seconds (or your preference)
4. Save and test

Gateway will receive data automatically.

## Directory Structure

```
~/gateway-prasena/
├── venv/                   # Virtual environment
├── weatherstation/         # Main application
│   ├── config/            # Configuration files
│   ├── database/          # Database module
│   ├── sensors/           # Sensor readers
│   ├── services/          # Background services
│   └── api/               # REST API
├── data/                  # SQLite database (auto-created)
├── logs/                  # Log files
├── scripts/               # Deployment scripts
└── systemd/               # Systemd service files
```

## Service Management

```bash
# Start
sudo systemctl start weatherstation

# Stop
sudo systemctl stop weatherstation

# Restart
sudo systemctl restart weatherstation

# Status
sudo systemctl status weatherstation

# Enable auto-start on boot
sudo systemctl enable weatherstation

# Disable auto-start
sudo systemctl disable weatherstation

# View logs (real-time)
sudo journalctl -u weatherstation -f

# View logs (last 100 lines)
sudo journalctl -u weatherstation -n 100
```

## Testing

### Test Battery Reader

```bash
cd ~/gateway-prasena
source venv/bin/activate
python -m weatherstation.main --service battery --test
```

### Test Weather Receiver

```bash
curl "http://localhost:5001/data/report/?stationtype=test&tempf=77&humidity=65"
```

Should return: `OK`

### Test MQTT Connection

Check logs for MQTT connection:

```bash
sudo journalctl -u weatherstation | grep -i mqtt
```

## Troubleshooting

### pigpiod not running

```bash
sudo systemctl status pigpiod
sudo systemctl start pigpiod
sudo systemctl enable pigpiod
```

### Permission denied on GPIO

Add user to gpio group:

```bash
sudo usermod -a -G gpio $USER
```

Logout and login again.

### Database not found

Initialize database:

```bash
cd ~/gateway-prasena
source venv/bin/activate
python -m weatherstation.main --init-db
```

### Service won't start

Check logs:

```bash
sudo journalctl -u weatherstation -n 50
```

Check pigpiod:

```bash
sudo systemctl status pigpiod
```

### High memory usage

Check resource usage:

```bash
sudo systemctl status weatherstation
```

Service has 384MB limit (safe for Pi Zero 2W).

## Updating

```bash
cd ~/gateway-prasena
git pull
source venv/bin/activate
pip install -r requirements.txt --upgrade
sudo systemctl restart weatherstation
```

## Uninstall

```bash
# Stop and disable service
sudo systemctl stop weatherstation
sudo systemctl disable weatherstation

# Remove systemd files
sudo rm /etc/systemd/system/weatherstation*
sudo systemctl daemon-reload

# Remove installation
rm -rf ~/gateway-prasena
```

## Support

- Repository: https://github.com/TensaiProject/Gateway-Prasena
- Issues: https://github.com/TensaiProject/Gateway-Prasena/issues
