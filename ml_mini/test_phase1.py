# ml_mini/test_phase1.py
"""
PHASE 1 TEST - Coordinator với self-healing
"""
import asyncio
from ml_mini.coordinator import SandboxCoordinator
from ml_mini.sandbox.base import SandboxState
from ml_mini.sandbox.demo import (
    ScorePredictorSandbox,
    AnomalyDetectorSandbox,
    TokenPredictorSandbox,
)


async def main():
    print("\n" + "=" * 70)
    print("🧪 ML MINI PHASE 1 - FULL TEST")
    print("=" * 70)
    
    # 1. Init coordinator
    coord = SandboxCoordinator()
    
    # 2. Register 3 sandboxes
    score = ScorePredictorSandbox()
    anomaly = AnomalyDetectorSandbox()
    token = TokenPredictorSandbox()
    
    coord.register_sandbox("score", score)
    coord.register_sandbox("anomaly", anomaly)
    coord.register_sandbox("token", token)
    
    # 3. Tạo mesh: tất cả kết nối với nhau
    coord.create_link("score", "anomaly")
    coord.create_link("anomaly", "token")
    coord.create_link("token", "score")
    
    # 4. Start coordinator
    await coord.start()
    
    # 5. Chạy ổn định 5s
    print("\n[TEST 1] Hệ thống ổn định 5s...")
    await asyncio.sleep(5)
    
    status = coord.get_status()
    print(f"\n📊 STATUS:")
    print(f"  Total sandboxes: {status['total_sandboxes']}")
    print(f"  Total links: {status['total_links']}")
    print(f"  States: {status['states']}")
    
    # 6. SIMULATE: anomaly sụp
    print("\n" + "=" * 70)
    print("🚨 SIMULATE: Sandbox 'anomaly' SỤP!")
    print("=" * 70)
    anomaly._is_running = False  # Force down
    anomaly.mark_down("Simulated crash")
    
    # 7. Chờ coordinator phát hiện (khoảng 6s: 2 misses × 3s)
    print("\n[TEST 2] Chờ coordinator phát hiện (6s)...")
    await asyncio.sleep(8)
    
    status = coord.get_status()
    print(f"\n📊 Sau khi sụp:")
    print(f"  anomaly state: {status['states']['anomaly']}")
    print(f"  Links còn lại: {status['total_links']} (đã gãy)")
    print(f"  Other sandboxes vẫn chạy:")
    print(f"    score: {status['states']['score']}")
    print(f"    token: {status['states']['token']}")
    
    # 8. Test circuit breaker: các sandbox khác vẫn gọi được nhau
    print(f"\n[TEST 3] Circuit breaker check:")
    print(f"  score → token: {coord.can_call('score', 'token')}")
    print(f"  score → anomaly: {coord.can_call('score', 'anomaly')} (phải FALSE)")
    
    # 9. Chờ auto-recovery (15s reconnect delay + backoff)
    print("\n[TEST 4] Chờ auto-recovery (25s)...")
    await asyncio.sleep(25)
    
    status = coord.get_status()
    print(f"\n📊 Sau recovery:")
    print(f"  anomaly state: {status['states']['anomaly']}")
    print(f"  Links: {status['total_links']}")
    print(f"  Restart count: {status['sandboxes']['anomaly']['restart_count']}")
    
    # 10. Final check
    print("\n" + "=" * 70)
    print("📋 EVENT LOG (last 10):")
    print("=" * 70)
    for event in coord.get_event_log(10):
        print(f"  [{event['time'][11:19]}] {event['type']:20s} {event['sandbox']:10s} {event['message']}")
    
    # 11. Stats
    print("\n" + "=" * 70)
    print("📊 FINAL STATS:")
    print("=" * 70)
    stats = coord.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    # Stop
    await coord.stop()
    
    print("\n" + "=" * 70)
    print("✅ PHASE 1 TEST HOÀN THÀNH")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())