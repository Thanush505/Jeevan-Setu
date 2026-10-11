# Telemetry API Documentation

## ⚠ SIMULATED ICU TELEMETRY — DEVELOPMENT / TESTING ONLY

This document describes the existing Jeevan Setu backend API endpoint used by the
telemetry simulator to submit vital signs. The simulator does NOT create new endpoints —
it uses the existing transactional vital submission pipeline.

---

## Endpoint

**POST** `/vitals/patient/{patient_id}/submit`

This is the **Core Clinical Data Flow** endpoint that performs:
1. Patient existence verification
2. Vital sign validation (4 parameters)
3. EWS calculation (via `services.ews_service`)
4. Clinical decision evaluation (via `services.decision_service`)
5. Transactional database persistence (vitals → ews_scores → recommendations → alerts)
6. Critical alert generation with duplicate suppression
7. Audit logging

### URL Parameters

| Parameter    | Type | Required | Description           |
|-------------|------|----------|-----------------------|
| `patient_id` | int  | Yes      | Existing patient ID   |

### Request Headers

```
Content-Type: application/json
Accept: application/json
Authorization: Bearer <jwt-token>   (optional in local dev mode)
```

**Authentication Note:**  
When the simulator runs on `127.0.0.1` / `localhost` and the backend is in development
mode, the `permission_required` decorator falls back to the admin user automatically.
For LAN or production use, a valid JWT is required (obtained via `POST /api/v1/auth/login`).

### Request Body (JSON)

```json
{
    "heart_rate": 75.0,
    "respiratory_rate": 16.0,
    "systolic_bp": 120.0,
    "temperature": 36.8
}
```

| Field              | Type  | Required | Range       | Unit         |
|-------------------|-------|----------|-------------|--------------|
| `heart_rate`       | float | Yes      | 20 – 300    | bpm          |
| `respiratory_rate` | float | Yes      | 4 – 80      | breaths/min  |
| `systolic_bp`      | float | Yes      | 40 – 300    | mmHg         |
| `temperature`      | float | Yes      | 25.0 – 45.0 | °C           |

### Success Response (HTTP 201)

```json
{
    "success": true,
    "message": "Vitals recorded. EWS: 0 (Stable)",
    "data": {
        "patient_id": 1,
        "vital_id": 142,
        "vitals": {
            "respiratory_rate": 16.0,
            "heart_rate": 75.0,
            "systolic_bp": 120.0,
            "temperature": 36.8
        },
        "scores": {
            "respiratory_rate": 0,
            "heart_rate": 0,
            "systolic_bp": 0,
            "temperature": 0
        },
        "total_score": 0,
        "condition": "Stable",
        "recommendation": "Fit for HDU Transfer",
        "abnormal_parameters": [],
        "recorded_at": null
    }
}
```

### Error Responses

| Code | Meaning                                  |
|------|------------------------------------------|
| 401  | Authentication required (missing/invalid JWT) |
| 403  | Permission denied (role lacks `record_vitals`) |
| 404  | Patient not found                         |
| 422  | Validation error (missing/out-of-range values) |
| 500  | Internal server error                     |

**422 Example:**
```json
{
    "success": false,
    "errors": ["Heart Rate must be between 20 and 300."],
    "error": "Heart Rate must be between 20 and 300."
}
```

---

## Authentication Endpoint

**POST** `/api/v1/auth/login`

### Request Body
```json
{
    "username": "nurse_rekha",
    "password": "nurse123"
}
```

### Success Response (HTTP 200)
```json
{
    "success": true,
    "data": {
        "token": "eyJhbGciOiJIUzI...",
        "token_type": "Bearer",
        "expires_in": 86400,
        "user": {
            "id": 4,
            "role": "nurse",
            "permissions": ["view_patients", "record_vitals", ...]
        }
    }
}
```

---

## Patient List Endpoint

**GET** `/api/v1/patients`

### Query Parameters

| Parameter | Default    | Description                |
|-----------|-----------|----------------------------|
| `status`  | `admitted` | Filter by patient status   |
| `limit`   | `20`       | Max results                |

### Success Response (HTTP 200)
```json
{
    "success": true,
    "data": {
        "patients": [
            {
                "patient_id": 1,
                "name": "Rajesh Kumar",
                "ward_type": "ICU",
                "bed_number": "ICU-B01",
                "patient_code": "UHID-2026-00001"
            }
        ]
    }
}
```

---

## Data Flow

```
Simulator (raw vitals only)
    │
    │  POST /vitals/patient/{id}/submit
    ▼
Flask Backend
    │
    ├── Validate 4 parameters
    ├── Calculate EWS (scoring_engine.py / ews_service.py)
    ├── Evaluate decision (decision_service.py)
    ├── Save vitals → ews_scores → recommendations (transactional)
    ├── Generate alerts if critical (alert_engine.py)
    └── Write audit log
    │
    ▼
MySQL Database (vitals, ews_scores, recommendations, alerts, audit_logs)
    │
    ▼
Doctor / Nurse / Attendant Portals, Chatbot, Reports
```
