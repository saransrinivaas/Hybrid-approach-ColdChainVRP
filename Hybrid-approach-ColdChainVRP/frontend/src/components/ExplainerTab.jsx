import { useState, useEffect } from 'react';

const HAMILTONIAN_TERMS = {
  distance: {
    title: 'H_distance — Travel Distance Cost',
    math: '$$\\mathcal{H}_{\\text{distance}} = \\sum_{i=0}^{n-1} \\sum_{j \\neq i} d(i,j) \\sum_{t=0}^{n-2} x[i,t] \\cdot x[j,t+1]$$',
    physicalMeaning: 'Minimizes the total route length.',
    reason: 'Incurs a penalty proportional to the geographic distance traveled between consecutive stops.',
    qubitImpact: 'Creates quadratic coupling between consecutive time steps t and t+1. Mapped efficiently to O(n²) couplers in our solver.',
    color: '#8fd6c2'
  },
  spoilage: {
    title: 'H_spoilage — Vaccine Spoilage Cost',
    math: '$$\\mathcal{H}_{\\text{spoilage}} = \\sum_{i=0}^{n-1} \\sum_{t=0}^{n-1} \\left( \\sum_{c \\in C} \\text{Value}_c \\cdot \\alpha_c \\cdot D_{i,c} \\right) \\cdot \\bar{t}_{\\text{arrival}}(t) \\cdot x[i,t]$$',
    physicalMeaning: 'Prioritizes high-value, highly perishable vaccines early.',
    reason: 'Linearly scales penalties with delivery transit time. Ambient vaccines decay fast; Frozen vaccines degrade slowly but have high value.',
    qubitImpact: 'Linear (local field) term. Easily run on physical quantum computers with zero extra coupling overhead.',
    color: '#f472b6'
  },
  refrigeration: {
    title: 'H_refrigeration — Active Cooling Energy',
    math: '$$\\mathcal{H}_{\\text{refrigeration}} = \\sum_{i=0}^{n-1} \\sum_{t=0}^{n-1} \\left( \\frac{\\sum_{c \\in C} \\text{Power}_c \\cdot T_{\\text{duration}}}{n} \\right) \\cdot x[i,t]$$',
    physicalMeaning: 'Minimizes refrigeration energy consumed during transit.',
    reason: 'Balances travel duration against active refrigerator power (Frozen, Chilled, Ambient cooling compartments).',
    qubitImpact: 'Linear term. Provides a constant shift of the energy spectrum to balance cooling overheads.',
    color: '#d8bd7f'
  },
  visit: {
    title: 'H_visit — Visit Once Constraint',
    math: '$$\\mathcal{H}_{\\text{visit}} = M \\cdot \\sum_{i=0}^{n-1} \\left( \\sum_{t=0}^{n-1} x[i,t] - 1 \\right)^2$$',
    physicalMeaning: 'Ensures each clinic is visited exactly once.',
    reason: 'Applies a large squared penalty M = 2 × max(d(i,j)) to any route that skips or repeats a clinic stop.',
    qubitImpact: 'Fully connected quadratic terms. Represents the main coupling bottleneck for current NISQ processors.',
    color: '#cfcfcf'
  },
  position: {
    title: 'H_position — Position Once Constraint',
    math: '$$\\mathcal{H}_{\\text{position}} = M \\cdot \\sum_{t=0}^{n-1} \\left( \\sum_{i=0}^{n-1} x[i,t] - 1 \\right)^2$$',
    physicalMeaning: 'Ensures each time slot has exactly one clinic.',
    reason: 'Applies a squared penalty M to prevent visiting multiple clinics at the same time slot, or leaving slots empty.',
    qubitImpact: 'Fully connected quadratic terms. Couples qubits across clinics at each time step t.',
    color: '#caa5d8'
  }
};

const PIPELINE_STEPS = [
  {
    step: '1',
    title: 'Temporal Clustering',
    desc: 'Agglomerative clustering: D = geo × (1 + 0.6 × temporal_penalty).',
    details: 'Groups clinics by both physical proximity and operating time windows to prevent assigning incompatible stops to the same truck.'
  },
  {
    step: '2',
    title: 'Capacity Repair',
    desc: 'Greedy checks and dynamic capacity relaxation over 50 iterations.',
    details: 'Balances clinic demands across vehicles. Reassigns nodes or splits them into distinct trips if they exceed truck compartment limits.'
  },
  {
    step: '3',
    title: 'Sub-clustering',
    desc: 'Generates sub-clusters of size K <= 4 nodes with an overlap of 2 nodes.',
    details: 'Our key hybrid feature! Instead of a large 10-node route (100 qubits), we split it into sub-problems requiring only 9 or 16 qubits.'
  },
  {
    step: '4',
    title: 'Qiskit QAOA Run',
    desc: 'Runs actual Qiskit QAOA statevector sampler (p=3 depth) on each sub-cluster.',
    details: 'Optimizes parameters classically (COBYLA) to find the best scheduling bitstrings on simulated or physical quantum processors.'
  },
  {
    step: '5',
    title: 'Stitching & Consensus',
    desc: 'Merges overlapping sub-routes using weighted majority consensus voting.',
    details: 'Accumulates sub-cluster results, giving 3x confidence weight to pristine quantum routes and 1x to repaired ones.'
  },
  {
    step: '6',
    title: 'Post-Optimization',
    desc: 'Runs classical 2-opt and spoilage-aware Or-opt operators.',
    details: 'Refines global routes by reversing segments and shifting node sequences to achieve the absolute lowest combined cost.'
  }
];

export default function ExplainerTab({ activeTab }) {
  const [selectedTerm, setSelectedTerm] = useState('spoilage');
  const [selectedStep, setSelectedStep] = useState('3');

  useEffect(() => {
    if (activeTab === 'explainer' && window.MathJax && window.MathJax.typesetPromise) {
      setTimeout(() => {
        try {
          if (window.MathJax.typesetClear) {
            window.MathJax.typesetClear();
          }
        } catch (e) {
          console.warn('MathJax clear error:', e);
        }
        window.MathJax.typesetPromise().catch((err) => console.log('MathJax typesetting error:', err));
      }, 50);
    }
  }, [activeTab, selectedTerm, selectedStep]);

  const sizes = [2, 3, 4, 5, 6, 8, 10];
  const directQubits = sizes.map(s => s * s);
  const subClusterQubits = sizes.map(s => s <= 4 ? s * s : 16);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.75rem', alignItems: 'start' }}>
      
      {/* LEFT COLUMN: Main Engine Mechanics & Core Explanations */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        
        {/* Hamiltonian Explorer */}
        <div className="card glass-panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.35rem', color: '#fff', fontWeight: 700 }}>
            Interactive Hamiltonian Term Explorer
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', marginBottom: '1.25rem', lineHeight: '1.6' }}>
            The objective function is expressed as a Quadratic Unconstrained Binary Optimization (QUBO) Hamiltonian. Click on any term to explore its mathematical formula, functional purpose, and quantum hardware mapping.
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem', marginBottom: '1.25rem' }}>
            {Object.keys(HAMILTONIAN_TERMS).map((key) => {
              const isSelected = selectedTerm === key;
              return (
                <button
                  key={key}
                  onClick={() => setSelectedTerm(key)}
                  style={{
                    padding: '0.6rem 1rem',
                    background: isSelected ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.03)',
                    color: isSelected ? '#ffffff' : 'var(--text)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '0.92rem',
                    fontWeight: 600,
                    transition: 'all 0.2s',
                    borderLeft: isSelected ? '3px solid #ffffff' : '3px solid rgba(255,255,255,0.1)'
                  }}
                >
                  {key.toUpperCase()}
                </button>
              );
            })}
          </div>

          <div
            style={{
              padding: '1.25rem',
              background: 'rgba(0,0,0,0.2)',
              borderRadius: '8px',
              border: '1px solid rgba(255,255,255,0.05)',
              marginBottom: '1.25rem',
              textAlign: 'center',
              overflowX: 'auto'
            }}
          >
            <div key={selectedTerm} style={{ fontSize: '1.35rem', color: '#ffffff' }}>
              {HAMILTONIAN_TERMS[selectedTerm].math}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', fontSize: '0.95rem' }}>
            <div style={{ padding: '0.8rem', background: 'rgba(255,255,255,0.01)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.03)' }}>
              <div style={{ fontWeight: 700, color: 'var(--text)', marginBottom: '0.4rem' }}>
                Functional Objective
              </div>
              <div style={{ color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                {HAMILTONIAN_TERMS[selectedTerm].reason}
              </div>
            </div>
            <div style={{ padding: '0.8rem', background: 'rgba(255,255,255,0.01)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.03)' }}>
              <div style={{ fontWeight: 700, color: 'var(--text)', marginBottom: '0.4rem' }}>
                Quantum Gate Mapping
              </div>
              <div style={{ color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                {HAMILTONIAN_TERMS[selectedTerm].qubitImpact}
              </div>
            </div>
          </div>
        </div>

        {/* Physical Qubit Scaling Complexity */}
        <div className="card glass-panel" style={{ padding: '1.25rem' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.05rem', color: '#fff', fontWeight: 700 }}>
            Physical Qubit Scaling Complexity
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', lineHeight: '1.5', marginBottom: '1rem' }}>
            VRP Hamiltonians scale quadratically (N² qubits). Our hybrid sub-clustering bounds quantum resource complexity to safe simulator thresholds.
          </p>

          <div style={{ position: 'relative', marginBottom: '1rem' }}>
            <svg viewBox="0 0 100 60" style={{ width: '100%', height: 'auto', background: 'rgba(0,0,0,0.2)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.04)' }}>
              <line x1="12" y1="5" x2="12" y2="50" stroke="rgba(255,255,255,0.07)" strokeWidth="0.5" />
              <line x1="12" y1="50" x2="95" y2="50" stroke="rgba(255,255,255,0.07)" strokeWidth="0.5" />
              <line x1="12" y1="42" x2="95" y2="42" stroke="#ef4444" strokeWidth="0.5" strokeDasharray="1 1" />
              <text x="94" y="40" fill="#ef4444" fontSize="2.2" textAnchor="end">Local Simulator Safe Limit (16 Qubits)</text>
              
              {sizes.map((s, idx) => {
                const x = 18 + (idx * 11);
                const directY = 50 - (directQubits[idx] * 0.45);
                const subY = 50 - (subClusterQubits[idx] * 0.45);

                return (
                  <g key={s}>
                    <circle cx={x} cy={directY} r="1.2" fill="#ef4444" />
                    <circle cx={x} cy={subY} r="1.2" fill="#10b981" />
                    
                    {idx < sizes.length - 1 && (
                      <>
                        <line
                          x1={x}
                          y1={directY}
                          x2={18 + ((idx + 1) * 11)}
                          y2={50 - (directQubits[idx + 1] * 0.45)}
                          stroke="#ef4444"
                          strokeWidth="1.2"
                        />
                        <line
                          x1={x}
                          y1={subY}
                          x2={18 + ((idx + 1) * 11)}
                          y2={50 - (subClusterQubits[idx + 1] * 0.45)}
                          stroke="#10b981"
                          strokeWidth="1.2"
                        />
                      </>
                    )}
                  </g>
                );
              })}

              {sizes.map((s, idx) => (
                <text key={s} x={18 + (idx * 11)} y="55" fill="var(--text-faint)" fontSize="2.2" textAnchor="middle">{s}n</text>
              ))}
              <text x="6" y="8" fill="var(--text-faint)" fontSize="2.2" textAnchor="start" transform="rotate(-90 6 8)">Qubits Required →</text>
            </svg>
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
            <div style={{ padding: '0.5rem 0.75rem', borderRadius: '6px', background: 'rgba(255,255,255,0.02)' }}>
              <strong style={{ color: '#ef4444', display: 'block', marginBottom: '2px' }}>Direct approach (Red line):</strong>
              Running a whole route together scales exponentially. 10 clinics require 100 qubits—unsimulatable on local laptops.
            </div>
            <div style={{ padding: '0.5rem 0.75rem', borderRadius: '6px', background: 'rgba(255,255,255,0.02)' }}>
              <strong style={{ color: '#10b981', display: 'block', marginBottom: '2px' }}>Hybrid approach (Green line):</strong>
              Splits routes into small sub-clusters. Qubit cost stays constant at 9 or 16 qubits, regardless of global VRP scale.
            </div>
          </div>
        </div>

        {/* Core Novel Contributions */}
        <div className="card glass-panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.35rem', color: '#fff', fontWeight: 700 }}>
            Core Novel Contributions
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', marginBottom: '1.25rem', lineHeight: '1.5' }}>
            Our hybrid design introduces three primary contributions to cold-chain quantum optimization:
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {[
              {
                num: '01',
                title: 'Spoilage Physics in Quantum Hamiltonian',
                body: 'Encodes decay equations directly as a Hamiltonian optimization term, making the optimizer minimize actual product value loss rather than just distance.'
              },
              {
                num: '02',
                title: 'Cap-Bounded Multi-Trip Fleet Clustering',
                body: 'Groups clinics using temporal time window penalties, and uses a classical first-fit bin packer to split large clusters into feasible refrigerator trips.'
              },
              {
                num: '03',
                title: 'Weighted Consensus Stitching',
                body: 'Merges overlapping sub-routes by voting, giving 3x higher weight to pristine quantum routes and 1x to classically repaired ones.'
              }
            ].map(({ num, title, body }) => (
              <div key={num} style={{
                display: 'flex',
                gap: '1rem',
                alignItems: 'flex-start',
                padding: '0.8rem 1rem',
                borderRadius: '8px',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)'
              }}>
                <span style={{
                  flexShrink: 0,
                  width: '2.5rem',
                  height: '2.5rem',
                  borderRadius: '6px',
                  background: 'rgba(255,255,255,0.06)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.95rem',
                  fontWeight: 700,
                  color: 'rgba(255,255,255,0.45)',
                  fontFamily: 'var(--font-mono)'
                }}>{num}</span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text)', marginBottom: '0.3rem' }}>{title}</div>
                  <p style={{ margin: 0, fontSize: '0.92rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* RIGHT COLUMN: Visual Charts & Workflow */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        
        {/* Spoilage Physics Curves Chart */}
        <div className="card glass-panel" style={{ padding: '1.25rem' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.05rem', color: '#fff', fontWeight: 700 }}>
            Spoilage Physics Curves
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', lineHeight: '1.5', marginBottom: '1rem' }}>
            Perishable decay over delivery transit hours. Ambient products spoil rapidly; Chilled vaccines lose value linearly; Frozen vaccines decay very slowly.
          </p>

          <div style={{ position: 'relative', marginBottom: '1rem' }}>
            <svg viewBox="0 0 100 60" style={{ width: '100%', height: 'auto', background: 'rgba(0,0,0,0.2)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.04)' }}>
              <line x1="12" y1="5" x2="12" y2="50" stroke="rgba(255,255,255,0.07)" strokeWidth="0.5" />
              <line x1="12" y1="50" x2="95" y2="50" stroke="rgba(255,255,255,0.07)" strokeWidth="0.5" />
              <line x1="12" y1="27.5" x2="95" y2="27.5" stroke="rgba(255,255,255,0.03)" strokeWidth="0.3" strokeDasharray="1 1" />
              
              <path d="M 12 49 C 30 48.8, 60 48.5, 95 48" fill="none" stroke="#38bdf8" strokeWidth="1.8" />
              <path d="M 12 49 C 30 45, 60 40, 95 32" fill="none" stroke="#10b981" strokeWidth="1.8" />
              <path d="M 12 49 C 30 40, 60 20, 95 5" fill="none" stroke="#f59e0b" strokeWidth="1.8" />

              <text x="12" y="55" fill="var(--text-faint)" fontSize="2.2" textAnchor="middle">0h</text>
              <text x="53.5" y="55" fill="var(--text-faint)" fontSize="2.2" textAnchor="middle">5h</text>
              <text x="95" y="55" fill="var(--text-faint)" fontSize="2.2" textAnchor="middle">10h</text>
              <text x="6" y="8" fill="var(--text-faint)" fontSize="2.2" textAnchor="start" transform="rotate(-90 6 8)">Spoilage Cost →</text>
            </svg>
          </div>
          
          <div style={{ padding: '0.75rem', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.04)', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.85rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr 1fr', color: 'var(--text-muted)', fontWeight: 700, borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '0.25rem' }}>
                <span>Transit</span>
                <span style={{ color: '#38bdf8' }}>Frozen</span>
                <span style={{ color: '#10b981' }}>Chilled</span>
                <span style={{ color: '#f59e0b' }}>Ambient</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr 1fr', borderBottom: '1px solid rgba(255,255,255,0.02)', paddingBottom: '0.2rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>2 Hours</span>
                <span>Rs 2.0</span>
                <span>Rs 12.0</span>
                <span>Rs 20.0</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr 1fr', borderBottom: '1px solid rgba(255,255,255,0.02)', paddingBottom: '0.2rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>5 Hours</span>
                <span>Rs 5.0</span>
                <span>Rs 30.0</span>
                <span>Rs 50.0</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr 1fr' }}>
                <span style={{ color: 'var(--text-secondary)' }}>10 Hours</span>
                <span>Rs 10.0</span>
                <span>Rs 60.0</span>
                <span>Rs 100.0</span>
              </div>
            </div>
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
            {[
              { color: '#38bdf8', label: 'Frozen (mRNA)', text: 'Degrades very slowly (low alpha). Safe for long trips, but value is extremely high.' },
              { color: '#10b981', label: 'Chilled (Standard)', text: 'Loss accumulates linearly. Must balance stop order with distance.' },
              { color: '#f59e0b', label: 'Ambient (Oral)', text: 'Fast decay (alpha=0.05). Must be delivered first to prevent complete spoilage.' }
            ].map(({ color, label, text }) => (
              <div key={label} style={{ display: 'flex', gap: '0.6rem', padding: '0.5rem 0.75rem', borderRadius: '6px', background: 'rgba(255,255,255,0.02)', border: `1px solid ${color}22` }}>
                <div style={{ fontWeight: 700, color, minWidth: '120px' }}>{label}:</div>
                <div style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>{text}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Hybrid Pipeline Workflow */}
        <div className="card glass-panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.35rem', color: '#fff', fontWeight: 700 }}>
            Interactive End-to-End Pipeline Walkthrough
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', marginBottom: '1.25rem', lineHeight: '1.6' }}>
            Click on any pipeline step to see how geographic routing tasks are mapped, solved on the Qiskit simulator, and merged into the final post-optimized routes.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '0.5rem', marginBottom: '1.25rem' }}>
            {PIPELINE_STEPS.map((s) => {
              const isSelected = selectedStep === s.step;
              return (
                <button
                  key={s.step}
                  onClick={() => setSelectedStep(s.step)}
                  style={{
                    padding: '0.75rem 0.5rem',
                    background: isSelected ? '#f97316' : 'rgba(255,255,255,0.03)',
                    color: isSelected ? '#ffffff' : 'var(--text)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '0.2rem',
                    fontWeight: 600,
                    transition: 'all 0.2s'
                  }}
                >
                  <span style={{ fontSize: '0.7rem', opacity: 0.6 }}>STEP {s.step}</span>
                  <span style={{ textAlign: 'center', fontSize: '0.8rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', width: '100%' }}>
                    {s.title.split(' ')[0]}
                  </span>
                </button>
              );
            })}
          </div>

          <div
            style={{
              padding: '1.25rem',
              background: 'rgba(255,255,255,0.02)',
              borderRadius: '8px',
              border: '1px solid rgba(255,255,255,0.05)',
              borderLeft: '4px solid #f97316'
            }}
          >
            <div style={{ fontWeight: 700, fontSize: '1.05rem', color: '#ffffff', marginBottom: '0.4rem' }}>
              Step {selectedStep}: {PIPELINE_STEPS.find(s => s.step === selectedStep).title}
            </div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.96rem', lineHeight: '1.6', marginBottom: '0.6rem' }}>
              {PIPELINE_STEPS.find(s => s.step === selectedStep).details}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.88rem', color: 'var(--text-muted)', background: 'rgba(0,0,0,0.15)', padding: '0.45rem 0.65rem', borderRadius: '4px' }}>
              {PIPELINE_STEPS.find(s => s.step === selectedStep).desc}
            </div>
          </div>
        </div>

        {/* Quantum Advantage & Scalability Roadmap */}
        <div className="card glass-panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.35rem', color: '#fff', fontWeight: 700 }}>
            Quantum Advantage & Scalability Roadmap
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', marginBottom: '1.25rem', lineHeight: '1.5' }}>
            How our hybrid coprocessor outperforms pure classical solvers:
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div style={{ padding: '0.8rem 1rem', borderRadius: '8px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', fontSize: '1.0rem' }}>
              <strong style={{ color: '#ffffff', display: 'block', fontSize: '1.05rem', marginBottom: '0.25rem' }}>
                1. Linear Scaling vs Classical Exponential Wall
              </strong>
              <p style={{ margin: 0, color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                Exact classical solvers (Gurobi) scale exponentially O(2^N) and crash on 100+ nodes. Our hybrid decomposition scales linearly O(N) by keeping sub-problems small and constant.
              </p>
            </div>

            <div style={{ padding: '0.8rem 1rem', borderRadius: '8px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', fontSize: '1.0rem' }}>
              <strong style={{ color: '#ffffff', display: 'block', fontSize: '1.05rem', marginBottom: '0.25rem' }}>
                2. Overcoming Heuristic Local Basins
              </strong>
              <p style={{ margin: 0, color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                Classical heuristics (ALNS) get trapped in poor local solutions. QAOA uses superposition to navigate complex routing options globally, providing an optimized starting route backbone.
              </p>
            </div>
          </div>
        </div>

      </div>

    </div>
  );
}
