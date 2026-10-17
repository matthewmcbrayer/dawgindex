/* DAWG Lab: Original Investigation pages (LAB 001: tougher half vs. easier half of a schedule).
   Reads the case data embedded in the page (#lab-data); the team explorer loads its game rows from explorer.json.
   No framework. Everything is drawn at the container's real width, so labels stay a readable size on phones,
   and every interaction is a tap or a select (nothing needs hover). */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var STORE = "dawg-lab-team";
  var el = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var fmt = function (v) { var m = Math.abs(v).toFixed(1); return (m === "0.0" ? "" : v > 0 ? "+" : "−") + m; };   /* rounds like lab.py */
  var POS = "#1E7A50", NEG = "#D13A2F", INK = "#131210", INK2 = "#3B362E", MUTED = "#6E6557", PAPER = "#FBF4E2", FOLDER = "#EADFC4";
  var gradeColor = function (v) { var m = Math.abs(v).toFixed(1); return m === "0.0" ? INK : v > 0 ? POS : NEG; };
  var store = {
    get: function () { try { return window.localStorage.getItem(STORE); } catch (e) { return null; } },
    set: function (v) { try { window.localStorage.setItem(STORE, v); } catch (e) {} }
  };
  var dataNode = el("lab-data");
  if (!dataNode) return;
  var D = JSON.parse(dataNode.textContent);

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
  var COND = "font-family:'Barlow Condensed',sans-serif;font-weight:700;text-transform:uppercase;letter-spacing:.03em;";
  var DISP = "font-family:'Big Shoulders Display',sans-serif;font-weight:900;";

  /* ------------------------------------------------------------ Exhibit 1: tougher half vs easier half (sorted by the spread) */
  function drawIllusion(node, il) {
    var W = width(node, 640), narrow = W < 520, fs = narrow ? 13 : 14;
    var lw = narrow ? 96 : 130, vw = narrow ? 52 : 64, rowH = narrow ? 50 : 54, top = 12, H = top + rowH * 2 + 40;
    var x0 = lw, x1 = W - vw, mid = (x0 + x1) / 2, mx = 2, X = function (v) { return mid + v / mx * (x1 - x0) / 2; };
    var s = svg(W, H, "Average DAWG grade: tougher half " + fmt(il.tougher) + ", easier half " + fmt(il.easier) + ", gap " + fmt(il.gap));
    add(s, "line", { x1: mid, y1: top - 4, x2: mid, y2: top + rowH * 2 + 4, stroke: INK, "stroke-width": 2 });
    [["Tougher half", il.tougher], ["Easier half", il.easier]].forEach(function (r, i) {
      var y = top + i * rowH, c = gradeColor(r[1]);
      add(s, "text", { x: 0, y: y + rowH / 2 + 5, style: COND + "font-size:" + (fs + 3) + "px;fill:" + INK }, r[0]);
      add(s, "rect", { x: Math.min(mid, X(r[1])), y: y + 10, width: Math.abs(X(r[1]) - mid), height: rowH - 20, fill: c });
      add(s, "text", { x: W, y: y + rowH / 2 + 8, "text-anchor": "end", style: DISP + "font-size:" + (narrow ? 24 : 28) + "px;fill:" + c }, fmt(r[1]));
    });
    (narrow ? [-2, 0, 2] : [-2, -1, 0, 1, 2]).forEach(function (v) {
      add(s, "text", { x: X(v), y: top + rowH * 2 + 20, "text-anchor": v === -2 ? "start" : v === 2 ? "end" : "middle", style: "font-size:12px;fill:" + MUTED }, v === 0 ? "0" : fmt(v));
    });
    add(s, "text", { x: mid, y: H - 2, "text-anchor": "middle", style: "font-size:12px;fill:" + MUTED }, narrow ? "Avg. DAWG grade" : "Average DAWG grade (points vs. expected)");
    node.innerHTML = ""; node.appendChild(s);
    var cap = document.createElement("p"); cap.className = "lb-oi-gap";
    cap.innerHTML = "Gap: <b>" + esc(fmt(il.gap)) + " points</b> <span>(95% range " + esc(fmt(il.ci[0])) + " to " + esc(fmt(il.ci[1])) + ")</span>";
    node.appendChild(cap);
  }
  function drawSeasons(node, il) {
    var W = width(node, 640), yrs = Object.keys(il.by_season).sort(), n = yrs.length;
    var top = 22, bot = 24, H = 150, cw = W / n, mx = Math.max(4.5, Math.ceil(Math.max.apply(null, yrs.map(function (y) { return il.by_season[y]; })) + 0.5));
    var Y = function (v) { return top + (1 - v / mx) * (H - top - bot); };
    var s = svg(W, H, "Gap by season: " + yrs.map(function (y) { return y + " " + fmt(il.by_season[y]); }).join(", "));
    add(s, "line", { x1: 0, y1: Y(0), x2: W, y2: Y(0), stroke: INK, "stroke-width": 1.5 });
    yrs.forEach(function (y, i) {
      var v = il.by_season[y], cx = cw * i + cw / 2, bw = Math.min(30, cw * 0.62);
      add(s, "rect", { x: cx - bw / 2, y: Y(Math.max(0, v)), width: bw, height: Math.abs(Y(v) - Y(0)), fill: INK2 });
      add(s, "text", { x: cx, y: Y(Math.max(0, v)) - 5, "text-anchor": "middle", style: "font-size:" + (cw < 34 ? 11 : 12) + "px;font-weight:600;fill:" + INK }, cw < 34 ? fmt(v).replace("+", "") : fmt(v));
      add(s, "text", { x: cx, y: H - 6, "text-anchor": "middle", style: "font-size:12px;fill:" + MUTED }, "’" + y.slice(2));
    });
    node.innerHTML = ""; node.appendChild(s);
  }

  /* ------------------------------------------------------------ Exhibit 2: the same games, two ways to rank opponents */
  function drawReveal(node, rv, opt) {
    opt = opt || {};
    var W = width(node, 640), k = opt.big ? 2 : opt.mid ? 1.3 : 1, narrow = W < 520 && !opt.big && !opt.mid, tight = W / k < 600;
    var lo = -2, hi = 4, pad = 6 * k, x0 = pad, x1 = W - pad;
    var X = function (v) { return x0 + (v - lo) / (hi - lo) * (x1 - x0); };
    var rows = [{ label: "Sorted by that game’s spread", b: rv.spread }, { label: tight ? (W / k < 420 ? "Sorted by opponent strength" : "Sorted by opponent strength before kickoff") : "Sorted by the opponent’s strength before kickoff", b: rv.opponent }];
    var labH = 30 * k, bandH = 34 * k, subH = opt.compact ? 6 * k : 26 * k, gapH = 16 * k, rowH = labH + bandH + subH + gapH;
    var axH = 44 * k, H = rowH * rows.length + axH;
    var s = svg(W, H, rows.map(function (r) { return r.label + ": " + fmt(r.b.gap) + " (95% range " + fmt(r.b.ci[0]) + " to " + fmt(r.b.ci[1]) + ")"; }).join("; "));
    rows.forEach(function (r, i) {
      var y = i * rowH, by = y + labH, cy = by + bandH / 2, fsL = (narrow ? 15 : 16) * k;
      add(s, "text", { x: x0, y: y + 21 * k, style: COND + "font-size:" + fsL + "px;fill:" + INK }, r.label);
      add(s, "text", { x: x1, y: y + 25 * k, "text-anchor": "end", style: DISP + "font-size:" + (opt.compact ? 26 : 32) * k + "px;fill:" + INK }, fmt(r.b.gap));
      add(s, "rect", { x: x0, y: by, width: x1 - x0, height: bandH, fill: PAPER, stroke: "rgba(19,18,16,.18)" });
      add(s, "rect", { x: X(0), y: by, width: x1 - X(0), height: bandH, fill: FOLDER });
      add(s, "line", { x1: X(0), y1: by - 3, x2: X(0), y2: by + bandH + 3, stroke: INK, "stroke-width": 2 * Math.min(k, 1.6) });
      add(s, "line", { x1: X(r.b.ci[0]), y1: cy, x2: X(r.b.ci[1]), y2: cy, stroke: INK, "stroke-width": 4 * Math.min(k, 1.6), "stroke-linecap": "round" });
      add(s, "circle", { cx: X(r.b.gap), cy: cy, r: 9 * Math.min(k, 1.7), fill: INK, stroke: PAPER, "stroke-width": 2.5 });
      if (!opt.compact) add(s, "text", { x: x0, y: by + bandH + 19 * k, style: "font-size:" + (narrow ? 12.5 : 13) * k + "px;fill:" + INK2 },
        "Tougher half " + fmt(r.b.tougher) + " · Easier half " + fmt(r.b.easier));
    });
    var ay = rows.length * rowH + 2 * k, afs = (narrow ? 12 : 13) * k;
    [-2, 0, 2, 4].forEach(function (v) {
      add(s, "text", { x: X(v), y: ay + 8 * k, "text-anchor": v === hi ? "end" : v === lo ? "start" : "middle", style: "font-size:" + afs + "px;" + (v === 0 ? "font-weight:600;fill:" + INK : "fill:" + MUTED) }, v === 0 ? "0" : fmt(v));
    });
    add(s, "text", { x: x0, y: ay + 28 * k, style: "font-size:" + afs + "px;fill:" + INK2 }, W / k < 380 ? "← worse" : tight ? "← worse vs. tougher" : "← worse against tougher opponents");
    add(s, "text", { x: x1, y: ay + 28 * k, "text-anchor": "end", style: "font-size:" + afs + "px;fill:" + INK2 }, W / k < 380 ? "better vs. tougher →" : tight ? "better vs. tougher →" : "better against tougher opponents →");
    node.innerHTML = ""; node.appendChild(s);
  }

  /* ------------------------------------------------------------ share-card mode: draw and stop */
  if (document.body.getAttribute("data-mode") === "card") {
    [].forEach.call(document.querySelectorAll("[data-chart=reveal]"), function (n) {
      drawReveal(n, D.reveal, { big: n.getAttribute("data-size") !== "m", mid: n.getAttribute("data-size") === "m", compact: n.getAttribute("data-size") === "m" });
    });
    document.body.setAttribute("data-ready", "1");
    return;
  }

  /* ------------------------------------------------------------ Lab homepage */
  var homePick = el("lb-home-pick");
  if (homePick) {
    var hl = el("lb-home-link"), ha = el("lb-home-ans"), hline = el("lb-home-line"), a0 = ha.textContent, l0 = hline.textContent, t0 = hl.textContent;
    var setHome = function (slug) {
      var name = D.teams[slug];
      homePick.value = name ? slug : "";
      if (!name) { ha.textContent = a0; hline.textContent = l0; hl.href = D.case.url + "#your-team"; hl.textContent = t0; return; }
      ha.textContent = name + ", every season since 2014."; hline.textContent = "Its tougher and easier halves, game by game.";
      hl.href = D.case.url + "?team=" + slug + "#your-team"; hl.textContent = "See " + name + "’s seasons →";
    };
    var f0 = store.get(); setHome(D.teams[f0] ? f0 : null);
    homePick.addEventListener("change", function () { if (homePick.value) store.set(homePick.value); setHome(homePick.value); });
    var hx = el("lb-home-ex");
    if (hx) { var hd = function () { drawReveal(hx, D.reveal, { compact: true }); }; hd(); window.addEventListener("resize", hd); }
    document.body.setAttribute("data-ready", "1");
    return;
  }

  /* ------------------------------------------------------------ the case page: exhibits 1 and 2 */
  function drawExhibits() {
    var a = el("lb-illusion"); if (a) drawIllusion(a, D.illusion);
    var b = el("lb-seasons"); if (b) drawSeasons(b, D.illusion);
    var c = el("lb-reveal"); if (c) drawReveal(c, D.reveal, {});
  }

  /* ------------------------------------------------------------ Exhibit 3: the team explorer */
  var X = { data: null, team: null, season: null, sel: null };
  var pickT = el("lb-xp-team"), pickS = el("lb-xp-season"), lead = el("lb-xp-lead"), chart = el("lb-xp-chart"), tap = el("lb-xp-tap"), list = el("lb-xp-list"), rowsEl = el("lb-xp-rows");
  var spreadWords = function (e) { var m = Math.abs(e).toFixed(1).replace(/\.0$/, ""); return Math.abs(e) < 0.25 ? "pick’em" : e > 0 ? "favored by " + m : "underdog by " + m; };
  var spreadShort = function (e) { var m = Math.abs(e).toFixed(1).replace(/\.0$/, ""); return Math.abs(e) < 0.25 ? "PK" : (e > 0 ? "Fav " : "Dog ") + m; };
  var avgWords = function (e) { var m = Math.abs(e).toFixed(1); return Math.abs(e) < 0.5 ? "about even on average" : e > 0 ? "favored by " + m + " on average" : "underdog by " + m + " on average"; };
  var MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var dayText = function (md) { var p = md.split("-"); return MON[+p[0] - 1] + " " + (+p[1]); };
  var venueWord = function (v) { return v === 1 ? "vs." : v === -1 ? "at" : "vs."; };
  var halfWord = { t: "Tougher half", e: "Easier half", x: "Neither half", "": "—" };

  function seasonsOf(slug) { return Object.keys(X.data.teams[slug].seasons).sort().reverse(); }
  function isResearch(season) { return D.research.through && +season <= D.research.through; }
  var LATEST = null;
  function seasonLabel(slug, season) {
    var ts = X.data.teams[slug].seasons[season];
    return season + (+season === LATEST && !ts.T ? " (so far)" : "");
  }
  function fillTeams() {
    var names = Object.keys(X.data.teams).map(function (s) { return [s, X.data.teams[s].name]; });
    names.forEach(function (p) { var o = document.createElement("option"); o.value = p[0]; o.textContent = p[1]; pickT.appendChild(o); });
  }
  function fillSeasons(slug) {
    pickS.innerHTML = "";
    seasonsOf(slug).forEach(function (y) { var o = document.createElement("option"); o.value = y; o.textContent = seasonLabel(slug, y); pickS.appendChild(o); });
    pickS.disabled = false;
  }
  function defaultSeason(slug) {
    var ss = seasonsOf(slug);
    for (var i = 0; i < ss.length; i++) if (X.data.teams[slug].seasons[ss[i]].T) return ss[i];
    return ss[0];
  }
  function setURL() {
    try {
      var u = new URL(window.location.href);
      if (X.team) { u.searchParams.set("team", X.team); u.searchParams.set("season", X.season); } else { u.searchParams.delete("team"); u.searchParams.delete("season"); }
      history.replaceState(history.state, "", u.pathname + u.search + u.hash);
    } catch (e) {}
  }

  function renderLead(slug, season) {
    var tm = X.data.teams[slug], ts = tm.seasons[season], name = tm.name, H = [];
    var rnote = isResearch(season) ? '<p class="lb-xp-rn"><i aria-hidden="true"></i>' + esc(season) + " grades are research grades: computed with the DAWG formula, not official DAWG grades.</p>" : "";
    if (!ts.T) {
      var soFar = +season === LATEST;
      H.push('<p class="lb-xp-small"><b>' + esc(name) + " " + esc(season) + ":</b> " + ts.n + " graded game" + (ts.n === 1 ? "" : "s") + (soFar ? " so far" : "") +
             ". Splitting a schedule into halves needs at least " + X.data.min_games + " games" + (soFar ? ", so this season gets halves once it has enough." : ".") + "</p>");
      H.push(rnote);
      lead.innerHTML = H.join(""); return;
    }
    var row = function (label, h) {
      var c = gradeColor(h[2]);
      return '<div class="lb-xp-row"><span class="lb-xp-k">' + label + '</span><span class="lb-xp-m">' + h[0] + " games · " + esc(avgWords(h[1])) +
             '</span><span class="lb-xp-v" style="color:' + c + '">' + esc(fmt(h[2])) + '</span><span class="lb-xp-u">vs. expected</span></div>';
    };
    H.push('<div class="lb-xp-rows">' + row("Against its tougher half", ts.T) + row("Against its easier half", ts.E) + "</div>");
    var g = ts.gap, gm = Math.abs(g).toFixed(1);
    H.push('<p class="lb-xp-sent">' + (gm === "0.0" ? esc(name) + " graded the same against both halves in " + esc(season) + "."
      : esc(name) + " graded " + gm + " points " + (g > 0 ? "better" : "worse") + " against its tougher half than its easier half in " + esc(season) + ".") + "</p>");
    var xs = ts.g.filter(function (r) { return r[5] === "x"; }).length;
    if (xs) H.push('<p class="lb-xp-small">' + xs + " game" + (xs === 1 ? " counts" : "s count") + " in neither half (hollow in the chart): the middle game of an odd-numbered schedule, or games tied on the spread at the halfway line.</p>");
    H.push('<p class="lb-xp-small">With halves this small, big gaps happen by chance. Across ' + D.illusion.team_seasons + " team-seasons, the gaps vary about as much as luck alone predicts. This describes what happened, not a finding about " + esc(name) + ".</p>");
    H.push(rnote);
    lead.innerHTML = H.join("");
  }

  function renderChart(slug, season) {
    var ts = X.data.teams[slug].seasons[season], G = ts.g, W = width(chart, 640), narrow = W < 520, f = narrow ? 13 : 12;
    var es = G.map(function (r) { return r[2]; }), ys = G.map(function (r) { return r[3]; });
    var xlo = Math.min(-7, Math.floor((Math.min.apply(null, es) - 3) / 7) * 7), xhi = Math.max(7, Math.ceil((Math.max.apply(null, es) + 3) / 7) * 7), ymax = Math.max(20, Math.ceil((Math.max.apply(null, ys.map(Math.abs)) + 4) / 10) * 10);
    var l = narrow ? 34 : 40, r = 12, top = 28, bot = 46, H = narrow ? 330 : 340;
    var Xs = function (e) { return l + (e - xlo) / (xhi - xlo) * (W - l - r); }, Ys = function (y) { return top + (ymax - y) / (2 * ymax) * (H - top - bot); };
    var s = svg(W, H, X.data.teams[slug].name + " " + season + ": " + G.length + " games, DAWG grade by spread");
    if (ts.T) {
      var tMax = -1e9, eMin = 1e9;
      G.forEach(function (g) { if (g[5] === "t") tMax = Math.max(tMax, g[2]); if (g[5] === "e") eMin = Math.min(eMin, g[2]); });
      var bx = Xs((tMax + eMin) / 2);
      add(s, "rect", { x: l, y: top, width: bx - l, height: H - top - bot, fill: FOLDER, opacity: 0.6 });
      add(s, "line", { x1: bx, y1: top, x2: bx, y2: H - bot, stroke: INK2, "stroke-width": 1.5, "stroke-dasharray": "5 4" });
      add(s, "text", { x: l + 6, y: top - 10, style: COND + "font-size:" + (f + 2) + "px;fill:" + INK }, "Tougher half");
      add(s, "text", { x: W - r, y: top - 10, "text-anchor": "end", style: COND + "font-size:" + (f + 2) + "px;fill:" + INK }, "Easier half");
      [["t", ts.T, l, bx], ["e", ts.E, bx, W - r]].forEach(function (h) {
        var y = Ys(h[1][2]), c = gradeColor(h[1][2]);
        add(s, "line", { x1: h[2] + 8, y1: y, x2: h[3] - 8, y2: y, stroke: c, "stroke-width": 3, "stroke-dasharray": "2 0" });
        add(s, "text", { x: h[0] === "t" ? h[2] + 10 : h[3] - 10, y: y - 7, "text-anchor": h[0] === "t" ? "start" : "end", style: "font-size:" + f + "px;font-weight:600;fill:" + c }, "avg " + fmt(h[1][2]));
      });
    }
    for (var v = -ymax; v <= ymax; v += 10) {
      add(s, "line", { x1: l, y1: Ys(v), x2: W - r, y2: Ys(v), stroke: v === 0 ? INK : "rgba(19,18,16,.12)", "stroke-width": v === 0 ? 1.5 : 1 });
      add(s, "text", { x: l - 6, y: Ys(v) + 4, "text-anchor": "end", style: "font-size:" + f + "px;fill:" + MUTED }, v === 0 ? "0" : fmt(v).replace(".0", ""));
    }
    var step = (xhi - xlo) > (narrow ? 42 : 70) ? 14 : 7, lastX = -1e9;
    for (var e = Math.ceil(xlo / step) * step; e <= xhi; e += step) {
      var tx = Xs(e), anc = tx - l < 24 ? "start" : W - r - tx < 24 ? "end" : "middle", half = (narrow ? 26 : 30);
      if (tx - lastX < half * 2) continue;
      add(s, "text", { x: tx, y: H - bot + 18, "text-anchor": anc, style: "font-size:" + f + "px;fill:" + MUTED }, spreadShort(e)); lastX = tx;
    }
    add(s, "text", { x: l, y: H - 6, style: "font-size:" + f + "px;fill:" + INK2 }, "← bigger underdog");
    add(s, "text", { x: W - r, y: H - 6, "text-anchor": "end", style: "font-size:" + f + "px;fill:" + INK2 }, "bigger favorite →");
    var dots = [], pts = [];
    G.forEach(function (g, i) {
      var cx = Xs(g[2]), cy = Ys(g[3]), c = gradeColor(g[3]), hollow = g[5] === "x";
      var d = add(s, "circle", { cx: cx, cy: cy, r: 7, fill: hollow ? PAPER : c, stroke: hollow ? INK : PAPER, "stroke-width": hollow ? 2.5 : 2 });
      dots.push(d); pts.push([cx, cy]);
    });
    /* one tap layer over the plot: a tap picks the nearest game (repeat taps cycle through games stacked on one spot);
       keyboard users get one focusable stop per game */
    var layer = add(s, "rect", { x: 0, y: 0, width: W, height: H, fill: "transparent", "data-tap": "1" });
    layer.style.cursor = "pointer";
    layer.addEventListener("click", function (ev) {
      var bb = s.getBoundingClientRect(), px = (ev.clientX - bb.left) * W / bb.width, py = (ev.clientY - bb.top) * H / bb.height;
      var near = pts.map(function (q, i) { return [Math.hypot(q[0] - px, q[1] - py), i]; }).filter(function (q) { return q[0] <= 28; }).sort(function (a, b) { return a[0] - b[0]; });
      if (!near.length) return;
      var cur = near.map(function (q) { return q[1]; }).indexOf(X.sel), pick = near[0][1];
      if (cur > -1 && near.length > 1 && near[cur][0] - near[0][0] < 14) pick = near[(cur + 1) % near.length][1];
      select(pick, dots);
    });
    G.forEach(function (g, i) {
      var k = add(s, "circle", { cx: pts[i][0], cy: pts[i][1], r: 12, fill: "transparent", "data-i": i, tabindex: 0, role: "button", "aria-label": gameText(g) });
      k.style.pointerEvents = "none";
      k.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(i, dots); } });
    });
    chart.innerHTML = ""; chart.appendChild(s); chart.hidden = false;
    var help = document.createElement("p"); help.className = "lb-xp-help"; help.textContent = "Up = better than expected (DAWG grade). Tap a dot for the game."; chart.appendChild(help);
    X.dots = dots;
  }
  function gameText(g) {
    var opp = X.data.opps[g[1]];
    return dayText(g[0]) + " · " + venueWord(g[4]) + " " + opp + (g[4] === 0 ? " (neutral site)" : "") + " · " + spreadWords(g[2]) + " · DAWG " + fmt(g[3]) + (g[5] ? " · " + halfWord[g[5]] : "");
  }
  function select(i, dots) {
    X.sel = i;
    (dots || X.dots || []).forEach(function (d, j) { d.setAttribute("r", j === i ? 10 : 7); });
    var g = X.data.teams[X.team].seasons[X.season].g[i];
    tap.hidden = false; tap.textContent = gameText(g);
  }
  function renderList(slug, season) {
    var ts = X.data.teams[slug].seasons[season];
    var G = ts.g.map(function (g, i) { return [g, i]; }).sort(function (a, b) { return a[0][2] - b[0][2] || a[1] - b[1]; });
    rowsEl.innerHTML = G.map(function (p) {
      var g = p[0];
      return '<tr><th scope="row" class="lb-tl">' + esc(dayText(g[0])) + " " + esc(venueWord(g[4])) + " " + esc(X.data.opps[g[1]]) + "</th><td>" + esc(spreadWords(g[2])) +
             '</td><td style="color:' + gradeColor(g[3]) + ';font-weight:600">' + esc(fmt(g[3])) + "</td><td>" + esc(halfWord[g[5]]) + "</td></tr>";
    }).join("");
    list.hidden = false;
  }
  function show(slug, season, how) {
    if (!X.data || !X.data.teams[slug]) {
      X.team = null; pickT.value = ""; pickS.innerHTML = ""; pickS.disabled = true; chart.hidden = true; tap.hidden = true; list.hidden = true;
      lead.innerHTML = '<p class="lb-xp-empty">Pick a team to see its tougher and easier halves, season by season.</p>';
      if (how !== "load") setURL(); return;
    }
    if (X.team !== slug) fillSeasons(slug);
    if (!X.data.teams[slug].seasons[season]) season = defaultSeason(slug);
    X.team = slug; X.season = season; X.sel = null; pickT.value = slug; pickS.value = season; tap.hidden = true;
    renderLead(slug, season); renderChart(slug, season); renderList(slug, season);
    if (how !== "load") { store.set(slug); setURL(); }
  }

  function initExplorer() {
    if (!pickT) return Promise.resolve();
    return fetch(D.explorer).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (j) {
      X.data = j;
      LATEST = Math.max.apply(null, [].concat.apply([], Object.keys(j.teams).map(function (s) { return Object.keys(j.teams[s].seasons).map(Number); })));
      fillTeams();
      var q = new URLSearchParams(window.location.search), qt = q.get("team"), qs = q.get("season");
      var slug = j.teams[qt] ? qt : (j.teams[store.get()] ? store.get() : null);
      show(slug, qs, "load");
      pickT.addEventListener("change", function () { show(pickT.value, null); });
      pickS.addEventListener("change", function () { show(X.team, pickS.value); });
      if (qt && j.teams[qt] && window.location.hash === "#your-team") { var t = el("your-team"); if (t) t.scrollIntoView(); }
    }).catch(function () {
      lead.innerHTML = '<p class="lb-xp-empty">The team data didn’t load. Refresh the page to try again.</p>';
    });
  }

  drawExhibits();
  var rw = null;
  window.addEventListener("resize", function () {
    clearTimeout(rw);
    rw = setTimeout(function () { drawExhibits(); if (X.team) { renderChart(X.team, X.season); } }, 120);
  });
  initExplorer().then(function () { document.body.setAttribute("data-ready", "1"); });
  window.DAWGLabOI = { show: function (s, y) { show(s, y); }, data: D, state: X };
})();
