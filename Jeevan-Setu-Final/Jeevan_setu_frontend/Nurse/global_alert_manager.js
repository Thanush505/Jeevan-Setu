/**
 * Jeevan Setu — Global Alert & Transfer Monitoring System
 * 
 * Provides universal, role-aware, real-time emergency critical alert popups
 * and prolonged ready-to-transfer approval notifications across all Doctor
 * and Nurse pages without requiring navigation back to the dashboard.
 * 
 * Includes fully self-contained, isolated CSS styling to ensure flawless rendering
 * on any page regardless of whether Tailwind CDN or other stylesheets are present.
 */

(function () {
    'use strict';

    // Configuration
    const POLL_INTERVAL_MS = 5000; // 5 seconds
    const DISMISSED_SESSION_KEY = 'jeevan_setu_dismissed_alerts';
    let isPollingActive = false;
    let pollTimer = null;
    let activeModals = new Map(); // alert_id -> DOM element

    // Self-contained CSS injection
    function injectGlobalAlertStyles() {
        if (document.getElementById('js-global-alert-styles')) return;

        const style = document.createElement('style');
        style.id = 'js-global-alert-styles';
        style.textContent = `
            #jeevan-setu-global-overlay-root {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999999;
                display: flex;
                flex-direction: column;
                gap: 16px;
                max-width: 480px;
                width: calc(100vw - 40px);
                pointer-events: none;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }

            .js-alert-card {
                pointer-events: auto;
                background: #ffffff;
                border-radius: 16px;
                box-shadow: 0 20px 35px -5px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(0, 0, 0, 0.08);
                overflow: hidden;
                transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                animation: jsAlertSlideIn 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                box-sizing: border-box;
            }

            @keyframes jsAlertSlideIn {
                from {
                    opacity: 0;
                    transform: translateY(-20px) scale(0.96);
                }
                to {
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }
            }

            .js-alert-card-critical {
                border: 2px solid #ef4444;
                box-shadow: 0 20px 40px -8px rgba(239, 68, 68, 0.4), 0 0 0 1px rgba(239, 68, 68, 0.2);
            }

            .js-alert-card-transfer {
                border: 2px solid #f59e0b;
                box-shadow: 0 20px 40px -8px rgba(245, 158, 11, 0.35), 0 0 0 1px rgba(245, 158, 11, 0.2);
            }

            .js-alert-header {
                padding: 14px 18px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                color: #ffffff;
            }

            .js-alert-header-critical {
                background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
            }

            .js-alert-header-transfer {
                background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
            }

            .js-alert-header-left {
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .js-alert-icon-box {
                width: 36px;
                height: 36px;
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.2);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 20px;
            }

            .js-alert-title-main {
                font-weight: 700;
                font-size: 14px;
                letter-spacing: 0.02em;
                margin: 0;
                line-height: 1.2;
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .js-alert-subtitle {
                font-size: 11px;
                opacity: 0.9;
                margin: 2px 0 0 0;
                font-weight: 500;
            }

            .js-alert-badge-tag {
                background: rgba(255, 255, 255, 0.25);
                padding: 2px 8px;
                border-radius: 9999px;
                font-size: 10px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }

            .js-alert-btn-close {
                background: transparent;
                border: none;
                color: rgba(255, 255, 255, 0.8);
                cursor: pointer;
                padding: 4px;
                border-radius: 6px;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s;
            }
            .js-alert-btn-close:hover {
                background: rgba(255, 255, 255, 0.2);
                color: #ffffff;
            }

            .js-alert-body {
                padding: 16px 18px;
                display: flex;
                flex-direction: column;
                gap: 12px;
                background: #ffffff;
            }

            .js-alert-patient-box {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 12px 14px;
                border-radius: 12px;
                background: #fef2f2;
                border: 1px solid #fee2e2;
            }

            .js-alert-patient-box-transfer {
                background: #fffbeb;
                border: 1px solid #fef3c7;
            }

            .js-alert-patient-name {
                font-weight: 700;
                font-size: 16px;
                color: #111827;
                margin: 0 0 2px 0;
            }

            .js-alert-patient-sub {
                font-size: 12px;
                color: #4b5563;
                margin: 0;
                font-family: monospace;
            }

            .js-alert-score-badge {
                display: inline-flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                background: #ef4444;
                color: #ffffff;
                font-weight: 800;
                font-size: 16px;
                padding: 4px 12px;
                border-radius: 8px;
                min-width: 45px;
            }

            .js-alert-score-label {
                font-size: 9px;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-top: 1px;
            }

            .js-alert-notice-box {
                padding: 10px 12px;
                border-radius: 10px;
                background: #f9fafb;
                border: 1px solid #e5e7eb;
                font-size: 12px;
                color: #374151;
                line-height: 1.45;
            }

            .js-alert-actions {
                display: flex;
                align-items: center;
                justify-content: flex-end;
                gap: 8px;
                padding-top: 4px;
            }

            .js-btn {
                padding: 8px 16px;
                border-radius: 10px;
                font-size: 12px;
                font-weight: 600;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                text-decoration: none;
                transition: all 0.2s;
                border: none;
            }

            .js-btn-outline {
                background: #ffffff;
                border: 1px solid #d1d5db;
                color: #374151;
            }
            .js-btn-outline:hover {
                background: #f3f4f6;
                border-color: #9ca3af;
            }

            .js-btn-critical {
                background: #dc2626;
                color: #ffffff;
                box-shadow: 0 4px 10px rgba(220, 38, 38, 0.3);
            }
            .js-btn-critical:hover {
                background: #b91c1c;
            }

            .js-btn-approve {
                background: #059669;
                color: #ffffff;
                box-shadow: 0 4px 10px rgba(5, 150, 105, 0.3);
            }
            .js-btn-approve:hover {
                background: #047857;
            }

            .js-badge-pending-doctor {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                background: #fef3c7;
                color: #92400e;
                font-size: 11px;
                font-weight: 700;
                padding: 6px 10px;
                border-radius: 8px;
                border: 1px solid #fde68a;
                margin-right: auto;
            }
        `;
        document.head.appendChild(style);
    }

    // Helpers for session dismissed tracking
    function getDismissedAlertIds() {
        try {
            const raw = sessionStorage.getItem(DISMISSED_SESSION_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return [];
        }
    }

    function markAlertDismissedInSession(alertId) {
        try {
            const list = getDismissedAlertIds();
            if (!list.includes(alertId)) {
                list.push(alertId);
                sessionStorage.setItem(DISMISSED_SESSION_KEY, JSON.stringify(list));
            }
        } catch (e) {}
    }

    // Audio Chime
    function playAlertChime(isCritical = true) {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!AudioContext) return;
            const ctx = new AudioContext();
            const now = ctx.currentTime;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.type = isCritical ? 'sawtooth' : 'sine';

            if (isCritical) {
                osc.frequency.setValueAtTime(880, now);
                osc.frequency.setValueAtTime(660, now + 0.15);
                osc.frequency.setValueAtTime(880, now + 0.3);
                gain.gain.setValueAtTime(0.1, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.55);
            } else {
                osc.frequency.setValueAtTime(523.25, now);
                osc.frequency.setValueAtTime(659.25, now + 0.15);
                gain.gain.setValueAtTime(0.06, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
            }

            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now);
            osc.stop(now + 0.6);
        } catch (e) {}
    }

    function getOverlayContainer() {
        let container = document.getElementById('jeevan-setu-global-overlay-root');
        if (!container) {
            container = document.createElement('div');
            container.id = 'jeevan-setu-global-overlay-root';
            document.body.appendChild(container);
        }
        return container;
    }

    function getAuthHeaders() {
        const token = localStorage.getItem('jeevan_setu_token');
        const headers = { 'Accept': 'application/json' };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    }

    // Poll the backend global feed
    async function fetchGlobalAlertFeed() {
        try {
            const response = await fetch('/api/v1/alerts/global-feed', {
                method: 'GET',
                headers: getAuthHeaders()
            });

            if (response.status === 401 || response.status === 403) return;
            if (!response.ok) return;

            const data = await response.json();
            if (!data.success) return;

            const dismissed = getDismissedAlertIds();
            const isDoctor = data.can_approve_transfers || data.role === 'doctor' || data.role === 'admin';
            const isNurse = data.role === 'nurse';

            // 1. Process CRITICAL Emergency Alerts (Render top 1 active modal at a time to prevent screen flooding)
            if (Array.isArray(data.emergency_alerts) && data.emergency_alerts.length > 0) {
                // Filter out dismissed
                const pendingCrit = data.emergency_alerts.filter(a => !dismissed.includes(`crit_${a.alert_id}`));
                if (pendingCrit.length > 0) {
                    const topAlert = pendingCrit[0];
                    const alertKey = `crit_${topAlert.alert_id}`;
                    if (!activeModals.has(alertKey)) {
                        // If another emergency modal is displayed, remove it before showing new one
                        for (let [k, modalEl] of activeModals.entries()) {
                            if (k.startsWith('crit_')) {
                                removeModalWithAnimation(k);
                            }
                        }
                        renderCriticalEmergencyPopup(topAlert, alertKey, isDoctor, isNurse, pendingCrit.length - 1);
                    }
                }
            }

            // 2. Process Prolonged Ready-to-Transfer Alerts (Top 1 at a time)
            if (Array.isArray(data.transfer_alerts) && data.transfer_alerts.length > 0) {
                const pendingTrans = data.transfer_alerts.filter(t => !dismissed.includes(`trans_${t.recommendation_id}_${t.patient_id}`));
                if (pendingTrans.length > 0) {
                    const topTrans = pendingTrans[0];
                    const transKey = `trans_${topTrans.recommendation_id}_${topTrans.patient_id}`;
                    if (!activeModals.has(transKey)) {
                        for (let [k, modalEl] of activeModals.entries()) {
                            if (k.startsWith('trans_')) {
                                removeModalWithAnimation(k);
                            }
                        }
                        renderTransferAlertPopup(topTrans, transKey, isDoctor, isNurse, pendingTrans.length - 1);
                    }
                }
            }

            // Update badge counters
            updatePageNotificationBadges(data.unread_count);

        } catch (err) {}
    }

    // Render CRITICAL Emergency Modal Popup with bulletproof styling
    function renderCriticalEmergencyPopup(alert, alertKey, isDoctor, isNurse, remainingCount = 0) {
        injectGlobalAlertStyles();
        const root = getOverlayContainer();

        const modal = document.createElement('div');
        modal.id = `modal-${alertKey}`;
        modal.className = 'js-alert-card js-alert-card-critical';

        const patientName = alert.patient_name || 'Patient';
        const uhid = alert.patient_code || `P${alert.patient_id}`;
        const ward = alert.ward_type || 'ICU';
        const bed = alert.bed_number || 'N/A';
        const score = alert.value !== undefined ? alert.value : (alert.latest_ews_score || 8);
        const patientId = alert.patient_id;

        let targetPatientUrl = `../Doctor_patient_reports/Doctor_patient_reports.html?patient_id=${patientId}`;
        if (isNurse) {
            targetPatientUrl = `../Nurse_enter_vitals/Nurse_enter_vitals.html?patient_id=${patientId}`;
        }

        const moreTag = remainingCount > 0 ? `<span class="js-alert-badge-tag">+${remainingCount} more</span>` : '';

        modal.innerHTML = `
            <div class="js-alert-header js-alert-header-critical">
                <div class="js-alert-header-left">
                    <div class="js-alert-icon-box">⚠️</div>
                    <div>
                        <h3 class="js-alert-title-main">
                            CRITICAL EMERGENCY ${moreTag}
                        </h3>
                        <p class="js-alert-subtitle">Immediate Clinical Review Required</p>
                    </div>
                </div>
                <button type="button" class="js-alert-btn-close btn-dismiss-alert" title="Dismiss">✕</button>
            </div>

            <div class="js-alert-body">
                <div class="js-alert-patient-box">
                    <div>
                        <div style="font-size: 10px; font-weight: 700; color: #b91c1c; text-transform: uppercase;">PATIENT DETAILS</div>
                        <h4 class="js-alert-patient-name">${patientName}</h4>
                        <p class="js-alert-patient-sub">UHID: ${uhid} • ${ward} (Bed ${bed})</p>
                    </div>
                    <div style="text-align: right;">
                        <div class="js-alert-score-badge">
                            ${score}
                            <span class="js-alert-score-label">EWS</span>
                        </div>
                    </div>
                </div>

                <div class="js-alert-notice-box">
                    <strong>Clinical Notice:</strong> ${alert.message || 'Critical condition detected. Immediate clinical review required.'}
                </div>

                <div class="js-alert-actions">
                    <button type="button" class="js-btn js-btn-outline btn-acknowledge-alert">
                        ✓ Acknowledge
                    </button>
                    <a href="${targetPatientUrl}" class="js-btn js-btn-critical">
                        👁 View Patient
                    </a>
                </div>
            </div>
        `;

        root.appendChild(modal);
        activeModals.set(alertKey, modal);
        playAlertChime(true);

        modal.querySelector('.btn-acknowledge-alert')?.addEventListener('click', async () => {
            try {
                await fetch(`/api/v1/alerts/emergency/acknowledge/${alert.alert_id}`, {
                    method: 'POST',
                    headers: getAuthHeaders()
                });
            } catch (e) {}
            markAlertDismissedInSession(alertKey);
            removeModalWithAnimation(alertKey);
            setTimeout(fetchGlobalAlertFeed, 400);
        });

        modal.querySelector('.btn-dismiss-alert')?.addEventListener('click', () => {
            markAlertDismissedInSession(alertKey);
            removeModalWithAnimation(alertKey);
            setTimeout(fetchGlobalAlertFeed, 400);
        });
    }

    // Render Ready-to-Transfer Modal Popup with bulletproof styling
    function renderTransferAlertPopup(transfer, transferKey, isDoctor, isNurse, remainingCount = 0) {
        injectGlobalAlertStyles();
        const root = getOverlayContainer();

        const modal = document.createElement('div');
        modal.id = `modal-${transferKey}`;
        modal.className = 'js-alert-card js-alert-card-transfer';

        const patientName = transfer.patient_name || 'Patient';
        const uhid = transfer.patient_code || `P${transfer.patient_id}`;
        const fromWard = transfer.from_ward || 'ICU';
        const toWard = transfer.to_ward || 'HDU';
        const waitingTime = transfer.waiting_formatted || `${transfer.minutes_waiting || 0} mins`;
        const patientId = transfer.patient_id;
        const recId = transfer.recommendation_id;
        const transferId = transfer.transfer_id;

        let targetPatientUrl = `../Doctor_transfer_recommendations/Doctor_transfer_recommendations.html?patient_id=${patientId}`;
        if (isNurse) {
            targetPatientUrl = `../Nurse_my_patients/Nurse_my_patients.html?patient_id=${patientId}`;
        }

        let actionButtonsHtml = '';
        if (isDoctor) {
            actionButtonsHtml = `
                <button type="button" class="js-btn js-btn-outline btn-dismiss-transfer">Dismiss</button>
                <a href="${targetPatientUrl}" class="js-btn js-btn-outline">Review</a>
                <button type="button" class="js-btn js-btn-approve btn-approve-transfer">
                    ✓ Approve Transfer
                </button>
            `;
        } else {
            actionButtonsHtml = `
                <span class="js-badge-pending-doctor">
                    ⏳ Doctor Approval Pending
                </span>
                <button type="button" class="js-btn js-btn-outline btn-dismiss-transfer">Dismiss</button>
                <a href="${targetPatientUrl}" class="js-btn js-btn-critical" style="background:#0053db;">
                    👁 View Patient
                </a>
            `;
        }

        modal.innerHTML = `
            <div class="js-alert-header js-alert-header-transfer">
                <div class="js-alert-header-left">
                    <div class="js-alert-icon-box">📋</div>
                    <div>
                        <h3 class="js-alert-title-main">
                            ${isDoctor ? 'TRANSFER APPROVAL REQUIRED' : 'READY TO TRANSFER'}
                        </h3>
                        <p class="js-alert-subtitle">${fromWard} → ${toWard} (${waitingTime} waiting)</p>
                    </div>
                </div>
                <button type="button" class="js-alert-btn-close btn-close-modal" title="Close">✕</button>
            </div>

            <div class="js-alert-body">
                <div class="js-alert-patient-box js-alert-patient-box-transfer">
                    <div>
                        <div style="font-size: 10px; font-weight: 700; color: #b45309; text-transform: uppercase;">PATIENT</div>
                        <h4 class="js-alert-patient-name">${patientName}</h4>
                        <p class="js-alert-patient-sub">UHID: ${uhid} • Current: ${fromWard}</p>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 11px; font-weight: 700; color: #b45309;">TARGET</div>
                        <div style="font-size: 16px; font-weight: 800; color: #0053db;">${toWard}</div>
                    </div>
                </div>

                <div class="js-alert-notice-box">
                    <strong>Recommendation:</strong> ${transfer.message || `Patient ${patientName} is clinically stable and ready for step-down transfer from ${fromWard} to ${toWard}. Attending Doctor authorization required.`}
                </div>

                <div class="js-alert-actions">
                    ${actionButtonsHtml}
                </div>
            </div>
        `;

        root.appendChild(modal);
        activeModals.set(transferKey, modal);
        playAlertChime(false);

        modal.querySelector('.btn-dismiss-transfer')?.addEventListener('click', () => {
            markAlertDismissedInSession(transferKey);
            removeModalWithAnimation(transferKey);
            setTimeout(fetchGlobalAlertFeed, 400);
        });
        modal.querySelector('.btn-close-modal')?.addEventListener('click', () => {
            markAlertDismissedInSession(transferKey);
            removeModalWithAnimation(transferKey);
            setTimeout(fetchGlobalAlertFeed, 400);
        });

        if (isDoctor) {
            modal.querySelector('.btn-approve-transfer')?.addEventListener('click', async (e) => {
                const btn = e.currentTarget;
                btn.disabled = true;
                btn.innerText = 'Approving...';

                try {
                    let approveUrl = transferId ? `/api/v1/transfers/${transferId}/approve` : (recId ? `/api/v1/decision/approve/${recId}` : null);
                    const res = await fetch(approveUrl, {
                        method: 'POST',
                        headers: {
                            ...getAuthHeaders(),
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ remarks: 'Approved via Global Emergency & Transfer Alert Layer' })
                    });

                    const json = await res.json();
                    if (res.ok && json.success) {
                        btn.innerText = '✓ Approved!';
                        setTimeout(() => {
                            markAlertDismissedInSession(transferKey);
                            removeModalWithAnimation(transferKey);
                            setTimeout(fetchGlobalAlertFeed, 400);
                        }, 1000);
                    } else {
                        alert(json.error || 'Failed to approve transfer.');
                        btn.disabled = false;
                        btn.innerText = '✓ Approve Transfer';
                    }
                } catch (err) {
                    alert('Error approving transfer.');
                    btn.disabled = false;
                    btn.innerText = '✓ Approve Transfer';
                }
            });
        }
    }

    function removeModalWithAnimation(key) {
        const el = activeModals.get(key);
        if (el) {
            el.style.opacity = '0';
            el.style.transform = 'translateY(-15px) scale(0.95)';
            setTimeout(() => {
                if (el.parentNode) el.parentNode.removeChild(el);
                activeModals.delete(key);
            }, 250);
        }
    }

    function updatePageNotificationBadges(unreadCount) {
        const badgeContainers = document.querySelectorAll('[data-alert-badge], .badge-notification-count');
        badgeContainers.forEach(el => {
            if (unreadCount > 0) {
                el.innerText = unreadCount;
                el.style.display = '';
            }
        });
    }

    function initGlobalAlertManager() {
        if (isPollingActive) return;
        isPollingActive = true;
        injectGlobalAlertStyles();
        fetchGlobalAlertFeed();
        pollTimer = setInterval(fetchGlobalAlertFeed, POLL_INTERVAL_MS);
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                fetchGlobalAlertFeed();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initGlobalAlertManager);
    } else {
        initGlobalAlertManager();
    }
})();
