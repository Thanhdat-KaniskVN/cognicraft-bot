# store/backend/models.py
"""
Pydantic models for Store API
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class PluginUpload(BaseModel):
    """Request model for uploading plugin"""
    slug: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-z0-9_]+$')
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., max_length=500)
    long_description: Optional[str] = None
    author: str = Field(..., min_length=2, max_length=100)
    author_email: Optional[str] = None
    category: str = "tools"
    tags: List[str] = []
    icon: str = "📦"
    homepage: Optional[str] = None
    repository: Optional[str] = None
    license: str = "MIT"
    version: str = "1.0.0"
    changelog: Optional[str] = None
    requirements: List[str] = []
    file_url: Optional[str] = None
    file_size: int = 0


class PluginResponse(BaseModel):
    """Response model for plugin"""
    id: str
    slug: str
    name: str
    description: str
    author: str
    category: str
    tags: List[str] = []
    icon: str
    homepage: Optional[str] = None
    repository: Optional[str] = None
    license: str
    latest_version: str
    downloads: int
    installs: int
    rating: float
    review_count: int
    verified: bool
    featured: bool
    created_at: datetime


class ReviewSubmit(BaseModel):
    """Request model for review"""
    user_id: str
    user_name: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class PluginListResponse(BaseModel):
    """Response for plugin list"""
    total: int
    plugins: List[PluginResponse]
    page: int = 1
    per_page: int = 20