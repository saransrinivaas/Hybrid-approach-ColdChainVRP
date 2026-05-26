import numpy as np
from pyqubo import Array

try:
    import scenario_dynamic as scenario
except ImportError:
    import scenario

CLINICS = scenario.CLINICS
DEMANDS = scenario.DEMANDS
DISTANCE_MATRIX = scenario.DISTANCE_MATRIX
SPOILAGE = scenario.SPOILAGE
AVG_SPEED_KMH = scenario.AVG_SPEED_KMH
ENERGY_RATE = scenario.ENERGY_RATE

import temp_preprocessing

# ─────────────────────────────────────────
# COMPARTMENT SETTINGS
# ─────────────────────────────────────────
COMPARTMENTS = {
    0: "frozen",
    1: "chilled",
    2: "ambient"
}

# ─────────────────────────────────────────
# ARRIVAL TIME ESTIMATOR
# Order-independent: uses average inter-clinic
# distance so QUBO doesn't assume a fixed ordering.
# Position t has estimated arrival = t * avg_hop_time.
# The optimizer learns that later positions cost
# more spoilage — without needing to know the route.
# ─────────────────────────────────────────
def estimate_positional_arrival_times(clinic_ids):
    """
    Estimate arrival time at each position t based on
    average inter-clinic distance within the sub-cluster.
    This is order-independent — the QUBO decides the actual order.
    """
    n = len(clinic_ids)
    if n <= 1:
        return [0.0]

    # Average distance between all pairs (excluding self)
    total_dist = 0.0
    count = 0
    for i in range(n):
        for j in range(n):
            if i != j:
                total_dist += DISTANCE_MATRIX[clinic_ids[i]][clinic_ids[j]]
                count += 1
    avg_dist     = total_dist / count if count > 0 else 0.0
    avg_hop_time = avg_dist / AVG_SPEED_KMH  # hours per hop

    # Position t: estimated arrival = t * avg_hop_time
    return [t * avg_hop_time for t in range(n)]

# ─────────────────────────────────────────
# CORE QUBO BUILDER
# Formulation: x[i][t] — shape (n, n) — n² qubits
# One stop serves all compartments simultaneously.
# This matches the actual vehicle design where a single
# cold-chain truck carries frozen/chilled/ambient together.
# ─────────────────────────────────────────
def build_qubo(clinic_ids: list):
    n  = len(clinic_ids)   # number of clinics in sub-cluster
    nc = 3                  # compartment count (for cost calcs)

    print(f"\n=== Building QUBO for cluster {clinic_ids} ===")
    print(f"  Variables: {n}x{n} = {n*n} qubits")

    # ── Decision variables ──
    # x[i][t] = 1 if clinic i visited at position t
    x = Array.create("x", shape=(n, n), vartype="BINARY")

    # ── Precompute position-based arrival times ──
    arrival_times = estimate_positional_arrival_times(clinic_ids)

    # ── Precompute local distance matrix ──
    dist_matrix_local = np.array([
        [DISTANCE_MATRIX[clinic_ids[i]][clinic_ids[j]]
         for j in range(n)]
        for i in range(n)
    ])
    max_dist = float(np.max(dist_matrix_local))
    M = 2.0 * max_dist  # penalty coefficient base

    print(f"  Max distance in cluster: {max_dist:.2f} km")
    print(f"  Penalty coefficient M:   {M:.2f}")

    # ─────────────────────────────────────
    # TERM 1 — TRAVEL DISTANCE COST
    # Sum of d(i,j) * x[i,t] * x[j,t+1]
    # Rewards routes with shorter consecutive hops.
    # ─────────────────────────────────────
    H_distance = 0.0

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            d = dist_matrix_local[i][j]
            for t in range(n - 1):      # consecutive positions
                H_distance += d * x[i, t] * x[j, t + 1]

    print("  [OK] Term 1 (distance) built")

    # ─────────────────────────────────────
    # TERM 2 — SPOILAGE COST (NOVEL)
    # For each clinic i at position t, sum spoilage
    # across all compartments: value * alpha * arr_time * demand.
    # Aggregated into one scalar per (i,t) since x[i,t]
    # means the vehicle visits, delivering all compartments.
    # ─────────────────────────────────────
    H_spoilage = 0.0

    for i in range(n):
        clinic_id = clinic_ids[i]
        for t in range(n):
            arr_time = arrival_times[t]
            total_coeff = 0.0
            for c in range(nc):
                temp_class = COMPARTMENTS[c]
                alpha      = SPOILAGE[temp_class]["alpha"]
                value      = SPOILAGE[temp_class]["value"]
                demand     = DEMANDS[clinic_id][temp_class]
                total_coeff += value * alpha * arr_time * demand
            H_spoilage += total_coeff * x[i, t]

    print("  [OK] Term 2 (spoilage) built")

    # ─────────────────────────────────────
    # TERM 3 — REFRIGERATION ENERGY (NOVEL)
    # Constant cost: vehicle runs all compartments
    # for the full route duration regardless of order.
    # Distributed equally per visit slot so it influences
    # the Hamiltonian landscape.
    # ─────────────────────────────────────
    H_refrigeration = 0.0

    route_duration    = arrival_times[-1] if len(arrival_times) > 1 else (max_dist / AVG_SPEED_KMH)
    total_energy_cost = sum(ENERGY_RATE[COMPARTMENTS[c]] * route_duration for c in range(nc))
    energy_per_slot   = total_energy_cost / n if n > 0 else 0.0

    for i in range(n):
        for t in range(n):
            H_refrigeration += energy_per_slot * x[i, t]

    print("  [OK] Term 3 (refrigeration) built")

    # ─────────────────────────────────────
    # TERM 4 — VISIT ONCE CONSTRAINT
    # Each clinic visited at exactly one position.
    # sum_t x[i,t] = 1  for each i
    # ─────────────────────────────────────
    H_visit = 0.0

    for i in range(n):
        visit_sum = sum(x[i, t] for t in range(n))
        H_visit  += (visit_sum - 1) ** 2

    H_visit *= M

    print("  [OK] Term 4 (visit-once) built")

    # ─────────────────────────────────────
    # TERM 5 — POSITION ONCE CONSTRAINT
    # Each position holds exactly one clinic.
    # sum_i x[i,t] = 1  for each t
    # ─────────────────────────────────────
    H_position = 0.0

    for t in range(n):
        pos_sum     = sum(x[i, t] for i in range(n))
        H_position += (pos_sum - 1) ** 2

    H_position *= M

    print("  [OK] Term 5 (position-once) built")

    # ─────────────────────────────────────
    # TERM 6 — CAPACITY (SKIPPED)
    # Capacity is guaranteed by the clustering step.
    # Adding it here creates a massive constant offset
    # (was 6767 → reduced to 85 after removing it).
    # ─────────────────────────────────────
    print("  [OK] Term 6 (capacity) skipped — guaranteed by clustering")

    # ─────────────────────────────────────
    # COMBINED HAMILTONIAN
    # ─────────────────────────────────────
    H_total = H_distance + H_spoilage + H_refrigeration + H_visit + H_position

    print("  [OK] Combined Hamiltonian built")

    # ─────────────────────────────────────
    # COMPILE TO QUBO
    # ─────────────────────────────────────
    model        = H_total.compile()
    qubo, offset = model.to_qubo()

    print(f"  [OK] Compiled to QUBO")
    print(f"    QUBO terms:    {len(qubo)}")
    print(f"    Energy offset: {offset:.4f}")

    return model, qubo, offset, x, n

# ─────────────────────────────────────────
# COST BREAKDOWN
# Evaluates a decoded solution dict against
# the three real-world cost terms.
# Keys: "x[i][t]" matching PyQUBO output.
# ─────────────────────────────────────────
def compute_cost_breakdown(solution_dict, clinic_ids):
    n  = len(clinic_ids)
    nc = 3

    arrival_times = estimate_positional_arrival_times(clinic_ids)
    dist_matrix_local = np.array([
        [DISTANCE_MATRIX[clinic_ids[i]][clinic_ids[j]]
         for j in range(n)]
        for i in range(n)
    ])

    route_duration = (arrival_times[-1]
                      if len(arrival_times) > 1
                      else float(np.max(dist_matrix_local)) / AVG_SPEED_KMH)

    distance_cost      = 0.0
    spoilage_cost      = 0.0

    for i in range(n):
        clinic_id = clinic_ids[i]
        for t in range(n):
            key = f"x[{i}][{t}]"
            if solution_dict.get(key, 0) == 1:
                # Distance to next stop
                if t < n - 1:
                    for j in range(n):
                        if solution_dict.get(f"x[{j}][{t+1}]", 0) == 1:
                            distance_cost += dist_matrix_local[i][j]

                # Spoilage across all compartments
                arr = arrival_times[t]
                for c in range(nc):
                    temp_class = COMPARTMENTS[c]
                    alpha      = SPOILAGE[temp_class]["alpha"]
                    value      = SPOILAGE[temp_class]["value"]
                    demand     = DEMANDS[clinic_id][temp_class]
                    spoilage_cost += value * alpha * arr * demand

    # Refrigeration is a constant for the full trip
    refrigeration_cost = sum(ENERGY_RATE[COMPARTMENTS[c]] * route_duration for c in range(nc))

    return {
        "distance":      round(distance_cost, 4),
        "spoilage":      round(spoilage_cost, 4),
        "refrigeration": round(refrigeration_cost, 4),
        "total":         round(distance_cost + spoilage_cost + refrigeration_cost, 4)
    }

# ─────────────────────────────────────────
# DECODE BITSTRING → SOLUTION DICT
# Converts QAOA sample dict → readable route.
# Keys: "x[i][t]" — matching PyQUBO variable names.
# ─────────────────────────────────────────
def decode_solution(sample: dict, clinic_ids: list):
    n     = len(clinic_ids)
    route = [None] * n
    assignment = {}

    for i in range(n):
        for t in range(n):
            key = f"x[{i}][{t}]"
            if sample.get(key, 0) == 1:
                route[t] = clinic_ids[i]
                assignment[clinic_ids[i]] = "all compartments"

    return {
        "route":      route,
        "assignment": assignment,
        "valid":      None not in route and len(set(route)) == n
    }

# ─────────────────────────────────────────
# MAIN — integration test
# ─────────────────────────────────────────
if __name__ == "__main__":
    from clustering import build_clusters, generate_subclusters

    print("=" * 55)
    print("  QUBO BUILDER — Pipeline Integration Test")
    print("=" * 55)

    vehicle_routes = build_clusters()

    first_vehicle_id, first_trips = vehicle_routes[0]
    first_trip  = first_trips[0]
    subclusters = generate_subclusters(first_trip)
    test_cluster = subclusters[0]

    print(f"\n--- Testing QUBO on sub-cluster {test_cluster} from {first_vehicle_id} ---")

    model, qubo, offset, x, n = build_qubo(test_cluster)

    print("\n=== QUBO Summary ===")
    print(f"  Cluster:       {test_cluster}")
    print(f"  Qubits:        {n*n}   (n={n}, formulation x[i][t])")
    print(f"  QUBO terms:    {len(qubo)}")
    print(f"  Energy offset: {offset:.4f}")

    print("\n=== Spoilage Parameters Used ===")
    for c in range(3):
        temp = COMPARTMENTS[c]
        print(f"    {temp:>8}: alpha={SPOILAGE[temp]['alpha']}  "
              f"value={SPOILAGE[temp]['value']}  "
              f"capacity={temp_preprocessing.CAPACITY[temp]}")

    print("\n[OK] QUBO ready for QAOA solver")
    print("  Next: python qaoa_solver.py")
