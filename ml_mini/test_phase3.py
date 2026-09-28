# ml_mini/test_phase3.py
"""
PHASE 3 TEST - Integration
"""
import asyncio
from ml_mini.integration.ml_manager import get_ml_manager


async def main():
    print("\n" + "=" * 70)
    print("🧪 ML MINI PHASE 3 - INTEGRATION TEST")
    print("=" * 70)
    
    # 1. Init manager
    manager = get_ml_manager()
    await manager.start()
    
    # 2. Test predictions
    print("\n" + "=" * 70)
    print("📊 TEST 1: Score Prediction via Manager")
    print("=" * 70)
    result = await manager.predict_score("DatPT", weeks_ahead=4)
    print(f"Member: {result.get('member')}")
    print(f"Current: {result.get('current_score')}")
    print(f"Model: {result.get('model')}")
    for p in result.get("predictions", []):
        print(f"  W+{p['week_ahead']}: {p['predicted_score']}")
    
    # 3. Test anomaly
    print("\n" + "=" * 70)
    print("🚨 TEST 2: Anomaly Detection via Manager")
    print("=" * 70)
    result = await manager.detect_anomalies("DatPT")
    print(f"Member: {result.get('member')}")
    print(f"Is anomaly: {result.get('is_anomaly')}")
    print(f"Latest: {result.get('latest_score')}")
    
    # 4. Test token prediction
    print("\n" + "=" * 70)
    print("⚡ TEST 3: Token Prediction via Manager")
    print("=" * 70)
    for task in ["scoring", "quiz", "socratic"]:
        result = await manager.predict_tokens(task, prompt_length=1500)
        print(f"{task}: {result['predicted_tokens']:,} tokens (conf={result['confidence']})")
    
    # 5. Status
    print("\n" + "=" * 70)
    print("📊 ML MANAGER STATUS")
    print("=" * 70)
    status = manager.get_status()
    print(f"Sandboxes: {status['total_sandboxes']}")
    print(f"Links: {status['total_links']}")
    print(f"States: {status['states']}")
    
    # 6. Events
    print("\n" + "=" * 70)
    print("📋 RECENT EVENTS")
    print("=" * 70)
    events = manager.get_events(5)
    for e in events:
        print(f"  [{e['time'][11:19]}] {e['type']:20s} {e['sandbox']:10s} {e['message']}")
    
    await manager.stop()
    
    print("\n" + "=" * 70)
    print("✅ PHASE 3 TEST HOÀN THÀNH")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())