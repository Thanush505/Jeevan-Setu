/**
 * Jeevan Setu — Global Alert & Transfer Monitoring System
 * 
 * Provides universal, role-aware, real-time emergency critical alert popups
 * and prolonged ready-to-transfer approval notifications across all Doctor
 * and Nurse pages without requiring navigation back to the dashboard.
 * 
 * Role Access Rules:
 * - Nurse: Review, View, Acknowledge/Dismiss ONLY. Never render or attach 'Approve Transfer' controls.
 * - Doctor/Admin: Review, View, Acknowledge/Dismiss, and Approve Transfer.
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

    // Self-contained CSS injection matching exact Jeevan Setu UI
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
                background: #18181b;
                color: #f4f4f5;
                border-radius: 16px;
                box-shadow: 0 20px 40px -5px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.08);
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

            @keyframes jsSpin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }

            .js-alert-card-critical {
                border: 2px solid #ef4444;
                box-shadow: 0 20px 40px -8px rgba(239, 68, 68, 0.5), 0 0 0 1px rgba(239, 68, 68, 0.3);
            }

            .js-alert-card-transfer {
                border: 2px solid #b45309;
                box-shadow: 0 20px 40px -8px rgba(245, 158, 11, 0.4), 0 0 0 1px rgba(245, 158, 11, 0.25);
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
                background: linear-gradient(135deg, #b45309 0%, #92400e 100%);
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
                letter-spacing: 0.03em;
                margin: 0;
                line-height: 1.2;
                display: flex;
                align-items: center;
                gap: 8px;
                color: #ffffff;
                text-transform: uppercase;
            }

            .js-alert-subtitle {
                font-size: 12px;
                color: rgba(255, 255, 255, 0.9);
                margin: 3px 0 0 0;
                font-weight: 500;
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
                font-size: 18px;
                line-height: 1;
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
                background: #18181b;
            }

            .js-alert-patient-box {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 12px 14px;
                border-radius: 12px;
                background: #2a1b1b;
                border: 1px solid #4a2323;
            }

            .js-alert-patient-box-transfer {
                background: #221808;
                border: 1px solid #452b0d;
            }

            .js-alert-patient-name {
                font-weight: 700;
                font-size: 16px;
                color: #ffffff;
                margin: 0 0 3px 0;
            }

            .js-alert-patient-sub {
                font-size: 12px;
                color: #a1a1aa;
                margin: 0;
                font-family: inherit;
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
                padding: 12px 14px;
                border-radius: 10px;
                background: #27272a;
                border: 1px solid #3f3f46;
                font-size: 13px;
                color: #e4e4e7;
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
                box-sizing: border-box;
            }

            .js-btn-outline {
                background: transparent;
                border: 1px solid #3f3f46;
                color: #e4e4e7;
            }
            .js-btn-outline:hover {
                background: #27272a;
                border-color: #71717a;
                color: #ffffff;
            }

            .js-btn-critical {
                background: #dc2626;
                color: #ffffff;
                box-shadow: 0 4px 10px rgba(220, 38, 38, 0.4);
            }
            .js-btn-critical:hover {
                background: #b91c1c;
            }

            .js-btn-approve {
                background: #059669;
                color: #ffffff;
                border: 1px solid #10b981;
                box-shadow: 0 4px 12px rgba(5, 150, 105, 0.35);
            }
            .js-btn-approve:hover {
                background: #047857;
            }
            .js-alert-card-approved {
                border-left: 4px solid #10b981;
            }
            .js-alert-header-approved {
                background: linear-gradient(135deg, #065f46 0%, #047857 100%);
                padding: 14px 18px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-bottom: 1px solid #059669;
            }
            .js-alert-patient-box-approved {
                background: #064e3b22;
                border: 1px solid #05966944;
            }
        
        `;
        document.head.appendChild(style);
    }


    // Render Doctor Approved Transfer Modal Popup for Nurses & Staff
    function renderApprovedTransferPopup(item, itemKey, isDoctor, isNurse) {
        injectGlobalAlertStyles();
        const root = getOverlayContainer();

        const modal = document.createElement('div');
        modal.id = `modal-${itemKey}`;
        modal.className = 'js-alert-card js-alert-card-approved';

        const patientName = item.patient_name || 'Patient';
        const uhid = item.patient_code || `P${item.patient_id}`;
        const ward = item.ward_type || 'HDU';
        const bed = item.bed_number || 'Assigned';
        const patientId = item.patient_id;
        const notifId = item.notification_id;

        const pathLower = (window.location.pathname || '').toLowerCase();
        const isNursePortal = pathLower.includes('/nurse') || pathLower.includes('nurse_');
        const isDoctorPortal = pathLower.includes('/doctor') || pathLower.includes('doctor_');

        let targetPatientUrl = '#';
        if (isNursePortal) {
            targetPatientUrl = `../Nurse_my_patients/Nurse_my_patients.html?patient_id=${patientId}`;
        } else if (isDoctorPortal) {
            targetPatientUrl = `../Doctor_my_patients/Doctor_my_patients.html?patient_id=${patientId}`;
        } else {
            targetPatientUrl = isNurse ? `/Nurse/Nurse_my_patients/Nurse_my_patients.html?patient_id=${patientId}` : `/Doctor/Doctor_my_patients/Doctor_my_patients.html?patient_id=${patientId}`;
        }

        modal.innerHTML = `
            <div class="js-alert-header js-alert-header-approved">
                <div class="js-alert-header-left">
                    <div class="js-alert-icon-box">✅</div>
                    <div>
                        <h3 class="js-alert-title-main">TRANSFER APPROVED</h3>
                        <p class="js-alert-subtitle">ICU → HDU • Ready for Step-Down Transfer</p>
                    </div>
                </div>
                <button type="button" class="js-alert-btn-close btn-dismiss-approved" title="Dismiss">✕</button>
            </div>

            <div class="js-alert-body">
                <div class="js-alert-patient-box js-alert-patient-box-approved">
                    <div>
                        <h4 class="js-alert-patient-name">${patientName}</h4>
                        <p class="js-alert-patient-sub">UHID: ${uhid} • Destination: <strong>${ward}</strong> (Bed: <strong>${bed}</strong>)</p>
                    </div>
                    <div style="text-align: right;">
                        <span style="display: inline-block; padding: 4px 10px; background: #059669; color: #fff; border-radius: 6px; font-weight: 700; font-size: 11px; text-transform: uppercase;">
                            APPROVED
                        </span>
                    </div>
                </div>

                <div class="js-alert-notice-box" style="border-color: #05966944; background: #064e3b18;">
                    <strong>Transfer Notice:</strong> ${item.message || 'Doctor approval completed. Patient is approved for transfer to HDU.'}
                </div>

                <div class="js-alert-actions">
                    <button type="button" class="js-btn js-btn-outline btn-dismiss-approved">Dismiss</button>
                    <a href="${targetPatientUrl}" class="js-btn js-btn-approve">
                        👁️ Review Patient
                    </a>
                </div>
            </div>
        `;

        root.appendChild(modal);
        activeModals.set(itemKey, modal);
        playAlertChime(false);

        const dismissAction = async () => {
            if (notifId) {
                try {
                    await fetch(`/api/v1/notifications/${notifId}/read`, {
                        method: 'POST',
                        headers: getAuthHeaders()
                    });
                } catch (e) {}
            }
            markAlertDismissedInSession(itemKey);
            removeModalWithAnimation(itemKey);
            setTimeout(fetchGlobalAlertFeed, 400);
        };

        modal.querySelectorAll('.btn-dismiss-approved').forEach(btn => {
            btn.addEventListener('click', dismissAction);
        });
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

            // 1. Determine Portal Context
            const pathLower = (window.location.pathname || '').toLowerCase();
            const isNursePortal = pathLower.includes('/nurse') || pathLower.includes('nurse_');
            const isDoctorPortal = pathLower.includes('/doctor') || pathLower.includes('doctor_');
            const isAdminPortal = pathLower.includes('/admin') || pathLower.includes('admin_');

            // 2. Extract Authenticated User Role from Token, LocalStorage, and API Feed
            let storedRole = '';
            try {
                const userObj = JSON.parse(localStorage.getItem('jeevan_setu_user') || sessionStorage.getItem('jeevan_setu_user') || '{}');
                storedRole = (userObj.role || '').toLowerCase();
            } catch (e) {}

            let jwtRole = '';
            try {
                const token = localStorage.getItem('jeevan_setu_token');
                if (token && token.includes('.')) {
                    const payload = JSON.parse(atob(token.split('.')[1]));
                    jwtRole = (payload.role || '').toLowerCase();
                }
            } catch (e) {}

            const apiRole = (data.role || '').toLowerCase();
            const canApproveTransfersApi = data.can_approve_transfers === true;

            // 3. Strict Role-Aware Flag Assignment
            // - Within Nurse Portal: Always strictly Nurse (Review/Dismiss only, NO Approve button).
            // - Within Doctor/Admin Portal or for authorized Doctor: Doctor (Approve button enabled).
            let isNurse = false;
            let isDoctor = false;

            if (isNursePortal) {
                isNurse = true;
                isDoctor = false;
            } else if (isDoctorPortal || isAdminPortal) {
                isDoctor = true;
                isNurse = false;
            } else {
                if (apiRole === 'nurse' || jwtRole === 'nurse' || storedRole === 'nurse') {
                    isNurse = true;
                    isDoctor = false;
                } else if (canApproveTransfersApi || apiRole === 'doctor' || apiRole === 'admin' || jwtRole === 'doctor' || jwtRole === 'admin' || storedRole === 'doctor' || storedRole === 'admin') {
                    isDoctor = true;
                    isNurse = false;
                }
            }

            // 4. Process CRITICAL Emergency Alerts (Top 1 active modal)
            if (Array.isArray(data.emergency_alerts) && data.emergency_alerts.length > 0) {
                const pendingCrit = data.emergency_alerts.filter(a => !dismissed.includes(`crit_${a.alert_id}`));
                if (pendingCrit.length > 0) {
                    const topAlert = pendingCrit[0];
                    const alertKey = `crit_${topAlert.alert_id}`;
                    if (!activeModals.has(alertKey)) {
                        for (let [k, modalEl] of activeModals.entries()) {
                            if (k.startsWith('crit_')) {
                                removeModalWithAnimation(k);
                            }
                        }
                        renderCriticalEmergencyPopup(topAlert, alertKey, isDoctor, isNurse, pendingCrit.length - 1);
                    }
                }
            }

            // 4b. Process Approved Transfer Notifications (Top 1 active modal)
            if (Array.isArray(data.approved_transfers) && data.approved_transfers.length > 0) {
                const pendingApproved = data.approved_transfers.filter(a => !dismissed.includes(`apprv_${a.notification_id}`));
                if (pendingApproved.length > 0) {
                    const topApprv = pendingApproved[0];
                    const apprvKey = `apprv_${topApprv.notification_id}`;
                    if (!activeModals.has(apprvKey)) {
                        for (let [k, modalEl] of activeModals.entries()) {
                            if (k.startsWith('apprv_')) {
                                removeModalWithAnimation(k);
                            }
                        }
                        renderApprovedTransferPopup(topApprv, apprvKey, isDoctor, isNurse);
                    }
                }
            }

            // 5. Process Prolonged Ready-to-Transfer Alerts (Top 1 active modal)
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

    // Render CRITICAL Emergency Modal Popup
    function renderCriticalEmergencyPopup(alert, alertKey, isDoctor, isNurse, remainingCount = 0) {
        injectGlobalAlertStyles();
        const root = getOverlayContainer();

        const modal = document.createElement('div');
        modal.id = `modal-${alertKey}`;
        modal.className = 'js-alert-card js-alert-card-critical';

        const patientName = alert.patient_name || 'Patient';
        const uhid = alert.patient_code || `P${alert.patient_id}`;
        const ward = alert.ward_type || 'ICU';
        const bed = alert.bed_number || '--';
        const score = alert.ews_score ?? alert.score ?? '--';
        const param = alert.parameter ? alert.parameter.toUpperCase() : 'VITAL SIGN';
        const patientId = alert.patient_id;

        const pathLower = (window.location.pathname || '').toLowerCase();
        const isNursePortal = pathLower.includes('/nurse') || pathLower.includes('nurse_');
        const isDoctorPortal = pathLower.includes('/doctor') || pathLower.includes('doctor_');

        let targetPatientUrl = '#';
        if (isDoctorPortal) {
            targetPatientUrl = `../Doctor_my_patients/Doctor_my_patients.html?patient_id=${patientId}`;
        } else if (isNursePortal) {
            targetPatientUrl = `../Nurse_my_patients/Nurse_my_patients.html?patient_id=${patientId}`;
        } else {
            targetPatientUrl = isDoctor ? `/Doctor/Doctor_my_patients/Doctor_my_patients.html?patient_id=${patientId}` : `/Nurse/Nurse_my_patients/Nurse_my_patients.html?patient_id=${patientId}`;
        }

        modal.innerHTML = `
            <div class="js-alert-header js-alert-header-critical">
                <div class="js-alert-header-left">
                    <div class="js-alert-icon-box">🚨</div>
                    <div>
                        <h3 class="js-alert-title-main">CRITICAL EMERGENCY ALERT</h3>
                        <p class="js-alert-subtitle">${ward} (Bed ${bed}) • ${param} DETERIORATION</p>
                    </div>
                </div>
                <button type="button" class="js-alert-btn-close btn-dismiss-alert" title="Dismiss">✕</button>
            </div>

            <div class="js-alert-body">
                <div class="js-alert-patient-box">
                    <div>
                        <div style="font-size: 10px; font-weight: 700; color: #ef4444; text-transform: uppercase;">PATIENT DETAILS</div>
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
                        👁️ View Patient
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

    // Render Ready-to-Transfer Modal Popup with role-aware actions
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

        const pathLower = (window.location.pathname || '').toLowerCase();
        const isNursePortal = pathLower.includes('/nurse') || pathLower.includes('nurse_');
        const isDoctorPortal = pathLower.includes('/doctor') || pathLower.includes('doctor_');

        let targetPatientUrl = '#';
        if (isDoctorPortal) {
            targetPatientUrl = `../Doctor_transfer_recommendations/Doctor_transfer_recommendations.html?patient_id=${patientId}`;
        } else if (isNursePortal) {
            targetPatientUrl = `../Nurse_my_patients/Nurse_my_patients.html?patient_id=${patientId}`;
        } else {
            targetPatientUrl = isDoctor ? `/Doctor/Doctor_transfer_recommendations/Doctor_transfer_recommendations.html?patient_id=${patientId}` : `/Nurse/Nurse_my_patients/Nurse_my_patients.html?patient_id=${patientId}`;
        }

        let actionButtonsHtml = '';
        if (isDoctor && !isNurse) {
            // Doctor View: Dismiss, Review, and Approve Transfer
            actionButtonsHtml = `
                <button type="button" class="js-btn js-btn-outline btn-dismiss-transfer">Dismiss</button>
                <a href="${targetPatientUrl}" class="js-btn js-btn-outline">Review</a>
                <button type="button" class="js-btn js-btn-approve btn-approve-transfer">
                    ✓ Approve Transfer
                </button>
            `;
        } else {
            // Nurse View: Review & Dismiss ONLY. Strictly NO approval button rendered.
            actionButtonsHtml = `
                <button type="button" class="js-btn js-btn-outline btn-dismiss-transfer">Dismiss</button>
                <a href="${targetPatientUrl}" class="js-btn js-btn-outline">Review</a>
            `;
        }

        modal.innerHTML = `
            <div class="js-alert-header js-alert-header-transfer">
                <div class="js-alert-header-left">
                    <div class="js-alert-icon-box">📋</div>
                    <div>
                        <h3 class="js-alert-title-main">READY TO TRANSFER</h3>
                        <p class="js-alert-subtitle">${fromWard} → ${toWard} (${waitingTime} waiting)</p>
                    </div>
                </div>
                <button type="button" class="js-alert-btn-close btn-close-modal" title="Close">✕</button>
            </div>

            <div class="js-alert-body">
                <div class="js-alert-patient-box js-alert-patient-box-transfer">
                    <div>
                        <div style="font-size: 10px; font-weight: 700; color: #f59e0b; text-transform: uppercase;">PATIENT</div>
                        <h4 class="js-alert-patient-name">${patientName}</h4>
                        <p class="js-alert-patient-sub">UHID: ${uhid} • Current: ${fromWard}</p>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 11px; font-weight: 700; color: #f59e0b;">TARGET</div>
                        <div style="font-size: 16px; font-weight: 800; color: #38bdf8;">${toWard}</div>
                    </div>
                </div>

                <div class="js-alert-notice-box">
                    <strong>Recommendation:</strong> ${transfer.message || ('Patient ' + patientName + ' is Ready to Transfer (' + waitingTime + ' waiting). Doctor approval is required to proceed.')}
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

        // Doctor only: Attach transfer approval action handler
        if (isDoctor && !isNurse) {
            const approveBtn = modal.querySelector('.btn-approve-transfer');
            if (approveBtn) {
                approveBtn.addEventListener('click', async (e) => {
                    const btn = e.currentTarget;
                    btn.disabled = true;
                    btn.innerHTML = `
                        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" fill="none" stroke-width="2" style="animation: jsSpin 0.8s linear infinite;">
                            <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
                            <path d="M12 2a10 10 0 0 1 10 10"></path>
                        </svg> Approving...`;

                    try {
                        let approveUrl = transferId ? `/api/v1/transfers/${transferId}/approve` : (recId ? `/api/v1/decision/approve/${recId}` : `/api/v1/transfers`);
                        let reqMethod = 'POST';
                        let reqBody = { remarks: 'Approved via Doctor Global Alert Layer' };

                        if (!transferId && !recId) {
                            reqBody = {
                                patient_id: patientId,
                                to_ward: toWard,
                                reason: 'Approved step-down to HDU'
                            };
                        }

                        const res = await fetch(approveUrl, {
                            method: reqMethod,
                            headers: {
                                ...getAuthHeaders(),
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(reqBody)
                        });

                        const json = await res.json();
                        if (res.ok && json.success) {
                            btn.innerHTML = '✓ Approved!';
                            btn.style.background = '#047857';
                            setTimeout(() => {
                                markAlertDismissedInSession(transferKey);
                                removeModalWithAnimation(transferKey);
                                setTimeout(fetchGlobalAlertFeed, 400);
                            }, 900);
                        } else {
                            alert(json.error || 'Failed to approve transfer.');
                            btn.disabled = false;
                            btn.innerHTML = '✓ Approve Transfer';
                        }
                    } catch (err) {
                        alert('Network or server error while approving transfer.');
                        btn.disabled = false;
                        btn.innerHTML = '✓ Approve Transfer';
                    }
                });
            }
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
