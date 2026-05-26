"""
ortools_solver.py — Classical baseline using Google OR-Tools Routing (CVRPTW-style).

Minimizes total travel distance subject to:
  • per-vehicle capacities for frozen / chilled / ambient (three dimensions)
  • time windows at clinics (and depot window [0, 24h))

After OR-Tools returns routes, the same economic cost model as classical_solver
(distance + spoilage + refrigeration) is applied via route_cost() for fair
comparison with the hybrid pipeline in compare.py / the UI.

No NN / 2-opt / OR-opt — only the external MIP/CP-SAT based routing search.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from classical_solver import route_cost


def _matrix_node_ids(sc_module) -> list[int]:
    """Location index i in DISTANCE_MATRIX corresponds to this clinic/depot id."""
    return [sc_module.DEPOT["id"]] + [c["id"] for c in sc_module.CLINICS]


def solve_scenario(sc_module: Any) -> dict:
    """
    Run Google OR-Tools on a scenario module (scenario.py or scenario2.py).
    Same return shape as the former classical_solver.solve_scenario().
    """
    clinics      = sc_module.CLINICS
    vehicles     = sc_module.VEHICLES
    demands      = sc_module.DEMANDS
    dm           = np.asarray(sc_module.DISTANCE_MATRIX, dtype=float)
    tw           = sc_module.TIME_WINDOWS
    spoilage     = sc_module.SPOILAGE
    energy_rate  = sc_module.ENERGY_RATE
    avg_speed    = float(sc_module.AVG_SPEED_KMH)
    clinic_names = {c["id"]: c["name"] for c in clinics}
    node_ids     = _matrix_node_ids(sc_module)

    num_locations = dm.shape[0]
    num_vehicles  = len(vehicles)
    depot_idx     = 0

    cap_f = [vehicles[v]["compartments"]["frozen"]["capacity"] for v in range(num_vehicles)]
    cap_c = [vehicles[v]["compartments"]["chilled"]["capacity"] for v in range(num_vehicles)]
    cap_a = [vehicles[v]["compartments"]["ambient"]["capacity"] for v in range(num_vehicles)]

    # Integer arc costs: meters (km * 1000) — keeps OR-Tools in int64 comfortably
    dist_int = np.rint(dm * 1000.0).astype(np.int64)

    # Travel time in whole minutes (ceil) for time dimension
    time_mat = np.ceil(dm / max(avg_speed, 1e-6) * 60.0).astype(np.int64)
    time_mat[time_mat < 0] = 0

    # Time windows in minutes from midnight-style horizon [0, 24h)
    horizon = 24 * 60
    tw_start = [0] * num_locations
    tw_end   = [horizon] * num_locations
    for loc in range(1, num_locations):
        cid = node_ids[loc]
        o, cl = tw[cid]
        tw_start[loc] = int(o * 60)
        tw_end[loc]   = int(cl * 60)

    label = getattr(sc_module, "__name__", "scenario")
    print(f"\n{'='*55}")
    print(f"  OR-TOOLS ROUTING — {label}")
    print(f"  {len(clinics)} clinics / {num_vehicles} vehicles")
    print(f"{'='*55}")

    manager = pywrapcp.RoutingIndexManager(num_locations, num_vehicles, depot_idx)
    routing = pywrapcp.RoutingModel(manager)

    def distance_cb(from_index: int, to_index: int) -> int:
        a = manager.IndexToNode(from_index)
        b = manager.IndexToNode(to_index)
        return int(dist_int[a, b])

    def time_cb(from_index: int, to_index: int) -> int:
        a = manager.IndexToNode(from_index)
        b = manager.IndexToNode(to_index)
        return int(time_mat[a, b])

    dist_cb_ix = routing.RegisterTransitCallback(distance_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(dist_cb_ix)

    def demand_f(from_index: int) -> int:
        loc = manager.IndexToNode(from_index)
        if loc == depot_idx:
            return 0
        cid = node_ids[loc]
        return int(demands[cid]["frozen"])

    def demand_c(from_index: int) -> int:
        loc = manager.IndexToNode(from_index)
        if loc == depot_idx:
            return 0
        cid = node_ids[loc]
        return int(demands[cid]["chilled"])

    def demand_a(from_index: int) -> int:
        loc = manager.IndexToNode(from_index)
        if loc == depot_idx:
            return 0
        cid = node_ids[loc]
        return int(demands[cid]["ambient"])

    f_ix = routing.RegisterUnaryTransitCallback(demand_f)
    c_ix = routing.RegisterUnaryTransitCallback(demand_c)
    a_ix = routing.RegisterUnaryTransitCallback(demand_a)

    routing.AddDimensionWithVehicleCapacity(f_ix, 0, cap_f, True, "Frozen")
    routing.AddDimensionWithVehicleCapacity(c_ix, 0, cap_c, True, "Chilled")
    routing.AddDimensionWithVehicleCapacity(a_ix, 0, cap_a, True, "Ambient")

    time_cb_ix = routing.RegisterTransitCallback(time_cb)
    routing.AddDimension(time_cb_ix, horizon, horizon, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")

    for loc in range(num_locations):
        index = manager.NodeToIndex(loc)
        time_dim.CumulVar(index).SetRange(tw_start[loc], tw_end[loc])

    for vid in range(num_vehicles):
        time_dim.CumulVar(routing.Start(vid)).SetRange(0, horizon)
        time_dim.CumulVar(routing.End(vid)).SetRange(0, horizon)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    params.time_limit.FromSeconds(45)

    t0 = time.time()
    solution = routing.SolveWithParameters(params)
    solve_time = round(time.time() - t0, 4)

    if solution is None:
        print("  [FAIL] OR-Tools: no feasible assignment (check capacities / windows).")
        return {
            "solver":              "Google OR-Tools (Routing) — FAILED",
            "routes":              {},
            "fleet_distance":      0.0,
            "fleet_spoilage":      0.0,
            "fleet_refrigeration": 0.0,
            "fleet_total_cost":    0.0,
            "total_time":          solve_time,
            "status":              "failed",
        }

    routes_out: dict = {}
    total_dist = total_spoil = total_refrig = 0.0

    for vid in range(num_vehicles):
        vehicle_id = vehicles[vid]["id"]
        index = routing.Start(vid)
        loc_sequence: list[int] = []
        while not routing.IsEnd(index):
            loc_sequence.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        loc_sequence.append(manager.IndexToNode(index))

        id_route = [node_ids[loc] for loc in loc_sequence]
        inner = [cid for cid in id_route if cid != 0]

        bd = route_cost(inner, demands, dm, spoilage, energy_rate, avg_speed)

        cap_check = {}
        feasible = True
        for temp in ("frozen", "chilled", "ambient"):
            used = sum(demands[cid][temp] for cid in inner)
            cap = vehicles[vid]["compartments"][temp]["capacity"]
            cap_check[temp] = {"used": used, "cap": cap}
            if used > cap:
                feasible = False

        stops = [
            {"id": cid, "name": "Depot" if cid == 0 else clinic_names.get(cid, f"C{cid}")}
            for cid in id_route
        ]

        routes_out[vehicle_id] = {
            "route":            id_route,
            "stops":            stops,
            "distance_km":      bd["distance"],
            "spoilage_rs":      bd["spoilage"],
            "refrigeration_rs": bd["refrigeration"],
            "total_cost_rs":    bd["total"],
            "feasible":         feasible,
            "capacity":         cap_check,
            "computation_time": solve_time,
            "solver":           "Google OR-Tools (Routing)",
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

    total_cost = round(total_dist + total_spoil + total_refrig, 4)
    print(f"\n  Fleet distance : {total_dist:.2f} km")
    print(f"  Fleet spoilage : Rs {total_spoil:.4f}")
    print(f"  Fleet total    : Rs {total_cost:.4f}")
    print(f"  OR-Tools solve : {solve_time:.3f}s")

    return {
        "solver":              "Google OR-Tools (Routing)",
        "routes":              routes_out,
        "fleet_distance":      round(total_dist, 4),
        "fleet_spoilage":      round(total_spoil, 4),
        "fleet_refrigeration": round(total_refrig, 4),
        "fleet_total_cost":    total_cost,
        "total_time":          solve_time,
        "status":              "ok",
    }


if __name__ == "__main__":
    import scenario as sc1
    import scenario2 as sc2

    for sc in (sc1, sc2):
        r = solve_scenario(sc)
        print(f"\n[{sc.__name__}] OR-Tools fleet total: Rs {r['fleet_total_cost']:.4f}")
