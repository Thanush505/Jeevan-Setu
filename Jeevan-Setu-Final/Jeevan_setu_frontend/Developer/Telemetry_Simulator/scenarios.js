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
      let scen = (scenarioName || 'STABLE').toUpperCase();
      if (scen === 'GRADUAL_DETERIORATION' || scen === 'DETERIORATION') {
        scen = 'MODERATE';
      }
      this.scenarioName = scen;
      this.manualValues = manualValues || null;
      this.tick = 0;

      if (this.scenarioName === 'STABLE') {
        this.hr = randomBetween(70, 78);
        this.rr = randomBetween(14, 18);
        this.sbp = randomBetween(116, 124);
        this.temp = randomBetween(36.6, 37.0);
      } else if (this.scenarioName === 'MODERATE') {
        // Moderate clinical deviation (EWS 3-5)
        this.hr = randomBetween(96, 106);
        this.rr = randomBetween(21, 24);
        this.sbp = randomBetween(92, 98);
        this.temp = randomBetween(38.2, 38.6);
      } else if (this.scenarioName === 'CRITICAL') {
        // Severe physiological distress (EWS >= 7)
        this.hr = randomBetween(136, 152);
        this.rr = randomBetween(28, 36);
        this.sbp = randomBetween(56, 68);
        this.temp = randomBetween(39.4, 40.2);
      } else if (this.scenarioName === 'RECOVERY') {
        // Stabilizing convalescent state
        this.hr = randomBetween(76, 84);
        this.rr = randomBetween(16, 19);
        this.sbp = randomBetween(112, 120);
        this.temp = randomBetween(36.9, 37.3);
      } else if (this.scenarioName === 'MANUAL' && this.manualValues) {
        this.hr = parseFloat(this.manualValues.heart_rate) || 75.0;
        this.rr = parseFloat(this.manualValues.respiratory_rate) || 16.0;
        this.sbp = parseFloat(this.manualValues.systolic_bp) || 120.0;
        this.temp = parseFloat(this.manualValues.temperature) || 36.8;
      }
    }

    setScenario(scenarioName, immediate) {
      let scen = (scenarioName || 'STABLE').toUpperCase();
      if (scen === 'GRADUAL_DETERIORATION' || scen === 'DETERIORATION') {
        scen = 'MODERATE';
      }
      this.scenarioName = scen;
      this.tick = 0;

      // Immediate physiological transition aligns subsequent reading to target profile
      if (immediate !== false) {
        if (scen === 'STABLE') {
          this.hr = randomBetween(70, 78);
          this.rr = randomBetween(14, 18);
          this.sbp = randomBetween(116, 124);
          this.temp = randomBetween(36.6, 37.0);
        } else if (scen === 'MODERATE') {
          this.hr = randomBetween(96, 106);
          this.rr = randomBetween(21, 24);
          this.sbp = randomBetween(92, 98);
          this.temp = randomBetween(38.2, 38.6);
        } else if (scen === 'CRITICAL') {
          this.hr = randomBetween(136, 152);
          this.rr = randomBetween(28, 36);
          this.sbp = randomBetween(56, 68);
          this.temp = randomBetween(39.4, 40.2);
        } else if (scen === 'RECOVERY') {
          this.hr = randomBetween(76, 84);
          this.rr = randomBetween(16, 19);
          this.sbp = randomBetween(112, 120);
          this.temp = randomBetween(36.9, 37.3);
        }
      }
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
        case 'MODERATE':
        case 'GRADUAL_DETERIORATION':
          return this._moderateNext();
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

    _moderateNext() {
      // Fluctuate in moderate range (EWS 3-5: HR 95-108, RR 21-25, SBP 92-100, Temp 38.1-38.6)
      this.hr = clamp(drift(this.hr, 102, 1.2, 0.8), 92, 110);
      this.rr = clamp(drift(this.rr, 22, 0.6, 0.4), 18, 25);
      this.sbp = clamp(drift(this.sbp, 95, 1.5, 1.0), 85, 105);
      this.temp = clamp(drift(this.temp, 38.3, 0.05, 0.02), 37.8, 38.8);
      return this._snapshot();
    }

    _deteriorationNext() {
      return this._moderateNext();
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
    SCENARIO_LIST: ['STABLE', 'MODERATE', 'CRITICAL', 'RECOVERY', 'MANUAL'],
    createPatientState: function (scenarioName, manualValues) {
      return new PatientScenarioState(scenarioName, manualValues);
    }
  };
});
