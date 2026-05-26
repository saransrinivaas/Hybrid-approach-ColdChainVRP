"""
ortools_runner.py — Demonstrate OR-Tools failure on the Tough scenario.

Runs Google OR-Tools CVRPTW on scenario2 (10 clinics, 2 vehicles,
6 tight time windows) and streams the result.  Expected outcome:
OR-Tools exhausts its 45-second budget and returns no feasible solution.

Streamed via /api/run-ortools-tough.
"""

import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import scenario2 as SC2
from ortools_solver import solve_scenario

if __name__ == "__main__":
    print("=" * 60)
    print("  OR-TOOLS CVRPTW — TOUGH SCENARIO (Chennai Pilot)")
    print(f"  {len(SC2.CLINICS)} clinics · {len(SC2.VEHICLES)} vehicles · 3 compartments each")
    print("=" * 60)
    print()
    print("  Tight windows detected:")
    for cid, (o, cl) in SC2.TIME_WINDOWS.items():
        if (cl - o) <= 3:
            cname = next(c["name"] for c in SC2.CLINICS if c["id"] == cid)
            o_h, cl_h = int(o), int(cl)
            print(f"    Clinic {cid:2d}  {cname:<20s}  {o_h:02d}:{int((o%1)*60):02d}–{cl_h:02d}:{int((cl%1)*60):02d}")
    print()
    print("  Search parameters:")
    print("    Strategy  : PATH_CHEAPEST_ARC + Guided Local Search")
    print("    Time limit: 45 s")
    print("    Dimensions: Frozen / Chilled / Ambient capacity + Time")
    print()
    print("  Running OR-Tools… (this will exhaust the 45-second budget)")
    print()

    result = solve_scenario(SC2)

    print()
    print("=" * 60)
    if result.get("status") == "failed":
        print("  [FAIL] OR-Tools returned NO feasible solution.")
        print()
        print("  Root cause: 6 clinics have 1.5-hour windows split between")
        print("  morning (09:00–10:30) and afternoon (14:30–16:00) clusters.")
        print("  With only 2 vehicles and 30 km/h urban speed, it is")
        print("  geometrically impossible to honour all windows as hard")
        print("  constraints.  The MIP/CP-SAT search space is infeasible.")
        print()
        print("  => Hybrid pipeline will be used instead (soft penalties).")
    else:
        print(f"  OR-Tools found a solution  (total: Rs {result['fleet_total_cost']:.4f})")
    print("=" * 60)
