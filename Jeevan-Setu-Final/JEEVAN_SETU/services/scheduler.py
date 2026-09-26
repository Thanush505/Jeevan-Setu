"""
services/scheduler.py — Periodic task scheduler.

Runs scheduled jobs for automated vitals monitoring and alert checking.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from models.patient_model import Patient
from models.vitals_model import Vitals
from modules.alert_engine import check_vitals_and_alert
from modules.scoring_engine import get_risk_level

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def check_all_patients():
    """Periodic job: Check all admitted patients' latest vitals for alerts."""
    try:
        patients = Patient.get_all(status='admitted')
        for patient in patients:
            vitals = Vitals.get_latest(patient['patient_id'])
            if vitals:
                risk = get_risk_level(vitals.get('ews_score', 0))
                if risk in ('critical', 'high'):
                    alerts = check_vitals_and_alert(
                        patient['patient_id'], vitals, patient['name']
                    )
                    if alerts:
                        logger.warning(
                            f"Auto-alert for {patient['name']}: {len(alerts)} alert(s) generated"
                        )
        logger.info("Periodic patient check complete.")
    except Exception as e:
        logger.error(f"Scheduled patient check failed: {e}")


def start_scheduler(app):
    """Start the background scheduler with configured jobs."""
    interval = app.config.get('VITALS_CHECK_INTERVAL_SECONDS', 300)

    scheduler.add_job(
        func=check_all_patients,
        trigger='interval',
        seconds=interval,
        id='check_all_patients',
        replace_existing=True
    )

    scheduler.start()
    logger.info(f"Scheduler started. Patient check every {interval}s.")


def stop_scheduler():
    """Stop the background scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
