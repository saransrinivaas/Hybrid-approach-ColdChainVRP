import time
import subprocess
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
import os
import sys
import json
import functools

app = Flask(__name__)
CORS(app)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON_1 = os.path.join(BACKEND_DIR, 'venv', 'Scripts', 'python.exe')
VENV_PYTHON_2 = os.path.join(BACKEND_DIR, '..', 'venv', 'Scripts', 'python.exe')
if os.path.exists(VENV_PYTHON_1):
    PYTHON_EXE = VENV_PYTHON_1
elif os.path.exists(VENV_PYTHON_2):
    PYTHON_EXE = VENV_PYTHON_2
else:
    PYTHON_EXE = sys.executable



COMPUTED_STATE = {
    "pipeline_easy":    None,
    "compare_cl_easy":  None,
    "compare_cl_tough": None,
    "compare_ort_easy": None,
    "compare_ort_tough": None,
    "compare_qaoa_easy":  None,
    "compare_qaoa_tough": None,
}

@app.route('/api/submit-results', methods=['POST'])
def submit_results():
    data = request.json
    res_type = request.args.get('type')
    if res_type == 'pipeline_easy':
        COMPUTED_STATE['pipeline_easy'] = data
    elif res_type == 'compare':
        # Store classical & ortools separately per scenario for instant retrieval
        for key in ('easy', 'tough'):
            sc = data.get(key, {})
            if sc.get('classical'):
                COMPUTED_STATE[f'compare_cl_{key}'] = sc['classical']
                # Invalidate classical cache so next load re-runs with fresh scenario
            if sc.get('ortools'):
                COMPUTED_STATE[f'compare_ort_{key}'] = sc['ortools']
        if data.get('easy', {}).get('qaoa'):
            COMPUTED_STATE['compare_qaoa_easy'] = data['easy']['qaoa']
        if data.get('tough', {}).get('qaoa'):
            COMPUTED_STATE['compare_qaoa_tough'] = data['tough']['qaoa']
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


# ── Comparison endpoints ──────────────────────────────────────────────────────

@app.route('/api/run-compare')
def run_compare():
    """
    Stream Classical-only comparison on both scenarios (fast, < 2 s).
    compare.py defaults to classical-only when no --with-qaoa flag is passed.
    """
    return stream_script('compare.py')

@app.route('/api/run-compare-full')
def run_compare_full():
    """Stream Classical + QAOA comparison on both scenarios (slow, 10-20 min)."""
    return stream_script('compare.py', extra_args=['--with-qaoa'])

@app.route('/api/compare-results')
def compare_results():
    """
    Instant read: return whatever is already in COMPUTED_STATE.
    Classical results are populated by /api/run-compare or /api/run-compare-full.
    QAOA results are populated by those same scripts or pre-seeded at startup.
    """
    cl_easy  = COMPUTED_STATE.get('compare_cl_easy')
    cl_tough = COMPUTED_STATE.get('compare_cl_tough')

    # If no classical results yet, run the fast classical solver inline (< 1 s each)
    if cl_easy is None or cl_tough is None:
        try:
            sys.path.insert(0, BACKEND_DIR)
            import importlib
            import scenario as _SC2
            try:
                import scenario_dynamic as _SC1
                importlib.reload(_SC1)
            except Exception:
                _SC1 = _SC2
            importlib.reload(_SC2)
            from classical_solver import solve_scenario
            cl_easy  = solve_scenario(_SC1)
            cl_tough = solve_scenario(_SC2)
            COMPUTED_STATE['compare_cl_easy']  = cl_easy
            COMPUTED_STATE['compare_cl_tough'] = cl_tough
        except Exception as e:
            import traceback
            return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

    payload = {
        "easy":  {"classical": cl_easy},
        "tough": {"classical": cl_tough},
    }

    # OR-Tools results (only present after a full run)
    if COMPUTED_STATE.get('compare_ort_easy'):
        payload["easy"]["ortools"]  = COMPUTED_STATE['compare_ort_easy']
    if COMPUTED_STATE.get('compare_ort_tough'):
        payload["tough"]["ortools"] = COMPUTED_STATE['compare_ort_tough']

    # QAOA / Hybrid results from volatile memory
    comp_qaoa_easy  = COMPUTED_STATE['compare_qaoa_easy']
    comp_qaoa_tough = COMPUTED_STATE['compare_qaoa_tough']
    pipe_qaoa       = COMPUTED_STATE['pipeline_easy']

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

    return jsonify(payload)



# ── Scenario metadata ─────────────────────────────────────────────────────────

@app.route('/api/scenarios')
def get_scenarios():
    """Return metadata for benchmark scenario."""
    try:
        sys.path.insert(0, BACKEND_DIR)
        import scenario as SC2
        try:
            import scenario_dynamic as SC1
        except ImportError:
            SC1 = SC2

        @functools.lru_cache(maxsize=1)
        def _cached_meta():
            def sc_meta(sc, key):
                total_demand = sum(sum(sc.DEMANDS[c["id"]].values()) for c in sc.CLINICS)
                tight = sum(
                    1 for cid, (o, cl) in sc.TIME_WINDOWS.items() if (cl - o) <= 4
                )
                cap = sc.VEHICLES[0]["compartments"]
                return {
                    "key":           key,
                    "num_clinics":   len(sc.CLINICS),
                    "num_vehicles":  len(sc.VEHICLES),
                    "total_demand":  total_demand,
                    "tight_windows": tight,
                    "capacity":      {t: cap[t]["capacity"] for t in cap},
                    "depot":         sc.DEPOT,
                    "clinics": [
                        {
                            "id":          c["id"],
                            "name":        c["name"],
                            "lat":         c["lat"],
                            "lon":         c["lon"],
                            "demand":      sc.DEMANDS[c["id"]],
                            "time_window": list(sc.TIME_WINDOWS[c["id"]]),
                        }
                        for c in sc.CLINICS
                    ],
                }
            return {
                "easy":  sc_meta(SC1, "easy"),
                "tough": sc_meta(SC2, "tough"),
            }

        return jsonify(_cached_meta())
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


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
