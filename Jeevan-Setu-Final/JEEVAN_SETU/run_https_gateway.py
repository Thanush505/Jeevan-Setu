"""
Jeevan Setu HTTPS Mobile Camera Gateway
Listens on port 5443 with SSL SAN certificate for mobile browsers (iOS Safari & Android Chrome)
to provide a Secure Context (window.isSecureContext === true) for navigator.mediaDevices.getUserMedia().
"""
import os
import sys

# Ensure JEEVAN_SETU is in Python path
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from app import create_app
from werkzeug.serving import run_simple

if __name__ == '__main__':
    cert_path = os.path.join(base_dir, 'cert.pem')
    key_path = os.path.join(base_dir, 'key.pem')

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        print(f"[HTTPS Gateway] Error: cert.pem or key.pem not found in {base_dir}")
        sys.exit(1)

    print("[HTTPS Gateway] Initializing Jeevan Setu Flask App for SSL Gateway...")
    app = create_app()
    print("[HTTPS Gateway] Binding HTTPS server to 0.0.0.0:5443...")
    run_simple('0.0.0.0', 5443, app, ssl_context=(cert_path, key_path), threaded=True)
