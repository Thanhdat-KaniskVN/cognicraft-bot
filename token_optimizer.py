# token_optimizer.py
"""
Token Optimizer v3.1 - Smart Token Router + ML
- Task classification (CRITICAL/HIGH/NORMAL/LOW)
- Context analysis (time, history, demand, deadline)
- Smart allocation (reserve + distribute)
- Turbo amplifier (ECO/NORMAL/TURBO/HYPER)
- ML blend (70% ML + 30% rule-based)
- Feedback loop (learn + predict)
"""
import json
import os
import re
import asyncio
import time
from datetime import datetime, date, timedelta
from typing import Dict, Optional
from config import CACHE_DIR


# ============================================================
# PRIORITY LEVELS
# ============================================================

PRIORITY_CRITICAL = "CRITICAL"
PRIORITY_HIGH = "HIGH"
PRIORITY_NORMAL = "NORMAL"
PRIORITY_LOW = "LOW"


class TokenOptimizer:
    """Smart Token Router - Tự động phân luồng token + ML blend"""

    # ============================================================
    # TASK PRIORITY MAPPING
    # ============================================================

    TASK_PRIORITIES = {
        # CRITICAL: Deadline-driven, không thể fail
        "scoring": PRIORITY_CRITICAL,
        "coverage": PRIORITY_CRITICAL,

        # HIGH: Core functionality
        "distiller": PRIORITY_HIGH,
        "solutions": PRIORITY_HIGH,
        "code_analysis": PRIORITY_HIGH,
        "planner": PRIORITY_HIGH,

        # NORMAL: Enhancement
        "exercises": PRIORITY_NORMAL,
        "learning_report": PRIORITY_NORMAL,
        "socratic": PRIORITY_NORMAL,
        "quiz": PRIORITY_NORMAL,
        "chat": PRIORITY_NORMAL,
        "resource_recommend": PRIORITY_NORMAL,
        "progress_predict": PRIORITY_NORMAL,
        "advanced_mode": PRIORITY_NORMAL,
        "flashcard": PRIORITY_NORMAL,

        # LOW: Optional
        "ping": PRIORITY_LOW,
        "week_info": PRIORITY_LOW,
        "default": PRIORITY_NORMAL,
    }

    # ============================================================
    # TASK BUDGETS (baseline)
    # ============================================================

    TASK_BUDGETS = {
        # Tiny tasks
        "ping": {"min": 30, "optimal": 50, "max": 100},
        "week_info": {"min": 50, "optimal": 100, "max": 150},

        # Core tasks
        "scoring": {"min": 600, "optimal": 1000, "max": 1500},
        "coverage": {"min": 1500, "optimal": 2500, "max": 3500},
        "distiller": {"min": 700, "optimal": 1000, "max": 1200},
        "solutions": {"min": 1000, "optimal": 1500, "max": 2000},
        "exercises": {"min": 1200, "optimal": 1800, "max": 2500},
        "learning_report": {"min": 1500, "optimal": 2200, "max": 3000},

        # Learning tools
        "socratic": {"min": 400, "optimal": 500, "max": 800},
        "quiz": {"min": 1500, "optimal": 2500, "max": 3500},
        "chat": {"min": 500, "optimal": 800, "max": 1200},
        "flashcard": {"min": 800, "optimal": 1200, "max": 1800},
        "progress_predict": {"min": 500, "optimal": 800, "max": 1200},
        "planner": {"min": 1500, "optimal": 2200, "max": 3000},
        "advanced_mode": {"min": 1000, "optimal": 1500, "max": 2000},

        # Analysis tasks
        "code_analysis": {"min": 1000, "optimal": 2000, "max": 3000},
        "resource_recommend": {"min": 500, "optimal": 800, "max": 1200},

        # Fallback
        "default": {"min": 500, "optimal": 1000, "max": 2000},
    }

    # ============================================================
    # PRIORITY ALLOCATION
    # ============================================================

    PRIORITY_ALLOCATION = {
        PRIORITY_CRITICAL: 0.50,
        PRIORITY_HIGH: 0.30,
        PRIORITY_NORMAL: 0.15,
        PRIORITY_LOW: 0.05,
    }

    # ============================================================
    # TURBO AMPLIFIER
    # ============================================================

    TURBO_MULTIPLIERS = {
        "eco": 0.7,
        "normal": 1.0,
        "turbo": 1.5,
        "hyper": 2.0,
    }

    COMPLEXITY_KEYWORDS = {
        # CAO (1.0)
        "chứng minh": 1.0, "chung minh": 1.0, "proof": 1.0,
        "định lý": 1.0, "dinh ly": 1.0, "theorem": 1.0,
        "thuật toán": 1.0, "thuat toan": 1.0, "algorithm": 1.0,
        "độ phức tạp": 1.0, "do phuc tap": 1.0, "complexity": 1.0,
        "quy nạp": 1.0, "quy nap": 1.0, "induction": 1.0,
        "đệ quy": 1.0, "de quy": 1.0, "recursion": 1.0,
        "phản chứng": 1.0, "phan chung": 1.0, "contradiction": 1.0,

        # TRUNG BÌNH (0.5)
        "phân tích": 0.5, "phan tich": 0.5, "analysis": 0.5,
        "so sánh": 0.5, "so sanh": 0.5, "compare": 0.5,
        "tối ưu": 0.5, "toi uu": 0.5, "optimize": 0.5,
        "cấu trúc": 0.5, "cau truc": 0.5, "structure": 0.5,
        "hệ thống": 0.5, "he thong": 0.5, "system": 0.5,
        "liên kết": 0.5, "lien ket": 0.5, "connection": 0.5,
        "ứng dụng": 0.5, "ung dung": 0.5, "application": 0.5,

        # THẤP (0.3)
        "định nghĩa": 0.3, "dinh nghia": 0.3, "definition": 0.3,
        "ví dụ": 0.3, "vi du": 0.3, "example": 0.3,
        "giải thích": 0.3, "giai thich": 0.3, "explain": 0.3,
        "trình bày": 0.3, "trinh bay": 0.3, "presentation": 0.3,
    }

    # Ngân sách ngày
    DAILY_REQUEST_BUDGET = 250
    DAILY_TOKEN_BUDGET = 500_000

    def __init__(self, state_file=None):
        self.state_file = state_file or os.path.join(
            CACHE_DIR, "token_state.json"
        )
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        self.state = self._load_state()

        # ✅ ML Cache
        self._ml_cache: Dict[str, Dict] = {}
        self._ml_cache_updated: float = 0
        self._ml_enabled: bool = True
        self._ml_blend_log: list = []  # Track ML usage

    # ============================================================
    # STATE MANAGEMENT
    # ============================================================

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    if state.get("date") != str(date.today()):
                        return self._fresh_state()
                    return self._migrate(state)
            except Exception as e:
                print(f"[TokenOptimizer] Load error: {e}")
        return self._fresh_state()

    def _migrate(self, state):
        if "turbo_stats" not in state:
            state["turbo_stats"] = {"eco": 0, "normal": 0, "turbo": 0, "hyper": 0}
        if "priority_stats" not in state:
            state["priority_stats"] = {
                "CRITICAL": 0, "HIGH": 0, "NORMAL": 0, "LOW": 0
            }
        if "requests_by_task" not in state:
            state["requests_by_task"] = {}
        if "tokens_by_task" not in state:
            state["tokens_by_task"] = {}
        if "requests_used" not in state:
            state["requests_used"] = 0
        if "tokens_used" not in state:
            state["tokens_used"] = 0
        if "routing_log" not in state:
            state["routing_log"] = []
        if "ml_stats" not in state:
            state["ml_stats"] = {
                "used": 0,
                "fallback": 0,
                "total_saved": 0,
            }
        return state

    def _fresh_state(self):
        return {
            "date": str(date.today()),
            "requests_used": 0,
            "tokens_used": 0,
            "requests_by_task": {},
            "tokens_by_task": {},
            "turbo_stats": {"eco": 0, "normal": 0, "turbo": 0, "hyper": 0},
            "priority_stats": {
                "CRITICAL": 0, "HIGH": 0, "NORMAL": 0, "LOW": 0
            },
            "routing_log": [],
            "ml_stats": {
                "used": 0,
                "fallback": 0,
                "total_saved": 0,
            },
        }

    def _save_state(self):
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[TokenOptimizer] Save error: {e}")

    # ============================================================
    # TOKEN ESTIMATION
    # ============================================================

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return int(len(text) / 2.5)

    # ============================================================
    # TẦNG 1: TASK CLASSIFIER
    # ============================================================

    def classify_task(self, task_type: str) -> str:
        return self.TASK_PRIORITIES.get(task_type, PRIORITY_NORMAL)

    # ============================================================
    # TẦNG 2: CONTEXT ANALYZER
    # ============================================================

    def analyze_context(self) -> dict:
        now = datetime.now()
        weekday = now.weekday()

        days_to_sunday = (6 - weekday) % 7
        if days_to_sunday == 0:
            days_to_sunday = 7

        req_used = self.state["requests_used"]
        req_pct = req_used / self.DAILY_REQUEST_BUDGET

        top_task = None
        if self.state["requests_by_task"]:
            top_task = max(
                self.state["requests_by_task"].items(),
                key=lambda x: x[1]
            )[0]

        if days_to_sunday <= 1:
            context_mode = "deadline_week"
        elif req_pct > 0.7:
            context_mode = "low_budget"
        elif weekday == 3:
            context_mode = "scoring_day"
        elif weekday == 6:
            context_mode = "report_day"
        else:
            context_mode = "normal"

        return {
            "weekday": weekday,
            "days_to_sunday": days_to_sunday,
            "req_used": req_used,
            "req_pct": round(req_pct * 100, 1),
            "top_task": top_task,
            "context_mode": context_mode,
        }

    # ============================================================
    # TẦNG 3: SMART ALLOCATOR
    # ============================================================

    def get_priority_budget(self, priority: str) -> dict:
        total_requests = self.DAILY_REQUEST_BUDGET
        total_tokens = self.DAILY_TOKEN_BUDGET

        allocation = self.PRIORITY_ALLOCATION.get(priority, 0.15)
        priority_req_budget = int(total_requests * allocation)
        priority_token_budget = int(total_tokens * allocation)

        used_req = self.state["priority_stats"].get(priority, 0)

        return {
            "budget_requests": priority_req_budget,
            "used_requests": used_req,
            "remaining_requests": max(0, priority_req_budget - used_req),
            "budget_tokens": priority_token_budget,
            "allocation_pct": allocation * 100,
            "is_exhausted": used_req >= priority_req_budget * 0.9,
        }

    def calculate_priority_multiplier(self, priority: str, context: dict) -> float:
        base_mult = {
            PRIORITY_CRITICAL: 1.3,
            PRIORITY_HIGH: 1.15,
            PRIORITY_NORMAL: 1.0,
            PRIORITY_LOW: 0.7,
        }.get(priority, 1.0)

        mode = context["context_mode"]

        if mode == "deadline_week":
            if priority == PRIORITY_CRITICAL:
                base_mult *= 1.2
            elif priority == PRIORITY_LOW:
                base_mult *= 0.5
        elif mode == "low_budget":
            base_mult *= 0.7
        elif mode == "scoring_day":
            if priority in [PRIORITY_CRITICAL, PRIORITY_HIGH]:
                base_mult *= 1.1

        pbudget = self.get_priority_budget(priority)
        if pbudget["is_exhausted"]:
            base_mult *= 0.6

        return round(base_mult, 2)

    # ============================================================
    # TẦNG 4: TURBO AMPLIFIER
    # ============================================================

    def analyze_complexity(self, prompt: str) -> dict:
        if not prompt:
            return {"score": 0.0, "factors": {}, "mode": "eco"}

        prompt_lower = prompt.lower()

        # Factor 1: Độ dài
        length_score = min(len(prompt) / 10000, 1.0) * 0.3

        # Factor 2: Keywords
        keyword_score = 0
        matched_keywords = []
        for kw, weight in self.COMPLEXITY_KEYWORDS.items():
            count = prompt_lower.count(kw)
            if count > 0:
                keyword_score += weight * min(count, 3)
                matched_keywords.append(f"{kw}(x{count})")
        keyword_score = min(keyword_score / 10, 1.0) * 0.4

        # Factor 3: Cấu trúc
        paragraphs = prompt.count("\n\n")
        structure_score = min(paragraphs / 20, 1.0) * 0.15

        # Factor 4: Code
        code_patterns = [
            r"```", r"def ", r"class ", r"function ",
            r"\bfor\b", r"\bwhile\b", r"\bif\b", r"import ",
        ]
        code_count = sum(
            len(re.findall(p, prompt_lower)) for p in code_patterns
        )
        code_score = min(code_count / 10, 1.0) * 0.15

        total_score = round(
            length_score + keyword_score + structure_score + code_score,
            3
        )
        total_score = min(total_score, 1.0)

        if total_score > 0.9:
            mode = "hyper"
        elif total_score > 0.65:
            mode = "turbo"
        elif total_score >= 0.3:
            mode = "normal"
        else:
            mode = "eco"

        return {
            "score": total_score,
            "factors": {
                "length": round(length_score, 3),
                "keywords": round(keyword_score, 3),
                "structure": round(structure_score, 3),
                "code": round(code_score, 3),
            },
            "matched_keywords": matched_keywords[:10],
            "mode": mode,
        }

    # ============================================================
    # BUDGET GUARD
    # ============================================================

    def get_remaining_budget(self):
        return {
            "requests_remaining": max(
                0, self.DAILY_REQUEST_BUDGET - self.state["requests_used"]
            ),
            "tokens_remaining": max(
                0, self.DAILY_TOKEN_BUDGET - self.state["tokens_used"]
            ),
            "requests_used_pct": round(
                self.state["requests_used"] / self.DAILY_REQUEST_BUDGET * 100, 1
            ),
            "tokens_used_pct": round(
                self.state["tokens_used"] / self.DAILY_TOKEN_BUDGET * 100, 1
            ),
        }

    def should_use_minimal(self) -> bool:
        return self.state["requests_used"] >= self.DAILY_REQUEST_BUDGET * 0.9

    def should_disable_turbo(self) -> bool:
        return self.state["requests_used"] >= self.DAILY_REQUEST_BUDGET * 0.7

    # ============================================================
    # ✅ ML INTEGRATION
    # ============================================================

    async def refresh_ml_cache(self) -> bool:
        """Refresh ML predictions cache - chạy background mỗi 5 phút"""
        if not self._ml_enabled:
            return False

        try:
            from ml_mini.integration.ml_manager import get_ml_manager

            ml = get_ml_manager()

            task_types = [
                "scoring", "socratic", "quiz", "chat",
                "distiller", "exercises", "coverage",
            ]

            for task in task_types:
                try:
                    result = await ml.predict_tokens(
                        task_type=task,
                        prompt_length=1500,
                    )
                    self._ml_cache[task] = {
                        "predicted_tokens": result["predicted_tokens"],
                        "confidence": result["confidence"],
                    }
                except Exception as e:
                    print(f"[TokenOpt] ML predict {task} error: {e}")

            self._ml_cache_updated = time.time()
            print(f"[TokenOpt] ✅ ML cache updated: {len(self._ml_cache)} tasks")
            return True

        except ImportError:
            self._ml_enabled = False
            print("[TokenOpt] ML not available - using rule-based only")
            return False
        except Exception as e:
            print(f"[TokenOpt] ML refresh error: {e}")
            return False

    def _get_ml_blend(self, task_type: str, rule_based: int) -> Dict:
        """Blend ML + rule-based prediction"""
        if not self._ml_enabled or task_type not in self._ml_cache:
            return {
                "final": rule_based,
                "ml_used": False,
                "ml_tokens": 0,
                "rule_tokens": rule_based,
                "confidence": 0.0,
                "ml_weight": 0.0,
            }

        ml_data = self._ml_cache[task_type]
        ml_tokens = ml_data["predicted_tokens"]
        confidence = ml_data["confidence"]

        # Blend theo confidence
        ml_weight = 0.3 + (confidence - 0.5) * 0.8
        ml_weight = max(0.3, min(0.7, ml_weight))
        rule_weight = 1.0 - ml_weight

        final = int(ml_tokens * ml_weight + rule_based * rule_weight)

             # ✅ FIX v3.2: Clamp chặt — ML không lệch quá ±20%
        min_allowed = int(rule_based * 0.8)
        max_allowed = int(rule_based * 1.2)
        final = max(min_allowed, min(final, max_allowed))

        return {
            "final": final,
            "ml_used": True,
            "ml_tokens": ml_tokens,
            "rule_tokens": rule_based,
            "confidence": round(confidence, 2),
            "ml_weight": round(ml_weight, 2),
        }

    # ============================================================
    # ✅ CORE: SMART ROUTE (with ML)
    # ============================================================

    def optimize(
        self,
        prompt: str,
        task_type: str = "default",
        enable_turbo: bool = True,
        enable_ml: bool = True,
    ) -> dict:
        """
        Smart routing với ML blend

        Flow:
        1. Classify task → priority
        2. Analyze context → mode
        3. Allocate priority budget → multiplier
        4. Analyze complexity → turbo mode
        5. Apply → rule_based_tokens
        6. ✅ ML blend → final max_tokens
        """
        budget = self.TASK_BUDGETS.get(task_type, self.TASK_BUDGETS["default"])

        # 1. Priority classification
        priority = self.classify_task(task_type)

        # 2. Context analysis
        context = self.analyze_context()

        # 3. Base tokens theo input
        input_tokens = self.estimate_tokens(prompt)
        if input_tokens > 3000:
            base = budget["max"]
        elif input_tokens > 1500:
            base = budget["optimal"]
        elif input_tokens < 500:
            base = budget["min"]
        else:
            base = (budget["min"] + budget["optimal"]) // 2

        # 4. Complexity analysis
        complexity = self.analyze_complexity(prompt)
        complexity_mode = complexity["mode"]

        # 5. Priority multiplier
        priority_mult = self.calculate_priority_multiplier(priority, context)

        # 6. Turbo multiplier
        if enable_turbo and not self.should_disable_turbo():
            turbo_mult = self.TURBO_MULTIPLIERS.get(complexity_mode, 1.0)
        else:
            turbo_mult = 1.0
            if not enable_turbo:
                complexity_mode = "disabled"
            else:
                complexity_mode = "eco"

        # 7. Combined multiplier
        combined_mult = round(priority_mult * turbo_mult, 2)

        # 8. Apply (rule-based)
        rule_based = int(base * combined_mult)

        # 9. Clamp
        max_allowed = budget["max"] * 2
        rule_based = max(budget["min"], min(rule_based, max_allowed))

        # 10. Emergency
        if self.should_use_minimal():
            rule_based = budget["min"]
            complexity_mode = "minimal"

        # 11. ✅ ML BLEND
        if enable_ml and not self.should_use_minimal():
            ml_blend = self._get_ml_blend(task_type, rule_based)
        else:
            ml_blend = {
                "final": rule_based,
                "ml_used": False,
                "ml_tokens": 0,
                "rule_tokens": rule_based,
                "confidence": 0.0,
                "ml_weight": 0.0,
            }

        final_tokens = ml_blend["final"]

        # 12. Track ML stats
        if ml_blend["ml_used"]:
            self.state["ml_stats"]["used"] += 1
            saved = rule_based - final_tokens
            if saved > 0:
                self.state["ml_stats"]["total_saved"] += saved
        else:
            self.state["ml_stats"]["fallback"] += 1

        # 13. Track stats
        if complexity_mode in self.state["turbo_stats"]:
            self.state["turbo_stats"][complexity_mode] += 1
        if priority in self.state["priority_stats"]:
            self.state["priority_stats"][priority] += 1

        # 14. Log routing
        self.state["routing_log"].append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "task": task_type,
            "priority": priority,
            "context": context["context_mode"],
            "base": base,
            "priority_mult": priority_mult,
            "turbo_mult": turbo_mult,
            "rule_based": rule_based,
            "ml_used": ml_blend["ml_used"],
            "final": final_tokens,
        })
        self.state["routing_log"] = self.state["routing_log"][-50:]

        self._save_state()

        return {
            "max_tokens": final_tokens,
            "rule_based_tokens": rule_based,
            "base_tokens": base,
            "priority": priority,
            "priority_multiplier": priority_mult,
            "turbo_multiplier": turbo_mult,
            "combined_multiplier": combined_mult,
            "mode": complexity_mode,
            "context_mode": context["context_mode"],
            "complexity": complexity,
            "context": context,
            # ✅ ML info
            "ml_used": ml_blend["ml_used"],
            "ml_tokens": ml_blend["ml_tokens"],
            "ml_confidence": ml_blend["confidence"],
            "ml_weight": ml_blend["ml_weight"],
            "reason": self._build_reason(
                priority, context, complexity_mode, combined_mult
            ),
        }

    def _build_reason(self, priority, context, turbo_mode, combined_mult):
        return (
            f"[{priority}] {context['context_mode']} | "
            f"turbo={turbo_mode} | mult={combined_mult}x"
        )

    # ============================================================
    # TRACKING
    # ============================================================

    def track_usage(self, task_type: str, input_tokens: int, output_tokens: int):
        self.state["requests_used"] += 1
        self.state["tokens_used"] += input_tokens + output_tokens

        if task_type not in self.state["requests_by_task"]:
            self.state["requests_by_task"][task_type] = 0
            self.state["tokens_by_task"][task_type] = 0

        self.state["requests_by_task"][task_type] += 1
        self.state["tokens_by_task"][task_type] += input_tokens + output_tokens

        self._save_state()

    # ============================================================
    # STATISTICS
    # ============================================================

    def get_stats(self):
        remaining = self.get_remaining_budget()
        return {
            "date": self.state["date"],
            "requests_used": self.state["requests_used"],
            "requests_remaining": remaining["requests_remaining"],
            "tokens_used": self.state["tokens_used"],
            "tokens_remaining": remaining["tokens_remaining"],
            "requests_by_task": self.state["requests_by_task"],
            "tokens_by_task": self.state["tokens_by_task"],
            "budget_pct": remaining["requests_used_pct"],
            "turbo_stats": self.state.get("turbo_stats", {}),
            "priority_stats": self.state.get("priority_stats", {}),
            "ml_stats": self.state.get("ml_stats", {}),
            "routing_log": self.state.get("routing_log", [])[-5:],
        }

    def get_ml_stats(self):
        """ML-specific stats"""
        return {
            "enabled": self._ml_enabled,
            "cache_size": len(self._ml_cache),
            "cache_updated": self._ml_cache_updated,
            "used": self.state["ml_stats"]["used"],
            "fallback": self.state["ml_stats"]["fallback"],
            "total_saved": self.state["ml_stats"]["total_saved"],
            "cache": {
                k: {
                    "tokens": v["predicted_tokens"],
                    "confidence": v["confidence"],
                }
                for k, v in self._ml_cache.items()
            },
        }

    def reset(self):
        self.state = self._fresh_state()
        self._save_state()
        print("[TokenOptimizer] State reset")


# ============================================================
# TEST BLOCK
# ============================================================

if __name__ == "__main__":
    async def main():
        opt = TokenOptimizer()

        print("=" * 70)
        print("SMART TOKEN ROUTER v3.1 - ML INTEGRATED")
        print("=" * 70)

        # 1. Test ML cache
        print("\n[TEST 1] Refresh ML cache:")
        ok = await opt.refresh_ml_cache()
        print(f"  Success: {ok}")
        print(f"  Cache size: {len(opt._ml_cache)}")

        # 2. Test optimize with ML
        print("\n[TEST 2] Optimize with ML blend:")

        tests = [
            ("ping", "Return JSON: {ok: 1}"),
            ("scoring", "Cham diem bai nop ngan."),
            ("socratic", "Sinh cau hoi Socratic ve induction."),
            ("quiz", "Sinh 5 cau hoi trac nghiem ve induction." * 10),
            ("chat", "Em khong hieu phan induction."),
        ]

        for task, prompt in tests:
            result = opt.optimize(prompt, task)

            print(f"\n{'-' * 70}")
            print(f"TASK: {task} | PRIORITY: {result['priority']}")
            print(f"{'-' * 70}")
            print(f"  Context: {result['context_mode']}")
            print(f"  Complexity: {result['complexity']['score']} ({result['mode']})")
            print(f"  Base: {result['base_tokens']}")
            print(f"  Rule-based: {result['rule_based_tokens']}")
            print(f"  ML tokens: {result.get('ml_tokens', 0)}")
            print(f"  ML used: {result['ml_used']}")
            print(f"  ML confidence: {result.get('ml_confidence', 0)}")
            print(f"  ML weight: {result.get('ml_weight', 0)}")
            print(f"  → FINAL: {result['max_tokens']} tokens")

        # 3. ML Stats
        print("\n" + "=" * 70)
        print("ML STATS")
        print("=" * 70)
        ml_stats = opt.get_ml_stats()
        print(f"  Enabled: {ml_stats['enabled']}")
        print(f"  Cache size: {ml_stats['cache_size']}")
        print(f"  Used: {ml_stats['used']}")
        print(f"  Fallback: {ml_stats['fallback']}")
        print(f"  Total saved: {ml_stats['total_saved']} tokens")

    asyncio.run(main())