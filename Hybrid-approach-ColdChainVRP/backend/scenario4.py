import numpy as np

# ─────────────────────────────────────────
# DEPOT
# ─────────────────────────────────────────
DEPOT = {
    "id": 0,
    "name": "Regional Vaccine Depot",
    "lat": 13.0827,
    "lon": 80.2707,  # Chennai central
}

# ─────────────────────────────────────────
# CLINICS (5 Chennai GPS points)
# ─────────────────────────────────────────
CLINICS = [
    {"id": 1,  "name": "Tambaram PHC",       "lat": 12.9249, "lon": 80.1000},
    {"id": 2,  "name": "Chromepet Clinic",   "lat": 12.9516, "lon": 80.1462},
    {"id": 3,  "name": "Pallavaram PHC",     "lat": 12.9675, "lon": 80.1491},
    {"id": 4,  "name": "Guindy Hospital",    "lat": 13.0067, "lon": 80.2206},
    {"id": 5,  "name": "Adyar Clinic",       "lat": 13.0012, "lon": 80.2565},
]

# ─────────────────────────────────────────
# DEMAND CONFIGURATION
# Designed with oversized demands (capacity of vehicle is 10):
#   - Clinic 2 has oversized chilled demand (15)
#   - Clinic 3 has oversized frozen demand (25)
#   - Clinic 5 has oversized ambient demand (18)
# ─────────────────────────────────────────
DEMANDS = {
    1:  {"frozen": 3,  "chilled": 4,  "ambient": 2},
    2:  {"frozen": 2,  "chilled": 15, "ambient": 1},
    3:  {"frozen": 25, "chilled": 2,  "ambient": 3},
    4:  {"frozen": 1,  "chilled": 1,  "ambient": 1},
    5:  {"frozen": 0,  "chilled": 2,  "ambient": 18},
}

# ─────────────────────────────────────────
# VEHICLE FLEET (4 vehicles with 10 units capacity per compartment)
# ─────────────────────────────────────────
VEHICLES = [
    {
        "id": "V1",
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 10},
            "chilled": {"temp_c":   4, "capacity": 10},
            "ambient": {"temp_c":  20, "capacity": 10},
        }
    },
    {
        "id": "V2",
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 10},
            "chilled": {"temp_c":   4, "capacity": 10},
            "ambient": {"temp_c":  20, "capacity": 10},
        }
    },
    {
        "id": "V3",
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 10},
            "chilled": {"temp_c":   4, "capacity": 10},
            "ambient": {"temp_c":  20, "capacity": 10},
        }
    },
    {
        "id": "V4",
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 10},
            "chilled": {"temp_c":   4, "capacity": 10},
            "ambient": {"temp_c":  20, "capacity": 10},
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
# TIME WINDOWS (clinic operating hours)
# ─────────────────────────────────────────
TIME_WINDOWS = {
    i: (8, 18) for i in range(1, 6)
}
TIME_WINDOWS[2] = (8, 13)
TIME_WINDOWS[5] = (12, 17)

# ─────────────────────────────────────────
# SHARED PHYSICAL CONSTANTS
# ─────────────────────────────────────────
AVG_SPEED_KMH = 30  # average vehicle speed (km/h)

ENERGY_RATE = {
    "frozen":  0.050,   # kWh per hour per compartment
    "chilled": 0.030,
    "ambient": 0.010,
}

# ─────────────────────────────────────────
# DISTANCE MATRIX BUILDER
# ─────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def build_distance_matrix():
    locations = [DEPOT] + CLINICS
    n = len(locations)
    matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                matrix[i][j] = haversine(
                    locations[i]["lat"], locations[i]["lon"],
                    locations[j]["lat"], locations[j]["lon"]
                )
    return matrix

DISTANCE_MATRIX = build_distance_matrix()

if __name__ == "__main__":
    print("=== Scenario 4 (Edge Case Split Test) Loaded ===")
    print(f"Depot: {DEPOT['name']}")
    print(f"Clinics: {len(CLINICS)}")
    print(f"Vehicles: {len(VEHICLES)}")
    print(f"Distance matrix shape: {DISTANCE_MATRIX.shape}")
    print(f"Total Demands:")
    for temp in ("frozen", "chilled", "ambient"):
        tot = sum(d[temp] for d in DEMANDS.values())
        print(f"  {temp}: {tot} units (capacity: 40)")
