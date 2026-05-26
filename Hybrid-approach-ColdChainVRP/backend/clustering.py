# Temporal-Aware Capacitated Clustering for Cold Chain VRP

import math
import itertools
import numpy as np
from sklearn.cluster import AgglomerativeClustering

try:
    import scenario_dynamic as _default_scenario
except ImportError:
    import scenario as _default_scenario

from temp_preprocessing import (
    CAPACITY as _DEFAULT_CAPACITY,
    MAX_CLUSTER_SIZE,
    cluster_demand,
)

# ─────────────────────────────────────────
# CONFIGURABLE PARAMETERS
# ─────────────────────────────────────────
LAMBDA_TEMPORAL = 0.6  # weight of temporal penalty in composite distance
MAX_CLUSTER_SIZE = 4    # max nodes per sub‑cluster (qubit budget)
CAPACITY = {
    "frozen": 10,
    "chilled": 12,
    "ambient": 15,
}

# ─────────────────────────────────────────
# STEP 0 – Determine number of vehicles
# ─────────────────────────────────────────
def compute_n_vehicles(vehicles):
    n = len(vehicles)
    print(f"  Fleet size: {n} vehicle(s) -> targeting {n} vehicular cluster(s)")
    return n

# ─────────────────────────────────────────
# STEP 1 – Temporal‑aware K‑means (geographic + time‑window penalty)
# ─────────────────────────────────────────
def temporal_penalty(id_i, id_j):
    """Return a penalty in [0, 2] capturing time‑window incompatibility.
    0  → windows overlap perfectly.
    2  → windows completely incompatible.
    """
    open_i, close_i = _default_scenario.TIME_WINDOWS[id_i]
    open_j, close_j = _default_scenario.TIME_WINDOWS[id_j]

    # Overlap fraction
    overlap = max(0, min(close_i, close_j) - max(open_i, open_j))
    window_i = close_i - open_i
    window_j = close_j - open_j
    avg_win = (window_i + window_j) / 2
    overlap_frac = overlap / avg_win if avg_win > 0 else 0

    # Gap penalty when no overlap
    if overlap > 0:
        gap = 0.0
    else:
        gap = max(open_i - close_j, open_j - close_i, 0)
    gap_penalty = min(gap / 10.0, 1.0)  # normalize to 0‑1 (10 h max gap)
    return gap_penalty + (1 - overlap_frac)

def build_composite_distance_matrix():
    """Composite distance = geographic distance × (1 + λ·temporal_penalty)."""
    clinics = _default_scenario.CLINICS
    n = len(clinics)
    # Geographic distances from scenario's distance matrix (km)
    geo = np.array([
        [_default_scenario.DISTANCE_MATRIX[clinics[i]["id"]][clinics[j]["id"]]
         for j in range(n)]
        for i in range(n)
    ])
    geo_max = geo.max()
    geo_norm = geo / geo_max if geo_max > 0 else geo
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            temp = temporal_penalty(clinics[i]["id"], clinics[j]["id"])
            D[i][j] = geo_norm[i][j] * (1 + LAMBDA_TEMPORAL * temp)
    return D

def temporal_aware_kmeans(n_clusters):
    """Use AgglomerativeClustering on composite distances to avoid MDS hang."""
    D = build_composite_distance_matrix()
    clustering = AgglomerativeClustering(n_clusters=n_clusters, metric="precomputed", linkage="average")
    labels = clustering.fit_predict(D)
    clusters = {}
    for idx, label in enumerate(labels):
        clusters.setdefault(label, []).append(_default_scenario.CLINICS[idx]["id"])
    return list(clusters.values()), None, D

# ─────────────────────────────────────────
# STEP 2 – Vehicle‑level capacity check & repair (existing logic)
# ─────────────────────────────────────────
def _vehicle_capacity_check(clinic_ids, capacity, demands):
    violations = []
    for temp in capacity:
        total = sum(demands[cid][temp] for cid in clinic_ids)
        if total > capacity[temp]:
            violations.append(f"{temp} overflow: {total} > {capacity[temp]}")
    return violations

def _vehicle_trip_feasible(clinic_ids, capacity, demands):
    return len(_vehicle_capacity_check(clinic_ids, capacity, demands)) == 0

def clinic_to_cluster_distance(clinic_id, cluster_ids, distance_matrix):
    if not cluster_ids:
        return float("inf")
    distances = [distance_matrix[clinic_id][cid] for cid in cluster_ids]
    return np.mean(distances)

def find_best_vehicle_target(clinic_id, clusters, exclude_idx, capacity, demands, distance_matrix):
    best_idx, best_dist = None, float("inf")
    for i, cluster in enumerate(clusters):
        if i == exclude_idx:
            continue
        trial = cluster + [clinic_id]
        if _vehicle_trip_feasible(trial, capacity, demands):
            dist = clinic_to_cluster_distance(clinic_id, cluster, distance_matrix)
            if dist < best_dist:
                best_dist, best_idx = dist, i
    return best_idx

def find_worst_offender(clinic_ids, violation_type, demands, distance_matrix):
    if "nodes" in violation_type:
        distances = {
            cid: clinic_to_cluster_distance(cid, [x for x in clinic_ids if x != cid], distance_matrix)
            for cid in clinic_ids
        }
        return max(distances, key=distances.get)
    else:
        temp = violation_type.split()[0]
        return max(clinic_ids, key=lambda cid: demands[cid][temp])

def repair_vehicle_clusters(clusters, capacity, demands, distance_matrix):
    max_iterations = 50
    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        found = False
        for i, cluster in enumerate(clusters):
            violations = _vehicle_capacity_check(cluster, capacity, demands)
            if violations:
                found = True
                violation = violations[0]
                offender = find_worst_offender(cluster, violation, demands, distance_matrix)
                target_idx = find_best_vehicle_target(offender, clusters, i, capacity, demands, distance_matrix)
                if target_idx is not None:
                    clusters[i].remove(offender)
                    clusters[target_idx].append(offender)
                    print(f"  Iter {iteration}: moved Clinic {offender} from Vehicle {i+1} to Vehicle {target_idx+1} ({violation})")
                else:
                    clusters[i].remove(offender)
                    clusters.append([offender])
                    print(f"  Iter {iteration}: Clinic {offender} -> new vehicle (no feasible target for {violation})")
                break
        if not found:
            print(f"  Vehicle clusters feasible after {iteration-1} iterations [OK]")
            break
    return [c for c in clusters if c]

# ─────────────────────────────────────────
# STEP 3 – Assign trips (existing logic with capacity overflow handling)
# ─────────────────────────────────────────
def assign_trips(clinic_ids, capacity, demands, time_windows):
    if _vehicle_trip_feasible(clinic_ids, capacity, demands):
        return [clinic_ids]
    # Sort by closing time (most urgent first)
    sorted_ids = sorted(clinic_ids, key=lambda cid: time_windows[cid][1])
    trip1, trip2 = [], []
    for cid in sorted_ids:
        trial = trip1 + [cid]
        if _vehicle_trip_feasible(trial, capacity, demands):
            trip1.append(cid)
        else:
            trip2.append(cid)
    return [t for t in (trip1, trip2) if t]

# ─────────────────────────────────────────
# STEP 4 – Sub‑cluster generation (overlapping 3‑node combos)
# ─────────────────────────────────────────
def generate_subclusters(trip_nodes):
    n = len(trip_nodes)
    if n >= MAX_CLUSTER_SIZE:
        return [list(combo) for combo in itertools.combinations(trip_nodes, MAX_CLUSTER_SIZE)]
    return [list(trip_nodes)]

# ─────────────────────────────────────────
# STEP 5 – Temporal feasibility checks & repair
# ─────────────────────────────────────────
def check_temporal_feasibility(clinic_ids, avg_speed_kmh=30):
    """Return (feasible, best_sequence, total_idle_hours)."""
    from itertools import permutations
    if len(clinic_ids) <= 1:
        return True, clinic_ids, 0.0
    best_seq = None
    best_idle = float("inf")
    feasible_any = False
    for perm in permutations(clinic_ids):
        cur_time = 8.0  # start 8 am at depot (id 0)
        idle = 0.0
        ok = True
        prev = 0
        for cid in perm:
            travel = _default_scenario.DISTANCE_MATRIX[prev][cid] / avg_speed_kmh
            arrival = cur_time + travel
            open_t, close_t = _default_scenario.TIME_WINDOWS[cid]
            if arrival > close_t:
                ok = False
                break
            if arrival < open_t:
                idle += open_t - arrival
                cur_time = open_t
            else:
                cur_time = arrival
            cur_time += 0.5  # service time 0.5 h
            prev = cid
        if ok and idle < best_idle:
            feasible_any = True
            best_idle = idle
            best_seq = list(perm)
    return feasible_any, best_seq or list(clinic_ids), best_idle

def find_most_incompatible(clinic_ids):
    if len(clinic_ids) == 1:
        return clinic_ids[0]
    scores = {}
    for cid in clinic_ids:
        others = [x for x in clinic_ids if x != cid]
        scores[cid] = np.mean([temporal_penalty(cid, o) for o in others])
    return max(scores, key=scores.get)

def repair_temporal(clusters):
    max_iterations = 30
    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        changed = False
        for idx, cluster in enumerate(clusters):
            feasible, _, idle = check_temporal_feasibility(cluster)
            if not feasible or idle > 2.0:
                changed = True
                worst = find_most_incompatible(cluster)
                # Find best target cluster
                target = None
                best_idle = float("inf")
                for jdx, other in enumerate(clusters):
                    if jdx == idx or len(other) >= MAX_CLUSTER_SIZE:
                        continue
                    trial = other + [worst]
                    feas, _, idle2 = check_temporal_feasibility(trial)
                    if feas and idle2 < best_idle:
                        best_idle, target = idle2, jdx
                if target is not None:
                    clusters[idx].remove(worst)
                    clusters[target].append(worst)
                    print(f"  [TW repair] Iter {iteration}: Clinic {worst} -> Cluster {target}")
                else:
                    clusters[idx].remove(worst)
                    clusters.append([worst])
                    print(f"  [TW repair] Iter {iteration}: Clinic {worst} -> new cluster")
                break
        if not changed:
            print(f"  Temporal repair completed after {iteration-1} iterations [OK]")
            break
    return [c for c in clusters if c]

# ─────────────────────────────────────────
# STEP 6 – Summary utilities
# ─────────────────────────────────────────
def get_clinic_name(cid, clinics):
    return next(c["name"] for c in clinics if c["id"] == cid)

def print_summary(vehicle_routes, clinics, capacity, demands, time_windows):
    print("\n" + "="*55)
    print("  FINAL SUMMARY: VEHICULAR CLUSTERS & SUB-CLUSTERS")
    print("="*55)
    grand_qubits = 0
    grand_sub = 0
    for v_idx, (vehicle_id, trips) in enumerate(vehicle_routes):
        v_frozen = sum(cluster_demand(t, "frozen", demands) for t in trips)
        v_chilled = sum(cluster_demand(t, "chilled", demands) for t in trips)
        v_ambient = sum(cluster_demand(t, "ambient", demands) for t in trips)
        all_nodes = [cid for t in trips for cid in t]
        print(f"\n+- Vehicle {vehicle_id} ({'1' if len(trips)==1 else len(trips)} trip(s))")
        print(f"|  Clinics : {[get_clinic_name(c, clinics) for c in all_nodes]}")
        print(f"|  Frozen  : {v_frozen}/{capacity['frozen']} "
              f"{'[OK]' if v_frozen <= capacity['frozen'] else '[OVER]'}")
        print(f"|  Chilled : {v_chilled}/{capacity['chilled']} "
              f"{'[OK]' if v_chilled <= capacity['chilled'] else '[OVER]'}")
        print(f"|  Ambient : {v_ambient}/{capacity['ambient']} "
              f"{'[OK]' if v_ambient <= capacity['ambient'] else '[OVER]'}")
        for t_idx, trip in enumerate(trips):
            tw_open = min(time_windows[c][0] for c in trip)
            tw_close = min(time_windows[c][1] for c in trip)
            sub = generate_subclusters(trip)
            trip_qubits = sum(len(sc)**2 * 3 for sc in sub)
            grand_qubits += trip_qubits
            grand_sub += len(sub)
            label = f"Trip {t_idx+1}" if len(trips)>1 else "Single Trip"
            print(f"|")
            print(f"|  +- {label}: nodes={trip} | window=[{tw_open}:00-{tw_close}:00]")
            print(f"|  |  Sub-clusters ({len(sub)} groups, {trip_qubits} qubits):")
            for sc in sub:
                names = [get_clinic_name(c, clinics) for c in sc]
                print(f"|  |    {sc} -> {names}  [{len(sc)**2 * 3} qubits]")
        print("|")
    max_qubits = (MAX_CLUSTER_SIZE**2 * 3) * grand_sub
    print("="*55)
    print(f"  Total sub-clusters : {grand_sub}")
    print(f"  Total qubits       : {grand_qubits}")
    print(f"  Simulator safe     : {'[OK]' if grand_qubits <= max_qubits else '[WARN]'} "
          f"({grand_qubits}/{max_qubits} max)")
    print("="*55)

# ─────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────
def build_clusters(sc_module=None):
    """Run the full clustering pipeline.
    sc_module – optional scenario module (scenario or scenario2).
    """
    if sc_module is None:
        sc_module = _default_scenario
    clinics = sc_module.CLINICS
    vehicles = sc_module.VEHICLES
    demands = sc_module.DEMANDS
    distance_matrix = sc_module.DISTANCE_MATRIX
    time_windows = sc_module.TIME_WINDOWS
    # Determine capacity from first vehicle (assumed uniform)
    capacity = {temp: vehicles[0]["compartments"][temp]["capacity"] for temp in vehicles[0]["compartments"]}

    print("=== Vehicular Capacitated Clustering ===\n")
    n_vehicles = compute_n_vehicles(vehicles)
    # STEP 1 – temporal‑aware K‑means
    n_clusters = max(2, len(clinics) // MAX_CLUSTER_SIZE)
    clusters, _, _ = temporal_aware_kmeans(n_clusters)
    print(f"Initial clusters (temporal-aware): {clusters}\n")
    # STEP 2 – capacity repair
    clusters = repair_vehicle_clusters(clusters, capacity, demands, distance_matrix)
    # STEP 3 – assign trips per vehicle
    vehicle_routes = []
    for i, cluster in enumerate(clusters):
        vehicle_id = vehicles[i]["id"] if i < len(vehicles) else f"V{i+1}"
        trips = assign_trips(cluster, capacity, demands, time_windows)
        vehicle_routes.append((vehicle_id, trips))
    # STEP 4 – temporal repair of clusters
    vehicle_routes = [(vid, trips) for vid, trips in vehicle_routes]
    # Extract just clusters for temporal repair
    cluster_lists = [c for _, c in vehicle_routes]
    cluster_lists = repair_temporal(cluster_lists)
    # Re‑attach vehicle ids (may have changed ordering)
    vehicle_routes = [(vehicles[i]["id"] if i < len(vehicles) else f"V{i+1}", cl) for i, cl in enumerate(cluster_lists)]
    # STEP 5 – summary
    print_summary(vehicle_routes, clinics, capacity, demands, time_windows)
    return vehicle_routes

if __name__ == "__main__":
    build_clusters()

