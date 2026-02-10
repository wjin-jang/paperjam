"""PaperJam Web — Library API routes."""

from fastapi import APIRouter, Depends, Query

from auth import get_current_user
from core.scanner import get_scanner

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("/stats")
def library_stats(user: dict = Depends(get_current_user)):
    scanner = get_scanner()
    stats = scanner.stats
    stats["scanning"] = scanner.scanning
    if scanner.scanning:
        stats["scan_progress"] = scanner.scan_progress
        stats["scan_total"] = scanner.scan_total
    return stats


@router.get("/artists")
def list_artists(user: dict = Depends(get_current_user)):
    return get_scanner().get_artists()


@router.get("/artists/{name}")
def get_artist(name: str, user: dict = Depends(get_current_user)):
    result = get_scanner().get_artist(name)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(404, "Artist not found")
    return result


@router.get("/albums")
def list_albums(user: dict = Depends(get_current_user)):
    return get_scanner().get_albums()


@router.get("/albums/{name}")
def get_album(name: str, user: dict = Depends(get_current_user)):
    result = get_scanner().get_album(name)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(404, "Album not found")
    return result


@router.get("/tracks")
def list_tracks(user: dict = Depends(get_current_user)):
    return get_scanner().get_tracks()


@router.get("/search")
def search_library(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    return get_scanner().search(q, limit)


@router.post("/scan")
def trigger_scan(user: dict = Depends(get_current_user)):
    if not user.get("is_admin"):
        from fastapi import HTTPException
        raise HTTPException(403, "Admin only")
    scanner = get_scanner()
    scanner.scan(background=True)
    return {"status": "scanning"}
