import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.services.settings_service import SettingsService


app = create_app("production")

with app.app_context():
    db.create_all()
    SettingsService.seed_defaults()
