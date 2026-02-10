"""PaperJam Web — Playlist API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
import db

router = APIRouter(prefix="/api/playlists", tags=["playlists"])


class CreatePlaylist(BaseModel):
    name: str


class RenamePlaylist(BaseModel):
    name: str


class AddTrack(BaseModel):
    track_path: str


@router.get("")
def list_playlists(user: dict = Depends(get_current_user)):
    return db.get_playlists(user["user_id"])


@router.post("")
def create_playlist(body: CreatePlaylist, user: dict = Depends(get_current_user)):
    playlist_id = db.create_playlist(user["user_id"], body.name)
    return {"id": playlist_id, "name": body.name}


@router.get("/{playlist_id}")
def get_playlist(playlist_id: int, user: dict = Depends(get_current_user)):
    tracks = db.get_playlist_tracks(playlist_id, user["user_id"])
    return {"id": playlist_id, "tracks": tracks}


@router.put("/{playlist_id}")
def rename_playlist(playlist_id: int, body: RenamePlaylist, user: dict = Depends(get_current_user)):
    db.rename_playlist(playlist_id, user["user_id"], body.name)
    return {"ok": True}


@router.delete("/{playlist_id}")
def delete_playlist(playlist_id: int, user: dict = Depends(get_current_user)):
    db.delete_playlist(playlist_id, user["user_id"])
    return {"ok": True}


@router.post("/{playlist_id}/tracks")
def add_track(playlist_id: int, body: AddTrack, user: dict = Depends(get_current_user)):
    db.add_track_to_playlist(playlist_id, user["user_id"], body.track_path)
    return {"ok": True}


@router.delete("/{playlist_id}/tracks/{track_id}")
def remove_track(playlist_id: int, track_id: int, user: dict = Depends(get_current_user)):
    db.remove_track_from_playlist(playlist_id, user["user_id"], track_id)
    return {"ok": True}
