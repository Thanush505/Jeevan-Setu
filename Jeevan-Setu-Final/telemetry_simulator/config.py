"""
telemetry_simulator/config.py — Configuration for the Jeevan Setu Telemetry Simulator.

Loads settings from environment variables (.env file) with sensible defaults.
Never hardcodes secrets, IPs, or patient identifiers.
"""

import os
from dotenv import load_dotenv

# Load .env from the simulator directory first, then project root
_sim_dir = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_sim_dir, '.env')
if os.path.exists(_env_path):
    load_dotenv(_env_path)
else:
    # Try the parent project .env as fallback
    _parent_env = os.path.join(os.path.dirname(_sim_dir), 'JEEVAN_SETU', '.env')
    if os.path.exists(_parent_env):
        load_dotenv(_parent_env)

# Minimum allowed telemetry interval (seconds) to prevent API flooding
_MIN_INTERVAL_SECONDS = 1


class SimulatorConfig:
    """Immutable configuration loaded from environment."""

    # Backend connection
    API_BASE_URL: str = os.getenv('SIMULATOR_API_BASE_URL', 'http://127.0.0.1:5000')

    # Authentication credentials (for obtaining JWT)
    AUTH_USERNAME: str = os.getenv('SIMULATOR_AUTH_USERNAME', '')
    AUTH_PASSWORD: str = os.getenv('SIMULATOR_AUTH_PASSWORD', '')

    # Telemetry settings
    INTERVAL_SECONDS: int = max(
        _MIN_INTERVAL_SECONDS,
        int(os.getenv('SIMULATOR_INTERVAL_SECONDS', '5'))
    )
    REQUEST_TIMEOUT_SECONDS: int = int(os.getenv('SIMULATOR_TIMEOUT_SECONDS', '10'))
    MAX_RETRIES: int = int(os.getenv('SIMULATOR_MAX_RETRIES', '2'))
    RETRY_BACKOFF_SECONDS: float = float(os.getenv('SIMULATOR_RETRY_BACKOFF', '2.0'))

    # Simulator identity
    DEVICE_ID_PREFIX: str = os.getenv('SIMULATOR_DEVICE_PREFIX', 'SIM-ICU')
    MODE: str = os.getenv('SIMULATOR_MODE', 'development')

    # Vitals submission endpoint (discovered from project audit)
    # POST /vitals/patient/{patient_id}/submit
    VITALS_SUBMIT_PATH: str = '/vitals/patient/{patient_id}/submit'
    # GET /api/v1/patients (list patients)
    PATIENTS_LIST_PATH: str = '/api/v1/patients'
    # POST /api/v1/auth/login
    AUTH_LOGIN_PATH: str = '/api/v1/auth/login'

    # Clinical validation ranges (matching the existing backend validators)
    VALID_RANGES = {
        'heart_rate': (20, 300),
        'respiratory_rate': (4, 80),
        'systolic_bp': (40, 300),
        'temperature': (25.0, 45.0),
    }

    @classmethod
    def vitals_url(cls, patient_id: int) -> str:
        """Build the full URL for submitting vitals for a specific patient."""
        path = cls.VITALS_SUBMIT_PATH.format(patient_id=patient_id)
        return f"{cls.API_BASE_URL.rstrip('/')}{path}"

    @classmethod
    def patients_url(cls) -> str:
        """Build the full URL for listing patients."""
        return f"{cls.API_BASE_URL.rstrip('/')}{cls.PATIENTS_LIST_PATH}"

    @classmethod
    def auth_url(cls) -> str:
        """Build the full URL for authentication."""
        return f"{cls.API_BASE_URL.rstrip('/')}{cls.AUTH_LOGIN_PATH}"

    @classmethod
    def summary(cls) -> dict:
        """Return a safe summary of configuration (no secrets)."""
        return {
            'api_base_url': cls.API_BASE_URL,
            'interval_seconds': cls.INTERVAL_SECONDS,
            'timeout_seconds': cls.REQUEST_TIMEOUT_SECONDS,
            'max_retries': cls.MAX_RETRIES,
            'device_prefix': cls.DEVICE_ID_PREFIX,
            'mode': cls.MODE,
            'auth_username': cls.AUTH_USERNAME if cls.AUTH_USERNAME else '(not set — using local dev fallback)',
        }
