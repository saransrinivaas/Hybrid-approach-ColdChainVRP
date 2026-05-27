"""
compare.py — Classical vs QAOA on Scenario 1 (Easy) and Scenario 2 (Tough).

Run modes
─────────
  python compare.py              → Classical only (fast, < 2 s)
  python compare.py --with-qaoa  → Classical + QAOA (slow, 10-20 min)

Output: compare_results.json
  {
    "easy":  { "classical": {...}, "qaoa": {...} },
    "tough": { "classical": {...}, "qaoa": {...} }
  }

Streamed via Flask SSE:
  /api/run-compare            → classical only
  /api/run-compare-full       → classical + QAOA
"""

import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from classical_solver import solve_scenario as solve_classical
import ortools_solver
import gurobi_solver
import pulp_solver
import alns_solver

import scenario as SC2
try:
    import scenario_dynamic as SC1
    if not hasattr(SC1, 'CLINICS') or len(SC1.CLINICS) == 0:
        raise ImportError("Empty dynamic clinics list")
    print("[INFO] Dynamic scenario loaded successfully from scenario_dynamic.py")
except Exception:
    SC1 = SC2
    print("[INFO] Falling back to default static scenario")

import scenario3 as SC3

SCENARIO_MODULES = {
    "easy":  SC1,
    "tough": SC2,
    "tough3": SC3,
}

SCENARIO_LABELS = {
    "easy":  f"Scenario 1 - {len(SC1.CLINICS)} Clinics / {len(SC1.VEHICLES)} Vehicles",
    "tough": f"Scenario 2 - {len(SC2.CLINICS)} Clinics / {len(SC2.VEHICLES)} Vehicles",
    "tough3": f"Scenario 3 - {len(SC3.CLINICS)} Clinics / {len(SC3.VEHICLES)} Vehicles (Stress Test)",
}


# ─────────────────────────────────────────
# QAOA WRAPPER
# Runs the full QAOA pipeline on a scenario
# module by temporarily swapping the globals
# that qaoa_solver / qubo_builder / stitching_repair
# read at import time.
# ─────────────────────────────────────────
def _run_qaoa_on_scenario(sc_module) -> dict:
    """
    Execute clustering → QAOA → stitch on sc_module.
    Returns the same dict shape as solve_scenario().
    """
    import itertools
    from sklearn.cluster import KMeans
    from qaoa_solver import run_qaoa as qaoa_solve, solve_classically

    clinics      = sc_module.CLINICS
    vehicles     = sc_module.VEHICLES
    demands      = sc_module.DEMANDS
    dm           = sc_module.DISTANCE_MATRIX
    spoilage     = sc_module.SPOILAGE
    avg_speed    = sc_module.AVG_SPEED_KMH
    clinic_names = {c["id"]: c["name"] for c in clinics}
    capacity     = {
        temp: vehicles[0]["compartments"][temp]["capacity"]
        for temp in vehicles[0]["compartments"]
    }
    all_clinic_ids = [c["id"] for c in clinics]

    label = sc_module.__name__
    print(f"\n{'='*55}")
    print(f"  QAOA SOLVER - {label}")
    print(f"  {len(clinics)} clinics / {len(vehicles)} vehicles")
    print(f"{'='*55}")

    import clustering as _cl
    _orig_cl = _cl._default_scenario
    _cl._default_scenario = sc_module
    vehicle_routes = _cl.build_clusters(sc_module)
    _cl._default_scenario = _orig_cl

    assignments = {}
    for vehicle_id, trips in vehicle_routes:
        for t_idx, trip in enumerate(trips):
            trip_id = f"{vehicle_id}_{t_idx+1}" if len(trips) > 1 else vehicle_id
            assignments[trip_id] = trip
    print(f"  Clustering: {assignments}")


    # ── Step 2: QAOA per sub-cluster ──
    # Patch the global modules that qaoa_solver reads
    try:
        import scenario_dynamic as _sc
    except ImportError:
        import scenario as _sc
    import qubo_builder as _qb
    import qaoa_solver as _qa
    _orig = {
        "sc_CLINICS":  _sc.CLINICS,
        "sc_DEMANDS":  _sc.DEMANDS,
        "sc_DM":       _sc.DISTANCE_MATRIX,
        "sc_SPOILAGE": _sc.SPOILAGE,
        "qb_CLINICS":  _qb.CLINICS,
        "qb_DEMANDS":  _qb.DEMANDS,
        "qb_DM":       _qb.DISTANCE_MATRIX,
        "qb_SPOILAGE": _qb.SPOILAGE,
        "qa_CLINICS":  _qa.CLINICS,
        "qa_DM":       _qa.DISTANCE_MATRIX,
    }
    _sc.CLINICS          = clinics
    _sc.DEMANDS          = demands
    _sc.DISTANCE_MATRIX  = dm
    _sc.SPOILAGE         = spoilage
    _qb.CLINICS          = clinics
    _qb.DEMANDS          = demands
    _qb.DISTANCE_MATRIX  = dm
    _qb.SPOILAGE         = spoilage
    _qa.CLINICS          = clinics
    _qa.DISTANCE_MATRIX  = dm

    MAX_SC = 4  # sub-cluster size (qubit budget)

    def gen_subclusters(ids):
        return _cl.generate_subclusters(ids)

    qaoa_results = {}
    total_start  = time.time()

    try:
        for vehicle_id, clinic_ids in assignments.items():
            print(f"\n  [{vehicle_id}] clinics={clinic_ids}")
            sub_results = []
            for sc in gen_subclusters(clinic_ids):
                n = len(sc)
                print(f"    Sub-cluster {sc} ({n} nodes)")
                if n <= 2:
                    res = solve_classically(sc)
                else:
                    res = qaoa_solve(sc, p_depth=3, verbose=False)
                sub_results.append({
                    "clinic_ids": sc,
                    "route":      res["route"],
                    "feasible":   res["feasible"],
                    "cost":       res["cost_breakdown"],
                    "solver":     res.get("solver", "QAOA"),
                })
                status = "[OK]" if res["feasible"] else "[INFEASIBLE]"
                print(f"    {status} route={res['route']}  "
                      f"cost=Rs {res['cost_breakdown']['total']:.4f}")
            qaoa_results[vehicle_id] = {
                "clinic_ids":          clinic_ids,
                "sub_cluster_results": sub_results,
            }
    finally:
        # Always restore globals
        _sc.CLINICS         = _orig["sc_CLINICS"]
        _sc.DEMANDS         = _orig["sc_DEMANDS"]
        _sc.DISTANCE_MATRIX = _orig["sc_DM"]
        _sc.SPOILAGE        = _orig["sc_SPOILAGE"]
        _qb.CLINICS         = _orig["qb_CLINICS"]
        _qb.DEMANDS         = _orig["qb_DEMANDS"]
        _qb.DISTANCE_MATRIX = _orig["qb_DM"]
        _qb.SPOILAGE        = _orig["qb_SPOILAGE"]
        _qa.CLINICS         = _orig["qa_CLINICS"]
        _qa.DISTANCE_MATRIX = _orig["qa_DM"]

    # ── Step 3: Stitch + repair ──
    import stitching_repair as _sr
    import temp_preprocessing as _tp
    _orig_sr = {
        "CLINICS":  _sr.CLINICS,
        "DEMANDS":  _sr.DEMANDS,
        "DM":       _sr.DISTANCE_MATRIX,
        "SPOILAGE": _sr.SPOILAGE,
        "ALL":      _sr.ALL_CLINICS,
    }
    _orig_cap = _tp.CAPACITY

    _sr.CLINICS         = clinics
    _sr.DEMANDS         = demands
    _sr.DISTANCE_MATRIX = dm
    _sr.SPOILAGE        = spoilage
    _sr.ALL_CLINICS     = all_clinic_ids
    _tp.CAPACITY        = capacity

    try:
        from stitching_repair import stitch_and_repair, DEPOT_ID
        output = stitch_and_repair(qaoa_results)
    finally:
        _sr.CLINICS         = _orig_sr["CLINICS"]
        _sr.DEMANDS         = _orig_sr["DEMANDS"]
        _sr.DISTANCE_MATRIX = _orig_sr["DM"]
        _sr.SPOILAGE        = _orig_sr["SPOILAGE"]
        _sr.ALL_CLINICS     = _orig_sr["ALL"]
        _tp.CAPACITY        = _orig_cap

    total_time = round(time.time() - total_start, 4)

    # ── Build output dict ──
    routes_out = {}
    for vid, route in output["routes"].items():
        inner = [c for c in route if c != DEPOT_ID]
        dist  = sum(dm[route[i]][route[i+1]] for i in range(len(route)-1))

        # Recompute spoilage with correct scenario data
        spoil_cost = 0.0
        cum = 0.0
        for i in range(1, len(route)):
            prev, curr = route[i-1], route[i]
            if curr == DEPOT_ID:
                continue
            cum += dm[prev][curr] / avg_speed
            for temp in ("frozen", "chilled", "ambient"):
                spoil_cost += (spoilage[temp]["value"]
                               * spoilage[temp]["alpha"]
                               * cum
                               * demands[curr][temp])

        cap_check = {}
        feasible  = True
        for temp in ("frozen", "chilled", "ambient"):
            used = sum(demands[cid][temp] for cid in inner)
            cap  = capacity[temp]
            cap_check[temp] = {"used": used, "cap": cap}
            if used > cap:
                feasible = False

        stops = [
            {"id": cid,
             "name": "Depot" if cid == 0 else clinic_names.get(cid, f"C{cid}")}
            for cid in route
        ]

        energy_rate = sc_module.ENERGY_RATE
        refrig_cost = sum(energy_rate[temp] * cum for temp in ("frozen", "chilled", "ambient"))

        routes_out[vid] = {
            "route":            route,
            "stops":            stops,
            "distance_km":      round(dist, 4),
            "spoilage_rs":      round(spoil_cost, 4),
            "refrigeration_rs": round(refrig_cost, 4),
            "total_cost_rs":    round(dist + spoil_cost + refrig_cost, 4),
            "feasible":         feasible,
            "capacity":         cap_check,
            "computation_time": total_time,
            "solver":           "QAOA (p=3)",
        }

    fleet_dist  = sum(v["distance_km"]  for v in routes_out.values())
    fleet_spoil = sum(v["spoilage_rs"]  for v in routes_out.values())
    fleet_refrig = sum(v["refrigeration_rs"] for v in routes_out.values())
    fleet_total = round(fleet_dist + fleet_spoil + fleet_refrig, 4)

    print(f"\n  Fleet distance : {fleet_dist:.2f} km")
    print(f"  Fleet spoilage : Rs {fleet_spoil:.4f}")
    print(f"  Fleet refrig   : Rs {fleet_refrig:.4f}")
    print(f"  Fleet total    : Rs {fleet_total:.4f}")
    print(f"  Total time     : {total_time:.3f}s")

    return {
        "solver":              "QAOA (p=3)",
        "routes":              routes_out,
        "fleet_distance":      round(fleet_dist, 4),
        "fleet_spoilage":      round(fleet_spoil, 4),
        "fleet_refrigeration": round(fleet_refrig, 4),
        "fleet_total_cost":    fleet_total,
        "total_time":          total_time,
        "status":              "ok",
    }


# ─────────────────────────────────────────
# MAIN COMPARISON RUNNER
# ─────────────────────────────────────────
def run_comparison(with_qaoa: bool = False, target_scenario: str = None) -> dict:
    """
    Run Classical (always) and optionally QAOA on both scenarios.
    Saves compare_results.json and returns the dict.
    """
    results = {}
    pass

    for key, sc_module in SCENARIO_MODULES.items():
        if target_scenario and key != target_scenario:
            continue
        label = SCENARIO_LABELS[key]
        print(f"\n{'#'*55}")
        print(f"  SCENARIO: {label}")
        print(f"{'#'*55}")

        results.setdefault(key, {})
        entry = results[key]

        # ── Classical ──
        print("\n--- Classical Solver (NN + 2-opt + OR-opt) ---")
        entry["classical"] = solve_classical(sc_module)

        # ── OR-Tools ──
        print("\n--- OR-Tools Solver ---")
        try:
            entry["ortools"] = ortools_solver.solve_scenario(sc_module)
        except Exception as e:
            print(f"  [WARN] OR-Tools failed for {key}: {e}")
            entry["ortools"] = {"solver": "Google OR-Tools (Routing) — FAILED", "status": "failed", "error": str(e)}

        # ── Gurobi ──
        print("\n--- Gurobi Solver ---")
        try:
            entry["gurobi"] = gurobi_solver.solve_scenario(sc_module)
        except Exception as e:
            print(f"  [WARN] Gurobi failed for {key}: {e}")
            entry["gurobi"] = {"solver": "Gurobi (ILP) — FAILED", "status": "failed", "error": str(e)}



        # ── PuLP ──
        print("\n--- PuLP/CBC Solver ---")
        try:
            entry["pulp_cbc"] = pulp_solver.solve_scenario(sc_module)
        except Exception as e:
            print(f"  [WARN] PuLP failed for {key}: {e}")
            entry["pulp_cbc"] = {"solver": "PuLP/CBC (ILP) — FAILED", "status": "failed", "error": str(e)}

        # ── ALNS Metaheuristic ──
        print("\n--- ALNS Metaheuristic ---")
        try:
            entry["alns"] = alns_solver.solve_scenario(sc_module)
        except Exception as e:
            print(f"  [WARN] ALNS failed for {key}: {e}")
            entry["alns"] = {"solver": "ALNS Metaheuristic — FAILED", "status": "failed", "error": str(e)}

        # ── QAOA ──
        if with_qaoa:
            print("\n--- QAOA Solver (p=3) ---")
            try:
                entry["qaoa"] = _run_qaoa_on_scenario(sc_module)
            except Exception as e:
                import traceback
                print(f"  [WARN] QAOA failed for {key}: {e}")
                traceback.print_exc()
                entry["qaoa"] = {"error": str(e), "status": "failed"}
        else:
            entry["qaoa"] = {
                "status": "skipped",
                "note":   "Run with --with-qaoa to include QAOA results",
            }

        # ── Summary ──
        cl = entry["classical"]
        ort = entry.get("ortools", {"status": "skipped"})
        gur = entry.get("gurobi", {"status": "skipped"})
        plp = entry.get("pulp_cbc", {"status": "skipped"})
        alns = entry.get("alns", {"status": "skipped"})
        qa = entry["qaoa"]
        print(f"\n  ┌─ {label}")
        print(f"  │  Classical : Rs {cl.get('fleet_total_cost', 0.0):.4f}  ({cl.get('total_time', 0.0):.3f}s)")
        if ort.get("status") not in ("failed", "skipped", "unavailable"):
            print(f"  │  OR-Tools  : Rs {ort.get('fleet_total_cost', 0.0):.4f}  ({ort.get('total_time', 0.0):.3f}s)")
        else:
            print(f"  │  OR-Tools  : {ort.get('note', ort.get('status'))}")
        if gur.get("status") not in ("failed", "skipped", "unavailable"):
            print(f"  │  Gurobi    : Rs {gur.get('fleet_total_cost', 0.0):.4f}  ({gur.get('total_time', 0.0):.3f}s)")
        else:
            print(f"  │  Gurobi    : {gur.get('note', gur.get('status'))}")
        if plp.get("status") not in ("failed", "skipped", "unavailable"):
            print(f"  │  PuLP/CBC  : Rs {plp.get('fleet_total_cost', 0.0):.4f}  ({plp.get('total_time', 0.0):.3f}s)")
        else:
            print(f"  │  PuLP/CBC  : {plp.get('note', plp.get('status'))}")
        if alns.get("status") not in ("failed", "skipped", "unavailable"):
            print(f"  │  ALNS      : Rs {alns.get('fleet_total_cost', 0.0):.4f}  ({alns.get('total_time', 0.0):.3f}s)")
        else:
            print(f"  │  ALNS      : {alns.get('note', alns.get('status'))}")
        if qa.get("status") not in ("failed", "skipped"):
            diff = cl["fleet_total_cost"] - qa["fleet_total_cost"]
            pct  = (diff / cl["fleet_total_cost"] * 100) if cl["fleet_total_cost"] else 0
            print(f"  │  QAOA      : Rs {qa['fleet_total_cost']:.4f}  "
                  f"({qa['total_time']:.3f}s)")
            print(f"  │  Δ (Cl-QA) : {diff:+.4f} Rs  ({pct:+.1f}%)")
        else:
            print(f"  │  QAOA      : {qa.get('note', qa.get('status'))}")
        print(f"  └─")

    # Save merged results locally on disk as well (fallback/redundancy)
    try:
        out_path = os.path.join(BASE_DIR, "compare_results.json")
        existing_data = {}
        if os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        existing_data.update(results)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2)
        print(f"\n[OK] Persisted results locally to disk -> {out_path}")
    except Exception as e:
        print(f"\n[WARN] Failed to persist results locally to disk: {e}")

    # Submit to volatile memory via HTTP
    import urllib.request
    port = os.environ.get('FLASK_PORT', '5000')
    req = urllib.request.Request(
        f"http://localhost:{port}/api/submit-results?type=compare",
        data=json.dumps(results, default=str).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        # Explicitly bypass system proxies to avoid corporate VPN or local proxy redirects
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        with opener.open(req) as response:
            print("\n[OK] Results submitted to volatile memory")
    except Exception as e:
        print(f"\n[WARN] Failed to submit compare results: {e}")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Compare Classical vs QAOA solvers")
    parser.add_argument("--with-qaoa", action="store_true",
                        help="Also run QAOA solver (slow, 10-20 min)")
    parser.add_argument("--scenario", type=str, choices=["easy", "tough", "tough3"], default=None,
                        help="Run comparison for a specific scenario only")
    args = parser.parse_args()
    run_comparison(with_qaoa=args.with_qaoa, target_scenario=args.scenario)
