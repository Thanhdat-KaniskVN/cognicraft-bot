# sheets_sync.py
import time
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from config import SHEET_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsSync:
    def __init__(self, max_retries=5):
        """Init SheetsSync với retry logic cho lỗi 503"""
        if not SHEET_ID:
            raise ValueError("SHEET_ID chua cau hinh trong .env")

        creds = Credentials.from_service_account_file(
            "credentials.json", scopes=SCOPES
        )
        self.client = gspread.authorize(creds)

        # Retry mở Sheet nếu gặp 503
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                self.sheet = self.client.open_by_key(SHEET_ID)
                print(f"[Sheets] Connected OK (attempt {attempt})")
                break
            except gspread.exceptions.APIError as e:
                last_error = e
                err_str = str(e)

                if "503" in err_str or "Service is currently unavailable" in err_str:
                    wait = attempt * 3
                    print(f"[Sheets] 503 unavailable, doi {wait}s... ({attempt}/{max_retries})")
                    time.sleep(wait)
                else:
                    raise
        else:
            raise RuntimeError(
                f"Khong the ket noi Google Sheets sau {max_retries} lan: {last_error}"
            )

        self._ensure_worksheets()

    def _ensure_worksheets(self):
        existing = [ws.title for ws in self.sheet.worksheets()]

        if "Scores" not in existing:
            ws = self.sheet.add_worksheet(title="Scores", rows=1000, cols=12)
            ws.append_row([
                "Tuan", "Thanh vien", "Chinh xac", "Do sau",
                "Lien ket", "Trinh bay", "Tong",
                "Tu danh gia", "Nguon", "Nguoi sua", "Thoi gian"
            ])

        if "Participation" not in existing:
            ws = self.sheet.add_worksheet(title="Participation", rows=1000, cols=5)
            ws.append_row(["Tuan", "Thanh vien", "Da nop", "Thoi gian nop", "Ghi chu"])

        if "GHS" not in existing:
            ws = self.sheet.add_worksheet(title="GHS", rows=500, cols=6)
            ws.append_row(["Tuan", "AQ", "P", "WB", "GHS", "Trang thai"])

        if "Insights" not in existing:
            ws = self.sheet.add_worksheet(title="Insights", rows=1000, cols=8)
            ws.append_row([
                "Tuan", "Member", "Topic", "Insight chinh",
                "Goc nhin doc dao", "Ung dung thuc te", "Diem", "Tags"
            ])

        if "Code Vault" not in existing:
            ws = self.sheet.add_worksheet(title="Code Vault", rows=1000, cols=7)
            ws.append_row([
                "Tuan", "Member", "Topic", "Ngon ngu",
                "Code snippet", "Mo ta", "Diem"
            ])
        if "Chat Insights" not in existing:
            ws = self.sheet.add_worksheet(title="Chat Insights", rows=1000, cols=8)
            ws.append_row([
                "Tuan", "Member", "Role", "Topic", "Insight", "Type", "Timestamp", "Tags"
            ])
        if "Plans" not in existing:
            ws = self.sheet.add_worksheet(title="Plans", rows=500, cols=8)
            ws.append_row([
                "Tuan", "Mode", "Overview", "Group Tasks",
                "Member Tasks", "Warnings", "Focus Topics", "Timestamp"
            ])
    # ============ HELPER: XÓA DÒNG CŨ THEO TUẦN ============

    def _delete_week_rows(self, ws, week):
        """Xóa tất cả dòng có cột A = week"""
        all_values = ws.get_all_values()
        rows_to_delete = []
        week_str = str(week)

        for i, row in enumerate(all_values[1:], start=2):
            if row and str(row[0]) == week_str:
                rows_to_delete.append(i)

        # Xóa từ dưới lên để không lệch index
        for row_idx in reversed(rows_to_delete):
            ws.delete_rows(row_idx)

        return len(rows_to_delete)

    # ============ SCORES ============

    def sync_scores(self, week_scores):
        if not week_scores:
            return

        ws = self.sheet.worksheet("Scores")
        week = week_scores[0].get("week", "")

        # Xóa dòng cũ của tuần này
        deleted = self._delete_week_rows(ws, week)
        if deleted > 0:
            print(f"[Sheets] Deleted {deleted} old score rows")

        # Ghi dòng mới
        rows = []
        for s in week_scores:
            rows.append([
                s.get("week", ""),
                s.get("member", ""),
                s.get("accuracy", 0),
                s.get("depth", 0),
                s.get("connection", 0),
                s.get("presentation", 0),
                s.get("total", 0),
                s.get("self_score", ""),
                s.get("source", ""),
                s.get("changed_by", ""),
                str(s.get("created_at", "")),
            ])

        if rows:
            ws.append_rows(rows)
            print(f"[Sheets] Synced {len(rows)} scores for week {week}")

    # ============ PARTICIPATION ============

    def sync_participation(self, week, participation):
        if not participation:
            return

        ws = self.sheet.worksheet("Participation")

        # ✅ FIX: XÓA dòng cũ của tuần này trước khi ghi
        deleted = self._delete_week_rows(ws, week)
        if deleted > 0:
            print(f"[Sheets] Deleted {deleted} old participation rows")

        # Ghi dòng mới
        rows = []
        for p in participation:
            rows.append([
                week,
                p.get("member", ""),
                "Co" if p.get("submitted") else "Khong",
                str(p.get("submitted_at", "")),
                ""
            ])

        if rows:
            ws.append_rows(rows)
            print(f"[Sheets] Synced {len(rows)} participation")

    # ============ GHS ============

    def sync_ghs(self, week, aq, p_score, wb, ghs):
        ws = self.sheet.worksheet("GHS")

        # ✅ FIX: XÓA dòng cũ của tuần này trước khi ghi
        deleted = self._delete_week_rows(ws, week)
        if deleted > 0:
            print(f"[Sheets] Deleted {deleted} old GHS rows")

        # Ghi dòng mới
        status = "Healthy" if ghs >= 4.0 else ("Warning" if ghs >= 3.0 else "Critical")
        ws.append_row([
            week,
            round(aq, 2),
            round(p_score, 2),
            round(wb, 2),
            round(ghs, 2),
            status
        ])
        print(f"[Sheets] Synced GHS week {week}: {ghs}")

    # ============ INSIGHTS ============

    def sync_insights(self, week, member, topic, extracted, score):
        ws = self.sheet.worksheet("Insights")

        # Xóa dòng cũ của member này trong tuần này
        all_values = ws.get_all_values()
        rows_to_delete = []
        for i, row in enumerate(all_values[1:], start=2):
            if (row and str(row[0]) == str(week) and
                len(row) > 1 and row[1] == member):
                rows_to_delete.append(i)

        for row_idx in reversed(rows_to_delete):
            ws.delete_rows(row_idx)

        # Ghi dòng mới
        insights_list = extracted.get("insights", [])
        insights_text = " • ".join(insights_list) if insights_list else ""

        ws.append_row([
            week,
            member,
            topic,
            insights_text,
            extracted.get("unique_perspective", ""),
            extracted.get("real_world_application", ""),
            score,
            "",
        ])
        print(f"[Sheets] Synced insights for {member}")

    def load_insights(self, topic_filter=None, limit=20):
        try:
            ws = self.sheet.worksheet("Insights")
            all_rows = ws.get_all_records()

            if topic_filter:
                filtered = [
                    r for r in all_rows
                    if topic_filter.lower() in str(r.get("Topic", "")).lower()
                ]
                return filtered[:limit]
            return all_rows[:limit]
        except Exception as e:
            print(f"[Sheets] load_insights error: {e}")
            return []
    # ============ CHAT INSIGHTS ============

    def sync_chat_insight(self, week, member, role, topic, content, insight_type):
        """Sync chat insight lên tab Chat Insights"""
        ws = self.sheet.worksheet("Chat Insights")

        ws.append_row([
            week,
            member,
            role,
            topic,
            content,
            insight_type,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "",
        ])
        print(f"[Sheets] Synced chat insight for {member}")

    def load_chat_insights(self, member=None, limit=20):
        """Đọc chat insights"""
        try:
            ws = self.sheet.worksheet("Chat Insights")
            all_rows = ws.get_all_records()

            if member:
                filtered = [
                    r for r in all_rows
                    if str(r.get("Member", "")).lower() == member.lower()
                ]
                return filtered[-limit:]

            return all_rows[-limit:]
        except Exception as e:
            print(f"[Sheets] load_chat_insights error: {e}")
            return []
    # ============ CODE VAULT ============

    def sync_code_vault(self, week, member, topic, extracted, score):
        code = extracted.get("code_snippet", "").strip()
        if not code:
            return  # Không có code → bỏ qua

        ws = self.sheet.worksheet("Code Vault")

        # Xóa dòng cũ của member này trong tuần này
        all_values = ws.get_all_values()
        rows_to_delete = []
        for i, row in enumerate(all_values[1:], start=2):
            if (row and str(row[0]) == str(week) and
                len(row) > 1 and row[1] == member):
                rows_to_delete.append(i)

        for row_idx in reversed(rows_to_delete):
            ws.delete_rows(row_idx)

        # Ghi dòng mới
        ws.append_row([
            week,
            member,
            topic,
            extracted.get("code_language", "unknown"),
            code[:500],
            extracted.get("unique_perspective", ""),
            score,
        ])
        print(f"[Sheets] Synced code for {member}")

    def load_code_vault(self, topic_filter=None, limit=20):
        try:
            ws = self.sheet.worksheet("Code Vault")
            all_rows = ws.get_all_records()

            if topic_filter:
                filtered = [
                    r for r in all_rows
                    if topic_filter.lower() in str(r.get("Topic", "")).lower()
                ]
                return filtered[:limit]
            return all_rows[:limit]
        except Exception as e:
            print(f"[Sheets] load_code_vault error: {e}")
            return []
            # ============ PLANS ============

    def sync_plan(self, week, mode, plan):
        """Sync plan lên tab Plans"""
        ws = self.sheet.worksheet("Plans")

        ws.append_row([
            week,
            mode,
            plan.get("overview", "")[:500],
            " | ".join(plan.get("group_tasks", [])),
            json.dumps(plan.get("member_tasks", {}), ensure_ascii=False)[:1000],
            " | ".join(plan.get("warnings", [])),
            " | ".join(plan.get("focus_topics", [])),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ])
        print(f"[Sheets] Synced plan for week {week}")

    def load_plans(self, limit=10):
        """Đọc plans"""
        try:
            ws = self.sheet.worksheet("Plans")
            all_rows = ws.get_all_records()
            return all_rows[-limit:]
        except Exception as e:
            print(f"[Sheets] load_plans error: {e}")
            return []