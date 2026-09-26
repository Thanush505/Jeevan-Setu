# JEEVAN SETU (Backend & APIs) 🏥

**Jeevan Setu** — Intelligent Clinical Decision Support, Patient Transfer Management & Attendant Access System.

---

## 📌 Overview

The `JEEVAN_SETU` backend is powered by **Flask (Python)** and **MySQL**, providing:
- **Real-Time Vital Assessment & Automated EWS Scoring** (HR, SBP, RR, Temp).
- **Explainable Decision Engine** for clinical triage and ICU ↔ HDU patient transfer heuristics.
- **Permanent Patient-Specific QR Attendant Access Engine** with cryptographic token validation (`JS-QR-P{patient_id}-{entropy}`).
- **Two-Pass Multi-Patient Report Engine (ReportLab)** with repeating hospital headers, EWS parameter breakdowns, and audit trails.
- **Role-Based Access Control (RBAC)** enforced via JWT Bearer authentication.
- **Consolidated Bed Allocation & Resource Telemetry Analytics**.

---

## 🛠️ Tech Stack & Dependencies

| Layer | Technology |
| :--- | :--- |
| **Backend Framework** | Flask (Python 3.10+) |
| **Database** | MySQL 8.0+ |
| **Security & Auth** | PyJWT, bcrypt, cryptographically secure tokens |
| **PDF Generation** | ReportLab (two-pass canvas, custom medical emblems) |
| **QR Code Engine** | qrcode (Pillow, base64 data URLs) |
| **Testing** | pytest, requests |

---

## 📂 Project Structure

```
JEEVAN_SETU/
├── app.py                  # Main Flask app (entry point & router)
├── config.py               # Hospital metadata & database configuration
├── requirements.txt        # Python dependencies
├── database/               # Database connection & schema tables
│   ├── schema.sql          # MySQL table definitions
│   ├── init_db.py          # Database initialization & seed data
│   └── migration_manager.py# Automated SQL schema migrations
├── models/                 # Database models (Patient, Vitals, EWS, User, Bed, QRToken, Report, etc.)
├── modules/                # Decision heuristics, ReportLab engine & analytics
├── routes/                 # REST API Blueprints (Auth, Patient, Vitals, Bed, Attendant, Report, User)
├── static/                 # Static assets, styles & scripts
├── utils/                  # RBAC decorators, token helpers, validators
└── tests/                  # Automated pytest test suites
```

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure .env file
# DB_HOST=127.0.0.1, DB_USER=root, DB_PASSWORD=your_password, DB_NAME=jeevan_setu

# 3. Initialize the database
python database/init_db.py

# 4. Run the application
python app.py
```

The application runs on `http://127.0.0.1:5000`.

---

## 🧪 Test Execution

```bash
# Run all pytest suites
pytest tests/ -v

# Run Permanent Patient QR Attendant Access Lifecycle tests (10/10 PASS)
python scratch/test_attendant_qr_lifecycle.py

# Run Admin Navigation & Merged Module tests
python scratch/test_admin_navigation.py
```

---

## 📄 License

This project is licensed under the MIT License.
