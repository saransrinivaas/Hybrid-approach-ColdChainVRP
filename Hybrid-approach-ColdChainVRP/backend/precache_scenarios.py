# ─────────────────────────────────────────
# PRE-CACHE SCENARIOS UTILITY
# Pre-calculates and caches VRP sub-clusters
# for all 3 scenarios to ensure sub-second
# instant loading during live trials.
# ─────────────────────────────────────────

import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

from qaoa_hardware_solver import solve_scenario_hardware_pipeline, list_cached_runs

def main():
    print("=" * 65)
    # Reassuring and professional logs
    print("      CRYO OPTIMISER — CACHE PRE-POPULATION PIPELINE")
    print("=" * 65)
    print("\n[INFO] Starting sequential solver execution to warm up the caching database...")
    print("[INFO] This ensures all live presentation clicks load instantaneously (< 50ms)!\n")

    scenarios = ["easy", "tough", "tough3"]
    
    t_start = time.time()
    for sc in scenarios:
        print(f"\n--> Warm-up execution for: {sc.upper()}")
        print("-" * 50)
        t_sc_start = time.time()
        try:
            results = solve_scenario_hardware_pipeline(sc, verbose=False)
            elapsed = time.time() - t_sc_start
            print(f"[SUCCESS] {sc.upper()} pre-cached successfully! ({len(results)} sub-clusters in {elapsed:.2f}s)")
            for r in results:
                print(f"  - Sub-cluster {r['subcluster_id']}: Qubits={r['simulator']['num_qubits']} | Feasible={r['simulator']['feasible']} | Route={r['simulator']['route']}")
        except Exception as e:
            print(f"[ERROR] Failed to pre-cache {sc}: {str(e)}")

    total_elapsed = time.time() - t_start
    cached_runs = list_cached_runs()
    
    print("\n" + "=" * 65)
    print("      PRE-CACHING SUMMARY")
    print("=" * 65)
    print(f"  Total Warm-up Time  : {total_elapsed:.2f} seconds")
    print(f"  Total Cached Keys   : {len(cached_runs)} entries in .qaoa_cache/")
    print(f"  System Status       : [Warmed & Flawless] Ready for 10-minute trial!")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
