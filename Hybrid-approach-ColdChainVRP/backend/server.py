import os
import sys
import time
import subprocess
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
import json


BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
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
                    COMPUTED_STATE[f'compare_gurobi_{key}'] = _gurobi.solve_scenario(sc)
                if COMPUTED_STATE.get(f'compare_pulp_{key}') is None:
                    COMPUTED_STATE[f'compare_pulp_{key}'] = _pulp.solve_scenario(sc)
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

    # If no fast-solver results yet, run them inline (classical + OR-Tools + ALNS are fast)
    if cl_easy is None or cl_tough is None or cl_tough3 is None:
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

            # Define inline functions safely inside
            from classical_solver import solve_scenario as solve_classical
            import ortools_solver
            import alns_solver

            # Evaluate Classical (Scenario 1)
            if cl_easy is None:
                try:
                    cl_easy = solve_classical(_SC1)
                    COMPUTED_STATE['compare_cl_easy'] = cl_easy
                except Exception as e:
                    print(f"[compare-results] Classical Easy failed: {e}")
            # Evaluate Classical (Scenario 2)
            if cl_tough is None:
                try:
                    cl_tough = solve_classical(_SC2)
                    COMPUTED_STATE['compare_cl_tough'] = cl_tough
                except Exception as e:
                    print(f"[compare-results] Classical Tough failed: {e}")
            # Evaluate Classical (Scenario 3)
            if cl_tough3 is None:
                try:
                    cl_tough3 = solve_classical(_SC3)
                    COMPUTED_STATE['compare_cl_tough3'] = cl_tough3
                except Exception as e:
                    print(f"[compare-results] Classical Tough3 failed: {e}")

            # Evaluate OR-Tools (Scenario 1)
            if COMPUTED_STATE.get('compare_ort_easy') is None:
                try:
                    COMPUTED_STATE['compare_ort_easy'] = ortools_solver.solve_scenario(_SC1)
                except Exception as e:
                    print(f"[compare-results] OR-Tools Easy failed: {e}")
            # Evaluate OR-Tools (Scenario 2)
            if COMPUTED_STATE.get('compare_ort_tough') is None:
                try:
                    COMPUTED_STATE['compare_ort_tough'] = ortools_solver.solve_scenario(_SC2)
                except Exception as e:
                    print(f"[compare-results] OR-Tools Tough failed: {e}")
            # Evaluate OR-Tools (Scenario 3)
            if COMPUTED_STATE.get('compare_ort_tough3') is None:
                try:
                    COMPUTED_STATE['compare_ort_tough3'] = ortools_solver.solve_scenario(_SC3)
                except Exception as e:
                    print(f"[compare-results] OR-Tools Tough3 failed: {e}")

            # Evaluate ALNS (Scenario 1)
            if COMPUTED_STATE.get('compare_alns_easy') is None:
                try:
                    COMPUTED_STATE['compare_alns_easy'] = alns_solver.solve_scenario(_SC1)
                except Exception as e:
                    print(f"[compare-results] ALNS Easy failed: {e}")
            # Evaluate ALNS (Scenario 2)
            if COMPUTED_STATE.get('compare_alns_tough') is None:
                try:
                    COMPUTED_STATE['compare_alns_tough'] = alns_solver.solve_scenario(_SC2)
                except Exception as e:
                    print(f"[compare-results] ALNS Tough failed: {e}")
            # Evaluate ALNS (Scenario 3)
            if COMPUTED_STATE.get('compare_alns_tough3') is None:
                try:
                    COMPUTED_STATE['compare_alns_tough3'] = alns_solver.solve_scenario(_SC3)
                except Exception as e:
                    print(f"[compare-results] ALNS Tough3 failed: {e}")

            # Auto-save computed fast-solver results to disk
            _save_computed_state_to_disk()

            # Kick off slow ILP solvers in background thread (non-blocking)
            _start_ilp_background()

        except Exception as e:
            print(f"[compare-results] Inline evaluation error: {e}")

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

    if comp_qaoa_easy and comp_qaoa_easy.get('status') == 'ok':
        payload["easy"]["qaoa"] = comp_qaoa_easy
    elif pipe_qaoa and not pipe_qaoa.get('error'):
        q_data = pipe_qaoa.get('qaoa', pipe_qaoa)
        if q_data.get('routes'):
            payload["easy"]["qaoa"] = {
                'solver': 'Hybrid QAOA Pipeline',
                'routes': q_data['routes'],
                'fleet_distance':      q_data.get('fleet_distance'),
                'fleet_spoilage':      q_data.get('fleet_spoilage'),
                'fleet_refrigeration': q_data.get('fleet_refrigeration', 0.0),
                'fleet_total_cost':    q_data.get('fleet_total_cost'),
                'total_time': pipe_qaoa.get('total_time', 0.0),
                'status': 'ok',
            }
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

        # ── Pull static GPS coords from scenario.py (never change) ──
        sys.path.insert(0, BACKEND_DIR)
        import scenario as _base_sc
        base_clinics_by_id = {c["id"]: c for c in _base_sc.CLINICS}
        base_depot = _base_sc.DEPOT

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

        return jsonify({"status": "ok", "scenario_file": "scenario_dynamic.py",
                        "num_clinics": len(included), "num_vehicles": num_vehicles})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 5000))
    print(f"Starting Flask Streaming Server on port {port}...")
    app.run(port=port, debug=True, threaded=True, use_reloader=False)
