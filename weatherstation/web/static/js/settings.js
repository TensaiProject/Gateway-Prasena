/**
 * Weather Station Gateway - Settings Page
 * WiFi Configuration and Network Management
 */

// Load network info when page loads
document.addEventListener('DOMContentLoaded', function() {
    loadNetworkInfo();
    loadSettings();
    initWiFiHandlers();
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
 * Initialize WiFi configuration handlers
 */
function initWiFiHandlers() {
    // Password toggle
    const passwordToggle = document.getElementById('wifi-password-toggle');
    const passwordInput = document.getElementById('wifi-password');

    passwordToggle.addEventListener('click', function() {
        if (passwordInput.type === 'password') {
            passwordInput.type = 'text';
            passwordToggle.textContent = '👁️‍🗨️';
        } else {
            passwordInput.type = 'password';
            passwordToggle.textContent = '👁';
        }
    });

    // IP mode toggle
    const ipModeDhcp = document.getElementById('ip-mode-dhcp');
    const ipModeStatic = document.getElementById('ip-mode-static');
    const staticFields = document.getElementById('static-ip-fields');

    ipModeDhcp.addEventListener('change', function() {
        if (this.checked) {
            staticFields.classList.add('hidden');
        }
    });

    ipModeStatic.addEventListener('change', function() {
        if (this.checked) {
            staticFields.classList.remove('hidden');
        }
    });

    // WiFi Scan button
    const scanBtn = document.getElementById('wifi-scan-btn');
    scanBtn.addEventListener('click', scanWiFiNetworks);

    // WiFi Connect button
    const connectBtn = document.getElementById('wifi-connect-btn');
    connectBtn.addEventListener('click', connectToWiFi);
}

/**
 * Scan for available WiFi networks
 */
async function scanWiFiNetworks() {
    const scanBtn = document.getElementById('wifi-scan-btn');
    const scanText = document.getElementById('wifi-scan-text');
    const scanSpinner = document.getElementById('wifi-scan-spinner');
    const networksList = document.getElementById('wifi-networks-list');
    const networksContainer = document.getElementById('wifi-networks-container');

    // Show loading state
    scanBtn.disabled = true;
    scanText.textContent = 'Scanning...';
    scanSpinner.classList.remove('hidden');

    try {
        const response = await fetch('/api/wifi/scan');
        const data = await response.json();

        if (data.success && data.data.length > 0) {
            // Clear previous results
            networksContainer.innerHTML = '';

            // Populate networks list
            data.data.forEach(network => {
                const networkDiv = document.createElement('div');
                networkDiv.style.cssText = 'padding: var(--space-sm); margin-bottom: var(--space-xs); border-radius: var(--radius-sm); cursor: pointer; border: 1px solid transparent;';
                networkDiv.onmouseover = () => networkDiv.style.background = 'var(--color-bg-secondary)';
                networkDiv.onmouseout = () => networkDiv.style.background = 'transparent';

                // Signal strength indicator
                let signalBars = '';
                if (network.signal >= 75) signalBars = '▂▄▆█';
                else if (network.signal >= 50) signalBars = '▂▄▆';
                else if (network.signal >= 25) signalBars = '▂▄';
                else signalBars = '▂';

                // Security icon
                const securityIcon = network.security && network.security !== 'Open' ? '🔒' : '🔓';

                networkDiv.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong>${network.ssid}</strong>
                            <span style="margin-left: var(--space-sm); color: var(--color-text-muted);">${securityIcon}</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: var(--space-sm);">
                            <span style="font-size: 12px; color: var(--color-text-muted);">${signalBars}</span>
                            <span style="font-size: 12px; color: var(--color-text-muted);">${network.signal}%</span>
                        </div>
                    </div>
                `;

                // Click to select network
                networkDiv.addEventListener('click', function() {
                    document.getElementById('wifi-ssid').value = network.ssid;

                    // Highlight selected network
                    networksContainer.querySelectorAll('div').forEach(div => {
                        div.style.borderColor = 'transparent';
                    });
                    networkDiv.style.borderColor = 'var(--color-primary)';
                });

                networksContainer.appendChild(networkDiv);
            });

            // Show networks list
            networksList.classList.remove('hidden');
        } else {
            alert('No WiFi networks found. Please try again.');
        }
    } catch (error) {
        console.error('WiFi scan failed:', error);
        alert('Failed to scan WiFi networks. Please try again.');
    } finally {
        // Reset button state
        scanBtn.disabled = false;
        scanText.textContent = 'Scan WiFi Networks';
        scanSpinner.classList.add('hidden');
    }
}

/**
 * Connect to WiFi network
 */
async function connectToWiFi() {
    const ssid = document.getElementById('wifi-ssid').value.trim();
    const password = document.getElementById('wifi-password').value;
    const ipMethod = document.querySelector('input[name="ip-config-mode"]:checked').value;

    // Validation
    if (!ssid) {
        alert('Please enter WiFi SSID');
        return;
    }

    if (password && password.length < 8) {
        alert('Password must be at least 8 characters');
        return;
    }

    // Get static IP fields if selected
    let requestData = {
        ssid: ssid,
        password: password,
        ip_method: ipMethod
    };

    if (ipMethod === 'static') {
        const ipAddress = document.getElementById('wifi-ip-address').value.trim();
        const gateway = document.getElementById('wifi-gateway').value.trim();
        const netmask = document.getElementById('wifi-netmask').value.trim();
        const dns = document.getElementById('wifi-dns').value.trim();

        if (!ipAddress || !gateway) {
            alert('IP Address and Gateway are required for static IP');
            return;
        }

        requestData.ip_address = ipAddress;
        requestData.gateway = gateway;
        requestData.netmask = netmask;
        requestData.dns = dns;
    }

    // Show loading state
    const connectBtn = document.getElementById('wifi-connect-btn');
    const connectText = document.getElementById('wifi-connect-text');
    const connectSpinner = document.getElementById('wifi-connect-spinner');

    connectBtn.disabled = true;
    connectText.textContent = `Connecting to ${ssid}...`;
    connectSpinner.classList.remove('hidden');

    try {
        const response = await fetch('/api/config/wifi', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        const data = await response.json();

        if (data.success) {
            // Success notification with new IP
            const newIp = data.data.ip_address || 'Unknown';
            const message = `✓ Successfully connected to ${ssid}\n\nNew IP Address: ${newIp}`;

            alert(message);

            // Reload network info to show new values
            await loadNetworkInfo();

            // Clear password field
            document.getElementById('wifi-password').value = '';
        } else {
            alert(`Failed to connect to WiFi: ${data.error}`);
        }
    } catch (error) {
        console.error('WiFi connection failed:', error);
        alert('Failed to connect to WiFi. Please check your credentials and try again.');
    } finally {
        // Reset button state
        connectBtn.disabled = false;
        connectText.textContent = 'Connect to WiFi';
        connectSpinner.classList.add('hidden');
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
