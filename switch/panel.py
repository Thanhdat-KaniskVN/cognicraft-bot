# panel.py
"""
CogniCraft Switch Board Panel
- FastAPI server
- Control Panel UI (Cyberpunk)
- Plugin Hub Web UI
- REST API
"""
import os
import sys
import json
import importlib.util
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv


# ============================================================
# PATH SETUP
# ============================================================

_THIS_DIR = Path(__file__).parent.resolve()
_BOT_ROOT = _THIS_DIR.parent.resolve()
_SWITCH_DIR = _THIS_DIR

# Add bot root + switch dir to sys.path
if str(_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOT_ROOT))
if str(_SWITCH_DIR) not in sys.path:
    sys.path.insert(0, str(_SWITCH_DIR))

# Load .env
_env_file = _SWITCH_DIR / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


# ============================================================
# LOAD BOARD
# ============================================================

from board import SwitchBoard

board = SwitchBoard()


# ============================================================
# LOAD HUB (từ root bằng absolute path)
# ============================================================

_hub_file = _BOT_ROOT / "hub.py"

if not _hub_file.exists():
    raise ImportError(f"❌ Không tìm thấy hub.py tại: {_hub_file}")

_spec = importlib.util.spec_from_file_location("cognicraft_hub_root", str(_hub_file))
_hub_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hub_module)

PluginHub = _hub_module.PluginHub

# Init hub with absolute paths
_hub = PluginHub()
print(f"[Panel] ✅ Loaded hub.py: {_hub_file}")


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await board.boot()
    yield
    await board.shutdown()


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="CogniCraft Switch Board",
    description="Bảng điện - Quản lý tất cả kết nối + Plugin Hub",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# STATIC FILES
# ============================================================

# Switch Board Web UI
_web_dir = _SWITCH_DIR / "web"
if _web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_web_dir)), name="static")
    print(f"[Panel] Static mounted: {_web_dir}")

# Plugin Hub Web UI
_web_plugins_dir = _SWITCH_DIR / "web_plugins"
if _web_plugins_dir.exists():
    app.mount("/static-plugins", StaticFiles(directory=str(_web_plugins_dir)), name="static-plugins")
    print(f"[Panel] Plugin Web UI mounted: {_web_plugins_dir}")
# ============================================================
# ML MINI WEB UI + API
# ============================================================

_ml_web_dir = _BOT_ROOT / "ml_mini" / "web"
if _ml_web_dir.exists():
    app.mount("/static-ml", StaticFiles(directory=str(_ml_web_dir)), name="static-ml")
    print(f"[Panel] ML Mini Web UI mounted: {_ml_web_dir}")

# ML Mini API router
try:
    from ml_mini.integration.ml_web import router as ml_router
    app.include_router(ml_router, prefix="/ml")
    print(f"[Panel] ML Mini API loaded")
except Exception as e:
    print(f"[Panel] ⚠️ ML Mini error: {e}")


@app.get("/ml/", response_class=HTMLResponse)
async def ml_web_ui():
    """ML Mini Web UI"""
    index = _ml_web_dir / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>❌ Không tìm thấy ml_mini/web/index.html</h1>", status_code=500)
    return FileResponse(str(index))


# ============================================================
# CODE ROOM WEB UI + API
# ============================================================

_code_room_dir = _BOT_ROOT / "code_room" / "web"
if _code_room_dir.exists():
    app.mount("/static-code", StaticFiles(directory=str(_code_room_dir)), name="static-code")
        # ✅ Store Bridge — Code Room ↔ Store integration
    from code_room.backend.store_bridge import router as store_bridge_router
    app.include_router(store_bridge_router, prefix="/code", tags=["store-bridge"])
    print(f"[Panel] Store Bridge mounted at /code/api/store/*")
    print(f"[Panel] Code Room mounted: {_code_room_dir}")

# Code Room API router
try:
    from code_room.backend.api import router as code_router
    app.include_router(code_router, prefix="/code")
    print(f"[Panel] Code Room API loaded")
except Exception as e:
    print(f"[Panel] ⚠️ Code Room error: {e}")


@app.get("/code/", response_class=HTMLResponse)
async def code_room_ui():
    """Code Room UI"""
    index = _code_room_dir / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>❌ Không tìm thấy code_room/web/index.html</h1>", status_code=500)
    return FileResponse(str(index))

# ============================================================
# ROOT + HEALTH
# ============================================================

@app.get("/")
async def root():
    return {
        "service": "CogniCraft Switch Board",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "panel": "/panel",
            "plugins": "/plugins/",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health():
    from datetime import datetime
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "sockets": len(board.registry.sockets),
    }


# ============================================================
# PANEL UI
# ============================================================

@app.get("/panel", response_class=HTMLResponse)
async def panel_ui():
    """Cyberpunk Switch Board Panel"""
    index_file = _web_dir / "index.html"

    if not index_file.exists():
        return HTMLResponse(
            "<h1>❌ Không tìm thấy web/index.html</h1>"
            "<p>Tạo file: D:\\Bot deepseek\\switch\\web\\index.html</p>",
            status_code=500,
        )

    return FileResponse(str(index_file))


# ============================================================
# PANEL API
# ============================================================

@app.get("/panel/status")
async def panel_status():
    """Trạng thái toàn board"""
    return board.registry.get_board_status()


@app.get("/panel/wires")
async def panel_wires():
    """Xem tất cả dây đã nối"""
    return board.router.list_wires()


@app.get("/panel/history")
async def panel_history(limit: int = 20):
    """Lịch sử events"""
    return {"history": board.router.get_history(limit)}


@app.post("/panel/socket/{name}/start")
async def socket_start(name: str):
    """Bật socket"""
    ok = await board.registry.start(name)
    if not ok:
        raise HTTPException(400, f"Không bật được {name}")
    return {"status": "on", "socket": name}


@app.post("/panel/socket/{name}/stop")
async def socket_stop(name: str):
    """Tắt socket"""
    ok = await board.registry.stop(name)
    if not ok:
        raise HTTPException(400, f"Không tắt được {name}")
    return {"status": "off", "socket": name}


@app.get("/panel/socket/{name}/health")
async def socket_health(name: str):
    """Health check"""
    socket = board.registry.get(name)
    if not socket:
        raise HTTPException(404, f"Socket không tìm thấy: {name}")
    ok = await socket.health_check()
    return {"socket": name, "healthy": ok, "info": socket.to_dict()}


# ============================================================
# COGNI BOT API (proxy qua socket)
# ============================================================

@app.get("/cogni/members")
async def cogni_members():
    """Lấy danh sách members"""
    cogni = board.registry.get("cogni_bot")
    if not cogni:
        raise HTTPException(503, "Cogni Bot chưa cắm")
    members = await cogni.call("get_members")
    return {"members": members}


@app.get("/cogni/scores")
async def cogni_scores(week: int):
    """Lấy scores của tuần"""
    cogni = board.registry.get("cogni_bot")
    if not cogni:
        raise HTTPException(503, "Cogni Bot chưa cắm")
    scores = await cogni.call("get_scores", week=week)
    return {"week": week, "scores": scores}


@app.get("/cogni/stats")
async def cogni_stats():
    """Stats tổng quan"""
    cogni = board.registry.get("cogni_bot")
    if not cogni:
        raise HTTPException(503, "Cogni Bot chưa cắm")
    return await cogni.call("get_stats")


@app.get("/cogni/score/{member}")
async def cogni_member_score(member: str, week: int):
    """Lấy score 1 member"""
    cogni = board.registry.get("cogni_bot")
    if not cogni:
        raise HTTPException(503, "Cogni Bot chưa cắm")
    score = await cogni.call("get_member_score", week=week, member=member)
    if not score:
        raise HTTPException(404, f"Không tìm thấy {member} tuần {week}")
    return score


# ============================================================
# MAGIC ENDPOINTS
# ============================================================

class EmitRequest(BaseModel):
    event: str
    payload: dict = {}


@app.post("/panel/emit")
async def panel_emit(req: EmitRequest):
    """Phát event → Router tự tìm socket"""
    results = await board.router.emit(req.event, req.payload)
    return {"event": req.event, "results": results}


@app.post("/switch/sync-score-to-calendar")
async def sync_score_to_calendar(week: int, member: str, date: str = None):
    """
    🔥 MAGIC: Lấy score từ Cogni Bot → Tạo event trên Google Calendar
    """
    cogni = board.registry.get("cogni_bot")
    if not cogni:
        raise HTTPException(503, "Cogni Bot chưa cắm")

    score = await cogni.call("get_member_score", week=week, member=member)
    if not score:
        raise HTTPException(404, f"Không tìm thấy {member} tuần {week}")

    results = await board.router.emit("cogni.score.confirmed", {
        "week": week,
        "member": member,
        "total": score.get("total"),
        "date": date,
    })

    return {"status": "synced", "score": score, "routed": results}


# ============================================================
# PLUGIN HUB API
# ============================================================

@app.get("/plugins/api/list")
async def plugins_api_list():
    """List all plugins"""
    try:
        plugins = _hub.list_plugins()
        stats = _hub.get_stats()
        return {
            "total": stats["total_plugins"],
            "installed": stats["installed"],
            "available": stats["available"],
            "categories": stats["categories"],
            "plugins": plugins,
        }
    except Exception as e:
        import traceback
        print(f"[API] /plugins/api/list ERROR: {e}")
        traceback.print_exc()
        raise HTTPException(500, f"Hub error: {e}")


@app.get("/plugins/api/info/{plugin_id}")
async def plugins_api_info(plugin_id: str):
    """Get plugin info"""
    try:
        plugin = _hub.get_plugin(plugin_id)
        if not plugin:
            raise HTTPException(404, f"Plugin không tìm thấy: {plugin_id}")

        # Đọc manifest đầy đủ
        source_path = Path(plugin["source_path"])
        manifest_file = source_path / "plugin.json"
        full_manifest = {}
        if manifest_file.exists():
            with open(manifest_file, "r", encoding="utf-8") as f:
                full_manifest = json.load(f)

        return {
            **plugin,
            "commands": full_manifest.get("commands", []),
            "config": full_manifest.get("config", {}),
            "permissions": full_manifest.get("permissions", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[API] /plugins/api/info ERROR: {e}")
        traceback.print_exc()
        raise HTTPException(500, f"Error: {e}")


@app.post("/plugins/api/install/{plugin_id}")
async def plugins_api_install(plugin_id: str):
    """Install plugin"""
    try:
        result = _hub.install(plugin_id)
        return result
    except Exception as e:
        import traceback
        print(f"[API] install ERROR: {e}")
        traceback.print_exc()
        raise HTTPException(500, f"Error: {e}")


@app.post("/plugins/api/uninstall/{plugin_id}")
async def plugins_api_uninstall(plugin_id: str):
    """Uninstall plugin"""
    try:
        result = _hub.uninstall(plugin_id)
        return result
    except Exception as e:
        import traceback
        print(f"[API] uninstall ERROR: {e}")
        traceback.print_exc()
        raise HTTPException(500, f"Error: {e}")


# ============================================================
# PLUGIN WEB UI ROUTES
# ============================================================

@app.get("/plugins/", response_class=HTMLResponse)
async def plugins_hub_ui():
    """Plugin Hub dashboard"""
    index_file = _web_plugins_dir / "index.html"
    if not index_file.exists():
        return HTMLResponse(
            "<h1>❌ Không tìm thấy web_plugins/index.html</h1>",
            status_code=500,
        )
    return FileResponse(str(index_file))


@app.get("/plugins/{plugin_id}/", response_class=HTMLResponse)
@app.get("/plugins/{plugin_id}", response_class=HTMLResponse)
async def plugin_detail_ui(plugin_id: str):
    """Individual plugin UI"""
    index_file = _web_plugins_dir / "plugin" / "index.html"
    if not index_file.exists():
        return HTMLResponse(
            "<h1>❌ Không tìm thấy web_plugins/plugin/index.html</h1>",
            status_code=500,
        )
    return FileResponse(str(index_file))


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("SWITCH_HOST", "0.0.0.0")
    port = int(os.getenv("SWITCH_PORT", "8000"))

    print(f"\n🚀 Switch Board: http://localhost:{port}")
    print(f"📊 Panel UI:    http://localhost:{port}/panel")
    print(f"📦 Plugin Hub:  http://localhost:{port}/plugins/")
    print(f"📖 API Docs:    http://localhost:{port}/docs\n")

    uvicorn.run(
        "panel:app",
        host=host,
        port=port,
        reload=True,
        app_dir=str(_SWITCH_DIR),
    )