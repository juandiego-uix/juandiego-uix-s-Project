import secrets
from datetime import datetime, timedelta
from re import fullmatch
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cryptography.fernet import Fernet
from flask import Flask, jsonify, render_template, request, send_from_directory, session
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException

load_dotenv()

from config import Config
from controllers.auth_controller import authenticate, clear_auth, load_auth
from controllers.finance_controller import FinanceController, ValidationError
from routes.auth import auth_bp
from routes.finance import finance_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    missing = [
        key for key in ("SECRET_KEY", "FERNET_KEY", "SUPABASE_URL", "SUPABASE_ANON_KEY")
        if not app.config.get(key)
    ]
    if missing:
        raise RuntimeError(f"Faltan variables de entorno requeridas: {', '.join(missing)}")
    if len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("SECRET_KEY debe tener al menos 32 caracteres.")
    supabase_url = app.config["SUPABASE_URL"].strip()
    parsed_supabase_url = urlsplit(supabase_url)
    if (
        parsed_supabase_url.scheme != "https"
        or not parsed_supabase_url.hostname
        or parsed_supabase_url.username
        or parsed_supabase_url.password
        or parsed_supabase_url.path not in ("", "/")
        or parsed_supabase_url.query
        or parsed_supabase_url.fragment
    ):
        raise RuntimeError(
            "SUPABASE_URL debe ser la URL base HTTPS del proyecto, sin /rest/v1 ni otros parámetros."
        )
    app.config["SUPABASE_URL"] = supabase_url.rstrip("/")
    if not fullmatch(r"[A-Z]{3}", app.config["CURRENCY_CODE"]):
        raise RuntimeError("CURRENCY_CODE debe ser un código ISO 4217 de tres letras.")
    try:
        Fernet(app.config["FERNET_KEY"].encode("ascii"))
        ZoneInfo(app.config["BUSINESS_TIMEZONE"])
    except (ValueError, UnicodeEncodeError, ZoneInfoNotFoundError) as error:
        raise RuntimeError("FERNET_KEY o BUSINESS_TIMEZONE no tiene un formato válido.") from error
    app.permanent_session_lifetime = timedelta(hours=8)
    app.register_blueprint(auth_bp)
    app.register_blueprint(finance_bp)

    @app.before_request
    def restore_authentication():
        if request.endpoint in {"auth.login", "static", "service_worker"}:
            return None
        if session.get("access_token"):
            load_auth()
        return None

    @app.get("/")
    def index():
        if not session.get("access_token"):
            session.setdefault("csrf_token", secrets.token_urlsafe(32))
            return render_template("login.html")
        return render_template(
            "dashboard.html",
            csrf_token=session.get("csrf_token", ""),
            initial_date=datetime.now(ZoneInfo(app.config["BUSINESS_TIMEZONE"])).date().isoformat(),
            business_timezone=app.config["BUSINESS_TIMEZONE"],
        )

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": error.description}), error.code
        return error

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled application error")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Ocurrió un error interno. Intente nuevamente."}), 500
        return "Ocurrió un error interno.", 500

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        if request.path.startswith("/static/") or request.endpoint == "service_worker":
            response.headers["Cache-Control"] = "no-cache"
        else:
            response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "font-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; form-action 'self'; "
            "frame-ancestors 'none'; manifest-src 'self'; worker-src 'self'"
        )
        if request.is_secure or app.config["SESSION_COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.get("/service-worker.js")
    def service_worker():
        response = send_from_directory(app.static_folder, "service-worker.js", mimetype="application/javascript")
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        return response

    return app


app = create_app()
