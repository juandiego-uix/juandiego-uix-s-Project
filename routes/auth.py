from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from controllers.auth_controller import authenticate, clear_auth, csrf_protect
from database import get_user_client

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
@csrf_protect
def login():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    if not email or not password:
        return render_template("login.html", error="Ingrese su correo y contraseña."), 400
    try:
        authenticate(email, password)
    except PermissionError as error:
        return render_template("login.html", error=str(error)), 403
    except Exception:
        current_app.logger.warning("Login failed for submitted email")
        return render_template("login.html", error="Credenciales incorrectas o servicio no disponible."), 401
    return redirect(url_for("index"))


@auth_bp.post("/logout")
@csrf_protect
def logout():
    try:
        get_user_client().auth.sign_out()
    except Exception:
        current_app.logger.warning("Supabase sign-out failed; clearing local session")
    clear_auth()
    return redirect(url_for("index"))
