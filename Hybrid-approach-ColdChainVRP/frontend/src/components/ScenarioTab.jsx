import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { Navigation, Activity } from 'lucide-react';
import { DEPOT, CLINICS, SCENARIO_STATS } from '../data';

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

export default function ScenarioTab() {
  return (
    <div className="content-grid">
      {/* Map */}
      <div className="main-content">
        <div className="map-container" style={{ height: '600px' }}>
          <MapContainer
            center={[13.045, 80.18]}
            zoom={11}
            style={{ height: '100%', width: '100%', background: '#111827' }}
          >
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
            />
            <Marker position={[DEPOT.lat, DEPOT.lon]} icon={depotIcon}>
              <Popup>
                <strong style={{ color: '#111827' }}>{DEPOT.name}</strong>
                <br />Central Hub
              </Popup>
            </Marker>
            {CLINICS.map((c) => (
              <Marker key={c.id} position={[c.lat, c.lon]} icon={createCustomIcon('#3b82f6')}>
                <Popup>
                  <strong style={{ color: '#111827' }}>{c.name}</strong>
                  <br />
                  F:{c.demand.frozen} C:{c.demand.chilled} A:{c.demand.ambient}
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
      </div>

      {/* Sidebar */}
      <div className="sidebar">
        <div className="card glass-panel">
          <h3>
            <Navigation size={20} className="gradient-text" /> Base Scenario
          </h3>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem', lineHeight: '1.5' }}>
            <p style={{ marginBottom: '0.75rem' }}>
              <strong>The Scenario:</strong> Coordinating a cold-chain delivery network across Chennai.
              The network consists of <strong>{SCENARIO_STATS.totalLocations} locations</strong>: 1 Central
              Depot and {SCENARIO_STATS.numClinics} surrounding medical clinics.
            </p>
            <p>
              <strong>The Demand:</strong> The clinics collectively require{' '}
              <strong>{SCENARIO_STATS.totalDemand} units</strong> of medical supplies split across 3
              temperature compartments: <em>Frozen</em>, <em>Chilled</em>, and <em>Ambient</em>.
            </p>
          </div>
          <div className="stat-row">
            <span className="stat-label">Total Locations</span>
            <span className="stat-value">
              {SCENARIO_STATS.totalLocations} (1 Depot, {SCENARIO_STATS.numClinics} Clinics)
            </span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Total Demand</span>
            <span className="stat-value">{SCENARIO_STATS.totalDemand} units</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Available Fleet</span>
            <span className="stat-value">{SCENARIO_STATS.numVehicles} Vehicles</span>
          </div>
        </div>

        <div className="card glass-panel" style={{ marginTop: '1rem' }}>
          <h3 style={{ marginBottom: '1rem' }}>
            <Activity size={20} className="gradient-text" /> Individual Node Demand
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {CLINICS.map((c) => (
              <div
                key={c.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.5rem 0.75rem',
                  background: 'rgba(255,255,255,0.03)',
                  borderRadius: '6px',
                  border: '1px solid rgba(255,255,255,0.05)',
                }}
              >
                <span style={{ fontWeight: 500, color: '#e5e7eb', fontSize: '0.85rem' }}>{c.name}</span>
                <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.85rem', fontFamily: 'monospace' }}>
                  <span style={{ color: '#3b82f6' }}>F:{c.demand.frozen}</span>
                  <span style={{ color: '#10b981' }}>C:{c.demand.chilled}</span>
                  <span style={{ color: '#f59e0b' }}>A:{c.demand.ambient}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
