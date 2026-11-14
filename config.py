import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    FERNET_KEY = os.environ.get("FERNET_KEY")
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
    CURRENCY_CODE = os.environ.get("CURRENCY_CODE", "USD")
    BUSINESS_TIMEZONE = os.environ.get("BUSINESS_TIMEZONE", "UTC")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_NAME = "aranko_session"
    MAX_CONTENT_LENGTH = 1024 * 1024
