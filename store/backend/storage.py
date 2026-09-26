# store/backend/storage.py
"""
Supabase Storage — Persistent file storage
"""
import os
import httpx
from typing import Optional


SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mqgcvrojhafewfokpwtx.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
BUCKET = "plugins"


async def upload_file(file_bytes: bytes, filename: str, content_type: str = "application/zip") -> bool:
    """Upload file lên Supabase Storage"""
    if not SUPABASE_SERVICE_KEY:
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