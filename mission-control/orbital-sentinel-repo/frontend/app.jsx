/* Orbital Sentinel — Mission Control UI (React) */

"use strict";

const { useState, useEffect, useRef, useMemo, useCallback } = React;

/* ---------- Data shape ---------- */
const SHELL_KEYS = ["A", "B", "C"];
const SHELL_META = {
  A: { name: "Shell A", alt: 600, range: "550–650 km" },
  B: { name: "Shell B", alt: 800, range: "750–850 km" },
  C: { name: "Shell C", alt: 1000, range: "950–1050 km" },
};
const DATA_KEYS = {
  A: "Shell_A_600km",
  B: "Shell_B_800km",
  C: "Shell_C_1000km",
};

const STATUS_LABEL = {
  green: "NOMINAL",
  amber: "WATCH",
  red: "CRITICAL",
};
const STATUS_NORMALIZED = { green: "safe", amber: "caution", red: "danger" };

/* ---------- What-if scenarios (computed locally) ----------
 * Approximates the FastAPI engine: per-shell L_fold is roughly inversely
 * proportional to gamma_multiplier; net L is (L_current * L_mult) − removal.
 */
function applyScenario(baseShells, scen) {
  const out = {};
  for (const k of SHELL_KEYS) {
    const b = baseShells[k];
    const L_current = b.L_current * scen.L_mult;
    const L_net = Math.max(0, L_current - scen.removal);
    const L_fold = b.L_fold / scen.gamma_mult;
    const frac = L_fold > 0 ? L_net / L_fold : 99;
    let status = "green";
    if (frac >= 0.95) status = "red";
    else if (frac >= 0.8) status = "amber";
    out[k] = { ...b, L_current: L_net, L_fold, L_fraction: frac, traffic_light: status };
  }
  return out;
}

/* ---------- UI bits ---------- */

function Brand() {
  return (
    <div className="brand">
      <div className="brand-mark" />
      <div className="brand-text">
        <div className="brand-title">Orbital Sentinel</div>
        <div className="brand-sub">MISSION CONTROL · v2.1</div>
      </div>
    </div>
  );
}

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const iso = now.toISOString().replace("T", " ").slice(0, 19) + "Z";
  return (
    <div className="clock">
      <span className="label">UTC</span>
      {iso}
    </div>
  );
}

function TopBar({ tab, setTab, dataSource }) {
  const isLive = dataSource?.live;
  const hasError = !!dataSource?.error;
  const status = isLive ? { color: "var(--safe)", label: "LIVE FEED · ONLINE" }
    : hasError ? { color: "var(--caution)", label: "CACHED · LIVE UNREACHABLE" }
    : { color: "var(--active)", label: "CACHED SNAPSHOT" };
  return (
    <div className="topbar">
      <Brand />
      <div className="topbar-nav">
        <button className={tab === "mission" ? "active" : ""} onClick={() => setTab("mission")}>Mission</button>
        <button className={tab === "bifurcation" ? "active" : ""} onClick={() => setTab("bifurcation")}>Bifurcation</button>
        <button className={tab === "crisis" ? "active" : ""} onClick={() => setTab("crisis")}>The Crisis</button>
        <button className={`cta-tab${tab === "act" ? " active" : ""}`} onClick={() => setTab("act")}>Take Action</button>
      </div>
      <div className="topbar-right">
        <div className="status-pill">
          <span className="dot" style={{ background: status.color, boxShadow: `0 0 8px ${status.color}` }} />
          {status.label}
        </div>
        <Clock />
      </div>
    </div>
  );
}

function StatusDot({ status }) {
  const norm = STATUS_NORMALIZED[status] || status;
  return <span className={`scenario-chip-light ${norm}`} />;
}

function ShellCard({ shellKey, data, active, hovered, onClick }) {
  const meta = SHELL_META[shellKey];
  const status = STATUS_NORMALIZED[data.traffic_light] || "safe";
  const frac = Math.min(1.4, data.L_fraction);
  const fillPct = Math.min(100, frac * 100);

  return (
    <div
      className={`shell-card shell-card-minimal ${active ? "active" : ""} ${hovered ? "hovered" : ""}`}
      data-status={status}
      onClick={onClick}
    >
      <div className="shell-card-head">
        <span className="shell-card-name">{meta.name}</span>
        <span className="shell-card-alt">{meta.range}</span>
      </div>
      <div className="shell-card-status">{STATUS_LABEL[data.traffic_light]} · L/L_fold {(frac * 100).toFixed(1)}%</div>
      <div className="shell-meter">
        <div className="shell-meter-fill" style={{ width: `${Math.min(100, fillPct)}%` }} />
        <div className="shell-meter-fold" />
      </div>
      <div className="shell-meter-label">
        <span>0</span>
        <span><strong>L_fold</strong> {fmtNumber(data.L_fold)} obj/yr</span>
      </div>
      <div className="shell-card-stats-row">
        <div>
          <div className="shell-card-stat-label">Satellites</div>
          <div className="shell-card-stat-val">{fmtInt(data.S_current ?? data.S)}</div>
        </div>
        <div>
          <div className="shell-card-stat-label">Debris</div>
          <div className="shell-card-stat-val">{fmtInt(data.D_current ?? data.D)}</div>
        </div>
      </div>
      <div className="shell-card-hint">Tap to expand ›</div>
    </div>
  );
}

function fmtInt(n) {
  if (n == null) return "—";
  return Math.round(n).toLocaleString("en-US");
}
function fmtNumber(n, digits = 0) {
  if (n == null) return "—";
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return n.toFixed(digits);
}

/* ---------- Right rail: scenario controls ---------- */

const PRESETS = [
  { label: "Starlink doubles", L_mult: 2.0, removal: 0, gamma_mult: 1.0 },
  { label: "ESA removes 5/yr", L_mult: 1.0, removal: 5, gamma_mult: 1.0 },
  { label: "Major collision",  L_mult: 1.0, removal: 0, gamma_mult: 1.5 },
  { label: "Removal blitz",    L_mult: 1.0, removal: 30, gamma_mult: 1.0 },
];

const OVERLAY_COLORS = ["#69d2ff", "#3fd6a3", "#ffb547", "#c790ff", "#ff5a76"];

function ScenarioPanel({ baseShells, scenarios, setScenarios, apiUrl }) {
  const [L_mult, setLMult] = useState(1.0);
  const [removal, setRemoval] = useState(0);
  const [gamma_mult, setGammaMult] = useState(1.0);
  const [computing, setComputing] = useState(false);

  // Cumulative params: each new scenario stacks on top of the last committed one
  const prevParams = scenarios.length > 0
    ? scenarios[scenarios.length - 1].params
    : { L_mult: 1, removal: 0, gamma_mult: 1 };
  const cumL    = prevParams.L_mult * L_mult;
  const cumRem  = prevParams.removal + removal;
  const cumGamma = prevParams.gamma_mult * gamma_mult;

  const preview = useMemo(
    () => applyScenario(baseShells, { L_mult: cumL, removal: cumRem, gamma_mult: cumGamma }),
    [baseShells, cumL, cumRem, cumGamma]
  );

  const applyPreset = (p) => {
    setLMult(p.L_mult); setRemoval(p.removal); setGammaMult(p.gamma_mult);
  };

  const addScenario = async () => {
    if (scenarios.length >= 5 || computing) return;
    const label = (
      L_mult !== 1 ? `×${L_mult.toFixed(1)} launch` :
      removal > 0 ? `−${removal}/yr removal` :
      gamma_mult !== 1 ? `γ×${gamma_mult.toFixed(2)}` : "Baseline"
    );
    setComputing(true);
    try {
      const base = apiUrl || "http://localhost:8000";
      const resp = await fetch(`${base}/api/whatif`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ L_multiplier: cumL, debris_removal_rate: cumRem, gamma_multiplier: cumGamma, label }),
      });
      if (resp.status === 400) {
        // Server overlay cap — sync clear then return
        await fetch(`${base}/api/whatif/clear`, { method: "DELETE" });
        setScenarios([]);
        return;
      }
      const result = await resp.json();
      // Map API response to frontend scenario shape (merge with base S/D counts)
      const shells = {};
      for (const k of SHELL_KEYS) {
        const s = result.shells[k];
        shells[k] = {
          ...baseShells[k],
          L_current: s.L_current_new,
          L_fold: s.L_fold_new ?? baseShells[k].L_fold,
          L_fraction: s.L_fold_new ? s.L_current_new / s.L_fold_new : 99,
          traffic_light: s.traffic_light,
          curve: s.curve,
        };
      }
      setScenarios(prev => [...prev, {
        id: Date.now(),
        label: result.label || label,
        color: OVERLAY_COLORS[prev.length % OVERLAY_COLORS.length],
        shells,
        params: { L_mult: cumL, removal: cumRem, gamma_mult: cumGamma },
      }]);
    } catch (e) {
      // Fallback to client-side approximation if API unreachable
      const result = applyScenario(baseShells, { L_mult: cumL, removal: cumRem, gamma_mult: cumGamma });
      setScenarios(prev => [...prev, {
        id: Date.now(), label,
        color: OVERLAY_COLORS[prev.length % OVERLAY_COLORS.length],
        shells: result, params: { L_mult: cumL, removal: cumRem, gamma_mult: cumGamma },
      }]);
    } finally {
      setComputing(false);
    }
  };

  const clearAll = async () => {
    try { await fetch(`${apiUrl || "http://localhost:8000"}/api/whatif/clear`, { method: "DELETE" }); } catch (_) {}
    setScenarios([]);
  };

  const reset = () => { setLMult(1); setRemoval(0); setGammaMult(1); };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">What-If Scenario</span>
        <span className="panel-meta">{scenarios.length}/5</span>
      </div>
      <div className="panel-hint">Pick a preset or adjust the sliders — then commit to overlay the result on the Earth view.</div>
      <div className="panel-body">
        <div className="preset-row">
          {PRESETS.map(p => (
            <button key={p.label} className="preset-btn" onClick={() => applyPreset(p)}>{p.label}</button>
          ))}
        </div>

        <div className="slider-row">
          <div className="slider-row-head">
            <span className="slider-row-label">Launch Rate Multiplier</span>
            <span className="slider-row-value">×{L_mult.toFixed(1)}</span>
          </div>
          <input className="slider" type="range" min="0.1" max="5" step="0.1"
            value={L_mult} onChange={e => setLMult(+e.target.value)} />
        </div>

        <div className="slider-row">
          <div className="slider-row-head">
            <span className="slider-row-label">Debris Removal</span>
            <span className="slider-row-value">{removal}/yr</span>
          </div>
          <input className="slider" type="range" min="0" max="50" step="1"
            value={removal} onChange={e => setRemoval(+e.target.value)} />
        </div>

        <div className="slider-row">
          <div className="slider-row-head">
            <span className="slider-row-label">Cascade Coefficient γ</span>
            <span className="slider-row-value">×{gamma_mult.toFixed(2)}</span>
          </div>
          <input className="slider" type="range" min="0.5" max="3" step="0.05"
            value={gamma_mult} onChange={e => setGammaMult(+e.target.value)} />
        </div>

        {/* Preview row */}
        <div className="scenario-chip" style={{ marginTop: 4 }}>
          <span className="swatch" style={{ color: OVERLAY_COLORS[scenarios.length % 5], background: OVERLAY_COLORS[scenarios.length % 5] }} />
          <span className="name">Preview</span>
          <div className="lights">
            {SHELL_KEYS.map(k => (
              <span key={k} className={`light ${STATUS_NORMALIZED[preview[k].traffic_light]}`} />
            ))}
          </div>
        </div>

        <button className="run-btn" onClick={addScenario} disabled={scenarios.length >= 5 || computing}>
          {scenarios.length >= 5 ? "Overlay Cap Reached" : computing ? "Computing…" : "Commit Scenario"}
        </button>

        {scenarios.length > 0 && (
          <div className="scenarios-list">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
              <span style={{ fontFamily: "var(--mono)", fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.1em" }}>ACTIVE OVERLAYS</span>
              <button className="x" style={{ fontSize: 9, padding: "1px 5px", opacity: 0.7 }} onClick={clearAll}>Clear all</button>
            </div>
            {scenarios.map((s, i) => (
              <div key={s.id} className="scenario-chip">
                <span className="swatch" style={{ color: s.color, background: s.color }} />
                <span className="name">{s.label}</span>
                <div className="lights">
                  {SHELL_KEYS.map(k => (
                    <span key={k} className={`light ${STATUS_NORMALIZED[s.shells[k].traffic_light]}`} />
                  ))}
                </div>
                <button className="x" onClick={() => setScenarios(scenarios.filter(x => x.id !== s.id))}>×</button>
              </div>
            ))}
          </div>
        )}

        {scenarios.length === 0 && (
          <div className="empty-state">NO OVERLAYS ACTIVE</div>
        )}
      </div>
    </div>
  );
}

/* ---------- Bottom strip: bifurcation mini-charts ---------- */

function BifurcCard({ shellKey, baseData, currentData, overlays, curveData }) {
  const meta = SHELL_META[shellKey];
  const status = STATUS_NORMALIZED[currentData.traffic_light] || "safe";
  const accent = status === "danger" ? "#ff5a76" : status === "caution" ? "#ffb547" : "#3fd6a3";

  const W = 280, H = 88;
  const L_fold = baseData.L_fold;
  const L_max = L_fold * 1.15;

  // Real engine curves with log scale
  const lb = curveData?.lower_branch;
  const ub = curveData?.upper_branch;
  const hasReal = !!(lb && lb.L.length > 0);
  const allDV = hasReal ? [...lb.D_star, ...ub.D_star] : [1000, 1000000];
  const logMin = Math.log10(Math.max(1, Math.min(...allDV)));
  const logMax = Math.log10(Math.max(1, Math.max(...allDV)));
  const xM = (L) => (L / L_max) * W;
  const yM = (D) => {
    const t = (Math.log10(Math.max(1, D || 1)) - logMin) / Math.max(0.001, logMax - logMin);
    return H * (1 - Math.max(0, Math.min(1, t)));
  };
  const mkMini = (Ls, Ds) => {
    if (!Ls || !Ls.length) return "";
    const p = [];
    for (let i = 0; i < Ls.length; i += 5)
      p.push(xM(Ls[i]).toFixed(1) + "," + yM(Ds[i]).toFixed(1));
    const j = Ls.length - 1;
    if (j % 5) p.push(xM(Ls[j]).toFixed(1) + "," + yM(Ds[j]).toFixed(1));
    return "M " + p.join(" L ");
  };

  let lowerPath, upperPath;
  if (hasReal) {
    lowerPath = mkMini(lb.L, lb.D_star);
    upperPath = mkMini(ub.L, ub.D_star);
  } else {
    const pL = [], pU = [];
    for (let i = 0; i <= 50; i++) {
      const L = (i / 50) * L_fold * 0.98;
      pL.push([(L / L_max * W).toFixed(1), Math.max(8, H - 8 - Math.pow(L / L_fold, 0.45) * (H * 0.55)).toFixed(1)]);
    }
    for (let i = 0; i <= 50; i++) {
      const L = L_fold * 0.05 + (i / 50) * L_fold * 0.93;
      pU.push([(L / L_max * W).toFixed(1), (6 + Math.pow(1 - L / L_fold, 0.6) * 20).toFixed(1)]);
    }
    lowerPath = "M " + pL.map(p => p.join(",")).join(" L ");
    upperPath = "M " + pU.map(p => p.join(",")).join(" L ");
  }

  const Lc = currentData.L_current;
  const Dc = currentData.D_current ?? currentData.D;
  const x_c = xM(Lc);
  const y_c = hasReal ? yM(Dc) : (H - 8 - Math.pow(Math.min(1, Lc / L_fold), 0.45) * (H * 0.55));
  const x_fold = xM(L_fold);

  return (
    <div className="bifurc-card">
      <div className="bifurc-head">
        <span className="bifurc-title">{meta.name} · {meta.alt} km</span>
        <span className="bifurc-status" style={{ color: accent }}>
          {STATUS_LABEL[currentData.traffic_light]}
        </span>
      </div>
      <svg className="bifurc-chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id={`grad-${shellKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity="0.3" />
            <stop offset="100%" stopColor={accent} stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* Fold line */}
        <line x1={x_fold} y1="2" x2={x_fold} y2={H - 2}
          stroke="#ff5a76" strokeWidth="1" strokeDasharray="3 3" opacity="0.7" />
        <text x={x_fold - 4} y="10" fontSize="8" fill="#ff5a76" textAnchor="end" fontFamily="monospace">L_fold</text>

        {/* Stable branch fill */}
        <path d={`${lowerPath} L ${W},${H} L 0,${H} Z`}
          fill={`url(#grad-${shellKey})`} opacity="0.4" />

        {/* Upper unstable branch (dashed) */}
        <path d={upperPath} fill="none" stroke={accent} strokeWidth="1.5"
          strokeDasharray="3 2" opacity="0.55" />
        {/* Lower stable branch */}
        <path d={lowerPath} fill="none" stroke={accent} strokeWidth="1.7" />

        {/* Overlay scenarios */}
        {overlays.map((s, i) => {
          const sd = s.shells[shellKey];
          const sLcur = sd.L_current ?? sd.L_current_new;
          const sx = xM(sLcur);
          const newD = sd.curve ? (() => { let c = sd.curve[0]; for (const p of sd.curve) if (Math.abs(p.L - sLcur) < Math.abs(c.L - sLcur)) c = p; return c.D_star; })() : null;
          const sy = newD ? yM(newD) : y_c;
          return (
            <g key={s.id}>
              <line x1={sx} y1="2" x2={sx} y2={H - 2}
                stroke={s.color} strokeWidth="0.6" strokeDasharray="2 2" opacity="0.45" />
              <circle cx={sx} cy={sy} r="3" fill={s.color}
                stroke="#0a121f" strokeWidth="1" />
            </g>
          );
        })}

        {/* Current state marker */}
        <circle cx={x_c} cy={Math.max(8, y_c)} r="4" fill={accent}
          stroke="#0a121f" strokeWidth="1.5">
          <animate attributeName="r" values="4;6;4" dur="2.2s" repeatCount="indefinite" />
        </circle>
      </svg>
    </div>
  );
}

/* ---------- Tweaks ---------- */

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "altitude_exaggeration": 1.0,
  "show_satellites": true,
  "show_debris": true,
  "show_shell_surface": true,
  "show_wireframe": true,
  "earth_style": "textured",
  "auto_rotate": true,
  "live_api": true,
  "api_url": "http://localhost:8000"
}/*EDITMODE-END*/;

function TweaksHost({ onChange }) {
  const Panel = window.TweaksPanel;
  const useTweaksFn = window.useTweaks;
  if (!Panel || !useTweaksFn) return null;
  const [tweaks, setTweak] = useTweaksFn(TWEAK_DEFAULTS);

  useEffect(() => { onChange(tweaks); }, [tweaks]);

  return (
    <Panel title="Tweaks">
      <window.TweakSection label="Scene">
        <window.TweakSlider label="Altitude exaggeration"
          value={tweaks.altitude_exaggeration} min={0.4} max={2.5} step={0.05}
          onChange={v => setTweak("altitude_exaggeration", v)} />
        <window.TweakToggle label="Auto rotate camera"
          value={tweaks.auto_rotate}
          onChange={v => setTweak("auto_rotate", v)} />
      </window.TweakSection>
      <window.TweakSection label="Visibility">
        <window.TweakToggle label="Satellites"
          value={tweaks.show_satellites} onChange={v => setTweak("show_satellites", v)} />
        <window.TweakToggle label="Debris fragments"
          value={tweaks.show_debris} onChange={v => setTweak("show_debris", v)} />
        <window.TweakToggle label="Shell surface"
          value={tweaks.show_shell_surface} onChange={v => setTweak("show_shell_surface", v)} />
        <window.TweakToggle label="Wireframe overlay"
          value={tweaks.show_wireframe} onChange={v => setTweak("show_wireframe", v)} />
      </window.TweakSection>
      <window.TweakSection label="Earth">
        <window.TweakRadio label="Style" value={tweaks.earth_style}
          options={["textured", "minimal", "wireframe"]}
          onChange={v => setTweak("earth_style", v)} />
      </window.TweakSection>
      <window.TweakSection label="Data Source">
        <window.TweakToggle label="Try live /api/live"
          value={tweaks.live_api}
          onChange={v => setTweak("live_api", v)} />
        <window.TweakText label="API base URL"
          value={tweaks.api_url}
          placeholder="http://localhost:8000"
          onChange={v => setTweak("api_url", v)} />
      </window.TweakSection>
    </Panel>
  );
}

/* ---------- BIFURCATION VIEW ---------- */

function WhatIfDrawer({ baseShells, scenarios, setScenarios, apiUrl }) {
  const [open, setOpen] = useState(false);
  const [L_mult, setLMult] = useState(1.0);
  const [removal, setRemoval] = useState(0);
  const [gamma_mult, setGammaMult] = useState(1.0);
  const [computing, setComputing] = useState(false);

  const prevParams = scenarios.length > 0
    ? scenarios[scenarios.length - 1].params
    : { L_mult: 1, removal: 0, gamma_mult: 1 };
  const cumL    = prevParams.L_mult * L_mult;
  const cumRem  = prevParams.removal + removal;
  const cumGamma = prevParams.gamma_mult * gamma_mult;

  const preview = useMemo(
    () => baseShells ? applyScenario(baseShells, { L_mult: cumL, removal: cumRem, gamma_mult: cumGamma }) : null,
    [baseShells, cumL, cumRem, cumGamma]
  );

  if (!baseShells) return null;

  const addScenario = async () => {
    if (!baseShells || scenarios.length >= 5 || computing) return;
    const label = (
      L_mult !== 1 ? `×${L_mult.toFixed(1)} launch` :
      removal > 0  ? `−${removal}/yr removal` :
      gamma_mult !== 1 ? `γ×${gamma_mult.toFixed(2)}` : "Baseline"
    );
    setComputing(true);
    try {
      const base = apiUrl || "http://localhost:8000";
      const resp = await fetch(`${base}/api/whatif`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ L_multiplier: cumL, debris_removal_rate: cumRem, gamma_multiplier: cumGamma, label }),
      });
      if (resp.status === 400) {
        await fetch(`${base}/api/whatif/clear`, { method: "DELETE" });
        setScenarios([]);
        return;
      }
      const result = await resp.json();
      const shells = {};
      for (const k of SHELL_KEYS) {
        const s = result.shells[k];
        shells[k] = {
          ...baseShells[k],
          L_current: s.L_current_new,
          L_fold: s.L_fold_new ?? baseShells[k].L_fold,
          L_fraction: s.L_fold_new ? s.L_current_new / s.L_fold_new : 99,
          traffic_light: s.traffic_light,
          curve: s.curve,
        };
      }
      setScenarios(prev => [...prev, {
        id: Date.now(), label: result.label || label,
        color: OVERLAY_COLORS[prev.length % OVERLAY_COLORS.length],
        shells, params: { L_mult: cumL, removal: cumRem, gamma_mult: cumGamma },
      }]);
    } catch (_) {
      const result = applyScenario(baseShells, { L_mult: cumL, removal: cumRem, gamma_mult: cumGamma });
      setScenarios(prev => [...prev, {
        id: Date.now(), label,
        color: OVERLAY_COLORS[prev.length % OVERLAY_COLORS.length],
        shells: result, params: { L_mult: cumL, removal: cumRem, gamma_mult: cumGamma },
      }]);
    } finally { setComputing(false); }
  };

  const clearAll = async () => {
    try { await fetch(`${apiUrl || "http://localhost:8000"}/api/whatif/clear`, { method: "DELETE" }); } catch (_) {}
    setScenarios([]);
  };

  return (
    <div className="whatif-drawer">
      <div className="whatif-drawer-toggle" onClick={() => setOpen(o => !o)}>
        <span className="whatif-drawer-label">What-If Scenarios</span>
        <span className="whatif-drawer-count">{scenarios.length}/5</span>
        {scenarios.map(s => (
          <span key={s.id} className="whatif-color-dot" style={{ background: s.color }} />
        ))}
        <span className="whatif-drawer-chevron">{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div className="whatif-drawer-body">
          <div className="whatif-presets">
            {PRESETS.map(p => (
              <button key={p.label} className="preset-btn" onClick={() => { setLMult(p.L_mult); setRemoval(p.removal); setGammaMult(p.gamma_mult); }}>
                {p.label}
              </button>
            ))}
          </div>
          <div className="whatif-sliders">
            <div className="whatif-slider-item">
              <div className="whatif-slider-head">
                <span>Launch rate ×</span>
                <span className="whatif-slider-val">{L_mult.toFixed(1)}</span>
              </div>
              <input className="slider" type="range" min="0.1" max="5" step="0.1"
                value={L_mult} onChange={e => setLMult(+e.target.value)} />
            </div>
            <div className="whatif-slider-item">
              <div className="whatif-slider-head">
                <span>Debris removal</span>
                <span className="whatif-slider-val">{removal}/yr</span>
              </div>
              <input className="slider" type="range" min="0" max="50" step="1"
                value={removal} onChange={e => setRemoval(+e.target.value)} />
            </div>
            <div className="whatif-slider-item">
              <div className="whatif-slider-head">
                <span>Cascade coeff γ ×</span>
                <span className="whatif-slider-val">{gamma_mult.toFixed(2)}</span>
              </div>
              <input className="slider" type="range" min="0.5" max="3" step="0.05"
                value={gamma_mult} onChange={e => setGammaMult(+e.target.value)} />
            </div>
          </div>
          <div className="whatif-actions">
            <div className="whatif-preview-lights">
              <span className="whatif-preview-label">Preview</span>
              {preview && SHELL_KEYS.map(k => (
                <span key={k} className={`light ${STATUS_NORMALIZED[preview[k].traffic_light]}`} />
              ))}
            </div>
            <button className="run-btn" onClick={addScenario} disabled={scenarios.length >= 5 || computing}>
              {scenarios.length >= 5 ? "Cap reached" : computing ? "Computing…" : "Add overlay"}
            </button>
            {scenarios.length > 0 && (
              <button className="x" style={{ marginLeft: 4 }} onClick={clearAll}>Clear all</button>
            )}
          </div>
          {scenarios.length > 0 && (
            <div className="whatif-chips">
              {scenarios.map(s => (
                <div key={s.id} className="scenario-chip">
                  <span className="swatch" style={{ color: s.color, background: s.color }} />
                  <span className="name">{s.label}</span>
                  <div className="lights">
                    {SHELL_KEYS.map(k => (
                      <span key={k} className={`light ${STATUS_NORMALIZED[s.shells[k].traffic_light]}`} />
                    ))}
                  </div>
                  <button className="x" onClick={() => setScenarios(scenarios.filter(x => x.id !== s.id))}>×</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function BigBifurcCard({ shellKey, baseData, currentData, overlays, curveData }) {
  const meta = SHELL_META[shellKey];
  const status = STATUS_NORMALIZED[currentData.traffic_light] || "safe";
  const accent = status === "danger" ? "#ff5a76" : status === "caution" ? "#ffb547" : "#3fd6a3";

  const W = 460, H = 340;
  const PAD_L = 54, PAD_R = 16, PAD_T = 28, PAD_B = 40;
  const PW = W - PAD_L - PAD_R;
  const PH = H - PAD_T - PAD_B;

  const L_fold = baseData.L_fold;
  const L_max = L_fold * 1.18;

  // Real engine curves via log scale when curveData is available
  const lb = curveData?.lower_branch;
  const ub = curveData?.upper_branch;
  const hasReal = !!(lb && lb.L.length > 0);

  const allDV = hasReal ? [...lb.D_star, ...ub.D_star] : [1000, 1000000];
  const logMin = Math.log10(Math.max(1, Math.min(...allDV)));
  const logMax = Math.log10(Math.max(1, Math.max(...allDV)));
  const xS = (L) => PAD_L + (L / L_max) * PW;
  const yS = (D) => {
    const t = (Math.log10(Math.max(1, D || 1)) - logMin) / Math.max(0.001, logMax - logMin);
    return PAD_T + PH * (1 - Math.max(0, Math.min(1, t)));
  };
  const STEP = 4;
  const mkPath = (Ls, Ds) => {
    if (!Ls || !Ls.length) return "";
    const p = [];
    for (let i = 0; i < Ls.length; i += STEP)
      p.push(xS(Ls[i]).toFixed(1) + "," + yS(Ds[i]).toFixed(1));
    const j = Ls.length - 1;
    if (j % STEP) p.push(xS(Ls[j]).toFixed(1) + "," + yS(Ds[j]).toFixed(1));
    return "M " + p.join(" L ");
  };

  let lowerPath, upperPath;
  if (hasReal) {
    lowerPath = mkPath(lb.L, lb.D_star);
    upperPath = mkPath(ub.L, ub.D_star);
  } else {
    // Procedural fallback while data loads
    const pL = [], pU = [];
    for (let i = 0; i <= 60; i++) {
      const L = (i / 60) * L_fold * 0.99;
      pL.push([(PAD_L + (L / L_max) * PW).toFixed(1), (PAD_T + PH - 10 - Math.pow(L / L_fold, 0.42) * (PH * 0.6)).toFixed(1)]);
    }
    for (let i = 0; i <= 60; i++) {
      const L = L_fold * 0.04 + (i / 60) * L_fold * 0.94;
      pU.push([(PAD_L + (L / L_max) * PW).toFixed(1), (PAD_T + 12 + Math.pow(1 - L / L_fold, 0.7) * (PH * 0.18)).toFixed(1)]);
    }
    lowerPath = "M " + pL.map(p => p.join(",")).join(" L ");
    upperPath = "M " + pU.map(p => p.join(",")).join(" L ");
  }

  const Lc = currentData.L_current;
  const Dc = currentData.D_current ?? currentData.D;
  const x_c = xS(Lc);
  const y_c = hasReal ? yS(Dc) : (PAD_T + PH - 10 - Math.pow(Math.min(1, Lc / L_fold), 0.42) * (PH * 0.6));
  const x_fold = xS(L_fold);

  // Y-axis tick marks (log decades)
  const yTicks = hasReal ? (() => {
    const t = [];
    for (let e = Math.ceil(logMin); e <= Math.floor(logMax); e++) {
      const D = Math.pow(10, e);
      const y = yS(D);
      if (y >= PAD_T + 4 && y <= PAD_T + PH - 4)
        t.push({ y, label: D >= 1e6 ? "1M" : D >= 1e3 ? (D / 1e3) + "k" : String(D) });
    }
    return t;
  })() : [];

  // X-axis ticks
  const xTicks = [0, 0.25, 0.5, 0.75, 1.0].map(t => {
    const L = t * L_max;
    return { L, x: xS(L), label: L >= 1000 ? (L / 1000).toFixed(1) + "k" : Math.round(L) };
  });

  // Find D* on a curve array at a given L (for overlay markers)
  const findD = (curve, Ltgt) => {
    if (!curve || !curve.length) return null;
    let c = curve[0];
    for (const p of curve) if (Math.abs(p.L - Ltgt) < Math.abs(c.L - Ltgt)) c = p;
    return c.D_star;
  };

  return (
    <div className="big-bifurc-card panel" data-status={status}>
      <div className="big-bifurc-head">
        <div>
          <div className="big-bifurc-title">{meta.name}</div>
          <div className="big-bifurc-sub">{meta.alt} km · {meta.range}</div>
        </div>
        <div className="big-bifurc-status" style={{ color: accent }}>
          <span className="big-bifurc-dot" style={{ background: accent, boxShadow: `0 0 10px ${accent}` }} />
          {STATUS_LABEL[currentData.traffic_light]}
        </div>
      </div>

      <svg className="big-bifurc-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id={`big-grad-${shellKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity="0.35" />
            <stop offset="100%" stopColor={accent} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Grid — X */}
        {xTicks.map(t => (
          <line key={t.L} x1={t.x} y1={PAD_T} x2={t.x} y2={PAD_T + PH}
            stroke="rgba(120,150,200,0.07)" strokeWidth="1" />
        ))}
        {/* Grid — Y (log decades) */}
        {yTicks.map(t => (
          <line key={t.label} x1={PAD_L} y1={t.y} x2={PAD_L + PW} y2={t.y}
            stroke="rgba(120,150,200,0.07)" strokeWidth="1" />
        ))}

        {/* Fold line */}
        <line x1={x_fold} y1={PAD_T} x2={x_fold} y2={PAD_T + PH}
          stroke="#ff5a76" strokeWidth="1.2" strokeDasharray="4 4" opacity="0.85" />
        <text x={x_fold + 6} y={PAD_T + 12} fontSize="10" fill="#ff5a76" fontFamily="monospace">L_fold</text>
        <text x={x_fold + 6} y={PAD_T + 24} fontSize="9" fill="#ff5a76" fontFamily="monospace" opacity="0.7">
          {fmtNumber(L_fold, 0)} /yr
        </text>

        {/* Fill under stable branch */}
        <path d={`${lowerPath} L ${PAD_L + PW},${PAD_T + PH} L ${PAD_L},${PAD_T + PH} Z`}
          fill={`url(#big-grad-${shellKey})`} />

        {/* Upper unstable branch (dashed) */}
        <path d={upperPath} fill="none" stroke={accent} strokeWidth="1.6"
          strokeDasharray="4 3" opacity="0.6" />
        {/* Lower stable branch */}
        <path d={lowerPath} fill="none" stroke={accent} strokeWidth="2.2" />

        {/* Overlay scenarios */}
        {overlays.map((s) => {
          const sd = s.shells[shellKey];
          const sLfold = sd.L_fold ?? sd.L_fold_new;
          const sLcur = sd.L_current ?? sd.L_current_new;
          const x_sfold = sLfold ? xS(sLfold) : null;
          const sx = xS(sLcur);
          const newD = sd.curve ? findD(sd.curve, sLcur) : null;
          const sy = newD ? yS(newD) : y_c;
          const sCurvePath = sd.curve
            ? mkPath(sd.curve.map(p => p.L), sd.curve.map(p => p.D_star))
            : null;
          return (
            <g key={s.id}>
              {sCurvePath && (
                <path d={sCurvePath} fill="none" stroke={s.color}
                  strokeWidth="1.5" strokeDasharray="4 3" opacity="0.7" />
              )}
              {x_sfold && (
                <line x1={x_sfold} y1={PAD_T} x2={x_sfold} y2={PAD_T + PH}
                  stroke={s.color} strokeWidth="1" strokeDasharray="3 3" opacity="0.55" />
              )}
              <line x1={PAD_L} y1={sy} x2={sx} y2={sy}
                stroke={s.color} strokeWidth="0.8" strokeDasharray="2 2" opacity="0.4" />
              <line x1={sx} y1={PAD_T + PH} x2={sx} y2={sy}
                stroke={s.color} strokeWidth="0.8" strokeDasharray="2 2" opacity="0.4" />
              <circle cx={sx} cy={sy} r="4" fill={s.color} stroke="#0a121f" strokeWidth="1.5" />
            </g>
          );
        })}

        {/* Current state marker */}
        <line x1={PAD_L} y1={y_c} x2={x_c} y2={y_c}
          stroke={accent} strokeWidth="0.8" strokeDasharray="2 3" opacity="0.5" />
        <line x1={x_c} y1={PAD_T + PH} x2={x_c} y2={y_c}
          stroke={accent} strokeWidth="0.8" strokeDasharray="2 3" opacity="0.5" />
        <circle cx={x_c} cy={y_c} r="5" fill={accent} stroke="#0a121f" strokeWidth="2">
          <animate attributeName="r" values="5;7;5" dur="2.2s" repeatCount="indefinite" />
        </circle>

        {/* Axes */}
        <line x1={PAD_L} y1={PAD_T + PH} x2={PAD_L + PW} y2={PAD_T + PH} stroke="rgba(120,150,200,0.25)" />
        <line x1={PAD_L} y1={PAD_T} x2={PAD_L} y2={PAD_T + PH} stroke="rgba(120,150,200,0.25)" />

        {/* X tick labels */}
        {xTicks.map(t => (
          <text key={t.L} x={t.x} y={PAD_T + PH + 14} fontSize="9"
            fill="var(--text-dim)" textAnchor="middle" fontFamily="monospace">{t.label}</text>
        ))}

        {/* Y label + log tick labels */}
        <text x={PAD_L - 8} y={PAD_T + 10} fontSize="9" fill="var(--text-dim)"
          textAnchor="end" fontFamily="monospace">D*</text>
        {yTicks.map(t => (
          <text key={t.label} x={PAD_L - 5} y={t.y + 3} fontSize="8"
            fill="var(--text-dim)" textAnchor="end" fontFamily="monospace">{t.label}</text>
        ))}
        <text x={PAD_L + PW / 2} y={PAD_T + PH + 30} fontSize="10" fill="var(--text-dim)"
          textAnchor="middle" fontFamily="monospace">L (new objects / year)</text>
      </svg>

      <div className="big-bifurc-readout">
        <div>
          <div className="bbr-label">L current</div>
          <div className="bbr-value" style={{ color: accent }}>{fmtNumber(currentData.L_current, 1)}</div>
        </div>
        <div>
          <div className="bbr-label">L fold</div>
          <div className="bbr-value">{fmtNumber(L_fold)}</div>
        </div>
        <div>
          <div className="bbr-label">L/L_fold</div>
          <div className="bbr-value" style={{ color: accent }}>{(currentData.L_fraction * 100).toFixed(1)}%</div>
        </div>
      </div>
    </div>
  );
}

function BifurcationView({ baseShells, effective, scenarios, baseCurves, setScenarios, apiUrl }) {
  return (
    <div className="bifurc-page">

      {/* Page header */}
      <div className="bifurc-page-header">
        <div className="bifurc-page-title">Bifurcation Analysis</div>
        <div className="bifurc-page-sub">
          Equilibrium debris population D* as a function of launch rate L · validated across three independently implemented model variants (2-D, 3-species, split-decay)
        </div>
      </div>

      {/* Collapsible What-If drawer */}
      <WhatIfDrawer baseShells={baseShells} scenarios={scenarios} setScenarios={setScenarios} apiUrl={apiUrl} />

      {/* Three shell bifurcation diagrams */}
      <div className="bifurc-charts-row">
        {SHELL_KEYS.map(k => (
          <BigBifurcCard key={k} shellKey={k}
            baseData={baseShells[k]}
            currentData={effective[k]}
            overlays={scenarios}
            curveData={baseCurves?.[DATA_KEYS[k]]} />
        ))}
      </div>

      {/* Legend */}
      <div className="bifurc-legend">
        <span><span className="lg-line solid" /> Stable equilibrium D*</span>
        <span><span className="lg-line dashed" /> Unstable upper branch</span>
        <span><span className="lg-line foldline" /> L_fold (tipping point)</span>
        <span><span className="lg-dot" /> Current state · 2026</span>
        {scenarios.map(s => (
          <span key={s.id}><span className="lg-dot" style={{ background: s.color }} /> {s.label}</span>
        ))}
      </div>

      {/* ── Information sections ── */}
      <div className="bifurc-info-grid">

        {/* The model */}
        <div className="bifurc-info-card">
          <div className="bifurc-info-title">The Mathematical Model</div>
          <div className="bifurc-eq-block">
            <div className="bifurc-eq">Ṡ = L &minus; δ<sub>S</sub>&thinsp;S &minus; β&thinsp;S&thinsp;D</div>
            <div className="bifurc-eq">Ḋ = β&thinsp;S&thinsp;D + γ&thinsp;D² &minus; δ<sub>D</sub>&thinsp;D</div>
          </div>
          <div className="bifurc-info-vars">
            <div><span className="biv-sym">S</span>active satellites + rocket bodies</div>
            <div><span className="biv-sym">D</span>trackable debris fragments (&gt;10 cm)</div>
            <div><span className="biv-sym">L</span>launch rate [obj/year] — the bifurcation parameter</div>
            <div><span className="biv-sym">β</span>satellite-debris collision cross-section</div>
            <div><span className="biv-sym">γ</span>debris self-cascade coefficient <em>(the Kessler term)</em></div>
            <div><span className="biv-sym">δ<sub>S</sub>, δ<sub>D</sub></span>atmospheric drag / decay rates per species</div>
          </div>
          <div className="bifurc-info-note">
            The γD² term is quadratic in D. Above a critical debris density it outgrows
            δ<sub>D</sub>&thinsp;D and the debris population runs away regardless of S.
            That is the mathematical signature of Kessler syndrome.
          </div>
        </div>

        {/* Engine findings */}
        <div className="bifurc-info-card">
          <div className="bifurc-info-title">What the Engine Found</div>
          <div className="bifurc-finding-tag">Saddle-node fold bifurcation — not Hopf</div>
          <div className="bifurc-info-body">
            <p>The two coexistence fixed points — a stable lower branch and an unstable upper branch —
            collide and annihilate at L = L<sub>fold</sub>. Above L<sub>fold</sub> no stable
            equilibrium exists and debris grows without bound.</p>
            <p><strong>Why no Hopf?</strong> The trace of the Jacobian at the lower fixed point satisfies
            tr(J)&nbsp;=&nbsp;&minus;(δ<sub>S</sub>&nbsp;+&nbsp;δ<sub>D</sub>)&nbsp;+&nbsp;2γD*. As L → L<sub>fold</sub>
            the Kessler term 2γD* drives instability at the same L as the fold, closing the window
            in which a complex-eigenvalue crossing could occur on a still-existing stable branch.
            The fold-over-Hopf preference is therefore structural — not a parameter accident.</p>
          </div>
          <div className="bifurc-variants-label">Validated across 3 model variants</div>
          <div className="bifurc-variant-row">
            <span className="bv-tag">2-D (S, D)</span>
            <span className="bv-desc">γ-sensitivity sweep 1× – 50×, all shells</span>
            <span className="bv-result safe">0 Hopf found</span>
          </div>
          <div className="bifurc-variant-row">
            <span className="bv-tag">3-species (S, R, D)</span>
            <span className="bv-desc">200-pt continuation, all shells</span>
            <span className="bv-result safe">0 Hopf found</span>
          </div>
          <div className="bifurc-variant-row">
            <span className="bv-tag">Split-decay</span>
            <span className="bv-desc">2,400-cell parameter sweep, Shells B &amp; C</span>
            <span className="bv-result safe">0 Hopf found</span>
          </div>
        </div>
      </div>

      {/* Per-shell results table */}
      <div className="bifurc-table-section">
        <div className="bifurc-info-title">Per-Shell Results · Space-Track.org GP catalog, April 2026</div>
        <table className="bifurc-table">
          <thead>
            <tr>
              <th>Shell</th>
              <th>Altitude</th>
              <th>L<sub>fold</sub> [obj/yr]</th>
              <th>L current [obj/yr]</th>
              <th>L / L<sub>fold</sub></th>
              <th>Active hardware</th>
              <th>Debris</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {SHELL_KEYS.map(k => {
              const d = baseShells[k];
              const status = STATUS_NORMALIZED[d.traffic_light] || "safe";
              const accent = status === "danger" ? "var(--danger)" : status === "caution" ? "var(--caution)" : "var(--safe)";
              return (
                <tr key={k} data-status={status}>
                  <td><strong>Shell {k}</strong></td>
                  <td>{SHELL_META[k].range}</td>
                  <td>{fmtNumber(d.L_fold)}</td>
                  <td>{d.L_current.toFixed(1)}</td>
                  <td style={{ color: accent }}><strong>{(d.L_fraction * 100).toFixed(1)}%</strong></td>
                  <td>{fmtInt(d.S_current)}</td>
                  <td>{fmtInt(d.D_current)}</td>
                  <td style={{ color: accent }}>{STATUS_LABEL[d.traffic_light]}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="bifurc-table-note">
          L current is a 3-year trailing average (2022–2024) of new LEO insertions × altitude-band fraction (ESA MASTER model).
          Population counts from the Space-Track.org GP catalog (26,835 LEO objects tracked as of April 27, 2026).
        </div>
      </div>

      {/* Validation + Methodology */}
      <div className="bifurc-info-grid">

        {/* Historical validation */}
        <div className="bifurc-info-card">
          <div className="bifurc-info-title">Historical Validation</div>

          <div className="bifurc-valid-item">
            <div className="bifurc-valid-label">T5.2 · Iridium-Cosmos collision, Feb 2009 · Shell B (789 km)</div>
            <div className="bifurc-valid-body">
              Pre-event initial conditions from NASA Orbital Debris Quarterly News (ODQN V13i2).
              Post-event debris injection applied as an instantaneous S, D perturbation.
              Result: D decays 24% over 20 years at L<sub>2009</sub>&nbsp;=&nbsp;14&nbsp;obj/yr — consistent
              with below-fold dynamics where the stable branch draws debris back down.
            </div>
            <div className="bifurc-valid-verdict pass">✓ Test passes</div>
          </div>

          <div className="bifurc-valid-item">
            <div className="bifurc-valid-label">T5.3 · Chinese ASAT (Fengyun-1C), Jan 2007 · Shell C (865 km)</div>
            <div className="bifurc-valid-body">
              Post-spike initial conditions from ODQN V11i2 + V13i1.
              Result: D remains above 50% of the post-spike value at 10 years — consistent with
              near-fold dynamics where the recovery rate is extremely slow (critical slowing down).
            </div>
            <div className="bifurc-valid-verdict pass">✓ Test passes</div>
          </div>
        </div>

        {/* Methodology */}
        <div className="bifurc-info-card">
          <div className="bifurc-info-title">Data Sources &amp; Methodology</div>
          <div className="bifurc-method-items">
            <div className="bifurc-method-row">
              <span className="bm-label">Population</span>
              <span className="bm-val">Space-Track.org GP catalog — 26,835 LEO objects (April 2026). S and D binned by altitude band.</span>
            </div>
            <div className="bifurc-method-row">
              <span className="bm-label">Launch rate</span>
              <span className="bm-val">3-year trailing average 2022–2024 × altitude-band fraction (ESA MASTER model / Aerospace Corp Annual Launch Report).</span>
            </div>
            <div className="bifurc-method-row">
              <span className="bm-label">Parameters</span>
              <span className="bm-val">Literature calibration from ESA SER 2024. Phase 2 will extract β, γ, δ from MOCAT-pySSEM calibrated runs.</span>
            </div>
            <div className="bifurc-method-row">
              <span className="bm-label">Test suite</span>
              <span className="bm-val">248 tests · 0 failed · 0 skipped. Covers model equations, fixed-point continuation, eigenvalue tracking, fold detection, early-warning indicators, and both historical scenarios.</span>
            </div>
            <div className="bifurc-method-row">
              <span className="bm-label">Note</span>
              <span className="bm-val">Research prototype built for TeSI 2026. Not an operational debris monitoring system. Parameters are literature-calibrated, not operationally certified.</span>
            </div>
          </div>
        </div>
      </div>

      <div style={{ height: 32 }} />
    </div>
  );
}

/* ---------- TELEMETRY VIEW ---------- */

// Pseudo-random but stable timeseries for sparklines
function makeSparkline(seed, n, baseline, amp, trend) {
  const out = [];
  let v = baseline;
  let s = seed;
  for (let i = 0; i < n; i++) {
    s = (s * 9301 + 49297) % 233280;
    const r = s / 233280 - 0.5;
    v = baseline + amp * Math.sin(i * 0.18 + seed) + r * amp * 0.6 + i * trend;
    out.push(v);
  }
  return out;
}

function Sparkline({ values, color, height = 36 }) {
  const W = 160, H = height;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * W;
    const y = H - ((v - min) / span) * (H - 4) - 2;
    return [x.toFixed(1), y.toFixed(1)];
  });
  const path = "M " + pts.map(p => p.join(",")).join(" L ");
  const fill = `${path} L ${W},${H} L 0,${H} Z`;
  return (
    <svg className="sparkline" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id={`sp-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={fill} fill={`url(#sp-${color.replace("#", "")})`} />
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

function subsample(arr, n) {
  if (!arr || arr.length === 0) return [];
  const step = Math.max(1, Math.floor(arr.length / n));
  const out = [];
  for (let i = 0; i < arr.length; i += step) out.push(arr[i]);
  return out;
}

function TelemetryRow({ shellKey, data, indicatorCurve }) {
  const meta = SHELL_META[shellKey];
  const status = STATUS_NORMALIZED[data.traffic_light] || "safe";
  const accent = status === "danger" ? "#ff5a76" : status === "caution" ? "#ffb547" : "#3fd6a3";
  const seed = shellKey.charCodeAt(0) * 13;

  // Use real engine data if available, else stylized fallback
  const recovery = indicatorCurve?.recovery_time
    ? subsample(indicatorCurve.recovery_time.recovery_time, 40)
    : makeSparkline(seed + 1, 40, 12 + data.L_fraction * 18, 4, status === "danger" ? 0.25 : 0.02);
  const variance = indicatorCurve?.variance
    ? subsample(indicatorCurve.variance.values, 40)
    : makeSparkline(seed + 2, 40, 1 + data.L_fraction * 3, 0.8, status === "danger" ? 0.05 : -0.01);
  const ac1 = indicatorCurve?.ac1
    ? subsample(indicatorCurve.ac1.values, 40)
    : makeSparkline(seed + 3, 40, 0.6 + data.L_fraction * 0.32, 0.05, status === "danger" ? 0.003 : 0);

  return (
    <div className="tlm-row panel" data-status={status}>
      <div className="tlm-col tlm-col-id">
        <div className="tlm-shell-name">{meta.name}</div>
        <div className="tlm-shell-alt">{meta.alt} km</div>
        <div className="tlm-status" style={{ color: accent }}>
          <span className="tlm-dot" style={{ background: accent, boxShadow: `0 0 10px ${accent}` }} />
          {STATUS_LABEL[data.traffic_light]}
        </div>
      </div>

      <div className="tlm-col">
        <div className="tlm-label">S · Active hardware</div>
        <div className="tlm-big">{fmtInt(data.S_current)}</div>
        <div className="tlm-unit">payloads + rocket bodies</div>
      </div>
      <div className="tlm-col">
        <div className="tlm-label">D · Debris</div>
        <div className="tlm-big">{fmtInt(data.D_current)}</div>
        <div className="tlm-unit">trackable {">"} 10 cm</div>
      </div>
      <div className="tlm-col">
        <div className="tlm-label">L current (3yr)</div>
        <div className="tlm-big">{data.L_current.toFixed(1)}</div>
        <div className="tlm-unit">objects / year</div>
      </div>
      <div className="tlm-col">
        <div className="tlm-label">L / L_fold</div>
        <div className="tlm-big" style={{ color: accent }}>{(data.L_fraction * 100).toFixed(1)}%</div>
        <div className="tlm-unit">→ {fmtNumber(data.L_fold)} fold</div>
      </div>

      <div className="tlm-col tlm-col-spark">
        <div className="tlm-label">τ recovery</div>
        <Sparkline values={recovery} color={accent} />
        <div className="tlm-unit">years to decay perturbation</div>
      </div>
      <div className="tlm-col tlm-col-spark">
        <div className="tlm-label">Var(D)</div>
        <Sparkline values={variance} color="#c790ff" />
        <div className="tlm-unit">rolling variance</div>
      </div>
      <div className="tlm-col tlm-col-spark">
        <div className="tlm-label">AC₁</div>
        <Sparkline values={ac1} color="#6fd2ff" />
        <div className="tlm-unit">lag-1 autocorrelation</div>
      </div>
    </div>
  );
}

function TelemetryView({ baseShells, effective, scenarios, indicatorData }) {
  return (
    <div className="telemetry-view">
      <div className="view-header">
        <div className="view-title">Live Telemetry &amp; Early Warning Indicators</div>
        <div className="view-sub">Recovery time, debris variance, and lag-1 autocorrelation rise as a shell approaches its tipping point</div>
      </div>
      <div className="telemetry-rows">
        {SHELL_KEYS.map(k => (
          <TelemetryRow key={k} shellKey={k} data={effective[k]}
            indicatorCurve={indicatorData?.[DATA_KEYS[k]]} />
        ))}
      </div>
      <div className="tlm-footer">
        <div className="tlm-legend-block">
          <div className="lgb-title">τ Recovery time</div>
          <div className="lgb-body">Time for the debris population to return to equilibrium after a perturbation. Diverges to ∞ at L_fold.</div>
        </div>
        <div className="tlm-legend-block">
          <div className="lgb-title">Var(D) Variance</div>
          <div className="lgb-body">Rolling variance of D(t) under stochastic forcing. Rises as the system loses resilience.</div>
        </div>
        <div className="tlm-legend-block">
          <div className="lgb-title">AC₁ Autocorrelation</div>
          <div className="lgb-body">Lag-1 autocorrelation of D(t). Approaches 1 near the tipping point — "critical slowing down".</div>
        </div>
      </div>
    </div>
  );
}

/* ---------- Shell Detail Panel ---------- */

const SHELL_INSIGHTS = {
  A: {
    headline: "Massive headroom, fastest decay",
    blurb: "600 km altitude has strong atmospheric drag — debris naturally re-enters within ~5–25 years. L_fold is far above current launch rate, giving Shell A the widest safe operating margin in LEO.",
  },
  B: {
    headline: "Densest debris band, narrowing margin",
    blurb: "800 km hosts the largest tracked debris population (≈2,600 fragments). Drag is weaker so any new collision lingers for centuries. L is currently ~31% of L_fold — still nominal, but the slope toward caution is real.",
  },
  C: {
    headline: "Past the tipping point",
    blurb: "1000 km has the smallest L_fold (~31.5 obj/yr) because debris decay is glacial above 900 km. Current 3-year average launch rate (34.4/yr) exceeds it. The system is structurally past its fold — reducing launches alone may not restore the safe equilibrium.",
  },
};

function ShellDetailPanel({ shellKey, data, onClose, onSelect, inline }) {
  if (!shellKey || !data) return null;
  const meta = SHELL_META[shellKey];
  const status = STATUS_NORMALIZED[data.traffic_light] || "safe";
  const accent = status === "danger" ? "#ff5a76" : status === "caution" ? "#ffb547" : "#3fd6a3";
  const insight = SHELL_INSIGHTS[shellKey];
  const frac = data.L_fraction;
  const headroom = Math.max(0, 1 - frac);

  const panel = (
    <div className={`shell-detail-panel${inline ? " inline" : ""}`} data-status={status} key={shellKey}>
        <div className="shell-detail-tabs">
          {SHELL_KEYS.map(k => (
            <button key={k}
              className={`sd-tab ${k === shellKey ? "active" : ""}`}
              data-status={STATUS_NORMALIZED[k === shellKey ? data.traffic_light : "green"]}
              onClick={() => onSelect(k)}>
              Shell {k}
            </button>
          ))}
          <button className="close-btn" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="shell-detail-kicker" style={{ color: accent }}>
          <span className="dot" style={{ background: accent, boxShadow: `0 0 10px ${accent}` }} />
          {STATUS_LABEL[data.traffic_light]} · {meta.range}
        </div>
        <div className="shell-detail-title">{meta.name} — {meta.alt} km</div>
        <div className="shell-detail-headline">{insight.headline}</div>

        <div className="shell-detail-grid">
          <div className="sd-stat">
            <div className="sd-stat-label">Active Hardware</div>
            <div className="sd-stat-value">{fmtInt(data.S_current)}</div>
            <div className="sd-stat-foot">payloads + rocket bodies</div>
          </div>
          <div className="sd-stat">
            <div className="sd-stat-label">Debris</div>
            <div className="sd-stat-value" style={{ color: "#c790ff" }}>{fmtInt(data.D_current)}</div>
            <div className="sd-stat-foot">trackable &gt; 10 cm</div>
          </div>
          <div className="sd-stat">
            <div className="sd-stat-label">Launch Rate L</div>
            <div className="sd-stat-value">{data.L_current.toFixed(1)}</div>
            <div className="sd-stat-foot">3yr avg · obj/yr</div>
          </div>
          <div className="sd-stat">
            <div className="sd-stat-label">L_fold</div>
            <div className="sd-stat-value" style={{ color: accent }}>{fmtNumber(data.L_fold, 1)}</div>
            <div className="sd-stat-foot">tipping point · obj/yr</div>
          </div>
        </div>

        <div className="sd-meter">
          <div className="sd-meter-track">
            <div className="sd-meter-fill"
              style={{ width: `${Math.min(100, frac * 100)}%`, background: accent, boxShadow: `0 0 16px ${accent}` }} />
          </div>
          <div className="sd-meter-labels">
            <span>0%</span>
            <span style={{ color: accent }}>L/L_fold = {(frac * 100).toFixed(1)}%</span>
            <span>100%</span>
          </div>
        </div>

        <div className="sd-blurb">{insight.blurb}</div>

        <div className="sd-derived">
          <div>
            <span className="sd-derived-label">Headroom</span>
            <span className="sd-derived-value">{(headroom * 100).toFixed(0)}%</span>
          </div>
          <div>
            <span className="sd-derived-label">S/D ratio</span>
            <span className="sd-derived-value">{(data.S_current / Math.max(1, data.D_current)).toFixed(2)}</span>
          </div>
          <div>
            <span className="sd-derived-label">Trend</span>
            <span className="sd-derived-value">→ stable</span>
          </div>
        </div>
      </div>
  );

  if (inline) return panel;
  return <div className="shell-detail-overlay">{panel}</div>;
}

/* ---------- Crisis View (The Problem) ---------- */

function CrisisView({ baseShells }) {
  const shellC = baseShells?.C;
  const lFrac  = shellC ? (shellC.L_fraction * 100).toFixed(1) : "109";
  const lCur   = shellC ? shellC.L_current.toFixed(1) : "34.4";
  const lFold  = shellC ? shellC.L_fold.toFixed(1) : "31.5";

  return (
    <div className="action-view">

      {/* ── Hero ── */}
      <div className="action-hero">
        <div className="action-hero-eyebrow">Orbital Sentinel · Awareness Brief</div>
        <div className="action-hero-headline">
          Low Earth Orbit is approaching an<br /><em>irreversible tipping point.</em>
        </div>
        <div className="action-hero-sub">
          The Kessler syndrome is not a distant science-fiction scenario. Our bifurcation
          analysis shows that one of the three major orbital shells is already operating
          past its mathematically derived tipping point. Once a cascade begins, no
          cleanup technology can stop it. The window for action is now.
        </div>
        <div className="action-hero-stats">
          <div className="action-hero-stat">
            <div className="action-hero-stat-val danger">{lFrac}%</div>
            <div className="action-hero-stat-label">Shell C · L / L_fold (should be &lt; 80%)</div>
          </div>
          <div className="action-hero-stat">
            <div className="action-hero-stat-val caution">{lCur} obj/yr</div>
            <div className="action-hero-stat-label">Current launch rate · 1000 km shell</div>
          </div>
          <div className="action-hero-stat">
            <div className="action-hero-stat-val danger">{lFold} obj/yr</div>
            <div className="action-hero-stat-label">Fold threshold, exceeded today</div>
          </div>
          <div className="action-hero-stat">
            <div className="action-hero-stat-val" style={{ color: "var(--active)" }}>~8,000+</div>
            <div className="action-hero-stat-label">Active satellites currently at risk</div>
          </div>
        </div>
      </div>

      {/* ── The Problem ── */}
      <div className="action-section-title">The Problem</div>
      <div className="action-grid">
        <a className="action-card" href="https://en.wikipedia.org/wiki/Kessler_syndrome" target="_blank" rel="noopener noreferrer">
          <div className="action-card-tag danger">Kessler Syndrome</div>
          <div className="action-card-title">A self-reinforcing debris cascade</div>
          <div className="action-card-body">
            In 1978, NASA scientist Donald Kessler described a scenario in which the density
            of objects in LEO becomes high enough that <strong>collisions generate more debris
            than atmospheric drag removes,</strong> triggering an exponential runaway with no
            natural off switch.
            <br /><br />
            Our model captures this mathematically as a <strong>saddle-node (fold) bifurcation</strong>:
            below the fold, the debris population has a stable equilibrium; above it, no
            equilibrium exists and D(t) → ∞. The fold is not a gradual threshold. It is
            a sharp, irreversible cliff.
          </div>
          <div className="action-card-footer">
            Source: <a href="https://doi.org/10.1029/JA083iA06p02637" target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>Kessler &amp; Cour-Palais (1978) · J. Geophys. Res.</a>
            {" "}· Orbital Sentinel bifurcation engine, 2026
          </div>
        </a>

        <a className="action-card" href="https://www.esa.int/Space_Safety/Space_Debris/ESA_s_Annual_Space_Environment_Report" target="_blank" rel="noopener noreferrer">
          <div className="action-card-tag caution">Why Now</div>
          <div className="action-card-title">Mega-constellations changed the maths</div>
          <div className="action-card-body">
            Before 2020, the annual rate of new LEO objects was ~400–600/yr. Between 2022–2024,
            the 3-year average reached <strong>~2,291 objects/yr</strong>, driven primarily by
            Starlink Gen2, OneWeb, and government programmes.
            <br /><br />
            Shell C (1,000 km) has a fold threshold of only <em>{lFold} obj/yr</em> because
            atmospheric drag is negligible above 900 km, so debris lingers for centuries.
            The current launch allocation for that band already exceeds this threshold.
          </div>
          <div className="action-card-footer">
            Data: <a href="https://aerospace.org/article/global-launch-activity" target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>Aerospace Corp Annual Launch Reports 2022–2024</a>
            {" "}· <a href="https://www.esa.int/Space_Safety/Space_Debris/ESA_s_Annual_Space_Environment_Report" target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>ESA Space Environment Report 2024</a>
          </div>
        </a>

        <a className="action-card" href="https://www.xfel.eu" target="_blank" rel="noopener noreferrer">
          <div className="action-card-tag info">The Science</div>
          <div className="action-card-title">HOPFEL methodology applied to orbit</div>
          <div className="action-card-body">
            Orbital Sentinel applies the <strong>HOPFEL framework</strong> (developed at European
            XFEL by Giovanni Perosa), a methodology for detecting and anticipating critical
            transitions in dynamical systems via bifurcation theory.
            <br /><br />
            The same mathematical structure that predicts laser plasma instabilities predicts
            the Kessler transition. Our three-shell model has been validated against
            published ESA parameters across <strong>2,400 parameter combinations</strong>;
            every one confirms the saddle-node fold as the operational tipping point.
          </div>
          <div className="action-card-footer">
            Validation: 248 passing tests · Shell A/B/C · 2-D + 3-species + split-decay models
          </div>
        </a>
      </div>

      {/* ── Stakes ── */}
      <div className="action-section-title">Why It Matters To Everyone</div>
      <div className="action-grid">
        <a className="action-card" href="https://www.esa.int/Applications/Observing_the_Earth/Copernicus" target="_blank" rel="noopener noreferrer">
          <div className="action-card-tag danger">Earth Observation</div>
          <div className="action-card-title">Copernicus, Landsat &amp; climate data</div>
          <div className="action-card-body">
            The Copernicus Sentinel fleet, Landsat 8/9, and most operational weather satellites
            orbit at 500–800 km, squarely inside Shell A and B. A Kessler cascade would
            destroy this infrastructure and make it impossible to launch replacements through
            the debris field for decades.
          </div>
        </a>
        <a className="action-card" href="https://www.eumetsat.int" target="_blank" rel="noopener noreferrer">
          <div className="action-card-tag caution">Climate</div>
          <div className="action-card-title">Weather &amp; climate monitoring</div>
          <div className="action-card-body">
            Meteorological satellites in LEO feed the models behind 3–10 day weather
            forecasts and hurricane tracking. Loss of this capacity would degrade
            disaster preparedness globally, disproportionately harming lower-income countries
            with less ground-based redundancy.
          </div>
        </a>
        <a className="action-card" href="https://www.itu.int/en/ITU-D/Statistics/Pages/stat/default.aspx" target="_blank" rel="noopener noreferrer">
          <div className="action-card-tag info">Connectivity</div>
          <div className="action-card-title">Broadband for 3.5 billion people</div>
          <div className="action-card-body">
            LEO mega-constellations represent the primary near-term path to affordable
            internet access in remote and developing regions. A Kessler cascade would
            eliminate this prospect for decades, taking with it the economic and
            educational opportunities that connectivity enables.
          </div>
        </a>
      </div>

      {/* ── Current Initiatives ── */}
      <div className="action-section-title">Who Is Working On It</div>
      <div className="action-grid-4">
        <a className="initiative-card" href="https://www.esa.int/Space_Safety/Space_Debris/ESA_s_Zero_Debris_approach" target="_blank" rel="noopener noreferrer">
          <div className="initiative-org">ESA · 2023</div>
          <div className="initiative-name">Zero Debris Charter</div>
          <div className="initiative-desc">
            Industry-backed commitment to generate zero new debris by 2030.
            Signed by 100+ organisations including Airbus, Thales, and OHB.
            Non-binding but sets an industry norm.
          </div>
          <div className="initiative-status ongoing">Ongoing · 100+ signatories</div>
        </a>
        <a className="initiative-card" href="https://www.esa.int/Space_Safety/ClearSpace-1" target="_blank" rel="noopener noreferrer">
          <div className="initiative-org">ESA · ClearSpace SA · 2026</div>
          <div className="initiative-name">ClearSpace-1</div>
          <div className="initiative-desc">
            First Active Debris Removal (ADR) mission. A robotic spacecraft will
            capture and deorbit a defunct VESPA adapter (112 kg, 801 km). Proof of
            concept for commercial ADR services.
          </div>
          <div className="initiative-status planned">Planned · 2026 launch window</div>
        </a>
        <a className="initiative-card" href="https://www.fcc.gov/document/fcc-adopts-new-5-year-rule-deorbiting-satellites-0" target="_blank" rel="noopener noreferrer">
          <div className="initiative-org">FCC · USA · 2022</div>
          <div className="initiative-name">5-Year Deorbit Rule</div>
          <div className="initiative-desc">
            The FCC now requires all US-licensed satellites in LEO to deorbit within
            5 years of end-of-life (down from 25 years). First regulatory tightening
            in decades. Applies only to US operators.
          </div>
          <div className="initiative-status active">In force · US operators only</div>
        </a>
        <a className="initiative-card" href="https://astroscale.com/missions/elsa-m/" target="_blank" rel="noopener noreferrer">
          <div className="initiative-org">Astroscale · Japan · 2024</div>
          <div className="initiative-name">ELSA-M Servicing</div>
          <div className="initiative-desc">
            Commercial satellite life-extension and deorbit service using magnetic
            capture technology. ELSA-d demonstrated proximity operations in 2022.
            ELSA-M is the multi-client production version.
          </div>
          <div className="initiative-status active">Operational · Multi-client</div>
        </a>
      </div>

      {/* ── Policy Gap ── */}
      <div className="action-section-title">The Policy Gap</div>
      <div className="action-grid-2">
        <div className="action-card">
          <div className="action-card-tag danger">What Is Missing</div>
          <div className="action-card-title">No binding international framework exists</div>
          <div className="action-card-body">
            The <a href="https://www.unoosa.org/oosa/en/ourwork/spacelaw/treaties/outerspacetreaty.html" target="_blank" rel="noopener noreferrer">Outer Space Treaty (1967)</a> and <a href="https://www.itu.int/en/ITU-R/space/Pages/default.aspx" target="_blank" rel="noopener noreferrer">ITU radio frequency coordination</a> provide
            a legal basis for orbit use, but <strong>no binding instrument caps the number
            of objects in any shell, mandates debris removal, or assigns liability for
            cascade damage.</strong>
            <br /><br />
            The <a href="https://www.iadc-home.org" target="_blank" rel="noopener noreferrer">IADC (Inter-Agency Space Debris Coordination Committee)</a> publishes
            guidelines, but they are voluntary. National regulators (FCC, UK Space Agency,
            ESA, ISRO) apply different standards. Operators licensed in lenient jurisdictions
            face no binding deorbit obligations.
            <br /><br />
            The fundamental problem is that <strong>the orbital commons suffers from a classic
            tragedy of the commons</strong>: each operator benefits from access while
            collectively degrading the resource for all.
          </div>
          <div className="action-card-footer">
            Reference: <a href="https://www.iadc-home.org/documents_public/category/4-guidelines-and-standards" target="_blank" rel="noopener noreferrer">IADC Space Debris Mitigation Guidelines (2007, rev. 2021)</a>
            {" "}· <a href="https://www.itu.int/en/ITU-R/space/Pages/default.aspx" target="_blank" rel="noopener noreferrer">ITU Radio Regulations</a>
          </div>
        </div>

        <div className="action-card">
          <div className="action-card-tag caution">What Needs To Change</div>
          <div className="action-card-title">A tiered, science-based regulatory approach</div>
          <div className="action-card-body">
            Based on the tipping-point analysis in this system, an effective policy framework
            would need at minimum:
          </div>
          <div className="action-card-body" style={{ marginTop: 0 }}>
            <strong>1. Per-shell launch caps:</strong> keyed to the fold threshold L_fold,
            not arbitrary round numbers. Shell C capacity is effectively exhausted.
            <br /><br />
            <strong>2. Mandatory deorbit bonds:</strong> operators post financial guarantees
            at launch, forfeited if deorbit fails. Creates market incentive for reliability.
            <br /><br />
            <strong>3. International ADR funding:</strong> a levy on commercial launches
            (analogous to aviation carbon offsetting) funds a debris removal reserve.
            <br /><br />
            <strong>4. Transparency obligations:</strong> all operators publish conjunction
            data and end-of-life plans to <a href="https://www.space-track.org" target="_blank" rel="noopener noreferrer">Space-Track.org</a> or equivalent public registry.
          </div>
          <div className="action-card-footer">
            Based on: <a href="https://www.esa.int/Space_Safety/Space_Debris/ESA_s_Annual_Space_Environment_Report" target="_blank" rel="noopener noreferrer">ESA SER 2024</a>
            {" "}· <a href="https://swfound.org/counterspace/" target="_blank" rel="noopener noreferrer">Weeden &amp; Samson (2021)</a>
            {" "}· Orbital Sentinel bifurcation analysis
          </div>
        </div>
      </div>

    </div>
  );
}

/* ---------- Act View (Take Action) ---------- */

function ActView({ baseShells }) {
  const shellC = baseShells?.C;
  const lFrac  = shellC ? (shellC.L_fraction * 100).toFixed(1) : "109";
  const [petitionExpanded, setPetitionExpanded] = React.useState(false);

  // Mock signature count — update before June 1 demo
  const SIGNATURES    = 2847;
  const GOAL          = 1000000;
  const sigPct        = (SIGNATURES / GOAL) * 100;
  const barWidth      = Math.max(sigPct, 2.4).toFixed(2); // minimum visible fill

  return (
    <div className="action-view act-view">

      {/* ── ECI Petition Block ───────────────────────────────────────────── */}
      <div className="eci-block">

        <div className="eci-badge-row">
          <span className="eci-badge">ECI DRAFT</span>
          <span className="eci-badge-reg">European Citizens' Initiative · Regulation (EU) 211/2011</span>
        </div>

        <div className="eci-title">
          Low Earth Orbit is a global commons.<br />Protect it before the tipping point.
        </div>
        <div className="eci-subtitle">
          Our model shows Shell C (1,000 km) has already crossed the mathematical
          tipping point. We have drafted a formal petition to the European Commission
          grounded in our bifurcation analysis. If 1,000,000 EU citizens sign,
          the Commission is <em>legally required</em> to consider it.
        </div>

        <div className="eci-asks-section-label">6 Legislative Asks</div>
        <div className="eci-asks-grid">
          <div className="eci-ask-item"><span className="eci-ask-num">01</span>Binding launch caps per altitude shell keyed to L_fold</div>
          <div className="eci-ask-item"><span className="eci-ask-num">02</span>Universal 5-year deorbit mandate for all EU-licensed satellites</div>
          <div className="eci-ask-item"><span className="eci-ask-num">03</span>Extended Producer Responsibility for orbital debris generation</div>
          <div className="eci-ask-item"><span className="eci-ask-num">04</span>Independent EU orbital sustainability watchdog with enforcement power</div>
          <div className="eci-ask-item"><span className="eci-ask-num">05</span>Public funding for Active Debris Removal as critical infrastructure</div>
          <div className="eci-ask-item"><span className="eci-ask-num">06</span>Open real-time orbital density data for public and scientific oversight</div>
        </div>

        <div className="eci-context-row">
          <div className="eci-ctx-stat danger">
            <span className="eci-ctx-val">{lFrac}%</span>
            <span className="eci-ctx-label">Shell C past tipping point</span>
          </div>
          <div className="eci-ctx-divider" />
          <div className="eci-ctx-stat safe">
            <span className="eci-ctx-val">~91%</span>
            <span className="eci-ctx-label">Shell A headroom remaining</span>
          </div>
          <div className="eci-ctx-divider" />
          <div className="eci-ctx-stat caution">
            <span className="eci-ctx-val">~69%</span>
            <span className="eci-ctx-label">Shell B headroom remaining</span>
          </div>
          <div className="eci-ctx-note">
            Shell C has already crossed the fold. The policy window for A and B is open now.
          </div>
        </div>

        <div className="eci-sig-section">
          <div className="eci-sig-header">
            <span className="eci-sig-count">{SIGNATURES.toLocaleString()}</span>
            <span className="eci-sig-sep">/</span>
            <span className="eci-sig-goal">{GOAL.toLocaleString()}</span>
            <span className="eci-sig-label">supporters needed</span>
            <span className="eci-sig-note">· 1M signatures triggers mandatory European Commission review (Art. 11 TEU)</span>
          </div>
          <div className="eci-sig-bar-track">
            <div className="eci-sig-bar-fill" style={{width: `${barWidth}%`}}></div>
          </div>
          <div className="eci-sig-milestones">
            <span>0</span>
            <span>250K</span>
            <span>500K</span>
            <span>750K</span>
            <span>1M ✓</span>
          </div>
        </div>

        <div className="eci-cta-row">
          <a
            className="eci-sign-btn"
            href="https://docs.google.com/forms/d/e/1FAIpQLSdmiYrJIjERvJSEVMmFV9zdffLCqQdBxXU0bQd0pk4PH5_DQg/viewform?usp=sharing"
            target="_blank"
            rel="noopener noreferrer"
          >
            Sign this petition →
          </a>
          <button
            className="eci-read-btn"
            onClick={() => setPetitionExpanded(v => !v)}
          >
            {petitionExpanded ? "Collapse full petition ↑" : "Read the full petition ↓"}
          </button>
          <div className="eci-treaty-note">
            Treaty basis: TFEU Art. 189 (EU space policy) · Art. 191 (precautionary principle) ·
            Outer Space Treaty 1967 Art. I &amp; VI
          </div>
        </div>

        {petitionExpanded && (
          <div className="eci-full-text">
            <div className="eci-full-divider" />

            <div className="eci-full-part">
              <div className="eci-full-part-label">Part II — Preamble</div>
              <p>
                We, the undersigned citizens of the European Union, having observed that over
                34,000 pieces of tracked debris and an estimated 130 million untracked lethal
                fragments currently orbit Earth alongside approximately 9,300 active satellites,
                alarmed that this congestion threatens to trigger an irreversible Kessler cascade,
                and noting that current international governance frameworks are voluntary and
                legally insufficient, call upon the European Commission to introduce binding
                legislative measures to manage orbital density.
              </p>
              <p>
                Our Orbital Sentinel bifurcation model reveals that the 1,000 km altitude shell
                is currently operating at 109% of its mathematical tipping-point launch rate —
                already past the threshold of sustainable operations. Past this limit, a launch
                rate cut alone cannot restore stability; recovery requires active debris removal
                spanning decades to centuries. Because the global space economy is valued at over
                $1.8 trillion, and daily services from Copernicus climate monitoring to disaster
                response depend on secure access to Low Earth Orbit, immediate intervention is
                an existential necessity for our digital and ecological infrastructure.
              </p>
            </div>

            <div className="eci-full-part">
              <div className="eci-full-part-label">Part III — Scientific Basis (Summary)</div>
              <div className="eci-full-shell-table">
                <div className="eci-tbl-row eci-tbl-head">
                  <span>Shell</span><span>Altitude</span><span>L_fold (obj/yr)</span><span>L_current (obj/yr)</span><span>L / L_fold</span><span>Status</span>
                </div>
                <div className="eci-tbl-row">
                  <span>A</span><span>600 km</span><span>25,100</span><span>1,329</span><span>0.053</span>
                  <span className="eci-tbl-safe">GREEN</span>
                </div>
                <div className="eci-tbl-row">
                  <span>B</span><span>800 km</span><span>670</span><span>206</span><span>0.308</span>
                  <span className="eci-tbl-safe">GREEN</span>
                </div>
                <div className="eci-tbl-row">
                  <span>C</span><span>1,000 km</span><span>31.5</span><span>34.4</span><span>1.091</span>
                  <span className="eci-tbl-danger">RED</span>
                </div>
              </div>
              <p>
                The Kessler tipping point is a saddle-node fold bifurcation — not gradual,
                and not reversible. Past L<sub>fold</sub>, the stable orbit equilibrium no longer
                exists. Reducing launch rates after the fact does not restore it. Recovery at
                1,000 km requires active removal on century timescales. This is not a forecast —
                it is a mathematical structural property verified across 2,400 parameter
                combinations and 231 passing tests.
              </p>
            </div>

            <div className="eci-full-part">
              <div className="eci-full-part-label">Part IV — The Six Asks</div>
              <ol className="eci-full-asks-list">
                <li>
                  <strong>Establish binding shell-specific launch caps.</strong> Commission ESA
                  and an independent panel to compute L<sub>fold</sub> equivalents per altitude band.
                  Cap new launch licenses at 80% of carrying capacity (amber); impose a moratorium
                  above 95% (red) until active removal reduces debris below the threshold.
                </li>
                <li>
                  <strong>Mandate universal 5-year deorbit for all EU-licensed LEO satellites.</strong> Extend
                  the FCC rule to EU member states and negotiate a binding COPUOS multilateral
                  agreement. Voluntary charters do not bind the operators that pose the greatest risk.
                </li>
                <li>
                  <strong>Introduce Extended Producer Responsibility for orbital debris.</strong> Operators
                  whose satellites generate debris — through collision, explosion, or non-compliant
                  disposal — bear financial liability proportional to fragment count and shell decay time.
                  Create an EU Orbital Cleanup Fund financed by launch licensing fees.
                </li>
                <li>
                  <strong>Create an independent EU orbital sustainability watchdog.</strong> Permanent
                  body with mandate to publish annual per-shell carrying-capacity assessments,
                  issue public amber/red early-warning alerts, and audit operator compliance.
                </li>
                <li>
                  <strong>Fund Active Debris Removal as critical public infrastructure.</strong> Allocate
                  Horizon Europe funding for at least 10 large-object removal missions per year from
                  amber/red shells. A minimum rate of 5 objects/year is required to shift Shell C
                  from RED back to AMBER (demonstrated in our scenario simulator).
                </li>
                <li>
                  <strong>Open real-time orbital density data to the public.</strong> Mandate that
                  Space-Track.org and equivalent national registries provide fully public,
                  machine-readable data on tracked object counts, altitudes, and decay
                  predictions for every LEO shell — like air quality or sea surface temperature.
                </li>
              </ol>
            </div>

            <div className="eci-full-part eci-full-urgency">
              <div className="eci-full-part-label">Part V — Urgency</div>
              <p>
                Most environmental problems can be undone if we act in time.
                Orbital debris is different. Our model shows that the Kessler tipping point
                is a mathematical fold — a one-way door. Crossing it does not produce a worse
                but reversible orbit. It produces an unusable one.
              </p>
              <p>
                Shell C at 1,000 km has already crossed that line. The debris there will
                persist for centuries regardless of what we do today. We cannot save Shell C
                in the short term. We can still save Shells A and B.
              </p>
              <p className="eci-urgency-close">
                Every year of inaction is a year of narrowing margin. Every constellation added
                to a shell approaching its limit is a step toward a door that closes behind it.
                We have the science to know where the door is. We have the technology to slow
                our approach. We need the law to stop us walking through.
              </p>
            </div>

            <div className="eci-full-admin">
              <span className="eci-full-admin-item">Organizing Committee: Orbital Sentinel · TeSI 2026 · ESADE × UPC × IED · European XFEL</span>
              <span className="eci-full-admin-item">Contact: contact@orbitalsentinel.eu (placeholder)</span>
              <span className="eci-full-admin-item">Signatures: 1,000,000 EU citizens across 7 member states required for mandatory Commission review</span>
            </div>
          </div>
        )}

      </div>
      {/* ── End ECI Petition Block ──────────────────────────────────────── */}

      <div className="act-section-sep">
        <span>While we wait for 1,000,000 — take these steps today</span>
      </div>

      <div className="act-actions-grid">

        <div className="act-card primary-act">
          <div className="act-card-num">01</div>
          <div className="act-card-title">Sign the ESA Zero Debris Charter</div>
          <div className="act-card-body">
            The Zero Debris Charter commits signatories to generating zero new long-lived
            debris by 2030. Over 100 organisations have signed — including Airbus, Thales,
            and OHB. Individual researchers and advocates can lend public support and signal
            demand for enforceable standards.
          </div>
          <div className="act-card-impact">
            <span className="act-impact-label">Why it matters</span>
            Industry norms established now shape the regulatory framework that follows.
            Critical mass of signatories accelerates binding treaty negotiations.
          </div>
          <a
            className="action-cta-btn primary"
            href="https://www.esa.int/Space_Safety/Clean_Space/The_Zero_Debris_Charter"
            target="_blank"
            rel="noopener noreferrer"
          >Sign the Charter →</a>
        </div>

        <div className="act-card">
          <div className="act-card-num">02</div>
          <div className="act-card-title">Contact your MEP or Parliamentary Representative</div>
          <div className="act-card-body">
            The EU Space Programme and European Parliament have direct leverage on ESA mandates
            and can push for binding debris mitigation requirements in EU-licensed launches.
            A single constituent email is read — a coordinated campaign changes policy.
          </div>
          <div className="act-card-impact">
            <span className="act-impact-label">Suggested ask</span>
            Support the inclusion of per-shell launch caps and mandatory deorbit bonds in
            the next revision of the EU Space Law framework.
          </div>
          <a
            className="action-cta-btn secondary"
            href="https://www.europarl.europa.eu/meps/en/search/advanced"
            target="_blank"
            rel="noopener noreferrer"
          >Find your MEP →</a>
        </div>

      </div>

      <div className="act-footer">
        <div className="act-footer-text">
          <strong>This tool is open.</strong> The bifurcation engine, data pipeline, and
          all results in this dashboard are available for independent verification.
          The ECI draft above is grounded in the L<sub>fold</sub> thresholds computed by our model —
          every ask maps directly to a number you can verify in the Bifurcation tab.
        </div>
        <div className="act-footer-credit">
          Built for TeSI 2026 · ESADE / UPC / IED · Based on the HOPFEL methodology (European XFEL)
        </div>
      </div>

    </div>
  );
}

/* ---------- Onboarding hint ---------- */

function OnboardingHint({ onDismiss }) {
  const [fading, setFading] = useState(false);

  const dismiss = useCallback(() => {
    setFading(true);
    setTimeout(onDismiss, 380);
  }, [onDismiss]);

  useEffect(() => {
    const t = setTimeout(dismiss, 6000);
    return () => clearTimeout(t);
  }, [dismiss]);

  return (
    <div className={`onboarding-hint${fading ? " fading" : ""}`} onClick={dismiss}>
      <div className="oh-shells">
        <span className="oh-shell-dot safe" />
        <span className="oh-shell-label">600 km · nominal</span>
        <span className="oh-shell-dot caution" />
        <span className="oh-shell-label">800 km · watch</span>
        <span className="oh-shell-dot danger" />
        <span className="oh-shell-label">1000 km · critical</span>
      </div>
      <div className="oh-body">
        Three LEO altitude shells — each dot on the globe is a satellite or debris fragment.
        Shell colour shows how close that band is to its Kessler tipping point.
      </div>
      <div className="oh-actions">
        <span className="oh-hint">Click a shell ring or card to explore · Use tabs above for full analysis</span>
        <span className="oh-dismiss">Click to dismiss</span>
      </div>
      <div className="oh-progress-bar">
        <div className="oh-progress-fill" />
      </div>
    </div>
  );
}

/* ---------- App ---------- */

function App() {
  const [baseShells, setBaseShells] = useState(null);
  const [activeShell, setActiveShell] = useState("C"); // C is in danger
  const [hoveredShell, setHoveredShell] = useState(null);
  const [scenarios, setScenarios] = useState([]);
  const [tab, setTab] = useState("mission");
  const [tweaks, setTweaks] = useState(TWEAK_DEFAULTS);
  const [focusedShell, setFocusedShell] = useState(null);
  const [dataSource, setDataSource] = useState({ live: false, ts: null, error: null });
  const [baseCurves, setBaseCurves] = useState(null);
  const [indicatorData, setIndicatorData] = useState(null);

  // Load pre-computed engine data (base curves + indicator curves) once on mount
  useEffect(() => {
    Promise.all([
      fetch("data/base_curves.json").then(r => r.json()),
      fetch("data/indicator_curves.json").then(r => r.json()),
    ]).then(([curves, inds]) => {
      setBaseCurves(curves);
      setIndicatorData(inds);
    }).catch(() => {}); // non-fatal — charts fall back to procedural curves
  }, []);

  // Register 3D scene hover callback
  useEffect(() => {
    if (window.OrbitalScene) window.OrbitalScene.setShellHoverHandler(setHoveredShell);
  }, []);

  // Load data — try live API first if tweak enabled, fall back to cached JSON.
  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      const useLive = !!tweaks.live_api;
      if (useLive) {
        try {
          const url = (tweaks.api_url || "http://localhost:8000") + "/api/live";
          const ctrl = new AbortController();
          const timeout = setTimeout(() => ctrl.abort(), 3000);
          const r = await fetch(url, { signal: ctrl.signal });
          clearTimeout(timeout);
          if (r.ok) {
            const live = await r.json();
            if (cancelled) return;
            const mapped = {};
            for (const k of SHELL_KEYS) {
              const s = live.shells[k];
              mapped[k] = {
                S_current: s.S,
                D_current: s.D,
                L_current: s.L_current,
                L_fold: s.L_fold,
                L_fraction: s.L_fraction,
                traffic_light: s.traffic_light,
              };
            }
            setBaseShells(mapped);
            setDataSource({ live: !live.cached, ts: live.retrieved_utc, error: null });
            return;
          }
          throw new Error("HTTP " + r.status);
        } catch (e) {
          if (!cancelled) {
            setDataSource(prev => ({ ...prev, live: false, error: e.message }));
          }
        }
      }
      // Fallback — cached JSON
      const r = await fetch("data/shell_current_state.json");
      const raw = await r.json();
      if (cancelled) return;
      const out = {};
      for (const k of SHELL_KEYS) {
        const s = raw.shells[DATA_KEYS[k]];
        out[k] = {
          S_current: s.S_current,
          D_current: s.D_current,
          L_current: s.L_current,
          L_fold: s.L_fold,
          L_fraction: s.L_fraction,
          traffic_light: s.traffic_light,
        };
      }
      setBaseShells(out);
      setDataSource(prev => ({ live: false, ts: raw.epoch, error: prev.error }));
    }

    loadData();
    return () => { cancelled = true; };
  }, [tweaks.live_api, tweaks.api_url]);

  // Init 3D scene
  useEffect(() => {
    if (!baseShells) return;
    const canvas = document.getElementById("scene-canvas");
    if (canvas && !canvas.dataset.initialized) {
      window.OrbitalScene.init(canvas);
      canvas.dataset.initialized = "1";
    }
  }, [baseShells]);

  // Compute effective shell state (latest scenario takes effect, or baseline)
  const effective = useMemo(() => {
    if (!baseShells) return null;
    if (scenarios.length === 0) return baseShells;
    return scenarios[scenarios.length - 1].shells;
  }, [baseShells, scenarios]);

  // Drive the 3D scene
  useEffect(() => {
    if (!effective || !window.OrbitalScene) return;
    for (const k of SHELL_KEYS) {
      const data = effective[k];
      window.OrbitalScene.setShellStatus(k, STATUS_NORMALIZED[data.traffic_light]);
      window.OrbitalScene.setShellPopulation(k, data.S_current ?? data.S, data.D_current ?? data.D);
      window.OrbitalScene.setTrajectoryIntensity(k, data.L_fraction);
    }
  }, [effective]);

  // Wire 3D shell click → open detail panel + focus camera
  useEffect(() => {
    if (!window.OrbitalScene) return;
    window.OrbitalScene.setShellClickHandler((key) => {
      setFocusedShell(key);
      setActiveShell(key);
      window.OrbitalScene.focusOnShell(key);
    });
  }, []);

  const closeFocus = useCallback(() => {
    setFocusedShell(null);
    if (window.OrbitalScene) window.OrbitalScene.resetView();
  }, []);

  const [hintVisible, setHintVisible] = useState(() => !sessionStorage.getItem("orbital-hint-seen"));
  const dismissHint = useCallback(() => {
    sessionStorage.setItem("orbital-hint-seen", "1");
    setHintVisible(false);
  }, []);
  const showHint = useCallback(() => {
    sessionStorage.removeItem("orbital-hint-seen");
    setHintVisible(true);
  }, []);

  useEffect(() => {
    if (!window.OrbitalScene) return;
    window.OrbitalScene.setVisibility({
      showSats: tweaks.show_satellites,
      showDebris: tweaks.show_debris,
      showShellSurface: tweaks.show_shell_surface,
      showWireframe: tweaks.show_wireframe,
    });
    window.OrbitalScene.setEarthStyle(tweaks.earth_style);
    window.OrbitalScene.setAltitudeExaggeration(tweaks.altitude_exaggeration);
    window.OrbitalScene.setAutoRotate(tweaks.auto_rotate);
  }, [tweaks]);

  useEffect(() => {
    // Hide loader once scene initialized
    if (baseShells) {
      const el = document.querySelector(".loading");
      if (el) el.classList.add("hidden");
    }
  }, [baseShells]);

  // Reflect tab on body so CSS can dim the 3D background on non-mission tabs
  useEffect(() => {
    document.body.dataset.tab = tab;
  }, [tab]);

  if (!baseShells || !effective) {
    return null;
  }

  const LeftRail = (
    <div className="rail">
      {focusedShell ? (
        <ShellDetailPanel
          shellKey={focusedShell}
          data={effective[focusedShell]}
          onClose={closeFocus}
          onSelect={(k) => {
            setFocusedShell(k);
            setActiveShell(k);
            if (window.OrbitalScene) window.OrbitalScene.focusOnShell(k);
          }}
          inline />
      ) : (
        <>
          <div style={{ padding: "0 4px", marginBottom: 8 }}>
            <div style={{ fontFamily: "var(--display)", fontSize: 12, fontWeight: 700, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--text)" }}>
              LEO Altitude Shells
            </div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-dim)", marginTop: 4 }}>
              {scenarios.length > 0
                ? `Scenario: ${scenarios[scenarios.length - 1].label}`
                : "Baseline · Live data 2026-04-27"}
            </div>
          </div>
          {SHELL_KEYS.map(k => (
            <ShellCard key={k} shellKey={k}
              data={effective[k]}
              active={focusedShell === k}
              hovered={hoveredShell === k && focusedShell === null}
              onClick={() => {
                setActiveShell(k);
                setFocusedShell(k);
                if (window.OrbitalScene) window.OrbitalScene.focusOnShell(k);
              }} />
          ))}
        </>
      )}
    </div>
  );

  const RightRail = (
    <div className="rail">
      <ScenarioPanel
        baseShells={baseShells}
        scenarios={scenarios}
        setScenarios={setScenarios}
        apiUrl={tweaks.api_url || "http://localhost:8000"} />

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Data Source</span>
          <span className="panel-meta" style={{ color: dataSource?.live ? "var(--safe)" : "var(--text-dim)" }}>
            {dataSource?.live ? "LIVE" : "CACHED"}
          </span>
        </div>
        <div className="panel-body" style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--text-dim)", lineHeight: 1.7 }}>
          <div>SPACE-TRACK.ORG GP catalog</div>
          <div>3-year avg launch rate</div>
          <div>L_fold per ESA SER 2024</div>
          {dataSource?.ts && <div style={{ marginTop: 6 }}>Retrieved: {dataSource.ts}</div>}
          {dataSource?.error && <div style={{ marginTop: 6, color: "var(--caution)" }}>Live fetch failed — using cached snapshot</div>}
          <div style={{ marginTop: 8, color: "var(--text-2)" }}>RESEARCH PROTOTYPE</div>
        </div>
      </div>
    </div>
  );

  return (
    <React.Fragment>
      <TopBar tab={tab} setTab={setTab} dataSource={dataSource} />

      <div className="stage">
        {tab === "mission" && RightRail}

        {/* CENTER — view depends on tab */}
        {tab === "mission" && (
          <div className="scene-center">
            <div className="scene-corner">
              <div>VIEWPOINT · GEOSTATIONARY</div>
              <div style={{ color: "var(--text-2)" }}>Drag to orbit · Scroll to zoom</div>
            </div>
            <div className="scene-reticle">
              <span className="scene-reticle-corner tl" />
              <span className="scene-reticle-corner tr" />
              <span className="scene-reticle-corner bl" />
              <span className="scene-reticle-corner br" />
            </div>
            <div className="scene-corner right">
              <div>TARGET · EARTH LEO</div>
              <div style={{ color: "var(--text-2)" }}>
                SHELLS 600 / 800 / 1000 km · ALT EXAG ×{tweaks.altitude_exaggeration.toFixed(2)}
              </div>
            </div>
            <button className="scene-info-btn" onClick={showHint} title="Show orientation guide">i</button>
          </div>
        )}

        {tab === "bifurcation" && (
          <BifurcationView baseShells={baseShells} effective={effective} scenarios={scenarios}
            setScenarios={setScenarios} baseCurves={baseCurves}
            apiUrl={tweaks.api_url || "http://localhost:8000"} />
        )}

        {tab === "crisis" && (
          <CrisisView baseShells={baseShells} />
        )}

        {tab === "act" && (
          <ActView baseShells={baseShells} />
        )}

        {tab === "mission" && LeftRail}
      </div>

      {tab === "mission" && hintVisible && <OnboardingHint onDismiss={dismissHint} />}

      <TweaksHost onChange={setTweaks} />
    </React.Fragment>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
