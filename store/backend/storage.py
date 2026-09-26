# store/backend/storage.py
"""
Supabase Storage — Persistent file storage
- Tolerant env var loading (handles leading/trailing whitespace in names)
"""
import os
import httpx
from typing import Optional


def _get_env(name: str, default: str = "") -> str:
    """Get env var — tolerant với whitespace trong tên"""
    # Try exact match first
    val = os.getenv(name)
    if val:
        return val.strip()

    # Try with whitespace stripped in key names
    for key, value in os.environ.items():
        if key.strip() == name:
            return value.strip()

    return default


SUPABASE_URL = (
    _get_env("SB_URL") or
    _get_env("SUPABASE_URL") or
    "https://mqgcvrojhafewfokpwtx.supabase.co"
)
SUPABASE_SERVICE_KEY = (
    _get_env("SB_SERVICE_KEY") or
    _get_env("SUPABASE_SERVICE_KEY")
)
BUCKET = "plugins"


async def upload_file(file_bytes: bytes, filename: str, content_type: str = "application/zip") -> bool:
    """Upload file lên Supabase Storage"""
    if not SUPABASE_SERVICE_KEY:
        # Debug info
        print(f"[Storage] Missing SUPABASE_SERVICE_KEY. Available keys: {list(os.environ.keys())[:30]}")
        raise RuntimeError("SUPABASE_SERVICE_KEY chưa cấu hình")

    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{filename}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            url,
            content=file_bytes,
            headers={
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": content_type,
                "x-upsert": "true",
            },
        )
    return r.status_code in (200, 201)


async def download_file(filename: str) -> Optional[bytes]:
    """Download file từ Supabase Storage"""
    if not SUPABASE_SERVICE_KEY:
        raise RuntimeError("SUPABASE_SERVICE_KEY chưa cấu hình")

    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{filename}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(
            url,
            headers={"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
        )

    if r.status_code == 200:
        return r.content
    return None


async def delete_file(filename: str) -> bool:
    """Delete file khỏi Supabase Storage"""
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{filename}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.delete(
            url,
            headers={"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
        )
    return r.status_code == 200