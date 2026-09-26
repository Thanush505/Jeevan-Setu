# Core Clinical Data Flow — Implementation Plan

## Background

After thorough inspection of **42 files** across the existing project, the Jeevan Setu backend is already ~80% complete. The project has:

- ✅ Flask app with blueprints, RBAC, JWT auth, Flask-Login
- ✅ MySQL schema with all tables (`vitals`, `ews_scores`, `recommendations`, `alerts`, `decisions`, `explanations`)
- ✅ `modules/scoring_engine.py` — **EWS scoring thresholds ALREADY EXIST** (see below)
- ✅ `modules/decision_engine.py` — Full ward-aware decision logic
- ✅ `routes/vitals_routes.py` — POST/GET vitals endpoints already implemented
- ✅ `models/` — All models (Vitals, EWSScore, Recommendation, Alert, Decision)
- ✅ `utils/decorators.py` — RBAC with `permission_required('record_vitals')` etc.
- ✅ `utils/validators.py` — Clinical input range validation
- ✅ `database/db.py` — Transaction context manager
- ⚠️ Frontend pages are **static HTML prototypes** (not wired to API)

## Existing EWS Threshold Table (FOUND)

> [!IMPORTANT]
> The approved EWS scoring thresholds **already exist** in [`scoring_engine.py`](file:///d:/Major_Project/JSA-1/JEEVAN_SETU/modules/scoring_engine.py#L10-L31):

| Parameter | Score 0 | Score 1 | Score 2 | Score 3 |
|---|---|---|---|---|
| Heart Rate | 51–90 | 41–50 or 91–110 | 111–130 | ≤40 or ≥131 |
| Systolic BP | 101–199 | 81–100 | 71–80 | ≤70 or ≥200 |
| Respiratory Rate | 12–20 | 9–11 | 21–24 | ≤8 or ≥25 |
| Temperature | 36.1–38.0 | 35.1–36.0 or 38.1–39.0 | 39.1+ | ≤35.0 |

These are the project's approved thresholds. **No external medical system (NEWS, MEWS) is being substituted.**

---

## What Needs to Be Done

The existing backend has the infrastructure but is **missing the user-request's specific simplified clinical flow** connecting the nurse's 4-parameter submission to the specified 3-tier decision rule:

| Total Score | Condition | Recommendation |
|---|---|---|
| 0–2 | Stable | Fit for HDU Transfer |
| 3–4 | Moderate Risk | Re-evaluate |
| ≥5 | Critical | Keep in ICU |

The existing `decision_engine.py` has a more complex ward-aware rule set. We need a **dedicated EWS service** and **decision service** as specified, plus **frontend wiring**.

---

## Proposed Changes

### Component 1: EWS Service

#### [NEW] [`services/ews_service.py`](file:///d:/Major_Project/JSA-1/JEEVAN_SETU/services/ews_service.py)

Dedicated service wrapping the existing `scoring_engine.py` with the 4-parameter interface requested:

- `calculate_respiratory_rate_score(value)` → uses existing `EWS_RANGES['respiratory_rate']`
- `calculate_heart_rate_score(value)` → uses existing `EWS_RANGES['heart_rate']`
- `calculate_systolic_bp_score(value)` → uses existing `EWS_RANGES['blood_pressure_sys']`
- `calculate_temperature_score(value)` → uses existing `EWS_RANGES['temperature']`
- `calculate_ews(rr, hr, sbp, temp)` → returns the full structured result with `abnormal_parameters`

Delegates to `scoring_engine.calculate_parameter_score()` — **no threshold duplication**.

---

### Component 2: Decision Service

#### [NEW] [`services/decision_service.py`](file:///d:/Major_Project/JSA-1/JEEVAN_SETU/services/decision_service.py)

Implements the specification's 3-tier rule:
```python
0 ≤ score ≤ 2  → condition="Stable",        recommendation="Fit for HDU Transfer"
3 ≤ score ≤ 4  → condition="Moderate Risk",  recommendation="Re-evaluate"
score ≥ 5      → condition="Critical",       recommendation="Keep in ICU"
```

Separate from database/route logic.

---

### Component 3: Vital Submission Endpoint

#### [MODIFY] [`routes/vitals_routes.py`](file:///d:/Major_Project/JSA-1/JEEVAN_SETU/routes/vitals_routes.py)

Add a new **patient-scoped endpoint** as specified:

`POST /api/v1/vitals/patient/<patient_id>/submit`

This endpoint will:
1. Authenticate user (existing `permission_required('record_vitals')`)
2. Verify patient exists
3. Validate all 4 parameters (required + range check)
4. Call `ews_service.calculate_ews()`
5. Call `decision_service.evaluate()`
6. Use `db.transaction()` to atomically save vitals → ews_scores → recommendation → alerts
7. Audit log
8. Return the complete structured response per spec

Also add:
- `GET /api/v1/vitals/patient/<patient_id>/latest-status` — latest vitals + scores + condition + recommendation
- `GET /api/v1/vitals/patient/<patient_id>/history` — historical records with scores

> [!NOTE]
> The existing `POST /api/v1/vitals/` endpoint will NOT be removed. The new endpoint provides the simplified 4-parameter flow alongside it.

---

### Component 4: Database

#### No Schema Changes Required

The existing tables already have all needed columns:

- **`vitals`**: `heart_rate`, `blood_pressure_sys`, `respiratory_rate`, `temperature`, `ews_score`, `recorded_by`, `recorded_at`
- **`ews_scores`**: `hr_score`, `bp_score`, `rr_score`, `temp_score`, `total_score`, `risk_level`
- **`recommendations`**: `recommendation_text`, `score`, `reason`, `from_ward`, `to_ward`
- **`alerts`**: `alert_type`, `title`, `message`, `parameter`, `value`, `threshold`

No migration needed.

---

### Component 5: Frontend Integration

#### [MODIFY] [`Nurse/Nurse_enter_vitals/code.html`](file:///d:/Major_Project/JSA-1/Jeevan_setu_frontend/Nurse/Nurse_enter_vitals/code.html)

Replace the simulated `setTimeout` save with a real `fetch()` API call to the new endpoint. After successful response:
- Display EWS score, condition, recommendation in a results panel
- Add `id` attributes to all input fields for reliable DOM access
- Add a results display section showing scores

#### [MODIFY] [`Nurse/Nurse_dashboard/code.html`](file:///d:/Major_Project/JSA-1/Jeevan_setu_frontend/Nurse/Nurse_dashboard/code.html)

Wire the dashboard's patient table to fetch live data from `GET /api/v1/vitals/patient/{id}/latest-status`. Add 10-second auto-refresh polling.

#### [MODIFY] [`Doctor/Doctor_dashboard_/code.html`](file:///d:/Major_Project/JSA-1/Jeevan_setu_frontend/Doctor/Doctor_dashboard_/code.html)

Wire the ICU patient overview table to fetch latest vitals/EWS from the API. Add auto-refresh.

#### [MODIFY] [`Attendant/patient_update_mobile_view_replica/code.html`](file:///d:/Major_Project/JSA-1/Jeevan_setu_frontend/Attendant/patient_update_mobile_view_replica/code.html)

Wire to the attendant API for simplified patient status (Stable/Moderate/Critical). Attendant only sees permitted data per existing RBAC.

---

### Component 6: Tests

#### [NEW] [`tests/test_core_clinical_flow.py`](file:///d:/Major_Project/JSA-1/JEEVAN_SETU/tests/test_core_clinical_flow.py)

20 test cases covering:
1. Valid vital submission (all 4 params)
2–5. Missing individual parameters
6. Invalid numeric values
7. Unknown patient
8. Unauthorized user
9. Nurse can submit
10. Attendant cannot submit
11. Doctor can submit (existing RBAC allows `record_vitals` for doctor role)
12. Individual score calculations (RR, HR, SBP, Temp)
13. Total score calculation
14–16. Decision rule: 0–2 → Stable, 3–4 → Moderate, ≥5 → Critical
17. Database persistence verification
18. Latest patient data retrieval
19. Historical records retrieval
20. Transaction rollback on failure

---

## Open Questions

> [!IMPORTANT]
> **Temperature Unit**: The frontend form shows `°F` but the backend scoring engine uses `°C` thresholds. The implementation will use **°C** (matching the database schema and scoring engine). Should the frontend convert °F→°C, or should the label be changed to °C?

> [!NOTE]
> **Existing 6-parameter vs 4-parameter**: The existing system supports 6+ vital parameters (HR, RR, SBP, Temp, SpO2, Consciousness, etc.). The new simplified endpoint requires only 4 parameters (HR, RR, SBP, Temp) as specified. The existing full-parameter endpoint will remain available. The new endpoint scores only the 4 specified parameters.

---

## Verification Plan

### Automated Tests
```bash
cd d:\Major_Project\JSA-1\JEEVAN_SETU
python -m pytest tests/test_core_clinical_flow.py -v
```

### Manual Verification
1. Start Flask backend (`python app.py`)
2. Open nurse enter vitals page → enter 4 vitals → submit → verify EWS result
3. Check MySQL for persisted records (`vitals`, `ews_scores`, `recommendations`)
4. Open doctor dashboard → verify same EWS score displayed
5. Open attendant view → verify only simplified status shown
6. Submit vitals again → verify history appends (no overwrite)
