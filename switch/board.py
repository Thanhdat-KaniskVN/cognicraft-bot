# switch/board.py
"""
Switch Board - Bảng điện trung tâm
Nơi cắm tất cả sockets + nối dây
"""
import os
from pathlib import Path
from dotenv import load_dotenv

from core import SocketRegistry, EventRouter


class SwitchBoard:
    """
    Bảng điện - Quản lý tất cả sockets + wires
    """

    def __init__(self):
        # Load env
        env_file = Path(__file__).parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)

        # Init core
        self.registry = SocketRegistry(sockets_dir="sockets")
        self.router = EventRouter(registry=self.registry)

    async def boot(self):
        """Khởi động bảng điện"""
        print("\n" + "=" * 60)
        print("🏛️  COGNICRAFT SWITCH BOARD - BOOT")
        print("=" * 60 + "\n")

        # 1. Discover sockets
        print("🔍 Step 1: Discovering sockets...")
        self.registry.discover()

        # 2. Plug sockets (from config)
        print("\n🔌 Step 2: Plugging sockets...")
        self._plug_sockets()

        # 3. Wire events
        print("\n⚡ Step 3: Wiring events...")
        self._wire_events()

        # 4. Start sockets
        print("\n🚀 Step 4: Starting sockets...")
        await self.registry.start_all()

        # 5. Show status
        print("\n" + "=" * 60)
        print("📊 BOARD STATUS")
        print("=" * 60)
        for info in self.registry.list_all():
            status_icon = {
                "on": "🟢",
                "off": "⚪",
                "error": "🔴",
                "warning": "🟠",
                "starting": "🟡",
                "disabled": "⚫",
            }.get(info["status"], "❓")
            print(f"  {status_icon} {info['name']:20s} v{info['version']} – {info['status']}")

        print("\n" + "=" * 60)
        print("✅ SWITCH BOARD READY")
        print("=" * 60 + "\n")

    def _plug_sockets(self):
        """Cắm sockets vào board (theo config)"""
        # Plug Google Calendar
        if Path(__file__).parent.joinpath("credentials.json").exists():
            self.registry.register("google_calendar", config={
                "credentials_file": str(Path(__file__).parent / "credentials.json"),
                "token_file": str(Path(__file__).parent / "token.json"),
                "calendar_id": os.getenv("GOOGLE_CALENDAR_ID", "primary"),
            })
        else:
            print("[Board] ⚠️ Google Calendar skipped (no credentials.json)")

        # Plug Cogni Bot
        db_path = os.getenv("BOT_DB_PATH", "../scores.db")
        self.registry.register("cogni_bot", config={"db_path": db_path})
        # ✅ ML Socket
        try:
            self.registry.register("ml_sandbox", config={})
            print("[Board] 🔌 ML Sandbox plugged")
        except Exception as e:
            print(f"[Board] ⚠️ ML Sandbox skipped: {e}")

    def _wire_events(self):
        """Nối dây giữa các sockets"""
        # Wire 1: CogniBot score.confirmed → GoogleCalendar add_event
        def score_to_event(payload):
            member = payload.get("member", "?")
            week = payload.get("week", "?")
            total = payload.get("total", "?")
            return {
                "title": f"✅ W{week}: {member} – {total}/5",
                "date": payload.get("date") or __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
                "description": f"Điểm: {total}/5 (tuần {week})",
            }

        self.router.wire(
            event_name="cogni.score.confirmed",
            socket_name="google_calendar",
            action="add_event",
            transform=score_to_event,
        )
        # ✅ Wire 3: ML anomaly → Google Calendar
        def ml_anomaly_to_event(payload):
            member = payload.get("member", "?")
            anomalies = payload.get("anomalies", [])
            desc = "\n".join(f"- {a.get('message', '')[:100]}" for a in anomalies[:3])
            return {
                "title": f"🚨 ML Alert: {member}",
                "date": __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
                "description": f"Phát hiện {len(anomalies)} bất thường:\n{desc}",
            }

        self.router.wire(
            event_name="ml.anomaly.detected",
            socket_name="google_calendar",
            action="add_event",
            transform=ml_anomaly_to_event,
        )

        # ✅ Wire 4: ML prediction → Google Calendar
        def ml_prediction_to_event(payload):
            member = payload.get("member", "?")
            predictions = payload.get("predictions", [])
            next_pred = predictions[0].get("predicted_score", "?") if predictions else "?"
            return {
                "title": f"🔮 ML Prediction: {member} → {next_pred}/5",
                "date": __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
                "description": f"Dự đoán tuần tới: {next_pred}/5",
            }

        self.router.wire(
            event_name="ml.prediction.ready",
            socket_name="google_calendar",
            action="add_event",
            transform=ml_prediction_to_event,
        )
        # Wire 2: CogniBot deadline.reminder → GoogleCalendar add_event
        def deadline_to_event(payload):
            return {
                "title": f"⏰ Deadline: {payload.get('member')} – W{payload.get('week')}",
                "date": payload.get("date"),
                "description": "Nộp bài trước 23:59",
            }

        self.router.wire(
            event_name="cogni.deadline.reminder",
            socket_name="google_calendar",
            action="add_event",
            transform=deadline_to_event,
        )

    async def shutdown(self):
        """Tắt bảng điện"""
        print("\n[Board] Shutting down...")
        await self.registry.stop_all()