"""
pipeline.py — End-to-end orchestrator

Runs the full quantum VRP pipeline in sequence:
  1. Clustering (classical)
  2. QAOA solver (quantum simulation)
  3. Stitching + repair (classical post-processing)

Writes two JSON files:
  qaoa_results.json  — raw QAOA output per vehicle
  results.json       — final stitched routes + cost summary

Designed to be streamed via Flask SSE (/api/run-pipeline).
"""
import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Dynamic Scenario Loading ──
if "--easy" in sys.argv:
    import scenario as _sc1
    sys.modules['scenario_dynamic'] = _sc1
    sys.modules['scenario'] = _sc1
    scenario = _sc1
    print("  [LOAD] Forcing base Easy scenario (scenario.py)")
else:
    try:
        import scenario_dynamic as scenario
        print("  [LOAD] Using dynamic scenario (scenario_dynamic.py)")
    except ImportError:
        import scenario
        print("  [LOAD] Using base scenario (scenario.py)")

# ─────────────────────────────────────────
# STEP 1 — CLUSTERING
# ─────────────────────────────────────────
def run_clustering():
    print("\n" + "=" * 55)
    print("  STEP 1 — VEHICULAR CLUSTERING")
    print("=" * 55)
    from clustering import build_clusters, generate_subclusters
    vehicle_routes = build_clusters()
    # vehicle_routes: [(vehicle_id, [trip, ...]), ...]
    # trip: list of clinic IDs
    # generate_subclusters(trip) → [[c1,c2,c3], ...]
    return vehicle_routes, generate_subclusters

# ─────────────────────────────────────────
# STEP 2 — QAOA PER SUB-CLUSTER
# ─────────────────────────────────────────
def run_qaoa(vehicle_routes, generate_subclusters):
    print("\n" + "=" * 55)
    print("  STEP 2 — QAOA SOLVER")
    print("=" * 55)
    from qaoa_solver import run_qaoa as qaoa_solve, solve_classically
    clinic_names = {c["id"]: c["name"] for c in scenario.CLINICS}

    qaoa_results = {}   # keyed by vehicle_id

    for vehicle_id, trips in vehicle_routes:
        # Flatten all clinic IDs for this vehicle
        all_clinic_ids = [cid for trip in trips for cid in trip]
        sub_cluster_results = []

        for trip in trips:
            subclusters = generate_subclusters(trip)
            for sc in subclusters:
                n = len(sc)
                print(f"\n  [{vehicle_id}] Sub-cluster {sc} ({n} clinics)")
                if n <= 2:
                    print(f"  Classical (trivial {n}-node route)")
                    res = solve_classically(sc)
                else:
                    res = qaoa_solve(sc, p_depth=3, verbose=True)

                sub_cluster_results.append({
                    "clinic_ids": sc,
                    "route":      res["route"],
                    "feasible":   res["feasible"],
                    "cost":       res["cost_breakdown"],
                    "solver":     res.get("solver", "QAOA"),
                })

                names = [clinic_names.get(c, str(c)) for c in (res["route"] or [])]
                status = "[OK]" if res["feasible"] else "[INFEASIBLE]"
                print(f"  {status} Route: {res['route']} -> {names}")

        qaoa_results[vehicle_id] = {
            "clinic_ids":           all_clinic_ids,
            "sub_cluster_results":  sub_cluster_results,
        }

    # Persist QAOA results for inspection / resume
    qaoa_path = os.path.join(BASE_DIR, "qaoa_results.json")
    with open(qaoa_path, "w") as f:
        json.dump(qaoa_results, f, indent=2)
    print(f"\n  [OK] QAOA results saved -> {qaoa_path}")
    return qaoa_results

def run_stitching(qaoa_results, out_filename="results.json"):
    print("\n" + "=" * 55)
    print("  STEP 3 — STITCHING + REPAIR")
    print("=" * 55)
    from stitching_repair import stitch_and_repair

    output = stitch_and_repair(qaoa_results)

    clinic_names = {c["id"]: c["name"] for c in scenario.CLINICS}
    clinic_lats = {c["id"]: c["lat"] for c in scenario.CLINICS}
    clinic_lons = {c["id"]: c["lon"] for c in scenario.CLINICS}

    # Build serialisable results for the frontend
    routes_out = {}
    for vid, route in output["routes"].items():
        stops = [
            {
                "id": cid, 
                "name": "Depot" if cid == 0 else clinic_names.get(cid, f"C{cid}"),
                "lat": scenario.DEPOT["lat"] if cid == 0 else clinic_lats.get(cid),
                "lon": scenario.DEPOT["lon"] if cid == 0 else clinic_lons.get(cid)
            }
            for cid in route
        ]
        dist = sum(
            scenario.DISTANCE_MATRIX[route[i]][route[i + 1]]
            for i in range(len(route) - 1)
        )
        from stitching_repair import compute_spoilage, vehicle_demand, route_feasible, DEPOT_ID, CAPACITY
        inner = [c for c in route if c != DEPOT_ID]
        spoilage = compute_spoilage(route)
        ok, _ = route_feasible(inner)
        capacity_check = {
            temp: {"used": vehicle_demand(inner, temp), "cap": CAPACITY[temp]}
            for temp in ("frozen", "chilled", "ambient")
        }
        routes_out[vid] = {
            "route":          route,
            "stops":          stops,
            "distance_km":    round(dist, 2),
            "spoilage_rs":    round(spoilage, 4),
            "total_cost_rs":  round(dist + spoilage, 4),
            "feasible":       ok,
            "capacity":       capacity_check,
        }

    results = {
        "routes":           routes_out,
        "fleet_distance":   round(output["total_distance"], 2),
        "fleet_spoilage":   round(output["total_spoilage"], 4),
        "fleet_total_cost": round(output["total_cost"], 4),
        "status":           "ok",
    }

    return results

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  COLD CHAIN VRP — HYBRID PIPELINE")
    print("=" * 55)

    try:
        vehicle_routes, gen_sc = run_clustering()
        qaoa_results            = run_qaoa(vehicle_routes, gen_sc)
        final                   = run_stitching(qaoa_results)

        print("\n" + "=" * 55)
        print("  STEP 4 — CLASSICAL BASELINE (FOR COMPARISON)")
        print("=" * 55)
        from classical_solver import solve_scenario
        classical_result = solve_scenario(scenario)

        print("\n" + "=" * 55)
        print("  PIPELINE COMPLETE")
        print("=" * 55)
        print(f"  [QAOA] Fleet distance : {final['fleet_distance']} km")
        print(f"  [QAOA] Fleet spoilage : Rs {final['fleet_spoilage']}")
        print(f"  [QAOA] Combined cost  : Rs {final['fleet_total_cost']}")
        
        # Write the combined payload expected by ResultsView's Comparison tab
        combined_payload = {
            "classical": classical_result,
            "qaoa": final
        }
        
        import urllib.request
        import json
        req = urllib.request.Request(
            "http://127.0.0.1:5000/api/submit-results?type=pipeline_easy",
            data=json.dumps(combined_payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        try:
            # Explicitly bypass system proxies to avoid corporate VPN or local proxy redirects
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            with opener.open(req) as response:
                print("\n  [OK] Final combined results submitted to volatile memory")
        except Exception as e:
            print(f"\n  [WARN] Failed to submit results: {e}")

        print("=" * 55)

    except Exception as e:
        import traceback
        print(f"\n[ERROR] Pipeline failed: {e}")
        traceback.print_exc()
        sys.exit(1)
