# ml_mini/config.py
"""
ML Mini Config - Tất cả settings tập trung
"""
from pathlib import Path


class MLConfig:
    """Config cho ML Mini"""
    
    # ============================================================
    # PATHS
    # ============================================================
    
    BASE_DIR = Path(__file__).parent.resolve()
    BOT_ROOT = BASE_DIR.parent.resolve()
    
    STATE_DIR = BOT_ROOT / "ml_state"
    SANDBOX_LOGS_DIR = STATE_DIR / "sandbox_logs"
    MODELS_DIR = BOT_ROOT / "ml_models"
    RESULTS_DIR = BOT_ROOT / "ml_results"
    
    COORDINATOR_STATE_FILE = STATE_DIR / "coordinator_state.json"
    
    # ============================================================
    # HEARTBEAT (Adaptive)
    # ============================================================
    
    # Base interval
    HEARTBEAT_INTERVAL_BASE = 3        # 3s
    
    # Adaptive range
    HEARTBEAT_INTERVAL_MIN = 1         # Nhanh nhất: 1s (khi có lỗi)
    HEARTBEAT_INTERVAL_MAX = 15        # Chậm nhất: 15s (khi ổn định)
    
    # Ngưỡng để tăng/giảm interval
    HEARTBEAT_HEALTHY_STREAK = 5       # 5 lần OK → tăng interval
    HEARTBEAT_ERROR_THRESHOLD = 1      # 1 lỗi → giảm interval
    
    # ============================================================
    # RECOVERY
    # ============================================================
    
    RECONNECT_DELAY = 15               # 15s trước khi nối lại
    MAX_MISSED_HEARTBEATS = 2          # Sụp sau 2 lần miss
    MAX_RESTART_ATTEMPTS = 5           # Tối đa 5 lần restart
    RESTART_BACKOFF_BASE = 5           # 5s backoff cơ bản
    
    # ============================================================
    # SANDBOX
    # ============================================================
    
    SANDBOX_TIMEOUT = 60               # Timeout mỗi run (60s)
    SANDBOX_MAX_MEMORY_MB = 512        # Max memory
    SANDBOX_MAX_ERRORS = 5             # Sụp sau 5 lỗi
    
    # ============================================================
    # LOGGING
    # ============================================================
    
    LOG_LEVEL = "INFO"
    LOG_MAX_LINES = 1000               # Max log lines in memory
    LOG_ROTATE_SIZE_MB = 10            # Rotate logs khi > 10MB
    
    # ============================================================
    # PERSISTENCE
    # ============================================================
    
    AUTO_SAVE_INTERVAL = 30            # Save state mỗi 30s
    KEEP_HISTORY_DAYS = 7              # Giữ history 7 ngày
    
    # ============================================================
    # MESH
    # ============================================================
    
    MAX_LINKS_PER_SANDBOX = 10         # Max 10 links mỗi sandbox
    LINK_TIMEOUT = 30                  # Link hết hạn sau 30s không dùng
    
    @classmethod
    def ensure_dirs(cls):
        """Đảm bảo tất cả folder tồn tại"""
        for d in [
            cls.STATE_DIR,
            cls.SANDBOX_LOGS_DIR,
            cls.MODELS_DIR,
            cls.RESULTS_DIR,
        ]:
            d.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def to_dict(cls) -> dict:
        """Export config"""
        return {
            "heartbeat": {
                "base": cls.HEARTBEAT_INTERVAL_BASE,
                "min": cls.HEARTBEAT_INTERVAL_MIN,
                "max": cls.HEARTBEAT_INTERVAL_MAX,
            },
            "recovery": {
                "reconnect_delay": cls.RECONNECT_DELAY,
                "max_missed": cls.MAX_MISSED_HEARTBEATS,
                "max_restarts": cls.MAX_RESTART_ATTEMPTS,
            },
            "sandbox": {
                "timeout": cls.SANDBOX_TIMEOUT,
                "max_errors": cls.SANDBOX_MAX_ERRORS,
            },
        }


# Ensure dirs on import
MLConfig.ensure_dirs()