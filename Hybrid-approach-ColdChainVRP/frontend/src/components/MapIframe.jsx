import React, { useState, useEffect } from 'react';
import { API_BASE } from '../data';

export default function MapIframe({ routes, depot, clinics, hideLines = false }) {
  const [mapHtml, setMapHtml] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!depot || !clinics || clinics.length === 0) return;
    
    let isMounted = true;
    setLoading(true);
    
    fetch(`${API_BASE}/api/map`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ routes: routes || {}, depot, clinics, hide_lines: hideLines })
    })
    .then(async res => {
      const text = await res.text();
      try { return JSON.parse(text); } catch(e) { throw e; }
    })
    .then(data => {
      if (isMounted && data?.map_html) {
        setMapHtml(data.map_html);
      }
    })
    .catch(console.error)
    .finally(() => {
      if (isMounted) setLoading(false);
    });

    return () => { isMounted = false; };
  }, [depot, clinics, routes, hideLines]);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: '#000000', borderRadius: '8px', overflow: 'hidden' }}>
      {loading && (
        <div style={{ position: 'absolute', inset: 0, zIndex: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(4px)', flexDirection: 'column', gap: '0.75rem' }}>
          <div style={{ width: 28, height: 28, border: `3px solid rgba(255,255,255,0.1)`, borderTopColor: '#ffffff', borderRadius: '50%', animation: 'spin 0.9s linear infinite' }} />
          <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>Loading map data...</span>
        </div>
      )}
      {mapHtml ? (
        <iframe 
          srcDoc={mapHtml} 
          style={{ width: '100%', height: '100%', border: 'none', background: '#000000' }} 
          title="Interactive Map"
        />
      ) : (
        <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#000000', color: '#6b7280' }}>
          {!loading && "Map not available"}
        </div>
      )}
    </div>
  );
}
