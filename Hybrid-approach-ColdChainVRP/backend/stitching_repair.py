import functools
import numpy as np

try:
    import scenario_dynamic as scenario
except ImportError:
    import scenario

CLINICS = scenario.CLINICS
DEPOT = scenario.DEPOT
DISTANCE_MATRIX = scenario.DISTANCE_MATRIX
DEMANDS = scenario.DEMANDS
SPOILAGE = scenario.SPOILAGE
AVG_SPEED_KMH = scenario.AVG_SPEED_KMH

import temp_preprocessing
CAPACITY = temp_preprocessing.CAPACITY


# ─────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────
AVG_SPEED   = AVG_SPEED_KMH  # alias kept for readability
DEPOT_ID    = 0
ALL_CLINICS = [c["id"] for c in CLINICS]  # derived from scenario, not hardcoded

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def route_distance(route: list) -> float:
    """Total distance of a full route (including depot hops)."""
    return sum(
        DISTANCE_MATRIX[route[i]][route[i + 1]]
        for i in range(len(route) - 1)
    )

def insertion_cost(route: list, clinic_id: int, pos: int) -> float:
    """
    Extra cost added by inserting clinic_id at position pos.
    Includes BOTH distance delta AND spoilage delta so that
    high-decay clinics are preferentially placed early in route.
    pos is an interior index (not at depot ends).
    """
    before = route[pos - 1]
    after  = route[pos]
    dist_delta = (DISTANCE_MATRIX[before][clinic_id]
                  + DISTANCE_MATRIX[clinic_id][after]
                  - DISTANCE_MATRIX[before][after])

    # Spoilage delta: cumulative time to reach clinic_id at pos
    cum_time = 0.0
    for k in range(1, pos):
        cum_time += DISTANCE_MATRIX[route[k - 1]][route[k]] / AVG_SPEED
    cum_time += DISTANCE_MATRIX[before][clinic_id] / AVG_SPEED

    spoilage_delta = 0.0
    for temp in ("frozen", "chilled", "ambient"):
        alpha  = SPOILAGE[temp]["alpha"]
        value  = SPOILAGE[temp]["value"]
        demand = DEMANDS[clinic_id][temp]
        spoilage_delta += value * alpha * cum_time * demand

    return dist_delta + spoilage_delta

def vehicle_demand(inner_route: list, temp_class: str) -> int:
    """Total demand for a temperature class (inner route = no depots)."""
    return sum(DEMANDS[cid][temp_class] for cid in inner_route)

def route_feasible(inner_route: list):
    """
    Check if all compartment capacities are satisfied.
    Returns (True, None) or (False, overflowing_temp).
    """
    for temp in ("frozen", "chilled", "ambient"):
        if vehicle_demand(inner_route, temp) > temp_preprocessing.CAPACITY[temp]:
            return False, temp
    return True, None

def compute_spoilage(route: list) -> float:
    """Cumulative spoilage cost for a route with depot endpoints."""
    total    = 0.0
    cum_time = 0.0
    for i in range(1, len(route)):
        prev = route[i - 1]
        curr = route[i]
        if curr == DEPOT_ID:
            continue
        cum_time += DISTANCE_MATRIX[prev][curr] / AVG_SPEED
        for temp in ("frozen", "chilled", "ambient"):
            alpha  = SPOILAGE[temp]["alpha"]
            value  = SPOILAGE[temp]["value"]
            demand = DEMANDS[curr][temp]
            total += value * alpha * cum_time * demand
    return total

def add_depot(inner: list) -> list:
    """Wrap an inner route with depot at start and end."""
    return [DEPOT_ID] + inner + [DEPOT_ID]

# ─────────────────────────────────────────
# PHASE 1 — REPAIR INFEASIBLE SUB-CLUSTERS
# Fix bad QAOA bitstrings before stitching
# ─────────────────────────────────────────
def repair_sub_cluster(result: dict) -> dict:
    """
    Repair a sub-cluster result whose route is infeasible
    (contains None, duplicates, or missing clinics).
    Uses cheapest-insertion to place missing clinics.
    """
    clinic_ids = result["clinic_ids"]
    route      = result.get("route", [])

    # Already good
    if result.get("feasible") and route and None not in route:
        return result

    print(f"    Repairing {clinic_ids}  raw={route}")

    # Strip Nones, find duplicates and missing
    visited    = [c for c in route if c is not None]
    seen       = set()
    clean      = []
    for c in visited:
        if c not in seen:
            clean.append(c)
            seen.add(c)

    missing = [c for c in clinic_ids if c not in seen]

    # Cheapest insertion for each missing clinic
    for mc in missing:
        if not clean:
            clean.append(mc)
            continue
        best_pos  = 0
        best_cost = float("inf")
        for pos in range(len(clean) + 1):
            trial = clean[:pos] + [mc] + clean[pos:]
            cost  = sum(
                DISTANCE_MATRIX[trial[k]][trial[k + 1]]
                for k in range(len(trial) - 1)
            )
            if cost < best_cost:
                best_cost = cost
                best_pos  = pos
        clean.insert(best_pos, mc)

    print(f"    Repaired  {clinic_ids}  fixed={clean}")
    result = dict(result)
    result["route"]    = clean
    result["feasible"] = True
    result["repaired"] = True
    return result

# ─────────────────────────────────────────
# PHASE 2 — CONSENSUS
# Vote on the canonical ordering of all clinics
# assigned to one vehicle, from overlapping
# sub-cluster results.
# ─────────────────────────────────────────
def build_consensus_route(sub_results: list, all_clinic_ids: list) -> list:
    """
    Pairwise voting: for each pair (a, b), count how many
    sub-cluster routes visit a before b.
    Majority wins; ties broken by depot distance.
    Returns ordered list of clinic IDs.
    """
    n = len(all_clinic_ids)

    if n <= 1:
        return list(all_clinic_ids)

    if n == 2:
        a, b = all_clinic_ids
        # Closer to depot goes first
        return [a, b] if DISTANCE_MATRIX[0][a] <= DISTANCE_MATRIX[0][b] else [b, a]

    # Build pairwise preference counts
    pref = {(a, b): 0 for a in all_clinic_ids for b in all_clinic_ids if a != b}

    for res in sub_results:
        route = res.get("route", [])
        if not route or None in route:
            continue
        for i in range(len(route)):
            for j in range(i + 1, len(route)):
                key = (route[i], route[j])
                if key in pref:
                    pref[key] += 1

    def compare(a, b):
        ab = pref.get((a, b), 0)
        ba = pref.get((b, a), 0)
        if ab > ba:
            return -1      # a before b
        if ba > ab:
            return 1       # b before a
        # Tie: place higher-spoilage clinic first to minimise decay time
        def spoilage_urgency(cid):
            return sum(
                SPOILAGE[t]["alpha"] * SPOILAGE[t]["value"] * DEMANDS[cid][t]
                for t in ("frozen", "chilled", "ambient")
            )
        sa, sb = spoilage_urgency(a), spoilage_urgency(b)
        if sa != sb:
            return -1 if sa > sb else 1  # higher urgency goes first
        # Final tie: closer to depot goes first
        return -1 if DISTANCE_MATRIX[0][a] <= DISTANCE_MATRIX[0][b] else 1

    ordered = sorted(all_clinic_ids, key=functools.cmp_to_key(compare))
    return ordered

# ─────────────────────────────────────────
# PHASE 3 — 2-OPT IMPROVEMENT
# Standard route improvement: try reversing
# segments to shorten total distance.
# Depot endpoints are kept fixed.
# ─────────────────────────────────────────
def two_opt(route: list) -> list:
    """2-opt local search optimising total cost (distance + spoilage), depot endpoints fixed."""
    if len(route) <= 4:
        return route

    inner    = route[1:-1]
    improved = True

    def full_cost(inner_r):
        r = [0] + inner_r + [0]
        return route_distance(r) + compute_spoilage(r)

    best_cost = full_cost(inner)

    while improved:
        improved = False
        for i in range(len(inner) - 1):
            for j in range(i + 2, len(inner)):
                new_inner = inner[:i] + inner[i:j + 1][::-1] + inner[j + 1:]
                c = full_cost(new_inner)
                if c < best_cost - 1e-9:
                    inner     = new_inner
                    best_cost = c
                    improved  = True
                    break
            if improved:
                break

    return [0] + inner + [0]

# ─────────────────────────────────────────
# PHASE 4 — CROSS-VEHICLE REPAIR
# Fix duplicates, missing clinics, and
# capacity overflows across all vehicles.
# ─────────────────────────────────────────
def repair_cross_vehicle(vehicle_routes: dict) -> dict:
    """
    Operates on full routes (with depots).
    Fixes:
      Type 1 — same clinic in multiple vehicles
      Type 2 — clinic not assigned to any vehicle
      Type 3 — capacity overflow after stitching
    """
    print("\n  [Cross-vehicle repair]")

    # Build assignment map: clinic_id → [vehicle_ids]
    assignments = {}
    for vid, route in vehicle_routes.items():
        for cid in route:
            if cid == DEPOT_ID:
                continue
            assignments.setdefault(cid, []).append(vid)

    duplicates = {cid: vids for cid, vids in assignments.items() if len(vids) > 1}
    missing    = [cid for cid in ALL_CLINICS if cid not in assignments]

    # ── Type 1: Duplicates ──
    for cid, vids in duplicates.items():
        print(f"    [DUP] Clinic {cid} in {vids}")
        costs = {}
        for vid in vids:
            route = vehicle_routes[vid]
            idx   = route.index(cid)
            if idx == 0 or idx == len(route) - 1:
                costs[vid] = float("inf")
            else:
                costs[vid] = (DISTANCE_MATRIX[route[idx - 1]][cid]
                              + DISTANCE_MATRIX[cid][route[idx + 1]])
        keeper = min(costs, key=costs.get)
        for vid in vids:
            if vid != keeper:
                vehicle_routes[vid] = [c for c in vehicle_routes[vid] if c != cid]
                print(f"    Removed Clinic {cid} from {vid} → kept in {keeper}")

    # ── Type 2: Missing ──
    for cid in missing:
        print(f"    [MISSING] Clinic {cid}")
        best_vid, best_pos, best_cost = None, None, float("inf")
        for vid, route in vehicle_routes.items():
            inner = [c for c in route if c != DEPOT_ID]
            ok, _ = route_feasible(inner + [cid])
            if not ok:
                continue
            for pos in range(1, len(route)):
                cost = insertion_cost(route, cid, pos)
                if cost < best_cost:
                    best_cost, best_pos, best_vid = cost, pos, vid
        if best_vid:
            vehicle_routes[best_vid].insert(best_pos, cid)
            print(f"    Inserted Clinic {cid} → {best_vid} at pos {best_pos}")
        else:
            print(f"    [WARN] No vehicle has capacity for Clinic {cid}")

    # ── Type 3: Capacity overflows ──
    for vid in list(vehicle_routes.keys()):
        route = vehicle_routes[vid]
        inner = [c for c in route if c != DEPOT_ID]
        ok, bad_temp = route_feasible(inner)
        if ok:
            continue
        print(f"    [OVERFLOW] {vid} {bad_temp}")
        offload = max(inner, key=lambda c: DEMANDS[c][bad_temp])
        inner.remove(offload)
        vehicle_routes[vid] = add_depot(inner)
        moved = False
        for other_vid, other_route in vehicle_routes.items():
            if other_vid == vid:
                continue
            other_inner = [c for c in other_route if c != DEPOT_ID]
            ok2, _ = route_feasible(other_inner + [offload])
            if ok2:
                best_pos  = 1
                best_cost = float("inf")
                for pos in range(1, len(other_route)):
                    cost = insertion_cost(other_route, offload, pos)
                    if cost < best_cost:
                        best_cost, best_pos = cost, pos
                vehicle_routes[other_vid].insert(best_pos, offload)
                print(f"    Moved Clinic {offload} → {other_vid}")
                moved = True
                break
        if not moved:
            print(f"    [WARN] Could not offload Clinic {offload}")

    return vehicle_routes

# ─────────────────────────────────────────
# MAIN — STITCH AND REPAIR
# ─────────────────────────────────────────
def stitch_and_repair(qaoa_results: dict) -> dict:
    """
    Full pipeline: repair → consensus → depot → 2-opt → cross-repair.

    Input format:
      {
        "V1": {
            "clinic_ids": [1,2,3,5],
            "sub_cluster_results": [
                {"clinic_ids":[1,2,3], "route":[2,1,3], "feasible":True},
                ...
            ]
        },
        ...
      }

    Returns:
      {
        "routes": {"V1": [0,2,1,3,5,0], ...},
        "total_distance": float,
        "total_spoilage": float,
        "total_cost": float
      }
    """
    print("\n" + "=" * 55)
    print("  STITCHING + REPAIR PIPELINE")
    print("=" * 55)

    vehicle_routes = {}

    for vid, vdata in qaoa_results.items():
        clinic_ids  = vdata["clinic_ids"]
        sub_results = vdata["sub_cluster_results"]

        print(f"\n── {vid} ── clinics={clinic_ids}")

        # Trivial 2-node case: classical
        if len(clinic_ids) <= 2:
            a, b = (clinic_ids + clinic_ids)[:2]  # handles len==1 too
            if len(clinic_ids) == 1:
                route = add_depot([a])
            else:
                route = add_depot(
                    [a, b] if DISTANCE_MATRIX[0][a] <= DISTANCE_MATRIX[0][b]
                    else [b, a]
                )
            vehicle_routes[vid] = route
            print(f"  Classical route: {route}")
            continue

        # Phase 1: Repair bad sub-clusters
        print("  Phase 1: Repairing sub-clusters...")
        repaired = [repair_sub_cluster(r) for r in sub_results]
        n_ok = sum(1 for r in repaired if r.get("feasible"))
        print(f"  {n_ok}/{len(repaired)} feasible after repair")

        # Phase 2: Consensus ordering
        print("  Phase 2: Consensus vote...")
        consensus = build_consensus_route(repaired, clinic_ids)
        print(f"  Consensus: {consensus}")

        # Phase 3: Add depot
        full = add_depot(consensus)

        # Phase 4: 2-opt
        before = route_distance(full)
        full   = two_opt(full)
        after  = route_distance(full)
        print(f"  2-opt: {before:.2f} → {after:.2f} km  "
              f"(saved {before - after:.2f} km)")
        print(f"  Route: {full}")

        vehicle_routes[vid] = full

    # Phase 5: Cross-vehicle repair
    vehicle_routes = repair_cross_vehicle(vehicle_routes)

    # ── Final summary ──
    clinic_names   = {c["id"]: c["name"] for c in CLINICS}
    total_distance = 0.0
    total_spoilage = 0.0

    print(f"\n{'=' * 55}")
    print("  FINAL ROUTES")
    print(f"{'=' * 55}")

    for vid, route in vehicle_routes.items():
        dist     = route_distance(route)
        spoilage = compute_spoilage(route)
        total_distance += dist
        total_spoilage += spoilage

        stops = [
            "Depot" if cid == 0 else clinic_names.get(cid, f"C{cid}")
            for cid in route
        ]
        print(f"\n  {vid}: {' -> '.join(stops)}")
        inner = [c for c in route if c != DEPOT_ID]
        ok, _ = route_feasible(inner)
        for temp in ("frozen", "chilled", "ambient"):
            d = vehicle_demand(inner, temp)
            cap = temp_preprocessing.CAPACITY[temp]
            status = "OK" if d <= cap else "OVERFLOW"
            print(f"    {temp:>8}: {d}/{cap} [{status}]")
        print(f"    Distance:  {dist:.2f} km")
        print(f"    Spoilage:  Rs {spoilage:.4f}")

    print(f"\n  {'─' * 45}")
    print(f"  Fleet distance: {total_distance:.2f} km")
    print(f"  Fleet spoilage: Rs {total_spoilage:.4f}")
    print(f"  Combined cost:  Rs {total_distance + total_spoilage:.4f}")
    print(f"{'=' * 55}")

    return {
        "routes":         vehicle_routes,
        "total_distance": round(total_distance, 4),
        "total_spoilage": round(total_spoilage, 4),
        "total_cost":     round(total_distance + total_spoilage, 4)
    }

# ─────────────────────────────────────────
# SELF-TEST — dummy QAOA output
# Includes one infeasible result to verify repair
# ─────────────────────────────────────────
if __name__ == "__main__":

    dummy = {
        "V1": {
            "clinic_ids": [1, 2, 3, 5],
            "sub_cluster_results": [
                {"clinic_ids": [1, 2, 3], "route": [2, 1, 3],       "feasible": True},
                {"clinic_ids": [1, 2, 5], "route": [1, 5, 2],       "feasible": True},
                {"clinic_ids": [1, 3, 5], "route": [None, 1, 5],    "feasible": False},  # infeasible
                {"clinic_ids": [2, 3, 5], "route": [5, 2, 3],       "feasible": True},
            ]
        },
        "V2": {
            "clinic_ids": [7, 8, 9, 10],
            "sub_cluster_results": [
                {"clinic_ids": [7, 8, 9],   "route": [8, 7, 9],    "feasible": True},
                {"clinic_ids": [7, 8, 10],  "route": [7, 10, 8],   "feasible": True},
                {"clinic_ids": [7, 9, 10],  "route": [9, 7, 10],   "feasible": True},
                {"clinic_ids": [8, 9, 10],  "route": [10, 8, 9],   "feasible": True},
            ]
        },
        "V3": {
            "clinic_ids": [6, 4],
            "sub_cluster_results": [
                {"clinic_ids": [6, 4], "route": [6, 4], "feasible": True},
            ]
        }
    }

    output = stitch_and_repair(dummy)
