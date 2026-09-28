# ml_mini/test_phase2.py
"""
PHASE 2 TEST - Real Sandboxes
"""
import asyncio
from ml_mini.coordinator import SandboxCoordinator
from ml_mini.sandbox import (
    ScorePredictorSandbox,
    AnomalyDetectorSandbox,
    TokenPredictorSandbox,
)


async def main():
    print("\n" + "=" * 70)
    print("🧪 ML MINI PHASE 2 - REAL SANDBOXES TEST")
    print("=" * 70)
    
    coord = SandboxCoordinator()
    
    # Register 3 real sandboxes
    score = ScorePredictorSandbox()
    anomaly = AnomalyDetectorSandbox()
    token = TokenPredictorSandbox()
    
    coord.register_sandbox("score", score)
    coord.register_sandbox("anomaly", anomaly)
    coord.register_sandbox("token", token)
    
    coord.create_link("score", "anomaly")
    coord.create_link("anomaly", "token")
    
    await coord.start()
    await asyncio.sleep(2)
    
    # ============================================================
    # TEST 1: Score Predictor
    # ============================================================
    print("\n" + "=" * 70)
    print("📊 TEST 1: Score Predictor")
    print("=" * 70)
    result = await score.run(member="DatPT", weeks_ahead=4)
    print(f"Member: {result.get('member')}")
    print(f"Current: {result.get('current_score')}")
    print(f"Trend: {result.get('trend')} (slope={result.get('slope')})")
    print(f"R²: {result.get('r2_score')}")
    print(f"Predictions:")
    for p in result.get("predictions", []):
        print(f"  W+{p['week_ahead']}: {p['predicted_score']}")
    
    # ============================================================
    # TEST 2: Anomaly Detector
    # ============================================================
    print("\n" + "=" * 70)
    print("🚨 TEST 2: Anomaly Detector")
    print("=" * 70)
    result = await anomaly.run(member="DatPT")
    print(f"Member: {result.get('member')}")
    print(f"Latest: {result.get('latest_score')}")
    print(f"Mean: {result.get('mean')} ± {result.get('std')}")
    print(f"Is anomaly: {result.get('is_anomaly')}")
    print(f"Anomaly score: {result.get('anomaly_score')}")
    if result.get("anomalies"):
        print("Anomalies found:")
        for a in result["anomalies"]:
            print(f"  [{a['severity']}] {a['type']}: {a['message']}")
    else:
        print("✅ No anomalies detected")
    
    # ============================================================
    # TEST 3: Token Predictor
    # ============================================================
    print("\n" + "=" * 70)
    print("⚡ TEST 3: Token Predictor")
    print("=" * 70)
    
    for task in ["scoring", "socratic", "quiz"]:
        result = await token.run(task_type=task, prompt_length=1500)
        print(f"\n{task}:")
        print(f"  Predicted: {result['predicted_tokens']} tokens")
        print(f"  Confidence: {result['confidence']}")
    
    # Record some actual values
    await token.record_actual("scoring", 1200)
    await token.record_actual("scoring", 1350)
    await token.record_actual("scoring", 1100)
    
    # Test accuracy
    accuracy = await token.get_accuracy("scoring")
    print(f"\nToken Accuracy: {accuracy}")
    
    # ============================================================
    # STATUS
    # ============================================================
    print("\n" + "=" * 70)
    print("📊 COORDINATOR STATUS")
    print("=" * 70)
    status = coord.get_status()
    print(f"Sandboxes: {status['total_sandboxes']}")
    print(f"Links: {status['total_links']}")
    print(f"States: {status['states']}")
    
    await coord.stop()
    
    print("\n" + "=" * 70)
    print("✅ PHASE 2 TEST HOÀN THÀNH")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())