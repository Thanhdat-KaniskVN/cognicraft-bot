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