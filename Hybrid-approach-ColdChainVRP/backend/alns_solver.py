"""
alns_solver.py — Adaptive Large Neighborhood Search (ALNS) Metaheuristic Solver.

Implements a state-of-the-art classical metaheuristic for multi-vehicle cold-chain VRP.
It starts with an initial heuristic solution and iteratively:
  1. Ruins the solution by removing a subset of clinics (randomly or by cost).
  2. Recreates the solution by greedily inserting the clinics in their optimal positions.
  3. Accepts/rejects improvements using simulated annealing.

Exposes the same solve_scenario() interface as classical_solver.py.
"""

import time
import random
import copy
import numpy as np
from classical_solver import solve_scenario as solve_initial_classical, route_cost

def solve_scenario(sc_module) -> dict:
    """
    Run ALNS metaheuristic on a scenario module.
    Returns the same schema as classical_solver.solve_scenario().
    """
    t0 = time.time()
    label = getattr(sc_module, "__name__", "scenario")
    print(f"\n{'='*55}")
    print(f"  ALNS METAHEURISTIC SOLVER — {label}")
    print(f"{'='*55}")

    # Load initial solution from the local search heuristic (NN+2opt)
    initial_res = solve_initial_classical(sc_module)
    if initial_res.get("status") != "ok":
        return initial_res

    clinics = sc_module.CLINICS
    vehicles = sc_module.VEHICLES
    demands = sc_module.DEMANDS
    dm = np.asarray(sc_module.DISTANCE_MATRIX, dtype=float)
    spoilage = sc_module.SPOILAGE
    energy_rate = sc_module.ENERGY_RATE
    avg_speed = float(sc_module.AVG_SPEED_KMH)
    clinic_names = {c["id"]: c["name"] for c in clinics}
    
    capacity = {
        temp: vehicles[0]["compartments"][temp]["capacity"]
        for temp in vehicles[0]["compartments"]
    }

    # Initial state
    current_routes = {}
    for vid, vdata in initial_res["routes"].items():
        # Exclude depot endpoints (store only inner clinic list)
        current_routes[vid] = [c for c in vdata["route"] if c != 0]

    # Evaluate the total cost of a routes dictionary
    def evaluate_solution(routes_dict):
        total_dist = 0.0
        total_spoil = 0.0
        total_refrig = 0.0
        feasible = True
        
        for vid, r in routes_dict.items():
            bd = route_cost(r, demands, dm, spoilage, energy_rate, avg_speed)
            total_dist += bd["distance"]
            total_spoil += bd["spoilage"]
            total_refrig += bd["refrigeration"]
            
            # Capacity check
            for temp in ("frozen", "chilled", "ambient"):
                used = sum(demands[c][temp] for c in r)
                if used > capacity[temp]:
                    feasible = False
                    
        total_cost = total_dist + total_spoil + total_refrig
        # Apply a high penalty for infeasibility to guide search
        if not feasible:
            total_cost += 1e5
        return total_cost, feasible

    best_routes = copy.deepcopy(current_routes)
    best_cost, best_feasible = evaluate_solution(best_routes)
    
    current_cost = best_cost
    current_feasible = best_feasible

    # ALNS Parameters
    n_iterations = 100
    temp = 100.0
    cooling_rate = 0.95
    ruin_size = 2  # Number of clinics to remove per iteration

    all_clinic_ids = [c["id"] for c in clinics]

    # ── ALNS Main Loop ──
    for iteration in range(n_iterations):
        # 1. Ruin Phase: randomly select and remove clinics
        ruined_routes = copy.deepcopy(current_routes)
        removed_clinics = []
        
        # Collect all active clinics in current solution
        active_clinics = []
        for r in ruined_routes.values():
            active_clinics.extend(r)
            
        if len(active_clinics) >= ruin_size:
            removed_clinics = random.sample(active_clinics, ruin_size)
            for cid in removed_clinics:
                for vid in ruined_routes:
                    if cid in ruined_routes[vid]:
                        ruined_routes[vid].remove(cid)
                        break
        else:
            # Fallback if too few clinics
            removed_clinics = list(active_clinics)
            for vid in ruined_routes:
                ruined_routes[vid] = []

        # 2. Recreate Phase: insert ruined clinics in their optimal feasible positions
        # Shuffle the removed clinics to randomize insertion order
        random.shuffle(removed_clinics)
        
        for cid in removed_clinics:
            best_insert_vid = None
            best_insert_idx = None
            best_insert_cost = float("inf")
            
            # Try inserting clinic 'cid' into every position in every vehicle route
            for vid, route in ruined_routes.items():
                # Check capacity bounds first
                cap_valid = True
                for temp_key in ("frozen", "chilled", "ambient"):
                    used = sum(demands[c][temp_key] for c in route) + demands[cid][temp_key]
                    if used > capacity[temp_key]:
                        cap_valid = False
                        break
                
                # If capacity is violated, allow but with penalty (will be selected only if no feasible fits exist)
                penalty = 0.0 if cap_valid else 1e4
                
                for idx in range(len(route) + 1):
                    test_route = route[:idx] + [cid] + route[idx:]
                    test_dict = copy.deepcopy(ruined_routes)
                    test_dict[vid] = test_route
                    
                    cost, _ = evaluate_solution(test_dict)
                    cost += penalty
                    
                    if cost < best_insert_cost:
                        best_insert_cost = cost
                        best_insert_vid = vid
                        best_insert_idx = idx
            
            # Perform insertion
            if best_insert_vid is not None:
                ruined_routes[best_insert_vid].insert(best_insert_idx, cid)

        # 3. Acceptance Phase (Simulated Annealing)
        cand_cost, cand_feasible = evaluate_solution(ruined_routes)
        
        delta = cand_cost - current_cost
        accept = False
        if delta < 0:
            accept = True
        else:
            p = np.exp(-delta / max(temp, 1e-3))
            if random.random() < p:
                accept = True
                
        if accept:
            current_routes = ruined_routes
            current_cost = cand_cost
            current_feasible = cand_feasible
            
            # Check global best
            if cand_cost < best_cost:
                best_routes = copy.deepcopy(ruined_routes)
                best_cost = cand_cost
                best_feasible = cand_feasible

        # Cool temperature
        temp *= cooling_rate

    # Reconstruct the output dictionary matching our standard schema
    routes_out = {}
    total_dist = 0.0
    total_spoil = 0.0
    total_refrig = 0.0
    
    for vehicle_id, inner in best_routes.items():
        route = [0] + inner + [0]
        
        bd = route_cost(inner, demands, dm, spoilage, energy_rate, avg_speed)
        
        cap_check = {}
        feasible = True
        for temp_key in ("frozen", "chilled", "ambient"):
            used = sum(demands[cid][temp_key] for cid in inner)
            cap_limit = capacity[temp_key]
            cap_check[temp_key] = {"used": used, "cap": cap_limit}
            if used > cap_limit:
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
            "computation_time": round(time.time() - t0, 4),
            "solver":           "ALNS Metaheuristic",
        }
        
        total_dist   += bd["distance"]
        total_spoil  += bd["spoilage"]
        total_refrig += bd["refrigeration"]

    total_time = round(time.time() - t0, 4)
    total_cost = round(total_dist + total_spoil + total_refrig, 4)

    print(f"\n  ALNS Fleet dist : {total_dist:.2f} km")
    print(f"  ALNS Fleet spoil : Rs {total_spoil:.4f}")
    print(f"  ALNS Fleet total : Rs {total_cost:.4f}")
    print(f"  ALNS solve time  : {total_time:.3f}s")

    return {
        "solver":              "ALNS Metaheuristic",
        "routes":              routes_out,
        "fleet_distance":      round(total_dist, 4),
        "fleet_spoilage":      round(total_spoil, 4),
        "fleet_refrigeration": round(total_refrig, 4),
        "fleet_total_cost":    total_cost,
        "total_time":          total_time,
        "status":              "ok",
    }

if __name__ == "__main__":
    import scenario as sc1
    res = solve_scenario(sc1)
    print("\n[ALNS Test] fleet total cost:", res["fleet_total_cost"])
