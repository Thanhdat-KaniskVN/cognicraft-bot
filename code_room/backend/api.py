# code_room/backend/api.py
"""
Code Room API - FastAPI routes
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from pathlib import Path

from .sandbox_runner import CodeSandbox
from .history import CodeHistory
from .ai_fixer import AICodeFixer


router = APIRouter()

# Init
_history = CodeHistory()
_sandbox = CodeSandbox(timeout=10)
_fixer = AICodeFixer()


# ============================================================
# MODELS
# ============================================================

class SaveRequest(BaseModel):
    name: str
    content: str


class RunRequest(BaseModel):
    code: str
    timeout: int = 10


class FixRequest(BaseModel):
    code: str
    language: str = "python"


class RestoreRequest(BaseModel):
    name: str
    snapshot_id: str


class UndoRequest(BaseModel):
    name: str


# ============================================================
# FILE MANAGEMENT
# ============================================================

@router.get("/api/files")
async def list_files():
    """List tất cả files"""
    return {"files": _history.list_files()}


@router.post("/api/save")
async def save_file(req: SaveRequest):
    """Save file + tạo snapshot"""
    try:
        _history.save_file(req.name, req.content)
        return {"success": True, "message": f"Đã lưu {req.name}"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/load")
async def load_file(name: str):
    """Load file"""
    try:
        content = _history.load_file(name)
        return {"name": name, "content": content}
    except FileNotFoundError:
        raise HTTPException(404, f"File không tồn tại: {name}")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/api/delete")
async def delete_file(name: str):
    """Xóa file"""
    try:
        _history.delete_file(name)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))


# ============================================================
# SNAPSHOTS / UNDO
# ============================================================

@router.get("/api/snapshots")
async def list_snapshots(name: str):
    """List snapshots của file"""
    try:
        snapshots = _history.list_snapshots(name)
        return {"snapshots": snapshots}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/api/restore")
async def restore_snapshot(req: RestoreRequest):
    """Restore từ snapshot cụ thể"""
    try:
        content = _history.get_snapshot(req.name, req.snapshot_id)
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(404, "Snapshot không tồn tại")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/api/undo")
async def undo(req: UndoRequest):
    """Undo = lấy snapshot trước đó"""
    try:
        content = _history.undo(req.name)
        return {"content": content}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# ============================================================
# RUN CODE
# ============================================================

@router.post("/api/run")
async def run_code(req: RunRequest):
    """Chạy code Python"""
    try:
        result = _sandbox.run_python(req.code, timeout=req.timeout)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# ============================================================
# AI FIX
# ============================================================

@router.post("/api/fix")
async def fix_code(req: FixRequest):
    """Phân tích code với AI"""
    try:
        result = await _fixer.analyze(req.code, req.language)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))