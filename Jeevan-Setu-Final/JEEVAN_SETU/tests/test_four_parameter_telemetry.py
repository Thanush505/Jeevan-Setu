"""
tests/test_four_parameter_telemetry.py — Comprehensive verification of the 4-parameter Bedside Telemetry observations on Doctor and Nurse pages.
"""

import os
import sys
import unittest
import urllib.request
import re

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
JEEVAN_SETU_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if JEEVAN_SETU_ROOT not in sys.path:
    sys.path.insert(0, JEEVAN_SETU_ROOT)

from models.user_model import User
from services.auth_service import AuthService
from app import create_app


class TestFourParameterTelemetry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        cls.frontend_root = os.path.abspath(os.path.join(JEEVAN_SETU_ROOT, '..', 'Jeevan_setu_frontend'))
        
        # Authenticated doctor and nurse tokens
        cls.doc_user = User.get_by_id(1)  # Dr. Sunil Mehta
        cls.nurse_user = User.get_by_id(5)  # Nurse Priya
        cls.doc_token = AuthService.generate_access_token(cls.doc_user)['access_token']
        cls.nurse_token = AuthService.generate_access_token(cls.nurse_user)['access_token']

    def _get_page_html(self, relative_path):
        file_path = os.path.join(self.frontend_root, relative_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_01_doctor_page_has_exactly_four_telemetry_cards(self):
        """Doctor page bedside telemetry section contains exactly 4 cards."""
        html = self._get_page_html(os.path.join("Doctor", "Doctor_patient_summary_ai", "Doctor_patient_summary_ai.html"))
        norm_html = re.sub(r'\s+', ' ', html)
        start = norm_html.find('Bedside Telemetry Observations')
        end = norm_html.find('Early Warning Score', start)
        section = norm_html[start:end]

        # Verify exactly 4 vital-tile instances
        card_count = section.count('class="vital-tile"')
        self.assertEqual(card_count, 4, f"Expected exactly 4 telemetry cards in Doctor page, found {card_count}")

    def test_02_nurse_page_has_exactly_four_telemetry_cards(self):
        """Nurse page bedside telemetry section contains exactly 4 cards."""
        html = self._get_page_html(os.path.join("Nurse", "Nurse_patient_summary_ai", "Nurse_patient_summary_ai.html"))
        norm_html = re.sub(r'\s+', ' ', html)
        start = norm_html.find('Bedside Telemetry Observations')
        end = norm_html.find('Early Warning Score', start)
        section = norm_html[start:end]

        card_count = section.count('class="vital-tile"')
        self.assertEqual(card_count, 4, f"Expected exactly 4 telemetry cards in Nurse page, found {card_count}")

    def test_03_four_retained_parameters_exist_with_proper_elements(self):
        """Verify Heart Rate, Respiratory Rate, Blood Pressure, and Temperature exist with units and tags."""
        pages = [
            os.path.join("Doctor", "Doctor_patient_summary_ai", "Doctor_patient_summary_ai.html"),
            os.path.join("Nurse", "Nurse_patient_summary_ai", "Nurse_patient_summary_ai.html")
        ]
        required_elements = [
            # Heart Rate
            ('vital-hr-val', 'vital-hr-tag', 'bpm', 'Target: 60–100 bpm'),
            # Respiratory Rate
            ('vital-rr-val', 'vital-rr-tag', '/min', 'Target: 12–20/min'),
            # Blood Pressure
            ('vital-bp-val', 'vital-bp-tag', 'mmHg', 'Sys: 100–130 mmHg'),
            # Temperature
            ('vital-temp-val', 'vital-temp-tag', '°C', 'Norm: 36.5–37.5°C'),
        ]
        for rel_path in pages:
            html = self._get_page_html(rel_path)
            for val_id, tag_id, unit, target in required_elements:
                self.assertIn(f'id="{val_id}"', html, f"Missing value element {val_id} in {rel_path}")
                self.assertIn(f'id="{tag_id}"', html, f"Missing tag element {tag_id} in {rel_path}")
                self.assertIn(unit, html, f"Missing unit {unit} in {rel_path}")
                self.assertIn(target, html, f"Missing target range {target} in {rel_path}")

    def test_04_spo2_and_avpu_completely_removed_from_telemetry_section(self):
        """Verify SpO2 and AVPU cards are removed from Bedside Telemetry section on both pages."""
        pages = [
            os.path.join("Doctor", "Doctor_patient_summary_ai", "Doctor_patient_summary_ai.html"),
            os.path.join("Nurse", "Nurse_patient_summary_ai", "Nurse_patient_summary_ai.html")
        ]
        for rel_path in pages:
            html = self._get_page_html(rel_path)
            norm_html = re.sub(r'\s+', ' ', html)
            start = norm_html.find('Bedside Telemetry Observations')
            end = norm_html.find('Early Warning Score', start)
            section = norm_html[start:end]

            # SpO2 must not appear
            self.assertNotIn('vital-spo2-val', section, f"vital-spo2-val found in {rel_path}")
            self.assertNotIn('vital-spo2-tag', section, f"vital-spo2-tag found in {rel_path}")
            self.assertNotIn('SpO2', section, f"SpO2 label found in {rel_path}")
            self.assertNotIn('spo2', section.lower(), f"spo2 text found in {rel_path}")

            # AVPU must not appear
            self.assertNotIn('vital-avpu-val', section, f"vital-avpu-val found in {rel_path}")
            self.assertNotIn('AVPU', section, f"AVPU label found in {rel_path}")
            self.assertNotIn('avpu', section.lower(), f"avpu text found in {rel_path}")

    def test_05_responsive_four_column_grid_layout(self):
        """Verify the grid layout is configured for 1 col mobile, 2 col tablet, and 4 col desktop."""
        pages = [
            os.path.join("Doctor", "Doctor_patient_summary_ai", "Doctor_patient_summary_ai.html"),
            os.path.join("Nurse", "Nurse_patient_summary_ai", "Nurse_patient_summary_ai.html")
        ]
        for rel_path in pages:
            html = self._get_page_html(rel_path)
            norm_html = re.sub(r'\s+', ' ', html)
            start = norm_html.find('Bedside Telemetry Observations')
            end = norm_html.find('Early Warning Score', start)
            section = norm_html[start:end]

            self.assertIn('grid-cols-1', section, f"Missing grid-cols-1 mobile layout in {rel_path}")
            self.assertIn('sm:grid-cols-2', section, f"Missing sm:grid-cols-2 tablet layout in {rel_path}")
            self.assertIn('lg:grid-cols-4', section, f"Missing lg:grid-cols-4 desktop layout in {rel_path}")

    def test_06_sync_button_and_timestamp_preserved(self):
        """Verify Sync button and recorded timestamp exist in both pages."""
        pages = [
            os.path.join("Doctor", "Doctor_patient_summary_ai", "Doctor_patient_summary_ai.html"),
            os.path.join("Nurse", "Nurse_patient_summary_ai", "Nurse_patient_summary_ai.html")
        ]
        for rel_path in pages:
            html = self._get_page_html(rel_path)
            norm_html = re.sub(r'\s+', ' ', html)
            start = norm_html.find('Bedside Telemetry Observations')
            end = norm_html.find('Early Warning Score', start)
            section = norm_html[start:end]

            self.assertIn('id="vital-recorded-at"', section, f"Missing vital-recorded-at in {rel_path}")
            self.assertIn('syncLiveVitals()', section, f"Missing syncLiveVitals() in {rel_path}")
            self.assertIn('Sync', section, f"Missing Sync button in {rel_path}")

    def test_07_backend_api_still_returns_all_six_parameters(self):
        """Backend patient summary API preserves complete clinical data including SpO2 and consciousness."""
        headers = {'Authorization': f'Bearer {self.doc_token}'}
        res = self.client.get('/chatbot/patient/1/summary', headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        ctx = data['context']
        latest_vitals = ctx['latest_vitals']

        # Ensure backend still provides all clinical fields
        self.assertIn('heart_rate', latest_vitals)
        self.assertIn('respiratory_rate', latest_vitals)
        self.assertIn('blood_pressure_sys', latest_vitals)
        self.assertIn('blood_pressure_dia', latest_vitals)
        self.assertIn('temperature', latest_vitals)
        self.assertIn('spo2', latest_vitals, "Backend must still retain spo2 for clinical decisions")
        self.assertIn('consciousness', latest_vitals, "Backend must still retain consciousness for clinical decisions")

        # EWS calculation & recommendations must remain intact
        self.assertIn('ews', ctx)
        self.assertIn('recommendation', ctx)
        self.assertIsNotNone(ctx['ews']['score'])

    def test_08_nurse_api_access_preserves_ews_and_vitals(self):
        """Nurse access also retains full backend vitals and EWS calculations."""
        headers = {'Authorization': f'Bearer {self.nurse_token}'}
        res = self.client.get('/chatbot/patient/1/summary', headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['context']['patient']['patient_id'], 1)
        self.assertIn('spo2', data['context']['latest_vitals'])
        self.assertIn('consciousness', data['context']['latest_vitals'])


if __name__ == '__main__':
    unittest.main()
