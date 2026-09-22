from app.routes.public import public_bp
from app.routes.auth import auth_bp
from app.routes.customer import customer_bp
from app.routes.admin import admin_bp
from app.routes.staff import staff_bp
from app.routes.security import security_bp
from app.routes.content import content_bp
from app.routes.api import api_bp

__all__ = [
    "public_bp",
    "auth_bp",
    "customer_bp",
    "admin_bp",
    "staff_bp",
    "security_bp",
    "content_bp",
    "api_bp",
]
