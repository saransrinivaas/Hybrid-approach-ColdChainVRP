import { useState, useEffect } from 'react';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { Moon, Play, Sun, GitCompare, Settings, Activity, BookOpen, Sparkles } from 'lucide-react';

import ScenarioPanel from './components/ScenarioPanel';
import CompareTab    from './components/CompareTab';
import InputTab      from './components/InputTab';
import ResultsView   from './components/ResultsView';
import ExplainerTab  from './components/ExplainerTab';
import FutureResultsTab from './components/FutureResultsTab';
import { API_BASE }  from './data';
import { runSSE }    from './utils/sse';

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
    { id: 'explainer', label: 'Explainer', icon: BookOpen   },
    { id: 'future',    label: 'Future Results', icon: Sparkles },
  ];

  return (
    <div className="dashboard-container" data-theme={theme}>
      <header className="app-header">
        <div className="app-title-block">
          <p className="app-kicker">Routing lab</p>
          <h1>Cold chain VRP</h1>
          <p className="app-sub">
            Configure vaccine deliveries, run the hybrid QAOA pipeline, and compare against classical solvers.
          </p>
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
          <button
            type="button"
            className="theme-toggle"
            onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          >
            {theme === 'dark' ? <Sun size={15} aria-hidden /> : <Moon size={15} aria-hidden />}
            {theme === 'dark' ? 'Light' : 'Dark'}
          </button>
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
            scenarioKey="easy"
            meta={scenarioMeta?.easy}
            pipelineEndpoint="/api/run-pipeline"
            resultsEndpoint="/api/results"
            label="Scenario 1 (Configured)"
            subtitle="Based on your inputs in the Input tab"
            accentColor="var(--solver-classical)"
            runPipeline={runSSE}
          />
          <ScenarioPanel
            scenarioKey="tough"
            meta={scenarioMeta?.tough}
            pipelineEndpoint="/api/run-pipeline-easy"
            resultsEndpoint="/api/results-tough"
            label="Scenario 2 (Baseline)"
            subtitle="10 clinics · 2 vehicles · uniform 8–18h windows"
            accentColor="var(--solver-qaoa)"
            runPipeline={runSSE}
          />
          <ScenarioPanel
            scenarioKey="tough3"
            meta={scenarioMeta?.tough3}
            pipelineEndpoint="/api/run-pipeline-tough3"
            resultsEndpoint="/api/results-tough3"
            label="Scenario 3 (Stress Test)"
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
