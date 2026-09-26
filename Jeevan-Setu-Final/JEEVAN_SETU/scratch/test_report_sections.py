import sys
import os
import io
import json

# Add project root to sys.path
sys.path.insert(0, os.path.abspath('d:/Major_Project/JSA-1/JEEVAN_SETU'))

from app import create_app
from database.db import db
from modules.report_engine import generate_multi_patient_report_data, render_multi_patient_pdf
from routes.report_routes import sanitize_filename_part

app = create_app()

import zlib
import re

def extract_pdf_text(pdf_bytes):
    """Decompress Adobe ASCII85 + FlateDecode streams in ReportLab PDF to extract text."""
    import base64
    text_chunks = []
    idx = 0
    while True:
        s_pos = pdf_bytes.find(b'stream', idx)
        if s_pos == -1:
            break
        e_pos = pdf_bytes.find(b'endstream', s_pos)
        if e_pos == -1:
            break
        raw = pdf_bytes[s_pos + 6:e_pos].strip()
        try:
            a85_dec = base64.a85decode(raw, adobe=True)
            decomp = zlib.decompress(a85_dec)
            text_chunks.append(decomp.decode('latin1', errors='ignore'))
        except Exception:
            try:
                decomp = zlib.decompress(raw)
                text_chunks.append(decomp.decode('latin1', errors='ignore'))
            except Exception:
                text_chunks.append(raw.decode('latin1', errors='ignore'))
        idx = e_pos + 9
    return "\n".join(text_chunks)

def run_tests():
    with app.app_context():
        print("=== 1. Filename Sanitization Tests ===")
        assert sanitize_filename_part("Ravi Kumar") == "Ravi_Kumar", f"Failed: {sanitize_filename_part('Ravi Kumar')}"
        assert sanitize_filename_part("Rajesh Kumar") == "Rajesh_Kumar"
        assert sanitize_filename_part("Ravi Kumar / Test") == "Ravi_Kumar_Test"
        assert sanitize_filename_part("Anita Devi (Special)") == "Anita_Devi_Special"
        print("[PASS] Filename sanitization passed!")

        client = app.test_client()

        from services.auth_service import AuthService
        user_dict = {'user_id': 1, 'username': 'admin_js', 'role': 'admin', 'email': 'admin@jeevansetu.org', 'department': 'Administration'}
        token_info = AuthService.generate_access_token(user_dict)
        token = token_info['access_token']
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

        print("\n=== 2. Testing Test Cases 1-6 ===")

        # Test 1: Vitals only
        res1 = client.post('/api/v1/reports/patients/pdf', json={'patient_ids': [1], 'sections': ['vitals']}, headers=headers)
        assert res1.status_code == 200, f"Test 1 failed: {res1.status_code}"
        cd1 = res1.headers.get('Content-Disposition')
        print("Test 1 Content-Disposition:", cd1)
        assert 'JeevanSetu_Rajesh_Kumar.pdf' in cd1
        
        text1 = extract_pdf_text(res1.data)
        assert "Vital Signs Monitoring Records" in text1
        assert "Early Warning Score" not in text1
        assert "Clinical Decision Support" not in text1
        assert "Ward & Bed Transfer History" not in text1
        assert "Patient Clinical Timeline" not in text1
        print("[PASS] Test 1 Passed: PDF contains only Vitals!")

        # Test 2: EWS only
        res2 = client.post('/api/v1/reports/patients/pdf', json={'patient_ids': [1], 'sections': ['ews']}, headers=headers)
        assert res2.status_code == 200
        text2 = extract_pdf_text(res2.data)
        assert "Early Warning Score" in text2
        assert "Vital Signs Monitoring Records" not in text2
        assert "Clinical Decision Support" not in text2
        assert "Ward & Bed Transfer History" not in text2
        assert "Patient Clinical Timeline" not in text2
        print("[PASS] Test 2 Passed: PDF contains only EWS!")

        # Test 3: CDS only
        res3 = client.post('/api/v1/reports/patients/pdf', json={'patient_ids': [1], 'sections': ['cds']}, headers=headers)
        assert res3.status_code == 200
        text3 = extract_pdf_text(res3.data)
        assert "Clinical Decision Support" in text3
        assert "Vital Signs Monitoring Records" not in text3
        assert "Early Warning Score" not in text3
        assert "Ward & Bed Transfer History" not in text3
        assert "Patient Clinical Timeline" not in text3
        print("[PASS] Test 3 Passed: PDF contains only CDS!")

        # Test 4: Vitals + EWS + CDS
        res4 = client.post('/api/v1/reports/patients/pdf', json={'patient_ids': [1], 'sections': ['vitals', 'ews', 'cds']}, headers=headers)
        assert res4.status_code == 200
        text4 = extract_pdf_text(res4.data)
        assert "Vital Signs Monitoring Records" in text4
        assert "Early Warning Score" in text4
        assert "Clinical Decision Support" in text4
        assert "Ward & Bed Transfer History" not in text4
        assert "Patient Clinical Timeline" not in text4
        print("[PASS] Test 4 Passed: PDF contains Vitals + EWS + CDS!")

        # Test 5: All 5 sections
        res5 = client.post('/api/v1/reports/patients/pdf', json={'patient_ids': [1], 'sections': ['vitals', 'ews', 'cds', 'transfers', 'timeline']}, headers=headers)
        assert res5.status_code == 200
        text5 = extract_pdf_text(res5.data)
        assert "Vital Signs Monitoring Records" in text5
        assert "Early Warning Score" in text5
        assert "Clinical Decision Support" in text5
        assert "Ward & Bed Transfer History" in text5
        assert "Patient Clinical Timeline" in text5
        print("[PASS] Test 5 Passed: PDF contains all 5 sections!")

        # Test 6: Empty sections -> 400 error
        res6 = client.post('/api/v1/reports/patients/pdf', json={'patient_ids': [1], 'sections': []}, headers=headers)
        assert res6.status_code == 400
        assert "Please select at least one report section." in res6.get_json()['error']
        print("[PASS] Test 6 Passed: Empty section selection returns 400 with clear validation error message!")

        # Test 7: Multiple Patients Filename Test
        res7 = client.post('/api/v1/reports/patients/pdf', json={'patient_ids': [1, 2], 'sections': ['vitals', 'ews']}, headers=headers)
        assert res7.status_code == 200
        cd7 = res7.headers.get('Content-Disposition')
        print("Multiple patients Content-Disposition:", cd7)
        assert 'JeevanSetu_Patient_Reports.pdf' in cd7
        print("[PASS] Multiple patients filename passed!")

        # Test 8: Preview JSON endpoint with section selection
        prev_res = client.post('/api/v1/reports/generate/patient-report', json={'patient_ids': [1], 'sections': ['vitals']}, headers=headers)
        assert prev_res.status_code == 200
        prev_data = prev_res.get_json()['data']
        assert 'sections' in prev_data
        assert prev_data['sections'] == ['vitals']
        print("[PASS] Preview API endpoint passed!")

        print("\nALL AUTOMATED TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run_tests()
