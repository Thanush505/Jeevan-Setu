# Jeevan Setu — System Execution & Run Guide

This document contains the complete set of commands, configuration details, credentials, and URLs required to run, test, and interact with the **Jeevan Setu** Clinical Decision Support and Patient Management System.

---

## 1. Prerequisites & Environment Setup

### 1.1 Python Virtual Environment
From the project root:
```powershell
# Navigate to the workspace root
cd d:\Major_Project\JSA-1

# Activate the virtual environment
.venv\Scripts\Activate.ps1

# Navigate to backend directory
cd JEEVAN_SETU

# Install dependencies (if not already installed)
pip install -r requirements.txt
```

### 1.2 Database Configuration (`JEEVAN_SETU/.env`)
Ensure your `JEEVAN_SETU/.env` matches your MySQL service:
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

## 2. Starting the Application Server

Start the Flask backend application (serves both REST API and frontend static pages):

```powershell
cd d:\Major_Project\JSA-1\JEEVAN_SETU

# Run the Flask development server
python app.py
```

Server will be running at: **`http://127.0.0.1:5000`**

---

## 3. Frontend Portal URLs

| Portal | URL | Description |
| :--- | :--- | :--- |
| **Login Page** | `http://127.0.0.1:5000/Login/Login.html` | Unified multi-role authentication interface |
| **Admin Dashboard** | `http://127.0.0.1:5000/Admin/Administrator_dashboard_/Administrator_dashboard_.html` | Hospital census, occupancy metrics, and critical alerts |
| **Admin Patients** | `http://127.0.0.1:5000/Admin/Admin_patient_management/Admin_patient_management.html` | Patient list, census metrics, and **"+ Admit Patient"** modal |
| **Admin Beds, Wards & Resources** | `http://127.0.0.1:5000/Admin/Admin_beds_wards/Admin_beds_wards.html` | Live bed matrix floorplan, critical care pressure & telemetry |
| **Admin Users & Roles** | `http://127.0.0.1:5000/Admin/Admin_users_roles/Admin_users_roles.html` | Clinician & staff directory, and **"+ Add User"** modal |
| **Admin Attendant QR Access** | `http://127.0.0.1:5000/Admin/Admin_attendant_access/Admin_attendant_access.html` | Permanent patient QR generator, badge printing, revocation & regeneration |
| **Admin Clinical Reports** | `http://127.0.0.1:5000/Admin/Admin_clinical_reports/Admin_clinical_reports.html` | Multi-patient ReportLab PDF generation with permanent hospital header |
| **Admin EWS Analytics** | `http://127.0.0.1:5000/Admin/Admin_ews_analytics/Admin_ews_analytics.html` | Risk score distributions and unit-level vital statistics |
| **Admin Audit Logs** | `http://127.0.0.1:5000/Admin/Admin_audit_logs/Admin_audit_logs.html` | Real-time audit trails (authentication, QR scans, reports) |
| **Doctor Dashboard** | `http://127.0.0.1:5000/Doctor/Doctor_dashboard_/Doctor_dashboard_.html` | Assigned patient roster, summaries, and transfer approvals |
| **Doctor EWS Calculator** | `http://127.0.0.1:5000/Doctor/Doctor_ews_calculator/Doctor_ews_calculator.html` | Bedside vital signs, automated EWS scoring, and triage heuristics |
| **Nurse Dashboard** | `http://127.0.0.1:5000/Nurse/Nurse_dashboard/Nurse_dashboard.html` | Real-time ICU monitoring and nursing shift roster |
| **Nurse Enter Vitals** | `http://127.0.0.1:5000/Nurse/Nurse_enter_vitals/Nurse_enter_vitals.html` | Rapid 4-parameter vital sign recording |
| **Attendant QR Scan Landing** | `http://127.0.0.1:5000/Attendant/attendant_access.html` | Mobile-first scan entry page for family attendants |
| **Attendant Live Dashboard** | `http://127.0.0.1:5000/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html` | Read-only patient health metrics & recovery status |

---

## 4. Default Role Credentials

| Role | Username | Password | Full Name / Details |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` / `admin_js` | `admin123` / `Admin@123` | System Administrator |
| **Doctor 1** | `doctor` / `dr_sharma` | `doctor123` / `Doctor@123` | Dr. Anil Sharma (Cardiology) |
| **Doctor 2** | `dr_patel` | `Doctor@123` | Dr. Kavita Patel (Pulmonology) |
| **Doctor 3** | `dr_gupta` | `Doctor@123` | Dr. Rajiv Gupta (Critical Care) |
| **Nurse 1** | `nurse` / `nurse_priya` | `nurse123` / `Nurse@123` | Priya Menon (ICU) |
| **Nurse 2** | `nurse_arun` | `Nurse@123` | Arun Krishnan (HDU) |
| **Nurse 3** | `nurse_meera` | `Nurse@123` | Meera Jain (General) |

---

## 5. Automated Verification & Testing Commands

```powershell
cd d:\Major_Project\JSA-1\JEEVAN_SETU

# 1. Run Permanent Patient QR Attendant Access test suite (10/10 PASS)
python scratch\test_attendant_qr_lifecycle.py

# 2. Run Manual Attendant Login & Patient Search test
python scratch\test_attendant_manual_login.py

# 3. Run Admin Navigation & Merged Module audit
python scratch\test_admin_navigation.py

# 4. Run Nurse Portal Navigation audit
python scratch\test_nurse_navigation.py

# 4. Run Multi-Patient PDF Report generation test
pytest tests/test_patient_pdf_report.py -v

# 5. Run Patient Admission workflow test
pytest tests/test_patient_admission_workflow.py -v

# 6. Run User Creation & RBAC test
pytest tests/test_user_creation_workflow.py -v

# 7. Run full unit and integration test suite
pytest tests/ -v
```
