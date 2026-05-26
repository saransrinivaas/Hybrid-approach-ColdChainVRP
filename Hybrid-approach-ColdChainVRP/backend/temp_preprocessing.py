try:
    import scenario_dynamic as scenario
except ImportError:
    import scenario

CLINICS = scenario.CLINICS
VEHICLES = scenario.VEHICLES
DEMANDS = scenario.DEMANDS

CAPACITY = {
    temp: VEHICLES[0]["compartments"][temp]["capacity"]
    for temp in VEHICLES[0]["compartments"]
}


MAX_CLUSTER_SIZE = 4  # qubit budget: 4×4=16 binary vars per sub-cluster (QAOA p=3)

def check_cluster(clinic_ids):
    violations = []

    # Check node count
    if len(clinic_ids) > MAX_CLUSTER_SIZE:
        violations.append(f"too many nodes: {len(clinic_ids)} > {MAX_CLUSTER_SIZE}")

    # Check each compartment
    for temp in CAPACITY:
        total = sum(DEMANDS[cid][temp] for cid in clinic_ids)
        if total > CAPACITY[temp]:
            violations.append(
                f"{temp} overflow: {total} > {CAPACITY[temp]}"
            )

    return violations

def cluster_demand(clinic_ids, temp, demands=None):
    if demands is None:
        demands = DEMANDS
    return sum(demands[cid][temp] for cid in clinic_ids)

def cluster_feasible(clinic_ids):
    return len(check_cluster(clinic_ids)) == 0

def vehicle_capacity_check(clinic_ids):
    """Check if a set of clinics fits within ONE vehicle's total capacity.
    This is the vehicular-level check (no node-count limit)."""
    violations = []
    for temp in CAPACITY:
        total = sum(DEMANDS[cid][temp] for cid in clinic_ids)
        if total > CAPACITY[temp]:
            violations.append(f"{temp} overflow: {total} > {CAPACITY[temp]}")
    return violations

def vehicle_trip_feasible(clinic_ids):
    return len(vehicle_capacity_check(clinic_ids)) == 0
