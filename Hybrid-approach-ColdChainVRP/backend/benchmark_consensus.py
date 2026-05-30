"""
Benchmark: QAOA-dominant consensus (current) vs Urgency-dominant consensus (proposed)
Runs the full stitch_and_repair pipeline on all 3 scenarios with both variants.
Decision: keep whichever gives lower total cost (distance + spoilage).
"""
import sys, os, functools, importlib
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

BACKEND = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND)

import stitching_repair as sr
original_build_consensus_route = sr.build_consensus_route

# ─────────────────────────────────────────────────────────────
# PROPOSED: Urgency-dominant consensus (QAOA as tiebreaker only)
# ─────────────────────────────────────────────────────────────
def build_consensus_route_URGENCY(sub_results: list, all_clinic_ids: list) -> list:
    """
    Urgency ordering is PRIMARY.
    QAOA votes only override when > 80% of sub-clusters agree.
    """
    n = len(all_clinic_ids)
    if n <= 1: return list(all_clinic_ids)
    if n == 2:
        a, b = all_clinic_ids
        return [a, b] if sr.DISTANCE_MATRIX[0][a] <= sr.DISTANCE_MATRIX[0][b] else [b, a]

    def spoilage_urgency(cid):
        return sum(
            sr.SPOILAGE[t]["alpha"] * sr.SPOILAGE[t]["value"] * sr.DEMANDS[cid][t]
            for t in ("frozen", "chilled", "ambient")
        )

    # Build QAOA pairwise vote matrix
    pref = {(a, b): 0.0 for a in all_clinic_ids for b in all_clinic_ids if a != b}
    for res in sub_results:
        route = res.get("route", [])
        if not route or None in route or not res.get("feasible"):
            continue
        weight = 1.0 if res.get("repaired") else 3.0
        for i in range(len(route)):
            for j in range(i + 1, len(route)):
                key = (route[i], route[j])
                if key in pref:
                    pref[key] += weight

    n_subclusters = len([r for r in sub_results if r.get("feasible")])
    threshold = n_subclusters * 0.8  # 80% agreement to override urgency

    def compare(a, b):
        ab = pref.get((a, b), 0.0)
        ba = pref.get((b, a), 0.0)
        # Only use QAOA vote if strong agreement
        if ab > threshold and ab > ba:
            return -1
        if ba > threshold and ba > ab:
            return 1
        # Fall back to urgency
        sa, sb = spoilage_urgency(a), spoilage_urgency(b)
        if abs(sa - sb) > 1e-9:
            return -1 if sa > sb else 1
        return -1 if sr.DISTANCE_MATRIX[0][a] <= sr.DISTANCE_MATRIX[0][b] else 1

    return sorted(all_clinic_ids, key=functools.cmp_to_key(compare))


# ─────────────────────────────────────────────────────────────
# CURRENT: QAOA-dominant consensus (original)
# ─────────────────────────────────────────────────────────────
def build_consensus_route_QAOA(sub_results: list, all_clinic_ids: list) -> list:
    """Original: QAOA pairwise votes are primary, urgency is tiebreaker."""
    return original_build_consensus_route(sub_results, all_clinic_ids)


# ─────────────────────────────────────────────────────────────
# Run pipeline with a swapped consensus function
# ─────────────────────────────────────────────────────────────
def run_with_consensus(sc_module, consensus_fn, label):
    """Reload stitching_repair against the given scenario, then run."""
    # Patch module globals to point to the given scenario
    sr.CLINICS         = sc_module.CLINICS
    sr.DEPOT           = sc_module.DEPOT
    sr.DISTANCE_MATRIX = sc_module.DISTANCE_MATRIX
    sr.DEMANDS         = sc_module.DEMANDS
    sr.SPOILAGE        = sc_module.SPOILAGE
    sr.AVG_SPEED_KMH   = sc_module.AVG_SPEED_KMH
    sr.AVG_SPEED       = sc_module.AVG_SPEED_KMH
    sr.ALL_CLINICS     = [c["id"] for c in sc_module.CLINICS]

    # Patch the consensus function
    original = sr.build_consensus_route
    sr.build_consensus_route = consensus_fn
    try:
        # Import and run the classical pipeline to get QAOA-like cluster structure
        import classical_solver
        importlib.reload(classical_solver)
        result = classical_solver.solve_scenario(sc_module)
        # We need the QAOA pipeline's sub-cluster structure
        # So instead run the actual pipeline module
        import pipeline
        importlib.reload(pipeline)
        qaoa_out = pipeline.run_pipeline(sc_module)
        out = sr.stitch_and_repair(qaoa_out)
    except Exception as e:
        print(f"  ERROR in {label}: {e}")
        out = {"total_distance": 9999, "total_spoilage": 9999, "total_cost": 99999}
    finally:
        sr.build_consensus_route = original

    return out


def run_benchmark_via_solver(sc_module, scenario_name):
    """
    Use the hybrid solver (which goes through the full QAOA pipeline)
    but swap the consensus function before calling stitch_and_repair.
    """
    import compare
    importlib.reload(compare)

    results = {}
    for variant, fn in [("CURRENT (QAOA-dominant)", build_consensus_route_QAOA),
                        ("PROPOSED (Urgency-dominant)", build_consensus_route_URGENCY)]:
        # Temporarily monkey-patch
        original = sr.build_consensus_route
        sr.build_consensus_route = fn
        try:
            r = compare._run_qaoa_on_scenario(sc_module)
            dist = r.get("fleet_distance", 0) or r.get("total_distance", 0)
            spoil = r.get("fleet_spoilage", 0) or r.get("total_spoilage", 0)
            total = r.get("fleet_total_cost", 0) or (dist + spoil)
            results[variant] = {"distance": dist, "spoilage": spoil, "total": total, "status": r.get("status")}
        except Exception as e:
            print(f"  [{scenario_name}] {variant} ERROR: {e}")
            results[variant] = {"distance": 9999, "spoilage": 9999, "total": 99999, "status": "error"}
        finally:
            sr.build_consensus_route = original

    return results


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("  CONSENSUS FUNCTION BENCHMARK")
    print("  Current: QAOA-dominant  |  Proposed: Urgency-dominant")
    print("=" * 70)

    import scenario, scenario3
    importlib.reload(scenario)
    importlib.reload(scenario3)

    try:
        import scenario_dynamic
        importlib.reload(scenario_dynamic)
        sc_easy = scenario_dynamic
    except Exception:
        sc_easy = scenario

    scenarios = [
        ("Easy (Custom/Scenario1)", sc_easy),
        ("Tough (Scenario2)",       scenario),
        ("Tough3 (Scenario3)",      scenario3),
    ]

    summary = []
    for sc_name, sc_mod in scenarios:
        print(f"\n{'─'*60}")
        print(f"  Scenario: {sc_name}")
        print(f"{'─'*60}")
        res = run_benchmark_via_solver(sc_mod, sc_name)
        row = {"scenario": sc_name}
        for variant, vals in res.items():
            tag = "current" if "CURRENT" in variant else "proposed"
            print(f"  {variant}")
            print(f"    Distance : {vals['distance']:.2f} km")
            print(f"    Spoilage : Rs {vals['spoilage']:.4f}")
            print(f"    Total    : Rs {vals['total']:.4f}  [{vals['status']}]")
            row[tag] = vals["total"]
        diff = row.get("current", 0) - row.get("proposed", 0)
        winner = "PROPOSED" if diff > 0.01 else ("CURRENT" if diff < -0.01 else "TIE")
        print(f"  >> Delta: {diff:+.4f}  →  WINNER: {winner}")
        row["winner"] = winner
        summary.append(row)

    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")
    proposed_wins = sum(1 for r in summary if r["winner"] == "PROPOSED")
    current_wins  = sum(1 for r in summary if r["winner"] == "CURRENT")
    ties          = sum(1 for r in summary if r["winner"] == "TIE")

    for r in summary:
        curr_t = r.get("current", 0)
        prop_t = r.get("proposed", 0)
        diff   = curr_t - prop_t
        print(f"  {r['scenario'][:35]:<35}  current={curr_t:>8.2f}  proposed={prop_t:>8.2f}  delta={diff:+.2f}  {r['winner']}")

    print(f"\n  Proposed wins: {proposed_wins}/{len(summary)}  |  Current wins: {current_wins}/{len(summary)}  |  Ties: {ties}")

    if proposed_wins > current_wins:
        print("\n  ✅ VERDICT: PROPOSED (Urgency-dominant) is BETTER — recommend keeping it.")
    elif current_wins > proposed_wins:
        print("\n  ❌ VERDICT: CURRENT (QAOA-dominant) is BETTER — recommend reverting.")
    else:
        print("\n  ⚖️  VERDICT: TIE — no meaningful difference, current stays.")
