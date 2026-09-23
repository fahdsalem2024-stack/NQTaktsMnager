# config.py
import os

class Config:
    # ===== الأمان =====
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your_secret_key_here_change_in_production')
    
    # ===== قاعدة بيانات =====
    DB_PATH = os.environ.get('DB_PATH', 'tasks.db')
    
    # ===== مجلدات =====
    UPLOAD_FOLDER = 'uploads/'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    # ===== إعدادات الإيميل =====
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', 'false').lower() == 'true'
    
    # ===== الشركة =====
    COMPANY_NAME = 'شركة التقنية المتقدمة'
    COMPANY_NAME_EN = 'Advanced Technology Company'
    COMPANY_PHONE = '+966 50 123 4567'
    COMPANY_ADDRESS = 'الرياض، المملكة العربية السعودية'
    COMPANY_LOGO = 'logo.png'
    
    # ===== مستخدم افتراضي =====
    DEFAULT_USERNAME = 'Fahd01'
    DEFAULT_PASSWORD = '1234'
    
    FLASK_ENV = os.environ.get('FLASK_ENV', 'production')