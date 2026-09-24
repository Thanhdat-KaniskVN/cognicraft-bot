# ml_mini/data/loader.py
"""
Data Loader - Đọc từ scores.db và cache
"""
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional


class DataLoader:
    """Load data cho ML Mini sandboxes"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            base = Path(__file__).parent.parent.parent.resolve()
            db_path = str(base / "scores.db")
        
        self.db_path = Path(db_path)
    
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    # ============================================================
    # SCORES
    # ============================================================
    
    def get_member_scores(self, member: str) -> List[Dict]:
        """Lấy scores của 1 member"""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT week, total, accuracy, depth, connection, presentation
                   FROM scores WHERE member = ? ORDER BY week ASC""",
                (member,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    
    def get_all_members(self) -> List[str]:
        """List tất cả members"""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT member FROM scores ORDER BY member"
            ).fetchall()
            return [r["member"] for r in rows]
        finally:
            conn.close()
    
    def get_all_scores(self) -> List[Dict]:
        """Lấy TẤT CẢ scores"""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM scores ORDER BY week, member"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    
    def get_member_history(self, member: str, limit: int = 10) -> List[float]:
        """Lấy lịch sử điểm (chỉ total)"""
        scores = self.get_member_scores(member)
        totals = [s["total"] for s in scores if s["total"] is not None]
        return totals[-limit:]
    
    # ============================================================
    # STATS
    # ============================================================
    
    def get_member_stats(self, member: str) -> Optional[Dict]:
        """Stats của 1 member"""
        scores = self.get_member_scores(member)
        if not scores:
            return None
        
        totals = [s["total"] for s in scores if s["total"] is not None]
        if not totals:
            return None
        
        return {
            "member": member,
            "count": len(totals),
            "avg": round(sum(totals) / len(totals), 2),
            "min": round(min(totals), 2),
            "max": round(max(totals), 2),
            "latest": round(totals[-1], 2),
        }
    
    def get_cohort_avg_by_week(self) -> Dict[int, float]:
        """Average score theo tuần"""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT week, AVG(total) as avg_score 
                   FROM scores WHERE total IS NOT NULL 
                   GROUP BY week ORDER BY week"""
            ).fetchall()
            return {r["week"]: round(r["avg_score"], 2) for r in rows}
        finally:
            conn.close()