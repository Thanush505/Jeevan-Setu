/**
 * Telemetry_Simulator.js — Frontend Coordinator for the ICU Telemetry Simulator.
 * 
 * Manages:
 * - Real database patient loading & selection
 * - Single / Multi-Patient mode rendering
 * - Scenario configuration & manual parameter inputs
 * - Start / Stop / Send One lifecycle
 * - Real-time ICU monitor displays
 * - Database Write & Read-back verification
 * - EWS relationship integrity checks
 * - Performance metrics aggregation & JSON report export
 */

(function () {
  'use strict';

  // State
  let engine = null;
  let allPatients = [];
  let selectedPatientIds = new Set();
  let currentSinglePatientId = null;
  let selectionMode = 'single'; // 'single' or 'multi'
  let currentScenario = 'STABLE';

  // DOM Elements Cache
  const el = {};

  document.addEventListener('DOMContentLoaded', init);

  async function init() {
    cacheDomElements();
    setupEngine();
    setupEventListeners();
    await verifyAccess();
    await checkDatabaseHealth();
    await loadDatabasePatients();
  }

  function cacheDomElements() {
    el.userDisplayName = document.getElementById('user-display-name');
    el.userDisplayRole = document.getElementById('user-display-role');
    el.btnLogout = document.getElementById('btn-logout');

    el.dbStatusDot = document.getElementById('db-status-dot');
    el.dbStatusText = document.getElementById('db-status-text');
    el.btnRefreshDbHealth = document.getElementById('btn-refresh-db-health');

    el.selectInterval = document.getElementById('select-sampling-interval');
    el.globalStatusDot = document.getElementById('global-status-dot');
    el.globalStatusText = document.getElementById('global-status-text');
    el.activeSimCountBadge = document.getElementById('active-sim-count-badge');

    el.labelModeSingle = document.getElementById('label-mode-single');
    el.labelModeMulti = document.getElementById('label-mode-multi');
    el.btnSelectAll = document.getElementById('btn-select-all');
    el.btnClearAll = document.getElementById('btn-clear-all');
    el.patientSearchInput = document.getElementById('patient-search-input');
    el.patientListContainer = document.getElementById('patient-list-container');
    el.selectedPatientsCounter = document.getElementById('selected-patients-counter');

    el.scenarioSelectorGrid = document.getElementById('scenario-selector-grid');
    el.manualInputsPanel = document.getElementById('manual-inputs-panel');
    el.manualHr = document.getElementById('manual-hr');
    el.manualRr = document.getElementById('manual-rr');
    el.manualSbp = document.getElementById('manual-sbp');
    el.manualTemp = document.getElementById('manual-temp');

    el.btnStartSim = document.getElementById('btn-start-sim');
    el.btnStartText = document.getElementById('btn-start-text');
    el.btnStopSim = document.getElementById('btn-stop-sim');
    el.btnStopText = document.getElementById('btn-stop-text');
    el.btnSendOne = document.getElementById('btn-send-one');
    el.btnSendOneText = document.getElementById('btn-send-one-text');

    el.singleMonitorSection = document.getElementById('single-patient-monitor-section');
    el.multiMonitorSection = document.getElementById('multi-patient-monitor-section');
    el.singlePatientNameBadge = document.getElementById('single-patient-name-badge');
    el.singleLastTime = document.getElementById('single-last-time');
    el.singleResponseBadge = document.getElementById('single-response-badge');

    el.tileHrVal = document.getElementById('tile-hr-val');
    el.tileRrVal = document.getElementById('tile-rr-val');
    el.tileSbpVal = document.getElementById('tile-sbp-val');
    el.tileTempVal = document.getElementById('tile-temp-val');

    el.singleBackendEws = document.getElementById('single-backend-ews');
    el.singleBackendCondition = document.getElementById('single-backend-condition');
    el.singleBackendRecommendation = document.getElementById('single-backend-recommendation');
    el.btnSingleVerifyReadback = document.getElementById('btn-single-verify-readback');
    el.btnSingleVerifyEws = document.getElementById('btn-single-verify-ews');

    el.multiPatientTableBody = document.getElementById('multi-patient-table-body');
    el.btnVerifyAllReadback = document.getElementById('btn-verify-all-readback');
    el.btnVerifyAllEws = document.getElementById('btn-verify-all-ews');

    el.metricTotalSent = document.getElementById('metric-total-sent');
    el.metricSuccessful = document.getElementById('metric-successful');
    el.metricFailed = document.getElementById('metric-failed');
    el.metricSuccessRate = document.getElementById('metric-success-rate');
    el.metricLatencyAvg = document.getElementById('metric-latency-avg');
    el.metricLatencyRange = document.getElementById('metric-latency-range');
    el.metricRpm = document.getElementById('metric-rpm');
    el.metricInFlight = document.getElementById('metric-in-flight');

    el.vsumPatients = document.getElementById('vsum-patients');
    el.vsumReadback = document.getElementById('vsum-readback');
    el.vsumEwsMap = document.getElementById('vsum-ews-map');
    el.vsumDbPing = document.getElementById('vsum-db-ping');

    el.btnExportResults = document.getElementById('btn-export-results');
    el.presetSmall = document.getElementById('preset-small');
    el.presetNormal = document.getElementById('preset-normal');
    el.presetFull = document.getElementById('preset-full');
  }

  function setupEngine() {
    engine = new window.SimulatorEngine({
      deviceId: 'JS-ICU-SIM-001',
      samplingInterval: parseInt(el.selectInterval.value, 10),
      apiBase: '/api/v1/vitals',
      patientApi: '/api/v1/patients',
      onPatientUpdate: handlePatientUpdate,
      onMetricsUpdate: handleMetricsUpdate,
      onAlert: (msg) => alert(msg)
    });
  }

  function getAuthHeaders() {
    const token = localStorage.getItem('jeevan_setu_token') || sessionStorage.getItem('jeevan_setu_token') || localStorage.getItem('token') || '';
    const headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    return headers;
  }

  async function verifyAccess() {
    try {
      const res = await fetch('/api/v1/developer/telemetry-simulator/verify-access', {
        headers: getAuthHeaders(),
        credentials: 'same-origin'
      });
      if (res.ok) {
        const json = await res.json();
        if (json.success && json.data) {
          if (json.data.authenticated) {
            el.userDisplayName.textContent = json.data.full_name || json.data.username;
            el.userDisplayRole.textContent = `ROLE: ${(json.data.role || 'USER').toUpperCase()}`;
          } else {
            el.userDisplayName.textContent = 'Developer / Guest';
            el.userDisplayRole.textContent = 'MODE: PUBLIC TESTING';
          }
        }
      }
    } catch (e) {
      console.warn('Access verification check:', e);
    }
  }

  async function checkDatabaseHealth() {
    try {
      el.dbStatusDot.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping';
      el.dbStatusText.textContent = 'DB: Pinging...';

      const res = await fetch('/api/v1/developer/telemetry-simulator/health', {
        headers: getAuthHeaders(),
        credentials: 'same-origin'
      });

      if (res.ok) {
        const json = await res.json();
        if (json.success && json.data && json.data.query_success) {
          el.dbStatusDot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400';
          el.dbStatusText.textContent = `DB: Connected (${json.data.latency_ms} ms)`;
          el.vsumDbPing.textContent = `${json.data.latency_ms} ms`;
        } else {
          el.dbStatusDot.className = 'w-2.5 h-2.5 rounded-full bg-rose-500';
          el.dbStatusText.textContent = 'DB: Query Failed';
        }
      } else {
        el.dbStatusDot.className = 'w-2.5 h-2.5 rounded-full bg-rose-500';
        el.dbStatusText.textContent = 'DB: Disconnected';
      }
    } catch (e) {
      el.dbStatusDot.className = 'w-2.5 h-2.5 rounded-full bg-rose-500';
      el.dbStatusText.textContent = 'DB: Offline';
    }
  }

  async function loadDatabasePatients() {
    try {
      el.patientListContainer.innerHTML = `
        <div class="p-6 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
          <span class="material-symbols-outlined animate-spin text-[24px] text-cyan-400">autorenew</span>
          <span>Loading authorized patients from database...</span>
        </div>`;

      const res = await fetch('/api/v1/patients?status=admitted&limit=50', {
        headers: getAuthHeaders(),
        credentials: 'same-origin'
      });

      if (res.ok) {
        const json = await res.json();
        const list = json.data || json.patients || [];
        allPatients = Array.isArray(list) ? list : [];

        el.vsumPatients.textContent = `${allPatients.length} Admitted`;

        // Register each patient in the simulator engine
        allPatients.forEach(p => {
          engine.registerPatient(p, 'STABLE');
        });

        // Load authoritative persistent scenario states from MySQL
        await engine.loadAuthoritativeScenarios();

        renderPatientList(allPatients);

        // Auto-select first patient if available
        if (allPatients.length > 0) {
          selectPatient(allPatients[0].patient_id, false);
        }
      } else if (res.status === 401) {
        el.patientListContainer.innerHTML = `
          <div class="p-5 text-center text-amber-300/90 text-xs flex flex-col items-center gap-2">
            <span class="material-symbols-outlined text-amber-400 text-[24px]">lock</span>
            <span class="font-medium">Authentication Required for Clinical Patient Data</span>
            <span class="text-slate-400 text-[11px] max-w-[220px]">To query real admitted patient records from MySQL, log in with an authorized account (Doctor, Nurse, or Admin).</span>
            <a href="/login?next=/Developer/Telemetry_Simulator/" class="mt-2 px-3 py-1.5 bg-cyan-600/30 hover:bg-cyan-600/50 border border-cyan-500/40 rounded-lg text-cyan-300 font-semibold transition-all">Log In</a>
          </div>`;
      } else {
        el.patientListContainer.innerHTML = `
          <div class="p-4 text-center text-rose-400 text-xs">
            Failed to load patients (HTTP ${res.status}). Ensure you are logged in.
          </div>`;
      }
    } catch (e) {
      console.error('Failed to fetch patients:', e);
      el.patientListContainer.innerHTML = `
        <div class="p-4 text-center text-rose-400 text-xs">
          Network error loading patients. Check backend connection.
        </div>`;
    }
  }

  function renderPatientList(patients) {
    if (!patients || patients.length === 0) {
      el.patientListContainer.innerHTML = `
        <div class="p-4 text-center text-slate-400 text-xs">
          No admitted patients found.
        </div>`;
      return;
    }

    el.patientListContainer.innerHTML = '';
    patients.forEach(p => {
      const isSelected = selectedPatientIds.has(p.patient_id);
      const row = document.createElement('div');
      row.className = `p-2.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between text-xs select-none ${
        isSelected 
          ? 'bg-cyan-950/40 border-cyan-500/60 text-white shadow-sm' 
          : 'bg-slate-900/60 border-slate-800 text-slate-300 hover:border-slate-700'
      }`;
      row.dataset.patientId = p.patient_id;

      const pCode = p.patient_code || `P${String(p.patient_id).padStart(3, '0')}`;
      const bed = p.bed_number || 'ICU-Bed';
      const ward = p.ward_type || p.ward_name || 'ICU';

      row.innerHTML = `
        <div class="flex items-center gap-2.5">
          <input type="${selectionMode === 'single' ? 'radio' : 'checkbox'}" 
                 name="patientSelectGroup" 
                 value="${p.patient_id}" 
                 class="rounded border-slate-700 text-cyan-500 focus:ring-0 cursor-pointer"
                 ${isSelected ? 'checked' : ''}>
          <div>
            <div class="font-bold flex items-center gap-1.5">
              <span>${p.name}</span>
              <span class="text-[10px] text-slate-400 font-mono">(${pCode})</span>
            </div>
            <div class="text-[10px] text-slate-400 flex items-center gap-2 mt-0.5">
              <span>Bed: <strong class="text-slate-300">${bed}</strong></span>
              <span>•</span>
              <span>${ward}</span>
              <span>•</span>
              <span>${p.age || '--'} ${p.gender ? (p.gender === 'Female' ? 'F' : 'M') : ''}</span>
            </div>
          </div>
        </div>
        <div class="text-right">
          <span class="text-[10px] px-2 py-0.5 rounded font-mono font-bold ${
            (p.ews_score || 0) >= 7 ? 'bg-rose-950 text-rose-300 border border-rose-800/40' :
            (p.ews_score || 0) >= 5 ? 'bg-amber-950 text-amber-300 border border-amber-800/40' :
            'bg-emerald-950 text-emerald-300 border border-emerald-800/40'
          }">
            EWS: ${p.ews_score || 0}
          </span>
        </div>
      `;

      row.addEventListener('click', (e) => {
        // Prevent toggle if clicking directly on checkbox (handled naturally)
        if (e.target.tagName !== 'INPUT') {
          togglePatientSelection(p.patient_id);
        }
      });

      const input = row.querySelector('input');
      input.addEventListener('change', () => {
        togglePatientSelection(p.patient_id);
      });

      el.patientListContainer.appendChild(row);
    });

    updateSelectionCounters();
  }

  function togglePatientSelection(patientId) {
    patientId = parseInt(patientId, 10);
    if (selectionMode === 'single') {
      selectPatient(patientId, true);
    } else {
      if (selectedPatientIds.has(patientId)) {
        selectedPatientIds.delete(patientId);
        engine.stopPatient(patientId);
      } else {
        selectedPatientIds.add(patientId);
      }
      renderPatientList(allPatients);
      renderMultiPatientTable();
    }
  }

  function selectPatient(patientId, notifyIfRunning) {
    patientId = parseInt(patientId, 10);
    const p = allPatients.find(item => item.patient_id === patientId);
    if (!p) return;

    if (currentSinglePatientId && currentSinglePatientId !== patientId) {
      // Patient change guard
      const prev = engine.getPatient(currentSinglePatientId);
      if (prev && prev.isRunning) {
        engine.stopPatient(currentSinglePatientId);
        if (notifyIfRunning) {
          alert(`Simulation stopped because patient changed to ${p.name}.`);
        }
      }
    }

    currentSinglePatientId = patientId;
    selectedPatientIds.clear();
    selectedPatientIds.add(patientId);

    // Update single monitor display badge
    const pCode = p.patient_code || `P${String(p.patient_id).padStart(3, '0')}`;
    const bed = p.bed_number || 'ICU-Bed';
    el.singlePatientNameBadge.textContent = `${p.name} (${pCode} • ${bed})`;

    // Reset single tile display
    const pState = engine.getPatient(patientId);
    if (pState && pState.lastReading) {
      updateSingleTiles(pState.lastReading);
    } else {
      resetSingleTiles();
    }

    renderPatientList(allPatients);
    updateSelectionCounters();
    updateButtonStates();
  }

  function updateSelectionCounters() {
    const count = selectedPatientIds.size;
    el.selectedPatientsCounter.textContent = `${count} Patient${count === 1 ? '' : 's'} Selected`;
  }

  function resetSingleTiles() {
    el.tileHrVal.textContent = '--';
    el.tileRrVal.textContent = '--';
    el.tileSbpVal.textContent = '--';
    el.tileTempVal.textContent = '--';
    el.singleBackendEws.textContent = '--';
    el.singleBackendCondition.textContent = '--';
    el.singleBackendRecommendation.textContent = '--';
    el.singleLastTime.textContent = '--';
    el.singleResponseBadge.textContent = 'Ready';
    el.singleResponseBadge.className = 'px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300';
  }

  function updateSingleTiles(reading) {
    el.tileHrVal.textContent = reading.heart_rate !== undefined ? reading.heart_rate : '--';
    el.tileRrVal.textContent = reading.respiratory_rate !== undefined ? reading.respiratory_rate : '--';
    el.tileSbpVal.textContent = reading.systolic_bp !== undefined ? reading.systolic_bp : '--';
    el.tileTempVal.textContent = reading.temperature !== undefined ? reading.temperature : '--';
  }

  function handlePatientUpdate(patientId, pState) {
    // 1. Single mode updates
    if (selectionMode === 'single' && currentSinglePatientId === patientId) {
      if (pState.lastReading) {
        updateSingleTiles(pState.lastReading);
        el.singleLastTime.textContent = pState.lastSentTime || '--';
      }

      if (pState.lastResponse) {
        if (pState.lastResponse.success) {
          el.singleResponseBadge.textContent = '✓ Transmitted';
          el.singleResponseBadge.className = 'px-2 py-0.5 rounded bg-emerald-950 border border-emerald-500/40 text-emerald-300';
          el.singleBackendEws.textContent = pState.lastResponse.total_score !== undefined ? pState.lastResponse.total_score : '--';
          el.singleBackendCondition.textContent = pState.lastResponse.condition || '--';
          el.singleBackendRecommendation.textContent = pState.lastResponse.recommendation || '--';
        } else {
          el.singleResponseBadge.textContent = '✕ Error';
          el.singleResponseBadge.className = 'px-2 py-0.5 rounded bg-rose-950 border border-rose-500/40 text-rose-300';
        }
      }
    }

    // 2. Multi mode table row update
    if (selectionMode === 'multi') {
      updateMultiTableRow(pState);
    }

    updateButtonStates();
  }

  function handleMetricsUpdate(metrics) {
    el.metricTotalSent.textContent = metrics.totalReadingsSent;
    el.metricSuccessful.textContent = metrics.successfulRequests;
    el.metricFailed.textContent = metrics.failedRequests;
    el.metricSuccessRate.textContent = `${metrics.successRatePercent}%`;
    el.metricLatencyAvg.textContent = `${metrics.avgLatencyMs} ms`;
    el.metricLatencyRange.textContent = `${metrics.minLatencyMs} ms / ${metrics.maxLatencyMs} ms`;
    el.metricRpm.textContent = `${metrics.readingsPerMinute} RPM`;
    el.metricInFlight.textContent = metrics.requestsInProgress;

    el.activeSimCountBadge.textContent = `${metrics.activeRunningCount} Running`;

    if (metrics.activeRunningCount > 0) {
      el.globalStatusDot.className = 'w-3 h-3 rounded-full bg-emerald-500 pulse-active';
      el.globalStatusText.textContent = 'RUNNING';
      el.globalStatusText.className = 'font-bold text-sm text-emerald-400 uppercase tracking-wide';
    } else {
      el.globalStatusDot.className = 'w-3 h-3 rounded-full bg-slate-500';
      el.globalStatusText.textContent = 'STOPPED';
      el.globalStatusText.className = 'font-bold text-sm text-slate-300 uppercase tracking-wide';
    }
  }

  function renderMultiPatientTable() {
    el.multiPatientTableBody.innerHTML = '';
    if (selectedPatientIds.size === 0) {
      el.multiPatientTableBody.innerHTML = `
        <tr>
          <td colspan="12" class="p-6 text-center text-slate-500 text-xs">
            No patients selected. Select one or more patients from the left panel.
          </td>
        </tr>`;
      return;
    }

    selectedPatientIds.forEach(pid => {
      const pState = engine.getPatient(pid);
      if (!pState) return;
      const tr = createMultiTableRow(pState);
      el.multiPatientTableBody.appendChild(tr);
    });
  }

  function getScenarioBadgeClass(scenario) {
    const s = (scenario || 'STABLE').toUpperCase();
    switch (s) {
      case 'STABLE': return 'scenario-badge-stable';
      case 'MODERATE':
      case 'GRADUAL_DETERIORATION': return 'scenario-badge-moderate';
      case 'CRITICAL': return 'scenario-badge-critical';
      case 'RECOVERY': return 'scenario-badge-recovery';
      case 'MANUAL': return 'scenario-badge-manual';
      default: return 'scenario-badge-stable';
    }
  }

  function getScenarioIcon(scenario) {
    const s = (scenario || 'STABLE').toUpperCase();
    switch (s) {
      case 'STABLE': return '<span class="material-symbols-outlined text-[13px]">favorite</span>';
      case 'MODERATE':
      case 'GRADUAL_DETERIORATION': return '<span class="material-symbols-outlined text-[13px]">trending_down</span>';
      case 'CRITICAL': return '<span class="material-symbols-outlined text-[13px]">crisis_alert</span>';
      case 'RECOVERY': return '<span class="material-symbols-outlined text-[13px]">healing</span>';
      case 'MANUAL': return '<span class="material-symbols-outlined text-[13px]">edit_note</span>';
      default: return '<span class="material-symbols-outlined text-[13px]">favorite</span>';
    }
  }

  function renderTransitionOptions(currentScenario) {
    const current = (currentScenario || 'STABLE').toUpperCase();
    const all = [
      { id: 'STABLE', label: 'Stable (Healthy Baseline)' },
      { id: 'MODERATE', label: 'Moderate (Deterioration)' },
      { id: 'CRITICAL', label: 'Critical (Acute Severe)' },
      { id: 'RECOVERY', label: 'Recovery (Stabilizing)' },
      { id: 'MANUAL', label: 'Manual Parameters' }
    ];

    const targets = all.filter(item => item.id !== current && (current !== 'GRADUAL_DETERIORATION' || item.id !== 'MODERATE'));
    return targets.map(item => `<option value="${item.id}">→ ${item.label}</option>`).join('');
  }

  function getNextWorsenScenario(currentScenario) {
    const s = (currentScenario || 'STABLE').toUpperCase();
    if (s === 'STABLE') return 'MODERATE';
    if (s === 'MODERATE' || s === 'GRADUAL_DETERIORATION') return 'CRITICAL';
    if (s === 'RECOVERY') return 'MODERATE';
    if (s === 'MANUAL') return 'MODERATE';
    return null; // Already at highest deterioration
  }

  function getNextImproveScenario(currentScenario) {
    const s = (currentScenario || 'STABLE').toUpperCase();
    if (s === 'CRITICAL') return 'MODERATE';
    if (s === 'MODERATE' || s === 'GRADUAL_DETERIORATION') return 'STABLE';
    if (s === 'RECOVERY') return 'STABLE';
    if (s === 'MANUAL') return 'STABLE';
    return null; // Already at stable baseline
  }

  async function performScenarioTransition(patientId, targetScenario, reason) {
    const pState = engine.getPatient(patientId);
    if (!pState) return;

    const tr = document.getElementById(`multi-row-${patientId}`);
    const statusEl = tr ? tr.querySelector('.cell-trans-status') : null;
    const worsenBtn = tr ? tr.querySelector('.btn-stepper-worsen') : null;
    const improveBtn = tr ? tr.querySelector('.btn-stepper-improve') : null;
    const targetSelect = tr ? tr.querySelector('.transition-target-select') : null;
    const applyBtn = tr ? tr.querySelector('.btn-apply-transition') : null;

    if (statusEl) {
      statusEl.innerHTML = `<span class="text-amber-400 flex items-center gap-1"><span class="material-symbols-outlined text-[13px] animate-spin">sync</span> Transitioning to ${targetScenario}...</span>`;
    }
    if (worsenBtn) worsenBtn.disabled = true;
    if (improveBtn) improveBtn.disabled = true;
    if (targetSelect) targetSelect.disabled = true;
    if (applyBtn) applyBtn.disabled = true;

    try {
      const res = await engine.transitionPatientScenario(patientId, targetScenario, reason);
      const newScenario = res.data.current_scenario || targetScenario;

      if (statusEl) {
        statusEl.innerHTML = `<span class="text-emerald-400 font-semibold flex items-center gap-1"><span class="material-symbols-outlined text-[13px]">check_circle</span> Transitioned to ${newScenario}</span>`;
      }

      // If viewing this patient in single monitor mode, keep card selection aligned
      if (currentSinglePatientId === patientId) {
        currentScenario = newScenario;
        document.querySelectorAll('.scenario-card').forEach(c => {
          c.classList.toggle('border-cyan-500', c.dataset.scenario === newScenario);
          c.classList.toggle('bg-cyan-950/40', c.dataset.scenario === newScenario);
        });
      }
    } catch (err) {
      if (statusEl) {
        statusEl.innerHTML = `<span class="text-rose-400 font-semibold flex items-center gap-1"><span class="material-symbols-outlined text-[13px]">error</span> ${err.message}</span>`;
      }
    } finally {
      updateMultiTableRow(pState);
    }
  }

  function createMultiTableRow(pState) {
    const tr = document.createElement('tr');
    tr.id = `multi-row-${pState.patientId}`;
    tr.className = `transition-colors hover:bg-slate-900/50 ${pState.isRunning ? 'table-row-running' : ''}`;

    const p = pState.patient;
    const pCode = p.patient_code || `P${String(p.patientId).padStart(3, '0')}`;
    const bed = p.bed_number || 'ICU-Bed';
    const normScen = (pState.scenario === 'GRADUAL_DETERIORATION' ? 'MODERATE' : pState.scenario) || 'STABLE';

    const canWorsen = getNextWorsenScenario(normScen) !== null && !pState.isTransitioning;
    const canImprove = getNextImproveScenario(normScen) !== null && !pState.isTransitioning;

    tr.innerHTML = `
      <td class="p-3 font-bold text-white">${p.name}</td>
      <td class="p-3 text-[11px] font-mono text-slate-400">${pCode} • ${bed}</td>
      <td class="p-3">
        <div class="scenario-transition-box" id="trans-box-${pState.patientId}">
          <!-- Current Scenario & Quick Stepper Controls -->
          <div class="flex items-center justify-between gap-1.5 flex-wrap">
            <div class="flex items-center gap-1">
              <span class="text-[10px] text-slate-400 font-semibold uppercase">Current:</span>
              <span class="scenario-badge ${getScenarioBadgeClass(normScen)} cell-current-scenario">
                ${getScenarioIcon(normScen)}
                <span>${normScen}</span>
              </span>
            </div>
            <div class="flex items-center gap-1">
              <button class="btn-stepper btn-stepper-worsen" data-patient-id="${pState.patientId}" title="Deteriorate (Stable → Moderate → Critical)" ${!canWorsen ? 'disabled' : ''}>
                <span class="material-symbols-outlined text-[13px]">trending_up</span>
                <span>⚡ Worsen</span>
              </button>
              <button class="btn-stepper btn-stepper-improve" data-patient-id="${pState.patientId}" title="Improve (Critical → Moderate → Stable)" ${!canImprove ? 'disabled' : ''}>
                <span class="material-symbols-outlined text-[13px]">trending_down</span>
                <span>🌱 Improve</span>
              </button>
            </div>
          </div>

          <!-- Destination Target Dropdown & Apply Action -->
          <div class="flex items-center gap-1.5 mt-1">
            <span class="text-[10px] text-slate-400 font-semibold uppercase">To:</span>
            <select class="transition-target-select flex-1 bg-slate-900 text-slate-200 text-[11px] rounded border border-slate-700 px-1.5 py-0.5 focus:border-cyan-500 focus:outline-none" data-patient-id="${pState.patientId}" ${pState.isTransitioning ? 'disabled' : ''}>
              ${renderTransitionOptions(normScen)}
            </select>
            <button class="btn-apply-transition px-2 py-0.5 rounded text-[11px] font-bold bg-cyan-900 hover:bg-cyan-800 text-cyan-200 border border-cyan-700/60 transition-colors" data-patient-id="${pState.patientId}" ${pState.isTransitioning ? 'disabled' : ''}>
              Apply
            </button>
          </div>

          <!-- Transition Status Feedback -->
          <div class="cell-trans-status text-[10px] text-slate-400 font-medium flex items-center gap-1 mt-0.5">
            ${pState.isTransitioning 
              ? '<span class="text-amber-400 flex items-center gap-1"><span class="material-symbols-outlined text-[13px] animate-spin">sync</span> Transitioning...</span>' 
              : (pState.lastTransition ? `<span class="text-emerald-400 font-medium">✓ Authoritative: ${normScen}</span>` : '<span class="text-slate-500">Ready</span>')}
          </div>
        </div>
      </td>
      <td class="p-3 font-mono font-bold text-emerald-400 text-sm cell-hr">${pState.lastReading ? pState.lastReading.heart_rate : '--'}</td>
      <td class="p-3 font-mono font-bold text-cyan-400 text-sm cell-rr">${pState.lastReading ? pState.lastReading.respiratory_rate : '--'}</td>
      <td class="p-3 font-mono font-bold text-amber-400 text-sm cell-sbp">${pState.lastReading ? pState.lastReading.systolic_bp : '--'}</td>
      <td class="p-3 font-mono font-bold text-pink-400 text-sm cell-temp">${pState.lastReading ? pState.lastReading.temperature : '--'}</td>
      <td class="p-3">
        <span class="cell-status text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
          pState.isRunning 
            ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40' 
            : 'bg-slate-900 text-slate-400 border border-slate-700'
        }">
          ${pState.isRunning ? 'Running' : 'Stopped'}
        </span>
      </td>
      <td class="p-3 font-mono font-bold cell-ews text-slate-300">
        ${pState.lastResponse && pState.lastResponse.total_score !== undefined ? pState.lastResponse.total_score : '--'}
      </td>
      <td class="p-3 text-[11px] cell-rec text-slate-300 truncate max-w-[140px]">
        ${pState.lastResponse && pState.lastResponse.recommendation ? pState.lastResponse.recommendation : '--'}
      </td>
      <td class="p-3 font-mono text-[10px] cell-readback text-slate-400">
        ${pState.readBackVerification ? pState.readBackVerification.result : '--'}
      </td>
      <td class="p-3 text-right space-x-1">
        <button class="btn-row-toggle px-2 py-1 rounded text-[11px] font-bold ${
          pState.isRunning ? 'bg-rose-950 text-rose-300 hover:bg-rose-900 border border-rose-800/40' : 'bg-emerald-950 text-emerald-300 hover:bg-emerald-900 border border-emerald-800/40'
        }" data-patient-id="${pState.patientId}">
          ${pState.isRunning ? 'Stop' : 'Start'}
        </button>
        <button class="btn-row-sendone px-2 py-1 rounded text-[11px] bg-slate-800 text-cyan-300 hover:bg-slate-700 border border-slate-700" data-patient-id="${pState.patientId}" title="Send One Reading">
          Send
        </button>
      </td>
    `;

    // Row Event Listeners
    const worsenBtn = tr.querySelector('.btn-stepper-worsen');
    worsenBtn.addEventListener('click', () => {
      const cur = pState.scenario === 'GRADUAL_DETERIORATION' ? 'MODERATE' : pState.scenario;
      const next = getNextWorsenScenario(cur);
      if (next) performScenarioTransition(pState.patientId, next, `Deterioration step: ${cur} → ${next}`);
    });

    const improveBtn = tr.querySelector('.btn-stepper-improve');
    improveBtn.addEventListener('click', () => {
      const cur = pState.scenario === 'GRADUAL_DETERIORATION' ? 'MODERATE' : pState.scenario;
      const next = getNextImproveScenario(cur);
      if (next) performScenarioTransition(pState.patientId, next, `Improvement step: ${cur} → ${next}`);
    });

    const targetSelect = tr.querySelector('.transition-target-select');
    const applyBtn = tr.querySelector('.btn-apply-transition');
    applyBtn.addEventListener('click', () => {
      const target = targetSelect.value;
      if (target) {
        const cur = pState.scenario === 'GRADUAL_DETERIORATION' ? 'MODERATE' : pState.scenario;
        performScenarioTransition(pState.patientId, target, `Manual transition: ${cur} → ${target}`);
      }
    });

    const toggleBtn = tr.querySelector('.btn-row-toggle');
    toggleBtn.addEventListener('click', () => {
      if (pState.isRunning) {
        engine.stopPatient(pState.patientId);
      } else {
        engine.startPatient(pState.patientId);
      }
    });

    const sendOneBtn = tr.querySelector('.btn-row-sendone');
    sendOneBtn.addEventListener('click', () => {
      engine.sendSingleReading(pState.patientId);
    });

    return tr;
  }

  function updateMultiTableRow(pState) {
    const tr = document.getElementById(`multi-row-${pState.patientId}`);
    if (!tr) return;

    if (pState.isRunning) {
      tr.classList.add('table-row-running');
    } else {
      tr.classList.remove('table-row-running');
    }

    const normScen = (pState.scenario === 'GRADUAL_DETERIORATION' ? 'MODERATE' : pState.scenario) || 'STABLE';

    // Update Scenario Transition Controller elements
    const badge = tr.querySelector('.cell-current-scenario');
    if (badge) {
      badge.className = `scenario-badge ${getScenarioBadgeClass(normScen)} cell-current-scenario`;
      badge.innerHTML = `${getScenarioIcon(normScen)}<span>${normScen}</span>`;
    }

    const worsenBtn = tr.querySelector('.btn-stepper-worsen');
    if (worsenBtn) {
      const canWorsen = getNextWorsenScenario(normScen) !== null && !pState.isTransitioning;
      worsenBtn.disabled = !canWorsen;
    }

    const improveBtn = tr.querySelector('.btn-stepper-improve');
    if (improveBtn) {
      const canImprove = getNextImproveScenario(normScen) !== null && !pState.isTransitioning;
      improveBtn.disabled = !canImprove;
    }

    const targetSelect = tr.querySelector('.transition-target-select');
    if (targetSelect && !pState.isTransitioning) {
      targetSelect.disabled = false;
      // Refresh options if selected value matches current scenario
      if (targetSelect.value === normScen || !targetSelect.querySelector(`option[value="${targetSelect.value}"]`)) {
        targetSelect.innerHTML = renderTransitionOptions(normScen);
      }
    } else if (targetSelect) {
      targetSelect.disabled = true;
    }

    const applyBtn = tr.querySelector('.btn-apply-transition');
    if (applyBtn) {
      applyBtn.disabled = !!pState.isTransitioning;
    }

    const statusEl = tr.querySelector('.cell-trans-status');
    if (statusEl && pState.isTransitioning) {
      statusEl.innerHTML = `<span class="text-amber-400 flex items-center gap-1"><span class="material-symbols-outlined text-[13px] animate-spin">sync</span> Transitioning...</span>`;
    }

    if (pState.lastReading) {
      tr.querySelector('.cell-hr').textContent = pState.lastReading.heart_rate;
      tr.querySelector('.cell-rr').textContent = pState.lastReading.respiratory_rate;
      tr.querySelector('.cell-sbp').textContent = pState.lastReading.systolic_bp;
      tr.querySelector('.cell-temp').textContent = pState.lastReading.temperature;
    }

    const statusBadge = tr.querySelector('.cell-status');
    statusBadge.textContent = pState.isRunning ? 'Running' : 'Stopped';
    statusBadge.className = `cell-status text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
      pState.isRunning 
        ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40' 
        : 'bg-slate-900 text-slate-400 border border-slate-700'
    }`;

    if (pState.lastResponse) {
      tr.querySelector('.cell-ews').textContent = pState.lastResponse.total_score !== undefined ? pState.lastResponse.total_score : '--';
      tr.querySelector('.cell-rec').textContent = pState.lastResponse.recommendation || '--';
    }

    if (pState.readBackVerification) {
      const rb = tr.querySelector('.cell-readback');
      rb.textContent = pState.readBackVerification.result;
      rb.className = `font-mono text-[10px] cell-readback font-bold ${
        pState.readBackVerification.result === 'PASS' ? 'text-emerald-400' : 'text-rose-400'
      }`;
    }

    const toggleBtn = tr.querySelector('.btn-row-toggle');
    toggleBtn.textContent = pState.isRunning ? 'Stop' : 'Start';
    toggleBtn.className = `btn-row-toggle px-2 py-1 rounded text-[11px] font-bold ${
      pState.isRunning 
        ? 'bg-rose-950 text-rose-300 hover:bg-rose-900 border border-rose-800/40' 
        : 'bg-emerald-950 text-emerald-300 hover:bg-emerald-900 border border-emerald-800/40'
    }`;
  }

  function updateButtonStates() {
    const isAny = engine.isAnyRunning();
    el.btnStopSim.disabled = !isAny;

    if (selectionMode === 'single') {
      const p = engine.getPatient(currentSinglePatientId);
      const isSingleRunning = p ? p.isRunning : false;
      el.btnStartSim.disabled = isSingleRunning;
      if (isSingleRunning) {
        el.btnStartSim.classList.add('opacity-50', 'cursor-not-allowed');
      } else {
        el.btnStartSim.classList.remove('opacity-50', 'cursor-not-allowed');
      }
    } else {
      const allSelectedRunning = Array.from(selectedPatientIds).every(pid => {
        const p = engine.getPatient(pid);
        return p && p.isRunning;
      });
      el.btnStartSim.disabled = allSelectedRunning && selectedPatientIds.size > 0;
      if (el.btnStartSim.disabled) {
        el.btnStartSim.classList.add('opacity-50', 'cursor-not-allowed');
      } else {
        el.btnStartSim.classList.remove('opacity-50', 'cursor-not-allowed');
      }
    }
  }

  function setupEventListeners() {
    // Mode toggles
    document.querySelectorAll('input[name="selectionMode"]').forEach(radio => {
      radio.addEventListener('change', (e) => {
        selectionMode = e.target.value;
        if (selectionMode === 'single') {
          el.singleMonitorSection.classList.remove('hidden');
          el.multiMonitorSection.classList.add('hidden');
          el.btnStartText.textContent = 'Start Simulation';
          el.btnSendOneText.textContent = 'Send One Reading';
          if (selectedPatientIds.size > 0) {
            const first = Array.from(selectedPatientIds)[0];
            selectPatient(first, false);
          }
        } else {
          el.singleMonitorSection.classList.add('hidden');
          el.multiMonitorSection.classList.remove('hidden');
          el.btnStartText.textContent = 'Start Selected Patients';
          el.btnSendOneText.textContent = 'Send One to Selected';
          renderMultiPatientTable();
        }
        renderPatientList(allPatients);
        updateButtonStates();
      });
    });

    // Select All
    el.btnSelectAll.addEventListener('click', () => {
      allPatients.forEach(p => selectedPatientIds.add(p.patient_id));
      if (selectionMode === 'single') {
        // In single mode, selecting all prompts user to switch to multi mode
        selectionMode = 'multi';
        document.querySelector('input[name="selectionMode"][value="multi"]').checked = true;
        el.singleMonitorSection.classList.add('hidden');
        el.multiMonitorSection.classList.remove('hidden');
        el.btnStartText.textContent = 'Start Selected Patients';
        el.btnSendOneText.textContent = 'Send One to Selected';
      }
      renderPatientList(allPatients);
      renderMultiPatientTable();
      updateButtonStates();
    });

    // Clear All
    el.btnClearAll.addEventListener('click', () => {
      engine.stopAll();
      selectedPatientIds.clear();
      currentSinglePatientId = null;
      resetSingleTiles();
      renderPatientList(allPatients);
      renderMultiPatientTable();
      updateButtonStates();
    });

    // Search filter
    el.patientSearchInput.addEventListener('input', (e) => {
      const query = (e.target.value || '').toLowerCase().trim();
      if (!query) {
        renderPatientList(allPatients);
        return;
      }
      const filtered = allPatients.filter(p => {
        const name = (p.name || '').toLowerCase();
        const code = (p.patient_code || '').toLowerCase();
        const bed = (p.bed_number || '').toLowerCase();
        return name.includes(query) || code.includes(query) || bed.includes(query);
      });
      renderPatientList(filtered);
    });

    // Sampling Interval change
    el.selectInterval.addEventListener('change', (e) => {
      const val = parseInt(e.target.value, 10);
      if (val === 1000) {
        const ok = confirm('High request rate (1 second) selected. This will increase backend and database load. Proceed?');
        if (!ok) {
          el.selectInterval.value = '5000';
          engine.setInterval(5000);
          return;
        }
      }
      engine.setInterval(val);
    });

    // Scenario Selection
    document.querySelectorAll('.scenario-card').forEach(card => {
      card.addEventListener('click', () => {
        const scenario = card.dataset.scenario;
        currentScenario = scenario;

        // Visual selection update
        document.querySelectorAll('.scenario-card').forEach(c => {
          c.classList.remove('border-cyan-500', 'bg-cyan-950/40');
        });
        card.classList.add('border-cyan-500', 'bg-cyan-950/40');

        if (scenario === 'MANUAL') {
          el.manualInputsPanel.classList.remove('hidden');
        } else {
          el.manualInputsPanel.classList.add('hidden');
        }

        // Apply scenario transition to selected patient(s)
        selectedPatientIds.forEach(pid => {
          if (scenario === 'MANUAL') {
            const manualValues = {
              heart_rate: el.manualHr.value,
              respiratory_rate: el.manualRr.value,
              systolic_bp: el.manualSbp.value,
              temperature: el.manualTemp.value
            };
            engine.setPatientScenario(pid, scenario, manualValues);
          } else {
            performScenarioTransition(pid, scenario, `Card selection: ${scenario}`);
          }
        });

        if (selectionMode === 'multi') {
          renderMultiPatientTable();
        }
      });
    });

    // Start Simulation Button
    el.btnStartSim.addEventListener('click', () => {
      if (selectedPatientIds.size === 0) {
        alert('Please select at least one patient to start simulation.');
        return;
      }
      if (selectionMode === 'single') {
        engine.startPatient(currentSinglePatientId);
      } else {
        engine.startSelected(Array.from(selectedPatientIds));
      }
      updateButtonStates();
    });

    // Stop Simulation Button
    el.btnStopSim.addEventListener('click', () => {
      if (selectionMode === 'single') {
        engine.stopPatient(currentSinglePatientId);
      } else {
        engine.stopAll();
      }
      updateButtonStates();
    });

    // Send One Reading Button
    el.btnSendOne.addEventListener('click', async () => {
      if (selectedPatientIds.size === 0) {
        alert('Please select a patient first.');
        return;
      }

      let manualData = null;
      if (currentScenario === 'MANUAL') {
        // Validate manual parameters
        const hr = parseFloat(el.manualHr.value);
        const rr = parseFloat(el.manualRr.value);
        const sbp = parseFloat(el.manualSbp.value);
        const temp = parseFloat(el.manualTemp.value);

        if (isNaN(hr) || hr < 20 || hr > 300) { alert('Heart Rate must be between 20 and 300 bpm.'); return; }
        if (isNaN(rr) || rr < 4 || rr > 80) { alert('Respiratory Rate must be between 4 and 80 /min.'); return; }
        if (isNaN(sbp) || sbp < 40 || sbp > 300) { alert('Systolic BP must be between 40 and 300 mmHg.'); return; }
        if (isNaN(temp) || temp < 25.0 || temp > 45.0) { alert('Temperature must be between 25.0 and 45.0 °C.'); return; }

        manualData = { heart_rate: hr, respiratory_rate: rr, systolic_bp: sbp, temperature: temp };
      }

      if (selectionMode === 'single') {
        el.btnSendOne.disabled = true;
        try {
          await engine.sendSingleReading(currentSinglePatientId, manualData);
        } finally {
          el.btnSendOne.disabled = false;
        }
      } else {
        el.btnSendOne.disabled = true;
        try {
          await engine.sendSingleReadingToSelected(Array.from(selectedPatientIds));
        } finally {
          el.btnSendOne.disabled = false;
        }
      }
    });

    // Single Verification Buttons
    el.btnSingleVerifyReadback.addEventListener('click', async () => {
      if (!currentSinglePatientId) return;
      try {
        const res = await engine.verifyReadBack(currentSinglePatientId);
        alert(`Read-Back Verification for Patient #${currentSinglePatientId}:\n\nResult: ${res.result}\nSent HR: ${res.sent.hr} | DB HR: ${res.db.hr}\nSent RR: ${res.sent.rr} | DB RR: ${res.db.rr}\nSent SBP: ${res.sent.sbp} | DB SBP: ${res.db.sbp}\nSent Temp: ${res.sent.temp} | DB Temp: ${res.db.temp}\nDB Recorded At: ${res.db.recorded_at}`);
      } catch (err) {
        alert(`Read-Back Verification Error: ${err.message}`);
      }
    });

    el.btnSingleVerifyEws.addEventListener('click', async () => {
      if (!currentSinglePatientId) return;
      try {
        const res = await engine.verifyEwsRelationship(currentSinglePatientId);
        alert(`EWS Relationship Verification for Patient #${currentSinglePatientId}:\n\nStatus: ${res.status}\nVital ID: ${res.vitalId}\nEWS Vital ID: ${res.ewsVitalId}\nVital-to-EWS Match: ${res.vitalIdMatch ? 'PASS' : 'FAIL'}\nTotal Score: ${res.totalScore} (${res.riskLevel})\nRecorded At: ${res.recordedAt}`);
      } catch (err) {
        alert(`EWS Verification Error: ${err.message}`);
      }
    });

    // Multi-Patient Verification Buttons
    el.btnVerifyAllReadback.addEventListener('click', async () => {
      if (selectedPatientIds.size === 0) return;
      let passed = 0;
      let mismatches = 0;
      for (const pid of selectedPatientIds) {
        try {
          const res = await engine.verifyReadBack(pid);
          if (res.result === 'PASS') passed++; else mismatches++;
        } catch (_) {
          mismatches++;
        }
      }
      el.vsumReadback.textContent = `${passed}/${selectedPatientIds.size} Matched`;
      alert(`Multi-Patient Database Read-Back Verification Completed:\n\nTotal Checked: ${selectedPatientIds.size}\nVerified Matches: ${passed}\nMismatches: ${mismatches}`);
    });

    el.btnVerifyAllEws.addEventListener('click', async () => {
      if (selectedPatientIds.size === 0) return;
      let passed = 0;
      let errors = 0;
      for (const pid of selectedPatientIds) {
        try {
          const res = await engine.verifyEwsRelationship(pid);
          if (res.status === 'VERIFIED') passed++; else errors++;
        } catch (_) {
          errors++;
        }
      }
      el.vsumEwsMap.textContent = `${passed}/${selectedPatientIds.size} Correct`;
      alert(`Multi-Patient EWS Relationship Verification Completed:\n\nTotal Checked: ${selectedPatientIds.size}\nAuthoritative EWS Matches: ${passed}\nRelationship Errors: ${errors}`);
    });

    // DB Ping Button
    el.btnRefreshDbHealth.addEventListener('click', checkDatabaseHealth);

    // Load Testing Presets
    el.presetSmall.addEventListener('click', () => {
      selectedPatientIds.clear();
      allPatients.slice(0, 2).forEach(p => selectedPatientIds.add(p.patient_id));
      setMultiModeAndRender();
    });

    el.presetNormal.addEventListener('click', () => {
      selectedPatientIds.clear();
      allPatients.slice(0, 5).forEach(p => selectedPatientIds.add(p.patient_id));
      setMultiModeAndRender();
    });

    el.presetFull.addEventListener('click', () => {
      selectedPatientIds.clear();
      allPatients.forEach(p => selectedPatientIds.add(p.patient_id));
      setMultiModeAndRender();
    });

    function setMultiModeAndRender() {
      selectionMode = 'multi';
      document.querySelector('input[name="selectionMode"][value="multi"]').checked = true;
      el.singleMonitorSection.classList.add('hidden');
      el.multiMonitorSection.classList.remove('hidden');
      el.btnStartText.textContent = 'Start Selected Patients';
      el.btnSendOneText.textContent = 'Send One to Selected';
      renderPatientList(allPatients);
      renderMultiPatientTable();
      updateButtonStates();
    }

    // Export Test Results (JSON)
    el.btnExportResults.addEventListener('click', () => {
      const metrics = engine.getGlobalMetrics();
      const patientData = [];
      engine.patients.forEach(p => {
        patientData.push({
          patient_id: p.patientId,
          name: p.patient.name,
          uhid: p.patient.patient_code,
          bed_number: p.patient.bed_number,
          scenario: p.scenario,
          status: p.isRunning ? 'Running' : 'Stopped',
          total_sent: p.metrics.sent,
          successful: p.metrics.success,
          failed: p.metrics.failed,
          avg_latency_ms: p.metrics.avgLatency,
          last_reading: p.lastReading,
          last_response: p.lastResponse,
          read_back_verification: p.readBackVerification,
          ews_verification: p.ewsVerification
        });
      });

      const report = {
        test_session_id: 'TEST-' + Date.now(),
        exported_at: new Date().toISOString(),
        device_id: engine.deviceId,
        sampling_interval_seconds: metrics.samplingIntervalSeconds,
        aggregated_metrics: metrics,
        simulated_patients: patientData
      };

      const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(report, null, 2));
      const downloadAnchor = document.createElement('a');
      downloadAnchor.setAttribute('href', dataStr);
      downloadAnchor.setAttribute('download', `jeevan_setu_telemetry_test_${Date.now()}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    });

    // Logout
    el.btnLogout.addEventListener('click', async () => {
      engine.stopAll();
      try {
        await fetch('/api/v1/auth/logout', {
          method: 'POST',
          headers: getAuthHeaders(),
          credentials: 'same-origin'
        });
      } catch (_) {}
      localStorage.removeItem('jeevan_setu_token');
      localStorage.removeItem('token');
      sessionStorage.clear();
      window.location.href = '/login';
    });

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
      if (engine) engine.stopAll();
    });
  }

})();
