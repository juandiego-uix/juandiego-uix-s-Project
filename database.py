from flask import current_app, session
from supabase import Client, create_client

from controllers.auth_controller import decrypt_session_value


def get_user_client() -> Client:
    access = decrypt_session_value(session.get("access_token"))
    refresh = decrypt_session_value(session.get("refresh_token"))
    if not access or not refresh:
        raise PermissionError("La sesión expiró. Inicie sesión nuevamente.")
    client = create_client(
        current_app.config["SUPABASE_URL"],
        current_app.config["SUPABASE_ANON_KEY"],
    )
    client.auth.set_session(access, refresh)
    return client
