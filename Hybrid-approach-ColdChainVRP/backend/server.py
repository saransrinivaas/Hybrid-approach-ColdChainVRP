import os
import sys
import time
import subprocess
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
import json


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# Prevent loading incompatible compiled C-extensions if user runs with system Python (e.g. Python 3.9) instead of venv (Python 3.12)
venv_cfg_path = os.path.abspath(os.path.join(BACKEND_DIR, '..', '..', 'venv', 'pyvenv.cfg'))
if not os.path.exists(venv_cfg_path):
    venv_cfg_path = os.path.abspath(os.path.join(BACKEND_DIR, '..', 'venv', 'pyvenv.cfg'))

venv_version = None
if os.path.exists(venv_cfg_path):
    try:
        with open(venv_cfg_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith('version'):
                    venv_version = line.split('=')[1].strip()
                    break
    except Exception:
        pass

if venv_version:
    running_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    venv_ver_parts = venv_version.split('.')
    if len(venv_ver_parts) >= 2:
        venv_major_minor = f"{venv_ver_parts[0]}.{venv_ver_parts[1]}"
        if running_ver != venv_major_minor:
            print(f"\n" + "=" * 80)
            print(f" [CRITICAL ERROR] PYTHON INTERPRETER MISMATCH DETECTED!")
            print(f" =" * 40)
            print(f" Running Interpreter : Python {sys.version.split()[0]} (from '{sys.executable}')")
            print(f" Target Environment  : Python {venv_version} (built in '.\\venv')")
            print(f"\n Injecting the Python 3.12 site-packages into a Python {running_ver} runtime is guaranteed")
            print(f" to crash compiled binary modules (such as NumPy C-extensions, OR-Tools, etc.)!")
            print(f"\n [FIX]: Please run the backend server using the virtual environment's python directly:")
            print(f"        .\\venv\\Scripts\\python.exe backend\\server.py")
            print(f"        (Or activate the virtual env first: .\\venv\\Scripts\\Activate.ps1)")
            print("=" * 80 + "\n")
            sys.exit(1)

# Inject virtual environment site-packages to support running server.py globally
venv_paths = [
    os.path.join(BACKEND_DIR, '..', '..', 'venv', 'Lib', 'site-packages'),
    os.path.join(BACKEND_DIR, 'venv', 'Lib', 'site-packages'),
    os.path.join(BACKEND_DIR, '..', 'venv', 'Lib', 'site-packages')
]
for vp in venv_paths:
    if os.path.exists(vp) and vp not in sys.path:
        sys.path.insert(0, vp)

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
CORS(app)

VENV_PYTHON_0 = os.path.join(BACKEND_DIR, '..', '..', 'venv', 'Scripts', 'python.exe')
VENV_PYTHON_1 = os.path.join(BACKEND_DIR, 'venv', 'Scripts', 'python.exe')
VENV_PYTHON_2 = os.path.join(BACKEND_DIR, '..', 'venv', 'Scripts', 'python.exe')
if os.path.exists(VENV_PYTHON_0):
    PYTHON_EXE = VENV_PYTHON_0
elif os.path.exists(VENV_PYTHON_1):
    PYTHON_EXE = VENV_PYTHON_1
elif os.path.exists(VENV_PYTHON_2):
    PYTHON_EXE = VENV_PYTHON_2
else:
    PYTHON_EXE = sys.executable



COMPUTED_STATE = {
    "pipeline_easy":    None,
    "pipeline_tough":   None,
    "pipeline_tough3":  None,
    "compare_cl_easy":  None,
    "compare_cl_tough": None,
    "compare_cl_tough3": None,
    "compare_ort_easy": None,
    "compare_ort_tough": None,
    "compare_ort_tough3": None,
    "compare_gurobi_easy": None,
    "compare_gurobi_tough": None,
    "compare_gurobi_tough3": None,
    "compare_pulp_easy": None,
    "compare_pulp_tough": None,
    "compare_pulp_tough3": None,
    "compare_alns_easy": None,
    "compare_alns_tough": None,
    "compare_alns_tough3": None,
    "compare_qaoa_easy":  None,
    "compare_qaoa_tough": None,
    "compare_qaoa_tough3": None,
}

def _save_computed_state_to_disk():
    payload = {
        "easy":  {
            "classical": COMPUTED_STATE.get('compare_cl_easy'),
            "ortools": COMPUTED_STATE.get('compare_ort_easy'),
            "gurobi": COMPUTED_STATE.get('compare_gurobi_easy'),
            "pulp_cbc": COMPUTED_STATE.get('compare_pulp_easy'),
            "alns": COMPUTED_STATE.get('compare_alns_easy'),
            "qaoa": COMPUTED_STATE.get('compare_qaoa_easy'),
        },
        "tough": {
            "classical": COMPUTED_STATE.get('compare_cl_tough'),
            "ortools": COMPUTED_STATE.get('compare_ort_tough'),
            "gurobi": COMPUTED_STATE.get('compare_gurobi_tough'),
            "pulp_cbc": COMPUTED_STATE.get('compare_pulp_tough'),
            "alns": COMPUTED_STATE.get('compare_alns_tough'),
            "qaoa": COMPUTED_STATE.get('compare_qaoa_tough'),
        },
        "tough3": {
            "classical": COMPUTED_STATE.get('compare_cl_tough3'),
            "ortools": COMPUTED_STATE.get('compare_ort_tough3'),
            "gurobi": COMPUTED_STATE.get('compare_gurobi_tough3'),
            "pulp_cbc": COMPUTED_STATE.get('compare_pulp_tough3'),
            "alns": COMPUTED_STATE.get('compare_alns_tough3'),
            "qaoa": COMPUTED_STATE.get('compare_qaoa_tough3'),
        },
    }
    
    for key in ('easy', 'tough', 'tough3'):
        if not payload[key]["qaoa"]:
            pipe_data = COMPUTED_STATE.get(f'pipeline_{key}')
            if pipe_data and not pipe_data.get('error'):
                q_data = pipe_data.get('qaoa', pipe_data)
                if q_data.get('routes'):
                    payload[key]["qaoa"] = {
                        'solver': 'Hybrid QAOA Pipeline',
                        'routes': q_data['routes'],
                        'fleet_distance':      q_data.get('fleet_distance'),
                        'fleet_spoilage':      q_data.get('fleet_spoilage'),
                        'fleet_refrigeration': q_data.get('fleet_refrigeration', 0.0),
                        'fleet_total_cost':    q_data.get('fleet_total_cost'),
                        'total_time': pipe_data.get('total_time', 0.0),
                        'status': 'ok',
                    }
                else:
                    payload[key]["qaoa"] = {"status": "skipped", "note": "Run the Live Pipeline to generate Hybrid QAOA results."}
            else:
                if key == 'easy':
                    payload[key]["qaoa"] = {"status": "skipped", "note": "Run the Live Pipeline to generate Hybrid QAOA results."}
                elif key == 'tough':
                    payload[key]["qaoa"] = {"status": "skipped", "note": "Run 'Classical + QAOA' to see results."}
                else:
                    payload[key]["qaoa"] = {"status": "skipped", "note": "Scenario 3 is too large for the Qiskit Quantum Simulator."}

    try:
        filepath = os.path.join(BACKEND_DIR, 'compare_results.json')
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        print(f"[DISK PERSISTENCE] Successfully saved comparison results to {filepath}")
    except Exception as e:
        print(f"[DISK PERSISTENCE] Error saving comparison results: {e}")

# Try to load existing compare results from disk on startup
compare_loaded_data = None
try:
    compare_file = os.path.join(BACKEND_DIR, 'compare_results.json')
    if os.path.exists(compare_file):
        with open(compare_file, 'r', encoding='utf-8') as f:
            compare_loaded_data = json.load(f)
            for key in ('easy', 'tough', 'tough3'):
                sc = compare_loaded_data.get(key, {})
                if sc:
                    if sc.get('classical'):
                        COMPUTED_STATE[f'compare_cl_{key}'] = sc['classical']
                    if sc.get('ortools'):
                        COMPUTED_STATE[f'compare_ort_{key}'] = sc['ortools']
                    if sc.get('gurobi'):
                        COMPUTED_STATE[f'compare_gurobi_{key}'] = sc['gurobi']
                    if sc.get('pulp_cbc'):
                        COMPUTED_STATE[f'compare_pulp_{key}'] = sc['pulp_cbc']
                    if sc.get('alns'):
                        COMPUTED_STATE[f'compare_alns_{key}'] = sc['alns']
                    if sc.get('qaoa'):
                        if sc['qaoa'].get('status') == 'ok':
                            COMPUTED_STATE[f'compare_qaoa_{key}'] = sc['qaoa']
            print("[INFO] Successfully loaded compare_results.json from disk on startup.")
except Exception as e:
    print(f"[WARN] Failed to load compare_results.json on startup: {e}")

# Try to load existing pipeline results from disk on startup
for key in ('easy', 'tough', 'tough3'):
    try:
        pipeline_file = os.path.join(BACKEND_DIR, f'pipeline_{key}.json')
        if os.path.exists(pipeline_file):
            with open(pipeline_file, 'r', encoding='utf-8') as f:
                COMPUTED_STATE[f'pipeline_{key}'] = json.load(f)
            print(f"[INFO] Successfully loaded pipeline_{key}.json from disk on startup.")
        elif compare_loaded_data and key in compare_loaded_data:
            # Reconstruct pipeline results from compare_results.json and persist to disk
            sc = compare_loaded_data[key]
            reconstructed = {
                "classical": sc.get("classical"),
                "qaoa": sc.get("qaoa")
            }
            if reconstructed["classical"] or reconstructed["qaoa"]:
                COMPUTED_STATE[f'pipeline_{key}'] = reconstructed
                with open(pipeline_file, 'w', encoding='utf-8') as f:
                    json.dump(reconstructed, f, indent=2)
                print(f"[INFO] Successfully auto-generated and saved pipeline_{key}.json from comparison data.")
    except Exception as e:
        print(f"[WARN] Failed to load/generate pipeline_{key}.json on startup: {e}")


def _save_pipeline_state_to_disk(key, data):
    try:
        filepath = os.path.join(BACKEND_DIR, f'pipeline_{key}.json')
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"[DISK PERSISTENCE] Successfully saved pipeline_{key} to {filepath}")
    except Exception as e:
        print(f"[DISK PERSISTENCE] Error saving pipeline_{key}: {e}")


@app.route('/api/submit-results', methods=['POST'])
def submit_results():
    data = request.json
    res_type = request.args.get('type')
    if res_type == 'pipeline_easy':
        COMPUTED_STATE['pipeline_easy'] = data
        _save_pipeline_state_to_disk('easy', data)
    elif res_type == 'pipeline_tough':
        COMPUTED_STATE['pipeline_tough'] = data
        _save_pipeline_state_to_disk('tough', data)
    elif res_type == 'pipeline_tough3':
        COMPUTED_STATE['pipeline_tough3'] = data
        _save_pipeline_state_to_disk('tough3', data)
    elif res_type == 'compare':
        # Store classical, ortools, gurobi, and pulp separately per scenario for instant retrieval
        for key in ('easy', 'tough', 'tough3'):
            sc = data.get(key)
            if sc:
                if sc.get('classical'):
                    COMPUTED_STATE[f'compare_cl_{key}'] = sc['classical']
                if sc.get('ortools'):
                    COMPUTED_STATE[f'compare_ort_{key}'] = sc['ortools']
                if sc.get('gurobi'):
                    COMPUTED_STATE[f'compare_gurobi_{key}'] = sc['gurobi']
                if sc.get('pulp_cbc'):
                    COMPUTED_STATE[f'compare_pulp_{key}'] = sc['pulp_cbc']
                if sc.get('alns'):
                    COMPUTED_STATE[f'compare_alns_{key}'] = sc['alns']
                if sc.get('qaoa'):
                    COMPUTED_STATE[f'compare_qaoa_{key}'] = sc['qaoa']
        _save_computed_state_to_disk()
    return jsonify({"status": "ok"})

def stream_script(script_name, extra_args=None):
    """Generic SSE streamer — runs any backend script and streams stdout."""
    def generate():
        cmd = [PYTHON_EXE, '-X', 'utf8', script_name] + (extra_args or [])
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            bufsize=1,
            cwd=BACKEND_DIR,
        )
        for line in iter(process.stdout.readline, ''):
            if line:
                yield f"data: {json.dumps({'message': line.strip()})}\n\n"
                time.sleep(0.05)
        process.stdout.close()
        process.wait()
        yield f"data: {json.dumps({'status': 'DONE'})}\n\n"
    return Response(generate(), mimetype='text/event-stream')


# ── Existing pipeline endpoints ──────────────────────────────────────────────

@app.route('/api/run-clustering')
def run_clustering():
    return stream_script('clustering.py')

@app.route('/api/run-qubo')
def run_qubo():
    return stream_script('qubo_builder.py')

@app.route('/api/run-qaoa')
def run_qaoa():
    return stream_script('qaoa_solver.py')

@app.route('/api/run-stitching')
def run_stitching():
    return stream_script('stitching_repair.py')

@app.route('/api/run-pipeline')
def run_pipeline():
    """Run the full end-to-end Hybrid pipeline (user dynamic scenario) as a single SSE stream."""
    return stream_script('pipeline.py')

@app.route('/api/run-pipeline-easy')
def run_pipeline_easy():
    """Run the baseline Easy scenario (forces scenario.py)."""
    return stream_script('pipeline.py', extra_args=['--easy'])

@app.route('/api/run-pipeline-tough3')
def run_pipeline_tough3():
    """Run the Scenario 3 stress test (forces scenario3.py)."""
    return stream_script('pipeline.py', extra_args=['--tough3'])


# ── Clustering result (live, from scenario.py) ───────────────────────────────

@app.route('/api/clustering-result')
def clustering_result():
    """
    Return the live clustering result derived from scenario.py.
    Runs clustering in-process so the frontend map always reflects
    the real backend output.
    """
    try:
        sys.path.insert(0, BACKEND_DIR)
        import importlib
        if 'scenario_dynamic' in sys.modules:
            importlib.reload(sys.modules['scenario_dynamic'])
        if 'scenario' in sys.modules:
            importlib.reload(sys.modules['scenario'])
        if 'temp_preprocessing' in sys.modules:
            importlib.reload(sys.modules['temp_preprocessing'])
        if 'clustering' in sys.modules:
            importlib.reload(sys.modules['clustering'])

        from clustering import build_clusters, generate_subclusters

        VEHICLE_COLORS = ['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#ef4444']
        vehicle_routes = build_clusters()
        result = []
        for idx, (vehicle_id, trips) in enumerate(vehicle_routes):
            all_scs = [sc for trip in trips for sc in generate_subclusters(trip)]
            solver  = "Classical" if all(len(sc) <= 2 for sc in all_scs) else "QAOA"
            result.append({
                "vehicleId": vehicle_id,
                "color":     VEHICLE_COLORS[idx % len(VEHICLE_COLORS)],
                "solver":    solver,
                "trips": [
                    {"clinics": trip, "subclusters": generate_subclusters(trip)}
                    for trip in trips
                ],
            })
        return jsonify(result)
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


# ── Pipeline results ──────────────────────────────────────────────────────────

@app.route('/api/results')
def get_results():
    """Return results produced by the Easy Hybrid pipeline."""
    if COMPUTED_STATE['pipeline_easy']:
        return jsonify(COMPUTED_STATE['pipeline_easy'])
    return jsonify({"error": "No results available — run the pipeline first"}), 404

@app.route('/api/results-tough')
def get_results_tough():
    """Return results produced by the Tough Hybrid pipeline."""
    if COMPUTED_STATE['pipeline_tough']:
        return jsonify(COMPUTED_STATE['pipeline_tough'])
    return jsonify({"error": "No results available — run the pipeline first"}), 404

@app.route('/api/results-tough3')
def get_results_tough3():
    """Return results produced by the Scenario 3 stress test."""
    if COMPUTED_STATE['pipeline_tough3']:
        return jsonify(COMPUTED_STATE['pipeline_tough3'])
    return jsonify({"error": "No results available — run the pipeline first"}), 404


# ── Comparison endpoints ──────────────────────────────────────────────────────

import threading as _threading
_ilp_thread_lock = _threading.Lock()
_ilp_running = False

class RelaxedScenarioWrapper:
    def __init__(self, original_sc):
        self._orig = original_sc
        self.__name__ = getattr(original_sc, "__name__", "scenario") + "_relaxed"
        
        # Expose all original fields
        self.DEPOT = original_sc.DEPOT
        self.CLINICS = original_sc.CLINICS
        self.DEMANDS = original_sc.DEMANDS
        self.DISTANCE_MATRIX = original_sc.DISTANCE_MATRIX
        self.SPOILAGE = original_sc.SPOILAGE
        self.ENERGY_RATE = original_sc.ENERGY_RATE
        self.AVG_SPEED_KMH = original_sc.AVG_SPEED_KMH
        
        # Relaxed time windows: all clinics get [0, 24] (meaning 0 to 1440 minutes)
        self.TIME_WINDOWS = {c["id"]: (0, 24) for c in original_sc.CLINICS}
        
        # Relaxed vehicles capacity: sum of all demands + safety margin for each compartment
        total_frozen = sum(original_sc.DEMANDS[c["id"]]["frozen"] for c in original_sc.CLINICS)
        total_chilled = sum(original_sc.DEMANDS[c["id"]]["chilled"] for c in original_sc.CLINICS)
        total_ambient = sum(original_sc.DEMANDS[c["id"]]["ambient"] for c in original_sc.CLINICS)
        
        self.VEHICLES = []
        for v in original_sc.VEHICLES:
            v_relaxed = {
                "id": v["id"],
                "compartments": {
                    "frozen": {"temp_c": -20, "capacity": int(max(v["compartments"]["frozen"]["capacity"], total_frozen + 10))},
                    "chilled": {"temp_c": 4, "capacity": int(max(v["compartments"]["chilled"]["capacity"], total_chilled + 10))},
                    "ambient": {"temp_c": 20, "capacity": int(max(v["compartments"]["ambient"]["capacity"], total_ambient + 10))},
                }
            }
            self.VEHICLES.append(v_relaxed)

def enrich_solver_result(result: dict, sc_module) -> dict:
    """
    Enriches the solver result with real physical constraint checks:
      - capacity_feasible: per vehicle and compartment
      - time_window_feasible: per vehicle based on operating windows
      - overall_feasible (feasible): capacity_feasible and time_window_feasible
    """
    if not result or not result.get("routes"):
        return result
        
    dm = sc_module.DISTANCE_MATRIX
    tw = sc_module.TIME_WINDOWS
    demands = sc_module.DEMANDS
    vehicles = {v["id"]: v for v in sc_module.VEHICLES}
    avg_speed = sc_module.AVG_SPEED_KMH
    
    fleet_feasible = True
    
    for vid, rdata in result["routes"].items():
        route = rdata.get("route", [])
        if not route:
            continue
            
        # 1. Capacity Check
        inner = [cid for cid in route if cid != 0]
        cap_check = {}
        veh_cap_feasible = True
        
        # Get vehicle info. Fallback to first vehicle if vid not found.
        v_info = vehicles.get(vid, sc_module.VEHICLES[0])
        
        for temp in ("frozen", "chilled", "ambient"):
            used = sum(demands[cid][temp] for cid in inner)
            cap = v_info["compartments"][temp]["capacity"]
            cap_check[temp] = {"used": used, "cap": cap}
            if used > cap:
                veh_cap_feasible = False
                
        # 2. Time Window Check
        veh_tw_feasible = True
        current_time = 8.0
        for i in range(1, len(route)):
            prev, curr = route[i-1], route[i]
            travel_time = dm[prev][curr] / avg_speed
            current_time += travel_time
            if curr != 0:
                open_h, close_h = tw[curr]
                if current_time > close_h:
                    veh_tw_feasible = False
                elif current_time < open_h:
                    current_time = open_h
                    
        rdata["capacity"] = cap_check
        # We enrich with a "feasible" boolean representing strict physical compliance
        rdata["feasible"] = veh_cap_feasible and veh_tw_feasible
        rdata["time_window_feasible"] = veh_tw_feasible
        
        if not (veh_cap_feasible and veh_tw_feasible):
            fleet_feasible = False
            
    result["feasible"] = fleet_feasible
    result["status"] = "ok"
    return result

def run_solver_with_relaxed_fallback(solver_solve_func, sc_module):
    """
    Runs a solver. If it fails (returns status="failed" or status="unavailable"),
    retries with a relaxed scenario to guarantee a route is produced.
    Then applies enrichment to evaluate the path against original constraints.
    """
    try:
        res = solver_solve_func(sc_module)
        if res and res.get("status") == "unavailable":
            return res
        if not res or res.get("status") == "failed" or not res.get("routes"):
            print(f"[RELAXATION] Solver failed or returned failed status. Attempting relaxed solve...")
            relaxed_sc = RelaxedScenarioWrapper(sc_module)
            res = solver_solve_func(relaxed_sc)
            if res and res.get("status") == "unavailable":
                return res
            res["status"] = "ok"
            res["was_relaxed"] = True
        return enrich_solver_result(res, sc_module)
    except Exception as e:
        print(f"[RELAXATION] Error in solver execution: {e}. Retrying relaxed...")
        try:
            relaxed_sc = RelaxedScenarioWrapper(sc_module)
            res = solver_solve_func(relaxed_sc)
            if res and res.get("status") == "unavailable":
                return res
            res["status"] = "ok"
            res["was_relaxed"] = True
            return enrich_solver_result(res, sc_module)
        except Exception as ex:
            print(f"[RELAXATION] Critical: Relaxed solve also failed: {ex}")
            return {"status": "failed", "routes": {}, "error": str(e)}

def _start_ilp_background():
    """Launch Gurobi + PuLP in a daemon thread so they never block API responses."""
    global _ilp_running
    with _ilp_thread_lock:
        if _ilp_running:
            return
        _ilp_running = True
    def _run():
        global _ilp_running
        try:
            sys.path.insert(0, BACKEND_DIR)
            import importlib, scenario as _SC2b, scenario3 as _SC3b
            try:
                import scenario_dynamic as _SC1b
                importlib.reload(_SC1b)
            except Exception:
                _SC1b = _SC2b
            importlib.reload(_SC2b)
            importlib.reload(_SC3b)
            import gurobi_solver as _gurobi, pulp_solver as _pulp
            for key, sc in [('easy', _SC1b), ('tough', _SC2b), ('tough3', _SC3b)]:
                if COMPUTED_STATE.get(f'compare_gurobi_{key}') is None:
                    COMPUTED_STATE[f'compare_gurobi_{key}'] = run_solver_with_relaxed_fallback(_gurobi.solve_scenario, sc)
                if COMPUTED_STATE.get(f'compare_pulp_{key}') is None:
                    COMPUTED_STATE[f'compare_pulp_{key}'] = run_solver_with_relaxed_fallback(_pulp.solve_scenario, sc)
        except Exception as e:
            print(f"[ILP Background] Error: {e}")
        finally:
            with _ilp_thread_lock:
                _ilp_running = False
    _threading.Thread(target=_run, daemon=True).start()


@app.route('/api/run-compare')
def run_compare():
    """Stream Classical-only comparison. Supports optional scenario query parameter."""
    scenario = request.args.get('scenario')
    args = []
    if scenario:
        args += ['--scenario', scenario]
    return stream_script('compare.py', extra_args=args)

@app.route('/api/run-compare-full')
def run_compare_full():
    """Stream Classical + QAOA comparison. Supports optional scenario query parameter."""
    scenario = request.args.get('scenario')
    args = ['--with-qaoa']
    if scenario:
        args += ['--scenario', scenario]
    return stream_script('compare.py', extra_args=args)

@app.route('/api/compare-results')
def compare_results():
    """
    Instant read: return whatever is already in COMPUTED_STATE.
    Fast solvers (Classical, OR-Tools, ALNS) run inline on first call (~2s).
    Slow ILP solvers (Gurobi, PuLP) run in a background thread and populate
    COMPUTED_STATE asynchronously — endpoint returns immediately with partials.
    """
    cl_easy   = COMPUTED_STATE.get('compare_cl_easy')
    cl_tough  = COMPUTED_STATE.get('compare_cl_tough')
    cl_tough3 = COMPUTED_STATE.get('compare_cl_tough3')

    # Determine if any fast solver for any scenario needs computing.
    # Each solver is checked INDEPENDENTLY so a silent failure in one doesn't
    # permanently block retries for others on subsequent requests.
    easy_pending  = (cl_easy is None
                     or COMPUTED_STATE.get('compare_ort_easy')  is None
                     or COMPUTED_STATE.get('compare_alns_easy') is None)
    tough_pending  = (cl_tough is None
                      or COMPUTED_STATE.get('compare_ort_tough')  is None
                      or COMPUTED_STATE.get('compare_alns_tough') is None)
    tough3_pending = (cl_tough3 is None
                      or COMPUTED_STATE.get('compare_ort_tough3')  is None
                      or COMPUTED_STATE.get('compare_alns_tough3') is None)

    if easy_pending or tough_pending or tough3_pending:
        try:
            sys.path.insert(0, BACKEND_DIR)
            import importlib
            import scenario as _SC2
            import scenario3 as _SC3
            try:
                import scenario_dynamic as _SC1
                importlib.reload(_SC1)
            except Exception:
                _SC1 = _SC2
            importlib.reload(_SC2)
            importlib.reload(_SC3)

            from classical_solver import solve_scenario as solve_classical
            import ortools_solver
            import alns_solver

            # ── Scenario 1 (custom dynamic) ──────────────────────────────────
            if cl_easy is None:
                try:
                    cl_easy = run_solver_with_relaxed_fallback(solve_classical, _SC1)
                    COMPUTED_STATE['compare_cl_easy'] = cl_easy
                except Exception as e:
                    print(f"[compare-results] Classical Easy failed: {e}")

            if COMPUTED_STATE.get('compare_ort_easy') is None:
                try:
                    COMPUTED_STATE['compare_ort_easy'] = run_solver_with_relaxed_fallback(ortools_solver.solve_scenario, _SC1)
                    print(f"[compare-results] OR-Tools Easy done: {COMPUTED_STATE['compare_ort_easy'].get('status')}")
                except Exception as e:
                    print(f"[compare-results] OR-Tools Easy failed: {e}")
                    import traceback; traceback.print_exc()

            if COMPUTED_STATE.get('compare_alns_easy') is None:
                try:
                    COMPUTED_STATE['compare_alns_easy'] = run_solver_with_relaxed_fallback(alns_solver.solve_scenario, _SC1)
                    print(f"[compare-results] ALNS Easy done: {COMPUTED_STATE['compare_alns_easy'].get('status')}")
                except Exception as e:
                    print(f"[compare-results] ALNS Easy failed: {e}")
                    import traceback; traceback.print_exc()

            # ── Scenario 2 ───────────────────────────────────────────────────
            if cl_tough is None:
                try:
                    cl_tough = run_solver_with_relaxed_fallback(solve_classical, _SC2)
                    COMPUTED_STATE['compare_cl_tough'] = cl_tough
                except Exception as e:
                    print(f"[compare-results] Classical Tough failed: {e}")

            if COMPUTED_STATE.get('compare_ort_tough') is None:
                try:
                    COMPUTED_STATE['compare_ort_tough'] = run_solver_with_relaxed_fallback(ortools_solver.solve_scenario, _SC2)
                except Exception as e:
                    print(f"[compare-results] OR-Tools Tough failed: {e}")

            if COMPUTED_STATE.get('compare_alns_tough') is None:
                try:
                    COMPUTED_STATE['compare_alns_tough'] = run_solver_with_relaxed_fallback(alns_solver.solve_scenario, _SC2)
                except Exception as e:
                    print(f"[compare-results] ALNS Tough failed: {e}")

            # ── Scenario 3 ───────────────────────────────────────────────────
            if cl_tough3 is None:
                try:
                    cl_tough3 = run_solver_with_relaxed_fallback(solve_classical, _SC3)
                    COMPUTED_STATE['compare_cl_tough3'] = cl_tough3
                except Exception as e:
                    print(f"[compare-results] Classical Tough3 failed: {e}")

            if COMPUTED_STATE.get('compare_ort_tough3') is None:
                try:
                    COMPUTED_STATE['compare_ort_tough3'] = run_solver_with_relaxed_fallback(ortools_solver.solve_scenario, _SC3)
                except Exception as e:
                    print(f"[compare-results] OR-Tools Tough3 failed: {e}")

            if COMPUTED_STATE.get('compare_alns_tough3') is None:
                try:
                    COMPUTED_STATE['compare_alns_tough3'] = run_solver_with_relaxed_fallback(alns_solver.solve_scenario, _SC3)
                except Exception as e:
                    print(f"[compare-results] ALNS Tough3 failed: {e}")

            # Save fast-solver results to disk and kick off ILP background thread
            _save_computed_state_to_disk()
            _start_ilp_background()

        except Exception as e:
            print(f"[compare-results] Inline evaluation error: {e}")
            import traceback; traceback.print_exc()

    payload = {
        "easy":  {
            "classical": cl_easy,
            "ortools": COMPUTED_STATE.get('compare_ort_easy'),
            "gurobi": COMPUTED_STATE.get('compare_gurobi_easy'),
            "pulp_cbc": COMPUTED_STATE.get('compare_pulp_easy'),
            "alns": COMPUTED_STATE.get('compare_alns_easy'),
        },
        "tough": {
            "classical": cl_tough,
            "ortools": COMPUTED_STATE.get('compare_ort_tough'),
            "gurobi": COMPUTED_STATE.get('compare_gurobi_tough'),
            "pulp_cbc": COMPUTED_STATE.get('compare_pulp_tough'),
            "alns": COMPUTED_STATE.get('compare_alns_tough'),
        },
        "tough3": {
            "classical": cl_tough3,
            "ortools": COMPUTED_STATE.get('compare_ort_tough3'),
            "gurobi": COMPUTED_STATE.get('compare_gurobi_tough3'),
            "pulp_cbc": COMPUTED_STATE.get('compare_pulp_tough3'),
            "alns": COMPUTED_STATE.get('compare_alns_tough3'),
        },
    }

    # QAOA / Hybrid results from volatile memory
    comp_qaoa_easy   = COMPUTED_STATE['compare_qaoa_easy']
    comp_qaoa_tough  = COMPUTED_STATE['compare_qaoa_tough']
    comp_qaoa_tough3 = COMPUTED_STATE['compare_qaoa_tough3']
    pipe_qaoa        = COMPUTED_STATE['pipeline_easy']

    try:
        import scenario_dynamic as _SC1_check
        importlib.reload(_SC1_check)
    except Exception:
        import scenario as _SC1_check

    if comp_qaoa_easy and comp_qaoa_easy.get('status') == 'ok':
        payload["easy"]["qaoa"] = comp_qaoa_easy
    elif pipe_qaoa and not pipe_qaoa.get('error'):
        q_data = pipe_qaoa.get('qaoa', pipe_qaoa)
        if q_data.get('routes'):
            qaoa_payload = {
                'solver': 'Hybrid QAOA Pipeline',
                'routes': q_data['routes'],
                'fleet_distance':      q_data.get('fleet_distance'),
                'fleet_spoilage':      q_data.get('fleet_spoilage'),
                'fleet_refrigeration': q_data.get('fleet_refrigeration', 0.0),
                'fleet_total_cost':    q_data.get('fleet_total_cost'),
                'total_time': pipe_qaoa.get('total_time', 0.0),
                'status': 'ok',
            }
            payload["easy"]["qaoa"] = enrich_solver_result(qaoa_payload, _SC1_check)
        else:
            payload["easy"]["qaoa"] = {"status": "skipped", "note": "Run the Live Pipeline to generate Hybrid QAOA results."}
    else:
        payload["easy"]["qaoa"] = {"status": "skipped", "note": "Run the Live Pipeline to generate Hybrid QAOA results."}

    if comp_qaoa_tough and comp_qaoa_tough.get('status') == 'ok':
        payload["tough"]["qaoa"] = comp_qaoa_tough
    else:
        payload["tough"]["qaoa"] = {"status": "skipped", "note": "Run 'Classical + QAOA' to see results."}

    if comp_qaoa_tough3 and comp_qaoa_tough3.get('status') == 'ok':
        payload["tough3"]["qaoa"] = comp_qaoa_tough3
    else:
        payload["tough3"]["qaoa"] = {"status": "skipped", "note": "Scenario 3 is too large for the Qiskit Quantum Simulator."}

    # Signal to the frontend whether ILP results are still computing
    payload["ilp_computing"] = _ilp_running

    return jsonify(payload)



# ── Scenario metadata ─────────────────────────────────────────────────────────

@app.route('/api/scenarios')
def get_scenarios():
    """Return metadata for benchmark scenario. Parses scenario files with ast — no numpy needed."""
    import ast

    def _parse_scenario_file(filepath):
        """Read a scenario .py file and extract CLINICS, DEPOT, DEMANDS, VEHICLES, TIME_WINDOWS via ast."""
        try:
            with open(filepath, encoding='utf-8') as fh:
                source = fh.read()
            tree = ast.parse(source)
            ns = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            try:
                                ns[target.id] = ast.literal_eval(node.value)
                            except Exception:
                                pass  # skip complex expressions (haversine, etc.)
            return ns
        except Exception:
            return {}

    def _sc_meta(ns, key):
        clinics  = ns.get('CLINICS', [])
        depot    = ns.get('DEPOT', {'id': 0, 'name': 'Depot', 'lat': 13.0827, 'lon': 80.2707})
        demands  = ns.get('DEMANDS', {})
        vehicles = ns.get('VEHICLES', [])
        tw       = ns.get('TIME_WINDOWS', {})

        # TIME_WINDOWS for scenario3 is built via dict-comprehension — not literal_eval-able;
        # fall back to uniform 8-18 if missing
        if not tw:
            tw = {c['id']: (8, 18) for c in clinics}

        total_demand = sum(sum(demands.get(c['id'], {}).values()) for c in clinics)
        tight = sum(1 for (o, cl) in tw.values() if (cl - o) <= 4)
        cap = vehicles[0]['compartments'] if vehicles else {}

        return {
            'key':           key,
            'num_clinics':   len(clinics),
            'num_vehicles':  len(vehicles),
            'total_demand':  total_demand,
            'tight_windows': tight,
            'capacity':      {t: cap[t]['capacity'] for t in cap} if cap else {},
            'depot':         depot,
            'clinics': [
                {
                    'id':          c['id'],
                    'name':        c['name'],
                    'lat':         float(c['lat']),
                    'lon':         float(c['lon']),
                    'demand':      demands.get(c['id'], {'frozen': 0, 'chilled': 0, 'ambient': 0}),
                    'time_window': list(tw.get(c['id'], (8, 18))),
                }
                for c in clinics
            ],
        }

    try:
        sc2_path  = os.path.join(BACKEND_DIR, 'scenario.py')
        sc3_path  = os.path.join(BACKEND_DIR, 'scenario3.py')
        sc1_path  = os.path.join(BACKEND_DIR, 'scenario_dynamic.py')

        ns2 = _parse_scenario_file(sc2_path)
        ns3 = _parse_scenario_file(sc3_path)
        ns1 = _parse_scenario_file(sc1_path) if os.path.exists(sc1_path) else ns2

        # scenario3 has TIME_WINDOWS as a dict comprehension (not literal_eval-able);
        # manually build it from the override lines we know
        if not ns3.get('TIME_WINDOWS'):
            tw3 = {i: (8, 18) for i in range(1, 31)}
            tw3.update({2:(8,12), 5:(13,17), 11:(9,13), 15:(14,18), 20:(10,14), 25:(12,16)})
            ns3['TIME_WINDOWS'] = tw3

        return jsonify({
            'easy':   _sc_meta(ns1, 'easy'),
            'tough':  _sc_meta(ns2, 'tough'),
            'tough3': _sc_meta(ns3, 'tough3'),
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


# ── Dynamic scenario configuration ────────────────────────────────────────────

@app.route('/api/configure', methods=['POST'])
def configure_scenario():
    """
    Accept a JSON configuration from the Input tab and write scenario_dynamic.py.
    The dynamic scenario mirrors the structure of scenario.py so all downstream
    scripts (clustering, qubo_builder, pipeline) can import it unchanged.
    Returns { status, scenario_file } immediately; frontend then calls /api/run-pipeline.
    """
    try:
        cfg = request.get_json(force=True)
        if not cfg:
            return jsonify({"error": "Empty body"}), 400

        clinics_cfg  = cfg.get("clinics",  [])
        vehicles_cfg = cfg.get("vehicles", [])
        vaccines_cfg = cfg.get("vaccines", [])
        num_vehicles = int(cfg.get("num_vehicles", len(vehicles_cfg)))

        # ── Resolve vaccine → compartment spoilage params ──
        # Build per-compartment alpha/value from whichever vaccines are selected.
        # If multiple vaccines share a compartment, use the one with highest alpha.
        spoilage = {"frozen": {"alpha": 0.001, "value": 500},
                    "chilled": {"alpha": 0.010, "value": 200},
                    "ambient": {"alpha": 0.050, "value": 50}}
        for v in vaccines_cfg:
            comp = v.get("compartment")
            if comp in spoilage:
                if v.get("alpha", 0) > spoilage[comp]["alpha"]:
                    spoilage[comp] = {"alpha": v["alpha"], "value": v.get("value", spoilage[comp]["value"])}

        # ── Pull static GPS coords from scenario.py without importing (avoids numpy dep) ──
        import ast as _ast
        _sc_path = os.path.join(BACKEND_DIR, 'scenario.py')
        _base_clinics_by_id = {}
        _base_depot = {"id": 0, "name": "Regional Vaccine Depot", "lat": 13.0827, "lon": 80.2707}
        try:
            with open(_sc_path, encoding='utf-8') as _fh:
                _tree = _ast.parse(_fh.read())
            for _node in _ast.walk(_tree):
                if isinstance(_node, _ast.Assign):
                    for _t in _node.targets:
                        if isinstance(_t, _ast.Name):
                            try:
                                if _t.id == 'CLINICS':
                                    _base_clinics_by_id = {c['id']: c for c in _ast.literal_eval(_node.value)}
                                elif _t.id == 'DEPOT':
                                    _base_depot = _ast.literal_eval(_node.value)
                            except Exception:
                                pass
        except Exception as _e:
            print(f"[configure] Could not parse scenario.py via ast: {_e}")
        base_clinics_by_id = _base_clinics_by_id
        base_depot = _base_depot

        # ── Build included clinic list ──
        included = [c for c in clinics_cfg if c.get("included", True)]
        if len(included) < 5:
            return jsonify({"error": "At least 5 clinics must be included"}), 400

        # ── Generate Python source ──
        lines = [
            "# Auto-generated by /api/configure — do not edit manually",
            "import math",
            "",
            "# Depot",
            f"DEPOT = {repr(base_depot)}",
            "",
            "# Clinics (user-selected subset)",
            "CLINICS = [",
        ]
        for c in included:
            base = base_clinics_by_id.get(c['id'], {})
            name = c.get('name') or base.get('name') or f"Clinic {c['id']}"
            lat = c.get('lat') or base.get('lat') or 13.0
            lon = c.get('lon') or base.get('lon') or 80.2
            lines.append(f"    {{\"id\": {c['id']}, \"name\": {repr(name)}, "
                         f"\"lat\": {lat}, \"lon\": {lon}}},")
        lines += [
            "]",
            "",
            "# Demands per clinic per compartment",
            "DEMANDS = {",
        ]
        for c in included:
            d = c.get("demand", {"frozen": 0, "chilled": 0, "ambient": 0})
            lines.append(f"    {c['id']}: {{\"frozen\": {d.get('frozen',0)}, "
                         f"\"chilled\": {d.get('chilled',0)}, \"ambient\": {d.get('ambient',0)}}},")
        lines += [
            "}",
            "",
            "# Time windows per clinic [open_hour, close_hour]",
            "TIME_WINDOWS = {",
        ]
        for c in included:
            tw = c.get("time_window", [8, 18])
            lines.append(f"    {c['id']}: ({tw[0]}, {tw[1]}),")
        lines += [
            "}",
            "",
            "# Fleet configuration",
            "VEHICLES = [",
        ]
        for v in vehicles_cfg:
            comp = v.get("compartments", {"frozen": 10, "chilled": 12, "ambient": 15})
            lines.append(f"    {{\"id\": {repr(v['id'])}, \"compartments\": {{"
                         f"\"frozen\": {{\"capacity\": {comp.get('frozen',10)}}}, "
                         f"\"chilled\": {{\"capacity\": {comp.get('chilled',12)}}}, "
                         f"\"ambient\": {{\"capacity\": {comp.get('ambient',15)}}}}}}},")
        lines += [
            "]",
            "",
            "# Shared Physical Constants",
            "AVG_SPEED_KMH = 30",
            "ENERGY_RATE = {",
            "    \"frozen\":  0.050,",
            "    \"chilled\": 0.030,",
            "    \"ambient\": 0.010,",
            "}",
            "",
            "# Spoilage parameters derived from vaccine selection",
            f"SPOILAGE = {repr(spoilage)}",
            "",
            "# Distance matrix calculated dynamically",
            "def haversine(lat1, lon1, lat2, lon2):",
            "    import numpy as np",
            "    R = 6371",
            "    phi1, phi2 = np.radians(lat1), np.radians(lat2)",
            "    dphi = np.radians(lat2 - lat1)",
            "    dlambda = np.radians(lon2 - lon1)",
            "    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2",
            "    return 2 * R * np.arcsin(np.sqrt(a))",
            "",
            "def build_distance_matrix():",
            "    import numpy as np",
            "    locations = [DEPOT] + CLINICS",
            "    max_id = max(loc['id'] for loc in locations)",
            "    matrix = np.zeros((max_id + 1, max_id + 1))",
            "    for i in range(len(locations)):",
            "        for j in range(len(locations)):",
            "            if i != j:",
            "                loc_i, loc_j = locations[i], locations[j]",
            "                matrix[loc_i['id']][loc_j['id']] = haversine(loc_i['lat'], loc_i['lon'], loc_j['lat'], loc_j['lon'])",
            "    return matrix",
            "",
            "DISTANCE_MATRIX = build_distance_matrix()",
        ]

        out_path = os.path.join(BACKEND_DIR, "scenario_dynamic.py")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        # Clear cached dynamic scenario comparison results to force re-evaluation on new configuration
        for k in ['compare_cl_easy', 'compare_ort_easy', 'compare_gurobi_easy', 'compare_pulp_easy', 'compare_alns_easy', 'compare_qaoa_easy', 'pipeline_easy']:
            COMPUTED_STATE[k] = None

        return jsonify({"status": "ok", "scenario_file": "scenario_dynamic.py",
                        "num_clinics": len(included), "num_vehicles": num_vehicles})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route('/api/recompute-easy', methods=['POST'])
def recompute_easy():
    """Force clear and recompute all solver results for the custom (easy/dynamic) scenario.
    Called by the frontend 'Refresh Solvers' button in Step 5 Comparison."""
    for k in ['compare_cl_easy', 'compare_ort_easy', 'compare_gurobi_easy',
              'compare_pulp_easy', 'compare_alns_easy']:
        COMPUTED_STATE[k] = None
    # The next call to /api/compare-results will recompute all of them automatically.
    return jsonify({"status": "ok", "message": "Easy scenario solver cache cleared. Fetch /api/compare-results to recompute."})


# ─────────────────────────────────────────
# HARDWARE ENDPOINTS
# ─────────────────────────────────────────
from qaoa_hardware_solver import (
    submit_hardware_job,
    retrieve_hardware_result,
    list_cached_runs,
    _load_jobs,
    run_qaoa_with_cache,
    solve_scenario_hardware_pipeline,
    run_quantum_scaling_test,
    run_qaoa_parameter_sweep
)

@app.route("/api/hardware/parameter-sweep", methods=["POST"])
def hardware_parameter_sweep():
    """Run a parameter sweep test across depths p and shots values."""
    try:
        results = run_qaoa_parameter_sweep()
        return jsonify({
            "status": "success",
            "results": results
        })
    except Exception as e:
        import traceback
        return jsonify({
            "status": "error",
            "message": str(e),
            "trace": traceback.format_exc()
        }), 500


@app.route("/api/hardware/scaling-test", methods=["POST"])
def hardware_scaling_test():
    """Run a Qubit Scaling & Fidelity Stress Test comparing noiseless vs physical hardware."""
    try:
        results = run_quantum_scaling_test()
        return jsonify({
            "status": "success",
            "results": results
        })
    except Exception as e:
        import traceback
        return jsonify({
            "status": "error",
            "message": str(e),
            "trace": traceback.format_exc()
        }), 500


@app.route("/api/hardware/run-scenario", methods=["POST"])
def hardware_run_scenario():
    """Run an entire scenario's VRP sub-clusters through simulated vs actual hardware comparison."""
    data = request.json or {}
    scenario_key = data.get("scenario", "easy")
    
    try:
        results = solve_scenario_hardware_pipeline(scenario_key, verbose=True)
        return jsonify({
            "status": "success",
            "scenario": scenario_key,
            "subclusters": results
        })
    except Exception as e:
        import traceback
        return jsonify({
            "status": "error",
            "message": str(e),
            "trace": traceback.format_exc()
        }), 500


@app.route("/api/hardware/submit", methods=["POST"])
def hardware_submit():
    """Submit one sub-cluster to IBM hardware."""
    data       = request.json or {}
    clinic_ids = data.get("clinic_ids", [1, 2, 3, 4])
    p_depth    = data.get("p_depth", 3)

    if not os.environ.get("IBM_QUANTUM_TOKEN") or "your_token_here" in os.environ.get("IBM_QUANTUM_TOKEN", ""):
        return jsonify({
            "status": "error",
            "message": "IBM_QUANTUM_TOKEN not configured or is placeholder"
        }), 400

    try:
        job_id = submit_hardware_job(clinic_ids, p_depth, verbose=True)
        return jsonify({
            "status":     "submitted",
            "job_id":     job_id,
            "clinic_ids": clinic_ids,
            "p_depth":    p_depth,
            "message":    f"Job submitted. Check quantum.ibm.com. Retrieve with job_id: {job_id}"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/hardware/retrieve/<job_id>", methods=["GET"])
def hardware_retrieve(job_id):
    """Retrieve a completed hardware job."""
    try:
        result = retrieve_hardware_result(job_id, verbose=False)
        if result is None:
            return jsonify({
                "status":  "pending",
                "job_id":  job_id,
                "message": "Job not complete yet"
            })
        return jsonify({"status": "done", "result": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/hardware/jobs", methods=["GET"])
def hardware_jobs():
    """List all submitted hardware jobs."""
    jobs = _load_jobs()
    return jsonify({"jobs": list(jobs.values())})


@app.route("/api/qaoa/cache", methods=["GET"])
def qaoa_cache():
    """List all cached QAOA runs (simulator + hardware)."""
    runs = list_cached_runs()
    return jsonify({"runs": runs, "count": len(runs)})


@app.route("/api/qaoa/cache", methods=["DELETE"])
def qaoa_cache_clear():
    """Clear all cached runs."""
    from qaoa_hardware_solver import CACHE_DIR
    cleared = 0
    if CACHE_DIR.exists():
        for p in CACHE_DIR.glob("*.json"):
            p.unlink()
            cleared += 1
    return jsonify({"status": "cleared", "count": cleared})


if __name__ == '__main__':

    port = int(os.environ.get('FLASK_PORT', 5000))
    print(f"Starting Flask Streaming Server on port {port}...")
    app.run(port=port, debug=True, threaded=True, use_reloader=False)
