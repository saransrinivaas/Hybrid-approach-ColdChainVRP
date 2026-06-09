# Cold Chain VRP Backend API Documentation

This document describes the REST and Server-Sent Events (SSE) endpoints exposed by the Flask backend server.

---

## 1. Pipeline & Live Run Endpoints

### `GET /api/run-pipeline`
- **Method:** `GET` (Server-Sent Events)
- **Description:** Runs the end-to-end VRP solver pipeline (Clustering -> QUBO -> QAOA -> Stitching) and streams live console logs.
- **Query Parameters:**
  - `scenario`: Optional scenario name (e.g. `easy`, `tough`, `tough3`, `tough4`, `blr`, `hyd`, `stress`).

---

### Scenario-Specific Pipelines
- **Endpoints:**
  - `GET /api/run-pipeline-easy`
  - `GET /api/run-pipeline-tough3`
  - `GET /api/run-pipeline-scenario4`
  - `GET /api/run-pipeline-blr`
  - `GET /api/run-pipeline-hyd`
  - `GET /api/run-pipeline-stress`
- **Method:** `GET` (Server-Sent Events)
- **Description:** Direct shortcuts to stream and execute predefined scenario pipelines.

---

### Step-by-Step Live Stream Endpoints
- **Endpoints:**
  - `GET /api/run-clustering`: SSE stream running the Temporal-Aware Capacitated Clustering phase.
  - `GET /api/run-qubo`: SSE stream translating clustered groups into linear/quadratic Hamiltonians.
  - `GET /api/run-qaoa`: SSE stream solving the QUBO using classical/VQE/QAOA simulators.
  - `GET /api/run-stitching`: SSE stream running consensus voting, multi-vehicle repair, and 2-opt post-optimization.
- **Method:** `GET` (Server-Sent Events)
- **Description:** Used in the frontend "Live Run" pipeline interface to execute and stream logs for individual steps.

---

### `POST /api/submit-results`
- **Method:** `POST`
- **Description:** Caches the output from a step in memory/on disk.
- **Query Parameters:**
  - `type`: Step type (`pipeline_easy`, `pipeline_tough`, etc.)
- **Request Body:** JSON payload containing the step results.
- **Response:**
  ```json
  { "status": "ok" }
  ```

---

### `GET /api/clustering-result`
- **Method:** `GET`
- **Description:** Retrieves the latest computed clustering result.
- **Response:** JSON representation of the computed clusters.

---

## 2. Configuration & Comparison Endpoints

### `POST /api/configure`
- **Method:** `POST`
- **Description:** Saves a user-defined custom scenario configuration to `scenario_dynamic.py` and resets the comparison state.
- **Request Body:**
  ```json
  {
    "clinics": [
      { "id": 1, "name": "Clinic A", "lat": 12.92, "lon": 80.1, "demands": { "frozen": 2, "chilled": 1, "ambient": 3 } }
    ],
    "vehicles": 2,
    "vehicle_capacity": { "frozen": 10, "chilled": 12, "ambient": 15 }
  }
  ```
- **Response:**
  ```json
  {
    "status": "ok",
    "scenario_file": "scenario_dynamic.py",
    "num_clinics": 1,
    "num_vehicles": 2
  }
  ```

---

### `POST /api/recompute-easy`
- **Method:** `POST`
- **Description:** Clears the comparison solver cache (Classical, OR-Tools, ALNS, Pulp, Gurobi) for the custom (easy/dynamic) scenario.
- **Response:**
  ```json
  {
    "status": "ok",
    "message": "Easy scenario solver cache cleared. Fetch /api/compare-results to recompute."
  }
  ```

---

### `GET /api/scenarios`
- **Method:** `GET`
- **Description:** Returns the available scenarios list and the configuration status of each (e.g. clinic count, fleet details, and active parameters).

---

### `GET /api/compare-results`
- **Method:** `GET`
- **Description:** Retrieves pre-computed/cached comparison results for all solver algorithms across all scenarios. If a dynamic scenario has been cleared, it triggers background solving.

---

### Comparison Streams
- **Endpoints:**
  - `GET /api/run-compare`: Runs comparison solvers in background.
  - `GET /api/run-compare-full`: Runs comparison solvers including Gurobi.
- **Method:** `GET` (Server-Sent Events)

---

## 3. Map Endpoints

### `POST /api/map`
- **Method:** `POST`
- **Description:** Generates an interactive Folium/Leaflet map with coordinates, markers colored by cluster, and road routing polylines via Google Maps API (with fallback to Haversine straight lines if no API key).
- **Request Body:**
  ```json
  {
    "routes": {
      "V1": [0, 1, 2, 0]
    },
    "depot": { "lat": 13.0827, "lon": 80.2707 }
  }
  ```
- **Response:**
  ```json
  {
    "map_html": "<html>...</html>"
  }
  ```

---

## 4. Quantum Hardware & Cache Endpoints

### `POST /api/hardware/run-scenario`
- **Method:** `POST`
- **Description:** Runs an entire scenario's VRP sub-clusters through simulated vs actual QPU comparisons.
- **Request Body:**
  ```json
  {
    "scenario": "easy",
    "max_cluster_size": 3
  }
  ```
- **Response:**
  ```json
  {
    "status": "success",
    "scenario": "easy",
    "subclusters": [
      {
        "subcluster_id": "V1-T1-SC1",
        "clinics": [2, 1, 3],
        "converged": true,
        "simulator": { "route": [3, 2, 1], ... },
        "hardware": { "route": [3, 2, 1], ... }
      }
    ],
    "stitched_comparison": {
      "converged": true,
      "simulator": { "routes": { ... } },
      "hardware": { "routes": { ... } }
    }
  }
  ```

---

### `POST /api/hardware/parameter-sweep`
- **Method:** `POST`
- **Description:** Sweeps QAOA depths ($p=1, 2, 3$) and shots ($100, 250, 500$) for a 3-node VRP cluster, and evaluates optimization levels, error mitigation strategy parameters, and ansatz topologies.

---

### `POST /api/hardware/scaling-test`
- **Method:** `POST`
- **Description:** Runs qubit scaling test comparing 2 nodes (4 qubits) up to 6 nodes (36 qubits) between noiseless simulation vs real physical IBM hardware.

---

### `POST /api/hardware/submit`
- **Method:** `POST`
- **Description:** Submits a single subcluster's VRP QUBO to the physical IBM hardware.
- **Request Body:**
  ```json
  {
    "clinic_ids": [1, 2, 3],
    "p_depth": 3
  }
  ```
- **Response:**
  ```json
  {
    "status": "submitted",
    "job_id": "ibm_job_id_12345",
    "clinic_ids": [1, 2, 3],
    "p_depth": 3,
    "message": "Job submitted."
  }
  ```

---

### `POST /api/hardware/execute-once`
- **Method:** `POST`
- **Description:** Submits a subcluster to IBM QPU and polls/blocks until the execution results are returned.

---

### `GET /api/hardware/retrieve/<job_id>`
- **Method:** `GET`
- **Description:** Retrieves the results of a specific IBM job by ID.

---

### `GET /api/hardware/jobs`
- **Method:** `GET`
- **Description:** Returns lists of all registered jobs and their status (`SUBMITTED`, `PENDING`, `DONE`, etc.).

---

### Cache Management
- **Endpoints:**
  - `GET /api/qaoa/cache`: Lists all cached QAOA runs.
  - `DELETE /api/qaoa/cache`: Clears all simulator and hardware json files in `.qaoa_cache`.
- **Response (`DELETE`):**
  ```json
  {
    "status": "cleared",
    "count": 12
  }
  ```

---

## 5. Benchmarks Endpoints

### `GET /api/benchmarks/data`
- **Method:** `GET`
- **Description:** Serves Solomon VRPTW benchmark dataset comparison statistics (pre-calculated on 56 instances comparing CHO vs OR-Tools and Classical algorithms).
