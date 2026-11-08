/**
 * static/js/jeevan_setu_rag_chatbot.js
 *
 * Shared Frontend Module for the Jeevan Setu Agentic Hybrid Multimodal RAG Chatbot.
 * Used by both:
 *   - Doctor Patient Summary AI Page (/Doctor/Doctor_patient_summary_ai/Doctor_patient_summary_ai.html)
 *   - Nurse Patient Summary AI Page  (/Nurse/Nurse_patient_summary_ai/Nurse_patient_summary_ai.html)
 *
 * Connects to centralized Flask RAG endpoints:
 *   - GET  /chatbot/patients
 *   - POST /chatbot/message & /api/v1/chatbot/message
 *   - GET  /chatbot/patient/<id>/summary
 *   - GET  /chatbot/patients/search
 *   - GET  /chatbot/history/<id> & /chatbot/history
 *   - POST /chatbot/image/upload & /api/v1/chatbot/image/upload
 *   - GET  /chatbot/patient/<id>/images
 */

(function (window) {
    'use strict';

    // ─────────────────────────────────────────────────────────────────────────
    // 1. STATE & CONFIGURATION
    // ─────────────────────────────────────────────────────────────────────────
    let chatbotConfig = {
        role: 'doctor', // 'doctor' | 'nurse'
        storagePatientKey: 'jeevan_setu_active_patient_id'
    };

    let chatMode = 'patient'; // 'patient' | 'general'
    let authorizedPatients = [];
    let activePatientId = null;
    let activePatientData = null;
    let voiceReadoutEnabled = false;
    let isSending = false;
    let debounceTimer = null;
    let stagedImageFile = null;
    let stagedImagePreviewUrl = null;
    let activeChatImageContext = null;

    function formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 2. DOM ELEMENT ACCESSORS
    // ─────────────────────────────────────────────────────────────────────────
    function el(id) {
        return document.getElementById(id);
    }

    function getAuthHeaders(includeJsonContentType = true) {
        const token =
            localStorage.getItem('jeevan_setu_token') ||
            sessionStorage.getItem('jeevan_setu_token') ||
            localStorage.getItem('token') ||
            '';
        const headers = {};
        if (includeJsonContentType) {
            headers['Content-Type'] = 'application/json';
        }
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    }

    function escapeHtml(string) {
        if (!string) return '';
        return String(string).replace(/[&<>"'`=\/]/g, function (s) {
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

    function formatMarkdownBold(str) {
        return str
            .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-slate-900">$1</strong>')
            .replace(/`(.*?)`/g, '<code class="bg-slate-100 px-1 py-0.5 rounded text-blue-800 font-mono text-[11px]">$1</code>');
    }

    function formatBotText(text) {
        if (!text) return '';
        if (text.includes('----------------------------------------')) {
            const parts = text.split('----------------------------------------');
            let html = '<div class="space-y-3 font-sans">';
            for (let i = 1; i < parts.length; i += 2) {
                const title = parts[i].trim();
                const body = (parts[i + 1] || '').trim();
                let headerColor = 'text-blue-900 bg-blue-50 border-blue-200';
                if (title.includes('ALERT') || title.includes('CRITICAL')) headerColor = 'text-red-900 bg-red-50 border-red-200';
                if (title.includes('RECOMMENDATION')) headerColor = 'text-indigo-900 bg-indigo-50 border-indigo-200';
                if (title.includes('TREND')) headerColor = 'text-teal-900 bg-teal-50 border-teal-200';

                html += `
                    <div class="border border-slate-200 rounded-xl overflow-hidden bg-white shadow-xs">
                        <div class="px-3.5 py-2 font-bold text-[11px] uppercase tracking-wider border-b ${headerColor} flex items-center justify-between">
                            <span>${escapeHtml(title)}</span>
                            <span class="material-symbols-outlined text-[15px] opacity-70">verified</span>
                        </div>
                        <div class="p-3 text-xs leading-relaxed text-slate-700 whitespace-pre-line font-medium">
                            ${formatMarkdownBold(escapeHtml(body))}
                        </div>
                    </div>
                `;
            }
            html += '</div>';
            return html;
        }

        const lines = text.split('\n');
        return lines.map(line => {
            const trimmed = line.trim();
            if (!trimmed) return '<div class="h-1"></div>';
            if (trimmed.startsWith('•') || trimmed.startsWith('-') || (trimmed.startsWith('*') && !trimmed.startsWith('**') && !trimmed.endsWith('*'))) {
                return `<div class="flex items-start gap-1.5 my-1 text-slate-700">
                            <span class="text-blue-600 font-bold">•</span>
                            <span>${formatMarkdownBold(escapeHtml(trimmed.substring(1).trim()))}</span>
                        </div>`;
            }
            if (trimmed.startsWith('#')) {
                return `<p class="font-bold text-blue-950 text-sm mt-2 mb-1">${formatMarkdownBold(escapeHtml(trimmed.replace(/^#+\s*/, '')))}</p>`;
            }
            return `<p class="my-1 text-slate-700">${formatMarkdownBold(escapeHtml(trimmed))}</p>`;
        }).join('');
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 3. COMPACT SOURCE REFERENCES RENDERER (ChromaDB + MySQL Citations)
    // ─────────────────────────────────────────────────────────────────────────
    function renderSourceReferencesHtml(data) {
        if (!data || typeof data !== 'object') return '';
        if (data.response_type === 'image_qa') return '';

        const ragSources = Array.isArray(data.rag_sources) ? data.rag_sources : [];
        const mysqlSources = Array.isArray(data.mysql_sources) ? data.mysql_sources : [];

        if (ragSources.length === 0 && mysqlSources.length === 0) {
            return '';
        }

        let html = `
            <div class="mt-3 pt-2.5 border-t border-slate-200/80 space-y-2" data-testid="chatbot-source-references">
                <div class="flex items-center justify-between">
                    <span class="text-[10px] font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1">
                        <span class="material-symbols-outlined text-[13px] text-blue-600">fact_check</span>
                        Verified Source References
                    </span>
                    <span class="text-[10px] text-slate-400 font-mono">
                        ${mysqlSources.length > 0 ? `${mysqlSources.length} MySQL` : ''}${mysqlSources.length > 0 && ragSources.length > 0 ? ' • ' : ''}${ragSources.length > 0 ? `${ragSources.length} ChromaDB` : ''}
                    </span>
                </div>
        `;

        // 1. MySQL Patient Fact Citations (Patient Chat mode only)
        if (mysqlSources.length > 0 && chatMode === 'patient') {
            html += `<div class="grid grid-cols-1 sm:grid-cols-2 gap-1.5" data-testid="mysql-source-citations">`;
            mysqlSources.slice(0, 4).forEach(src => {
                const field = escapeHtml(src.field || 'Patient Record');
                const val = escapeHtml(src.value || '');
                const units = src.units ? ` (${escapeHtml(src.units)})` : '';
                const recAt = escapeHtml(src.recorded_at || 'Verified');
                const sourceId = escapeHtml(src.source || 'MySQL jeevan_setu');
                html += `
                    <div class="bg-blue-50/70 border border-blue-200/80 rounded-lg px-2.5 py-1.5 text-[10px] text-slate-700">
                        <div class="flex items-center justify-between font-bold text-blue-900">
                            <span class="truncate">${field}</span>
                            <span class="text-[9px] font-mono bg-blue-100 text-blue-800 px-1 rounded">${sourceId}</span>
                        </div>
                        <div class="mt-0.5 text-slate-700 font-medium truncate">${val}${units}</div>
                        <div class="text-[9px] text-slate-500 flex items-center gap-1 mt-0.5">
                            <span class="material-symbols-outlined text-[11px]">schedule</span> ${recAt}
                        </div>
                    </div>
                `;
            });
            html += `</div>`;
        }

        // 2. ChromaDB Hospital Knowledge Citations
        if (ragSources.length > 0) {
            html += `<div class="space-y-1.5" data-testid="chromadb-source-citations">`;
            ragSources.slice(0, 3).forEach(src => {
                const docTitle = escapeHtml(src.document_title || src.source_file || 'Hospital Guideline');
                const sourceFile = escapeHtml(src.source_file || src.source || 'knowledge_base');
                const pageNum = src.page_number ? `Page ${escapeHtml(src.page_number)}` : 'Full Doc';
                const category = escapeHtml((src.category || 'clinical_guideline').replace(/_/g, ' ').toUpperCase());
                const excerpt = escapeHtml(src.excerpt || '');
                html += `
                    <div class="bg-purple-50/60 border border-purple-200/80 rounded-lg px-2.5 py-1.5 text-[10px] text-slate-700">
                        <div class="flex flex-wrap items-center justify-between gap-1">
                            <span class="font-bold text-purple-950 flex items-center gap-1">
                                <span class="material-symbols-outlined text-[12px] text-purple-700">menu_book</span>
                                ${docTitle}
                            </span>
                            <div class="flex items-center gap-1">
                                <span class="px-1.5 py-0.2 bg-purple-100 text-purple-800 rounded font-bold text-[9px]">${category}</span>
                                <span class="px-1.5 py-0.2 bg-slate-200 text-slate-700 rounded font-mono text-[9px]">${sourceFile} • ${pageNum}</span>
                            </div>
                        </div>
                        ${excerpt ? `<p class="mt-1 text-[10px] text-slate-600 italic line-clamp-2">"${excerpt}"</p>` : ''}
                    </div>
                `;
            });
            html += `</div>`;
        }

        html += `</div>`;
        return html;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 4. MESSAGE RENDERING & VOICE READOUT
    // ─────────────────────────────────────────────────────────────────────────
    function toggleSpeechReadout() {
        voiceReadoutEnabled = !voiceReadoutEnabled;
        const voiceIcon = el('voice-icon');
        if (voiceReadoutEnabled) {
            if (voiceIcon) {
                voiceIcon.textContent = 'volume_up';
                voiceIcon.classList.add('text-blue-600');
            }
            speakText('Voice readout enabled. Dr. Setu will brief you aloud.');
        } else {
            if (voiceIcon) {
                voiceIcon.textContent = 'volume_off';
                voiceIcon.classList.remove('text-blue-600');
            }
            if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        }
    }

    function speakText(text) {
        if (!voiceReadoutEnabled || !('speechSynthesis' in window)) return;
        window.speechSynthesis.cancel();
        const clean = String(text || '').replace(/[*#`•\-_]/g, ' ').replace(/\s+/g, ' ');
        const utterance = new SpeechSynthesisUtterance(clean);
        utterance.rate = 1.05;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
    }

    function appendMessage(sender, text, data = null) {
        const chatMessages = el('chat-messages');
        if (!chatMessages) return;

        const row = document.createElement('div');
        row.className = sender === 'user' ? 'flex justify-end' : 'flex items-start gap-3';

        if (sender === 'user') {
            let userImgHtml = '';
            if (data && data.imagePreviewUrl) {
                userImgHtml = `
                    <div class="mb-2 rounded-lg overflow-hidden border border-blue-400/40 bg-blue-900/40">
                        <img src="${escapeHtml(data.imagePreviewUrl)}" alt="Attached Image" class="max-h-48 rounded-lg object-contain cursor-pointer hover:opacity-95" onclick="window.open('${escapeHtml(data.imagePreviewUrl)}', '_blank')" />
                        <div class="px-2 py-1 text-[10px] text-blue-100 flex items-center justify-between">
                            <span class="truncate">${escapeHtml(data.imageName || 'Clinical Image')}</span>
                            <span>${escapeHtml(data.imageSize || '')}</span>
                        </div>
                    </div>
                `;
            }
            row.innerHTML = `
                <div class="chat-bubble-user px-4 py-2.5 max-w-xl text-xs font-medium leading-relaxed shadow-sm">
                    ${userImgHtml}
                    ${text ? `<div class="whitespace-pre-wrap">${escapeHtml(text)}</div>` : ''}
                </div>
            `;
        } else {
            let formattedContent = formatBotText(text);

            // Multimodal image display badge/card
            if (data && data.image) {
                const imgUrl = data.image.image_url || (data.image.patient_image_id ? `/chatbot/image/${data.image.patient_image_id}/view` : (data.image.image_id ? `/chatbot/image/${data.image.image_id}/view` : ''));
                if (imgUrl) {
                    const imgTitle = data.image.title || 'Clinical Image';
                    const imgType = (data.image.image_type || 'image').toUpperCase();
                    const dim = data.image.width && data.image.height ? `${data.image.width}×${data.image.height} px` : '';
                    formattedContent = `
                        <div class="mb-3 p-2 bg-slate-50 border border-slate-200 rounded-xl max-w-md">
                            <div class="flex items-center justify-between text-[11px] font-bold text-slate-700 mb-1.5 px-1">
                                <span class="truncate">${escapeHtml(imgTitle)}</span>
                                <span class="text-[9px] font-mono px-1.5 py-0.5 rounded bg-blue-100 text-blue-800">${escapeHtml(imgType)}</span>
                            </div>
                            <div class="relative rounded-lg overflow-hidden border border-slate-200 bg-slate-900/5 group">
                                <img src="${imgUrl}" alt="${escapeHtml(imgTitle)}" class="max-h-56 w-full object-contain mx-auto rounded-lg transition-transform group-hover:scale-[1.01]" />
                                <a href="${imgUrl}" target="_blank" class="absolute bottom-1.5 right-1.5 bg-slate-900/70 hover:bg-slate-900 text-white text-[10px] px-2 py-0.5 rounded-md flex items-center gap-1 backdrop-blur-xs transition-colors">
                                    <span class="material-symbols-outlined text-[12px]">fullscreen</span> Expand
                                </a>
                            </div>
                            ${dim ? `<div class="text-[9px] text-slate-400 mt-1 px-1 font-mono">${escapeHtml(dim)}</div>` : ''}
                        </div>
                    ` + formattedContent;
                }
            }

            // Disambiguation selection cards
            if (data && Array.isArray(data.candidates) && data.candidates.length > 0) {
                let cardsHtml = '<div class="grid grid-cols-1 md:grid-cols-2 gap-2.5 mt-3">';
                data.candidates.forEach(c => {
                    const pid = c.patient_id || c.id;
                    cardsHtml += `
                        <div onclick="selectPatientById(${pid})"
                             class="p-3 bg-slate-50 hover:bg-blue-50/80 border border-slate-200 hover:border-blue-400 rounded-xl cursor-pointer transition-all shadow-xs">
                            <div class="flex items-center justify-between">
                                <strong class="text-xs text-blue-900">${escapeHtml(c.name)}</strong>
                                <span class="text-[10px] font-mono bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded font-bold">${escapeHtml(c.patient_code || 'JS-' + pid)}</span>
                            </div>
                            <div class="text-[11px] text-slate-600 mt-1">
                                Age: ${c.age || '--'} (${c.gender || '--'}) • Unit: <strong>${escapeHtml(c.ward_type || 'ICU')}</strong> (Bed ${escapeHtml(c.bed_number || 'N/A')})
                            </div>
                            <button class="mt-2 text-[10px] bg-blue-600 text-white font-bold px-2.5 py-1 rounded-md hover:bg-blue-700 shadow-xs flex items-center gap-1 cursor-pointer">
                                <span class="material-symbols-outlined text-[12px]">open_in_new</span> Select for Rounds
                            </button>
                        </div>
                    `;
                });
                cardsHtml += '</div>';
                formattedContent += cardsHtml;
            }

            if (data && data.intent === 'patient_found' && data.patient_id) {
                formattedContent += `
                    <div class="mt-3 flex gap-2">
                        <button onclick="confirmShowSummary(${data.patient_id})" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-3 py-1.5 rounded-lg transition-colors shadow-sm flex items-center gap-1 cursor-pointer">
                            <span class="material-symbols-outlined text-[14px]">clinical_notes</span> Full Clinical Briefing
                        </button>
                        <button onclick="sendQuickAction('Current Vitals')" class="bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors border border-slate-300 cursor-pointer">
                            Bedside Vitals Only
                        </button>
                    </div>
                `;
            }

            // Append compact source citations when returned by the RAG backend
            formattedContent += renderSourceReferencesHtml(data);

            row.innerHTML = `
                <div class="w-9 h-9 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-xs flex-shrink-0 shadow-sm border-2 border-white">
                    <span class="material-symbols-outlined text-lg">stethoscope</span>
                </div>
                <div class="chat-bubble-doctor p-4.5 shadow-sm max-w-2xl text-xs text-slate-800 leading-relaxed space-y-2">
                    ${formattedContent}
                </div>
            `;

            if (sender === 'bot') {
                speakText(text);
            }
        }

        chatMessages.appendChild(row);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 5. PATIENT DROPDOWN & RBAC AUTHORIZED PATIENT LOADING
    // ─────────────────────────────────────────────────────────────────────────
    function togglePatientDropdown(e) {
        if (e) e.stopPropagation();
        const dropdownMenu = el('patient-dropdown-menu');
        if (!dropdownMenu) return;
        if (dropdownMenu.classList.contains('hidden')) {
            openPatientDropdown();
        } else {
            closePatientDropdown();
        }
    }

    function openPatientDropdown() {
        const dropdownMenu = el('patient-dropdown-menu');
        const dropdownArrow = el('dropdown-arrow');
        const dropdownSearch = el('dropdown-patient-search');
        if (dropdownMenu) dropdownMenu.classList.remove('hidden');
        if (dropdownArrow) dropdownArrow.style.transform = 'rotate(180deg)';
        if (dropdownSearch) {
            dropdownSearch.value = '';
            dropdownSearch.focus();
        }
        renderPatientDropdown(authorizedPatients);
    }

    function closePatientDropdown() {
        const dropdownMenu = el('patient-dropdown-menu');
        const dropdownArrow = el('dropdown-arrow');
        if (dropdownMenu) dropdownMenu.classList.add('hidden');
        if (dropdownArrow) dropdownArrow.style.transform = 'rotate(0deg)';
    }

    async function loadAuthorizedPatients() {
        const listContainer = el('patient-dropdown-list');
        const quickPicks = el('patient-quick-picks');
        if (listContainer) {
            listContainer.innerHTML = `
                <div class="p-3 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
                    <span class="material-symbols-outlined animate-spin text-sm text-blue-400">progress_activity</span>
                    <span>Loading authorized patients...</span>
                </div>
            `;
        }

        try {
            const res = await fetch('/chatbot/patients', { headers: getAuthHeaders() });
            if (res.status === 401) {
                throw new Error('Authentication required (401)');
            }
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            const data = await res.json();

            if (data.success && Array.isArray(data.patients) && data.patients.length > 0) {
                authorizedPatients = data.patients;
                renderPatientDropdown(authorizedPatients);

                if (quickPicks) {
                    const prefix = chatbotConfig.role === 'nurse' ? 'Assigned: ' : 'Examples: ';
                    const picks = authorizedPatients.slice(0, 3);
                    quickPicks.innerHTML = prefix + picks.map(p =>
                        `<button onclick="selectPatientById(${p.patient_id || p.id})" class="text-blue-600 font-bold hover:underline cursor-pointer">"${escapeHtml(p.name)}"</button>`
                    ).join(' • ');
                }

                const urlPid = (new URLSearchParams(window.location.search)).get('patient_id') || (new URLSearchParams(window.location.search)).get('id');
                const savedPid = sessionStorage.getItem(chatbotConfig.storagePatientKey);
                let initialPatient = null;
                if (urlPid) {
                    initialPatient = authorizedPatients.find(p => String(p.patient_id || p.id) === String(urlPid));
                }
                if (!initialPatient && savedPid) {
                    initialPatient = authorizedPatients.find(p => String(p.patient_id || p.id) === String(savedPid));
                }
                if (!initialPatient) {
                    initialPatient = authorizedPatients[0];
                }

                selectPatient(initialPatient, false);
            } else {
                authorizedPatients = [];
                const emptyLabel = chatbotConfig.role === 'nurse' ? 'No assigned patients available' : 'No patients available';
                if (listContainer) listContainer.innerHTML = `<div class="p-4 text-center text-xs text-slate-400">${emptyLabel}</div>`;
                if (el('bar-patient-name')) el('bar-patient-name').textContent = emptyLabel;
                if (el('bar-patient-code')) el('bar-patient-code').textContent = '--';
                if (el('bar-patient-ward')) el('bar-patient-ward').textContent = '--';
                if (el('bar-patient-bed')) el('bar-patient-bed').textContent = '--';
                if (el('bar-patient-ews')) {
                    el('bar-patient-ews').textContent = '--';
                    el('bar-patient-ews').className = 'px-2 py-0.5 rounded font-bold text-[11px] bg-slate-800 text-white';
                }
                if (el('bar-telemetry-time')) {
                    el('bar-telemetry-time').innerHTML = `<span class="material-symbols-outlined text-[13px]">schedule</span> Ready`;
                }
                if (quickPicks) quickPicks.textContent = 'No authorized patients found in database.';
            }
        } catch (err) {
            console.error('Failed to load authorized patients:', err);
            authorizedPatients = [];
            if (listContainer) listContainer.innerHTML = `<div class="p-4 text-center text-xs text-red-400 font-medium">Unable to load patients</div>`;
            if (el('bar-patient-name')) el('bar-patient-name').textContent = 'Unable to load patients';
            if (quickPicks) quickPicks.textContent = 'Unable to load patients from database.';
        }
    }

    function renderPatientDropdown(patientsList) {
        const listContainer = el('patient-dropdown-list');
        if (!listContainer) return;
        if (!patientsList || patientsList.length === 0) {
            const emptyLabel = chatbotConfig.role === 'nurse' ? 'No assigned patients available' : 'No patients available';
            listContainer.innerHTML = `<div class="p-4 text-center text-xs text-slate-400">${emptyLabel}</div>`;
            return;
        }

        let html = '';
        patientsList.forEach(p => {
            const pid = p.patient_id || p.id;
            const pCode = p.patient_code || `JS-${pid}`;
            const pName = escapeHtml(p.name);
            const ward = p.ward_type || p.ward_name || 'ICU';
            const bed = p.bed_number ? `Bed ${p.bed_number}` : 'No Bed';
            const ews = p.ews_score ?? 0;
            const risk = (p.ews_risk_level || p.risk_level || (ews >= 7 ? 'CRITICAL' : (ews >= 5 ? 'HIGH' : (ews >= 1 ? 'MEDIUM' : 'LOW')))).toUpperCase();

            let ewsBadgeClass = 'text-emerald-400 font-bold';
            if (risk === 'CRITICAL' || risk === 'HIGH' || ews >= 5) {
                ewsBadgeClass = 'text-red-400 font-bold';
            } else if (risk === 'MEDIUM' || ews >= 1) {
                ewsBadgeClass = 'text-amber-400 font-bold';
            }

            const isSelected = activePatientId && String(activePatientId) === String(pid);
            const bgClass = isSelected ? 'bg-blue-900/60 border-l-3 border-blue-400' : 'hover:bg-slate-800/80';

            html += `
                <div onclick="selectPatientById(${pid})"
                     class="p-2.5 ${bgClass} cursor-pointer flex items-center justify-between transition-colors">
                    <div class="min-w-0 pr-2">
                        <p class="text-xs font-bold text-white truncate">${pName}</p>
                        <p class="text-[10px] text-slate-400">${escapeHtml(pCode)} • ${escapeHtml(ward)} (${escapeHtml(bed)})</p>
                    </div>
                    <div class="text-right flex-shrink-0">
                        <span class="text-[10px] ${ewsBadgeClass}">EWS: ${ews}</span>
                        <p class="text-[9px] text-slate-400 font-semibold uppercase tracking-wider">${escapeHtml(risk)}</p>
                    </div>
                </div>
            `;
        });
        listContainer.innerHTML = html;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 6. QUICK ACTIONS & CHAT MODE SWITCHING (Patient Chat vs General Chat)
    // ─────────────────────────────────────────────────────────────────────────
    function renderQuickActions() {
        const container = el('quick-chips-container');
        const label = el('quick-actions-label');
        const uploadBtn = el('chat-image-upload-btn');
        if (!container) return;

        if (uploadBtn) {
            uploadBtn.disabled = false;
            uploadBtn.classList.remove('opacity-40', 'cursor-not-allowed');
            uploadBtn.title = chatMode === 'patient'
                ? 'Attach Clinical Image (ECG, X-Ray, Lab Sheet, Monitor Snapshot) for Active Patient'
                : 'Attach Medical Reference Image / Clinical Diagram for General Chat Analysis';
        }

        if (chatMode === 'patient') {
            if (label) label.innerHTML = `<span class="material-symbols-outlined text-[13px]">bolt</span> Clinical Handover:`;
            const protocolChipLabel = chatbotConfig.role === 'nurse' ? 'Nursing Escalation SOP' : 'Compare with ICU Protocol';
            container.innerHTML = `
                <button onclick="sendQuickAction('Current Vitals')" class="quick-chip bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-gray-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">ecg_heart</span> Current Vitals
                </button>
                <button onclick="sendQuickAction('Patient Summary')" class="quick-chip bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-gray-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">summarize</span> Full Summary
                </button>
                <button onclick="sendQuickAction('Vital Trends')" class="quick-chip bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-gray-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">trending_up</span> Longitudinal Trends
                </button>
                <button onclick="sendQuickAction('EWS & Score')" class="quick-chip bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-gray-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">speed</span> EWS & CSI Index
                </button>
                <button onclick="sendQuickAction('Transfer Recommendation')" class="quick-chip bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-gray-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">swap_horiz</span> Transfer Decision
                </button>
                <button onclick="sendQuickAction('Protocol Comparison')" class="quick-chip bg-purple-50 hover:bg-purple-100 text-purple-800 border border-purple-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">menu_book</span> ${protocolChipLabel}
                </button>
                <button onclick="sendQuickAction('Previous Decisions')" class="quick-chip bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-gray-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">history</span> Review History
                </button>
                <button onclick="sendQuickAction('Documented Condition')" class="quick-chip bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-gray-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">diagnosis</span> Documented Condition
                </button>
                <button onclick="openCustomTelemetryModal()" class="quick-chip bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-700 hover:to-indigo-700 px-3.5 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 flex-shrink-0 shadow-sm transition-all transform hover:scale-105 cursor-pointer">
                    <span class="material-symbols-outlined text-[15px]">science</span> ⚡ Custom Input / Simulator
                </button>
            `;
        } else {
            if (label) label.innerHTML = `<span class="material-symbols-outlined text-[13px]">school</span> General Healthcare & Hospital SOPs:`;
            container.innerHTML = `
                <button onclick="sendGeneralQuickPrompt('What is the hospital ICU to HDU step-down transfer protocol?')" class="quick-chip bg-purple-50 hover:bg-purple-100 text-purple-800 border border-purple-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">menu_book</span> ICU ↔ HDU Step-Down SOP
                </button>
                <button onclick="sendGeneralQuickPrompt('What is EWS and how is it scored according to hospital protocol?')" class="quick-chip bg-purple-50 hover:bg-purple-100 text-purple-800 border border-purple-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">speed</span> EWS Escalation Protocol
                </button>
                <button onclick="sendGeneralQuickPrompt('What are the normal vital signs for an adult?')" class="quick-chip bg-purple-50 hover:bg-purple-100 text-purple-800 border border-purple-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">vital_signs</span> Normal Vital Signs
                </button>
                <button onclick="sendGeneralQuickPrompt('What is the difference between ICU and HDU?')" class="quick-chip bg-purple-50 hover:bg-purple-100 text-purple-800 border border-purple-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">domain</span> ICU vs HDU Criteria
                </button>
                <button onclick="sendGeneralQuickPrompt('What are the clinical signs and criteria for sepsis?')" class="quick-chip bg-purple-50 hover:bg-purple-100 text-purple-800 border border-purple-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">warning</span> Sepsis Criteria
                </button>
                <button onclick="sendGeneralQuickPrompt('What does oxygen saturation (SpO2) measure?')" class="quick-chip bg-purple-50 hover:bg-purple-100 text-purple-800 border border-purple-200 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 flex-shrink-0 cursor-pointer">
                    <span class="material-symbols-outlined text-[14px]">air</span> Oxygen Saturation
                </button>
            `;
        }
    }

    function setChatMode(newMode) {
        chatMode = newMode === 'general' ? 'general' : 'patient';
        activeChatImageContext = null;
        const patientBtn = el('mode-patient-btn');
        const generalBtn = el('mode-general-btn');
        const pDropdownBtn = el('patient-dropdown-btn');
        const pCodeEl = el('bar-patient-code');
        const locContainer = el('bar-location-container');
        const ewsContainer = el('bar-ews-container');
        const ewsDivider = el('bar-ews-divider');
        const timeEl = el('bar-telemetry-time');
        const syncBtn = el('sync-vitals-btn');
        const switchBtn = el('switch-patient-btn');
        const userInputEl = el('user-input');

        if (chatMode === 'general') {
            if (patientBtn) patientBtn.className = 'px-2.5 py-1 text-xs font-semibold rounded-md flex items-center gap-1 transition-all text-slate-400 hover:text-slate-200 cursor-pointer';
            if (generalBtn) generalBtn.className = 'px-2.5 py-1 text-xs font-bold rounded-md flex items-center gap-1 transition-all bg-purple-600 text-white shadow-xs cursor-pointer';

            if (el('bar-patient-name')) el('bar-patient-name').textContent = 'No Patient Selected';
            if (pDropdownBtn) pDropdownBtn.className = 'bg-slate-800/60 text-slate-400 font-medium text-xs px-2.5 py-1 rounded border border-slate-700/60 flex items-center gap-1.5 cursor-not-allowed opacity-80';
            if (pCodeEl) pCodeEl.textContent = 'GENERAL_MODE';
            if (locContainer) locContainer.innerHTML = 'Mode: <strong class="text-purple-300">General Healthcare & Hospital SOPs (Zero Patient Data)</strong>';
            if (ewsContainer) ewsContainer.classList.add('hidden');
            if (ewsDivider) ewsDivider.classList.add('hidden');
            if (timeEl) timeEl.innerHTML = `<span class="material-symbols-outlined text-[13px]">public</span> ChromaDB Knowledge + Gemma 4`;
            if (syncBtn) syncBtn.disabled = true;
            if (switchBtn) switchBtn.classList.add('hidden');
            if (userInputEl) userInputEl.placeholder = 'Ask general medical, SOP, protocol, or EWS scoring questions (no patient data accessed)...';

            appendMessage(
                'bot',
                '🌐 **Switched to General Healthcare Chat Mode.**\n\nNo patient record is attached. You can query general medical knowledge, approved hospital SOPs, ICU/HDU admission & step-down protocols, and EWS guidelines.\n\n*Privacy Guarantee: Individual patient records, vitals, and patient-specific images are strictly blocked in General Chat mode.*'
            );
        } else {
            if (patientBtn) patientBtn.className = 'px-2.5 py-1 text-xs font-bold rounded-md flex items-center gap-1 transition-all bg-blue-600 text-white shadow-xs cursor-pointer';
            if (generalBtn) generalBtn.className = 'px-2.5 py-1 text-xs font-semibold rounded-md flex items-center gap-1 transition-all text-slate-400 hover:text-slate-200 cursor-pointer';

            if (pDropdownBtn) pDropdownBtn.className = 'bg-blue-900/80 hover:bg-blue-800/90 text-white font-bold text-xs px-2.5 py-1 rounded border border-blue-700/60 flex items-center gap-1.5 transition-all shadow-xs focus:outline-none focus:ring-1 focus:ring-blue-400 cursor-pointer';
            if (ewsContainer) ewsContainer.classList.remove('hidden');
            if (ewsDivider) ewsDivider.classList.remove('hidden');
            if (switchBtn) switchBtn.classList.remove('hidden');
            if (userInputEl) {
                userInputEl.placeholder = chatbotConfig.role === 'nurse'
                    ? 'Ask Dr. Setu about current vitals, EWS risk, nursing SOPs, or transfer readiness...'
                    : 'Ask Dr. Setu about current vitals, EWS risk, hospital protocols, or transfer decision...';
            }

            if (activePatientData) {
                selectPatient(activePatientData, false);
                appendMessage(
                    'bot',
                    `👤 **Switched to Patient Chat Mode.**\n\nActive context for **${escapeHtml(activePatientData.name || 'Selected Patient')}** (${escapeHtml(activePatientData.patient_code || '')}) restored from verified Jeevan Setu MySQL records + ChromaDB clinical protocols.`
                );
            } else if (authorizedPatients && authorizedPatients.length > 0) {
                selectPatient(authorizedPatients[0], false);
                appendMessage(
                    'bot',
                    `👤 **Switched to Patient Chat Mode.**\n\nActive context for **${escapeHtml(authorizedPatients[0].name)}** selected.`
                );
            } else {
                if (el('bar-patient-name')) el('bar-patient-name').textContent = 'Select a Patient';
                if (pCodeEl) pCodeEl.textContent = '--';
                if (locContainer) locContainer.innerHTML = 'Location: <strong class="text-white">--</strong>';
            }
        }
        renderQuickActions();
    }

    function sendGeneralQuickPrompt(promptText) {
        sendMessage(promptText);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 7. PATIENT SELECTION & CONVERSATION HISTORY RESTORATION
    // ─────────────────────────────────────────────────────────────────────────
    async function loadConversationHistory(patientId) {
        if (!patientId) return;
        try {
            const res = await fetch(`/chatbot/history/${patientId}?limit=5`, { headers: getAuthHeaders() });
            if (!res.ok) return;
            const data = await res.json();
            if (data.success && Array.isArray(data.data) && data.data.length > 0) {
                return data.data;
            }
        } catch (e) {
            // Non-blocking history fetch
        }
        return [];
    }

    function selectPatient(patient, announceChat = true) {
        if (!patient) return;
        activeChatImageContext = null;
        const pid = patient.patient_id || patient.id;
        activePatientId = pid;
        activePatientData = patient;
        sessionStorage.setItem(chatbotConfig.storagePatientKey, pid);

        if (chatMode !== 'patient') {
            chatMode = 'patient';
            const patientBtn = el('mode-patient-btn');
            const generalBtn = el('mode-general-btn');
            if (patientBtn) patientBtn.className = 'px-2.5 py-1 text-xs font-bold rounded-md flex items-center gap-1 transition-all bg-blue-600 text-white shadow-xs cursor-pointer';
            if (generalBtn) generalBtn.className = 'px-2.5 py-1 text-xs font-semibold rounded-md flex items-center gap-1 transition-all text-slate-400 hover:text-slate-200 cursor-pointer';
            if (el('bar-ews-container')) el('bar-ews-container').classList.remove('hidden');
            if (el('bar-ews-divider')) el('bar-ews-divider').classList.remove('hidden');
            if (el('switch-patient-btn')) el('switch-patient-btn').classList.remove('hidden');
            renderQuickActions();
        }

        if (el('bar-patient-name')) el('bar-patient-name').textContent = patient.name || `Patient #${pid}`;
        if (el('bar-patient-code')) el('bar-patient-code').textContent = patient.patient_code || `JS-${pid}`;

        const locContainer = el('bar-location-container');
        const wardName = patient.ward_type || patient.ward_name || 'ICU';
        const bedNumber = patient.bed_number || 'N/A';
        if (locContainer) {
            locContainer.innerHTML = `Location: <strong class="text-white" id="bar-patient-ward">${escapeHtml(wardName)}</strong> (Bed: <span id="bar-patient-bed">${escapeHtml(bedNumber)}</span>)`;
        }

        const ewsBadge = el('bar-patient-ews');
        const ewsVal = patient.ews_score ?? 0;
        const risk = (patient.ews_risk_level || patient.risk_level || (ewsVal >= 7 ? 'CRITICAL' : (ewsVal >= 5 ? 'HIGH' : (ewsVal >= 1 ? 'MEDIUM' : 'LOW')))).toUpperCase();
        if (ewsBadge) {
            ewsBadge.textContent = `${ewsVal} (${risk})`;
            if (risk === 'CRITICAL' || risk === 'HIGH' || ewsVal >= 5) {
                ewsBadge.className = 'px-2 py-0.5 rounded font-bold text-[11px] bg-red-600 text-white shadow-xs';
            } else if (risk === 'MEDIUM' || ewsVal >= 1) {
                ewsBadge.className = 'px-2 py-0.5 rounded font-bold text-[11px] bg-amber-500 text-white shadow-xs';
            } else {
                ewsBadge.className = 'px-2 py-0.5 rounded font-bold text-[11px] bg-emerald-600 text-white shadow-xs';
            }
        }

        const recTime = patient.recorded_at || patient.vitals_recorded_at || 'Recently recorded';
        if (el('bar-telemetry-time')) {
            el('bar-telemetry-time').innerHTML = `<span class="material-symbols-outlined text-[13px]">schedule</span> Recorded: ${escapeHtml(recTime)}`;
        }

        const syncVitalsBtn = el('sync-vitals-btn');
        if (syncVitalsBtn) syncVitalsBtn.disabled = false;

        closePatientDropdown();
        renderPatientDropdown(authorizedPatients);

        const searchInput = el('top-patient-search');
        if (searchInput) searchInput.value = patient.name || '';

        fetch(`/chatbot/patient/${pid}/summary`, { headers: getAuthHeaders() })
            .then(r => {
                if (r.status === 403) throw new Error('Unauthorized');
                return r.json();
            })
            .then(data => {
                if (data.success && data.context) {
                    activePatientData = data.context.patient || patient;
                    if (data.context.ews && ewsBadge) {
                        const e = data.context.ews;
                        const eScore = e.score ?? ewsVal;
                        const eRisk = (e.risk_level || risk).toUpperCase();
                        ewsBadge.textContent = `${eScore} (${eRisk})`;
                        if (eRisk === 'CRITICAL' || eRisk === 'HIGH' || eScore >= 5) {
                            ewsBadge.className = 'px-2 py-0.5 rounded font-bold text-[11px] bg-red-600 text-white shadow-xs';
                        } else if (eRisk === 'MEDIUM' || eScore >= 1) {
                            ewsBadge.className = 'px-2 py-0.5 rounded font-bold text-[11px] bg-amber-500 text-white shadow-xs';
                        } else {
                            ewsBadge.className = 'px-2 py-0.5 rounded font-bold text-[11px] bg-emerald-600 text-white shadow-xs';
                        }
                    }
                    if (data.context && typeof window.updateDashboardFromContext === 'function') {
                        window.updateDashboardFromContext(data.context, data.text);
                    }
                    if (announceChat) {
                        const roundLabel = chatbotConfig.role === 'nurse' ? 'nurse rounds' : 'clinical rounds';
                        appendMessage(
                            'bot',
                            `Patient **${escapeHtml(patient.name)}** (${escapeHtml(patient.patient_code || 'JS-' + pid)}) selected for ${roundLabel}.\n\n**Location:** ${escapeHtml(patient.ward_type || 'ICU')} (Bed ${escapeHtml(patient.bed_number || 'N/A')}) | **EWS:** ${patient.ews_score ?? 0} (${escapeHtml(risk)})\n**Diagnosis:** ${escapeHtml(data.context.diagnosis || patient.diagnosis || 'Documented in EHR')}\n\nYou can ask clinical questions, compare with hospital protocols, upload clinical images, or check transfer status for this patient.`
                        );
                    }
                }
            })
            .catch(() => {
                if (announceChat) {
                    appendMessage('bot', `Patient **${escapeHtml(patient.name)}** (${escapeHtml(patient.patient_code || 'JS-' + pid)}) selected.`);
                }
            });
    }

    function selectPatientById(pid) {
        const patient = authorizedPatients.find(p => String(p.patient_id || p.id) === String(pid));
        if (patient) {
            selectPatient(patient, true);
        } else {
            appendMessage('bot', '⚠️ **Access Forbidden**: Patient #' + pid + ' is not assigned to your clinician account.');
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 8. CORE MESSAGE SENDING (with Duplicate-Submission Lock & Error Handling)
    // ─────────────────────────────────────────────────────────────────────────
    function setSendingState(sending) {
        isSending = sending;
        const sendBtn = el('send-btn');
        const userInput = el('user-input');
        const typingIndicator = el('typing-indicator');
        if (sendBtn) {
            sendBtn.disabled = sending;
            if (sending) {
                sendBtn.classList.add('opacity-60', 'cursor-not-allowed');
            } else {
                sendBtn.classList.remove('opacity-60', 'cursor-not-allowed');
            }
        }
        if (userInput) {
            userInput.disabled = sending;
        }
        if (typingIndicator) {
            if (sending) {
                typingIndicator.classList.remove('hidden');
            } else {
                typingIndicator.classList.add('hidden');
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 8. ATTACHMENT STAGING & PREVIEW (Composer Upgrade)
    // ─────────────────────────────────────────────────────────────────────────
    function stageChatAttachment(file) {
        if (!file) return;

        const allowedTypes = ['image/png', 'image/jpeg', 'image/webp'];
        if (!allowedTypes.includes(file.type)) {
            appendMessage('bot', '⚠️ **Unsupported Image Format**: Only `PNG`, `JPEG`, and `WebP` images are supported.');
            return;
        }

        const maxBytes = 10 * 1024 * 1024; // 10 MB
        if (file.size > maxBytes) {
            appendMessage('bot', '⚠️ **File Too Large**: Maximum allowed image size is **10 MB**.');
            return;
        }

        if (stagedImagePreviewUrl) {
            try { URL.revokeObjectURL(stagedImagePreviewUrl); } catch (e) {}
        }

        stagedImageFile = file;
        stagedImagePreviewUrl = URL.createObjectURL(file);

        const container = el('chat-attachment-preview-container');
        const thumb = el('chat-attachment-thumbnail');
        const fallbackIcon = el('chat-attachment-fallback-icon');
        const nameEl = el('chat-attachment-filename');
        const sizeEl = el('chat-attachment-filesize');

        if (thumb) {
            thumb.src = stagedImagePreviewUrl;
            thumb.classList.remove('hidden');
        }
        if (fallbackIcon) fallbackIcon.classList.add('hidden');
        if (nameEl) nameEl.textContent = file.name || 'Attached Image';
        if (sizeEl) sizeEl.textContent = formatFileSize(file.size);
        if (container) container.classList.remove('hidden');
    }

    function removeChatAttachment() {
        if (stagedImagePreviewUrl) {
            try { URL.revokeObjectURL(stagedImagePreviewUrl); } catch (e) {}
            stagedImagePreviewUrl = null;
        }
        stagedImageFile = null;

        const container = el('chat-attachment-preview-container');
        const thumb = el('chat-attachment-thumbnail');
        const fallbackIcon = el('chat-attachment-fallback-icon');
        const input = el('chat-image-upload-input');

        if (container) container.classList.add('hidden');
        if (thumb) {
            thumb.src = '';
            thumb.classList.add('hidden');
        }
        if (fallbackIcon) fallbackIcon.classList.remove('hidden');
        if (input) input.value = '';
    }

    function triggerPatientImageUpload() {
        const fileInput = el('chat-image-upload-input');
        if (fileInput) {
            fileInput.value = '';
            fileInput.click();
        }
    }

    function handlePatientImageSelected(event) {
        const fileInput = event.target;
        if (!fileInput || !fileInput.files || fileInput.files.length === 0) return;
        const file = fileInput.files[0];
        stageChatAttachment(file);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 9. CORE MESSAGE SENDING (Supports Text-Only, Image-Only, and Combined)
    // ─────────────────────────────────────────────────────────────────────────
    async function sendMessage(msgText, customVitals = null, customNotes = null) {
        if (isSending) return;
        const cleanMsg = (msgText || '').trim();
        const hasAttachment = Boolean(stagedImageFile);

        if (!cleanMsg && !customVitals && !hasAttachment) return;

        // In patient mode, if sending image ensure active patient is selected
        if (hasAttachment && chatMode === 'patient' && !activePatientId) {
            appendMessage('bot', '⚠️ **No Patient Selected**: Please select an authorized patient from the dropdown before uploading a clinical image.');
            return;
        }

        const displayText = cleanMsg || (customVitals
            ? `Evaluate Custom Telemetry (SpO2: ${customVitals.spo2 || 'N/A'}%, HR: ${customVitals.heart_rate || 'N/A'} bpm, BP: ${customVitals.blood_pressure_sys || 'N/A'}/${customVitals.blood_pressure_dia || 'N/A'})`
            : (hasAttachment ? `📎 Attached Image: ${stagedImageFile.name}` : ''));

        const userMsgData = hasAttachment ? {
            imagePreviewUrl: stagedImagePreviewUrl,
            imageName: stagedImageFile.name,
            imageSize: formatFileSize(stagedImageFile.size)
        } : null;

        appendMessage('user', displayText, userMsgData);

        const userInput = el('user-input');
        if (userInput) userInput.value = '';
        setSendingState(true);

        const sendingFile = stagedImageFile;
        const sendingPreviewUrl = stagedImagePreviewUrl;

        try {
            let response;
            let data;

            if (sendingFile) {
                // Submit multimodal payload via FormData
                const formData = new FormData();
                formData.append('image', sendingFile);
                formData.append('mode', chatMode);
                if (chatMode === 'patient' && activePatientId) {
                    formData.append('patient_id', String(activePatientId));
                }
                formData.append('title', sendingFile.name);
                formData.append('image_type', 'other');
                if (cleanMsg) {
                    formData.append('message', cleanMsg);
                }

                try {
                    response = await fetch('/chatbot/image/upload', {
                        method: 'POST',
                        headers: getAuthHeaders(false),
                        body: formData
                    });
                } catch (e1) {
                    response = await fetch('/api/v1/chatbot/image/upload', {
                        method: 'POST',
                        headers: getAuthHeaders(false),
                        body: formData
                    });
                }

                data = await response.json().catch(() => ({}));
            } else {
                // Standard text / telemetry payload
                const payload = {
                    message: cleanMsg,
                    mode: chatMode,
                    patient_id: chatMode === 'patient' ? activePatientId : null
                };
                if (activeChatImageContext && activeChatImageContext.imageId) {
                    payload.active_image_id = activeChatImageContext.imageId;
                }
                if (customVitals) payload.custom_vitals = customVitals;
                if (customNotes) payload.custom_notes = customNotes;

                try {
                    response = await fetch('/chatbot/message', {
                        method: 'POST',
                        headers: getAuthHeaders(true),
                        body: JSON.stringify(payload)
                    });
                } catch (e1) {
                    response = await fetch('/api/v1/chatbot/message', {
                        method: 'POST',
                        headers: getAuthHeaders(true),
                        body: JSON.stringify(payload)
                    });
                }

                data = await response.json().catch(() => ({}));
            }

            setSendingState(false);
            if (userInput) userInput.focus();

            if (response.status === 401) {
                appendMessage('bot', '🔒 **Session Expired or Unauthenticated (401)**: Please sign in again to continue using the Jeevan Setu Clinical Assistant.');
                return;
            }

            if (response.status === 403) {
                appendMessage('bot', `⚠️ **Access Forbidden (403)**: ${data.error || 'You are not authorized to perform this clinical action under hospital RBAC policy.'}`);
                return;
            }

            if (response.status === 404) {
                appendMessage('bot', '⚠️ **Patient Record Not Found (404)**: The requested patient record could not be located in Jeevan Setu.');
                return;
            }

            if (response.status === 429) {
                appendMessage('bot', '⏳ **Service Busy (429)**: Too many requests. Please wait a moment and try again.');
                return;
            }

            if (data.success) {
                // Remove staged attachment only on confirmed successful send
                if (sendingFile) {
                    removeChatAttachment();
                    if (data.image) {
                        activeChatImageContext = {
                            imageId: data.image.image_id || data.image.patient_image_id,
                            title: data.image.title,
                            url: data.image.image_url
                        };
                    }
                }

                if (chatMode === 'patient' && data.patient_id && (!activePatientId || String(activePatientId) !== String(data.patient_id))) {
                    const authP = authorizedPatients.find(p => String(p.patient_id || p.id) === String(data.patient_id));
                    if (authP) {
                        selectPatient(authP, false);
                    }
                }
                appendMessage('bot', data.text || data.response, data);
            } else {
                // Retain staged attachment on failure so clinician can retry
                appendMessage('bot', data.error || data.text || 'Unable to process your request at this time.');
            }
        } catch (err) {
            setSendingState(false);
            if (userInput) userInput.focus();
            // Retain staged attachment on network failure
            appendMessage('bot', '⚠️ **Network Connection Error**: Unable to reach the Jeevan Setu chatbot service. Please verify your connection.');
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 10. CUSTOM TELEMETRY SIMULATOR MODAL & QUICK ACTIONS
    // ─────────────────────────────────────────────────────────────────────────
    function openCustomTelemetryModal() {
        const modal = el('custom-telemetry-modal');
        if (modal) modal.classList.remove('hidden');
    }

    function closeCustomTelemetryModal() {
        const modal = el('custom-telemetry-modal');
        if (modal) modal.classList.add('hidden');
    }

    function resetCustomTelemetryForm() {
        if (el('custom-spo2')) el('custom-spo2').value = '';
        if (el('custom-hr')) el('custom-hr').value = '';
        if (el('custom-rr')) el('custom-rr').value = '';
        if (el('custom-sys')) el('custom-sys').value = '';
        if (el('custom-dia')) el('custom-dia').value = '';
        if (el('custom-temp')) el('custom-temp').value = '';
        if (el('custom-avpu')) el('custom-avpu').value = 'Alert';
        if (el('custom-notes')) el('custom-notes').value = '';
    }

    function loadTelemetryPreset(type) {
        if (type === 'sepsis') {
            el('custom-spo2').value = 91;
            el('custom-hr').value = 128;
            el('custom-rr').value = 28;
            el('custom-sys').value = 85;
            el('custom-dia').value = 52;
            el('custom-temp').value = 39.2;
            el('custom-avpu').value = 'Voice';
            el('custom-notes').value = 'Suspected septic shock with severe physiological decompensation.';
        } else if (type === 'resp_distress') {
            el('custom-spo2').value = 84;
            el('custom-hr').value = 118;
            el('custom-rr').value = 32;
            el('custom-sys').value = 135;
            el('custom-dia').value = 88;
            el('custom-temp').value = 37.8;
            el('custom-avpu').value = 'Alert';
            el('custom-notes').value = 'Acute respiratory distress with low oxygen saturation and tachypnea.';
        } else if (type === 'tachycardia') {
            el('custom-spo2').value = 93;
            el('custom-hr').value = 142;
            el('custom-rr').value = 24;
            el('custom-sys').value = 88;
            el('custom-dia').value = 56;
            el('custom-temp').value = 38.1;
            el('custom-avpu').value = 'Voice';
            el('custom-notes').value = 'Hemodynamically unstable supraventricular tachycardia with borderline hypotension.';
        } else if (type === 'normal') {
            el('custom-spo2').value = 98;
            el('custom-hr').value = 74;
            el('custom-rr').value = 16;
            el('custom-sys').value = 120;
            el('custom-dia').value = 80;
            el('custom-temp').value = 36.8;
            el('custom-avpu').value = 'Alert';
            el('custom-notes').value = 'Normal baseline telemetry parameters.';
        }
    }

    function submitCustomTelemetry() {
        const vitals = {};
        const spo2 = parseFloat(el('custom-spo2')?.value);
        const hr = parseFloat(el('custom-hr')?.value);
        const rr = parseFloat(el('custom-rr')?.value);
        const sys = parseFloat(el('custom-sys')?.value);
        const dia = parseFloat(el('custom-dia')?.value);
        const temp = parseFloat(el('custom-temp')?.value);
        const avpu = el('custom-avpu')?.value;
        const notes = (el('custom-notes')?.value || '').trim();

        if (!isNaN(spo2)) vitals.spo2 = spo2;
        if (!isNaN(hr)) vitals.heart_rate = hr;
        if (!isNaN(rr)) vitals.respiratory_rate = rr;
        if (!isNaN(sys)) vitals.blood_pressure_sys = sys;
        if (!isNaN(dia)) vitals.blood_pressure_dia = dia;
        if (!isNaN(temp)) vitals.temperature = temp;
        if (avpu) vitals.consciousness = avpu;

        if (Object.keys(vitals).length === 0 && !notes) {
            alert('Please enter at least one vital parameter or clinical note.');
            return;
        }

        closeCustomTelemetryModal();
        const queryText = notes || `Assess custom telemetry: SpO2 ${vitals.spo2 || 'N/A'}%, HR ${vitals.heart_rate || 'N/A'} bpm, BP ${vitals.blood_pressure_sys || 'N/A'}/${vitals.blood_pressure_dia || 'N/A'} mmHg, RR ${vitals.respiratory_rate || 'N/A'}/min`;
        sendMessage(queryText, vitals, notes);
    }

    async function syncLiveVitals() {
        if (!activePatientId || chatMode !== 'patient' || isSending) return;
        const typingIndicator = el('typing-indicator');
        if (typingIndicator) typingIndicator.classList.remove('hidden');
        try {
            const res = await fetch(`/chatbot/patient/${activePatientId}/summary`, { headers: getAuthHeaders() });
            const data = await res.json();
            if (typingIndicator) typingIndicator.classList.add('hidden');
            if (data.success) {
                selectPatient(data.context.patient || activePatientData, false);
                appendMessage('bot', `**Live Telemetry Update Synced** at ${new Date().toLocaleTimeString()}:\n\n` + data.text);
            }
        } catch (e) {
            if (typingIndicator) typingIndicator.classList.add('hidden');
        }
    }

    function sendQuickAction(actionName) {
        if (chatMode !== 'patient') {
            setChatMode('patient');
        }
        if (!activePatientId && actionName !== 'Patient Summary') {
            const roleTitle = chatbotConfig.role === 'nurse' ? 'Nurse' : 'Clinician';
            appendMessage('bot', `${roleTitle}, please select an authorized patient from the dropdown first before requesting ${actionName}.`);
            return;
        }
        if (actionName === 'Current Vitals') {
            sendMessage('What are the latest vitals?');
        } else if (actionName === 'Patient Summary') {
            sendMessage('Show complete patient summary');
        } else if (actionName === 'Vital Trends') {
            sendMessage('How have the vitals changed? Show vital trends.');
        } else if (actionName === 'EWS & Score') {
            sendMessage('What is the current EWS score and stability index?');
        } else if (actionName === 'Transfer Recommendation') {
            sendMessage('What is the transfer recommendation for this patient and why?');
        } else if (actionName === 'Protocol Comparison') {
            const q = chatbotConfig.role === 'nurse'
                ? 'Compare this patient current vitals and EWS with the hospital nursing escalation protocol and SOP.'
                : 'Compare this patient current vitals, EWS, and transfer status with the hospital ICU to HDU step-down protocol.';
            sendMessage(q);
        } else if (actionName === 'Previous Decisions') {
            sendMessage('Show transfer decision history and clinician reviews.');
        } else if (actionName === 'Documented Condition') {
            sendMessage('What illness or diagnosis is documented for this patient?');
        }
    }

    function confirmShowSummary(patientId) {
        const authP = authorizedPatients.find(p => String(p.patient_id || p.id) === String(patientId));
        if (!authP) {
            appendMessage('bot', '⚠️ **Access Forbidden**: You are not authorized to view clinical data for patient #' + patientId + '.');
            return;
        }
        selectPatient(authP, false);
        sendMessage('Show complete patient summary');
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 11. INITIALIZATION & EVENT BINDINGS
    // ─────────────────────────────────────────────────────────────────────────
    function initJeevanSetuRagChatbot(options = {}) {
        chatbotConfig.role = (options.role || 'doctor').toLowerCase();
        chatbotConfig.storagePatientKey = chatbotConfig.role === 'nurse'
            ? 'jeevan_setu_nurse_active_patient_id'
            : 'jeevan_setu_active_patient_id';

        const chatForm = el('chat-form');
        const userInput = el('user-input');
        const dropdownSearch = el('dropdown-patient-search');
        const searchInput = el('top-patient-search');
        const searchDropdown = el('search-dropdown');
        const clearSearchBtn = el('clear-search-btn');
        const imageInput = el('chat-image-upload-input');

        if (chatForm) {
            chatForm.addEventListener('submit', (e) => {
                e.preventDefault();
                if (userInput) sendMessage(userInput.value);
            });
        }

        if (imageInput) {
            imageInput.addEventListener('change', handlePatientImageSelected);
        }

        if (dropdownSearch) {
            dropdownSearch.addEventListener('input', () => {
                const q = dropdownSearch.value.trim().toLowerCase();
                if (!q) {
                    renderPatientDropdown(authorizedPatients);
                    return;
                }
                const filtered = authorizedPatients.filter(p => {
                    const name = (p.name || '').toLowerCase();
                    const code = (p.patient_code || '').toLowerCase();
                    const ward = (p.ward_type || p.ward_name || '').toLowerCase();
                    const bed = (p.bed_number || '').toLowerCase();
                    return name.includes(q) || code.includes(q) || ward.includes(q) || bed.includes(q);
                });
                renderPatientDropdown(filtered);
            });
        }

        if (searchInput) {
            searchInput.addEventListener('input', () => {
                const q = searchInput.value.trim();
                if (q.length > 0) {
                    if (clearSearchBtn) clearSearchBtn.classList.remove('hidden');
                } else {
                    if (clearSearchBtn) clearSearchBtn.classList.add('hidden');
                    if (searchDropdown) searchDropdown.classList.add('hidden');
                    return;
                }

                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(async () => {
                    try {
                        const res = await fetch(`/chatbot/patients/search?q=${encodeURIComponent(q)}`, { headers: getAuthHeaders() });
                        const data = await res.json();
                        if (data.success && Array.isArray(data.patients) && data.patients.length > 0) {
                            let html = '';
                            data.patients.forEach(p => {
                                const pid = p.patient_id || p.id;
                                html += `
                                    <div onclick="selectPatientById(${pid})"
                                         class="px-3.5 py-2.5 hover:bg-blue-50 cursor-pointer border-b border-gray-100 flex items-center justify-between transition-colors">
                                        <div>
                                            <p class="text-xs font-bold text-slate-800">${escapeHtml(p.name)}</p>
                                            <p class="text-[10px] text-slate-500">${p.age || '--'}y (${p.gender || '--'}) • <strong>${escapeHtml(p.ward_type || 'ICU')}</strong> (Bed ${escapeHtml(p.bed_number || 'N/A')})</p>
                                        </div>
                                        <span class="text-[10px] font-mono bg-blue-100 text-blue-800 font-bold px-2 py-0.5 rounded">${escapeHtml(p.patient_code || 'JS-' + pid)}</span>
                                    </div>
                                `;
                            });
                            if (searchDropdown) {
                                searchDropdown.innerHTML = html;
                                searchDropdown.classList.remove('hidden');
                            }
                        } else if (searchDropdown) {
                            const emptyMsg = chatbotConfig.role === 'nurse'
                                ? 'No matching assigned patients found.'
                                : 'No matching authorized patients found.';
                            searchDropdown.innerHTML = `<div class="p-3 text-xs text-gray-400">${emptyMsg}</div>`;
                            searchDropdown.classList.remove('hidden');
                        }
                    } catch (e) {
                        console.error('Search failed', e);
                    }
                }, 200);
            });
        }

        if (clearSearchBtn) {
            clearSearchBtn.addEventListener('click', () => {
                if (searchInput) searchInput.value = '';
                clearSearchBtn.classList.add('hidden');
                if (searchDropdown) searchDropdown.classList.add('hidden');
            });
        }

        document.addEventListener('click', (e) => {
            if (searchInput && searchDropdown && !searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
                searchDropdown.classList.add('hidden');
            }
            const dropdownMenu = el('patient-dropdown-menu');
            const pBtn = el('patient-dropdown-btn');
            const swBtn = el('switch-patient-btn');
            if (dropdownMenu && !dropdownMenu.contains(e.target) && (!pBtn || !pBtn.contains(e.target)) && (!swBtn || !swBtn.contains(e.target))) {
                closePatientDropdown();
            }
        });

        // Populate clinician profile in sidebar/header
        try {
            const userObj = JSON.parse(localStorage.getItem('jeevan_setu_user') || sessionStorage.getItem('jeevan_setu_user') || '{}');
            if (userObj && (userObj.full_name || userObj.username)) {
                const fullName = userObj.full_name || userObj.username;
                if (el('sidebar-clinician-name')) el('sidebar-clinician-name').textContent = fullName;
                if (el('sidebar-clinician-role')) {
                    const r = (userObj.role || chatbotConfig.role).toUpperCase();
                    el('sidebar-clinician-role').textContent = `${r} • Hospital Duty`;
                }
                if (el('sidebar-clinician-avatar')) {
                    el('sidebar-clinician-avatar').textContent = fullName.substring(0, 2).toUpperCase();
                }
                if (el('header-nurse-name')) el('header-nurse-name').textContent = fullName;
                if (el('header-nurse-ward')) el('header-nurse-ward').textContent = userObj.ward || userObj.department || 'Nurse Station';
            }
        } catch (e) {}

        // ─────────────────────────────────────────────────────────────────────
        // Clipboard Paste Listener (Ctrl+V): Handles image paste, preserves text paste
        // ─────────────────────────────────────────────────────────────────────
        document.addEventListener('paste', (e) => {
            const clipboardData = e.clipboardData || window.clipboardData;
            if (!clipboardData) return;

            const items = clipboardData.items;
            if (!items) return;

            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                if (item.kind === 'file' && item.type.startsWith('image/')) {
                    e.preventDefault();
                    const blob = item.getAsFile();
                    if (blob) {
                        const ext = blob.type.split('/')[1] || 'png';
                        const timeStr = new Date().toISOString().replace(/[:.]/g, '-');
                        const file = new File([blob], `pasted_clip_${timeStr}.${ext}`, { type: blob.type });
                        stageChatAttachment(file);
                    }
                    return;
                }
            }
            // If clipboard contains plain text, browser default paste into user-input operates unhindered
        });

        // ─────────────────────────────────────────────────────────────────────
        // Drag and Drop Listeners: Interactive drop zone with visual indicators
        // ─────────────────────────────────────────────────────────────────────
        const chatFormEl = el('chat-form');
        const chatMessagesEl = el('chat-messages');
        const dropTargetNodes = [chatFormEl, chatMessagesEl].filter(Boolean);

        function onDragHighlight(e) {
            e.preventDefault();
            e.stopPropagation();
            if (chatFormEl) {
                chatFormEl.classList.add('ring-2', 'ring-blue-500', 'bg-blue-50/50');
            }
        }

        function onDragUnhighlight(e) {
            e.preventDefault();
            e.stopPropagation();
            if (chatFormEl && (!e.relatedTarget || !chatFormEl.contains(e.relatedTarget))) {
                chatFormEl.classList.remove('ring-2', 'ring-blue-500', 'bg-blue-50/50');
            }
        }

        function onFileDrop(e) {
            e.preventDefault();
            e.stopPropagation();
            if (chatFormEl) {
                chatFormEl.classList.remove('ring-2', 'ring-blue-500', 'bg-blue-50/50');
            }
            const dt = e.dataTransfer;
            if (dt && dt.files && dt.files.length > 0) {
                for (let i = 0; i < dt.files.length; i++) {
                    const f = dt.files[i];
                    if (f.type.startsWith('image/')) {
                        stageChatAttachment(f);
                        break;
                    }
                }
            }
        }

        // Prevent browser default window drag/drop behavior (which navigates away from page)
        window.addEventListener('dragover', (e) => e.preventDefault(), false);
        window.addEventListener('drop', (e) => e.preventDefault(), false);

        dropTargetNodes.forEach(node => {
            node.addEventListener('dragenter', onDragHighlight, false);
            node.addEventListener('dragover', (e) => { e.preventDefault(); e.stopPropagation(); }, false);
            node.addEventListener('dragleave', onDragUnhighlight, false);
            node.addEventListener('drop', onFileDrop, false);
        });

        loadAuthorizedPatients();
        renderQuickActions();
    }

    // Expose public functions to window for HTML onclick handlers
    window.togglePatientDropdown = togglePatientDropdown;
    window.openPatientDropdown = openPatientDropdown;
    window.closePatientDropdown = closePatientDropdown;
    window.toggleSpeechReadout = toggleSpeechReadout;
    window.speakText = speakText;
    window.appendMessage = appendMessage;
    window.loadAuthorizedPatients = loadAuthorizedPatients;
    window.renderPatientDropdown = renderPatientDropdown;
    window.renderQuickActions = renderQuickActions;
    window.setChatMode = setChatMode;
    window.sendGeneralQuickPrompt = sendGeneralQuickPrompt;
    window.selectPatient = selectPatient;
    window.selectPatientById = selectPatientById;
    window.sendMessage = sendMessage;
    window.stageChatAttachment = stageChatAttachment;
    window.removeChatAttachment = removeChatAttachment;
    window.triggerPatientImageUpload = triggerPatientImageUpload;
    window.handlePatientImageSelected = handlePatientImageSelected;
    window.openCustomTelemetryModal = openCustomTelemetryModal;
    window.closeCustomTelemetryModal = closeCustomTelemetryModal;
    window.resetCustomTelemetryForm = resetCustomTelemetryForm;
    window.loadTelemetryPreset = loadTelemetryPreset;
    window.submitCustomTelemetry = submitCustomTelemetry;
    window.syncLiveVitals = syncLiveVitals;
    window.sendQuickAction = sendQuickAction;
    window.confirmShowSummary = confirmShowSummary;
    window.loadConversationHistory = loadConversationHistory;
    window.initJeevanSetuRagChatbot = initJeevanSetuRagChatbot;

})(window);

