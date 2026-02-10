"""PaperJam Web — Authentication middleware and routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from config import COOKIE_NAME
import db

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def get_current_user(request: Request) -> dict:
    """Dependency: extract and validate session from cookie."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Not authenticated")
    user = db.validate_session(token)
    if not user:
        raise HTTPException(401, "Session expired")
    return user


def get_optional_user(request: Request) -> dict | None:
    """Dependency: extract user if authenticated, None otherwise."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return db.validate_session(token)


@router.post("/auth/login")
def login(body: LoginRequest, response: Response):
    user = db.get_user_by_username(body.username)
    if not user or not db.verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    token = db.create_session(user["id"])
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=db.SESSION_EXPIRY_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True in production with HTTPS
    )
    return {
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "is_admin": bool(user["is_admin"]),
    }


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.delete_session(token)
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/auth/me")
def get_me(user: dict = Depends(get_current_user)):
    return user


@router.post("/auth/change-password")
def change_password(body: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    full_user = db.get_user_by_id(user["user_id"])
    if not full_user or not db.verify_password(body.current_password, full_user["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    db.update_user(user["user_id"], password=body.new_password)
    return {"ok": True}
