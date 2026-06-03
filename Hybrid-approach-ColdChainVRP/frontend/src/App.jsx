import { useState, useEffect } from 'react';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { Play, GitCompare, Settings, Activity, BookOpen, Sparkles, Cpu, BarChart2 } from 'lucide-react';

import ScenarioPanel from './components/ScenarioPanel';
import CompareTab    from './components/CompareTab';
import InputTab      from './components/InputTab';
import ResultsView   from './components/ResultsView';
import ExplainerTab  from './components/ExplainerTab';
import FutureResultsTab from './components/FutureResultsTab';
import HardwareTab   from './components/HardwareTab';
import BenchmarkingTab from './components/BenchmarkingTab';
import { API_BASE }  from './data';
import { runSSE }    from './utils/sse';
import cryoLogo     from './assets/cryo_logo.png';

// Fix Leaflet default marker icons once at app level
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl:       'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl:     'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

export default function App() {
  const [activeTab,      setActiveTab]      = useState('input');
  const [scenarioMeta,   setScenarioMeta]   = useState(null);
  const [theme,          setTheme]          = useState('dark');
  const [loading,        setLoading]        = useState(true);
  // pipelineConfig is set after a successful /api/configure POST
  // and signals the Scenarios tab to show ResultsView instead of ScenarioPanels
  const [pipelineConfig, setPipelineConfig] = useState(null);
  const [pipelineLogs,   setPipelineLogs]   = useState([]);
  const [pipelineRunning,setPipelineRunning]= useState(false);

  // Fetch scenario metadata once (cached server-side after first call)
  useEffect(() => {
    fetch(`${API_BASE}/api/scenarios`)
      .then(r => r.json())
      .then(d => { if (!d.error) setScenarioMeta(d); })
      .catch(() => {});
      
    // Load cached run
    try {
      const cached = localStorage.getItem('vrp_last_run');
      if (cached) {
        const data = JSON.parse(cached);
        if (data.config) {
          setPipelineConfig({ payload: data.config, apiResponse: { status: 'ok' } });
        }
      }
    } catch (e) {
      console.error('Failed to load cache', e);
    }
    // Initialize premium splash timer
    const timer = setTimeout(() => {
      setLoading(false);
    }, 1800);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  // Trigger a window resize event to force Leaflet to recalculate container bounds
  // and resolve gray screen/rendering issues when switching tabs
  useEffect(() => {
    const timer = setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 200);
    return () => clearTimeout(timer);
  }, [activeTab]);

  // Called by InputTab after /api/configure succeeds
  function handleConfigureAndRun(payload, apiResponse) {
    setPipelineConfig({ payload, apiResponse });
    // Save minimal metadata to trigger results fetch on refresh
    localStorage.setItem('vrp_last_run', JSON.stringify({
      config: payload,
      timestamp: Date.now()
    }));
    setActiveTab('liverun');
    // Kick off the pipeline SSE stream
    runSSE('/api/run-pipeline', setPipelineLogs, setPipelineRunning, () => {});
  }

  const TABS = [
    { id: 'input',     label: 'Input',     icon: Settings  },
    { id: 'liverun',   label: 'Live Run',  icon: Activity  },
    { id: 'scenarios', label: 'Scenarios', icon: Play      },
    { id: 'compare',   label: 'Compare',   icon: GitCompare },
    { id: 'hardware',  label: 'Quantum Hardware', icon: Cpu },
    { id: 'benchmarking', label: 'Benchmarking', icon: BarChart2 },
    { id: 'explainer', label: 'Explainer', icon: BookOpen   },
    { id: 'future',    label: 'Future Results', icon: Sparkles },
  ];

  return (
    <div className="dashboard-container" data-theme={theme}>
      {/* Splash Screen Loading overlay */}
      <div className={`splash-overlay ${!loading ? 'hidden' : ''}`}>
        <img src={cryoLogo} alt="Cryo Logo" className="splash-logo" />
        <h1 className="splash-title">Cryo Hybrid Optimiser</h1>
        <p className="splash-subtitle">Quantum-Classical VRP Initializer</p>
        <div className="splash-progress-track">
          <div className="splash-progress-bar"></div>
        </div>
      </div>

      <header className="app-header">
        <div className="app-title-block" style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div>
            <p className="app-kicker" style={{ color: theme === 'dark' ? '#e2e8f0' : '#475569', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', margin: 0, fontSize: '0.75rem' }}>Quantum-Classical VRP</p>
            <h1 style={{ margin: '0.1rem 0 0 0', fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
              Cryo Hybrid Optimiser
            </h1>
            <p className="app-sub" style={{ margin: '0.2rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Thermodynamic Cold-Chain VRP Solver & NISQ-Era Hybrid QAOA Coprocessor
            </p>
          </div>
        </div>
        <div className="header-actions">
          <nav className="tab-segment" aria-label="Main">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                className={`tab-btn ${activeTab === id ? 'active' : ''}`}
                onClick={() => setActiveTab(id)}
              >
                <Icon size={15} strokeWidth={2} aria-hidden />
                {label}
              </button>
            ))}
          </nav>

        </div>
      </header>

      {/* ── Input tab ── */}
      <div style={{ display: activeTab === 'input' ? 'block' : 'none' }}>
        <InputTab onConfigureAndRun={handleConfigureAndRun} pipelineRunning={pipelineRunning} />
      </div>

      {/* ── Live Run tab ── */}
      <div style={{ display: activeTab === 'liverun' ? 'block' : 'none' }}>
        {pipelineConfig ? (
          <ResultsView
            config={pipelineConfig.payload}
            runPipeline={runSSE}
            pipelineLogs={pipelineLogs}
            pipelineRunning={pipelineRunning}
          />
        ) : (
          <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center' }}>
            <Activity size={32} style={{ opacity: 0.5, marginBottom: '1rem' }} />
            <h3>No Active Run</h3>
            <p style={{ color: 'var(--text-muted)' }}>Configure and run a scenario from the Input tab to see live results here.</p>
          </div>
        )}
      </div>

      {/* ── Scenarios tab ── */}
      <div style={{ display: activeTab === 'scenarios' ? 'block' : 'none' }}>
        <div className="app-scenarios-grid">
          <ScenarioPanel
            scenarioKey="tough"
            meta={scenarioMeta?.tough}
            pipelineEndpoint="/api/run-pipeline-easy"
            resultsEndpoint="/api/results-tough"
            label="Scenario 1 (Baseline)"
            subtitle="10 clinics · 2 vehicles · uniform 8–18h windows"
            accentColor="var(--solver-qaoa)"
            runPipeline={runSSE}
          />
          <ScenarioPanel
            scenarioKey="easy"
            meta={scenarioMeta?.easy}
            pipelineEndpoint="/api/run-pipeline"
            resultsEndpoint="/api/results"
            label="Scenario 2 (Configured)"
            subtitle="Based on your inputs in the Input tab"
            accentColor="var(--solver-classical)"
            runPipeline={runSSE}
          />
          <ScenarioPanel
            scenarioKey="tough4"
            meta={scenarioMeta?.tough4}
            pipelineEndpoint="/api/run-pipeline-scenario4"
            resultsEndpoint="/api/results-tough4"
            label="Scenario 3 (Edge Cases)"
            subtitle="5 clinics · 4 vehicles · demand overflow node splitting"
            accentColor="var(--solver-gurobi)"
            runPipeline={runSSE}
          />
          <ScenarioPanel
            scenarioKey="tough3"
            meta={scenarioMeta?.tough3}
            pipelineEndpoint="/api/run-pipeline-tough3"
            resultsEndpoint="/api/results-tough3"
            label="Scenario 4 (Stress Test)"
            subtitle="30 clinics · 3 vehicles · non-uniform operating windows"
            accentColor="var(--solver-alns)"
            runPipeline={runSSE}
          />
        </div>
      </div>

      {/* ── Compare tab ── */}
      <div style={{ display: activeTab === 'compare' ? 'block' : 'none' }}>
        <CompareTab runPipeline={runSSE} compareActive={activeTab === 'compare'} />
      </div>

      {/* ── Quantum Hardware tab ── */}
      <div style={{ display: activeTab === 'hardware' ? 'block' : 'none' }}>
        <HardwareTab runPipeline={runSSE} activeTab={activeTab} />
      </div>

      {/* ── Benchmarking tab ── */}
      <div style={{ display: activeTab === 'benchmarking' ? 'block' : 'none' }}>
        <BenchmarkingTab />
      </div>

      {/* ── Explainer tab ── */}
      <div style={{ display: activeTab === 'explainer' ? 'block' : 'none' }}>
        <ExplainerTab activeTab={activeTab} />
      </div>

      {/* ── Future Results tab ── */}
      <div style={{ display: activeTab === 'future' ? 'block' : 'none' }}>
        <FutureResultsTab activeTab={activeTab} />
      </div>
    </div>
  );
}
