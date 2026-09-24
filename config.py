# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# ============ PROMPT VERSION ============
PROMPT_VERSION = "v2.6"   # Bump để invalidate caches

# ============ DISCORD ============
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
CHECKPOINT_CHANNEL = int(os.getenv("CHECKPOINT_CHANNEL", "0"))
ADMIN_REVIEW_CHANNEL = int(os.getenv("ADMIN_REVIEW_CHANNEL", "0"))
REPORT_CHANNEL = int(os.getenv("REPORT_CHANNEL", "0"))
ADMIN_ROLE = os.getenv("ADMIN_ROLE", "Admin")

# ============ AI PROVIDER ============
AI_PROVIDER = os.getenv("AI_PROVIDER", "auto")

GEMINI_API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
]
if not any(GEMINI_API_KEYS):
    legacy_key = os.getenv("GEMINI_API_KEY")
    if legacy_key:
        GEMINI_API_KEYS = [legacy_key]
GEMINI_API_KEYS = [k for k in GEMINI_API_KEYS if k]

GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# ============ MEMBERS ============
# Đã sửa: thêm Minh nếu là member G1
ALL_MEMBERS = [
    "QuanAP-NR.G1",
    "Long-NR.G1",
    "TrieuNH-NR.G1",
    "HoàngIS-NR.Guest",
    "DatPT-NR.Admin",
    # "Minh-NR.G1",  # ← Bỏ comment nếu Minh là member G1
]
# ============ BLACKLIST THREADS ============
# Threads cần bỏ qua khi collect (theo tên chính xác)
BLACKLIST_THREADS = [
    "[Tuần 3] Minh",
]
# ============ TIME GỐC (GROUND TRUTH) ============

# Ngày bắt đầu lộ trình G1
# Tuần 1: 14/09/2026 (Thứ 2) → 20/09/2026 (CN)
ROADMAP_START_DATE = (2026, 9, 14)  # Thứ 2, 14/09/2026

# Mỗi tuần = 7 ngày
WEEK_DURATION_DAYS = 7

# Break Weeks (cứ 4 tuần học → 1 tuần nghỉ)
BREAK_WEEKS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]

# Override tuần (Admin có thể set thủ công)
OVERRIDE_WEEK = None  # None = dùng công thức

# Mode của từng tuần trong chu kỳ 4 tuần
CYCLE_MODES = {
    1: "Academic",
    2: "Academic",
    3: "Research Literacy",
    4: "Project",
}

# Deadline theo SOP-Lite 2.0 (day: 0=Mon, 6=Sun)
DEADLINES = {
    "monday_goal": {"day": 0, "hour": 21, "minute": 0, "desc": "Đăng mục tiêu tuần"},
    "thursday_leave": {"day": 3, "hour": 23, "minute": 59, "desc": "Đăng ký nghỉ phép"},
    "friday_product": {"day": 4, "hour": 23, "minute": 59, "desc": "Đăng ký sản phẩm"},
    "sunday_submit": {"day": 6, "hour": 12, "minute": 0, "desc": "Nộp bài + Review"},
    "sunday_meeting": {"day": 6, "hour": 19, "minute": 0, "desc": "Họp cuối tuần"},
}

# Backward compat
START_DATE = ROADMAP_START_DATE
TIMEZONE = "Asia/Ho_Chi_Minh"

# Task scheduler
AI_SCORING_DAY = 3   # Thứ 5
REPORT_DAY = 6       # Chủ Nhật
TASK_HOUR = 20
TASK_MINUTE = 0

# ============ SCORING ============
SCORE_WEIGHTS = {
    "accuracy": 0.3,
    "depth": 0.3,
    "connection": 0.2,
    "presentation": 0.2,
}

# ============ LIMITS ============
MAX_THREAD_CONTENT = 8000
MAX_GITHUB_CONTENT = 5000
MAX_TOTAL_CONTENT = 15000
DISCORD_MSG_LIMIT = 1900

MAX_INSIGHT_LEN = 80
MAX_PERSPECTIVE_LEN = 150
MAX_APPLICATION_LEN = 150
MAX_CODE_LEN = 500

# ============ CACHE ============
CACHE_DIR = ".cache"

# ============ GOOGLE ============
SHEET_ID = os.getenv("SHEET_ID", "")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "")