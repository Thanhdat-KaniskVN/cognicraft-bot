# store/backend/auth.py
"""
Google OAuth Authentication
- Verify Google ID token
- Create/lookup user
- Issue session JWT
"""
import os
import jwt
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from .database import get_db


router = APIRouter()

# Config
GOOGLE_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID",
    "426541573663-cksl4s1t4qrv2gr0fa4f191404u0imnc.apps.googleusercontent.com"
)
JWT_SECRET = os.getenv("JWT_SECRET", "cognicraft-secret-change-in-production-2026")
JWT_ALGO = "HS256"
JWT_EXPIRE_DAYS = 30


# ============================================================
# MODELS
# ============================================================
class GoogleAuthRequest(BaseModel):
    credential: str


# ============================================================
# HELPERS
# ============================================================
def create_session_token(user_id: str, email: str, name: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def verify_session_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token đã hết hạn")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token không hợp lệ")


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Thiếu Authorization header")
    token = authorization.replace("Bearer ", "")
    return verify_session_token(token)


# ============================================================
# POST /google
# ============================================================
@router.post("/google")
async def auth_google(req: GoogleAuthRequest):
    """User gửi Google ID token → verify → tạo user + session"""
    # 1. Verify with Google
    try:
        idinfo = id_token.verify_oauth2_token(
            req.credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError as e:
        raise HTTPException(401, f"Google token không hợp lệ: {str(e)}")

    # 2. Extract info
    google_id = idinfo["sub"]
    email = idinfo["email"]
    name = idinfo.get("name", email.split("@")[0])
    picture = idinfo.get("picture", "")

    db = get_db()

    # 3. Upsert user (schema public)
    user = db.query_one(
        "SELECT * FROM public.users WHERE google_id = %s",
        (google_id,),
    )

    if user:
        db.execute(
            "UPDATE public.users SET last_login = NOW(), name = %s, avatar_url = %s WHERE id = %s",
            (name, picture, user["id"]),
        )
        user_id = user["id"]
    else:
        new_user = db.execute_returning(
            """
            INSERT INTO public.users (google_id, email, name, avatar_url, created_at, last_login)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            RETURNING id
            """,
            (google_id, email, name, picture),
        )
        user_id = new_user["id"]

    # 4. Create session JWT
    session_token = create_session_token(str(user_id), email, name)

    return {
        "success": True,
        "token": session_token,
        "user": {
            "id": str(user_id),
            "email": email,
            "name": name,
            "avatar_url": picture,
        },
    }


# ============================================================
# GET /me
# ============================================================
@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    db = get_db()

    db_user = db.query_one(
        "SELECT * FROM public.users WHERE id = %s",
        (user["sub"],),
    )
    if not db_user:
        raise HTTPException(404, "User không tồn tại")

    return {
        "id": str(db_user["id"]),
        "email": db_user["email"],
        "name": db_user["name"],
        "avatar_url": db_user.get("avatar_url"),
        "github_username": db_user.get("github_username"),
        "bio": db_user.get("bio"),
        "created_at": db_user["created_at"].isoformat() if db_user.get("created_at") else None,
    }


# ============================================================
# PUT /me — Update profile
# ============================================================
class ProfileUpdateRequest(BaseModel):
    github_username: Optional[str] = None
    code_room_slug: Optional[str] = None
    website: Optional[str] = None
    bio: Optional[str] = None


@router.put("/me")
async def update_me(
    req: ProfileUpdateRequest,
    user: dict = Depends(get_current_user),
):
    """Update user profile"""
    db = get_db()

    # Get current
    current = db.query_one("SELECT * FROM public.users WHERE id = %s", (user["sub"],))
    if not current:
        raise HTTPException(404, "User không tồn tại")

    # Merge values (None = giữ nguyên)
    github = req.github_username if req.github_username is not None else current.get("github_username")
    code_room = req.code_room_slug if req.code_room_slug is not None else current.get("code_room_slug")
    website = req.website if req.website is not None else current.get("website")
    bio = req.bio if req.bio is not None else current.get("bio")

    # Sanitize
    def clean(s):
        if s is None: return None
        return s.strip()[:200] if s.strip() else None

    db.execute(
        """
        UPDATE public.users 
        SET github_username = %s, code_room_slug = %s, website = %s, bio = %s
        WHERE id = %s
        """,
        (clean(github), clean(code_room), clean(website), clean(bio), user["sub"]),
    )

    return {
        "success": True,
        "message": "Đã cập nhật profile",
        "user": {
            "github_username": clean(github),
            "code_room_slug": clean(code_room),
            "website": clean(website),
            "bio": clean(bio),
        },
    }


# ============================================================
# GET /me/dashboard — User dashboard stats (FIXED v2)
# ============================================================
@router.get("/me/dashboard")
async def get_dashboard(user: dict = Depends(get_current_user)):
    """Get user dashboard summary — matches by github_username, name, id"""
    db = get_db()

    db_user = db.query_one("SELECT * FROM public.users WHERE id = %s", (user["sub"],))
    if not db_user:
        raise HTTPException(404, "User không tồn tại")

    user_id         = str(db_user["id"])
    github_username = (db_user.get("github_username") or "").strip()
    user_name       = (db_user.get("name") or "").strip()

    # Danh sách biến thể author có thể gặp
    candidates = [c for c in {github_username, user_name, user_id} if c]
    if not candidates:
        candidates = ["__none__"]

    # --- My plugins ---
    my_plugins = db.query(
        """
        SELECT id, slug, name, icon, description, category,
               downloads, installs, rating, review_count,
               latest_version, created_at, author
        FROM plugins
        WHERE LOWER(author) = ANY(%s)
        ORDER BY downloads DESC
        """,
        ([c.lower() for c in candidates],),
    )
    for p in my_plugins:
        if p.get("created_at"):
            p["created_at"] = p["created_at"].isoformat()

    # --- Stats ---
    total_downloads = sum(p.get("downloads", 0) or 0 for p in my_plugins)
    total_installs  = sum(p.get("installs", 0) or 0 for p in my_plugins)
    total_reviews_received = sum(p.get("review_count", 0) or 0 for p in my_plugins)

    if my_plugins:
        weights = sum(p.get("review_count", 0) or 0 for p in my_plugins)
        avg_rating = round(
            sum((p.get("rating", 0) or 0) * (p.get("review_count", 0) or 0)
                for p in my_plugins) / weights, 1
        ) if weights > 0 else 0
    else:
        avg_rating = 0

    # --- My reviews ---
    my_reviews = db.query(
        """
        SELECT r.id, r.rating, r.comment, r.helpful_count, r.created_at,
               p.slug AS plugin_slug, p.name AS plugin_name, p.icon AS plugin_icon
        FROM reviews r
        JOIN plugins p ON p.id = r.plugin_id
        WHERE r.user_id = ANY(%s)
           OR LOWER(r.user_name) = ANY(%s)
        ORDER BY r.created_at DESC
        LIMIT 20
        """,
        (
            candidates,
            [c.lower() for c in candidates],
        ),
    )
    for r in my_reviews:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()

    return {
        "user": {
            "id": user_id,
            "name": db_user.get("name"),
            "email": db_user.get("email"),
            "avatar_url": db_user.get("avatar_url"),
            "github_username": db_user.get("github_username"),
            "bio": db_user.get("bio"),
            "created_at": db_user.get("created_at").isoformat() if db_user.get("created_at") else None,
        },
        "stats": {
            "total_plugins": len(my_plugins),
            "total_downloads": total_downloads,
            "total_installs": total_installs,
            "total_reviews_received": total_reviews_received,
            "avg_rating": avg_rating,
            "total_reviews_written": len(my_reviews),
        },
        "my_plugins": my_plugins,
        "my_reviews": my_reviews,
    }