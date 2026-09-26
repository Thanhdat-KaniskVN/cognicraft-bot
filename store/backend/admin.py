# store/backend/admin.py
"""
Admin Panel API
- Chỉ user is_admin=TRUE mới truy cập được
- Quản lý users, themes, plugins, reports
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from pydantic import BaseModel

from .database import get_db
from .auth import get_current_user

router = APIRouter()


# ============================================================
# MIDDLEWARE — check admin
# ============================================================
async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Chỉ cho admin đi qua"""
    db = get_db()
    db_user = db.query_one(
        "SELECT id, email, name, is_admin, banned FROM public.users WHERE id = %s",
        (user["sub"],),
    )

    if not db_user:
        raise HTTPException(404, "User không tồn tại")

    if db_user.get("banned"):
        raise HTTPException(403, "Tài khoản đã bị khóa")

    if not db_user.get("is_admin"):
        raise HTTPException(403, "Bạn không có quyền admin")

    return db_user


# ============================================================
# MODELS
# ============================================================
class BanRequest(BaseModel):
    reason: Optional[str] = "Vi phạm điều khoản"


class FeatureRequest(BaseModel):
    featured: bool


class VerifyRequest(BaseModel):
    verified: bool


class HideRequest(BaseModel):
    hidden: bool


class ReportResolveRequest(BaseModel):
    status: Optional[str] = "resolved"


# ============================================================
# GET /api/admin/me — check quyền admin
# ============================================================
@router.get("/me")
async def admin_me(admin: dict = Depends(require_admin)):
    return {
        "is_admin": True,
        "id": str(admin["id"]),
        "email": admin["email"],
        "name": admin["name"],
    }


# ============================================================
# GET /api/admin/stats — overview
# ============================================================
@router.get("/stats")
async def admin_stats(admin: dict = Depends(require_admin)):
    db = get_db()

    total_users = db.query_one("SELECT COUNT(*) AS c FROM public.users")["c"]
    total_plugins = db.query_one("SELECT COUNT(*) AS c FROM plugins WHERE type = 'plugin'")["c"]
    total_themes = db.query_one("SELECT COUNT(*) AS c FROM plugins WHERE type = 'theme'")["c"]
    total_reports = db.query_one("SELECT COUNT(*) AS c FROM reports WHERE status = 'pending'")["c"]
    total_orders = db.query_one("SELECT COUNT(*) AS c FROM orders")["c"]
    total_revenue = db.query_one("SELECT COALESCE(SUM(amount_vnd), 0) AS s FROM orders WHERE status = 'paid'")["s"]

    # Users mới trong 7 ngày
    recent_users = db.query_one(
        "SELECT COUNT(*) AS c FROM public.users WHERE created_at > NOW() - INTERVAL '7 days'"
    )["c"]

    return {
        "users": total_users,
        "recent_users": recent_users,
        "plugins": total_plugins,
        "themes": total_themes,
        "pending_reports": total_reports,
        "orders": total_orders,
        "revenue_vnd": int(total_revenue or 0),
    }


# ============================================================
# GET /api/admin/users — list users
# ============================================================
@router.get("/users")
async def admin_list_users(
    search: Optional[str] = None,
    filter: Optional[str] = Query(None, pattern="^(all|admin|banned|normal)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = 0,
    admin: dict = Depends(require_admin),
):
    db = get_db()

    conditions = []
    params = []

    if search:
        conditions.append("(name ILIKE %s OR email ILIKE %s OR github_username ILIKE %s)")
        p = f"%{search}%"
        params.extend([p, p, p])

    if filter == "admin":
        conditions.append("is_admin = TRUE")
    elif filter == "banned":
        conditions.append("banned = TRUE")
    elif filter == "normal":
        conditions.append("COALESCE(is_admin, FALSE) = FALSE AND COALESCE(banned, FALSE) = FALSE")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    total_row = db.query_one(
        f"SELECT COUNT(*) AS c FROM public.users {where}",
        tuple(params),
    )
    total = total_row["c"] if total_row else 0

    users = db.query(
        f"""
        SELECT 
            id, email, name, avatar_url, github_username, bio,
            is_admin, banned, ban_reason, banned_at,
            created_at, last_login
        FROM public.users
        {where}
        ORDER BY created_at DESC NULLS LAST
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )

    for u in users:
        u["id"] = str(u["id"])
        if u.get("created_at"):
            u["created_at"] = u["created_at"].isoformat()
        if u.get("last_login"):
            u["last_login"] = u["last_login"].isoformat()
        if u.get("banned_at"):
            u["banned_at"] = u["banned_at"].isoformat()

    return {"total": total, "users": users}


# ============================================================
# POST /api/admin/users/{id}/ban
# ============================================================
@router.post("/users/{user_id}/ban")
async def admin_ban_user(
    user_id: str,
    req: BanRequest,
    admin: dict = Depends(require_admin),
):
    db = get_db()

    if str(admin["id"]) == user_id:
        raise HTTPException(400, "Không thể tự ban chính mình")

    result = db.execute(
        """
        UPDATE public.users 
        SET banned = TRUE, ban_reason = %s, banned_at = NOW()
        WHERE id = %s
        """,
        (req.reason, user_id),
    )

    return {"success": True, "message": "Đã ban user"}


# ============================================================
# POST /api/admin/users/{id}/unban
# ============================================================
@router.post("/users/{user_id}/unban")
async def admin_unban_user(
    user_id: str,
    admin: dict = Depends(require_admin),
):
    db = get_db()

    db.execute(
        """
        UPDATE public.users 
        SET banned = FALSE, ban_reason = NULL, banned_at = NULL
        WHERE id = %s
        """,
        (user_id,),
    )

    return {"success": True, "message": "Đã unban user"}


# ============================================================
# POST /api/admin/users/{id}/toggle-admin
# ============================================================
@router.post("/users/{user_id}/toggle-admin")
async def admin_toggle_admin(
    user_id: str,
    admin: dict = Depends(require_admin),
):
    db = get_db()

    if str(admin["id"]) == user_id:
        raise HTTPException(400, "Không thể tự thay đổi quyền admin")

    current = db.query_one("SELECT is_admin FROM public.users WHERE id = %s", (user_id,))
    if not current:
        raise HTTPException(404, "User không tồn tại")

    new_val = not bool(current.get("is_admin"))
    db.execute("UPDATE public.users SET is_admin = %s WHERE id = %s", (new_val, user_id))

    return {"success": True, "is_admin": new_val}


# ============================================================
# GET /api/admin/themes — list tất cả theme + plugin
# ============================================================
@router.get("/themes")
async def admin_list_themes(
    type_filter: Optional[str] = Query(None, alias="type", pattern="^(theme|plugin)$"),
    search: Optional[str] = None,
    sort: str = Query("created_at", pattern="^(created_at|downloads|rating)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = 0,
    admin: dict = Depends(require_admin),
):
    db = get_db()

    conditions = ["1=1"]
    params = []

    if type_filter:
        conditions.append("type = %s")
        params.append(type_filter)

    if search:
        conditions.append("(name ILIKE %s OR slug ILIKE %s OR author ILIKE %s)")
        p = f"%{search}%"
        params.extend([p, p, p])

    where = " AND ".join(conditions)

    order_map = {
        "created_at": "created_at DESC",
        "downloads": "downloads DESC",
        "rating": "rating DESC NULLS LAST",
    }
    order = order_map.get(sort, "created_at DESC")

    total_row = db.query_one(f"SELECT COUNT(*) AS c FROM plugins WHERE {where}", tuple(params))
    total = total_row["c"] if total_row else 0

    rows = db.query(
        f"""
        SELECT 
            id, slug, name, type, author, category,
            downloads, installs, rating, review_count,
            featured, verified, price_vnd, is_paid,
            created_at
        FROM plugins
        WHERE {where}
        ORDER BY {order}
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )

    for r in rows:
        r["id"] = str(r["id"])
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()

    return {"total": total, "items": rows}


# ============================================================
# POST /api/admin/themes/{slug}/feature
# ============================================================
@router.post("/themes/{slug}/feature")
async def admin_feature(
    slug: str,
    req: FeatureRequest,
    admin: dict = Depends(require_admin),
):
    db = get_db()

    result = db.execute(
        "UPDATE plugins SET featured = %s WHERE slug = %s",
        (req.featured, slug),
    )

    return {"success": True, "featured": req.featured}


# ============================================================
# POST /api/admin/themes/{slug}/verify
# ============================================================
@router.post("/themes/{slug}/verify")
async def admin_verify(
    slug: str,
    req: VerifyRequest,
    admin: dict = Depends(require_admin),
):
    db = get_db()

    db.execute(
        "UPDATE plugins SET verified = %s WHERE slug = %s",
        (req.verified, slug),
    )

    return {"success": True, "verified": req.verified}


# ============================================================
# DELETE /api/admin/themes/{slug} — xóa force
# ============================================================
@router.delete("/themes/{slug}")
async def admin_delete_theme(
    slug: str,
    admin: dict = Depends(require_admin),
):
    db = get_db()

    db.execute("DELETE FROM plugins WHERE slug = %s", (slug,))

    return {"success": True, "message": "Đã xóa"}


# ============================================================
# GET /api/admin/reports
# ============================================================
@router.get("/reports")
async def admin_list_reports(
    status: Optional[str] = Query(None, pattern="^(pending|resolved|dismissed)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = 0,
    admin: dict = Depends(require_admin),
):
    db = get_db()

    conditions = []
    params = []

    if status:
        conditions.append("r.status = %s")
        params.append(status)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    total_row = db.query_one(f"SELECT COUNT(*) AS c FROM reports r {where}", tuple(params))
    total = total_row["c"] if total_row else 0

    rows = db.query(
        f"""
        SELECT 
            r.id, r.reported_type, r.reported_slug, r.reason, r.description,
            r.status, r.created_at, r.resolved_at,
            reporter.name AS reporter_name, reporter.email AS reporter_email,
            resolver.name AS resolver_name
        FROM reports r
        LEFT JOIN public.users reporter ON reporter.id = r.reporter_id
        LEFT JOIN public.users resolver ON resolver.id = r.resolved_by
        {where}
        ORDER BY r.created_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )

    for r in rows:
        r["id"] = str(r["id"])
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
        if r.get("resolved_at"):
            r["resolved_at"] = r["resolved_at"].isoformat()

    return {"total": total, "reports": rows}

# ============================================================
# 📊 ANALYTICS ENDPOINTS (Phase 11)
# ============================================================

# ============================================================
# GET /api/admin/analytics/overview — KPIs tổng hợp
# ============================================================
@router.get("/analytics/overview")
async def analytics_overview(admin: dict = Depends(require_admin)):
    db = get_db()

    # Users
    total_users = db.query_one("SELECT COUNT(*) AS c FROM public.users")["c"] or 0
    users_7d = db.query_one(
        "SELECT COUNT(*) AS c FROM public.users WHERE created_at > NOW() - INTERVAL '7 days'"
    )["c"] or 0
    users_30d = db.query_one(
        "SELECT COUNT(*) AS c FROM public.users WHERE created_at > NOW() - INTERVAL '30 days'"
    )["c"] or 0
    users_prev_7d = db.query_one(
        """SELECT COUNT(*) AS c FROM public.users 
           WHERE created_at > NOW() - INTERVAL '14 days' 
           AND created_at <= NOW() - INTERVAL '7 days'"""
    )["c"] or 0

    # Content
    total_themes = db.query_one("SELECT COUNT(*) AS c FROM plugins WHERE type = 'theme'")["c"] or 0
    total_plugins = db.query_one("SELECT COUNT(*) AS c FROM plugins WHERE type = 'plugin'")["c"] or 0
    themes_7d = db.query_one(
        """SELECT COUNT(*) AS c FROM plugins 
           WHERE type = 'theme' AND created_at > NOW() - INTERVAL '7 days'"""
    )["c"] or 0

    # Engagement
    total_downloads = db.query_one("SELECT COALESCE(SUM(downloads), 0) AS s FROM plugins")["s"] or 0
    total_likes = db.query_one("SELECT COALESCE(SUM(likes), 0) AS s FROM plugins WHERE type = 'theme'")["s"] or 0
    total_reviews = db.query_one("SELECT COUNT(*) AS c FROM reviews")["c"] or 0

    # Revenue
    total_revenue = db.query_one(
        "SELECT COALESCE(SUM(amount_vnd), 0) AS s FROM orders WHERE status = 'paid'"
    )["s"] or 0
    pending_orders = db.query_one("SELECT COUNT(*) AS c FROM orders WHERE status = 'pending'")["c"] or 0

    # Growth rates
    user_growth = 0
    if users_prev_7d > 0:
        user_growth = round(((users_7d - users_prev_7d) / users_prev_7d) * 100, 1)
    elif users_7d > 0:
        user_growth = 100

    return {
        "users": {
            "total": total_users,
            "last_7d": users_7d,
            "last_30d": users_30d,
            "growth_7d_pct": user_growth,
        },
        "content": {
            "themes": total_themes,
            "plugins": total_plugins,
            "themes_7d": themes_7d,
        },
        "engagement": {
            "downloads": total_downloads,
            "likes": total_likes,
            "reviews": total_reviews,
        },
        "revenue": {
            "total_vnd": int(total_revenue),
            "pending_orders": pending_orders,
        },
    }


# ============================================================
# GET /api/admin/analytics/timeline — data theo ngày
# ============================================================
@router.get("/analytics/timeline")
async def analytics_timeline(
    days: int = Query(30, ge=7, le=90),
    admin: dict = Depends(require_admin),
):
    """Trả về timeline theo ngày: users, themes, downloads"""
    db = get_db()

    # Users theo ngày
    users_rows = db.query(
        f"""
        SELECT 
            TO_CHAR(created_at::date, 'YYYY-MM-DD') AS day,
            COUNT(*) AS count
        FROM public.users
        WHERE created_at > NOW() - INTERVAL '{days} days'
        GROUP BY day
        ORDER BY day
        """,
    )

    # Themes/plugins theo ngày
    items_rows = db.query(
        f"""
        SELECT 
            TO_CHAR(created_at::date, 'YYYY-MM-DD') AS day,
            COUNT(*) AS count,
            SUM(CASE WHEN type = 'theme' THEN 1 ELSE 0 END) AS theme_count,
            SUM(CASE WHEN type = 'plugin' THEN 1 ELSE 0 END) AS plugin_count
        FROM plugins
        WHERE created_at > NOW() - INTERVAL '{days} days'
        GROUP BY day
        ORDER BY day
        """,
    )

    # Orders theo ngày
    orders_rows = db.query(
        f"""
        SELECT 
            TO_CHAR(created_at::date, 'YYYY-MM-DD') AS day,
            COUNT(*) AS count,
            COALESCE(SUM(CASE WHEN status = 'paid' THEN amount_vnd ELSE 0 END), 0) AS revenue
        FROM orders
        WHERE created_at > NOW() - INTERVAL '{days} days'
        GROUP BY day
        ORDER BY day
        """,
    )

    # Build full timeline (fill missing days with 0)
    from datetime import datetime, timedelta
    today = datetime.utcnow().date()
    days_list = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    users_map = {r["day"]: r["count"] for r in users_rows}
    items_map = {r["day"]: dict(r) for r in items_rows}
    orders_map = {r["day"]: dict(r) for r in orders_rows}

    timeline = []
    for day in days_list:
        items = items_map.get(day, {})
        orders = orders_map.get(day, {})
        timeline.append({
            "date": day,
            "users": users_map.get(day, 0),
            "items": items.get("count", 0),
            "themes": items.get("theme_count", 0),
            "plugins": items.get("plugin_count", 0),
            "orders": orders.get("count", 0),
            "revenue": int(orders.get("revenue", 0)),
        })

    return {"timeline": timeline, "days": days}


# ============================================================
# GET /api/admin/analytics/top — top themes, authors
# ============================================================
@router.get("/analytics/top")
async def analytics_top(
    limit: int = Query(10, ge=5, le=50),
    admin: dict = Depends(require_admin),
):
    db = get_db()

    # Top themes by downloads
    top_themes = db.query(
        """
        SELECT slug, name, type, author, downloads, likes, rating, 
               review_count, price_vnd, is_paid
        FROM plugins
        WHERE type = 'theme'
        ORDER BY downloads DESC, likes DESC
        LIMIT %s
        """,
        (limit,),
    )

    # Top plugins by downloads
    top_plugins = db.query(
        """
        SELECT slug, name, type, author, downloads, rating, review_count
        FROM plugins
        WHERE type = 'plugin'
        ORDER BY downloads DESC
        LIMIT %s
        """,
        (limit,),
    )

    # Top authors by total downloads
    top_authors = db.query(
        """
        SELECT 
            author,
            COUNT(*) AS item_count,
            SUM(downloads) AS total_downloads,
            SUM(likes) AS total_likes,
            AVG(rating) FILTER (WHERE review_count > 0) AS avg_rating
        FROM plugins
        GROUP BY author
        ORDER BY total_downloads DESC NULLS LAST
        LIMIT %s
        """,
        (limit,),
    )

    for a in top_authors:
        a["total_downloads"] = int(a["total_downloads"] or 0)
        a["total_likes"] = int(a["total_likes"] or 0)
        a["avg_rating"] = round(float(a["avg_rating"] or 0), 2)

    # Top tags
    top_tags = db.query(
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

    return {
        "top_themes": top_themes,
        "top_plugins": top_plugins,
        "top_authors": top_authors,
        "top_tags": top_tags,
    }
# ============================================================
# POST /api/admin/reports/{id}/resolve
# ============================================================
@router.post("/reports/{report_id}/resolve")
async def admin_resolve_report(
    report_id: str,
    req: ReportResolveRequest,
    admin: dict = Depends(require_admin),
):
    db = get_db()

    db.execute(
        """
        UPDATE reports 
        SET status = %s, resolved_by = %s, resolved_at = NOW()
        WHERE id = %s
        """,
        (req.status, admin["id"], report_id),
    )

    return {"success": True}