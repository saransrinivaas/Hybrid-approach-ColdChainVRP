"""
node_splitting.py — Demand-overflow Node Splitter for Cold-Chain VRP

When a clinic's demand in any compartment exceeds the maximum vehicle capacity,
it cannot be served in a single trip.  This module splits such a clinic into
multiple *phantom* nodes that share the same coordinates but each carry a
vehicle-feasible portion of the demand.

Design decisions
────────────────
• Phantom nodes use composite IDs:  original_id * 1000 + part_index
  e.g. clinic 7 → 7001, 7002, 7003
  This keeps IDs numeric, avoids string-parsing in solvers, and makes
  the original clinic trivially recoverable (id // 1000).

• Phantom nodes inherit the original clinic's lat/lon, time window, name
  (with " Part N" suffix), and all other metadata.

• The DISTANCE_MATRIX is extended: phantom nodes at the same location
  have zero distance between themselves and the same distances to all
  other nodes as the original.

• Demands are split greedily across compartments: each part takes as much
  as the vehicle can carry in that compartment until the remainder is zero.

• The module is non-destructive: original scenario attributes are not
  mutated.  It returns a new lightweight namespace with extended data.

Usage
─────
    from node_splitting import apply_node_splitting
    sc_ext = apply_node_splitting(scenario_module)
    # sc_ext has: CLINICS, DEMANDS, TIME_WINDOWS, DISTANCE_MATRIX,
    #             DEPOT, VEHICLES, SPOILAGE, ENERGY_RATE, AVG_SPEED_KMH
    #             split_map  → {phantom_id: original_id}
    #             is_split   → True if any splits occurred

Route post-processing
─────────────────────
After stitching, call collapse_split_nodes(route, split_map) to replace
phantom IDs back with the original clinic ID in the display output.
"""

import copy
import math
import numpy as np

# ─────────────────────────────────────────
# Public API
# ─────────────────────────────────────────

def apply_node_splitting(sc):
    """
    Inspect every clinic in *sc* against the fleet's maximum per-compartment
    capacity.  Clinics that overflow any compartment are replaced by phantom
    nodes; all others pass through unchanged.

    Returns a SimpleNamespace that mirrors the scenario's attribute API so
    that every downstream module (clustering, QAOA solver, stitching) works
    without modification.
    """
    vehicles   = sc.VEHICLES
    clinics    = sc.CLINICS
    demands    = sc.DEMANDS
    time_wins  = sc.TIME_WINDOWS
    dm         = np.asarray(sc.DISTANCE_MATRIX, dtype=float)

    max_cap = _max_capacity(vehicles)

    new_clinics    = []
    new_demands    = {}
    new_time_wins  = {}
    split_map      = {}   # phantom_id → original_id
    any_split      = False

    for clinic in clinics:
        cid = clinic["id"]
        dem = demands[cid]

        if _needs_split(dem, max_cap):
            parts = _split_clinic(clinic, dem, max_cap)
            any_split = True
            print(f"  [SPLIT] Clinic {cid} ({clinic['name']}) -> "
                  f"{len(parts)} phantom nodes "
                  f"(frozen={dem['frozen']}, chilled={dem['chilled']}, "
                  f"ambient={dem['ambient']}  /  cap={max_cap})")
            for part in parts:
                new_clinics.append(part)
                new_demands[part["id"]]   = part["demand"]
                new_time_wins[part["id"]] = time_wins[cid]
                split_map[part["id"]]     = cid
        else:
            new_clinics.append(clinic)
            new_demands[cid]   = dem
            new_time_wins[cid] = time_wins[cid]

    if not any_split:
        print("  [SPLIT] No oversized clinics - scenario passes through unchanged.")
        # Attach helpers even on pass-through so callers don't need to branch
        sc_ext = _make_namespace(sc, clinics, demands, time_wins, dm, {}, False)
        return sc_ext

    # Extend the distance matrix to cover phantom node IDs
    new_dm = _extend_distance_matrix(dm, clinics, new_clinics, split_map, sc.DEPOT)
    sc_ext  = _make_namespace(sc, new_clinics, new_demands, new_time_wins,
                               new_dm, split_map, True)
    return sc_ext


def collapse_split_nodes(route, split_map):
    """
    Replace phantom IDs in *route* with the original clinic ID.
    Multiple phantoms of the same clinic appear as repeated stops — correct
    because a different vehicle visits each time.

    Args:
        route      List[int] — route with possible phantom IDs
        split_map  Dict[int,int] — phantom_id → original_id

    Returns:
        List[int] — route with all phantom IDs resolved to originals
    """
    return [split_map.get(cid, cid) for cid in route]


def get_original_id(node_id, split_map):
    """Return the original clinic ID, resolving phantoms if necessary."""
    return split_map.get(node_id, node_id)


# ─────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────

_COMPARTMENTS = ("frozen", "chilled", "ambient")
_PHANTOM_MULTIPLIER = 1000   # phantom id = original_id * 1000 + part_index


def _max_capacity(vehicles):
    """Maximum per-compartment capacity across all vehicles."""
    return {
        t: max(v["compartments"][t]["capacity"] for v in vehicles)
        for t in _COMPARTMENTS
    }


def _needs_split(demand, max_cap):
    """True if any compartment demand exceeds max vehicle capacity."""
    return any(demand.get(t, 0) > max_cap[t] for t in _COMPARTMENTS)


def _split_clinic(clinic, demand, max_cap):
    """
    Decompose *clinic* into the minimum number of phantom nodes so that
    each part fits within max_cap for every compartment.

    Returns a list of new clinic dicts, each with a unique phantom ID and
    a partial demand dict.
    """
    remaining = {t: demand.get(t, 0) for t in _COMPARTMENTS}
    parts     = []
    part_idx  = 1

    while any(remaining[t] > 0 for t in _COMPARTMENTS):
        part_demand = {}
        for t in _COMPARTMENTS:
            part_demand[t] = min(remaining[t], max_cap[t])
            remaining[t]  -= part_demand[t]

        phantom_id = clinic["id"] * _PHANTOM_MULTIPLIER + part_idx
        parts.append({
            **clinic,
            "id":           phantom_id,
            "name":         f"{clinic['name']} (Part {part_idx})",
            "demand":       part_demand,
            "is_phantom":   True,
            "original_id":  clinic["id"],
        })
        part_idx += 1

    return parts


def _extend_distance_matrix(dm, original_clinics, new_clinics, split_map, depot):
    """
    Build an extended distance matrix that includes all phantom node IDs.

    Strategy:
    • phantom nodes at the same location → distance 0 to each other
    • phantom node → any other node: same distance as original clinic → that node
    • The matrix is indexed by node ID; depot is ID 0.
    """
    # Collect all node IDs we need
    all_ids = {0}   # depot
    for c in original_clinics:
        all_ids.add(c["id"])
    for c in new_clinics:
        all_ids.add(c["id"])

    max_id = max(all_ids)
    new_dm = np.zeros((max_id + 1, max_id + 1))

    # Copy existing distances for original IDs
    orig_max = dm.shape[0]
    for i in range(min(orig_max, max_id + 1)):
        for j in range(min(orig_max, max_id + 1)):
            new_dm[i][j] = dm[i][j]

    # Build original_id → lat/lon lookup (for haversine fallback)
    loc_lookup = {0: (depot["lat"], depot["lon"])}
    for c in original_clinics:
        loc_lookup[c["id"]] = (c["lat"], c["lon"])
    for c in new_clinics:
        if not c.get("is_phantom"):
            loc_lookup[c["id"]] = (c["lat"], c["lon"])

    def _dist(a, b):
        """Distance from node a to node b in the extended matrix."""
        # Resolve phantoms to originals for distance lookup
        real_a = split_map.get(a, a)
        real_b = split_map.get(b, b)
        if real_a == real_b:
            return 0.0   # same physical location
        if real_a < orig_max and real_b < orig_max:
            return dm[real_a][real_b]
        # Haversine fallback for newly added nodes
        if real_a in loc_lookup and real_b in loc_lookup:
            return _haversine(*loc_lookup[real_a], *loc_lookup[real_b])
        return 0.0

    # Fill in phantom ↔ everything distances
    phantom_ids = set(split_map.keys())
    all_node_ids = list(all_ids)

    for pid in phantom_ids:
        for oid in all_node_ids:
            d = _dist(pid, oid)
            new_dm[pid][oid] = d
            new_dm[oid][pid] = d

    return new_dm


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi   = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def _make_namespace(sc, clinics, demands, time_wins, dm, split_map, is_split):
    """Return a lightweight object that mimics a scenario module's API."""
    from types import SimpleNamespace
    return SimpleNamespace(
        DEPOT           = sc.DEPOT,
        CLINICS         = clinics,
        DEMANDS         = demands,
        TIME_WINDOWS    = time_wins,
        DISTANCE_MATRIX = dm,
        VEHICLES        = sc.VEHICLES,
        SPOILAGE        = sc.SPOILAGE,
        ENERGY_RATE     = sc.ENERGY_RATE,
        AVG_SPEED_KMH   = sc.AVG_SPEED_KMH,
        split_map       = split_map,   # phantom_id → original_id
        is_split        = is_split,
        __name__        = getattr(sc, "__name__", "scenario") + ("_split" if is_split else ""),
    )


# ─────────────────────────────────────────
# Quick self-test
# ─────────────────────────────────────────
if __name__ == "__main__":
    try:
        import scenario_dynamic as sc
    except ImportError:
        import scenario as sc

    print("=" * 55)
    print("  NODE SPLITTING SELF-TEST")
    print("=" * 55)

    sc_ext = apply_node_splitting(sc)
    print(f"\n  Original clinics : {len(sc.CLINICS)}")
    print(f"  Extended clinics : {len(sc_ext.CLINICS)}")
    print(f"  Split map        : {sc_ext.split_map}")
    print(f"  DM shape         : {sc_ext.DISTANCE_MATRIX.shape}")

    if sc_ext.is_split:
        print("\n  Phantom nodes:")
        for c in sc_ext.CLINICS:
            if c.get("is_phantom"):
                print(f"    {c['id']} -> {c['name']}  demand={c['demand']}")
    else:
        print("\n  No splits needed for this scenario.")
