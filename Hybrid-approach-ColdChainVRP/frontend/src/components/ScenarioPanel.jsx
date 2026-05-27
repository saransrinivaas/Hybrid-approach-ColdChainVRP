import { useState, useRef, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import L from 'leaflet';
import { Activity, AlertTriangle, Boxes, CheckCircle2, Clock3, Home, MapPin, Package, Play, Route, Truck } from 'lucide-react';
import { API_BASE } from '../data';

const makeIcon = (color, label = '') => new L.DivIcon({
  className: 'vrp-marker',
  html: `<div class="vrp-place-marker" style="--marker-color:${color}"><div class="vrp-place-bubble">${label}</div><div class="vrp-place-chip">Clinic ${label}</div></div>`,
  iconSize: [44, 58], iconAnchor: [22, 29],
});

const depotIcon = new L.DivIcon({
  className: 'vrp-marker',
  html: `<div class="vrp-place-marker depot"><div class="vrp-place-bubble">D</div><div class="vrp-place-chip">Depot</div></div>`,
  iconSize: [54, 58], iconAnchor: [27, 29],
});

const VEHICLE_COLORS = ['#8fd6c2', '#9fb7e8', '#d8bd7f', '#caa5d8', '#d89b9b'];

function RouteTimeline({ stops = [], color }) {
  return (
    <div
      className="route-timeline"
      style={{ '--route-color': color, display: 'flex', flexDirection: 'row', flexWrap: 'nowrap' }}
    >
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

export default function ScenarioPanel({
  scenarioKey,   // 'easy' | 'tough'
  meta,          // from /api/scenarios
  pipelineEndpoint,
  resultsEndpoint,
  label,
  subtitle,
  accentColor,
  runPipeline,
}) {
  const [logs, setLogs]           = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults]     = useState(null);
  const [showLogs, setShowLogs]   = useState(false);
  const [localMeta, setLocalMeta] = useState(meta || null);
  const logsEndRef = useRef(null);

  // Sync localMeta when prop changes (parent fetched it)
  useEffect(() => { if (meta) setLocalMeta(meta); }, [meta]);

  // Auto-retry fetching scenarios meta every 3s until we have it
  useEffect(() => {
    if (localMeta) return;
    const interval = setInterval(() => {
      fetch(`${API_BASE}/api/scenarios`)
        .then(r => r.json())
        .then(d => {
          if (!d.error) {
            const key = scenarioKey === 'easy' ? 'easy' : scenarioKey === 'tough' ? 'tough' : 'tough3';
            const found = d[key];
            if (found?.clinics?.length > 0) setLocalMeta(found);
          }
        })
        .catch(() => {});
    }, 3000);
    return () => clearInterval(interval);
  }, [localMeta, scenarioKey]);

  useEffect(() => {
    if (logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Try to load existing results on mount
  useEffect(() => {
    fetch(`${API_BASE}${resultsEndpoint}`)
      .then(r => r.json())
      .then(d => { if (!d.error) setResults(d); })
      .catch(() => {});
  }, [resultsEndpoint]);

  const handleRun = () => {
    setShowLogs(true);
    runPipeline(pipelineEndpoint, setLogs, setIsRunning, () => {
      fetch(`${API_BASE}${resultsEndpoint}`)
        .then(r => r.json())
        .then(d => { if (!d.error) setResults(d); })
        .catch(() => {});
    });
  };

  const depot   = localMeta?.depot;
  const clinics = localMeta?.clinics || [];

  // Build route polylines from results if available with type-guarded coords
  const solverResults = results?.qaoa || results;
  const routeLines = solverResults?.routes
    ? Object.entries(solverResults.routes).map(([vid, vdata], idx) => {
        const color = VEHICLE_COLORS[idx % VEHICLE_COLORS.length];
        const positions = (vdata.route || []).map(id => {
          if (id === 0 && depot && typeof depot.lat === 'number' && typeof depot.lon === 'number') {
            return [depot.lat, depot.lon];
          }
          const c = clinics.find(x => x.id === id);
          return c && typeof c.lat === 'number' && typeof c.lon === 'number' ? [c.lat, c.lon] : null;
        }).filter(Boolean);
        return { vid, color, positions };
      })
    : [];

  const mapCenter = depot && typeof depot.lat === 'number' && typeof depot.lon === 'number' ? [depot.lat, depot.lon] : [13.02, 80.17];

  return (
    <div className="card glass-panel" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
            {scenarioKey === 'easy'
              ? <CheckCircle2 size={18} color='var(--text)' />
              : <AlertTriangle size={18} color='var(--text)' />}
            <h2 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text)' }}>{label}</h2>
          </div>
          <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{subtitle}</p>
        </div>
        <button
          onClick={handleRun}
          disabled={isRunning}
          style={{
            background: isRunning ? 'transparent' : '#f4f4f4',
            color: isRunning ? 'var(--text-secondary)' : '#111111',
            border: isRunning ? `1px solid ${accentColor}44` : '1px solid rgba(255,255,255,0.32)',
            padding: '0.55rem 1.15rem',
            borderRadius: '999px',
            cursor: isRunning ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            fontWeight: 600, fontSize: '0.85rem',
            whiteSpace: 'nowrap',
          }}
        >
          {isRunning ? <Activity size={14} /> : <Play size={14} />}
          {isRunning ? 'Running...' : 'Run Hybrid Pipeline'}
        </button>
      </div>

      {/* Stats row */}
      {localMeta && (
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {[
            { label: 'Clinics',   value: localMeta.num_clinics, icon: MapPin },
            { label: 'Vehicles',  value: localMeta.num_vehicles, icon: Truck },
            { label: 'Demand',    value: `${localMeta.total_demand} units`, icon: Package },
            { label: 'Tight Windows', value: localMeta.tight_windows || 0, icon: Clock3 },
          ].map(({ label: l, value, icon: Icon }) => (
            <div key={l} style={{
              flex: '1 1 0', minWidth: '70px',
              padding: '0.55rem 0.6rem',
              background: 'rgba(255,255,255,0.03)',
              borderRadius: '8px',
              border: `1px solid ${accentColor}22`,
              textAlign: 'center',
            }}>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary)', marginBottom: '0.20rem', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem' }}>
                <Icon size={12} strokeWidth={2} aria-hidden />{l}
              </div>
              <div style={{ fontWeight: 700, color: 'var(--text)', fontSize: '0.95rem' }}>{value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Map — always pre-rendered so tiles load immediately */}
      <div className="map-shell scenario-map-shell" style={{ height: '430px', position: 'relative' }}>
        {!localMeta && (
          <div style={{
            position: 'absolute', inset: 0, zIndex: 1000,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(17,17,17,0.75)', backdropFilter: 'blur(4px)',
            borderRadius: '8px', flexDirection: 'column', gap: '0.75rem',
          }}>
            <div style={{ width: 28, height: 28, border: `3px solid ${accentColor}`, borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.9s linear infinite' }} />
            <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>Loading map data…</span>
          </div>
        )}
        <MapContainer center={mapCenter} zoom={10} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; OpenStreetMap &copy; CARTO'
          />
          {depot && typeof depot.lat === 'number' && typeof depot.lon === 'number' && (
            <Marker position={[depot.lat, depot.lon]} icon={depotIcon}>
              <Popup><strong>{depot.name}</strong></Popup>
            </Marker>
          )}
          {routeLines.map(({ vid, color, positions }) => (
            positions.length >= 2 && (
              <Polyline key={vid} positions={positions}
                pathOptions={{ color, weight: 3.5, opacity: 0.92, lineCap: 'round', lineJoin: 'round' }} />
            )
          ))}
          {clinics.map((c) => {
            let color = accentColor;
            if (solverResults?.routes) {
              const entry = Object.entries(solverResults.routes).find(([, vd]) =>
                (vd.route || []).includes(c.id)
              );
              if (entry) color = VEHICLE_COLORS[Object.keys(solverResults.routes).indexOf(entry[0]) % VEHICLE_COLORS.length];
            }
            const tight = c.time_window && (c.time_window[1] - c.time_window[0]) <= 4;
            if (typeof c.lat !== 'number' || typeof c.lon !== 'number') return null;
            return (
              <Marker key={c.id} position={[c.lat, c.lon]} icon={makeIcon(color, c.id)}>
                <Popup>
                  <strong>{c.name}</strong><br />
                  F:{c.demand.frozen} C:{c.demand.chilled} A:{c.demand.ambient}
                  {tight && <><br /><span>Tight window {c.time_window[0]}-{c.time_window[1]}h</span></>}
                </Popup>
              </Marker>
            );
          })}
          <div className="map-float-card">
            <span>{solverResults?.routes ? 'Optimized routes' : 'Clinic network'}</span>
            <strong>{clinics.length} stops</strong>
          </div>
        </MapContainer>
      </div>

      {/* Results summary */}
      {solverResults?.routes && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '0.5rem' }}>
            <Route size={15} color={accentColor} />
            <span style={{ fontWeight: 600, fontSize: '0.82rem', color: 'var(--text)' }}>Optimal Deliveries Route Timeline</span>
          </div>
          {Object.entries(solverResults.routes).map(([vid, vdata], idx) => {
            const color = VEHICLE_COLORS[idx % VEHICLE_COLORS.length];
            const stops = (vdata.route || []).map(id => {
              if (id === 0 && depot) return depot;
              return clinics.find(x => x.id === id);
            }).filter(Boolean);
            return (
              <div key={vid} className="panel-route-row" style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.78rem' }}>
                  <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: color }} />
                  <strong style={{ color: 'var(--text)' }}>{vid} Route</strong>
                  <span style={{ color: 'var(--text-secondary)' }}>· {vdata.distance_km?.toFixed(1) || vdata.cost_breakdown?.distance?.toFixed(1) || 0} km · {vdata.spoilage_rs ? `₹${(vdata.spoilage_rs).toFixed(0)} spoilage` : vdata.cost_breakdown?.spoilage_cost ? `₹${(vdata.cost_breakdown.spoilage_cost * 100).toFixed(0)} spoilage` : ''}</span>
                </div>
                <RouteTimeline stops={stops} color={color} />
              </div>
            );
          })}
        </div>
      )}

      {/* Logs console */}
      {showLogs && (
        <div style={{
          background: '#0a0a0c',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '8px',
          padding: '0.75rem 0.95rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.5rem',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              <Boxes size={13} />
              <span>Console Stream Output</span>
            </div>
            {isRunning && <span className="pulse-dot" style={{ background: accentColor }} />}
          </div>
          <div style={{
            maxHeight: '140px',
            overflowY: 'auto',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.75rem',
            color: '#b0b0b8',
            whiteSpace: 'pre-wrap',
            lineHeight: 1.6,
          }}>
            {logs.join('\n')}
            <div ref={logsEndRef} />
          </div>
        </div>
      )}
    </div>
  );
}
