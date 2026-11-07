from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.core.config import get_settings

COOKIE_NAME = "transporte_session"


def serializer():
    return URLSafeTimedSerializer(get_settings().session_secret, salt="transporte-demo-session")


def get_current_user(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Inicia una sesión de demostración para continuar.")
    try:
        payload = serializer().loads(token, max_age=get_settings().session_hours * 3600)
        username = payload["username"]
        if not isinstance(username, str) or not username.strip() or len(username) > 80:
            raise ValueError()
        return username
    except (BadSignature, KeyError, TypeError, ValueError):
        raise HTTPException(401, "La sesión ha caducado. Ingresa nuevamente.")
