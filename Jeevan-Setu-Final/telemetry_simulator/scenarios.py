"""
telemetry_simulator/scenarios.py — Simulation scenarios for the Jeevan Setu Telemetry Simulator.

Each scenario generates RAW VITAL SIGN DATA only.
NO EWS calculation. NO risk assessment. NO clinical decisions.
The existing Jeevan Setu backend is solely responsible for all scoring.

Scenarios:
    STABLE               — Normal adult resting vitals with small physiological drift.
    GRADUAL_DETERIORATION — Values gradually migrate from normal toward abnormal ranges.
    CRITICAL             — Values rapidly move to severely abnormal readings.
    RECOVERY             — Values gradually return from abnormal toward stable.
    MANUAL               — User specifies exact values (pass-through).
"""

import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class _PhysiologicalState:
    """Internal mutable state tracking current simulated vital values."""
    heart_rate: float = 75.0
    respiratory_rate: float = 16.0
    systolic_bp: float = 120.0
    temperature: float = 36.8
    tick: int = 0  # Number of readings generated so far


def _clamp(value: float, lo: float, hi: float) -> float:
    """Restrict a value to [lo, hi] range."""
    return max(lo, min(hi, value))


def _drift(current: float, target: float, max_step: float, noise: float = 0.0) -> float:
    """
    Move current value toward target by at most max_step, with optional random noise.
    Produces the gradual, realistic-looking changes required by the specification.
    """
    diff = target - current
    step = min(abs(diff), max_step)
    direction = 1.0 if diff > 0 else -1.0
    new_val = current + direction * step + random.uniform(-noise, noise)
    return new_val


class ScenarioEngine:
    """
    Generates the next set of raw vital values based on the selected scenario.

    Usage:
        engine = ScenarioEngine('STABLE')
        vitals = engine.next()  # dict with heart_rate, respiratory_rate, systolic_bp, temperature
    """

    SCENARIO_NAMES = ['STABLE', 'GRADUAL_DETERIORATION', 'CRITICAL', 'RECOVERY', 'MANUAL']

    def __init__(self, scenario: str, manual_values: Optional[dict] = None):
        """
        Args:
            scenario: One of SCENARIO_NAMES.
            manual_values: Dict with heart_rate, respiratory_rate, systolic_bp, temperature
                           (only used when scenario == 'MANUAL').
        """
        scenario = scenario.upper().strip()
        if scenario not in self.SCENARIO_NAMES:
            raise ValueError(f"Unknown scenario '{scenario}'. Choose from {self.SCENARIO_NAMES}")

        self.scenario = scenario
        self.manual_values = manual_values
        self._state = _PhysiologicalState()

        # Set initial state based on scenario
        if scenario == 'STABLE':
            self._state.heart_rate = random.uniform(70, 80)
            self._state.respiratory_rate = random.uniform(14, 18)
            self._state.systolic_bp = random.uniform(115, 125)
            self._state.temperature = random.uniform(36.5, 37.0)

        elif scenario == 'GRADUAL_DETERIORATION':
            # Start near-normal
            self._state.heart_rate = random.uniform(72, 78)
            self._state.respiratory_rate = random.uniform(15, 17)
            self._state.systolic_bp = random.uniform(118, 122)
            self._state.temperature = random.uniform(36.6, 36.9)

        elif scenario == 'CRITICAL':
            # Start normal, will deteriorate quickly
            self._state.heart_rate = random.uniform(75, 85)
            self._state.respiratory_rate = random.uniform(16, 18)
            self._state.systolic_bp = random.uniform(115, 120)
            self._state.temperature = random.uniform(36.8, 37.2)

        elif scenario == 'RECOVERY':
            # Start in abnormal territory
            self._state.heart_rate = random.uniform(125, 140)
            self._state.respiratory_rate = random.uniform(28, 35)
            self._state.systolic_bp = random.uniform(65, 75)
            self._state.temperature = random.uniform(39.0, 39.8)

    def next(self) -> dict:
        """
        Generate the next set of raw vital values.

        Returns:
            dict with keys: heart_rate, respiratory_rate, systolic_bp, temperature
        """
        if self.scenario == 'MANUAL':
            return self._manual_next()
        elif self.scenario == 'STABLE':
            return self._stable_next()
        elif self.scenario == 'GRADUAL_DETERIORATION':
            return self._deterioration_next()
        elif self.scenario == 'CRITICAL':
            return self._critical_next()
        elif self.scenario == 'RECOVERY':
            return self._recovery_next()

    def _manual_next(self) -> dict:
        """Return the fixed manual values each time."""
        if not self.manual_values:
            raise ValueError("Manual scenario requires manual_values to be provided.")
        return {
            'heart_rate': float(self.manual_values.get('heart_rate', 75)),
            'respiratory_rate': float(self.manual_values.get('respiratory_rate', 16)),
            'systolic_bp': float(self.manual_values.get('systolic_bp', 120)),
            'temperature': float(self.manual_values.get('temperature', 36.8)),
        }

    def _stable_next(self) -> dict:
        """Small physiological variations around normal resting values."""
        s = self._state
        s.tick += 1

        # Gentle random walk around a normal centre
        s.heart_rate = _clamp(_drift(s.heart_rate, 75, 1.0, noise=0.5), 60, 95)
        s.respiratory_rate = _clamp(_drift(s.respiratory_rate, 16, 0.5, noise=0.3), 12, 20)
        s.systolic_bp = _clamp(_drift(s.systolic_bp, 120, 1.5, noise=1.0), 100, 140)
        s.temperature = _clamp(_drift(s.temperature, 36.8, 0.05, noise=0.02), 36.2, 37.4)

        return self._snapshot()

    def _deterioration_next(self) -> dict:
        """
        Four-phase gradual deterioration.
        Phase 1 (ticks 0-11):  Mostly stable
        Phase 2 (ticks 12-23): Mild changes
        Phase 3 (ticks 24-35): Progressive abnormality
        Phase 4 (ticks 36+):   Severe abnormal readings
        """
        s = self._state
        s.tick += 1
        tick = s.tick

        if tick <= 12:
            # Phase 1: mostly stable with tiny drift
            s.heart_rate = _clamp(_drift(s.heart_rate, 78, 0.8, noise=0.5), 65, 90)
            s.respiratory_rate = _clamp(_drift(s.respiratory_rate, 17, 0.4, noise=0.3), 13, 21)
            s.systolic_bp = _clamp(_drift(s.systolic_bp, 118, 1.0, noise=0.8), 105, 135)
            s.temperature = _clamp(_drift(s.temperature, 37.0, 0.03, noise=0.02), 36.4, 37.5)
        elif tick <= 24:
            # Phase 2: mild deviations
            s.heart_rate = _clamp(_drift(s.heart_rate, 95, 1.5, noise=0.8), 70, 115)
            s.respiratory_rate = _clamp(_drift(s.respiratory_rate, 22, 0.6, noise=0.4), 16, 26)
            s.systolic_bp = _clamp(_drift(s.systolic_bp, 95, 1.5, noise=1.0), 80, 120)
            s.temperature = _clamp(_drift(s.temperature, 37.8, 0.06, noise=0.03), 36.8, 38.5)
        elif tick <= 36:
            # Phase 3: progressive abnormality
            s.heart_rate = _clamp(_drift(s.heart_rate, 120, 2.0, noise=1.0), 90, 140)
            s.respiratory_rate = _clamp(_drift(s.respiratory_rate, 28, 0.8, noise=0.5), 20, 35)
            s.systolic_bp = _clamp(_drift(s.systolic_bp, 78, 2.0, noise=1.2), 60, 100)
            s.temperature = _clamp(_drift(s.temperature, 38.8, 0.08, noise=0.04), 37.5, 39.5)
        else:
            # Phase 4: severe
            s.heart_rate = _clamp(_drift(s.heart_rate, 140, 2.5, noise=1.5), 120, 165)
            s.respiratory_rate = _clamp(_drift(s.respiratory_rate, 34, 1.0, noise=0.6), 28, 45)
            s.systolic_bp = _clamp(_drift(s.systolic_bp, 65, 2.5, noise=1.5), 45, 80)
            s.temperature = _clamp(_drift(s.temperature, 39.5, 0.1, noise=0.05), 38.5, 40.5)

        return self._snapshot()

    def _critical_next(self) -> dict:
        """
        Rapid deterioration to severely abnormal values.
        Reaches critical territory within ~10-15 ticks.
        """
        s = self._state
        s.tick += 1
        tick = s.tick

        if tick <= 5:
            # Quick initial worsening
            s.heart_rate = _clamp(_drift(s.heart_rate, 110, 4.0, noise=1.5), 80, 130)
            s.respiratory_rate = _clamp(_drift(s.respiratory_rate, 25, 1.5, noise=0.8), 18, 30)
            s.systolic_bp = _clamp(_drift(s.systolic_bp, 85, 4.0, noise=2.0), 70, 110)
            s.temperature = _clamp(_drift(s.temperature, 38.5, 0.15, noise=0.05), 37.0, 39.0)
        elif tick <= 10:
            # Worsening
            s.heart_rate = _clamp(_drift(s.heart_rate, 135, 4.0, noise=2.0), 110, 160)
            s.respiratory_rate = _clamp(_drift(s.respiratory_rate, 33, 1.5, noise=1.0), 24, 40)
            s.systolic_bp = _clamp(_drift(s.systolic_bp, 68, 3.5, noise=2.0), 50, 85)
            s.temperature = _clamp(_drift(s.temperature, 39.5, 0.15, noise=0.08), 38.5, 40.5)
        else:
            # Sustained critical with some fluctuation
            s.heart_rate = _clamp(_drift(s.heart_rate, 145, 3.0, noise=2.5), 125, 175)
            s.respiratory_rate = _clamp(_drift(s.respiratory_rate, 38, 1.2, noise=1.0), 30, 50)
            s.systolic_bp = _clamp(_drift(s.systolic_bp, 58, 3.0, noise=2.5), 42, 72)
            s.temperature = _clamp(_drift(s.temperature, 40.0, 0.1, noise=0.08), 39.0, 41.0)

        return self._snapshot()

    def _recovery_next(self) -> dict:
        """
        Gradual return from abnormal toward stable values.
        Takes ~25-35 ticks to reach near-normal.
        """
        s = self._state
        s.tick += 1
        tick = s.tick

        if tick <= 10:
            # Slow initial recovery
            s.heart_rate = _clamp(_drift(s.heart_rate, 110, 2.0, noise=1.0), 95, 145)
            s.respiratory_rate = _clamp(_drift(s.respiratory_rate, 24, 0.8, noise=0.5), 20, 36)
            s.systolic_bp = _clamp(_drift(s.systolic_bp, 85, 2.0, noise=1.0), 62, 100)
            s.temperature = _clamp(_drift(s.temperature, 38.2, 0.1, noise=0.04), 37.5, 39.8)
        elif tick <= 20:
            # Continued improvement
            s.heart_rate = _clamp(_drift(s.heart_rate, 92, 1.5, noise=0.8), 80, 115)
            s.respiratory_rate = _clamp(_drift(s.respiratory_rate, 19, 0.6, noise=0.4), 15, 25)
            s.systolic_bp = _clamp(_drift(s.systolic_bp, 105, 1.5, noise=1.0), 85, 125)
            s.temperature = _clamp(_drift(s.temperature, 37.4, 0.08, noise=0.03), 36.8, 38.5)
        else:
            # Near-normal stabilisation
            s.heart_rate = _clamp(_drift(s.heart_rate, 78, 1.0, noise=0.5), 65, 95)
            s.respiratory_rate = _clamp(_drift(s.respiratory_rate, 16, 0.4, noise=0.3), 12, 20)
            s.systolic_bp = _clamp(_drift(s.systolic_bp, 118, 1.2, noise=0.8), 105, 135)
            s.temperature = _clamp(_drift(s.temperature, 36.8, 0.05, noise=0.02), 36.3, 37.3)

        return self._snapshot()

    def _snapshot(self) -> dict:
        """Return current state as a dict of rounded values."""
        s = self._state
        return {
            'heart_rate': round(s.heart_rate, 1),
            'respiratory_rate': round(s.respiratory_rate, 1),
            'systolic_bp': round(s.systolic_bp, 1),
            'temperature': round(s.temperature, 1),
        }

    @property
    def tick(self) -> int:
        return self._state.tick
