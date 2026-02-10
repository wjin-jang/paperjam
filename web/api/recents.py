"""PaperJam Web — Recently played API routes."""

from fastapi import APIRouter, Depends, Query

from auth import get_current_user
import db

router = APIRouter(prefix="/api/recents", tags=["recents"])


@router.get("")
def list_recents(
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    settings = db.get_user_settings(user["user_id"])
    max_limit = int(settings.get("recents_limit", 50))
    return db.get_recents(user["user_id"], min(limit, max_limit))
