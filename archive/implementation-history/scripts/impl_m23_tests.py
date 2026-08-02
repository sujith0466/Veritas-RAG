import os
import subprocess
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 23.4 Implementation (Tests)...")
    os.makedirs("tests/unit/backend/modules/intelligence", exist_ok=True)

    # 1. test_optimizer.py
    with open("tests/unit/backend/modules/intelligence/test_optimizer.py", "w") as f:
        f.write("""import pytest
from backend.modules.intelligence.services.optimizer import ThresholdOptimizer

def test_threshold_optimizer():
    optimizer = ThresholdOptimizer()
    
    res1 = optimizer.analyze_thresholds("t1", historical_false_positives=50)
    assert res1 is None
    
    res2 = optimizer.analyze_thresholds("t1", historical_false_positives=150)
    assert res2 is not None
    assert res2.recommended_value == 0.75
""")

    # 2. test_advisor.py
    with open("tests/unit/backend/modules/intelligence/test_advisor.py", "w") as f:
        f.write("""import pytest
from backend.modules.intelligence.services.advisor import IndexAdvisor

def test_index_advisor():
    advisor = IndexAdvisor()
    actions = advisor.analyze_index_health("t1", avg_latency_ms=600)
    assert len(actions) == 1
    assert "Re-cluster" in actions[0]
""")

    print("Created test files.")

    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/backend/modules/intelligence"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    print("Milestone 23.4 completed.")

if __name__ == "__main__":
    main()
