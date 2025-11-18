# Web Admin Socket Activation (On-Demand)

## 🎯 Problem

On low-memory systems (like Raspberry Pi with 512MB RAM), running web admin 24/7 wastes **15-30 MB memory** even when not being used.

## ✅ Solution: Systemd Socket Activation

Web admin **only runs when accessed** via browser!

- ✅ **Zero memory** when idle
- ✅ **Auto-start** when you open `http://localhost:8080`
- ✅ **Auto-stop** after 5 minutes idle
- ✅ Native systemd support (reliable & battle-tested)

---

## 📦 Installation

### Run Setup Script:

```bash
cd /home/weatherstation1/Gateway-Prasena
sudo ./scripts/setup_web_admin_socket.sh
```

This will:
1. Install systemd socket unit (`/etc/systemd/system/web-admin.socket`)
2. Install systemd service unit (`/etc/systemd/system/web-admin.service`)
3. Enable and start socket listener
4. Configure auto-stop after idle

---

## 🚀 Usage

### Access Web Admin:

1. **Open browser**: `http://192.168.0.122:8080`
2. **Wait 2-3 seconds** for web admin to start (first time)
3. **Use normally** - configure settings, register devices
4. **Close browser** - web admin will auto-stop after 5 min idle

### Check Status:

```bash
# Check socket status (should be "listening")
sudo systemctl status web-admin.socket

# Check service status (should be "inactive" when idle)
sudo systemctl status web-admin.service

# View logs (real-time)
sudo journalctl -u web-admin -f
```

### Memory Comparison:

| Mode | Memory Usage |
|------|-------------|
| **Always Running** (old) | 15-30 MB constant |
| **Socket Activation** (new) | 0 MB idle, 15-30 MB when accessed |

**Savings: ~15-30 MB when not used!** ✅

---

## 🔧 Configuration

### Auto-Stop Timeout:

Edit `/etc/systemd/system/web-admin.service`:

```ini
[Service]
# Stop after 5 minutes idle (default)
RuntimeMaxSec=300

# Or stop after 10 minutes:
RuntimeMaxSec=600
```

Reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart web-admin.socket
```

### Resource Limits:

Current limits (in `web-admin.service`):
- **Memory**: Max 50 MB
- **CPU**: Max 20%

Adjust if needed for your system.

---

## 🛠️ Troubleshooting

### Service Fails to Start:

```bash
# Check logs
sudo journalctl -u web-admin -n 50

# Check if port 8080 is available
sudo netstat -tlnp | grep 8080

# Manually test web admin
cd /home/weatherstation1/Gateway-Prasena
python3 -m weatherstation.main --service web
```

### Socket Not Listening:

```bash
# Restart socket
sudo systemctl restart web-admin.socket

# Check if socket is active
sudo systemctl is-active web-admin.socket

# Should output: "active"
```

### Slow First Load:

First access takes 2-3 seconds (normal - service starting).
Subsequent accesses are instant while service is running.

---

## 🗑️ Disable Socket Activation

To go back to always-running mode:

```bash
# Stop and disable socket
sudo systemctl stop web-admin.socket
sudo systemctl disable web-admin.socket

# Enable web admin in config
nano weatherstation/config/system_config.yaml
```

```yaml
web_admin:
  enabled: true  # Change to true
```

```bash
# Restart main service
sudo systemctl restart weatherstation
```

---

## 📊 How It Works

```
┌─────────────────────────────────────────────┐
│  IDLE STATE (Zero Memory)                   │
├─────────────────────────────────────────────┤
│  systemd listens on port 8080               │
│  web-admin.service: inactive (dead)         │
│  Memory usage: 0 MB ✅                      │
└─────────────────────────────────────────────┘
                    ↓
            User opens browser
            http://192.168.0.122:8080
                    ↓
┌─────────────────────────────────────────────┐
│  ACTIVE STATE (Service Running)             │
├─────────────────────────────────────────────┤
│  systemd triggers web-admin.service         │
│  Flask app starts (2-3 sec)                 │
│  User can configure settings                │
│  Memory usage: 15-30 MB                     │
└─────────────────────────────────────────────┘
                    ↓
            User closes browser
            5 minutes idle timeout
                    ↓
┌─────────────────────────────────────────────┐
│  AUTO-STOP (Back to Idle)                   │
├─────────────────────────────────────────────┤
│  web-admin.service stops                    │
│  systemd keeps listening on port 8080       │
│  Memory freed: 15-30 MB ✅                  │
└─────────────────────────────────────────────┘
```

---

## ✨ Benefits

1. **Memory Efficient**: Only uses RAM when actually needed
2. **Always Available**: Still accessible anytime via URL
3. **Zero Configuration**: Works automatically after setup
4. **Battle-Tested**: Native systemd feature, very reliable
5. **Perfect for Low-RAM Systems**: Ideal for Pi Zero, Pi 3, etc.

---

## 📝 Notes

- First access takes 2-3 seconds (service startup time)
- Service auto-stops after 5 minutes idle (configurable)
- Socket listener uses <1 MB memory
- Main weatherstation service runs independently
- Can be used alongside `--service all` mode

---

**Recommended for systems with <1GB RAM!** 🎯
