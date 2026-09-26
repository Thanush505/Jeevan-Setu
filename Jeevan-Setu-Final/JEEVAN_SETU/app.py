"""
app.py — Main Flask application entry point for Jeevan Setu.
"""

import os
import logging
from flask import Flask, redirect, url_for, request, make_response
from flask_login import LoginManager

from config import get_config

# Import route blueprints
from routes.auth_routes import auth_bp
from routes.auth_api_routes import auth_api_bp
from routes.user_routes import user_mgmt_bp
from routes.patient_routes import patient_bp
from routes.vitals_routes import vitals_bp
from routes.decision_routes import decision_bp
from routes.alert_routes import alert_bp
from routes.explanation_routes import explanation_bp
from routes.chatbot_routes import chatbot_bp
from routes.ward_routes import ward_bp
from routes.bed_routes import bed_bp
from routes.transfer_routes import transfer_bp
from routes.report_routes import report_bp
from routes.attendant_routes import attendant_bp
from routes.notification_routes import notification_bp
from routes.analytics_routes import analytics_bp



def create_app():
    """Application factory — creates and configures the Flask app."""
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Jeevan_setu_frontend'))
    app = Flask(
        __name__,
        template_folder=frontend_dir,
        static_folder=frontend_dir,
        static_url_path='/static_frontend'
    )

    # Load configuration
    config = get_config()
    app.config.from_object(config)

    # Setup logging
    setup_logging(app)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        from models.user_model import User
        return User.get_by_id(user_id)

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(auth_api_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(user_mgmt_bp, url_prefix='/api/v1/users')
    app.register_blueprint(user_mgmt_bp, url_prefix='/users', name='user_mgmt_alias')
    app.register_blueprint(patient_bp, url_prefix='/api/v1/patients', name='patient_api_alias')
    app.register_blueprint(patient_bp, url_prefix='/patients')
    app.register_blueprint(ward_bp, url_prefix='/api/v1/wards', name='ward_api_alias')
    app.register_blueprint(ward_bp, url_prefix='/wards')
    app.register_blueprint(bed_bp, url_prefix='/api/v1/beds', name='bed_api_alias')
    app.register_blueprint(bed_bp, url_prefix='/beds')
    app.register_blueprint(transfer_bp, url_prefix='/api/v1/transfers', name='transfer_api_alias')
    app.register_blueprint(transfer_bp, url_prefix='/transfers')
    app.register_blueprint(vitals_bp, url_prefix='/api/v1/vitals', name='vitals_api_alias')
    app.register_blueprint(vitals_bp, url_prefix='/vitals')
    app.register_blueprint(decision_bp, url_prefix='/api/v1/decision', name='decision_api_alias')
    app.register_blueprint(decision_bp, url_prefix='/decision')
    app.register_blueprint(alert_bp, url_prefix='/alerts')
    app.register_blueprint(alert_bp, url_prefix='/alert', name='alert_singular_alias')
    app.register_blueprint(alert_bp, url_prefix='/api/v1/alerts', name='alert_api_alias')
    app.register_blueprint(alert_bp, url_prefix='/api/v1/alert', name='alert_api_singular_alias')
    app.register_blueprint(explanation_bp, url_prefix='/api/v1/explanation', name='explanation_api_alias')
    app.register_blueprint(explanation_bp, url_prefix='/explanation')
    app.register_blueprint(chatbot_bp, url_prefix='/api/v1/chatbot', name='chatbot_api_alias')
    app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
    app.register_blueprint(report_bp, url_prefix='/api/v1/reports', name='report_api_alias')
    app.register_blueprint(report_bp, url_prefix='/reports')
    app.register_blueprint(attendant_bp, url_prefix='/api/v1/attendant', name='attendant_api_alias')
    app.register_blueprint(attendant_bp, url_prefix='/attendant')
    app.register_blueprint(notification_bp, url_prefix='/api/v1/notifications', name='notification_api_alias')
    app.register_blueprint(notification_bp, url_prefix='/notifications')
    app.register_blueprint(analytics_bp, url_prefix='/api/v1/analytics', name='analytics_api_alias')
    app.register_blueprint(analytics_bp, url_prefix='/analytics')

    # Security Middleware & HTTP Headers
    from utils.security import apply_security_headers
    app.after_request(apply_security_headers)

    # Global QR Scan Redirection Route
    @app.route('/qr/<path:token_or_code>', methods=['GET'])
    def root_qr_redirect(token_or_code):
        from routes.attendant_routes import handle_qr_redirect
        return handle_qr_redirect(token_or_code)

    @app.route('/qr', methods=['GET'])
    def root_qr_base():
        return redirect('/Attendant/attendant_access.html', code=302)

    # ─────────────────────────────────────────────────────────────
    # Frontend Role Direct Routes & Universal Page Viewers
    # ─────────────────────────────────────────────────────────────
    from flask import render_template, send_from_directory

    # Build comprehensive lookup dictionary for all frontend pages and assets
    page_lookup = {
        'login': 'Login/Login.html',
        'login.html': 'Login/Login.html',
        'Login/Login.html': 'Login/Login.html',
    }
    asset_dirs = {
        'login': os.path.join(frontend_dir, 'Login')
    }

    for root, dirs, files in os.walk(frontend_dir):
        if '.git' in root:
            continue
        rel_dir = os.path.relpath(root, frontend_dir).replace('\\', '/')
        folder_name = os.path.basename(root)
        for f in files:
            if f.endswith('.html'):
                rel_file = f"{rel_dir}/{f}"
                page_lookup[folder_name] = rel_file
                page_lookup[folder_name.lower()] = rel_file
                page_lookup[rel_dir] = rel_file
                page_lookup[rel_dir.lower()] = rel_file
                page_lookup[rel_file] = rel_file
                page_lookup[rel_file.lower()] = rel_file
                page_lookup[f] = rel_file
                page_lookup[f.lower()] = rel_file
                # Also support folder_name/code.html as alias
                page_lookup[f"{rel_dir}/code.html"] = rel_file
                page_lookup[f"{folder_name}/code.html"] = rel_file

        asset_dirs[folder_name] = root
        asset_dirs[folder_name.lower()] = root
        asset_dirs[rel_dir] = root
        asset_dirs[rel_dir.lower()] = root

    def resolve_frontend_template(path_str):
        """Resolve any given path string to a valid Jeevan_setu_frontend template."""
        if not path_str:
            return None
        clean = path_str.strip('/').replace('\\', '/')

        # 1. Exact match in page_lookup
        if clean in page_lookup:
            return page_lookup[clean]
        if clean.lower() in page_lookup:
            return page_lookup[clean.lower()]

        # 2. Check stripping code.html
        if clean.endswith('/code.html'):
            alt = clean[:-10].strip('/')
            if alt in page_lookup:
                return page_lookup[alt]
            if alt.lower() in page_lookup:
                return page_lookup[alt.lower()]

        # 3. Last segment match (e.g. Doctor_all_patients.html or Doctor_all_patients)
        last_seg = clean.split('/')[-1]
        if last_seg in page_lookup:
            return page_lookup[last_seg]
        if last_seg.lower() in page_lookup:
            return page_lookup[last_seg.lower()]

        # 4. Direct template file check
        if os.path.exists(os.path.join(frontend_dir, clean)):
            return clean
        if os.path.exists(os.path.join(frontend_dir, f"{clean}.html")):
            return f"{clean}.html"

        return None

    @app.route('/')
    @app.route('/login')
    def index():
        return redirect(url_for('auth.login'))

    @app.route('/Login/Login.html')
    @app.route('/Login/code.html')
    @app.route('/code.html')
    def login_direct():
        return render_template('Login/Login.html')

    @app.route('/admin')
    def admin_home():
        return render_template('Admin/Administrator_dashboard_/Administrator_dashboard_.html')

    @app.route('/doctor')
    def doctor_home():
        return render_template('Doctor/Doctor_dashboard_/Doctor_dashboard_.html')

    @app.route('/nurse')
    def nurse_home():
        return render_template('Nurse/Nurse_dashboard/Nurse_dashboard.html')

    @app.route('/attendant-portal')
    def attendant_home():
        return render_template('Attendant/attendant_login_mobile_revised/attendant_login_mobile_revised.html')

    @app.route('/Nurse/Nurse_tasks/Nurse_tasks.html')
    @app.route('/Nurse_tasks/Nurse_tasks.html')
    @app.route('/Nurse_tasks')
    def redirect_nurse_tasks():
        return redirect('/Nurse/Nurse_alerts/Nurse_alerts.html?tab=tasks')

    @app.route('/Nurse/Nurse_transfers/Nurse_transfers.html')
    @app.route('/Nurse_transfers/Nurse_transfers.html')
    @app.route('/Nurse_transfers')
    def redirect_nurse_transfers():
        return redirect('/Nurse/Nurse_dashboard/Nurse_dashboard.html')

    @app.route('/Nurse/Nurse_reports/Nurse_reports.html')
    @app.route('/Nurse_reports/Nurse_reports.html')
    @app.route('/Nurse_reports')
    def redirect_nurse_reports():
        return redirect('/Nurse/Nurse_dashboard/Nurse_dashboard.html')

    # Universal 1-level route (e.g., /Doctor_all_patients/Doctor_all_patients.html, /Administrator_dashboard_/code.html)
    @app.route('/<page_name>/<filename>.html')
    def serve_single_level_page(page_name, filename):
        tmpl = resolve_frontend_template(f"{page_name}/{filename}.html") or resolve_frontend_template(page_name)
        if tmpl:
            return render_template(tmpl)
        return {'success': False, 'error': f'Page {page_name}/{filename}.html not found'}, 404

    # Universal 2-level route (e.g., /Doctor/Doctor_all_patients/Doctor_all_patients.html, /Admin/Admin_beds_wards/Admin_beds_wards.html)
    @app.route('/<role_folder>/<page_folder>/<filename>.html')
    def serve_frontend_page(role_folder, page_folder, filename):
        tmpl = (
            resolve_frontend_template(f"{role_folder}/{page_folder}/{filename}.html") or
            resolve_frontend_template(f"{role_folder}/{page_folder}") or
            resolve_frontend_template(page_folder)
        )
        if tmpl:
            return render_template(tmpl)
        return {'success': False, 'error': f'Page {role_folder}/{page_folder}/{filename}.html not found'}, 404

    # Universal route for single-level assets (e.g. /Doctor_dashboard_/screen.png)
    @app.route('/<page_name>/<filename>')
    def serve_single_level_asset(page_name, filename):
        if filename.endswith('.html'):
            tmpl = resolve_frontend_template(f"{page_name}/{filename}") or resolve_frontend_template(page_name)
            if tmpl:
                return render_template(tmpl)
        target_dir = asset_dirs.get(page_name) or asset_dirs.get(page_name.lower())
        if target_dir and os.path.exists(os.path.join(target_dir, filename)):
            return send_from_directory(target_dir, filename)
        if os.path.exists(os.path.join(frontend_dir, filename)):
            return send_from_directory(frontend_dir, filename)
        return {'success': False, 'error': f'Asset {filename} not found'}, 404

    # Universal route for 2-level assets (e.g. /Doctor/Doctor_dashboard_/screen.png)
    @app.route('/<role_folder>/<page_folder>/<filename>')
    def serve_frontend_asset(role_folder, page_folder, filename):
        if filename.endswith('.html'):
            tmpl = resolve_frontend_template(f"{role_folder}/{page_folder}/{filename}") or resolve_frontend_template(page_folder)
            if tmpl:
                return render_template(tmpl)
        asset_dir = os.path.join(frontend_dir, role_folder, page_folder)
        if os.path.exists(os.path.join(asset_dir, filename)):
            return send_from_directory(asset_dir, filename)
        target_dir = asset_dirs.get(page_folder) or asset_dirs.get(page_folder.lower())
        if target_dir and os.path.exists(os.path.join(target_dir, filename)):
            return send_from_directory(target_dir, filename)
        return {'success': False, 'error': f'Asset {filename} not found'}, 404

    # Secure Error Handlers (Zero Stack Trace Leakage)
    @app.errorhandler(400)
    def bad_request(e):
        return {'success': False, 'error': getattr(e, 'description', 'Bad request')}, 400

    @app.errorhandler(401)
    def unauthorized(e):
        return {'success': False, 'error': 'Authentication required. Please provide a valid Bearer token.'}, 401

    @app.errorhandler(403)
    def forbidden(e):
        return {'success': False, 'error': 'Access forbidden: Insufficient role permissions.'}, 403

    @app.errorhandler(404)
    def not_found(e):
        return {'success': False, 'error': 'Resource not found'}, 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return {'success': False, 'error': 'Method not allowed'}, 405

    @app.errorhandler(429)
    def ratelimit_exceeded(e):
        return {'success': False, 'error': 'Too many requests. Please try again later.'}, 429

    @app.errorhandler(500)
    def internal_error(e):
        import traceback
        app.logger.error(f'Internal server error: {e}\n{traceback.format_exc()}')
        return {'success': False, 'error': 'Internal server error'}, 500

    return app


def setup_logging(app):
    """Configure application logging."""
    log_dir = app.config.get('LOG_DIR', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # System log
    system_handler = logging.FileHandler(os.path.join(log_dir, 'system.log'), encoding='utf-8')
    system_handler.setLevel(logging.INFO)
    system_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))

    # Error log
    error_handler = logging.FileHandler(os.path.join(log_dir, 'error.log'), encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s\n%(pathname)s:%(lineno)d'
    ))

    app.logger.addHandler(system_handler)
    app.logger.addHandler(error_handler)
    app.logger.setLevel(getattr(logging, app.config.get('LOG_LEVEL', 'INFO')))


if __name__ == '__main__':
    app = create_app()
    app.logger.info('Jeevan Setu is starting...')
    app.run(host='0.0.0.0', port=5000, debug=True)
