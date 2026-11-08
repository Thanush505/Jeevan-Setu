/**
 * Jeevan Setu — Authoritative Patient Context & Navigation Utility
 * Ensures all patient navigation, data fetching, and state management
 * strictly respects and isolates the active patient ID.
 *
 * Prevents hardcoding, fallback substitutions, and cross-patient data leaks.
 */

(function (window) {
    'use strict';

    const JeevanSetuPatientContext = {
        /**
         * Retrieve active auth token from browser storage.
         * @returns {string}
         */
        getAuthToken: function () {
            return localStorage.getItem('jeevan_setu_token') ||
                sessionStorage.getItem('jeevan_setu_token') ||
                localStorage.getItem('token') ||
                '';
        },

        /**
         * Return standard API request headers with auth token.
         * @param {Object} [extraHeaders]
         * @returns {Object}
         */
        getAuthHeaders: function (extraHeaders = {}) {
            const headers = {
                'Accept': 'application/json',
                ...extraHeaders
            };
            const token = this.getAuthToken();
            if (token) {
                headers['Authorization'] = 'Bearer ' + token;
            }
            return headers;
        },

        /**
         * Parse and validate patient_id from current URL parameters.
         * Strictly returns a positive integer or null.
         * NEVER falls back to 1 or a default patient.
         *
         * @param {string|string[]} [paramNames=['patient_id', 'id', 'pid']]
         * @returns {number|null}
         */
        getPatientIdFromUrl: function (paramNames = ['patient_id', 'id', 'pid']) {
            try {
                const searchParams = new URLSearchParams(window.location.search);
                const names = Array.isArray(paramNames) ? paramNames : [paramNames];

                for (const name of names) {
                    const raw = searchParams.get(name);
                    if (raw !== null && raw !== undefined && raw.trim() !== '') {
                        const parsed = parseInt(raw.trim(), 10);
                        if (!isNaN(parsed) && parsed > 0 && String(parsed) === raw.trim()) {
                            return parsed;
                        }
                    }
                }
            } catch (err) {
                console.error('[PatientContext] Error parsing URL search params:', err);
            }
            return null;
        },

        /**
         * Validate that a value is a valid positive integer patient ID.
         * @param {*} val
         * @returns {boolean}
         */
        isValidPatientId: function (val) {
            if (val === null || val === undefined) return false;
            const parsed = parseInt(val, 10);
            return !isNaN(parsed) && parsed > 0;
        },

        /**
         * Update current URL parameter without reloading the page.
         * @param {number} patientId
         * @param {boolean} [replace=true]
         */
        updateUrlPatientId: function (patientId, replace = true) {
            if (!this.isValidPatientId(patientId)) return;
            try {
                const url = new URL(window.location.href);
                url.searchParams.set('patient_id', String(patientId));
                if (replace) {
                    window.history.replaceState({ patient_id: patientId }, '', url.toString());
                } else {
                    window.history.pushState({ patient_id: patientId }, '', url.toString());
                }
            } catch (e) {
                console.warn('[PatientContext] Failed to update URL query param:', e);
            }
        },

        /**
         * Build a destination URL with explicit patient_id parameter.
         * @param {string} basePath
         * @param {number} patientId
         * @param {Object} [extraParams={}]
         * @returns {string}
         */
        buildPatientUrl: function (basePath, patientId, extraParams = {}) {
            if (!this.isValidPatientId(patientId)) {
                console.warn('[PatientContext] buildPatientUrl called with invalid patientId:', patientId);
                return basePath;
            }
            try {
                // If basePath has query string already, parse it
                const parts = basePath.split('?');
                const path = parts[0];
                const searchParams = new URLSearchParams(parts[1] || '');
                searchParams.set('patient_id', String(patientId));
                for (const [k, v] of Object.entries(extraParams)) {
                    if (v !== undefined && v !== null) {
                        searchParams.set(k, String(v));
                    }
                }
                return `${path}?${searchParams.toString()}`;
            } catch (e) {
                return `${basePath}?patient_id=${patientId}`;
            }
        },

        /**
         * Fetch patient profile by ID from backend.
         * Strictly handles 401, 403 (unauthorized/IDOR), 404 (not found).
         * @param {number} patientId
         * @returns {Promise<{success: boolean, data?: Object, error?: string, status: number}>}
         */
        fetchPatient: async function (patientId) {
            if (!this.isValidPatientId(patientId)) {
                return { success: false, status: 400, error: 'Invalid or missing patient ID.' };
            }

            try {
                const res = await fetch(`/api/v1/patients/${patientId}`, {
                    headers: this.getAuthHeaders()
                });

                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    return {
                        success: false,
                        status: res.status,
                        error: data.error || `Error loading patient #${patientId} (HTTP ${res.status})`
                    };
                }

                return {
                    success: true,
                    status: 200,
                    data: data.data || data
                };
            } catch (err) {
                console.error(`[PatientContext] Network error fetching patient #${patientId}:`, err);
                return {
                    success: false,
                    status: 0,
                    error: 'Network connection failed. Please check server availability.'
                };
            }
        },

        /**
         * Fetch latest vitals for a specific patient.
         * @param {number} patientId
         * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
         */
        fetchPatientVitals: async function (patientId) {
            if (!this.isValidPatientId(patientId)) {
                return { success: false, error: 'Invalid patient ID' };
            }

            try {
                const res = await fetch(`/api/v1/vitals/latest/${patientId}`, {
                    headers: this.getAuthHeaders()
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok || !data.success) {
                    // Try fallback endpoint /api/v1/vitals/patient/{id}
                    const altRes = await fetch(`/api/v1/vitals/patient/${patientId}`, {
                        headers: this.getAuthHeaders()
                    });
                    const altData = await altRes.json().catch(() => ({}));
                    if (altRes.ok && altData.success) {
                        return { success: true, data: altData.data ? (Array.isArray(altData.data) ? altData.data[0] : altData.data) : null };
                    }
                    return { success: false, error: data.error || 'Failed to fetch vitals' };
                }
                return { success: true, data: data.data };
            } catch (e) {
                return { success: false, error: e.message };
            }
        },

        /**
         * Evaluate clinical decision for a specific patient.
         * @param {number} patientId
         * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
         */
        fetchPatientDecision: async function (patientId) {
            if (!this.isValidPatientId(patientId)) {
                return { success: false, error: 'Invalid patient ID' };
            }

            try {
                const res = await fetch(`/decision/evaluate/${patientId}`, {
                    headers: this.getAuthHeaders()
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok || !data.success) {
                    return { success: false, error: data.error || 'Decision evaluation unavailable' };
                }
                return { success: true, data: data };
            } catch (e) {
                return { success: false, error: e.message };
            }
        },

        /**
         * Fetch recommendation history for a specific patient.
         * @param {number} patientId
         * @returns {Promise<{success: boolean, data?: Array, error?: string}>}
         */
        fetchPatientHistory: async function (patientId) {
            if (!this.isValidPatientId(patientId)) {
                return { success: false, error: 'Invalid patient ID' };
            }

            try {
                const res = await fetch(`/decision/history/${patientId}`, {
                    headers: this.getAuthHeaders()
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok || !data.success) {
                    return { success: false, error: data.error || 'History unavailable' };
                }
                return { success: true, data: data.data || [] };
            } catch (e) {
                return { success: false, error: e.message };
            }
        },

        /**
         * Fetch pending transfer approvals scoped to current doctor.
         * @returns {Promise<{success: boolean, data?: Array, count?: number, error?: string}>}
         */
        fetchPendingApprovals: async function () {
            try {
                const res = await fetch('/api/v1/decision/pending', {
                    headers: this.getAuthHeaders()
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok || !data.success) {
                    return { success: false, error: data.error || 'Pending queue unavailable' };
                }
                return { success: true, data: data.data || [], count: data.count || 0 };
            } catch (e) {
                return { success: false, error: e.message };
            }
        },

        /**
         * Approve transfer recommendation.
         * @param {number} recommendationId
         * @returns {Promise<{success: boolean, message?: string, error?: string}>}
         */
        approveRecommendation: async function (recommendationId) {
            try {
                const res = await fetch(`/api/v1/decision/approve/${recommendationId}`, {
                    method: 'POST',
                    headers: this.getAuthHeaders({ 'Content-Type': 'application/json' })
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok || !data.success) {
                    return { success: false, error: data.error || 'Approval failed' };
                }
                return { success: true, message: data.message || 'Approved successfully' };
            } catch (e) {
                return { success: false, error: e.message };
            }
        },

        /**
         * Reject transfer recommendation with remarks.
         * @param {number} recommendationId
         * @param {string} remarks
         * @returns {Promise<{success: boolean, message?: string, error?: string}>}
         */
        rejectRecommendation: async function (recommendationId, remarks = 'Rejected by attending doctor') {
            try {
                const res = await fetch(`/api/v1/decision/reject/${recommendationId}`, {
                    method: 'POST',
                    headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify({ remarks: remarks })
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok || !data.success) {
                    return { success: false, error: data.error || 'Rejection failed' };
                }
                return { success: true, message: data.message || 'Recommendation rejected' };
            } catch (e) {
                return { success: false, error: e.message };
            }
        },

        /**
         * Render a structured, accessible error container when a patient ID is missing or unauthorized.
         * NEVER silently falls back to another patient!
         *
         * @param {HTMLElement|string} target
         * @param {Object} options
         * @param {string} options.title
         * @param {string} options.message
         * @param {string} [options.actionText]
         * @param {string} [options.actionHref]
         * @param {Function} [options.actionCallback]
         */
        renderPatientError: function (target, options = {}) {
            const container = typeof target === 'string' ? document.getElementById(target) : target;
            if (!container) return;

            const title = options.title || 'Patient Information Unavailable';
            const message = options.message || 'The requested patient record could not be loaded or is not assigned to your account.';
            const isForbidden = options.status === 403 || message.toLowerCase().includes('forbidden') || message.toLowerCase().includes('not authorized');
            const icon = isForbidden ? 'lock' : 'person_off';
            const borderClass = isForbidden ? 'border-amber-500/40 bg-amber-500/5' : 'border-red-500/40 bg-red-500/5';
            const iconClass = isForbidden ? 'text-amber-500' : 'text-red-500';

            let actionHtml = '';
            if (options.actionHref && options.actionText) {
                actionHtml = `
                    <a href="${options.actionHref}" class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs transition-colors shadow-sm mt-4">
                        <span class="material-symbols-outlined text-[16px]">arrow_back</span>
                        <span>${options.actionText}</span>
                    </a>
                `;
            }

            container.innerHTML = `
                <div class="rounded-xl border ${borderClass} p-8 text-center flex flex-col items-center justify-center max-w-xl mx-auto my-8">
                    <div class="w-14 h-14 rounded-full bg-slate-800/10 dark:bg-white/10 flex items-center justify-center mb-3">
                        <span class="material-symbols-outlined text-3xl ${iconClass}">${icon}</span>
                    </div>
                    <h3 class="text-base font-bold text-slate-900 dark:text-white mb-1">${title}</h3>
                    <p class="text-xs text-slate-600 dark:text-slate-400 max-w-md leading-relaxed">${message}</p>
                    ${actionHtml}
                </div>
            `;

            if (options.actionCallback && options.actionText) {
                const btn = container.querySelector('a, button');
                if (btn) btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    options.actionCallback();
                });
            }
        }
    };

    window.JeevanSetuPatientContext = JeevanSetuPatientContext;

})(window);

