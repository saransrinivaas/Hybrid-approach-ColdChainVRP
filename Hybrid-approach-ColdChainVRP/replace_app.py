import re
import os

with open('frontend/src/App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Add Activity icon import
content = content.replace("from 'lucide-react';", ", Activity } from 'lucide-react';")

# Change handleConfigureAndRun to navigate to 'liverun'
content = content.replace("setActiveTab('scenarios');", "setActiveTab('liverun');")

# Change TABS array
old_tabs = """  const TABS = [
    { id: 'input',     label: 'Input',     icon: Settings  },
    { id: 'scenarios', label: 'Scenarios', icon: Play      },
    { id: 'compare',   label: 'Compare',   icon: GitCompare },
  ];"""
new_tabs = """  const TABS = [
    { id: 'input',     label: 'Input',     icon: Settings  },
    { id: 'scenarios', label: 'Scenarios', icon: Play      },
    { id: 'liverun',   label: 'Live Run',  icon: Activity  },
    { id: 'compare',   label: 'Compare',   icon: GitCompare },
  ];"""
content = content.replace(old_tabs, new_tabs)

# Change the Scenarios tab div
old_scenarios_div = """      {/* ── Scenarios tab — shows ResultsView after configure, ScenarioPanels otherwise ── */}
      <div style={{ display: activeTab === 'scenarios' ? 'block' : 'none' }}>
        {pipelineConfig ? (
          <ResultsView
            config={pipelineConfig.payload}
            runPipeline={runSSE}
            pipelineLogs={pipelineLogs}
            pipelineRunning={pipelineRunning}
          />
        ) : (
          <div className="app-scenarios-grid">
            <ScenarioPanel
              scenarioKey="easy"
              meta={scenarioMeta?.easy}
              pipelineEndpoint="/api/run-pipeline-easy"
              resultsEndpoint="/api/results"
              label="Easy scenario"
              subtitle="10 clinics · 2 vehicles · uniform 8–18h windows"
              accentColor="var(--solver-classical)"
              runPipeline={runSSE}
            />
            <ScenarioPanel
              scenarioKey="tough"
              meta={scenarioMeta?.tough}
              pipelineEndpoint="/api/run-pipeline-tough"
              resultsEndpoint="/api/results-tough"
              label="Tough scenario"
              subtitle="15 clinics · 3 vehicles · 6 tight windows · OR-Tools: no solution"
              accentColor="var(--bad)"
              runPipeline={runSSE}
            />
          </div>
        )}
      </div>"""

new_scenarios_div = """      {/* ── Live Run tab ── */}
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
            pipelineEndpoint="/api/run-pipeline-easy"
            resultsEndpoint="/api/results"
            label="Easy scenario"
            subtitle="10 clinics · 2 vehicles · uniform 8–18h windows"
            accentColor="var(--solver-classical)"
            runPipeline={runSSE}
          />
        </div>
      </div>"""

content = content.replace(old_scenarios_div, new_scenarios_div)

with open('frontend/src/App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
