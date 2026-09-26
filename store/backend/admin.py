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