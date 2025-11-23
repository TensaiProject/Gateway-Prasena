/**
 * Weather Station Gateway - Settings Page
 * WiFi Configuration and Network Management
 */

// Load network info when page loads
document.addEventListener('DOMContentLoaded', function() {
    loadNetworkInfo();
    loadSettings();
});

/**
 * Load current network information
 */
async function loadNetworkInfo() {
    try {
        const response = await fetch('/api/network/info');
        const data = await response.json();

        if (data.success) {
            const networkInfo = data.data;

            // Update WiFi SSID
            const ssidInput = document.getElementById('current-wifi-ssid');
            const wifiStatus = document.getElementById('wifi-status');

            if (networkInfo.wifi.connected) {
                ssidInput.value = networkInfo.wifi.ssid || 'Not connected';
                wifiStatus.textContent = '●';
                wifiStatus.style.color = 'var(--color-success)';
            } else {
                ssidInput.value = 'Not connected';
                wifiStatus.textContent = '●';
                wifiStatus.style.color = 'var(--color-danger)';
            }

            // Update IP info
            document.getElementById('current-ip-address').value = networkInfo.ip.address || 'N/A';
            document.getElementById('current-gateway').value = networkInfo.ip.gateway || 'N/A';
            document.getElementById('current-dns').value = networkInfo.ip.dns || 'N/A';
            document.getElementById('current-ip-method').value = networkInfo.ip.method || 'dhcp';
        }
    } catch (error) {
        console.error('Failed to load network info:', error);
    }
}

/**
 * Load existing settings (intervals, MQTT, etc.)
 */
async function loadSettings() {
    try {
        // Load interval settings
        const intervalsResponse = await fetch('/api/config/intervals');
        const intervalsData = await intervalsResponse.json();

        if (intervalsData.success) {
            const data = intervalsData.data;

            // Battery sensor intervals
            if (data.battery_sensors) {
                document.getElementById('battery-sampling-rate').value = data.battery_sensors.sampling_rate || 1;
                document.getElementById('battery-poll-interval').value = data.battery_sensors.poll_interval || 1;
                document.getElementById('battery-aggregation-window').value = data.battery_sensors.aggregation_window || 60;
            }

            // MQTT intervals
            if (data.mqtt && data.mqtt.publisher) {
                document.getElementById('mqtt-poll-interval').value = data.mqtt.publisher.poll_interval || 5;
                document.getElementById('mqtt-batch-size').value = data.mqtt.publisher.batch_size || 10;
            }

            // Database
            if (data.database) {
                document.getElementById('database-backup-interval').value = data.database.backup_interval || 86400;
            }
        }

        // Load MQTT connection settings
        const mqttResponse = await fetch('/api/config/mqtt');
        const mqttData = await mqttResponse.json();

        if (mqttData.success) {
            const mqtt = mqttData.data;
            document.getElementById('mqtt-broker-host').value = mqtt.broker_host || '';
            document.getElementById('mqtt-broker-port').value = mqtt.broker_port || 1883;
            document.getElementById('mqtt-username').value = mqtt.username || '';
            document.getElementById('mqtt-password').value = mqtt.password || '';
            document.getElementById('mqtt-qos').value = mqtt.qos || 1;
            document.getElementById('mqtt-keepalive').value = mqtt.keepalive || 60;
            document.getElementById('mqtt-client-id').value = mqtt.client_id || '';
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

// Save settings form (existing functionality - keep as is)
document.getElementById('save-settings-btn')?.addEventListener('click', async function() {
    // ... existing save settings code ...
});

// Restart services button (existing functionality - keep as is)
document.getElementById('restart-services-btn')?.addEventListener('click', async function() {
    // ... existing restart services code ...
});
