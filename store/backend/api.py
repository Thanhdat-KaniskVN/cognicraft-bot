# store/backend/api.py
"""
Store API - FastAPI routes (v3.0 - Plugin + Theme unified)
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional, List
import re

from .database import get_db
from .models import (
    PluginUpload,
    PluginResponse,
    ReviewSubmit,
    PluginListResponse,
)


router = APIRouter()


# ============================================================
# HELPERS
# ============================================================

def _slugify(text: str) -> str:
    """Convert text to slug"""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')


# ============================================================
# LIST PLUGINS — Advanced search + filter (v3.0)
# ============================================================

@router.get("/plugins", response_model=PluginListResponse)
async def list_plugins(
    category: Optional[str] = None,
    search: Optional[str] = None,
    author: Optional[str] = None,
    tag: Optional[str] = None,
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    price_type: Optional[str] = Query(None, pattern="^(free|paid|freemium)$"),
    featured: Optional[bool] = None,
    type_filter: Optional[str] = Query(None, alias="type", pattern="^(plugin|theme|all)$"),
    sort: str = Query("downloads", pattern="^(downloads|rating|created_at|name|trending)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    List plugins/themes với ADVANCED filter + search + pagination

    Query params:
    - type: plugin | theme | all (default: chỉ plugin)
    - category, search, author, tag, min_rating, featured
    - price_type: free | paid
    - sort, page, per_page
    """
    db = get_db()

    conditions = []
    params = []

    # ⭐ TYPE FILTER — mặc định chỉ plugin
    if type_filter == "all":
        pass  # không filter type
    elif type_filter == "theme":
        conditions.append("type = %s")
        params.append("theme")
    else:
        # Default: chỉ plugin (không lẫn theme)
        conditions.append("type = %s")
        params.append("plugin")

    if category:
        conditions.append("category = %s")
        params.append(category)

    if search:
        conditions.append(
            "(name ILIKE %s OR description ILIKE %s OR author ILIKE %s OR %s = ANY(tags))"
        )
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern, search_pattern, search.lower()])

    if author:
        conditions.append("author ILIKE %s")
        params.append(f"%{author}%")

    if tag:
        conditions.append("%s = ANY(tags)")
        params.append(tag.lower())

    if min_rating is not None:
        conditions.append("rating >= %s")
        params.append(min_rating)

    if featured is not None:
        conditions.append("featured = %s")
        params.append(featured)

    # Price filter — dùng cột is_paid (theme) hoặc price_vnd
    if price_type == "free":
        conditions.append("(is_paid = FALSE OR is_paid IS NULL OR price_vnd = 0 OR price_vnd IS NULL)")
    elif price_type == "paid":
        conditions.append("(is_paid = TRUE AND price_vnd > 0)")

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Count total
    count_sql = f"SELECT COUNT(*) as total FROM plugins {where_clause}"
    total_row = db.query_one(count_sql, tuple(params))
    total = total_row["total"] if total_row else 0

    # Order clause
    offset = (page - 1) * per_page
    order_map = {
        "downloads": "downloads DESC",
        "rating": "rating DESC NULLS LAST",
        "created_at": "created_at DESC",
        "name": "name ASC",
        "trending": "(downloads * 0.7 + COALESCE(rating, 0) * 100 * 0.3) DESC",
    }
    order_clause = order_map.get(sort, "downloads DESC")

    sql = f"""
        SELECT * FROM plugins
        {where_clause}
        ORDER BY {order_clause}
        LIMIT %s OFFSET %s
    """
    params.extend([per_page, offset])

    plugins = db.query(sql, tuple(params))

    for p in plugins:
        if p.get("created_at"):
            p["created_at"] = p["created_at"].isoformat()
        if p.get("updated_at"):
            p["updated_at"] = p["updated_at"].isoformat()

        # Check file .cogni (chỉ plugin mới có)
        if p.get("type") == "theme":
            p["has_file"] = False
        else:
            version_row = db.query_one(
                "SELECT file_url FROM plugin_versions WHERE plugin_id = %s AND file_url IS NOT NULL LIMIT 1",
                (p["id"],),
            )
            p["has_file"] = bool(version_row and version_row.get("file_url"))

    return {
        "total": total,
        "plugins": plugins,
        "page": page,
        "per_page": per_page,
    }


# ============================================================
# SEARCH SUGGESTIONS
# ============================================================

@router.get("/search/suggest")
async def search_suggest(q: str = Query(..., min_length=1), limit: int = 8):
    """Autocomplete suggestions"""
    db = get_db()

    suggestions = []

    # Plugins + themes
    plugins = db.query(
        "SELECT name, slug, icon, type FROM plugins WHERE name ILIKE %s LIMIT %s",
        (f"%{q}%", limit),
    )
    for p in plugins:
        suggestions.append({
            "type": p.get("type") or "plugin",
            "text": p["name"],
            "slug": p["slug"],
            "icon": p.get("icon", "📦"),
        })

    # Authors
    authors = db.query(
        "SELECT DISTINCT author FROM plugins WHERE author ILIKE %s LIMIT %s",
        (f"%{q}%", 3),
    )
    for a in authors:
        suggestions.append({
            "type": "author",
            "text": a["author"],
            "icon": "👤",
        })

    # Tags
    tags_rows = db.query(
        """
        SELECT DISTINCT unnest(tags) as tag 
        FROM plugins 
        WHERE EXISTS (
            SELECT 1 FROM unnest(tags) t WHERE t ILIKE %s
        )
        LIMIT 5
        """,
        (f"%{q}%",),
    )
    for t in tags_rows:
        suggestions.append({
            "type": "tag",
            "text": t["tag"],
            "icon": "🏷️",
        })

    return {"suggestions": suggestions[:limit]}


# ============================================================
# POPULAR TAGS
# ============================================================

@router.get("/tags")
async def list_tags(limit: int = 20):
    """List popular tags"""
    db = get_db()

    rows = db.query(
        """
        SELECT tag, COUNT(*) as count
        FROM (
            SELECT unnest(tags) as tag FROM plugins
        ) sub
        GROUP BY tag
        ORDER BY count DESC
        LIMIT %s
        """,
        (limit,),
    )

    return {"tags": rows}


# ============================================================
# GET PLUGIN / THEME DETAIL
# ============================================================

@router.get("/plugins/{slug}")
async def get_plugin(slug: str):
    """Get plugin/theme detail với versions + reviews"""
    db = get_db()

    plugin = db.query_one("SELECT * FROM plugins WHERE slug = %s", (slug,))
    if not plugin:
        raise HTTPException(404, f"Không tồn tại: {slug}")

    if plugin.get("created_at"):
        plugin["created_at"] = plugin["created_at"].isoformat()
    if plugin.get("updated_at"):
        plugin["updated_at"] = plugin["updated_at"].isoformat()

    # Versions (chỉ plugin mới có)
    if plugin.get("type") == "theme":
        versions = []
    else:
        versions = db.query(
            """SELECT version, changelog, created_at, file_size, downloads 
               FROM plugin_versions WHERE plugin_id = %s ORDER BY created_at DESC""",
            (plugin["id"],),
        )
        for v in versions:
            if v.get("created_at"):
                v["created_at"] = v["created_at"].isoformat()

    # Reviews
    reviews = db.query(
        """SELECT id, user_id, user_name, rating, comment, helpful_count, created_at 
           FROM reviews WHERE plugin_id = %s 
           ORDER BY helpful_count DESC, created_at DESC LIMIT 10""",
        (plugin["id"],),
    )
    for r in reviews:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()

    return {
        "plugin": plugin,
        "versions": versions,
        "reviews": reviews,
    }


# ============================================================
# UPLOAD PLUGIN
# ============================================================

@router.post("/upload")
async def upload_plugin(data: PluginUpload):
    """Upload plugin mới hoặc update version"""
    db = get_db()

    existing = db.query_one("SELECT id FROM plugins WHERE slug = %s", (data.slug,))

    if existing:
        db.execute(
            """
            UPDATE plugins SET
                name = %s, description = %s, long_description = %s,
                author = %s, category = %s, tags = %s, icon = %s,
                latest_version = %s, updated_at = NOW()
            WHERE slug = %s
            """,
            (
                data.name, data.description, data.long_description,
                data.author, data.category, data.tags, data.icon,
                data.version, data.slug,
            ),
        )
        plugin_id = existing["id"]
    else:
        result = db.execute_returning(
            """
            INSERT INTO plugins (
                slug, name, description, long_description,
                author, author_email, category, tags, icon,
                homepage, repository, license, latest_version, type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'plugin')
            RETURNING id
            """,
            (
                data.slug, data.name, data.description, data.long_description,
                data.author, data.author_email, data.category, data.tags, data.icon,
                data.homepage, data.repository, data.license, data.version,
            ),
        )
        plugin_id = result["id"]

    db.execute(
        """
        INSERT INTO plugin_versions (plugin_id, version, changelog, requirements, file_url, file_size)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (plugin_id, version) DO UPDATE SET
            changelog = EXCLUDED.changelog,
            file_url = EXCLUDED.file_url,
            file_size = EXCLUDED.file_size
        """,
        (plugin_id, data.version, data.changelog, data.requirements, data.file_url, data.file_size),
    )

    return {
        "success": True,
        "slug": data.slug,
        "version": data.version,
        "message": f"Plugin {data.name} v{data.version} đã upload!",
    }


# ============================================================
# INSTALL PLUGIN
# ============================================================

@router.post("/install/{slug}")
async def install_plugin(slug: str):
    """Track install + return download info"""
    db = get_db()

    plugin = db.query_one("SELECT id, name, latest_version FROM plugins WHERE slug = %s", (slug,))
    if not plugin:
        raise HTTPException(404, f"Không tồn tại: {slug}")

    db.execute(
        "UPDATE plugins SET installs = installs + 1, downloads = downloads + 1 WHERE id = %s",
        (plugin["id"],),
    )

    version = db.query_one(
        "SELECT file_url, file_size FROM plugin_versions WHERE plugin_id = %s AND version = %s",
        (plugin["id"], plugin["latest_version"]),
    )

    return {
        "success": True,
        "name": plugin["name"],
        "version": plugin["latest_version"],
        "download_url": version["file_url"] if version else None,
        "file_size": version["file_size"] if version else 0,
    }


# ============================================================
# REVIEWS
# ============================================================

@router.post("/reviews/{slug}")
async def submit_review(slug: str, review: ReviewSubmit):
    """Submit hoặc update đánh giá — tự động recompute rating"""
    db = get_db()

    plugin = db.query_one("SELECT id, name FROM plugins WHERE slug = %s", (slug,))
    if not plugin:
        raise HTTPException(404, f"'{slug}' không tồn tại")

    plugin_id = plugin["id"]

    existing = db.query_one(
        "SELECT id FROM reviews WHERE plugin_id = %s AND user_id = %s",
        (plugin_id, review.user_id),
    )

    if existing:
        db.execute(
            """
            UPDATE reviews 
            SET rating = %s, comment = %s, user_name = %s, created_at = NOW()
            WHERE id = %s
            """,
            (review.rating, review.comment or "", review.user_name, existing["id"]),
        )
        action = "updated"
    else:
        db.execute(
            """
            INSERT INTO reviews (plugin_id, user_id, user_name, rating, comment, helpful_count, created_at)
            VALUES (%s, %s, %s, %s, %s, 0, NOW())
            """,
            (plugin_id, review.user_id, review.user_name, review.rating, review.comment or ""),
        )
        action = "created"

    # Recompute rating
    stats = db.query_one(
        """
        SELECT 
            AVG(rating) as avg_rating,
            COUNT(*) as total
        FROM reviews
        WHERE plugin_id = %s
        """,
        (plugin_id,),
    )

    avg = 0.0
    total = 0
    if stats:
        avg = round(float(stats["avg_rating"] or 0), 1)
        total = int(stats["total"] or 0)
        db.execute(
            "UPDATE plugins SET rating = %s, review_count = %s WHERE id = %s",
            (avg, total, plugin_id),
        )

    return {
        "success": True,
        "action": action,
        "message": f"Đã {('cập nhật' if action == 'updated' else 'gửi')} đánh giá",
        "new_rating": avg,
        "total_reviews": total,
    }


@router.get("/reviews/{slug}")
async def get_reviews(slug: str, limit: int = 50, offset: int = 0):
    """Lấy danh sách reviews"""
    db = get_db()

    plugin = db.query_one("SELECT id FROM plugins WHERE slug = %s", (slug,))
    if not plugin:
        raise HTTPException(404, f"'{slug}' không tồn tại")

    reviews = db.query(
        """
        SELECT id, user_id, user_name, rating, comment, helpful_count, created_at
        FROM reviews
        WHERE plugin_id = %s
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        (plugin["id"], limit, offset),
    )

    for r in reviews:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()

    breakdown_rows = db.query(
        """
        SELECT rating, COUNT(*) as count
        FROM reviews
        WHERE plugin_id = %s
        GROUP BY rating
        ORDER BY rating DESC
        """,
        (plugin["id"],),
    )

    breakdown = {r["rating"]: r["count"] for r in breakdown_rows}

    return {
        "total": len(reviews),
        "reviews": reviews,
        "breakdown": breakdown,
    }


@router.post("/reviews/{review_id}/helpful")
async def mark_helpful(review_id: str):
    """Tăng helpful_count"""
    db = get_db()

    result = db.execute_returning(
        """
        UPDATE reviews
        SET helpful_count = helpful_count + 1
        WHERE id = %s
        RETURNING helpful_count
        """,
        (review_id,),
    )

    if not result:
        raise HTTPException(404, "Review không tồn tại")

    return {
        "success": True,
        "helpful_count": result["helpful_count"],
    }


# ============================================================
# CATEGORIES
# ============================================================

@router.get("/categories")
async def list_categories():
    """List all categories với count (chỉ đếm plugin, không đếm theme)"""
    db = get_db()

    db.execute("""
        UPDATE categories SET plugin_count = (
            SELECT COUNT(*) FROM plugins 
            WHERE category = categories.id AND type = 'plugin'
        )
    """)

    return {"categories": db.query("SELECT * FROM categories ORDER BY name")}


# ============================================================
# STATS
# ============================================================

@router.get("/stats")
async def get_stats():
    """Store statistics — tách plugin và theme"""
    db = get_db()

    total_plugins = db.query_one(
        "SELECT COUNT(*) as c FROM plugins WHERE type = 'plugin'"
    )["c"]

    total_themes = db.query_one(
        "SELECT COUNT(*) as c FROM plugins WHERE type = 'theme'"
    )["c"]

    categories = db.query_one(
        "SELECT COUNT(DISTINCT category) as c FROM plugins WHERE type = 'plugin'"
    )["c"]

    downloads = db.query_one(
        "SELECT SUM(downloads) as s FROM plugins WHERE type = 'plugin'"
    )["s"] or 0

    avg_rating = db.query_one(
        "SELECT AVG(rating) as a FROM plugins WHERE review_count > 0 AND type = 'plugin'"
    )["a"] or 0

    return {
        "total_plugins": total_plugins,
        "total_themes": total_themes,
        "categories": categories,
        "total_downloads": downloads,
        "avg_rating": round(float(avg_rating), 2),
    }


# ============================================================
# USER + AUTHOR PROFILES
# ============================================================

@router.get("/users/{username}")
async def get_user_profile(username: str):
    """Get user profile — reviews đã viết + stats"""
    db = get_db()

    user_id = username.lower().replace(" ", "_").replace("-", "_")

    reviews = db.query(
        """
        SELECT 
            r.id, r.user_name, r.rating, r.comment, r.helpful_count, r.created_at,
            p.slug AS plugin_slug, p.name AS plugin_name, p.icon AS plugin_icon, p.type AS item_type
        FROM reviews r
        JOIN plugins p ON p.id = r.plugin_id
        WHERE r.user_id = %s OR LOWER(REPLACE(r.user_name, ' ', '_')) = %s
        ORDER BY r.created_at DESC
        LIMIT 50
        """,
        (user_id, user_id),
    )

    for r in reviews:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()

    if not reviews:
        return {
            "username": username,
            "display_name": username,
            "reviews": [],
            "stats": {
                "total_reviews": 0,
                "avg_rating_given": 0,
                "helpful_received": 0,
            },
            "not_found": True,
        }

    total_reviews = len(reviews)
    avg_rating = round(sum(r["rating"] for r in reviews) / total_reviews, 2) if total_reviews else 0
    helpful_received = sum(r["helpful_count"] or 0 for r in reviews)
    display_name = reviews[0]["user_name"]

    return {
        "username": username,
        "display_name": display_name,
        "reviews": reviews,
        "stats": {
            "total_reviews": total_reviews,
            "avg_rating_given": avg_rating,
            "helpful_received": helpful_received,
        },
        "not_found": False,
    }


@router.get("/authors/{username}")
async def get_author_profile(username: str):
    """Get author profile — plugins + themes đã publish"""
    db = get_db()

    plugins = db.query(
        """
        SELECT 
            id, slug, name, description, icon, category,
            latest_version, downloads, installs, rating, review_count,
            verified, featured, created_at, type,
            price_vnd, is_paid
        FROM plugins
        WHERE LOWER(author) = LOWER(%s)
        ORDER BY downloads DESC
        """,
        (username,),
    )

    for p in plugins:
        if p.get("created_at"):
            p["created_at"] = p["created_at"].isoformat()

    if not plugins:
        return {
            "username": username,
            "plugins": [],
            "stats": {
                "total_plugins": 0,
                "total_downloads": 0,
                "total_installs": 0,
                "avg_rating": 0,
                "total_reviews": 0,
            },
            "not_found": True,
        }

    total_plugins = len(plugins)
    total_downloads = sum(p["downloads"] or 0 for p in plugins)
    total_installs = sum(p["installs"] or 0 for p in plugins)
    total_reviews = sum(p["review_count"] or 0 for p in plugins)

    total_weight = sum(p["review_count"] or 0 for p in plugins)
    if total_weight > 0:
        weighted = sum((p["rating"] or 0) * (p["review_count"] or 0) for p in plugins)
        avg_rating = round(weighted / total_weight, 2)
    else:
        avg_rating = 0

    display_name = username
    author_row = db.query_one(
        "SELECT author FROM plugins WHERE LOWER(author) = LOWER(%s) LIMIT 1",
        (username,),
    )
    if author_row:
        display_name = author_row["author"]

    return {
        "username": username,
        "display_name": display_name,
        "plugins": plugins,
        "stats": {
            "total_plugins": total_plugins,
            "total_downloads": total_downloads,
            "total_installs": total_installs,
            "avg_rating": avg_rating,
            "total_reviews": total_reviews,
        },
        "not_found": False,
    }