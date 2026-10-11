# Jeevan Setu — System Execution & Run Guide

This document contains the complete set of commands, configuration details, credentials, portal URLs, telemetry simulator instructions, and testing workflows required to run and test the **Jeevan Setu** Clinical Decision Support and Patient Management System.

---

## 1. Prerequisites & Environment Setup

### 1.1 Python Virtual Environment
From the workspace root:
```powershell
# Navigate to the workspace root
cd D:\Major_Project\JSF\Jeevan-Setu-Final

# Activate the virtual environment
.venv\Scripts\Activate.ps1

# Install backend dependencies
cd JEEVAN_SETU
pip install -r requirements.txt
```

### 1.2 Database Configuration (`JEEVAN_SETU/.env`)
Ensure `JEEVAN_SETU/.env` matches your MySQL service:
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=NewPassword123!
DB_NAME=jeevan_setu
JWT_SECRET_KEY=jeevan-setu-super-secret-jwt-key-2026-production
JWT_EXPIRATION_HOURS=24
FLASK_ENV=development
DEBUG=True
PORT=5000
```

---

## 2. Database Initialization & Seeding Commands

If initializing the database for the first time or resetting test data:

```powershell
cd D:\Major_Project\JSF\Jeevan-Setu-Final\JEEVAN_SETU

# 1. Apply database migrations
python database\migrate.py

# 2. (Optional) Apply admission schema & nurse assignments
python scratch\migrate_admission.py

# 3. (Optional) Seed realistic demo patients, doctors, nurses, and attendants:
python scratch\seed_data.py
```

---

## 3. Starting the Application Server

Start the Flask backend application (serves both REST API and frontend static pages):

```powershell
cd D:\Major_Project\JSF\Jeevan-Setu-Final\JEEVAN_SETU

# Run the Flask development server
python app.py
```

Server will be running at: **`http://127.0.0.1:5000`**

---

## 4. Running the Local ICU Telemetry Simulator

The telemetry simulator simulates a bedside multi-parameter monitor (HR, RR, SBP, Temperature) and sends live vitals into the Jeevan Setu pipeline.

### 4.1 Simulator Setup
```powershell
cd D:\Major_Project\JSF\Jeevan-Setu-Final\telemetry_simulator

# Install dependencies
pip install -r requirements.txt

# (Optional) Copy environment configuration
copy .env.example .env
```

### 4.2 Run Interactive Mode
```powershell
python simulator.py
```
This presents an interactive CLI menu to:
1. Select an admitted patient (or enter a Patient ID)
2. Choose a simulation scenario (`stable`, `deterioration`, `recovery`, `critical`, `manual`)
3. Set the telemetry broadcast interval (default: 5 seconds)
4. Monitor live telemetry dispatches and responses

### 4.3 Run Command-Line Arguments Mode
```powershell
# Stable vitals for Patient 1 at 3-second intervals
python simulator.py --patient 1 --scenario stable --interval 3

# Gradual physiological deterioration for Patient 2
python simulator.py --patient 2 --scenario deterioration --interval 5

# Physiological recovery scenario for Patient 3
python simulator.py --patient 3 --scenario recovery --interval 5

# Rapid critical event escalation
python simulator.py --patient 1 --scenario critical --interval 2

# Custom manual baseline values
python simulator.py --patient 1 --scenario manual --hr 125 --sbp 85 --rr 28 --temp 39.1 --interval 5
```

### 4.4 Run Telemetry Simulator Test Suite
```powershell
cd D:\Major_Project\JSF\Jeevan-Setu-Final\telemetry_simulator
python -m pytest tests/ -v
```
*(54 passing tests covering client, scenarios, validation, configuration, and isolation)*

---

## 5. Frontend Portal URLs

| Portal | URL | Description |
| :--- | :--- | :--- |
| **Login Page** | `http://127.0.0.1:5000/Login/Login.html` | Unified multi-role authentication interface |
| **Admin Dashboard** | `http://127.0.0.1:5000/Admin/Administrator_dashboard_/Administrator_dashboard_.html` | Hospital census, occupancy metrics, and critical alerts |
| **Admin Patients** | `http://127.0.0.1:5000/Admin/Admin_patient_management/Admin_patient_management.html` | Patient list, census metrics, and **"+ Admit Patient"** modal |
| **Admin Beds, Wards & Resources** | `http://127.0.0.1:5000/Admin/Admin_beds_wards/Admin_beds_wards.html` | Live bed matrix floorplan, critical care pressure & telemetry |
| **Admin Users & Roles** | `http://127.0.0.1:5000/Admin/Admin_users_roles/Admin_users_roles.html` | Clinician & staff directory, and **"+ Add User"** modal |
| **Admin Attendant QR Access** | `http://127.0.0.1:5000/Admin/Admin_attendant_access/Admin_attendant_access.html` | Permanent patient QR generator, badge printing, revocation & regeneration |
| **Admin Clinical Reports** | `http://127.0.0.1:5000/Admin/Admin_clinical_reports/Admin_clinical_reports.html` | Multi-patient ReportLab PDF generation with hospital header |
| **Admin EWS Analytics** | `http://127.0.0.1:5000/Admin/Admin_ews_analytics/Admin_ews_analytics.html` | Risk score distributions and unit-level vital statistics |
| **Admin Audit Logs** | `http://127.0.0.1:5000/Admin/Admin_audit_logs/Admin_audit_logs.html` | Real-time audit trails (authentication, QR scans, reports) |
| **Doctor Dashboard** | `http://127.0.0.1:5000/Doctor/Doctor_dashboard_/Doctor_dashboard_.html` | Assigned patient roster, summaries, and transfer approvals |
| **Doctor EWS Calculator** | `http://127.0.0.1:5000/Doctor/Doctor_ews_calculator/Doctor_ews_calculator.html` | Bedside vital signs, automated EWS scoring, and triage heuristics |
| **Nurse Dashboard** | `http://127.0.0.1:5000/Nurse/Nurse_dashboard/Nurse_dashboard.html` | Real-time ICU monitoring and nursing shift roster |
| **Nurse Enter Vitals** | `http://127.0.0.1:5000/Nurse/Nurse_enter_vitals/Nurse_enter_vitals.html` | Rapid 4-parameter vital sign recording |
| **Attendant QR Scan Landing** | `http://127.0.0.1:5000/Attendant/attendant_access.html` | Mobile-first scan entry page for family attendants |
| **Attendant Live Dashboard** | `http://127.0.0.1:5000/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html` | Read-only patient health metrics & recovery status |

---

## 6. Default Role Credentials

| Role | Username | Password | Full Name / Details |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` / `admin_js` | `admin123` / `Admin@123` | System Administrator |
| **Doctor 1** | `doctor` / `dr_sharma` | `doctor123` / `Doctor@123` | Dr. Anil Sharma (Cardiology) |
| **Doctor 2** | `dr_patel` | `Doctor@123` | Dr. Kavita Patel (Pulmonology) |
| **Doctor 3** | `dr_gupta` | `Doctor@123` | Dr. Rajiv Gupta (Critical Care) |
| **Nurse 1** | `nurse` / `nurse_priya` | `nurse123` / `Nurse@123` | Priya Menon (ICU) |
| **Nurse 2** | `nurse_arun` | `Nurse@123` | Arun Krishnan (HDU) |
| **Nurse 3** | `nurse_meera` | `Nurse@123` | Meera Jain (General) |
| **Attendant** | `att_rajesh` | `Attendant@123` | Suman Kumar (Attendant for P001) |

---

## 7. Verification & Automated Testing Commands

```powershell
cd D:\Major_Project\JSF\Jeevan-Setu-Final\JEEVAN_SETU

# 1. Run Multi-Patient PDF Report generation test
pytest tests/test_patient_pdf_report.py -v

# 2. Run Patient Admission workflow test
pytest tests/test_patient_admission_workflow.py -v

# 3. Run User Creation & RBAC test
pytest tests/test_user_creation_workflow.py -v

# 4. Run Doctor critical alert & EWS score test
pytest tests/test_doctor_critical_alert_ews_score.py -v

# 5. Run Decision Engine tests
pytest tests/test_decision.py -v

# 6. Run Telemetry Simulator tests
cd ..\telemetry_simulator
python -m pytest tests/ -v
```

---

## 8. Key REST API Endpoints

### 8.1 Telemetry & Vital Signs (`/vitals`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/vitals/patient/{id}/submit` | Submit bedside vital readings (HR, RR, SBP, Temp) | Optional in Local Dev |
| `GET` | `/vitals/patient/{id}/latest` | Fetch latest vital parameters & calculated EWS | Bearer `<JWT>` |
| `GET` | `/vitals/patient/{id}/history` | Fetch historical vitals timeline | Bearer `<JWT>` |

### 8.2 User Management (`/api/v1/users`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/users` | List, search, filter, and paginate users | `Bearer <JWT>` (Admin) |
| `POST` | `/api/v1/users` | Create user with role assignment and sync | `Bearer <JWT>` (Admin) |
| `GET` | `/api/v1/users/roles-summary` | Role definitions, active user counts | `Bearer <JWT>` (Admin) |
| `GET` | `/api/v1/users/{id}` | Retrieve specific user profile | `Bearer <JWT>` (Admin) |
| `PUT` | `/api/v1/users/{id}` | Update user details, role, department | `Bearer <JWT>` (Admin) |
| `POST` | `/api/v1/users/{id}/reset-password` | Admin direct password reset | `Bearer <JWT>` (Admin) |

### 8.3 Patient Intake & Admission (`/api/v1/patients`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/patients/admission-options` | Returns next UHID, wards, available beds | `Bearer <JWT>` |
| `POST` | `/api/v1/patients/admit` | Executes atomic admission transaction | `Bearer <JWT>` (Admin) |
| `GET` | `/api/v1/patients` | Retrieves admitted patient roster | `Bearer <JWT>` |
