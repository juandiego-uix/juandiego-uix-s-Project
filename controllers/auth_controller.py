from functools import wraps
import logging

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, jsonify, redirect, request, session, url_for
from supabase import create_client


def _fernet():
    key = current_app.config.get("FERNET_KEY")
    if not key:
        raise RuntimeError("FERNET_KEY no está configurada.")
    return Fernet(key.encode("ascii"))


def encrypt_session_value(value):
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_session_value(value):
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken:
        clear_auth()
        return None


def authenticate(email, password):
    client = create_client(
        current_app.config["SUPABASE_URL"],
        current_app.config["SUPABASE_ANON_KEY"],
    )
    result = client.auth.sign_in_with_password({"email": email, "password": password})
    user = result.user
    role_result = (
        client.table("user_roles")
        .select("role")
        .eq("user_id", user.id)
        .limit(1)
        .execute()
    )
    if not role_result.data or role_result.data[0]["role"] != "admin":
        client.auth.sign_out()
        raise PermissionError("Esta cuenta no tiene autorización de administrador.")
    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["email"] = user.email
    session["access_token"] = encrypt_session_value(result.session.access_token)
    session["refresh_token"] = encrypt_session_value(result.session.refresh_token)
    session["csrf_token"] = Fernet.generate_key().decode("ascii")


def load_auth():
    access = decrypt_session_value(session.get("access_token"))
    refresh = decrypt_session_value(session.get("refresh_token"))
    if not access or not refresh:
        clear_auth()
        return
    client = create_client(current_app.config["SUPABASE_URL"], current_app.config["SUPABASE_ANON_KEY"])
    try:
        client.auth.set_session(access, refresh)
        current_session = client.auth.get_session()
        user = client.auth.get_user().user
        current_access = current_session.access_token
        current_refresh = current_session.refresh_token
        session["access_token"] = encrypt_session_value(current_access)
        session["refresh_token"] = encrypt_session_value(current_refresh)
        if user.id != session.get("user_id"):
            clear_auth()
    except Exception:
        logging.getLogger(__name__).warning("Supabase session validation failed")
        clear_auth()


def clear_auth():
    session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("access_token"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Autenticación requerida."}), 401
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapped


def csrf_protect(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        submitted = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        expected = session.get("csrf_token")
        if not expected or not submitted or submitted != expected:
            return jsonify({"error": "Solicitud no válida. Recargue la página e intente nuevamente."}), 403
        return view(*args, **kwargs)

    return wrapped
