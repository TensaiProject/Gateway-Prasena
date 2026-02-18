# Gateway-Prasena Deployment Guide

Complete guide for deploying Gateway-Prasena weatherstation system on Raspberry Pi.

## Table of Contents

- [Hardware Requirements](#hardware-requirements)
- [Software Requirements](#software-requirements)
- [Initial Setup](#initial-setup)
- [System Configuration](#system-configuration)
- [Service Installation](#service-installation)
- [Device Registration](#device-registration)
- [Network Configuration](#network-configuration)
- [Verification & Testing](#verification--testing)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)

---

## Hardware Requirements

### Minimum Specifications

- **Raspberry Pi**: Zero 2 W or higher (Pi 3B+, Pi 4 recommended for production)
- **Storage**: 32GB microSD card (Class 10 or UHS-1)
- **Power Supply**: 5V 2.5A minimum (3A recommended)
- **Network**: Ethernet or WiFi connectivity

### Sensors (Supported)

- **Weather Station**: Ecowitt GW1000/GW2000 or compatible
- **Battery Monitor**: PZEM-017 DC Energy Meter (Modbus RTU)

### Optional

- USB Serial adapter for PZEM-017 (if using battery monitoring)
- Ethernet cable (for more stable connection)

---

## Software Requirements

### Operating System

- **Raspberry Pi OS Lite (64-bit)** - Debian Bookworm based
- Download: [https://www.raspberrypi.com/software/operating-systems/](https://www.raspberrypi.com/software/operating-systems/)

### Required Packages (will be installed during setup)

- Python 3.11+
- pip3
- git
- sqlite3
- systemd

---

## Initial Setup

### 1. Flash OS to SD Card

Use **Raspberry Pi Imager** or **balenaEtcher**:

1. Download Raspberry Pi Imager
2. Select **Raspberry Pi OS Lite (64-bit)**
3. Configure settings (RECOMMENDED):
   - Set hostname: `weatherstation2` (or your preferred name)
   - Enable SSH
   - Set username: `weatherstation2` (recommended)
   - Set password
   - Configure WiFi (if needed)
   - Set timezone: `Asia/Jakarta`

4. Flash to SD card

### 2. First Boot

1. Insert SD card into Raspberry Pi
2. Connect power
3. Wait 2-3 minutes for first boot
4. Find IP address:
   - Check your router's DHCP client list
   - Or use: `ping weatherstation2.local`

### 3. SSH Connection

```bash
ssh weatherstation2@<IP_ADDRESS>
# Or using mDNS:
ssh weatherstation2@weatherstation2.local
```

### 4. Update System (Optional but Recommended)

```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
```

**Note:** The installer script will also update packages, so you can skip this if you want faster initial setup.

---

## System Configuration

### Quick Installation (Recommended)

For fastest deployment, use the **two-step automated installation**:

#### Step 1: Clone Repository with Auto-Pull Script

Run this one-command setup to configure SSH key and clone repository:

Gateway-Prasena includes an automated setup script with SSH deploy key for secure, password-less git operations.

#### Setup SSH Deploy Key and Clone Repository

**Option 1: Using Auto-Pull Script (Recommended)**

Contact the repository administrator for the one-liner setup command that will:
- Configure SSH deploy key for GitHub access
- Create `~/auto_pull.sh` script for automated git operations
- Enable password-less cloning and updates

After receiving the one-liner, run it on your Raspberry Pi, then execute:
```bash
~/auto_pull.sh
```

Expected output:
```
=== Gateway Prasena Auto Pull ===
Timestamp: 2026-01-25 17:30:00
Cloning repository...
✓ Repository cloned
=== Done ===
```

**Option 2: Manual Clone**

If you don't have access to the auto-pull setup:

```bash
cd ~
git clone https://github.com/TensaiProject/Gateway-Prasena.git
cd Gateway-Prasena
```

#### Step 2: Run Automated Installer

Navigate to the repository and run the installer:

```bash
cd ~/Gateway-Prasena
bash scripts/auto_install.sh
```

The installer will automatically:
1. Update system packages
2. Install dependencies (Python, Git, SQLite, pigpio, etc.)
3. Create Python virtual environment
4. Install Python packages from requirements.txt
5. Create data and log directories
6. Configure system name and location
7. Initialize database
8. Setup systemd services (weatherstation, web-admin)
9. Install subnet keep-alive service (optional)
10. Register sensors (optional)

**Installation takes ~5-10 minutes** depending on your internet speed and Pi model.

Expected output:
```
╔════════════════════════════════════════════╗
║   Gateway-Prasena Auto Installer          ║
║   Weather Station Gateway System           ║
╚════════════════════════════════════════════╝

[1/9] Installing system dependencies...
[2/9] Setting hostname...
[3/9] Setting up repository...
[4/9] Setting up Python virtual environment...
[5/9] Creating data directories...
[6/9] System configuration...
[7/9] Initializing database...
[8/9] Setting up systemd services...
[9/9] Setting up subnet keep-alive service...

Installation Complete!
```

#### Step 3: Start Services

The installer will offer to start services automatically. If you declined, start them manually:

```bash
sudo systemctl start weatherstation.service
sudo systemctl start web-admin.socket
```

Check service status:
```bash
sudo systemctl status weatherstation.service
# Should show: Active: active (running)

# View logs
sudo journalctl -u weatherstation.service -f
```

Web admin will start on-demand when accessed: `http://<IP_ADDRESS>:8080`

---

## Device Registration

### 1. Access Web Admin

Open browser and navigate to:
```
http://<RASPBERRY_PI_IP>:8080
```

Or using hostname:
```
http://weatherstation2.local:8080
```

### 2. Register Weather Station

1. Go to **Devices** page
2. Click **"Register Device"**
3. Fill in the following information:

   **Required Fields:**
   - **Device ID**: Enter a unique identifier for this device
     - Format: 3-26 characters (alphanumeric + underscore + hyphen)
     - Examples: `WEATHER_STATION_01`, `WS_JAKARTA`, `ECOWITT_001`
     - Must be unique across all devices

   - **Device Type**: Select `weather` (or `weather_station`)

   - **Device Name**: Friendly name for this device
     - Example: "Weather Station Jakarta Utara"

   **Optional Fields:**
   - **Location**: Physical location of the device
     - Example: "Gedung A - Lantai 3 - Jakarta"

   - **Enabled**: ✓ (checked) to activate immediately

4. Click **Submit**
5. **IMPORTANT**: Save the Device ID you entered - you'll need it for troubleshooting

### 3. Register Battery Sensor (if applicable)

1. Click **"Register Device"** again
2. Fill in the following information:

   **Required Fields:**
   - **Device ID**: Enter a unique identifier for this battery sensor
     - Format: 3-26 characters (alphanumeric + underscore + hyphen)
     - Examples: `PZEM_001`, `BATTERY_STATION_01`, `BAT_JAKARTA_01`
     - Must be unique across all devices

   - **Device Type**: Select `battery`

   - **Device Name**: Friendly name for this sensor
     - Example: "PZEM Battery Monitor 1"

   - **Modbus Address**: RS485 Modbus address (1-247)
     - Each battery sensor must have a unique modbus address
     - Default PZEM address is usually `1`
     - If you have multiple PZEM sensors, set addresses to `1`, `2`, `3`, etc.

   **Optional Fields:**
   - **Location**: Physical location
     - Example: "Gedung A - Panel Listrik - Jakarta"

   - **Enabled**: ✓ (checked) to activate immediately

3. Click **Submit**
4. **IMPORTANT**: Save the Device ID and Modbus Address for reference

### 4. Configure Ecowitt Weather Station

1. Open Ecowitt app or access weather station web interface
2. Go to **Weather Services** > **Customized**
3. Configure:
   - **Protocol**: Ecowitt
   - **Server IP**: `<RASPBERRY_PI_IP>`
   - **Port**: `5001`
   - **Path**: `/data/report/`
   - **Interval**: 60 seconds (recommended)
4. Save and test connection

---

## Network Configuration

### 1. Set Static IP (Recommended for Production)

Edit dhcpcd configuration:
```bash
sudo nano /etc/dhcpcd.conf
```

Add at the end (adjust to your network):
```
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 1.1.1.1

# Or for WiFi:
interface wlan0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 1.1.1.1
```

Restart networking:
```bash
sudo systemctl restart dhcpcd
```

### 2. Configure Firewall (Optional)

```bash
# Install UFW
sudo apt install -y ufw

# Allow SSH
sudo ufw allow 22/tcp

# Allow Web Admin
sudo ufw allow 8080/tcp

# Allow Weather Station data receiver
sudo ufw allow 5001/tcp

# Enable firewall
sudo ufw enable
```

### 3. Enable Auto-Update Cron Job (Optional)

If you setup auto-pull script during [System Configuration](#2-clone-repository-with-auto-pull-script-recommended), you can enable automatic updates every 6 hours:

```bash
crontab -e
```

Add this line:
```
0 */6 * * * ~/auto_pull.sh >> ~/auto_pull.log 2>&1 && cd ~/Gateway-Prasena && sudo systemctl restart weatherstation.service
```

This will:
- Run `~/auto_pull.sh` every 6 hours
- Log output to `~/auto_pull.log`
- Restart weatherstation service if updates were pulled

Check cron log:
```bash
tail -f ~/auto_pull.log
```

---

## Verification & Testing

### 1. Check Database

```bash
cd ~/Gateway-Prasena
sqlite3 data/weatherstation.db "SELECT * FROM devices;"
```

Should show your registered devices.

### 2. Check Data Collection

Wait 1-2 minutes, then:
```bash
sqlite3 data/weatherstation.db "SELECT COUNT(*) FROM sensor_data;"
```

Should show increasing number of records.

### 3. Check Recent Data

```bash
sqlite3 data/weatherstation.db "SELECT timestamp, device_id FROM sensor_data ORDER BY timestamp DESC LIMIT 5;"
```

Timestamps should be in RFC 3339 format with timezone:
```
2026-01-25T17:30:45.123+07:00
```

### 4. Check MQTT Publishing

```bash
sudo journalctl -u weatherstation.service -n 100 --no-pager | grep "Published"
```

Should show:
```
Published battery data: <DEVICE_ID> (ID: <ID>, quality: 100%)
Published weather data: <DEVICE_ID> (ID: <ID>, quality: 100%)
```

### 5. Check Auto-Cleanup

```bash
sudo journalctl -u weatherstation.service --no-pager | grep "Cleanup threshold"
```

Should show:
```
Cleanup threshold: 90 days
```

### 6. Check Storage Usage

```bash
df -h | grep root
du -h ~/Gateway-Prasena/data/weatherstation.db
```

Database size should grow steadily (approximately 1-2 MB per day).

### 7. Test Web Admin

Access `http://<IP>:8080` and verify:
- Can view devices
- Can view MQTT settings
- Can view system intervals
- Can export data

---

## Troubleshooting

### Service Not Starting

```bash
# Check service status
sudo systemctl status weatherstation.service

# Check logs
sudo journalctl -u weatherstation.service -n 100 --no-pager

# Check Python errors
cd ~/Gateway-Prasena
source venv/bin/activate
python -m weatherstation.service_manager
```

### No Data Being Collected

1. Check if weather station is sending data:
```bash
sudo journalctl -u weatherstation.service --no-pager | grep "Stored Ecowitt"
```

2. Verify weather station configuration:
   - Correct IP address
   - Correct port (5001)
   - Correct path (/data/report/)

3. Check network connectivity:
```bash
ping <WEATHER_STATION_IP>
```

### MQTT Not Publishing

```bash
# Check MQTT logs
sudo journalctl -u weatherstation.service --no-pager | grep "MQTT"

# Look for connection errors
sudo journalctl -u weatherstation.service --no-pager | grep "Error\|Failed"
```

Common issues:
- Incorrect MQTT credentials
- Firewall blocking port 8084
- Network connectivity issues

### Database Issues

```bash
# Check database integrity
sqlite3 ~/Gateway-Prasena/data/weatherstation.db "PRAGMA integrity_check;"
# Should return: ok

# Check database size
du -h ~/Gateway-Prasena/data/weatherstation.db

# Vacuum database (if too large)
sqlite3 ~/Gateway-Prasena/data/weatherstation.db "VACUUM;"
```

### High CPU/Memory Usage

```bash
# Check process usage
htop

# Check service resource usage
systemctl status weatherstation.service | grep "Memory\|CPU"

# Restart service if needed
sudo systemctl restart weatherstation.service
```

### Service Keeps Restarting

```bash
# Check crash logs
sudo journalctl -u weatherstation.service -p err -n 50

# Check for Python errors
sudo journalctl -u weatherstation.service | grep "Traceback" -A 10
```

---

## Maintenance

### Regular Tasks

#### Daily
- Monitor via web admin: `http://<IP>:8080`
- Check data is being collected

#### Weekly
- Check disk space: `df -h`
- Check service status: `sudo systemctl status weatherstation.service`
- Review logs: `sudo journalctl -u weatherstation.service -n 100`

#### Monthly
- Update system: `sudo apt update && sudo apt upgrade -y`
- Pull latest code: `~/auto_pull.sh` (or `cd ~/Gateway-Prasena && git pull origin staging`)
- Vacuum database: `sqlite3 data/weatherstation.db "VACUUM;"`
- Check database size: `du -h data/weatherstation.db`

#### Quarterly
- Export data backup via Web Admin
- Verify all sensors are working
- Check storage capacity (should have >5GB free)

### Backup Data

#### Via Web Admin
1. Access `http://<IP>:8080`
2. Go to **Data Export**
3. Select date range
4. Choose format (CSV or JSON)
5. Click **Download**

#### Via Command Line
```bash
# Copy entire database
cp ~/Gateway-Prasena/data/weatherstation.db ~/backup_$(date +%Y%m%d).db

# Export to CSV
sqlite3 ~/Gateway-Prasena/data/weatherstation.db \
  -header -csv "SELECT * FROM sensor_data;" > sensor_data_backup.csv
```

### Update System

#### Using Auto-Pull Script (Recommended)

```bash
# Pull latest updates
~/auto_pull.sh

# Restart services
sudo systemctl restart weatherstation.service
sudo systemctl restart web-admin.socket
```

#### Manual Update

```bash
# Update repository manually
cd ~/Gateway-Prasena
git pull origin staging

# Restart services
sudo systemctl restart weatherstation.service
sudo systemctl restart web-admin.socket
```

### Factory Reset

If you need to start fresh:

```bash
# Stop services
sudo systemctl stop weatherstation.service
sudo systemctl stop web-admin.socket

# Backup old database (optional)
mv ~/Gateway-Prasena/data/weatherstation.db ~/weatherstation_backup_$(date +%Y%m%d).db

# Reinitialize database
cd ~/Gateway-Prasena
source venv/bin/activate
python -m weatherstation.database.init_db

# Start services
sudo systemctl start weatherstation.service
```

---

## Configuration Reference

### Key Configuration Files

| File | Purpose |
|------|---------|
| `weatherstation/config/system_config.yaml` | Main system configuration |
| `systemd/weatherstation.service` | Main service definition |
| `systemd/web-admin.service` | Web admin service |
| `systemd/web-admin.socket` | Web admin socket activation |
| `data/weatherstation.db` | SQLite database |

### Important Settings

#### Auto-Cleanup
- **Default**: 90 days
- **Location**: `system_config.yaml` → `database.auto_cleanup_days`
- **Range**: 1-365 days
- Can be changed via Web Admin

#### Data Retention
- With 90-day cleanup: ~6.5 GB storage for 3 months
- With 180-day cleanup: ~13 GB storage for 6 months
- Database auto-VACUUM runs after cleanup

#### Polling Intervals
- **Battery Sensor**: 1 second sampling, 30 second aggregation
- **MQTT Publisher**: 5 second poll interval
- **Weather Station**: 60 seconds (configured in Ecowitt)

---

## Support & Resources

### Documentation
- Main README: `~/Gateway-Prasena/README.md`
- This guide: `~/Gateway-Prasena/DEPLOYMENT_GUIDE.md`

### Logs Location
```bash
# Service logs
sudo journalctl -u weatherstation.service
sudo journalctl -u web-admin.service

# Journald disk usage
journalctl --disk-usage
```

### Useful Commands

```bash
# Service management
sudo systemctl start weatherstation.service
sudo systemctl stop weatherstation.service
sudo systemctl restart weatherstation.service
sudo systemctl status weatherstation.service

# View logs
sudo journalctl -u weatherstation.service -f  # Follow logs
sudo journalctl -u weatherstation.service -n 100  # Last 100 lines
sudo journalctl -u weatherstation.service --since "1 hour ago"

# Database queries
sqlite3 ~/Gateway-Prasena/data/weatherstation.db
```

### Common SQL Queries

```sql
-- Count total records
SELECT COUNT(*) FROM sensor_data;

-- Check oldest and newest data
SELECT MIN(timestamp), MAX(timestamp) FROM sensor_data;

-- Count by sensor type
SELECT d.sensor_type, COUNT(*)
FROM sensor_data sd
JOIN devices d ON sd.device_id = d.id
GROUP BY d.sensor_type;

-- Check data from last hour
SELECT timestamp, device_id
FROM sensor_data
WHERE timestamp > datetime('now', '-1 hour')
ORDER BY timestamp DESC;
```

---

## Quick Deployment Checklist

### Initial Setup
- [ ] Flash Raspberry Pi OS Lite to SD card
- [ ] Configure hostname, user, SSH, WiFi/Ethernet in Pi Imager
- [ ] First boot and SSH connection
- [ ] (Optional) Update system: `sudo apt update && sudo apt upgrade -y`

### Installation
- [ ] Get one-liner from admin or clone manually
- [ ] Run `~/auto_pull.sh` or `git clone` to get repository
- [ ] Run `bash scripts/auto_install.sh`
- [ ] Wait ~5-10 minutes for installation to complete
- [ ] Start services (or let installer start them)

### Configuration
- [ ] Register devices via Web Admin (`http://<IP>:8080`)
- [ ] Configure Ecowitt weather station (IP, Port 5001, Path: /data/report/)
- [ ] Set static IP (recommended for production)
- [ ] Enable auto-update cron job (optional)

### Verification
- [ ] Test data collection (check logs and database)
- [ ] Verify MQTT publishing
- [ ] Check auto-cleanup settings (should be 90 days)
- [ ] Test web admin access
- [ ] Document IP address and device IDs

---

## Production Deployment Notes

### Security Recommendations

1. **Change default password** for `weatherstation2` user
2. **Use SSH keys** instead of password authentication
3. **Enable firewall** (UFW)
4. **Keep system updated** regularly
5. **Monitor logs** for suspicious activity
6. **Backup data** regularly

### Performance Optimization

1. Use **wired Ethernet** for more stable connection
2. Use **quality SD card** (UHS-1 or better)
3. Monitor **disk space** regularly
4. Run **VACUUM** on database monthly
5. Keep **auto-cleanup** enabled (90 days recommended)

### Scalability

For deploying multiple units:
1. Use **unique hostnames** (e.g., `weatherstation1`, `weatherstation2`, etc.)
2. Document **IP addresses** in a spreadsheet
3. Use **static IP** for each unit
4. Consider **centralized monitoring** dashboard
5. Set up **auto-update** cron job for easier maintenance

---

**Last Updated**: 2026-01-25
**Version**: 1.0
**Tested On**: Raspberry Pi Zero 2 W, Raspberry Pi OS Lite (64-bit) Bookworm
