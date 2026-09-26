# store/backend/theme_marketplace.py
"""
Theme Marketplace v3 — with Pricing backend
- Free themes: apply trực tiếp
- Paid themes: yêu cầu mua trước (Phase 9 — payment coming Phase 7)
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


class PurchaseRequest(BaseModel):
    payment_method: Optional[str] = "payos"


# ============================================================
# POST /api/marketplace/themes — Publish
# ============================================================
@router.post("/themes")
async def publish_theme(
    req: PublishThemeRequest,
    user: dict = Depends(get_current_user),
):
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

    base_slug = slugify(req.name)
    slug = base_slug
    counter = 1
    while db.query_one("SELECT id FROM plugins WHERE slug = %s", (slug,)):
        slug = f"{base_slug}-{counter}"
        counter += 1
        if counter > 100:
            raise HTTPException(400, "Không tạo được slug, thử tên khác")

    tags = [t.strip().lower() for t in (req.tags or []) if t and t.strip()][:10]

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
            slug, req.name.strip(),
            (req.description or "")[:500],
            (req.long_description or "")[:5000],
            db_user.get("name") or "Anonymous",
            tags, clean_css,
            req.preview_image or "",
            db_user.get("avatar_url") or "",
            price, is_paid,
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

    total_row = db.query_one(f"SELECT COUNT(*) AS c FROM plugins WHERE {where}", tuple(params))
    total = total_row["c"] if total_row else 0

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
# 🆕 CHECK PURCHASE — user đã mua theme chưa?
# ============================================================
@router.get("/themes/{slug}/check-purchase")
async def check_purchase(
    slug: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    user_id = user["sub"]

    theme = db.query_one(
        "SELECT is_paid, price_vnd, author, slug FROM plugins WHERE slug = %s AND type = 'theme'",
        (slug,),
    )
    if not theme:
        raise HTTPException(404, "Theme không tồn tại")

    # Nếu FREE → không cần mua
    if not theme.get("is_paid"):
        return {"owned": True, "is_paid": False, "reason": "free"}

    # Kiểm tra user có phải author không
    db_user = db.query_one("SELECT name FROM public.users WHERE id = %s", (user_id,))
    if db_user and theme.get("author") == db_user.get("name"):
        return {"owned": True, "is_paid": True, "reason": "owner"}

    # Check đã mua chưa
    order = db.query_one(
        """
        SELECT id, status FROM orders 
        WHERE user_id = %s AND theme_slug = %s AND status = 'paid'
        LIMIT 1
        """,
        (user_id, slug),
    )

    if order:
        return {"owned": True, "is_paid": True, "reason": "purchased", "order_id": str(order["id"])}

    return {"owned": False, "is_paid": True, "price_vnd": theme["price_vnd"]}


# ============================================================
# 🆕 PURCHASE — tạo order
# ============================================================
@router.post("/themes/{slug}/purchase")
async def purchase_theme(
    slug: str,
    req: PurchaseRequest,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    user_id = user["sub"]

    theme = db.query_one(
        "SELECT is_paid, price_vnd, author, name FROM plugins WHERE slug = %s AND type = 'theme'",
        (slug,),
    )
    if not theme:
        raise HTTPException(404, "Theme không tồn tại")

    if not theme.get("is_paid"):
        raise HTTPException(400, "Theme này miễn phí — không cần mua")

    # Không tự mua theme của chính mình
    db_user = db.query_one("SELECT name FROM public.users WHERE id = %s", (user_id,))
    if db_user and theme.get("author") == db_user.get("name"):
        raise HTTPException(400, "Bạn là tác giả — không cần mua")

    # Check đã có order chưa
    existing = db.query_one(
        """
        SELECT id, status FROM orders 
        WHERE user_id = %s AND theme_slug = %s
        ORDER BY created_at DESC LIMIT 1
        """,
        (user_id, slug),
    )

    if existing and existing["status"] == "paid":
        return {
            "success": True,
            "message": "Bạn đã mua theme này rồi",
            "order_id": str(existing["id"]),
            "already_paid": True,
        }

    # Tạo order mới (pending)
    result = db.execute_returning(
        """
        INSERT INTO orders (user_id, theme_slug, amount_vnd, status, payment_method)
        VALUES (%s, %s, %s, 'pending', %s)
        RETURNING id
        """,
        (user_id, slug, theme["price_vnd"], req.payment_method or "payos"),
    )

    return {
        "success": True,
        "order_id": str(result["id"]),
        "amount_vnd": theme["price_vnd"],
        "theme_name": theme["name"],
        "status": "pending",
        "payment_method": req.payment_method or "payos",
        "message": "Order đã tạo — thanh toán sẽ available sớm (Phase 7)",
    }


# ============================================================
# 🆕 MY PURCHASES — list theme đã mua
# ============================================================
@router.get("/my-purchases")
async def my_purchases(user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = user["sub"]

    rows = db.query(
        """
        SELECT 
            o.id AS order_id, o.theme_slug, o.amount_vnd, o.status, 
            o.created_at, o.paid_at,
            p.name AS theme_name, p.preview_image, p.author
        FROM orders o
        LEFT JOIN plugins p ON p.slug = o.theme_slug AND p.type = 'theme'
        WHERE o.user_id = %s
        ORDER BY o.created_at DESC
        LIMIT 50
        """,
        (user_id,),
    )

    for r in rows:
        r["order_id"] = str(r["order_id"])
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
        if r.get("paid_at"):
            r["paid_at"] = r["paid_at"].isoformat()

    return {"purchases": rows, "total": len(rows)}


# ============================================================
# APPLY — check pricing trước khi apply
# ============================================================
@router.post("/themes/{slug}/apply")
async def apply_theme(
    slug: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()

    theme = db.query_one(
        "SELECT css_content, is_paid, price_vnd, author FROM plugins WHERE slug = %s AND type = 'theme'",
        (slug,),
    )
    if not theme:
        raise HTTPException(404, "Theme không tồn tại")

    user_id = user["sub"]

    # Nếu PAID theme → check ownership
    if theme.get("is_paid"):
        # Author → bỏ qua check
        db_user = db.query_one("SELECT name FROM public.users WHERE id = %s", (user_id,))
        is_owner = db_user and theme.get("author") == db_user.get("name")

        if not is_owner:
            # Check đã mua
            order = db.query_one(
                """
                SELECT id FROM orders 
                WHERE user_id = %s AND theme_slug = %s AND status = 'paid'
                LIMIT 1
                """,
                (user_id, slug),
            )

            if not order:
                raise HTTPException(
                    402,
                    f"Theme trả phí {theme['price_vnd']}đ. Vui lòng mua trước khi áp dụng."
                )

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
# LIKE
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
# TAGS
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
# AUTHORS
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
# DELETE
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

    db_user = db.query_one("SELECT name FROM public.users WHERE id = %s", (user["sub"],))
    if not db_user or theme["author"] != db_user["name"]:
        raise HTTPException(403, "Bạn không có quyền xóa theme này")

    db.execute("DELETE FROM plugins WHERE slug = %s AND type = 'theme'", (slug,))

    return {"success": True, "message": "Đã xóa theme"}