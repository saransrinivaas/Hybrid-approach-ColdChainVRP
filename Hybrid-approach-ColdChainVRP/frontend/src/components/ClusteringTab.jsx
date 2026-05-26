import React, { useState, useRef, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import L from 'leaflet';
import { Truck, CheckCircle2 } from 'lucide-react';
import { CLINICS, CAPACITY, computeDemand, computeQubits, API_BASE } from '../data';
import TerminalPanel from './TerminalPanel';

const createCustomIcon = (color) =>
  new L.DivIcon({
    className: 'custom-icon',
    html: `<div style="background-color:${color};width:16px;height:16px;border-radius:50%;border:2px solid white;box-shadow:0 0 10px ${color}"></div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });

const depotIcon = new L.DivIcon({
  className: 'depot-icon',
  html: `<div style="background-color:#ef4444;width:20px;height:20px;border-radius:4px;border:2px solid white;box-shadow:0 0 15px rgba(239,68,68,0.8);display:flex;align-items:center;justify-content:center"><div style="width:8px;height:8px;background:white;border-radius:2px"></div></div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

// Props: depot (object), runPipeline (fn)
export default function ClusteringTab({ depot, runPipeline }) {
  const [logs, setLogs] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [vehicleRoutes, setVehicleRoutes] = useState(null); // fetched from backend
  const logsEndRef = useRef(null);

  useEffect(() => {
    if (logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const getClinic = (id) => CLINICS.find((c) => c.id === id);
  const getVehicleClinics = (vr) => vr.trips.flatMap((t) => t.clinics);

  const handleRun = () => {
    runPipeline('/api/run-clustering', setLogs, setIsRunning, () => {
      // After clustering finishes, fetch the real result from the backend
      fetch(`${API_BASE}/api/clustering-result`)
        .then((r) => r.json())
        .then((data) => {
          if (!data.error) setVehicleRoutes(data);
        })
        .catch(() => {});
    });
  };

  const allSubclusters = vehicleRoutes
    ? vehicleRoutes.flatMap((v) => v.trips.flatMap((t) => t.subclusters))
    : [];
  const totalQubits = allSubclusters.reduce((s, sc) => s + computeQubits(sc.length), 0);
  const maxQubits = allSubclusters.length * computeQubits(4);

  return (
    <div className="content-grid">
      <div className="main-content">
        {/* Map */}
        <div className="map-container" style={{ height: '400px' }}>
          <MapContainer
            center={[13.045, 80.18]}
            zoom={11}
            style={{ height: '100%', width: '100%', background: '#111827' }}
          >
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
            />
            <Marker position={[depot.lat, depot.lon]} icon={depotIcon}>
              <Popup>
                <strong style={{ color: '#111827' }}>{depot.name}</strong>
                <br />Central Hub
              </Popup>
            </Marker>

            {/* Before clustering: all blue */}
            {!vehicleRoutes &&
              CLINICS.map((c) => (
                <Marker key={c.id} position={[c.lat, c.lon]} icon={createCustomIcon('#3b82f6')}>
                  <Popup>
                    <strong style={{ color: '#111827' }}>{c.name}</strong>
                    <br />
                    F:{c.demand.frozen} C:{c.demand.chilled} A:{c.demand.ambient}
                  </Popup>
                </Marker>
              ))}

            {/* After clustering: vehicle-coloured */}
            {vehicleRoutes &&
              vehicleRoutes.map((vr) => (
                <React.Fragment key={vr.vehicleId}>
                  {getVehicleClinics(vr).map((cid) => {
                    const c = getClinic(cid);
                    if (!c || typeof c.lat !== 'number' || typeof c.lon !== 'number') return null;
                    return (
                      <Marker key={cid} position={[c.lat, c.lon]} icon={createCustomIcon(vr.color)}>
                        <Popup>
                          <strong style={{ color: '#111827' }}>{c.name}</strong>
                          <br />
                          Vehicle: {vr.vehicleId}
                          <br />
                          F:{c.demand.frozen} C:{c.demand.chilled} A:{c.demand.ambient}
                        </Popup>
                      </Marker>
                    );
                  })}
                  {(() => {
                    const polyPositions = getVehicleClinics(vr)
                      .map((id) => getClinic(id))
                      .filter((c) => c && typeof c.lat === 'number' && typeof c.lon === 'number')
                      .map((c) => [c.lat, c.lon]);
                    if (polyPositions.length < 2) return null;
                    return (
                      <Polyline
                        positions={[...polyPositions, polyPositions[0]]}
                        pathOptions={{ color: vr.color, weight: 2, dashArray: '5, 5', opacity: 0.8 }}
                      />
                    );
                  })()}
                </React.Fragment>
              ))}
          </MapContainer>
        </div>

        {/* Terminal */}
        <TerminalPanel
          logs={logs}
          logsEndRef={logsEndRef}
          isRunning={isRunning}
          onRun={handleRun}
          btnLabel="Run Clustering"
          idleText='Ready. Click "Run Clustering" to start the vehicular clustering pipeline...'
        />
      </div>

      {/* Sidebar */}
      <div className="sidebar" style={{ maxHeight: 'calc(100vh - 120px)', overflowY: 'auto', paddingRight: '10px' }}>
        {vehicleRoutes ? (
          <>
            <div className="card glass-panel" style={{ padding: '1rem', marginBottom: '0.5rem' }}>
              <div className="stat-row" style={{ border: 'none', padding: 0 }}>
                <span className="stat-label">Total Qubits</span>
                <span className="stat-value success">{totalQubits} / {maxQubits}</span>
              </div>
              <div className="stat-row" style={{ border: 'none', padding: '0.25rem 0 0' }}>
                <span className="stat-label">Sub-clusters</span>
                <span className="stat-value">{allSubclusters.length}</span>
              </div>
            </div>
            <div className="cluster-list">
              {vehicleRoutes.map((vr) => {
                const allIds = getVehicleClinics(vr);
                const demand = computeDemand(allIds);
                return (
                  <div key={vr.vehicleId} className="cluster-item" style={{ borderLeft: `4px solid ${vr.color}` }}>
                    <div className="cluster-header">
                      <span className="cluster-title">
                        <Truck size={14} style={{ display: 'inline', marginRight: '4px' }} />
                        {vr.vehicleId}
                      </span>
                      <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                        <span className="badge" style={{ background: `${vr.color}20`, color: vr.color }}>
                          {allIds.length} nodes
                        </span>
                        <span
                          className="badge"
                          style={{
                            background:
                              vr.solver === 'Classical'
                                ? 'rgba(107,114,128,0.15)'
                                : 'rgba(139,92,246,0.15)',
                            color: vr.solver === 'Classical' ? '#9ca3af' : '#a78bfa',
                            fontSize: '0.7rem',
                          }}
                        >
                          {vr.solver}
                        </span>
                      </div>
                    </div>
                    <div className="capacity-bars">
                      {['frozen', 'chilled', 'ambient'].map((temp, idx) => {
                        const colors = ['#3b82f6', '#10b981', '#f59e0b'];
                        const labels = ['F', 'C', 'A'];
                        return (
                          <div key={temp} className="cap-bar-wrapper">
                            <span className="cap-bar-label">{labels[idx]} ({demand[temp]})</span>
                            <div className="cap-bar-bg">
                              <div
                                className="cap-bar-fill"
                                style={{
                                  width: `${(demand[temp] / CAPACITY[temp]) * 100}%`,
                                  background: colors[idx],
                                }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      {vr.trips.map((trip, ti) => (
                        <div key={ti} style={{ marginBottom: '0.25rem' }}>
                          <span style={{ color: '#e5e7eb' }}>
                            {vr.trips.length > 1 ? `Trip ${ti + 1}` : 'Trip'}:
                          </span>{' '}
                          C({trip.clinics.length},4) = {trip.subclusters.length} sub-clusters{' '}
                          <CheckCircle2 size={11} style={{ display: 'inline', color: '#34d399' }} />
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          <div
            className="card glass-panel"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px' }}
          >
            <p style={{ color: 'var(--text-secondary)', textAlign: 'center' }}>
              Run the clustering pipeline to see vehicle assignments and sub-clusters.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
