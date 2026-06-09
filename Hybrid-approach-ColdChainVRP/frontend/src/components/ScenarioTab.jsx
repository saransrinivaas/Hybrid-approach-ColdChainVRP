import React from 'react';
import { Navigation, Activity } from 'lucide-react';
import { DEPOT, CLINICS, SCENARIO_STATS } from '../data';
import MapIframe from './MapIframe';



export default function ScenarioTab() {
  return (
    <div className="content-grid">
      {/* Map */}
      <div className="main-content">
        <div className="map-container map-shell map-frame" style={{ height: '600px', position: 'relative', background: '#000000' }}>
          <MapIframe depot={DEPOT} clinics={CLINICS} routes={{}} />
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
