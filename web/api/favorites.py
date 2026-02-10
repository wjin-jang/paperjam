"""PaperJam Web — Favorites API routes."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from auth import get_current_user
import db

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


class ToggleFavorite(BaseModel):
    item_type: str  # 'track', 'album', 'artist'
    item_key: str


@router.get("")
def list_favorites(
    item_type: str = Query(None),
    user: dict = Depends(get_current_user),
):
    return db.get_favorites(user["user_id"], item_type)


@router.post("/toggle")
def toggle_favorite(body: ToggleFavorite, user: dict = Depends(get_current_user)):
    if body.item_type not in ("track", "album", "artist"):
        from fastapi import HTTPException
        raise HTTPException(400, "Invalid item_type")
    added = db.toggle_favorite(user["user_id"], body.item_type, body.item_key)
    return {"favorited": added}


@router.get("/check")
def check_favorite(
    item_type: str = Query(...),
    item_key: str = Query(...),
    user: dict = Depends(get_current_user),
):
    return {"favorited": db.is_favorite(user["user_id"], item_type, item_key)}
