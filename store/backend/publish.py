# store/backend/publish.py
"""
Publish API — upload .cogni packages lên Store
Endpoints:
- POST /api/store/publish          upload plugin mới
- POST /api/store/publish/version  upload version mới cho plugin đã có
- GET  /api/store/download/{slug}  download .cogni
"""
import sys
import json
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Add path để import cogni_package
# - Local: parent.parent.parent = root project
# - Deploy (store = root): parent.parent = /app
_root = Path(__file__).parent.parent.parent.resolve()
if not (_root / "cogni_package").exists():
    # Fallback cho Railway: cogni_package đã copy vào store/
    _root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(_root))

from cogni_package.manifest import (
    CogniManifest,
    validate_manifest,
    ManifestError,
)
from .database import get_db


router = APIRouter()


# ============================================================
# CONFIG
# ============================================================
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXT = {".cogni"}

# MVP: simple token auth. Production: JWT / OAuth
PUBLISH_TOKEN = "cognicraft-dev-token-2026"


# ============================================================
# SCHEMAS
# ============================================================
class PublishResponse(BaseModel):
    success: bool
    slug: str
    version: str
    message: str
    download_url: str


# ============================================================
# HELPERS
# ============================================================
def _check_auth(authorization: Optional[str]) -> str:
    """Simple token auth — trả về author name nếu OK"""
    if not authorization:
        raise HTTPException(401, "Missing Authorization header")

    # Format: "Bearer <token>:<author>"
    parts = authorization.replace("Bearer ", "").split(":", 1)
    if len(parts) != 2:
        raise HTTPException(401, "Invalid Authorization format. Use: Bearer <token>:<author>")

    token, author = parts
    if token != PUBLISH_TOKEN:
        raise HTTPException(403, "Invalid publish token")

    return author


def _compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_manifest_from_cogni(cogni_path: Path) -> CogniManifest:
    """Đọc manifest.json từ trong file .cogni"""
    import zipfile
    try:
        with zipfile.ZipFile(cogni_path, "r") as zf:
            if "manifest.json" not in zf.namelist():
                raise HTTPException(400, "Package thiếu manifest.json")
            raw = zf.read("manifest.json")
            data = json.loads(raw)
            return CogniManifest.from_dict(data)
    except zipfile.BadZipFile:
        raise HTTPException(400, "File không phải .cogni hợp lệ (zip corrupt)")


async def _save_upload(file: UploadFile) -> Path:
    """Lưu file upload vào temp, kiểm tra size"""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Chỉ chấp nhận file {ALLOWED_EXT}")

    # Save to temp
    tmp_path = UPLOAD_DIR / f".tmp-{datetime.now().timestamp()}-{file.filename}"
    size = 0

    with open(tmp_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                f.close()
                tmp_path.unlink(missing_ok=True)
                raise HTTPException(413, f"File quá lớn (max {MAX_FILE_SIZE // 1024 // 1024} MB)")
            f.write(chunk)

    return tmp_path


# ============================================================
# POST /publish — Upload plugin mới
# ============================================================
@router.post("/publish", response_model=PublishResponse)
async def publish_plugin(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # comma-separated
    authorization: Optional[str] = Header(None),
):
    """
    Upload plugin .cogni lên Store

    Headers:
        Authorization: Bearer <token>:<author>

    Form:
        file: file.cogni
        category: tools (optional, override manifest)
        tags: tag1,tag2 (optional)
    """
    author = _check_auth(authorization)

    # 1. Save file
    tmp = await _save_upload(file)

    try:
        # 2. Read manifest
        manifest = _read_manifest_from_cogni(tmp)

        # 3. Validate
        errors = validate_manifest(manifest)
        if errors:
            raise HTTPException(400, "Manifest không hợp lệ:\n  - " + "\n  - ".join(errors))

        # Override author từ auth (tránh giả mạo)
        manifest.author = author

        # 4. Check duplicate
        db = get_db()
        existing = db.query_one(
            "SELECT id FROM plugins WHERE slug = %s",
            (manifest.id,),
        )

        if existing:
            raise HTTPException(
                409,
                f"Plugin '{manifest.id}' đã tồn tại. "
                "Dùng /publish/version để upload version mới."
            )

        # 5. Upload to Supabase Storage
        from .storage import upload_file

        final_name = f"{manifest.id}-{manifest.version}.cogni"
        file_bytes = tmp.read_bytes()

        ok = await upload_file(file_bytes, final_name, "application/zip")
        if not ok:
            tmp.unlink(missing_ok=True)
            raise HTTPException(500, "Upload lên Supabase Storage thất bại")

        # 6. Compute checksum
        checksum = _compute_sha256(tmp)
        file_size = len(file_bytes)

        # Xóa file tmp
        tmp.unlink(missing_ok=True)

        # 7. Insert DB
        plugin_row = db.execute_returning(
            """
            INSERT INTO plugins (
                slug, name, description, long_description, author,
                category, tags, icon, homepage, repository, license,
                latest_version, downloads, installs, rating, review_count,
                verified, featured, created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, 0, 0, 0, 0,
                FALSE, FALSE, NOW()
            ) RETURNING id, slug, name, latest_version
            """,
            (
                manifest.id,
                manifest.name,
                manifest.description,
                manifest.long_description,
                manifest.author,
                category or manifest.category,
                tags.split(",") if tags else manifest.tags,
                manifest.icon,
                manifest.homepage,
                manifest.repository,
                manifest.license,
                manifest.version,
            ),
        )

        plugin_id = plugin_row["id"]

        # 8. Insert plugin_version
        db.execute(
            """
            INSERT INTO plugin_versions (
                plugin_id, version, changelog, file_url,
                file_size, file_hash, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                plugin_id,
                manifest.version,
                manifest.changelog,
                final_name,
                file_size,
                checksum,
            ),
        )

        return PublishResponse(
            success=True,
            slug=manifest.id,
            version=manifest.version,
            message=f"✅ Đã publish {manifest.name} v{manifest.version}",
            download_url=f"/api/store/download/{manifest.id}",
        )

    except HTTPException:
        tmp.unlink(missing_ok=True)
        raise
    except Exception as e:
        tmp.unlink(missing_ok=True)
        raise HTTPException(500, f"Publish failed: {str(e)}")


# ============================================================
# POST /publish/version — Upload version mới
# ============================================================
@router.post("/publish/version", response_model=PublishResponse)
async def publish_version(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Upload version mới cho plugin đã tồn tại"""
    author = _check_auth(authorization)

    tmp = await _save_upload(file)

    try:
        manifest = _read_manifest_from_cogni(tmp)
        errors = validate_manifest(manifest)
        if errors:
            raise HTTPException(400, "Manifest lỗi:\n  - " + "\n  - ".join(errors))

        db = get_db()
        plugin = db.query_one(
            "SELECT id, author FROM plugins WHERE slug = %s",
            (manifest.id,),
        )
        if not plugin:
            raise HTTPException(404, f"Plugin '{manifest.id}' chưa tồn tại. Dùng /publish trước.")

        if plugin["author"] != author:
            raise HTTPException(403, "Bạn không phải tác giả plugin này")

        # Check version chưa tồn tại
        dup = db.query_one(
            "SELECT id FROM plugin_versions WHERE plugin_id = %s AND version = %s",
            (plugin["id"], manifest.version),
        )
        if dup:
            raise HTTPException(409, f"Version {manifest.version} đã tồn tại")

        # Upload to Supabase Storage
        from .storage import upload_file

        final_name = f"{manifest.id}-{manifest.version}.cogni"
        file_bytes = tmp.read_bytes()

        ok = await upload_file(file_bytes, final_name, "application/zip")
        if not ok:
            tmp.unlink(missing_ok=True)
            raise HTTPException(500, "Upload lên Supabase Storage thất bại")

        checksum = _compute_sha256(tmp)
        file_size = len(file_bytes)

        tmp.unlink(missing_ok=True)

        # Insert version
        db.execute(
            """
            INSERT INTO plugin_versions (
                plugin_id, version, changelog, file_url,
                file_size, file_hash, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                plugin["id"],
                manifest.version,
                manifest.changelog,
                final_name,
                file_size,
                checksum,
            ),
        )

        # Update latest_version
        db.execute(
            "UPDATE plugins SET latest_version = %s WHERE id = %s",
            (manifest.version, plugin["id"]),
        )

        return PublishResponse(
            success=True,
            slug=manifest.id,
            version=manifest.version,
            message=f"✅ Đã publish version {manifest.version}",
            download_url=f"/api/store/download/{manifest.id}",
        )

    except HTTPException:
        tmp.unlink(missing_ok=True)
        raise
    except Exception as e:
        tmp.unlink(missing_ok=True)
        raise HTTPException(500, f"Publish version failed: {str(e)}")


# ============================================================
# GET /download/{slug} — Download .cogni
# ============================================================
@router.get("/download/{slug}")
async def download_plugin(slug: str, version: Optional[str] = None):
    """
    Download .cogni của plugin

    Query:
        version: version cụ thể (default: latest)
    """
    db = get_db()

    plugin = db.query_one(
        "SELECT id, slug, name, latest_version FROM plugins WHERE slug = %s",
        (slug,),
    )
    if not plugin:
        raise HTTPException(404, f"Plugin '{slug}' không tồn tại")

    target_version = version or plugin["latest_version"]

    pv = db.query_one(
        """
        SELECT version, file_url, file_hash
        FROM plugin_versions
        WHERE plugin_id = %s AND version = %s
        """,
        (plugin["id"], target_version),
    )
    if not pv:
        raise HTTPException(404, f"Version '{target_version}' không tồn tại")

    file_path = UPLOAD_DIR / pv["file_url"]
    if not file_path.exists():
        raise HTTPException(500, "File vật lý bị mất — cần re-upload")

    # Increment downloads
    db.execute(
        "UPDATE plugins SET downloads = downloads + 1 WHERE id = %s",
        (plugin["id"],),
    )

    return FileResponse(
        path=str(file_path),
        media_type="application/zip",
        filename=f"{slug}-{target_version}.cogni",
    )