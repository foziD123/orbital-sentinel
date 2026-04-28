/**
 * chart.js — D3 bifurcation diagram component for Orbital Sentinel Module 2.
 *
 * Exports one function:
 *   createBifurcationChart(container, shellName, shellKey, baseCurves, currentState)
 *
 * And one method on the returned chart object:
 *   chart.addOverlay(scenarioData, color, label)
 *   chart.removeOverlay(label)
 *   chart.clearOverlays()
 *   chart.updateTrafficLight(color)   // "green" | "amber" | "red"
 *
 * Spec from MODULE2_PLAN.md:
 *   - X axis: L (launch rate), range 0 → 1.2 × L_fold_base
 *   - Y axis: D* (debris equilibrium), log scale
 *   - Lower branch: solid blue
 *   - Upper branch: dashed blue
 *   - L_fold line: red dashed vertical, labelled "Point of no return"
 *   - Real-world marker: orange star at (L_current, D_current) with tooltip
 *   - What-if overlays: coloured curve + L_fold line per scenario
 *   - Traffic light: coloured dot in top-right corner
 *   - Tooltip on hover
 */

"use strict";

/* -------------------------------------------------------------------------
 * Colour palette (matches MODULE2_PLAN.md presets)
 * ----------------------------------------------------------------------- */
const TRAFFIC_COLORS = { green: "#2DC653", amber: "#F4A100", red: "#D62828" };

/* -------------------------------------------------------------------------
 * createBifurcationChart
 * ----------------------------------------------------------------------- */
function createBifurcationChart(container, shellName, shellKey, baseCurves, currentState) {
  const shellData = baseCurves[shellName];
  const shellState = currentState.shells[shellName];

  /* ---- Layout ---- */
  const margin = { top: 48, right: 32, bottom: 56, left: 72 };
  const totalW = container.clientWidth || 420;
  const totalH = 360;
  const W = totalW - margin.left - margin.right;
  const H = totalH - margin.top - margin.bottom;

  /* ---- SVG ---- */
  const svg = d3.select(container)
    .append("svg")
    .attr("width", totalW)
    .attr("height", totalH)
    .attr("class", "bifurcation-svg");

  const g = svg.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  /* ---- Scales ---- */
  const L_fold_base = shellData.L_fold;
  const xMax = 1.2 * L_fold_base;

  // Collect all D_star values for initial y domain
  const allD = [
    ...shellData.lower_branch.D_star,
    ...shellData.upper_branch.D_star,
  ].filter(d => d > 0);
  const yMin = Math.max(1, d3.min(allD) * 0.5);
  const yMax = d3.max(allD) * 3;

  const xScale = d3.scaleLinear().domain([0, xMax]).range([0, W]);
  const yScale = d3.scaleLog().domain([yMin, yMax]).range([H, 0]).clamp(true);

  /* ---- Axes ---- */
  const xAxis = d3.axisBottom(xScale)
    .ticks(5)
    .tickFormat(d => d >= 1000 ? `${(d / 1000).toFixed(0)}k` : d.toFixed(0));
  const yAxis = d3.axisLeft(yScale)
    .ticks(5, "~s");

  g.append("g").attr("class", "x-axis")
    .attr("transform", `translate(0,${H})`)
    .call(xAxis);

  g.append("g").attr("class", "y-axis").call(yAxis);

  /* ---- Axis labels ---- */
  g.append("text")
    .attr("class", "axis-label")
    .attr("x", W / 2).attr("y", H + 44)
    .attr("text-anchor", "middle")
    .text("Launch rate L (objects/yr)");

  g.append("text")
    .attr("class", "axis-label")
    .attr("transform", "rotate(-90)")
    .attr("x", -H / 2).attr("y", -58)
    .attr("text-anchor", "middle")
    .text("Debris equilibrium D* (objects)");

  /* ---- Title ---- */
  const altLabel = { A: "600 km", B: "800 km", C: "1000 km" }[shellKey];
  svg.append("text")
    .attr("class", "chart-title")
    .attr("x", totalW / 2).attr("y", 22)
    .attr("text-anchor", "middle")
    .text(`Shell ${shellKey} — ${altLabel}`);

  /* ---- Traffic-light dot (top-right inside chart area) ---- */
  const tlGroup = svg.append("g")
    .attr("transform", `translate(${totalW - margin.right - 18}, 22)`);

  const tlCircle = tlGroup.append("circle")
    .attr("r", 10)
    .attr("fill", TRAFFIC_COLORS[shellState.traffic_light] || "#888")
    .attr("stroke", "#fff").attr("stroke-width", 1.5);

  const tlLabel = tlGroup.append("text")
    .attr("x", -16).attr("y", 4)
    .attr("text-anchor", "end")
    .attr("class", "traffic-label")
    .text(shellState.traffic_light.toUpperCase());

  /* ---- Line generators ---- */
  function makeLine() {
    return d3.line()
      .x(d => xScale(d.L))
      .y(d => yScale(Math.max(d.D_star, yMin)))
      .defined(d => d.D_star > 0 && isFinite(d.D_star));
  }

  /* ---- Base lower branch (solid blue) ---- */
  const lowerData = shellData.lower_branch.L.map((L, i) => ({
    L, D_star: shellData.lower_branch.D_star[i],
  }));

  g.append("path")
    .datum(lowerData)
    .attr("class", "branch lower-branch")
    .attr("d", makeLine())
    .attr("fill", "none")
    .attr("stroke", "#2166ac")
    .attr("stroke-width", 2.2);

  /* ---- Base upper branch (dashed blue) ---- */
  const upperData = shellData.upper_branch.L.map((L, i) => ({
    L, D_star: shellData.upper_branch.D_star[i],
  }));

  g.append("path")
    .datum(upperData)
    .attr("class", "branch upper-branch")
    .attr("d", makeLine())
    .attr("fill", "none")
    .attr("stroke", "#2166ac")
    .attr("stroke-width", 2.2)
    .attr("stroke-dasharray", "6 4");

  /* ---- L_fold vertical line (base) ---- */
  const foldLineBase = g.append("line")
    .attr("class", "fold-line base-fold")
    .attr("x1", xScale(L_fold_base)).attr("x2", xScale(L_fold_base))
    .attr("y1", 0).attr("y2", H)
    .attr("stroke", "#D62828")
    .attr("stroke-width", 1.5)
    .attr("stroke-dasharray", "8 4");

  g.append("text")
    .attr("class", "fold-label")
    .attr("x", xScale(L_fold_base) + 4).attr("y", 12)
    .attr("fill", "#D62828")
    .attr("font-size", "10px")
    .text("Point of no return");

  /* ---- Real-world marker (orange star) ---- */
  const L_current = shellState.L_current;
  const D_current = shellState.D_current;

  const markerGroup = g.append("g").attr("class", "rw-marker");

  // Horizontal dashed guide line
  markerGroup.append("line")
    .attr("x1", 0).attr("x2", xScale(L_current))
    .attr("y1", yScale(Math.max(D_current, yMin))).attr("y2", yScale(Math.max(D_current, yMin)))
    .attr("stroke", "#E76F51").attr("stroke-width", 1).attr("stroke-dasharray", "3 3").attr("opacity", 0.6);

  // Vertical dashed guide line
  markerGroup.append("line")
    .attr("x1", xScale(L_current)).attr("x2", xScale(L_current))
    .attr("y1", yScale(Math.max(D_current, yMin))).attr("y2", H)
    .attr("stroke", "#E76F51").attr("stroke-width", 1).attr("stroke-dasharray", "3 3").attr("opacity", 0.6);

  // Star marker using a ★ text glyph
  markerGroup.append("text")
    .attr("x", xScale(L_current))
    .attr("y", yScale(Math.max(D_current, yMin)) + 6)
    .attr("text-anchor", "middle")
    .attr("font-size", "18px")
    .attr("fill", "#E76F51")
    .attr("class", "rw-star")
    .text("★");

  /* ---- Tooltip ---- */
  const tooltip = d3.select(container).select(".tooltip");
  // tooltip div is created by app.jsx; fall back to body if not present
  const tip = tooltip.empty()
    ? d3.select(document.body).append("div").attr("class", "tooltip")
    : tooltip;

  markerGroup.select(".rw-star")
    .style("cursor", "pointer")
    .on("mouseover", (event) => {
      const L_frac = shellState.L_fraction;
      const tl = shellState.traffic_light;
      tip.style("display", "block")
        .html(
          `<strong>Current state (2026)</strong><br>` +
          `L = ${L_current.toFixed(1)} obj/yr<br>` +
          `D = ${D_current.toLocaleString()} objects<br>` +
          `L / L<sub>fold</sub> = ${L_frac.toFixed(3)}<br>` +
          `Status: <span class="tl-${tl}">${tl.toUpperCase()}</span>`
        );
    })
    .on("mousemove", (event) => {
      tip.style("left", (event.pageX + 14) + "px")
         .style("top", (event.pageY - 28) + "px");
    })
    .on("mouseout", () => tip.style("display", "none"));

  /* ---- Overlay container (overlays drawn on top of base) ---- */
  const overlayGroup = g.append("g").attr("class", "overlays");
  const overlayMap = new Map(); // label → {path, foldLine}

  /* ---- Public API ---- */

  /**
   * Add a new what-if overlay curve.
   * scenarioData: the per-shell dict from /api/whatif response
   * (fields: L_fold_new, L_current_new, traffic_light, curve: [{L, D_star}])
   */
  function addOverlay(scenarioData, color, label) {
    const layer = overlayGroup.append("g").attr("class", "overlay-layer");

    // Curve
    if (scenarioData.curve && scenarioData.curve.length > 0) {
      layer.append("path")
        .datum(scenarioData.curve)
        .attr("class", "overlay-curve")
        .attr("d", makeLine())
        .attr("fill", "none")
        .attr("stroke", color)
        .attr("stroke-width", 2)
        .attr("opacity", 0.85);
    }

    // New L_fold line (if fold exists)
    if (scenarioData.L_fold_new != null) {
      layer.append("line")
        .attr("class", "overlay-fold-line")
        .attr("x1", xScale(scenarioData.L_fold_new)).attr("x2", xScale(scenarioData.L_fold_new))
        .attr("y1", 0).attr("y2", H)
        .attr("stroke", color)
        .attr("stroke-width", 1.2)
        .attr("stroke-dasharray", "6 3")
        .attr("opacity", 0.75);
    }

    // New L_current marker (vertical tick)
    const xNew = xScale(scenarioData.L_current_new);
    layer.append("line")
      .attr("class", "overlay-lcurrent")
      .attr("x1", xNew).attr("x2", xNew)
      .attr("y1", H - 8).attr("y2", H)
      .attr("stroke", color).attr("stroke-width", 2.5);

    overlayMap.set(label, layer);
  }

  function removeOverlay(label) {
    if (overlayMap.has(label)) {
      overlayMap.get(label).remove();
      overlayMap.delete(label);
    }
  }

  function clearOverlays() {
    overlayGroup.selectAll(".overlay-layer").remove();
    overlayMap.clear();
  }

  function updateTrafficLight(status) {
    tlCircle.attr("fill", TRAFFIC_COLORS[status] || "#888");
    tlLabel.text(status.toUpperCase());
  }

  return { addOverlay, removeOverlay, clearOverlays, updateTrafficLight };
}
