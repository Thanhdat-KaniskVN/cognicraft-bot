# store/backend/models.py
"""
Pydantic schemas cho Store API
Cập nhật để support unified plugin + theme (v3.0)
"""
from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================
# PLUGIN UPLOAD (request)
# ============================================================
class PluginUpload(BaseModel):
    slug: str
    name: str
    description: Optional[str] = ""
    long_description: Optional[str] = ""
    author: str
    author_email: Optional[str] = ""
    category: Optional[str] = "other"
    tags: Optional[List[str]] = []
    icon: Optional[str] = "📦"
    homepage: Optional[str] = ""
    repository: Optional[str] = ""
    license: Optional[str] = "MIT"
    version: str = "1.0.0"
    changelog: Optional[str] = ""
    requirements: Optional[List[str]] = []
    file_url: Optional[str] = ""
    file_size: Optional[int] = 0


# ============================================================
# PLUGIN RESPONSE (bao gồm cả theme)
# ============================================================
class PluginResponse(BaseModel):
    # Core
    id: str
    slug: str
    name: str
    description: Optional[str] = None
    long_description: Optional[str] = None

    # Author
    author: Optional[str] = None
    author_email: Optional[str] = None
    author_avatar: Optional[str] = None

    # Category + tags
    category: Optional[str] = None
    tags: Optional[List[str]] = []

    # Meta
    icon: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None
    license: Optional[str] = None
    latest_version: Optional[str] = None

    # Stats
    downloads: int = 0
    installs: int = 0
    rating: float = 0.0
    review_count: int = 0

    # Flags
    verified: bool = False
    featured: bool = False

    # Time
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # ⭐ FIELD MỚI — Type + Theme
    type: Optional[str] = "plugin"
    css_content: Optional[str] = None
    preview_image: Optional[str] = None
    likes: int = 0
    price_vnd: int = 0
    is_paid: bool = False

    # Computed
    has_file: bool = False

    class Config:
        # Cho phép extra fields không bị strip
        extra = "allow"


# ============================================================
# PLUGIN LIST RESPONSE (wrapper)
# ============================================================
class PluginListResponse(BaseModel):
    total: int
    plugins: List[PluginResponse]
    page: int = 1
    per_page: int = 20


# ============================================================
# REVIEW SUBMIT (request)
# ============================================================
class ReviewSubmit(BaseModel):
    user_id: str
    user_name: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = ""


# ============================================================
# REVIEW RESPONSE
# ============================================================
class ReviewResponse(BaseModel):
    id: str
    user_id: str
    user_name: str
    rating: int
    comment: Optional[str] = None
    helpful_count: int = 0
    created_at: Optional[str] = None

    class Config:
        extra = "allow"


# ============================================================
# CATEGORY RESPONSE
# ============================================================
class CategoryResponse(BaseModel):
    id: str
    name: str
    icon: Optional[str] = None
    plugin_count: int = 0

    class Config:
        extra = "allow"


# ============================================================
# THEME PUBLISH REQUEST (dùng cho marketplace)
# ============================================================
class ThemePublishRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    long_description: Optional[str] = ""
    preview_image: Optional[str] = ""
    css_content: str
    tags: Optional[List[str]] = []
    price_vnd: Optional[int] = 0


# ============================================================
# THEME RESPONSE
# ============================================================
class ThemeResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: Optional[str] = None
    long_description: Optional[str] = None
    css_content: Optional[str] = None
    preview_image: Optional[str] = None
    tags: Optional[List[str]] = []

    # Author
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None

    # Stats
    downloads: int = 0
    likes: int = 0
    rating: float = 0.0
    review_count: int = 0

    # Pricing
    price_vnd: int = 0
    is_paid: bool = False

    # Flags
    featured: bool = False
    verified: bool = False

    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        extra = "allow"


# ============================================================
# THEME LIST RESPONSE
# ============================================================
class ThemeListResponse(BaseModel):
    total: int
    themes: List[ThemeResponse]
    page: int = 1
    per_page: int = 24