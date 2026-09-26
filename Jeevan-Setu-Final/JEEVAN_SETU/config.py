"""
config.py — Application configuration and database settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def get_lan_ip():
    """
    Dynamically determine the host machine's active local Wi-Fi / Ethernet IP address.
    Filters out loopback (127.0.0.1) and virtual network adapters (e.g. VirtualBox 192.168.56.x).
    """
    env_ip = os.getenv('LAN_IP')
    if env_ip and env_ip != '0.0.0.0' and not env_ip.startswith('127.') and not env_ip.startswith('192.168.56.'):
        return env_ip

    # 1. Quick UDP routing socket detection
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith('127.') and not ip.startswith('192.168.56.'):
            return ip
    except Exception:
        pass

    # 2. Hostname interface enumeration
    try:
        import socket
        hostname = socket.gethostname()
        _, _, ip_list = socket.gethostbyname_ex(hostname)
        for ip in ip_list:
            if ip.startswith('127.') or ip.startswith('192.168.56.'):
                continue
            if ip.startswith(('192.168.', '10.', '172.')):
                return ip
    except Exception:
        pass

    return '192.168.1.3'


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'jeevan-setu-secret-key-change-in-production')
    DEBUG = False
    TESTING = False

    # Dynamic Network & Server Binding (LAN access for mobile testing)
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    LAN_IP = get_lan_ip()
    EXTERNAL_BASE_URL = os.getenv('EXTERNAL_BASE_URL') or f"http://{get_lan_ip()}:{os.getenv('PORT', 5000)}"

    # Database
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'jeevan_setu')

    # JWT Authentication
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 86400))  # 24 hours
    JWT_ALGORITHM = 'HS256'
    PASSWORD_RESET_TIMEOUT = int(os.getenv('PASSWORD_RESET_TIMEOUT', 3600))  # 1 hour

    # Session
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

    # Logging
    LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
    LOG_LEVEL = 'INFO'

    # Alert thresholds
    CRITICAL_EWS_THRESHOLD = 7
    HIGH_EWS_THRESHOLD = 5
    MEDIUM_EWS_THRESHOLD = 3

    # Transfer Waiting Period (Prolonged Ready-to-Transfer Alert Threshold)
    TRANSFER_WAITING_PERIOD_MINUTES = int(os.getenv('TRANSFER_WAITING_PERIOD_MINUTES', 120))  # 2 hours default

    # Scheduler
    VITALS_CHECK_INTERVAL_SECONDS = 300  # 5 minutes
    ALERT_CHECK_INTERVAL_SECONDS = 60    # 1 minute

    # Hospital Information (Permanent Clinical Reports & Official Documentation)
    HOSPITAL_NAME = os.getenv('HOSPITAL_NAME', 'JEEVAN SETU MULTISPECIALTY HOSPITAL')
    HOSPITAL_TAGLINE = os.getenv('HOSPITAL_TAGLINE', 'Intelligent Clinical Decision & Critical Care Transfer System')
    HOSPITAL_ADDRESS = os.getenv('HOSPITAL_ADDRESS', 'Jeevan Setu Medical Enclave, Health City, Sector 12')
    HOSPITAL_LOCATION = os.getenv('HOSPITAL_LOCATION', 'New Delhi, Delhi - 110029, India')
    HOSPITAL_PHONE = os.getenv('HOSPITAL_PHONE', '+91 11 2658 8500 / +91 1800 123 4567')
    HOSPITAL_EMAIL = os.getenv('HOSPITAL_EMAIL', 'clinical.reports@jeevansetu.org')
    HOSPITAL_WEBSITE = os.getenv('HOSPITAL_WEBSITE', 'www.jeevansetu.org')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    LOG_LEVEL = 'WARNING'


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DB_NAME = 'jeevan_setu_test'
    LOG_LEVEL = 'DEBUG'


# Configuration mapping
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get configuration based on environment variable."""
    env = os.getenv('FLASK_ENV', 'development')
    return config_map.get(env, DevelopmentConfig)
