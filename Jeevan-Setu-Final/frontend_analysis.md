# 🏥 Jeevan Setu — Frontend Analysis

## What Is This Project?

**Jeevan Setu** ("Bridge of Life") is an **ICU ↔ HDU Intelligent Transfer Decision Support System**. It helps hospital staff monitor patient vitals, compute **Early Warning Scores (EWS)** based on NEWS2 guidelines, and make data-driven decisions about transferring patients between the **ICU** (Intensive Care Unit) and **HDU** (High Dependency Unit).

---

## Frontend Architecture at a Glance

| Aspect | Details |
|---|---|
| **Format** | Static HTML prototypes — each page is a standalone `code.html` + `screen.png` mockup |
| **CSS Framework** | TailwindCSS (CDN) with a custom Material 3 / Material You–inspired design token system |
| **Fonts** | Poppins (headings) + Inter (body) via Google Fonts |
| **Icons** | Material Symbols Outlined |
| **Color System** | Full Material Design 3 surface/on-surface token palette (primary `#004AC6`, blue healthcare theme) |
| **Responsive** | Desktop-first for Admin/Doctor/Nurse; Mobile-first for Attendant |
| **JS** | Inline — simple form handling, toggle visibility, loading overlays |
| **Backend coupling** | None yet — these are pure UI prototypes (no API calls wired) |

---

## 4 User Roles & Their Modules

### 1. 🔐 Login (Shared Entry Point)
Single page with role selection (Clinical: Doctor/Nurse vs. Administrative).

### 2. 👨‍💼 Admin — 13 pages
Full hospital operations management:

| Module | Purpose |
|---|---|
| Dashboard | KPI overview: patients, bed occupancy, transfers, critical alerts, EWS distribution |
| Patient Management | CRUD patients, search, status tracking |
| Beds & Wards | ICU/HDU bed occupancy, availability matrix |
| Transfers Management | Approve/reject ICU↔HDU transfers |
| Users & Roles | Staff management, role assignment |
| Attendant Access | QR-based attendant provisioning |
| EWS Analytics | Risk heatmaps, trend charts by ward, clinical escalation metrics |
| Resource Utilization | Bed/staff utilization analytics |
| Clinical Reports | Patient reports, transfer reports |
| Notification Settings | Alert threshold configuration |
| System Settings | App-wide config |
| Audit Logs | Activity trail for compliance |
| Backup & Restore | Data backup management |

### 3. 🩺 Doctor — 14 pages
Clinical decision-making focus:

| Module | Purpose |
|---|---|
| Dashboard | ICU patient overview table with vitals, EWS, transfer status; score distribution donut; occupancy gauge |
| My Patients | Assigned patient list |
| All Patients | Hospital-wide patient view |
| Patient Search | Search by name/ID/bed |
| EWS Calculator | Vitals → NEWS2 score calculator with clinical guidance |
| EWS Trends | 24h score trend charts |
| Transfer Recommendations | AI-generated ICU→HDU or HDU→ICU recommendations |
| Patient Summary (AI) | XAI-powered patient condition summary |
| Pending Approvals | Transfer requests awaiting doctor sign-off |
| Alerts & Notifications | Critical/warning alert feed |
| Patient Reports | Generate/download clinical reports |
| Transfer Reports | Transfer history and outcomes |
| Audit Logs | Doctor activity trail |
| Settings | Preferences |

### 4. 👩‍⚕️ Nurse — 12 pages
Bedside care & vitals entry:

| Module | Purpose |
|---|---|
| Dashboard | Assigned patients overview with EWS scores, status badges, recent alerts |
| My Patients | Nurse's assigned patient list |
| Patient Monitoring | Real-time vitals monitoring |
| Enter Vitals | Form: HR, RR, SBP, DBP, Temp, SpO₂, AVPU → Save & Calculate EWS |
| I/O Chart | Intake/output fluid tracking |
| Medication Log | Medication administration records |
| Nursing Notes | Free-text clinical observations |
| Alerts | Critical alert notifications |
| Tasks | Pending nursing tasks |
| Transfers | Transfer status for nurse's patients |
| EWS Calculator | Quick EWS calculation tool |
| Reports | Nursing shift reports |

### 5. 👨‍👩‍👦 Attendant (Mobile) — 2 pages
Patient family member view (mobile-optimized):

| Module | Purpose |
|---|---|
| Login | Mobile login via Phone/Patient ID + PIN/OTP + QR code option |
| Patient Update | Live status: EWS score, vitals (HR, SpO₂, Temp), transfer status timeline, recent updates, "Call Nurse" CTA |

---

## Design System Summary

```
Primary:        #004AC6 (deep blue)
Primary Container: #2563EB
Secondary:      #006591 (teal accent)
Tertiary:       #46566C
Background:     #F9F9FF (off-white)
Surface layers:  5 elevation levels (lowest → highest)
Error:          #BA1A1A
```

- **Card pattern**: White cards (`surface-container-lowest`) with `shadow-xl`, `rounded-xl`, `gap-lg` padding
- **Sidebar**: Dark navy (`#0F1729`-ish) with white text, active state uses primary blue highlight
- **Status badges**: Green (Stable/Low), Orange/Blue (Medium/Observation), Red (Critical/High)
- **Animations**: `fadeInUp` entrance, hover scale/translate micro-interactions, loading spinner overlay

---

## Key Observations

> [!IMPORTANT]
> These are **static HTML prototypes only** — they are not yet connected to the Flask backend in [`JEEVAN_SETU/`](file:///d:/Major_Project/JSA-1/JEEVAN_SETU). The backend has 9 API blueprint modules (auth, patients, vitals, decisions, alerts, explanations, chatbot, reports, attendant) ready to be wired up.

> [!NOTE]
> The frontend is currently **41 standalone HTML files** across 4 roles. Each file is self-contained with its own Tailwind config and styles — there is no shared component system, routing, or state management.

> [!TIP]
> The design quality is excellent — clean, professional healthcare UI with proper data visualization placeholders (donut charts, line graphs, heatmaps, progress indicators). The Material 3 token system ensures consistency.

---

## Total Page Inventory

| Role | Pages | Layout |
|---|---|---|
| Login | 1 | Centered card |
| Admin | 13 | Sidebar + content |
| Doctor | 14 | Sidebar + content |
| Nurse | 12 | Sidebar + content |
| Attendant | 2 | Mobile card stack |
| **Total** | **42 pages** | |
