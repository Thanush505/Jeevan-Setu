/**
 * dashboard.js — Live dashboard updates via AJAX polling.
 */

(function () {
    'use strict';

    const POLL_INTERVAL = 30000; // 30 seconds

    /**
     * Fetch and update the alert badge count.
     */
    function updateAlertBadge() {
        fetch('/alerts/api/count')
            .then(res => res.json())
            .then(data => {
                const badge = document.getElementById('alert-badge');
                if (badge) {
                    const total = data.reduce((sum, item) => sum + item.count, 0);
                    badge.textContent = total > 0 ? total : '';
                    badge.style.display = total > 0 ? 'inline' : 'none';
                }
            })
            .catch(err => console.error('Alert badge update failed:', err));
    }

    /**
     * Simple client-side patient search.
     */
    function setupSearch() {
        const searchInput = document.getElementById('search-input');
        if (!searchInput) return;

        searchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase();
            const cards = document.querySelectorAll('.patient-card');

            cards.forEach(card => {
                const text = card.textContent.toLowerCase();
                card.style.display = text.includes(query) ? '' : 'none';
            });
        });
    }

    // Initialize
    document.addEventListener('DOMContentLoaded', function () {
        updateAlertBadge();
        setupSearch();
        setInterval(updateAlertBadge, POLL_INTERVAL);
    });
})();
