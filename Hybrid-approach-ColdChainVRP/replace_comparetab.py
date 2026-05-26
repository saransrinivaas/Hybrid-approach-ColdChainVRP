import re
import os

with open('frontend/src/components/CompareTab.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove OrtoolsFailBlock
content = re.sub(r"function OrtoolsFailBlock.*?\}\n\nfunction RouteMap", "function RouteMap", content, flags=re.DOTALL)

# 2. Modify ConstraintVerificationBlock getLimits to remove `isTough` logic
content = re.sub(
    r"      frozen: frozen \|\| \(isTough \? 12 : 10\),\n      chilled: chilled \|\| \(isTough \? 14 : 12\),\n      ambient: ambient \|\| \(isTough \? 18 : 15\)",
    r"      frozen: frozen || 10,\n      chilled: chilled || 12,\n      ambient: ambient || 15",
    content
)

# 3. Remove isTough definition
content = content.replace("  const isTough = activeScenario === 'tough';\n", "")

# 4. Modify ConstraintVerificationBlock timewindows logic
old_tw_logic = """    if (type === 'timewindows') {
      if (!isTough) {
        return <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ PASSED (100% Adherence)</span>;
      }
      if (stats.isClassical) {
        return <span style={{ color: 'var(--bad)', fontWeight: 600 }}>✗ FAILED (Time Windows Breached)</span>;
      }
      return <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ PASSED (100% Adherence)</span>;
    }"""
new_tw_logic = """    if (type === 'timewindows') {
      return <span style={{ color: 'var(--good)', fontWeight: 600 }}>✓ PASSED (100% Adherence)</span>;
    }"""
content = content.replace(old_tw_logic, new_tw_logic)

# 5. Remove scenario toggles from CompareTab
old_scenario_pick = """      <div className="scenario-pick">
        {['easy', 'tough'].map((key) => {
          const m = scenarioMeta?.[key];
          const active = activeScenario === key;
          return (
            <button
              key={key}
              type="button"
              data-active={active}
              onClick={() => setActiveScenario(key)}
            >
              <div className="sp-title">
                {key === 'easy' ? (
                  <CheckCircle2 size={15} color="var(--solver-classical)" aria-hidden />
                ) : (
                  <AlertTriangle size={15} color="var(--bad)" aria-hidden />
                )}
                {key === 'easy' ? 'Easy scenario' : 'Tough scenario'}
              </div>
              <div className="sp-meta">
                {m
                  ? `${m.num_clinics} clinics · ${m.num_vehicles} vehicles${
                      m.tight_windows > 0 ? ` · ${m.tight_windows} tight windows` : ''
                    }`
                  : key === 'easy'
                    ? '10 clinics · 2 vehicles · uniform windows'
                    : '15 clinics · 3 vehicles · tight windows'}
              </div>
            </button>
          );
        })}
      </div>"""
content = content.replace(old_scenario_pick, "")

# 6. Remove Tough scenario specific rendering in the return block
start_idx = content.find("            {/* ── For the TOUGH scenario: hide classical metrics, show OR-Tools failure + hybrid summary ── */}")
end_idx = content.find("            )}", start_idx) + 14
end_idx = content.find("          </div>", end_idx)

replacement = """              <>
                <div className="compare-metrics">
                  <MetricCard
                    label="Fleet distance"
                    classical={cl.fleet_distance}
                    qaoa={qaAvailable ? qaM.fleet_distance : null}
                    unit=" km"
                  />
                  <MetricCard
                    label="Fleet spoilage"
                    classical={cl.fleet_spoilage}
                    qaoa={qaAvailable ? qaM.fleet_spoilage : null}
                    unit=" Rs"
                  />
                  <MetricCard
                    label="Total cost"
                    classical={cl.fleet_total_cost}
                    qaoa={qaAvailable ? qaM.fleet_total_cost : null}
                    unit=" Rs"
                  />
                </div>
                <div className="compare-metrics-sub">
                  <MetricCard
                    label="Compute time"
                    classical={cl.total_time}
                    qaoa={qaAvailable ? qaM.total_time : null}
                    unit=" s"
                    lowerIsBetter
                  />
                  <div className="metric-card">
                    <div className="metric-label">QAOA status</div>
                    {qaAvailable ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: 'var(--good)', fontWeight: 600, fontSize: '0.875rem' }}>
                        <CheckCircle2 size={16} aria-hidden />
                        {qa?.solver && String(qa.solver).toLowerCase().includes('hybrid')
                          ? 'Hybrid run (Scenarios tab)'
                          : 'QAOA benchmark (compare.py)'}
                      </div>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                        <Clock size={16} aria-hidden />
                        {qa?.note || 'Run "Classical + QAOA" to add the hybrid solver row.'}
                      </div>
                    )}
                  </div>
                </div>
                <ConstraintVerificationBlock classical={cl} qaoa={qaAvailable ? qa : null} activeScenario={activeScenario} meta={meta} />
              </>"""

content = content[:start_idx] + replacement + content[end_idx:]

# 7. Maps Grid
old_maps = """          <div className="compare-maps-grid" key={`maps-${activeScenario}`}>
            {/* Hide classical map panel for tough scenario where OR-Tools failed */}
            {!ortoolsFailed && (
              <div className="glass-panel compare-map-panel" style={{ padding: '1rem' }}>
                <h3 className="classical">
                  <Cpu size={15} aria-hidden />
                  Classical
                </h3>
                <RouteMap scenarioData={meta} solverResult={cl} height="420px" />
                <RouteTable result={cl} color="var(--solver-classical)" />
              </div>
            )}

            <div className="glass-panel compare-map-panel" style={{ padding: '1rem', gridColumn: ortoolsFailed ? '1 / -1' : undefined }}>
              <h3 className="qaoa">
                <Zap size={15} aria-hidden />
                {qaoaRightTitle}
              </h3>
              {hybridAvailable ? (
                <>
                  <RouteMap scenarioData={meta} solverResult={hyb} height="420px" />
                  <RouteTable result={hyb} color="var(--solver-qaoa)" />
                </>
              ) : qaAvailable ? (
                <>
                  <RouteMap scenarioData={meta} solverResult={qa} height="420px" />
                  <RouteTable result={qa} color="var(--solver-qaoa)" />
                </>
              ) : (
                <div className="qaoa-placeholder">
                  <Zap size={22} strokeWidth={1.5} style={{ opacity: 0.5 }} aria-hidden />
                  <span>No QAOA routes in this file.</span>
                  <span className="faint">Full benchmark is slow; classical-only still populates the left column.</span>
                </div>
              )}
            </div>
          </div>"""

new_maps = """          <div className="compare-maps-grid" key={`maps-${activeScenario}`}>
            <div className="glass-panel compare-map-panel" style={{ padding: '1rem' }}>
              <h3 className="classical">
                <Cpu size={15} aria-hidden />
                Classical
              </h3>
              <RouteMap scenarioData={meta} solverResult={cl} height="420px" />
              <RouteTable result={cl} color="var(--solver-classical)" />
            </div>

            <div className="glass-panel compare-map-panel" style={{ padding: '1rem' }}>
              <h3 className="qaoa">
                <Zap size={15} aria-hidden />
                {qaoaRightTitle}
              </h3>
              {qaAvailable ? (
                <>
                  <RouteMap scenarioData={meta} solverResult={qa} height="420px" />
                  <RouteTable result={qa} color="var(--solver-qaoa)" />
                </>
              ) : (
                <div className="qaoa-placeholder">
                  <Zap size={22} strokeWidth={1.5} style={{ opacity: 0.5 }} aria-hidden />
                  <span>No QAOA routes in this file.</span>
                  <span className="faint">Full benchmark is slow; classical-only still populates the left column.</span>
                </div>
              )}
            </div>
          </div>"""
content = content.replace(old_maps, new_maps)

with open('frontend/src/components/CompareTab.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
