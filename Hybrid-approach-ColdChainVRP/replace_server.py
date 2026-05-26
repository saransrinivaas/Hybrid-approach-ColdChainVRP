import re

with open('backend/server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace from def _load_json_file(filename): down to the end of def get_scenarios():
start_str = "def _load_json_file(filename):"
end_str = "        return jsonify(_cached_meta())\n    except Exception as e:\n        import traceback\n        return jsonify({\"error\": str(e), \"trace\": traceback.format_exc()}), 500"

start_idx = content.find(start_str)
end_idx = content.find(end_str) + len(end_str)

new_code = """
COMPUTED_STATE = {
    "pipeline_easy": None,
    "compare_qaoa_easy": None
}

@app.route('/api/submit-results', methods=['POST'])
def submit_results():
    data = request.json
    res_type = request.args.get('type')
    if res_type == 'pipeline_easy':
        COMPUTED_STATE['pipeline_easy'] = data
    elif res_type == 'compare':
        if data.get('easy', {}).get('qaoa'):
            COMPUTED_STATE['compare_qaoa_easy'] = data['easy']['qaoa']
    return jsonify({"status": "ok"})

def stream_script(script_name, extra_args=None):
    \"\"\"Generic SSE streamer — runs any backend script and streams stdout.\"\"\"
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
                yield f"data: {json.dumps({'message': line.strip()})}\\n\\n"
                time.sleep(0.05)
        process.stdout.close()
        process.wait()
        yield f"data: {json.dumps({'status': 'DONE'})}\\n\\n"
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
    \"\"\"Run the full end-to-end Hybrid pipeline (user dynamic scenario) as a single SSE stream.\"\"\"
    return stream_script('pipeline.py')

@app.route('/api/run-pipeline-easy')
def run_pipeline_easy():
    \"\"\"Run the baseline Easy scenario (forces scenario.py).\"\"\"
    return stream_script('pipeline.py', extra_args=['--easy'])


# ── Clustering result (live, from scenario.py) ───────────────────────────────

@app.route('/api/clustering-result')
def clustering_result():
    \"\"\"
    Return the live clustering result derived from scenario.py.
    Runs clustering in-process so the frontend map always reflects
    the real backend output.
    \"\"\"
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
    \"\"\"Return results produced by the Easy Hybrid pipeline.\"\"\"
    if COMPUTED_STATE['pipeline_easy']:
        return jsonify(COMPUTED_STATE['pipeline_easy'])
    return jsonify({"error": "No results available — run the pipeline first"}), 404


# ── Comparison endpoints ──────────────────────────────────────────────────────

@app.route('/api/run-compare')
def run_compare():
    \"\"\"
    Stream Classical-only comparison on both scenarios (fast, < 2 s).
    compare.py defaults to classical-only when no --with-qaoa flag is passed.
    \"\"\"
    return stream_script('compare.py')

@app.route('/api/run-compare-full')
def run_compare_full():
    \"\"\"Stream Classical + QAOA comparison on both scenarios (slow, 10-20 min).\"\"\"
    return stream_script('compare.py', extra_args=['--with-qaoa'])

@app.route('/api/compare-results')
def compare_results():
    \"\"\"
    Compare view: Run solvers dynamically.
    \"\"\"
    try:
        sys.path.insert(0, BACKEND_DIR)
        import scenario as SC1
        from classical_solver import solve_scenario
        from ortools_solver import solve_scenario as solve_ortools

        payload = {"easy": {}}

        payload["easy"]["classical"] = solve_scenario(SC1)
        payload["easy"]["ortools"] = solve_ortools(SC1)

        # Retrieve QAOA from volatile memory if run
        comp_qaoa = COMPUTED_STATE['compare_qaoa_easy']
        pipe_qaoa = COMPUTED_STATE['pipeline_easy']

        if comp_qaoa and comp_qaoa.get('status') == 'ok':
            payload["easy"]["qaoa"] = comp_qaoa
        elif pipe_qaoa and not pipe_qaoa.get('error'):
            # Convert pipeline payload to compare payload shape
            q_data = pipe_qaoa.get('qaoa', pipe_qaoa)
            if q_data.get('routes'):
                payload["easy"]["qaoa"] = {
                    'solver': 'Hybrid pipeline (Scenarios)',
                    'routes': q_data['routes'],
                    'fleet_distance': q_data.get('fleet_distance'),
                    'fleet_spoilage': q_data.get('fleet_spoilage'),
                    'fleet_refrigeration': q_data.get('fleet_refrigeration', 0.0),
                    'fleet_total_cost': q_data.get('fleet_total_cost'),
                    'total_time': pipe_qaoa.get('total_time') if pipe_qaoa.get('total_time') is not None else 0.0,
                    'status': 'ok',
                    'note': 'Last hybrid run from the Scenarios tab. Not the same as "Classical + QAOA" in this tab.',
                }
            else:
                payload["easy"]["qaoa"] = {"status": "skipped", "note": "Run 'Classical + QAOA' or Pipeline to see results."}
        else:
            payload["easy"]["qaoa"] = {"status": "skipped", "note": "Run 'Classical + QAOA' or Pipeline to see results."}

        return jsonify(payload)
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


# ── Scenario metadata ─────────────────────────────────────────────────────────

@app.route('/api/scenarios')
def get_scenarios():
    \"\"\"Return metadata for benchmark scenario.\"\"\"
    try:
        sys.path.insert(0, BACKEND_DIR)
        import scenario  as SC1

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
            }

        return jsonify(_cached_meta())
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500
"""

new_content = content[:start_idx] + new_code.strip() + content[end_idx:]

with open('backend/server.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
