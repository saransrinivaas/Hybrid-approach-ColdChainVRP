# NISQ-Aware Hybrid Quantum-Classical Framework
## Cold-Chain Multi-Compartment Vehicle Routing Optimization

> *Every routing tool asks when vaccines arrive. Ours asks how much of their value survives the journey.*

---

## Table of Contents

1. [What This Project Does](#what-this-project-does)
2. [Why It Matters](#why-it-matters)
3. [The Gap in Existing Tools](#the-gap-in-existing-tools)
4. [System Architecture](#system-architecture)
5. [Novel Contributions](#novel-contributions)
6. [Technology Stack](#technology-stack)
7. [How to Run](#how-to-run)
8. [Project Structure](#project-structure)

---

## What This Project Does

This system finds optimal delivery routes for refrigerated vehicles carrying temperature-sensitive vaccines to clinics — minimizing not just travel distance but the actual monetary value lost to product spoilage during transit — while ensuring each vaccine type is assigned to the correct temperature compartment.

It does this using a **hybrid quantum-classical pipeline**:
- Classical algorithms handle vehicular clustering, trip assignment, and repair
- A quantum algorithm (QAOA) handles the core combinatorial optimization per sub-cluster
- The result is compared against three classical solvers: OR-Tools, Gurobi, and CPLEX

---

## Why It Matters

| Metric | Reality |
|---|---|
| Global cold-chain market | $280–375 billion |
| Vaccines arriving temperature-compromised | 25% |
| Global food lost to cold-chain failures | 14% |
| Refrigerated trucking profit margins | Under 2% |
| Annual savings for a 350-truck fleet from 3–5% routing improvement | $1–2.9 million |

Cold-chain logistics is where optimization failures have direct human consequences. Vaccines that arrive temperature-compromised cannot be used. The cost is not just monetary — it is lives.

---

## The Gap in Existing Tools

Every commercial and open-source routing tool in production today — OR-Tools, Gurobi, Descartes, PTV, Paragon — treats perishability the same way:

> *"Deliver before the deadline."*

None of them encode the actual physics of product degradation into the optimization objective. They do not know that a frozen vaccine loses value exponentially with time. They do not know that a slightly longer route delivering frozen vaccines first can save more money than the distance costs. They treat all cargo the same.

This project closes that gap with four specific contributions:

**Contribution 1 — Spoilage physics inside the quantum cost function**
The decay equation `cost = value × alpha × cumulative_time × quantity` is encoded directly as a term in the QUBO Hamiltonian. The optimizer minimizes actual monetary loss, not just distance.

**Contribution 2 — Cap-Bounded Multi-Trip Fleet Clustering**
Instead of assigning clinics to routes purely by distance or creating too many routes, this system uses a smart two-level classical planner:
* **Strict Fleet Capping**: Clinics are grouped strictly into the actual number of vehicles in the fleet (e.g., exactly 2 or 3). Clinics are grouped together only if they are close geographically AND have compatible delivery windows.
* **Multi-Compartment Load Balancing & Presorting**: The system dynamically balances total demand and scales capacity limits to allow multi-trip route optimization, coupled with heat-risk urgency queue presorting.
* **First-Fit Trip Splitting**: A greedy bin-packing algorithm automatically divides a vehicle's clinics into multiple trips, ensuring each individual trip strictly satisfies the frozen, chilled, and ambient capacity limits.

**Contribution 3 — Hybrid Local Search & Quality-Weighted Voting**
* **Quality-Weighted Consensus Voting**: Accumulates multiple samples from the QAOA optimizer, assigning higher confidence weights to pristine quantum runs ($3\times$) compared to classically repaired runs ($1\times$) to choose optimal base routes.
* **Intra-Route Or-Opt**: Repositioning individual clinics within a trip route to minimize transit times and heat spoilage.
* **Cross-Vehicle Or-Opt**: Relocating clinics across different vehicle routes and trips to balance overall load, avoid compartment limit violations, and optimize refrigeration costs.

**Contribution 4 — First bridge between quantum VRP and cold-chain logistics research**
Quantum VRP researchers and cold-chain logistics researchers publish in entirely different fields and have never connected. This project extends the Dash et al. 2025 hierarchical QAOA architecture into the multi-compartment cold-chain domain for the first time.

---

## System Architecture

```
┌─────────────────────────────────────────────┐
│              REACT FRONTEND                 │
│  Map View · Cost Charts · QAOA Controls     │
│  Before/After Routes · Live Solver Results  │
└──────────────────┬──────────────────────────┘
                   │ REST API (SSE streaming)
                   ▼
┌─────────────────────────────────────────────┐
│           PYTHON BACKEND (Flask)            │
│  /api/run-clustering                        │
└──────────┬──────────────────────────────────┘
           │
    ┌──────┴───────┐
    ▼              ▼
CLASSICAL      QUANTUM PIPELINE
SOLVERS
                Vehicular K-Means Clustering
OR-Tools            ↓
Gurobi         Capacity Repair (greedy)
CPLEX               ↓
               Trip Assignment (time windows)
                    ↓
               Overlapping C(n,3) Sub-clusters
                    ↓
               QUBO Construction (PyQUBO)
                    ↓
               QAOA Optimization (Qiskit)
                    ↓
               Classical Stitching
                    ↓
               Feasibility Repair
                    ↓
               Results + Comparison
```

---

## Novel Contributions

**Contribution 1 — Spoilage physics in quantum Hamiltonian**
No published quantum VRP paper has encoded temperature-dependent spoilage decay as a term in the cost function. The decay equation `value × alpha × cumulative_time × quantity` is encoded directly as a Hamiltonian term, making the optimizer minimize actual monetary loss rather than just distance.

**Contribution 2 — Cap-Bounded Multi-Trip Fleet Clustering**
A classical two-level hierarchical planner manages fleet constraints and subproblem routing:
* **Strict Fleet Capping**: The Level-1 geographic K-means algorithm groups clinics strictly into the actual fleet size (`n_clusters = n_vehicles`), repelling clinics with incompatible delivery windows.
* **Dynamic Load Repair & Urgency Presorting**: Vehicle clusters are balanced using a dynamically scaled relaxed capacity based on the scenario's average vehicle load, allowing a vehicle to carry a higher total demand over multiple trips. Clinic delivery queues are presorted based on time-window deadlines and thermal risk.
* **First-Fit Trip Splitting**: A greedy bin-packing algorithm dynamically splits each vehicle's cluster into multiple trips. Each individual trip is guaranteed to fit perfectly under the three compartment capacity limits (frozen, chilled, and ambient), and is then split into overlapping 3-node subproblems (Level 2) for the quantum solver.

**Contribution 3 — Hybrid Local Search & Quality-Weighted Voting**
* **Quality-Weighted Consensus Voting**: Accumulates multiple samples from the QAOA optimizer, assigning higher confidence weights to pristine quantum runs ($3\times$) compared to classically repaired runs ($1\times$) to choose optimal base routes.
* **Intra-Route Or-Opt**: Repositioning individual clinics within a trip route to minimize transit times and heat spoilage.
* **Cross-Vehicle Or-Opt**: Relocating clinics across different vehicle routes and trips to balance overall load, avoid compartment limit violations, and optimize refrigeration costs.

**Contribution 4 — First quantum-classical cold-chain bridge**
Extends the Dash et al. 2025 hierarchical QAOA architecture into multi-compartment cold-chain VRP — connecting two research communities that have never intersected.

---

## Technology Stack

```
Quantum
  Qiskit 2.4.0              circuit construction
  Qiskit Aer 0.17.2         27-qubit local simulation
  qiskit-optimization       QUBO to Ising conversion
  IBM Heron r2              48-qubit hardware validation

Formulation
  PyQUBO                    Hamiltonian construction
  NumPy 2.4.4               distance matrix and linear algebra
  NetworkX                  route graph operations

Classical Solvers
  OR-Tools                  primary classical baseline
  Gurobi                    optimal solutions (academic license)
  CPLEX                     secondary MILP comparison

Clustering
  scikit-learn              vehicular K-means

Backend
  Python 3.12               core pipeline
  Flask + CORS              REST API with SSE streaming

Frontend
  React 18 + Vite           interactive dashboard
  React-Leaflet             route maps
  Lucide React              iconography
```

---

## How to Run

### Prerequisites

Python 3.12, pip, Node.js

### Backend Setup

```bash
# Create and activate virtual environment
py -3.12 -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac/Linux

# Install dependencies
pip install "qiskit>=2.0" qiskit-aer qiskit-optimization pyqubo ortools scikit-learn networkx numpy flask flask-cors

# Run the clustering pipeline
cd backend
python -X utf8 clustering.py

# Start the Flask server
python server.py
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be available at `http://localhost:5173` with the backend API on port `5000`.

---

## Project Structure

```
cold_chain_vrp/
│
├── start.py                      launch script
│
├── backend/
│   ├── scenario.py               problem instance (depot, clinics, demands, distances)
│   ├── temp_preprocessing.py     capacity limits derived from vehicle specs
│   ├── clustering.py             vehicular clustering + overlapping sub-clusters
│   └── server.py                 Flask API with SSE streaming
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx               dashboard (scenario + clustering tabs)
│   │   ├── data.js               frontend scenario data
│   │   ├── index.css             global styles
│   │   └── main.jsx              entry point
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
└── venv/                         Python virtual environment
```

---

## Key References

- Dash, Banerjee & Panigrahi (2025), arXiv:2511.00506 — architecture template
- Azfar et al. (2025), arXiv:2505.01614 — hardware reality and penalty tuning
- Chen, Liu & Langevin (2019), C&OR 111:58–66 — classical cold-chain MCVRP baseline
- Palackal et al. (2024), Nature Sci Rep 14:24791 — qubit scaling analysis
- Liepold et al. (2026), EJOR 331:92–107 — latest classical MCVRP

---

*Built for Unisys Innovation Program 2026 · Python 3.12 · Qiskit 2.4.0 · IBM Heron r2*
