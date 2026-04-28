/**
 * app.jsx — React application for Orbital Sentinel Module 2.
 *
 * Loads static JSON on mount (page works even if FastAPI is down).
 * Connects to the FastAPI what-if API for scenario overlays.
 *
 * Architecture (MODULE2_PLAN.md):
 *   - 3 bifurcation diagrams side by side (D3 via chart.js)
 *   - Control panel: preset buttons + parameter inputs + scenario list
 *   - Traffic lights update per shell per scenario
 *   - Max 5 overlays; "Clear all" appears after 5
 *   - Debounced API calls (400 ms after slider stop)
 */

"use strict";

const { useState, useEffect, useRef, useCallback } = React;

/* -------------------------------------------------------------------------
 * Constants (from MODULE2_PLAN.md)
 * ----------------------------------------------------------------------- */
const OVERLAY_COLORS = ["#E76F51", "#2A9D8F", "#E9C46A", "#9B5DE5", "#F72585"];
const MAX_OVERLAYS = 5;
const API_BASE = "http://localhost:8000";

const SHELL_NAMES = ["Shell_A_600km", "Shell_B_800km", "Shell_C_1000km"];
const SHELL_KEYS  = ["A", "B", "C"];

const PRESETS = [
  { label: "Starlink doubles",  L_multiplier: 2.0, debris_removal_rate: 0,   gamma_multiplier: 1.0 },
  { label: "ESA removes 5/yr", L_multiplier: 1.0, debris_removal_rate: 5,   gamma_multiplier: 1.0 },
  { label: "Major collision",   L_multiplier: 1.0, debris_removal_rate: 0,   gamma_multiplier: 1.5 },
];

/* -------------------------------------------------------------------------
 * TrafficLight component
 * ----------------------------------------------------------------------- */
function TrafficLight({ status }) {
  const colors = { green: "#2DC653", amber: "#F4A100", red: "#D62828" };
  return (
    <span
      className={`traffic-light tl-${status}`}
      style={{ background: colors[status] || "#888" }}
      title={status.toUpperCase()}
    />
  );
}

/* -------------------------------------------------------------------------
 * ShellPanel — wrapper that holds one D3 chart + traffic light header
 * ----------------------------------------------------------------------- */
function ShellPanel({ shellName, shellKey, baseCurves, currentState, chartRefs }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!baseCurves || !currentState || !containerRef.current) return;
    // Clear any previous chart
    containerRef.current.innerHTML = "";
    const chart = createBifurcationChart(
      containerRef.current,
      shellName,
      shellKey,
      baseCurves,
      currentState,
    );
    chartRefs.current[shellKey] = chart;
  }, [baseCurves, currentState]);

  const shellState = currentState?.shells[shellName];
  const altLabel = { A: "600 km", B: "800 km", C: "1000 km" }[shellKey];

  return (
    <div className="shell-panel">
      <div className="shell-header">
        {shellState && <TrafficLight status={shellState.traffic_light} />}
        <span className="shell-title">Shell {shellKey} — {altLabel}</span>
      </div>
      <div className="chart-container" ref={containerRef} />
    </div>
  );
}

/* -------------------------------------------------------------------------
 * ScenarioItem — one row in the active scenario list
 * ----------------------------------------------------------------------- */
function ScenarioItem({ scenario, index, onRemove }) {
  return (
    <div className="scenario-item">
      <span
        className="scenario-swatch"
        style={{ background: OVERLAY_COLORS[index % OVERLAY_COLORS.length] }}
      />
      <span className="scenario-label">{scenario.label}</span>
      <div className="scenario-lights">
        {SHELL_KEYS.map(k => (
          <TrafficLight key={k} status={scenario.shells[k].traffic_light} />
        ))}
      </div>
      <button className="btn-remove" onClick={() => onRemove(scenario.label)} title="Remove">✕</button>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * App — root component
 * ----------------------------------------------------------------------- */
function App() {
  /* Static data */
  const [baseCurves, setBaseCurves]     = useState(null);
  const [currentState, setCurrentState] = useState(null);
  const [dataError, setDataError]       = useState(null);

  /* What-if panel state */
  const [lMult, setLMult]               = useState(1.0);
  const [debrisRate, setDebrisRate]     = useState(0.0);
  const [gammaMult, setGammaMult]       = useState(1.0);
  const [scenarioLabel, setLabel]       = useState("Custom scenario");

  /* Scenarios */
  const [scenarios, setScenarios]       = useState([]);
  const [computing, setComputing]       = useState(false);
  const [apiError, setApiError]         = useState(null);
  const [apiAvail, setApiAvail]         = useState(null); // null=unknown, true, false

  /* D3 chart references */
  const chartRefs = useRef({});

  /* ---- Load static data on mount ---- */
  useEffect(() => {
    const load = async () => {
      try {
        const [bc, cs] = await Promise.all([
          fetch("data/base_curves.json").then(r => r.json()),
          fetch("data/shell_current_state.json").then(r => r.json()),
        ]);
        setBaseCurves(bc);
        setCurrentState(cs);
      } catch (e) {
        setDataError("Failed to load static data. Run scripts/export_frontend_data.py first.");
      }
    };
    load();
  }, []);

  /* ---- Check API availability and reset server state on mount ---- */
  useEffect(() => {
    fetch(`${API_BASE}/api/health`)
      .then(r => {
        if (r.ok) {
          setApiAvail(true);
          // Reset any leftover server-side scenario state from previous sessions
          return fetch(`${API_BASE}/api/whatif/clear`, { method: "DELETE" });
        } else {
          setApiAvail(false);
        }
      })
      .catch(() => setApiAvail(false));
  }, []);

  /* ---- Apply a scenario to all charts ---- */
  const applyScenarioToCharts = useCallback((scenario, index) => {
    SHELL_KEYS.forEach(k => {
      const chart = chartRefs.current[k];
      if (!chart) return;
      chart.addOverlay(scenario.shells[k], OVERLAY_COLORS[index % OVERLAY_COLORS.length], scenario.label);
      chart.updateTrafficLight(scenario.shells[k].traffic_light);
    });
  }, []);

  /* ---- Remove a scenario from charts and state ---- */
  const handleRemoveScenario = useCallback(async (label) => {
    SHELL_KEYS.forEach(k => chartRefs.current[k]?.removeOverlay(label));

    // Call API clear + replay remaining
    await fetch(`${API_BASE}/api/whatif/clear`, { method: "DELETE" });

    setScenarios(prev => {
      const remaining = prev.filter(s => s.label !== label);
      // Restore remaining overlays in order
      SHELL_KEYS.forEach(k => chartRefs.current[k]?.clearOverlays());

      remaining.forEach((s, i) => {
        SHELL_KEYS.forEach(k => {
          chartRefs.current[k]?.addOverlay(s.shells[k], OVERLAY_COLORS[i], s.label);
          chartRefs.current[k]?.updateTrafficLight(s.shells[k].traffic_light);
        });
      });

      // After removal, revert to base traffic lights if no scenarios left
      if (remaining.length === 0 && currentState) {
        SHELL_KEYS.forEach((k, i) => {
          const tl = currentState.shells[SHELL_NAMES[i]]?.traffic_light;
          if (tl) chartRefs.current[k]?.updateTrafficLight(tl);
        });
      }

      return remaining;
    });
  }, [currentState]);

  /* ---- Clear all ---- */
  const handleClearAll = useCallback(async () => {
    await fetch(`${API_BASE}/api/whatif/clear`, { method: "DELETE" });
    SHELL_KEYS.forEach(k => chartRefs.current[k]?.clearOverlays());
    if (currentState) {
      SHELL_KEYS.forEach((k, i) => {
        const tl = currentState.shells[SHELL_NAMES[i]]?.traffic_light;
        if (tl) chartRefs.current[k]?.updateTrafficLight(tl);
      });
    }
    setScenarios([]);
    setApiError(null);
    // Reset form to defaults
    setLMult(1.0);
    setDebrisRate(0.0);
    setGammaMult(1.0);
    setLabel("Custom scenario");
  }, [currentState]);

  /* ---- Compute what-if ---- */
  const handleCompute = useCallback(async (params = null) => {
    if (scenarios.length >= MAX_OVERLAYS) return;
    if (!apiAvail) { setApiError("FastAPI server is not running. Start it with: uvicorn api.main:app --port 8000"); return; }

    const body = params || {
      L_multiplier: lMult,
      debris_removal_rate: debrisRate,
      gamma_multiplier: gammaMult,
      label: scenarioLabel,
    };

    setComputing(true);
    setApiError(null);

    try {
      const res = await fetch(`${API_BASE}/api/whatif`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "API error");
      }
      const scenario = await res.json();
      const idx = scenarios.length;
      setScenarios(prev => [...prev, scenario]);
      applyScenarioToCharts(scenario, idx);
    } catch (e) {
      setApiError(`Computation failed: ${e.message}`);
    } finally {
      setComputing(false);
    }
  }, [scenarios, apiAvail, lMult, debrisRate, gammaMult, scenarioLabel, applyScenarioToCharts]);

  /* ---- Preset handler — fills sliders only, does not auto-submit ---- */
  const handlePreset = useCallback((preset) => {
    setLMult(preset.L_multiplier);
    setDebrisRate(preset.debris_removal_rate);
    setGammaMult(preset.gamma_multiplier);
    setLabel(preset.label);
  }, []);

  /* ---- Render ---- */

  if (dataError) {
    return <div className="error-banner">{dataError}</div>;
  }

  if (!baseCurves || !currentState) {
    return <div className="loading">Loading bifurcation data…</div>;
  }

  const atMax = scenarios.length >= MAX_OVERLAYS;

  return (
    <div className="app">
      {/* Nav bar */}
      <nav className="nav-bar">
        <a href="index.html" className="active">Simulator</a>
        <a href="dashboard.html">Dashboard</a>
      </nav>

      {/* Header */}
      <header className="app-header">
        <h1>Orbital Sentinel — Kessler Syndrome Scenario Simulator</h1>
        <div className="api-status">
          API:{" "}
          {apiAvail === null ? "checking…" :
           apiAvail ? <span className="api-ok">online</span> :
                      <span className="api-down">offline (base view only)</span>}
        </div>
      </header>

      {/* Three bifurcation diagrams */}
      <div className="charts-row">
        {SHELL_NAMES.map((name, i) => (
          <ShellPanel
            key={name}
            shellName={name}
            shellKey={SHELL_KEYS[i]}
            baseCurves={baseCurves}
            currentState={currentState}
            chartRefs={chartRefs}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="legend-row">
        <span className="legend-item"><svg width="28" height="10"><line x1="0" y1="5" x2="28" y2="5" stroke="#2166ac" strokeWidth="2.2"/></svg> Stable (lower) branch</span>
        <span className="legend-item"><svg width="28" height="10"><line x1="0" y1="5" x2="28" y2="5" stroke="#2166ac" strokeWidth="2.2" strokeDasharray="6 4"/></svg> Unstable (upper) branch</span>
        <span className="legend-item"><svg width="28" height="10"><line x1="0" y1="5" x2="28" y2="5" stroke="#D62828" strokeWidth="1.5" strokeDasharray="8 4"/></svg> L<sub>fold</sub> — point of no return</span>
        <span className="legend-item"><span style={{color:"#E76F51", fontSize:"16px"}}>★</span> Current state (2026)</span>
      </div>

      {/* Control panel */}
      <div className="control-panel">
        <div className="panel-section">
          <h3>What-if scenario</h3>

          {/* Preset buttons */}
          <div className="presets">
            {PRESETS.map(p => (
              <button
                key={p.label}
                className="btn-preset"
                disabled={atMax || computing || !apiAvail}
                onClick={() => handlePreset(p)}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Parameter inputs */}
          <div className="params-grid">
            <label>
              Launch rate multiplier
              <span className="param-value">{lMult.toFixed(1)}×</span>
            </label>
            <input type="range" min="0.1" max="10" step="0.1" value={lMult}
              onChange={e => setLMult(parseFloat(e.target.value))} />

            <label>
              Debris removal rate (objects/yr)
              <span className="param-value">{debrisRate.toFixed(0)}</span>
            </label>
            <input type="range" min="0" max="100" step="1" value={debrisRate}
              onChange={e => setDebrisRate(parseFloat(e.target.value))} />

            <label>
              Cascade multiplier (γ)
              <span className="param-value">{gammaMult.toFixed(1)}×</span>
            </label>
            <input type="range" min="0.1" max="10" step="0.1" value={gammaMult}
              onChange={e => setGammaMult(parseFloat(e.target.value))} />

            <label>Scenario label</label>
            <input type="text" value={scenarioLabel} maxLength={80}
              onChange={e => setLabel(e.target.value)} className="label-input" />
          </div>

          <button
            className="btn-compute"
            disabled={atMax || computing || !apiAvail}
            onClick={() => handleCompute()}
          >
            {computing ? "Computing…" : "Add scenario"}
          </button>

          {apiError && <div className="toast-error">{apiError}</div>}
        </div>

        {/* Active scenarios */}
        <div className="panel-section">
          <h3>Active overlays ({scenarios.length}/{MAX_OVERLAYS})</h3>

          {scenarios.length === 0 && (
            <p className="no-scenarios">No scenarios added yet. Use preset buttons or custom sliders above.</p>
          )}

          {scenarios.map((s, i) => (
            <ScenarioItem
              key={s.label + i}
              scenario={s}
              index={i}
              onRemove={handleRemoveScenario}
            />
          ))}

          {scenarios.length > 0 && (
            <button className="btn-clear-all" onClick={handleClearAll}>
              {atMax ? "⚠ Max reached — Clear all scenarios" : "Clear all scenarios"}
            </button>
          )}
        </div>

        {/* Traffic-light legend */}
        <div className="panel-section tl-legend">
          <h3>Traffic light legend</h3>
          <div className="tl-row"><TrafficLight status="green" /> L &lt; 0.80 × L<sub>fold</sub> — Safe</div>
          <div className="tl-row"><TrafficLight status="amber" /> 0.80 ≤ L &lt; 0.95 × L<sub>fold</sub> — Caution</div>
          <div className="tl-row"><TrafficLight status="red" />   L ≥ 0.95 × L<sub>fold</sub> — Critical</div>
        </div>
      </div>

      {/* Tooltip (shared, positioned by chart.js) */}
      <div className="tooltip" style={{ display: "none" }} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
