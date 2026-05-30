# PROJECT TECHNICAL NOTES: HYBRID QUANTUM-CLASSICAL COLD-CHAIN VRP

This document provides a comprehensive academic and physical deep dive into the **Hybrid Quantum-Classical Vehicle Routing Problem (VRP) with Spoilage-Aware Logistics**. It outlines the mathematical formulations, physical equations, clustering mechanics, and stitching-repair details of the system.

---

## 1. Problem Formulation & Physics

In cold-chain vaccine logistics, delivery optimization is a multi-physics problem. Standard VRP formulations prioritize travel distance only. However, our proposed framework incorporates **thermodynamic cooling energy** and **biological product spoilage** directly into the optimization landscape.

### 1.1 Decision Variables
The routing for each sub-cluster of size $n$ is represented by a set of binary decision variables $x[i,t] \in \{0, 1\}$:
$$
x[i,t] = \begin{cases}
1, & \text{if clinic } i \text{ is visited at sequence position } t \\
0, & \text{otherwise}
\end{cases}
$$
where $i \in \{0, \dots, n-1\}$ and $t \in \{0, \dots, n-1\}$. This grid requires $n^2$ variables (mapped to $n^2$ physical qubits in the quantum computer).

---

## 2. The Global Hamiltonian ($\mathcal{H}_{\text{total}}$)

The problem is compiled into a **Quadratic Unconstrained Binary Optimization (QUBO)** Hamiltonian:
$$
\mathcal{H}_{\text{total}} = \mathcal{H}_{\text{distance}} + \mathcal{H}_{\text{spoilage}} + \mathcal{H}_{\text{refrigeration}} + \mathcal{H}_{\text{visit}} + \mathcal{H}_{\text{position}}
$$

### Term 1: Travel Distance Cost ($\mathcal{H}_{\text{distance}}$)
Minimizes the path length traversed by the truck between consecutive sequence stops $t$ and $t+1$:
$$
\mathcal{H}_{\text{distance}} = \sum_{i=0}^{n-1} \sum_{j \neq i} d(i,j) \sum_{t=0}^{n-2} x[i,t] \cdot x[j,t+1]
$$
* **$d(i,j)$**: The geographic Haversine distance between clinic $i$ and clinic $j$.
* **Qubit Coupling**: This creates quadratic couplers ($J_{ij} Z_i Z_j$) between sequence positions, representing the physical paths.

### Term 2: Spoilage Cost ($\mathcal{H}_{\text{spoilage}}$) — **NOVELTY**
Embeds product decay physics directly into the Hamiltonian. Rather than computing spoilage post-hoc, this term penalizes solutions where perishables sit in the truck for too long:
$$
\mathcal{H}_{\text{spoilage}} = \sum_{i=0}^{n-1} \sum_{t=0}^{n-1} \left( \sum_{c \in C} \text{Value}_c \cdot \alpha_c \cdot D_{i,c} \right) \cdot \bar{t}_{\text{arrival}}(t) \cdot x[i,t]
$$
* **$C = \{\text{frozen}, \text{chilled}, \text{ambient}\}$**: Vaccine temperature compartments.
* **$\text{Value}_c$**: Base monetary value per unit of vaccine in compartment $c$ (e.g., Frozen $\approx$ ₹500, Ambient $\approx$ ₹50).
* **$\alpha_c$**: Spoilage decay rate per hour. Frozen decays at $\alpha = 0.001$, Chilled at $\alpha = 0.010$, and Ambient at $\alpha = 0.050$.
* **$D_{i,c}$**: Demand of clinic $i$ for vaccines of type $c$.
* **$\bar{t}_{\text{arrival}}(t)$**: Pre-estimated arrival time at sequence slot $t$, computed based on average sub-cluster speeds to keep the term linear (order-independent):
$$
\bar{t}_{\text{arrival}}(t) = t \cdot \bar{t}_{\text{hop}} \quad \text{where} \quad \bar{t}_{\text{hop}} = \frac{\sum_{i \neq j} d(i,j)}{n(n-1) \cdot \text{Speed}}
$$
This linear term behaves as a local Z-magnetic field, which quantum hardware can optimize with zero overhead.

### Term 3: Refrigeration Energy ($\mathcal{H}_{\text{refrigeration}}$) — **NOVELTY**
Models the energy cost of maintaining active refrigeration across all compartments:
$$
\mathcal{H}_{\text{refrigeration}} = \sum_{i=0}^{n-1} \sum_{t=0}^{n-1} \left( \frac{\sum_{c \in C} \text{Power}_c \cdot T_{\text{duration}}}{n} \right) \cdot x[i,t]
$$
* **$\text{Power}_c$**: Electrical power drawing rate for compartment $c$ (kWh/h).
* **$T_{\text{duration}}$**: Estimated total trip transit duration based on sub-cluster geometry.
* Since refrigeration power runs continuously, this term distributes the energy cost equally per stop, letting the quantum optimizer balance energy expenditures against spatial layouts.

### Term 4: Visit-Once Constraint ($\mathcal{H}_{\text{visit}}$)
A mathematical penalty enforcing that each clinic $i$ is visited exactly once:
$$
\mathcal{H}_{\text{visit}} = M \cdot \sum_{i=0}^{n-1} \left( \sum_{t=0}^{n-1} x[i,t] - 1 \right)^2
$$
* **$M$**: Penalty scaling factor, configured as $2 \times \max(d(i,j))$ to ensure invalid states are energetically blocked.

### Term 5: Position-Once Constraint ($\mathcal{H}_{\text{position}}$)
Enforces that each sequence position $t$ in the route is occupied by exactly one clinic:
$$
\mathcal{H}_{\text{position}} = M \cdot \sum_{t=0}^{n-1} \left( \sum_{i=0}^{n-1} x[i,t] - 1 \right)^2
$$

---

## 3. The Clustering Pipeline

Because a global 10-node VRP requires $10^2 = 100$ qubits—which exceeds the capabilities of standard quantum hardware and simulators—we employ a **Clustering Pipeline**.

### Step 1: Temporal-Aware K-Means
Standard clustering only groups nodes spatially. Our framework uses a **composite distance metric** incorporating geographic distance and operating window penalties:
$$
D_{ij} = \text{Haversine}(i, j) \cdot (1 + \lambda \cdot \text{Penalty}_{ij})
$$
* **$\lambda = 0.6$**: Weight of the temporal penalty.
* **$\text{Penalty}_{ij}$**: Compares operating windows. If operating hours do not overlap, a high penalty is added:
$$
\text{Penalty}_{ij} = \text{GapPenalty} + (1 - \text{OverlapFraction})
$$
This groups clinics that can be served sequentially within their open hours.

### Step 2: Capacity Repair & Urgency Trip Sorting
Ensures that sum of clinic demands in a cluster does not exceed truck capacities. Demands are checked across Frozen, Chilled, and Ambient compartments. Tripping order is assigned by sorting clinics on composite urgency:
$$
\text{Urgency}_i = \sum_{c \in C} (\text{Value}_c \cdot \alpha_c \cdot D_{i,c}) + \frac{1}{\text{CloseTime}_i}
$$

### Step 3: Overlapping Sub-clusters (The Qubit Budget Bridge)
Large trips are divided into sub-clusters of size $K \le 4$ with a **2-node overlap**:
* A trip `[1, 2, 3, 4, 5, 6]` is divided into Sub-cluster A `[1, 2, 3, 4]` and Sub-cluster B `[3, 4, 5, 6]`.
* Each sub-cluster requires $4^2 = 16$ qubits, which can be solved via Qiskit QAOA simulation in seconds.

---

## 4. Stitching, Consensus & Post-Optimization

Once the simulated QAOA solver computes the optimal ordering for each sub-cluster, the sub-routes must be combined.

### Phase 1: QAOA Route Repair
If QAOA returns an infeasible sequence (e.g. duplicate nodes or missing visits due to local minima), a classical **cheapest insertion** heuristic repairs it locally.

### Phase 2: Quality-Weighted Consensus Voting
Overlapping nodes (e.g., nodes `3` and `4` in the example above) are ordered using majority consensus voting:
* Sub-cluster A votes on relative sequence.
* Sub-cluster B votes.
* Votes are weighted: pristine (unrepaired) QAOA solutions receive **3x weight**, while repaired solutions receive **1x weight**.

### Phase 3: Spoilage-Aware Or-opt (The Novelty Proof)
After stitching and cross-vehicle duplicate checks, we run a post-optimizer. Standard Or-opt only moves nodes if it shortens path distance. Our **spoilage-aware Or-opt** evaluates moves using:
$$
\Delta \text{Cost} = \Delta \text{Distance} + \Delta \text{Spoilage} < 0
$$
This prevents situations where a route is shortened by 1 km but delays a high-value frozen delivery by 2 hours (which would cause massive spoilage costs).

---

## 5. Summary of Quantum Contribution

By splitting a 10-node network into small sub-clusters, QAOA is applied in its physical "sweet spot" ($\le 16$ qubits), while classical heuristics manage vehicle capacities and boundary stitching. This is the essence of **Hybrid Quantum-Classical Optimization**, proving that QAOA can actively drive routing quality on modern NISQ-era quantum computing configurations.
