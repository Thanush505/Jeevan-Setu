"""
telemetry_simulator/simulator.py — Main entry point for the Jeevan Setu Telemetry Simulator.

┌──────────────────────────────────────────────────────────────┐
│  SIMULATED ICU TELEMETRY – DEVELOPMENT / TESTING ONLY       │
│  This is NOT a real medical device.                         │
│  Do NOT use for real clinical care.                         │
└──────────────────────────────────────────────────────────────┘

Architecture:
    SIMULATOR  →  raw vitals  →  Flask backend  →  EWS  →  Decision  →  Alerts  →  Portals

The simulator ONLY generates raw vital sign data (HR, RR, SBP, Temperature).
All EWS scoring, clinical decisions, and alert generation are performed
exclusively by the existing Jeevan Setu backend.
"""

import sys
import time
import signal
import argparse
from datetime import datetime, timezone

from config import SimulatorConfig
from logger import setup_logger, get_logger
from client import BackendClient
from scenarios import ScenarioEngine
from models import VitalReading, SimulatorStatus


# ─────────────────── Global state ───────────────────
_shutdown_requested = False


def _signal_handler(signum, frame):
    """Handle CTRL+C for graceful shutdown."""
    global _shutdown_requested
    _shutdown_requested = True
    print()  # Newline after ^C


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ─────────────────── Banner ───────────────────

BANNER = r"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║       JEEVAN SETU — ICU TELEMETRY SIMULATOR                 ║
║       Simulated ICU Multi-Parameter Bedside Monitor          ║
║                                                              ║
║       ⚠  DEVELOPMENT / TESTING ONLY                         ║
║       ⚠  NOT a real medical device                          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""


# ─────────────────── CLI Interactive Mode ───────────────────

def select_patient(client: BackendClient) -> dict:
    """Interactively select a patient from the backend."""
    patients = client.fetch_patients()
    if not patients:
        print("\n  ❌ No admitted patients found. Is the Flask backend running?")
        sys.exit(1)

    print("\n  Available Patients:")
    print("  " + "─" * 50)
    for i, p in enumerate(patients, 1):
        pid = p.get('patient_id', '?')
        name = p.get('name', 'Unknown')
        ward = p.get('ward_type', '?')
        bed = p.get('bed_number', '?')
        code = p.get('patient_code', '')
        print(f"    {i}. {name} (ID: {pid}, {ward}, Bed: {bed}) {code}")
    print()

    while True:
        try:
            choice = input("  Select patient [1-{}]: ".format(len(patients))).strip()
            if not choice:
                continue
            idx = int(choice) - 1
            if 0 <= idx < len(patients):
                return patients[idx]
            print("  Invalid selection. Try again.")
        except (ValueError, EOFError):
            print("  Invalid input. Enter a number.")


def select_scenario() -> tuple:
    """Interactively select a simulation scenario. Returns (scenario_name, manual_values or None)."""
    print("\n  Simulation Scenarios:")
    print("  " + "─" * 50)
    scenarios = [
        ('STABLE', 'Normal resting vitals with small drift'),
        ('GRADUAL_DETERIORATION', 'Gradual migration toward abnormal'),
        ('CRITICAL', 'Rapid deterioration to critical values'),
        ('RECOVERY', 'Return from abnormal toward stable'),
        ('MANUAL', 'Enter exact values manually'),
    ]
    for i, (name, desc) in enumerate(scenarios, 1):
        print(f"    {i}. {name:<25} — {desc}")
    print()

    while True:
        try:
            choice = input("  Select scenario [1-5]: ").strip()
            if not choice:
                continue
            idx = int(choice) - 1
            if 0 <= idx < len(scenarios):
                scenario_name = scenarios[idx][0]
                manual_values = None

                if scenario_name == 'MANUAL':
                    print("\n  Enter vital values:")
                    manual_values = {}
                    for field, label, default in [
                        ('heart_rate', 'Heart Rate (bpm)', '75'),
                        ('respiratory_rate', 'Respiratory Rate (breaths/min)', '16'),
                        ('systolic_bp', 'Systolic BP (mmHg)', '120'),
                        ('temperature', 'Temperature (°C)', '36.8'),
                    ]:
                        val = input(f"    {label} [{default}]: ").strip()
                        manual_values[field] = float(val) if val else float(default)

                return scenario_name, manual_values
            print("  Invalid selection. Try again.")
        except (ValueError, EOFError):
            print("  Invalid input. Enter a number.")


def select_interval() -> int:
    """Interactively select the telemetry interval."""
    print("\n  Telemetry Interval:")
    print("  " + "─" * 50)
    intervals = [1, 2, 5, 10]
    for i, sec in enumerate(intervals, 1):
        print(f"    {i}. {sec} second{'s' if sec > 1 else ''}")
    print()

    while True:
        try:
            choice = input("  Select interval [1-4] (default: 3): ").strip()
            if not choice:
                return 5  # Default
            idx = int(choice) - 1
            if 0 <= idx < len(intervals):
                return intervals[idx]
            print("  Invalid selection. Try again.")
        except (ValueError, EOFError):
            print("  Invalid input. Enter a number.")


# ─────────────────── Simulation Loop ───────────────────

def run_simulation(
    client: BackendClient,
    patient: dict,
    scenario_name: str,
    interval: int,
    device_id: str,
    manual_values: dict = None,
):
    """
    Main telemetry loop. Generates raw vitals and POSTs them to the backend.

    The backend handles: validation → EWS → decision → alerts → persistence.
    """
    global _shutdown_requested
    logger = get_logger()

    patient_id = patient['patient_id']
    patient_name = patient.get('name', 'Unknown')

    engine = ScenarioEngine(scenario_name, manual_values=manual_values)
    status = SimulatorStatus(
        running=True,
        patient_id=patient_id,
        patient_name=patient_name,
        scenario=scenario_name,
        device_id=device_id,
        interval_seconds=interval,
        started_at=datetime.now(timezone.utc),
    )

    logger.info("=" * 60)
    logger.info("SIMULATION STARTED — SIMULATED ICU TELEMETRY")
    logger.info("Patient: %s (ID: %d)", patient_name, patient_id)
    logger.info("Scenario: %s", scenario_name)
    logger.info("Device: %s", device_id)
    logger.info("Interval: %d second(s)", interval)
    logger.info("Backend: %s", SimulatorConfig.API_BASE_URL)
    logger.info("Press CTRL+C to stop.")
    logger.info("=" * 60)

    try:
        while not _shutdown_requested:
            # Generate next raw vital values
            vitals = engine.next()

            # Create reading model
            reading = VitalReading(
                heart_rate=vitals['heart_rate'],
                respiratory_rate=vitals['respiratory_rate'],
                systolic_bp=vitals['systolic_bp'],
                temperature=vitals['temperature'],
                patient_id=patient_id,
                device_id=device_id,
            )

            # Log what we're sending
            logger.info(
                "[Tick %d] Sending: %s",
                engine.tick,
                reading.display_str(),
            )

            # Submit to backend
            success, resp = client.submit_vitals(reading)

            if success:
                status.record_success()
                # Extract EWS info from backend response (for observability only)
                resp_data = resp.get('data', {})
                total_score = resp_data.get('total_score', '?')
                condition = resp_data.get('condition', '?')
                vital_id = resp_data.get('vital_id', '?')
                logger.info(
                    "  ✓ Accepted — vital_id=%s | Backend EWS=%s, Condition=%s",
                    vital_id, total_score, condition,
                )
            else:
                error_msg = resp.get('error', str(resp)[:100])
                status.record_failure(error_msg)
                logger.error("  ✗ Rejected — %s", error_msg)

            # Wait for next cycle (interruptible)
            for _ in range(interval * 10):
                if _shutdown_requested:
                    break
                time.sleep(0.1)

    except KeyboardInterrupt:
        pass
    finally:
        status.running = False
        logger.info("=" * 60)
        logger.info("SIMULATION STOPPED")
        logger.info("Total sent: %d | Successful: %d | Failed: %d",
                     status.readings_sent, status.successful, status.failed)
        logger.info("=" * 60)

    return status


# ─────────────────── CLI Argument Parsing ───────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description='Jeevan Setu — ICU Telemetry Simulator (Development/Testing Only)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python simulator.py                                    # Interactive mode
  python simulator.py --patient-id 1 --scenario STABLE   # Direct mode
  python simulator.py --patient-id 3 --scenario CRITICAL --interval 2
        """,
    )
    parser.add_argument('--patient-id', type=int, help='Patient ID to simulate')
    parser.add_argument(
        '--scenario',
        choices=['STABLE', 'GRADUAL_DETERIORATION', 'CRITICAL', 'RECOVERY', 'MANUAL'],
        help='Simulation scenario',
    )
    parser.add_argument('--interval', type=int, help='Telemetry interval in seconds')
    parser.add_argument('--hr', type=float, help='Manual heart rate (MANUAL scenario)')
    parser.add_argument('--rr', type=float, help='Manual respiratory rate (MANUAL scenario)')
    parser.add_argument('--sbp', type=float, help='Manual systolic BP (MANUAL scenario)')
    parser.add_argument('--temp', type=float, help='Manual temperature (MANUAL scenario)')
    parser.add_argument('--device-id', type=str, help='Override device ID')
    return parser.parse_args()


# ─────────────────── Main ───────────────────

def main():
    global _shutdown_requested
    setup_logger('INFO')
    logger = get_logger()

    print(BANNER)

    args = parse_args()
    client = BackendClient()

    # Step 1: Authenticate
    if not client.authenticate():
        logger.error("Authentication failed. Check credentials or backend availability.")
        sys.exit(1)

    # Step 2: Select patient
    if args.patient_id:
        # Direct mode — verify patient exists
        patients = client.fetch_patients()
        patient = None
        for p in patients:
            if p.get('patient_id') == args.patient_id:
                patient = p
                break
        if not patient:
            logger.error("Patient ID %d not found among admitted patients.", args.patient_id)
            sys.exit(1)
    else:
        patient = select_patient(client)

    # Step 3: Select scenario
    manual_values = None
    if args.scenario:
        scenario_name = args.scenario
        if scenario_name == 'MANUAL':
            manual_values = {
                'heart_rate': args.hr or 75,
                'respiratory_rate': args.rr or 16,
                'systolic_bp': args.sbp or 120,
                'temperature': args.temp or 36.8,
            }
    else:
        scenario_name, manual_values = select_scenario()

    # Step 4: Select interval
    interval = args.interval or select_interval() if not args.interval else args.interval
    interval = max(1, interval)  # Enforce minimum

    # Step 5: Device ID
    device_id = args.device_id or f"{SimulatorConfig.DEVICE_ID_PREFIX}-{patient['patient_id']:03d}"

    # Step 6: Confirmation
    print(f"\n  {'─' * 55}")
    print(f"  Patient:   {patient.get('name')} (ID: {patient['patient_id']})")
    print(f"  Scenario:  {scenario_name}")
    print(f"  Interval:  {interval} second(s)")
    print(f"  Device:    {device_id}")
    print(f"  Backend:   {SimulatorConfig.API_BASE_URL}")
    print(f"  {'─' * 55}")

    if not args.patient_id:  # Only ask in interactive mode
        confirm = input("\n  Start simulation? [Y/n]: ").strip().lower()
        if confirm and confirm != 'y':
            print("  Simulation cancelled.")
            client.close()
            sys.exit(0)

    # Step 7: Run
    try:
        status = run_simulation(
            client=client,
            patient=patient,
            scenario_name=scenario_name,
            interval=interval,
            device_id=device_id,
            manual_values=manual_values,
        )
    finally:
        client.close()

    sys.exit(0 if status.failed == 0 else 1)


if __name__ == '__main__':
    main()
