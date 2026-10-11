# Jeevan Setu — ICU Telemetry Simulator

## ⚠ SIMULATED ICU TELEMETRY — DEVELOPMENT / TESTING ONLY

This simulator is a **software-based ICU multi-parameter bedside monitor** for development
and testing of the Jeevan Setu system. It generates simulated physiological readings and
submits them to the existing Flask backend.

**This is NOT a real medical device. Do NOT use for real clinical care.**

---

## 1. Purpose

Generate continuous simulated vital signs (HR, RR, SBP, Temperature) and feed them into
the existing Jeevan Setu backend so the complete pipeline is exercised:

```
SIMULATOR → raw vitals → Flask → Validation → EWS → Decision → Alerts → Portals
```

The simulator **never** calculates EWS, risk levels, or clinical decisions.
All scoring is performed exclusively by the existing Jeevan Setu backend.

---

## 2. Architecture

```
┌─────────────────────────────┐
│  Telemetry Simulator        │
│  (Python script)            │
│  Generates: HR, RR, SBP, T │
└─────────────┬───────────────┘
              │ POST /vitals/patient/{id}/submit
              ▼
┌─────────────────────────────┐
│  Jeevan Setu Flask Backend  │
│  - Vital validation         │
│  - EWS calculation          │
│  - Decision engine          │
│  - Alert generation         │
│  - Audit logging            │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  MySQL Database             │
│  vitals, ews_scores,        │
│  recommendations, alerts    │
└─────────────┬───────────────┘
              ▼
       ┌──────┼──────┐
       ▼      ▼      ▼
    Doctor  Nurse  Attendant
    Portal  Portal  Portal
```

---

## 3. Installation

```bash
# Navigate to the simulator directory
cd Jeevan-Setu-Final/telemetry_simulator

# Create virtual environment (optional but recommended)
python -m venv .venv
.venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
copy .env.example .env
# Edit .env if needed (defaults work for local testing)
```

---

## 4. Configuration

All settings are loaded from environment variables (`.env` file):

| Variable                     | Default                    | Description                        |
|------------------------------|----------------------------|------------------------------------|
| `SIMULATOR_API_BASE_URL`     | `http://127.0.0.1:5000`   | Flask backend URL                  |
| `SIMULATOR_AUTH_USERNAME`    | *(empty)*                  | Login username (optional locally)  |
| `SIMULATOR_AUTH_PASSWORD`    | *(empty)*                  | Login password (optional locally)  |
| `SIMULATOR_INTERVAL_SECONDS` | `5`                        | Seconds between readings           |
| `SIMULATOR_TIMEOUT_SECONDS`  | `10`                       | HTTP request timeout               |
| `SIMULATOR_MAX_RETRIES`      | `2`                        | Retry attempts on failure          |
| `SIMULATOR_DEVICE_PREFIX`    | `SIM-ICU`                  | Device ID prefix                   |

**Note:** When running on `127.0.0.1` with the backend in development mode, authentication
credentials are optional — the backend's local dev fallback handles authorization.

---

## 5. Starting Flask Backend

```bash
cd Jeevan-Setu-Final/JEEVAN_SETU
python app.py
```

Verify it's running: `http://127.0.0.1:5000`

---

## 6. Starting the Simulator

### Interactive Mode
```bash
cd Jeevan-Setu-Final/telemetry_simulator
python simulator.py
```

You'll be prompted to select a patient, scenario, and interval.

### Command-Line Mode
```bash
python simulator.py --patient-id 1 --scenario STABLE --interval 5
python simulator.py --patient-id 3 --scenario CRITICAL --interval 2
python simulator.py --patient-id 1 --scenario MANUAL --hr 44 --rr 44 --sbp 44 --temp 40
```

---

## 7. Selecting a Patient

The simulator fetches the existing admitted patients from the backend:

```
Available Patients:
──────────────────────────────────────────────────
  1. Rajesh Kumar (ID: 1, ICU, Bed: ICU-B01) UHID-2026-00001
  2. Amit Verma (ID: 2, ICU, Bed: ICU-B02) UHID-2026-00002
  ...
```

Select by number. The simulator operates on existing patients only — it never creates new ones.

---

## 8. Selecting a Scenario

| # | Scenario               | Description                                    |
|---|------------------------|------------------------------------------------|
| 1 | **STABLE**             | Normal resting vitals with small drift          |
| 2 | **GRADUAL_DETERIORATION** | Gradual migration toward abnormal            |
| 3 | **CRITICAL**           | Rapid deterioration to critical values          |
| 4 | **RECOVERY**           | Return from abnormal toward stable              |
| 5 | **MANUAL**             | Enter exact values manually                     |

---

## 9. Stopping the Simulator

Press **CTRL+C** to stop gracefully. The simulator will:
- Stop generating new readings
- Finish the current HTTP request
- Close network resources
- Print a summary and exit cleanly

---

## 10. Scenario Details

### STABLE
Small physiological variations around normal adult resting values:
- HR: ~70-80 bpm
- RR: ~14-18 breaths/min
- SBP: ~115-125 mmHg
- Temp: ~36.5-37.0 °C

### GRADUAL DETERIORATION
Four phases over ~40+ readings:
1. **Phase 1** (ticks 1-12): Mostly stable
2. **Phase 2** (ticks 13-24): Mild deviations
3. **Phase 3** (ticks 25-36): Progressive abnormality
4. **Phase 4** (ticks 37+): Severe abnormal readings

### CRITICAL
Rapid worsening reaching severely abnormal territory within ~10-15 readings:
- HR rises above 130+
- RR rises above 30+
- SBP drops below 70
- Temp rises above 39+

### RECOVERY
Starts with abnormal values and gradually returns to near-normal over ~25-35 readings.

### MANUAL
Send specific exact values for reproducing known test cases:
```bash
python simulator.py --patient-id 1 --scenario MANUAL --hr 44 --rr 44 --sbp 44 --temp 40
```

---

## 11. Troubleshooting

| Error                | Cause                                | Fix                                     |
|---------------------|--------------------------------------|------------------------------------------|
| `Connection refused` | Flask backend not running            | Start Flask: `python app.py`             |
| `HTTP 401`           | JWT expired or invalid               | Set credentials in `.env` or run locally |
| `HTTP 403`           | Role lacks `record_vitals` permission | Use nurse/doctor/admin credentials       |
| `HTTP 404`           | Patient ID not found                 | Verify patient exists and is admitted    |
| `HTTP 422`           | Values out of valid range            | Check range limits in TELEMETRY_API.md   |
| `HTTP 500`           | Backend error                        | Check Flask logs in `JEEVAN_SETU/logs/`  |
| `No patients found`  | Database empty or backend down       | Verify MySQL is running with seed data   |

---

## 12. LAN Testing

For testing with mobile devices on the same network:

1. Set Flask to bind to all interfaces: `HOST=0.0.0.0` (already configured)
2. Find your PC's LAN IP (e.g., `172.20.10.2`)
3. Update simulator `.env`:
   ```
   SIMULATOR_API_BASE_URL=http://172.20.10.2:5000
   ```
4. Start the simulator

---

## 13. Running Tests

```bash
cd Jeevan-Setu-Final/telemetry_simulator
python -m pytest tests/ -v
```

---

## 14. File Structure

```
telemetry_simulator/
├── simulator.py          # Main entry point & CLI
├── config.py             # Environment configuration
├── client.py             # HTTP client for Flask backend
├── scenarios.py          # Simulation scenario engines
├── models.py             # Data models (VitalReading, SimulatorStatus)
├── logger.py             # Structured logging
├── requirements.txt      # Python dependencies
├── .env.example          # Configuration template
├── README.md             # This file
├── TELEMETRY_API.md      # API documentation
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_scenarios.py
    ├── test_validation.py
    ├── test_client.py
    └── test_simulator.py
```

---

## 15. Important Disclaimer

> **⚠ SIMULATED ICU TELEMETRY — DEVELOPMENT / TESTING ONLY**
>
> This simulator generates synthetic physiological data for software testing purposes.
> It is NOT a certified medical device. Do NOT use simulated readings for real clinical
> decisions. Jeevan Setu remains a clinical decision-support prototype.
