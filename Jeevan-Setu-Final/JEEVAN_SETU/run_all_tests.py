"""
run_all_tests.py — Runs all phase test suites (Phase 2 to Phase 11).
"""

import os
import sys
import unittest

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    test_files = [
        'test_phase2_database.py',
        'test_phase3_auth.py',
        'test_phase4_rbac.py',
        'test_phase5_user_management.py',
        'test_phase6_patient_management.py',
        'test_phase7_ward_bed_management.py',
        'test_phase8_vitals_management.py',
        'test_phase10_decision_engine.py',
        'test_phase11_explainable_decision.py',
        'test_phase12_transfer_management.py',
        'test_phase13_qr_attendant.py',
        'test_phase14_notifications_alerts.py',
        'test_phase15_reports.py',
        'test_phase16_analytics.py',
        'test_phase17_chatbot.py',
        'test_phase19_security.py'
    ]

    total_passed = 0
    total_failed = 0
    total_errors = 0

    for test_file in test_files:
        print(f"\n========================================================")
        print(f"  RUNNING: {test_file}")
        print(f"========================================================")
        module_name = f"tests.{test_file[:-3]}"
        suite = unittest.defaultTestLoader.loadTestsFromName(module_name)
        result = unittest.TextTestRunner(verbosity=2).run(suite)

        if not result.wasSuccessful():
            print(f"FAILED: {test_file}")
            sys.exit(1)

    print("\n========================================================")
    print("  ALL TESTS PASSED SUCCESSFULLY (PHASES 2 - 19)!")
    print("========================================================")
    sys.exit(0)
