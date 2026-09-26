# Jeevan Setu — Attendant Mobile Access & QR Testing Guide

This guide explains how to access, test, and run the **Jeevan Setu Patient Attendant Mobile Portal** on physical mobile devices over your local Wi-Fi network with real-time QR code scanning and redirection.

---

## 📌 Overview & Architecture

When family attendants visit admitted patients in the ICU or HDU, they can scan the patient's permanent QR badge from their smartphone camera to open the real-time, read-only recovery telemetry dashboard.

```
       [ Admin Portal on PC ]
                 │
                 ▼
     [ Generate Patient QR ]
  (Embeds: http://<LAN-IP>:5000/qr/JS-QR-P...)
                 │
                 ▼
  [ Attendant Scans QR via Mobile Camera (Wi-Fi) ]
                 │
                 ▼
  [ Backend Validates Cryptographic Token ]
                 │
                 ▼
  [ Issues Signed 8-Hour Attendant JWT Session ]
                 │
                 ▼
  [ Automatic 302 Redirection to Live Dashboard ]
  (http://<LAN-IP>:5000/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html?patient_id=<id>)
                 │
                 ▼
  [ Attendant Views Authorized Patient Recovery Telemetry ]
  (Live Vitals, EWS Risk Level, Ward/Bed Telemetry from MySQL)
```

---

## ⚙️ 1. Local Network & Wi-Fi Configuration

Ensure your PC and mobile device are connected to the **same Wi-Fi router**.

| Property | Value | Notes |
| :--- | :--- | :--- |
| **PC Wi-Fi IPv4** | `192.168.1.3` | Local network IP of host PC |
| **Subnet Mask** | `255.255.255.0` | Standard Wi-Fi subnet |
| **Gateway** | `192.168.1.1` | Router gateway |
| **Flask Port** | `5000` | Port used by Jeevan Setu |
| **Do NOT Use** | `192.168.56.1` | (VirtualBox host-only adapter) |

---

## 🛠️ 2. Environment Configuration (`JEEVAN_SETU/.env`)

Ensure `JEEVAN_SETU/.env` contains the network binding parameters:

```env
# Server Network & Mobile Access
HOST=0.0.0.0
PORT=5000
LAN_IP=192.168.1.3
EXTERNAL_BASE_URL=http://192.168.1.3:5000

# Database
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=NewPassword123!
DB_NAME=jeevan_setu
```

---

## 🚀 3. Starting the Server

From your PowerShell terminal:

```powershell
# 1. Navigate to backend directory
cd d:\Major_Project\JSA-1\JEEVAN_SETU

# 2. Activate virtual environment
..\.venv\Scripts\Activate.ps1

# 3. Start the Flask application listening on all interfaces (0.0.0.0:5000)
python app.py
```

The console will confirm:
```
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.1.3:5000
```

---

## 📱 4. Mobile URLs & Access Points

| Page | URL for Mobile Phone (Wi-Fi) | Description |
| :--- | :--- | :--- |
| **Attendant Mobile Sign-In** | `http://192.168.1.3:5000/Attendant/attendant_access.html` | Mobile-first attendant entry page (Manual Search or QR Token) |
| **Live Attendant Dashboard** | `http://192.168.1.3:5000/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html?patient_id=1` | Live read-only telemetry, vitals, condition & EWS |
| **Staff & Clinician Login** | `http://192.168.1.3:5000/Login/Login.html` | Multi-role clinician/admin login |

---

## 🧪 5. End-to-End QR Scanning Workflow Test

### Step A: Generate QR on Admin Portal (PC)
1. Open your browser on PC:
   ```
   http://127.0.0.1:5000/Admin/Admin_attendant_access/Admin_attendant_access.html
   ```
2. Locate any patient (e.g. **Patient 1: Rajesh Kumar**, Bed `ICU-A01`).
3. Click **"View QR"** or **"Generate QR"**.
4. The QR image displayed on screen encodes the mobile-reachable URL:
   ```
   http://192.168.1.3:5000/Attendant/attendant_access.html?token=JS-QR-P1-...
   ```

### Step B: Scan with Smartphone Camera
1. Connect your phone to the same Wi-Fi.
2. Open your phone's native **Camera app** or **Google Lens / QR Scanner**.
3. Point the camera at the QR code on your PC monitor.
4. Tap the recognized link banner to open the page.

### Step C: Attendant Authentication & Live Telemetry
1. The **Attendant Mobile Sign-In** page opens with the patient automatically verified (`UHID-2026-00001 · ICU-A01`).
2. Enter your name (e.g., `Suman Kumar`) and tap **"Enter Live Patient Monitor"**.
3. The live mobile patient dashboard loads instantly with:
   - Patient Name & UHID
   - Ward & Bed Allocation
   - Current Condition & EWS Risk Level
   - Real-time Vitals (Heart Rate, Blood Pressure, Temperature, Respiratory Rate)
   - Clinical Care Update Banner

---

## 🛡️ 6. Windows Firewall Troubleshooting

If your phone displays *“Connection Refused”* or *“Site can’t be reached”*, open PowerShell as **Administrator** and run:

```powershell
netsh advfirewall firewall add rule name="Flask Jeevan Setu (Port 5000)" dir=in action=allow protocol=TCP localport=5000
```

To verify your active Wi-Fi IP address at any time:
```powershell
ipconfig | Select-String -Pattern "IPv4 Address", "Default Gateway", "Wireless LAN" -Context 0,2
```

---

## 🔒 7. Security & Isolation Assurances

1. **Zero Patient PII in QR Code**: The QR image and URL contain only an opaque cryptographic token (`JS-QR-P{id}-{entropy}`). No names, diagnoses, or sensitive health records are embedded in the QR.
2. **Patient Isolation**: A scanned QR token strictly locks the session to that specific patient. Attendants cannot switch to or view another patient's data.
3. **Real-time MySQL Integration**: Data updates dynamically from the central MySQL `jeevan_setu` database with auto-refresh every 8 seconds.
