"""PaperJam Web — User settings API routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user
import db

router = APIRouter(prefix="/api/settings", tags=["settings"])

VALID_SETTINGS = {
    "streaming_quality": ["low", "medium", "high", "extreme", "original"],
    "locale": ["en", "ko", "ja"],
    "theme": ["dark", "light"],
    "recents_limit": ["10", "30", "50", "100"],
}


class UpdateSetting(BaseModel):
    key: str
    value: str


@router.get("")
def get_settings(user: dict = Depends(get_current_user)):
    return db.get_user_settings(user["user_id"])


@router.put("")
def update_setting(body: UpdateSetting, user: dict = Depends(get_current_user)):
    if body.key not in VALID_SETTINGS:
        from fastapi import HTTPException
        raise HTTPException(400, f"Invalid setting: {body.key}")
    if body.value not in VALID_SETTINGS[body.key]:
        from fastapi import HTTPException
        raise HTTPException(400, f"Invalid value for {body.key}: {body.value}")
    db.set_user_setting(user["user_id"], body.key, body.value)
    return {"ok": True}
