// Your County (v0.2.0; Scott chose A of notes/yp-front-A-desk-2026-10-22.png): three tiles, This Season So Far, and the
// county's yields since 2000 with the model's 80% ranges. Every number comes from /api/county (yieldpred/web/county.py),
// built from the same files as the Streamlit app. No HTML strings: every piece is built as an element, so a county name
// can never become markup.
"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const crop = params.get("crop") === "soybeans" ? "soybeans" : "corn";
  const EXAMPLE = "31079";                  // Hall County, Nebraska: the example before anyone picks
  const SVG = "http://www.w3.org/2000/svg";
  const KEY = "yp-county";
  let shown = null;                         // the county page on screen, for redrawing the chart on resize

  function el(tag, attrs = {}, ...kids) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v; else if (k === "text") node.textContent = v; else node.setAttribute(k, v);
    }
    for (const kid of kids) if (kid != null) node.append(kid);
    return node;
  }
  function svg(tag, attrs = {}, text) {
    const node = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text != null) node.textContent = text;
    return node;
  }
  const whole = (n) => Math.round(n).toLocaleString("en-US");
  const one = (n) => (Math.round(n * 10) / 10).toFixed(1);
  const remember = (fips) => { try { localStorage.setItem(KEY, fips); } catch { /* private window: fine */ } };
  const remembered = () => { try { return localStorage.getItem(KEY); } catch { return null; } };
  const valid = (f) => /^(31|19)\d{3}$/.test(f || "");
  function day(iso) {
    const d = new Date(`${iso}T12:00:00`);
    return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
  }

  // --- the tiles ---------------------------------------------------------------------------------------------------
  function tiles(p) {
    const box = el("div", { class: "tiles" });
    const last = p.last;
    if (last) {
      const where = last.low == null ? "The model has no range for this county."
        : last.inside ? `The model's range was ${whole(last.low)} to ${whole(last.high)}: it landed inside.`
        : `The model's range was ${whole(last.low)} to ${whole(last.high)}: it landed outside.`;
      const late = last.year < p.latest_year ? ` USDA published no ${p.latest_year} yield for this county.` : "";
      box.append(el("div", { class: "tile" }, el("p", { class: "k", text: `${last.year} harvest` }),
        el("p", { class: "v" }, `${whole(last.yield)} `, el("small", { text: p.unit })),
        el("p", { text: `${where} USDA, all ${p.crop_name.toLowerCase()}.${late}` })));
    }
    if (p.trend) {
      const t = p.trend;
      box.append(el("div", { class: "tile" }, el("p", { class: "k", text: `A trend year for ${t.year}` }),
        el("p", { class: "v" }, `${whole(t.value)} `, el("small", { text: p.unit })),
        el("p", { text: `The county's ${t.from} to ${t.to} trend (${t.slope >= 0 ? "+" : ""}${t.slope.toFixed(1)} bu a year), `
          + `not a forecast. USDA's ${t.year} county yields come out in February.` })));
    }
    if (p.record) {
      box.append(el("div", { class: "tile" }, el("p", { class: "k", text: "How often the range held" }),
        el("p", { class: "v" }, `${p.record.held} `, el("small", { text: `of ${p.record.years} years` })),
        el("p", { text: "Each range came from a model that never saw this part of the state. An honest 80% range misses "
          + "about 1 year in 5; red dots below are the misses." })));
    } else {
      box.append(el("div", { class: "tile" }, el("p", { class: "k", text: "The model's ranges" }),
        el("p", { class: "v", text: "None here" }),
        el("p", { text: "Some of the model's inputs are missing for this county (its crop rotation, for one), so it has no ranges here. The yields are still USDA's." })));
    }
    return box;
  }

  // --- this season so far -------------------------------------------------------------------------------------------
  function bars(title, rows, unit, scale, digits) {
    const box = el("div", {}, el("h4", { text: title }));
    for (const [label, value, now] of rows) {
      if (value == null) continue;
      const bar = el("i");
      bar.style.width = `${Math.max(2, (100 * value) / scale)}%`;
      box.append(el("div", { class: `bar${now ? " now" : ""}` }, el("span", { text: label }), bar,
        el("span", { text: `${digits ? one(value) : whole(value)}${unit}` })));
    }
    return box;
  }
  function season(p) {
    const s = p.season;
    const box = el("section", { class: "panel", "aria-labelledby": "season-title" });
    box.append(el("h3", { id: "season-title", text: s.complete ? `The ${s.season} Season` : "This Season So Far" }));
    box.append(el("p", { class: "sub", text: `${day(s.from).replace(/, \d{4}$/, "")} to ${day(s.through)}, ${p.county} County `
      + `weather (NASA POWER), beside a normal season (${s.normal_years[0]} to ${s.normal_years[1]}) and the two drought `
      + "years, all over the same days." }));
    const y12 = s.years["2012"] || {}, y22 = s.years["2022"] || {};
    const rows = (k) => [[String(s.season), s.now[k], true], ["Normal", s.normal[k], false], ["2012", y12[k], false],
      ["2022", y22[k], false]];
    const max = (k) => Math.max(...rows(k).map((r) => r[1] || 0)) * 1.05 || 1;
    const grid = el("div", { class: "cmp" }, bars("Rain", rows("rain_in"), " in", max("rain_in"), true),
      bars("Days over 90°F", rows("hot_days"), "", max("hot_days"), false));
    if (s.now.jul_rain_in != null) grid.append(bars("July rain", rows("jul_rain_in"), " in", max("jul_rain_in"), true));
    box.append(grid);
    if (p.season_words) box.append(el("p", { class: "say", text: p.season_words }));
    box.append(el("p", { class: "src", text: "Weather is the county's NASA POWER point, a few days behind. Rain since "
      + "May 1 isn't a yield forecast: irrigated fields and August weather matter too." }));
    return box;
  }

  // --- the yields chart ---------------------------------------------------------------------------------------------
  function chart(p, width) {
    const narrow = width < 520;
    const h = narrow ? 260 : 300, L = 40, R = 12, T = 14, B = 26;
    const pts = p.history.filter((r) => r.yield != null);
    const values = [...pts.map((r) => r.yield), ...pts.filter((r) => r.low != null).flatMap((r) => [r.low, r.high]),
      ...p.dryland.map((d) => d.yield)];
    const step = p.unit === "bu/acre" && Math.max(...values) > 100 ? 40 : 10;
    const lo = Math.max(0, Math.floor(Math.min(...values) / step) * step - step);
    const hi = Math.ceil(Math.max(...values) / step) * step;
    const x0 = 2000, x1 = Math.max(2025, ...pts.map((r) => r.year));
    const X = (y) => L + ((width - L - R) * (y - x0)) / (x1 - x0);
    const Y = (v) => T + ((h - T - B) * (hi - v)) / (hi - lo);
    const root = svg("svg", { viewBox: `0 0 ${width} ${h}`, role: "img",
      "aria-label": `${p.county} County ${p.crop_name.toLowerCase()} yields ${x0} to ${x1}, with the model's 80% ranges` });
    for (let v = lo; v <= hi; v += step) {
      root.append(svg("line", { x1: L, x2: width - R, y1: Y(v), y2: Y(v), stroke: "#ecebe6" }));
      root.append(svg("text", { x: L - 6, y: Y(v) + 4, "font-size": 12, "text-anchor": "end", fill: "#5e5c57" }, String(v)));
    }
    if (p.dryland.length > 1) {
      root.append(svg("polyline", { fill: "none", stroke: "#8a8f98", "stroke-width": 1.6, "stroke-dasharray": "5 4",
        points: p.dryland.map((d) => `${X(d.year).toFixed(1)},${Y(d.yield).toFixed(1)}`).join(" ") }));
    }
    const barW = narrow ? 5 : 7;
    for (const r of pts) {
      const cx = X(r.year);
      const tip = `${r.year}: ${whole(r.yield)} ${p.unit}` + (r.low != null ? ` (model's range ${whole(r.low)} to ${whole(r.high)})` : "");
      if (r.low != null) {
        root.append(svg("line", { x1: cx, x2: cx, y1: Y(r.high), y2: Y(r.low), stroke: "#2a78d6", "stroke-opacity": 0.35,
          "stroke-width": barW, "stroke-linecap": "round" }));
      }
      const dot = svg("circle", { cx, cy: Y(r.yield), r: narrow ? 3.4 : 4.2, fill: r.inside === false ? "#b4441c" : "#1d1c1a",
        stroke: "#fff", "stroke-width": 1.5 });
      dot.append(svg("title", {}, tip));
      root.append(dot);
      // a wider, invisible target for the hover title
      const hit = svg("rect", { x: cx - 8, y: T, width: 16, height: h - T - B, fill: "transparent" });
      hit.append(svg("title", {}, tip));
      root.append(hit);
    }
    for (const yr of [2012, 2022]) {
      const r = pts.find((q) => q.year === yr);
      if (!r) continue;
      const below = r.low != null ? Math.min(r.low, r.yield) : r.yield;
      root.append(svg("text", { x: X(yr), y: Y(below) + 18, "font-size": 12, "text-anchor": "middle", fill: "#3d3d3a" },
        yr === 2012 ? "2012 drought" : "2022"));
    }
    if (!narrow && p.dryland.length > 1) {
      const mid = p.dryland[Math.floor(p.dryland.length / 2)];
      root.append(svg("text", { x: X(mid.year), y: Y(mid.yield) + 20, "font-size": 12, "text-anchor": "middle", fill: "#3d3d3a" },
        `dryland (to ${p.dryland[p.dryland.length - 1].year})`));
    }
    if (!narrow) {
      for (const yr of p.missing_years) {
        root.append(svg("text", { x: X(yr), y: T + 12, "font-size": 11, "text-anchor": "middle", fill: "#8a8f98" }, `${yr}: none`));
      }
    }
    for (let yr = x0; yr <= x1; yr += narrow ? 10 : 5) {
      root.append(svg("text", { x: X(yr), y: h - 8, "font-size": 12, "text-anchor": "middle", fill: "#5e5c57" }, String(yr)));
    }
    return root;
  }

  function numbers(p) {
    const head = el("tr", {}, el("th", { text: "Year" }), el("th", { text: "Yield" }), el("th", { text: "Model's range" }),
      el("th", { text: "Inside?" }));
    const body = el("tbody");
    for (const r of [...p.history].reverse()) {
      body.append(el("tr", {}, el("td", { text: String(r.year) }), el("td", { text: one(r.yield) }),
        el("td", { text: r.low != null ? `${one(r.low)} to ${one(r.high)}` : "none" }),
        el("td", { text: r.inside == null ? "" : r.inside ? "Yes" : "No" })));
    }
    return el("details", { class: "numbers" }, el("summary", { text: "Show the Numbers" }),
      el("div", { class: "table-wrap" }, el("table", {}, el("thead", {}, head), body)));
  }

  function historyPanel(p) {
    const box = el("section", { class: "panel", "aria-labelledby": "hist-title" });
    const first = p.history[0]?.year, last = p.history[p.history.length - 1]?.year;
    box.append(el("h3", { id: "hist-title", text: `${p.county} County ${p.crop_name}, ${first} to ${last}` }));
    const missing = p.missing_years.length ? ` USDA didn't publish ${p.county} County's ${p.missing_years.join(", ")} yield.` : "";
    box.append(el("p", { class: "sub", text: "Dots: what the county yielded (USDA). Blue bars: the model's 80% range for that "
      + "year, from its weather, soils and irrigation, by a model that never saw this part of the state." + missing }));
    const holder = el("div", { class: "chart", id: "chart" });
    box.append(holder);
    const key = el("p", { class: "key" }, el("span", {}, el("i", { class: "k-dot" }), "yield, inside the range"),
      el("span", {}, el("i", { class: "k-miss" }), "outside it"), el("span", {}, el("i", { class: "k-bar" }), "the model's 80% range"));
    if (p.dryland.length > 1) key.append(el("span", {}, el("i", { class: "k-dry" }), `dryland ${p.crop_name.toLowerCase()} (USDA stopped after ${p.dryland[p.dryland.length - 1].year})`));
    box.append(key, numbers(p));
    box.append(el("p", { class: "src", text: "USDA NASS county yields. How the model was built and tested: Learn, How We Test." }));
    return box;
  }
  function drawChart() {
    const holder = $("chart");
    if (!holder || !shown) return;
    holder.replaceChildren(chart(shown, Math.max(300, Math.round(holder.clientWidth))));
  }

  // --- the page -------------------------------------------------------------------------------------------------------
  function render(p, from) {
    shown = p;
    document.title = `${p.county} County, ${p.state} · Yield Predictor`;
    $("county-name").textContent = `${p.county} County, ${p.state}`;
    $("county-from").textContent = from;
    const page = $("page");
    page.replaceChildren(tiles(p));
    const s = p.season ? season(p) : null;
    if (s) page.append(s);
    else page.append(el("p", { class: "note", text: p.state_code === "ia" ? "This season's weather comes to Iowa counties next."
      : "This season's weather starts on May 1." }));
    page.append(historyPanel(p));
    drawChart();
    window.ypStreamlitLinks?.(window.ypStreamlitBase || "", p.state_code);
  }

  async function load(fips, from) {
    const r = await fetch(`/api/county/${encodeURIComponent(fips)}?crop=${crop}`);
    if (!r.ok) {
      const why = (await r.json().catch(() => ({}))).detail || "That county couldn't be shown.";
      if (fips !== EXAMPLE) return load(EXAMPLE, `${why} Showing Hall County, Nebraska, as an example.`);
      $("page").replaceChildren(el("p", { class: "note", text: why }));
      return;
    }
    render(await r.json(), from);
    pickState(fips.startsWith("19") ? "ia" : "ne", fips);
  }

  async function pickState(state, selected) {
    $("state-select").value = state;
    const r = await fetch(`/api/counties?state=${state}&crop=${crop}`);
    const list = r.ok ? (await r.json()).counties : [];
    $("county-select").replaceChildren(...list.map((c) => {
      const o = el("option", { value: c.fips, text: `${c.name} County` });
      if (c.fips === selected) o.selected = true;
      return o;
    }));
  }

  document.addEventListener("DOMContentLoaded", async () => {
    // The crop switch keeps the county; the county keeps the crop.
    for (const a of document.querySelectorAll(".crop-switch a")) {
      a.setAttribute("aria-current", String(a.dataset.crop === crop));
      a.addEventListener("click", (e) => {
        e.preventDefault();
        const q = new URLSearchParams(location.search);
        if (a.dataset.crop === "corn") q.delete("crop"); else q.set("crop", a.dataset.crop);
        location.search = q.toString();
      });
    }
    const why = params.get("why");
    if (why) { $("why").textContent = why; $("why").classList.remove("hidden"); }
    $("change").addEventListener("click", () => $("pick-form").classList.toggle("open"));
    $("state-select").addEventListener("change", (e) => pickState(e.target.value, null));
    $("pick-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const fips = $("county-select").value;
      if (!valid(fips)) return;
      remember(fips);
      const q = new URLSearchParams(location.search);
      q.set("county", fips);
      q.delete("why");
      history.replaceState(null, "", `?${q}`);
      $("pick-form").classList.remove("open");
      load(fips, "Your county, remembered in this browser");
    });
    let timer;
    window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(drawChart, 150); });

    const status = await window.ypStatus;
    window.ypStreamlitBase = (status.streamlit_url || "").replace(/\/$/, "");
    const place = status.user?.place;
    const asked = params.get("county");
    if (valid(asked)) return load(asked, place?.fips === asked ? "Your county, from My Farm" : "");
    if (place && valid(place.fips)) return load(place.fips, "Your county, from My Farm");
    const kept = remembered();
    if (valid(kept)) return load(kept, "Your county, remembered in this browser");
    $("pick-form").classList.add("open");
    return load(EXAMPLE, "An example: pick your county below");
  });
})();
