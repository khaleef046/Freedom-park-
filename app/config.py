import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

class BaseConfig:
    """Base configuration common to all environments."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-freedom-park-secret-key-2026")
    
    # Session & Cookie Security
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    
    # SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # WTForms / CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # Prevents unexpected form expiry during long booking sessions
    
    # Uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    
    # OTP Authentication
    OTP_MOCK_MODE = False
    OTP_MOCK_CODE = os.environ.get("OTP_MOCK_CODE", "123456")
    
    # Business Defaults (Fallback if not in DB settings)
    PARK_NAME = "FREEDOM PARK"
    PARK_LOCATION = "Pernambut, India"
    DEFAULT_CAPACITY = 100
    DEFAULT_OPERATING_HOURS = "8:00 AM – 8:00 PM"


def get_db_uri():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        # Render may provide the legacy postgres:// scheme.
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
        return database_url
    db_file = os.path.join(BASE_DIR, "freedom_park.db")
    return f"sqlite:///{db_file}"


class DevelopmentConfig(BaseConfig):
    """Development environment configuration."""
    DEBUG = True
    ENV = "development"
    SQLALCHEMY_DATABASE_URI = get_db_uri()
    OTP_MOCK_MODE = True  # Mock OTP for fast local testing


class TestingConfig(BaseConfig):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = False
    ENV = "testing"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    OTP_MOCK_MODE = True
    SECRET_KEY = "testing-secret-key"


class ProductionConfig(BaseConfig):
    """Production environment configuration."""
    DEBUG = False
    ENV = "production"
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    OTP_MOCK_MODE = False
    SQLALCHEMY_DATABASE_URI = get_db_uri()
    
    @classmethod
    def init_app(cls, app):
        pass


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

def get_config(config_name=None):
    """Return appropriate config class based on name or FLASK_ENV."""
    if not config_name:
        config_name = os.environ.get("FLASK_ENV", "development").lower()
    return config_map.get(config_name, DevelopmentConfig)
