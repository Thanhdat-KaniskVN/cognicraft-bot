# store/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from dotenv import load_dotenv

from backend.api import router as store_router
from backend.publish import router as publish_router
from backend.auth import router as auth_router
from backend.github_oauth import router as github_router
from backend.github_sync import router as github_sync_router
from backend.presence import router as presence_router
from backend.theme import router as theme_router
from backend.theme_marketplace import router as marketplace_router
from backend.admin import router as admin_router

_root = Path(__file__).parent.parent
load_dotenv(_root / ".env")


app = FastAPI(
    title="CogniCraft Store API",
    description="Plugin marketplace API",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(store_router, prefix="/api/store", tags=["store"])
app.include_router(publish_router, prefix="/api/store", tags=["publish"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(github_router, prefix="/api/auth", tags=["github"])
app.include_router(github_sync_router, prefix="/api/github", tags=["github-sync"])
app.include_router(presence_router, prefix="/api/presence", tags=["presence"])
app.include_router(theme_router, prefix="/api/theme", tags=["theme"])
app.include_router(marketplace_router, prefix="/api/marketplace", tags=["marketplace"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])


_web_dir = Path(__file__).parent / "web"
if _web_dir.exists():
    app.mount("/store", StaticFiles(directory=str(_web_dir), html=True), name="store-ui")
    print(f"📦 Store UI mounted at /store → {_web_dir}")


@app.get("/")
async def root():
    return {
        "service": "CogniCraft Store API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    from datetime import datetime
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    print(f"\n🚀 Store API: http://localhost:{port}")
    print(f"📖 Docs: http://localhost:{port}/docs\n")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)