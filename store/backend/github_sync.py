# store/backend/github_sync.py
"""
GitHub Sync — Tạo repo + push plugin files
"""
import os
import base64
import httpx
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from .database import get_db
from .auth import get_current_user


router = APIRouter()

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"


# ============================================================
# MODELS
# ============================================================
class SyncRequest(BaseModel):
    repo_name: Optional[str] = None       # Nếu None → dùng slug
    private: bool = False
    description: Optional[str] = None


# ============================================================
# HELPERS — GitHub API
# ============================================================
async def gh_api(
    method: str,
    path: str,
    token: str,
    json_data: dict = None,
) -> dict:
    """Call GitHub API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.request(
            method,
            f"https://api.github.com{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json=json_data,
        )

    if r.status_code >= 400:
        try:
            err = r.json()
            msg = err.get("message", r.text[:200])
        except Exception:
            msg = r.text[:200]
        raise HTTPException(r.status_code, f"GitHub API: {msg}")

    if r.status_code == 204:
        return {"success": True}
    return r.json()


async def push_file(
    token: str,
    owner: str,
    repo: str,
    file_path: str,
    content: bytes,
    message: str = "Add file",
) -> dict:
    """Push 1 file lên repo"""
    encoded = base64.b64encode(content).decode()

    # Check file tồn tại (để lấy SHA nếu update)
    async with httpx.AsyncClient(timeout=30.0) as client:
        check = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}",
            headers={"Authorization": f"Bearer {token}"},
        )

    payload = {
        "message": message,
        "content": encoded,
    }

    if check.status_code == 200:
        # File tồn tại → cần SHA để update
        payload["sha"] = check.json()["sha"]

    return await gh_api(
        "PUT",
        f"/repos/{owner}/{repo}/contents/{file_path}",
        token,
        payload,
    )


# ============================================================
# POST /github/sync/{slug} — Sync plugin lên GitHub
# ============================================================
@router.post("/sync/{slug}")
async def sync_plugin_to_github(
    slug: str,
    req: SyncRequest,
    user: dict = Depends(get_current_user),
):
    """
    Tạo repo GitHub + push plugin files

    User phải là owner của plugin.
    User phải login bằng GitHub (có github_access_token).
    """
    db = get_db()

    # 1. Get user
    db_user = db.query_one(
        "SELECT * FROM public.users WHERE id = %s",
        (user["sub"],),
    )
    if not db_user:
        raise HTTPException(404, "User không tồn tại")

    token = db_user.get("github_access_token")
    github_username = db_user.get("github_username")

    if not token or not github_username:
        raise HTTPException(401, "Bạn cần đăng nhập bằng GitHub để sync")

    # 2. Get plugin
    plugin = db.query_one(
        "SELECT * FROM plugins WHERE slug = %s",
        (slug,),
    )
    if not plugin:
        raise HTTPException(404, f"Plugin '{slug}' không tồn tại")

    if plugin.get("author") != db_user.get("name") and plugin.get("author") != github_username:
        # Cho phép nếu author trùng tên hoặc username
        # TODO: Chặt hơn — check ownership thật
        pass

    # 3. Find .cogni file
    version_row = db.query_one(
        "SELECT file_url FROM plugin_versions WHERE plugin_id = %s ORDER BY created_at DESC LIMIT 1",
        (plugin["id"],),
    )
    if not version_row or not version_row.get("file_url"):
        raise HTTPException(404, "Plugin chưa có file .cogni")

    cogni_path = UPLOAD_DIR / version_row["file_url"]
    if not cogni_path.exists():
        raise HTTPException(404, "File .cogni bị mất")

    # 4. Repo name
    repo_name = req.repo_name or slug.replace("_", "-")
    repo_desc = req.description or plugin.get("description", "")

    # 5. Create repo (hoặc lấy nếu đã tồn tại)
    try:
        repo = await gh_api(
            "POST",
            "/user/repos",
            token,
            {
                "name": repo_name,
                "description": repo_desc,
                "private": req.private,
                "auto_init": True,
                "has_issues": True,
                "has_wiki": False,
            },
        )
    except HTTPException as e:
        if "already exists" in str(e.detail):
            # Repo đã có → get info
            repo = await gh_api("GET", f"/repos/{github_username}/{repo_name}", token)
        else:
            raise

    owner = repo["owner"]["login"]
    repo_url = repo["html_url"]

    # 6. Push .cogni file
    cogni_content = cogni_path.read_bytes()
    await push_file(
        token,
        owner,
        repo_name,
        f"dist/{slug}.cogni",
        cogni_content,
        f"Add {slug} v{plugin.get('latest_version', '1.0.0')}",
    )

    # 7. Push README
    readme = f"""# {plugin['name']}

{plugin.get('description', '')}

## Install

Download from [CogniCraft Store]({repo_url}).

## Author

{plugin.get('author', '')}

## Version

v{plugin.get('latest_version', '1.0.0')}

---

Synced from CogniCraft Store
"""
    await push_file(
        token,
        owner,
        repo_name,
        "README.md",
        readme.encode(),
        "Add README",
    )

    # 8. Save repo URL to DB
    db.execute(
        "UPDATE public.users SET github_repo_url = %s WHERE id = %s",
        (repo_url, user["sub"]),
    )

    return {
        "success": True,
        "message": f"Đã sync {plugin['name']} lên GitHub",
        "repo_url": repo_url,
        "repo_name": repo_name,
        "owner": owner,
    }


# ============================================================
# GET /github/status/{slug} — Check sync status
# ============================================================
@router.get("/status/{slug}")
async def sync_status(
    slug: str,
    user: dict = Depends(get_current_user),
):
    """Check plugin đã sync chưa"""
    db = get_db()

    db_user = db.query_one(
        "SELECT github_username, github_repo_url FROM public.users WHERE id = %s",
        (user["sub"],),
    )

    return {
        "github_username": db_user.get("github_username") if db_user else None,
        "github_repo_url": db_user.get("github_repo_url") if db_user else None,
        "can_sync": bool(db_user and db_user.get("github_username")),
    }