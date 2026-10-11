# JEEVAN SETU (जीवन सेतु) 🏥

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Backend-Flask-black.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/Database-MySQL-00758F.svg?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite%20Snapshot-003B57.svg?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![JavaScript](https://img.shields.io/badge/Frontend-HTML5%20%2B%20Vanilla%20JS-F7DF1E.svg?logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Build-Passing-brightgreen.svg)]()

> **Intelligent ICU ↔ HDU Clinical Decision Support, Real-Time Bedside Telemetry Simulation & Patient Transfer System**

---

## 📌 Overview

**Jeevan Setu** (*Bridge of Life*) is an enterprise-grade hospital clinical decision support system (CDSS) designed to optimize critical care patient monitoring and streamline clinical transfers between **Intensive Care Units (ICU)**, **High Dependency Units (HDU)**, and General Wards.

By combining continuous vital signs telemetry, automated **Early Warning Score (EWS)** calculation, explainable clinical heuristics, a **Universal Global Alert System**, prolonged **Ready-to-Transfer Monitoring**, permanent patient-specific QR attendant portals, an **Interactive Bedside Telemetry Simulator**, and multi-patient ReportLab clinical reports, Jeevan Setu provides clinical staff with objective, real-time decision support.

---

## ✨ Key Capabilities & Modules

### 🚨 1. Global Emergency Alert System
- **Real-Time Critical Detection**: Automatically detects when patient vitals trigger critical deviations ($\text{EWS} \ge 7$ or single extreme vital parameter failure).
- **Universal Global Popup**: Dispatches instant emergency alert popups across all Doctor and Nurse pages without requiring users to navigate back to the dashboard.
- **Smart Queue & Modal**: Audio-visual indicators, vitals telemetry, patient UHID/bed info, and one-click clinical navigation.
- **Duplicate Prevention & Auto-Resolution**: Automatically marks critical alerts resolved when the patient's condition stabilizes.

---

### 🔄 2. Atomic Transfer Approval & HDU Bed Allocation
- **Prolonged Transfer Detection**: Monitors patients in *Ready-to-Transfer* state; alerts when wait time exceeds threshold (default: 120 minutes).
- **Doctor-Only Transfer Approval**: Only Attending Doctors and Administrators have authorization to approve transfers.
- **Strict Nurse RBAC Enforcement**: Nurse portal displays read-only transfer status. Unauthorized transfer approval attempts return `HTTP 403 Forbidden` and log a security audit event.
- **Atomic Concurrency-Safe Bed Allocation**: Row-level locking (`SELECT FOR UPDATE`) atomically frees the previous ICU bed and occupies the target HDU bed in a single transaction.

---

### 📟 3. Bedside Telemetry Simulator (CLI & GUI)
- **Standalone CLI Simulator** (`telemetry_simulator/`): Simulates a multi-parameter bedside monitor streaming live vitals ($HR$, $SBP$, $RR$, $Temp$) into the Jeevan Setu pipeline via HTTP `POST /vitals/patient/{id}/submit`.
- **5 Clinical Simulation Scenarios**:
  - `stable`: Vitals fluctuate within normal ranges.
  - `deterioration`: Progressive degradation towards critical EWS score.
  - `recovery`: Vitals improve steadily from critical back to stable baseline.
  - `critical`: Immediate acute physiological collapse triggering emergency alerts.
  - `manual`: Custom user-defined vital parameter inputs.
- **Browser Developer GUI**: Accessible directly at [`/Developer/Telemetry_Simulator/Telemetry_Simulator.html`](http://127.0.0.1:5000/Developer/Telemetry_Simulator/Telemetry_Simulator.html) for real-time visual testing and live vital streaming.

---

### 🛡️ 4. Administrator Portal
- **Real-Time Census**: Live hospital census, active ICU/HDU bed occupancy, pending transfers, and critical alerts.
- **Bed Matrix & Resource Utilization**: Floorplan grid for ICU-A and HDU-B with capacity tracking and high-load warnings.
- **User & Staff Management**: Clinician accounts with bcrypt/werkzeug hashed passwords and granular permissions.
- **Permanent Patient QR Attendant Access**: Cryptographically secure permanent tokens (`JS-QR-P{patient_id}-{entropy}`) for mobile visitor badges.
- **Multi-Patient Clinical Reports**: ReportLab PDF generator with two-pass repeating hospital header canvas.
- **Audit Logs**: Real-time audit trails tracking authentication, transfers, clinical reports, and QR scans.

---

### 📱 5. Mobile Attendant Portal & QR Access
- **Mobile-First Scan Landing** (`/Attendant/attendant_access.html`): Mobile-responsive layout for family members.
- **Strict Data Isolation**: Read-only clinical updates dynamically bound to the verified QR token with zero cross-patient data exposure.

---

### 🤖 6. Jeevan Setu AI Clinical Assistant (OpenRouter & Gemma 4)
- Powered by OpenRouter integration (`google/gemma-4-31b-it:free`).
- **Context-Grounded Clinical Reasoning (CCRL)**: Answers clinician inquiries against live database telemetry and generates structured clinical summaries.

---

## 👥 Default Credentials & Baseline Accounts

| Role | Username | Password | Full Name | Department / Ward |
| :--- | :--- | :--- | :--- | :--- |
| **🛡️ Admin** | `admin_js` | `Admin@123` | System Administrator | Administration |
| **👨‍⚕️ Doctor 1** | `dr_sharma` | `Doctor@123` | Dr. Anil Sharma (Cardiology) | Assigned to Patients 1, 2, 7 |
| **👨‍⚕️ Doctor 2** | `dr_patel` | `Doctor@123` | Dr. Kavita Patel (Pulmonology) | Assigned to Patients 3, 4, 8 |
| **👨‍⚕️ Doctor 3** | `dr_gupta` | `Doctor@123` | Dr. Rajiv Gupta (Neurology) | Assigned to Patients 5, 6, 9, 10 |
| **👩‍⚕️ Nurse 1** | `nurse_priya` | `Nurse@123` | Priya Menon | ICU Ward |
| **👩‍⚕️ Nurse 2** | `nurse_arun` | `Nurse@123` | Arun Krishnan | HDU Ward |
| **👩‍⚕️ Nurse 3** | `nurse_meera` | `Nurse@123` | Meera Jain | ICU/HDU Ward |
| **📱 Attendant** | `att_rajesh` | `Attendant@123` | Suman Kumar | Family Attendant for Patient 1 |

---

## 🏥 Canonical 10-Patient Census & Bed Allocation

As defined in [`rules.md`](rules.md), the system maintains exactly **10 active patients**:

| Patient ID | UHID | Name | Age / Gender | Ward | Bed | Bed ID | Assigned Doctor | Assigned Nurse | Status |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- | :---: |
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

- **Bed Allocation**: 10 occupied beds (400–409), 48 available beds (`ICU-A01..A20` & `HDU-B01..B20`).
- **Database Reset & Cleanup**: Run `python JEEVAN_SETU/database/cleanup_patients.py` to restore this 10-patient baseline after test runs.

---

## 🏛️ System Architecture

```mermaid
graph TD
    A[Staff / Clinician / Attendant Browser] -->|REST API / HTTP| B[Flask Application Server]
    B --> C[RBAC & JWT / Session Auth]
    B --> D[4-Parameter EWS & Decision Engine]
    B --> E[Global Emergency & Transfer Alert Engine]
    B --> F[ReportLab Clinical PDF Engine]
    B --> G[QR Cryptographic Token Engine]
    B --> I[Developer Telemetry Simulator GUI]
    T[Telemetry Simulator CLI] -->|POST /vitals/patient/{id}/submit| B
    D --> H[(MySQL Database)]
    E --> H
    F --> H
    G --> H
    H -->|Live Vitals, Alerts, Beds & Audits| B
    B -->|Global Alert JSON / UI / PDF Stream| A
```

---

## 📂 Project Structure

```
Jeevan-Setu/
├── rules.md                     # Operational, clinical, and architectural system rules
├── schema.db                    # Synchronized SQLite database snapshot
├── Jeevan-Setu-Final/           # Unified production application root
│   ├── rules.md                 # System rules copy for local reference
│   ├── run.md                   # Complete operational run guide & credentials
│   ├── JEEVAN_SETU/             # Flask Backend Application
│   │   ├── app.py               # Main Flask server entrypoint
│   │   ├── config.py            # Configuration & dynamic LAN IP detection
│   │   ├── requirements.txt     # Python dependencies
│   │   ├── database/            # Database assets & management utilities
│   │   │   ├── schema.sql       # Authoritative MySQL DDL (27 tables)
│   │   │   ├── schema.db        # SQLite database snapshot
│   │   │   ├── sync_schema.py   # Database scanner & schema sync script
│   │   │   ├── cleanup_patients.py # 10-patient baseline restoration tool
│   │   │   └── db.py            # MySQL thread-safe connection pooling
│   │   ├── models/              # Data models (Patient, Vitals, EWS, Alert, User, Bed, Transfer)
│   │   ├── routes/              # Modular Flask blueprints (alert, vitals, patient, bed, transfer, developer)
│   │   └── tests/               # Pytest automated test suites
│   │
│   ├── Jeevan_setu_frontend/    # Frontend UI Pages & Assets
│   │   ├── Admin/               # Hospital Administrator management pages
│   │   ├── Doctor/              # Physician dashboards & review views
│   │   ├── Nurse/               # Nursing vitals monitoring & bedside views
│   │   ├── Attendant/           # Mobile QR attendant landing & patient replica view
│   │   ├── Developer/           # Browser-based live Telemetry Simulator GUI
│   │   ├── Login/               # Multi-role authentication interface
│   │   └── global_alert_manager.js # Real-time emergency alert manager
│   │
│   └── telemetry_simulator/     # Standalone Bedside Telemetry Simulator
│       ├── simulator.py         # Interactive & automated CLI vital sign simulator
│       ├── requirements.txt     # Simulator dependencies
│       └── tests/               # 54 passing simulator test suites
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.10+**
- **MySQL 8.0+**
- **Git**

---

### 2. Setup Virtual Environment & Dependencies
```powershell
# Navigate to application folder
cd Jeevan-Setu-Final

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
cd JEEVAN_SETU
pip install -r requirements.txt
```

---

### 3. Database Configuration (`.env`)
Verify `JEEVAN_SETU/.env`:
```env
HOST=0.0.0.0
PORT=5000
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=jeevan_setu
SECRET_KEY=jeevan-setu-dev-secret-key-2026
JWT_SECRET=jeevan-setu-dev-secret-key-2026
```

---

### 4. Run the Application Server
```powershell
cd Jeevan-Setu-Final\JEEVAN_SETU
python app.py
```
- **Local Browser**: [http://127.0.0.1:5000/Login/Login.html](http://127.0.0.1:5000/Login/Login.html)
- **Local Network / Wi-Fi**: `http://<LAN_IP>:5000/Login/Login.html`

---

### 5. Run the Telemetry Simulator (Optional)
```powershell
cd Jeevan-Setu-Final\telemetry_simulator

# Interactive mode
python simulator.py

# Automated scenarios:
python simulator.py --patient 1 --scenario stable --interval 3
python simulator.py --patient 2 --scenario deterioration --interval 5
python simulator.py --patient 3 --scenario recovery --interval 5
```

---

## 🧪 Testing & Verification

```powershell
cd Jeevan-Setu-Final\JEEVAN_SETU

# 1. Test Global Emergency Alert System
pytest tests/test_global_emergency_transfer_alerts.py -v

# 2. Test Patient Admission Workflow
pytest tests/test_patient_admission_workflow.py -v

# 3. Test Multi-Patient PDF Report Generation
pytest tests/test_patient_pdf_report.py -v

# 4. Test Auto-Refresh System
pytest tests/test_auto_refresh_system.py -v

# 5. Test Telemetry Simulator
cd ..\telemetry_simulator
python -m pytest tests/ -v
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author & Acknowledgments

- **Lead Developer**: [Thanush505](https://github.com/Thanush505)
- Developed for **Jeevan Setu — Intelligent ICU ↔ HDU Clinical Decision Support System**.
