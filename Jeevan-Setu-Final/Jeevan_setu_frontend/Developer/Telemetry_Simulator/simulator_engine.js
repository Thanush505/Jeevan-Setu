/**
 * simulator_engine.js — Concurrency-Safe ICU Multi-Patient Simulation Engine.
 * 
 * Manages:
 * - Independent simulation loops per patient (strict patient data isolation)
 * - Safe async scheduling (NO overlapping in-flight requests, NO memory leaks)
 * - Real-time latency tracking (min, max, avg response times)
 * - Resilient error backoff & auto-pause on repeated connection drops
 * - Native integration with the existing Jeevan Setu vital submission API
 * - NEVER calculates EWS or risk locally. Relies strictly on backend response.
 */

(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define(['ScenarioManager'], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./scenarios'));
  } else {
    root.SimulatorEngine = factory(root.ScenarioManager);
  }
})(typeof self !== 'undefined' ? self : this, function (ScenarioManager) {
  'use strict';

  class SimulatorEngine {
    constructor(options) {
      options = options || {};
      this.deviceId = options.deviceId || 'JS-ICU-SIM-001';
      this.samplingInterval = options.samplingInterval || 5000; // ms
      this.apiBase = options.apiBase || '/api/v1/vitals';
      this.patientApi = options.patientApi || '/api/v1/patients';

      // Map: patientId (number) -> PatientSimulationState
      this.patients = new Map();

      // Global aggregated metrics
      this.globalMetrics = {
        totalReadingsSent: 0,
        successfulRequests: 0,
        failedRequests: 0,
        requestsInProgress: 0,
        startTime: null,
        latencies: [],
        avgLatencyMs: 0,
        minLatencyMs: null,
        maxLatencyMs: null,
        lastSuccessfulTime: null,
        lastFailedTime: null,
        readingsPerMinute: 0
      };

      // Callbacks
      this.onPatientUpdate = options.onPatientUpdate || null;
      this.onMetricsUpdate = options.onMetricsUpdate || null;
      this.onAlert = options.onAlert || null;

      // Rate calculation interval
      this._rpmTimer = null;
      this._startRpmTracker();
    }

    _startRpmTracker() {
      if (this._rpmTimer) clearInterval(this._rpmTimer);
      let lastSentCount = 0;
      this._rpmTimer = setInterval(() => {
        const delta = this.globalMetrics.totalReadingsSent - lastSentCount;
        lastSentCount = this.globalMetrics.totalReadingsSent;
        // Every 5 seconds, extrapolate to readings per minute: delta * (60 / 5)
        this.globalMetrics.readingsPerMinute = delta * 12;
        if (this.onMetricsUpdate) this.onMetricsUpdate(this.getGlobalMetrics());
      }, 5000);
    }

    getAuthHeaders() {
      const token = localStorage.getItem('jeevan_setu_token') || sessionStorage.getItem('jeevan_setu_token') || localStorage.getItem('token') || '';
      const headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      };
      if (token) {
        headers['Authorization'] = 'Bearer ' + token;
      }
      return headers;
    }

    registerPatient(patientData, defaultScenario) {
      const pid = parseInt(patientData.patient_id, 10);
      if (isNaN(pid)) return null;

      if (!this.patients.has(pid)) {
        const state = {
          patientId: pid,
          patient: patientData,
          scenario: defaultScenario || 'STABLE',
          scenarioEngine: ScenarioManager.createPatientState(defaultScenario || 'STABLE'),
          isRunning: false,
          isRequestInFlight: false,
          timerId: null,
          lastReading: null,
          lastSentTime: null,
          lastResponse: null,
          readBackVerification: null,
          ewsVerification: null,
          metrics: {
            sent: 0,
            success: 0,
            failed: 0,
            latencies: [],
            avgLatency: 0,
            minLatency: null,
            maxLatency: null,
            lastError: null
          },
          errorStreak: 0
        };
        this.patients.set(pid, state);
      } else {
        // Update patient metadata
        const existing = this.patients.get(pid);
        existing.patient = Object.assign(existing.patient, patientData);
      }
      return this.patients.get(pid);
    }

    getPatient(patientId) {
      return this.patients.get(parseInt(patientId, 10));
    }

    setPatientScenario(patientId, scenarioName, manualValues) {
      const p = this.getPatient(patientId);
      if (!p) return;
      p.scenario = scenarioName.toUpperCase();
      if (p.scenario === 'MANUAL' && manualValues) {
        p.scenarioEngine.setManualValues(manualValues);
      } else {
        p.scenarioEngine.setScenario(p.scenario);
      }
      if (this.onPatientUpdate) this.onPatientUpdate(p.patientId, p);
    }

    setInterval(ms) {
      this.samplingInterval = Math.max(1000, parseInt(ms, 10) || 5000);
    }

    startPatient(patientId) {
      const p = this.getPatient(patientId);
      if (!p) return false;
      if (p.isRunning) return true; // Prevent duplicate loops

      p.isRunning = true;
      p.errorStreak = 0;

      if (!this.globalMetrics.startTime) {
        this.globalMetrics.startTime = new Date();
      }

      // Trigger immediate first cycle
      this._scheduleNextCycle(p, 0);

      if (this.onPatientUpdate) this.onPatientUpdate(p.patientId, p);
      if (this.onMetricsUpdate) this.onMetricsUpdate(this.getGlobalMetrics());
      return true;
    }

    stopPatient(patientId) {
      const p = this.getPatient(patientId);
      if (!p) return false;

      p.isRunning = false;
      if (p.timerId) {
        clearTimeout(p.timerId);
        p.timerId = null;
      }
      if (this.onPatientUpdate) this.onPatientUpdate(p.patientId, p);
      if (this.onMetricsUpdate) this.onMetricsUpdate(this.getGlobalMetrics());
      return true;
    }

    startSelected(patientIds) {
      let started = 0;
      patientIds.forEach(pid => {
        if (this.startPatient(pid)) started++;
      });
      return started;
    }

    stopAll() {
      this.patients.forEach(p => {
        this.stopPatient(p.patientId);
      });
      if (this.onMetricsUpdate) this.onMetricsUpdate(this.getGlobalMetrics());
    }

    isAnyRunning() {
      for (const p of this.patients.values()) {
        if (p.isRunning) return true;
      }
      return false;
    }

    getActiveRunningCount() {
      let count = 0;
      for (const p of this.patients.values()) {
        if (p.isRunning) count++;
      }
      return count;
    }

    _scheduleNextCycle(patientState, delayMs) {
      if (!patientState.isRunning) return;
      if (patientState.timerId) clearTimeout(patientState.timerId);

      patientState.timerId = setTimeout(async () => {
        patientState.timerId = null;
        if (!patientState.isRunning) return;

        await this._executeCycle(patientState);

        // Schedule next execution strictly AFTER previous request finished + samplingInterval
        if (patientState.isRunning) {
          this._scheduleNextCycle(patientState, this.samplingInterval);
        }
      }, delayMs);
    }

    async _executeCycle(patientState) {
      if (patientState.isRequestInFlight) {
        // Concurrency guard: Do not trigger another request if previous is in flight
        return;
      }

      // Generate raw vitals from patient's independent scenario engine
      const reading = patientState.scenarioEngine.next();
      reading.timestamp = new Date().toISOString();
      reading.deviceId = this.deviceId;
      patientState.lastReading = reading;

      // Transmit to backend
      await this.transmitReading(patientState, reading);
    }

    async sendSingleReading(patientId, optionalManual) {
      const p = this.getPatient(patientId);
      if (!p) throw new Error('Patient not registered in simulator.');

      let reading;
      if (optionalManual) {
        reading = {
          heart_rate: parseFloat(optionalManual.heart_rate),
          respiratory_rate: parseFloat(optionalManual.respiratory_rate),
          systolic_bp: parseFloat(optionalManual.systolic_bp),
          temperature: parseFloat(optionalManual.temperature),
          scenario: 'MANUAL',
          timestamp: new Date().toISOString(),
          deviceId: this.deviceId
        };
      } else {
        reading = p.scenarioEngine.next();
        reading.timestamp = new Date().toISOString();
        reading.deviceId = this.deviceId;
      }

      p.lastReading = reading;
      return await this.transmitReading(p, reading);
    }

    async sendSingleReadingToSelected(patientIds) {
      const promises = patientIds.map(pid => this.sendSingleReading(pid));
      return await Promise.allSettled(promises);
    }

    async transmitReading(patientState, reading) {
      patientState.isRequestInFlight = true;
      patientState.lastSentTime = new Date().toLocaleTimeString();
      patientState.metrics.sent++;
      this.globalMetrics.totalReadingsSent++;
      this.globalMetrics.requestsInProgress++;

      if (this.onMetricsUpdate) this.onMetricsUpdate(this.getGlobalMetrics());
      if (this.onPatientUpdate) this.onPatientUpdate(patientState.patientId, patientState);

      const endpoint = `${this.apiBase}/patient/${patientState.patientId}/submit`;
      const payload = {
        heart_rate: reading.heart_rate,
        respiratory_rate: reading.respiratory_rate,
        systolic_bp: reading.systolic_bp,
        temperature: reading.temperature,
        source: 'SIMULATOR',
        device_id: this.deviceId
      };

      const startTime = performance.now();
      let responseOk = false;
      let responseData = null;

      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: this.getAuthHeaders(),
          body: JSON.stringify(payload)
        });

        const elapsedMs = Math.round(performance.now() - startTime);

        if (response.ok) {
          const json = await response.json();
          if (json.success) {
            responseOk = true;
            responseData = json.data;
            this._recordSuccess(patientState, elapsedMs, responseData);
          } else {
            this._recordFailure(patientState, elapsedMs, json.error || 'Server rejected vitals');
          }
        } else if (response.status === 401) {
          this._recordFailure(patientState, elapsedMs, 'HTTP 401: Unauthorized');
          this.stopPatient(patientState.patientId);
          if (this.onAlert) this.onAlert('Session expired or unauthorized. Please log in.');
        } else if (response.status === 403) {
          this._recordFailure(patientState, elapsedMs, 'HTTP 403: Forbidden - Requires Administrator/Staff role');
          this.stopPatient(patientState.patientId);
        } else {
          let errText = `HTTP ${response.status}`;
          try {
            const errJson = await response.json();
            if (errJson.error) errText += `: ${errJson.error}`;
          } catch (_) {}
          this._recordFailure(patientState, elapsedMs, errText);
        }
      } catch (networkErr) {
        const elapsedMs = Math.round(performance.now() - startTime);
        this._recordFailure(patientState, elapsedMs, networkErr.message || 'Network connection failed');
      } finally {
        patientState.isRequestInFlight = false;
        this.globalMetrics.requestsInProgress = Math.max(0, this.globalMetrics.requestsInProgress - 1);
        if (this.onMetricsUpdate) this.onMetricsUpdate(this.getGlobalMetrics());
        if (this.onPatientUpdate) this.onPatientUpdate(patientState.patientId, patientState);
      }

      return { success: responseOk, data: responseData };
    }

    _recordSuccess(patientState, latencyMs, responseData) {
      patientState.metrics.success++;
      patientState.errorStreak = 0;
      patientState.lastResponse = {
        success: true,
        vital_id: responseData.vital_id,
        total_score: responseData.total_score,
        condition: responseData.condition,
        recommendation: responseData.recommendation,
        scores: responseData.scores,
        timestamp: new Date().toLocaleTimeString()
      };

      // Add to latencies
      patientState.metrics.latencies.push(latencyMs);
      if (patientState.metrics.latencies.length > 50) patientState.metrics.latencies.shift();
      patientState.metrics.avgLatency = Math.round(patientState.metrics.latencies.reduce((a, b) => a + b, 0) / patientState.metrics.latencies.length);

      this.globalMetrics.successfulRequests++;
      this.globalMetrics.lastSuccessfulTime = new Date().toLocaleTimeString();
      this.globalMetrics.latencies.push(latencyMs);
      if (this.globalMetrics.latencies.length > 200) this.globalMetrics.latencies.shift();

      this._updateLatencyStats();
    }

    _recordFailure(patientState, latencyMs, errorMessage) {
      patientState.metrics.failed++;
      patientState.metrics.lastError = errorMessage;
      patientState.errorStreak++;
      patientState.lastResponse = {
        success: false,
        error: errorMessage,
        timestamp: new Date().toLocaleTimeString()
      };

      this.globalMetrics.failedRequests++;
      this.globalMetrics.lastFailedTime = new Date().toLocaleTimeString();

      // Repeated error safety: auto-pause after 3 consecutive connection drops
      if (patientState.errorStreak >= 3 && patientState.isRunning) {
        this.stopPatient(patientState.patientId);
        if (this.onAlert) {
          this.onAlert(`Simulation paused for ${patientState.patient.name} due to repeated backend errors (${errorMessage}).`);
        }
      }

      this._updateLatencyStats();
    }

    _updateLatencyStats() {
      const arr = this.globalMetrics.latencies;
      if (arr.length > 0) {
        this.globalMetrics.minLatencyMs = Math.min(...arr);
        this.globalMetrics.maxLatencyMs = Math.max(...arr);
        this.globalMetrics.avgLatencyMs = Math.round(arr.reduce((a, b) => a + b, 0) / arr.length);
      }
    }

    getGlobalMetrics() {
      const total = this.globalMetrics.totalReadingsSent;
      const succ = this.globalMetrics.successfulRequests;
      const rate = total > 0 ? ((succ / total) * 100).toFixed(1) : '100.0';

      return {
        selectedPatientsCount: this.patients.size,
        activeRunningCount: this.getActiveRunningCount(),
        samplingIntervalSeconds: (this.samplingInterval / 1000).toFixed(0),
        totalReadingsSent: total,
        successfulRequests: succ,
        failedRequests: this.globalMetrics.failedRequests,
        requestsInProgress: this.globalMetrics.requestsInProgress,
        successRatePercent: parseFloat(rate),
        avgLatencyMs: this.globalMetrics.avgLatencyMs,
        minLatencyMs: this.globalMetrics.minLatencyMs || 0,
        maxLatencyMs: this.globalMetrics.maxLatencyMs || 0,
        readingsPerMinute: this.globalMetrics.readingsPerMinute,
        lastSuccessfulTime: this.globalMetrics.lastSuccessfulTime || '--',
        lastFailedTime: this.globalMetrics.lastFailedTime || '--'
      };
    }

    /**
     * Read-back Verification:
     * Queries authoritative backend GET /api/v1/vitals/patient/<id>/latest-status
     * Compares transmitted vs stored vital parameters.
     */
    async verifyReadBack(patientId) {
      const p = this.getPatient(patientId);
      if (!p) throw new Error('Patient not found');

      const url = `${this.apiBase}/patient/${patientId}/latest-status`;
      const res = await fetch(url, { headers: this.getAuthHeaders() });
      if (!res.ok) throw new Error(`Read-back query failed: HTTP ${res.status}`);

      const json = await res.json();
      if (!json.success || !json.data) throw new Error('Invalid latest-status response');

      const dbData = json.data;
      const dbVitals = dbData.latest_vitals || {};
      const sent = p.lastReading || {};

      const hrMatch = sent.heart_rate !== undefined ? Math.abs(sent.heart_rate - (dbVitals.heart_rate || 0)) < 0.2 : true;
      const rrMatch = sent.respiratory_rate !== undefined ? Math.abs(sent.respiratory_rate - (dbVitals.respiratory_rate || 0)) < 0.2 : true;
      const sbpMatch = sent.systolic_bp !== undefined ? Math.abs(sent.systolic_bp - (dbVitals.systolic_bp || 0)) < 0.2 : true;
      const tempMatch = sent.temperature !== undefined ? Math.abs(sent.temperature - (dbVitals.temperature || 0)) < 0.2 : true;

      const passed = hrMatch && rrMatch && sbpMatch && tempMatch;

      p.readBackVerification = {
        sent: {
          hr: sent.heart_rate,
          rr: sent.respiratory_rate,
          sbp: sent.systolic_bp,
          temp: sent.temperature
        },
        db: {
          hr: dbVitals.heart_rate,
          rr: dbVitals.respiratory_rate,
          sbp: dbVitals.systolic_bp,
          temp: dbVitals.temperature,
          recorded_at: dbData.recorded_at
        },
        result: passed ? 'PASS' : 'MISMATCH',
        checkedAt: new Date().toLocaleTimeString()
      };

      if (this.onPatientUpdate) this.onPatientUpdate(p.patientId, p);
      return p.readBackVerification;
    }

    /**
     * EWS Accuracy & Relationship Verification:
     * Queries GET /api/v1/vitals/<patientId>/latest
     * Verifies ews.vital_id == vitals.vital_id and patient_id integrity.
     */
    async verifyEwsRelationship(patientId) {
      const p = this.getPatient(patientId);
      if (!p) throw new Error('Patient not found');

      const url = `${this.apiBase}/${patientId}/latest`;
      const res = await fetch(url, { headers: this.getAuthHeaders() });
      if (!res.ok) throw new Error(`EWS query failed: HTTP ${res.status}`);

      const json = await res.json();
      if (!json.success || !json.data) throw new Error('Invalid EWS query response');

      const vitals = json.data.vitals;
      const ews = json.data.ews;

      if (!vitals || !ews) {
        p.ewsVerification = {
          status: 'NO_DATA',
          message: 'No vitals or EWS recorded yet'
        };
        return p.ewsVerification;
      }

      const vitalIdMatch = vitals.vital_id === ews.vital_id;
      const patientIdMatch = parseInt(vitals.patient_id, 10) === parseInt(patientId, 10) && parseInt(ews.patient_id, 10) === parseInt(patientId, 10);

      const passed = vitalIdMatch && patientIdMatch;

      p.ewsVerification = {
        patientId: patientId,
        vitalId: vitals.vital_id,
        ewsVitalId: ews.vital_id,
        vitalIdMatch: vitalIdMatch,
        patientIdMatch: patientIdMatch,
        totalScore: ews.total_score,
        riskLevel: ews.risk_level,
        recordedAt: vitals.recorded_at,
        status: passed ? 'VERIFIED' : 'EWS RELATIONSHIP ERROR',
        checkedAt: new Date().toLocaleTimeString()
      };

      if (this.onPatientUpdate) this.onPatientUpdate(p.patientId, p);
      return p.ewsVerification;
    }

    destroy() {
      this.stopAll();
      if (this._rpmTimer) clearInterval(this._rpmTimer);
    }
  }

  return SimulatorEngine;
});
