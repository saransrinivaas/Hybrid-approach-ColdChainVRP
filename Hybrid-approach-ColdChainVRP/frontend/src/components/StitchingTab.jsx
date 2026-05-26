import { useState, useRef, useEffect } from 'react';
import { GitMerge } from 'lucide-react';
import TerminalPanel from './TerminalPanel';

const PHASES = [
  { phase: 'Phase 1', name: 'Sub-cluster Repair',  desc: 'Fix infeasible QAOA output via cheapest insertion', color: '#ef4444' },
  { phase: 'Phase 2', name: 'Consensus Vote',       desc: 'Pairwise voting across overlapping sub-clusters',  color: '#f59e0b' },
  { phase: 'Phase 3', name: 'Depot Wrapping',       desc: 'Prepend and append depot ID=0 to each route',      color: '#3b82f6' },
  { phase: 'Phase 4', name: '2-opt Improvement',    desc: 'Reverse segments to shorten total distance',       color: '#8b5cf6' },
  { phase: 'Phase 5', name: 'Cross-vehicle Repair', desc: 'Fix duplicates, missing clinics, overflows',       color: '#10b981' },
];

export default function StitchingTab({ runPipeline }) {
  const [logs, setLogs] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [done, setDone] = useState(false);
  const logsEndRef = useRef(null);

  useEffect(() => {
    if (logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="content-grid">
      <div className="main-content">
        <TerminalPanel
          logs={logs}
          logsEndRef={logsEndRef}
          isRunning={isRunning}
          onRun={() => runPipeline('/api/run-stitching', setLogs, setIsRunning, setDone)}
          btnLabel="Run Stitch & Repair"
          idleText="Ready. Click to run the stitching + repair pipeline on the QAOA output."
        />
        {done && (
          <div className="card glass-panel" style={{ marginTop: '1rem' }}>
            <h3>
              <GitMerge size={20} className="gradient-text" /> Pipeline Phases
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {PHASES.map(({ phase, name, desc, color }) => (
                <div
                  key={phase}
                  style={{
                    padding: '0.75rem',
                    background: 'rgba(255,255,255,0.02)',
                    borderRadius: '8px',
                    border: '1px solid rgba(255,255,255,0.05)',
                    borderLeft: `3px solid ${color}`,
                  }}
                >
                  <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', marginBottom: '0.2rem' }}>
                    <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: '#6b7280' }}>{phase}</span>
                    <span style={{ fontWeight: 600, color }}>{name}</span>
                  </div>
                  <div style={{ fontSize: '0.83rem', color: 'var(--text-secondary)' }}>{desc}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Sidebar */}
      <div className="sidebar" style={{ maxHeight: 'calc(100vh - 120px)', overflowY: 'auto', paddingRight: '10px' }}>
        <div className="card glass-panel">
          <h3>
            <GitMerge size={20} className="gradient-text" /> About Stitching
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: '1.6' }}>
            QAOA returns an optimal ordering for each 3-node sub-cluster independently.
            Stitching combines these overlapping results into a single coherent route per vehicle,
            then applies 2-opt improvement and cross-vehicle feasibility repair.
          </p>
        </div>
        <div className="card glass-panel" style={{ marginTop: '1rem' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>
            <GitMerge size={20} className="gradient-text" /> Repair Types
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {[
              { label: 'Type 1 — Duplicates',  desc: 'Same clinic assigned to multiple vehicles', color: '#ef4444' },
              { label: 'Type 2 — Missing',      desc: 'Clinic not assigned to any vehicle',        color: '#f59e0b' },
              { label: 'Type 3 — Overflow',     desc: 'Capacity exceeded after stitching',         color: '#8b5cf6' },
            ].map(({ label, desc, color }) => (
              <div
                key={label}
                style={{
                  padding: '0.6rem 0.75rem',
                  background: 'rgba(255,255,255,0.03)',
                  borderRadius: '6px',
                  border: '1px solid rgba(255,255,255,0.05)',
                  borderLeft: `3px solid ${color}`,
                }}
              >
                <div style={{ fontWeight: 600, color, fontSize: '0.85rem', marginBottom: '0.2rem' }}>{label}</div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
