"""
pulp_solver.py — Integer Linear Programming solver using PuLP + CBC.

Formulates CVRPTW with:
  • 3 demand dimensions (frozen, chilled, ambient)
  • Time windows at clinics
  • MTZ subtour elimination constraints

Since PuLP/CBC is open source, this solver acts as a reliable classical ILP baseline.
"""

import time
import numpy as np

try:
    import pulp
    PULP_AVAILABLE = True
except ImportError:
    PULP_AVAILABLE = False


def solve_scenario(sc_module) -> dict:
    """
    Run PuLP + CBC ILP solver on a scenario module (scenario.py or scenario2.py).
    Same return shape as classical_solver.solve_scenario().
    """
    t0 = time.time()
    label = getattr(sc_module, "__name__", "scenario")
    print(f"\n{'='*55}")
    print(f"  PULP/CBC ILP SOLVER — {label}")
    print(f"{'='*55}")

    if not PULP_AVAILABLE:
        print("  [WARN] PuLP is not installed. Skipping PuLP solver.")
        return {
            "solver": "PuLP/CBC (ILP) — UNAVAILABLE",
            "routes": {},
            "fleet_distance": 0.0,
            "fleet_spoilage": 0.0,
            "fleet_refrigeration": 0.0,
            "fleet_total_cost": 0.0,
            "total_time": 0.0,
            "status": "unavailable",
        }

    try:
        clinics = sc_module.CLINICS
        vehicles = sc_module.VEHICLES
        demands = sc_module.DEMANDS
        dm = np.asarray(sc_module.DISTANCE_MATRIX, dtype=float)
        tw = sc_module.TIME_WINDOWS
        spoilage = sc_module.SPOILAGE
        energy_rate = sc_module.ENERGY_RATE
        avg_speed = float(sc_module.AVG_SPEED_KMH)
        clinic_names = {c["id"]: c["name"] for c in clinics}

        # Node index mapping: 0 is depot, 1..N are clinics
        nodes = [0] + [c["id"] for c in clinics]
        n_nodes = len(nodes)
        n_vehicles = len(vehicles)

        # Precompute travel times (hours)
        travel_times = dm / max(avg_speed, 1e-6)

        # Capacity capacities
        cap = {
            "frozen": [v["compartments"]["frozen"]["capacity"] for v in vehicles],
            "chilled": [v["compartments"]["chilled"]["capacity"] for v in vehicles],
            "ambient": [v["compartments"]["ambient"]["capacity"] for v in vehicles],
        }

        # Define PuLP Problem
        prob = pulp.LpProblem("CVRPTW", pulp.LpMinimize)

        # Decision Variables
        # x[i, j, k] = 1 if vehicle k travels from node i to node j
        x = pulp.LpVariable.dicts("x",
                                  ((i, j, k) for i in range(n_nodes) for j in range(n_nodes) for k in range(n_vehicles)),
                                  cat=pulp.LpBinary)

        # Arrival time u[i, k] of vehicle k at node i
        u = pulp.LpVariable.dicts("u",
                                  ((i, k) for i in range(n_nodes) for k in range(n_vehicles)),
                                  lowBound=0.0,
                                  upBound=24.0,
                                  cat=pulp.LpContinuous)

        # Cumulative compartment loads w[i, temp, k]
        w = {}
        for temp in ("frozen", "chilled", "ambient"):
            w[temp] = pulp.LpVariable.dicts(f"w_{temp}",
                                            ((i, k) for i in range(n_nodes) for k in range(n_vehicles)),
                                            lowBound=0.0,
                                            cat=pulp.LpContinuous)

        # Objective Function: Minimize total travel distance
        prob += pulp.lpSum(dm[nodes[i], nodes[j]] * x[i, j, k]
                           for i in range(n_nodes)
                           for j in range(n_nodes)
                           for k in range(n_vehicles))

        # Constraints
        # 1. No self loops
        for i in range(n_nodes):
            for k in range(n_vehicles):
                prob += x[i, i, k] == 0

        # 2. Each clinic visited exactly once
        for i in range(1, n_nodes):
            prob += pulp.lpSum(x[j, i, k] for j in range(n_nodes) for k in range(n_vehicles)) == 1

        # 3. Flow conservation: in-flow = out-flow
        for k in range(n_vehicles):
            for i in range(n_nodes):
                prob += pulp.lpSum(x[j, i, k] for j in range(n_nodes)) == \
                        pulp.lpSum(x[i, j, k] for j in range(n_nodes))

        # 4. Each vehicle leaves the depot at most once
        for k in range(n_vehicles):
            prob += pulp.lpSum(x[0, j, k] for j in range(1, n_nodes)) <= 1

        # Big-M value: 24h is the horizon
        M = 24.0
        for k in range(n_vehicles):
            # Depot start time
            prob += u[0, k] == 0.0
            for i in range(n_nodes):
                for j in range(1, n_nodes):
                    # u_i + t_ij - u_j <= M(1 - x_ijk)
                    prob += u[i, k] + travel_times[nodes[i], nodes[j]] - u[j, k] <= M * (1 - x[i, j, k])

        # Clinic time window bounds
        for i in range(1, n_nodes):
            cid = nodes[i]
            tw_start, tw_end = tw[cid]
            for k in range(n_vehicles):
                prob += u[i, k] >= tw_start
                prob += u[i, k] <= tw_end

        # 6. Capacity constraints (MTZ-style for 3 compartments)
        for k in range(n_vehicles):
            for temp in ("frozen", "chilled", "ambient"):
                # Depot initial demand tracking
                prob += w[temp][0, k] == 0.0
                
                # Bounds
                for i in range(1, n_nodes):
                    cid = nodes[i]
                    dem = demands[cid][temp]
                    cap_val = cap[temp][k]
                    prob += w[temp][i, k] >= dem
                    prob += w[temp][i, k] <= cap_val

                # Transition
                for i in range(n_nodes):
                    for j in range(1, n_nodes):
                        cid_j = nodes[j]
                        dem_j = demands[cid_j][temp]
                        cap_val = cap[temp][k]
                        # w_ik + d_j - w_jk <= Q(1 - x_ijk)
                        prob += w[temp][i, k] + dem_j - w[temp][j, k] <= cap_val * (1 - x[i, j, k])

        # Solve the model using CBC solver with quiet option
        # timeLimit=20 keeps response time reasonable; threads speeds up MIP search
        solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=45.0)
        status = prob.solve(solver)

        if status != pulp.LpStatusOptimal and prob.sol_status != pulp.LpSolutionIntegerFeasible:
            print("  [FAIL] PuLP/CBC: no feasible assignment found.")
            return {
                "solver": "PuLP/CBC (ILP) — FAILED",
                "routes": {},
                "fleet_distance": 0.0,
                "fleet_spoilage": 0.0,
                "fleet_refrigeration": 0.0,
                "fleet_total_cost": 0.0,
                "total_time": round(time.time() - t0, 4),
                "status": "failed",
            }

        # Reconstruct routes
        routes_out = {}
        total_dist = 0.0
        total_spoil = 0.0
        total_refrig = 0.0

        from classical_solver import route_cost

        for k in range(n_vehicles):
            vehicle_id = vehicles[k]["id"]
            
            # Find sequence
            active_arcs = []
            for i in range(n_nodes):
                for j in range(n_nodes):
                    val = pulp.value(x[i, j, k])
                    if val is not None and val > 0.5:
                        active_arcs.append((i, j))

            if not active_arcs:
                routes_out[vehicle_id] = {
                    "route": [0, 0],
                    "stops": [{"id": 0, "name": "Depot"}],
                    "distance_km": 0.0,
                    "spoilage_rs": 0.0,
                    "refrigeration_rs": 0.0,
                    "total_cost_rs": 0.0,
                    "feasible": True,
                    "capacity": {
                        t: {"used": 0, "cap": cap[t][k]}
                        for t in ("frozen", "chilled", "ambient")
                    },
                    "computation_time": round(time.time() - t0, 4),
                    "solver": "PuLP/CBC (ILP)",
                }
                continue

            # Build ordered path starting at 0
            curr = 0
            route_indices = [0]
            visited_in_loop = set([0])
            while True:
                next_node = None
                for arc in active_arcs:
                    if arc[0] == curr:
                        next_node = arc[1]
                        break
                if next_node is None or next_node in visited_in_loop:
                    if next_node == 0:
                        route_indices.append(0)
                    break
                route_indices.append(next_node)
                visited_in_loop.add(next_node)
                curr = next_node

            if route_indices[-1] != 0:
                route_indices.append(0)

            # Map back to clinic IDs
            id_route = [nodes[idx] for idx in route_indices]
            inner = [cid for cid in id_route if cid != 0]

            # Re-evaluate with exact cost function for fair comparison
            bd = route_cost(inner, demands, dm, spoilage, energy_rate, avg_speed)

            cap_check = {}
            feasible = True
            for temp in ("frozen", "chilled", "ambient"):
                used = sum(demands[cid][temp] for cid in inner)
                capacity_limit = cap[temp][k]
                cap_check[temp] = {"used": used, "cap": capacity_limit}
                if used > capacity_limit:
                    feasible = False

            stops = [
                {
                    "id": cid,
                    "name": "Depot" if cid == 0 else clinic_names.get(cid, f"C{cid}"),
                    "lat": sc_module.DEPOT["lat"] if cid == 0 else next((c["lat"] for c in sc_module.CLINICS if c["id"] == cid), None),
                    "lon": sc_module.DEPOT["lon"] if cid == 0 else next((c["lon"] for c in sc_module.CLINICS if c["id"] == cid), None)
                }
                for cid in id_route
            ]

            routes_out[vehicle_id] = {
                "route": id_route,
                "stops": stops,
                "distance_km": bd["distance"],
                "spoilage_rs": bd["spoilage"],
                "refrigeration_rs": bd["refrigeration"],
                "total_cost_rs": bd["total"],
                "feasible": feasible,
                "capacity": cap_check,
                "computation_time": round(time.time() - t0, 4),
                "solver": "PuLP/CBC (ILP)",
            }

            total_dist += bd["distance"]
            total_spoil += bd["spoilage"]
            total_refrig += bd["refrigeration"]

            status = "[OK]" if feasible else "[INFEASIBLE]"
            stops_str = " → ".join(s["name"] for s in stops)
            print(f"  {status} [{vehicle_id}] {stops_str}")
            print(
                f"    dist={bd['distance']:.2f} km  spoilage=Rs {bd['spoilage']:.4f}  "
                f"total=Rs {bd['total']:.4f}"
            )

        total_time = round(time.time() - t0, 4)
        total_cost = round(total_dist + total_spoil + total_refrig, 4)

        print(f"\n  Fleet distance : {total_dist:.2f} km")
        print(f"  Fleet spoilage : Rs {total_spoil:.4f}")
        print(f"  Fleet total    : Rs {total_cost:.4f}")
        print(f"  PuLP/CBC solve : {total_time:.3f}s")

        return {
            "solver": "PuLP/CBC (ILP)",
            "routes": routes_out,
            "fleet_distance": round(total_dist, 4),
            "fleet_spoilage": round(total_spoil, 4),
            "fleet_refrigeration": round(total_refrig, 4),
            "fleet_total_cost": total_cost,
            "total_time": total_time,
            "status": "ok",
        }

    except Exception as e:
        import traceback
        print(f"  [ERROR] PuLP solver error: {e}")
        traceback.print_exc()
        return {
            "solver": "PuLP/CBC (ILP) — ERROR",
            "routes": {},
            "fleet_distance": 0.0,
            "fleet_spoilage": 0.0,
            "fleet_refrigeration": 0.0,
            "fleet_total_cost": 0.0,
            "total_time": round(time.time() - t0, 4),
            "status": "failed",
        }


if __name__ == "__main__":
    import scenario as sc1
    try:
        import scenario_dynamic as sc2
    except ImportError:
        sc2 = sc1

    for sc in (sc1, sc2):
        if sc:
            r = solve_scenario(sc)
            print(f"\n[{getattr(sc, '__name__', 'scenario')}] PuLP fleet total: Rs {r['fleet_total_cost']:.4f}")
