"""
telemetry_simulator/models.py — Data models for the Jeevan Setu Telemetry Simulator.

Simple dataclasses representing telemetry readings and simulator state.
Contains NO EWS scoring, NO clinical decision logic, NO risk assessment.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class VitalReading:
    """
    A single set of raw vital sign values to be submitted.

    This is purely a data container — no EWS calculation happens here.
    The backend is solely responsible for scoring and clinical decisions.
    """
    heart_rate: float
    respiratory_rate: float
    systolic_bp: float
    temperature: float
    patient_id: int
    device_id: str = ''
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_payload(self) -> dict:
        """Convert to the JSON payload expected by POST /vitals/patient/{id}/submit."""
        return {
            'heart_rate': round(self.heart_rate, 1),
            'respiratory_rate': round(self.respiratory_rate, 1),
            'systolic_bp': round(self.systolic_bp, 1),
            'temperature': round(self.temperature, 1),
        }

    def display_str(self) -> str:
        """Human-readable summary for logging."""
        return (
            f"HR={self.heart_rate:.0f} "
            f"RR={self.respiratory_rate:.0f} "
            f"SBP={self.systolic_bp:.0f} "
            f"TEMP={self.temperature:.1f}"
        )

    def validate(self, ranges: dict) -> list:
        """
        Validate that all vital values are within the backend's accepted ranges.

        Args:
            ranges: Dict mapping field names to (min, max) tuples.

        Returns:
            List of error strings. Empty list means valid.
        """
        errors = []
        for field_name, (lo, hi) in ranges.items():
            value = getattr(self, field_name, None)
            if value is None:
                errors.append(f'{field_name} is required.')
            elif value < lo or value > hi:
                errors.append(f'{field_name} ({value}) is outside accepted range [{lo}, {hi}].')
        return errors


@dataclass
class SimulatorStatus:
    """Tracks the runtime state of the simulator for observability."""
    running: bool = False
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    scenario: Optional[str] = None
    device_id: str = ''
    interval_seconds: int = 5
    readings_sent: int = 0
    successful: int = 0
    failed: int = 0
    last_success_time: Optional[datetime] = None
    last_error: Optional[str] = None
    started_at: Optional[datetime] = None

    def record_success(self):
        self.readings_sent += 1
        self.successful += 1
        self.last_success_time = datetime.now(timezone.utc)
        self.last_error = None

    def record_failure(self, error: str):
        self.readings_sent += 1
        self.failed += 1
        self.last_error = error

    def summary(self) -> dict:
        return {
            'running': self.running,
            'patient_id': self.patient_id,
            'patient_name': self.patient_name,
            'scenario': self.scenario,
            'device_id': self.device_id,
            'interval_seconds': self.interval_seconds,
            'readings_sent': self.readings_sent,
            'successful': self.successful,
            'failed': self.failed,
            'last_success': str(self.last_success_time) if self.last_success_time else None,
            'last_error': self.last_error,
            'started_at': str(self.started_at) if self.started_at else None,
        }
