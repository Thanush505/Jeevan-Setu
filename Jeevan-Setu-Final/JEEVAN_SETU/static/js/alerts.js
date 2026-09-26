/**
 * alerts.js — Alert panel interactivity.
 */

(function () {
    'use strict';

    const POLL_INTERVAL = 15000; // 15 seconds

    /**
     * Acknowledge an alert via API.
     */
    window.acknowledgeAlert = function (alertId) {
        fetch(`/alerts/acknowledge/${alertId}`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                const alertEl = document.getElementById(`alert-${alertId}`);
                if (alertEl) {
                    alertEl.style.opacity = '0.5';
                    alertEl.style.transition = 'opacity 0.3s';
                    setTimeout(() => alertEl.remove(), 500);
                }
            })
            .catch(err => {
                console.error('Failed to acknowledge alert:', err);
                alert('Failed to acknowledge alert. Please try again.');
            });
    };

    /**
     * Refresh the alert list periodically.
     */
    function refreshAlerts() {
        fetch('/alerts/api/active')
            .then(res => res.json())
            .then(alerts => {
                // Update alert count in any badge
                const badge = document.getElementById('alert-badge');
                if (badge) {
                    badge.textContent = alerts.length > 0 ? alerts.length : '';
                }
            })
            .catch(err => console.error('Alert refresh failed:', err));
    }

    // Auto-refresh alerts
    setInterval(refreshAlerts, POLL_INTERVAL);
})();
