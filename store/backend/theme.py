# store/backend/theme.py

import re
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from .database import get_db
from .auth import get_current_user

router = APIRouter()

# Max CSS size — 50KB
MAX_CSS_LENGTH = 50_000

# Patterns nguy hiểm cần block
DANGEROUS_PATTERNS = [
    r'@import',                    # Import external CSS
    r'javascript\s*:',             # JS protocol
    r'expression\s*\(',            # IE expression
    r'behavior\s*:',               # IE behavior
    r'<\s*script',                 # Script tag
    r'<\s*/\s*style',              # Close style tag  
    r'url\s*\(\s*[\'"]?\s*data:',  # Data URLs (có thể chứa JS)
]


# ============================================================
# MODELS
# ============================================================
class ThemeUpdateRequest(BaseModel):
    css_content: str


# ============================================================
# HELPERS
# ============================================================
def sanitize_css(css: str) -> str:
    """
    Làm sạch CSS — block các pattern nguy hiểm.
    Không dùng regex phức tạp vì dễ bị bypass.
    """
    if not css:
        return ""

    if len(css) > MAX_CSS_LENGTH:
        raise HTTPException(
            400, 
            f"CSS quá dài ({len(css)} ký tự). Tối đa {MAX_CSS_LENGTH}."
        )

    # Lowercase để check patterns
    lower = css.lower()

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, lower):
            raise HTTPException(
                400, 
                f"CSS chứa pattern không được phép: {pattern}"
            )

    return css


# ============================================================
# GET /api/theme/me
# ============================================================
@router.get("/me")
async def get_my_theme(user: dict = Depends(get_current_user)):
    """Lấy theme hiện tại của user"""
    db = get_db()

    row = db.query_one(
        "SELECT css_content, is_active, updated_at FROM user_themes WHERE user_id = %s",
        (user["sub"],),
    )

    if not row:
        return {
            "css_content": "",
            "is_active": False,
            "updated_at": None,
            "has_theme": False,
        }

    return {
        "css_content": row.get("css_content", ""),
        "is_active": row.get("is_active", False),
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
        "has_theme": bool(row.get("css_content")),
    }


# ============================================================
# PUT /api/theme/me
# ============================================================
@router.put("/me")
async def save_my_theme(
    req: ThemeUpdateRequest,
    user: dict = Depends(get_current_user),
):
    """Save CSS theme — tự động bật is_active = TRUE"""
    db = get_db()

    clean_css = sanitize_css(req.css_content or "")

    db.execute(
        """
        INSERT INTO user_themes (user_id, css_content, is_active, updated_at)
        VALUES (%s, %s, TRUE, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET css_content = %s,
            is_active = TRUE,
            updated_at = NOW()
        """,
        (user["sub"], clean_css, clean_css),
    )

    return {
        "success": True,
        "message": "Đã lưu theme",
        "length": len(clean_css),
    }


# ============================================================
# POST /api/theme/me/toggle
# ============================================================
class ToggleRequest(BaseModel):
    is_active: bool


@router.post("/me/toggle")
async def toggle_my_theme(
    req: ToggleRequest,
    user: dict = Depends(get_current_user),
):
    """Bật/tắt theme mà không xóa CSS"""
    db = get_db()

    db.execute(
        """
        INSERT INTO user_themes (user_id, css_content, is_active, updated_at)
        VALUES (%s, '', %s, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET is_active = %s,
            updated_at = NOW()
        """,
        (user["sub"], req.is_active, req.is_active),
    )

    return {"success": True, "is_active": req.is_active}


# ============================================================
# DELETE /api/theme/me
# ============================================================
@router.delete("/me")
async def reset_my_theme(user: dict = Depends(get_current_user)):
    """Xóa theme — reset về mặc định"""
    db = get_db()

    db.execute(
        "DELETE FROM user_themes WHERE user_id = %s",
        (user["sub"],),
    )

    return {"success": True, "message": "Đã reset theme"}


# ============================================================
# GET /api/theme/preview/{user_id}
# Public endpoint — không cần auth
# Dùng cho trường hợp muốn xem theme của user khác
# ============================================================
@router.get("/preview/{user_id}")
async def preview_theme(user_id: str):
    """Xem CSS theme của user khác (public)"""
    db = get_db()

    row = db.query_one(
        """
        SELECT css_content, is_active 
        FROM user_themes 
        WHERE user_id = %s AND is_active = TRUE
        """,
        (user_id,),
    )

    if not row:
        return {"css_content": "", "is_active": False}

    return {
        "css_content": row.get("css_content", ""),
        "is_active": row.get("is_active", False),
    }