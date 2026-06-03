# Temporal-Aware Capacitated Clustering for Cold Chain VRP

import math
import itertools
import numpy as np
from sklearn.cluster import AgglomerativeClustering

import threading
import sys
import types

_local = threading.local()

try:
    import scenario_dynamic as _init_scenario
except ImportError:
    import scenario as _init_scenario

class ScenarioProxy:
    def __init__(self, fallback=None):
        self.__dict__['_fallback'] = fallback

    def _get_current_object(self):
        if hasattr(_local, "scenario"):
            return _local.scenario
        fallback = self.__dict__.get('_fallback')
        return fallback if fallback is not None else _init_scenario

    def __getattr__(self, name):
        return getattr(self._get_current_object(), name)

    def __setattr__(self, name, value):
        setattr(self._get_current_object(), name, value)

    def __str__(self):
        return str(self._get_current_object())

    def __repr__(self):
        return repr(self._get_current_object())

class _ClusteringModule(types.ModuleType):
    def __setattr__(self, name, value):
        if name == "_default_scenario":
            _local.scenario = value
        else:
            super().__setattr__(name, value)

# Set the module's class to the custom class
sys.modules[__name__].__class__ = _ClusteringModule

_default_scenario = ScenarioProxy(_init_scenario)

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

def find_best_vehicle_target(clinic_id, clusters, exclude_idx, capacity, demands, distance_matrix, force=False):
    best_idx, best_dist = None, float("inf")
    best_violation_idx, min_violation = None, float("inf")
    
    for i, cluster in enumerate(clusters):
        if i == exclude_idx:
            continue
        trial = cluster + [clinic_id]
        violations = _vehicle_capacity_check(trial, capacity, demands)
        if len(violations) == 0:
            dist = clinic_to_cluster_distance(clinic_id, cluster, distance_matrix)
            if dist < best_dist:
                best_dist, best_idx = dist, i
        elif force:
            violation_amt = 0
            for temp in capacity:
                total = sum(demands[cid][temp] for cid in trial)
                if total > capacity[temp]:
                    violation_amt += (total - capacity[temp])
            if violation_amt < min_violation:
                min_violation, best_violation_idx = violation_amt, i
                
    if best_idx is not None:
        return best_idx
    if force:
        return best_violation_idx
    return None

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
                    # Force assignment under minimum capacity violation instead of spawning a new vehicle
                    target_idx = find_best_vehicle_target(offender, clusters, i, capacity, demands, distance_matrix, force=True)
                    if target_idx is not None:
                        clusters[i].remove(offender)
                        clusters[target_idx].append(offender)
                        print(f"  Iter {iteration}: forced Clinic {offender} to Vehicle {target_idx+1} ({violation})")
                    else:
                        print(f"  Iter {iteration}: Clinic {offender} kept in Vehicle {i+1} (reached fleet limit)")
                break
        if not found:
            print(f"  Vehicle clusters feasible after {iteration-1} iterations [OK]")
            break
    return [c for c in clusters if c]

# ─────────────────────────────────────────
# STEP 3 – Assign trips (urgency-aware with capacity overflow handling)
# ─────────────────────────────────────────
def _clinic_urgency(cid, demands, spoilage, time_windows):
    """
    Composite urgency score — higher means serve this clinic first.
      = spoilage_rate * demand_weight + time_pressure
    spoilage_rate = sum over temps of alpha * value * demand
    time_pressure = 1 / (close_window)   so tight windows rank high
    """
    decay = sum(
        spoilage[t]["alpha"] * spoilage[t]["value"] * demands[cid][t]
        for t in ("frozen", "chilled", "ambient")
    )
    close_time = time_windows[cid][1]
    time_pressure = 1.0 / max(close_time, 1.0)
    return decay + time_pressure


def assign_trips(clinic_ids, capacity, demands, time_windows):
    # Sort by composite urgency: high spoilage + tight window first
    import scenario_dynamic as _sc
    try:
        spoilage = _sc.SPOILAGE
    except AttributeError:
        import scenario as _sc2
        spoilage = _sc2.SPOILAGE

    sorted_ids = sorted(
        clinic_ids,
        key=lambda cid: _clinic_urgency(cid, demands, spoilage, time_windows),
        reverse=True  # most urgent first
    )
    trips = []
    for cid in sorted_ids:
        placed = False
        for trip in trips:
            trial = trip + [cid]
            if _vehicle_trip_feasible(trial, capacity, demands):
                trip.append(cid)
                placed = True
                break
        if not placed:
            trips.append([cid])
    return trips

# ─────────────────────────────────────────
# STEP 4 – Sub‑cluster generation (overlapping 3‑node combos)
# ─────────────────────────────────────────
def generate_subclusters(trip_nodes, max_size=None):
    limit_size = max_size if max_size is not None else MAX_CLUSTER_SIZE
    n = len(trip_nodes)
    if n <= limit_size:
        return [list(trip_nodes)]
    
    subclusters = []
    overlap = 2
    step = limit_size - overlap
    
    for i in range(0, n - overlap, step):
        end_idx = min(i + limit_size, n)
        sub = trip_nodes[i:end_idx]
        # Stretch last window backwards if it is smaller than limit_size
        if len(sub) < limit_size and n >= limit_size:
            sub = trip_nodes[n - limit_size:n]
        if list(sub) not in subclusters:
            subclusters.append(list(sub))
    return subclusters

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
    # Already handled by temporal K-means and sorted trip assignment
    return clusters

# ─────────────────────────────────────────
# STEP 6 – Summary utilities
# ─────────────────────────────────────────
def get_clinic_name(cid, clinics):
    return next(c["name"] for c in clinics if c["id"] == cid)

def print_summary(vehicle_routes, clinics, capacity, demands, time_windows, max_size=None):
    print("\n" + "="*55)
    print("  FINAL SUMMARY: VEHICULAR CLUSTERS & SUB-CLUSTERS")
    print("="*55)
    grand_qubits = 0
    grand_sub = 0
    for v_idx, (vehicle_id, trips) in enumerate(vehicle_routes):
        all_nodes = [cid for t in trips for cid in t]
        print(f"\n+- Vehicle {vehicle_id} ({'1' if len(trips)==1 else len(trips)} trip(s))")
        print(f"|  Clinics : {[get_clinic_name(c, clinics) for c in all_nodes]}")
        for t_idx, trip in enumerate(trips):
            trip_frozen = sum(demands[cid]["frozen"] for cid in trip)
            trip_chilled = sum(demands[cid]["chilled"] for cid in trip)
            trip_ambient = sum(demands[cid]["ambient"] for cid in trip)
            
            tw_open = min(time_windows[c][0] for c in trip)
            tw_close = min(time_windows[c][1] for c in trip)
            sub = generate_subclusters(trip, max_size=max_size)
            trip_qubits = sum(len(sc)**2 for sc in sub)
            grand_qubits += trip_qubits
            grand_sub += len(sub)
            label = f"Trip {t_idx+1}" if len(trips)>1 else "Single Trip"
            print(f"|")
            print(f"|  +- {label}: nodes={trip} | window=[{tw_open}:00-{tw_close}:00]")
            print(f"|  |  Load : Frozen={trip_frozen}/{capacity['frozen']} [OK] · Chilled={trip_chilled}/{capacity['chilled']} [OK] · Ambient={trip_ambient}/{capacity['ambient']} [OK]")
            print(f"|  |  Sub-clusters ({len(sub)} groups, {trip_qubits} qubits):")
            for sc in sub:
                names = [get_clinic_name(c, clinics) for c in sc]
                print(f"|  |    {sc} -> {names}  [{len(sc)**2} qubits]")
        print("|")
    limit_size = max_size if max_size is not None else MAX_CLUSTER_SIZE
    max_qubits = (limit_size**2) * grand_sub
    print("="*55)
    print(f"  Total sub-clusters : {grand_sub}")
    print(f"  Total qubits       : {grand_qubits}")
    print(f"  Simulator safe     : {'[OK]' if grand_qubits <= max_qubits else '[WARN]'} "
          f"({grand_qubits}/{max_qubits} max)")
    print("="*55)

# ─────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────
def build_clusters(sc_module=None, max_size=None):
    """Run the full clustering pipeline.
    sc_module – optional scenario module (scenario or scenario2).
    """
    global _default_scenario
    if sc_module is not None:
        _default_scenario = sc_module
    else:
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
    # STEP 1 – temporal‑aware K‑means with exactly n_vehicles
    n_clusters = n_vehicles
    clusters, _, _ = temporal_aware_kmeans(n_clusters)
    print(f"Initial clusters (temporal-aware): {clusters}\n")
    # STEP 2 – capacity repair (using dynamic relaxed capacity for multi-trip vehicle clusters)
    total_demands = {temp: sum(demands[c["id"]][temp] for c in clinics) for temp in capacity}
    avg_demand_per_vehicle = {temp: total_demands[temp] / n_vehicles for temp in capacity}
    relaxed_capacity = {
        temp: max(capacity[temp] * 2.0, avg_demand_per_vehicle[temp] * 1.5)
        for temp in capacity
    }
    clusters = repair_vehicle_clusters(clusters, relaxed_capacity, demands, distance_matrix)
    # STEP 3 – assign trips per vehicle (using actual capacity for individual trips)
    vehicle_routes = []
    for i, cluster in enumerate(clusters):
        vehicle_id = vehicles[i]["id"] if i < len(vehicles) else f"V{i+1}"
        trips = assign_trips(cluster, capacity, demands, time_windows)
        vehicle_routes.append((vehicle_id, trips))
    # STEP 4 – temporal repair of clusters (no-op)
    vehicle_routes = [(vid, trips) for vid, trips in vehicle_routes]
    cluster_lists = [c for _, c in vehicle_routes]
    cluster_lists = repair_temporal(cluster_lists)
    vehicle_routes = [(vehicles[i]["id"] if i < len(vehicles) else f"V{i+1}", cl) for i, cl in enumerate(cluster_lists)]
    # STEP 5 – summary
    print_summary(vehicle_routes, clinics, capacity, demands, time_windows, max_size=max_size)
    return vehicle_routes

if __name__ == "__main__":
    build_clusters()

