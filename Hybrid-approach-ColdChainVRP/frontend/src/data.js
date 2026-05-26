// ─────────────────────────────────────────
// API base URL — override with VITE_API_BASE env var for production
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:5000';

// ─────────────────────────────────────────
// DEPOT — Regional Vaccine Hub, Chennai
// ─────────────────────────────────────────
export const DEPOT = { id: 0, name: 'Regional Vaccine Depot', lat: 13.0827, lon: 80.2707 };

// ─────────────────────────────────────────
// 15 Chennai clinic presets (GPS-accurate PHCs & hospitals)
// These are read-only geographic anchors — demand/time-window
// are fully editable in the Input tab at runtime.
// ─────────────────────────────────────────
export const PRESET_CLINICS = [
  { id: 1,  name: 'Tambaram PHC',          lat: 12.9249, lon: 80.1000 },
  { id: 2,  name: 'Chromepet Clinic',      lat: 12.9516, lon: 80.1462 },
  { id: 3,  name: 'Pallavaram PHC',        lat: 12.9675, lon: 80.1491 },
  { id: 4,  name: 'Guindy Hospital',       lat: 13.0067, lon: 80.2206 },
  { id: 5,  name: 'Adyar Clinic',          lat: 13.0012, lon: 80.2565 },
  { id: 6,  name: 'Velachery PHC',         lat: 12.9815, lon: 80.2180 },
  { id: 7,  name: 'Porur Clinic',          lat: 13.0350, lon: 80.1567 },
  { id: 8,  name: 'Ambattur PHC',          lat: 13.1143, lon: 80.1548 },
  { id: 9,  name: 'Avadi Clinic',          lat: 13.1067, lon: 80.0950 },
  { id: 10, name: 'Poonamallee PHC',       lat: 13.0467, lon: 80.0956 },
  { id: 11, name: 'Perambur PHC',          lat: 13.1148, lon: 80.2345 },
  { id: 12, name: 'Royapettah Hospital',   lat: 13.0524, lon: 80.2609 },
  { id: 13, name: 'Kodambakkam PHC',       lat: 13.0524, lon: 80.2209 },
  { id: 14, name: 'Tondiarpet Clinic',     lat: 13.1220, lon: 80.2891 },
  { id: 15, name: 'Sholinganallur PHC',    lat: 12.9010, lon: 80.2279 },
];

// ─────────────────────────────────────────
// Legacy CLINICS — kept for ScenarioPanel / CompareTab backward compat.
// The 10-clinic easy scenario continues to use this.
// ─────────────────────────────────────────
export const CLINICS = [
  { id: 1,  name: 'Tambaram PHC',      lat: 12.9249, lon: 80.1000, demand: { frozen: 2, chilled: 3, ambient: 4 } },
  { id: 2,  name: 'Chromepet Clinic',  lat: 12.9516, lon: 80.1462, demand: { frozen: 1, chilled: 2, ambient: 3 } },
  { id: 3,  name: 'Pallavaram PHC',    lat: 12.9675, lon: 80.1491, demand: { frozen: 3, chilled: 1, ambient: 2 } },
  { id: 4,  name: 'Guindy Hospital',   lat: 13.0067, lon: 80.2206, demand: { frozen: 2, chilled: 4, ambient: 1 } },
  { id: 5,  name: 'Adyar Clinic',      lat: 13.0012, lon: 80.2565, demand: { frozen: 1, chilled: 3, ambient: 3 } },
  { id: 6,  name: 'Velachery PHC',     lat: 12.9815, lon: 80.2180, demand: { frozen: 4, chilled: 2, ambient: 2 } },
  { id: 7,  name: 'Porur Clinic',      lat: 13.0350, lon: 80.1567, demand: { frozen: 2, chilled: 2, ambient: 4 } },
  { id: 8,  name: 'Ambattur PHC',      lat: 13.1143, lon: 80.1548, demand: { frozen: 1, chilled: 4, ambient: 2 } },
  { id: 9,  name: 'Avadi Clinic',      lat: 13.1067, lon: 80.0950, demand: { frozen: 3, chilled: 1, ambient: 3 } },
  { id: 10, name: 'Poonamallee PHC',   lat: 13.0467, lon: 80.0956, demand: { frozen: 2, chilled: 3, ambient: 1 } },
];

export const VEHICLES = [
  { id: 'V1', capacity: { frozen: 10, chilled: 12, ambient: 15 } },
  { id: 'V2', capacity: { frozen: 10, chilled: 12, ambient: 15 } },
];

export const CAPACITY = VEHICLES[0].capacity;

export const SPOILAGE = {
  frozen:  { alpha: 0.001, value: 500 },
  chilled: { alpha: 0.010, value: 200 },
  ambient: { alpha: 0.050, value:  50 },
};

// ─────────────────────────────────────────
// VACCINES CATALOG
// Each vaccine has a fixed compartment (physics, not preference).
// alpha = spoilage decay rate; value = ₹ per vial/dose
// ─────────────────────────────────────────
export const VACCINES = [
  {
    id: 'mrna',
    name: 'mRNA Vaccine',
    compartment: 'frozen',
    temp: '-20°C',
    alpha: 0.001,
    value: 500,
    unit: 'vial',
    reason: 'mRNA strands degrade irreversibly above -20°C within hours.',
  },
  {
    id: 'protein_subunit',
    name: 'Protein Subunit',
    compartment: 'chilled',
    temp: '2–8°C',
    alpha: 0.010,
    value: 200,
    unit: 'vial',
    reason: 'Adjuvanted protein antigens precipitate if frozen or kept above 8°C.',
  },
  {
    id: 'opv',
    name: 'Oral Vaccine (OPV)',
    compartment: 'ambient',
    temp: '15–25°C',
    alpha: 0.050,
    value: 50,
    unit: 'dose',
    reason: 'Live attenuated poliovirus tolerates ambient temps for short hauls.',
  },
  {
    id: 'live_attenuated',
    name: 'Live Attenuated',
    compartment: 'frozen',
    temp: '-20°C',
    alpha: 0.002,
    value: 450,
    unit: 'vial',
    reason: 'Live viral particles lose viability rapidly above freezing.',
  },
  {
    id: 'toxoid',
    name: 'Toxoid (Tetanus/DTP)',
    compartment: 'chilled',
    temp: '2–8°C',
    alpha: 0.008,
    value: 150,
    unit: 'vial',
    reason: 'Aluminium-adjuvanted toxoids flocculate when frozen or overheated.',
  },
  {
    id: 'inactivated',
    name: 'Inactivated (IPV/Hep-B)',
    compartment: 'chilled',
    temp: '2–8°C',
    alpha: 0.012,
    value: 180,
    unit: 'vial',
    reason: 'Inactivated virions are sensitive to temperature excursions above 8°C.',
  },
];


// ─────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────

/** Compute total demand for a set of clinic IDs. */
export function computeDemand(clinicIds) {
  const frozen  = clinicIds.reduce((s, id) => s + (CLINICS.find(c => c.id === id)?.demand.frozen  || 0), 0);
  const chilled = clinicIds.reduce((s, id) => s + (CLINICS.find(c => c.id === id)?.demand.chilled || 0), 0);
  const ambient = clinicIds.reduce((s, id) => s + (CLINICS.find(c => c.id === id)?.demand.ambient || 0), 0);
  return { frozen, chilled, ambient, total: frozen + chilled + ambient };
}

/** Qubit count for an n-node sub-cluster: x[i][t] formulation → n² qubits. */
export function computeQubits(n) { return n * n; }

/** Fetch live clustering result from the backend. Returns null on error. */
export async function fetchClusteringResult() {
  try {
    const res = await fetch(`${API_BASE}/api/clustering-result`);
    const data = await res.json();
    return data.error ? null : data;
  } catch {
    return null;
  }
}

// Derived scenario stats
export const SCENARIO_STATS = (() => {
  const totalDemand = computeDemand(CLINICS.map(c => c.id));
  return {
    totalLocations: 1 + CLINICS.length,
    numClinics: CLINICS.length,
    numVehicles: VEHICLES.length,
    totalDemand: totalDemand.total,
    demandBreakdown: totalDemand,
  };
})();
