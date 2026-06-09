import os
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO: Bengaluru City Run — MULTI-TRIP STRESS
#
# This scenario is designed to force MULTI-TRIP routing:
#   • Vehicle capacity: 12 units per compartment
#   • Fleet (2 vehicles) total capacity: 24 per compartment
#   • Total demand per compartment: ~30 units — EXCEEDS fleet single-trip capacity
#
# Consequence: at least one vehicle must return to the depot mid-route and
# reload before completing all deliveries. This stresses the routing solver's
# ability to plan depot revisits and correctly account for cumulative travel time.
#
# No individual clinic exceeds capacity 12 → no node splitting triggered.
# ─────────────────────────────────────────────────────────────────────────────

DEPOT = {
    "id": 0,
    "name": "Bengaluru Central Vaccine Depot",
    "lat": 12.9716,
    "lon": 77.5946,  # Bengaluru City Station area
}

# 12 real Bengaluru GPS clinic locations
CLINICS = [
    {"id": 1,  "name": "Rajajinagar PHC",        "lat": 12.9890, "lon": 77.5530},
    {"id": 2,  "name": "Malleshwaram Clinic",    "lat": 13.0040, "lon": 77.5710},
    {"id": 3,  "name": "Hebbal PHC",             "lat": 13.0358, "lon": 77.5970},
    {"id": 4,  "name": "Yeshwanthpur Clinic",    "lat": 13.0214, "lon": 77.5542},
    {"id": 5,  "name": "Electronic City PHC",    "lat": 12.8399, "lon": 77.6770},
    {"id": 6,  "name": "Koramangala Clinic",     "lat": 12.9352, "lon": 77.6245},
    {"id": 7,  "name": "BTM Layout PHC",         "lat": 12.9165, "lon": 77.6101},
    {"id": 8,  "name": "Whitefield Clinic",      "lat": 12.9698, "lon": 77.7500},
    {"id": 9,  "name": "Marathahalli PHC",       "lat": 12.9591, "lon": 77.6974},
    {"id": 10, "name": "Jayanagar Hospital",     "lat": 12.9248, "lon": 77.5838},
    {"id": 11, "name": "JP Nagar Clinic",        "lat": 12.9061, "lon": 77.5856},
    {"id": 12, "name": "Banashankari PHC",       "lat": 12.9258, "lon": 77.5462},
]

# ─────────────────────────────────────────────────────────────────────────────
# DEMANDS — alternating pattern gives exactly 30 units per compartment total
# Fleet can carry 24 per compartment (2 × 12) in one pass.
# 30 > 24 → at least one vehicle must reload (multi-trip required).
# No individual demand exceeds the per-vehicle capacity of 12.
# ─────────────────────────────────────────────────────────────────────────────
DEMANDS = {
    1:  {"frozen": 3, "chilled": 2, "ambient": 3},   # cumulative frozen: 3
    2:  {"frozen": 2, "chilled": 3, "ambient": 2},   # cumulative frozen: 5
    3:  {"frozen": 3, "chilled": 2, "ambient": 3},   # cumulative frozen: 8
    4:  {"frozen": 2, "chilled": 3, "ambient": 2},   # cumulative frozen: 10
    5:  {"frozen": 3, "chilled": 2, "ambient": 3},   # cumulative frozen: 13
    6:  {"frozen": 2, "chilled": 3, "ambient": 2},   # cumulative frozen: 15
    7:  {"frozen": 3, "chilled": 2, "ambient": 3},   # cumulative frozen: 18
    8:  {"frozen": 2, "chilled": 3, "ambient": 2},   # cumulative frozen: 20
    9:  {"frozen": 3, "chilled": 2, "ambient": 3},   # cumulative frozen: 23
    10: {"frozen": 2, "chilled": 3, "ambient": 2},   # cumulative frozen: 25
    11: {"frozen": 3, "chilled": 2, "ambient": 3},   # cumulative frozen: 28
    12: {"frozen": 2, "chilled": 3, "ambient": 2},   # cumulative frozen: 30
}
# Total per compartment:
#   frozen:  30  |  chilled: 30  |  ambient: 30
# Fleet capacity: 2 vehicles × 12 = 24 per compartment
# SHORTFALL: 6 units per compartment → multi-trip mandatory

# ─────────────────────────────────────────────────────────────────────────────
# VEHICLE FLEET — capacity intentionally tight to force multi-trip
# ─────────────────────────────────────────────────────────────────────────────
VEHICLES = [
    {
        "id": "V1",
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 12},
            "chilled": {"temp_c":   4, "capacity": 12},
            "ambient": {"temp_c":  20, "capacity": 12},
        }
    },
    {
        "id": "V2",
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 12},
            "chilled": {"temp_c":   4, "capacity": 12},
            "ambient": {"temp_c":  20, "capacity": 12},
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
# TIME WINDOWS — Bengaluru clinics with 4 tight windows to add scheduling pressure
# ─────────────────────────────────────────────────────────────────────────────
TIME_WINDOWS = {i: (8, 18) for i in range(1, 13)}
TIME_WINDOWS[3]  = (8,  13)   # Hebbal — morning only
TIME_WINDOWS[5]  = (10, 16)   # Electronic City — mid-day
TIME_WINDOWS[8]  = (9,  14)   # Whitefield — tight (far east, takes time to reach)
TIME_WINDOWS[11] = (13, 18)   # JP Nagar — afternoon only

# ─────────────────────────────────────────────────────────────────────────────
# PHYSICAL CONSTANTS — Bengaluru traffic is slow
# ─────────────────────────────────────────────────────────────────────────────
AVG_SPEED_KMH = 25  # Bengaluru city traffic

ENERGY_RATE = {
    "frozen":  0.050,
    "chilled": 0.030,
    "ambient": 0.010,
}

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
    print("=== Scenario BLR (Bengaluru — Multi-Trip) Loaded ===")
    print(f"Depot: {DEPOT['name']}")
    print(f"Clinics: {len(CLINICS)}")
    print(f"Vehicles: {len(VEHICLES)}, Capacity: 12/compartment")
    for temp in ("frozen", "chilled", "ambient"):
        tot = sum(d[temp] for d in DEMANDS.values())
        fleet_cap = 2 * VEHICLES[0]["compartments"][temp]["capacity"]
        print(f"  {temp}: {tot} demand vs {fleet_cap} fleet capacity  ← {'MULTI-TRIP REQUIRED' if tot > fleet_cap else 'OK'}")
    print("\n✓ Bengaluru multi-trip scenario data ready")
