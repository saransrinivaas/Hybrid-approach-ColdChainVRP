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
# CLINIC LOCATIONS (30 Real Chennai GPS points)
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
    {"id": 11, "name": "Koyambedu PHC",      "lat": 13.0694, "lon": 80.1948},
    {"id": 12, "name": "T. Nagar Clinic",    "lat": 13.0418, "lon": 80.2337},
    {"id": 13, "name": "Mylapore PHC",       "lat": 13.0330, "lon": 80.2690},
    {"id": 14, "name": "Anna Nagar Clinic",  "lat": 13.0850, "lon": 80.2101},
    {"id": 15, "name": "Nungambakkam Clinic","lat": 13.0587, "lon": 80.2444},
    {"id": 16, "name": "Egmore PHC",         "lat": 13.0782, "lon": 80.2570},
    {"id": 17, "name": "Royapettah Hospital","lat": 13.0524, "lon": 80.2609},
    {"id": 18, "name": "Perambur PHC",       "lat": 13.1148, "lon": 80.2345},
    {"id": 19, "name": "Saidapet Clinic",    "lat": 13.0200, "lon": 80.2200},
    {"id": 20, "name": "Ekkaduthangal PHC",  "lat": 13.0180, "lon": 80.2040},
    {"id": 21, "name": "Ashok Nagar Clinic", "lat": 13.0350, "lon": 80.2120},
    {"id": 22, "name": "Vadapalani Clinic",  "lat": 13.0494, "lon": 80.2089},
    {"id": 23, "name": "Maduravoyal PHC",    "lat": 13.0689, "lon": 80.1601},
    {"id": 24, "name": "K.K. Nagar Clinic",  "lat": 13.0380, "lon": 80.1960},
    {"id": 25, "name": "Triplicane PHC",     "lat": 13.0587, "lon": 80.2757},
    {"id": 26, "name": "Alandur Clinic",     "lat": 13.0038, "lon": 80.2015},
    {"id": 27, "name": "St. Thomas Mount PHC","lat": 13.0055, "lon": 80.1982},
    {"id": 28, "name": "Pallikaranai PHC",   "lat": 12.9372, "lon": 80.2153},
    {"id": 29, "name": "Medavakkam Clinic",  "lat": 12.9191, "lon": 80.2195},
    {"id": 30, "name": "Sholinganallur PHC", "lat": 12.9010, "lon": 80.2270},
]

# ─────────────────────────────────────────
# DEMAND CONFIGURATION
# Balanced so that the sum of demands satisfies:
#   frozen: 42 <= 45 capacity
#   chilled: 39 <= 45 capacity
#   ambient: 42 <= 45 capacity
# ─────────────────────────────────────────
DEMANDS = {
    1:  {"frozen": 2, "chilled": 3, "ambient": 3},
    2:  {"frozen": 1, "chilled": 2, "ambient": 3},
    3:  {"frozen": 3, "chilled": 1, "ambient": 2},
    4:  {"frozen": 2, "chilled": 3, "ambient": 1},
    5:  {"frozen": 1, "chilled": 2, "ambient": 3},
    6:  {"frozen": 4, "chilled": 2, "ambient": 2},
    7:  {"frozen": 2, "chilled": 2, "ambient": 3},
    8:  {"frozen": 1, "chilled": 2, "ambient": 2},
    9:  {"frozen": 3, "chilled": 1, "ambient": 2},
    10: {"frozen": 2, "chilled": 3, "ambient": 1},
    11: {"frozen": 1, "chilled": 1, "ambient": 1},
    12: {"frozen": 2, "chilled": 0, "ambient": 1},
    13: {"frozen": 1, "chilled": 2, "ambient": 1},
    14: {"frozen": 1, "chilled": 1, "ambient": 2},
    15: {"frozen": 2, "chilled": 0, "ambient": 1},
    16: {"frozen": 0, "chilled": 2, "ambient": 1},
    17: {"frozen": 1, "chilled": 1, "ambient": 1},
    18: {"frozen": 1, "chilled": 1, "ambient": 0},
    19: {"frozen": 1, "chilled": 1, "ambient": 1},
    20: {"frozen": 1, "chilled": 0, "ambient": 2},
    21: {"frozen": 1, "chilled": 1, "ambient": 1},
    22: {"frozen": 0, "chilled": 1, "ambient": 1},
    23: {"frozen": 2, "chilled": 1, "ambient": 1},
    24: {"frozen": 1, "chilled": 1, "ambient": 1},
    25: {"frozen": 1, "chilled": 2, "ambient": 0},
    26: {"frozen": 1, "chilled": 1, "ambient": 1},
    27: {"frozen": 1, "chilled": 1, "ambient": 1},
    28: {"frozen": 1, "chilled": 0, "ambient": 1},
    29: {"frozen": 0, "chilled": 1, "ambient": 0},
    30: {"frozen": 1, "chilled": 1, "ambient": 1},
}

# ─────────────────────────────────────────
# VEHICLE FLEET (3 vehicles for 30 clinics)
# ─────────────────────────────────────────
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
    {
        "id": "V3",
        "compartments": {
            "frozen":  {"temp_c": -20, "capacity": 15},
            "chilled": {"temp_c":   4, "capacity": 15},
            "ambient": {"temp_c":  20, "capacity": 15},
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
    i: (8, 18) for i in range(1, 31)
}
# Challenging, non-uniform time windows to create scheduling friction
TIME_WINDOWS[2] = (8, 12)   # Chromepet Clinic
TIME_WINDOWS[5] = (13, 17)  # Adyar Clinic
TIME_WINDOWS[11] = (9, 13)  # Koyambedu PHC
TIME_WINDOWS[15] = (14, 18) # Nungambakkam Clinic
TIME_WINDOWS[20] = (10, 14) # Ekkaduthangal PHC
TIME_WINDOWS[25] = (12, 16) # Triplicane PHC

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
    print("=== Scenario 3 (Industry Stress Test) Loaded ===")
    print(f"Depot: {DEPOT['name']}")
    print(f"Clinics: {len(CLINICS)}")
    print(f"Vehicles: {len(VEHICLES)}")
    print(f"Distance matrix shape: {DISTANCE_MATRIX.shape}")
    print(f"Total Demands:")
    for temp in ("frozen", "chilled", "ambient"):
        tot = sum(d[temp] for d in DEMANDS.values())
        print(f"  {temp}: {tot} units (capacity: 45)")
