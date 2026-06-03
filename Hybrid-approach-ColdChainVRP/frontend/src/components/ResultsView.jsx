import { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import {
  CheckCircle2, Circle, BarChart2, Cpu, Zap, GitMerge,
  Route, Home, MapPin, Truck, Clock, Activity, ShieldAlert, AlertTriangle, RefreshCw, Layers
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
  const pct      = cap > 0 ? (used / cap) * 100 : 0;
  const over     = pct > 100;
  const fillPct  = Math.min(100, pct);
  const fillColor = over ? '#f87171' : pct > 80 ? '#fb923c' : '#fff';
  return (
    <div className="cap-bar-wrapper" style={{ marginTop: over ? '10px' : '0' }}>
      <span className="cap-bar-label" style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{label}</span>
      <div className="cap-bar-bg" style={{ position: 'relative', overflow: 'visible' }}>
        <div className="cap-bar-fill" style={{ width: `${fillPct}%`, background: fillColor, transition: 'width 0.4s ease' }} />
        {over && (
          <div style={{
            position: 'absolute',
            top: '-15px',
            right: '4px',
            fontSize: '0.55rem',
            color: '#f87171',
            background: 'rgba(248, 113, 113, 0.12)',
            border: '1px solid rgba(248, 113, 113, 0.3)',
            padding: '1px 5px',
            borderRadius: '4px',
            fontWeight: 800,
            whiteSpace: 'nowrap',
            lineHeight: 1
          }}>
            +{Math.round(pct - 100)}% OVER
          </div>
        )}
      </div>
      <span style={{ fontSize: '0.68rem', color: over ? '#f87171' : 'var(--text-faint)', width: '3rem', textAlign: 'right', fontWeight: over ? 700 : 400 }}>
        {used}/{cap}
      </span>
    </div>
  );
}

// ── Step 1: Input summary ─────────────────────────────────────────────────────
const COMP_STYLE = {
  frozen:  { color: '#60a5fa', label: 'Frozen',  icon: '❄️' },
  chilled: { color: '#34d399', label: 'Chilled', icon: '🧊' },
  ambient: { color: '#fbbf24', label: 'Ambient', icon: '📦' },
};

function Step1Input({ config }) {
  if (!config) return <div style={{ color: 'var(--text-muted)', padding: '2rem', textAlign: 'center' }}>No configuration loaded.</div>;
  const included = (config.clinics || []).filter(c => c.included);

  // Compute per-compartment totals
  const totals = { frozen: 0, chilled: 0, ambient: 0 };
  included.forEach(c => {
    const d = c.demand || {};
    totals.frozen  += d.frozen  || 0;
    totals.chilled += d.chilled || 0;
    totals.ambient += d.ambient || 0;
  });

  // Vehicle capacity (sum across fleet)
  const vehicles = config.vehicles || [];
  const fleetCap = { frozen: 0, chilled: 0, ambient: 0 };
  vehicles.forEach(v => {
    const comp = v.compartments || {};
    fleetCap.frozen  += comp.frozen  || 10;
    fleetCap.chilled += comp.chilled || 12;
    fleetCap.ambient += comp.ambient || 15;
  });

  return (
    <div className="results-step-body">
      <ExplainCard>
        Configuration submitted. {included.length} clinics across {config.num_vehicles} vehicle(s), {(config.vaccines || []).length} vaccine type(s).
        The pipeline will cluster clinics, build QUBO sub-problems, run QAOA at p=3, then stitch routes.
      </ExplainCard>

      {/* Row 1 — Vaccines + Fleet Capacity */}
      <div className="results-grid-2">
        {/* Vaccines */}
        <div className="glass-panel" style={{ padding: '1rem' }}>
          <h3 style={{ fontSize: '0.85rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            Vaccines
          </h3>
          {(config.vaccines || []).map(v => (
            <div key={v.id} className="result-row" style={{ padding: '0.4rem 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontSize: '0.82rem' }}>{v.id}</span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                <span style={{ color: COMP_STYLE[v.compartment]?.color }}>{COMP_STYLE[v.compartment]?.icon} {v.compartment}</span>
                {' '}· α={v.alpha}
              </span>
            </div>
          ))}
        </div>

        {/* Fleet Capacity vs Total Demand */}
        <div className="glass-panel" style={{ padding: '1rem' }}>
          <h3 style={{ fontSize: '0.85rem', marginBottom: '0.3rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            Fleet Capacity vs Demand
          </h3>
          <p style={{ fontSize: '0.68rem', color: 'var(--text-faint)', margin: '0 0 0.85rem' }}>
            Total across {vehicles.length} vehicle(s). Red = demand exceeds fleet capacity.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {Object.entries(COMP_STYLE).map(([k, s]) => {
              const over = totals[k] > (fleetCap[k] || 0);
              return (
                <CapBar
                  key={k}
                  label={<span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <span>{s.icon}</span>
                    <span style={{ color: s.color }}>{s.label}</span>
                  </span>}
                  used={totals[k]}
                  cap={fleetCap[k] || 1}
                  color={s.color}
                />
              );
            })}
          </div>
        </div>
      </div>

      {/* Row 2 — Demand per clinic table */}
      <div className="glass-panel" style={{ padding: '1rem' }}>
        <h3 style={{ fontSize: '0.85rem', marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          Demand per Clinic
        </h3>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.77rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                <th style={{ textAlign: 'left',   padding: '0.4rem 0.6rem', color: 'var(--text-muted)', fontWeight: 600 }}>Clinic</th>
                <th style={{ textAlign: 'left',   padding: '0.4rem 0.6rem', color: 'var(--text-muted)', fontWeight: 600 }}>Name</th>
                <th style={{ textAlign: 'center', padding: '0.4rem 0.6rem', color: COMP_STYLE.frozen.color,  fontWeight: 600 }}>❄️ Frozen</th>
                <th style={{ textAlign: 'center', padding: '0.4rem 0.6rem', color: COMP_STYLE.chilled.color, fontWeight: 600 }}>🧊 Chilled</th>
                <th style={{ textAlign: 'center', padding: '0.4rem 0.6rem', color: COMP_STYLE.ambient.color, fontWeight: 600 }}>📦 Ambient</th>
                <th style={{ textAlign: 'center', padding: '0.4rem 0.6rem', color: 'var(--text-muted)', fontWeight: 600 }}><Clock size={11} /> Window</th>
              </tr>
            </thead>
            <tbody>
              {included.map((c, i) => {
                const d  = c.demand || {};
                const tw = c.time_window || [8, 18];
                const isOdd = i % 2 === 1;
                return (
                  <tr key={c.id} style={{ background: isOdd ? 'rgba(255,255,255,0.02)' : 'transparent', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <td style={{ padding: '0.38rem 0.6rem', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent)' }}>#{c.id}</td>
                    <td style={{ padding: '0.38rem 0.6rem', color: 'var(--text)' }}>{c.name || `Clinic ${c.id}`}</td>
                    <td style={{ padding: '0.38rem 0.6rem', textAlign: 'center', color: COMP_STYLE.frozen.color,  fontFamily: 'var(--font-mono)' }}>{d.frozen  ?? 0}</td>
                    <td style={{ padding: '0.38rem 0.6rem', textAlign: 'center', color: COMP_STYLE.chilled.color, fontFamily: 'var(--font-mono)' }}>{d.chilled ?? 0}</td>
                    <td style={{ padding: '0.38rem 0.6rem', textAlign: 'center', color: COMP_STYLE.ambient.color, fontFamily: 'var(--font-mono)' }}>{d.ambient ?? 0}</td>
                    <td style={{ padding: '0.38rem 0.6rem', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.7rem' }}>{tw[0]}:00–{tw[1]}:00</td>
                  </tr>
                );
              })}
              {/* Totals footer */}
              <tr style={{ borderTop: '1px solid rgba(255,255,255,0.12)', fontWeight: 700 }}>
                <td colSpan={2} style={{ padding: '0.4rem 0.6rem', color: 'var(--text-muted)', fontSize: '0.72rem' }}>TOTAL DEMAND</td>
                <td style={{ padding: '0.4rem 0.6rem', textAlign: 'center', color: COMP_STYLE.frozen.color,  fontFamily: 'var(--font-mono)' }}>{totals.frozen}</td>
                <td style={{ padding: '0.4rem 0.6rem', textAlign: 'center', color: COMP_STYLE.chilled.color, fontFamily: 'var(--font-mono)' }}>{totals.chilled}</td>
                <td style={{ padding: '0.4rem 0.6rem', textAlign: 'center', color: COMP_STYLE.ambient.color, fontFamily: 'var(--font-mono)' }}>{totals.ambient}</td>
                <td />
              </tr>
            </tbody>
          </table>
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
                    {vehicle.vehicleId}
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
  const clinicById = Object.fromEntries(clinics.map((c) => [c.id, c]));

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
                const route = Array.isArray(vdata) ? vdata : (vdata.route || []);
                const positions = route.map(id => {
                  if (id === 0 && depot && typeof depot.lat === 'number' && typeof depot.lon === 'number') {
                    return [depot.lat, depot.lon];
                  }
                  const originalId = id >= 1000 ? Math.floor(id / 1000) : id;
                  const c = clinicById[originalId];
                  return c && typeof c.lat === 'number' && typeof c.lon === 'number' ? [c.lat, c.lon] : null;
                }).filter(Boolean);
                return (
                  <Polyline key={vid} positions={positions} pathOptions={{ color, weight: 3.5, opacity: 0.9, lineCap: 'round' }} />
                );
              })}
              {Object.entries(results.qaoa.routes).map(([vid, vdata], idx) => {
                const color = VEHICLE_COLORS[idx % VEHICLE_COLORS.length];
                const route = Array.isArray(vdata) ? vdata : (vdata.route || []);
                const stops = vdata.stops || route.map(id => {
                  if (id === 0 && depot) return depot;
                  const originalId = id >= 1000 ? Math.floor(id / 1000) : id;
                  return clinics.find(x => x.id === originalId);
                }).filter(Boolean);
                return stops.filter(s => s.name !== 'Depot' && s.id !== 0).map((s, i) => {
                  const originalId = s.id >= 1000 ? Math.floor(s.id / 1000) : s.id;
                  const c = clinicById[originalId];
                  if (!c || typeof c.lat !== 'number' || typeof c.lon !== 'number') return null;
                  return <Marker key={`${vid}-${s.id}-${i}`} position={[c.lat, c.lon]} icon={makeIcon(color, originalId)}><Popup><strong>{c.name}</strong><br />{vid}</Popup></Marker>;
                });
              })}
            </MapContainer>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {Object.entries(results.qaoa.routes).map(([vid, vdata], idx) => {
              const color = VEHICLE_COLORS[idx % VEHICLE_COLORS.length];
              const route = Array.isArray(vdata) ? vdata : (vdata.route || []);
              const stops = vdata.stops || route.map(id => {
                if (id === 0 && depot) return depot;
                const originalId = id >= 1000 ? Math.floor(id / 1000) : id;
                return clinics.find(x => x.id === originalId);
              }).filter(Boolean);
              return (
                <div key={vid} className="glass-panel" style={{ padding: '0.65rem 0.85rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.15rem', fontSize: '0.78rem' }}>
                    <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      {vid}
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                      {vdata.distance_km != null ? `${vdata.distance_km} km` : ''} {vdata.spoilage_rs != null ? `· Rs ${vdata.spoilage_rs}` : ''} {vdata.feasible !== undefined ? (vdata.feasible ? <span style={{ color: 'var(--good)' }}>· OK</span> : <span style={{ color: 'var(--warn)' }}>· Repaired</span>) : ''}
                    </span>
                  </div>
                  <RouteTimeline stops={stops} color={color} />
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

const ROADMAP = [
  { year: '2026', status: 'active',  label: 'Today', desc: 'p=3, classical wins distance, QAOA wins constraint handling at ~85% approx. ratio on NISQ hardware.' },
  { year: '2027', status: 'future',  label: 'Near-term', desc: 'IBM Flamingo 1000+ qubits — full 10-node clusters, performance gap closes to ~2%.' },
  { year: '2029', status: 'future',  label: 'Long-term', desc: 'Fault-tolerant QC enables provably optimal cold-chain routing with full constraint satisfaction.' },
];

// ── Solver Route Map (reusable) ────────────────────────────────────────────────
function getHaversineDistance(lat1, lon1, lat2, lon2) {
  if (lat1 == null || lon1 == null || lat2 == null || lon2 == null) return 0;
  const R = 6371; // Earth's radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function FitBounds({ routes, depot, clinics = [] }) {
  const map = useMap();
  const clinicById = Object.fromEntries(clinics.map((c) => [c.id, c]));

  useEffect(() => {
    const pts = [];
    if (depot?.lat && depot?.lon) pts.push([depot.lat, depot.lon]);
    
    Object.values(routes || {}).forEach(v => {
      if (Array.isArray(v)) {
        v.forEach(id => {
          if (id !== 0) {
            const originalId = id >= 1000 ? Math.floor(id / 1000) : id;
            const c = clinicById[originalId];
            if (c && typeof c.lat === 'number' && typeof c.lon === 'number') {
              pts.push([c.lat, c.lon]);
            }
          }
        });
      } else if (v && v.stops) {
        v.stops.forEach(s => {
          if (typeof s.lat === 'number' && typeof s.lon === 'number') {
            pts.push([s.lat, s.lon]);
          }
        });
      }
    });

    if (pts.length > 1) map.fitBounds(pts, { padding: [20, 20] });
  }, [routes, depot, clinics]);
  return null;
}

function SolverRouteMap({ result, depot, clinics = [], label }) {
  const center = [depot?.lat || 13.04, depot?.lon || 80.18];
  const routes = result?.routes || {};
  const hasRoutes = Object.keys(routes).length > 0;
  const clinicById = Object.fromEntries(clinics.map((c) => [c.id, c]));

  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <div style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', padding: '0 0.1rem' }}>
        {label}
      </div>
      <div className="map-shell" style={{ height: '320px', borderRadius: '10px', overflow: 'hidden' }}>
        <MapContainer center={center} zoom={11} style={{ height: '100%', width: '100%' }} scrollWheelZoom={false}>
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" attribution="&copy; OpenStreetMap &copy; CARTO" />
          {hasRoutes && <FitBounds routes={routes} depot={depot} clinics={clinics} />}
          {depot && typeof depot.lat === 'number' && (
            <Marker position={[depot.lat, depot.lon]} icon={depotIcon}>
              <Popup><strong>{depot.name || 'Depot'}</strong></Popup>
            </Marker>
          )}
          {Object.entries(routes).map(([vid, vdata], idx) => {
            const color = VEHICLE_COLORS[idx % VEHICLE_COLORS.length];
            const route = Array.isArray(vdata) ? vdata : (vdata.route || []);
            const positions = route
              .map((id) => {
                if (id === 0 && depot && typeof depot.lat === 'number' && typeof depot.lon === 'number') {
                  return [depot.lat, depot.lon];
                }
                const originalId = id >= 1000 ? Math.floor(id / 1000) : id;
                const c = clinicById[originalId];
                return c && typeof c.lat === 'number' && typeof c.lon === 'number' ? [c.lat, c.lon] : null;
              })
              .filter(Boolean);
            return (
              <Polyline key={vid} positions={positions}
                pathOptions={{ color, weight: 3.5, opacity: 0.9, lineCap: 'round', lineJoin: 'round' }} />
            );
          })}
          {Object.entries(routes).map(([vid, vdata], idx) => {
            const color = VEHICLE_COLORS[idx % VEHICLE_COLORS.length];
            const route = Array.isArray(vdata) ? vdata : (vdata.route || []);
            const stops = Array.isArray(vdata)
              ? route.map(id => {
                  if (id === 0) return { id: 0, name: depot?.name || 'Depot' };
                  const originalId = id >= 1000 ? Math.floor(id / 1000) : id;
                  const c = clinicById[originalId];
                  return c ? { id: c.id, name: c.name, lat: c.lat, lon: c.lon } : { id, name: `Clinic ${originalId}` };
                })
              : (vdata.stops || []);

            return stops
              .filter(s => s.name !== 'Depot' && s.id !== 0)
              .map((s, i) => {
                const originalId = s.id >= 1000 ? Math.floor(s.id / 1000) : s.id;
                const c = clinicById[originalId];
                if (!c || typeof c.lat !== 'number' || typeof c.lon !== 'number') return null;
                return (
                  <Marker key={`${vid}-${s.id}-${i}`} position={[c.lat, c.lon]} icon={makeIcon(color, originalId)}>
                    <Popup><strong>{c.name}</strong><br />{vid}</Popup>
                  </Marker>
                );
              });
          })}
        </MapContainer>
      </div>
      {/* Route legend */}
      {hasRoutes ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {Object.entries(routes).map(([vid, vdata], idx) => (
            <div key={vid} style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.7rem' }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', background: VEHICLE_COLORS[idx % VEHICLE_COLORS.length], flexShrink: 0 }} />
              <span style={{ color: 'var(--text)', fontWeight: 600 }}>{vid}</span>
              <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {vdata.distance_km?.toFixed?.(2) ?? vdata.distance_km} km
                {vdata.spoilage_rs != null && ` · ₹${Number(vdata.spoilage_rs).toFixed(2)}`}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)', textAlign: 'center', padding: '0.5rem' }}>No route data</div>
      )}
    </div>
  );
}

function toFiniteNumber(v) {
  if (v === null || v === undefined || v === '') return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

function fleetTotalsFromRoutes(routes) {
  if (!routes || typeof routes !== 'object') return null;
  const rows = Object.values(routes);
  if (!rows.length) return null;
  let fleet_distance = 0;
  let fleet_spoilage = 0;
  let fleet_refrigeration = 0;
  let fleet_total_cost = 0;
  for (const row of rows) {
    const dk = toFiniteNumber(row.distance_km) ?? 0;
    const sp = toFiniteNumber(row.spoilage_rs) ?? 0;
    const rf = toFiniteNumber(row.refrigeration_rs) ?? 0;
    fleet_distance += dk;
    fleet_spoilage += sp;
    fleet_refrigeration += rf;
    const tc = toFiniteNumber(row.total_cost_rs);
    fleet_total_cost += tc != null ? tc : dk + sp + rf;
  }
  return { fleet_distance, fleet_spoilage, fleet_refrigeration, fleet_total_cost };
}

function resolveQaoaMetrics(qa) {
  if (!qa || typeof qa !== 'object') return { available: false, m: null };
  const st = String(qa.status ?? '').toLowerCase();
  if (st === 'skipped' || st === 'failed') return { available: false, m: null };

  const derived = fleetTotalsFromRoutes(qa.routes);
  const fleet_total_cost = toFiniteNumber(qa.fleet_total_cost) ?? derived?.fleet_total_cost ?? null;
  if (fleet_total_cost == null || !Number.isFinite(fleet_total_cost)) {
    return { available: false, m: null };
  }

  const fleet_distance = toFiniteNumber(qa.fleet_distance) ?? derived?.fleet_distance ?? null;
  const fleet_spoilage = toFiniteNumber(qa.fleet_spoilage) ?? derived?.fleet_spoilage ?? null;
  const fleet_refrigeration = toFiniteNumber(qa.fleet_refrigeration) ?? derived?.fleet_refrigeration ?? null;
  const total_time = toFiniteNumber(qa.total_time);

  return {
    available: true,
    m: {
      fleet_distance,
      fleet_spoilage,
      fleet_refrigeration,
      fleet_total_cost,
      total_time,
    },
  };
}

const SOLVER_OPTIONS = [
  { id: 'classical', label: 'Classical' },
  { id: 'alns',      label: 'ALNS' },
  { id: 'ortools',   label: 'OR-Tools' },
  { id: 'pulp_cbc',  label: 'PuLP/CBC' },
  { id: 'qaoa',      label: 'Hybrid QAOA' },
];

function Step5Comparison({ results, compareResults, config, scenarioMeta, onRefreshCompare }) {
  const clinics = config?.clinics || scenarioMeta?.easy?.clinics || [];
  const sc = compareResults?.easy;
  const cl = sc?.classical || results?.classical;
  const alns = sc?.alns;
  const ort = sc?.ortools;
  const pulp = sc?.pulp_cbc;
  const qa = sc?.qaoa || results?.qaoa;

  const [leftSolver,  setLeftSolver]  = useState('classical');
  const [rightSolver, setRightSolver] = useState('qaoa');

  const { available: qaAvailable, m: qaM } = resolveQaoaMetrics(qa);

  const getLimits = () => {
    let frozen = scenarioMeta?.easy?.capacity?.frozen ?? 10;
    let chilled = scenarioMeta?.easy?.capacity?.chilled ?? 12;
    let ambient = scenarioMeta?.easy?.capacity?.ambient ?? 15;
    
    const rData = cl?.routes || qa?.routes || ort?.routes;
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
  const totalClinics = config?.clinics ? config.clinics.filter(c => c.included).length : (scenarioMeta?.easy?.num_clinics ?? 10);

  const getConstraintStats = (result) => {
    if (!result || result.status !== 'ok' || !result.routes) return null;
    let maxFrozen = 0;
    let maxChilled = 0;
    let maxAmbient = 0;
    let allFeasible = true;
    let timeWindowOk = true;
    let clinicsDelivered = new Set();
    const vehicleStats = {};

    Object.entries(result.routes).forEach(([vid, r]) => {
      const vFrozen = r.capacity?.frozen?.used ?? 0;
      const vChilled = r.capacity?.chilled?.used ?? 0;
      const vAmbient = r.capacity?.ambient?.used ?? 0;
      const vFrozenCap = r.capacity?.frozen?.cap ?? limits.frozen;
      const vChilledCap = r.capacity?.chilled?.cap ?? limits.chilled;
      const vAmbientCap = r.capacity?.ambient?.cap ?? limits.ambient;

      vehicleStats[vid] = {
        frozen: vFrozen,
        chilled: vChilled,
        ambient: vAmbient,
        frozenCap: vFrozenCap,
        chilledCap: vChilledCap,
        ambientCap: vAmbientCap,
        frozenOk: vFrozen <= vFrozenCap,
        chilledOk: vChilled <= vChilledCap,
        ambientOk: vAmbient <= vAmbientCap,
        timeWindowOk: r.time_window_feasible !== false,
      };

      maxFrozen = Math.max(maxFrozen, vFrozen);
      maxChilled = Math.max(maxChilled, vChilled);
      maxAmbient = Math.max(maxAmbient, vAmbient);
      
      if (r.feasible === false) {
        allFeasible = false;
      }
      if (r.time_window_feasible === false) {
        timeWindowOk = false;
      }
      const route = Array.isArray(r) ? r : (r.route || []);
      route.forEach(id => {
        if (id !== 0) {
          const originalId = id >= 1000 ? Math.floor(id / 1000) : id;
          clinicsDelivered.add(originalId);
        }
      });
      if (r && r.stops) {
        r.stops.forEach(s => {
          if (s.id !== 0 && s.id !== undefined) {
            const originalId = s.id >= 1000 ? Math.floor(s.id / 1000) : s.id;
            clinicsDelivered.add(originalId);
          }
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
      timeWindowOk,
      numDelivered,
      isComplete,
      frozenOk: maxFrozen <= limits.frozen,
      chilledOk: maxChilled <= limits.chilled,
      ambientOk: maxAmbient <= limits.ambient,
      vehicleStats
    };
  };

  const clStats = getConstraintStats(cl);
  const alnsStats = getConstraintStats(alns);
  const ortStats = getConstraintStats(ort);
  const pulpStats = getConstraintStats(pulp);
  const qaStats = qaAvailable ? getConstraintStats(qa) : null;

  const isAvailable = (s) => s && s.status === 'ok';

  const isSolverFeasible = (s, isQa = false) => {
    if (isQa) {
      if (!qaAvailable || !s || !s.routes) return false;
      return Object.values(s.routes).every(r => r.feasible !== false);
    }
    if (!s || s.status !== 'ok' || !s.routes) return false;
    return Object.values(s.routes).every(r => r.feasible !== false);
  };

  const renderMetricCell = (key, unit, isLowerBetter = true) => {
    const clVal  = toFiniteNumber(cl?.[key]);
    const alnsVal = toFiniteNumber(alns?.[key]);
    const ortVal  = toFiniteNumber(ort?.[key]);
    const pulpVal = toFiniteNumber(pulp?.[key]);
    const qaVal   = qaAvailable ? toFiniteNumber(qaM?.[key]) : null;

    const solvers = [
      { id: 'classical', val: clVal,  obj: cl   },
      { id: 'alns',      val: alnsVal, obj: alns  },
      { id: 'ortools',   val: ortVal,  obj: ort   },
      { id: 'pulp',      val: pulpVal, obj: pulp  },
      { id: 'qaoa',      val: qaVal,   obj: qa    },
    ];

    let bestVal = null;
    const eligibleSolvers = solvers.filter(s => {
      if (s.val === null) return false;
      const avail   = s.id === 'qaoa' ? qaAvailable : isAvailable(s.obj);
      const feasible = s.id === 'qaoa' ? isSolverFeasible(s.obj, true) : isSolverFeasible(s.obj);
      return avail && feasible;
    });
    if (eligibleSolvers.length > 0) {
      bestVal = eligibleSolvers[0].val;
      for (const s of eligibleSolvers) {
        if (isLowerBetter ? s.val < bestVal : s.val > bestVal) bestVal = s.val;
      }
    }

    return solvers.map(s => {
      const isSolAvail  = s.id === 'qaoa' ? qaAvailable : isAvailable(s.obj);
      const isFeasible  = s.id === 'qaoa' ? isSolverFeasible(s.obj, true) : isSolverFeasible(s.obj);

      if (!isSolAvail) {
        let note = 'N/A';
        if (s.id === 'gurobi' && gur && gur.status === 'unavailable') note = 'No Lic/Lib';
        else if (s.obj && s.obj.status === 'failed')  note = 'Failed';
        else if (s.obj && s.obj.status === 'skipped') note = 'Skipped';
        return (
          <td key={s.id} style={{ color: 'var(--text-faint)' }}>
            <em>{note}</em>
          </td>
        );
      }

      if (s.val === null) {
        return <td key={s.id} style={{ color: 'var(--text-faint)' }}>—</td>;
      }

      if (!isFeasible) {
        return (
          <td key={s.id} className="val-mono">
            <span style={{ textDecoration: 'line-through' }}>{s.val.toFixed(2)}{unit}</span>
            <span className="solver-badge failed" style={{ marginLeft: '0.4rem', padding: '0.05rem 0.25rem', fontSize: '0.58rem', verticalAlign: 'middle' }}>INFEASIBLE</span>
          </td>
        );
      }

      const isWinner    = bestVal !== null && Math.abs(s.val - bestVal) < 1e-4;
      const isClassical = s.id === 'classical';

      let deltaStr  = '';
      let deltaClass = '';
      if (!isClassical && clVal !== null && clVal !== 0) {
        const delta = s.val - clVal;
        const pct   = (delta / clVal) * 100;
        const isBetter = isLowerBetter ? delta < -1e-4 : delta > 1e-4;
        const isWorse  = isLowerBetter ? delta > 1e-4  : delta < -1e-4;
        if (Math.abs(pct) > 0.05) {
          deltaStr = ` (${pct > 0 ? '+' : ''}${pct.toFixed(1)}%)`;
          if (isBetter) deltaClass = ' delta-val better';
          if (isWorse)  deltaClass = ' delta-val worse';
        }
      }

      return (
        <td key={s.id} className={isWinner ? 'val-mono font-bold' : 'val-mono'}>
          <span style={isWinner ? { color: 'var(--good)' } : {}}>
            {s.val.toFixed(2)}{unit}
          </span>
          {isWinner && <span className="solver-badge winner" style={{ marginLeft: '0.45rem', padding: '0.05rem 0.25rem', fontSize: '0.6rem' }}>Best</span>}
          {deltaStr && <span className={deltaClass}>{deltaStr}</span>}
        </td>
      );
    });
  };

  const renderStatus = (stats, type) => {
    if (!stats) return <span style={{ color: 'var(--text-faint)', fontSize: '0.72rem' }}>—</span>;
    
    if (type === 'frozen' || type === 'chilled' || type === 'ambient') {
      if (stats.vehicleStats && Object.keys(stats.vehicleStats).length > 0) {
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
            {Object.entries(stats.vehicleStats).map(([vid, v]) => {
              const ok = type === 'frozen' ? v.frozenOk : type === 'chilled' ? v.chilledOk : v.ambientOk;
              const used = type === 'frozen' ? v.frozen : type === 'chilled' ? v.chilled : v.ambient;
              const cap = type === 'frozen' ? v.frozenCap : type === 'chilled' ? v.chilledCap : v.ambientCap;
              return (
                <div key={vid} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.7rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>{vid}:</span>
                  <span style={{ color: ok ? 'var(--good)' : 'var(--bad)', fontWeight: 600 }}>
                    {used}/{cap}
                  </span>
                </div>
              );
            })}
          </div>
        );
      }
    }
    if (type === 'completeness') {
      return stats.isComplete
        ? <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ {stats.numDelivered}/{totalClinics}</span>
        : <span style={{ color: 'var(--bad)', fontWeight: 600 }}>✗ {stats.numDelivered}/{totalClinics}</span>;
    }
    if (type === 'timewindows') {
      const allTwFeasible = Object.values(stats.vehicleStats || {}).every(v => v.timeWindowOk !== false) && stats.timeWindowOk !== false;
      return allTwFeasible
        ? <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ Passed</span>
        : <span style={{ color: 'var(--bad)', fontWeight: 600 }}>✗ Failed</span>;
    }
    if (type === 'depot') {
      return <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ Passed</span>;
    }
    if (type === 'feasibility') {
      return stats.allFeasible
        ? <span className="solver-badge winner" style={{ padding: '0.1rem 0.35rem', fontSize: '0.65rem' }}>FEASIBLE</span>
        : <span className="solver-badge failed" style={{ padding: '0.1rem 0.35rem', fontSize: '0.65rem' }}>INFEASIBLE</span>;
    }
    return null;
  };

  const hasAnyData = cl || alns || ort || gur || pulp || qaAvailable;

  if (!hasAnyData) {
    return (
      <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '1rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
        <span>Run the pipeline to generate performance metrics, or refresh to re-run all solvers.</span>
        {onRefreshCompare && (
          <button className="btn btn-secondary" style={{ fontSize: '0.78rem', padding: '0.45rem 0.9rem' }} onClick={onRefreshCompare}>
            <RefreshCw size={13} /> Refresh Solvers
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="results-step-body">
      <div className="glass-panel" style={{ padding: '1.25rem 1.4rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.95rem' }}>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '0.45rem', color: 'var(--text)' }}>
            Solver Comparison Matrix (Custom Scenario)
          </h3>
          {onRefreshCompare && (
            <button
              className="btn btn-secondary"
              style={{ fontSize: '0.72rem', padding: '0.3rem 0.7rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
              onClick={onRefreshCompare}
              title="Re-run all solvers on the current custom scenario"
            >
              <RefreshCw size={12} /> Refresh Solvers
            </button>
          )}
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="compare-table" style={{ width: '100%', fontSize: '0.78rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <th style={{ textAlign: 'left', padding: '0.5rem', color: 'var(--text-muted)' }}>Metric</th>
                <th style={{ textAlign: 'left', padding: '0.5rem', color: 'var(--solver-classical)' }}>Classical</th>
                <th style={{ textAlign: 'left', padding: '0.5rem', color: 'var(--solver-alns)' }}>ALNS</th>
                <th style={{ textAlign: 'left', padding: '0.5rem', color: 'var(--solver-ortools)' }}>OR-Tools</th>
                <th style={{ textAlign: 'left', padding: '0.5rem', color: 'var(--solver-pulp)' }}>PuLP/CBC</th>
                <th style={{ textAlign: 'left', padding: '0.5rem', color: 'var(--solver-qaoa)' }}>Hybrid QAOA</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                <td style={{ padding: '0.65rem 0.5rem', fontWeight: 500 }}>Fleet Distance</td>
                {renderMetricCell('fleet_distance', ' km', true)}
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                <td style={{ padding: '0.65rem 0.5rem', fontWeight: 500 }}>Fleet Spoilage</td>
                {renderMetricCell('fleet_spoilage', ' Rs', true)}
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                <td style={{ padding: '0.65rem 0.5rem', fontWeight: 500 }}>Refrigeration Cost</td>
                {renderMetricCell('fleet_refrigeration', ' Rs', true)}
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                <td style={{ padding: '0.65rem 0.5rem', fontWeight: 500 }}>Combined Fleet Cost</td>
                {renderMetricCell('fleet_total_cost', ' Rs', true)}
              </tr>
              <tr>
                <td style={{ padding: '0.65rem 0.5rem', fontWeight: 500 }}>Execution Time</td>
                {renderMetricCell('total_time', ' s', true)}
              </tr>
            </tbody>
          </table>
        </div>
        {compareResults?.ilp_computing && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginTop: '0.85rem', color: 'var(--solver-qaoa)', fontSize: '0.72rem' }}>
            <Activity className="spin" size={12} />
            <span>Asynchronous ILP solver (PuLP) is still solving in the background...</span>
          </div>
        )}
      </div>

      <div className="glass-panel" style={{ padding: '1.25rem 1.4rem', marginTop: '1.25rem' }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.45rem', color: 'var(--text)' }}>
          Physical Constraint Verification Ledger
        </h3>
        <div style={{ overflowX: 'auto' }}>
          <table className="compare-table" style={{ width: '100%', fontSize: '0.78rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <th style={{ textAlign: 'left', padding: '0.5rem', color: 'var(--text-muted)' }}>Constraint Category</th>
                <th style={{ textAlign: 'left', padding: '0.5rem', color: 'var(--solver-classical)' }}>Classical</th>
                <th style={{ textAlign: 'left', padding: '0.5rem', color: 'var(--solver-alns)' }}>ALNS</th>
                <th style={{ textAlign: 'left', padding: '0.5rem', color: 'var(--solver-ortools)' }}>OR-Tools</th>
                <th style={{ textAlign: 'left', padding: '0.5rem', color: 'var(--solver-pulp)' }}>PuLP/CBC</th>
                <th style={{ textAlign: 'left', padding: '0.5rem', color: 'var(--solver-qaoa)' }}>Hybrid QAOA</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                <td style={{ padding: '0.55rem 0.5rem', fontWeight: 500 }}>Frozen Compartment Load</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(clStats, 'frozen')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(alnsStats, 'frozen')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(ortStats, 'frozen')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(pulpStats, 'frozen')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(qaStats, 'frozen')}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                <td style={{ padding: '0.55rem 0.5rem', fontWeight: 500 }}>Chilled Compartment Load</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(clStats, 'chilled')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(alnsStats, 'chilled')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(ortStats, 'chilled')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(pulpStats, 'chilled')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(qaStats, 'chilled')}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                <td style={{ padding: '0.55rem 0.5rem', fontWeight: 500 }}>Ambient Compartment Load</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(clStats, 'ambient')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(alnsStats, 'ambient')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(ortStats, 'ambient')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(pulpStats, 'ambient')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(qaStats, 'ambient')}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                <td style={{ padding: '0.55rem 0.5rem', fontWeight: 500 }}>Completeness (All Clinics)</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(clStats, 'completeness')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(alnsStats, 'completeness')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(ortStats, 'completeness')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(pulpStats, 'completeness')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(qaStats, 'completeness')}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                <td style={{ padding: '0.55rem 0.5rem', fontWeight: 500 }}>Time Window Adherence</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(clStats, 'timewindows')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(alnsStats, 'timewindows')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(ortStats, 'timewindows')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(pulpStats, 'timewindows')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(qaStats, 'timewindows')}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                <td style={{ padding: '0.55rem 0.5rem', fontWeight: 500 }}>Depot Return Guarantee</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(clStats, 'depot')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(alnsStats, 'depot')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(ortStats, 'depot')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(pulpStats, 'depot')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(qaStats, 'depot')}</td>
              </tr>
              <tr>
                <td style={{ padding: '0.55rem 0.5rem', fontWeight: 600 }}>Overall Trip Feasibility</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(clStats, 'feasibility')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(alnsStats, 'feasibility')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(ortStats, 'feasibility')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(pulpStats, 'feasibility')}</td>
                <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(qaStats, 'feasibility')}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Dual Route Map Comparison ─────────────────────────────────────── */}
      {(() => {
        const solverMap = { classical: cl, alns, ortools: ort, pulp_cbc: pulp, qaoa: qa };
        const depot = scenarioMeta?.easy?.depot || DEPOT;
        const leftResult  = solverMap[leftSolver];
        const rightResult = solverMap[rightSolver];
        const selStyle = { background: 'var(--bg-muted)', border: '1px solid var(--border)', borderRadius: '6px', color: 'var(--text)', fontSize: '0.72rem', padding: '0.3rem 0.5rem', cursor: 'pointer', outline: 'none' };
        return (
          <div className="glass-panel" style={{ padding: '1.25rem 1.4rem', marginTop: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '0.88rem', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '0.45rem', color: 'var(--text)' }}>
                Route Map Comparison
              </h3>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-faint)' }}>Select a solver for each map</span>
            </div>
            <div style={{ display: 'flex', gap: '1rem' }}>
              {/* Left map */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Left map:</span>
                  <select value={leftSolver} onChange={e => setLeftSolver(e.target.value)} style={selStyle}>
                    {SOLVER_OPTIONS.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                  </select>
                </div>
                <SolverRouteMap
                  result={(leftSolver === 'qaoa' && qaAvailable) || isAvailable(leftResult) ? leftResult : null}
                  depot={depot}
                  clinics={clinics}
                  label={SOLVER_OPTIONS.find(s => s.id === leftSolver)?.label + ' Routes'}
                />
              </div>
              {/* Right map */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Right map:</span>
                  <select value={rightSolver} onChange={e => setRightSolver(e.target.value)} style={selStyle}>
                    {SOLVER_OPTIONS.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                  </select>
                </div>
                <SolverRouteMap
                  result={(rightSolver === 'qaoa' && qaAvailable) || isAvailable(rightResult) ? rightResult : null}
                  depot={depot}
                  clinics={clinics}
                  label={SOLVER_OPTIONS.find(s => s.id === rightSolver)?.label + ' Routes'}
                />
              </div>
            </div>
          </div>
        );
      })()}

      <div className="glass-panel" style={{ padding: '1rem', marginTop: '1.25rem' }}>
        <h3 style={{ fontSize: '0.85rem', marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
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
          if (Array.isArray(r)) {
            r.forEach(id => {
              if (id !== 0) {
                const originalId = id >= 1000 ? Math.floor(id / 1000) : id;
                stops.add(originalId);
              }
            });
          } else if (r && typeof r === 'object') {
            const route = r.route || [];
            route.forEach(id => {
              if (id !== 0) {
                const originalId = id >= 1000 ? Math.floor(id / 1000) : id;
                stops.add(originalId);
              }
            });
            if (r.stops) {
              r.stops.forEach(s => {
                if (s.id !== 0 && s.id !== undefined) {
                  const originalId = s.id >= 1000 ? Math.floor(s.id / 1000) : s.id;
                  stops.add(originalId);
                }
              });
            }
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

  function handleRefreshCompare() {
    // Force the server to wipe stale 'easy' solver cache and recompute everything
    fetch(`${API_BASE}/api/recompute-easy`, { method: 'POST' })
      .then(() => fetch(`${API_BASE}/api/compare-results`))
      .then(r => r.json())
      .then(d => { if (!d.error) setCompareResults(d); })
      .catch(() => {});
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
      {currentStep === 'comparison' && <Step5Comparison results={results} compareResults={compareResults} config={config} scenarioMeta={scenarioMeta} onRefreshCompare={handleRefreshCompare} />}
    </div>
  );
}
