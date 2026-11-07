from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.modules.auth.dependencies import COOKIE_NAME, get_current_user, serializer
from app.shared.validators import fail, text

router = APIRouter(prefix="/auth", tags=["Sesión de demostración"])


class Login(BaseModel):
    username: str = Field(max_length=80)
    password: str = Field(max_length=200)


@router.post("/login")
def login(data: Login, response: Response):
    username = text(data.username, "usuario", 80)
    if not data.password.strip():
        fail("La contraseña de demostración no puede estar vacía.")
    settings = get_settings()
    response.set_cookie(COOKIE_NAME, serializer().dumps({"username": username}), max_age=settings.session_hours * 3600, httponly=True, secure=settings.session_cookie_secure, samesite="strict", path="/")
    return {"username": username}


@router.get("/me")
def me(username: str = Depends(get_current_user)):
    return {"username": username}


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="strict")
