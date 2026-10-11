# 📖 JEEVAN SETU (जीवन सेतु) — Master Codebase & Architecture Specification

> **Document Purpose**: This document (`full.md`) serves as the **authoritative, 100% complete technical blueprint, feature inventory, audit log, and progress report** for the **Jeevan Setu** Clinical Decision Support and Patient Management System. Any AI agent, software architect, or clinical engineer reading this file will understand the entire scope of work done, architectural conventions, database schemas, frontend portals, API contracts, telemetry simulator, and future roadmap without needing to infer or re-investigate.

---

## 🤖 AI Briefing & Continuity Prompt (Copy & Paste for Future AI)

If you are handing this project over to another AI assistant, you can prepend the following prompt:

```text
You are continuing development on "Jeevan Setu", an intelligent Clinical Decision Support System (CDSS) for ICU ↔ HDU critical care monitoring, EWS triage, bedside telemetry simulation, and patient transfers.
Before making any changes or answering questions, read full.md and rules.md in the workspace root.
Key hard rules to observe:
1. Keep all modifications strictly inside "d:\Major_Project\JSF-Web_Broswer_simulator" (and "Jeevan-Setu-Final").
2. The active database must maintain exactly 10 baseline patients (UHID-2026-00001 to UHID-2026-00010). If tests pollute the database, run "python JEEVAN_SETU\database\cleanup_patients.py".
3. Use Vanilla HTML5, CSS (no Tailwind), and JavaScript for the frontend.
4. Server runs on Flask at port 5000 (binds to 0.0.0.0 for dynamic LAN access).
5. Live MySQL database is synced with "schema.sql" and SQLite snapshot "schema.db" via "sync_schema.py".
```

---

## 📊 1. Quantitative Codebase Metrics

| Metric | Measured Value | Notes |
| :--- | :--- | :--- |
| **Total Lines of Code** | **~67,327+ Lines** | Excluding `.venv` & third-party packages |
| **Python Files (`*.py`)** | **166 files** (30,819 lines) | Flask blueprints, models, services, engines, tests |
| **HTML UI Pages (`*.html`)** | **43 complete pages** (24,465 lines) | Admin, Doctor, Nurse, Attendant, Developer portals |
| **JavaScript Scripts (`*.js`)** | **18 modular files** (8,360 lines) | Auto-refresh, alert managers, charts, simulator engine |
| **CSS Style Modules (`*.css`)** | **2 files** (397 lines) | Centralized clinical tokens, glassmorphism, responsive |
| **Database Schema (`*.sql`)** | **7 files** (921 lines) | Live DDL with 27 tables, constraints, indices |
| **Documentation (`*.md`)** | **19 files** (2,365 lines) | Architecture, guides, API specs, SRS, runbooks |
| **Database Tables (MySQL)** | **27 Core Tables** | Fully normalized with foreign keys and cascade rules |
| **Database Snapshot (SQLite)** | **`schema.db` (3.02 MB)** | Synchronized mirror with complete live census |
| **Automated Test Cases** | **407+ Tests** (353 Backend + 54 Simulator) | Covering RBAC, IDOR, EWS, transfers, alerts, simulator |
| **Active Baseline Census** | **10 Patients (Admitted)** | 4 ICU + 6 HDU across 3 Doctors and 3 Nurses |
| **Hospital Bed Matrix** | **58 Beds** | 10 Occupied (Beds 400–409), 48 Available |

---

## 🏛️ 2. Architectural Blueprint & Data Flow

```mermaid
graph TD
    subgraph Client Portals [Frontend - Vanilla HTML5/JS/CSS (43 Pages)]
        ADM[Admin Portal - 12 Pages]
        DOC[Doctor Portal - 14 Pages]
        NUR[Nurse Portal - 12 Pages]
        ATT[Attendant Mobile Portal - 3 Pages]
        DEV[Developer Telemetry GUI - 1 Page]
    end

    subgraph Bedside Telemetry Simulation
        CLI_SIM[Python Telemetry Simulator CLI]
        DEV -->|WebSocket / HTTP Submit| API_VITALS
        CLI_SIM -->|HTTP POST /vitals/patient/:id/submit| API_VITALS
    end

    subgraph Flask Backend Services [Flask 3.0+ on Port 5000]
        API_AUTH[Auth & RBAC Service / JWT 24h]
        API_VITALS[Vitals & Telemetry Ingestion]
        API_EWS[Scoring Engine / EWS 4-Param]
        API_DEC[Clinical Decision & Step-Down Engine]
        API_ALERT[Universal Global Emergency Alert Engine]
        API_TRANS[Atomic Bed Transfer & Locking Pipeline]
        API_AI[Dr. Setu AI - OpenRouter / Gemma 4]
        API_PDF[ReportLab Clinical PDF Engine]
        API_QR[Cryptographic QR Token Engine]
        API_SYNC[Auto-Refresh & Polling Manager]
    end

    subgraph Persistence Layer [Dual-Engine Storage]
        MYSQL[(MySQL Database 'jeevan_setu' - 27 Tables)]
        SQLITE[(SQLite Snapshot 'schema.db' - 3.02 MB)]
    end

    Client Portals -->|REST API / Bearer JWT| Flask Backend Services
    API_AUTH --> MYSQL
    API_VITALS --> API_EWS
    API_EWS --> MYSQL
    API_EWS --> API_ALERT
    API_EWS --> API_DEC
    API_DEC --> API_TRANS
    API_TRANS -->|ACID Transaction / SELECT FOR UPDATE| MYSQL
    API_ALERT -->|Real-Time Popups| Client Portals
    API_AI -->|CCRL Live Queries| MYSQL
    API_PDF --> MYSQL
    API_QR --> MYSQL
    API_SYNC --> Client Portals
    MYSQL -.->|sync_schema.py| SQLITE
```

---

## 📋 3. Complete Feature Inventory & Work Completed Status

### 🟢 Status Key:
- `COMPLETED (100%)`: Fully designed, implemented in backend & frontend, verified with automated tests, and live in production.
- `ACTIVE & OPERATIONAL`: Running continuously in real-time.

---

### Module 1: Patient Census & Admission Management
* **Status**: `COMPLETED (100%)`
* **Backend**: `routes/patient_routes.py`, `models/patient_model.py`, `models/ward_model.py`
* **Frontend**: `Admin/Admin_patient_management/`, `Doctor/Doctor_my_patients/`, `Doctor/Doctor_all_patients/`
* **Key Capabilities**:
  1. **Canonical 10-Patient Census**: Maintains exactly 10 active admitted patients with assigned doctors, nurses, and dedicated beds.
  2. **In-App Admission Modal**: Generates next automatic hospital UHID (`UHID-2026-XXXXX`), assigns ward, filters mutually exclusive available beds, and assigns attending clinician.
  3. **Doctor-Patient Authorization Scoping**: Doctor views only assigned patients; unauthorized access attempts to other patients return `403 Forbidden` with IDOR audit logs.
  4. **Automated Baseline Restoration**: `database/cleanup_patients.py` purges test artifacts (> 10) and restores the canonical 10-patient roster instantly.

---

### Module 2: 4-Parameter Vital Signs Telemetry Engine
* **Status**: `COMPLETED (100%)`
* **Backend**: `routes/vitals_routes.py`, `models/vitals_model.py`, `services/realtime_service.py`
* **Frontend**: `Nurse/Nurse_enter_vitals/`, `Nurse/nurse_patient_monitoring/`, `Doctor/Doctor_dashboard_/`
* **Key Capabilities**:
  1. **4-Parameter Ingestion**:
     - Heart Rate ($HR$): valid range `30` to `220` bpm.
     - Systolic Blood Pressure ($SBP$): valid range `50` to `250` mmHg.
     - Respiratory Rate ($RR$): valid range `6` to `60` breaths/min.
     - Temperature ($Temp$): valid range `32.0`°C to `43.0`°C.
  2. **Time-Series Storage**: Captures historical timelines and latest vitals cache per patient in `vitals` table.
  3. **Real-Time Calculation Hook**: Immediately upon submission, invokes EWS calculation, risk categorization, and emergency alert checks.

---

### Module 3: Early Warning Score (EWS) Scoring Engine
* **Status**: `COMPLETED (100%)`
* **Backend**: `modules/scoring_engine.py`, `services/ews_service.py`, `models/ews_score_model.py`
* **Frontend**: `Doctor/Doctor_ews_calculator/`, `Doctor/Doctor_ews_trends/`, `Nurse/Nurse_ews_calculator/`
* **Clinical Heuristic Matrix**:
  | Vital Sign | Score 3 | Score 2 | Score 1 | Score 0 (Normal) | Score 1 | Score 2 | Score 3 |
  | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
  | **RR (breaths/min)** | $\le 8$ | — | $9 - 11$ | $12 - 20$ | — | $21 - 24$ | $\ge 25$ |
  | **HR (bpm)** | $\le 40$ | — | $41 - 50$ | $51 - 90$ | $91 - 110$ | $111 - 130$ | $\ge 131$ |
  | **SBP (mmHg)** | $\le 90$ | $91 - 100$ | $101 - 110$ | $111 - 219$ | — | — | $\ge 220$ |
  | **Temp (°C)** | $\le 35.0$ | — | $35.1 - 36.0$ | $36.1 - 38.0$ | $38.1 - 39.0$ | $\ge 39.1$ | — |
* **Risk Categorization**:
  - `EWS 0`: Normal
  - `EWS 1 - 4`: Low / Stable
  - `EWS 5 - 6`: Medium / Elevated
  - `EWS >= 7`: High / Critical (immediate ICU admission or retention alert)

---

### Module 4: Explainable Clinical Decision Engine
* **Status**: `COMPLETED (100%)`
* **Backend**: `modules/decision_engine.py`, `modules/explanation_engine.py`, `routes/decision_routes.py`
* **Frontend**: `Doctor/Doctor_transfer_recommendations/`, `Doctor/Doctor_transfer_reports/`
* **Key Capabilities**:
  1. **Step-Down Eligibility**: Determines if an ICU patient can safely step down to HDU when $\text{EWS} \le 4$ consecutively for 4+ hours with stable hemodynamic vitals.
  2. **Step-Up Escalation**: Triggers emergency transfer to ICU when an HDU patient reaches $\text{EWS} \ge 7$ or exhibits acute respiratory distress.
  3. **Feature Importance & Explanations**: Generates feature contribution logs stored in `explanations` table detailing which vital parameter contributed most to the recommendation.

---

### Module 5: Atomic Concurrency-Safe Bed Transfer Approval Pipeline
* **Status**: `COMPLETED (100%)`
* **Backend**: `routes/transfer_routes.py`, `models/transfer_model.py`, `models/bed_management_model.py`
* **Frontend**: `Doctor/Doctor_pending_approvals/`, `Nurse/Nurse_transfers/`, `Admin/Admin_beds_wards/`
* **Key Capabilities**:
  1. **Doctor-Only Approval Guardrail**: Only attending physicians can approve step-down transfers. Nurse interfaces display read-only status and approve attempts by nurses are rejected with `HTTP 403 Forbidden`.
  2. **ACID Transaction with Row Locking**:
     - Locks patient and transfer rows (`FOR UPDATE`).
     - Locates available HDU bed; if none available, cleanly rolls back without state corruption.
     - Frees previous ICU bed (`status = 'available'`).
     - Marks destination HDU bed (`status = 'occupied'`).
     - Updates patient ward & bed number.
     - Emits real-time notification to ward nurses with target bed number.

---

### Module 6: Universal Global Emergency Alerting System
* **Status**: `COMPLETED (100%)`
* **Backend**: `modules/alert_engine.py`, `routes/alert_routes.py`, `models/alert_model.py`
* **Frontend**: `global_alert_manager.js`, `Doctor/global_alert_manager.js`, `Nurse/global_alert_manager.js`
* **Key Capabilities**:
  1. **Omnipresent Modal Alarm**: Non-blocking audio-visual alert modal pops up across **all 14 Doctor pages and 12 Nurse pages** within 3 seconds of a critical event without page reloads.
  2. **Duplicate Suppression**: Suppresses repeated alarms while an unacknowledged critical alert is pending for that patient.
  3. **Clinical Auto-Resolution**: When the patient stabilizes ($\text{EWS} \le 4$), active alerts are automatically marked resolved in MySQL.
  4. **Doctor Acknowledgment Tracking**: Stores timestamp and user ID of the acknowledging clinician in `alerts` table.

---

### Module 7: Prolonged Ready-to-Transfer Monitoring
* **Status**: `COMPLETED (100%)`
* **Backend**: `modules/alert_engine.py`, `services/scheduler.py`
* **Frontend**: `Doctor/Doctor_pending_approvals/`, `Admin/Administrator_dashboard_/`
* **Key Capabilities**:
  1. Tracks the elapsed duration that a stabilized patient has been marked "Ready for HDU Transfer".
  2. If waiting time exceeds threshold (default: 120 minutes), generates a high-priority amber notification to prevent ICU bed blocking.

---

### Module 8: Dr. Setu AI Clinical Assistant (OpenRouter & Gemma 4)
* **Status**: `COMPLETED (100%)`
* **Backend**: `modules/openrouter_service.py`, `modules/chatbot_engine.py`, `routes/chatbot_routes.py`
* **Frontend**: `Doctor/Doctor_patient_summary_ai/`, embedded chatbot widgets across clinical portals
* **Key Capabilities**:
  1. **Model**: Powered by `google/gemma-4-31b-it:free` via OpenRouter API.
  2. **Context-Grounded Clinical Reasoning (CCRL)**: Pulls live patient vitals, medications, EWS trends, and bed assignments to answer clinical questions.
  3. **Structured Clinical Summary**: Generates SOAP-format clinical summaries (Subjective, Objective, Assessment, Plan).

---

### Module 9: Mobile Attendant Access & Permanent QR Code System
* **Status**: `COMPLETED (100%)`
* **Backend**: `routes/attendant_routes.py`, `models/qr_token_model.py`, `models/attendant_model.py`
* **Frontend**: `Attendant/attendant_access.html`, `Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html`
* **Key Capabilities**:
  1. **Permanent Cryptographic Token**: Token format `JS-QR-P{patient_id}-{entropy}` stored in `patient_qr_tokens` table.
  2. **Zero PII Exposure**: QR contains no patient medical data. Scans resolve via backend token validation.
  3. **Mobile Family Replica View**: Displays read-only patient condition (Stable/Observation/Critical), ward location, bed number, and attending physician without exposing complex clinical telemetry or other patients.
  4. **Printable Hospital Badge Passes**: Generated directly from Admin portal.

---

### Module 10: Multi-Patient Clinical ReportLab PDF Engine
* **Status**: `COMPLETED (100%)`
* **Backend**: `modules/report_engine.py`, `routes/report_routes.py`, `models/report_model.py`
* **Frontend**: `Admin/Admin_clinical_reports/`, `Doctor/Doctor_patient_reports/`
* **Key Capabilities**:
  1. **Hospital Header Canvas**: Two-pass ReportLab PDF generation with repeating hospital branding, patient UHID header, and page numbering.
  2. **Multi-Patient Batching**: Generates single-patient discharge summaries or multi-patient census reports.
  3. **Audit Trail Logging**: Every PDF generation and download is recorded in `audit_logs`.

---

### Module 11: Security, RBAC & Cross-Doctor IDOR Protection
* **Status**: `COMPLETED (100%)`
* **Backend**: `utils/auth_middleware.py`, `services/auth_service.py`, `routes/auth_routes.py`
* **Frontend**: `Login/Login.html`
* **Key Capabilities**:
  1. **Bearer JWT Authentication**: 24-hour expiration tokens containing `user_id`, `role`, and permissions.
  2. **Password Security**: Hashed passwords using bcrypt/werkzeug.
  3. **Zero Frontend Filtering / Strict Database Scoping**: Clinician endpoints filter exclusively on `patients.assigned_doctor = current_doctor_id`. Unauthorized access attempts trigger `HTTP 403 Forbidden` and security audit logs (`UNAUTHORIZED_PATIENT_ACCESS_ATTEMPT`).
  4. **Token Blacklist**: Logout blacklists active JWTs in `token_blacklist` table.

---

### Module 12: Real-Time Auto-Refresh & Live Synchronization
* **Status**: `COMPLETED (100%)`
* **Frontend**: `Jeevan_setu_frontend/auto_refresh_manager.js`, `Doctor/auto_refresh_manager.js`, `Nurse/auto_refresh_manager.js`, `Attendant/auto_refresh_manager.js`
* **Key Capabilities**:
  1. Background polling and event notification listener syncs Doctor, Nurse, and Attendant screens every 3–5 seconds.
  2. Updates patient vitals, EWS risk badges, occupied bed counts, and alert banners smoothly without jarring full-page browser reloads.

---

### Module 13: Bedside Telemetry Simulator (CLI + GUI)
* **Status**: `COMPLETED (100%)`
* **CLI Simulator**: `telemetry_simulator/simulator.py`, `client.py`, `scenarios.py`, `config.py`
* **Web GUI Simulator**: `Jeevan_setu_frontend/Developer/Telemetry_Simulator/Telemetry_Simulator.html`
* **Backend Integration**: `routes/developer_routes.py`
* **Key Capabilities**:
  1. **5 Clinical Scenarios**:
     - `stable`: Realistic vital noise within normal ranges.
     - `deterioration`: Progressive worsening towards critical EWS score.
     - `recovery`: Clinical recovery from critical state back to normal.
     - `critical`: Acute physiological crisis triggering emergency alarms.
     - `manual`: User-defined custom vital values.
  2. **CLI Modes**: Interactive console menu and command-line argument mode (`--patient 1 --scenario stable --interval 3`).
  3. **GUI Modes**: Real-time waveform display, scenario selector, broadcast frequency adjustment, and live server response inspector.
  4. **Test Suite**: 54 passing automated tests in `telemetry_simulator/tests/`.

---

### Module 14: Hospital Administration & Resource Utilization
* **Status**: `COMPLETED (100%)`
* **Backend**: `routes/ward_routes.py`, `routes/bed_routes.py`, `routes/analytics_routes.py`
* **Frontend**: `Admin/Administrator_dashboard_/`, `Admin/Admin_beds_wards/`, `Admin/Admin_resource_utilization/`, `Admin/Admin_ews_analytics/`
* **Key Capabilities**:
  1. **Floorplan Bed Matrix**: Live visual representation of ICU-A (20 beds) and HDU-B (20 beds).
  2. **Capacity Pressure Alerts**: Warns hospital management when unit occupancy exceeds $85\%$.
  3. **User Provisioning & Role Management**: Administrative interface to create, update, deactivate, and reset passwords for clinicians and staff.

---

## 🗄️ 4. Complete Database Schema (27 Tables)

The database engine is MySQL 8.0+ (`jeevan_setu`), with a synchronized SQLite snapshot at `schema.db` (3.02 MB).

| # | Table Name | Purpose | Key Columns / Relations |
| :-: | :--- | :--- | :--- |
| **1** | `roles` | System RBAC roles | `role_id` (PK), `name` (admin, doctor, nurse, attendant) |
| **2** | `users` | User credentials & accounts | `user_id` (PK), `username`, `password_hash`, `email`, `role_id` (FK) |
| **3** | `doctors` | Physician professional profiles | `doctor_id` (PK), `user_id` (FK), `specialization`, `license_number` |
| **4** | `nurses` | Nursing staff profiles | `nurse_id` (PK), `user_id` (FK), `ward_assignment`, `shift` |
| **5** | `attendants` | Family attendants mapped to patients | `attendant_id` (PK), `patient_id` (FK), `user_id` (FK), `access_code` |
| **6** | `wards` | Hospital ward units | `ward_id` (PK), `name` (ICU-A, HDU-B), `ward_type`, `total_beds` |
| **7** | `beds` | Bed matrix and occupancy | `bed_id` (PK), `ward_id` (FK), `bed_number`, `status` (occupied, available) |
| **8** | `patients` | Admitted patient records | `patient_id` (PK), `patient_code` (UHID), `name`, `ward_id`, `bed_id`, `assigned_doctor`, `assigned_nurse` |
| **9** | `vitals` | Bedside 4-parameter vital readings | `vital_id` (PK), `patient_id` (FK), `heart_rate`, `systolic_bp`, `respiratory_rate`, `temperature`, `recorded_at` |
| **10** | `ews_scores` | Calculated EWS score & risk | `ews_id` (PK), `patient_id` (FK), `vital_id` (FK), `score`, `risk_level` |
| **11** | `decisions` | Step-down triage recommendations | `decision_id` (PK), `patient_id` (FK), `recommendation`, `confidence` |
| **12** | `recommendations` | Clinical action recommendations | `recommendation_id` (PK), `patient_id` (FK), `action_type`, `status` |
| **13** | `explanations` | Feature importance logs | `explanation_id` (PK), `decision_id` (FK), `patient_id` (FK), `feature_name`, `contribution` |
| **14** | `transfers` | Inter-ward transfer workflows | `transfer_id` (PK), `patient_id` (FK), `from_ward`, `to_ward`, `status` (pending, approved, completed) |
| **15** | `bed_management` | Historical bed assignment logs | `management_id` (PK), `patient_id` (FK), `bed_id` (FK), `status` |
| **16** | `alerts` | Clinical emergency alerts | `alert_id` (PK), `patient_id` (FK), `alert_type` (critical, high), `status`, `is_acknowledged` |
| **17** | `notifications` | Role-targeted staff notices | `notification_id` (PK), `user_id` (FK), `patient_id` (FK), `type`, `message`, `is_read` |
| **18** | `patient_qr_tokens` | Permanent QR visitor tokens | `token_id` (PK), `patient_id` (FK), `token_hash`, `is_active`, `expires_at` |
| **19** | `reports` | Clinical PDF generated reports | `report_id` (PK), `patient_id` (FK), `report_type`, `file_path`, `generated_by` |
| **20** | `chatbot_conversations`| Dr. Setu AI consultation history | `conversation_id` (PK), `user_id` (FK), `patient_id` (FK), `prompt`, `response` |
| **21** | `clinical_notes` | Physician clinical observations | `note_id` (PK), `patient_id` (FK), `doctor_id` (FK), `note_text`, `created_at` |
| **22** | `token_blacklist` | Revoked / logged-out JWT tokens | `blacklist_id` (PK), `token`, `blacklisted_at` |
| **23** | `audit_logs` | Comprehensive security audit log | `log_id` (PK), `user_id` (FK), `action`, `resource`, `ip_address`, `timestamp` |
| **24** | `audit_log` | Auxiliary audit compatibility | `id` (PK), `event`, `details`, `created_at` |
| **25** | `user_preferences` | User theme & display settings | `pref_id` (PK), `user_id` (FK), `theme`, `notifications_enabled` |
| **26** | `password_reset_tokens`| Password recovery tokens | `token_id` (PK), `user_id` (FK), `token`, `expires_at` |
| **27** | `schema_migrations` | Database version migrations | `migration_id` (PK), `version`, `description`, `applied_at` |

---

## 🏥 5. Canonical 10-Patient Census Reference

| ID | UHID | Name | Age / Sex | Ward | Bed | Bed ID | Assigned Doctor | Assigned Nurse | Status |
| :-: | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- | :---: |
| **1** | `UHID-2026-00001` | Rajesh Kumar | 58 / M | ICU | `ICU-01` | 400 | Dr. Sharma (ID: 2) | Nurse Priya (ID: 5) | Admitted |
| **2** | `UHID-2026-00002` | Anita Devi | 45 / F | HDU | `HDU-01` | 401 | Dr. Sharma (ID: 2) | Nurse Priya (ID: 5) | Admitted |
| **3** | `UHID-2026-00003` | Vikram Singh | 62 / M | ICU | `ICU-02` | 402 | Dr. Patel (ID: 3) | Nurse Arun (ID: 6) | Admitted |
| **4** | `UHID-2026-00004` | Sunita Rao | 51 / F | ICU | `ICU-03` | 403 | Dr. Patel (ID: 3) | Nurse Arun (ID: 6) | Admitted |
| **5** | `UHID-2026-00005` | Mohammed Ali | 67 / M | ICU | `ICU-04` | 404 | Dr. Gupta (ID: 4) | Nurse Meera (ID: 7) | Admitted |
| **6** | `UHID-2026-00006` | Priya Nair | 34 / F | HDU | `HDU-02` | 405 | Dr. Gupta (ID: 4) | Nurse Meera (ID: 7) | Admitted |
| **7** | `UHID-2026-00007` | Amit Verma | 42 / M | HDU | `HDU-03` | 406 | Dr. Sharma (ID: 2) | Nurse Priya (ID: 5) | Admitted |
| **8** | `UHID-2026-00008` | Lakshmi Iyer | 70 / F | HDU | `HDU-04` | 407 | Dr. Patel (ID: 3) | Nurse Arun (ID: 6) | Admitted |
| **9** | `UHID-2026-00009` | Deepak Joshi | 55 / M | HDU | `HDU-05` | 408 | Dr. Gupta (ID: 4) | Nurse Meera (ID: 7) | Admitted |
| **10** | `UHID-2026-00010` | Fatima Begum | 61 / F | HDU | `HDU-06` | 409 | Dr. Gupta (ID: 4) | Nurse Meera (ID: 7) | Admitted |

---

## 🌐 6. Complete Frontend Portals & Pages Directory (43 Pages)

### 🛡️ Administrator Portal (12 Pages)
1. `Admin/Administrator_dashboard_/Administrator_dashboard_.html` — Hospital census, occupancy metrics, critical care load.
2. `Admin/Admin_patient_management/Admin_patient_management.html` — Patient list, in-app admission modal, census filters.
3. `Admin/Admin_beds_wards/Admin_beds_wards.html` — Interactive spatial floorplan matrix for ICU-A and HDU-B.
4. `Admin/Admin_resource_utilization/Admin_resource_utilization.html` — Medical device telemetry, ventilator usage.
5. `Admin/Admin_users_roles/Admin_users_roles.html` — Staff directory, account provisioning, password reset.
6. `Admin/Admin_attendant_access/Admin_attendant_access.html` — QR badge generator, printable badge pass modal.
7. `Admin/Admin_clinical_reports/Admin_clinical_reports.html` — ReportLab batch PDF generation and downloads.
8. `Admin/Admin_ews_analytics/Admin_ews_analytics.html` — Unit risk distributions, score histograms.
9. `Admin/Admin_audit_logs/Admin_audit_logs.html` — Real-time security, login, and clinical transfer logs.
10. `Admin/Admin_notification_settings/Admin_notification_settings.html` — Hospital alert routing thresholds.
11. `Admin/Admin_system_settings/Admin_system_settings.html` — Hospital branding, shift definitions.
12. `Admin/Admin_backup_restore/Admin_backup_restore.html` — Database dump & recovery management.

### 👨‍⚕️ Doctor Portal (14 Pages)
1. `Doctor/Doctor_dashboard_/Doctor_dashboard_.html` — Assigned patient roster, active alerts, step-down approvals.
2. `Doctor/Doctor_my_patients/Doctor_my_patients.html` — Dedicated list of patients assigned to logged-in doctor.
3. `Doctor/Doctor_all_patients/Doctor_all_patients.html` — Hospital-wide directory with authorization checks.
4. `Doctor/Doctor_pending_approvals/Doctor_pending_approvals.html` — Step-down transfer approval/rejection queue.
5. `Doctor/Doctor_ews_calculator/Doctor_ews_calculator.html` — Bedside vital sign EWS calculation scratchpad.
6. `Doctor/Doctor_ews_trends/Doctor_ews_trends.html` — Longitudinal vital signs trajectory graphs.
7. `Doctor/Doctor_transfer_recommendations/Doctor_transfer_recommendations.html` — AI triage recommendations.
8. `Doctor/Doctor_transfer_reports/Doctor_transfer_reports.html` — Historical inter-ward transfer audit logs.
9. `Doctor/Doctor_patient_reports/Doctor_patient_reports.html` — Patient clinical summaries & PDF downloads.
10. `Doctor/Doctor_patient_search/Doctor_patient_search.html` — Diagnostic and demographic patient lookup.
11. `Doctor/Doctor_patient_summary_ai/Doctor_patient_summary_ai.html` — OpenRouter Gemma 4 interactive assistant.
12. `Doctor/Doctor_alerts_notifications/Doctor_alerts_notifications.html` — Clinician emergency alarm history.
13. `Doctor/Doctor_audit_logs/Doctor_audit_logs.html` — Clinical action timestamp verification.
14. `Doctor/Doctor_settings_jeevan/Doctor_settings_jeevan.html` — Physician profile and notification settings.

### 👩‍⚕️ Nurse Portal (12 Pages)
1. `Nurse/Nurse_dashboard/Nurse_dashboard.html` — Live ward roster, rapid status indicators.
2. `Nurse/nurse_patient_monitoring/nurse_patient_monitoring.html` — High-frequency vital monitoring cards.
3. `Nurse/Nurse_enter_vitals/Nurse_enter_vitals.html` — 4-parameter rapid vitals entry form with live EWS preview.
4. `Nurse/Nurse_alerts/Nurse_alerts.html` — Real-time ward alarms and notification feed.
5. `Nurse/Nurse_tasks/Nurse_tasks.html` — Nursing shift task checklist and vital check schedule.
6. `Nurse/Nurse_transfers/Nurse_transfers.html` — Read-only transfer queue (guardrailed against nurse approval).
7. `Nurse/Nurse_reports/Nurse_reports.html` — Nursing shift reports and vitals export.
8. `Nurse/Nurse_ews_calculator/Nurse_ews_calculator.html` — Nursing vital sign scoring calculator.
9. `Nurse/Nurse_i_o_chart/Nurse_i_o_chart.html` — Fluid intake and output recording.
10. `Nurse/Nurse_medication_log/Nurse_medication_log.html` — Bedside medication administration schedule.
11. `Nurse/Nurse_nursing_notes/Nurse_nursing_notes.html` — Daily nursing observations and shift handovers.
12. `Nurse/Nurse_settings/Nurse_settings.html` — Nurse profile and shift preferences.

### 📱 Attendant & Family Portal (3 Pages)
1. `Attendant/attendant_access.html` — Mobile-first QR code scan entry and name verification landing page.
2. `Attendant/attendant_login_mobile_replica/attendant_login_mobile_replica.html` — Fallback manual patient login.
3. `Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html` — Real-time mobile patient condition card (Stable/Observation/Critical), bed location, and doctor info.

### 💻 Developer Tools (1 Page)
1. `Developer/Telemetry_Simulator/Telemetry_Simulator.html` — Browser-based interactive ICU bedside telemetry simulator with live waveform visualizer, patient selection, and scenario triggers.

### 🔑 Authentication (1 Page)
1. `Login/Login.html` — Centralized multi-role clinical authentication portal.

---

## 📡 7. REST API Endpoints Catalog

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| **POST** | `/api/v1/auth/login` | Multi-role user login (returns JWT token) | Public |
| **POST** | `/api/v1/auth/logout` | User logout (blacklists active JWT) | Bearer JWT |
| **GET** | `/api/v1/users` | List, search, and paginate hospital staff | Admin |
| **POST** | `/api/v1/users` | Provision new clinician or staff account | Admin |
| **GET** | `/api/v1/patients` | Retrieve admitted patient census | Bearer JWT |
| **POST** | `/api/v1/patients/admit` | Execute atomic patient intake & admission | Admin |
| **GET** | `/api/v1/patients/admission-options`| Returns next UHID and available beds | Admin |
| **POST** | `/vitals/patient/{id}/submit` | Ingest bedside vitals (HR, SBP, RR, Temp) | Optional / Dev |
| **GET** | `/vitals/patient/{id}/latest` | Fetch latest vital parameters and EWS | Bearer JWT |
| **GET** | `/vitals/patient/{id}/history` | Fetch historical vital time-series | Bearer JWT |
| **GET** | `/api/v1/decision/patient/{id}` | Evaluate step-down / step-up triage | Doctor / Admin |
| **POST** | `/api/v1/transfers/approve/{id}` | Atomic doctor transfer approval & HDU bed lock | Doctor / Admin |
| **POST** | `/api/v1/transfers/reject/{id}` | Reject step-down transfer request | Doctor / Admin |
| **GET** | `/api/v1/alerts/active` | Fetch active emergency alarms | Bearer JWT |
| **POST** | `/api/v1/alerts/{id}/acknowledge` | Doctor acknowledgment of critical alarm | Doctor / Admin |
| **POST** | `/api/v1/attendant/verify-token` | Validate QR token and issue attendant session | Public |
| **GET** | `/api/v1/attendant/patient-status` | Fetch read-only family recovery card | Attendant Token |
| **POST** | `/api/v1/chatbot/chat` | Dr. Setu AI OpenRouter consultation | Bearer JWT |
| **GET** | `/api/v1/reports/patient/{id}/pdf` | Generate ReportLab patient PDF report | Bearer JWT |
| **GET** | `/api/v1/analytics/census` | Unit-level occupancy and EWS distributions | Admin / Doctor |

---

## 🧪 8. Automated Testing & Verification Suite

The repository contains **over 407 automated tests**:
1. **Backend Integration Suites (`JEEVAN_SETU/tests/`)**:
   - `test_global_emergency_transfer_alerts.py` — Verifies universal popups, duplicate suppression, and auto-resolution.
   - `test_patient_admission_workflow.py` — Tests atomic intake transaction and bed mutual exclusion.
   - `test_patient_pdf_report.py` — Tests ReportLab multi-page canvas, headers, and download streams.
   - `test_doctor_approve_button_and_nurse_guardrail.py` — Verifies HTTP 403 enforcement when nurses attempt transfer approvals.
   - `test_auto_refresh_system.py` — Verifies background polling endpoints and payload integrity.
   - `test_openrouter_ai.py` — Validates AI prompt formatting and fallback handling.
   - `test_phase2` through `test_phase19` — Legacy phased verification tests covering database, auth, RBAC, vitals, beds, and security.
2. **Telemetry Simulator Suites (`telemetry_simulator/tests/`)**:
   - `test_client.py` — Validates HTTP client connection, retries, and headers.
   - `test_scenarios.py` — Verifies math generators for `stable`, `deterioration`, `recovery`, and `critical` scenarios.
   - `test_validation.py` — Ensures out-of-bound vital signs are rejected prior to transmission.
   - `test_simulator.py` — Tests interactive CLI and automated loop runners.

---

## 🛠️ 9. Developer & System Execution Commands

### 1. Start Application Server
```powershell
cd D:\Major_Project\JSF-Web_Broswer_simulator\Jeevan-Setu-Final\JEEVAN_SETU
python app.py
```
- Server URL: `http://127.0.0.1:5000`
- Mobile / LAN Access: `http://<LAN_IP>:5000`

### 2. Run CLI Telemetry Simulator
```powershell
cd D:\Major_Project\JSF-Web_Broswer_simulator\Jeevan-Setu-Final\telemetry_simulator
python simulator.py --patient 1 --scenario stable --interval 3
```

### 3. Open Developer Telemetry Simulator GUI
In browser: [http://127.0.0.1:5000/Developer/Telemetry_Simulator/Telemetry_Simulator.html](http://127.0.0.1:5000/Developer/Telemetry_Simulator/Telemetry_Simulator.html)

### 4. Restore 10-Patient Database Baseline
```powershell
cd D:\Major_Project\JSF-Web_Broswer_simulator\Jeevan-Setu-Final\JEEVAN_SETU
python database\cleanup_patients.py
```

### 5. Resync Database Schema (`schema.sql` & `schema.db`)
```powershell
cd D:\Major_Project\JSF-Web_Broswer_simulator\Jeevan-Setu-Final\JEEVAN_SETU
python database\sync_schema.py
```

---

## 🗺️ 10. Roadmap & Potential Future Enhancements

If continuing development in future sprints, the following modules can be further expanded:
1. **Physical HL7 / FHIR Ingestion Protocol**: Adapt the telemetry client to accept direct HL7 v2 / FHIR Observation bundles from physical hospital bedside monitors (Philips IntelliVue, GE CARESCAPE).
2. **WebSocket Push Pipeline**: Upgrade the current 3-second background polling manager to WebSocket push notifications (Flask-SocketIO) for sub-second telemetry updates.
3. **Containerized Deployment**: Provide production `docker-compose.yml` orchestrating Gunicorn, Nginx reverse proxy, MySQL 8.0, and Redis cache.
4. **Predictive Sepsis AI Model**: Integrate machine learning models (e.g. XGBoost trained on MIMIC-III) alongside rule-based EWS to predict sepsis onset 6 hours in advance.
