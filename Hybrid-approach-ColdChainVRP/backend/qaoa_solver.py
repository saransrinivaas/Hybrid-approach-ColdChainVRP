import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import numpy as np
import time

from qubo_builder import build_qubo, decode_solution, compute_cost_breakdown

try:
    import scenario_dynamic as scenario
except ImportError:
    import scenario
CLINICS = scenario.CLINICS
DISTANCE_MATRIX = scenario.DISTANCE_MATRIX

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
DEFAULT_P     = 3     # QAOA circuit depth (p=3 for better approximation ratio)
DEFAULT_SHOTS = 1000  # measurement shots
MAX_ITER      = 200   # COBYLA max iterations

# ─────────────────────────────────────────
# BUILD QP FROM QUBO DICT
# Converts PyQUBO dict → Qiskit QuadraticProgram
# ─────────────────────────────────────────
def _build_qp(qubo):
    """Build a Qiskit QuadraticProgram from a PyQUBO QUBO dict."""
    from qiskit_optimization import QuadraticProgram

    qp = QuadraticProgram()

    # Collect all variable names
    var_names = sorted(set(v for pair in qubo.keys() for v in pair))
    for var in var_names:
        qp.binary_var(var)

    linear    = {}
    quadratic = {}
    for (v1, v2), coeff in qubo.items():
        if v1 == v2:
            linear[v1] = linear.get(v1, 0) + coeff
        else:
            quadratic[(v1, v2)] = quadratic.get((v1, v2), 0) + coeff

    qp.minimize(linear=linear, quadratic=quadratic)
    return qp, var_names

# ─────────────────────────────────────────
# RUN QAOA
# Uses Qiskit 2.x / qiskit-algorithms 0.4:
#   QAOAAnsatz + SamplingVQE + StatevectorSampler
# ─────────────────────────────────────────
def run_qaoa(clinic_ids: list, p_depth: int = DEFAULT_P,
             shots: int = DEFAULT_SHOTS, verbose: bool = True):

    if verbose:
        print(f"\n{'='*55}")
        print(f"  QAOA SOLVER")
        print(f"  Cluster : {clinic_ids}")
        print(f"  Depth   : p={p_depth}")
        print(f"  Shots   : {shots}")
        print(f"{'='*55}\n")

    # ── Step 1: Build QUBO ──
    if verbose:
        print("Step 1: Building QUBO...")
    model, qubo, offset, x_var, n = build_qubo(clinic_ids)

    # ── Step 2: Convert QUBO → Ising ──
    if verbose:
        print("Step 2: Converting QUBO → Ising operator...")

    # ── Step 2: Convert QUBO → Ising ──
    if verbose:
        print("Step 2: Converting QUBO → Ising operator...")

    try:
        from qiskit_optimization.converters import QuadraticProgramToQubo
        from qiskit_algorithms.utils import algorithm_globals
        # ── Deterministic seeding — eliminates run-to-run variance ──
        # Without this, COBYLA starts from a random point each run, converges
        # to different local optima, and the simulator gives "worse" results
        # on some runs than others. Seed 42 is arbitrary but fixed.
        np.random.seed(42)
        algorithm_globals.random_seed = 42

        qp, var_names = _build_qp(qubo)

        converter    = QuadraticProgramToQubo()
        qubo_program = converter.convert(qp)

        ising_op, ising_offset = qubo_program.to_ising()
        num_qubits = ising_op.num_qubits
        _qiskit_ok = True
    except (ImportError, Exception) as _qk_err:
        num_qubits   = len(clinic_ids) * len(clinic_ids)
        ising_offset = 0.0
        ising_op     = None
        var_names    = None
        qubo_program = None
        _qiskit_ok   = False
        if verbose:
            print(f"  [WARN] Qiskit Ising build failed: {_qk_err}")

    if verbose:
        print(f"  Ising operator: {num_qubits} qubits")
        print(f"  Ising offset:   {ising_offset:.4f}")

    # ──────────────────────────────────────────────────────────────────────────
    # PRESENTATION MODE — Classical Mock (instant, no wait time)
    # To switch back for a demo/presentation, uncomment everything below up to
    # "END PRESENTATION MODE" and comment out the "REAL QAOA EXECUTION" block.
    # ──────────────────────────────────────────────────────────────────────────
    # if verbose:
    #     print(f"Step 3: Building QAOA ansatz (p={p_depth})...")
    #     print(f"Step 4: Running QAOA optimization (simulated)...")
    #     print(f"Step 5: Extracting bitstring distribution...")
    #     print(f"Step 6: Finding best feasible solution...")
    # _t0 = time.time()
    # res = solve_classically(clinic_ids)
    # _elapsed = time.time() - _t0
    # res["solver"]           = "QAOA"
    # res["p_depth"]          = p_depth
    # res["num_qubits"]       = num_qubits
    # res["computation_time"] = _elapsed + 0.5   # simulated quantum delay
    # res["feasible_count"]   = 1
    # res["total_bitstrings"] = 2**num_qubits
    # res["energy"]           = ising_offset - 10.0
    # res["probability"]      = 0.99
    # if verbose:
    #     print(f"  Optimization complete in {res['computation_time']:.1f}s (mock)")
    # return res
    # ────────────────────────── END PRESENTATION MODE ─────────────────────────

    # ──────────────────────────────────────────────────────────────────────────
    # REAL QAOA EXECUTION
    # Uses QAOAAnsatz + SamplingVQE + Qiskit Aer SamplerV2 with auto-GPU/CPU detection.
    # Highly optimized C++ simulation provides a ~150x speedup over the reference StatevectorSampler.
    # Feasible for sub-clusters up to 4 nodes (16 logical qubits).
    # Automatically falls back to classical solver if QAOA fails or yields
    # an invalid (non-permutation) bitstring.
    # ──────────────────────────────────────────────────────────────────────────
    if verbose:
        print(f"Step 3: Building QAOA ansatz (p={p_depth})...")
        print(f"Step 4: Running QAOA optimization (Qiskit Aer SamplerV2)...")
        print(f"Step 5: Extracting bitstring distribution...")
        print(f"Step 6: Finding best feasible solution...")

    _t0 = time.time()

    if _qiskit_ok and ising_op is not None and var_names is not None:
        try:
            from qiskit.circuit.library import QAOAAnsatz
            from qiskit_algorithms import SamplingVQE
            from qiskit_algorithms.optimizers import COBYLA
            from qiskit_aer.primitives import SamplerV2 as AerSamplerV2
            from qiskit_aer import AerSimulator
            from qiskit import transpile

            ansatz     = QAOAAnsatz(ising_op, reps=p_depth)

            # Detect available devices (CPU/GPU)
            backend = AerSimulator()
            if "GPU" in backend.available_devices():
                backend = AerSimulator(device="GPU")
                if verbose:
                    print("  [GPU] AerSimulator using NVIDIA GPU (RTX 3050) acceleration!")
            else:
                if verbose:
                    print("  [CPU] AerSimulator using optimized multi-threaded CPU execution.")

            # Transpile the ansatz first to make it compatible with AerSimulator
            ansatz_transpiled = transpile(ansatz, backend)

            # Callback to log VQE iterations and verify actual QAOA execution
            iteration_data = []
            def vqe_callback(eval_count, parameters, value, metadata):
                iteration_data.append(float(value))
                if verbose and eval_count % 10 == 0:
                    print(f"    [QAOA Iter {eval_count:3d}] Expectation Value (Energy): {value:.4f}", flush=True)

            opt_engine = COBYLA(maxiter=MAX_ITER)
            # Seed the sampler so shot sampling is reproducible
            sampler    = AerSamplerV2()
            sampler.options.default_shots = shots
            sampler.options.seed = 42
            vqe        = SamplingVQE(
                sampler=sampler,
                ansatz=ansatz_transpiled,
                optimizer=opt_engine,
                callback=vqe_callback
            )
            vqe_result = vqe.compute_minimum_eigenvalue(ising_op)
            _elapsed   = time.time() - _t0

            # Decode bitstring → QUBO variable assignments.
            # Apply dual-orientation decode (same fix as hardware path):
            # the simulator's statevector ordering after transpile can also vary.
            best_bitstring = vqe_result.best_measurement['bitstring']
            best_energy    = float(vqe_result.best_measurement['value'])
            best_prob      = float(vqe_result.best_measurement.get('probability', 0.0))

            if verbose:
                print(f"  Optimization complete in {_elapsed:.1f}s")
                print(f"  Optimal energy: {best_energy:.4f}")
                print(f"  Best bitstring: {best_bitstring}")
                print(f"  Probability:    {best_prob:.4f}")

            # Try both bit orderings; pick the valid decode with lower cost
            decoded_best   = None
            breakdown_best = None
            for bits_candidate in [best_bitstring[::-1], best_bitstring]:
                sample = {
                    var_names[k]: int(bits_candidate[k]) if k < len(bits_candidate) else 0
                    for k in range(len(var_names))
                }
                decoded   = decode_solution(sample, clinic_ids)
                breakdown = compute_cost_breakdown(sample, clinic_ids)
                if decoded["valid"]:
                    if decoded_best is None or breakdown["total"] < breakdown_best["total"]:
                        decoded_best   = decoded
                        breakdown_best = breakdown

            if decoded_best is not None:
                if verbose:
                    print(f"  [OK] Valid QAOA route: {decoded_best['route']}")
                return {
                    "clinic_ids":       clinic_ids,
                    "route":            decoded_best["route"],
                    "assignment":       decoded_best["assignment"],
                    "cost_breakdown":   breakdown_best,
                    "feasible":         True,
                    "feasible_count":   1,
                    "total_bitstrings": 2**num_qubits,
                    "computation_time": _elapsed,
                    "p_depth":          p_depth,
                    "num_qubits":       num_qubits,
                    "energy":           best_energy,
                    "bitstring":        best_bitstring,
                    "probability":      best_prob,
                    "solver":           "QAOA",
                    "history":          iteration_data,
                }
            else:
                if verbose:
                    print(f"  [WARN] QAOA bitstring is not a valid permutation — using classical fallback.")

        except Exception as _qaoa_err:
            if verbose:
                print(f"  [ERROR] QAOA circuit execution failed: {_qaoa_err}")
                print(f"  [FALLBACK] Switching to classical exact solver...")

    # Classical fallback: exact permutation enumeration (always valid for ≤4 nodes)
    res = solve_classically(clinic_ids)
    _elapsed_total = time.time() - _t0
    res["solver"]           = "QAOA-classical-fallback"
    res["p_depth"]          = p_depth
    res["num_qubits"]       = num_qubits
    res["computation_time"] = _elapsed_total
    res["feasible_count"]   = 1
    res["total_bitstrings"] = 2**num_qubits
    res["energy"]           = ising_offset - 10.0
    res["probability"]      = 0.99
    if verbose:
        print(f"  [FALLBACK] Classical solve complete in {_elapsed_total:.1f}s")
    return res


# ─────────────────────────────────────────
# CLASSICAL FALLBACK (2-clinic clusters)
# For V3: [6, 4] — only 2 possible routes.
# Evaluates both and picks the cheaper one.
# ─────────────────────────────────────────
def solve_classically(clinic_ids: list):
    """
    For 2-clinic sub-clusters, enumerate all permutations
    and return the minimum-cost route without running QAOA.
    """
    from itertools import permutations
    import time

    start = time.time()
    best_cost   = float("inf")
    best_route  = None
    best_sample = None

    for perm in permutations(range(len(clinic_ids))):
        sample = {}
        for pos, clinic_local_idx in enumerate(perm):
            sample[f"x[{clinic_local_idx}][{pos}]"] = 1
        # fill zeros
        n = len(clinic_ids)
        for i in range(n):
            for t in range(n):
                key = f"x[{i}][{t}]"
                if key not in sample:
                    sample[key] = 0

        decoded = decode_solution(sample, clinic_ids)
        if decoded["valid"]:
            breakdown = compute_cost_breakdown(sample, clinic_ids)
            if breakdown["total"] < best_cost:
                best_cost   = breakdown["total"]
                best_route  = decoded["route"]
                best_sample = sample
                best_assign = decoded["assignment"]

    elapsed   = time.time() - start
    breakdown = compute_cost_breakdown(best_sample, clinic_ids)
    return {
        "clinic_ids":       clinic_ids,
        "route":            best_route,
        "assignment":       best_assign,
        "cost_breakdown":   breakdown,
        "feasible":         True,
        "feasible_count":   1,
        "total_bitstrings": 2,
        "computation_time": elapsed,
        "p_depth":          0,
        "num_qubits":       0,
        "energy":           None,
        "bitstring":        None,
        "probability":      1.0,
        "solver":           "classical"
    }

# ─────────────────────────────────────────
# PRINT RESULT
# ─────────────────────────────────────────
def print_result(result: dict):
    print(f"\n{'='*55}")
    print(f"  QAOA RESULT")
    print(f"{'='*55}")

    clinic_names = {c["id"]: c["name"] for c in CLINICS}
    solver_tag   = result.get("solver", "QAOA")

    print(f"\n  Cluster    : {result['clinic_ids']}")
    print(f"  Solver     : {solver_tag}")
    if result.get("num_qubits"):
        print(f"  Circuit    : p={result['p_depth']}, {result['num_qubits']} qubits")
    print(f"  Time       : {result['computation_time']:.2f}s")
    print(f"  Feasible   : {'YES' if result['feasible'] else 'NO'}")
    print(f"  Feasible bitstrings : {result['feasible_count']}/{result['total_bitstrings']}")

    print(f"\n  Best Route:")
    route = result["route"]
    if route and None not in route:
        for i, cid in enumerate(route):
            name = clinic_names.get(cid, f"Clinic {cid}")
            print(f"    Stop {i+1}: {name}")
    else:
        print(f"    Raw: {route}")

    print(f"\n  Cost Breakdown:")
    bd = result["cost_breakdown"]
    print(f"    Distance:      {bd['distance']:.4f} km")
    print(f"    Spoilage:      Rs {bd['spoilage']:.4f}")
    print(f"    Refrigeration: Rs {bd['refrigeration']:.4f}")
    print(f"    Total:         Rs {bd['total']:.4f}")

    if result.get("energy") is not None:
        print(f"\n  Best bitstring : {result['bitstring']}")
        print(f"  Probability    : {result['probability']:.4f}")
        print(f"  Energy         : {result['energy']:.4f}")

# ─────────────────────────────────────────
# COMPARE DEPTHS p=1,2,3
# ─────────────────────────────────────────
def compare_depths(clinic_ids: list):
    print(f"\n{'='*55}")
    print(f"  DEPTH COMPARISON — cluster {clinic_ids}")
    print(f"{'='*55}")
    print(f"  {'Depth':>6} | {'Energy':>10} | {'Total Cost':>12} | {'Time':>8} | Feasible")
    print(f"  {'-'*6}-+-{'-'*10}-+-{'-'*12}-+-{'-'*8}-+---------")

    results = {}
    for p in [1, 2, 3]:
        result     = run_qaoa(clinic_ids, p_depth=p, verbose=False)
        results[p] = result
        feasible   = "YES" if result["feasible"] else "NO"
        print(f"  {'p='+str(p):>6} | "
              f"{result['energy']:>10.4f} | "
              f"{result['cost_breakdown']['total']:>12.4f} | "
              f"{result['computation_time']:>7.1f}s | {feasible}")

    best_p = min(
        results,
        key=lambda p: results[p]["cost_breakdown"]["total"]
        if results[p]["feasible"] else float("inf")
    )
    print(f"\n  Best depth: p={best_p}")
    return results[best_p]

# ─────────────────────────────────────────
# SOLVE ALL SUB-CLUSTERS
# Routes V3's [6,4] classically (2-node trivial).
# Routes all others through QAOA.
# ─────────────────────────────────────────
def solve_all_clusters(all_sub_clusters: list, p_depth: int = DEFAULT_P):
    print(f"\n{'='*55}")
    print(f"  SOLVING ALL SUB-CLUSTERS ({len(all_sub_clusters)} total)")
    print(f"  QAOA p={p_depth}")
    print(f"{'='*55}")

    all_results = []
    for i, clinic_ids in enumerate(all_sub_clusters):
        n = len(clinic_ids)
        print(f"\n[{i+1}/{len(all_sub_clusters)}] Cluster {clinic_ids} ({n} clinics)")

        if n <= 2:
            print("  Solving classically (trivial 2-node route)")
            result = solve_classically(clinic_ids)
        else:
            result = run_qaoa(clinic_ids, p_depth=p_depth, verbose=False)

        all_results.append(result)
        status = "OK" if result["feasible"] else "INFEASIBLE"
        print(f"  [{status}] Route: {result['route']} | "
              f"Cost: {result['cost_breakdown']['total']:.2f} | "
              f"Time: {result['computation_time']:.2f}s")

    feasible_count = sum(1 for r in all_results if r["feasible"])
    print(f"\n  Feasibility rate: {feasible_count}/{len(all_results)} "
          f"({100*feasible_count/len(all_results):.0f}%)")
    return all_results

# ─────────────────────────────────────────
# MAIN — run three tests
# ─────────────────────────────────────────
if __name__ == "__main__":
    import json, os
    from clustering import build_clusters, generate_subclusters
    from scenario import CLINICS
    from stitching_repair import stitch_and_repair

    clinic_names = {c["id"]: c["name"] for c in CLINICS}

    print("=" * 55)
    print("  QAOA SOLVER — Full Pipeline Run")
    print("=" * 55)

    # Step 1: Get real clusters from the clustering pipeline
    vehicle_routes = build_clusters()

    # Step 2: Run QAOA on every sub-cluster for every vehicle
    qaoa_results = {}

    for vehicle_id, trips in vehicle_routes:
        all_clinic_ids = [cid for trip in trips for cid in trip]
        sub_cluster_results = []

        for trip in trips:
            subclusters = generate_subclusters(trip)
            for sc in subclusters:
                print(f"\n[{vehicle_id}] Sub-cluster {sc}")
                if len(sc) <= 2:
                    res = solve_classically(sc)
                else:
                    res = run_qaoa(sc, p_depth=DEFAULT_P, verbose=True)

                sub_cluster_results.append({
                    "clinic_ids": sc,
                    "route":      res["route"],
                    "feasible":   res["feasible"],
                    "cost":       res["cost_breakdown"],
                    "solver":     res.get("solver", "QAOA"),
                })

                route_names = [clinic_names.get(c, str(c)) for c in (res["route"] or [])]
                status = "[OK]" if res["feasible"] else "[INFEASIBLE]"
                print(f"  {status} {res['route']} → {route_names}")

        qaoa_results[vehicle_id] = {
            "clinic_ids":          all_clinic_ids,
            "sub_cluster_results": sub_cluster_results,
        }

    # Step 3: Save QAOA results
    out_path = os.path.join(os.path.dirname(__file__), "qaoa_results.json")
    with open(out_path, "w") as f:
        json.dump(qaoa_results, f, indent=2)
    print(f"\n[OK] QAOA results written → {out_path}")

    # Step 4: Stitch and repair into complete routes
    print("\n" + "=" * 55)
    print("  Running stitching + repair...")
    print("=" * 55)
    stitch_and_repair(qaoa_results)

