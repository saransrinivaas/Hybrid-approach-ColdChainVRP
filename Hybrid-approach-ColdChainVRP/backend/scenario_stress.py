import os
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# SOUTH INDIA MULTI-CITY STRESS TEST — 50 Nodes
#
# This scenario is a true algorithmic stress test spanning 5 South Indian cities:
#   - Chennai       (10 clinics)  — depot city
#   - Bengaluru     (12 clinics)  — ~350 km from Chennai
#   - Hyderabad     (10 clinics)  — ~620 km from Chennai
#   - Coimbatore    (8 clinics)   — ~500 km from Chennai
#   - Madurai       (10 clinics)  — ~450 km from Chennai
#
# Challenge dimensions:
#   • 50 delivery nodes across 5 cities with real GPS coordinates
#   • Inter-city distances of 300–700 km stretch cold-chain limits
#   • 5 vehicles — but demand is intentionally tight per-vehicle
#   • Non-uniform, city-specific time windows (government clinic hours vary)
#   • Mixed spoilage urgency: frozen (-20°C) and ambient vaccines on same route
#   • Capacity barely sufficient — requires node splitting for overflow clinics
# ─────────────────────────────────────────────────────────────────────────────

DEPOT = {
    "id": 0,
    "name": "South India Regional Vaccine Hub (Chennai)",
    "lat": 13.0827,
    "lon": 80.2707,  # Chennai — central distribution hub
}

# ─────────────────────────────────────────
# CLINICS
# IDs 1–10:  Chennai
# IDs 11–22: Bengaluru
# IDs 23–32: Hyderabad
# IDs 33–40: Coimbatore
# IDs 41–50: Madurai
# ─────────────────────────────────────────
CLINICS = [
    # ── Chennai (10) ──────────────────────────────────────────────────────────
    {"id": 1,  "name": "Tambaram PHC",          "lat": 12.9249, "lon": 80.1000},
    {"id": 2,  "name": "Guindy Hospital",       "lat": 13.0067, "lon": 80.2206},
    {"id": 3,  "name": "Adyar Clinic",          "lat": 13.0012, "lon": 80.2565},
    {"id": 4,  "name": "Velachery PHC",         "lat": 12.9815, "lon": 80.2180},
    {"id": 5,  "name": "Koyambedu PHC",         "lat": 13.0694, "lon": 80.1948},
    {"id": 6,  "name": "Anna Nagar Clinic",     "lat": 13.0850, "lon": 80.2101},
    {"id": 7,  "name": "Egmore PHC",            "lat": 13.0782, "lon": 80.2570},
    {"id": 8,  "name": "Perambur PHC",          "lat": 13.1148, "lon": 80.2345},
    {"id": 9,  "name": "Sholinganallur PHC",    "lat": 12.9010, "lon": 80.2270},
    {"id": 10, "name": "Avadi Clinic",          "lat": 13.1067, "lon": 80.0950},

    # ── Bengaluru (12) ────────────────────────────────────────────────────────
    {"id": 11, "name": "Koramangala Clinic BLR",   "lat": 12.9352, "lon": 77.6245},
    {"id": 12, "name": "Malleshwaram PHC BLR",     "lat": 13.0040, "lon": 77.5710},
    {"id": 13, "name": "Electronic City PHC BLR",  "lat": 12.8399, "lon": 77.6770},
    {"id": 14, "name": "Hebbal Clinic BLR",        "lat": 13.0358, "lon": 77.5970},
    {"id": 15, "name": "Whitefield PHC BLR",       "lat": 12.9698, "lon": 77.7500},
    {"id": 16, "name": "Jayanagar Hospital BLR",   "lat": 12.9248, "lon": 77.5838},
    {"id": 17, "name": "BTM Layout PHC BLR",       "lat": 12.9165, "lon": 77.6101},
    {"id": 18, "name": "Marathahalli Clinic BLR",  "lat": 12.9591, "lon": 77.6974},
    {"id": 19, "name": "Rajajinagar PHC BLR",      "lat": 12.9890, "lon": 77.5530},
    {"id": 20, "name": "Banashankari PHC BLR",     "lat": 12.9258, "lon": 77.5462},
    {"id": 21, "name": "Yeshwanthpur Clinic BLR",  "lat": 13.0214, "lon": 77.5542},
    {"id": 22, "name": "JP Nagar Clinic BLR",      "lat": 12.9061, "lon": 77.5856},

    # ── Hyderabad (10) ────────────────────────────────────────────────────────
    {"id": 23, "name": "Banjara Hills PHC HYD",    "lat": 17.4156, "lon": 78.4347},
    {"id": 24, "name": "Gachibowli Hospital HYD",  "lat": 17.4401, "lon": 78.3489},
    {"id": 25, "name": "Kukatpally Clinic HYD",    "lat": 17.4850, "lon": 78.3996},
    {"id": 26, "name": "Malkajgiri PHC HYD",       "lat": 17.4554, "lon": 78.5329},
    {"id": 27, "name": "Uppal Clinic HYD",         "lat": 17.4064, "lon": 78.5598},
    {"id": 28, "name": "Dilsukhnagar PHC HYD",     "lat": 17.3692, "lon": 78.5261},
    {"id": 29, "name": "Mehdipatnam Clinic HYD",   "lat": 17.3936, "lon": 78.4382},
    {"id": 30, "name": "Madhapur PHC HYD",         "lat": 17.4504, "lon": 78.3916},
    {"id": 31, "name": "LB Nagar PHC HYD",         "lat": 17.3469, "lon": 78.5534},
    {"id": 32, "name": "Tolichowki Clinic HYD",    "lat": 17.3987, "lon": 78.4162},

    # ── Coimbatore (8) ────────────────────────────────────────────────────────
    {"id": 33, "name": "RS Puram PHC CBE",         "lat": 11.0143, "lon": 76.9525},
    {"id": 34, "name": "Peelamedu Clinic CBE",     "lat": 11.0263, "lon": 77.0200},
    {"id": 35, "name": "Gandhipuram PHC CBE",      "lat": 11.0176, "lon": 76.9674},
    {"id": 36, "name": "Singanallur Hospital CBE", "lat": 10.9929, "lon": 77.0153},
    {"id": 37, "name": "Saibaba Colony PHC CBE",   "lat": 11.0300, "lon": 76.9700},
    {"id": 38, "name": "Ukkadam Clinic CBE",       "lat": 10.9956, "lon": 76.9803},
    {"id": 39, "name": "Kuniyamuthur PHC CBE",     "lat": 10.9741, "lon": 76.9508},
    {"id": 40, "name": "Sulur Clinic CBE",         "lat": 11.0330, "lon": 77.1200},

    # ── Madurai (10) ──────────────────────────────────────────────────────────
    {"id": 41, "name": "Tallakulam PHC MDU",       "lat": 9.9252,  "lon": 78.1198},
    {"id": 42, "name": "KK Nagar Clinic MDU",      "lat": 9.9179,  "lon": 78.1048},
    {"id": 43, "name": "Anna Nagar PHC MDU",       "lat": 9.9312,  "lon": 78.1350},
    {"id": 44, "name": "Arappalayam Hospital MDU", "lat": 9.9450,  "lon": 78.1278},
    {"id": 45, "name": "Villapuram Clinic MDU",    "lat": 9.8971,  "lon": 78.1143},
    {"id": 46, "name": "Arapalayam PHC MDU",       "lat": 9.9634,  "lon": 78.1103},
    {"id": 47, "name": "Ellis Nagar Clinic MDU",   "lat": 9.9088,  "lon": 78.1295},
    {"id": 48, "name": "Surveyor Colony PHC MDU",  "lat": 9.9396,  "lon": 78.0987},
    {"id": 49, "name": "Palanganatham Clinic MDU", "lat": 9.8855,  "lon": 78.1380},
    {"id": 50, "name": "Thirunagar PHC MDU",       "lat": 9.9517,  "lon": 78.1435},
]

# ─────────────────────────────────────────
# DEMANDS
# Intentionally varied to stress capacity across routes.
# Each vehicle handles ~35 frozen + 35 chilled + 35 ambient capacity.
# ─────────────────────────────────────────
DEMANDS = {
    # Chennai (10 clinics)
    1:  {"frozen": 2, "chilled": 2, "ambient": 2},
    2:  {"frozen": 3, "chilled": 2, "ambient": 2},
    3:  {"frozen": 1, "chilled": 2, "ambient": 2},
    4:  {"frozen": 2, "chilled": 1, "ambient": 2},
    5:  {"frozen": 3, "chilled": 2, "ambient": 2},
    6:  {"frozen": 1, "chilled": 2, "ambient": 1},
    7:  {"frozen": 2, "chilled": 2, "ambient": 2},
    8:  {"frozen": 3, "chilled": 1, "ambient": 2},
    9:  {"frozen": 1, "chilled": 2, "ambient": 2},
    10: {"frozen": 2, "chilled": 2, "ambient": 1},
    # Bengaluru (12 clinics)
    11: {"frozen": 3, "chilled": 2, "ambient": 2},
    12: {"frozen": 2, "chilled": 2, "ambient": 2},
    13: {"frozen": 1, "chilled": 2, "ambient": 2},
    14: {"frozen": 3, "chilled": 1, "ambient": 2},
    15: {"frozen": 2, "chilled": 2, "ambient": 1},
    16: {"frozen": 1, "chilled": 2, "ambient": 2},
    17: {"frozen": 3, "chilled": 2, "ambient": 2},
    18: {"frozen": 2, "chilled": 1, "ambient": 2},
    19: {"frozen": 1, "chilled": 2, "ambient": 2},
    20: {"frozen": 2, "chilled": 2, "ambient": 2},
    21: {"frozen": 3, "chilled": 1, "ambient": 1},
    22: {"frozen": 1, "chilled": 2, "ambient": 2},
    # Hyderabad (10 clinics)
    23: {"frozen": 2, "chilled": 2, "ambient": 2},
    24: {"frozen": 3, "chilled": 2, "ambient": 2},
    25: {"frozen": 1, "chilled": 2, "ambient": 2},
    26: {"frozen": 2, "chilled": 1, "ambient": 2},
    27: {"frozen": 3, "chilled": 2, "ambient": 1},
    28: {"frozen": 2, "chilled": 2, "ambient": 2},
    29: {"frozen": 1, "chilled": 2, "ambient": 2},
    30: {"frozen": 3, "chilled": 1, "ambient": 2},
    31: {"frozen": 2, "chilled": 2, "ambient": 2},
    32: {"frozen": 1, "chilled": 2, "ambient": 2},
    # Coimbatore (8 clinics)
    33: {"frozen": 2, "chilled": 2, "ambient": 2},
    34: {"frozen": 3, "chilled": 2, "ambient": 2},
    35: {"frozen": 1, "chilled": 2, "ambient": 2},
    36: {"frozen": 2, "chilled": 2, "ambient": 2},
    37: {"frozen": 3, "chilled": 1, "ambient": 2},
    38: {"frozen": 2, "chilled": 2, "ambient": 1},
    39: {"frozen": 1, "chilled": 2, "ambient": 2},
    40: {"frozen": 2, "chilled": 2, "ambient": 2},
    # Madurai (10 clinics)
    41: {"frozen": 3, "chilled": 2, "ambient": 2},
    42: {"frozen": 2, "chilled": 2, "ambient": 2},
    43: {"frozen": 1, "chilled": 2, "ambient": 2},
    44: {"frozen": 3, "chilled": 1, "ambient": 2},
    45: {"frozen": 2, "chilled": 2, "ambient": 2},
    46: {"frozen": 1, "chilled": 2, "ambient": 2},
    47: {"frozen": 3, "chilled": 2, "ambient": 1},
    48: {"frozen": 2, "chilled": 1, "ambient": 2},
    49: {"frozen": 1, "chilled": 2, "ambient": 2},
    50: {"frozen": 2, "chilled": 2, "ambient": 2},
}
# Total per compartment:
#   frozen:  100  |  chilled: 94  |  ambient: 91
# Fleet cap: 5 × 20 = 100  →  frozen uses 100% capacity (maximum stress),
# chilled/ambient at 94% and 91% — heavily loaded but feasible.

# ─────────────────────────────────────────
# VEHICLE FLEET — 5 vehicles for 50 nodes
# Each vehicle is a dedicated city-corridor runner
# ─────────────────────────────────────────
VEHICLES = [
    {
        "id": "V1",  # Chennai corridor
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 20},
            "chilled": {"temp_c":   4, "capacity": 20},
            "ambient": {"temp_c":  20, "capacity": 20},
        }
    },
    {
        "id": "V2",  # Bengaluru corridor
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 20},
            "chilled": {"temp_c":   4, "capacity": 20},
            "ambient": {"temp_c":  20, "capacity": 20},
        }
    },
    {
        "id": "V3",  # Hyderabad corridor
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 20},
            "chilled": {"temp_c":   4, "capacity": 20},
            "ambient": {"temp_c":  20, "capacity": 20},
        }
    },
    {
        "id": "V4",  # Coimbatore / Madurai corridor
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 20},
            "chilled": {"temp_c":   4, "capacity": 20},
            "ambient": {"temp_c":  20, "capacity": 20},
        }
    },
    {
        "id": "V5",  # Overflow / cross-city support
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 20},
            "chilled": {"temp_c":   4, "capacity": 20},
            "ambient": {"temp_c":  20, "capacity": 20},
        }
    },
]

# ─────────────────────────────────────────
# SPOILAGE PARAMETERS
# ─────────────────────────────────────────
SPOILAGE = {
    "frozen":  {"alpha": 0.001, "value": 500},
    "chilled": {"alpha": 0.010, "value": 200},
    "ambient": {"alpha": 0.050, "value":  50},
}

# ─────────────────────────────────────────
# TIME WINDOWS
# Realistic government clinic hours for each city region.
# Many clinics have STRICT windows — creating scheduling friction
# across the 300–700 km inter-city travel distances.
# ─────────────────────────────────────────
TIME_WINDOWS = {i: (8, 18) for i in range(1, 51)}

# Chennai tight windows
TIME_WINDOWS[3]  = (8,  13)   # Adyar — morning
TIME_WINDOWS[7]  = (10, 16)   # Egmore — mid-day
TIME_WINDOWS[9]  = (13, 18)   # Sholinganallur — afternoon

# Bengaluru tight windows (traffic-heavy)
TIME_WINDOWS[13] = (9,  14)   # Electronic City — tight
TIME_WINDOWS[15] = (8,  13)   # Whitefield — morning (far east)
TIME_WINDOWS[22] = (13, 17)   # JP Nagar — afternoon

# Hyderabad tight windows
TIME_WINDOWS[24] = (9,  14)   # Gachibowli — tech corridor hours
TIME_WINDOWS[26] = (8,  12)   # Malkajgiri — strict morning
TIME_WINDOWS[31] = (14, 18)   # LB Nagar — afternoon only

# Coimbatore tight windows
TIME_WINDOWS[36] = (8,  13)   # Singanallur — morning
TIME_WINDOWS[40] = (11, 16)   # Sulur — mid-day (outskirts)

# Madurai tight windows
TIME_WINDOWS[45] = (8,  13)   # Villapuram — morning
TIME_WINDOWS[47] = (13, 18)   # Ellis Nagar — afternoon
TIME_WINDOWS[49] = (9,  14)   # Palanganatham — strict mid

# ─────────────────────────────────────────
# SHARED PHYSICAL CONSTANTS
# Inter-city highways: 60 km/h average including stops
# ─────────────────────────────────────────
AVG_SPEED_KMH = 60  # highway speed for inter-city legs

ENERGY_RATE = {
    "frozen":  0.050,   # kWh per hour per compartment
    "chilled": 0.030,
    "ambient": 0.010,
}

# ─────────────────────────────────────────
# DISTANCE MATRIX (Haversine — geographic straight-line)
# ─────────────────────────────────────────
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
    print("=== South India Multi-City Stress Test (50 nodes) Loaded ===")
    print(f"Depot: {DEPOT['name']}")
    print(f"Clinics: {len(CLINICS)} across 5 cities")
    print(f"Vehicles: {len(VEHICLES)}")
    print(f"Distance matrix shape: {DISTANCE_MATRIX.shape}")
    print(f"Sample — Chennai to Bengaluru (Koramangala): {DISTANCE_MATRIX[0][11]:.0f} km")
    print(f"Sample — Chennai to Hyderabad (Banjara Hills): {DISTANCE_MATRIX[0][23]:.0f} km")
    print(f"Sample — Chennai to Coimbatore: {DISTANCE_MATRIX[0][33]:.0f} km")
    print(f"Sample — Chennai to Madurai: {DISTANCE_MATRIX[0][41]:.0f} km")
    for temp in ("frozen", "chilled", "ambient"):
        tot = sum(d[temp] for d in DEMANDS.values())
        total_cap = sum(v["compartments"][temp]["capacity"] for v in VEHICLES)
        print(f"  {temp}: {tot} demand / {total_cap} total capacity")
    print("\n✓ South India Stress Test scenario data ready")
