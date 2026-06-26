from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import APP_HOST, APP_MODE, APP_PORT, FRONTEND_DIR
from routers.api import router as api_router
from routers.auth import router as auth_router
from routers.users import router as users_router
from config import LOCAL_DATA_DIR, LOGS_DIR, SHARED_DATA_DIR, STORAGE_BACKEND
from services import excel_service
from services.bootstrap_service import ensure_local_runtime

ensure_local_runtime()

app = FastAPI(title="سامانه تدارکات", version="3.0.0")


@app.on_event("startup")
def startup_init_data():
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        SHARED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    from services.settings_service import apply_runtime_paths
    apply_runtime_paths()
    if STORAGE_BACKEND == "sqlite":
        from db.migrate_legacy import run_if_needed
        run_if_needed()
    if APP_MODE != "import":
        excel_service.warm_cache()
    from services.import_scheduler_service import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
def shutdown_cleanup():
    from services.import_scheduler_service import stop_scheduler
    stop_scheduler()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(api_router)

static_dir = FRONTEND_DIR
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def index():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        return {"message": "frontend/index.html not found"}
    return FileResponse(index_path)


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith("api"):
        return {"detail": "Not Found"}
    file_path = FRONTEND_DIR / full_path
    if file_path.is_file():
        return FileResponse(file_path)
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "not found"}