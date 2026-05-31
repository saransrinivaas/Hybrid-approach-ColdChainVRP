import { useState, useEffect } from 'react';
import { BookOpen, ShieldAlert, Cpu, Award, Zap, Clock, Info, TrendingUp, Snowflake } from 'lucide-react';

const HAMILTONIAN_TERMS = {
  distance: {
    title: 'H_distance — Travel Distance Cost',
    math: '$$\\mathcal{H}_{\\text{distance}} = \\sum_{i=0}^{n-1} \\sum_{j \\neq i} d(i,j) \\sum_{t=0}^{n-2} x[i,t] \\cdot x[j,t+1]$$',
    physicalMeaning: 'Minimizes the total geographic route length across all clinics in the sub-cluster.',
    reason: 'Encourages consecutive stops to be physically close. By multiplying the geographic distance $d(i,j)$ by the active binary variables $x[i,t]$ and $x[j,t+1]$, it incurs a penalty proportional to the distance traveled if clinic $i$ is visited at stop $t$ and clinic $j$ is visited at stop $t+1$.',
    qubitImpact: 'Quadratic coupling between consecutive time steps $t$ and $t+1$. Requires $O(n^3)$ interactions in the Ising layout but is mapped to $O(n^2)$ couplers in our QUBO solver.',
    color: '#8fd6c2'
  },
  spoilage: {
    title: 'H_spoilage — Spoilage Cost (Novel)',
    math: '$$\\mathcal{H}_{\\text{spoilage}} = \\sum_{i=0}^{n-1} \\sum_{t=0}^{n-1} \\left( \\sum_{c \\in C} \\text{Value}_c \\cdot \\alpha_c \\cdot D_{i,c} \\right) \\cdot \\bar{t}_{\\text{arrival}}(t) \\cdot x[i,t]$$',
    physicalMeaning: 'Embeds vaccine spoilage physics directly into the optimization landscape.',
    reason: 'Ensures that clinics with high-value, highly perishable demand (like mRNA vaccines in the Frozen compartment) or tight delivery windows are scheduled earlier in the route. Position $t$ is mapped to an estimated arrival time $\\bar{t}_{\\text{arrival}}(t)$ (based on average sub-cluster speeds), so scheduling a clinic at a later position quadratically/linearly scales the spoilage cost penalty.',
    qubitImpact: 'Linear (local field) term. Easily handled by quantum hardware with zero extra coupling overhead, making it highly suitable for QAOA.',
    color: '#f472b6'
  },
  refrigeration: {
    title: 'H_refrigeration — Refrigeration Energy (Novel)',
    math: '$$\\mathcal{H}_{\\text{refrigeration}} = \\sum_{i=0}^{n-1} \\sum_{t=0}^{n-1} \\left( \\frac{\\sum_{c \\in C} \\text{Power}_c \\cdot T_{\\text{duration}}}{n} \\right) \\cdot x[i,t]$$',
    physicalMeaning: 'Accounts for the continuous active cooling energy needed for the refrigerator compartments.',
    reason: 'Distributed equally across all visit slots. It ensures the quantum optimizer evaluates the energy consumption overhead of the cooling units (frozen, chilled, ambient compartments) during the transit window. By charging this cost proportionally per stop, the optimizer seeks routes that balance refrigeration power against travel duration.',
    qubitImpact: 'Linear term. Provides a constant shift of the energy spectrum to ensure exact cost balancing without adding coupling constraints.',
    color: '#d8bd7f'
  },
  visit: {
    title: 'H_visit — Visit Once Constraint',
    math: '$$\\mathcal{H}_{\\text{visit}} = M \\cdot \\sum_{i=0}^{n-1} \\left( \\sum_{t=0}^{n-1} x[i,t] - 1 \\right)^2$$',
    physicalMeaning: 'Enforces that each clinic in the sub-cluster is visited exactly once.',
    reason: 'Strict physical requirement. If a clinic is visited zero times, or visited multiple times, the term $( \\sum x[i,t] - 1 )$ becomes non-zero, squaring the penalty and multiplying it by a large coefficient $M = 2 \\times \\max(d(i,j))$. This penalizes invalid route permutations heavily, forcing the QAOA statevector to converge on mathematically valid tours.',
    qubitImpact: 'Fully connected quadratic terms. Creates heavy qubit coupling that represents the main bottleneck for NISQ quantum simulators.',
    color: '#cfcfcf'
  },
  position: {
    title: 'H_position — Position Once Constraint',
    math: '$$\\mathcal{H}_{\\text{position}} = M \\cdot \\sum_{t=0}^{n-1} \\left( \\sum_{i=0}^{n-1} x[i,t] - 1 \\right)^2$$',
    physicalMeaning: 'Enforces that each stop index in the route is occupied by exactly one clinic.',
    reason: 'Strict scheduling requirement. Prevents the vehicle from visiting two clinics at the same time slot $t$, or leaving a time slot empty. Like the visit-once constraint, it squares any deviations and applies the large penalty scaling $M$ to ensure only valid mathematical route permutations are energetically stable.',
    qubitImpact: 'Fully connected quadratic terms. Couples qubits across clinics for a given time step $t$.',
    color: '#caa5d8'
  }
};

const PIPELINE_STEPS = [
  {
    step: '1',
    title: 'Temporal-Aware Clustering',
    desc: 'Agglomerative clustering using composite distance $D = \\text{geo} \\times (1 + \\lambda \\cdot \\text{temporal\\_penalty})$. Weight $\\lambda = 0.6$.',
    details: 'Groups clinics by both physical proximity and operating time windows. If two clinics have non-overlapping open hours, they are penalized and separated into different vehicular clusters.'
  },
  {
    step: '2',
    title: 'Capacity Repair & Assignment',
    desc: 'Greedy checks and dynamic capacity relaxation over 50 iterations.',
    details: 'Balances clinic demands across vehicles. If a cluster exceeds the maximum truck compartment capacities (Frozen, Chilled, Ambient), nodes are reassigned or split into distinct trips.'
  },
  {
    step: '3',
    title: 'Overlapping Sub-clustering',
    desc: 'Generates sub-clusters of size $K \\le 4$ nodes with an overlap of 2 nodes.',
    details: 'This is the key hybrid design feature! Instead of routing a large 10-node cluster on a quantum computer (which requires $10^2 = 100$ qubits, unsimulatable locally), we subdivide it into overlapping sub-clusters of size 3 and 4, requiring only $3^2=9$ and $4^2=16$ qubits, which can be easily simulated using real Qiskit QAOA.'
  },
  {
    step: '4',
    title: 'Qiskit QAOA Run (Actual Qiskit)',
    desc: 'Runs actual Qiskit QAOA statevector sampler ($p=3$ depth) on each sub-cluster QUBO.',
    details: 'Runs parameter optimization (COBYLA) to find the optimal scheduling bitstrings on a simulated quantum backend, capturing real quantum convergence metrics and feasible state distributions.'
  },
  {
    step: '5',
    title: 'Stitching & Consensus Vote',
    desc: 'Merges overlapping sub-routes into global vehicular routes.',
    details: 'Uses quality-weighted majority consensus voting. Since sub-clusters overlap by 2 nodes, they vote on the relative ordering of nodes (e.g. if Sub-cluster A prefers stop Order 1-2-3 and Sub-cluster B prefers 2-3-4, consensus confirms the order 1-2-3-4).'
  },
  {
    step: '6',
    title: 'Post-Optimization (2-opt & Or-opt)',
    desc: 'Runs classical 2-opt and spoilage-aware Or-opt operators.',
    details: 'Performs final local path modifications. Reverses subsegments (2-opt) and shifts node sequences (Or-opt) using the integrated spoilage-aware evaluation model, ensuring the global route is refined to the absolute lowest combined cost.'
  }
];

export default function ExplainerTab({ activeTab }) {
  const [selectedTerm, setSelectedTerm] = useState('spoilage');
  const [selectedStep, setSelectedStep] = useState('3');

  // Trigger MathJax typesetting when tab changes to explainer or term changes
  useEffect(() => {
    if (activeTab === 'explainer' && window.MathJax && window.MathJax.typesetPromise) {
      // Delay slightly to allow the DOM to render
      setTimeout(() => {
        window.MathJax.typesetPromise().catch((err) => console.log('MathJax typesetting error:', err));
      }, 50);
    }
  }, [activeTab, selectedTerm, selectedStep]);

  // Qubit scaling chart variables
  const sizes = [2, 3, 4, 5, 6, 8, 10];
  const directQubits = sizes.map(s => s * s);
  const subClusterQubits = sizes.map(s => s <= 4 ? s * s : 16); // capped at 16 qubits (max sub-cluster size 4)

  return (
    <div className="content-grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
      
      {/* Main Section */}
      <div className="main-content" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', height: '100%', justifyContent: 'space-between' }}>
        
        {/* Title Panel */}
        <div className="card glass-panel" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '0.5rem' }}>
            <Snowflake size={24} style={{ color: '#ffffff' }} />
            <h2 style={{ margin: 0 }}>
              Cryo Route Engine Explainer
            </h2>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', lineHeight: '1.6' }}>
            This tab provides a deep mathematical walkthrough of the <strong>Cryo Hybrid Optimiser</strong> for the Cold-Chain Vehicle Routing Problem (VRP). 
            By decomposing large geographic networks into computationally safe quantum sub-clusters, the Cryo Hybrid Optimiser leverages real-world physics (vaccine spoilage and active cooling power) directly inside the optimization Hamiltonian. We completely bypass the catastrophic memory limits of classical statevector simulation by generating targeted 10-node sub-problems that securely fit within modern hardware thresholds. This hybrid architecture guarantees that the quantum hardware execution perfectly matches theoretical parity, while the robust classical edge-stitching algorithm manages global fleet capacity and inter-vehicle logic. Explore the interactive Hamiltonian formulas and the end-to-end execution pipeline below to understand precisely how we achieve hardware-ready quantum parity today.
          </p>
        </div>

        {/* Hamiltonian Explorer */}
        <div className="card glass-panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Zap size={18} style={{ color: '#ffffff' }} />
            Interactive Hamiltonian Term Explorer
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginBottom: '1rem' }}>
            The objective function is expressed as a Quadratic Unconstrained Binary Optimization (QUBO) Hamiltonian. Click on any term to explore its mathematical formula, functional purpose, and quantum hardware implications.
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1.25rem' }}>
            {Object.keys(HAMILTONIAN_TERMS).map((key) => {
              const term = HAMILTONIAN_TERMS[key];
              const isSelected = selectedTerm === key;
              return (
                <button
                  key={key}
                  onClick={() => setSelectedTerm(key)}
                  style={{
                    padding: '0.5rem 0.8rem',
                    background: isSelected ? '#ec489925' : 'rgba(255,255,255,0.03)',
                    color: isSelected ? '#ec4899' : 'var(--text)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    transition: 'all 0.2s',
                    borderLeft: '3px solid #ec4899'
                  }}
                >
                  {key.toUpperCase()}
                </button>
              );
            })}
          </div>

          {/* Hamiltonian Formula Display */}
          <div
            style={{
              padding: '1.25rem',
              background: 'rgba(0,0,0,0.2)',
              borderRadius: '8px',
              border: '1px solid rgba(255,255,255,0.05)',
              marginBottom: '1rem',
              textAlign: 'center',
              overflowX: 'auto'
            }}
          >
            <div style={{ fontSize: '1.1rem', color: '#ec4899' }}>
              {HAMILTONIAN_TERMS[selectedTerm].math}
            </div>
          </div>

          {/* Details Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', fontSize: '0.88rem' }}>
            <div style={{ padding: '0.8rem', background: 'rgba(255,255,255,0.01)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.03)' }}>
              <div style={{ fontWeight: 600, color: 'var(--text)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Info size={14} style={{ color: '#ffffff' }} />
                Functional Objective
              </div>
              <div style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                {HAMILTONIAN_TERMS[selectedTerm].reason}
              </div>
            </div>
            <div style={{ padding: '0.8rem', background: 'rgba(255,255,255,0.01)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.03)' }}>
              <div style={{ fontWeight: 600, color: 'var(--text)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Cpu size={14} style={{ color: '#ffffff' }} />
                Quantum Gate Mapping
              </div>
              <div style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                {HAMILTONIAN_TERMS[selectedTerm].qubitImpact}
              </div>
            </div>
          </div>
        </div>

        {/* Hybrid Pipeline Workflow */}
        <div className="card glass-panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Cpu size={18} style={{ color: '#ffffff' }} />
            Interactive End-to-End Pipeline Walkthrough
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginBottom: '1rem' }}>
            Click on any pipeline step to see how geographic routing tasks are mapped, solved on the Qiskit simulator, and merged into the final post-optimized routes.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '0.4rem', marginBottom: '1.25rem' }}>
            {PIPELINE_STEPS.map((s) => {
              const isSelected = selectedStep === s.step;
              return (
                <button
                  key={s.step}
                  onClick={() => setSelectedStep(s.step)}
                  style={{
                    padding: '0.6rem 0.4rem',
                    background: isSelected ? '#f97316' : 'rgba(255,255,255,0.03)',
                    color: isSelected ? '#ffffff' : 'var(--text)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '0.75rem',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '0.2rem',
                    fontWeight: 600,
                    transition: 'all 0.2s'
                  }}
                >
                  <span style={{ fontSize: '0.68rem', opacity: 0.6 }}>STEP {s.step}</span>
                  <span style={{ textAlign: 'center', fontSize: '0.73rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', width: '100%' }}>
                    {s.title.split(' ')[0]}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Selected Step Description */}
          <div
            style={{
              padding: '1rem 1.25rem',
              background: 'rgba(255,255,255,0.02)',
              borderRadius: '8px',
              border: '1px solid rgba(255,255,255,0.05)',
              borderLeft: '4px solid #f97316'
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.95rem', color: '#ffffff', marginBottom: '0.4rem' }}>
              Step {selectedStep}: {PIPELINE_STEPS.find(s => s.step === selectedStep).title}
            </div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: '1.5', marginBottom: '0.5rem' }}>
              {PIPELINE_STEPS.find(s => s.step === selectedStep).details}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--text-muted)', background: 'rgba(0,0,0,0.15)', padding: '0.4rem 0.6rem', borderRadius: '4px' }}>
              {PIPELINE_STEPS.find(s => s.step === selectedStep).desc}
            </div>
          </div>
        </div>

        {/* Core Novel Contributions */}
        <div className="card glass-panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Award size={18} style={{ color: 'var(--text)' }} />
            Core Novel Contributions
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginBottom: '1.25rem' }}>
            This project bridges the gap between quantum VRP and cold-chain logistics research by introducing five primary contributions as detailed in our system blueprint:
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {[
              {
                num: '01',
                title: 'Spoilage Physics inside Quantum Hamiltonian',
                body: 'No published quantum VRP paper has encoded temperature-dependent spoilage decay as a term in the cost function. The decay equation (Value × Alpha × Cumulative_time × Quantity) is encoded directly as a Hamiltonian term, making the optimizer minimize actual monetary loss rather than just geographic distance.'
              },
              {
                num: '02',
                title: 'Cap-Bounded Multi-Trip Fleet Clustering',
                body: 'A classical two-level hierarchical planner manages fleet constraints and subproblem routing. Geographic K-means groups clinics strictly into the actual fleet size while repelling incompatible delivery windows. Dynamic load repair presorts delivery queues by time deadlines, and a greedy first-fit bin-packing algorithm dynamically splits clusters into trips satisfying frozen, chilled, and ambient compartment capacities.'
              },
              {
                num: '03',
                title: 'Hybrid Local Search & Quality-Weighted Voting',
                body: 'Integrates Quality-Weighted Consensus Voting which accumulates samples from the QAOA optimizer, assigning higher confidence weights to pristine quantum runs (3x) compared to repaired runs (1x). Symmetrizes the routing pipeline by feeding all paths into global duplicate repair and cross-vehicle Or-opt relocations to balance load and reduce refrigeration costs.'
              },
              {
                num: '04',
                title: 'First Quantum-Classical Cold-Chain Bridge',
                body: 'Directly connects the quantum computing research community with the cold-chain logistics research community by extending the Dash et al. 2025 hierarchical QAOA template into the multi-compartment cold-chain domain for the very first time.'
              },
              {
                num: '05',
                title: 'Rigorous OR Mathematical Formulation',
                body: 'Developed a mathematically complete MILP Operations Research formulation for the Cold-Chain VRP. It formally couples geographic routing constraints, active refrigeration power equations, and temperature-sensitive decay dynamics into a unified objective, providing a high-fidelity baseline for classical solver validation.'
              }
            ].map(({ num, title, body }) => (
              <div key={num} style={{
                display: 'flex',
                gap: '1rem',
                alignItems: 'flex-start',
                padding: '0.9rem 1rem',
                borderRadius: '8px',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
                transition: 'background 0.2s'
              }}>
                <span style={{
                  flexShrink: 0,
                  width: '2rem',
                  height: '2rem',
                  borderRadius: '6px',
                  background: 'rgba(255,255,255,0.06)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  color: 'rgba(255,255,255,0.45)',
                  letterSpacing: '0.04em',
                  fontFamily: 'var(--font-mono)'
                }}>{num}</span>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.88rem', color: 'var(--text)', marginBottom: '0.3rem' }}>{title}</div>
                  <p style={{ margin: 0, fontSize: '0.81rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* Sidebar: SVG Charts */}
      <div className="sidebar" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', height: '100%', justifyContent: 'space-between' }}>
        
        {/* Spoilage Physics Curves Chart */}
        <div className="card glass-panel" style={{ padding: '1.25rem' }}>
          <h3 style={{ fontSize: '0.98rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Clock size={16} style={{ color: 'var(--text)' }} />
            Spoilage Physics Curves
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', lineHeight: '1.4', marginBottom: '1rem' }}>
            Perishable decay over delivery transit hours. Frozen products spoil slowly (low alpha, high base cost), while Ambient products decay quickly.
          </p>

          {/* SVG Chart */}
          <div style={{ position: 'relative' }}>
            <svg viewBox="0 0 100 60" style={{ width: '100%', height: 'auto', background: 'rgba(0,0,0,0.2)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.04)' }}>
              {/* Grid Lines */}
              <line x1="10" y1="5" x2="10" y2="50" stroke="rgba(255,255,255,0.07)" strokeWidth="0.5" />
              <line x1="10" y1="50" x2="95" y2="50" stroke="rgba(255,255,255,0.07)" strokeWidth="0.5" />
              <line x1="10" y1="27.5" x2="95" y2="27.5" stroke="rgba(255,255,255,0.03)" strokeWidth="0.3" strokeDasharray="1 1" />
              
              {/* Curves */}
              <path d="M 10 49 C 30 48.8, 60 48.5, 95 48" fill="none" stroke="#38bdf8" strokeWidth="1.2" />
              <path d="M 10 49 C 30 45, 60 40, 95 32" fill="none" stroke="#10b981" strokeWidth="1.2" />
              <path d="M 10 49 C 30 40, 60 20, 95 5" fill="none" stroke="#f59e0b" strokeWidth="1.2" />

              {/* Axis Labels */}
              <text x="10" y="54" fill="var(--text-faint)" fontSize="2" textAnchor="middle">0h</text>
              <text x="52.5" y="54" fill="var(--text-faint)" fontSize="2" textAnchor="middle">5h</text>
              <text x="95" y="54" fill="var(--text-faint)" fontSize="2" textAnchor="middle">10h</text>
              <text x="6" y="8" fill="var(--text-faint)" fontSize="2" textAnchor="start" transform="rotate(-90 6 8)">Spoilage Cost →</text>
            </svg>
          </div>
          
          {/* Static Simulated Cost Breakdown Table */}
          <div style={{ marginTop: '0.8rem', padding: '0.75rem', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.04)' }}>
            <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.8rem', color: '#ffffff', fontWeight: 600 }}>
              Simulated Spoilage Cost Breakdown (Rs)
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.75rem' }}>
              {/* Table Header */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr 1fr', color: 'var(--text-muted)', fontWeight: 600, borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '0.25rem' }}>
                <span>Transit</span>
                <span style={{ color: '#38bdf8' }}>Frozen</span>
                <span style={{ color: '#10b981' }}>Chilled</span>
                <span style={{ color: '#f59e0b' }}>Ambient</span>
              </div>
              
              {/* Row 1: 2h */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr 1fr', borderBottom: '1px solid rgba(255,255,255,0.02)', paddingBottom: '0.2rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>2 Hours</span>
                <span>Rs 2.0</span>
                <span>Rs 12.0</span>
                <span>Rs 20.0</span>
              </div>

              {/* Row 2: 5h */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr 1fr', borderBottom: '1px solid rgba(255,255,255,0.02)', paddingBottom: '0.2rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>5 Hours</span>
                <span>Rs 5.0</span>
                <span>Rs 30.0</span>
                <span>Rs 50.0</span>
              </div>

              {/* Row 3: 10h */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr 1fr' }}>
                <span style={{ color: 'var(--text-secondary)' }}>10 Hours</span>
                <span>Rs 10.0</span>
                <span>Rs 60.0</span>
                <span>Rs 100.0</span>
              </div>
            </div>
          </div>
          
          <div style={{ marginTop: '0.8rem', fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            <strong style={{ color: 'var(--text-secondary)' }}>How to read these curves:</strong>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.5rem' }}>
              {[
                { color: '#38bdf8', label: 'Frozen', icon: '❄️', text: 'Almost flat line. Deep-frozen mRNA vaccines (stored at –70°C) degrade very slowly — but even 0.5% daily loss on a high-value shipment is expensive. Long delays still matter.' },
                { color: '#10b981', label: 'Chilled', icon: '🧊', text: 'Steady upward slope. Standard refrigerated vaccines (2–8°C) lose value steadily across the delivery window. Each extra hour costs roughly the same amount — a linear decay.' },
                { color: '#f59e0b', label: 'Ambient', icon: '🌡️', text: 'Sharp curve upward. Room-temperature goods (oral vaccines, some supplements) degrade at ~5% per hour. Deliver early or the entire batch becomes worthless.' }
              ].map(({ color, label, icon, text }) => (
                <div key={label} style={{ display: 'flex', gap: '0.6rem', padding: '0.6rem 0.75rem', borderRadius: '6px', background: 'rgba(255,255,255,0.02)', border: `1px solid ${color}22` }}>
                  <span style={{ fontSize: '0.9rem', flexShrink: 0 }}>{icon}</span>
                  <div>
                    <div style={{ fontWeight: 600, color, marginBottom: '0.15rem' }}>{label}</div>
                    <div style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>{text}</div>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: '0.75rem', padding: '0.6rem 0.75rem', borderRadius: '6px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              <strong style={{ color: 'var(--text-secondary)' }}>Key insight: </strong>The QAOA optimizer sees all three curve types simultaneously inside the Hamiltonian. It naturally schedules Ambient deliveries early and Frozen last — without being explicitly told to.
            </div>
          </div>
        </div>

        {/* Qubit Scaling: Direct vs Sub-Cluster */}
        <div className="card glass-panel" style={{ padding: '1.25rem' }}>
          <h3 style={{ fontSize: '0.98rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Cpu size={16} style={{ color: 'var(--text)' }} />
            Physical Qubit Scaling Complexity
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', lineHeight: '1.4', marginBottom: '1rem' }}>
            VRP Hamiltonians scale quadratically ($N^2$ qubits). The hybrid sub-clustering bounds quantum resource complexity to safe thresholds.
          </p>

          {/* SVG Qubit Chart */}
          <div style={{ position: 'relative' }}>
            <svg viewBox="0 0 100 60" style={{ width: '100%', height: 'auto', background: 'rgba(0,0,0,0.2)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.04)' }}>
              {/* Grid Lines */}
              <line x1="12" y1="5" x2="12" y2="50" stroke="rgba(255,255,255,0.07)" strokeWidth="0.5" />
              <line x1="12" y1="50" x2="95" y2="50" stroke="rgba(255,255,255,0.07)" strokeWidth="0.5" />
              <line x1="12" y1="42" x2="95" y2="42" stroke="#ef4444" strokeWidth="0.4" strokeDasharray="1 1" />
              <text x="94" y="40.5" fill="#ef4444" fontSize="1.8" textAnchor="end">Local Simulator Safe Limit (16 Qubits)</text>
              
              {/* Plotting points */}
              {sizes.map((s, idx) => {
                const x = 18 + (idx * 11);
                const directY = 50 - (directQubits[idx] * 0.45);
                const subY = 50 - (subClusterQubits[idx] * 0.45);

                return (
                  <g key={s}>
                    <circle cx={x} cy={directY} r="1" fill="#ef4444" />
                    <circle cx={x} cy={subY} r="1" fill="var(--solver-ortools)" />
                    
                    {idx < sizes.length - 1 && (
                      <>
                        <line
                          x1={x}
                          y1={directY}
                          x2={18 + ((idx + 1) * 11)}
                          y2={50 - (directQubits[idx + 1] * 0.45)}
                          stroke="#ef4444"
                          strokeWidth="0.6"
                        />
                        <line
                          x1={x}
                          y1={subY}
                          x2={18 + ((idx + 1) * 11)}
                          y2={50 - (subClusterQubits[idx + 1] * 0.45)}
                          stroke="var(--solver-ortools)"
                          strokeWidth="0.6"
                        />
                      </>
                    )}
                  </g>
                );
              })}

              {/* Axis labels */}
              {sizes.map((s, idx) => (
                <text key={s} x={18 + (idx * 11)} y="54" fill="var(--text-faint)" fontSize="2" textAnchor="middle">{s} nodes</text>
              ))}
              <text x="6" y="8" fill="var(--text-faint)" fontSize="2" textAnchor="start" transform="rotate(-90 6 8)">Qubits Required →</text>
            </svg>
          </div>
          
          <div style={{ marginTop: '0.8rem', fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            <strong style={{ color: 'var(--text-secondary)' }}>In plain terms:</strong>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.5rem' }}>
              {[
                { color: '#ef4444', label: 'Direct approach (red line)', text: 'Try to run the whole route on one quantum circuit. Each extra clinic doubles the memory needed. At 10 clinics you need 100 qubits — far more than any current hardware.' },
                { color: 'var(--solver-ortools)', label: 'Hybrid approach (flat line)', text: 'Split into groups of 4 clinics. Each group needs only 16 qubits. No matter how many clinics exist in total, the qubit cost stays the same — that is the key engineering breakthrough.' }
              ].map(({ color, label, text }) => (
                <div key={label} style={{ padding: '0.6rem 0.75rem', borderRadius: '6px', background: 'rgba(255,255,255,0.02)', border: `1px solid ${typeof color === 'string' && color.startsWith('#') ? color + '33' : 'rgba(255,255,255,0.06)'}` }}>
                  <div style={{ fontWeight: 600, color, marginBottom: '0.15rem' }}>{label}</div>
                  <div style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>{text}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: '0.75rem', padding: '0.6rem 0.75rem', borderRadius: '6px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              <strong style={{ color: 'var(--text-secondary)' }}>Dashed red line = </strong>the 16-qubit safe limit. Everything above it cannot be simulated on a standard laptop or run on current quantum hardware. The hybrid approach keeps us safely below.
            </div>
          </div>
        </div>


      </div>

    </div>
  );
}
