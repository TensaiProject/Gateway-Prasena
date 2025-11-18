/**
 * Weather Station Gateway - Web Admin
 * Common JavaScript functions
 */

/**
 * Show toast notification
 * @param {string} message - Message to display
 * @param {string} type - Type of notification (success, danger, warning, info)
 */
function showNotification(message, type = 'info') {
    const toast = document.getElementById('notification-toast');
    const toastBody = toast.querySelector('.toast-body');
    const toastHeader = toast.querySelector('.toast-header');

    // Set message
    toastBody.textContent = message;

    // Set icon and color based on type
    let icon = 'bi-info-circle';
    let bgClass = 'bg-info';

    switch (type) {
        case 'success':
            icon = 'bi-check-circle';
            bgClass = 'bg-success';
            break;
        case 'danger':
            icon = 'bi-exclamation-triangle';
            bgClass = 'bg-danger';
            break;
        case 'warning':
            icon = 'bi-exclamation-circle';
            bgClass = 'bg-warning';
            break;
    }

    // Update icon
    const iconElement = toastHeader.querySelector('i');
    iconElement.className = `bi ${icon} me-2`;

    // Remove old background classes
    toastHeader.classList.remove('bg-success', 'bg-danger', 'bg-warning', 'bg-info', 'text-white');

    // Add new background class
    if (type !== 'info') {
        toastHeader.classList.add(bgClass, 'text-white');
    }

    // Show toast
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: 5000
    });
    bsToast.show();
}

/**
 * Format timestamp to human-readable format
 * @param {string} timestamp - ISO timestamp
 * @returns {string} Formatted timestamp
 */
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

/**
 * Format relative time (e.g., "2 minutes ago")
 * @param {string} timestamp - ISO timestamp
 * @returns {string} Relative time string
 */
function formatRelativeTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) {
        return `${diffSec} second${diffSec !== 1 ? 's' : ''} ago`;
    } else if (diffMin < 60) {
        return `${diffMin} minute${diffMin !== 1 ? 's' : ''} ago`;
    } else if (diffHour < 24) {
        return `${diffHour} hour${diffHour !== 1 ? 's' : ''} ago`;
    } else {
        return `${diffDay} day${diffDay !== 1 ? 's' : ''} ago`;
    }
}

/**
 * Validate numeric input within range
 * @param {number} value - Value to validate
 * @param {number} min - Minimum allowed value
 * @param {number} max - Maximum allowed value
 * @returns {boolean} True if valid
 */
function validateRange(value, min, max) {
    return value >= min && value <= max;
}

/**
 * Copy text to clipboard
 * @param {string} text - Text to copy
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard', 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showNotification('Failed to copy to clipboard', 'danger');
    });
}

/**
 * Format bytes to human-readable size
 * @param {number} bytes - Bytes to format
 * @returns {string} Formatted size string
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Debounce function - delays execution until after wait time has elapsed
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Check if API is reachable
 * @returns {Promise<boolean>} True if API is reachable
 */
async function checkApiHealth() {
    try {
        const response = await fetch('/api/status');
        return response.ok;
    } catch (error) {
        return false;
    }
}

// Global error handler for fetch requests
window.addEventListener('unhandledrejection', event => {
    console.error('Unhandled promise rejection:', event.reason);
    showNotification('An unexpected error occurred', 'danger');
});

// Log when page is loaded
console.log('Weather Station Gateway Web Admin - Ready');
