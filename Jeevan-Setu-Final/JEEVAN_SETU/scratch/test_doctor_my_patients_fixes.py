import sys
import os
import re
import urllib.request
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import execute_query
from services.auth_service import AuthService

def test_no_admit_button_in_doctor_portal():
    print("\n[TEST 1] Verifying '+ Admit' button is NOT in Doctor My Patients & All Patients pages...")
    for page in ["Doctor_my_patients.html", "Doctor_all_patients.html"]:
        folder = page.replace(".html", "")
        html_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "Jeevan_setu_frontend", "Doctor", folder, page
        )
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "add</span> Admit" not in content, f"Error: '+ Admit' button still exists in {page}!"
        assert "Admit</button>" not in content, f"Error: 'Admit</button>' still found in {page}!"
        print(f" -> PASSED: '+ Admit' button successfully removed from {page}.")

def test_admin_admit_intact():
    print("\n[TEST 2] Verifying Admin Admission functionality is intact...")
    admin_html_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "Jeevan_setu_frontend", "Admin", "Admin_patient_management", "Admin_patient_management.html"
    )
    with open(admin_html_path, "r", encoding="utf-8") as f:
        admin_content = f.read()
    
    assert "modal-admit-patient" in admin_content or "Admit Patient" in admin_content or "admit_patient" in admin_content.lower()
    print(" -> PASSED: Admin Patient Management admission interface remains fully intact.")

def test_doctor_summary_counts_and_filters():
    print("\n[TEST 3] Testing dynamic EWS Summary Cards & Ward Filter computations across all Doctors...")
    
    docs = execute_query(
        "SELECT user_id, username, full_name, email, role, department FROM users WHERE username IN ('dr_sharma', 'dr_patel', 'dr_gupta') ORDER BY user_id",
        fetch=True
    )
    
    expected_data = {
        'dr_sharma': {
            'total': 3,
            'critical': 2, # Rajesh (7), Vikram (5)
            'monitor': 0,
            'stable': 1,   # Anita (0)
            'icu': 3,
            'hdu': 0,
            'cardio': 1    # Anita (CABG / Post-Op CABG)
        },
        'dr_patel': {
            'total': 3,
            'critical': 1, # Priya (8)
            'monitor': 2,  # Sunita (3), Mohammed (4)
            'stable': 0,
            'icu': 3,
            'hdu': 0,
            'cardio': 0
        },
        'dr_gupta': {
            'total': 4,
            'critical': 0,
            'monitor': 0,
            'stable': 4,   # Amit (0), Lakshmi (0), Deepak (2), Fatima (0)
            'icu': 0,
            'hdu': 4,
            'cardio': 1    # Amit (Decompensated Heart Failure)
        }
    }

    for doc in docs:
        username = doc['username']
        exp = expected_data[username]
        token = AuthService.generate_access_token(doc)['access_token']
        
        req = urllib.request.Request(
            'http://127.0.0.1:5000/api/v1/patients?status=admitted',
            headers={'Authorization': f'Bearer {token}'}
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode())
            patients = res.get('data', [])
            
            print(f"\n--- Doctor: {doc['full_name']} (@{username}) ---")
            print(f"  Authorized Patients: {len(patients)} (Expected: {exp['total']})")
            assert len(patients) == exp['total'], f"Expected {exp['total']} patients, got {len(patients)}"
            
            # Simulate frontend calculation logic
            crit_count = sum(1 for p in patients if (p.get('condition') == 'Critical' or (p.get('ews_score') or 0) >= 5))
            mon_count = sum(1 for p in patients if (p.get('condition') in ('Moderate Risk', 'Observation') or (p.get('ews_score') in (3, 4))))
            stab_count = sum(1 for p in patients if (p.get('condition') == 'Stable' or ((p.get('ews_score') or 0) in (0, 1, 2))))
            
            icu_count = sum(1 for p in patients if (p.get('ward_type') == 'ICU' or 'ICU' in (p.get('ward_name') or '')))
            hdu_count = sum(1 for p in patients if (p.get('ward_type') == 'HDU' or 'HDU' in (p.get('ward_name') or '')))
            
            print(f"  EWS Critical: {crit_count} (Expected: {exp['critical']})")
            print(f"  EWS Monitor:  {mon_count} (Expected: {exp['monitor']})")
            print(f"  EWS Stable:   {stab_count} (Expected: {exp['stable']})")
            print(f"  Ward ICU:     {icu_count} (Expected: {exp['icu']})")
            print(f"  Ward HDU:     {hdu_count} (Expected: {exp['hdu']})")
            
            assert crit_count == exp['critical'], f"Critical mismatch: {crit_count} != {exp['critical']}"
            assert mon_count == exp['monitor'], f"Monitor mismatch: {mon_count} != {exp['monitor']}"
            assert stab_count == exp['stable'], f"Stable mismatch: {stab_count} != {exp['stable']}"
            assert icu_count == exp['icu'], f"ICU mismatch: {icu_count} != {exp['icu']}"
            assert hdu_count == exp['hdu'], f"HDU mismatch: {hdu_count} != {exp['hdu']}"
            
    print("\n -> PASSED: Dynamic calculations match doctor-scoped authorized datasets perfectly.")

def test_database_10_patients_intact():
    print("\n[TEST 4] Verifying database contains exactly the original 10 patients...")
    total_pts = execute_query("SELECT COUNT(*) as cnt FROM patients WHERE status='admitted'", fetch=True)[0]['cnt']
    print(f"  Total admitted hospital patients: {total_pts}")
    assert total_pts == 10, f"Expected exactly 10 patients, found {total_pts}"
    print(" -> PASSED: Exactly 10 canonical patients exist in database.")

if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING COMPLETE TEST SUITE FOR DOCTOR MY PATIENTS FIXES")
    print("=" * 70)
    test_no_admit_button_in_doctor_portal()
    test_admin_admit_intact()
    test_doctor_summary_counts_and_filters()
    test_database_10_patients_intact()
    print("\n" + "=" * 70)
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 70)
