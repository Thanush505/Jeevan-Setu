"""
telemetry_simulator/client.py — HTTP client for the Jeevan Setu backend.

Handles:
    - JWT authentication via POST /api/v1/auth/login
    - Patient listing via GET /api/v1/patients
    - Vital submission via POST /vitals/patient/{patient_id}/submit
    - Error handling, timeouts, and retry logic

DOES NOT compute EWS, risk levels, or clinical decisions.
"""

import time
from typing import Optional, Tuple, List

import requests

from config import SimulatorConfig
from logger import get_logger
from models import VitalReading

logger = get_logger()


class BackendClient:
    """
    REST client for the Jeevan Setu Flask backend.

    Supports optional JWT authentication. When credentials are not configured
    and the simulator is running on the same machine as Flask, the backend's
    local-development fallback (decorators.py) will authorize the request.
    """

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        self._jwt_token: Optional[str] = None

    # ───────────────────── Authentication ─────────────────────

    def authenticate(self) -> bool:
        """
        Obtain a JWT token from the backend using configured credentials.

        Returns True if authentication succeeded or was unnecessary (no credentials set).
        Returns False on failure.
        """
        username = SimulatorConfig.AUTH_USERNAME
        password = SimulatorConfig.AUTH_PASSWORD

        if not username or not password:
            logger.info("No auth credentials configured — relying on local dev fallback.")
            return True

        url = SimulatorConfig.auth_url()
        logger.info("Authenticating as '%s' at %s", username, url)

        try:
            resp = self._session.post(
                url,
                json={'username': username, 'password': password},
                timeout=SimulatorConfig.REQUEST_TIMEOUT_SECONDS,
            )

            if resp.status_code == 200:
                data = resp.json()
                token = data.get('data', {}).get('token')
                if token:
                    self._jwt_token = token
                    self._session.headers['Authorization'] = f'Bearer {token}'
                    role = data.get('data', {}).get('user', {}).get('role', 'unknown')
                    logger.info("Authenticated successfully (role: %s).", role)
                    return True
                else:
                    logger.error("Auth response missing token: %s", data)
                    return False
            else:
                logger.error("Authentication failed: HTTP %d — %s", resp.status_code, resp.text[:200])
                return False

        except requests.ConnectionError:
            logger.error("Authentication failed: Cannot connect to %s", url)
            return False
        except requests.Timeout:
            logger.error("Authentication failed: Request timed out.")
            return False
        except Exception as e:
            logger.error("Authentication failed: %s", e)
            return False

    # ───────────────────── Patient Listing ─────────────────────

    def fetch_patients(self) -> List[dict]:
        """
        Fetch the list of admitted patients from the backend.

        Returns:
            List of patient dicts with at least 'patient_id' and 'name'.
        """
        url = SimulatorConfig.patients_url()
        logger.info("Fetching patient list from %s", url)

        try:
            resp = self._session.get(
                url,
                params={'status': 'admitted', 'limit': 50},
                timeout=SimulatorConfig.REQUEST_TIMEOUT_SECONDS,
            )

            if resp.status_code == 200:
                data = resp.json()
                patients = data.get('data', [])
                if isinstance(patients, dict) and 'patients' in patients:
                    patients = patients['patients']
                logger.info("Retrieved %d patient(s).", len(patients))
                return patients
            else:
                logger.error("Failed to fetch patients: HTTP %d — %s", resp.status_code, resp.text[:200])
                return []

        except requests.ConnectionError:
            logger.error("Cannot connect to backend at %s", url)
            return []
        except requests.Timeout:
            logger.error("Patient list request timed out.")
            return []
        except Exception as e:
            logger.error("Failed to fetch patients: %s", e)
            return []

    # ───────────────────── Vital Submission ─────────────────────

    def submit_vitals(self, reading: VitalReading) -> Tuple[bool, dict]:
        """
        Submit a vital reading to the existing backend endpoint.

        Uses POST /vitals/patient/{patient_id}/submit which triggers
        the full existing pipeline: validation → EWS → decision → alerts.

        Args:
            reading: VitalReading instance with raw values.

        Returns:
            (success: bool, response_data: dict)
        """
        # Pre-flight validation
        errors = reading.validate(SimulatorConfig.VALID_RANGES)
        if errors:
            logger.error("Validation failed before submission: %s", errors)
            return False, {'error': 'Local validation failed', 'details': errors}

        url = SimulatorConfig.vitals_url(reading.patient_id)
        payload = reading.to_payload()

        for attempt in range(1, SimulatorConfig.MAX_RETRIES + 1):
            try:
                resp = self._session.post(
                    url,
                    json=payload,
                    timeout=SimulatorConfig.REQUEST_TIMEOUT_SECONDS,
                )

                resp_data = {}
                try:
                    resp_data = resp.json()
                except ValueError:
                    resp_data = {'raw': resp.text[:300]}

                if resp.status_code == 201:
                    return True, resp_data
                elif resp.status_code == 401:
                    logger.warning("HTTP 401 — Token may have expired. Re-authenticating...")
                    if self.authenticate():
                        continue  # Retry with new token
                    return False, resp_data
                elif resp.status_code == 422:
                    # Validation error from backend — do not retry
                    logger.error("HTTP 422 — Validation error: %s", resp_data.get('error', resp_data))
                    return False, resp_data
                else:
                    logger.error(
                        "HTTP %d — %s (attempt %d/%d)",
                        resp.status_code,
                        resp_data.get('error', str(resp_data)[:100]),
                        attempt,
                        SimulatorConfig.MAX_RETRIES,
                    )
                    if attempt < SimulatorConfig.MAX_RETRIES:
                        time.sleep(SimulatorConfig.RETRY_BACKOFF_SECONDS)
                        continue
                    return False, resp_data

            except requests.ConnectionError:
                logger.error(
                    "Connection refused (attempt %d/%d). Is Flask running at %s?",
                    attempt, SimulatorConfig.MAX_RETRIES, SimulatorConfig.API_BASE_URL,
                )
                if attempt < SimulatorConfig.MAX_RETRIES:
                    time.sleep(SimulatorConfig.RETRY_BACKOFF_SECONDS)
                continue
            except requests.Timeout:
                logger.error(
                    "Request timed out (attempt %d/%d).",
                    attempt, SimulatorConfig.MAX_RETRIES,
                )
                if attempt < SimulatorConfig.MAX_RETRIES:
                    time.sleep(SimulatorConfig.RETRY_BACKOFF_SECONDS)
                continue
            except Exception as e:
                logger.error("Unexpected error: %s (attempt %d/%d)", e, attempt, SimulatorConfig.MAX_RETRIES)
                if attempt < SimulatorConfig.MAX_RETRIES:
                    time.sleep(SimulatorConfig.RETRY_BACKOFF_SECONDS)
                continue

        return False, {'error': 'All retry attempts exhausted'}

    def close(self):
        """Close the underlying HTTP session."""
        self._session.close()
