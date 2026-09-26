# store/main.py
"""
Store API - Standalone FastAPI service
Deploy to Railway as separate service
"""
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


# Load env
_root = Path(__file__).parent.parent
load_dotenv(_root / ".env")


app = FastAPI(
    title="CogniCraft Store API",
    description="Plugin marketplace API",
    version="1.0.0",
)


# CORS - Cho phép Cloudflare Pages truy cập
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP: allow all. Production: limit to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include router
app.include_router(store_router, prefix="/api/store", tags=["store"])
app.include_router(publish_router, prefix="/api/store", tags=["publish"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(github_router, prefix="/api/auth", tags=["github"])
app.include_router(github_sync_router, prefix="/api/github", tags=["github-sync"])


# ============================================================
# SERVE STORE UI (dev + prod fallback)
# ============================================================
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

@app.get("/debug/env")
async def debug_env():
    """DEBUG — XÓA sau khi fix"""
    import os
    return {
        "SB_KEY_exists": "SB_KEY" in os.environ,
        "SB_KEY_length": len(os.environ.get("SB_KEY", "")),
        "SB_KEY_prefix": os.environ.get("SB_KEY", "")[:15],
        "SB_URL_exists": "SB_URL" in os.environ,
        "SB_URL_value": os.environ.get("SB_URL", "")[:50],
        "all_sb_keys": [k for k in os.environ.keys() if "SB" in k.upper()],
    }
@app.get("/health")
async def health():
    from datetime import datetime
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8001))
    print(f"\n🚀 Store API: http://localhost:{port}")
    print(f"📖 Docs: http://localhost:{port}/docs\n")

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)