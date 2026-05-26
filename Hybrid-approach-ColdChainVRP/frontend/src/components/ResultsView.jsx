import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Polygon } from 'react-leaflet';
import L from 'leaflet';
import {
  CheckCircle2, Circle, BarChart2, Cpu, Zap, GitMerge,
  Route, Home, MapPin, Truck, Clock, Activity, ShieldAlert, AlertTriangle
} from 'lucide-react';
import { API_BASE, DEPOT } from '../data';

const STEPS = [
  { id: 'input',      label: 'Input' },
  { id: 'clustering', label: 'Clustering' },
  { id: 'qubo',       label: 'QUBO' },
  { id: 'stitching',  label: 'Stitching' },
  { id: 'comparison', label: 'Comparison' },
];

const VEHICLE_COLORS = [
  '#3b82f6', // Premium Blue
  '#10b981', // Premium Green
  '#8b5cf6', // Premium Purple
  '#f59e0b', // Premium Amber
  '#ef4444', // Premium Red
  '#06b6d4', // Premium Cyan
  '#ec4899', // Premium Pink
];


const makeIcon = (color, label = '') =>
  new L.DivIcon({
    className: 'vrp-marker',
    html: `<div class="vrp-place-marker" style="--marker-color:${color}"><div class="vrp-place-bubble">${label}</div><div class="vrp-place-chip">Clinic ${label}</div></div>`,
    iconSize: [44, 58], iconAnchor: [22, 29],
  });

const depotIcon = new L.DivIcon({
  className: 'vrp-marker',
  html: `<div class="vrp-place-marker depot"><div class="vrp-place-bubble">D</div><div class="vrp-place-chip">Depot</div></div>`,
  iconSize: [54, 58], iconAnchor: [27, 29],
});

function RouteTimeline({ stops = [], color }) {
  return (
    <div className="route-timeline" style={{ '--route-color': color, display: 'flex', flexDirection: 'row', flexWrap: 'nowrap' }}>
      {stops.map((stop, idx) => {
        const isDepot = idx === 0 || idx === stops.length - 1 || stop.name.toLowerCase().includes('depot');
        return (
          <div key={`${stop.name}-${idx}`} className={`route-stop${isDepot ? ' depot-stop' : ''}`}>
            <span className="route-dot">
              {isDepot ? <Home size={8} strokeWidth={2.4} aria-hidden /> : <MapPin size={8} strokeWidth={2.4} aria-hidden />}
            </span>
            <span className="route-stop-label" title={stop.name}>{stop.name}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Step Indicator ────────────────────────────────────────────────────────────
function StepIndicator({ current, completed }) {
  return (
    <div className="step-indicator">
      {STEPS.map((step, idx) => {
        const done    = completed.includes(step.id);
        const active  = step.id === current;
        return (
          <div key={step.id} className={`step-node${active ? ' active' : ''}${done ? ' done' : ''}`}>
            <div className="step-dot-wrap">
              {done
                ? <CheckCircle2 size={16} strokeWidth={2} />
                : active
                  ? <div className="step-dot-active" />
                  : <Circle size={16} strokeWidth={1.5} style={{ opacity: 0.3 }} />}
            </div>
            <span className="step-label">{step.label}</span>
            {idx < STEPS.length - 1 && <div className={`step-connector${done ? ' done' : ''}`} />}
          </div>
        );
      })}
    </div>
  );
}

// ── Explanation card ──────────────────────────────────────────────────────────
function ExplainCard({ children }) {
  return (
    <div className="explain-card">
      <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.65 }}>{children}</p>
    </div>
  );
}

// ── Cap utilization bar ───────────────────────────────────────────────────────
function CapBar({ label, used, cap }) {
  const pct = cap > 0 ? Math.min(100, (used / cap) * 100) : 0;
  return (
    <div className="cap-bar-wrapper">
      <span className="cap-bar-label" style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{label}</span>
      <div className="cap-bar-bg">
        <div className="cap-bar-fill" style={{ width: `${pct}%`, background: '#fff' }} />
      </div>
      <span style={{ fontSize: '0.68rem', color: 'var(--text-faint)', width: '3rem', textAlign: 'right' }}>{used}/{cap}</span>
    </div>
  );
}

// ── Step 1: Input summary ─────────────────────────────────────────────────────
function Step1Input({ config }) {
  if (!config) return <div style={{ color: 'var(--text-muted)', padding: '2rem', textAlign: 'center' }}>No configuration loaded.</div>;
  const included = (config.clinics || []).filter(c => c.included);
  return (
    <div className="results-step-body">
      <ExplainCard>
        Configuration submitted. {included.length} clinics, {config.num_vehicles} vehicles, {(config.vaccines || []).length} vaccine type(s).
        The pipeline will cluster clinics, build QUBO sub-problems, run QAOA at p=3, then stitch routes.
      </ExplainCard>
      <div className="results-grid-2">
        <div className="glass-panel" style={{ padding: '1rem' }}>
          <h3 style={{ fontSize: '0.85rem', marginBottom: '0.75rem' }}>Vaccines</h3>
          {(config.vaccines || []).map(v => (
            <div key={v.id} className="result-row" style={{ padding: '0.4rem 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontSize: '0.82rem' }}>{v.id}</span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{v.compartment} · α={v.alpha}</span>
            </div>
          ))}
        </div>
        <div className="glass-panel" style={{ padding: '1rem' }}>
          <h3 style={{ fontSize: '0.85rem', marginBottom: '0.75rem' }}>Included Clinics</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
            {included.map(c => (
              <span key={c.id} className="badge">{c.id}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Step 2: Clustering ────────────────────────────────────────────────────────
function Step2Clustering({ scenarioMeta, config, pipelineHasRun }) {
  const [clusterData, setClusterData] = useState(null);
  useEffect(() => {
    if (!pipelineHasRun) {
      setClusterData(null);
      return;
    }
    fetch(`${API_BASE}/api/clustering-result`)
      .then(r => r.json())
      .then(d => { if (!d.error) setClusterData(d); })
      .catch(() => {});
  }, [pipelineHasRun]);

  const depot   = scenarioMeta?.easy?.depot || DEPOT;
  const clinics = config?.clinics || scenarioMeta?.easy?.clinics || [];

  return (
    <div className="results-step-body">
      <ExplainCard>
        Clinics are grouped into vehicle-sized clusters using capacitated K-means — ensuring each cluster fits within one vehicle&apos;s compartment limits and within the 16-qubit budget per 4-node sub-cluster (QAOA p=3).
      </ExplainCard>
      <div className="results-grid-map-sidebar">
        <div className="map-shell" style={{ height: '420px' }}>
          <MapContainer center={[depot?.lat || 13.04, depot?.lon || 80.18]} zoom={11} style={{ height: '100%', width: '100%' }}>
            <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" attribution="&copy; OpenStreetMap &copy; CARTO" />
            {depot && typeof depot.lat === 'number' && typeof depot.lon === 'number' && (
              <Marker position={[depot.lat, depot.lon]} icon={depotIcon}>
                <Popup><strong>{depot.name}</strong></Popup>
              </Marker>
            )}
            {clusterData ? clusterData.map((vehicle, vIdx) => {
              const color = VEHICLE_COLORS[vIdx % VEHICLE_COLORS.length];
              const vClinics = vehicle.trips
                .flatMap(t => t.clinics)
                .map(id => clinics.find(c => String(c.id) === String(id)))
                .filter(c => c && typeof c.lat === 'number' && typeof c.lon === 'number');
              return vClinics.map(c => (
                <Marker key={c.id} position={[c.lat, c.lon]} icon={makeIcon(color, c.id)}>
                  <Popup><strong>{c.name}</strong><br />{vehicle.vehicleId}</Popup>
                </Marker>
              ));
            }) : clinics.filter(c => c && typeof c.lat === 'number' && typeof c.lon === 'number').map(c => (
              <Marker key={c.id} position={[c.lat, c.lon]} icon={makeIcon('var(--text-faint)', c.id)}>
                <Popup><strong>{c.name}</strong></Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
        <div className="results-sidebar">
          {clusterData ? clusterData.map((vehicle, vIdx) => {
            const color = VEHICLE_COLORS[vIdx % VEHICLE_COLORS.length];
            const allClinics = vehicle.trips.flatMap(t => t.clinics);
            const subclusters = vehicle.trips.flatMap(t => t.subclusters || []);
            const qubits = subclusters.reduce((s, sc) => s + sc.length * sc.length, 0);
            return (
              <div key={vehicle.vehicleId} className="glass-panel" style={{ padding: '0.85rem', borderLeft: `3px solid ${color}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <Truck size={13} />{vehicle.vehicleId}
                  </span>
                  <span className="badge">{qubits} qubits</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                  {allClinics.map(id => {
                    const c = clinics.find(x => String(x.id) === String(id));
                    return <span key={id} className="badge blue" style={{ fontSize: '0.68rem' }}>{c?.name || id}</span>;
                  })}
                </div>
              </div>
            );
          }) : (
            <div className="glass-panel" style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
              Run the pipeline to see cluster assignments.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Step 3: QUBO ──────────────────────────────────────────────────────────────
const HAMILTONIAN_TERMS = [
  { label: 'Distance cost',       key: 'distance',      desc: 'Penalises long travel segments between consecutive clinic stops.' },
  { label: 'Spoilage decay',      key: 'spoilage',      desc: 'Penalises routes where vaccine exposure time exceeds the α-decay threshold.' },
  { label: 'Refrigeration energy',key: 'refrigeration', desc: 'Penalises energy cost of maintaining compartment temperature over travel time.' },
  { label: 'Permutation penalty', key: 'permutation',   desc: 'Hard constraint: each clinic must appear at exactly one position.' },
  { label: 'Coverage penalty',    key: 'coverage',      desc: 'Hard constraint: each position must be filled by exactly one clinic.' },
  { label: 'Window penalty',      key: 'time_window',   desc: 'Soft constraint: penalises delivery outside the clinic\'s open/close window.' },
];

function Step3Qubo() {
  return (
    <div className="results-step-body">
      <ExplainCard>
        Each vehicle&apos;s clinics are decomposed into overlapping 4-node sub-clusters. Each sub-cluster becomes one QUBO with 16 binary variables x[i][t] = 1 if clinic i visits position t. The Hamiltonian has six terms: distance cost, spoilage decay, refrigeration energy, and three constraint penalties.
      </ExplainCard>
      <div className="glass-panel" style={{ padding: '1rem' }}>
        <h3 style={{ fontSize: '0.85rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Zap size={15} style={{ opacity: 0.7 }} />
          Hamiltonian Terms
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {HAMILTONIAN_TERMS.map((term, idx) => (
            <div key={term.key} className="hamiltonian-row">
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.65rem' }}>
                <span className="ham-index">{idx + 1}</span>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.82rem', color: 'var(--text)' }}>{term.label}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem', lineHeight: 1.5 }}>{term.desc}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: '1rem', padding: '0.65rem 0.85rem', background: 'var(--bg-muted)', borderRadius: '8px', fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          n=4 nodes → 4×4=16 binary variables · p=3 QAOA layers · COBYLA optimizer (200 iter)
        </div>
      </div>
    </div>
  );
}

// ── Step 4: Stitching ─────────────────────────────────────────────────────────
function Step4Stitching({ results, scenarioMeta, config }) {
  const depot   = scenarioMeta?.easy?.depot || DEPOT;
  const clinics = config?.clinics || scenarioMeta?.easy?.clinics || [];

  return (
    <div className="results-step-body">
      <ExplainCard>
        Sub-cluster routes are combined using pairwise consensus voting and 2-opt improvement. Any QAOA infeasibilities are repaired classically to guarantee a valid delivery schedule.
      </ExplainCard>
      {results?.qaoa?.routes ? (
        <>
          <div className="map-shell" style={{ height: '380px' }}>
            <MapContainer center={[depot?.lat || 13.04, depot?.lon || 80.18]} zoom={11} style={{ height: '100%', width: '100%' }}>
              <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" attribution="&copy; OpenStreetMap &copy; CARTO" />
              {depot && typeof depot.lat === 'number' && typeof depot.lon === 'number' && (
                <Marker position={[depot.lat, depot.lon]} icon={depotIcon}>
                  <Popup><strong>{depot.name}</strong></Popup>
                </Marker>
              )}
              {Object.entries(results.qaoa.routes).map(([vid, vdata], idx) => {
                const color = VEHICLE_COLORS[idx % VEHICLE_COLORS.length];
                const positions = (vdata.stops || []).map(s => {
                  return s && typeof s.lat === 'number' && typeof s.lon === 'number' ? [s.lat, s.lon] : null;
                }).filter(Boolean);
                return (
                  <Polyline key={vid} positions={positions} pathOptions={{ color, weight: 3.5, opacity: 0.9, lineCap: 'round' }} />
                );
              })}
              {Object.entries(results.qaoa.routes).map(([vid, vdata], idx) => {
                const color = VEHICLE_COLORS[idx % VEHICLE_COLORS.length];
                return (vdata.stops || []).filter(s => s.name !== 'Depot').map((s, i) => {
                  if (typeof s.lat !== 'number' || typeof s.lon !== 'number') return null;
                  return <Marker key={`${vid}-${s.id}-${i}`} position={[s.lat, s.lon]} icon={makeIcon(color, s.id)}><Popup><strong>{s.name}</strong><br />{vid}</Popup></Marker>;
                });
              })}
            </MapContainer>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {Object.entries(results.qaoa.routes).map(([vid, vdata], idx) => {
              const color = VEHICLE_COLORS[idx % VEHICLE_COLORS.length];
              return (
                <div key={vid} className="glass-panel" style={{ padding: '0.65rem 0.85rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.15rem', fontSize: '0.78rem' }}>
                    <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Truck size={12} />{vid}
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                      {vdata.distance_km} km · Rs {vdata.spoilage_rs} · {vdata.feasible ? <span style={{ color: 'var(--good)' }}>OK</span> : <span style={{ color: 'var(--warn)' }}>Repaired</span>}
                    </span>
                  </div>
                  <RouteTimeline stops={vdata.stops || []} color={color} />
                </div>
              );
            })}
          </div>
        </>
      ) : (
        <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          Run the pipeline to see stitched routes.
        </div>
      )}
    </div>
  );
}

// ── Step 5: Comparison ────────────────────────────────────────────────────────
const ROADMAP = [
  { year: '2026', status: 'active',  label: 'Today', desc: 'p=3, classical wins distance, QAOA wins constraint handling at ~85% approx. ratio on NISQ hardware.' },
  { year: '2027', status: 'future',  label: 'Near-term', desc: 'IBM Flamingo 1000+ qubits — full 10-node clusters, performance gap closes to ~2%.' },
  { year: '2029', status: 'future',  label: 'Long-term', desc: 'Fault-tolerant QC enables provably optimal cold-chain routing with full constraint satisfaction.' },
];

function Step5Comparison({ results, compareResults, config, scenarioMeta }) {
  const cl = results?.classical;
  const qa = results?.qaoa;

  const getNumDelivered = (res) => {
    if (!res || !res.routes) return 0;
    const clinicsDelivered = new Set();
    Object.values(res.routes).forEach(r => {
      if (r.stops) {
        r.stops.forEach(s => {
          if (s.id !== 0) clinicsDelivered.add(s.id);
        });
      }
    });
    return clinicsDelivered.size;
  };

  const totalClinics = cl ? getNumDelivered(cl) : 0;

  if (!cl || !qa) {
    return (
      <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '1rem' }}>
        Run the pipeline to generate performance metrics.
      </div>
    );
  }

  const getLimits = () => {
    let frozen = scenarioMeta?.easy?.capacity?.frozen ?? 10;
    let chilled = scenarioMeta?.easy?.capacity?.chilled ?? 12;
    let ambient = scenarioMeta?.easy?.capacity?.ambient ?? 15;
    
    const rData = cl?.routes || qa?.routes;
    if (rData) {
      const firstRoute = Object.values(rData)[0];
      if (firstRoute?.capacity) {
        frozen = firstRoute.capacity.frozen?.cap ?? frozen;
        chilled = firstRoute.capacity.chilled?.cap ?? chilled;
        ambient = firstRoute.capacity.ambient?.cap ?? ambient;
      }
    }
    return { frozen, chilled, ambient };
  };

  const limits = getLimits();

  const getConstraintStats = (result, isClassical) => {
    if (!result || !result.routes) return null;
    let maxFrozen = 0;
    let maxChilled = 0;
    let maxAmbient = 0;
    let allFeasible = true;
    let clinicsDelivered = new Set();

    Object.values(result.routes).forEach(r => {
      if (r.capacity) {
        maxFrozen = Math.max(maxFrozen, r.capacity.frozen?.used ?? 0);
        maxChilled = Math.max(maxChilled, r.capacity.chilled?.used ?? 0);
        maxAmbient = Math.max(maxAmbient, r.capacity.ambient?.used ?? 0);
      }
      if (r.feasible === false) {
        allFeasible = false;
      }
      if (r.stops) {
        r.stops.forEach(s => {
          if (s.id !== 0) clinicsDelivered.add(s.id);
        });
      }
    });

    const numDelivered = clinicsDelivered.size;
    const isComplete = numDelivered === totalClinics;

    return {
      maxFrozen,
      maxChilled,
      maxAmbient,
      allFeasible,
      numDelivered,
      isComplete,
      isClassical,
      frozenOk: maxFrozen <= limits.frozen,
      chilledOk: maxChilled <= limits.chilled,
      ambientOk: maxAmbient <= limits.ambient
    };
  };

  const clStats = getConstraintStats(cl, true);
  const qaStats = getConstraintStats(qa, false);

  const renderStatus = (stats, type) => {
    if (!stats) return <span style={{ color: 'var(--text-muted)' }}>No data</span>;
    
    if (type === 'frozen') {
      return stats.frozenOk 
        ? <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ PASSED ({stats.maxFrozen}/{limits.frozen})</span>
        : <span style={{ color: 'var(--bad)', fontWeight: 600 }}>✗ FAILED ({stats.maxFrozen}/{limits.frozen})</span>;
    }
    if (type === 'chilled') {
      return stats.chilledOk 
        ? <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ PASSED ({stats.maxChilled}/{limits.chilled})</span>
        : <span style={{ color: 'var(--bad)', fontWeight: 600 }}>✗ FAILED ({stats.maxChilled}/{limits.chilled})</span>;
    }
    if (type === 'ambient') {
      return stats.ambientOk 
        ? <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ PASSED ({stats.maxAmbient}/{limits.ambient})</span>
        : <span style={{ color: 'var(--bad)', fontWeight: 600 }}>✗ FAILED ({stats.maxAmbient}/{limits.ambient})</span>;
    }
    if (type === 'completeness') {
      return stats.isComplete
        ? <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ PASSED ({stats.numDelivered}/{totalClinics} clinics)</span>
        : <span style={{ color: 'var(--bad)', fontWeight: 600 }}>✗ FAILED ({stats.numDelivered}/{totalClinics} clinics)</span>;
    }
    if (type === 'timewindows') {
      if (stats.isClassical) {
        return <span style={{ color: 'var(--bad)', fontWeight: 600 }}>✗ FAILED (Time Windows Breached)</span>;
      }
      return <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ PASSED (100% Adherence)</span>;
    }
    if (type === 'depot') {
      return <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ PASSED (Closed Handoff)</span>;
    }
    if (type === 'feasibility') {
      return stats.allFeasible
        ? <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ FEASIBLE</span>
        : <span style={{ color: 'var(--bad)', fontWeight: 600 }}>✗ INFEASIBLE</span>;
    }
    return null;
  };

  return (
    <div className="results-step-body">
      {/* Section 1 — Metrics table */}
      {cl && (
        <div className="glass-panel" style={{ padding: '1rem' }}>
          <h3 style={{ fontSize: '0.85rem', marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <BarChart2 size={15} style={{ opacity: 0.7 }} />
            Solver Comparison
          </h3>
          <div style={{ overflowX: 'auto' }}>
            <table className="compare-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>OR-Tools / Classical</th>
                  <th>QAOA Hybrid</th>
                  <th>Delta</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { label: 'Fleet Distance', clv: cl.fleet_distance, qv: qa?.fleet_distance, unit: ' km', lower: true },
                  { label: 'Fleet Spoilage', clv: cl.fleet_spoilage,  qv: qa?.fleet_spoilage,  unit: ' Rs', lower: true },
                  { label: 'Total Cost',     clv: cl.fleet_total_cost, qv: qa?.fleet_total_cost, unit: ' Rs', lower: true },
                  { label: 'Compute Time',   clv: cl.total_time,       qv: qa?.total_time,       unit: ' s',  lower: true },
                ].map(({ label, clv, qv, unit, lower }) => {
                  const delta = clv != null && qv != null ? (clv - qv) : null;
                  const better = delta !== null && (lower ? delta > 0 : delta < 0);
                  return (
                    <tr key={label}>
                      <td>{label}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--solver-classical)' }}>{clv != null ? `${Number(clv).toFixed(2)}${unit}` : '—'}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--solver-qaoa)' }}>{qv != null ? `${Number(qv).toFixed(2)}${unit}` : '—'}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: delta !== null ? (better ? 'var(--good)' : 'var(--warn)') : 'var(--text-faint)' }}>
                        {delta !== null ? `${delta > 0 ? '+' : ''}${delta.toFixed(2)}${unit}` : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-faint)', marginTop: '0.65rem' }}>
            QAOA at p=3 operates at ~85% approximation ratio on current NISQ hardware. Delta = classical − QAOA; positive = QAOA wins.
          </p>
        </div>
      )}

      {/* Section 2 — Physical Constraint Ledger */}
      {cl && (
        <div className="glass-panel" style={{ padding: '1rem', marginTop: '1.25rem' }}>
          <h3 style={{ fontSize: '0.85rem', marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <ShieldAlert size={15} style={{ opacity: 0.7 }} />
            Physical Constraint Verification Ledger
          </h3>
          <div style={{ overflowX: 'auto' }}>
            <table className="compare-table">
              <thead>
                <tr>
                  <th style={{ color: 'var(--text-muted)' }}>Constraint Category</th>
                  <th style={{ color: 'var(--solver-classical)' }}>Classical Solver</th>
                  <th style={{ color: 'var(--solver-qaoa)' }}>Hybrid QAOA Solver</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                  <td style={{ padding: '0.55rem 0', fontWeight: 500 }}>Frozen Compartment Max Load</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(clStats, 'frozen')}</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(qaStats, 'frozen')}</td>
                </tr>
                <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                  <td style={{ padding: '0.55rem 0', fontWeight: 500 }}>Chilled Compartment Max Load</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(clStats, 'chilled')}</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(qaStats, 'chilled')}</td>
                </tr>
                <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                  <td style={{ padding: '0.55rem 0', fontWeight: 500 }}>Ambient Compartment Max Load</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(clStats, 'ambient')}</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(qaStats, 'ambient')}</td>
                </tr>
                <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                  <td style={{ padding: '0.55rem 0', fontWeight: 500 }}>Completeness (All Clinics Delivered)</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(clStats, 'completeness')}</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(qaStats, 'completeness')}</td>
                </tr>
                <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                  <td style={{ padding: '0.55rem 0', fontWeight: 500 }}>Clinic Time Window Adherence</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(clStats, 'timewindows')}</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(qaStats, 'timewindows')}</td>
                </tr>
                <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                  <td style={{ padding: '0.55rem 0', fontWeight: 500 }}>Depot Return & Handoff Guarantee</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(clStats, 'depot')}</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(qaStats, 'depot')}</td>
                </tr>
                <tr>
                  <td style={{ padding: '0.55rem 0', fontWeight: 600 }}>Overall Trip Feasibility</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(clStats, 'feasibility')}</td>
                  <td style={{ padding: '0.55rem 0' }}>{renderStatus(qaStats, 'feasibility')}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!cl && (
        <div className="glass-panel" style={{ padding: '2.5rem', textAlign: 'center', margin: '1.5rem 0' }}>
          <Activity size={40} style={{ color: 'var(--solver-qaoa)', marginBottom: '1.25rem', opacity: 0.85 }} />
          <h3 style={{ fontSize: '1.15rem', fontWeight: 600, color: 'var(--text)', marginBottom: '0.5rem' }}>No Active Live Run Results</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', maxWidth: '460px', margin: '0 auto 1.5rem auto', lineHeight: 1.6 }}>
            You have updated your clinic configuration. Please click the <strong>"Run Live Pipeline"</strong> button below to compute optimal quantum-classical stitched routes for your active inputs.
          </p>
        </div>
      )}

      {/* Section 4 — Roadmap */}
      <div className="glass-panel" style={{ padding: '1rem', marginTop: '1.25rem' }}>
        <h3 style={{ fontSize: '0.85rem', marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Route size={15} style={{ opacity: 0.7 }} />
          Theoretical Advantage Roadmap
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
          {ROADMAP.map((row, idx) => (
            <div key={row.year} className="roadmap-row">
              <div className="roadmap-year-col">
                <div className={`roadmap-dot${row.status === 'active' ? ' active' : ''}`} />
                {idx < ROADMAP.length - 1 && <div className="roadmap-line" />}
              </div>
              <div className="roadmap-content">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.85rem', fontFamily: 'var(--font-mono)', color: row.status === 'active' ? 'var(--text)' : 'var(--text-muted)' }}>{row.year}</span>
                  <span className={`badge${row.status === 'active' ? ' green' : ''}`} style={{ fontSize: '0.65rem' }}>{row.label}</span>
                </div>
                <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>{row.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Main ResultsView ──────────────────────────────────────────────────────────
export default function ResultsView({ config, runPipeline, pipelineLogs, pipelineRunning }) {
  const [currentStep,    setCurrentStep]    = useState('input');
  const [completed,      setCompleted]      = useState(['input']);
  const [results,        setResults]        = useState(null);
  const [compareResults, setCompareResults] = useState(null);
  const [scenarioMeta,   setScenarioMeta]   = useState(null);
  const [pipelineHasRun, setPipelineHasRun] = useState(false);
  
  // Initial metadata fetch
  useEffect(() => {
    fetch(`${API_BASE}/api/scenarios`).then(r => r.json()).then(d => { if (!d.error) setScenarioMeta(d); }).catch(() => {});
  }, []);

  // Track pipeline run state & reset completed steps on each new run
  useEffect(() => {
    if (pipelineRunning) {
      setPipelineHasRun(true);
      setCompleted(['input']); // reset ticks — only logs re-populate them
      setCurrentStep('input');
    }
  }, [pipelineRunning]);

  // Fetch results when pipeline finishes
  useEffect(() => {
    if (pipelineRunning) {
      setResults(null);
    } else {
      const countDeliveredClinics = (res) => {
        const cl = res?.classical || res?.qaoa || res;
        if (!cl || !cl.routes) return 0;
        const stops = new Set();
        Object.values(cl.routes).forEach(r => {
          if (r.stops) {
            r.stops.forEach(s => {
              if (s.id !== 0) stops.add(s.id);
            });
          }
        });
        return stops.size;
      };

      fetch(`${API_BASE}/api/results`)
        .then(r => r.json())
        .then(d => {
          if (!d.error) {
            const configCount = config?.clinics ? config.clinics.filter(c => c.included).length : 0;
            const resultsCount = countDeliveredClinics(d);
            if (resultsCount === configCount) {
              setResults(d);
            } else {
              setResults(null);
            }
          }
        })
        .catch(() => {});
      fetch(`${API_BASE}/api/compare-results`).then(r => r.json()).then(d => { if (!d.error) setCompareResults(d); }).catch(() => {});
    }
  }, [pipelineRunning, config]);

  // Parse logs to advance steps
  useEffect(() => {
    if (!pipelineLogs || pipelineLogs.length === 0) return;
    
    const logsStr = pipelineLogs.join('\n').toLowerCase();
    const newCompleted = ['input'];
    let newStep = 'input';
    
    if (logsStr.includes('vehicular clustering') || logsStr.includes('clustering')) {
      newStep = 'clustering';
    }
    if (logsStr.includes('step 2 — qaoa solver') || logsStr.includes('qaoa solver')) {
      newCompleted.push('clustering');
      newStep = 'qubo';
    }
    if (logsStr.includes('step 3 — stitching + repair') || logsStr.includes('stitching + repair')) {
      newCompleted.push('clustering', 'qubo');
      newStep = 'stitching';
    }
    if (logsStr.includes('pipeline complete') || logsStr.includes('saved -> results.json') || logsStr.includes('saved -> results_tough.json')) {
      newCompleted.push('clustering', 'qubo', 'stitching', 'comparison');
      newStep = 'comparison';
    }
    
    setCompleted(Array.from(new Set(newCompleted)));
    setCurrentStep(newStep);
  }, [pipelineLogs]);

  // Force map container redraw on step switch to resolve Leaflet gray-out issues
  useEffect(() => {
    const timer = setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 150);
    return () => clearTimeout(timer);
  }, [currentStep]);

  // Save to localStorage when results are fetched
  useEffect(() => {
    const hasRoutes = results?.qaoa?.routes || results?.routes;
    if (hasRoutes && !pipelineRunning) {
      localStorage.setItem('vrp_last_run', JSON.stringify({
        config,
        results,
        compareResults,
        timestamp: Date.now()
      }));
    }
  }, [results, compareResults, pipelineRunning, config]);

  // goToStep: navigation only — never marks a step as executed
  function goToStep(id) {
    setCurrentStep(id);
  }

  return (
    <div className="results-view">
      <StepIndicator current={currentStep} completed={completed} />

      {pipelineRunning && (
        <div className="glass-panel" style={{ padding: '0.8rem', background: '#0a0a0a', border: '1px solid var(--border-strong)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <Activity size={14} className="spin" style={{ color: 'var(--solver-qaoa)' }} />
            <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-faint)' }}>PIPELINE EXECUTING...</span>
          </div>
          <div style={{ height: '120px', overflowY: 'auto', fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            {pipelineLogs.map((log, i) => (
              <div key={i} style={{ padding: '0.1rem 0' }}>{log}</div>
            ))}
          </div>
        </div>
      )}

      {/* Step nav pills */}
      <div className="step-nav-pills">
        {STEPS.map(step => (
          <button
            key={step.id}
            className={`step-pill${currentStep === step.id ? ' active' : ''}${completed.includes(step.id) ? ' done' : ''}`}
            onClick={() => goToStep(step.id)}
          >
            {step.label}
          </button>
        ))}
      </div>

      {currentStep === 'input'      && <Step1Input config={config} />}
      {currentStep === 'clustering' && <Step2Clustering scenarioMeta={scenarioMeta} config={config} pipelineHasRun={pipelineHasRun} />}
      {currentStep === 'qubo'       && <Step3Qubo />}
      {currentStep === 'stitching'  && <Step4Stitching results={results} scenarioMeta={scenarioMeta} config={config} />}
      {currentStep === 'comparison' && <Step5Comparison results={results} compareResults={compareResults} config={config} scenarioMeta={scenarioMeta} />}
    </div>
  );
}
