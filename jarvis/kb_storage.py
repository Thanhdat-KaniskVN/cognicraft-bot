# jarvis/kb_storage.py
"""Supabase Storage wrapper - upload/download files."""
import os
from dotenv import load_dotenv
load_dotenv()  # MUST be before os.getenv

import httpx
from typing import Optional

SB_URL = os.getenv("SB_URL") or os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SB_KEY") or os.getenv("SUPABASE_KEY", "")
BUCKET = "jarvis-kb"


def _check_env():
    if not SB_URL or not SB_KEY:
        raise RuntimeError("SB_URL hoac SB_KEY chua set")
    return SB_URL.rstrip("/"), SB_KEY


def _public_url(path: str) -> str:
    base, _ = _check_env()
    return f"{base}/storage/v1/object/public/{BUCKET}/{path}"


async def upload_file_async(local_path: str, storage_path: str,
                             content_type: str = "application/octet-stream",
                             timeout: float = 30.0) -> Optional[str]:
    """Upload file len Supabase Storage. Return public URL hoac None.

    Args:
        local_path: path file local
        storage_path: path trong bucket (vd: 'mae101/w5.pdf')
    """
    if not os.path.exists(local_path):
        print(f"[KBStorage] File not found: {local_path}")
        return None

    try:
        base, key = _check_env()
    except Exception as e:
        print(f"[KBStorage] {e}")
        return None

    url = f"{base}/storage/v1/object/{BUCKET}/{storage_path}"

    try:
        with open(local_path, "rb") as f:
            data = f.read()

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, content=data, headers=headers)
            if r.status_code not in (200, 201):
                print(f"[KBStorage] Upload fail {r.status_code}: {r.text[:200]}")
                return None
            return _public_url(storage_path)
    except Exception as e:
        print(f"[KBStorage] Upload err: {e}")
        return None


async def upload_bytes_async(data: bytes, storage_path: str,
                              content_type: str = "application/octet-stream",
                              timeout: float = 30.0) -> Optional[str]:
    """Upload bytes truc tiep (khong can file local)."""
    try:
        base, key = _check_env()
    except Exception as e:
        print(f"[KBStorage] {e}")
        return None

    url = f"{base}/storage/v1/object/{BUCKET}/{storage_path}"

    try:
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, content=data, headers=headers)
            if r.status_code not in (200, 201):
                print(f"[KBStorage] Upload fail {r.status_code}: {r.text[:200]}")
                return None
            return _public_url(storage_path)
    except Exception as e:
        print(f"[KBStorage] Upload err: {e}")
        return None


async def delete_file_async(storage_path: str, timeout: float = 15.0) -> bool:
    try:
        base, key = _check_env()
    except Exception:
        return False

    url = f"{base}/storage/v1/object/{BUCKET}/{storage_path}"
    headers = {"Authorization": f"Bearer {key}"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.delete(url, headers=headers)
            return r.status_code in (200, 204)
    except Exception as e:
        print(f"[KBStorage] Delete err: {e}")
        return False


def health_check() -> dict:
    try:
        base, key = _check_env()
        return {"ok": True, "bucket": BUCKET, "url": base}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    import sys, os, asyncio
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    print("=" * 60)
    print("KB STORAGE TEST")
    print("=" * 60)
    print(f"[Health] {health_check()}")

    async def _test():
        # Test upload bytes
        content = b"# Test file\nHello JARVIS KB system!"
        url = await upload_bytes_async(
            content, "test/hello.txt", content_type="text/plain"
        )
        if url:
            print(f"[Upload] OK -> {url}")
            # Cleanup
            ok = await delete_file_async("test/hello.txt")
            print(f"[Cleanup] {ok}")
        else:
            print("[Upload] FAIL")

    asyncio.run(_test())