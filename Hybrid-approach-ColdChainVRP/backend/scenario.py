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
# CLINIC LOCATIONS (real Chennai GPS)
# ─────────────────────────────────────────
CLINICS = [
    {"id": 1,  "name": "Tambaram PHC",       "lat": 12.9249, "lon": 80.1000},
    {"id": 2,  "name": "Chromepet Clinic",   "lat": 12.9516, "lon": 80.1462},
    {"id": 3,  "name": "Pallavaram PHC",     "lat": 12.9675, "lon": 80.1491},
    {"id": 4,  "name": "Guindy Hospital",    "lat": 13.0067, "lon": 80.2206},
    {"id": 5,  "name": "Adyar Clinic",       "lat": 13.0012, "lon": 80.2565},
    {"id": 6,  "name": "Velachery PHC",      "lat": 12.9815, "lon": 80.2180},
    {"id": 7,  "name": "Porur Clinic",       "lat": 13.0350, "lon": 80.1567},
    {"id": 8,  "name": "Ambattur PHC",       "lat": 13.1143, "lon": 80.1548},
    {"id": 9,  "name": "Avadi Clinic",       "lat": 13.1067, "lon": 80.0950},
    {"id": 10, "name": "Poonamallee PHC",    "lat": 13.0467, "lon": 80.0956},
]

# ─────────────────────────────────────────
# VACCINE DEMAND PER CLINIC
# Each clinic needs 3 types of vaccines:
#   frozen  → mRNA vaccines      → -20°C compartment
#   chilled → protein subunit    → 2-8°C compartment
#   ambient → oral vaccines      → 15-25°C compartment
# Units are in doses (hundreds)
# ─────────────────────────────────────────
DEMANDS = {
    1:  {"frozen": 2, "chilled": 3, "ambient": 4},
    2:  {"frozen": 1, "chilled": 2, "ambient": 3},
    3:  {"frozen": 3, "chilled": 1, "ambient": 2},
    4:  {"frozen": 2, "chilled": 4, "ambient": 1},
    5:  {"frozen": 1, "chilled": 3, "ambient": 3},
    6:  {"frozen": 4, "chilled": 2, "ambient": 2},
    7:  {"frozen": 2, "chilled": 2, "ambient": 4},
    8:  {"frozen": 1, "chilled": 4, "ambient": 2},
    9:  {"frozen": 3, "chilled": 1, "ambient": 3},
    10: {"frozen": 2, "chilled": 3, "ambient": 1},
}

# ─────────────────────────────────────────
# VEHICLE FLEET
# 2 vehicles, each with 3 compartments
# capacity is in the same units as demand
# ─────────────────────────────────────────
VEHICLES = [
    {
        "id": "V1",
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 10},
            "chilled": {"temp_c":   4, "capacity": 12},
            "ambient": {"temp_c":  20, "capacity": 15},
        }
    },
    {
        "id": "V2",
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 10},
            "chilled": {"temp_c":   4, "capacity": 12},
            "ambient": {"temp_c":  20, "capacity": 15},
        }
    },
]

# ─────────────────────────────────────────
# SPOILAGE PARAMETERS
# alpha = decay rate per hour at that temp
# value = monetary value per unit (₹ hundreds)
# Higher alpha = spoils faster
# frozen has near-zero decay, ambient highest
# ─────────────────────────────────────────
SPOILAGE = {
    "frozen":  {"alpha": 0.001, "value": 500},
    "chilled": {"alpha": 0.010, "value": 200},
    "ambient": {"alpha": 0.050, "value":  50},
}

# ─────────────────────────────────────────
# TIME WINDOWS (clinic operating hours)
# Format: (open_hour, close_hour)
# ─────────────────────────────────────────
TIME_WINDOWS = {
    1:  (8, 18),
    2:  (8, 18),
    3:  (8, 18),
    4:  (8, 18),
    5:  (8, 18),
    6:  (8, 18),
    7:  (8, 18),
    8:  (8, 18),
    9:  (8, 18),
    10: (8, 18),
}

# ─────────────────────────────────────────
# SHARED PHYSICAL CONSTANTS
# Centralised here so qubo_builder.py and
# stitching_repair.py always stay in sync.
# ─────────────────────────────────────────
AVG_SPEED_KMH = 30  # average vehicle speed (km/h)

ENERGY_RATE = {
    "frozen":  0.050,   # kWh per hour per compartment
    "chilled": 0.030,
    "ambient": 0.010,
}

# ─────────────────────────────────────────
# DISTANCE MATRIX
# Haversine formula — real geographic distance
# between every pair of locations (km)
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

# ─────────────────────────────────────────
# QUICK SANITY CHECK
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("=== Scenario Loaded ===")
    print(f"Depot: {DEPOT['name']}")
    print(f"Clinics: {len(CLINICS)}")
    print(f"Vehicles: {len(VEHICLES)}")
    print(f"\nDistance matrix shape: {DISTANCE_MATRIX.shape}")
    print(f"Sample — Depot to Tambaram: {DISTANCE_MATRIX[0][1]:.2f} km")
    print(f"Sample — Tambaram to Adyar: {DISTANCE_MATRIX[1][5]:.2f} km")
    print("\nDemand check (Clinic 1):", DEMANDS[1])
    print("Time window (Clinic 1):", TIME_WINDOWS[1])
    print("\n✓ Scenario data ready")