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