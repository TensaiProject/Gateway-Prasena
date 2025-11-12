# Gateway Prasena - IoT Data Collection System

Gateway untuk mengumpulkan data sensor (battery, weather) dan upload ke server Prasena Energy.

## Hardware
- **Raspberry Pi Zero 2W**
- **Battery sensors** (RS485/Modbus - software serial)
- **Weather station**
- **MicroSD card** (min 8GB)

## Fitur
- ✅ Collect data dari multiple sensors
- ✅ Store lokal di SQLite (offline-capable)
- ✅ Batch upload ke server saat online
- ✅ Auto-cleanup data lama (prevent disk full)
- ✅ Web UI untuk konfigurasi sensor
- ✅ MQTT integration
- ✅ Systemd service (auto-restart)

---

## Quick Start

### 1. Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python3 and pip
sudo apt install python3 python3-pip python3-venv -y

# Install git
sudo apt install git -y

# Clone repository
cd ~
git clone <repo-url> sistem
cd sistem
git checkout staging

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
python3 -m weatherstation.main --init-db
```

### 3. Register Sensors

```bash
# Via CLI (interactive)
python3 -m weatherstation.main --register-device

# Atau via Web UI
python3 -m weatherstation.main --service api
# Buka http://raspi-ip:5000
```

### 4. Configure System

Edit `weatherstation/config/system_config.yaml`:

```yaml
database:
  auto_cleanup_enabled: true
  auto_cleanup_days: 7  # Delete uploaded data older than 7 days

battery_sensors:
  enabled: true
  poll_interval: 10       # Poll every 10 seconds
  sampling_rate: 1        # Sample every 1 second
  aggregation_window: 300 # Aggregate every 5 minutes

upload:
  interval: 60            # Upload every 60 seconds
  batch_size: 100
  main_server_url: "http://your-server.com/api"
  api_key: "your_api_key"

mqtt:
  broker_url: "wss://emqx-staging.prasenaenergy.com/mqtt"
  username: "prasena"
  password: "emqxoversecurewebsocket"
```

### 5. Start Services

```bash
# Manual (for testing)
python3 -m weatherstation.main --service upload

# Systemd (production)
./scripts/setup_services.sh
sudo systemctl start weatherstation-upload
sudo systemctl enable weatherstation-upload
```

---

## Services

| Service | Description | Command |
|---------|-------------|---------|
| `upload` | Upload data to server | `--service upload` |
| `cleanup` | Cleanup old data | `--service cleanup` |
| `api` | Web configuration UI | `--service api` |
| `weather` | Weather station receiver | `--service weather` |
| `mqtt` | MQTT subscriber | `--service mqtt` |

---

## Web API

Start web server:
```bash
python3 -m weatherstation.main --service api
# Access: http://raspi-ip:5000
```

### Endpoints

**Register Sensor:**
```bash
curl -X POST http://raspi-ip:5000/api/devices \
  -H "Content-Type: application/json" \
  -d '{
    "sensor_id": "01K9RSSBEVE5X1CV7ZGTB46MZP",
    "sensor_type": "battery",
    "sensor_name": "Battery 1",
    "modbus_address": 1,
    "location": "Panel A"
  }'
```

**Get All Sensors:**
```bash
curl http://raspi-ip:5000/api/devices
```

**Update Upload Config:**
```bash
curl -X PUT http://raspi-ip:5000/api/config/upload \
  -H "Content-Type: application/json" \
  -d '{"main_server_url": "http://new-server.com/api"}'
```

**Get System Status:**
```bash
curl http://raspi-ip:5000/api/status
```

---

## Database Schema

### Devices Table
- Internal ID (integer) + External sensor_id (ULID)
- Mapping: modbus_address → sensor_id

### Sensor Data Table (Universal)
- JSON-based data storage
- Example: `{"voltage": 12.5, "current": 2.3, "power": 28.75}`
- Supports any sensor type

---

## Troubleshooting

### Check Service Status
```bash
sudo systemctl status weatherstation-upload
sudo journalctl -u weatherstation-upload -f
```

### Check Database
```bash
sqlite3 data/weatherstation.db "SELECT * FROM devices;"
sqlite3 data/weatherstation.db "SELECT COUNT(*) FROM sensor_data WHERE uploaded=0;"
```

### Manual Cleanup
```bash
# Dry-run
python3 -m weatherstation.services.cleanup_service --once --dry-run

# Real cleanup
python3 -m weatherstation.main --service cleanup
```

### Check Disk Space
```bash
df -h
ls -lh data/weatherstation.db
```

---

## File Structure

```
weatherstation/
├── api/                  # Web server
├── config/               # YAML configs
├── database/             # SQLite manager + schema
├── services/             # Background services
├── utils/                # Logger, helpers
└── main.py               # CLI entry point

scripts/
└── setup_services.sh     # Systemd installer

systemd/
├── *.service             # Service definitions
└── *.timer               # Timer for cleanup
```

---

## Tips

1. **Storage Management**: Enable `auto_cleanup_enabled: true` untuk prevent disk full
2. **Monitoring**: Check logs: `sudo journalctl -u weatherstation-* -f`
3. **Testing**: Gunakan `--test` flag untuk single iteration
4. **Backup**: Database ada di `data/weatherstation.db`

---

## Support

- Logs: `./logs/`
- Database: `./data/weatherstation.db`
- Config: `weatherstation/config/system_config.yaml`
