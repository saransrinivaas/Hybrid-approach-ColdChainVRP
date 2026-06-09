import os
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO: Hyderabad City Run — NODE SPLITTING STRESS
#
# This scenario is designed to force NODE SPLITTING for at least 2 clinics:
#   • Vehicle capacity: 15 units per compartment (standard)
#   • Clinic 3  (Gachibowli Hospital): frozen = 16 → EXCEEDS 15 → splits into
#       3a (frozen=15) + 3b (frozen=1) — two separate delivery stops
#   • Clinic 8  (LB Nagar PHC):      chilled = 16 → EXCEEDS 15 → splits into
#       8a (chilled=15) + 8b (chilled=1) — two separate delivery stops
#
# Total demand across all clinics remains within 2-vehicle fleet capacity:
#   frozen:  27 < 30 (2×15)  ✓
#   chilled: 28 < 30 (2×15)  ✓
#   ambient: 24 < 30 (2×15)  ✓
# ─────────────────────────────────────────────────────────────────────────────

DEPOT = {
    "id": 0,
    "name": "Hyderabad Central Vaccine Hub",
    "lat": 17.3850,
    "lon": 78.4867,  # Secunderabad area
}

# 12 real Hyderabad GPS clinic locations
CLINICS = [
    {"id": 1,  "name": "Banjara Hills PHC",      "lat": 17.4156, "lon": 78.4347},
    {"id": 2,  "name": "Jubilee Hills Clinic",   "lat": 17.4313, "lon": 78.4077},
    {"id": 3,  "name": "Gachibowli Hospital",    "lat": 17.4401, "lon": 78.3489},
    {"id": 4,  "name": "Madhapur PHC",           "lat": 17.4504, "lon": 78.3916},
    {"id": 5,  "name": "Kukatpally Clinic",      "lat": 17.4850, "lon": 78.3996},
    {"id": 6,  "name": "Malkajgiri PHC",         "lat": 17.4554, "lon": 78.5329},
    {"id": 7,  "name": "Uppal Clinic",           "lat": 17.4064, "lon": 78.5598},
    {"id": 8,  "name": "LB Nagar PHC",           "lat": 17.3469, "lon": 78.5534},
    {"id": 9,  "name": "Dilsukhnagar Hospital",  "lat": 17.3692, "lon": 78.5261},
    {"id": 10, "name": "Mehdipatnam Clinic",     "lat": 17.3936, "lon": 78.4382},
    {"id": 11, "name": "Tolichowki PHC",         "lat": 17.3987, "lon": 78.4162},
    {"id": 12, "name": "Chandrayangutta Clinic", "lat": 17.3291, "lon": 78.4743},
]

# ─────────────────────────────────────────────────────────────────────────────
# DEMANDS
#   Clinic 3:  frozen=16  → exceeds vehicle capacity 15 → NODE SPLIT triggered
#   Clinic 8:  chilled=16 → exceeds vehicle capacity 15 → NODE SPLIT triggered
#   All others remain within capacity — no additional splitting.
#
# Total demand per compartment:
#   frozen:  16 + 11×1  = 27   < 30 fleet cap ✓
#   chilled:  2 + 16 + 10×1 = 28   < 30 fleet cap ✓
#   ambient: 12×2 = 24          < 30 fleet cap ✓
# ─────────────────────────────────────────────────────────────────────────────
DEMANDS = {
    1:  {"frozen": 1, "chilled": 1, "ambient": 2},   # normal
    2:  {"frozen": 1, "chilled": 1, "ambient": 2},   # normal
    3:  {"frozen": 16,"chilled": 2, "ambient": 2},   # ← OVERFLOW: frozen 16 > 15 → SPLIT
    4:  {"frozen": 1, "chilled": 1, "ambient": 2},   # normal
    5:  {"frozen": 1, "chilled": 1, "ambient": 2},   # normal
    6:  {"frozen": 1, "chilled": 1, "ambient": 2},   # normal
    7:  {"frozen": 1, "chilled": 1, "ambient": 2},   # normal
    8:  {"frozen": 1, "chilled": 16,"ambient": 2},   # ← OVERFLOW: chilled 16 > 15 → SPLIT
    9:  {"frozen": 1, "chilled": 1, "ambient": 2},   # normal
    10: {"frozen": 1, "chilled": 1, "ambient": 2},   # normal
    11: {"frozen": 1, "chilled": 1, "ambient": 2},   # normal
    12: {"frozen": 1, "chilled": 1, "ambient": 2},   # normal
}
# Total:
#   frozen:  27  |  chilled: 28  |  ambient: 24
# Fleet cap: 2×15=30 — all within limits post-splitting ✓

# ─────────────────────────────────────────────────────────────────────────────
# VEHICLE FLEET — standard 15-unit capacity
# ─────────────────────────────────────────────────────────────────────────────
VEHICLES = [
    {
        "id": "V1",
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 15},
            "chilled": {"temp_c":   4, "capacity": 15},
            "ambient": {"temp_c":  20, "capacity": 15},
        }
    },
    {
        "id": "V2",
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 15},
            "chilled": {"temp_c":   4, "capacity": 15},
            "ambient": {"temp_c":  20, "capacity": 15},
        }
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# SPOILAGE PARAMETERS
# ─────────────────────────────────────────────────────────────────────────────
SPOILAGE = {
    "frozen":  {"alpha": 0.001, "value": 500},
    "chilled": {"alpha": 0.010, "value": 200},
    "ambient": {"alpha": 0.050, "value":  50},
}

# ─────────────────────────────────────────────────────────────────────────────
# TIME WINDOWS — 4 tight/non-standard windows for scheduling friction
# ─────────────────────────────────────────────────────────────────────────────
TIME_WINDOWS = {i: (8, 18) for i in range(1, 13)}
TIME_WINDOWS[3]  = (9,  14)   # Gachibowli — tight mid-day (tech corridor)
TIME_WINDOWS[6]  = (8,  13)   # Malkajgiri — morning only
TIME_WINDOWS[8]  = (11, 17)   # LB Nagar — late morning (also a split node)
TIME_WINDOWS[12] = (13, 18)   # Chandrayangutta — afternoon only

# ─────────────────────────────────────────────────────────────────────────────
# PHYSICAL CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
AVG_SPEED_KMH = 28  # Hyderabad city traffic

ENERGY_RATE = {
    "frozen":  0.050,
    "chilled": 0.030,
    "ambient": 0.010,
}

# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# DISTANCE MATRIX (Google Maps / Haversine Fallback)
# ─────────────────────────────────────────────────────────────────────────────
from maps_api import get_road_distances

def build_distance_matrix():
    locations = [DEPOT] + CLINICS
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    matrix = get_road_distances(locations, api_key)
    return np.array(matrix)

DISTANCE_MATRIX = build_distance_matrix()

if __name__ == "__main__":
    print("=== Scenario HYD (Hyderabad — Node Splitting) Loaded ===")
    print(f"Depot: {DEPOT['name']}")
    print(f"Clinics: {len(CLINICS)}")
    print(f"Vehicles: {len(VEHICLES)}, Capacity: 15/compartment")
    cap = VEHICLES[0]["compartments"]
    for cid, d in DEMANDS.items():
        for temp in ("frozen", "chilled", "ambient"):
            if d[temp] > cap[temp]["capacity"]:
                print(f"  ⚡ Clinic {cid}: {temp}={d[temp]} > {cap[temp]['capacity']} → NODE SPLIT triggered")
    for temp in ("frozen", "chilled", "ambient"):
        tot = sum(d[temp] for d in DEMANDS.values())
        fleet_cap = 2 * cap[temp]["capacity"]
        print(f"  {temp}: {tot} demand / {fleet_cap} fleet cap  {'✓' if tot <= fleet_cap else '⚠ OVERFLOW'}")
    print("\n✓ Hyderabad node-splitting scenario data ready")
