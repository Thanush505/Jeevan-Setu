<p align="center">
  <img src="Jeevan-Setu-Final/Jeevan_setu_frontend/assets/jeevan_setu_logo.png" width="130" alt="Jeevan Setu Logo" />
</p>

<h1 align="center">JEEVAN SETU • जीवन सेतु 🏥</h1>

<p align="center">
  <strong>Intelligent ICU ↔ HDU Clinical Decision Support, Real-Time Bedside Telemetry Simulation & Patient Transfer System</strong><br>
  <em>Empowering critical care teams with explainable clinical intelligence, automated Early Warning Scoring, and zero-loss bedside transitions.</em>
</p>

<p align="center">
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+" /></a>
  <a href="https://flask.palletsprojects.com/"><img src="https://img.shields.io/badge/Backend-Flask%202.x-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" /></a>
  <a href="https://www.mysql.com/"><img src="https://img.shields.io/badge/Database-MySQL%208.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white" alt="MySQL" /></a>
  <a href="https://developer.mozilla.org/en-US/docs/Web/JavaScript"><img src="https://img.shields.io/badge/Frontend-Vanilla%20ES6%2B%20%7C%20Tailwind-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="Vanilla JS" /></a>
  <a href="#"><img src="https://img.shields.io/badge/Clinical%20EWS-Automated%204--Tier-E11D48?style=for-the-badge&logo=heartbeat&logoColor=white" alt="Clinical EWS" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-10B981?style=for-the-badge" alt="MIT License" /></a>
</p>

---

## 🌟 The Vision: Why "Jeevan Setu"?

In critical care, **every second is physiology**. 

Hospitals face two relentless challenges:
1. **The Delayed Step-Down Dilemma**: Recovering ICU patients remain in high-intensity beds hours longer than necessary because manual charting, risk calculations, and bed hunting in High Dependency Units (HDU) are slow and fragmented. This delays emergency admissions for incoming critical patients.
2. **The Sudden Deterioration Blindspot**: Subtle clinical trends—a mild respiratory drift, rising temperature, dropping blood pressure—often go unnoticed under alarm fatigue until a patient reaches acute decompensation.

**Jeevan Setu** (*Sanskrit: जीवन सेतु — "The Bridge of Life"*) transforms this workflow. It forms an intelligent digital nervous system bridging bedside telemetry, attending physicians, bedside nurses, operational administrators, and worried families into one cohesive, real-time clinical platform.

---

## 🏛️ The Five Bridges of Jeevan Setu

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           JEEVAN SETU ECOSYSTEM                          │
├─────────────────┬──────────────────┬──────────────────┬──────────────────┤
│ 👨‍⚕️ DOCTOR       │ 👩‍⚕️ NURSE        │ 🛡️ ADMINISTRATOR │ 📱 ATTENDANT     │
│ Decision Support│ Bedside Matrix   │ Live Bed Census  │ QR Badge Access  │
│ 1-Click Transfer│ Telemetry Ingest │ ReportLab PDF    │ Mobile Camera    │
│ Risk Breakdown  │ Global Alerts    │ Audit Compliance │ Zero Jargon      │
└────────┬────────┴────────┬─────────┴────────┬─────────┴────────┬─────────┘
         │                 │                  │                  │
         └─────────────────┼──────────────────┼──────────────────┘
                           ▼                  ▼
             ┌──────────────────────────────────────────────┐
             │         DUAL-PROTOCOL FLASK BACKEND          │
             │   • Port 5000 (HTTP API & Dashboards)        │
             │   • Port 5443 (HTTPS Secure Context Gateway) │
             └──────────────────────┬───────────────────────┘
                                    │
                                    ▼
             ┌──────────────────────────────────────────────┐
             │         CLINICAL INTELLIGENCE CORE           │
             │   • 4-Parameter Heuristic EWS Engine         │
             │   • Deterministic 3-Tier Transfer Logic      │
             │   • Atomic Row-Locked Bed Allocation         │
             │   • Universal Global Alert Broadcast         │
             └──────────────────────┬───────────────────────┘
                                    │
                                    ▼
             ┌──────────────────────────────────────────────┐
             │       CONCURRENT TELEMETRY SIMULATOR         │
             │   • 10-Patient Authoritative Matrix          │
             │   • Interactive Scenario State Transitions   │
             │   • Stable ↔ Moderate ↔ Critical ↔ Recovery  │
             └──────────────────────────────────────────────┘
```

### 1. 📟 The Telemetry & Simulator Bridge
- **Interactive Multi-Patient Matrix**: Features a browser-based developer console streaming real-time vitals ($HR$, $RR$, $SBP$, $Temp$) across 10 concurrent admitted patients.
- **Directional Scenario Steppers**: Testers can transition patient physiology in real time:
  - `⚡ Worsen`: $\text{STABLE} \longrightarrow \text{MODERATE} \longrightarrow \text{CRITICAL}$
  - `🌱 Improve`: $\text{CRITICAL} \longrightarrow \text{MODERATE} \longrightarrow \text{STABLE}$
  - Direct test routes: $\text{Stable} \longleftrightarrow \text{Recovery}$, $\text{Critical} \longleftrightarrow \text{Recovery}$
- **Authoritative Database Persistence**: Every scenario transition updates `simulator_patient_states`, writes an immutable audit record in `simulator_scenario_transitions`, and survives page refreshes.

### 2. 🧠 The Clinical Intelligence & EWS Engine
- **Sole Source of Clinical Truth**: The simulator *never* calculates risk or EWS locally. Raw telemetry is transmitted to `POST /api/v1/vitals/patient/{id}/submit` where the server calculates approved 4-parameter EWS:
  - **Respiratory Rate** (breaths/min)
  - **Heart Rate** (bpm)
  - **Systolic Blood Pressure** (mmHg)
  - **Body Temperature** (°C)
- **Deterministic 3-Tier Clinical Transfer Decision Engine**:
  - $\text{Total EWS } 0 - 2$: **Stable** $\longrightarrow$ *Fit for HDU Transfer*
  - $\text{Total EWS } 3 - 4$: **Moderate Risk** $\longrightarrow$ *Re-evaluate*
  - $\text{Total EWS } \ge 5$: **Critical** $\longrightarrow$ *Keep in ICU & Trigger Emergency Transfer Alert*

### 3. 🚨 The Universal Global Emergency Alert Bridge
- **Zero-Latency Clinical Notifications**: When a patient deteriorates into critical territory ($\text{EWS} \ge 7$ or extreme vital excursion), an emergency alert broadcasts globally.
- **Ubiquitous Popups**: Dispatched across every doctor and nurse view without requiring users to sit on a dashboard.
- **Self-Healing & Auto-Resolution**: When subsequent telemetry confirms patient stabilization, critical alerts auto-resolve with full timestamp auditing.

### 4. 🔄 The Atomic Bed Allocation Bridge
- **Prolonged Transfer Safety Net**: Monitors patients cleared for HDU transfer. If wait time exceeds the clinical threshold (120 mins), escalation alerts trigger automatically.
- **Strict Role-Based Access Control (RBAC)**: Only Attending Doctors and Administrators possess transfer approval authorization. Unauthorized approval attempts yield `HTTP 403 Forbidden` and log a security audit event.
- **Concurrency-Safe Atomic Bed Swaps**: Uses database row-level locking (`SELECT ... FOR UPDATE`) inside an atomic transaction to vacate the ICU bed and assign the target HDU bed simultaneously, preventing race conditions.

### 5. 📱 The Compassionate Attendant Bridge
- **Permanent Bedside QR Badges**: Each admitted patient receives a cryptographically salted QR token (`JS-QR-P{patient_id}-{entropy}`).
- **Native Mobile Camera Scanner**: Families scan the badge at the bedside using iOS Safari or Android Chrome via our built-in **HTTPS Secure Context Gateway** (port `5443`), eliminating insecure context camera blocks.
- **Privacy-Preserving Family Portal**: Displays reassuring, plain-language patient condition updates without exposing clinical jargon, developer diagnostics, or cross-patient records.

---

## 🔬 Clinical Scoring Architecture

Jeevan Setu adheres strictly to approved clinical Early Warning Score parameters:

| Vital Parameter | Score = 3 | Score = 2 | Score = 1 | Score = 0 (Normal) | Score = 1 | Score = 2 | Score = 3 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Heart Rate** (*bpm*) | $\le 40$ | — | $41 - 50$ | **$51 - 90$** | $91 - 110$ | $111 - 130$ | $\ge 131$ |
| **Systolic BP** (*mmHg*) | $\le 70$ | $71 - 80$ | $81 - 100$ | **$101 - 199$** | — | — | $\ge 200$ |
| **Respiratory Rate** (*rpm*) | $\le 8$ | — | $9 - 11$ | **$12 - 20$** | — | $21 - 24$ | $\ge 25$ |
| **Temperature** (*°C*) | $\le 35.0$ | — | $35.1 - 36.0$ | **$36.1 - 38.0$** | $38.1 - 39.0$ | $\ge 39.1$ | — |

---

## 👥 Baseline Clinicians & Roles

| Role | Username | Password | Full Name | Ward / Focus | Clinical Scope |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **🛡️ Admin** | `admin_js` | `Admin@123` | System Administrator | Hospital Admin | Full System, Audits, Census & Reports |
| **👨‍⚕️ Doctor 1** | `dr_sharma` | `Doctor@123` | Dr. Anil Sharma | Cardiology (ICU) | Assigned Patients 1, 2, 7 |
| **👨‍⚕️ Doctor 2** | `dr_patel` | `Doctor@123` | Dr. Kavita Patel | Pulmonology (ICU) | Assigned Patients 3, 4, 8 |
| **👨‍⚕️ Doctor 3** | `dr_gupta` | `Doctor@123` | Dr. Rajiv Gupta | Neurology (HDU) | Assigned Patients 5, 6, 9, 10 |
| **👩‍⚕️ Nurse 1** | `nurse_priya` | `Nurse@123` | Priya Menon | ICU Ward | Bedside Monitoring & Vitals Entry |
| **👩‍⚕️ Nurse 2** | `nurse_arun` | `Nurse@123` | Arun Krishnan | HDU Ward | Bedside Monitoring & Vitals Entry |
| **👩‍⚕️ Nurse 3** | `nurse_meera` | `Nurse@123` | Meera Jain | ICU / HDU Float | Bedside Monitoring & Vitals Entry |
| **📱 Attendant** | `att_rajesh` | `Attendant@123` | Suman Kumar | Bedside Family | Patient 1 Bedside QR Access |

---

## 🏥 Canonical 10-Patient Hospital Census

The system maintains a verified baseline of **exactly 10 admitted critical care patients**:

| ID | UHID | Patient Name | Age/Sex | Ward | Bed Code | Bed ID | Assigned Doctor | Assigned Nurse | Status |
| :-: | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- | :---: |
| **1** | `UHID-2026-00001` | Rajesh Kumar | 58 M | ICU | `ICU-01` | 400 | Dr. Sharma | Nurse Priya | **Admitted** |
| **2** | `UHID-2026-00002` | Anita Devi | 45 F | HDU | `HDU-01` | 401 | Dr. Sharma | Nurse Priya | **Admitted** |
| **3** | `UHID-2026-00003` | Vikram Singh | 62 M | ICU | `ICU-02` | 402 | Dr. Patel | Nurse Arun | **Admitted** |
| **4** | `UHID-2026-00004` | Sunita Rao | 51 F | ICU | `ICU-03` | 403 | Dr. Patel | Nurse Arun | **Admitted** |
| **5** | `UHID-2026-00005` | Mohammed Ali | 67 M | ICU | `ICU-04` | 404 | Dr. Gupta | Nurse Meera | **Admitted** |
| **6** | `UHID-2026-00006` | Priya Nair | 34 F | HDU | `HDU-02` | 405 | Dr. Gupta | Nurse Meera | **Admitted** |
| **7** | `UHID-2026-00007` | Amit Verma | 42 M | HDU | `HDU-03` | 406 | Dr. Sharma | Nurse Priya | **Admitted** |
| **8** | `UHID-2026-00008` | Lakshmi Iyer | 70 F | HDU | `HDU-04` | 407 | Dr. Patel | Nurse Arun | **Admitted** |
| **9** | `UHID-2026-00009` | Deepak Joshi | 55 M | HDU | `HDU-05` | 408 | Dr. Gupta | Nurse Meera | **Admitted** |
| **10**| `UHID-2026-00010` | Fatima Begum | 61 F | HDU | `HDU-06` | 409 | Dr. Gupta | Nurse Meera | **Admitted** |

---

## ⚡ Quick Start: Running Jeevan Setu

### 1. Prerequisites
- **Python 3.10+**
- **MySQL 8.0+**
- **Modern Web Browser** (Chrome, Edge, Firefox, Safari)

### 2. Installation & Setup
```powershell
# Clone the repository
git clone https://github.com/Thanush505/Jeevan-Setu.git
cd Jeevan-Setu\Jeevan-Setu-Final

# Create and activate Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
cd JEEVAN_SETU
pip install -r requirements.txt
```

### 3. Launch Dual-Protocol Hospital Gateway
```powershell
# Starts the Flask Server on 0.0.0.0:5000 and auto-spawns HTTPS gateway on 5443
python app.py
```

- **Clinician Login**: [http://127.0.0.1:5000/Login/Login.html](http://127.0.0.1:5000/Login/Login.html)
- **Developer Telemetry Simulator**: [http://127.0.0.1:5000/Developer/Telemetry_Simulator/Telemetry_Simulator.html](http://127.0.0.1:5000/Developer/Telemetry_Simulator/Telemetry_Simulator.html)
- **Mobile Attendant Camera Portal**: `https://<YOUR_LAN_IP>:5443/Attendant/attendant_access.html`

---

## 🧪 Comprehensive Automated Test Suites

```powershell
cd Jeevan-Setu-Final\JEEVAN_SETU

# 1. Test Interactive Patient Scenario Transitions (12 tests)
python -m unittest tests/test_scenario_transitions.py

# 2. Test Developer Telemetry Simulator Diagnostics & RBAC (10 tests)
python -m unittest tests/test_developer_telemetry_simulator.py

# 3. Test Attendant Mobile Camera & Assistance Requests (14 tests)
python -m unittest tests/test_attendant_assistance_requests.py

# 4. Verify 10-Patient Baseline Integrity (100% Passing)
python tests/verify_10_patients.py
```

---

## 📄 License & Credits

- **License**: Released under the [MIT License](LICENSE).
- **Creator & Lead Architect**: [Thanush505](https://github.com/Thanush505)
- **Mission**: *Transforming Critical Care Through Transparent, Explainable, and Objective Clinical Technology.*
