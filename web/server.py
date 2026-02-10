"""PaperJam Web — Main FastAPI application server."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import config
import db
from auth import router as auth_router, get_optional_user
from api.library import router as library_router
from api.stream import router as stream_router
from api.playlists import router as playlists_router
from api.favorites import router as favorites_router
from api.settings import router as settings_router
from api.admin import router as admin_router
from api.recents import router as recents_router
from core.scanner import get_scanner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("paperjam-web")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"PaperJam Web {config.VERSION}")
    logger.info(f"Music path: {config.MUSIC_PATH}")
    db.init_db()
    db.create_default_admin()
    db.cleanup_sessions()

    scanner = get_scanner()
    if not scanner.tracks:
        logger.info("No library cache found, starting initial scan...")
        scanner.scan(background=True)
    else:
        logger.info(f"Library loaded: {len(scanner.tracks)} tracks")

    yield

    # Shutdown
    logger.info("Shutting down")


app = FastAPI(
    title="PaperJam Web",
    version=config.VERSION,
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

# Register API routers
app.include_router(auth_router)
app.include_router(library_router)
app.include_router(stream_router)
app.include_router(playlists_router)
app.include_router(favorites_router)
app.include_router(settings_router)
app.include_router(admin_router)
app.include_router(recents_router)


@app.get("/")
def index(request: Request):
    user = get_optional_user(request)
    if not user:
        return FileResponse(config.STATIC_DIR / "login.html")
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/login")
def login_page():
    return FileResponse(config.STATIC_DIR / "login.html")


@app.get("/app")
def app_page(request: Request):
    user = get_optional_user(request)
    if not user:
        return RedirectResponse("/login")
    return FileResponse(config.STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level="info",
    )
