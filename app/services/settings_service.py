from decimal import Decimal
from typing import Any, Optional, Dict
from app.extensions import db
from app.models.setting import Setting, SettingCategory

class SettingsService:
    """
    Centralized service for reading and writing runtime business settings.
    Provides memory caching to avoid repetitive database hits per request.
    """
    _cache: Dict[str, Any] = {}
    _cache_initialized = False

    # Default fallback values if database hasn't been seeded yet
    DEFAULTS = {
        "partner_commission_enabled": ("1", "bool", SettingCategory.COMMISSION, "Enable the Staff Partner commission system"),
        "partner_referral_links_enabled": ("1", "bool", SettingCategory.COMMISSION, "Enable personal Staff Partner referral links"),
        "partner_commission_wallet_enabled": ("1", "bool", SettingCategory.COMMISSION, "Enable the Staff Partner commission wallet"),
        "partner_levels_enabled": ("1", "bool", SettingCategory.COMMISSION, "Enable Staff Partner levels"),
        "partner_share_availability_enabled": ("1", "bool", SettingCategory.COMMISSION, "Enable Staff Partner availability sharing"),
        "park_name": ("FREEDOM PARK", "string", SettingCategory.GENERAL, "Official Park Name"),
        "park_location": ("Pernambut, India", "string", SettingCategory.GENERAL, "Park Physical Location"),
        "park_phone": ("", "string", SettingCategory.CONTACT, "Official Phone Number (Configurable)"),
        "park_whatsapp": ("", "string", SettingCategory.CONTACT, "Official WhatsApp Number (Configurable)"),
        "operating_hours": ("8:00 AM – 8:00 PM", "string", SettingCategory.BOOKING, "Daily Park Hours"),
        "max_capacity": ("100", "int", SettingCategory.BOOKING, "Max Allowed Park Capacity per Day"),
        "booking_window_days": ("30", "int", SettingCategory.BOOKING, "How many days into the future customers can book"),
        "weekday_price": ("2000", "decimal", SettingCategory.PRICING, "Standard Monday–Friday Daily Park Price"),
        "weekend_price": ("3000", "decimal", SettingCategory.PRICING, "Standard Saturday–Sunday Daily Park Price"),
        "customer_cancel_threshold_hours": ("24", "int", SettingCategory.CANCELLATION, "Hours before booking for partial refund"),
        "customer_cancel_refund_before": ("50", "decimal", SettingCategory.CANCELLATION, "Customer refund percentage before threshold"),
        "customer_cancel_refund_after": ("0", "decimal", SettingCategory.CANCELLATION, "Customer refund percentage under threshold"),
        "park_cancel_refund_percentage": ("100", "decimal", SettingCategory.CANCELLATION, "Refund percentage when Park cancels"),
        "cancellation_policy_text": (
            "Cancellations made 24 hours or more before the booked date receive a 50% refund. "
            "Cancellations within 24 hours receive 0% refund. "
            "If Freedom Park cancels due to park-side reasons or maintenance, 100% refund is issued.",
            "text", SettingCategory.CANCELLATION, "Public Cancellation Policy Text"
        ),
        "default_commission": ("500", "decimal", SettingCategory.COMMISSION, "Default fixed commission per confirmed booking"),
        "google_maps_url": ("", "string", SettingCategory.CONTACT, "Google Maps Direct Link"),
        "instagram_url": ("", "string", SettingCategory.CONTACT, "Instagram Profile Link"),
        "facebook_url": ("", "string", SettingCategory.CONTACT, "Facebook Profile Link"),
        "payment_mode": ("SANDBOX", "string", SettingCategory.SYSTEM, "Payment Mode: SANDBOX or LIVE"),
        # Homepage / hero presentation settings (editable from Admin > Homepage & Gallery).
        "brand_subtitle": ("A UNIT OF MOOKANE MUQTHAR SAHIB PARK", "string", SettingCategory.GENERAL, "Small brand line shown under Freedom Park"),
        "hero_kicker": ("Your Family · Your Time · Our Park", "string", SettingCategory.GENERAL, "Homepage hero eyebrow text"),
        "hero_title_line1": ("Nature Brings People", "string", SettingCategory.GENERAL, "Homepage hero main heading line 1"),
        "hero_title_line2": ("Together", "string", SettingCategory.GENERAL, "Homepage hero highlighted heading line 2"),
        "hero_subtitle": ("Escape the stress, enjoy the fresh air and make beautiful memories with your family and friends at Freedom Park.", "text", SettingCategory.GENERAL, "Homepage hero supporting text"),
        "hero_background_path": ("/static/images/hero-v4-design-placeholder.jpg", "string", SettingCategory.GENERAL, "Homepage hero background image URL or static path"),
        "gallery_heading": ("A Glimpse of Freedom Park", "string", SettingCategory.GENERAL, "Homepage gallery heading"),
        "gallery_subtitle": ("See the greenery, open spaces and peaceful moments waiting for your family.", "text", SettingCategory.GENERAL, "Homepage gallery supporting text"),
    }

    @classmethod
    def invalidate_cache(cls):
        """Clear memory cache."""
        cls._cache.clear()
        cls._cache_initialized = False

    @classmethod
    def _load_cache(cls):
        """Load all settings from DB into memory cache."""
        try:
            settings = Setting.query.all()
            for s in settings:
                cls._cache[s.key] = s.get_typed_value()
            cls._cache_initialized = True
        except Exception:
            # Fallback before tables are created
            pass

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get setting value by key with typed casting."""
        if not cls._cache_initialized:
            cls._load_cache()
        if key in cls._cache:
            return cls._cache[key]
        
        # Fallback to defaults
        if key in cls.DEFAULTS:
            default_str, val_type, _, _ = cls.DEFAULTS[key]
            temp_setting = Setting(key=key, value=default_str, value_type=val_type)
            return temp_setting.get_typed_value()
        
        return default

    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        val = cls.get(key, default)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    @classmethod
    def get_decimal(cls, key: str, default: Decimal = Decimal("0.00")) -> Decimal:
        val = cls.get(key, default)
        try:
            return Decimal(str(val))
        except Exception:
            return default

    @classmethod
    def get_bool(cls, key: str, default: bool = False) -> bool:
        val = cls.get(key, default)
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes", "on")

    @classmethod
    def set(cls, key: str, value: Any, updated_by_id: Optional[int] = None) -> Setting:
        """Create or update a setting and clear cache."""
        setting = Setting.query.filter_by(key=key).first()
        if not setting:
            # Look up metadata from defaults if available
            _, val_type, cat, desc = cls.DEFAULTS.get(key, (str(value), "string", SettingCategory.GENERAL, ""))
            setting = Setting(key=key, value_type=val_type, category=cat, description=desc)
            db.session.add(setting)

        setting.set_typed_value(value)
        setting.updated_by = updated_by_id
        db.session.commit()
        
        cls.invalidate_cache()
        return setting

    @classmethod
    def seed_defaults(cls):
        """Seed initial default settings into database if not present."""
        for key, (val, vtype, cat, desc) in cls.DEFAULTS.items():
            existing = Setting.query.filter_by(key=key).first()
            if not existing:
                s = Setting(key=key, value=val, value_type=vtype, category=cat, description=desc)
                db.session.add(s)
        db.session.commit()
        cls.invalidate_cache()
