# store/backend/storage.py
"""
Supabase Storage — Persistent file storage
Uses short env names SB_KEY + SB_URL to avoid Railway whitespace bug
"""
import os
import httpx
from typing import Optional


# ⚠️ Railway strip variable name — dùng tên ngắn để tránh bug
SUPABASE_URL = os.getenv("SB_URL", "https://mqgcvrojhafewfokpwtx.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SB_KEY", "")
BUCKET = "plugins"


async def upload_file(file_bytes: bytes, filename: str, content_type: str = "application/zip") -> bool:
    if not SUPABASE_SERVICE_KEY:
        raise RuntimeError("SB_KEY chưa cấu hình trên Railway")

    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{filename}"

    # DEBUG — XÓA sau khi fix
    print(f"[Storage DEBUG] SUPABASE_URL = {repr(SUPABASE_URL)}")
    print(f"[Storage DEBUG] URL = {repr(url)}")
    print(f"[Storage DEBUG] Bucket = {repr(BUCKET)}")
    print(f"[Storage DEBUG] Filename = {repr(filename)}")
    print(f"[Storage DEBUG] Key prefix = {SUPABASE_SERVICE_KEY[:20] if SUPABASE_SERVICE_KEY else 'EMPTY'}")

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
    if not SUPABASE_SERVICE_KEY:
        raise RuntimeError("SB_KEY chưa cấu hình")

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
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{filename}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.delete(
            url,
            headers={"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
        )
    return r.status_code == 200