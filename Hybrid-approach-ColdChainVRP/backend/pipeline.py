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
elif "--tough3" in sys.argv or "--scenario3" in sys.argv:
    import scenario3 as _sc3
    sys.modules['scenario_dynamic'] = _sc3
    sys.modules['scenario'] = _sc3
    scenario = _sc3
    print("  [LOAD] Forcing Scenario 3 (scenario3.py)")
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
# STEP 2 — QAOA PER SUB-CLUSTER (PARALLEL)
# ─────────────────────────────────────────
def _solve_single_subcluster(args):
    """
    Top-level pickling-safe worker for ThreadPoolExecutor.
    Solves one sub-cluster with either QAOA (n>2) or classical (n<=2).
    """
    sc, p_depth, verbose = args
    from qaoa_solver import run_qaoa as qaoa_solve, solve_classically
    n = len(sc)
    if n <= 2:
        return sc, solve_classically(sc)
    return sc, qaoa_solve(sc, p_depth=p_depth, verbose=verbose)


def run_qaoa(vehicle_routes, generate_subclusters):
    print("\n" + "=" * 55)
    print("  STEP 2 — QAOA SOLVER  [PARALLEL EXECUTION]")
    print("=" * 55)
    clinic_names = {c["id"]: c["name"] for c in scenario.CLINICS}

    # ── Collect all (trip_id, trip, sub_cluster, order_idx) tuples ──
    task_meta  = []   # (trip_id, trip, sc, order_idx)
    trip_order = []   # preserves vehicle/trip ordering for final assembly

    for vehicle_id, trips in vehicle_routes:
        for t_idx, trip in enumerate(trips):
            trip_id = f"{vehicle_id}_{t_idx+1}" if len(trips) > 1 else vehicle_id
            if trip_id not in [tm[0] for tm in trip_order]:
                trip_order.append((trip_id, trip))
            subclusters = generate_subclusters(trip)
            for order_idx, sc in enumerate(subclusters):
                task_meta.append((trip_id, trip, sc, order_idx))

    total_tasks = len(task_meta)
    import os
    from concurrent.futures import ThreadPoolExecutor, as_completed
    max_workers = min(total_tasks, os.cpu_count() or 4)

    print(f"\n  [PARALLEL] {total_tasks} sub-clusters across all vehicles")
    print(f"  [PARALLEL] Using {max_workers} worker threads")
    print(f"  [PARALLEL] All sub-clusters solving simultaneously...\n")

    # ── Submit all tasks in parallel ──
    results_store = {}   # (trip_id, order_idx) → result

    # PRESENTATION MODE NOTE: if you switch qaoa_solver.py back to mock mode,
    # parallel execution still works — just returns instantly instead of ~45s/cluster.

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {}
        for trip_id, trip, sc, order_idx in task_meta:
            # Suppress verbose output per-cluster to avoid interleaved noise
            fut = executor.submit(_solve_single_subcluster, (sc, 3, False))
            future_map[fut] = (trip_id, trip, sc, order_idx)

        completed = 0
        for future in as_completed(future_map):
            trip_id, trip, sc, order_idx = future_map[future]
            try:
                sc_result, res = future.result()
                results_store[(trip_id, order_idx)] = {
                    "clinic_ids": sc,
                    "route":      res["route"],
                    "feasible":   res["feasible"],
                    "cost":       res["cost_breakdown"],
                    "solver":     res.get("solver", "QAOA"),
                }
                completed += 1
                status = "[OK]" if res["feasible"] else "[INFEASIBLE]"
                names  = [clinic_names.get(c, str(c)) for c in (res["route"] or [])]
                print(f"  [{completed}/{total_tasks}] {trip_id} sc={sc} {status} → {res['route']}")
            except Exception as e:
                print(f"  [ERROR] Sub-cluster {sc} in {trip_id} failed: {e}")
                results_store[(trip_id, order_idx)] = {
                    "clinic_ids": sc,
                    "route":      list(sc),
                    "feasible":   False,
                    "cost":       {"distance": 0, "spoilage": 0, "total": 0},
                    "solver":     "error-fallback",
                }

    # ── Assemble qaoa_results dict in correct trip order ──
    qaoa_results = {}
    trip_seen = {}
    for trip_id, trip, sc, order_idx in task_meta:
        if trip_id not in qaoa_results:
            qaoa_results[trip_id] = {
                "clinic_ids":          trip,
                "sub_cluster_results": [],
            }
            trip_seen[trip_id] = []

    # Re-sort sub_cluster_results by order_idx per trip
    for (trip_id, order_idx), res_data in results_store.items():
        trip_seen.setdefault(trip_id, [])
        trip_seen[trip_id].append((order_idx, res_data))

    for trip_id in qaoa_results:
        ordered = sorted(trip_seen.get(trip_id, []), key=lambda x: x[0])
        qaoa_results[trip_id]["sub_cluster_results"] = [r for _, r in ordered]

    # Persist QAOA results for inspection / resume
    qaoa_path = os.path.join(BASE_DIR, "qaoa_results.json")
    with open(qaoa_path, "w") as f:
        json.dump(qaoa_results, f, indent=2)
    print(f"\n  [OK] QAOA results saved → {qaoa_path}")
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
        avg_speed = scenario.AVG_SPEED_KMH
        cum = 0.0
        for i in range(1, len(route)):
            prev, curr = route[i-1], route[i]
            if curr == DEPOT_ID:
                continue
            cum += scenario.DISTANCE_MATRIX[prev][curr] / avg_speed
        
        refrig_cost = sum(scenario.ENERGY_RATE[temp] * cum for temp in ("frozen", "chilled", "ambient"))

        routes_out[vid] = {
            "route":          route,
            "stops":          stops,
            "distance_km":    round(dist, 2),
            "spoilage_rs":    round(spoilage, 4),
            "refrigeration_rs": round(refrig_cost, 4),
            "total_cost_rs":  round(dist + spoilage + refrig_cost, 4),
            "feasible":       ok,
            "capacity":       capacity_check,
        }

    fleet_refrig = sum(v["refrigeration_rs"] for v in routes_out.values())
    results = {
        "routes":           routes_out,
        "fleet_distance":   round(output["total_distance"], 2),
        "fleet_spoilage":   round(output["total_spoilage"], 4),
        "fleet_refrigeration": round(fleet_refrig, 4),
        "fleet_total_cost": round(output["total_distance"] + output["total_spoilage"] + fleet_refrig, 4),
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
        
        # Decide the type based on CLI arguments
        if "--easy" in sys.argv:
            submit_type = "pipeline_tough"
        elif "--tough3" in sys.argv or "--scenario3" in sys.argv:
            submit_type = "pipeline_tough3"
        else:
            submit_type = "pipeline_easy"

        import urllib.request
        import json
        req = urllib.request.Request(
            f"http://127.0.0.1:5000/api/submit-results?type={submit_type}",
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
