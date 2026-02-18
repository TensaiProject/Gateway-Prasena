# Gateway-Prasena Quick Install Guide

**Two-step automated installation** for Raspberry Pi weatherstation system.

---

## Prerequisites

- Raspberry Pi (Zero 2 W or higher) with Raspberry Pi OS Lite (64-bit)
- SD card flashed and Pi connected to network
- SSH access enabled

---

## Installation (2 Steps)

### Step 1: Clone Repository

SSH into your Raspberry Pi.

**Option A: Using Auto-Pull Script (Recommended)**

Contact the repository administrator for the one-liner setup command, then run:

```bash
~/auto_pull.sh
```

**Option B: Manual Clone**

```bash
cd ~
git clone https://github.com/TensaiProject/Gateway-Prasena.git
cd Gateway-Prasena
```

Expected output (Option A):
```
=== Gateway Prasena Auto Pull ===
Cloning repository...
✓ Repository cloned
=== Done ===
```

Expected output (Option B):
```
Cloning into 'Gateway-Prasena'...
done.
```

---

### Step 2: Run Installer

Navigate to the repository and run the installer:

```bash
cd ~/Gateway-Prasena
bash scripts/auto_install.sh
```

The installer will automatically:
1. Install system dependencies (Python, Git, SQLite, pigpio, etc.)
2. Set unique hostname for this Raspberry Pi
3. Setup Python virtual environment and install packages
4. Create data and log directories
5. Configure system name and location
6. Initialize database
7. Setup systemd services (weatherstation, web-admin socket)
8. Install subnet keep-alive service (prevents ARP timeout)
9. Optionally register sensors

**Installation takes ~5-10 minutes** depending on your internet speed and Pi model.

The installer will ask for:
- Hostname (must be unique per device)
- System name and location
- Whether to install subnet keep-alive
- Whether to register sensors now

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

---

## Post-Installation

### 1. Verify Services

The installer may have already started services. Check status:

```bash
sudo systemctl status weatherstation.service
```

Should show: `Active: active (running)`

If not running, start manually:
```bash
sudo systemctl start weatherstation.service
sudo systemctl start web-admin.socket
```

### 2. Access Web Admin

Open browser and navigate to:
```
http://<RASPBERRY_PI_IP>:8080
```

Or using hostname:
```
http://weatherstation2.local:8080
```

### 3. Register Devices

1. Go to **Devices** page
2. Click **"Register Device"**
3. Add weather station:
   - Sensor Type: `weather_station`
   - Location: "Your Location Name"
4. Add battery sensor (if applicable):
   - Sensor Type: `battery`
   - Location: "Battery Monitor Location"

### 4. Configure Ecowitt Weather Station

1. Open Ecowitt app or web interface
2. Go to **Weather Services** > **Customized**
3. Configure:
   - **Protocol**: Ecowitt
   - **Server IP**: `<RASPBERRY_PI_IP>`
   - **Port**: `5001`
   - **Path**: `/data/report/`
   - **Interval**: 60 seconds

### 5. Verify Data Collection

Wait 2-3 minutes, then check:

```bash
# Check logs
sudo journalctl -u weatherstation.service -n 50 --no-pager

# Check database
sqlite3 ~/Gateway-Prasena/data/weatherstation.db "SELECT COUNT(*) FROM sensor_data;"
```

Should show increasing number of records.

---

## Optional: Set Static IP

For production deployment, set a static IP:

```bash
sudo nano /etc/dhcpcd.conf
```

Add at the end:
```
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 1.1.1.1
```

Restart:
```bash
sudo systemctl restart dhcpcd
```

---

## Optional: Enable Auto-Update

To automatically pull updates every 6 hours:

```bash
crontab -e
```

Add:
```
0 */6 * * * ~/auto_pull.sh >> ~/auto_pull.log 2>&1 && cd ~/Gateway-Prasena && sudo systemctl restart weatherstation.service
```

---

## Maintenance Commands

```bash
# View logs
sudo journalctl -u weatherstation.service -f

# Restart service
sudo systemctl restart weatherstation.service

# Pull updates
~/auto_pull.sh && sudo systemctl restart weatherstation.service

# Check database size
du -h ~/Gateway-Prasena/data/weatherstation.db

# Check disk space
df -h
```

---

## Configuration

Main config file: `~/Gateway-Prasena/weatherstation/config/system_config.yaml`

Key settings:
- **Auto-cleanup**: 90 days (can change via Web Admin)
- **MQTT**: Configured for emqx.prasenaenergy.com
- **Database**: ~/Gateway-Prasena/data/weatherstation.db

---

## Need Help?

- **Full documentation**: `~/Gateway-Prasena/DEPLOYMENT_GUIDE.md`
- **Troubleshooting**: Check logs with `sudo journalctl -u weatherstation.service -f`
- **GitHub Issues**: https://github.com/TensaiProject/Gateway-Prasena/issues

---

**Last Updated**: 2026-01-25
**Version**: 1.0
**Tested On**: Raspberry Pi Zero 2 W, Raspberry Pi OS Lite (64-bit) Bookworm
