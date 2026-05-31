import sys
import os

# Set up paths
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BACKEND_DIR)

# Inject virtual environment site-packages
venv_paths = [
    os.path.join(BACKEND_DIR, '..', '..', 'venv', 'Lib', 'site-packages'),
    os.path.join(BACKEND_DIR, 'venv', 'Lib', 'site-packages'),
    os.path.join(BACKEND_DIR, '..', 'venv', 'Lib', 'site-packages')
]
for vp in venv_paths:
    vp_abs = os.path.abspath(vp)
    if os.path.exists(vp_abs) and vp_abs not in sys.path:
        sys.path.insert(0, vp_abs)

from qaoa_hardware_solver import solve_scenario_hardware_pipeline

try:
    print("Running solve_scenario_hardware_pipeline('tough3')...")
    res = solve_scenario_hardware_pipeline('tough3', verbose=True)
    print("Success! Scenario 3 results length:", len(res))
except Exception as e:
    import traceback
    print("FAILED with exception:")
    print(str(e))
    traceback.print_exc()
