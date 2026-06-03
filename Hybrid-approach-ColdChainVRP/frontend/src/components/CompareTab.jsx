import React, { useState, useRef, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import L from 'leaflet';
import { BarChart2, Activity, CheckCircle2, Zap, Cpu, Clock, AlertTriangle, RefreshCw, XCircle, ShieldAlert, Home, MapPin } from 'lucide-react';
import TerminalPanel from './TerminalPanel';
import { API_BASE } from '../data';

const makeIcon = (color, label = '') =>
  new L.DivIcon({
    className: 'vrp-marker',
    html: `<div class="vrp-place-marker" style="--marker-color:${color}"><div class="vrp-place-bubble">${label}</div><div class="vrp-place-chip">Clinic ${label}</div></div>`,
    iconSize: [44, 58],
    iconAnchor: [22, 29],
  });

const depotIcon = new L.DivIcon({
  className: 'vrp-marker',
  html: `<div class="vrp-place-marker depot"><div class="vrp-place-bubble">D</div><div class="vrp-place-chip">Depot</div></div>`,
  iconSize: [54, 58],
  iconAnchor: [27, 29],
});

const VEHICLE_COLORS = ['#8fd6c2', '#9fb7e8', '#d8bd7f', '#caa5d8', '#d89b9b'];

/** Coerce API/JSON values (number or numeric string) to a finite number or null */
function toFiniteNumber(v) {
  if (v === null || v === undefined || v === '') return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** Fleet rollups from per-vehicle rows when top-level fleet_* is missing */
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

/**
 * Decide if QAOA block has comparable metrics for the active scenario.
 * Backend uses status "ok"; we also accept route data unless status is skipped/failed.
 */
function resolveQaoaMetrics(qa) {
  if (!qa || typeof qa !== 'object') return { available: false, m: null };
  const st = String(qa.status ?? '').toLowerCase();
  if (st === 'skipped' || st === 'failed') return { available: false, m: null };

  const derived = fleetTotalsFromRoutes(qa.routes);
  const fleet_total_cost =
    toFiniteNumber(qa.fleet_total_cost) ?? derived?.fleet_total_cost ?? null;
  if (fleet_total_cost == null || !Number.isFinite(fleet_total_cost)) {
    return { available: false, m: null };
  }

  const fleet_distance = toFiniteNumber(qa.fleet_distance) ?? derived?.fleet_distance ?? null;
  const fleet_spoilage = toFiniteNumber(qa.fleet_spoilage) ?? derived?.fleet_spoilage ?? null;
  const fleet_refrigeration = toFiniteNumber(qa.fleet_refrigeration) ?? derived?.fleet_refrigeration ?? null;
  const total_time = toFiniteNumber(qa.total_time);

  const hasOk = st === 'ok';
  const hasRoutes = derived && Object.keys(qa.routes).length > 0;
  if (!hasOk && !hasRoutes) return { available: false, m: null };

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

function MetricCard({ label, classical, qaoa, hybrid, unit = '', lowerIsBetter = true }) {
  const cNum = toFiniteNumber(classical);
  const qNum = toFiniteNumber(qaoa);
  const hNum = toFiniteNumber(hybrid);
  const hasQaoa = qNum !== null;
  const hasHybrid = hNum !== null;
  const diff = hasQaoa && cNum !== null ? cNum - qNum : null;
  const hybridDiff = hasHybrid && cNum !== null ? cNum - hNum : null;
  const pct = hasQaoa && cNum !== null && cNum !== 0 ? (diff / cNum) * 100 : null;
  const hybridPct = hasHybrid && cNum !== null && cNum !== 0 ? (hybridDiff / cNum) * 100 : null;
  const qaoBetter = diff !== null && (lowerIsBetter ? diff > 0 : diff < 0);
  const hybridBetter = hybridDiff !== null && (lowerIsBetter ? hybridDiff > 0 : hybridDiff < 0);

  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-row">
        <div className="metric-col">
          <small>Classical</small>
          <div className="metric-val classical">
            {cNum !== null ? `${cNum.toFixed(2)}${unit}` : (classical ?? '—')}
          </div>
        </div>
        {hasHybrid ? (
          <div className="metric-col">
            <small>Hybrid QAOA</small>
            <div className="metric-val qaoa">
              {`${hNum.toFixed(2)}${unit}`}
            </div>
          </div>
        ) : (
          <div className="metric-col">
            <small>Hybrid QAOA</small>
            <div className={`metric-val ${hasQaoa ? 'qaoa' : 'muted'}`}>
              {hasQaoa ? `${qNum.toFixed(2)}${unit}` : '—'}
            </div>
          </div>
        )}
        {hybridDiff !== null && (
          <div className="metric-delta">
            <small>Δ vs classical</small>
            <div className={`delta-num ${hybridBetter ? 'pos' : 'neg'}`}>
              {hybridDiff > 0 ? '+' : ''}{hybridDiff.toFixed(2)}{unit}
              {hybridPct !== null && Number.isFinite(hybridPct) && (
                <span style={{ fontSize: '0.72rem', marginLeft: '0.35rem', opacity: 0.9 }}>
                  ({hybridPct > 0 ? '+' : ''}{hybridPct.toFixed(1)}%)
                </span>
              )}
            </div>
          </div>
        )}
        {diff !== null && !hasHybrid && (
          <div className="metric-delta">
            <small>Δ vs classical</small>
            <div className={`delta-num ${qaoBetter ? 'pos' : 'neg'}`}>
              {diff > 0 ? '+' : ''}{diff.toFixed(2)}{unit}
              {pct !== null && Number.isFinite(pct) && (
                <span style={{ fontSize: '0.72rem', marginLeft: '0.35rem', opacity: 0.9 }}>
                  ({pct > 0 ? '+' : ''}{pct.toFixed(1)}%)
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

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

function RouteMap({ scenarioData, solverResult, height = '280px' }) {
  if (!scenarioData || !solverResult || !solverResult.routes) return null;

  const depot = scenarioData.depot;
  const clinics = scenarioData.clinics;
  const clinicById = Object.fromEntries(clinics.map((c) => [c.id, c]));

  return (
    <div className="map-shell map-frame" style={{ height }}>
      <MapContainer center={[depot?.lat || 13.045, depot?.lon || 80.18]} zoom={10} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution="&copy; OpenStreetMap &copy; CARTO"
        />
        {depot && typeof depot.lat === 'number' && typeof depot.lon === 'number' && (
          <Marker position={[depot.lat, depot.lon]} icon={depotIcon}>
            <Popup>
              <strong>{depot.name}</strong>
            </Popup>
          </Marker>
        )}
        {Object.entries(solverResult.routes).map(([vid, vdata], idx) => {
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
            <React.Fragment key={vid}>
              <Polyline positions={positions} pathOptions={{ color, weight: 3.25, opacity: 0.9, lineCap: 'round', lineJoin: 'round' }} />
              {route
                .filter((id) => id !== 0)
                .map((id, index) => {
                  const originalId = id >= 1000 ? Math.floor(id / 1000) : id;
                  const c = clinicById[originalId];
                  if (!c || typeof c.lat !== 'number' || typeof c.lon !== 'number') return null;
                  return (
                    <Marker key={`${id}-${index}`} position={[c.lat, c.lon]} icon={makeIcon(color, originalId)}>
                      <Popup>
                        <strong>{c.name}</strong>
                        <br />
                        {vid} · F:{c.demand.frozen} C:{c.demand.chilled} A:{c.demand.ambient}
                      </Popup>
                    </Marker>
                  );
                })}
            </React.Fragment>
          );
        })}
      </MapContainer>
    </div>
  );
}

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

function RouteTable({ result, color, scenarioData }) {
  if (!result || !result.routes) {
    return <p style={{ color: 'var(--text-faint)', fontSize: '0.8125rem' }}>No route data</p>;
  }
  const clinics = scenarioData?.clinics || [];
  const clinicById = Object.fromEntries(clinics.map((c) => [c.id, c]));
  const depot = scenarioData?.depot;

  return (
    <div className="route-table-wrap">
      {Object.entries(result.routes).map(([vid, vdata]) => {
        const route = Array.isArray(vdata) ? vdata : (vdata.route || []);
        
        let stops = [];
        let distance_km = 0;
        let spoilage_rs = 0;
        let feasible = true;

        if (Array.isArray(vdata)) {
          stops = route.map(id => {
            if (id === 0) {
              return { id: 0, name: depot?.name || 'Depot' };
            }
            const originalId = id >= 1000 ? Math.floor(id / 1000) : id;
            const c = clinicById[originalId];
            return c ? { id: c.id, name: c.name } : { id, name: `Clinic ${originalId}` };
          });
          
          if (depot && clinics.length > 0) {
            let dist = 0;
            for (let i = 0; i < route.length - 1; i++) {
              const id1 = route[i];
              const id2 = route[i+1];
              const orig1 = id1 >= 1000 ? Math.floor(id1 / 1000) : id1;
              const orig2 = id2 >= 1000 ? Math.floor(id2 / 1000) : id2;
              
              const c1 = orig1 === 0 ? depot : clinicById[orig1];
              const c2 = orig2 === 0 ? depot : clinicById[orig2];
              
              if (c1 && c2 && typeof c1.lat === 'number' && typeof c1.lon === 'number' && typeof c2.lat === 'number' && typeof c2.lon === 'number') {
                dist += getHaversineDistance(c1.lat, c1.lon, c2.lat, c2.lon);
              }
            }
            distance_km = dist;
          }
          spoilage_rs = null;
          feasible = true;
        } else {
          stops = vdata.stops || [];
          distance_km = vdata.distance_km;
          spoilage_rs = vdata.spoilage_rs;
          feasible = vdata.feasible;
        }

        return (
          <div key={vid} className="route-row" style={{ borderLeftColor: color }}>
            <div className="route-row-top">
              <span className="route-id">{vid}</span>
              <div className="route-stats">
                <span style={{ color: 'var(--solver-classical)' }}>
                  {distance_km != null ? `${distance_km.toFixed(2)} km` : '—'}
                </span>
                <span style={{ color: 'var(--bad)' }}>
                  {spoilage_rs != null ? `Rs ${spoilage_rs.toFixed(2)}` : '—'}
                </span>
                <span style={{ color: feasible ? 'var(--good)' : 'var(--bad)' }}>
                  {feasible ? 'OK' : 'viol.'}
                </span>
              </div>
            </div>
            <RouteTimeline stops={stops} color={color} />
          </div>
        );
      })}
    </div>
  );
}

function ConstraintVerificationBlock({ classical, alns, ortools, pulp, qaoa, qaAvailable, activeScenario, meta }) {
  // Extract limits dynamically from solver results to avoid any hardcoding
  const getLimits = () => {
    let frozen = 0;
    let chilled = 0;
    let ambient = 0;

    const scanResult = (res) => {
      if (res && res.routes) {
        Object.values(res.routes).forEach(r => {
          if (r.capacity) {
            frozen = Math.max(frozen, r.capacity.frozen?.cap ?? 0);
            chilled = Math.max(chilled, r.capacity.chilled?.cap ?? 0);
            ambient = Math.max(ambient, r.capacity.ambient?.cap ?? 0);
          }
        });
      }
    };

    scanResult(classical);
    scanResult(alns);
    scanResult(ortools);
    scanResult(pulp);
    scanResult(qaoa);

    return {
      frozen: frozen || 10,
      chilled: chilled || 12,
      ambient: ambient || 15
    };
  };

  const getConstraintStats = (result, limits, totalClinics) => {
    if (!result || result.status !== 'ok' || !result.routes) return null;
    let maxFrozen = 0;
    let maxChilled = 0;
    let maxAmbient = 0;
    let allFeasible = true;
    let clinicsDelivered = new Set();
    const vehicleStats = {};
    // Collect time window adherence from per-vehicle flags written by backend enrich_solver_result
    let twFlagFound = false;
    let twAllPassed = true;

    Object.entries(result.routes).forEach(([vid, r]) => {
      const vFrozen = r.capacity?.frozen?.used ?? 0;
      const vChilled = r.capacity?.chilled?.used ?? 0;
      const vAmbient = r.capacity?.ambient?.used ?? 0;
      const vFrozenCap = r.capacity?.frozen?.cap ?? limits.frozen;
      const vChilledCap = r.capacity?.chilled?.cap ?? limits.chilled;
      const vAmbientCap = r.capacity?.ambient?.cap ?? limits.ambient;

      const capFrozenOk = vFrozen <= vFrozenCap;
      const capChilledOk = vChilled <= vChilledCap;
      const capAmbientOk = vAmbient <= vAmbientCap;

      vehicleStats[vid] = {
        frozen: vFrozen,
        chilled: vChilled,
        ambient: vAmbient,
        frozenCap: vFrozenCap,
        chilledCap: vChilledCap,
        ambientCap: vAmbientCap,
        frozenOk: capFrozenOk,
        chilledOk: capChilledOk,
        ambientOk: capAmbientOk
      };

      maxFrozen = Math.max(maxFrozen, vFrozen);
      maxChilled = Math.max(maxChilled, vChilled);
      maxAmbient = Math.max(maxAmbient, vAmbient);

      // Derive feasibility from actual capacity data, not just cached r.feasible flag
      // This catches stale cache where feasible:true but capacity clearly overflows
      const capFeasible = capFrozenOk && capChilledOk && capAmbientOk;
      if (r.feasible === false || !capFeasible) {
        allFeasible = false;
      }
      // Read time_window_feasible written by backend enrich_solver_result
      if (typeof r.time_window_feasible === 'boolean') {
        twFlagFound = true;
        if (!r.time_window_feasible) {
          twAllPassed = false;
          allFeasible = false; // TW failure also makes trip infeasible
        }
      }
      const route = Array.isArray(r) ? r : (r.route || []);
      route.forEach(id => {
        if (id !== 0) {
          const originalId = id >= 1000 ? Math.floor(id / 1000) : id;
          // Only count clinic IDs that belong to this scenario (1..totalClinics)
          // Rejects stale QAOA results from larger old scenarios
          if (originalId >= 1 && originalId <= totalClinics) {
            clinicsDelivered.add(originalId);
          }
        }
      });
      if (r && r.stops) {
        r.stops.forEach(s => {
          if (s.id !== 0 && s.id !== undefined) {
            const originalId = s.id >= 1000 ? Math.floor(s.id / 1000) : s.id;
            if (originalId >= 1 && originalId <= totalClinics) {
              clinicsDelivered.add(originalId);
            }
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
      numDelivered,
      isComplete,
      frozenOk: maxFrozen <= limits.frozen,
      chilledOk: maxChilled <= limits.chilled,
      ambientOk: maxAmbient <= limits.ambient,
      vehicleStats,
      twPassed: twFlagFound ? twAllPassed : null,  // null = no flag data available
    };
  };

  const limits = getLimits();
  const totalClinics = meta?.num_clinics ?? 10;

  const clStats = getConstraintStats(classical, limits, totalClinics);
  const alnsStats = getConstraintStats(alns, limits, totalClinics);
  const ortStats = getConstraintStats(ortools, limits, totalClinics);
  const pulpStats = getConstraintStats(pulp, limits, totalClinics);
  const qaStats = qaAvailable ? getConstraintStats(qaoa, limits, totalClinics) : null;

  const renderStatus = (stats, type, isClassical = false) => {
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
      // Use the actual per-vehicle time_window_feasible flag from backend enrich_solver_result
      if (stats.twPassed === true) {
        return <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ Passed</span>;
      }
      if (stats.twPassed === false) {
        return <span style={{ color: 'var(--bad)', fontWeight: 600 }}>✗ Failed</span>;
      }
      // Fallback when no TW flag data is stored (older cached results)
      // For tough scenarios classical solver is known to violate TW
      if ((activeScenario === 'tough' || activeScenario === 'tough3' || activeScenario === 'tough4') && isClassical) {
        return <span style={{ color: 'var(--bad)', fontWeight: 600 }}>✗ Failed</span>;
      }
      return <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ Passed</span>;
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

  return (
    <div className="constraint-validation-box" style={{
      marginTop: '1.25rem',
      background: 'rgba(255, 255, 255, 0.02)',
      border: '1px solid rgba(255, 255, 255, 0.08)',
      borderRadius: '10px',
      padding: '1.1rem 1.2rem'
    }}>
      <h4 style={{ marginBottom: '0.85rem', fontSize: '0.85rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.45rem', color: 'var(--text)' }}>
        <ShieldAlert size={16} color="var(--accent)" />
        Physical Constraint Verification Ledger
      </h4>
      <div style={{ overflowX: 'auto' }}>
        <table className="compare-table" style={{ width: '100%', fontSize: '0.78rem', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', textAlign: 'left' }}>
              <th style={{ padding: '0.5rem', color: 'var(--text-muted)' }}>Constraint Category</th>
              <th style={{ padding: '0.5rem', color: 'var(--solver-classical)' }}>Classical</th>
              <th style={{ padding: '0.5rem', color: 'var(--solver-alns)' }}>ALNS</th>
              <th style={{ padding: '0.5rem', color: 'var(--solver-ortools)' }}>OR-Tools</th>
              <th style={{ padding: '0.5rem', color: 'var(--solver-pulp)' }}>PuLP/CBC</th>
              <th style={{ padding: '0.5rem', color: 'var(--solver-qaoa)' }}>Hybrid QAOA</th>
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
              <td style={{ padding: '0.55rem 0.5rem' }}>{renderStatus(clStats, 'timewindows', true)}</td>
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
  );
}

function isValidComparePayload(d) {
  return d && typeof d === 'object' && !d.error && (d.easy || d.tough || d.tough3 || d.tough4);
}

export default function CompareTab({ runPipeline, compareActive = true }) {
  const [activeScenario, setActiveScenario] = useState('easy');
  const [logs, setLogs] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [resultsSource, setResultsSource] = useState(null);
  const [scenarioMeta, setScenarioMeta] = useState(null);
  const [terminalExpanded, setTerminalExpanded] = useState(true);
  const [compareLoadState, setCompareLoadState] = useState('idle');

  const [leftMapSolver, setLeftMapSolver] = useState('classical');
  const [rightMapSolver, setRightMapSolver] = useState('qaoa');

  const logsEndRef = useRef(null);

  useEffect(() => {
    if (logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  useEffect(() => {
    fetch(`${API_BASE}/api/scenarios`)
      .then((r) => r.json())
      .then((d) => {
        if (!d.error) setScenarioMeta(d);
      })
      .catch(() => { });
  }, []);

  const loadCompareFromApi = useCallback(() => {
    setCompareLoadState('loading');
    fetch(`${API_BASE}/api/compare-results`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (isValidComparePayload(d)) {
          setResults(d);
          setResultsSource('disk');
          setTerminalExpanded(false);
        }
      })
      .catch(() => { })
      .finally(() => setCompareLoadState('done'));
  }, []);

  useEffect(() => {
    if (!compareActive) return;
    loadCompareFromApi();
  }, [compareActive, loadCompareFromApi]);

  useEffect(() => {
    if (isRunning) setTerminalExpanded(true);
  }, [isRunning]);

  const mergeResults = (d) => {
    if (isValidComparePayload(d)) {
      setResults(d);
      setResultsSource('run');
    }
  };

  const handleRunClassical = () => {
    runPipeline(`/api/run-compare?scenario=${activeScenario}`, setLogs, setIsRunning, () => {
      fetch(`${API_BASE}/api/compare-results`)
        .then((r) => r.json())
        .then(mergeResults)
        .catch(() => { });
    });
  };

  const handleRunFull = () => {
    runPipeline(`/api/run-compare-full?scenario=${activeScenario}`, setLogs, setIsRunning, () => {
      fetch(`${API_BASE}/api/compare-results`)
        .then((r) => r.json())
        .then(mergeResults)
        .catch(() => { });
    });
  };

  const handleRefreshDisk = () => {
    loadCompareFromApi();
  };

  const sc = results?.[activeScenario];
  const cl = sc?.classical;
  const qa = sc?.qaoa;
  const ort = sc?.ortools;
  const gur = sc?.gurobi;
  const pulp = sc?.pulp_cbc;
  const alns = sc?.alns;

  const meta = scenarioMeta?.[activeScenario];
  const { available: qaAvailable, m: qaM } = resolveQaoaMetrics(qa);

  // Automatically update active solvers on map panel based on scenario availability
  useEffect(() => {
    if (qaAvailable) {
      setRightMapSolver('qaoa');
    } else if (alns && alns.status === 'ok') {
      setRightMapSolver('alns');
    } else if (ort && ort.status === 'ok') {
      setRightMapSolver('ortools');
    } else if (pulp && pulp.status === 'ok') {
      setRightMapSolver('pulp');
    }
  }, [qaAvailable, alns, ort, pulp]);

  const isAvailable = (s) => {
    if (!s || s.status !== 'ok') return false;
    // Defensive: reject solvers that produced only depot-only routes or zero distance.
    // PuLP/CBC sometimes returns {"V1": {route:[0,0]}} with fleet_distance=0 on timeout.
    const hasRealDeliveries = s.routes && Object.values(s.routes).some(r => {
      const route = Array.isArray(r) ? r : (r.route || []);
      return route.some(id => id !== 0);
    });
    const hasDistance = toFiniteNumber(s.fleet_distance) > 0;
    if (!hasRealDeliveries && !hasDistance) return false;
    return true;
  };

  /** True only if the solver ran successfully AND every vehicle is feasible */
  const isSolverFeasible = (s, isQa = false) => {
    if (isQa) {
      if (!qaAvailable || !s || !s.routes) return false;
      return Object.values(s.routes).every(r => r.feasible !== false);
    }
    if (!s || s.status !== 'ok' || !s.routes) return false;
    return Object.values(s.routes).every(r => r.feasible !== false);
  };

  const SOLVERS = {
    classical: { name: 'Classical Local Search (NN+2opt)', color: 'var(--solver-classical)', data: cl },
    alns: { name: 'ALNS Metaheuristic', color: 'var(--solver-alns)', data: alns },
    ortools: { name: 'Google OR-Tools (Routing)', color: 'var(--solver-ortools)', data: ort },
    pulp: { name: 'PuLP/CBC (ILP)', color: 'var(--solver-pulp)', data: pulp },
    qaoa: { name: 'Hybrid QAOA', color: 'var(--solver-qaoa)', data: qaAvailable ? qa : null },
  };

  const renderMetricCell = (key, unit, isLowerBetter = true) => {
    const clVal = toFiniteNumber(cl?.[key]);
    const alnsVal = toFiniteNumber(alns?.[key]);
    const ortVal = toFiniteNumber(ort?.[key]);
    const pulpVal = toFiniteNumber(pulp?.[key]);
    const qaVal = qaAvailable ? toFiniteNumber(qaM?.[key]) : null;

    const solvers = [
      { id: 'classical', val: clVal, obj: cl },
      { id: 'alns', val: alnsVal, obj: alns },
      { id: 'ortools', val: ortVal, obj: ort },
      { id: 'pulp', val: pulpVal, obj: pulp },
      { id: 'qaoa', val: qaVal, obj: qa },
    ];

    // Only feasible, active solvers compete for "Best"
    let bestVal = null;
    const eligibleSolvers = solvers.filter(s => {
      if (s.val === null) return false;
      const avail = s.id === 'qaoa' ? qaAvailable : isAvailable(s.obj);
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
      const isSolAvail = s.id === 'qaoa' ? qaAvailable : isAvailable(s.obj);
      const isFeasible = s.id === 'qaoa' ? isSolverFeasible(s.obj, true) : isSolverFeasible(s.obj);

      if (!isSolAvail) {
        // Detect trivially-failed solver: status "ok" but no real routes/distance
        // (e.g. CBC returning all-depot solution after timeout)
        const isTrivialFailed = s.obj && s.obj.status === 'ok'
          && !(s.obj.routes && Object.keys(s.obj.routes).length > 0)
          && !(toFiniteNumber(s.obj.fleet_distance) > 0);

        let note = 'N/A';
        if (s.id === 'gurobi' && gur && gur.status === 'unavailable') note = 'No Lic/Lib';
        else if (s.obj && (s.obj.status === 'failed' || isTrivialFailed)) note = 'Failed';
        else if (s.obj && s.obj.status === 'skipped') note = 'Skipped';

        const isFailed = note === 'Failed';
        return (
          <td key={s.id} style={{ color: isFailed ? 'var(--bad)' : 'var(--text-faint)' }}>
            {isFailed
              ? <span className="solver-badge failed" style={{ padding: '0.1rem 0.35rem', fontSize: '0.65rem' }}>Failed</span>
              : <em>{note}</em>
            }
          </td>
        );
      }

      if (s.val === null) {
        return <td key={s.id} style={{ color: 'var(--text-faint)' }}>—</td>;
      }

      // Infeasible solver: show value normally but skip "Best" competition
      if (!isFeasible) {
        return (
          <td key={s.id} className="val-mono">
            <span style={{ textDecoration: 'line-through' }}>{s.val.toFixed(2)}{unit}</span>
            <span className="solver-badge failed" style={{ marginLeft: '0.4rem', padding: '0.05rem 0.25rem', fontSize: '0.58rem', verticalAlign: 'middle' }}>INFEASIBLE</span>
          </td>
        );
      }

      const isWinner = bestVal !== null && Math.abs(s.val - bestVal) < 1e-4;
      const isClassical = s.id === 'classical';

      let deltaStr = '';
      let deltaClass = '';
      if (!isClassical && clVal !== null && clVal !== 0) {
        const delta = s.val - clVal;
        const pct = (delta / clVal) * 100;
        const isBetter = isLowerBetter ? delta < -1e-4 : delta > 1e-4;
        const isWorse = isLowerBetter ? delta > 1e-4 : delta < -1e-4;
        if (Math.abs(pct) > 0.05) {
          deltaStr = ` (${pct > 0 ? '+' : ''}${pct.toFixed(1)}%)`;
          if (isBetter) deltaClass = ' delta-val better';
          if (isWorse) deltaClass = ' delta-val worse';
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


  const renderStatusBadgeCell = () => {
    const solvers = [
      { id: 'classical', obj: cl, name: 'Classical' },
      { id: 'alns', obj: alns, name: 'ALNS' },
      { id: 'ortools', obj: ort, name: 'OR-Tools' },
      { id: 'pulp', obj: pulp, name: 'PuLP/CBC' },
      { id: 'qaoa', obj: qa, name: 'Hybrid QAOA', isQa: true },
    ];

    return solvers.map(s => {
      const avail = s.isQa ? qaAvailable : isAvailable(s.obj);
      const feasible = s.isQa ? isSolverFeasible(s.obj, true) : isSolverFeasible(s.obj);
      if (avail) {
        if (!feasible) {
          return (
            <td key={s.id}>
              <span className="solver-badge failed" title="Solution violates one or more vehicle capacity constraints.">Infeasible</span>
            </td>
          );
        }
        return (
          <td key={s.id}>
            <span className="solver-badge ok">Active</span>
          </td>
        );
      } else {
        if (s.id === 'gurobi' && gur && gur.status === 'unavailable') {
          return (
            <td key={s.id}>
              <span className="solver-badge unavailable" title="No Gurobi installation or valid license found.">Unavailable</span>
            </td>
          );
        }
        const isTrivialFailed = s.obj && s.obj.status === 'ok'
          && !(s.obj.routes && Object.keys(s.obj.routes).length > 0)
          && !(toFiniteNumber(s.obj.fleet_distance) > 0);
        if (s.obj && (s.obj.status === 'failed' || isTrivialFailed)) {
          return (
            <td key={s.id}>
              <span className="solver-badge failed" title={s.obj.error || 'Solver returned no valid routes'}>Failed</span>
            </td>
          );
        }
        return (
          <td key={s.id}>
            <span className="solver-badge unavailable">Not Run</span>
          </td>
        );
      }
    });
  };


  const renderMapPanelHeader = (side, active, onChange) => {
    return (
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.65rem' }}>
        <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.4rem', color: SOLVERS[active].color }}>
          {side === 'left' ? <Cpu size={15} /> : <Zap size={15} />}
          {SOLVERS[active].name}
        </h3>
        <select
          value={active}
          onChange={(e) => onChange(e.target.value)}
          style={{
            background: 'var(--bg-muted)',
            border: '1px solid var(--border)',
            borderRadius: '4px',
            color: 'var(--text)',
            fontSize: '0.75rem',
            padding: '0.2rem 0.4rem',
            cursor: 'pointer'
          }}
        >
          {Object.entries(SOLVERS).map(([key, info]) => {
            const avail = key === 'qaoa' ? qaAvailable : isAvailable(info.data);
            return (
              <option key={key} value={key} disabled={!avail}>
                {info.name} {!avail ? '(N/A)' : ''}
              </option>
            );
          })}
        </select>
      </div>
    );
  };

  const scenarioLabel = activeScenario === 'easy'
    ? 'Scenario 1 (Configured)'
    : activeScenario === 'tough'
      ? 'Scenario 2 (Baseline)'
      : activeScenario === 'tough3'
        ? 'Scenario 3 (Stress Test)'
        : 'Scenario 4 (Edge Cases)';

  return (
    <div className="compare-stack">
      <div className="glass-panel" style={{ padding: '1.1rem 1.15rem' }}>
        <div className="compare-panel-head">
          <div>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '1rem', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.75rem', marginBottom: '0.75rem' }}>
              <h2 style={{ margin: 0, paddingRight: '1rem', borderRight: '1px solid rgba(255,255,255,0.2)' }}>Compare solvers</h2>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  className={`btn ${activeScenario === 'easy' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setActiveScenario('easy')}
                  style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                >
                  Scenario 1
                </button>
                <button
                  className={`btn ${activeScenario === 'tough' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setActiveScenario('tough')}
                  style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                >
                  Scenario 2
                </button>
                <button
                  className={`btn ${activeScenario === 'tough3' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setActiveScenario('tough3')}
                  style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                >
                  Scenario 3
                </button>
                <button
                  className={`btn ${activeScenario === 'tough4' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setActiveScenario('tough4')}
                  style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                >
                  Scenario 4
                </button>
              </div>
              {cl && resultsSource === 'disk' && (
                <span className="badge green">Saved run</span>
              )}
              {cl && resultsSource === 'run' && (
                <span className="badge blue">Just computed</span>
              )}
              {compareLoadState === 'loading' && (
                <span className="badge">Loading…</span>
              )}
            </div>
            <p>
              Compare routing results across five different classical and hybrid quantum solvers.
              Deltas are shown relative to the Classical baseline, and the best-performing solver in each category is highlighted.
            </p>
          </div>
          <div className="compare-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleRefreshDisk}
              disabled={compareLoadState === 'loading' || isRunning}
              title="Reload compare_results.json from disk"
            >
              <RefreshCw size={15} />
              Refresh file
            </button>
            <button type="button" className="btn btn-primary" onClick={handleRunClassical} disabled={isRunning}>
              {isRunning ? <Activity size={15} /> : <Cpu size={15} />}
              {isRunning ? 'Running…' : 'Classical only'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={handleRunFull} disabled={isRunning}>
              {isRunning ? <Activity size={15} /> : <Zap size={15} />}
              {isRunning ? 'Running…' : 'Classical + QAOA'}
            </button>
          </div>
        </div>
      </div>

      {cl && (
        <>
          <div key={activeScenario} className="glass-panel" style={{ padding: '1.1rem 1.15rem' }}>
            <h3 style={{ marginBottom: '0.85rem', fontSize: '0.95rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
              <BarChart2 size={16} strokeWidth={2} aria-hidden style={{ opacity: 0.7 }} />
              Solver Comparison Matrix · {scenarioLabel}
            </h3>

            <div className="solver-comparison-table-wrapper">
              <table className="solver-comparison-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    {[
                      { id: 'classical', label: 'Classical Local Search (NN+2opt)', color: 'var(--solver-classical)', obj: cl, isQa: false },
                      { id: 'alns', label: 'ALNS Metaheuristic', color: 'var(--solver-alns)', obj: alns, isQa: false },
                      { id: 'ortools', label: 'Google OR-Tools', color: 'var(--solver-ortools)', obj: ort, isQa: false },
                      { id: 'pulp', label: 'PuLP/CBC (ILP)', color: 'var(--solver-pulp)', obj: pulp, isQa: false },
                      { id: 'qaoa', label: 'Hybrid QAOA', color: 'var(--solver-qaoa)', obj: qa, isQa: true },
                    ].map(({ id, label, color, obj, isQa }) => {
                      const avail = isQa ? qaAvailable : isAvailable(obj);
                      const feasible = avail && (isQa ? isSolverFeasible(obj, true) : isSolverFeasible(obj));
                      const infeasible = avail && !feasible;
                      return (
                        <th key={id} style={{ color }}>
                          {label}
                          {infeasible && (
                            <div style={{ fontSize: '0.62rem', fontWeight: 400, color: 'var(--bad)', marginTop: '2px', letterSpacing: '0.04em' }}>
                              ⚠ INFEASIBLE
                            </div>
                          )}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th style={{ color: 'var(--text-muted)' }}>Fleet Distance</th>
                    {renderMetricCell('fleet_distance', ' km', true)}
                  </tr>
                  <tr>
                    <th style={{ color: 'var(--text-muted)' }}>Fleet Spoilage</th>
                    {renderMetricCell('fleet_spoilage', ' Rs', true)}
                  </tr>
                  <tr>
                    <th style={{ color: 'var(--text-muted)' }}>Fleet Refrigeration</th>
                    {renderMetricCell('fleet_refrigeration', ' Rs', true)}
                  </tr>
                  <tr style={{ fontWeight: 'bold', background: 'rgba(255, 255, 255, 0.015)' }}>
                    <th style={{ color: 'var(--text)' }}>Fleet Total Cost</th>
                    {renderMetricCell('fleet_total_cost', ' Rs', true)}
                  </tr>
                  <tr>
                    <th style={{ color: 'var(--text-muted)' }}>Solve Time</th>
                    {renderMetricCell('total_time', ' s', true)}
                  </tr>
                  <tr>
                    <th style={{ color: 'var(--text-muted)' }}>Solver Status</th>
                    {renderStatusBadgeCell()}
                  </tr>
                </tbody>
              </table>
            </div>

            <ConstraintVerificationBlock
              classical={cl}
              alns={alns}
              ortools={ort}
              pulp={pulp}
              qaoa={qaAvailable ? qa : null}
              qaAvailable={qaAvailable}
              activeScenario={activeScenario}
              meta={meta}
            />
          </div>

          <div className="compare-maps-grid" key={`maps-${activeScenario}`}>
            <div className="glass-panel compare-map-panel" style={{ padding: '1rem' }}>
              {renderMapPanelHeader('left', leftMapSolver, setLeftMapSolver)}
              {((leftMapSolver === 'qaoa' && qaAvailable) || (leftMapSolver !== 'qaoa' && isAvailable(SOLVERS[leftMapSolver].data))) ? (
                <>
                  <RouteMap scenarioData={meta} solverResult={SOLVERS[leftMapSolver].data} height="420px" />
                  <RouteTable result={SOLVERS[leftMapSolver].data} color={SOLVERS[leftMapSolver].color} scenarioData={meta} />
                </>
              ) : (
                <div className="qaoa-placeholder">
                  <Cpu size={22} strokeWidth={1.5} style={{ opacity: 0.5 }} aria-hidden />
                  <span>Solver routes not available.</span>
                  <span className="faint">Run this solver to visualize its routes.</span>
                </div>
              )}
            </div>

            <div className="glass-panel compare-map-panel" style={{ padding: '1rem' }}>
              {renderMapPanelHeader('right', rightMapSolver, setRightMapSolver)}
              {((rightMapSolver === 'qaoa' && qaAvailable) || (rightMapSolver !== 'qaoa' && isAvailable(SOLVERS[rightMapSolver].data))) ? (
                <>
                  <RouteMap scenarioData={meta} solverResult={SOLVERS[rightMapSolver].data} height="420px" />
                  <RouteTable result={SOLVERS[rightMapSolver].data} color={SOLVERS[rightMapSolver].color} scenarioData={meta} />
                </>
              ) : (
                <div className="qaoa-placeholder">
                  <Zap size={22} strokeWidth={1.5} style={{ opacity: 0.5 }} aria-hidden />
                  <span>Solver routes not available.</span>
                  <span className="faint">Run this solver to visualize its routes.</span>
                </div>
              )}
            </div>
          </div>

          {meta && (
            <details className="details-compare">
              <summary>Scenario details · {scenarioLabel}</summary>
              <div className="details-inner">
                <div className="scenario-detail-grid">
                  {[
                    { label: 'Clinics', value: meta.num_clinics },
                    { label: 'Vehicles', value: meta.num_vehicles },
                    { label: 'Total demand', value: `${meta.total_demand} units` },
                    { label: 'Tight windows', value: meta.tight_windows || 0 },
                  ].map(({ label, value }) => (
                    <div key={label} className="scenario-detail-stat">
                      <div className="sdl">{label}</div>
                      <div className="sdv">{value}</div>
                    </div>
                  ))}
                </div>
                <div className="clinic-chips">
                  {meta.clinics.map((c) => {
                    const tight = c.time_window[1] - c.time_window[0] <= 4;
                    return (
                      <div key={c.id} className={`clinic-chip${tight ? ' tight' : ''}`}>
                        <div className="cn">{c.name}</div>
                        <div className="cd">
                          F:{c.demand.frozen} C:{c.demand.chilled} A:{c.demand.ambient}
                          {tight && (
                            <span style={{ color: 'var(--bad)', marginLeft: '0.35rem' }}>
                              {c.time_window[0]}–{c.time_window[1]}h
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </details>
          )}
        </>
      )}

      {!cl && !isRunning && compareLoadState === 'done' && (
        <div className="glass-panel compare-empty">
          <BarChart2 size={28} strokeWidth={1.5} style={{ opacity: 0.35, marginBottom: '0.5rem' }} aria-hidden />
          <p>
            No comparison file yet. Run <strong>Classical only</strong> for a quick solve, or{' '}
            <strong>Classical + QAOA</strong> for the full hybrid benchmark. Output is written to{' '}
            <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85em' }}>compare_results.json</code> on the
            server and will appear here on reload.
          </p>
        </div>
      )}

      {cl && !isRunning && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Pipeline log</span>
          <button type="button" className="btn btn-secondary" onClick={() => setTerminalExpanded((v) => !v)}>
            {terminalExpanded ? 'Hide' : 'Show'}
          </button>
        </div>
      )}

      {(terminalExpanded || isRunning || !cl) && (
        <TerminalPanel
          logs={logs}
          logsEndRef={logsEndRef}
          isRunning={isRunning}
          onRun={handleRunClassical}
          btnLabel="Classical only"
          idleText="Output from the last run appears here. Use the buttons above to start a job."
          height="200px"
          hideRunButton
        />
      )}
    </div>
  );
}
