"""
tests/test_qr_mobile_redirection.py — End-to-End Verification for Jeevan Setu Mobile QR Redirection.
"""

import sys
import os
import unittest
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database.db import db
from models.user_model import User
from models.patient_model import Patient
from models.qr_token_model import PatientQRToken
from services.auth_service import AuthService
from config import get_config, get_lan_ip


class TestQRMobileRedirection(unittest.TestCase):
    """Test suite for Mobile QR Redirection, Dynamic LAN IP, and Attendant Dashboard routing."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        # Admin Auth
        admin_user = User.authenticate('admin', 'admin123')
        cls.admin_token = AuthService.generate_access_token(admin_user)['access_token']
        cls.admin_headers = {'Authorization': f"Bearer {cls.admin_token}"}

    def test_01_dynamic_lan_ip_detection(self):
        """Verify LAN IP is dynamically determined without hardcoding."""
        lan_ip = get_lan_ip()
        self.assertIsNotNone(lan_ip)
        self.assertNotEqual(lan_ip, '127.0.0.1')
        self.assertFalse(lan_ip.startswith('192.168.56.'))  # No VirtualBox adapter

        config = get_config()
        self.assertNotIn('jeevansetu.org', config.EXTERNAL_BASE_URL)
        self.assertNotIn('127.0.0.1', config.EXTERNAL_BASE_URL)
        self.assertNotIn('localhost', config.EXTERNAL_BASE_URL)
        print(f"[PASS] Dynamic LAN IP detected: {lan_ip} -> Base URL: {config.EXTERNAL_BASE_URL}")

    def test_02_qr_url_generation_uses_lan_host(self):
        """Verify generated QR token contains http://<LAN-IP>:5000/qr/<token>."""
        token_info = PatientQRToken.generate_token(patient_id=4, force=True)
        access_url = token_info['access_url']

        self.assertIn('/qr/JS-QR-P4-', access_url)
        self.assertNotIn('jeevansetu.org', access_url)
        self.assertNotIn('127.0.0.1', access_url)
        self.assertNotIn('localhost', access_url)
        self.assertTrue(token_info['qr_image_data_url'].startswith('data:image/png;base64,'))
        print(f"[PASS] Patient 4 QR URL: {access_url}")

    def test_03_qr_scan_redirect_to_attendant_dashboard(self):
        """Verify scanning /qr/<token> redirects (302) to patient_update_mobile_view_replica.html with patient_id=4."""
        token_info = PatientQRToken.get_active_by_patient(4)
        raw_token = token_info['raw_token'] if 'raw_token' in token_info else None
        if not raw_token:
            token_info = PatientQRToken.generate_token(patient_id=4, force=True)
            raw_token = token_info['raw_token']

        # Scan QR endpoint
        res = self.client.get(f"/qr/{raw_token}")
        self.assertEqual(res.status_code, 302)

        redirect_loc = res.headers.get('Location', '')
        self.assertIn('/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html', redirect_loc)
        self.assertIn('patient_id=4', redirect_loc)
        self.assertIn('session_token=', redirect_loc)

        # Check cookie
        cookies = res.headers.getlist('Set-Cookie')
        self.assertTrue(any('jeevan_setu_token=' in c for c in cookies))
        print(f"[PASS] QR scan redirect Location: {redirect_loc}")

    def test_04_dynamic_patient_mapping_multi_patient(self):
        """Verify different patient QR codes map dynamically to their respective patient_ids."""
        for pid in [1, 2, 3, 4, 5]:
            tok = PatientQRToken.generate_token(patient_id=pid, force=True)
            res = self.client.get(f"/qr/{tok['raw_token']}")
            self.assertEqual(res.status_code, 302)
            loc = res.headers.get('Location', '')
            self.assertIn(f"patient_id={pid}", loc)
            print(f"[PASS] Patient {pid} scanned -> Redirected to patient_id={pid}")

    def test_05_uhid_scan_redirection_fallback(self):
        """Verify scanning /qr/UHID-2026-00004 dynamically resolves to patient_id=4."""
        res = self.client.get("/qr/UHID-2026-00004")
        self.assertEqual(res.status_code, 302)
        loc = res.headers.get('Location', '')
        self.assertIn("patient_id=4", loc)
        self.assertIn("/Attendant/patient_update_mobile_view_replica/patient_update_mobile_view_replica.html", loc)
        print(f"[PASS] UHID-2026-00004 scanned -> Redirected to patient_id=4")

    def test_06_invalid_and_revoked_qr_handling(self):
        """Verify invalid or revoked tokens render user-friendly error screens with proper HTTP status codes."""
        # 1. Invalid token
        res_inv = self.client.get("/qr/JS-QR-INVALID-TOKEN-999")
        self.assertEqual(res_inv.status_code, 404)
        self.assertIn(b"Invalid QR Code", res_inv.data)

        # 2. Revoked token
        tok = PatientQRToken.generate_token(patient_id=2, force=True)
        PatientQRToken.revoke_token(patient_id=2)
        res_rev = self.client.get(f"/qr/{tok['raw_token']}")
        self.assertEqual(res_rev.status_code, 403)
        self.assertIn(b"Access QR Revoked", res_rev.data)
        print("[PASS] Invalid & revoked tokens safely rejected with 404/403 mobile error screens.")

    def test_07_tamper_proofing_patient_data_isolation(self):
        """Verify attendant session token isolates patient data and prevents accessing another patient via ?patient_id=999."""
        tok = PatientQRToken.generate_token(patient_id=4, force=True)
        res = self.client.get(f"/qr/{tok['raw_token']}")
        loc = res.headers.get('Location', '')
        
        parsed = urlparse(loc)
        params = parse_qs(parsed.query)
        session_token = params['session_token'][0]

        # Call attendant patient API with token and TAMPERED patient_id=1
        api_res = self.client.get('/api/v1/attendant/patient?patient_id=1',
                                  headers={'Authorization': f"Bearer {session_token}"})
        self.assertEqual(api_res.status_code, 200)
        data = api_res.get_json()
        self.assertTrue(data['success'])
        # The backend MUST return patient 4 because the token was generated for patient 4!
        self.assertEqual(data['data']['patient_id'], 4)
        self.assertNotEqual(data['data']['patient_id'], 1)
        print("[PASS] Tamper attempt blocked: Session strictly returned authorized Patient #4 data.")

    def test_08_admin_qr_management_table_has_lan_urls(self):
        """Verify Admin QR Management endpoint returns LAN URLs for all patients without production/localhost domains."""
        res = self.client.get('/api/v1/attendant/patients', headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(len(data['data']), 5)

        for p in data['data']:
            if p.get('qr_status') == 'active' and p.get('access_url'):
                url = p['access_url']
                self.assertNotIn('jeevansetu.org', url)
                self.assertNotIn('127.0.0.1', url)
                self.assertNotIn('localhost', url)
                self.assertIn('/qr/', url)
        print("[PASS] Admin QR Management list verified with dynamic LAN URLs.")


if __name__ == '__main__':
    unittest.main()
