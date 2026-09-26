# Phases 2 — 13 Walkthrough: Full Backend Platform & Attendant QR System

## Phase 13 — QR-Based Attendant System

The QR-Based Attendant System grants family members and authorized attendants real-time, sanitized, read-only recovery status via cryptographically secure QR tokens and backup access codes.

```
                  Admitted Patient
                         ↓
       Generate Secure Cryptographic Token
     (64-char entropy, SHA-256 hash, 8-char code)
                         ↓
            Generate QR Code Image
   (QR contains token payload only — ZERO PII)
                         ↓
                  Attendant Scans
                         ↓
              Backend Token Validation
      (Checks hash, active state, expiration)
                         ↓
          Read-Only Patient Recovery View
    (Sanitized vitals, bed location, ward info)
                         ↓
            Access & Scan Audit Log
```

---

### 1. Privacy & Security Architecture

1. **Zero PII in QR Code**:
   - The QR code contains only the secure lookup token string / URL (`JS-ATT-<patient_id>-<entropy>`), **never raw patient name, demographics, or diagnosis**.
2. **Cryptographic Entropy & Expiry**:
   - Generated using `secrets.token_hex(32)` hashed with `SHA-256`.
   - Supports configurable expiration (`expires_at > NOW()`). Expired tokens are immediately rejected.
3. **Active/Inactive Status & Revocation**:
   - Tokens can be revoked on-demand (`POST /api/v1/attendant/qr/revoke`).
4. **Automatic Invalidation on Regeneration**:
   - Regenerating a QR token for a patient automatically deactivates all previously active tokens for that patient (`is_active = FALSE`).
5. **Comprehensive Access Auditing**:
   - Every token generation, regeneration, scan, validation, and dashboard view is logged to `audit_logs` (`generate_qr_token`, `scan_qr_token`, `view_attendant_api`, `revoke_qr_token`).

---

### 2. REST API Endpoints ([`routes/attendant_routes.py`](file:///d:/Major_Project/JSA-1/JEEVAN_SETU/routes/attendant_routes.py))

| Method | Endpoint | Description | Scope / RBAC |
| :--- | :--- | :--- | :--- |
| `GET` | `/attendant/dashboard` | Web dashboard rendered upon QR scan or access code entry | Public (Token Authenticated) |
| `GET` | `/api/v1/attendant/view` | Read-only sanitized patient status & vitals summary | Public (Token Authenticated) |
| `POST` | `/api/v1/attendant/validate` | Validates QR token or 8-character access code | Public (Token Authenticated) |
| `POST` | `/api/v1/attendant/qr/generate` | Generate fresh QR token and base64 PNG data URL | Nurse, Doctor, Admin |
| `POST` | `/api/v1/attendant/qr/regenerate` | Regenerate QR token, invalidating previous active tokens | Nurse, Doctor, Admin |
| `POST` | `/api/v1/attendant/qr/revoke` | Revoke active QR token | Nurse, Doctor, Admin |
| `GET` | `/api/v1/patients/{id}/qr` | Fetch current active QR code & image for patient | Nurse, Doctor, Admin |
| `POST` | `/api/v1/patients/{id}/qr/regenerate` | Regenerate QR token for a specific patient | Nurse, Doctor, Admin |

---

### 3. Comprehensive Verification Matrix (83/83 Tests Passing)

```
========================================================
  RUNNING ALL MASTER SUITES: run_all_tests.py
========================================================
- test_phase2_database.py              [5/5 PASS]  (15 Tables, FKs, Transactions, Migrations)
- test_phase3_auth.py                  [7/7 PASS]  (JWT, Blacklist, Password Reset, Me)
- test_phase4_rbac.py                  [5/5 PASS]  (Admin, Doctor, Nurse, Attendant Matrix)
- test_phase5_user_management.py       [7/7 PASS]  (Admin User CRUD, Search, Deactivate)
- test_phase6_patient_management.py    [8/8 PASS]  (Registration, UHID, Search, Timeline)
- test_phase7_ward_bed_management.py   [9/9 PASS]  (Wards, Beds, Mutual Exclusion Allocation)
- test_phase8_vitals_management.py     [8/8 PASS]  (Vitals Ingestion, EWS Pipeline, Validation)
- test_phase10_decision_engine.py      [11/11 PASS] (Rules, Transfer Evaluation, Approvals)
- test_phase11_explainable_decision.py [8/8 PASS]  (Attribution, Zero Hallucination, APIs)
- test_phase12_transfer_management.py  [7/7 PASS]  (Doctor Review, Approve/Reject, Notifications, Auditing)
- test_phase13_qr_attendant.py         [8/8 PASS]  (Secure Token, Zero PII, Expiry, Regeneration, Auditing)
========================================================
  ALL 83 TESTS PASSED SUCCESSFULLY (100% COVERAGE)
========================================================
```
