/* DAWG Lab page script. Reads the case data embedded in the page (#lab-data). No framework, no network.
   Team selection precedence: ?team= in the link, then the team remembered from an earlier visit, then none.
   A ?team= link opens that team's panel directly; Back closes it. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var STORE = "dawg-lab-team";
  var el = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var fmt = function (v) { return (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(1); };
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

  /* ------------------------------------------------------------ chart 1: carryover */
  function drawCarryover(node, co, team, opt) {
    opt = opt || {};
    var W = width(node, 700), narrow = W < 560, H = narrow ? Math.round(W * 1.02) : Math.min(460, Math.max(320, Math.round(W * 0.5)));
    if (opt.fit) {
      node.innerHTML = ""; var ch = node.clientHeight;
      try { var cs = getComputedStyle(node); ch -= (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0); } catch (e) {}
      if (ch > 120) H = Math.floor(ch);
    }
    var m = { l: narrow ? 30 : 40, r: narrow ? 10 : 14, t: narrow ? 70 : 58, b: 44 };
    var vals = co.points.map(function (p) { return Math.max(Math.abs(p.x), Math.abs(p.y)); });
    /* a tight, even domain so the dots fill the plot instead of huddling in the middle */
    var D0 = Math.max(6, Math.ceil(Math.max.apply(null, vals.concat([co.band + 0.5])) + 0.6)); if (D0 % 2) D0++;
    var step = D0 <= 8 ? 2 : D0 <= 16 ? 4 : 8;
    var X = function (v) { return m.l + (v + D0) / (2 * D0) * (W - m.l - m.r); };
    var Y = function (v) { return m.t + (D0 - v) / (2 * D0) * (H - m.t - m.b); };
    var s = svg(W, H, "Carryover: each program's gap in " + co.x_label + " against " + co.y_label);
    add(s, "rect", { x: m.l, y: Y(co.band), width: W - m.l - m.r, height: Y(-co.band) - Y(co.band), fill: "#EADFC4" });
    var ifmt = function (v) { return (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v); };
    for (var v = -Math.floor((D0 - 0.5) / step) * step; v < D0; v += step) {
      if (v === 0) continue;
      add(s, "line", { x1: X(v), y1: H - m.b, x2: X(v), y2: H - m.b + 5, stroke: "#6E6557" });
      add(s, "text", { x: X(v), y: H - m.b + 17, "text-anchor": "middle", style: "font-size:11px;fill:#6E6557" }, ifmt(v));
      add(s, "line", { x1: m.l - 5, y1: Y(v), x2: m.l, y2: Y(v), stroke: "#6E6557" });
      add(s, "text", { x: m.l - 7, y: Y(v) + 4, "text-anchor": "end", style: "font-size:11px;fill:#6E6557" }, ifmt(v));
    }
    add(s, "line", { x1: m.l, y1: H - m.b, x2: W - m.r, y2: H - m.b, stroke: "#131210", "stroke-opacity": 0.25 });
    add(s, "line", { x1: m.l, y1: m.t, x2: m.l, y2: H - m.b, stroke: "#131210", "stroke-opacity": 0.25 });
    add(s, "line", { x1: X(-D0), y1: Y(-D0), x2: X(D0), y2: Y(D0), stroke: "#2F64C0", "stroke-width": 2, "stroke-dasharray": "8 6" });
    add(s, "line", { x1: m.l, y1: Y(0), x2: W - m.r, y2: Y(0), stroke: "#131210", "stroke-width": 1.5 });
    add(s, "line", { x1: X(0), y1: m.t, x2: X(0), y2: H - m.b, stroke: "#131210", "stroke-opacity": 0.35 });
    /* what each corner means */
    var qs = "font-size:" + (narrow ? 10 : 11) + "px;fill:#6E6557;letter-spacing:.04em";
    var k = (H - m.t - m.b) / (W - m.l - m.r), off = Math.max(34, 24 / k + 4);   /* keep the corner labels clear of the dashed line */
    add(s, "text", { x: m.l + off, y: H - m.b - 8, style: qs }, "worse, then worse");
    add(s, "text", { x: W - m.r - off, y: m.t + 12, "text-anchor": "end", style: qs }, "better, then better");
    var sel = node._lbSel && co.points.filter(function (p) { return p.t === node._lbSel; })[0];
    co.points.forEach(function (p) {
      if (team && p.t === team) return;
      add(s, "circle", { cx: X(p.x), cy: Y(p.y), r: narrow ? 4.2 : 4.5, fill: "rgba(19,18,16,.42)" });
    });
    if (sel && sel.t !== team) add(s, "circle", { cx: X(sel.x), cy: Y(sel.y), r: 8, fill: "none", stroke: "#131210", "stroke-width": 2.5 });
    var hp = team && co.points.filter(function (p) { return p.t === team; })[0];
    if (hp) {
      add(s, "circle", { cx: X(hp.x), cy: Y(hp.y), r: 8.5, fill: "#D13A2F", stroke: "#FBF4E2", "stroke-width": 3 });
      var right = X(hp.x) < W - 120;
      add(s, "text", { x: X(hp.x) + (right ? 13 : -13), y: Y(hp.y) + 5, "text-anchor": right ? "start" : "end", "class": "lb-t-team" }, T[team] ? T[team].name : team);
    }
    add(s, "text", { x: W - m.r, y: H - 6, "text-anchor": "end" }, co.x_label + " →");
    add(s, "text", { x: m.l + 6, y: m.t - 8 }, "↑ " + co.y_label);
    node.innerHTML = ""; node.appendChild(s);
    /* legend above the plot so it never covers a dot; the second item wraps when it won't fit */
    var ly = 14, lx = m.l;
    add(s, "rect", { x: lx, y: ly - 9, width: 22, height: 12, fill: "#EADFC4", stroke: "#B8AD98" });
    var l1 = add(s, "text", { x: lx + 30, y: ly + 2 }, narrow ? "Luck range if nothing carries over" : "Shaded: the luck range if nothing carries over");
    var w1 = 0; try { w1 = l1.getComputedTextLength(); } catch (e) {}
    var lx2 = lx + 30 + w1 + 28, ly2 = ly;
    if (!w1 || lx2 + 160 > W - m.r) { lx2 = lx; ly2 = ly + 20; }
    add(s, "line", { x1: lx2, y1: ly2 - 3, x2: lx2 + 22, y2: ly2 - 3, stroke: "#2F64C0", "stroke-width": 2, "stroke-dasharray": "6 4" });
    add(s, "text", { x: lx2 + 30, y: ly2 + 2, style: "fill:#2F64C0" }, narrow ? "If gaps lasted" : "If gaps lasted: dots along the dashed line");
    if (!opt.readout) return;
    /* tap or hover a dot to see which program it is */
    var rd = document.createElement("p"); rd.className = "lb-co-read"; rd.setAttribute("aria-live", "polite");
    var show = sel || hp;
    rd.innerHTML = show ? "<b>" + esc(T[show.t] ? T[show.t].name : show.t) + "</b> earlier " + fmt(show.x) + " · later " + fmt(show.y) + (show === hp && !sel ? "" : ' <button type="button" data-clear>Clear</button>')
      : (narrow ? "Tap a dot to see which program it is." : "Hover or click a dot to see which program it is.");
    node.appendChild(rd);
    var clr = rd.querySelector("[data-clear]"); if (clr) clr.addEventListener("click", function () { node._lbSel = null; drawCarryover(node, co, team, opt); });
    var pick = function (ev, commit) {
      var r = s.getBoundingClientRect(), px = ev.clientX - r.left, py = ev.clientY - r.top, best = null, bd = 22 * 22;
      co.points.forEach(function (p) { var dx = X(p.x) - px, dy = Y(p.y) - py, d = dx * dx + dy * dy; if (d < bd) { bd = d; best = p; } });
      if (best && (commit || best.t !== node._lbSel)) { node._lbSel = best.t; drawCarryover(node, co, team, opt); }
    };
    s.addEventListener("click", function (ev) { pick(ev, true); });
    if (!narrow) s.addEventListener("mousemove", function (ev) { pick(ev, false); });
  }

  /* ------------------------------------------------------------ chart 2: upper bound */
  function drawBound(node, cut, threshold) {
    var W = width(node, 700), narrow = W < 560, H = 116, m = { l: 16, r: 16 };
    var max = Math.max(4, Math.ceil((cut.U || 0) + 1));
    var X = function (v) { return m.l + v / max * (W - m.l - m.r); };
    var y = 66;
    var s = svg(W, H, "Lasting effects bigger than ±" + cut.U + " points are ruled out; the size that matters is " + threshold);
    var defs = add(s, "defs", {});
    var pat = add(defs, "pattern", { id: "lbHatch" + node.id, width: 8, height: 8, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" });
    add(pat, "rect", { width: 8, height: 8, fill: "#EADFC4" }); add(pat, "line", { x1: 0, y1: 0, x2: 0, y2: 8, stroke: "#6E6557", "stroke-width": 2 });
    add(s, "rect", { x: X(cut.U), y: y - 16, width: X(max) - X(cut.U), height: 32, fill: "url(#lbHatch" + node.id + ")", stroke: "#131210", "stroke-width": 1.5 });
    add(s, "line", { x1: X(0), y1: y, x2: X(max), y2: y, stroke: "#131210", "stroke-width": 2 });
    for (var v = 0; v <= max; v++) { add(s, "line", { x1: X(v), y1: y + 16, x2: X(v), y2: y + 22, stroke: "#131210" }); add(s, "text", { x: X(v), y: y + 38, "text-anchor": "middle" }, String(v)); }
    add(s, "line", { x1: X(threshold), y1: y - 30, x2: X(threshold), y2: y + 16, stroke: "#D13A2F", "stroke-width": 3 });
    add(s, "text", { x: X(threshold), y: y - 36, "text-anchor": X(threshold) > W - 160 ? "end" : "middle", style: "fill:#C2342A;font-weight:600" }, "Size that matters: " + threshold);
    node.innerHTML = ""; node.appendChild(s);
    /* the ruled-out label goes inside the hatched block on a cream backing, shortened if the block is narrow */
    var x0 = X(cut.U), x1 = X(max), bg = add(s, "rect", { y: y - 10, height: 20, fill: "#FBF4E2" });
    var tx = add(s, "text", { x: (x0 + x1) / 2, y: y + 4, "text-anchor": "middle", style: "fill:#131210;font-weight:600" }, "Ruled out: bigger than ±" + cut.U);
    var tw = 0; try { tw = tx.getComputedTextLength(); } catch (e) {}
    if (tw && tw + 16 > x1 - x0) { tx.textContent = "±" + cut.U + "+ ruled out"; try { tw = tx.getComputedTextLength(); } catch (e) {} }
    if (tw && tw + 12 > x1 - x0) { tx.setAttribute("text-anchor", "end"); tx.setAttribute("x", x1); tx.setAttribute("y", y - 22); bg.setAttribute("width", 0); }
    else if (tw) { bg.setAttribute("x", (x0 + x1) / 2 - tw / 2 - 5); bg.setAttribute("width", tw + 10); }
  }

  /* ------------------------------------------------------------ chart 3: team vs luck */
  function drawStrip(node, t, opt) {
    opt = opt || {};
    var big = !!opt.big, W = width(node, big ? 900 : 520), H = big ? 150 : 100, pad = big ? 10 : 6, y = big ? 76 : 44;
    var span = Math.max(15, Math.ceil(Math.abs(t.raw) + 2));
    var X = function (v) { return pad + (v + span) / (2 * span) * (W - 2 * pad); };
    var fs = big ? 22 : 12;
    var s = svg(W, H, t.name + ": " + fmt(t.raw) + " points" + (t.state === "ok" ? ", luck range ±" + t.band.toFixed(1) : ""));
    if (t.state === "ok") add(s, "rect", { x: X(-t.band), y: y - (big ? 26 : 14), width: X(t.band) - X(-t.band), height: big ? 52 : 28, fill: "#EADFC4", stroke: "#6E6557", "stroke-width": big ? 2.5 : 1.5, "stroke-dasharray": "5 4" });
    add(s, "line", { x1: pad, y1: y, x2: W - pad, y2: y, stroke: "#131210", "stroke-width": big ? 3 : 2 });
    add(s, "line", { x1: X(0), y1: y - (big ? 34 : 20), x2: X(0), y2: y + (big ? 34 : 20), stroke: "#131210", "stroke-width": big ? 3 : 2 });
    if (t.state === "ok" && opt.adjusted !== false) add(s, "circle", { cx: X(t.adjusted), cy: y, r: big ? 13 : 7, fill: "none", stroke: "#131210", "stroke-width": big ? 4 : 2.5 });
    add(s, "circle", { cx: X(t.raw), cy: y, r: big ? 19 : 10, fill: "#D13A2F", stroke: "#FBF4E2", "stroke-width": big ? 5 : 3 });
    add(s, "text", { x: X(t.raw), y: y - (big ? 32 : 18), "text-anchor": "middle", style: "font-family:var(--cond),'Barlow Condensed',sans-serif;font-weight:800;font-size:" + (big ? 30 : 15) + "px;fill:#C2342A" }, fmt(t.raw));
    if (t.state === "ok") add(s, "text", { x: X(-t.band) + 4, y: y + (big ? 50 : 33), style: "font-size:" + (big ? 18 : 11) + "px;fill:#6E6557" }, "luck range");
    add(s, "text", { x: pad, y: H - 4, style: "font-size:" + fs + "px" }, "worse");
    add(s, "text", { x: X(0), y: H - 4, "text-anchor": "middle", style: "font-size:" + fs + "px" }, "0");
    add(s, "text", { x: W - pad, y: H - 4, "text-anchor": "end", style: "font-size:" + fs + "px" }, "better");
    node.innerHTML = ""; node.appendChild(s);
  }

  /* ------------------------------------------------------------ chart 4: four groups */
  function drawGroups(node, t, league) {
    var W = width(node, 520), narrow = W < 460, lw = narrow ? 112 : 150, vw = 70, rowH = 46, H = rowH * t.groups.length + 30;
    var all = t.groups.map(function (g) { return Math.abs(g.avg); }).concat(league.map(function (g) { return Math.abs(g.avg); }));
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
      var b = sc(g.avg); add(s, "rect", { x: Math.min(mid, mid + b), y: y + 13, width: Math.max(1.5, Math.abs(b)), height: 14, fill: "#D13A2F" });
      add(s, "text", { x: W, y: y + 18, "text-anchor": "end", style: "fill:#131210" }, fmt(g.avg) + " · " + g.n + " g");
    });
    node.innerHTML = ""; node.appendChild(s);
  }

  /* ------------------------------------------------------------ chart 5: season by season */
  function drawSeasons(node, t) {
    var rows = t.season_rows || [];
    var W = width(node, 520), H = 132, pad = 14, top = 14, bot = 40;
    var mx = Math.max(8, Math.ceil(Math.max.apply(null, rows.map(function (r) { return Math.abs(r.gap); }).concat([1])) + 1));
    var X = function (i) { return pad + (rows.length === 1 ? 0.5 : i / (rows.length - 1)) * (W - 2 * pad); };
    var Y = function (v) { return top + (mx - v) / (2 * mx) * (H - top - bot); };
    var s = svg(W, H, t.name + " season by season; hollow marks are research grades");
    add(s, "line", { x1: 0, y1: Y(0), x2: W, y2: Y(0), stroke: "#131210", "stroke-width": 1.5 });
    var every = W < 420 ? 2 : 1;
    rows.forEach(function (r, i) {
      var c = { cx: X(i), cy: Y(r.gap), r: 6 };
      if (r.research) { c.fill = "#FBF4E2"; c.stroke = "#D13A2F"; c["stroke-width"] = 2.5; } else { c.fill = "#D13A2F"; }
      add(s, "circle", c);
      if (i % every === 0 || i === rows.length - 1) {
        add(s, "text", { x: X(i), y: H - 22, "text-anchor": "middle", style: "font-size:11px" }, "’" + String(r.season).slice(2));
        add(s, "text", { x: X(i), y: H - 8, "text-anchor": "middle", style: "font-size:10px;fill:#6E6557" }, r.n + "g");
      }
    });
    node.innerHTML = ""; node.appendChild(s);
  }

  var LAB = window.DAWGLab = { drawCarryover: drawCarryover, drawBound: drawBound, drawStrip: drawStrip, drawGroups: drawGroups, drawSeasons: drawSeasons, data: D };

  /* ------------------------------------------------------------ share-card mode: draw and stop */
  if (document.body.getAttribute("data-mode") === "card") {
    [].forEach.call(document.querySelectorAll("[data-chart]"), function (n) {
      var k = n.getAttribute("data-chart"), t = T[n.getAttribute("data-team")];
      if (k === "strip" && t) drawStrip(n, t, { big: true });
      if (k === "carryover") drawCarryover(n, D.carryover, null, { fit: true });
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
    var ex = el("lb-home-ex"); if (ex && D.carryover) { var dr = function () { drawCarryover(ex, D.carryover, homePick.value, { fit: window.innerWidth >= 900 }); }; dr(); homePick.addEventListener("change", dr); window.addEventListener("resize", dr); }
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
      H.push('<section class="lb-sec"><div class="lb-insuff">' + esc(t.none_text) + '</div><a class="lb-btn" href="#lb-carry-sec" data-goto>See the full sample</a></section>');
    } else {
      var lo = t.state === "ok" ? "−" + t.band.toFixed(1) + " to +" + t.band.toFixed(1) : "";
      H.push('<section class="lb-sec"><span class="lb-label">2 · ' + esc(t.name) + " vs. luck</span>" +
        '<div class="lb-exhibit"><div id="lb-p-strip" style="padding:10px 12px 4px"></div>' +
        (t.state === "ok" ? '<div class="lb-ex-foot">Shaded = the luck range (' + lo + "): luck alone lands a program inside it " + esc(t.coverage) + " times in 100 over " + t.hf_games +
            " games. Ring = the same gap pulled toward the league average, because small samples swing more.</div>"
          : '<div class="lb-ex-foot">Raw gap only. Below the minimum there’s no luck range and no adjusted value.</div>') +
        rnote(t) + "</div></section>");
      H.push('<section class="lb-sec"><span class="lb-label">3 · Each kind of game</span><div class="lb-exhibit"><div id="lb-p-groups" style="padding:12px"></div>' +
        rnote(t, "Includes " + t.research_short.replace(/^incl\. /, "") + ", not official DAWG grades.") + "</div></section>");
      H.push('<section class="lb-sec"><span class="lb-label">4 · Season by season</span><div class="lb-exhibit"><div id="lb-p-seasons" style="padding:10px 10px 0"></div>' +
        rnote(t, "Hollow marks = " + D.research.label_short + ".") + '</div><span class="lb-note">Each season is only a few games. Read the row, not one dot.</span></section>');
      H.push('<section class="lb-sec"><span class="lb-label">5 · Sample and uncertainty</span><div class="lb-three">' +
        "<div><span class=\"lb-label\">Raw gap</span><b style=\"color:#C2342A\">" + fmt(t.raw) + "</b><small>what happened</small></div>" +
        (t.state === "ok" ? "<div><span class=\"lb-label\">Adjusted</span><b>" + fmt(t.adjusted) + "</b><small>pulled toward average for small samples</small></div>"
          : "<div><span class=\"lb-label\">Adjusted</span><b>—</b><small>not shown below the minimum</small></div>") +
        "<div><span class=\"lb-label\">Sample</span><b>" + t.hf_games + "</b><small>" + esc(t.n_label) + ", " + t.seasons + " seasons" +
        (t.research_games ? "; " + t.research_games + " use research grades" : "") + "</small></div></div></section>");
    }
    b.innerHTML = H.join("");
    [].forEach.call(b.querySelectorAll("[data-goto]"), function (a) {
      a.addEventListener("click", function (ev) {
        ev.preventDefault(); var id = a.getAttribute("href").slice(1); closePanel();
        setTimeout(function () { var n = el(id); if (n) n.scrollIntoView({ block: "start" }); }, 80);
      });
    });
    if (t.state !== "none") { drawStrip(el("lb-p-strip"), t, { adjusted: t.state === "ok" }); drawGroups(el("lb-p-groups"), t, D.league.groups); drawSeasons(el("lb-p-seasons"), t); }
    el("lb-p-share").hidden = !t.card;
    el("lb-p-team").href = "/" + current + "/"; el("lb-p-team").textContent = t.name + " team page";
  }

  function drawAll() {
    var co = el("lb-carry"); if (co) drawCarryover(co, (activeCut && activeCut.carryover) || D.carryover, current, { readout: true });
    var bd = el("lb-bound"); if (bd && activeCut) drawBound(bd, activeCut, D.threshold);
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

  /* cut switcher */
  var cuts = D.cuts || [], activeCut = cuts.filter(function (c) { return c.plan; })[0] || cuts[0];
  [].forEach.call(document.querySelectorAll("[data-cut]"), function (bt) {
    bt.addEventListener("click", function () {
      activeCut = cuts.filter(function (c) { return c.id === bt.getAttribute("data-cut"); })[0] || activeCut;
      [].forEach.call(document.querySelectorAll("[data-cut]"), function (o) { o.setAttribute("aria-pressed", o === bt ? "true" : "false"); });
      el("lb-cut-note").textContent = activeCut.note;
      drawAll();
    });
  });

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
