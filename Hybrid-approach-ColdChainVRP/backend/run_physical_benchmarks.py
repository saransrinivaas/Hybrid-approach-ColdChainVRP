import os
import sys
import time
from pathlib import Path

# Set up backend paths
BACKEND_DIR = Path(__file__).parent.resolve()
sys.path.append(str(BACKEND_DIR))

# Inject virtual environment site-packages
venv_paths = [
    BACKEND_DIR / "venv" / "Lib" / "site-packages",
    BACKEND_DIR.parent / "venv" / "Lib" / "site-packages"
]
for vp in venv_paths:
    if vp.exists() and str(vp) not in sys.path:
        sys.path.insert(0, str(vp))

# Load .env variables
_env_file = BACKEND_DIR / ".env"
if _env_file.exists():
    for line in _env_file.read_text().split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# Bypass cache by deleting the specific scaling runs from the .qaoa_cache folder
CACHE_DIR = BACKEND_DIR / ".qaoa_cache"
if CACHE_DIR.exists():
    import hashlib
    print("Clearing cached scaling runs to force fresh physical submissions...")
    cleared = 0
    # Clear cache files for scaling keys of sizes 2 to 6
    for n in [2, 3, 4, 5, 6]:
        clinic_ids = list(range(1, n + 1))
        # Remove simulator and hardware cache for these clinic lists
        for mode in ["simulator", "hardware"]:
            raw_key = f"{sorted(clinic_ids)}-p3-{mode}"
            key = hashlib.md5(raw_key.encode()).hexdigest()[:12]
            cache_file = CACHE_DIR / f"{key}.json"
            if cache_file.exists():
                cache_file.unlink()
                cleared += 1
    print(f"Cleared {cleared} cached benchmark lookups.")

from qaoa_hardware_solver import run_quantum_scaling_test, run_qaoa_parameter_sweep

print("\n" + "="*60)
print("  PHYSICAL QPU BENCHMARKS & COMPILES EXECUTION")
print("="*60)

# 1. Run Compiler sweeps on real physical backend topology
print("\n[1/2] Executing Multi-Parameter Compiler Sweeps on physical IBM topology...")
t0 = time.time()
try:
    sweeps_res = run_qaoa_parameter_sweep()
    print(f"Success! Sweeps completed in {time.time() - t0:.2f} seconds.")
    
    print("\n--- Optimization Level Benchmarks ---")
    for opt in sweeps_res["optimization_levels"]:
        print(f"  Level {opt['optimization_level']}: Depth = {opt['depth']} | CNOTs = {opt['cnot_count']} | Compile Time = {opt['compile_time']}s")
        print(f"    Note: {opt['note']}")
        
    print("\n--- Ansatz Entanglement Topologies ---")
    for top in sweeps_res["entanglement_topologies"]:
        print(f"  {top['topology']}: Depth = {top['gate_depth']} | CNOTs = {top['cnot_count']} | Fidelity = {top['fidelity']:.2f}")
        print(f"    Note: {top['note']}")
except Exception as e:
    print(f"Sweeps execution failed: {e}")

# 2. Submit Scaling Test Jobs physically to IBM Quantum
print("\n[2/2] Registering and submitting physical Qubit Scaling benchmarks...")
t0 = time.time()
try:
    scaling_res = run_quantum_scaling_test()
    print(f"Success! Scaling benchmarks registered/solved in {time.time() - t0:.2f} seconds.")
    print("\n--- Qubit Scaling & Fidelity Results ---")
    for run in scaling_res:
        print(f"  Clinics = {run['num_clinics']} ({run['qubits']} qubits) | Transpiled Depth = {run['depth']} | Gates = {run['gate_count']}")
        print(f"    Sim Prob: {run['sim_probability']*100:.1f}% | HW Prob: {run['hw_probability']*100:.1f}% | Convergence: {run['converged']}")
        print(f"    Fidelity: {run['fidelity']*100:.1f}%")
except Exception as e:
    print(f"Scaling test failed: {e}")

print("\n" + "="*60)
print("  QPU SUBMISSIONS & COMPILES COMPLETE")
print("="*60)
