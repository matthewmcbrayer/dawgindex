/* DAWG Lab page script. Reads the case data embedded in the page (#lab-data). No framework, no network.
   Team selection precedence: ?team= in the link, then the team remembered from an earlier visit, then none.
   A ?team= link opens that team's panel directly; Back closes it. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var STORE = "dawg-lab-team";
  var el = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var fmt = function (v) { var m = Math.abs(v).toFixed(1); return (m === "0.0" ? "" : v > 0 ? "+" : "−") + m; };  /* rounds like lab.py; no "−0.0" */
  var store = {
    get: function () { try { return window.localStorage.getItem(STORE); } catch (e) { return null; } },
    set: function (v) { try { window.localStorage.setItem(STORE, v); } catch (e) {} }
  };
  var dataNode = el("lab-data");
  if (!dataNode) return;
  var D = JSON.parse(dataNode.textContent);
  var T = D.teams || {};

  /* ------------------------------------------------------------ svg helpers */
  function svg(w, h, label) {
    var s = document.createElementNS(NS, "svg");
    s.setAttribute("viewBox", "0 0 " + w + " " + h); s.setAttribute("width", w); s.setAttribute("height", h);
    s.setAttribute("class", "lb-chart"); s.setAttribute("role", "img"); s.setAttribute("aria-label", label);
    return s;
  }
  function add(p, tag, attrs, text) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (text != null) n.textContent = text;
    p.appendChild(n); return n;
  }
  function width(node, fallback) {
    var w = node.clientWidth || 0;
    try { var cs = getComputedStyle(node); w -= (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0); } catch (e) {}
    w = Math.floor(w); return w > 40 ? w : fallback;
  }

  /* ------------------------------------------------------------ chart 1: carryover estimates (the verdict's evidence) */
  function drawPersistence(node, rows, opt) {
    opt = opt || {};
    rows = opt.compact ? rows.filter(function (r) { return r.card; }) : rows;
    var W = width(node, 700), mid = !!opt.mid, narrow = mid || W < 560, big = !!opt.big && !mid;
    var longest = Math.max.apply(null, rows.map(function (r) { return r.label.length; }));
    var fs = big ? 26 : mid ? 17 : narrow ? Math.max(10, Math.min(12, Math.floor((W - 24) / (longest * 0.61)))) : 13, lw = narrow ? 0 : Math.min(big ? 460 : 350, Math.round(W * 0.44));
    var rowH = big ? 70 : mid ? 62 : narrow ? 46 : 30, gh = opt.compact ? 0 : (big ? 52 : 30), top = big ? 56 : 40, bot = big ? 80 : 60;
    var groups = 0; rows.forEach(function (r, i) { if (!opt.compact && r.group && (i === 0 || rows[i - 1].group !== r.group)) groups++; });
    var H = top + bot + rowH * rows.length + gh * groups;
    if (opt.fit) { node.innerHTML = ""; var ch = node.clientHeight; if (ch > 120) { rowH = Math.max(40, Math.floor((ch - top - bot - gh * groups) / rows.length)); H = top + bot + rowH * rows.length + gh * groups; } }
    /* the axis stays readable: estimates beyond −12 / +8 are drawn at the edge with an arrow and their value */
    var lo = Math.min.apply(null, rows.map(function (r) { return r.T - r.SE; }).concat([-4])), hi = Math.max.apply(null, rows.map(function (r) { return r.T + r.SE; }).concat([4]));
    var step = 4; lo = Math.max(-12, Math.floor(lo / step) * step); hi = Math.min(8, Math.ceil(hi / step) * step);
    var x0 = lw + (narrow ? 8 : 16), x1 = W - (big ? 24 : 12);
    var X = function (v) { return x0 + (Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo) * (x1 - x0); };
    var s = svg(W, H, "Carryover estimates: " + rows.map(function (r) { return r.label + " " + fmt(r.T); }).join("; "));
    add(s, "rect", { x: X(0), y: top - 6, width: x1 - X(0), height: H - top - bot + 12, fill: "#EADFC4" });
    add(s, "text", { x: x1 - 4, y: top - 12, "text-anchor": "end", style: "font-size:" + fs + "px;fill:#6E6557" }, narrow && !big ? "a lasting pattern →" : "a lasting pattern would land here →");
    for (var v = lo; v <= hi; v += step) {
      add(s, "line", { x1: X(v), y1: H - bot + 4, x2: X(v), y2: H - bot + 10, stroke: "#6E6557" });
      add(s, "text", { x: X(v), y: H - bot + (big ? 38 : 24), "text-anchor": "middle", style: "font-size:" + fs + "px;fill:#6E6557" }, (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v));
    }
    add(s, "line", { x1: X(0), y1: top - 6, x2: X(0), y2: H - bot + 6, stroke: "#131210", "stroke-width": big ? 4 : 2 });
    add(s, "text", { x: x1, y: H - 8, "text-anchor": "end", style: "font-size:" + fs + "px" }, narrow && !big ? "← flips · carryover estimate · repeats →" : "← flips from season to season · carryover estimate · repeats →");
    var y = top;
    rows.forEach(function (r, i) {
      if (!opt.compact && r.group && (i === 0 || rows[i - 1].group !== r.group)) {
        add(s, "text", { x: 0, y: y + gh - (big ? 14 : 9), style: "font-size:" + (big ? 20 : 11) + "px;letter-spacing:.1em;fill:#6E6557;text-transform:uppercase" }, r.group.toUpperCase());
        y += gh;
      }
      var yc = y + (narrow && !big ? rowH * 0.66 : rowH / 2), col = r.primary ? "#D13A2F" : "#131210", out = r.T < lo || r.T > hi;
      /* rows that use 2014–18 research grades carry the research ring (same mark as the note under the chart) */
      var ly = narrow && !big ? y + fs + 1 : yc + fs * 0.36, rr = big ? 9 : 5, lx = rr * 2 + (big ? 10 : 6);
      if (r.includes_research) add(s, "circle", { cx: rr + 1, cy: ly - fs * 0.36, r: rr, fill: "#F4EAD2", stroke: "#131210", "stroke-width": big ? 3 : 2 });
      if (narrow && !big) add(s, "text", { x: lx, y: ly, style: "font-size:" + fs + "px;font-weight:" + (r.primary ? 700 : 500) + ";fill:#131210;paint-order:stroke;stroke:#FBF4E2;stroke-width:4px;stroke-linejoin:round" }, r.label);
      else add(s, "text", { x: lx, y: ly, style: "font-size:" + fs + "px;font-weight:" + (r.primary ? 700 : 500) + ";fill:#131210" }, r.label);
      var a = X(r.T - r.SE), b = X(r.T + r.SE);
      add(s, "line", { x1: a, y1: yc, x2: b, y2: yc, stroke: col, "stroke-width": big ? 5 : 2.5 });
      if (r.T - r.SE < lo) add(s, "path", { d: "M" + (a + 8) + " " + (yc - 6) + "L" + a + " " + yc + "L" + (a + 8) + " " + (yc + 6), fill: "none", stroke: col, "stroke-width": 2.5 });
      if (r.T + r.SE > hi) add(s, "path", { d: "M" + (b - 8) + " " + (yc - 6) + "L" + b + " " + yc + "L" + (b - 8) + " " + (yc + 6), fill: "none", stroke: col, "stroke-width": 2.5 });
      if (out) add(s, "circle", { cx: X(r.T), cy: yc, r: big ? 14 : 5.5, fill: "#FBF4E2", stroke: col, "stroke-width": 2.5 });
      else add(s, "circle", { cx: X(r.T), cy: yc, r: big ? 14 : r.primary ? 7 : 5.5, fill: col, stroke: "#FBF4E2", "stroke-width": 2 });
      if (!narrow || big) add(s, "text", { x: X(r.T) + (out ? 10 : 0), y: yc - (big ? 22 : 10), "text-anchor": out ? "start" : "middle", style: "font-size:" + (big ? 24 : 11) + "px;font-weight:600;fill:" + col }, fmt(r.T) + (out ? " (off the scale)" : ""));
      else {
        /* phones: the value sits beside its bar (right of it when there's room, else left, else on the dot) */
        var vt = fmt(r.T) + (out ? " (off scale)" : ""), vw = vt.length * fs * 0.62, vx, va;
        if (b + 6 + vw <= x1 && r.T + r.SE <= hi) { vx = b + 6; va = "start"; }
        else if (a - 6 - vw >= 0 && r.T - r.SE >= lo) { vx = a - 6; va = "end"; }
        else { vx = X(r.T) + (out ? 10 : 9); va = "start"; }
        add(s, "text", { x: vx, y: yc + fs * 0.36 - (vx === X(r.T) + 9 ? 9 : 0), "text-anchor": va, style: "font-size:" + fs + "px;font-weight:700;fill:" + col + ";paint-order:stroke;stroke:#FBF4E2;stroke-width:4px;stroke-linejoin:round" }, vt);
      }
      y += rowH;
    });
    node.innerHTML = ""; node.appendChild(s);
  }

  /* ------------------------------------------------------------ chart 2: all 68 programs against their expected ranges */
  function drawPrograms(node, teams, current, onPick) {
    var list = Object.keys(teams).map(function (k) { return teams[k]; });
    var W = width(node, 700), narrow = W < 560, lw = narrow ? 104 : 150, vw = narrow ? 40 : 52, rowH = narrow ? 22 : 19, top = 26, bot = 26;
    var H = top + bot + rowH * list.length;
    var mx = 4; list.forEach(function (t) { if (t.state === "none") return; mx = Math.max(mx, Math.abs(t.raw), t.state === "ok" ? Math.max(Math.abs(t.range_lo), Math.abs(t.range_hi)) : 0); });
    mx = Math.ceil(mx / 2) * 2;
    var x0 = lw, x1 = W - vw, X = function (v) { return x0 + (v + mx) / (2 * mx) * (x1 - x0); };
    var s = svg(W, H, "All 68 programs: big-favorite gap and expected range");
    var ticks = function (y, below) { for (var v = -mx; v <= mx; v += mx / 2) add(s, "text", { x: X(v), y: y, "text-anchor": "middle", style: "font-size:11px;fill:#6E6557" }, (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v)); };
    ticks(14); ticks(H - 8);
    add(s, "line", { x1: X(0), y1: top - 4, x2: X(0), y2: H - bot + 4, stroke: "#131210", "stroke-opacity": 0.5 });
    list.forEach(function (t, i) {
      var y = top + i * rowH + rowH / 2, sel = t.slug === current;
      if (sel) add(s, "rect", { x: 0, y: y - rowH / 2, width: W, height: rowH, fill: "#F2D9C9" });
      add(s, "text", { x: 0, y: y + 4, style: "font-size:" + (narrow ? 12 : 12.5) + "px;font-weight:" + (sel ? 700 : 500) + ";fill:#131210" }, t.name);
      if (t.state === "ok") {
        add(s, "rect", { x: X(t.range_lo), y: y - 4, width: X(t.range_hi) - X(t.range_lo), height: 8, fill: "#EADFC4", stroke: "#B8AD98" });
        add(s, "circle", { cx: X(t.raw), cy: y, r: sel ? 6 : 4.5, fill: t.inside ? "#FBF4E2" : (sel ? "#D13A2F" : "#131210"), stroke: sel ? "#D13A2F" : "#131210", "stroke-width": 2 });
      } else if (t.state === "below") {
        add(s, "circle", { cx: X(t.raw), cy: y, r: 4, fill: "#B8AD98" });
      }
      add(s, "text", { x: W, y: y + 4, "text-anchor": "end", style: "font-size:12px;fill:" + (sel ? "#C2342A" : "#3B362E") + ";font-weight:" + (sel ? 700 : 500) }, t.state === "none" ? "—" : fmt(t.raw));
    });
    node.innerHTML = ""; node.appendChild(s);
    if (onPick) s.addEventListener("click", function (ev) {
      var r = s.getBoundingClientRect(), i = Math.floor((ev.clientY - r.top - top) / rowH);
      if (i >= 0 && i < list.length) onPick(list[i].slug);
    });
  }

  /* ------------------------------------------------------------ chart 3: team vs its expected range */
  function drawStrip(node, t, opt) {
    opt = opt || {};
    var big = !!opt.big, xl = !!opt.xl, W = width(node, big ? 900 : 520), H = xl ? 220 : big ? 150 : 100, pad = big ? 10 : 6, y = xl ? 104 : big ? 76 : 44;
    var ext = Math.abs(t.raw); if (t.state === "ok") ext = Math.max(ext, Math.abs(t.range_lo), Math.abs(t.range_hi));
    var span = Math.max(10, Math.ceil(ext + 2));
    var X = function (v) { return pad + (v + span) / (2 * span) * (W - 2 * pad); };
    var fs = xl ? 30 : big ? 22 : 12;
    var s = svg(W, H, t.name + ": " + fmt(t.raw) + " points" + (t.state === "ok" ? ", expected range " + fmt(t.range_lo) + " to " + fmt(t.range_hi) : ""));
    if (t.state === "ok") add(s, "rect", { x: X(t.range_lo), y: y - (big ? 26 : 14), width: X(t.range_hi) - X(t.range_lo), height: big ? 52 : 28, fill: "#EADFC4", stroke: "#6E6557", "stroke-width": big ? 2.5 : 1.5, "stroke-dasharray": "5 4" });
    add(s, "line", { x1: pad, y1: y, x2: W - pad, y2: y, stroke: "#131210", "stroke-width": big ? 3 : 2 });
    add(s, "line", { x1: X(0), y1: y - (big ? 34 : 20), x2: X(0), y2: y + (big ? 34 : 20), stroke: "#131210", "stroke-width": big ? 3 : 2 });
    add(s, "circle", { cx: X(t.raw), cy: y, r: xl ? 24 : big ? 19 : 10, fill: "#D13A2F", stroke: "#FBF4E2", "stroke-width": big ? 5 : 3 });
    add(s, "text", { x: X(t.raw), y: y - (xl ? 40 : big ? 32 : 18), "text-anchor": "middle", style: "font-family:var(--cond),'Barlow Condensed',sans-serif;font-weight:800;font-size:" + (xl ? 56 : big ? 30 : 15) + "px;fill:#C2342A" }, fmt(t.raw));
    if (t.state === "ok") add(s, "text", { x: (X(t.range_lo) + X(t.range_hi)) / 2, "text-anchor": "middle", y: y + (xl ? 62 : big ? 50 : 33), style: "font-size:" + (xl ? 26 : big ? 18 : 11) + "px;fill:#6E6557" }, "expected range");
    add(s, "text", { x: pad, y: H - 4, style: "font-size:" + fs + "px" }, "worse as a big favorite");
    add(s, "text", { x: W - pad, y: H - 4, "text-anchor": "end", style: "font-size:" + fs + "px" }, "better");
    node.innerHTML = ""; node.appendChild(s);
  }

  /* ------------------------------------------------------------ chart 4: four groups */
  function drawGroups(node, t, league) {
    var W = width(node, 520), narrow = W < 460, lw = narrow ? 112 : 150, vw = 70, rowH = 46, H = rowH * t.groups.length + 30;
    var all = t.groups.filter(function (g) { return g.avg != null; }).map(function (g) { return Math.abs(g.avg); }).concat(league.map(function (g) { return Math.abs(g.avg); }));
    var mx = Math.max(4, Math.ceil(Math.max.apply(null, all) + 1));
    var x0 = lw, x1 = W - vw, mid = (x0 + x1) / 2, sc = function (v) { return v / mx * (x1 - x0) / 2; };
    var s = svg(W, H, "Average DAWG grade by kind of game, " + t.name + " vs all programs");
    add(s, "rect", { x: 0, y: 2, width: 12, height: 8, fill: "#B8AD98" }); add(s, "text", { x: 16, y: 10 }, "All programs");
    add(s, "rect", { x: 120, y: 2, width: 12, height: 8, fill: "#D13A2F" }); add(s, "text", { x: 136, y: 10 }, t.name);
    t.groups.forEach(function (g, i) {
      var y = 26 + i * rowH, lg = league[i] || { avg: 0 };
      add(s, "text", { x: 0, y: y + 19, style: "font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:15px;fill:#131210;text-transform:uppercase" }, g.label);
      add(s, "line", { x1: mid, y1: y, x2: mid, y2: y + 30, stroke: "#131210", "stroke-width": 1.5 });
      var a = sc(lg.avg); add(s, "rect", { x: Math.min(mid, mid + a), y: y + 2, width: Math.max(1.5, Math.abs(a)), height: 8, fill: "#B8AD98" });
      if (g.avg != null) { var b = sc(g.avg); add(s, "rect", { x: Math.min(mid, mid + b), y: y + 13, width: Math.max(1.5, Math.abs(b)), height: 14, fill: "#D13A2F" }); }
      add(s, "text", { x: W, y: y + 18, "text-anchor": "end", style: "fill:#131210" }, (g.avg == null ? "—" : fmt(g.avg)) + " · " + g.n + " g");
    });
    node.innerHTML = ""; node.appendChild(s);
  }

  var LAB = window.DAWGLab = { drawPersistence: drawPersistence, drawPrograms: drawPrograms, drawStrip: drawStrip, drawGroups: drawGroups, data: D };

  /* ------------------------------------------------------------ share-card mode: draw and stop */
  if (document.body.getAttribute("data-mode") === "card") {
    [].forEach.call(document.querySelectorAll("[data-chart]"), function (n) {
      var k = n.getAttribute("data-chart"), t = T[n.getAttribute("data-team")];
      if (k === "strip" && t) drawStrip(n, t, { big: true, xl: n.getAttribute("data-size") === "xl" });
      if (k === "persistence") drawPersistence(n, D.persistence, { compact: true, big: n.getAttribute("data-size") !== "m", mid: n.getAttribute("data-size") === "m" });
    });
    document.body.setAttribute("data-ready", "1");
    return;
  }

  /* ------------------------------------------------------------ Lab homepage */
  var homePick = el("lb-home-pick");
  if (homePick) {
    var line = el("lb-home-line"), link = el("lb-home-link"), ans = el("lb-home-ans"), hrn = el("lb-home-rn");
    var line0 = line.textContent, ans0 = ans.textContent, link0 = link.textContent;
    var setHome = function (slug) {
      var t = T[slug];
      homePick.value = t ? slug : "";
      if (!t) { ans.textContent = ans0; line.textContent = line0; link.href = D.case.url; link.textContent = link0; hrn.hidden = true; return; }
      ans.textContent = t.answer; line.textContent = t.sentence;
      link.href = D.case.url + "?team=" + slug; link.textContent = "See " + t.name + "’s result →";
      hrn.hidden = !t.research_text; hrn.querySelector("span").textContent = t.research_short ? t.research_short.replace(/^incl\. /, "Includes ") + ", not official DAWG grades" : "";
    };
    var first = store.get(); setHome(T[first] ? first : null);
    homePick.addEventListener("change", function () { if (homePick.value) store.set(homePick.value); setHome(homePick.value); });
    var ex = el("lb-home-ex"); if (ex && D.persistence) { var dr = function () { drawPersistence(ex, D.persistence, { compact: true }); }; dr(); window.addEventListener("resize", dr); }
    document.body.setAttribute("data-ready", "1");
    return;
  }

  /* ------------------------------------------------------------ case page */
  var pick = el("lb-pick"), panel = el("lb-panel"), scrim = el("lb-scrim"), pin = el("lb-pin"), side = el("lb-side");
  if (!pick || !panel) return;
  var current = null, panelOpen = false;

  function teamUrl(slug) { var u = new URL(window.location.href); if (slug) u.searchParams.set("team", slug); else u.searchParams.delete("team"); return u.pathname + u.search + u.hash; }

  /* research-only values: the label, how many games it covers, and a link to the provenance in the receipts */
  function rnote(t, text) {
    if (!t.has_research) return "";
    return '<div class="lb-research-note"><i></i><span>' + esc(text || t.research_text) + ' <a href="#lb-receipts" data-goto>How they were made</a></span></div>';
  }

  function renderStrip() {
    var res = el("lb-strip-res"), t = T[current];
    var openB = el("lb-open-panel"), shareB = el("lb-share");
    if (!t) { res.innerHTML = "<b>Pick a team to see what happened for it.</b><span>Every chart on the page will highlight it.</span>"; openB.hidden = true; shareB.hidden = true; return; }
    res.innerHTML = "<b>" + esc(t.sentence) + "</b><span>" + esc(t.band_text) + "</span>" +
      (t.has_research ? '<span class="lb-res-rn"><i aria-hidden="true"></i>' + esc(t.research_text) + "</span>" : "");
    openB.hidden = false; openB.textContent = t.name + "’s full breakdown →";
    shareB.hidden = !t.card;
  }

  function renderSide() {
    var t = T[current]; if (!side) return;
    if (!t) { side.hidden = true; return; }
    el("lb-side-name").textContent = t.name;
    el("lb-side-val").textContent = t.state === "none" ? "—" : fmt(t.raw);
    el("lb-side-txt").textContent = t.short;
    el("lb-side-n").textContent = t.state === "none" ? "No qualifying games" : t.hf_games + " games · " + t.seasons + " seasons · what happened, not a verdict" + (t.research_short ? " · " + t.research_short : "");
  }

  function renderPanel() {
    var t = T[current]; if (!t) return;
    el("lb-p-name").textContent = t.name;
    el("lb-p-q").textContent = t.answer;
    var logo = el("lb-p-logo"); if (t.id) { logo.src = "/logos/" + t.id + "-dark.png"; logo.onerror = function () { this.onerror = null; this.src = "/logos/" + t.id + ".png"; }; logo.hidden = false; } else logo.hidden = true;
    el("lb-p-pick").value = current;
    var b = el("lb-p-body"), H = [];
    if (t.finding) {
      H.push('<section class="lb-sec lb-finding"><span class="lb-desc-tag">Team finding · supported by the research</span><p class="lb-lead">' + esc(t.finding.text) + '</p><span class="lb-note">' + esc(t.finding.receipts || "") + "</span></section>");
    }
    H.push('<section class="lb-sec"><span class="lb-label">1 · What happened for ' + esc(t.name) + '</span><p class="lb-lead">' + esc(t.sentence) + "</p>" +
      (t.state === "none" ? "" : "<span>" + esc(t.band_text) + "</span>") + '<span class="lb-desc-tag">What happened · not a verdict on ' + esc(t.name) + "</span>" +
      (t.has_research ? '<div class="lb-exhibit lb-rn-box">' + rnote(t) + "</div>" : "") + "</section>");
    if (t.state === "none") {
      H.push('<section class="lb-sec"><div class="lb-insuff">' + esc(t.none_text) + '</div><a class="lb-btn" href="#lb-programs-sec" data-goto>See all 68 programs</a></section>');
    } else {
      var rg = t.state === "ok" ? fmt(t.range_lo) + " to " + fmt(t.range_hi) : "";
      H.push('<section class="lb-sec"><span class="lb-label">2 · ' + esc(t.name) + " vs. its expected range</span>" +
        '<div class="lb-exhibit"><div id="lb-p-strip" style="padding:10px 12px 4px"></div>' +
        (t.state === "ok" ? '<div class="lb-ex-foot">Expected range: where this program’s gap would usually land if it had no lasting tendency, under our simulation assumptions ' +
            "(same-season, same-spread grades from other programs; no carryover between seasons). For " + esc(t.name) + ": " + rg + ", a " + esc(t.coverage) + "% range.</div>"
          : '<div class="lb-ex-foot">Gap only. Below the display minimum there’s no expected range.</div>') +
        rnote(t) + "</div></section>");
      H.push('<section class="lb-sec"><span class="lb-label">3 · Each kind of game</span><div class="lb-exhibit"><div id="lb-p-groups" style="padding:12px"></div>' +
        '<div class="lb-ex-foot">Average DAWG grade in each kind of game, with the number of games. All programs average about 0 in every kind of game by construction.</div>' +
        rnote(t, "Includes " + t.research_short.replace(/^incl\. /, "") + ", not official DAWG grades.") + "</div></section>");
      H.push('<section class="lb-sec"><span class="lb-label">4 · Where the gap comes from</span><div class="lb-three">' +
        "<div><span class=\"lb-label\">Down part</span><b>" + fmt(t.down) + "</b><small>as a 14+ point favorite vs. its 3.5–13.5-point-favorite and within-3 games</small></div>" +
        "<div><span class=\"lb-label\">Up part</span><b>" + fmt(t.up) + "</b><small>its 3.5+ underdog games vs. those same games, weighted by how often it was an underdog</small></div>" +
        "<div><span class=\"lb-label\">Gap</span><b style=\"color:#C2342A\">" + fmt(t.raw) + "</b><small>down part minus up part</small></div></div>" +
        (t.has_research ? '<div class="lb-exhibit lb-rn-box">' + rnote(t) + "</div>" : "") +
        '<span class="lb-note">Official grades only (2019–26): ' + (t.official.hf_games ? fmt(t.official.raw) + " over " + t.official.hf_games + " games " + esc(D.range.measure) : "no games " + esc(D.range.measure)) + ".</span></section>");
      H.push('<section class="lb-sec"><span class="lb-label">5 · Sample and uncertainty</span><div class="lb-three">' +
        "<div><span class=\"lb-label\">Gap</span><b style=\"color:#C2342A\">" + fmt(t.raw) + "</b><small>what happened</small></div>" +
        (t.state === "ok" ? "<div><span class=\"lb-label\">Expected range</span><b>" + rg + "</b><small>" + (t.inside ? "inside the range" : "outside: about " + Math.round(68 * (100 - parseFloat(D.range.coverage)) / 100) + " of 68 land outside by chance alone") + "</small></div>"
          : "<div><span class=\"lb-label\">Expected range</span><b>—</b><small>not shown below the minimum</small></div>") +
        "<div><span class=\"lb-label\">Sample</span><b>" + t.hf_games + "</b><small>" + esc(t.n_label) + "; " + t.other_games + " other games; " + t.seasons + " seasons (" + t.eligible_seasons + " eligible)" +
        (t.research_games ? "; " + t.research_games + " games use research grades" : "") + "</small></div></div></section>");
    }
    b.innerHTML = H.join("");
    [].forEach.call(b.querySelectorAll("[data-goto]"), function (a) {
      a.addEventListener("click", function (ev) {
        ev.preventDefault(); var id = a.getAttribute("href").slice(1); closePanel();
        setTimeout(function () { var n = el(id); if (n) n.scrollIntoView({ block: "start" }); }, 80);
      });
    });
    if (t.state !== "none") { drawStrip(el("lb-p-strip"), t, {}); drawGroups(el("lb-p-groups"), t, D.league.groups); }
    el("lb-p-share").hidden = !t.card;
    el("lb-p-team").href = "/" + current + "/"; el("lb-p-team").textContent = t.name + " team page";
  }

  /* the program table: alphabetical by default; any column sorts (a reading aid, not a ranking) */
  function initSort(tbl) {
    var heads = tbl.querySelectorAll("thead th");
    Array.prototype.forEach.call(heads, function (h, i) {
      var b = h.querySelector("button"); if (!b) return;
      b.addEventListener("click", function () {
        var dir = h.getAttribute("aria-sort") === "ascending" ? "descending" : "ascending";
        Array.prototype.forEach.call(heads, function (x) { x.removeAttribute("aria-sort"); });
        h.setAttribute("aria-sort", dir);
        var txt = h.getAttribute("data-k") === "s", tb = tbl.tBodies[0], rows = Array.prototype.slice.call(tb.rows);
        rows.sort(function (r1, r2) {
          var a = r1.cells[i].getAttribute("data-v"), b2 = r2.cells[i].getAttribute("data-v"), c;
          if (txt) c = a.localeCompare(b2);
          else { if (a === "" && b2 === "") c = 0; else if (a === "") return 1; else if (b2 === "") return -1; else c = parseFloat(a) - parseFloat(b2); }
          if (!c) c = r1.cells[0].getAttribute("data-v").localeCompare(r2.cells[0].getAttribute("data-v"));
          return dir === "ascending" ? c : -c;
        });
        rows.forEach(function (r) { tb.appendChild(r); });
      });
    });
  }
  var progTbl = el("lb-prog-tbl"); if (progTbl) initSort(progTbl);

  function drawAll() {
    if (progTbl) Array.prototype.forEach.call(progTbl.tBodies[0].rows, function (r) { r.classList.toggle("lb-on", r.getAttribute("data-team") === current); });
    var ps = el("lb-persist"); if (ps) drawPersistence(ps, D.persistence, {});
    var pg = el("lb-programs"); if (pg) drawPrograms(pg, T, current, function (slug) { setTeam(slug); });
    var hs = el("lb-home-strip"); if (hs && T[current]) drawStrip(hs, T[current], {});
  }

  function setTeam(slug, how) {
    if (!T[slug]) slug = null;
    current = slug; pick.value = slug || "";
    if (slug) store.set(slug);
    if (how !== "load") history.replaceState(history.state, "", teamUrl(slug));
    renderStrip(); renderSide(); drawAll(); updatePin();
    if (panelOpen && slug) renderPanel();
  }

  function openPanel(push) {
    if (!T[current]) return;
    renderPanel(); panel.hidden = false; if (scrim) scrim.hidden = false; panelOpen = true;
    document.documentElement.style.overflow = "hidden";
    if (push) history.pushState({ lbPanel: true }, "", teamUrl(current));
    try { var hn = el("lb-p-name"); hn.setAttribute("tabindex", "-1"); hn.focus({ preventScroll: true }); } catch (e) {}
    updatePin();
  }
  function hidePanel() { panel.hidden = true; if (scrim) scrim.hidden = true; panelOpen = false; document.documentElement.style.overflow = ""; updatePin(); }
  function closePanel() { if (history.state && history.state.lbPanel) history.back(); else hidePanel(); }
  window.addEventListener("popstate", function (e) { if (panelOpen && !(e.state && e.state.lbPanel)) hidePanel(); else if (!panelOpen && e.state && e.state.lbPanel) openPanel(false); });

  /* pinned bar (phones) and side card (desktop) appear only once the team strip is out of view */
  var stripVisible = true;
  function updatePin() {
    var t = T[current];
    var show = !!t && !stripVisible && !panelOpen;
    if (pin) {
      pin.hidden = !show;
      document.body.classList.toggle("lb-has-pin", show);
      if (t) {
        el("lb-pin-n").textContent = t.name; el("lb-pin-v").textContent = t.state === "none" ? "—" : fmt(t.raw);
        el("lb-pin-t").innerHTML = esc(t.pin) + (t.research_short ? '<small><i aria-hidden="true"></i>' + esc(t.research_short) + "</small>" : "");
      }
    }
    if (side) side.hidden = !t || stripVisible;
  }
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (en) { stripVisible = en[0].isIntersecting; updatePin(); }, { threshold: 0 }).observe(el("lb-strip"));
  }

  /* share: the system share sheet with the team's short link (its preview shows the team card); else open the card image */
  function share() {
    var t = T[current]; if (!t || !t.card) return;
    var data = { title: t.short, text: t.short, url: t.share };
    if (navigator.share) { navigator.share(data).catch(function () {}); return; }
    window.open(t.card_png, "_blank", "noopener");
  }
  el("lb-share").addEventListener("click", share);
  el("lb-p-share").addEventListener("click", share);

  pick.addEventListener("change", function () { setTeam(pick.value || null); });
  el("lb-p-pick").addEventListener("change", function () { setTeam(this.value); renderPanel(); });
  el("lb-open-panel").addEventListener("click", function () { openPanel(true); });
  if (el("lb-side-open")) el("lb-side-open").addEventListener("click", function () { openPanel(true); });
  if (pin) pin.addEventListener("click", function () { openPanel(true); });
  [].forEach.call(panel.querySelectorAll(".lb-close, .lb-back"), function (b) { b.addEventListener("click", closePanel); });
  if (scrim) scrim.addEventListener("click", closePanel);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && panelOpen) closePanel(); });
  var lastW = window.innerWidth;
  window.addEventListener("resize", function () { if (Math.abs(window.innerWidth - lastW) < 8) return; lastW = window.innerWidth; drawAll(); if (panelOpen) renderPanel(); });

  /* start: ?team= wins, then the remembered team; a ?team= link opens the panel */
  var q = new URLSearchParams(window.location.search).get("team");
  if (q && !T[q]) {
    var nt = el("lb-notice"); nt.hidden = false; nt.textContent = "We couldn’t find a team called “" + q + "”. Pick one below.";
    history.replaceState(null, "", teamUrl(null)); q = null;
  }
  var start = q || (T[store.get()] ? store.get() : null);
  setTeam(start, "load");
  if (q) { history.replaceState({ lbPanel: false }, "", teamUrl(q)); openPanel(true); }
  document.body.setAttribute("data-ready", "1");
})();
