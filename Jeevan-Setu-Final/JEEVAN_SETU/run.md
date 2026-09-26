# Jeevan Setu — System Execution & Run Guide

This document contains the complete set of commands, configuration details, and credentials required to run, test, and interact with the **Jeevan Setu** Clinical Decision Support and Patient Management System.

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

## 2. Database Initialization & Seeding Commands

If initializing the database or resetting test data:

```powershell
cd d:\Major_Project\JSA-1\JEEVAN_SETU

# Apply database migration (nurse assignments & admission schema)
python scratch\migrate_admission.py

# (Optional) Seed 10 realistic patients, 3 doctors, 3 nurses, 10 attendants:
python scratch\seed_data.py
```

---

## 3. Starting the Application Server

Start the Flask backend application (serves both REST API and Frontend static pages):

```powershell
cd d:\Major_Project\JSA-1\JEEVAN_SETU

# Run the Flask development server
python app.py
```

Server will be running at: **`http://127.0.0.1:5000`**

---

## 4. Accessing Frontend Portals

Once the server is running, open the browser to any of the following portals:

| Portal | URL | Description |
| :--- | :--- | :--- |
| **Login Page** | `http://127.0.0.1:5000/Login/Login.html` | Unified login with role detection |
| **Admin Patient Management** | `http://127.0.0.1:5000/Admin/Admin_patient_management/Admin_patient_management.html` | Patient list, census metrics, and **"+ Admit Patient"** workflow |
| **Admin Users & Roles** | `http://127.0.0.1:5000/Admin/Admin_users_roles/Admin_users_roles.html` | Staff directory, RBAC summary, and **"+ Add User"** workflow |
| **Admin Beds & Wards** | `http://127.0.0.1:5000/Admin/Admin_beds_wards/Admin_beds_wards.html` | Live ICU/HDU bed occupancy status and floorplan |
| **Doctor EWS Calculator** | `http://127.0.0.1:5000/Doctor/Doctor_ews_calculator/Doctor_ews_calculator.html` | Patient vital signs, EWS calculation, and clinical recommendations |
| **Nurse Enter Vitals** | `http://127.0.0.1:5000/Nurse/Nurse_enter_vitals/Nurse_enter_vitals.html` | Bedside vitals monitoring and rapid triage |
| **Attendant Dashboard** | `http://127.0.0.1:5000/Attendant/Attendant_dashboard/Attendant_dashboard.html` | Family/attendant patient status and QR code access |

---

## 5. Default Role Credentials

| Role | Username | Password | Full Name / Details |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin_js` | `Admin@123` | System Administrator |
| **Doctor 1** | `dr_sharma` | `Doctor@123` | Dr. Anil Sharma (Cardiology) |
| **Doctor 2** | `dr_patel` | `Doctor@123` | Dr. Kavita Patel (Pulmonology) |
| **Doctor 3** | `dr_gupta` | `Doctor@123` | Dr. Rajiv Gupta (Critical Care) |
| **Nurse 1** | `nurse_priya` | `Nurse@123` | Priya Menon (ICU) |
| **Nurse 2** | `nurse_arun` | `Nurse@123` | Arun Krishnan (HDU) |
| **Nurse 3** | `nurse_meera` | `Nurse@123` | Meera Jain (General) |
| **Attendant** | `att_rajesh` | `Attendant@123` | Suman Kumar (Attendant for P001) |

---

## 6. Running Automated Tests

Run the test suite to verify endpoints and workflows:

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

# 5. Run patient admission workflow test
pytest tests/test_patient_admission_workflow.py -v

# 6. Run user creation & RBAC workflow test
pytest tests/test_user_creation_workflow.py -v

# 7. Run full test suite
pytest tests/ -v
```

---

## 7. Key REST API Endpoints

### 7.1 User Management (`/api/v1/users`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/users` | List, search, filter, and paginate users | `Bearer <JWT>` (Admin) |
| `POST` | `/api/v1/users` | Create user with role assignment and sync to doctors/nurses | `Bearer <JWT>` (Admin) |
| `GET` | `/api/v1/users/roles-summary` | Get role definitions, active user counts, and departments | `Bearer <JWT>` (Admin) |
| `GET` | `/api/v1/users/{id}` | Retrieve specific user profile | `Bearer <JWT>` (Admin) |
| `PUT` | `/api/v1/users/{id}` | Update user details, role, department, or status | `Bearer <JWT>` (Admin) |
| `POST` | `/api/v1/users/{id}/reset-password` | Admin direct password reset | `Bearer <JWT>` (Admin) |

### 7.2 Patient Intake & Admission (`/api/v1/patients`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/patients/admission-options` | Returns next UHID, wards, available beds, and staff workload | `Bearer <JWT>` |
| `POST` | `/api/v1/patients/admit` | Executes atomic admission transaction | `Bearer <JWT>` (Admin) |
| `GET` | `/api/v1/patients` | Retrieves admitted patient roster | `Bearer <JWT>` |
