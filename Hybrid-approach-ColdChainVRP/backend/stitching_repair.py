import functools
import numpy as np
import threading
import sys
import types

try:
    import scenario_dynamic as scenario
except ImportError:
    import scenario

import temp_preprocessing

_local = threading.local()

class LocalProxy:
    def __init__(self, name, default_factory):
        self._name = name
        self._default_factory = default_factory

    def _get_current_object(self):
        if not hasattr(_local, self._name):
            setattr(_local, self._name, self._default_factory())
        return getattr(_local, self._name)

    def __getitem__(self, key):
        return self._get_current_object()[key]

    def __setitem__(self, key, value):
        self._get_current_object()[key] = value

    def __len__(self):
        return len(self._get_current_object())

    def __iter__(self):
        return iter(self._get_current_object())

    def __contains__(self, item):
        return item in self._get_current_object()

    def __getattr__(self, name):
        return getattr(self._get_current_object(), name)

    def __truediv__(self, other):
        return self._get_current_object() / other

    def __rtruediv__(self, other):
        return other / self._get_current_object()

    def __add__(self, other):
        return self._get_current_object() + other

    def __radd__(self, other):
        return other + self._get_current_object()

    def __mul__(self, other):
        return self._get_current_object() * other

    def __rmul__(self, other):
        return other * self._get_current_object()

    def __str__(self):
        return str(self._get_current_object())

    def __repr__(self):
        return repr(self._get_current_object())

class _StitchingRepairModule(types.ModuleType):
    def __setattr__(self, name, value):
        if name in ["CLINICS", "DEPOT", "DISTANCE_MATRIX", "DEMANDS", "SPOILAGE", "AVG_SPEED_KMH", "AVG_SPEED", "CAPACITY", "ALL_CLINICS"]:
            setattr(_local, name, value)
            if name == "AVG_SPEED_KMH":
                setattr(_local, "AVG_SPEED", value)
        else:
            super().__setattr__(name, value)

# Set the module's class to the custom class
sys.modules[__name__].__class__ = _StitchingRepairModule

# Initialize proxies in the module namespace
CLINICS = LocalProxy("CLINICS", lambda: scenario.CLINICS)
DEPOT = LocalProxy("DEPOT", lambda: scenario.DEPOT)
DISTANCE_MATRIX = LocalProxy("DISTANCE_MATRIX", lambda: scenario.DISTANCE_MATRIX)
DEMANDS = LocalProxy("DEMANDS", lambda: scenario.DEMANDS)
SPOILAGE = LocalProxy("SPOILAGE", lambda: scenario.SPOILAGE)
AVG_SPEED_KMH = LocalProxy("AVG_SPEED_KMH", lambda: scenario.AVG_SPEED_KMH)
CAPACITY = LocalProxy("CAPACITY", lambda: temp_preprocessing.CAPACITY)
AVG_SPEED = LocalProxy("AVG_SPEED", lambda: scenario.AVG_SPEED_KMH)
ALL_CLINICS = LocalProxy("ALL_CLINICS", lambda: [c["id"] for c in scenario.CLINICS])

DEPOT_ID = 0

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
    """
    Cumulative spoilage cost for a route with depot endpoints.
    Uses real hop-by-hop arrival time per clinic (not average-hop estimation).
    When a return-to-depot leg is encountered, the clock resets to 0 for the
    next trip leg so multi-trip virtual vehicles are handled correctly.
    """
    total    = 0.0
    cum_time = 0.0
    for i in range(1, len(route)):
        prev = route[i - 1]
        curr = route[i]
        leg_time = DISTANCE_MATRIX[prev][curr] / AVG_SPEED
        cum_time += leg_time
        if curr == DEPOT_ID:
            # Starting a new trip leg — reset cumulative clock
            cum_time = 0.0
            continue
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
    Quality-weighted pairwise voting: for each pair (a, b), accumulate
    votes weighted by sub-cluster quality.
    
    Weight rules:
      - Feasible without repair  → weight 3
      - Feasible after repair    → weight 1
      - Infeasible / has None    → weight 0 (skip)
    
    Ties broken first by spoilage urgency, then by depot proximity.
    Returns ordered list of clinic IDs.
    """
    n = len(all_clinic_ids)

    if n <= 1:
        return list(all_clinic_ids)

    if n == 2:
        a, b = all_clinic_ids
        # Closer to depot goes first
        return [a, b] if DISTANCE_MATRIX[0][a] <= DISTANCE_MATRIX[0][b] else [b, a]

    # Build pairwise preference weights
    pref = {(a, b): 0.0 for a in all_clinic_ids for b in all_clinic_ids if a != b}

    for res in sub_results:
        route = res.get("route", [])
        if not route or None in route:
            continue
        # Quality weight: pristine feasible sub-clusters carry 3× weight
        was_repaired = res.get("repaired", False)
        is_feasible  = res.get("feasible", False)
        if not is_feasible:
            continue
        vote_weight = 1.0 if was_repaired else 3.0
        for i in range(len(route)):
            for j in range(i + 1, len(route)):
                key = (route[i], route[j])
                if key in pref:
                    pref[key] += vote_weight

    def compare(a, b):
        ab = pref.get((a, b), 0.0)
        ba = pref.get((b, a), 0.0)
        if ab > ba + 1e-9:
            return -1      # a before b
        if ba > ab + 1e-9:
            return 1       # b before a
        # Tie: place higher-spoilage clinic first to minimise decay time
        def spoilage_urgency(cid):
            d = DEMANDS.get(cid, {})
            return sum(
                SPOILAGE[t]["alpha"] * SPOILAGE[t]["value"] * d.get(t, 0)
                for t in ("frozen", "chilled", "ambient")
            )
        sa, sb = spoilage_urgency(a), spoilage_urgency(b)
        if abs(sa - sb) > 1e-9:
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


def or_opt(route: list) -> list:
    """
    Or-opt (single-node relocation) within a route.
    Tries moving each interior clinic to every other interior position.
    Keeps the move with the best improvement in (distance + spoilage).
    Depot endpoints are fixed. Repeats until no improvement is found.
    """
    if len(route) <= 4:
        return route

    inner = route[1:-1]

    def full_cost(inner_r):
        r = [0] + inner_r + [0]
        return route_distance(r) + compute_spoilage(r)

    best_cost = full_cost(inner)
    improved  = True

    while improved:
        improved = False
        for i in range(len(inner)):
            node     = inner[i]
            without  = inner[:i] + inner[i + 1:]  # route without node
            for j in range(len(without) + 1):     # insert before position j
                if j == i:                          # same position, skip
                    continue
                candidate = without[:j] + [node] + without[j:]
                c = full_cost(candidate)
                if c < best_cost - 1e-9:
                    inner     = candidate
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
                
                # Successfully moved, now remove from original
                inner.remove(offload)
                vehicle_routes[vid] = add_depot(inner)
                moved = True
                break
        if not moved:
            print(f"    [WARN] Could not offload Clinic {offload} -> keeping in original route despite overflow")

    return vehicle_routes


# ─────────────────────────────────────────
# PHASE 5.5 — CROSS-VEHICLE OR-OPT
# Relocate single clinics between vehicles
# to reduce total fleet cost.
# ─────────────────────────────────────────
def cross_vehicle_or_opt(vehicle_routes: dict) -> dict:
    """
    For every (source_vehicle, clinic) pair, try inserting that clinic
    into every feasible position of every other vehicle.
    Accepts the move if it reduces total fleet (distance + spoilage).
    Repeats until no improving move is found.
    """
    print("\n  [Cross-vehicle Or-opt]")

    def route_cost(route):
        return route_distance(route) + compute_spoilage(route)

    improved = True
    passes   = 0
    while improved and passes < 10:
        improved = False
        passes  += 1
        for src_vid in list(vehicle_routes.keys()):
            src_route = vehicle_routes[src_vid]
            src_inner = [c for c in src_route if c != DEPOT_ID]
            if len(src_inner) == 0:
                continue
            for node in list(src_inner):
                src_without = [c for c in src_inner if c != node]
                new_src     = add_depot(src_without)

                # Verify feasibility of donor after removal
                ok_src, _ = route_feasible(src_without)
                if not ok_src:
                    continue

                src_cost_before = route_cost(src_route)
                src_cost_after  = route_cost(new_src)

                for dst_vid in vehicle_routes:
                    if dst_vid == src_vid:
                        continue
                    dst_route = vehicle_routes[dst_vid]
                    dst_inner = [c for c in dst_route if c != DEPOT_ID]

                    # Only insert if capacity allows
                    ok_dst, _ = route_feasible(dst_inner + [node])
                    if not ok_dst:
                        continue

                    dst_cost_before = route_cost(dst_route)

                    # Find best insertion position in dst
                    best_delta = 0.0
                    best_new_dst = None
                    for pos in range(len(dst_inner) + 1):
                        candidate_inner = dst_inner[:pos] + [node] + dst_inner[pos:]
                        candidate_route = add_depot(candidate_inner)
                        delta = (route_cost(candidate_route) - dst_cost_before
                                 + src_cost_after - src_cost_before)
                        if delta < best_delta - 1e-9:
                            best_delta   = delta
                            best_new_dst = candidate_route

                    if best_new_dst is not None:
                        vehicle_routes[src_vid] = new_src
                        vehicle_routes[dst_vid] = best_new_dst
                        # Apply 2-opt + or-opt to both affected routes
                        vehicle_routes[src_vid] = or_opt(two_opt(vehicle_routes[src_vid]))
                        vehicle_routes[dst_vid] = or_opt(two_opt(vehicle_routes[dst_vid]))
                        print(f"    Moved Clinic {node}: {src_vid} → {dst_vid}  "
                              f"(fleet saving {-best_delta:.2f})")
                        improved = True
                        break  # restart from fresh pass
                if improved:
                    break
            if improved:
                break

    print(f"  Cross-vehicle Or-opt: {passes} pass(es)")
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

        # Phase 4a: 2-opt
        cost_before = route_distance(full) + compute_spoilage(full)
        full        = two_opt(full)
        # Phase 4b: Or-opt (single-node relocation within route)
        full        = or_opt(full)
        cost_after  = route_distance(full) + compute_spoilage(full)
        print(f"  2-opt + Or-opt: cost {cost_before:.2f} → {cost_after:.2f}  "
              f"(saved {cost_before - cost_after:.2f})")
        print(f"  Route: {full}")

        vehicle_routes[vid] = full

    # Phase 5: Cross-vehicle repair
    vehicle_routes = repair_cross_vehicle(vehicle_routes)

    # Phase 6: Cross-vehicle Or-opt — try relocating a single clinic
    # from one vehicle to another when it reduces total fleet cost.
    vehicle_routes = cross_vehicle_or_opt(vehicle_routes)

    # ── Final summary ──
    clinic_names   = {c["id"]: c["name"] for c in CLINICS}
    total_distance = 0.0
    total_spoilage = 0.0

    print(f"\n{'=' * 55}")
    print("  FINAL ROUTES")
    print(f"{'=' * 55}")

    # Clean up empty routes (routes with only depot endpoints) to eliminate redundant trips
    vehicle_routes = {vid: r for vid, r in vehicle_routes.items() if len([c for c in r if c != DEPOT_ID]) > 0}

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
