# CHATBOT MERGE REPORT: JEEVAN SETU CONSOLIDATED SYSTEM

## 1. Pre-Merge Architecture Comparison
- **Project 1 (Main Jeevan Setu Application)**:
  - Comprehensive clinical platform running on Flask (Port 5000) with MySQL database (jeevan_setu), JWT authentication, full RBAC, Decision Support Engine, Ward/Bed Management, Vitals tracking, EWS calculations, transfer approval workflow, live alerts, and attendant QR access.
- **Project 2 (Standalone Chatbot Application - 66/chat bot)**:
  - Independent Python service (port 6060) containing enhanced Dr. Setu conversational clinical reasoning, multi-turn dialogue, OpenRouter AI integration with Google Gemma 4, telemetry grounding, and specialized test suites.

---

## 2. Files Migrated from Chatbot Project
| Source File (Project 2) | Target File (Main Project) | Purpose |
|---|---|---|
| modules/openrouter_service.py | JEEVAN_SETU/modules/openrouter_service.py | Centralized OpenRouter API client, model fallback candidates, grounded clinical prompt |
| 	ests/test_openrouter_ai.py | JEEVAN_SETU/tests/test_openrouter_ai.py | 14-point test suite for API security, RBAC guardrails, and telemetry grounding |
| 	ests/test_patient_dropdown_and_rbac.py | JEEVAN_SETU/tests/test_patient_dropdown_and_rbac.py | Doctor/Nurse/Attendant patient isolation and dropdown access tests |
| 	ests/test_doctor_approve_button_and_nurse_guardrail.py | JEEVAN_SETU/tests/test_doctor_approve_button_and_nurse_guardrail.py | Verification of Doctor transfer approval vs Nurse read-only guardrail |
| 	ests/test_advanced_clinical_reasoning.py | JEEVAN_SETU/tests/test_advanced_clinical_reasoning.py | Multi-parameter clinical reasoning, prognosis handling, emergency escalation |
| 	ests/test_conversational_chatbot.py | JEEVAN_SETU/tests/test_conversational_chatbot.py | Conversational dialogue, intent disambiguation, vital trend explanations |

---

## 3. Files in Main Project Modified
- JEEVAN_SETU/modules/openrouter_service.py: Added to core modules with secure environment variable loading.
- JEEVAN_SETU/routes/transfer_routes.py: Cleaned variable references during transfer creation.
- JEEVAN_SETU/.env.example & Root .env.example: Updated with OPENROUTER_API_KEY and OPENROUTER_MODEL=google/gemma-4-31b-it:free placeholders.
- JEEVAN_SETU/tests/test_phase12_transfer_management.py: Aligned audit action assertions with unified logging.
- JEEVAN_SETU/tests/*.py: Adapted 5 chatbot test suites to run natively against the unified Flask app.

---

## 4. Files Intentionally NOT Copied & Rationale
- chat bot/app.py: Standalone http.server harness running on port 6060. NOT copied because the chatbot is now natively routed via Flask chatbot_bp on port 5000.
- chat bot/.env: Raw secrets file. NOT copied to maintain security. Only .env.example placeholders were integrated.
- Duplicate DB wrappers/models: NOT copied. The main MySQL database and models (User, Patient, Vitals, EWSScore, Recommendation, Transfer) remain the authoritative single source of truth.

---

## 5. Conflicts Found & Resolution
- **Port Conflict (6060 vs 5000)**: Chatbot frontend was hardcoded to http://localhost:6060. Resolved by migrating frontend and API requests to same-origin relative URLs (/chatbot/... / /api/v1/chatbot/...).
- **Authorization Scoping**: Standalone chatbot used mock user IDs. Resolved by connecting chatbot endpoints directly to Jeevan Setu's @jwt_required and @permission_required decorators with doctor-patient assignment checks.
- **Model Fallbacks**: Free-tier rate limits were mitigated by adding multi-candidate fallback support in openrouter_service.py (google/gemma-4-31b-it:free, inclusionai/ling-3.0-flash-sante:free, 
vidia/nemotron-3.5-lightning:free, google/gemini-2.0-flash-exp:free).

---

## 6. Authentication & RBAC Integration
- All chatbot API calls require standard Jeevan Setu Bearer JWT tokens.
- **Doctor**: Strictly restricted to querying and viewing assigned patients in the dropdown. Unauthorized cross-patient access returns HTTP 403 Forbidden.
- **Nurse**: Restricted to assigned patients and ward scopes.
- **Attendant**: Read-only patient status access for their specific linked patient only.
- **Admin**: System-wide administrative oversight.

---

## 7. Database Integration & Source of Truth
- Unified MySQL database: jeevan_setu.
- Table clinical_notes created to support historical clinical records.
- Zero duplicate tables or mock stores in production.

---

## 8. OpenRouter & Gemma AI Configuration
- Model: google/gemma-4-31b-it:free (customizable via OPENROUTER_MODEL).
- Environment variable: OPENROUTER_API_KEY.
- Zero frontend exposure of API keys; all AI synthesis happens server-side with strict clinical guardrails.

---

## 9. Frontend Integration & PDF Button Removal
- Doctor AI Assistant UI: Jeevan_setu_frontend/Doctor/Doctor_patient_summary_ai/Doctor_patient_summary_ai.html.
- Dark clinical theme preserved.
- Patient selector dropdown updates live telemetry headers (Name, UHID, Ward, Bed, Latest EWS, Risk).
- PDF Report generation button removed from chatbot UI as requested (preserved in main Doctor Reports portal).

---

## 10. Test Execution Summary
- Total Tests Executed: **125**
- Passed: **125**
- Failed: **0**
- Test suites covered:
  - 	est_openrouter_ai.py (14/14 PASSED)
  - 	est_patient_dropdown_and_rbac.py (5/5 PASSED)
  - 	est_doctor_approve_button_and_nurse_guardrail.py (4/4 PASSED)
  - 	est_advanced_clinical_reasoning.py (6/6 PASSED)
  - 	est_conversational_chatbot.py (14/14 PASSED)
  - 	est_phase3_auth.py (7/7 PASSED)
  - 	est_phase4_rbac.py (5/5 PASSED)
  - 	est_phase12_transfer_management.py (7/7 PASSED)
  - 	est_phase14_notifications_alerts.py (8/8 PASSED)
  - 	est_core_clinical_flow.py (55/55 PASSED)

---

## 11. How to Run the Integrated Jeevan Setu Application
1. **Start the Unified Server**:
   `ash
   cd D:\Major_Project\JSF\Jeevan-Setu-Final\JEEVAN_SETU
   python app.py
   `
2. **Access Doctor AI Chatbot (Dr. Setu)**:
   - URL: http://127.0.0.1:5000/Doctor/Doctor_patient_summary_ai/Doctor_patient_summary_ai.html
   - Or log in as Doctor at http://127.0.0.1:5000/Login.html and click **AI Assistant** in the Doctor sidebar.
