# store/backend/theme_marketplace.py
"""
Theme Marketplace (v2 — merged into plugins table)
- Themes là plugins có type='theme'
- Query chung bảng plugins với type='theme'
- Hỗ trợ free + paid (price_vnd)
"""
import re
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from .database import get_db
from .auth import get_current_user

router = APIRouter()

MAX_CSS_LENGTH = 50_000

DANGEROUS_PATTERNS = [
    r'@import',
    r'javascript\s*:',
    r'expression\s*\(',
    r'behavior\s*:',
    r'<\s*script',
    r'<\s*/\s*style',
    r'url\s*\(\s*[\'"]?\s*data:',
]


# ============================================================
# HELPERS
# ============================================================
def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def sanitize_css(css: str) -> str:
    if not css:
        raise HTTPException(400, "CSS không được rỗng")
    if len(css) > MAX_CSS_LENGTH:
        raise HTTPException(400, f"CSS quá dài. Tối đa {MAX_CSS_LENGTH} ký tự")
    lower = css.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, lower):
            raise HTTPException(400, f"CSS chứa pattern không được phép: {pattern}")
    return css


# ============================================================
# MODELS
# ============================================================
class PublishThemeRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    long_description: Optional[str] = ""
    preview_image: Optional[str] = ""
    css_content: str
    tags: Optional[List[str]] = []
    price_vnd: Optional[int] = 0


# ============================================================
# POST /api/marketplace/themes — Publish
# ============================================================
@router.post("/themes")
async def publish_theme(
    req: PublishThemeRequest,
    user: dict = Depends(get_current_user),
):
    """Publish theme lên marketplace (insert vào plugins với type='theme')"""
    db = get_db()
    user_id = user["sub"]

    db_user = db.query_one(
        "SELECT name, avatar_url FROM public.users WHERE id = %s",
        (user_id,),
    )
    if not db_user:
        raise HTTPException(404, "User không tồn tại")

    clean_css = sanitize_css(req.css_content)
    if not req.name or len(req.name.strip()) < 3:
        raise HTTPException(400, "Tên theme phải có ít nhất 3 ký tự")

    # Generate unique slug
    base_slug = slugify(req.name)
    slug = base_slug
    counter = 1
    while db.query_one("SELECT id FROM plugins WHERE slug = %s", (slug,)):
        slug = f"{base_slug}-{counter}"
        counter += 1
        if counter > 100:
            raise HTTPException(400, "Không tạo được slug, thử tên khác")

    tags = [t.strip().lower() for t in (req.tags or []) if t and t.strip()][:10]

    # Price logic
    price = max(0, int(req.price_vnd or 0))
    is_paid = price > 0

    result = db.execute_returning(
        """
        INSERT INTO plugins (
            slug, name, description, long_description,
            author, category, tags, icon,
            latest_version, type, css_content,
            preview_image, author_avatar,
            downloads, likes, rating, review_count,
            verified, featured, price_vnd, is_paid
        ) VALUES (
            %s, %s, %s, %s,
            %s, 'themes', %s, '🎨',
            '1.0.0', 'theme', %s,
            %s, %s,
            0, 0, 0, 0,
            FALSE, FALSE, %s, %s
        )
        RETURNING id, slug
        """,
        (
            slug,
            req.name.strip(),
            (req.description or "")[:500],
            (req.long_description or "")[:5000],
            db_user.get("name") or "Anonymous",
            tags,
            clean_css,
            req.preview_image or "",
            db_user.get("avatar_url") or "",
            price,
            is_paid,
        ),
    )

    return {
        "success": True,
        "id": str(result["id"]),
        "slug": result["slug"],
        "is_paid": is_paid,
        "price_vnd": price,
        "message": "Đã publish theme lên marketplace",
    }


# ============================================================
# GET /api/marketplace/themes — List
# ============================================================
@router.get("/themes")
async def list_themes(
    search: Optional[str] = None,
    tag: Optional[str] = None,
    author: Optional[str] = None,
    sort: str = Query("downloads", pattern="^(downloads|likes|rating|created_at|trending|price_asc|price_desc)$"),
    featured: Optional[bool] = None,
    price_type: Optional[str] = Query(None, pattern="^(free|paid)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
):
    """List themes (từ bảng plugins với type='theme')"""
    db = get_db()

    conditions = ["type = 'theme'"]
    params = []

    if search:
        conditions.append(
            "(name ILIKE %s OR description ILIKE %s OR author ILIKE %s OR %s = ANY(tags))"
        )
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern, search.lower()])

    if tag:
        conditions.append("%s = ANY(tags)")
        params.append(tag.lower())

    if author:
        conditions.append("author ILIKE %s")
        params.append(f"%{author}%")

    if featured is not None:
        conditions.append("featured = %s")
        params.append(featured)

    if price_type == "free":
        conditions.append("(is_paid = FALSE OR price_vnd = 0)")
    elif price_type == "paid":
        conditions.append("(is_paid = TRUE AND price_vnd > 0)")

    where = " AND ".join(conditions)

    # Count
    total_row = db.query_one(f"SELECT COUNT(*) AS c FROM plugins WHERE {where}", tuple(params))
    total = total_row["c"] if total_row else 0

    # Order
    order_map = {
        "downloads": "downloads DESC",
        "likes": "likes DESC",
        "rating": "rating DESC NULLS LAST",
        "created_at": "created_at DESC",
        "trending": "(downloads * 0.6 + likes * 2 + COALESCE(rating, 0) * 10) DESC",
        "price_asc": "price_vnd ASC",
        "price_desc": "price_vnd DESC",
    }
    order_clause = order_map.get(sort, "downloads DESC")
    offset = (page - 1) * per_page

    rows = db.query(
        f"""
        SELECT 
            id, slug, name, description, preview_image,
            author AS author_name, author_avatar, tags,
            downloads, likes, rating, review_count,
            featured, verified, created_at,
            price_vnd, is_paid
        FROM plugins
        WHERE {where}
        ORDER BY {order_clause}
        LIMIT %s OFFSET %s
        """,
        tuple(params + [per_page, offset]),
    )

    for r in rows:
        r["id"] = str(r["id"])
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "themes": rows,
    }


# ============================================================
# GET /api/marketplace/themes/{slug} — Detail
# ============================================================
@router.get("/themes/{slug}")
async def get_theme(slug: str):
    db = get_db()

    row = db.query_one(
        """
        SELECT 
            id, slug, name, description, long_description,
            preview_image, css_content, tags,
            author AS author_name, author_avatar,
            downloads, likes, rating, review_count,
            featured, verified, created_at, updated_at,
            price_vnd, is_paid
        FROM plugins
        WHERE slug = %s AND type = 'theme'
        """,
        (slug,),
    )

    if not row:
        raise HTTPException(404, "Theme không tồn tại")

    row["id"] = str(row["id"])
    if row.get("created_at"):
        row["created_at"] = row["created_at"].isoformat()
    if row.get("updated_at"):
        row["updated_at"] = row["updated_at"].isoformat()

    # Themes khác của cùng author
    other_themes = db.query(
        """
        SELECT slug, name, preview_image, downloads, price_vnd, is_paid
        FROM plugins
        WHERE author = %s AND slug != %s AND type = 'theme'
        ORDER BY downloads DESC
        LIMIT 6
        """,
        (row["author_name"], slug),
    )

    return {
        "theme": row,
        "other_themes": other_themes,
    }


# ============================================================
# POST /api/marketplace/themes/{slug}/apply — Apply (chỉ free)
# ============================================================
@router.post("/themes/{slug}/apply")
async def apply_theme(
    slug: str,
    user: dict = Depends(get_current_user),
):
    """Copy CSS vào user_themes — CHẶN nếu là paid theme (chưa thanh toán)"""
    db = get_db()

    theme = db.query_one(
        "SELECT css_content, is_paid, price_vnd FROM plugins WHERE slug = %s AND type = 'theme'",
        (slug,),
    )
    if not theme:
        raise HTTPException(404, "Theme không tồn tại")

    # Chưa có payment system → chỉ cho free
    if theme.get("is_paid"):
        raise HTTPException(
            402,
            f"Theme trả phí ({theme['price_vnd']}đ). Tính năng thanh toán đang phát triển."
        )

    user_id = user["sub"]
    css_content = theme["css_content"]

    db.execute(
        """
        INSERT INTO user_themes (user_id, css_content, is_active, updated_at)
        VALUES (%s, %s, TRUE, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET css_content = %s, is_active = TRUE, updated_at = NOW()
        """,
        (user_id, css_content, css_content),
    )

    db.execute(
        "UPDATE plugins SET downloads = downloads + 1 WHERE slug = %s AND type = 'theme'",
        (slug,),
    )

    return {
        "success": True,
        "message": "Đã apply theme. Reload trang để thấy hiệu ứng.",
    }


# ============================================================
# POST /api/marketplace/themes/{slug}/like
# ============================================================
@router.post("/themes/{slug}/like")
async def like_theme(slug: str, user: dict = Depends(get_current_user)):
    db = get_db()

    result = db.execute_returning(
        """
        UPDATE plugins
        SET likes = likes + 1
        WHERE slug = %s AND type = 'theme'
        RETURNING likes
        """,
        (slug,),
    )

    if not result:
        raise HTTPException(404, "Theme không tồn tại")

    return {"success": True, "likes": result["likes"]}


# ============================================================
# GET /api/marketplace/tags
# ============================================================
@router.get("/tags")
async def popular_tags(limit: int = 20):
    db = get_db()

    rows = db.query(
        """
        SELECT tag, COUNT(*) AS count
        FROM (
            SELECT unnest(tags) AS tag FROM plugins WHERE type = 'theme'
        ) sub
        GROUP BY tag
        ORDER BY count DESC
        LIMIT %s
        """,
        (limit,),
    )

    return {"tags": rows}


# ============================================================
# GET /api/marketplace/authors/{name}
# ============================================================
@router.get("/authors/{name}")
async def author_themes(name: str):
    db = get_db()

    rows = db.query(
        """
        SELECT 
            id, slug, name, description, preview_image,
            author AS author_name, author_avatar, tags,
            downloads, likes, rating, review_count, created_at,
            price_vnd, is_paid
        FROM plugins
        WHERE author ILIKE %s AND type = 'theme'
        ORDER BY downloads DESC
        """,
        (f"%{name}%",),
    )

    for r in rows:
        r["id"] = str(r["id"])
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()

    total_downloads = sum(r.get("downloads") or 0 for r in rows)
    total_likes = sum(r.get("likes") or 0 for r in rows)

    return {
        "author_name": name,
        "themes": rows,
        "stats": {
            "total_themes": len(rows),
            "total_downloads": total_downloads,
            "total_likes": total_likes,
        },
    }


# ============================================================
# DELETE /api/marketplace/themes/{slug}
# ============================================================
@router.delete("/themes/{slug}")
async def delete_theme(slug: str, user: dict = Depends(get_current_user)):
    db = get_db()

    theme = db.query_one(
        "SELECT author FROM plugins WHERE slug = %s AND type = 'theme'",
        (slug,),
    )
    if not theme:
        raise HTTPException(404, "Theme không tồn tại")

    # Get current user name
    db_user = db.query_one("SELECT name FROM public.users WHERE id = %s", (user["sub"],))
    if not db_user or theme["author"] != db_user["name"]:
        raise HTTPException(403, "Bạn không có quyền xóa theme này")

    db.execute("DELETE FROM plugins WHERE slug = %s AND type = 'theme'", (slug,))

    return {"success": True, "message": "Đã xóa theme"}