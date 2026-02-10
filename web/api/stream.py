"""PaperJam Web — Audio streaming and cover art API routes."""

import base64
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse, StreamingResponse

from auth import get_current_user
from config import MUSIC_PATH
from core.transcoder import transcode, needs_transcoding, get_mime_type
from core.cover_art import get_cover_path
import db

router = APIRouter(prefix="/api", tags=["stream"])


def decode_path(encoded: str) -> Path:
    """Decode a base64-encoded file path and validate it's within MUSIC_PATH."""
    try:
        decoded = base64.urlsafe_b64decode(encoded).decode()
    except Exception:
        raise HTTPException(400, "Invalid path encoding")

    path = Path(decoded).resolve()
    if not str(path).startswith(str(MUSIC_PATH.resolve())):
        raise HTTPException(403, "Access denied")
    if not path.exists():
        raise HTTPException(404, "File not found")
    return path


@router.get("/stream/{encoded_path:path}")
def stream_audio(
    encoded_path: str,
    request: Request,
    quality: str = Query("high"),
    user: dict = Depends(get_current_user),
):
    """Stream an audio file, optionally transcoded to the requested quality."""
    path = decode_path(encoded_path)

    # Record as recently played
    db.add_recent(user["user_id"], str(path))

    # Determine if transcoding is needed
    if quality != "original" and needs_transcoding(str(path), quality):
        transcoded = transcode(str(path), quality)
        if transcoded:
            serve_path = transcoded
            mime = "audio/mpeg"
        else:
            # Fallback to original if transcoding fails
            serve_path = path
            mime = get_mime_type(str(path))
    else:
        serve_path = path
        mime = get_mime_type(str(path))

    file_size = os.path.getsize(serve_path)

    # Handle Range requests for seeking
    range_header = request.headers.get("range")
    if range_header:
        ranges = range_header.replace("bytes=", "").split("-")
        start = int(ranges[0]) if ranges[0] else 0
        end = int(ranges[1]) if ranges[1] else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        def iter_range():
            with open(serve_path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=mime,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
            },
        )

    return FileResponse(
        serve_path,
        media_type=mime,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        },
    )


@router.get("/cover/{encoded_path:path}")
def get_cover(
    encoded_path: str,
    size: str = Query("medium"),
    user: dict = Depends(get_current_user),
):
    """Get cover art for a track."""
    path = decode_path(encoded_path)
    cover = get_cover_path(str(path), size)
    if not cover:
        raise HTTPException(404, "No cover art")
    return FileResponse(cover, media_type="image/jpeg")
