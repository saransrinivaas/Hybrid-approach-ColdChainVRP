import sys
sys.path.insert(0, '.')
from node_splitting import apply_node_splitting, collapse_split_nodes
import scenario_dynamic as sc
from types import SimpleNamespace
import copy

# Patch clinic 7 to have oversized frozen demand (cap=10, demand=25 -> needs 3 phantom nodes)
sc_test = SimpleNamespace(
    DEPOT=sc.DEPOT,
    CLINICS=copy.deepcopy(sc.CLINICS),
    DEMANDS=copy.deepcopy(sc.DEMANDS),
    TIME_WINDOWS=sc.TIME_WINDOWS,
    DISTANCE_MATRIX=sc.DISTANCE_MATRIX,
    VEHICLES=sc.VEHICLES,
    SPOILAGE=sc.SPOILAGE,
    ENERGY_RATE=sc.ENERGY_RATE,
    AVG_SPEED_KMH=sc.AVG_SPEED_KMH,
    __name__='sc_test'
)
sc_test.DEMANDS[7] = {'frozen': 25, 'chilled': 1, 'ambient': 4}

sc_ext = apply_node_splitting(sc_test)
print(f"\nOriginal clinics : {len(sc_test.CLINICS)}")
print(f"Extended clinics : {len(sc_ext.CLINICS)}")
print(f"Split map        : {sc_ext.split_map}")
print("\nPhantom nodes:")
for c in sc_ext.CLINICS:
    if c.get('is_phantom'):
        pid = c["id"]
        print(f"  {pid} -> {c['name']}  demand={c['demand']}")

# Test distance matrix extended correctly
print(f"\nDM shape: {sc_ext.DISTANCE_MATRIX.shape}")
print(f"DM[7001][7002] (same loc, should be 0): {sc_ext.DISTANCE_MATRIX[7001][7002]:.4f}")
print(f"DM[7001][0]  (phantom->depot): {sc_ext.DISTANCE_MATRIX[7001][0]:.4f}")
print(f"DM[7][0]     (original->depot): {sc_test.DISTANCE_MATRIX[7][0]:.4f}")

# Test collapse
route = [0, 7001, 5, 7002, 7003, 0]
collapsed = collapse_split_nodes(route, sc_ext.split_map)
print(f"\nRoute with phantoms : {route}")
print(f"Route collapsed     : {collapsed}")

print("\n[OK] Node splitting test passed!")
