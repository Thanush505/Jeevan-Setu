/**
 * scenarios.js — Raw Physiological Vital Sign Simulation Scenarios.
 * 
 * IMPORTANT ARCHITECTURAL RULE:
 * This module generates RAW VITAL READINGS ONLY (HR, RR, SBP, Temp).
 * It DOES NOT calculate EWS.
 * It DOES NOT assess clinical risk.
 * It DOES NOT make transfer or admission decisions.
 * The existing Jeevan Setu backend is the SOLE authority for all clinical scoring.
 */

(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.ScenarioManager = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function clamp(val, min, max) {
    return Math.max(min, Math.min(max, val));
  }

  function randomBetween(min, max) {
    return min + Math.random() * (max - min);
  }

  function drift(current, target, maxStep, noise) {
    const diff = target - current;
    const step = Math.min(Math.abs(diff), maxStep);
    const direction = diff >= 0 ? 1.0 : -1.0;
    const jitter = (Math.random() * 2 - 1) * (noise || 0);
    return current + direction * step + jitter;
  }

  /**
   * Represents an isolated physiological state for a single patient.
   */
  class PatientScenarioState {
    constructor(scenarioName, manualValues) {
      this.scenarioName = (scenarioName || 'STABLE').toUpperCase();
      this.manualValues = manualValues || null;
      this.tick = 0;

      // Initialize base values
      this.hr = 75.0;
      this.rr = 16.0;
      this.sbp = 120.0;
      this.temp = 36.8;

      this.reset(this.scenarioName, this.manualValues);
    }

    reset(scenarioName, manualValues) {
      this.scenarioName = (scenarioName || 'STABLE').toUpperCase();
      this.manualValues = manualValues || null;
      this.tick = 0;

      if (this.scenarioName === 'STABLE') {
        this.hr = randomBetween(70, 78);
        this.rr = randomBetween(14, 18);
        this.sbp = randomBetween(116, 124);
        this.temp = randomBetween(36.6, 37.0);
      } else if (this.scenarioName === 'GRADUAL_DETERIORATION') {
        // Start near-normal
        this.hr = randomBetween(72, 78);
        this.rr = randomBetween(15, 17);
        this.sbp = randomBetween(118, 122);
        this.temp = randomBetween(36.6, 36.9);
      } else if (this.scenarioName === 'CRITICAL') {
        // Rapid onset from slightly elevated to severely abnormal
        this.hr = randomBetween(80, 95);
        this.rr = randomBetween(18, 22);
        this.sbp = randomBetween(110, 118);
        this.temp = randomBetween(37.2, 37.6);
      } else if (this.scenarioName === 'RECOVERY') {
        // Starts in abnormal state
        this.hr = randomBetween(125, 138);
        this.rr = randomBetween(28, 34);
        this.sbp = randomBetween(65, 75);
        this.temp = randomBetween(39.1, 39.8);
      } else if (this.scenarioName === 'MANUAL' && this.manualValues) {
        this.hr = parseFloat(this.manualValues.heart_rate) || 75.0;
        this.rr = parseFloat(this.manualValues.respiratory_rate) || 16.0;
        this.sbp = parseFloat(this.manualValues.systolic_bp) || 120.0;
        this.temp = parseFloat(this.manualValues.temperature) || 36.8;
      }
    }

    setScenario(scenarioName) {
      this.scenarioName = (scenarioName || 'STABLE').toUpperCase();
      // Smooth transition: keep current physiological values and reset tick progression
      this.tick = 0;
    }

    setManualValues(values) {
      this.manualValues = values;
      this.scenarioName = 'MANUAL';
      if (values) {
        if (values.heart_rate !== undefined) this.hr = parseFloat(values.heart_rate);
        if (values.respiratory_rate !== undefined) this.rr = parseFloat(values.respiratory_rate);
        if (values.systolic_bp !== undefined) this.sbp = parseFloat(values.systolic_bp);
        if (values.temperature !== undefined) this.temp = parseFloat(values.temperature);
      }
    }

    next() {
      this.tick++;

      switch (this.scenarioName) {
        case 'MANUAL':
          return this._manualNext();
        case 'STABLE':
          return this._stableNext();
        case 'GRADUAL_DETERIORATION':
          return this._deteriorationNext();
        case 'CRITICAL':
          return this._criticalNext();
        case 'RECOVERY':
          return this._recoveryNext();
        default:
          return this._stableNext();
      }
    }

    _snapshot() {
      return {
        heart_rate: Math.round(this.hr * 10) / 10,
        respiratory_rate: Math.round(this.rr * 10) / 10,
        systolic_bp: Math.round(this.sbp * 10) / 10,
        temperature: Math.round(this.temp * 10) / 10,
        scenario: this.scenarioName,
        tick: this.tick
      };
    }

    _manualNext() {
      if (this.manualValues) {
        this.hr = parseFloat(this.manualValues.heart_rate) || this.hr;
        this.rr = parseFloat(this.manualValues.respiratory_rate) || this.rr;
        this.sbp = parseFloat(this.manualValues.systolic_bp) || this.sbp;
        this.temp = parseFloat(this.manualValues.temperature) || this.temp;
      }
      return this._snapshot();
    }

    _stableNext() {
      // Gentle random walk around healthy baseline
      this.hr = clamp(drift(this.hr, 75, 1.0, 0.6), 62, 92);
      this.rr = clamp(drift(this.rr, 16, 0.5, 0.3), 12, 19);
      this.sbp = clamp(drift(this.sbp, 120, 1.5, 1.0), 105, 135);
      this.temp = clamp(drift(this.temp, 36.8, 0.05, 0.02), 36.4, 37.3);
      return this._snapshot();
    }

    _deteriorationNext() {
      const t = this.tick;
      if (t <= 10) {
        // Phase 1: Near normal with slight drift
        this.hr = clamp(drift(this.hr, 82, 0.8, 0.5), 68, 92);
        this.rr = clamp(drift(this.rr, 18, 0.4, 0.3), 14, 21);
        this.sbp = clamp(drift(this.sbp, 116, 1.0, 0.8), 105, 130);
        this.temp = clamp(drift(this.temp, 37.1, 0.04, 0.02), 36.5, 37.5);
      } else if (t <= 22) {
        // Phase 2: Moderate deviation
        this.hr = clamp(drift(this.hr, 98, 1.5, 0.8), 75, 115);
        this.rr = clamp(drift(this.rr, 23, 0.7, 0.4), 16, 26);
        this.sbp = clamp(drift(this.sbp, 96, 1.8, 1.2), 85, 120);
        this.temp = clamp(drift(this.temp, 37.9, 0.08, 0.03), 36.8, 38.6);
      } else if (t <= 34) {
        // Phase 3: Significant abnormality
        this.hr = clamp(drift(this.hr, 122, 2.2, 1.0), 95, 140);
        this.rr = clamp(drift(this.rr, 29, 0.9, 0.5), 22, 36);
        this.sbp = clamp(drift(this.sbp, 78, 2.0, 1.4), 65, 98);
        this.temp = clamp(drift(this.temp, 38.9, 0.1, 0.04), 37.6, 39.7);
      } else {
        // Phase 4: Critical territory
        this.hr = clamp(drift(this.hr, 142, 2.5, 1.5), 125, 168);
        this.rr = clamp(drift(this.rr, 35, 1.2, 0.6), 28, 46);
        this.sbp = clamp(drift(this.sbp, 64, 2.5, 1.5), 45, 80);
        this.temp = clamp(drift(this.temp, 39.6, 0.12, 0.05), 38.6, 40.8);
      }
      return this._snapshot();
    }

    _criticalNext() {
      const t = this.tick;
      if (t <= 4) {
        // Rapid escalation
        this.hr = clamp(drift(this.hr, 115, 5.0, 1.5), 85, 135);
        this.rr = clamp(drift(this.rr, 27, 2.0, 0.8), 20, 32);
        this.sbp = clamp(drift(this.sbp, 82, 5.0, 2.0), 65, 105);
        this.temp = clamp(drift(this.temp, 38.6, 0.2, 0.05), 37.2, 39.2);
      } else if (t <= 8) {
        // Severe worsening
        this.hr = clamp(drift(this.hr, 138, 4.5, 2.0), 115, 160);
        this.rr = clamp(drift(this.rr, 34, 1.8, 1.0), 26, 42);
        this.sbp = clamp(drift(this.sbp, 66, 4.0, 2.0), 50, 85);
        this.temp = clamp(drift(this.temp, 39.6, 0.2, 0.06), 38.5, 40.5);
      } else {
        // Sustained critical with realistic ICU fluctuation
        this.hr = clamp(drift(this.hr, 148, 3.0, 2.5), 130, 175);
        this.rr = clamp(drift(this.rr, 38, 1.4, 1.0), 30, 48);
        this.sbp = clamp(drift(this.sbp, 58, 3.0, 2.5), 42, 74);
        this.temp = clamp(drift(this.temp, 40.1, 0.1, 0.08), 39.1, 41.2);
      }
      return this._snapshot();
    }

    _recoveryNext() {
      const t = this.tick;
      if (t <= 10) {
        // Initial gradual recovery step
        this.hr = clamp(drift(this.hr, 112, 2.2, 1.0), 96, 142);
        this.rr = clamp(drift(this.rr, 25, 0.9, 0.5), 20, 35);
        this.sbp = clamp(drift(this.sbp, 88, 2.2, 1.2), 65, 102);
        this.temp = clamp(drift(this.temp, 38.3, 0.12, 0.04), 37.6, 39.6);
      } else if (t <= 20) {
        // Intermediate recovery
        this.hr = clamp(drift(this.hr, 92, 1.8, 0.8), 80, 116);
        this.rr = clamp(drift(this.rr, 19, 0.7, 0.4), 15, 25);
        this.sbp = clamp(drift(this.sbp, 106, 1.8, 1.0), 88, 124);
        this.temp = clamp(drift(this.temp, 37.4, 0.09, 0.03), 36.9, 38.4);
      } else {
        // Near-normal recovery stabilization
        this.hr = clamp(drift(this.hr, 76, 1.2, 0.6), 65, 94);
        this.rr = clamp(drift(this.rr, 16, 0.5, 0.3), 12, 20);
        this.sbp = clamp(drift(this.sbp, 118, 1.2, 0.8), 105, 134);
        this.temp = clamp(drift(this.temp, 36.8, 0.05, 0.02), 36.4, 37.3);
      }
      return this._snapshot();
    }
  }

  // Factory/Manager
  return {
    SCENARIO_LIST: ['STABLE', 'GRADUAL_DETERIORATION', 'CRITICAL', 'RECOVERY', 'MANUAL'],
    createPatientState: function (scenarioName, manualValues) {
      return new PatientScenarioState(scenarioName, manualValues);
    }
  };
});
