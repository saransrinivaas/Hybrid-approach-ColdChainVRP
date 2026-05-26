import { useState, useRef, useEffect, useMemo } from 'react';
import { Zap, CheckCircle2, AlertCircle, Loader } from 'lucide-react';
import TerminalPanel from './TerminalPanel';
import { API_BASE } from '../data';

const STEPS = [
  { key: 'clustering', label: 'Vehicular Clustering',  color: '#3b82f6' },
  { key: 'qubo',       label: 'QUBO Construction',     color: '#8b5cf6' },
  { key: 'qaoa',       label: 'QAOA Solver',           color: '#f59e0b' },
  { key: 'stitching',  label: 'Stitch & Repair',       color: '#10b981' },
];

// Detect which pipeline step a log line belongs to
function detectStep(line) {
  if (line.includes('STEP 1') || line.includes('Vehicular Clustering') || line.includes('K-Means')) return 'clustering';
  if (line.includes('QUBO') || line.includes('Hamiltonian')) return 'qubo';
  if (line.includes('QAOA') || line.includes('STEP 2') || line.includes('Sub-cluster')) return 'qaoa';
  if (line.includes('STITCH') || line.includes('STEP 3') || line.includes('2-opt') || line.includes('Consensus')) return 'stitching';
  return null;
}

export default function PipelineTab({ runPipeline }) {
  const [logs, setLogs] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState(null);
  const logsEndRef = useRef(null);

  useEffect(() => {
    if (logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const { activeStep, completedSteps } = useMemo(() => {
    let current = null;
    const completed = new Set();
    for (const line of logs) {
      const step = detectStep(line);
      if (step && step !== current) {
        if (current) completed.add(current);
        current = step;
      }
    }
    if (!isRunning && logs.length > 0) {
      STEPS.forEach((s) => completed.add(s.key));
      current = null;
    }
    return { activeStep: current, completedSteps: completed };
  }, [logs, isRunning]);

  const handleRun = () => {
    setResults(null);
    runPipeline('/api/run-pipeline', setLogs, setIsRunning, () => {
      // Fetch final results
      fetch(`${API_BASE}/api/results`)
        .then((r) => r.json())
        .then((data) => { if (!data.error) setResults(data); })
        .catch(() => {});
    });
  };

  const stepStatus = (key) => {
    if (completedSteps.has(key)) return 'done';
    if (activeStep === key) return 'running';
    return 'pending';
  };

  return (
    <div className="content-grid">
      <div className="main-content">
        {/* Progress stepper */}
        <div className="card glass-panel" style={{ marginBottom: '1rem', padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
            {STEPS.map((step, idx) => {
              const status = stepStatus(step.key);
              return (
                <div key={step.key} style={{ display: 'contents' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background:
                          status === 'done'    ? step.color :
                          status === 'running' ? `${step.color}33` :
                          'rgba(255,255,255,0.05)',
                        border: `2px solid ${status !== 'pending' ? step.color : 'rgba(255,255,255,0.1)'}`,
                        transition: 'all 0.3s',
                      }}
                    >
                      {status === 'done'    && <CheckCircle2 size={14} color={step.color} />}
                      {status === 'running' && <Loader size={14} color={step.color} style={{ animation: 'spin 1s linear infinite' }} />}
                      {status === 'pending' && <span style={{ fontSize: '0.7rem', color: '#6b7280' }}>{idx + 1}</span>}
                    </div>
                    <span
                      style={{
                        fontSize: '0.85rem',
                        fontWeight: status !== 'pending' ? 600 : 400,
                        color: status !== 'pending' ? step.color : 'var(--text-secondary)',
                      }}
                    >
                      {step.label}
                    </span>
                  </div>
                  {idx < STEPS.length - 1 && (
                    <div
                      style={{
                        flex: 1,
                        height: 2,
                        minWidth: 20,
                        background: completedSteps.has(step.key)
                          ? `linear-gradient(90deg, ${step.color}, ${STEPS[idx + 1].color})`
                          : 'rgba(255,255,255,0.08)',
                        borderRadius: 1,
                        transition: 'background 0.5s',
                      }}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <TerminalPanel
          logs={logs}
          logsEndRef={logsEndRef}
          isRunning={isRunning}
          onRun={handleRun}
          btnLabel="Run Hybrid Pipeline"
          idleText='Click "Run Hybrid Pipeline" to execute all 4 stages end-to-end: Clustering → QUBO → QAOA → Stitch & Repair.'
          height="340px"
        />

        {/* Results summary */}
        {results && (
          <div className="card glass-panel" style={{ marginTop: '1rem' }}>
            <h3>
              <CheckCircle2 size={20} style={{ color: '#10b981' }} /> Hybrid Pipeline Complete — Final Results
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginTop: '1rem' }}>
              {[
                { label: 'Fleet Distance', value: `${results.fleet_distance} km`,    color: '#3b82f6' },
                { label: 'Fleet Spoilage', value: `Rs ${results.fleet_spoilage}`,    color: '#ef4444' },
                { label: 'Combined Cost',  value: `Rs ${results.fleet_total_cost}`,  color: '#10b981' },
              ].map(({ label, value, color }) => (
                <div
                  key={label}
                  style={{
                    padding: '1rem',
                    background: 'rgba(255,255,255,0.03)',
                    borderRadius: '10px',
                    border: `1px solid ${color}33`,
                    textAlign: 'center',
                  }}
                >
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>{label}</div>
                  <div style={{ fontSize: '1.3rem', fontWeight: 700, color }}>{value}</div>
                </div>
              ))}
            </div>

            {/* Per-vehicle routes */}
            <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {Object.entries(results.routes).map(([vid, vdata]) => (
                <div
                  key={vid}
                  style={{
                    padding: '0.75rem 1rem',
                    background: 'rgba(255,255,255,0.02)',
                    borderRadius: '8px',
                    border: '1px solid rgba(255,255,255,0.06)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                    <span style={{ fontWeight: 600, color: '#e5e7eb' }}>{vid}</span>
                    <div style={{ display: 'flex', gap: '1rem', fontSize: '0.82rem', fontFamily: 'monospace' }}>
                      <span style={{ color: '#3b82f6' }}>{vdata.distance_km} km</span>
                      <span style={{ color: '#ef4444' }}>Rs {vdata.spoilage_rs}</span>
                      <span style={{ color: vdata.feasible ? '#10b981' : '#ef4444' }}>
                        {vdata.feasible ? '✓ Feasible' : '✗ Infeasible'}
                      </span>
                    </div>
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                    {vdata.stops.map((s) => s.name).join(' → ')}
                  </div>
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
            <Zap size={20} className="gradient-text" /> Hybrid Pipeline
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: '1.6', marginBottom: '1rem' }}>
            Runs all four stages in sequence as a single streamed job. Results are saved to{' '}
            <code style={{ color: '#10b981' }}>results.json</code> on completion.
          </p>
          {STEPS.map((step, idx) => (
            <div key={step.key} className="stat-row">
              <span className="stat-label">Step {idx + 1}</span>
              <span className="stat-value" style={{ color: step.color }}>{step.label}</span>
            </div>
          ))}
        </div>

        <div className="card glass-panel" style={{ marginTop: '1rem' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>
            <AlertCircle size={20} className="gradient-text" /> Expected Runtime
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {[
              { step: 'Clustering',  time: '< 5s',    color: '#3b82f6' },
              { step: 'QUBO Build',  time: '< 10s',   color: '#8b5cf6' },
              { step: 'QAOA (p=2)', time: '2–10 min', color: '#f59e0b' },
              { step: 'Stitching',   time: '< 5s',    color: '#10b981' },
            ].map(({ step, time, color }) => (
              <div
                key={step}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '0.4rem 0.6rem',
                  background: 'rgba(255,255,255,0.02)',
                  borderRadius: '6px',
                  border: '1px solid rgba(255,255,255,0.05)',
                }}
              >
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{step}</span>
                <span style={{ fontSize: '0.85rem', fontFamily: 'monospace', color }}>{time}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
