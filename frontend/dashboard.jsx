/**
 * dashboard.jsx — Early Warning Dashboard for Orbital Sentinel Module 3.
 *
 * Non-interactive monitoring display. No sliders.
 * Loads live shell state from GET /api/live on page load.
 * Falls back to cached snapshot if Space-Track query fails.
 *
 * Four sections (MODULE3_PLAN.md):
 *   1. Shell Status Overview — large traffic-light cards, progress bars, stat grids
 *   2. Early Warning Indicators — recovery time, variance, lag-1 AC charts per shell
 *   3. What the Numbers Mean — plain-language explainer
 *   4. Shell C Alert Panel — shown only when Shell C is RED
 */

"use strict";

const { useState, useEffect, useRef } = React;

const API_BASE    = "http://localhost:8000";
const SHELL_NAMES = ["Shell_A_600km", "Shell_B_800km", "Shell_C_1000km"];
const SHELL_KEYS  = ["A", "B", "C"];
const ALT_LABELS  = { A: "600 km", B: "800 km", C: "1000 km" };

const TL_COLORS   = { green: "#2DC653", amber: "#F4A100", red: "#D62828" };
const TL_INTERP   = {
  green: "Well within safe operating margin",
  amber: "Approaching tipping point — recovery time increasing",
  red:   "At or past tipping point — launch rate exceeds critical threshold",
};

/* =========================================================================
 * Nav bar
 * ======================================================================= */
function NavBar() {
  return (
    <nav className="nav-bar">
      <a href="index.html">Simulator</a>
      <a href="dashboard.html" className="active">Dashboard</a>
    </nav>
  );
}

/* =========================================================================
 * Section 1 — Shell Status Cards
 * ======================================================================= */
function ProgressBar({ fraction, status }) {
  const pct = Math.min(fraction * 100, 100);
  const past = fraction > 1.0;
  return (
    <div className="progress-wrap">
      <div className="progress-label">
        <span>0%</span>
        <span>L / L<sub>fold</sub> = {(fraction * 100).toFixed(1)}%</span>
        <span>100%</span>
      </div>
      <div className="progress-bar-bg">
        <div
          className={`progress-bar-fill ${status}`}
          style={{ width: `${pct}%` }}
        />
        {past && <div className="progress-bar-overflow" />}
      </div>
    </div>
  );
}

function StatItem({ label, value, unit }) {
  return (
    <div className="stat-item">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {unit && <span className="stat-unit">{unit}</span>}
    </div>
  );
}

function TrendSpan({ trend }) {
  const cls = trend.startsWith("↑") ? "trend-up"
            : trend.startsWith("↓") ? "trend-down"
            : "trend-stable";
  return <span className={cls}>{trend}</span>;
}

function StatusCard({ shellKey, shellData }) {
  const status = shellData.traffic_light;
  const altLabel = ALT_LABELS[shellKey];
  return (
    <div className={`status-card ${status}`}>
      <div className="card-header">
        <div className="card-tl-dot" style={{ background: TL_COLORS[status] }} />
        <div>
          <div className="card-shell-name">Shell {shellKey} — {altLabel}</div>
          <div className="card-status-text">{status.toUpperCase()}</div>
        </div>
      </div>

      <ProgressBar fraction={shellData.L_fraction} status={status} />

      <div className="stats-grid">
        <StatItem label="S — active hardware" value={shellData.S.toLocaleString()} unit="objects" />
        <StatItem label="D — debris fragments" value={shellData.D.toLocaleString()} unit="objects" />
        <StatItem label="L_current (3yr avg)" value={shellData.L_current.toFixed(1)} unit="objects/yr" />
        <StatItem label="L_fold — tipping point" value={shellData.L_fold.toFixed(1)} unit="objects/yr" />
        <div className="stat-item" style={{ gridColumn: "span 2" }}>
          <span className="stat-label">Launch trend</span>
          <span className="stat-value"><TrendSpan trend={shellData.trend} /></span>
        </div>
      </div>

      <div className="card-interp">{TL_INTERP[status]}</div>
    </div>
  );
}

/* =========================================================================
 * Section 2 — Indicator Charts (D3)
 * ======================================================================= */

function RecoveryTimeChart({ shellName, indicatorData }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current || !indicatorData) return;
    const { L, recovery_time } = indicatorData.recovery_time;
    if (!L || L.length === 0) return;

    ref.current.innerHTML = "";
    const margin = { top: 16, right: 16, bottom: 36, left: 52 };
    const W = ref.current.clientWidth - margin.left - margin.right;
    const H = 140 - margin.top - margin.bottom;

    const svg = d3.select(ref.current).append("svg")
      .attr("width", W + margin.left + margin.right)
      .attr("height", H + margin.top + margin.bottom);
    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    const xScale = d3.scaleLinear().domain([d3.min(L), d3.max(L)]).range([0, W]);
    const rtFinite = recovery_time.filter(v => v != null && isFinite(v) && v > 0);
    const yScale = d3.scaleLog()
      .domain([Math.max(0.1, d3.min(rtFinite) * 0.8), d3.max(rtFinite) * 1.2])
      .range([H, 0]).clamp(true);

    g.append("g").attr("transform", `translate(0,${H})`)
      .call(d3.axisBottom(xScale).ticks(4)
        .tickFormat(d => d >= 1000 ? `${(d/1000).toFixed(0)}k` : d.toFixed(0)));
    g.append("g").call(d3.axisLeft(yScale).ticks(3, "~s"));

    // Axis labels
    g.append("text").attr("x", W / 2).attr("y", H + 30)
      .attr("text-anchor", "middle").attr("font-size", "9px").attr("fill", "#8890aa")
      .text("L (objects/yr)");
    g.append("text").attr("transform", "rotate(-90)")
      .attr("x", -H / 2).attr("y", -42)
      .attr("text-anchor", "middle").attr("font-size", "9px").attr("fill", "#8890aa")
      .text("τ = 1/|α| (yr)");

    const lineGen = d3.line()
      .x((_, i) => xScale(L[i]))
      .y(d => yScale(Math.max(0.1, d)))
      .defined(d => d != null && isFinite(d) && d > 0);

    g.append("path").datum(recovery_time)
      .attr("fill", "none").attr("stroke", "#4a90d9").attr("stroke-width", 1.8)
      .attr("d", lineGen);

    // L_fold marker
    const L_fold = indicatorData.L_fold;
    if (L_fold && xScale(L_fold) <= W) {
      g.append("line")
        .attr("x1", xScale(L_fold)).attr("x2", xScale(L_fold))
        .attr("y1", 0).attr("y2", H)
        .attr("stroke", "#D62828").attr("stroke-width", 1.2).attr("stroke-dasharray", "4 3");
    }
  }, [indicatorData]);

  return <div ref={ref} style={{ width: "100%" }} />;
}

function TimeSeriesChart({ shellName, tArr, vArr, color, yLabel }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current || !tArr || tArr.length === 0) return;

    ref.current.innerHTML = "";
    const margin = { top: 16, right: 16, bottom: 36, left: 52 };
    const W = ref.current.clientWidth - margin.left - margin.right;
    const H = 140 - margin.top - margin.bottom;

    const svg = d3.select(ref.current).append("svg")
      .attr("width", W + margin.left + margin.right)
      .attr("height", H + margin.top + margin.bottom);
    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    const pairs = tArr.map((t, i) => [t, vArr[i]])
      .filter(([t, v]) => t != null && v != null && isFinite(t) && isFinite(v));
    if (pairs.length === 0) return;

    const xScale = d3.scaleLinear().domain(d3.extent(pairs, d => d[0])).range([0, W]);
    const vFinite = pairs.map(d => d[1]).filter(v => isFinite(v));
    const yExt = [d3.min(vFinite) * 0.9, d3.max(vFinite) * 1.1];
    const yScale = d3.scaleLinear().domain(yExt).range([H, 0]).clamp(true);

    g.append("g").attr("transform", `translate(0,${H})`)
      .call(d3.axisBottom(xScale).ticks(4).tickFormat(d => `${d.toFixed(0)}yr`));
    g.append("g").call(d3.axisLeft(yScale).ticks(3, "~s"));

    g.append("text").attr("x", W / 2).attr("y", H + 30)
      .attr("text-anchor", "middle").attr("font-size", "9px").attr("fill", "#8890aa")
      .text("Time (years)");
    g.append("text").attr("transform", "rotate(-90)")
      .attr("x", -H / 2).attr("y", -44)
      .attr("text-anchor", "middle").attr("font-size", "9px").attr("fill", "#8890aa")
      .text(yLabel);

    const lineGen = d3.line()
      .x(d => xScale(d[0])).y(d => yScale(d[1]))
      .defined(d => d[0] != null && d[1] != null && isFinite(d[0]) && isFinite(d[1]));

    g.append("path").datum(pairs)
      .attr("fill", "none").attr("stroke", color).attr("stroke-width", 1.8)
      .attr("d", lineGen);

    // Reference line at AC=1 for autocorrelation chart
    if (yLabel.includes("AC")) {
      g.append("line")
        .attr("x1", 0).attr("x2", W)
        .attr("y1", yScale(1)).attr("y2", yScale(1))
        .attr("stroke", "#D62828").attr("stroke-width", 1).attr("stroke-dasharray", "4 3");
    }
  }, [tArr, vArr]);

  return <div ref={ref} style={{ width: "100%" }} />;
}

function IndicatorColumn({ shellName, shellKey, indicatorData }) {
  if (!indicatorData) return <div className="indicator-col"><p style={{color:"#8890aa",fontSize:"12px"}}>No data</p></div>;
  return (
    <div className="indicator-col">
      <div className="indicator-col-title">Shell {shellKey} — {ALT_LABELS[shellKey]}</div>

      <div className="indicator-chart-card">
        <h4>Recovery Time</h4>
        <RecoveryTimeChart shellName={shellName} indicatorData={indicatorData} />
        <p className="annotation">
          How long the debris population takes to return to equilibrium after a disturbance
          (e.g. a collision event), as a function of launch rate. The steep rise toward the
          red dashed line means that near the tipping point, the shell loses its ability to
          self-correct — small shocks have lasting consequences.
        </p>
      </div>

      <div className="indicator-chart-card">
        <h4>Debris Variance</h4>
        <TimeSeriesChart
          shellName={shellName}
          tArr={indicatorData.variance.t}
          vArr={indicatorData.variance.values}
          color="#9B5DE5"
          yLabel="Var(D)"
        />
        <p className="annotation">
          Rolling variance of the debris population D(t) simulated at 90% of the tipping
          point launch rate. A rising variance is a classic early-warning signal: the system
          is increasingly sensitive to perturbations and fluctuates more widely around its
          equilibrium before eventually losing it.
        </p>
      </div>

      <div className="indicator-chart-card">
        <h4>Lag-1 Autocorrelation</h4>
        <TimeSeriesChart
          shellName={shellName}
          tArr={indicatorData.ac1.t}
          vArr={indicatorData.ac1.values}
          color="#2A9D8F"
          yLabel="AC(1) of D"
        />
        <p className="annotation">
          Correlation between consecutive debris counts over time. As the system approaches
          the tipping point it recovers more slowly, so each value strongly resembles the
          previous one — autocorrelation rises toward 1. A value near 1 means the shell has
          effectively lost its memory and can no longer absorb shocks.
        </p>
      </div>
    </div>
  );
}

/* =========================================================================
 * Section 3 — Plain-language explainer
 * ======================================================================= */
function ExplainerSection() {
  return (
    <div className="explainer-grid">
      <div className="explainer-card">
        <h3>The tipping point explained</h3>
        <p>
          Each altitude shell has a critical launch rate — <strong>L<sub>fold</sub></strong> —
          beyond which no stable low-debris equilibrium exists. Below it, perturbations
          (collisions, failures) decay over time and the shell recovers. Above it, debris
          grows without bound regardless of any action taken. This is the mathematical
          signature of Kessler syndrome.
        </p>
        <p>
          The three early-warning indicators below — recovery time, variance, and
          autocorrelation — all increase as the system approaches L<sub>fold</sub>.
          They provide advance notice before the tipping point is crossed.
        </p>
        <p style={{ fontStyle: "italic", fontSize: "11px" }}>
          Research prototype — parameters calibrated from ESA SER 2024 literature values.
          Not an operational system.
        </p>
      </div>

      <div className="explainer-card">
        <h3>What the traffic light means for policy</h3>
        <div className="tl-line">
          <div className="tl-dot-sm" style={{ background: "#2DC653" }} />
          <p>
            <strong style={{ color: "#2DC653" }}>Green</strong> (L &lt; 80% of L<sub>fold</sub>):
            Wide margin. Standard monitoring. New constellation deployments can proceed
            with routine debris mitigation.
          </p>
        </div>
        <div className="tl-line">
          <div className="tl-dot-sm" style={{ background: "#F4A100" }} />
          <p>
            <strong style={{ color: "#F4A100" }}>Amber</strong> (80–95% of L<sub>fold</sub>):
            Recovery times lengthening. New deployments should be evaluated against the
            remaining margin before approval. Active debris removal begins to have
            measurable effect.
          </p>
        </div>
        <div className="tl-line">
          <div className="tl-dot-sm" style={{ background: "#D62828" }} />
          <p>
            <strong style={{ color: "#D62828" }}>Red</strong> (L ≥ 95% of L<sub>fold</sub>):
            At or past the fold. Structurally past the tipping point. Reducing launch
            rate alone may not restore the safe low-debris equilibrium — the system
            may have crossed into the basin of attraction of the runaway state.
          </p>
        </div>
      </div>
    </div>
  );
}

/* =========================================================================
 * Section 4 — Shell C Alert (conditional on RED status)
 * ======================================================================= */
function ShellCAlert({ shellCData }) {
  if (!shellCData || shellCData.traffic_light !== "red") return null;
  return (
    <div className="alert-panel">
      <h2>⚠ Shell C is currently past its critical launch threshold</h2>
      <p>
        The 1,000 km altitude band has a confirmed tipping point of approximately
        <strong> {shellCData.L_fold.toFixed(1)} new objects per year</strong>.
        The current 3-year average launch rate into this band is
        <strong> {shellCData.L_current.toFixed(1)} objects/yr</strong> —
        {" "}<strong>{(shellCData.L_fraction * 100).toFixed(0)}%</strong> of that threshold.
      </p>
      <p>
        The historical debris cloud from the 2007 Fengyun-1C ASAT test has largely decayed
        below the 950 km shell floor by 2026. Shell C is in red status because of current
        launch activity, not legacy events. This is consistent with published scientific
        assessments of the 1,000 km band.
      </p>
    </div>
  );
}

/* =========================================================================
 * Root App
 * ======================================================================= */
function Dashboard() {
  const [liveData, setLiveData]         = useState(null);
  const [indicatorData, setIndicator]   = useState(null);
  const [loading, setLoading]           = useState(true);
  const [loadError, setLoadError]       = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [live, ind] = await Promise.all([
          fetch(`${API_BASE}/api/live`).then(r => r.json()),
          fetch("data/indicator_curves.json").then(r => r.json()),
        ]);
        setLiveData(live);
        setIndicator(ind);
      } catch (e) {
        setLoadError(e.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div className="app">
        <NavBar />
        <div className="dash-loading">
          <div className="spinner" />
          <div>Fetching live debris data from Space-Track…</div>
          <div style={{ fontSize: "11px", color: "#8890aa" }}>
            This may take 10–30 seconds. Falling back to cached snapshot if unavailable.
          </div>
        </div>
      </div>
    );
  }

  if (loadError || !liveData) {
    return (
      <div className="app">
        <NavBar />
        <div className="error-banner">
          Failed to load data: {loadError}. Ensure the FastAPI server is running on port 8000.
        </div>
      </div>
    );
  }

  const shellC = liveData.shells["C"];

  return (
    <div className="app">
      <NavBar />

      {/* Header */}
      <div className="dash-header">
        <h1>
          Orbital Sentinel — Early Warning Dashboard
          <span className="prototype-badge">Research Prototype</span>
        </h1>
        <p className="subtitle">Live debris monitoring for Low Earth Orbit altitude shells</p>
        <div className="explainer">
          🟢 Green = safely below tipping point &nbsp;|&nbsp;
          🟡 Amber = approaching critical zone &nbsp;|&nbsp;
          🔴 Red = at or past tipping point
        </div>
        <p className="timestamp">
          Data: {liveData.source}
          {liveData.cached && ` (cached snapshot)`}
          {" · "}{liveData.retrieved_utc}
        </p>
      </div>

      {/* Cache warning */}
      {liveData.cached && (
        <div className="cache-banner">
          ⚠ Live Space-Track query unavailable — showing cached snapshot ({liveData.retrieved_utc}).
          {liveData.fallback_reason && ` Reason: ${liveData.fallback_reason}.`}
          {" "}Set SPACETRACK_USER and SPACETRACK_PASS environment variables for live data.
        </div>
      )}

      {/* Section 1 */}
      <div className="section-title">Shell Status Overview</div>
      <div className="status-cards">
        {SHELL_KEYS.map(k => (
          <StatusCard key={k} shellKey={k} shellData={liveData.shells[k]} />
        ))}
      </div>

      {/* Section 2 */}
      <div className="section-title">Early Warning Indicators</div>
      <div className="indicator-grid">
        {SHELL_NAMES.map((name, i) => (
          <IndicatorColumn
            key={name}
            shellName={name}
            shellKey={SHELL_KEYS[i]}
            indicatorData={indicatorData?.[name]}
          />
        ))}
      </div>

      {/* Section 3 */}
      <div className="section-title">What the Numbers Mean</div>
      <ExplainerSection />

      {/* Section 4 — conditional */}
      <ShellCAlert shellCData={shellC} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<Dashboard />);
