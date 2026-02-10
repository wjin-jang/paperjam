"""PaperJam Web — Admin API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
import db

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(user: dict = Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(403, "Admin access required")
    return user


class CreateUser(BaseModel):
    username: str
    display_name: str
    password: str
    is_admin: bool = False


class UpdateUser(BaseModel):
    display_name: str | None = None
    password: str | None = None
    is_admin: bool | None = None


@router.get("/users")
def list_users(user: dict = Depends(require_admin)):
    return db.list_users()


@router.post("/users")
def create_user(body: CreateUser, user: dict = Depends(require_admin)):
    if db.get_user_by_username(body.username):
        raise HTTPException(409, "Username already exists")
    user_id = db.create_user(body.username, body.display_name, body.password, body.is_admin)
    return {"id": user_id, "username": body.username}


@router.put("/users/{user_id}")
def update_user(user_id: int, body: UpdateUser, admin: dict = Depends(require_admin)):
    target = db.get_user_by_id(user_id)
    if not target:
        raise HTTPException(404, "User not found")
    updates = {}
    if body.display_name is not None:
        updates["display_name"] = body.display_name
    if body.password is not None:
        updates["password"] = body.password
    if body.is_admin is not None:
        updates["is_admin"] = int(body.is_admin)
    if updates:
        db.update_user(user_id, **updates)
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    if user_id == admin["user_id"]:
        raise HTTPException(400, "Cannot delete yourself")
    target = db.get_user_by_id(user_id)
    if not target:
        raise HTTPException(404, "User not found")
    db.delete_user(user_id)
    return {"ok": True}
