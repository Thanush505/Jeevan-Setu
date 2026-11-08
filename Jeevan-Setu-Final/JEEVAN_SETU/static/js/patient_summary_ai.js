/**
 * patient_summary_ai.js — Shared Clinical Dashboard & AI Summary Controller
 * Jeevan Setu — Intelligent Patient Transfer Decision Support System (ICU ↔ HDU)
 *
 * Coordinates between:
 * - Patient Selection & Demographics Card
 * - Real-Time Vitals Telemetry Grid (HR, SpO2, RR, BP, Temp, AVPU)
 * - Persisted EWS Score & Transfer Decision Indicators
 * - Structured AI Clinical Patient Summary Card
 * - Agentic Hybrid Multimodal RAG Chatbot (Dr. Setu)
 */

(function (window) {
    'use strict';

    let dashboardRole = 'doctor'; // 'doctor' | 'nurse'
    let currentPatientContext = null;
    let currentSummaryText = '';
    let isSummaryRefreshing = false;

    function el(id) {
        return document.getElementById(id);
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str).replace(/[&<>"'`=\/]/g, function (s) {
            return {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;',
                '/': '&#x2F;',
                '`': '&#x60;',
                '=': '&#x3D;'
            }[s];
        });
    }

    function formatMarkdownText(markdown) {
        if (!markdown) return '';

        // If backend returned the 6-section formatted delimiter:
        if (markdown.includes('----------------------------------------')) {
            const parts = markdown.split('----------------------------------------');
            let html = '<div class="space-y-3 font-sans">';
            for (let i = 1; i < parts.length; i += 2) {
                const title = parts[i].trim();
                const body = (parts[i + 1] || '').trim();
                let headerColor = 'text-blue-900 bg-blue-50/80 border-blue-200';
                let icon = 'clinical_notes';
                if (title.includes('ALERT') || title.includes('CRITICAL')) {
                    headerColor = 'text-red-900 bg-red-50/80 border-red-200';
                    icon = 'warning';
                } else if (title.includes('RECOMMENDATION') || title.includes('TRANSFER')) {
                    headerColor = 'text-indigo-900 bg-indigo-50/80 border-indigo-200';
                    icon = 'swap_horiz';
                } else if (title.includes('TREND') || title.includes('TRAJECTORY')) {
                    headerColor = 'text-teal-900 bg-teal-50/80 border-teal-200';
                    icon = 'trending_up';
                } else if (title.includes('VITALS') || title.includes('TELEMETRY')) {
                    headerColor = 'text-emerald-900 bg-emerald-50/80 border-emerald-200';
                    icon = 'vital_signs';
                }

                html += `
                    <div class="summary-subcard shadow-xs">
                        <div class="summary-subcard-header ${headerColor}">
                            <span class="flex items-center gap-1.5 font-bold">
                                <span class="material-symbols-outlined text-[15px]">${icon}</span>
                                ${escapeHtml(title)}
                            </span>
                            <span class="material-symbols-outlined text-[14px] opacity-60">verified</span>
                        </div>
                        <div class="p-3 text-xs leading-relaxed text-slate-700 whitespace-pre-line font-medium">
                            ${formatMarkdownInline(escapeHtml(body))}
                        </div>
                    </div>
                `;
            }
            html += '</div>';
            return html;
        }

        // Generic Markdown lines
        const lines = markdown.split('\n');
        return lines.map(line => {
            const trimmed = line.trim();
            if (!trimmed) return '<div class="h-1"></div>';
            if (trimmed.startsWith('•') || trimmed.startsWith('-') || (trimmed.startsWith('*') && !trimmed.startsWith('**') && !trimmed.endsWith('*'))) {
                return `<div class="flex items-start gap-1.5 my-1 text-slate-700 text-xs">
                            <span class="text-blue-600 font-bold">•</span>
                            <span>${formatMarkdownInline(escapeHtml(trimmed.substring(1).trim()))}</span>
                        </div>`;
            }
            if (trimmed.startsWith('###')) {
                return `<p class="font-bold text-slate-900 text-xs mt-2.5 mb-1 flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-blue-600"></span>${formatMarkdownInline(escapeHtml(trimmed.replace(/^#+\s*/, '')))}</p>`;
            }
            if (trimmed.startsWith('#')) {
                return `<p class="font-bold text-blue-950 text-sm mt-3 mb-1.5">${formatMarkdownInline(escapeHtml(trimmed.replace(/^#+\s*/, '')))}</p>`;
            }
            return `<p class="my-1 text-slate-700 text-xs leading-relaxed">${formatMarkdownInline(escapeHtml(trimmed))}</p>`;
        }).join('');
    }

    function formatMarkdownInline(str) {
        return str
            .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-slate-900">$1</strong>')
            .replace(/`(.*?)`/g, '<code class="bg-slate-100 px-1 py-0.5 rounded text-blue-800 font-mono text-[11px]">$1</code>');
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 1. RENDER PATIENT OVERVIEW CARD
    // ─────────────────────────────────────────────────────────────────────────
    function renderPatientOverview(patient) {
        if (!patient) return;

        const nameEl = el('dash-patient-name');
        const codeEl = el('dash-patient-code');
        const ageGenEl = el('dash-patient-age-gender');
        const bloodEl = el('dash-patient-blood-group');
        const wardBedEl = el('dash-patient-ward-bed');
        const docEl = el('dash-patient-doctor');
        const admEl = el('dash-patient-admission-date');
        const diagEl = el('dash-patient-diagnosis');
        const statusBadge = el('dash-patient-status-badge');

        if (nameEl) nameEl.textContent = patient.name || `Patient #${patient.patient_id || patient.id}`;
        if (codeEl) codeEl.textContent = patient.patient_code || `JS-${patient.patient_id || patient.id}`;

        const age = patient.age ? `${patient.age}y` : '--';
        const gender = patient.gender || '--';
        if (ageGenEl) ageGenEl.textContent = `${age} • ${gender}`;

        if (bloodEl) bloodEl.textContent = patient.blood_group || '--';

        const ward = patient.ward_type || patient.ward_name || 'ICU';
        const bed = patient.bed_number ? `Bed ${patient.bed_number}` : 'No Bed';
        if (wardBedEl) wardBedEl.textContent = `${ward} (${bed})`;

        const docTitle = dashboardRole === 'nurse' ? 'Attending Doctor:' : 'Physician:';
        if (docEl) docEl.textContent = patient.doctor_name || (dashboardRole === 'nurse' ? 'Dr. Sunita Mehta' : 'Assigned');

        if (admEl) {
            const rawAdm = patient.admission_date || patient.admitted_at || '';
            admEl.textContent = rawAdm ? rawAdm.replace('T', ' ').substring(0, 16) : 'Current Admission';
        }

        if (diagEl) diagEl.textContent = patient.diagnosis || 'Documented in Hospital EHR';

        if (statusBadge) {
            const status = (patient.status || 'Admitted').toUpperCase();
            statusBadge.textContent = status;
            statusBadge.className = 'px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-200';
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 2. RENDER VITALS TELEMETRY TILES
    // ─────────────────────────────────────────────────────────────────────────
    function renderVitalsTelemetry(vitals) {
        if (!vitals) return;

        // Heart Rate
        const hrVal = vitals.heart_rate;
        const hrEl = el('vital-hr-val');
        const hrTag = el('vital-hr-tag');
        if (hrEl) hrEl.textContent = hrVal !== null && hrVal !== undefined ? Math.round(hrVal) : '--';
        if (hrTag && hrVal !== null && hrVal !== undefined) {
            if (hrVal > 100) {
                hrTag.textContent = 'Tachycardic';
                hrTag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-800';
            } else if (hrVal < 50) {
                hrTag.textContent = 'Bradycardic';
                hrTag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-800';
            } else {
                hrTag.textContent = 'Normal';
                hrTag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-100 text-emerald-800';
            }
        }

        // Oxygen Saturation (SpO2)
        const spo2Val = vitals.spo2;
        const spo2El = el('vital-spo2-val');
        const spo2Tag = el('vital-spo2-tag');
        if (spo2El) spo2El.textContent = spo2Val !== null && spo2Val !== undefined ? `${Math.round(spo2Val)}%` : '--';
        if (spo2Tag && spo2Val !== null && spo2Val !== undefined) {
            if (spo2Val < 92) {
                spo2Tag.textContent = 'Hypoxemia';
                spo2Tag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-100 text-red-800';
            } else if (spo2Val < 95) {
                spo2Tag.textContent = 'Borderline';
                spo2Tag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-800';
            } else {
                spo2Tag.textContent = 'Optimal';
                spo2Tag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-100 text-emerald-800';
            }
        }

        // Respiratory Rate
        const rrVal = vitals.respiratory_rate;
        const rrEl = el('vital-rr-val');
        const rrTag = el('vital-rr-tag');
        if (rrEl) rrEl.textContent = rrVal !== null && rrVal !== undefined ? Math.round(rrVal) : '--';
        if (rrTag && rrVal !== null && rrVal !== undefined) {
            if (rrVal > 22) {
                rrTag.textContent = 'Tachypnea';
                rrTag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-800';
            } else if (rrVal < 12) {
                rrTag.textContent = 'Bradypnea';
                rrTag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-800';
            } else {
                rrTag.textContent = 'Normal';
                rrTag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-100 text-emerald-800';
            }
        }

        // Blood Pressure (Sys / Dia)
        const sysVal = vitals.blood_pressure_sys;
        const diaVal = vitals.blood_pressure_dia;
        const bpEl = el('vital-bp-val');
        const bpTag = el('vital-bp-tag');
        if (bpEl) {
            if (sysVal !== null && sysVal !== undefined) {
                bpEl.textContent = diaVal !== null && diaVal !== undefined ? `${Math.round(sysVal)}/${Math.round(diaVal)}` : `${Math.round(sysVal)}`;
            } else {
                bpEl.textContent = '--';
            }
        }
        if (bpTag && sysVal !== null && sysVal !== undefined) {
            if (sysVal < 90) {
                bpTag.textContent = 'Hypotension';
                bpTag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-100 text-red-800';
            } else if (sysVal >= 140) {
                bpTag.textContent = 'Hypertension';
                bpTag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-800';
            } else {
                bpTag.textContent = 'Normal';
                bpTag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-100 text-emerald-800';
            }
        }

        // Body Temperature
        const tempVal = vitals.temperature;
        const tempEl = el('vital-temp-val');
        const tempTag = el('vital-temp-tag');
        if (tempEl) tempEl.textContent = tempVal !== null && tempVal !== undefined ? `${Number(tempVal).toFixed(1)}°C` : '--';
        if (tempTag && tempVal !== null && tempVal !== undefined) {
            if (tempVal > 38.0) {
                tempTag.textContent = 'Fever';
                tempTag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-100 text-red-800';
            } else if (tempVal < 36.0) {
                tempTag.textContent = 'Hypothermia';
                tempTag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-800';
            } else {
                tempTag.textContent = 'Normal';
                tempTag.className = 'px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-100 text-emerald-800';
            }
        }

        // Consciousness (AVPU)
        const avpuVal = vitals.consciousness || 'Alert';
        const avpuEl = el('vital-avpu-val');
        if (avpuEl) avpuEl.textContent = avpuVal;

        // Recorded Timestamp
        const recEl = el('vital-recorded-at');
        if (recEl) {
            const rawRec = vitals.recorded_at || 'Just now';
            recEl.textContent = rawRec.replace('T', ' ').substring(0, 19);
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 3. RENDER EWS SCORE & TRANSFER DECISION CARDS
    // ─────────────────────────────────────────────────────────────────────────
    function renderEwsAndTransfer(ews, recommendation) {
        // EWS Section
        const ewsScoreEl = el('dash-ews-score');
        const ewsRiskEl = el('dash-ews-risk');
        const ewsBadgeWrap = el('dash-ews-badge-wrap');
        const ewsBreakdownEl = el('dash-ews-breakdown');

        const score = ews && ews.score !== undefined ? ews.score : 0;
        const risk = (ews && ews.risk_level ? ews.risk_level : (score >= 7 ? 'CRITICAL' : (score >= 5 ? 'HIGH' : (score >= 1 ? 'MEDIUM' : 'LOW')))).toUpperCase();

        if (ewsScoreEl) ewsScoreEl.textContent = score;
        if (ewsRiskEl) ewsRiskEl.textContent = `${risk} RISK`;

        if (ewsBadgeWrap) {
            if (risk === 'CRITICAL' || risk === 'HIGH' || score >= 5) {
                ewsBadgeWrap.className = 'px-3 py-1.5 rounded-xl font-bold text-xs bg-red-600 text-white shadow-xs flex items-center gap-1.5';
            } else if (risk === 'MEDIUM' || score >= 1) {
                ewsBadgeWrap.className = 'px-3 py-1.5 rounded-xl font-bold text-xs bg-amber-500 text-white shadow-xs flex items-center gap-1.5';
            } else {
                ewsBadgeWrap.className = 'px-3 py-1.5 rounded-xl font-bold text-xs bg-emerald-600 text-white shadow-xs flex items-center gap-1.5';
            }
        }

        if (ewsBreakdownEl && ews && ews.breakdown) {
            let pills = '';
            for (const [k, v] of Object.entries(ews.breakdown)) {
                const paramLabel = k.replace('blood_pressure_', 'BP ').replace('_', ' ').toUpperCase();
                const pScore = typeof v === 'object' && v !== null ? (v.score ?? 0) : v;
                pills += `<span class="px-2 py-0.5 rounded font-mono text-[10px] bg-slate-100 text-slate-700 border border-slate-200">${paramLabel}: +${pScore}</span> `;
            }
            ewsBreakdownEl.innerHTML = pills || '<span class="text-slate-400 text-[11px]">All physiological parameters in standard baseline limits</span>';
        }

        // Authoritative Transfer Recommendation Section
        const recTextEl = el('dash-rec-text');
        const recTrajEl = el('dash-rec-trajectory');
        const recReasonEl = el('dash-rec-reason');
        const recStatusEl = el('dash-rec-status');

        if (recommendation) {
            const rText = recommendation.recommendation_text || 'Under Evaluation';
            if (recTextEl) {
                recTextEl.textContent = rText;
                if (rText.toUpperCase().includes('ICU')) {
                    recTextEl.className = 'font-bold text-sm text-indigo-900';
                } else if (rText.toUpperCase().includes('HDU')) {
                    recTextEl.className = 'font-bold text-sm text-emerald-800';
                } else {
                    recTextEl.className = 'font-bold text-sm text-slate-800';
                }
            }

            const fromW = recommendation.from_ward || 'ICU';
            const toW = recommendation.to_ward || 'ICU';
            if (recTrajEl) recTrajEl.textContent = `${fromW} ➔ ${toW}`;

            if (recReasonEl) recReasonEl.textContent = recommendation.reason || 'Telemetry parameters evaluated by authoritative clinical engine.';

            if (recStatusEl) {
                const status = (recommendation.status || 'Auto Evaluated').toUpperCase();
                recStatusEl.textContent = status;
                recStatusEl.className = status === 'APPROVED'
                    ? 'px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200'
                    : 'px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-200';
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 4. RENDER AI PATIENT SUMMARY CARD
    // ─────────────────────────────────────────────────────────────────────────
    function renderAiPatientSummary(summaryText, context) {
        currentSummaryText = summaryText || '';
        const bodyEl = el('dash-ai-summary-body');
        const timeEl = el('dash-ai-summary-time');

        if (timeEl) {
            const now = new Date();
            timeEl.textContent = `Generated: ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
        }

        if (!bodyEl) return;

        if (!summaryText) {
            bodyEl.innerHTML = `
                <div class="p-6 text-center text-slate-400">
                    <span class="material-symbols-outlined text-3xl text-slate-300 mb-1">psychology</span>
                    <p class="text-xs font-medium">Select a patient above to load and synthesize the AI Clinical Briefing.</p>
                </div>
            `;
            return;
        }

        bodyEl.innerHTML = formatMarkdownText(summaryText);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 5. COPY SUMMARY & REFRESH ACTIONS
    // ─────────────────────────────────────────────────────────────────────────
    function copyAiSummaryToClipboard() {
        if (!currentSummaryText) {
            alert('No summary text is currently loaded.');
            return;
        }
        navigator.clipboard.writeText(currentSummaryText)
            .then(() => {
                const btn = el('dash-copy-summary-btn');
                if (btn) {
                    const originalHtml = btn.innerHTML;
                    btn.innerHTML = `<span class="material-symbols-outlined text-xs">check</span> Copied!`;
                    btn.classList.add('bg-emerald-50', 'text-emerald-700', 'border-emerald-300');
                    setTimeout(() => {
                        btn.innerHTML = originalHtml;
                        btn.classList.remove('bg-emerald-50', 'text-emerald-700', 'border-emerald-300');
                    }, 2000);
                }
            })
            .catch(() => {
                alert('Unable to copy summary to clipboard.');
            });
    }

    async function refreshActivePatientSummary() {
        if (isSummaryRefreshing) return;
        const pid = sessionStorage.getItem(dashboardRole === 'nurse' ? 'jeevan_setu_nurse_active_patient_id' : 'jeevan_setu_active_patient_id');
        if (!pid) return;

        isSummaryRefreshing = true;
        const refreshBtn = el('dash-refresh-summary-btn');
        if (refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.classList.add('opacity-50');
        }

        const bodyEl = el('dash-ai-summary-body');
        if (bodyEl) {
            bodyEl.innerHTML = `
                <div class="p-8 text-center text-blue-600 flex flex-col items-center justify-center gap-2">
                    <span class="material-symbols-outlined animate-spin text-3xl">progress_activity</span>
                    <span class="text-xs font-semibold">Updating verified clinical summary and telemetry...</span>
                </div>
            `;
        }

        try {
            const token = localStorage.getItem('jeevan_setu_token') || sessionStorage.getItem('jeevan_setu_token') || localStorage.getItem('token') || '';
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch(`/chatbot/patient/${pid}/summary`, { headers });
            const data = await res.json();
            if (data.success && data.context) {
                currentPatientContext = data.context;
                renderPatientOverview(data.context.patient);
                renderVitalsTelemetry(data.context.latest_vitals);
                renderEwsAndTransfer(data.context.ews, data.context.recommendation);
                renderAiPatientSummary(data.text, data.context);
            }
        } catch (e) {
            console.error('Failed to refresh clinical summary', e);
        } finally {
            isSummaryRefreshing = false;
            if (refreshBtn) {
                refreshBtn.disabled = false;
                refreshBtn.classList.remove('opacity-50');
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 6. DASHBOARD INTERCEPTOR HOOK (Connects to jeevan_setu_rag_chatbot.js)
    // ─────────────────────────────────────────────────────────────────────────
    function updateDashboardFromContext(context, text) {
        if (!context) return;
        currentPatientContext = context;
        if (context.patient) renderPatientOverview(context.patient);
        if (context.latest_vitals) renderVitalsTelemetry(context.latest_vitals);
        if (context.ews || context.recommendation) renderEwsAndTransfer(context.ews, context.recommendation);
        renderAiPatientSummary(text, context);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 7. RESPONSIVE SEGMENT SWITCHER (For Mobile & Tablet < 1024px)
    // ─────────────────────────────────────────────────────────────────────────
    function switchMobileTab(tab) {
        const summaryCol = el('left-dashboard-column');
        const chatCol = el('right-chatbot-column');
        const tabSummaryBtn = el('mobile-tab-summary-btn');
        const tabChatBtn = el('mobile-tab-chat-btn');

        if (tab === 'chat') {
            if (summaryCol) summaryCol.classList.add('hidden', 'lg:flex');
            if (chatCol) chatCol.classList.remove('hidden');
            if (tabSummaryBtn) tabSummaryBtn.className = 'flex-1 py-2 text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors';
            if (tabChatBtn) tabChatBtn.className = 'flex-1 py-2 text-xs font-bold bg-white text-blue-700 shadow-xs rounded-lg transition-colors';
        } else {
            if (summaryCol) summaryCol.classList.remove('hidden');
            if (chatCol) chatCol.classList.add('hidden', 'lg:flex');
            if (tabSummaryBtn) tabSummaryBtn.className = 'flex-1 py-2 text-xs font-bold bg-white text-blue-700 shadow-xs rounded-lg transition-colors';
            if (tabChatBtn) tabChatBtn.className = 'flex-1 py-2 text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors';
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 8. INITIALIZE DASHBOARD MODULE
    // ─────────────────────────────────────────────────────────────────────────
    function initPatientSummaryAiDashboard(role = 'doctor') {
        dashboardRole = (role || 'doctor').toLowerCase();

        // Bind copy & refresh buttons
        const copyBtn = el('dash-copy-summary-btn');
        if (copyBtn) copyBtn.addEventListener('click', copyAiSummaryToClipboard);

        const refreshBtn = el('dash-refresh-summary-btn');
        if (refreshBtn) refreshBtn.addEventListener('click', refreshActivePatientSummary);

        // Hook into fetch response when selectPatient is invoked in jeevan_setu_rag_chatbot.js
        const originalFetch = window.fetch;
        window.fetch = async function (...args) {
            const response = await originalFetch.apply(this, args);
            try {
                const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url ? args[0].url : '');
                if (url.includes('/chatbot/patient/') && url.endsWith('/summary') && response.ok) {
                    const clone = response.clone();
                    clone.json().then(data => {
                        if (data && data.success && data.context) {
                            updateDashboardFromContext(data.context, data.text);
                        }
                    }).catch(() => {});
                }
            } catch (e) {}
            return response;
        };
    }

    // Expose public API
    window.initPatientSummaryAiDashboard = initPatientSummaryAiDashboard;
    window.updateDashboardFromContext = updateDashboardFromContext;
    window.copyAiSummaryToClipboard = copyAiSummaryToClipboard;
    window.refreshActivePatientSummary = refreshActivePatientSummary;
    window.switchMobileTab = switchMobileTab;

})(window);

