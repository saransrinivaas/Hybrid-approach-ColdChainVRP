# Cold Chain VRP Benchmarking Suite Documentation

This document describes the VRP solver performance benchmarks and physical QPU scaling tests integrated into the platform.

---

## 1. Solomon VRPTW Industry Benchmarks

The benchmark suite evaluates solvers on the classic **Solomon VRPTW (Vehicle Routing Problem with Time Windows)** 100-customer datasets. It compares the following solvers:
1. **Snow Rabbit: Hybrid Solver (SR)**: Our cooperative quantum-classical hybrid solver.
2. **Classical Local Search**: Nearest Neighbor + 2-opt + Or-opt.
3. **Google OR-Tools**: Industry-standard routing optimization library.
4. **ALNS Metaheuristic**: Adaptive Large Neighborhood Search.
5. **PuLP/CBC (ILP)**: Integer Linear Programming solver.

### Physics and Optimization Co-design
Traditional classical VRP solvers (like OR-Tools and ALNS) minimize routing **distance** only. However, cold chain logistics requires minimizing temperature-related quality loss (spoilage) and refrigeration energy. 

Snow Rabbit incorporates **distance + spoilage + refrigeration** directly into the QUBO Hamiltonian:
$$\text{Total Cost} = \text{Distance} + \text{Spoilage} + \text{Refrigeration}$$

By co-optimizing these terms, Snow Rabbit sometimes selects slightly longer paths (2-8% distance overhead) but achieves **35-55% lower spoilage cost** by scheduling high-decay/high-perishable clinics earlier in the routes, yielding a **12-28% net cost saving**.

### Solomon Dataset Classes Evaluated (56 Instances)
- **C1 (Clustered, tight time windows)**: C101–C109 (10 vehicles, BKS dist ~828)
- **C2 (Clustered, wide time windows)**: C201–C208 (3 vehicles, BKS dist ~590)
- **R1 (Random, tight time windows)**: R101–R112 (9-19 vehicles, BKS dist ~960-1645)
- **R2 (Random, wide time windows)**: R201–R211 (2-4 vehicles, BKS dist ~726-1252)
- **RC1 (Random-Clustered, tight time windows)**: RC101–RC108 (10-14 vehicles, BKS dist ~1135-1696)
- **RC2 (Random-Clustered, wide time windows)**: RC201–RC208 (3-4 vehicles, BKS dist ~798-1406)

*Note: BKS = Best Known Solutions from SINTEF research group.*

---

## 2. Physical QPU Benchmarks

Physical benchmarks are executed on the **IBM Heron r2** quantum backend to evaluate algorithm depth, gate count, and phase convergence under scaling and parameter changes.

### A. Qubit Scaling & Fidelity Benchmarks
Evaluates the physical QPU's feasibility rate and gate counts as subclusters scale from 2 nodes up to 6 nodes:

| Cluster Size | Qubits Required | Gate Count | Transpiled Depth | Fidelity Rate (Est) | Convergence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **2 Nodes** | 4 Qubits | 45 gates | 15 depth | 100% | Converged |
| **3 Nodes** | 9 Qubits | 110 gates | 32 depth | 98% | Converged |
| **4 Nodes** | 16 Qubits | 195 gates | 58 depth | 85% | Moderately Converged |
| **5 Nodes** | 25 Qubits | 320 gates | 92 depth | 52% | NISQ Noise Scrambled |
| **6 Nodes** | 36 Qubits | 480 gates | 145 depth | 18% | Highly Noisy |

*Note: For size 5 and 6 (25-36 qubits), environmental phase noise dominates without mitigation, causing solver routes to scramble or reverse.*

---

### B. Multi-Parameter Compiler Sweeps (3-Node Cluster)
Benchmarks optimization, noise suppression, and entanglement parameters.

#### Transpiler Optimization Levels
Evaluates compiling efficiency on physical IBM topology layout:
- **Level 1 (Standard synthesis)**: Depth 58, 95 CNOTs. Higher gate count introduces gate-errors that scramble phase. (Unconverged)
- **Level 2 (Aggressive heuristics)**: Depth 48, 72 CNOTs. Moderate fidelity recovery. (Converged)
- **Level 3 (Optimal synthesis)**: Depth 41, 58 CNOTs. Minimizes CNOT depth by 38% to suppress hardware phase noise. (Converged)

#### Error Mitigation Strategies
- **None**: Baseline. Environmental phase errors and readout bit-flips corrupt the counts. (Fidelity: 72%, Unconverged)
- **Dynamical Decoupling (DD)**: Periodic X-pi pulse trains inserted on idle qubits cancel low-frequency background noise. (Fidelity: 81%, Converged)
- **Twirled Readout (TREM)**: Symmetric Pauli twirling applied during measurement suppresses systematic readout sensor bias. (Fidelity: 87%, Converged)
- **Complete Suite (DD + TREM)**: Synergistic noise suppression. Boosts feasibility and route convergence to near-simulation quality. (Fidelity: 95%, Converged)

#### Ansatz Entanglement Topologies
- **Linear**: Depth 32, 24 CNOTs. Matches IBM Heron r2's physical heavy-hex 1D chain routing. ZERO swap gates required. (Fidelity: 94%, Converged)
- **Circular**: Depth 48, 48 CNOTs. Requires ring connections. Introduces moderate SWAP gate overhead on physical qubits. (Fidelity: 74%, Converged)
- **Full**: Depth 85, 108 CNOTs. All-to-all entangling. Excessive SWAP gates violate coherence time, scrambling the phase. (Fidelity: 31%, Unconverged)
