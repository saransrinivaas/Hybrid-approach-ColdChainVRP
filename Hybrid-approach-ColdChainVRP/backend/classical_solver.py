"""
classical_solver.py — Classical VRP solver for benchmarking against QAOA.

Algorithm: Nearest-Neighbour construction → 2-opt → OR-opt.
Uses the identical cost function (distance + spoilage + refrigeration)
as qubo_builder.py so results are directly comparable.

Works with any scenario module (scenario.py or scenario2.py).
Solves per-vehicle (same structure as QAOA) for a fair comparison.
"""

import sys
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

import itertools
import time
import warnings
import numpy as np

# Suppress scipy/sklearn sparse matrix efficiency warnings — they are harmless
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*sparsity.*")
warnings.filterwarnings("ignore", message=".*CSC.*")
warnings.filterwarnings("ignore", message=".*CSR.*")


# ─────────────────────────────────────────
# COST FUNCTION
# Identical semantics to qubo_builder.py.
# route: inner list of clinic IDs (no depot endpoints).
# ─────────────────────────────────────────
def route_cost(route: list, demands: dict, distance_matrix,
               spoilage: dict, energy_rate: dict,
               avg_speed: float = 30.0) -> dict:
    """
    Compute distance + spoilage + refrigeration for an inner route.
    Returns a breakdown dict.
    """
    if not route:
        return {"distance": 0.0, "spoilage": 0.0, "refrigeration": 0.0, "total": 0.0}

    full = [0] + route + [0]

    # Distance
    distance = sum(
        distance_matrix[full[i]][full[i + 1]]
        for i in range(len(full) - 1)
    )

    # Cumulative arrival times at each clinic stop
    cum_time = 0.0
    arrival_times = []
    for i in range(1, len(full)):
        cum_time += distance_matrix[full[i - 1]][full[i]] / avg_speed
        if full[i] != 0:
            arrival_times.append(cum_time)

    # Spoilage
    spoilage_cost = 0.0
    for idx, cid in enumerate(route):
        arr = arrival_times[idx]
        for temp in ("frozen", "chilled", "ambient"):
            alpha  = spoilage[temp]["alpha"]
            value  = spoilage[temp]["value"]
            demand = demands[cid][temp]
            spoilage_cost += value * alpha * arr * demand

    # Refrigeration (constant for full trip duration)
    route_duration = arrival_times[-1] if arrival_times else 0.0
    refrigeration  = sum(energy_rate[t] * route_duration
                         for t in ("frozen", "chilled", "ambient"))

    total = distance + spoilage_cost + refrigeration
    return {
        "distance":      round(distance, 4),
        "spoilage":      round(spoilage_cost, 4),
        "refrigeration": round(refrigeration, 4),
        "total":         round(total, 4),
    }


# ─────────────────────────────────────────
# NEAREST-NEIGHBOUR CONSTRUCTION
# ─────────────────────────────────────────
def nearest_neighbour(clinic_ids: list, distance_matrix) -> list:
    """Greedy NN starting from depot (id=0). Returns inner route."""
    unvisited = list(clinic_ids)
    route     = []
    current   = 0
    while unvisited:
        nearest = min(unvisited, key=lambda cid: distance_matrix[current][cid])
        route.append(nearest)
        unvisited.remove(nearest)
        current = nearest
    return route


# ─────────────────────────────────────────
# 2-OPT LOCAL SEARCH
# ─────────────────────────────────────────
def two_opt(route: list, demands, distance_matrix,
            spoilage, energy_rate, avg_speed=30.0) -> list:
    """Reverse sub-segments to reduce total cost."""
    if len(route) <= 2:
        return route
    best      = list(route)
    best_cost = route_cost(best, demands, distance_matrix,
                           spoilage, energy_rate, avg_speed)["total"]
    improved  = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 2, len(best)):
                candidate = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                c_cost    = route_cost(candidate, demands, distance_matrix,
                                       spoilage, energy_rate, avg_speed)["total"]
                if c_cost < best_cost - 1e-9:
                    best, best_cost, improved = candidate, c_cost, True
                    break
            if improved:
                break
    return best


# ─────────────────────────────────────────
# OR-OPT (relocate single nodes)
# ─────────────────────────────────────────
def or_opt(route: list, demands, distance_matrix,
           spoilage, energy_rate, avg_speed=30.0) -> list:
    """Try moving each node to every other position."""
    if len(route) <= 2:
        return route
    best      = list(route)
    best_cost = route_cost(best, demands, distance_matrix,
                           spoilage, energy_rate, avg_speed)["total"]
    improved  = True
    while improved:
        improved = False
        for i in range(len(best)):
            node      = best[i]
            remaining = best[:i] + best[i + 1:]
            for j in range(len(remaining) + 1):
                candidate = remaining[:j] + [node] + remaining[j:]
                c_cost    = route_cost(candidate, demands, distance_matrix,
                                       spoilage, energy_rate, avg_speed)["total"]
                if c_cost < best_cost - 1e-9:
                    best, best_cost, improved = candidate, c_cost, True
                    break
            if improved:
                break
    return best


# ─────────────────────────────────────────
# CLUSTER CLINICS TO VEHICLES
# Reuses the same K-Means + greedy repair
# logic as clustering.py but parameterised.
# ─────────────────────────────────────────
def cluster_clinics(clinics, vehicles, demands, distance_matrix, sc_module=None):
    """
    Assign clinics to vehicles using our robust dynamic fleet-capping K-Means 
    and First-Fit bin-packing trip splitter.
    Returns {trip_id: [clinic_id, ...]}
    """
    import clustering as _cl
    
    # Run the modular clustering pipeline to get cap-balanced vehicle routes and trips
    vehicle_routes = _cl.build_clusters(sc_module)
    
    assignments = {}
    for vehicle_id, trips in vehicle_routes:
        assignments[vehicle_id] = [cid for trip in trips for cid in trip]
    return assignments


# ─────────────────────────────────────────
# SOLVE ONE VEHICLE
# ─────────────────────────────────────────
def solve_vehicle(vehicle_id, clinic_ids, demands, distance_matrix,
                  spoilage, energy_rate, avg_speed=30.0):
    """NN + 2-opt + OR-opt for one vehicle's clinic set."""
    start = time.time()

    if not clinic_ids:
        return {
            "vehicle_id": vehicle_id, "route": [0, 0], "inner_route": [],
            "cost_breakdown": {"distance": 0, "spoilage": 0,
                               "refrigeration": 0, "total": 0},
            "solver": "Classical (NN+2opt+ORopt)",
            "computation_time": 0.0,
        }

    nn    = nearest_neighbour(clinic_ids, distance_matrix)
    opt   = two_opt(nn, demands, distance_matrix, spoilage, energy_rate, avg_speed)
    opt   = or_opt(opt, demands, distance_matrix, spoilage, energy_rate, avg_speed)
    cost  = route_cost(opt, demands, distance_matrix, spoilage, energy_rate, avg_speed)

    return {
        "vehicle_id":       vehicle_id,
        "route":            [0] + opt + [0],
        "inner_route":      opt,
        "cost_breakdown":   cost,
        "solver":           "Classical (NN+2opt+ORopt)",
        "computation_time": round(time.time() - start, 4),
    }


# ─────────────────────────────────────────
# SOLVE FULL SCENARIO MODULE
# Accepts a scenario module (scenario or scenario2)
# ─────────────────────────────────────────
def solve_scenario(sc_module) -> dict:
    """
    Run the classical solver on a scenario module.
    sc_module must expose: DEPOT, CLINICS, VEHICLES, DEMANDS,
    DISTANCE_MATRIX, SPOILAGE, ENERGY_RATE, AVG_SPEED_KMH.
    """
    clinics      = sc_module.CLINICS
    vehicles     = sc_module.VEHICLES
    demands      = sc_module.DEMANDS
    dm           = sc_module.DISTANCE_MATRIX
    spoilage     = sc_module.SPOILAGE
    energy_rate  = sc_module.ENERGY_RATE
    avg_speed    = sc_module.AVG_SPEED_KMH
    clinic_names = {c["id"]: c["name"] for c in clinics}
    capacity     = {
        temp: vehicles[0]["compartments"][temp]["capacity"]
        for temp in vehicles[0]["compartments"]
    }

    label = getattr(sc_module, "__name__", "scenario")
    print(f"\n{'='*55}")
    print(f"  CLASSICAL SOLVER — {label}")
    print(f"  {len(clinics)} clinics / {len(vehicles)} vehicles")
    print(f"{'='*55}")

    assignments = cluster_clinics(clinics, vehicles, demands, dm, sc_module)
    print(f"  Clustering: {assignments}")

    total_start  = time.time()
    routes_out   = {}
    total_dist   = 0.0
    total_spoil  = 0.0
    total_refrig = 0.0

    for vehicle_id, clinic_ids in assignments.items():
        print(f"\n  [{vehicle_id}] clinics={clinic_ids}")
        res   = solve_vehicle(vehicle_id, clinic_ids, demands, dm,
                              spoilage, energy_rate, avg_speed)
        route = res["route"]
        inner = res["inner_route"]
        bd    = res["cost_breakdown"]

        cap_check = {}
        feasible  = True
        for temp in ("frozen", "chilled", "ambient"):
            used = sum(demands[cid][temp] for cid in inner)
            cap  = capacity[temp]
            cap_check[temp] = {"used": used, "cap": cap}
            if used > cap:
                feasible = False

        stops = [
            {
                "id": cid,
                "name": "Depot" if cid == 0 else clinic_names.get(cid, f"C{cid}"),
                "lat": sc_module.DEPOT["lat"] if cid == 0 else next((c["lat"] for c in sc_module.CLINICS if c["id"] == cid), None),
                "lon": sc_module.DEPOT["lon"] if cid == 0 else next((c["lon"] for c in sc_module.CLINICS if c["id"] == cid), None)
            }
            for cid in route
        ]

        routes_out[vehicle_id] = {
            "route":            route,
            "stops":            stops,
            "distance_km":      bd["distance"],
            "spoilage_rs":      bd["spoilage"],
            "refrigeration_rs": bd["refrigeration"],
            "total_cost_rs":    bd["total"],
            "feasible":         feasible,
            "capacity":         cap_check,
            "computation_time": res["computation_time"],
            "solver":           res["solver"],
        }

        total_dist   += bd["distance"]
        total_spoil  += bd["spoilage"]
        total_refrig += bd["refrigeration"]

        status    = "[OK]" if feasible else "[INFEASIBLE]"
        stops_str = " → ".join(s["name"] for s in stops)
        print(f"  {status} {stops_str}")
        print(f"    dist={bd['distance']:.2f} km  "
              f"spoilage=Rs {bd['spoilage']:.4f}  "
              f"total=Rs {bd['total']:.4f}  "
              f"time={res['computation_time']:.3f}s")

    total_time = round(time.time() - total_start, 4)
    total_cost = round(total_dist + total_spoil + total_refrig, 4)

    print(f"\n  Fleet distance : {total_dist:.2f} km")
    print(f"  Fleet spoilage : Rs {total_spoil:.4f}")
    print(f"  Fleet total    : Rs {total_cost:.4f}")
    print(f"  Total time     : {total_time:.3f}s")

    return {
        "solver":              "Classical (NN+2opt+ORopt)",
        "routes":              routes_out,
        "fleet_distance":      round(total_dist, 4),
        "fleet_spoilage":      round(total_spoil, 4),
        "fleet_refrigeration": round(total_refrig, 4),
        "fleet_total_cost":    total_cost,
        "total_time":          total_time,
        "status":              "ok",
    }


# ─────────────────────────────────────────
# MAIN — self-test on both scenarios
# ─────────────────────────────────────────
if __name__ == "__main__":
    import scenario as sc1
    try:
        import scenario_dynamic as sc2
    except ImportError:
        sc2 = sc1

    for sc in (sc1, sc2):
        if sc:
            result = solve_scenario(sc)
            print(f"\n[{getattr(sc, '__name__', 'scenario')}] Classical total: Rs {result['fleet_total_cost']:.4f}")
