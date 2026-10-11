# Jeevan Setu System Rules

- Maintain strict folder confinement inside `d:\Major_Project\JSF-Web_Broswer_simulator`.
- Maintain exactly 10 active admitted patients in the database (Patient IDs 1 through 10).
- If tests or workflows create test patients (> 10) or users (> 17), execute `python JEEVAN_SETU\database\cleanup_patients.py`.
- Adhere to the clinical EWS thresholds (>=7 critical, 5-6 moderate, 1-4 stable) and physiological vital bounds.
- Maintain RBAC permissions and secure JWT authorization across Admin, Doctor, Nurse, and Attendant roles.
- Use Vanilla JS and CSS for frontend development with auto-refresh managers for live synchronization.
