# 📋 Jeevan Setu — System Rules & Operational Standards

This document establishes the mandatory operational, architectural, clinical, and database rules for the **Jeevan Setu** Clinical Decision Support and Patient Management System. All automated agents, developers, and workflows must adhere strictly to these rules.

---

## 🗂️ 1. Workspace & Containment Rules

1. **Strict Folder Confinement**:
   - All files, code modifications, scratch files, and configuration changes **must remain strictly inside `d:\Major_Project\JSF-Web_Broswer_simulator`** (including its subfolder `Jeevan-Setu-Final`).
   - Under no circumstances should files be created, copied, or modified outside of this directory.
2. **Preserve Documentation & Code Comments**:
   - Existing code comments, docstrings, schema definitions, and markdown reports must be preserved and kept accurate.

---

## 🏥 2. Database Baseline & 10-Patient Rule

1. **Mandatory 10-Patient Baseline**:
   - The primary database (`jeevan_setu`) must **always maintain exactly 10 active admitted patients** (Patient IDs `1` through `10`, codes `UHID-2026-00001` through `UHID-2026-00010`).
   - The census must never be left in an inconsistent state after test runs or simulations.
2. **Standard 10-Patient Roster & Bed Matrix**:
   | Patient ID | UHID | Name | Age / Gender | Ward | Bed Number | Bed ID | Assigned Doctor | Assigned Nurse |
   | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
   | **1** | `UHID-2026-00001` | Rajesh Kumar | 58 / Male | ICU | `ICU-01` | 400 | Dr. Sharma (ID: 2) | Nurse Priya (ID: 5) |
   | **2** | `UHID-2026-00002` | Anita Devi | 45 / Female | HDU | `HDU-01` | 401 | Dr. Sharma (ID: 2) | Nurse Priya (ID: 5) |
   | **3** | `UHID-2026-00003` | Vikram Singh | 62 / Male | ICU | `ICU-02` | 402 | Dr. Patel (ID: 3) | Nurse Arun (ID: 6) |
   | **4** | `UHID-2026-00004` | Sunita Rao | 51 / Female | ICU | `ICU-03` | 403 | Dr. Patel (ID: 3) | Nurse Arun (ID: 6) |
   | **5** | `UHID-2026-00005` | Mohammed Ali | 67 / Male | ICU | `ICU-04` | 404 | Dr. Gupta (ID: 4) | Nurse Meera (ID: 7) |
   | **6** | `UHID-2026-00006` | Priya Nair | 34 / Female | HDU | `HDU-02` | 405 | Dr. Gupta (ID: 4) | Nurse Meera (ID: 7) |
   | **7** | `UHID-2026-00007` | Amit Verma | 42 / Male | HDU | `HDU-03` | 406 | Dr. Sharma (ID: 2) | Nurse Priya (ID: 5) |
   | **8** | `UHID-2026-00008` | Lakshmi Iyer | 70 / Female | HDU | `HDU-04` | 407 | Dr. Patel (ID: 3) | Nurse Arun (ID: 6) |
   | **9** | `UHID-2026-00009` | Deepak Joshi | 55 / Male | HDU | `HDU-05` | 408 | Dr. Gupta (ID: 4) | Nurse Meera (ID: 7) |
   | **10** | `UHID-2026-00010` | Fatima Begum | 61 / Female | HDU | `HDU-06` | 409 | Dr. Gupta (ID: 4) | Nurse Meera (ID: 7) |

3. **Bed Allocation & Occupancy Rules**:
   - The 10 baseline beds (`bed_id` 400 through 409) must have status `'occupied'`.
   - The 48 standard ward beds in Ward 1 (`ICU-A01` to `ICU-A20`) and Ward 2 (`HDU-B01` to `HDU-B20`) must have status `'available'`.
   - Temporary or test beds (e.g. `ICU-T-*`, `HDU-T-*`, `ICU-CRIT-*`) and test wards (`ward_id > 2`) must be removed upon test completion.
4. **Automated Cleanup Rule**:
   - Any test script, API test, or workflow that inserts test patients (`patient_id > 10`) or test users (`user_id > 17`) must be followed by running:
     ```powershell
     python JEEVAN_SETU\database\cleanup_patients.py
     ```
   - `cleanup_patients.py` automatically purges child tables (`alerts`, `vitals`, `decisions`, `ews_scores`, `patient_qr_tokens`, `reports`, `transfers`, `chatbot_conversations`, `clinical_notes`, `notifications`) for `patient_id > 10`, cleans test beds/users, resets bed occupancy, and restores `AUTO_INCREMENT = 11`.

---

## 🩺 3. Clinical & Early Warning Score (EWS) Rules

1. **Vital Sign Input Range Boundaries**:
   Every recorded vital parameter must fall within valid physiological boundaries:
   - **Heart Rate (HR)**: `30` – `220` bpm
   - **Systolic Blood Pressure (SBP)**: `50` – `250` mmHg
   - **Respiratory Rate (RR)**: `6` – `60` breaths/min
   - **Temperature**: `32.0`°C – `43.0`°C
2. **Early Warning Score (EWS) Thresholds**:
   - **Critical / High Risk (`EWS >= 7`)**:
     - Immediate clinical escalation.
     - Patient retained in or transferred to ICU.
     - Urgent visual red banner displayed on Doctor and Nurse dashboards.
   - **Moderate / Elevated Risk (`EWS 5 - 6`)**:
     - HDU close monitoring recommended.
     - Vital signs frequency increased to every 1–2 hours.
     - Amber alert indicator displayed.
   - **Low Risk / Stable (`EWS 1 - 4`)**:
     - Stable patient.
     - Eligible for ICU → HDU or HDU → General ward step-down evaluation.
     - Green / Yellow status indicator.
   - **Normal (`EWS 0`)**:
     - All vitals within reference ranges.
3. **Clinical Transfer Rules**:
   - **ICU to HDU Step-Down**: Permitted only when patient EWS score remains `<= 4` across multiple readings and assigned doctor approves.
   - **HDU to ICU Step-Up**: Triggered immediately when EWS reaches `>= 7` or single extreme vital parameter triggers critical threshold.
   - **Doctor Approval**: No inter-ward transfer can be executed without explicit doctor confirmation.

---

## 🔐 4. Role-Based Access Control (RBAC) & Security Rules

1. **Role Separation**:
   - **Administrator (`admin`)**: Access to Hospital Census, Bed Matrix, User Provisioning, Patient Admission, PDF Clinical Reports, and Audit Logs. Cannot override clinical triage decisions directly.
   - **Doctor (`doctor`)**: Access to assigned patient roster, EWS calculator, transfer approval/rejection queue, vital timelines, and AI explanation assistant.
   - **Nurse (`nurse`)**: Access to ward overview, rapid bedside vitals entry form, and live telemetry alert notifications.
   - **Attendant (`attendant`)**: Read-only mobile-replica view accessed strictly via verified patient QR token. **Zero access to other patients' Protected Health Information (PHI).**
2. **Authentication & Token Standards**:
   - Bearer JWT tokens with signed payload containing `user_id`, `role`, and expiration.
   - Token expiry is 24 hours.
   - Passwords must be hashed using secure bcrypt/werkzeug standards.
3. **Audit Trail Logging**:
   - All logins, patient admissions, vital entries, transfer approvals, QR token generations, and PDF report downloads must be recorded in `audit_logs`.

---

## ⚡ 5. Real-Time Telemetry & Auto-Refresh Rules

1. **Telemetry Simulation**:
   - Bedside monitor simulation runs independently via `telemetry_simulator/simulator.py`.
   - Communicates exclusively via HTTP `POST /vitals/patient/{id}/submit`.
   - Supports 5 distinct clinical scenarios: `stable`, `deterioration`, `recovery`, `critical`, `manual`.
2. **Frontend Auto-Refresh System**:
   - Doctor, Nurse, and Attendant portals utilize `auto_refresh_manager.js` and `global_alert_manager.js`.
   - Telemetry vitals updates, EWS calculations, and bed alerts update smoothly without causing jarring full-page refreshes.
   - Fallback interval for background poll is set between 3 to 5 seconds.

---

## 💻 6. Frontend & Code Development Rules

1. **Technology Stack**:
   - Structure: Semantic HTML5.
   - Logic: Vanilla JavaScript (modular ES6).
   - Styling: Pure Vanilla CSS with centralized design tokens (`var(--primary)`, `var(--bg-card)`, etc.).
   - Framework rule: No Tailwind CSS or external component libraries unless explicitly requested by the user.
2. **Design Standards**:
   - Modern, clinical-grade dark/light dashboard theme with glassmorphism touches and responsive layout.
   - Attendant portal must be mobile-first and optimized for small smartphone viewports.
3. **Unique Element IDs**:
   - All form inputs, modal dialogs, and actionable buttons must have descriptive, unique `id` attributes for automated browser testing.

---

## 🌐 7. Network & Deployment Rules

1. **LAN & Mobile Accessibility**:
   - Backend binds to `0.0.0.0:5000` to allow local hospital Wi-Fi and mobile hotspot access.
   - IP address is dynamically detected by `get_lan_ip()` in `config.py`.
2. **Environment File Integrity**:
   - Keep `.env` up to date with valid database credentials (`DB_HOST=localhost`, `DB_PORT=3306`, `DB_USER=root`, `DB_PASSWORD=NewPassword123!`, `DB_NAME=jeevan_setu`).
   - Do not commit production secrets or API keys into public repositories.

---

## 📱 8. Attendant Portal Network Address Configuration

1. **Designated Demo Base URL**:
   - The designated Attendant Portal base URL for local-network demonstrations is:
     ```
     http://172.20.10.4:5000
     ```

2. **Local Network & Mobile Device Accessibility**:
   - The Attendant Portal must be accessible to authorized mobile devices connected to the same local network, provided the Flask server is running and network/firewall configuration permits access.

3. **Key Pages & Routes**:
   - The following pages and routes must be considered when configuring or testing Attendant Portal access:
     - **Base URL**: `http://172.20.10.4:5000`
     - **Attendant Access Page**: `http://172.20.10.4:5000/Attendant/attendant_access.html`
     - **QR Access Routes**: Use the existing `/qr/<token>` route and preserve its server-side token verification.

4. **No Hardcoded Localhost in Browser-Side Requests**:
   - Do not hardcode `127.0.0.1` or `localhost` into browser-side API requests intended to be accessed from a mobile device.
   - Prefer relative URLs (e.g. `/api/v1/attendant/...`) or the existing application URL-generation mechanism so client requests automatically resolve to the reachable host.

5. **Network Interface & Port Binding**:
   - When running the Flask application for LAN demonstrations, configure the server to listen on an appropriate network interface, such as `0.0.0.0`, when required.
   - Keep the existing application port `5000` unless a documented requirement justifies changing it.

6. **Designated Demo IP Scope**:
   - Treat `172.20.10.4` as the designated demo IP, not a guaranteed permanent address.
   - If the host computer's network IP changes (e.g. switching between Wi-Fi and mobile hotspot), update the demo configuration and documentation accordingly.

7. **Security & Patient Data Protection Preservation**:
   - Preserve all existing security requirements, including authentication, authorization, RBAC, QR token validation, session handling, and patient-data protection.
   - Do not weaken access controls or bypass server-side token validation to make mobile demonstrations easier.

8. **Camera Access & Secure Context Requirements**:
   - Camera access must respect browser secure-context requirements (`window.isSecureContext`).
   - Do not assume that the HTTP LAN URL automatically supports live camera video streaming on every mobile browser (such as iOS Safari or Android Chrome).
   - Document any necessary HTTPS development configuration separately (e.g., development SSL gateway on port 5443 or native mobile photo capture fallback).

