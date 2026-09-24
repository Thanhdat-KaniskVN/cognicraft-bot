# ml_mini/coordinator.py
"""
ML Mini Coordinator - Bộ điều phối tài nguyên sandbox
- Heartbeat với adaptive interval
- Circuit breaker (auto-disconnect)
- Auto-reconnect sau 15s
- Persistence
- State management
"""
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple

from .config import MLConfig
from .heartbeat import AdaptiveHeartbeat
from .persistence import Persistence
from .sandbox.base import BaseSandbox, SandboxState


class LinkState:
    """Trạng thái của 1 liên kết"""
    ACTIVE = "active"
    BROKEN = "broken"
    RESTORING = "restoring"


class SandboxCoordinator:
    """
    Bộ điều phối - Trái tim của ML Mini
    
    Chức năng:
    1. Quản lý vòng đời sandbox
    2. Heartbeat check (adaptive interval)
    3. Circuit breaker khi sụp
    4. Auto-reconnect sau 15s
    5. Persistence (save/load state)
    """
    
    def __init__(self, auto_start: bool = True):
        self.config = MLConfig
        self.config.ensure_dirs()
        
        # Sandboxes
        self.sandboxes: Dict[str, dict] = {}
        self.states: Dict[str, SandboxState] = {}
        self.missed_heartbeats: Dict[str, int] = {}
        
        # Links (mesh)
        self.links: Set[Tuple[str, str]] = set()
        self.link_states: Dict[Tuple[str, str], str] = {}
        
        # Heartbeat
        self.heartbeat = AdaptiveHeartbeat(
            base=self.config.HEARTBEAT_INTERVAL_BASE,
            min_i=self.config.HEARTBEAT_INTERVAL_MIN,
            max_i=self.config.HEARTBEAT_INTERVAL_MAX,
        )
        self._next_heartbeats: Dict[str, float] = {}
        
        # Persistence
        self.persistence = Persistence(
            state_file=self.config.COORDINATOR_STATE_FILE,
            auto_save_interval=self.config.AUTO_SAVE_INTERVAL,
        )
        
        # Runtime
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._autosave_task: Optional[asyncio.Task] = None
        
        # Logs
        self.event_log: List[dict] = []
        self.max_log = self.config.LOG_MAX_LINES
        
        # Restart tracking
        self.restart_attempts: Dict[str, int] = {}
        
        # Try load state
        self._try_load_state()
    
    # ============================================================
    # STATE PERSISTENCE
    # ============================================================
    
    def _try_load_state(self):
        """Thử load state cũ"""
        state = self.persistence.load()
        if not state:
            return
        
        try:
            # Restore links
            saved_links = state.get("links", [])
            for link in saved_links:
                if isinstance(link, list) and len(link) == 2:
                    self.links.add(tuple(link))
            
            print(f"[Coordinator] 📂 Loaded {len(saved_links)} links from state")
        except Exception as e:
            print(f"[Coordinator] ⚠️ Load state error: {e}")
    
    def _get_state_for_save(self) -> dict:
        """Lấy state để save (bao gồm events cho web UI)"""
        return {
            "timestamp": datetime.now().isoformat(),
            "sandboxes": {
                sid: {
                    "name": data["instance"].NAME if "instance" in data else sid,
                    "state": self.states.get(sid, SandboxState.HEALTHY).value,
                    "restart_count": data.get("restart_count", 0),
                    "last_heartbeat": data.get("last_heartbeat"),
                }
                for sid, data in self.sandboxes.items()
            },
            "links": [list(link) for link in self.links if link[0] < link[1]],
            "restart_attempts": self.restart_attempts,
            "events": self.event_log[-100:],
            "stats": self.get_stats(),
        }
    
    # ============================================================
    # REGISTRATION
    # ============================================================
    
    def register_sandbox(
        self,
        sandbox_id: str,
        instance: BaseSandbox,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Đăng ký sandbox mới"""
        if sandbox_id in self.sandboxes:
            print(f"[Coordinator] ⚠️ Sandbox {sandbox_id} đã tồn tại")
            return False
        
        self.sandboxes[sandbox_id] = {
            "id": sandbox_id,
            "instance": instance,
            "registered_at": datetime.now().isoformat(),
            "last_heartbeat": time.time(),
            "restart_count": 0,
            "metadata": metadata or {},
        }
        self.states[sandbox_id] = SandboxState.HEALTHY
        self.missed_heartbeats[sandbox_id] = 0
        self.restart_attempts[sandbox_id] = 0
        self._next_heartbeats[sandbox_id] = time.time() + self.config.HEARTBEAT_INTERVAL_BASE
        
        self._log_event("register", sandbox_id, f"Registered {instance.NAME}")
        print(f"[Coordinator] ✅ Registered: {sandbox_id} ({instance.NAME})")
        return True
    
    def unregister_sandbox(self, sandbox_id: str) -> bool:
        """Xóa sandbox"""
        if sandbox_id not in self.sandboxes:
            return False
        
        # Break all links
        self._break_all_links(sandbox_id)
        
        # Remove
        del self.sandboxes[sandbox_id]
        self.states.pop(sandbox_id, None)
        self.missed_heartbeats.pop(sandbox_id, None)
        self.restart_attempts.pop(sandbox_id, None)
        self._next_heartbeats.pop(sandbox_id, None)
        
        self._log_event("unregister", sandbox_id, "Unregistered")
        print(f"[Coordinator] 🗑️ Unregistered: {sandbox_id}")
        return True
    
    # ============================================================
    # MESH LINKS
    # ============================================================
    
    def create_link(self, from_id: str, to_id: str) -> bool:
        """Tạo liên kết bidirectional giữa 2 sandbox"""
        if from_id not in self.sandboxes or to_id not in self.sandboxes:
            print(f"[Coordinator] ❌ Cannot link: missing sandbox")
            return False
        
        if from_id == to_id:
            return False
        
        # Check max links
        from_links = sum(1 for l in self.links if from_id in l)
        if from_links >= self.config.MAX_LINKS_PER_SANDBOX:
            print(f"[Coordinator] ⚠️ {from_id} đã đạt max links")
            return False
        
        # Add bidirectional
        self.links.add((from_id, to_id))
        self.links.add((to_id, from_id))
        self.link_states[(from_id, to_id)] = LinkState.ACTIVE
        self.link_states[(to_id, from_id)] = LinkState.ACTIVE
        
        self._log_event("link", from_id, f"Linked with {to_id}")
        print(f"[Coordinator] 🔗 Link: {from_id} ↔ {to_id}")
        return True
    
    def _break_link(self, from_id: str, to_id: str):
        """Gãy 1 link"""
        self.links.discard((from_id, to_id))
        self.link_states.pop((from_id, to_id), None)
    
    def _break_all_links(self, sandbox_id: str) -> List[Tuple[str, str]]:
        """Gãy TẤT CẢ links của 1 sandbox, trả về danh sách đã gãy"""
        broken = []
        for link in list(self.links):
            if sandbox_id in link:
                self._break_link(link[0], link[1])
                broken.append(link)
        
        if broken:
            print(f"[Coordinator] 💔 BROKE {len(broken)} links for {sandbox_id}")
            self._log_event("break_links", sandbox_id, f"Broke {len(broken)} links")
        
        return broken
    
    def _restore_links(self, sandbox_id: str, saved_links: List[Tuple[str, str]]):
        """Nối lại links"""
        restored = 0
        for (a, b) in saved_links:
            # Chỉ restore nếu cả 2 sandbox còn tồn tại
            if a in self.sandboxes and b in self.sandboxes:
                # Skip nếu sandbox kia đang DOWN
                other = b if a == sandbox_id else a
                if self.states.get(other) == SandboxState.DOWN:
                    continue
                
                self.links.add((a, b))
                self.link_states[(a, b)] = LinkState.ACTIVE
                restored += 1
        
        print(f"[Coordinator] 🔗 RESTORED {restored} links for {sandbox_id}")
        self._log_event("restore_links", sandbox_id, f"Restored {restored} links")
    
    def can_call(self, from_id: str, to_id: str) -> bool:
        """Check 2 sandbox có thể gọi nhau không"""
        if from_id not in self.sandboxes or to_id not in self.sandboxes:
            return False
        
        # Check target healthy
        if self.states.get(to_id) in (SandboxState.DOWN, SandboxState.DEAD):
            return False
        
        # Check link exists và active
        if (from_id, to_id) not in self.links:
            return False
        
        if self.link_states.get((from_id, to_id)) != LinkState.ACTIVE:
            return False
        
        return True
    
    # ============================================================
    # START / STOP
    # ============================================================
    
    async def start(self):
        """Khởi động coordinator"""
        if self._running:
            return
        
        self._running = True
        print("\n" + "=" * 60)
        print("🚀 ML MINI COORDINATOR - STARTING")
        print("=" * 60)
        
        # Start heartbeat loop
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        # Start auto-save
        self._autosave_task = asyncio.create_task(
            self.persistence.auto_save_loop(self._get_state_for_save)
        )
        
        print(f"[Coordinator] ✅ Started")
        print(f"  Heartbeat: {self.config.HEARTBEAT_INTERVAL_BASE}s (adaptive: {self.config.HEARTBEAT_INTERVAL_MIN}-{self.config.HEARTBEAT_INTERVAL_MAX}s)")
        print(f"  Reconnect delay: {self.config.RECONNECT_DELAY}s")
        print(f"  Max restarts: {self.config.MAX_RESTART_ATTEMPTS}")
        print()
    
    async def stop(self):
        """Dừng coordinator"""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel tasks
        for task in [self._heartbeat_task, self._autosave_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Stop auto-save
        self.persistence.stop_auto_save()
        
        # Save final state
        await self.persistence.save(self._get_state_for_save())
        
        print("[Coordinator] ⏹️ Stopped")
    
    # ============================================================
    # HEARTBEAT LOOP (ADAPTIVE)
    # ============================================================
    
    async def _heartbeat_loop(self):
        """Vòng lặp heartbeat - adaptive interval"""
        while self._running:
            try:
                now = time.time()
                
                # Check mỗi sandbox theo lịch riêng
                for sandbox_id in list(self.sandboxes.keys()):
                    if now >= self._next_heartbeats.get(sandbox_id, 0):
                        await self._check_sandbox_health(sandbox_id)
                        
                        # Schedule next heartbeat
                        interval = self.heartbeat.get_interval(sandbox_id)
                        self._next_heartbeats[sandbox_id] = time.time() + interval
                
                # Sleep ngắn để check lại
                await asyncio.sleep(0.5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Coordinator] ❌ Heartbeat loop error: {e}")
                await asyncio.sleep(1)
    
    async def _check_sandbox_health(self, sandbox_id: str):
        """Check 1 sandbox"""
        if sandbox_id not in self.sandboxes:
            return
        
        try:
            instance = self.sandboxes[sandbox_id]["instance"]
            is_alive = await asyncio.wait_for(
                instance.health_check(),
                timeout=5.0,
            )
            
            if is_alive:
                # Success
                self.missed_heartbeats[sandbox_id] = 0
                self.sandboxes[sandbox_id]["last_heartbeat"] = time.time()
                
                # Update heartbeat interval
                self.heartbeat.record_success(sandbox_id)
                
                # Nếu đang RECOVERING → chuyển HEALTHY
                if self.states.get(sandbox_id) == SandboxState.RECOVERING:
                    self.states[sandbox_id] = SandboxState.HEALTHY
                    self._log_event("recovered", sandbox_id, "Sandbox recovered")
                    print(f"[Coordinator] ✅ {sandbox_id} RECOVERED")
            else:
                # Miss heartbeat
                self.missed_heartbeats[sandbox_id] = self.missed_heartbeats.get(sandbox_id, 0) + 1
                self.heartbeat.record_error(sandbox_id)
                
                if self.missed_heartbeats[sandbox_id] >= self.config.MAX_MISSED_HEARTBEATS:
                    await self._handle_sandbox_down(sandbox_id)
        
        except asyncio.TimeoutError:
            self.missed_heartbeats[sandbox_id] = self.missed_heartbeats.get(sandbox_id, 0) + 1
            self.heartbeat.record_error(sandbox_id)
            print(f"[Coordinator] ⏱️ {sandbox_id} timeout")
            
            if self.missed_heartbeats[sandbox_id] >= self.config.MAX_MISSED_HEARTBEATS:
                await self._handle_sandbox_down(sandbox_id)
        
        except Exception as e:
            print(f"[Coordinator] ❌ Health check error for {sandbox_id}: {e}")
            self.missed_heartbeats[sandbox_id] = self.missed_heartbeats.get(sandbox_id, 0) + 1
            self.heartbeat.record_error(sandbox_id)
    
    # ============================================================
    # HANDLE SANDBOX DOWN (CIRCUIT BREAKER)
    # ============================================================
    
    async def _handle_sandbox_down(self, sandbox_id: str):
        """Xử lý khi sandbox sụp"""
        
        # Check nếu đã DOWN rồi
        if self.states.get(sandbox_id) in (SandboxState.DOWN, SandboxState.DEAD):
            return
        
        old_state = self.states.get(sandbox_id, SandboxState.HEALTHY)
        self.states[sandbox_id] = SandboxState.DOWN
        
        print(f"\n{'=' * 60}")
        print(f"🚨 SANDBOX DOWN: {sandbox_id}")
        print(f"{'=' * 60}")
        self._log_event("down", sandbox_id, f"Sandbox down (was {old_state.value})")
        
        # 1. GÃY tất cả links (Circuit Breaker)
        broken_links = self._break_all_links(sandbox_id)
        self.sandboxes[sandbox_id]["saved_links"] = broken_links
        
        # 2. Notify neighbors
        self._notify_neighbors(sandbox_id, "down")
        
        # 3. Check max restart attempts
        attempts = self.restart_attempts.get(sandbox_id, 0)
        if attempts >= self.config.MAX_RESTART_ATTEMPTS:
            print(f"[Coordinator] ❌ {sandbox_id} exceeded max restarts → DEAD")
            self.states[sandbox_id] = SandboxState.DEAD
            self._log_event("dead", sandbox_id, f"Exceeded {attempts} restarts")
            return
        
        # 4. Trigger restart (self-healing) - async
        asyncio.create_task(self._restart_sandbox(sandbox_id))
    
    async def _restart_sandbox(self, sandbox_id: str):
        """Restart sandbox sau RECONNECT_DELAY"""
        
        # Increment attempts
        self.restart_attempts[sandbox_id] = self.restart_attempts.get(sandbox_id, 0) + 1
        attempts = self.restart_attempts[sandbox_id]
        
        # Backoff delay
        backoff = self.config.RESTART_BACKOFF_BASE * attempts
        wait_time = max(self.config.RECONNECT_DELAY, backoff)
        
        print(f"[Coordinator] 🔄 {sandbox_id} - Restart #{attempts} in {wait_time}s...")
        self._log_event("restart_scheduled", sandbox_id, f"Restart #{attempts} in {wait_time}s")
        
        await asyncio.sleep(wait_time)
        
        if not self._running:
            return
        
        try:
            self.states[sandbox_id] = SandboxState.RESTARTING
            instance = self.sandboxes[sandbox_id]["instance"]
            
            success = await instance.restart()
            
            if success:
                self.states[sandbox_id] = SandboxState.RECOVERING
                self.missed_heartbeats[sandbox_id] = 0
                self.sandboxes[sandbox_id]["restart_count"] += 1
                
                # Restore links
                saved = self.sandboxes[sandbox_id].get("saved_links", [])
                self._restore_links(sandbox_id, saved)
                
                # Notify neighbors
                self._notify_neighbors(sandbox_id, "restored")
                
                # Reset restart attempts
                self.restart_attempts[sandbox_id] = 0
                
                self._log_event("restarted", sandbox_id, f"Restart #{attempts} success")
                print(f"[Coordinator] ✅ {sandbox_id} RESTORED\n")
            else:
                self.states[sandbox_id] = SandboxState.DOWN
                self._log_event("restart_failed", sandbox_id, "Restart returned False")
                
                # Retry
                if self.restart_attempts[sandbox_id] < self.config.MAX_RESTART_ATTEMPTS:
                    asyncio.create_task(self._restart_sandbox(sandbox_id))
        
        except Exception as e:
            print(f"[Coordinator] ❌ Restart error for {sandbox_id}: {e}")
            self.states[sandbox_id] = SandboxState.DOWN
            self._log_event("restart_error", sandbox_id, str(e))
    
    def _notify_neighbors(self, sandbox_id: str, event: str):
        """Thông báo các sandbox lân cận"""
        neighbors = set()
        for (a, b) in self.links:
            if a == sandbox_id:
                neighbors.add(b)
            elif b == sandbox_id:
                neighbors.add(a)
        
        # Also check saved_links (đã gãy)
        saved = self.sandboxes.get(sandbox_id, {}).get("saved_links", [])
        for (a, b) in saved:
            other = b if a == sandbox_id else a
            if other in self.sandboxes:
                neighbors.add(other)
        
        for n in neighbors:
            print(f"[Coordinator] 📢 Notify {n}: {sandbox_id} is {event}")
    
    # ============================================================
    # LOGGING
    # ============================================================
    
    def _log_event(self, event_type: str, sandbox_id: str, message: str):
        """Log event"""
        entry = {
            "time": datetime.now().isoformat(),
            "type": event_type,
            "sandbox": sandbox_id,
            "message": message,
        }
        self.event_log.append(entry)
        
        # Trim log
        if len(self.event_log) > self.max_log:
            self.event_log = self.event_log[-self.max_log:]
    
    # ============================================================
    # INFO
    # ============================================================
    
    def get_status(self) -> dict:
        """Trạng thái toàn hệ thống"""
        return {
            "running": self._running,
            "total_sandboxes": len(self.sandboxes),
            "total_links": len(self.links) // 2,  # /2 vì bidirectional
            "states": {sid: self.states[sid].value for sid in self.sandboxes},
            "sandboxes": {
                sid: {
                    "name": data["instance"].NAME,
                    "state": self.states[sid].value,
                    "restart_count": data["restart_count"],
                    "missed_heartbeats": self.missed_heartbeats.get(sid, 0),
                    "restart_attempts": self.restart_attempts.get(sid, 0),
                    "heartbeat_interval": self.heartbeat.get_interval(sid),
                }
                for sid, data in self.sandboxes.items()
            },
            "links": [list(link) for link in self.links if link[0] < link[1]],  # Chỉ 1 chiều
            "heartbeat_stats": self.heartbeat.get_stats(),
            "persistence": self.persistence.get_info(),
        }
    
    def get_stats(self) -> dict:
        """Stats tổng quan"""
        return {
            "total_sandboxes": len(self.sandboxes),
            "total_links": len(self.links) // 2,
            "healthy": sum(1 for s in self.states.values() if s == SandboxState.HEALTHY),
            "down": sum(1 for s in self.states.values() if s == SandboxState.DOWN),
            "recovering": sum(1 for s in self.states.values() if s == SandboxState.RECOVERING),
            "dead": sum(1 for s in self.states.values() if s == SandboxState.DEAD),
        }
    
    def get_event_log(self, limit: int = 50) -> List[dict]:
        """Lấy event log"""
        return self.event_log[-limit:]
    
    # ============================================================
    # MANUAL CONTROLS
    # ============================================================
    
    async def force_restart(self, sandbox_id: str) -> bool:
        """Force restart 1 sandbox"""
        if sandbox_id not in self.sandboxes:
            return False
        
        self.states[sandbox_id] = SandboxState.DOWN
        broken = self._break_all_links(sandbox_id)
        self.sandboxes[sandbox_id]["saved_links"] = broken
        self.restart_attempts[sandbox_id] = 0
        
        await self._restart_sandbox(sandbox_id)
        return True
    
    def mark_sandbox_healthy(self, sandbox_id: str) -> bool:
        """Đánh dấu sandbox healthy (manual)"""
        if sandbox_id not in self.sandboxes:
            return False
        
        self.states[sandbox_id] = SandboxState.HEALTHY
        self.missed_heartbeats[sandbox_id] = 0
        self.restart_attempts[sandbox_id] = 0
        
        # Restore links
        saved = self.sandboxes[sandbox_id].get("saved_links", [])
        self._restore_links(sandbox_id, saved)
        
        return True