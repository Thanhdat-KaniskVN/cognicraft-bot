# code_room/backend/store_bridge.py
"""
Store Bridge — Proxy Code Room ↔ Store API
- List plugins từ Store
- Install .cogni → extract vào code_room/plugins/
- List installed plugins
- Uninstall plugin
"""
import json
import shutil
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
import httpx


router = APIRouter()

# Config
STORE_API = "http://localhost:8001"
PLUGINS_DIR = Path(__file__).parent.parent / "plugins"
PLUGINS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# HELPER
# ============================================================

async def _store_get(path: str, params: dict = None) -> dict:
    """GET từ Store API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{STORE_API}{path}", params=params)
        if r.status_code != 200:
            raise HTTPException(r.status_code, f"Store API error: {r.text[:200]}")
        return r.json()


async def _store_download(slug: str, version: Optional[str] = None) -> bytes:
    """Download .cogni từ Store API"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        params = {"version": version} if version else {}
        r = await client.get(f"{STORE_API}/api/store/download/{slug}", params=params)
        if r.status_code != 200:
            raise HTTPException(404, f"Không tải được {slug}: {r.text[:200]}")
        return r.content


def _read_local_manifest(plugin_dir: Path) -> dict:
    """Đọc manifest.json của plugin đã cài"""
    mf = plugin_dir / "manifest.json"
    if not mf.exists():
        return {}
    try:
        return json.loads(mf.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ============================================================
# LIST PLUGINS FROM STORE (proxy)
# ============================================================

@router.get("/api/store/plugins")
async def list_store_plugins(
    search: Optional[str] = None,
    category: Optional[str] = None,
    sort: str = Query("downloads", pattern="^(downloads|rating|created_at|name|trending)$"),
    per_page: int = Query(50, ge=1, le=100),
):
    """Proxy list plugins từ Store"""
    params = {"sort": sort, "per_page": per_page}
    if search:
        params["search"] = search
    if category:
        params["category"] = category

    return await _store_get("/api/store/plugins", params)


# ============================================================
# GET PLUGIN DETAIL (proxy)
# ============================================================

@router.get("/api/store/plugins/{slug}")
async def get_store_plugin(slug: str):
    """Proxy plugin detail"""
    return await _store_get(f"/api/store/plugins/{slug}")


# ============================================================
# INSTALL PLUGIN
# ============================================================

@router.post("/api/store/install/{slug}")
async def install_plugin(slug: str, version: Optional[str] = None):
    """
    Install plugin vào code_room/plugins/<slug>/
    Flow:
      1. Download .cogni từ Store
      2. Save tạm
      3. Extract vào plugins/<slug>/
      4. Read manifest.json
      5. Return metadata
    """
    # 1. Download
    content = await _store_download(slug, version)

    # 2. Save tmp
    tmp_zip = PLUGINS_DIR / f".{slug}.cogni.tmp"
    tmp_zip.write_bytes(content)

    target = PLUGINS_DIR / slug
    manifest = {}

    try:
        # 3. Remove cũ (nếu update)
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)

        # 4. Extract
        with zipfile.ZipFile(tmp_zip) as zf:
            # Bảo vệ zip slip
            for member in zf.namelist():
                member_path = (target / member).resolve()
                if not str(member_path).startswith(str(target.resolve())):
                    raise HTTPException(400, f"Zip slip detected: {member}")
            zf.extractall(target)

        # 5. Read manifest
        manifest = _read_local_manifest(target)

    except HTTPException:
        tmp_zip.unlink(missing_ok=True)
        shutil.rmtree(target, ignore_errors=True)
        raise
    except zipfile.BadZipFile:
        tmp_zip.unlink(missing_ok=True)
        shutil.rmtree(target, ignore_errors=True)
        raise HTTPException(400, "File .cogni corrupt")
    except Exception as e:
        tmp_zip.unlink(missing_ok=True)
        shutil.rmtree(target, ignore_errors=True)
        raise HTTPException(500, f"Extract failed: {str(e)}")

    # 6. Cleanup tmp
    tmp_zip.unlink(missing_ok=True)

    return {
        "success": True,
        "slug": slug,
        "path": str(target),
        "version": manifest.get("version", version or "unknown"),
        "name": manifest.get("name", slug),
        "icon": manifest.get("icon", "📦"),
        "manifest": manifest,
    }


# ============================================================
# LIST INSTALLED
# ============================================================

@router.get("/api/store/installed")
async def list_installed():
    """List plugins đã cài vào code_room/plugins/"""
    installed = []

    if not PLUGINS_DIR.exists():
        return {"installed": []}

    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        if not plugin_dir.is_dir():
            continue
        if plugin_dir.name.startswith("."):
            continue

        manifest = _read_local_manifest(plugin_dir)
        installed.append({
            "slug": plugin_dir.name,
            "name": manifest.get("name", plugin_dir.name),
            "version": manifest.get("version", "?"),
            "icon": manifest.get("icon", "📦"),
            "description": manifest.get("description", ""),
            "author": manifest.get("author", "?"),
            "category": manifest.get("category", "tools"),
            "has_entry": (plugin_dir / manifest.get("entry", "plugin.py")).exists(),
            "path": str(plugin_dir),
        })

    return {"installed": installed}


# ============================================================
# UNINSTALL
# ============================================================

@router.delete("/api/store/installed/{slug}")
async def uninstall_plugin(slug: str):
    """Xóa plugin đã cài"""
    target = PLUGINS_DIR / slug

    # Bảo vệ path traversal
    if not str(target.resolve()).startswith(str(PLUGINS_DIR.resolve())):
        raise HTTPException(400, "Invalid slug")

    if not target.exists():
        raise HTTPException(404, f"Plugin {slug} chưa cài")

    try:
        shutil.rmtree(target)
    except Exception as e:
        raise HTTPException(500, f"Uninstall failed: {str(e)}")

    return {"success": True, "slug": slug}