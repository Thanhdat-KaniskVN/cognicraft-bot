# code_room/backend/history.py
"""
Code History - Snapshot + Undo/Redo system
Lưu snapshot mỗi lần save, cho phép restore
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict


class CodeHistory:
    """Quản lý lịch sử code"""

    def __init__(self, base_dir: Path = None):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent / "data"

        self.base_dir = Path(base_dir)
        self.snapshots_dir = self.base_dir / "snapshots"
        self.files_dir = self.base_dir / "files"

        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # FILE MANAGEMENT
    # ============================================================

    def list_files(self) -> List[str]:
        """List tất cả files"""
        return sorted([f.name for f in self.files_dir.glob("*.py")])

    def save_file(self, name: str, content: str):
        """Save file + tạo snapshot"""
        # Save file
        file_path = self.files_dir / name
        file_path.write_text(content, encoding="utf-8")

        # Tạo snapshot
        self._create_snapshot(name, content)

    def load_file(self, name: str) -> str:
        """Load file"""
        file_path = self.files_dir / name
        if not file_path.exists():
            raise FileNotFoundError(f"File không tồn tại: {name}")
        return file_path.read_text(encoding="utf-8")

    def delete_file(self, name: str):
        """Xóa file"""
        file_path = self.files_dir / name
        if file_path.exists():
            file_path.unlink()

    # ============================================================
    # SNAPSHOTS
    # ============================================================

    def _create_snapshot(self, name: str, content: str):
        """Tạo snapshot mới"""
        snapshot_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        snapshot = {
            "id": snapshot_id,
            "file": name,
            "time": datetime.now().isoformat(),
            "time_short": datetime.now().strftime("%H:%M:%S"),
            "content": content,
            "preview": content[:100].replace("\n", " ") + ("..." if len(content) > 100 else ""),
        }

        snapshot_path = self.snapshots_dir / f"{name}__{snapshot_id}.json"
        snapshot_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Cleanup: keep last 30 snapshots per file
        self._cleanup_snapshots(name, keep=30)

    def list_snapshots(self, name: str) -> List[Dict]:
        """List snapshots của 1 file"""
        snapshots = []
        for path in self.snapshots_dir.glob(f"{name}__*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                snapshots.append({
                    "id": data["id"],
                    "time": data.get("time", ""),
                    "time_short": data.get("time_short", ""),
                    "preview": data.get("preview", ""),
                })
            except Exception:
                continue

        snapshots.sort(key=lambda x: x["id"])
        return snapshots

    def get_snapshot(self, name: str, snapshot_id: str) -> str:
        """Lấy content của snapshot"""
        path = self.snapshots_dir / f"{name}__{snapshot_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Snapshot không tồn tại")
        data = json.loads(path.read_text(encoding="utf-8"))
        return data["content"]

    def undo(self, name: str) -> str:
        """Undo = lấy snapshot trước đó"""
        snapshots = self.list_snapshots(name)
        if len(snapshots) < 2:
            raise ValueError("Không có snapshot trước đó để undo")

        # Lấy snapshot thứ 2 từ cuối (bỏ snapshot hiện tại)
        prev_snapshot = snapshots[-2]
        return self.get_snapshot(name, prev_snapshot["id"])

    def _cleanup_snapshots(self, name: str, keep: int = 30):
        """Xóa snapshots cũ"""
        snapshots = sorted(
            self.snapshots_dir.glob(f"{name}__*.json"),
            key=lambda p: p.stat().st_mtime,
        )

        if len(snapshots) > keep:
            for old in snapshots[:-keep]:
                old.unlink()