# Systemd Service Configuration

## Overview

Weather Station Gateway runs as a **single systemd service** with multi-threaded execution for optimal performance on Raspberry Pi Zero 2W.

## Services Included

The main service (`weatherstation.service`) runs all components in one process:
- **Battery Reader**: Reads RS485/Modbus battery sensors with aggregation
- **Upload Service**: Uploads data to Prasena server with immediate delete
- **Weather Receiver**: HTTP endpoint for weather station data
- **MQTT Publisher**: Publishes sensor data to MQTT broker

## Architecture

- **Single Process**: All services run in one Python process
- **Multi-Threading**: Each service runs in its own thread
- **Auto-Restart**: Individual threads auto-restart on failure
- **Graceful Shutdown**: Proper signal handling (SIGTERM/SIGINT)
- **Resource Efficient**: Optimized for 512MB RAM (Pi Zero 2W)

## Installation

### 1. Install pigpiod (required for battery sensors)

```bash
sudo apt update
sudo apt install pigpio python3-pigpio
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

### 2. Copy service files

```bash
sudo cp weatherstation.service /etc/systemd/system/
sudo cp weatherstation-cleanup.service /etc/systemd/system/
sudo cp weatherstation-cleanup.timer /etc/systemd/system/
```

### 3. Update service file paths

Edit `/etc/systemd/system/weatherstation.service`:
- Change `User` and `Group` to your username
- Update `WorkingDirectory` to your installation path
- Update `ExecStart` path to your `run.py`

### 4. Reload systemd

```bash
sudo systemctl daemon-reload
```

### 5. Enable and start services

```bash
# Main gateway service
sudo systemctl enable weatherstation
sudo systemctl start weatherstation

# Cleanup service (runs daily)
sudo systemctl enable weatherstation-cleanup.timer
sudo systemctl start weatherstation-cleanup.timer
```

## Management Commands

### Check Status

```bash
sudo systemctl status weatherstation
```

### View Logs

```bash
# Real-time logs
sudo journalctl -u weatherstation -f

# Last 100 lines
sudo journalctl -u weatherstation -n 100

# Logs since boot
sudo journalctl -u weatherstation -b
```

### Restart Service

```bash
sudo systemctl restart weatherstation
```

### Stop Service

```bash
sudo systemctl stop weatherstation
```

### Disable Auto-start

```bash
sudo systemctl disable weatherstation
```

## Monitoring

### Service Health

```bash
# Check if running
sudo systemctl is-active weatherstation

# Check if enabled
sudo systemctl is-enabled weatherstation

# View resource usage
sudo systemctl status weatherstation
```

### Thread Status

Logs will show status of each thread:
```
[battery] Starting service...
[upload] Starting service...
[weather] Starting service...
[mqtt] Starting service...
```

### Auto-Restart

If a thread crashes, it will auto-restart:
```
[battery] Service crashed: Connection timeout
[battery] Auto-restart #1 in 10s...
```

## Troubleshooting

### Service won't start

1. Check pigpiod is running:
   ```bash
   sudo systemctl status pigpiod
   ```

2. Check permissions:
   ```bash
   ls -l /home/weatherstation1/sistem/
   ```

3. Check Python environment:
   ```bash
   /home/weatherstation1/sistem/venv/bin/python3 --version
   ```

### High memory usage

Monitor memory:
```bash
sudo systemctl status weatherstation
```

The service has a `MemoryLimit=384M` safeguard.

### Threads not starting

Check individual service logs:
```bash
sudo journalctl -u weatherstation | grep "\[battery\]"
sudo journalctl -u weatherstation | grep "\[upload\]"
sudo journalctl -u weatherstation | grep "\[weather\]"
sudo journalctl -u weatherstation | grep "\[mqtt\]"
```

### Graceful shutdown not working

Increase timeout in service file:
```ini
TimeoutStopSec=60
```

## Performance Tuning

### CPU Quota

Default: 200% (2 cores)
```ini
CPUQuota=200%
```

Increase for faster processing:
```ini
CPUQuota=400%
```

### Memory Limit

Default: 384MB
```ini
MemoryLimit=384M
```

Adjust based on available RAM.

### Thread Monitoring Interval

Edit `weatherstation/service_manager.py`:
```python
self.monitor_loop(check_interval=30)  # Default: 30s
```

## Configuration

Main configuration file:
```
/home/weatherstation1/sistem/weatherstation/config/system_config.yaml
```

After changing config:
```bash
sudo systemctl restart weatherstation
```

## Logs

Service logs go to:
- systemd journal: `journalctl -u weatherstation`
- File logs (configurable in system_config.yaml):
  - `./logs/main.log` - ServiceManager
  - `./logs/battery_reader.log` - Battery service
  - `./logs/upload_service.log` - Upload service
  - `./logs/weather_receiver.log` - Weather service
  - `./logs/mqtt_publisher.log` - MQTT service

## Cleanup Service

Runs daily via timer to cleanup orphaned uploaded records (safety net):

```bash
# Check timer status
sudo systemctl status weatherstation-cleanup.timer

# Manual run
sudo systemctl start weatherstation-cleanup.service

# View cleanup logs
sudo journalctl -u weatherstation-cleanup
```
