# ai_provider.py
"""
Abstraction layer cho AI providers.
- Hỗ trợ NHIỀU Gemini key (xoay vòng khi hết quota)
- Fallback sang DeepSeek
- Retry khi 503 UNAVAILABLE
- Timeout 60s cho mỗi call (tránh treo)
- Cache để tiết kiệm quota
- Smart Token Router v3.0: phân luồng token theo priority + context + complexity
- Validate JSON robust
"""
import json
import re
import time
import hashlib
import os
import concurrent.futures
from typing import Optional
from config import (
    AI_PROVIDER,
    GEMINI_API_KEYS,
    GEMINI_MODEL,
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    DEEPSEEK_BASE_URL,
    CACHE_DIR,
)
from token_optimizer import TokenOptimizer

# ============================================================
# CẤU HÌNH TIMEOUT
# ============================================================

GEMINI_TIMEOUT = 30
DEEPSEEK_TIMEOUT = 90

# ============================================================
# TOKEN OPTIMIZER
# ============================================================

_token_optimizer = TokenOptimizer()

# ============================================================
# CACHE
# ============================================================

AI_CACHE_DIR = os.path.join(CACHE_DIR, "ai_responses")
os.makedirs(AI_CACHE_DIR, exist_ok=True)


def _get_cache_key(prompt: str, max_tokens: int) -> str:
    return hashlib.md5(f"{prompt}|{max_tokens}".encode()).hexdigest()


def _check_cache(prompt: str, max_tokens: int) -> Optional[dict]:
    key = _get_cache_key(prompt, max_tokens)
    cache_file = os.path.join(AI_CACHE_DIR, f"{key}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"[AIProvider] Cache HIT ({key[:8]}...)")
                return data
        except Exception as e:
            print(f"[AIProvider] Cache read error: {e}")
    return None


def _save_cache(prompt: str, max_tokens: int, result: dict):
    key = _get_cache_key(prompt, max_tokens)
    cache_file = os.path.join(AI_CACHE_DIR, f"{key}.json")
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
        print(f"[AIProvider] Cache SAVED ({key[:8]}...)")
    except Exception as e:
        print(f"[AIProvider] Cache save error: {e}")


# ============================================================
# CLIENTS
# ============================================================

_gemini_clients = {}
_deepseek_client = None


def _get_gemini_client(api_key):
    global _gemini_clients
    if api_key not in _gemini_clients:
        try:
            from google import genai
            _gemini_clients[api_key] = genai.Client(api_key=api_key)
        except Exception as e:
            print(f"[AIProvider] Gemini init error: {e}")
            _gemini_clients[api_key] = None
    return _gemini_clients[api_key]


def _get_deepseek_client():
    global _deepseek_client
    if _deepseek_client is None and DEEPSEEK_API_KEY:
        try:
            from openai import OpenAI
            _deepseek_client = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,
            )
        except Exception as e:
            print(f"[AIProvider] DeepSeek init error: {e}")
    return _deepseek_client


# ============================================================
# JSON PARSER
# ============================================================

def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    cleaned = _strip_json_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


# ============================================================
# GEMINI
# ============================================================

def _call_gemini_with_key(api_key: str, prompt: str, max_tokens: int = 2000) -> str:
    client = _get_gemini_client(api_key)
    if not client:
        raise RuntimeError("Gemini client không khả dụng")

    from google.genai import types

    config_kwargs = {
        "temperature": 0,
        "max_output_tokens": max(max_tokens, 100),
        "response_mime_type": "application/json",
    }

    model_lower = GEMINI_MODEL.lower()
    if "lite" not in model_lower:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

    def _do_call():
        return client.models.generate_content(
            model=GEMINI_MODEL,
            contents=types.Part.from_text(text=prompt),
            config=types.GenerateContentConfig(**config_kwargs),
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_do_call)
        try:
            response = future.result(timeout=GEMINI_TIMEOUT)
        except concurrent.futures.TimeoutError:
            raise RuntimeError(f"Gemini call timeout sau {GEMINI_TIMEOUT}s")

    return response.text


def _call_gemini(prompt: str, max_tokens: int = 2000) -> str:
    if not GEMINI_API_KEYS:
        raise RuntimeError("Chưa cấu hình GEMINI_API_KEY_1/2")

    last_error = None

    for idx, api_key in enumerate(GEMINI_API_KEYS, start=1):
        try:
            print(f"[AIProvider] Trying Gemini key #{idx}...")
            result = _call_gemini_with_key(api_key, prompt, max_tokens)
            print(f"[AIProvider] Gemini key #{idx} OK")
            return result
        except Exception as e:
            err = str(e)
            last_error = e

            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                print(f"[AIProvider] Gemini key #{idx} QUOTA EXHAUSTED")
            elif "503" in err or "UNAVAILABLE" in err:
                print(f"[AIProvider] Gemini key #{idx} OVERLOADED (503)")
            elif "400" in err or "API key not valid" in err:
                print(f"[AIProvider] Gemini key #{idx} INVALID KEY")
            elif "404" in err or "NOT_FOUND" in err:
                print(f"[AIProvider] Gemini key #{idx} MODEL NOT FOUND")
            elif "timeout" in err.lower():
                print(f"[AIProvider] Gemini key #{idx} TIMEOUT")
            else:
                print(f"[AIProvider] Gemini key #{idx} ERROR: {err[:200]}")
            continue

    raise RuntimeError(f"Tất cả Gemini keys fail. Last: {last_error}")


# ============================================================
# DEEPSEEK
# ============================================================

def _call_deepseek(prompt: str, max_tokens: int = 2000) -> str:
    client = _get_deepseek_client()
    if not client:
        raise RuntimeError("DeepSeek client không khả dụng")

    def _do_call():
        return client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            timeout=DEEPSEEK_TIMEOUT,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_do_call)
        try:
            response = future.result(timeout=DEEPSEEK_TIMEOUT + 10)
        except concurrent.futures.TimeoutError:
            raise RuntimeError(f"DeepSeek call timeout sau {DEEPSEEK_TIMEOUT}s")

    return response.choices[0].message.content


# ============================================================
# MAIN ENTRY - SMART ROUTER v3.0
# ============================================================

def call_ai_json(
    prompt: str,
    max_tokens: int = None,
    max_retries: int = 1,
    task_type: str = "default",
) -> dict:
    """
    Gọi AI + validate JSON.
    - ✅ Smart Token Router v3.0
    - ✅ Cache check
    - ✅ Gemini (xoay vòng key) → DeepSeek fallback
    """
    # ✅ Smart Token Router v3.0
    if max_tokens is None:
        opt_result = _token_optimizer.optimize(
            prompt, task_type, enable_turbo=True
        )
        max_tokens = opt_result["max_tokens"]
        print(
            f"[AIProvider] Smart Route: {max_tokens} tokens | "
            f"{opt_result['priority']} | {opt_result['context_mode']} | "
            f"turbo={opt_result['mode']} | "
            f"mult={opt_result['combined_multiplier']}x | task={task_type}"
        )

    # ✅ Cache check
    cached = _check_cache(prompt, max_tokens)
    if cached is not None:
        return cached

    errors = []

    if AI_PROVIDER == "gemini":
        providers = [("Gemini", _call_gemini, bool(GEMINI_API_KEYS))]
    elif AI_PROVIDER == "deepseek":
        providers = [("DeepSeek", _call_deepseek, bool(DEEPSEEK_API_KEY))]
    else:
        providers = []
        if GEMINI_API_KEYS:
            providers.append(("Gemini", _call_gemini, True))
        if DEEPSEEK_API_KEY:
            providers.append(("DeepSeek", _call_deepseek, True))

    if not providers:
        raise RuntimeError("Không có provider nào được cấu hình")

    for name, caller, has_key in providers:
        if not has_key:
            errors.append(f"{name}: chưa có key")
            continue

        for attempt in range(max_retries):
            try:
                raw = caller(prompt, max_tokens)
                parsed = _extract_json(raw)

                if parsed is None:
                    errors.append(f"{name}: JSON parse failed")
                    print(f"[AIProvider] {name} JSON sai, chuyển provider khác...")
                    break

                # ✅ Save cache
                _save_cache(prompt, max_tokens, parsed)

                # ✅ Track usage
                input_tokens = _token_optimizer.estimate_tokens(prompt)
                output_tokens = _token_optimizer.estimate_tokens(raw)
                _token_optimizer.track_usage(task_type, input_tokens, output_tokens)

                return parsed

            except Exception as e:
                err = str(e)

                if "503" in err or "UNAVAILABLE" in err or "high demand" in err:
                    # KHÔNG retry nếu là 503 – để caller retry với asyncio.sleep
                    errors.append(f"{name}: 503 (không retry)")
                    print(f"[AIProvider] {name} 503, skip retry")
                    break  # Chuyển provider tiếp theo

                errors.append(f"{name}: {e}")
                print(f"[AIProvider] {name} exception: {err[:200]}")
                break
        else:
            errors.append(f"{name}: hết retry")

    raise RuntimeError(f"Tất cả providers fail: {errors}")


def call_ai_text(prompt: str, max_tokens: int = None) -> str:
    if max_tokens is None:
        opt_result = _token_optimizer.optimize(prompt, "default")
        max_tokens = opt_result["max_tokens"]

    providers = []
    if GEMINI_API_KEYS:
        providers.append(("Gemini", _call_gemini))
    if DEEPSEEK_API_KEY:
        providers.append(("DeepSeek", _call_deepseek))

    for name, caller in providers:
        try:
            return caller(prompt, max_tokens)
        except Exception as e:
            print(f"[AIProvider] {name} failed: {e}")
            continue
    raise RuntimeError("Không provider nào khả dụng")


# ============================================================
# UTILITIES
# ============================================================

def get_token_stats():
    """Lấy thống kê token usage"""
    return _token_optimizer.get_stats()


def reset_token_budget():
    """Reset token budget"""
    _token_optimizer.reset()


def clear_cache():
    """Xóa toàn bộ cache"""
    count = 0
    for filename in os.listdir(AI_CACHE_DIR):
        if filename.endswith(".json"):
            try:
                os.remove(os.path.join(AI_CACHE_DIR, filename))
                count += 1
            except Exception:
                pass
    print(f"[AIProvider] Cleared {count} cache files")
    return count


def cache_stats():
    """Thống kê cache"""
    if not os.path.exists(AI_CACHE_DIR):
        return {"files": 0, "size_mb": 0}
    files = [f for f in os.listdir(AI_CACHE_DIR) if f.endswith(".json")]
    total_size = sum(
        os.path.getsize(os.path.join(AI_CACHE_DIR, f)) for f in files
    )
    return {
        "files": len(files),
        "size_mb": round(total_size / 1024 / 1024, 2),
    }


# ============================================================
# TEST BLOCK
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("AI PROVIDER TEST - SMART ROUTER v3.0")
    print("=" * 60)
    print(f"AI_PROVIDER: {AI_PROVIDER}")
    print(f"Gemini keys: {len(GEMINI_API_KEYS)}")
    print(f"Gemini model: {GEMINI_MODEL}")
    print(f"DeepSeek: {'OK' if DEEPSEEK_API_KEY else 'CHUA CO'}")

    stats = cache_stats()
    print(f"Cache: {stats['files']} files, {stats['size_mb']} MB")

    token_stats = get_token_stats()
    print(f"Token budget: {token_stats['requests_used']}/{token_stats['requests_used'] + token_stats['requests_remaining']} requests")
    print()

    print("-" * 60)
    print("Test 1: Scoring task (input ngắn)")
    print("-" * 60)
    try:
        result = call_ai_json(
            'Return JSON: {"score": 4.5, "reason": "good"}',
            task_type="scoring",
        )
        print(f"✅ SUCCESS: {result}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    print()
    print("-" * 60)
    print("Test 2: Ping task (input rất ngắn)")
    print("-" * 60)
    try:
        result = call_ai_json(
            'Return JSON: {"ok": 1}',
            task_type="ping",
        )
        print(f"✅ SUCCESS: {result}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

    print()
    print("-" * 60)
    print("STATS AFTER TESTS")
    print("-" * 60)
    final_stats = get_token_stats()
    print(f"Requests used: {final_stats['requests_used']}")
    print(f"Tokens used: {final_stats['tokens_used']}")
    print(f"Budget used: {final_stats['budget_pct']}%")
    if final_stats['requests_by_task']:
        print(f"By task:")
        for task, count in final_stats['requests_by_task'].items():
            print(f"  {task}: {count} requests")
    if final_stats.get('priority_stats'):
        print(f"Priority stats: {final_stats['priority_stats']}")