/* Capitol Quest — Oʻahu overworld
 * Baked pixel-art iso map (see tools/) + Phaser camera/landmarks/UI.
 */

"use strict";

const DEEP_BLUE = "#1d4f8c";

/* ---------------------------------------------------------------- dialogue */
const Dialog = {
  el: null, nameEl: null, textEl: null,
  timer: null,
  init() {
    this.el = document.getElementById("dialog");
    this.nameEl = document.getElementById("dialog-name");
    this.textEl = document.getElementById("dialog-text");
    this.el.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      this.hide();
    });
  },
  show(name, text) {
    clearInterval(this.timer);
    this.nameEl.textContent = name;
    this.el.classList.remove("hidden");
    this.textEl.textContent = "";
    let i = 0;
    this.timer = setInterval(() => {
      i += 2;
      this.textEl.textContent = text.slice(0, i);
      if (i >= text.length) clearInterval(this.timer);
    }, 16);
  },
  hide() {
    clearInterval(this.timer);
    this.el.classList.add("hidden");
  },
};

/* ------------------------------------------------- radial flow (shared) */
/* Capitol-at-the-hub flow diagram used by both tabs of the money overlay:
   dir "out" drifts motes hub→node (budget), dir "in" node→hub (taxes).
   Node r ∝ √total; mote density ∝ dollars using the same Σ(rate ×
   duration) normalisation as the map streams. targetMotes is scaled per
   tab so dollars-per-mote MATCHES across the two views — the budget tab
   reading busier than the tax tab is the teaching point (federal funds
   and bond proceeds spend on top of state taxes). */
function buildRadialFlow(cfg) {
  const NS = "http://www.w3.org/2000/svg";
  const CX = 330, CY = 205, RX = 272, RY = 158;
  const SPEED = 62;            // svg units per second

  const mk = (tag, attrs) => {
    const el = document.createElementNS(NS, tag);
    for (const a in attrs) el.setAttribute(a, attrs[a]);
    return el;
  };

  const maxTotal = Math.max(...cfg.nodes.map((n) => n.total));
  const spokeG = mk("g", {});
  const moteG = mk("g", {});
  const nodeG = mk("g", {});
  cfg.svg.append(spokeG, moteG, nodeG);

  // hub: the Capitol sprite itself
  cfg.svg.append(mk("image", {
    href: "assets/sprites/capitol.png?v=1", x: CX - 56, y: CY - 46,
    width: 112, height: 86, preserveAspectRatio: "xMidYMid meet",
  }));
  const hubLabel = mk("text", { x: CX, y: CY + 58, class: "hub" });
  hubLabel.textContent = cfg.hubText;
  cfg.svg.append(hubLabel);

  const streams = [];
  cfg.nodes.forEach((n, i) => {
    const a = (i / cfg.nodes.length) * Math.PI * 2 - Math.PI / 2;
    const nx = CX + Math.cos(a) * RX;
    const ny = CY + Math.sin(a) * RY;
    // the spoke meets the hub outside the sprite, not under it
    const sx = CX + Math.cos(a) * 66;
    const sy = CY + Math.sin(a) * 52;
    const mx = (sx + nx) / 2 - Math.sin(a) * 26;
    const my = (sy + ny) / 2 + Math.cos(a) * 26;
    const r = Math.max(4.5, Math.min(23, 23 * Math.sqrt(n.total / maxTotal)));

    spokeG.append(mk("path", {
      class: "spoke", d: `M${sx},${sy} Q${mx},${my} ${nx},${ny}`,
    }));

    const node = mk("circle", {
      class: "node" + (n.onClick ? " drill" : ""), cx: nx, cy: ny, r,
    });
    // two label lines — name on top, dollar amount beneath
    const above = Math.sin(a) < -0.25;
    const label = mk("text", {
      class: "code", x: nx, y: ny + (above ? -r - (n.sub ? 17 : 6) : r + 11),
    });
    label.textContent = n.label;
    nodeG.append(node, label);
    if (n.sub) {
      const sub = mk("text", {
        class: "subv", x: nx, y: ny + (above ? -r - 6 : r + 22),
      });
      sub.textContent = n.sub;
      nodeG.append(sub);
    }
    // emoji badge inside the circle, when the circle is big enough
    if (n.icon && r >= 6.5) {
      const ic = mk("text", {
        class: "icon", x: nx, y: ny,
        "font-size": Math.max(10, Math.round(r * 1.3)),
      });
      ic.textContent = n.icon;
      nodeG.append(ic);
    }
    const show = () => {
      for (const el of nodeG.querySelectorAll(".node"))
        el.classList.remove("sel");
      node.classList.add("sel");
      cfg.detail.innerHTML = n.detail;
    };
    node.addEventListener("mouseenter", show);
    node.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      show();
      if (n.onClick) n.onClick();
    });

    const dist = Math.hypot(nx - sx, ny - sy);
    const hub = [sx, sy], rim = [nx, ny];
    const [p0, p2] = cfg.dir === "in" ? [rim, hub] : [hub, rim];
    for (const s of n.streams) {
      if (s.amt <= 0) continue;
      streams.push({
        p0, p1: [mx, my], p2,
        dur: Math.max(1.6, dist / SPEED),
        amt: s.amt, color: s.color, acc: Math.random(), rate: 0,
      });
    }
  });

  cfg.detail.innerHTML = cfg.defaultDetail;

  // density ∝ dollars: on-screen motes = Σ(rate × duration)
  const totalAmt = streams.reduce((s, x) => s + x.amt, 0);
  const wDur = streams.reduce(
    (s, x) => s + (x.amt / totalAmt) * x.dur, 0);
  const rateTotal = cfg.targetMotes / wDur;
  for (const s of streams) s.rate = rateTotal * (s.amt / totalAmt);

  const pool = [];
  for (let i = 0; i < Math.ceil(cfg.targetMotes * 1.4); i++) {
    const c = mk("circle", { class: "mote", r: 2.7, opacity: 0 });
    moteG.append(c);
    pool.push({ el: c, free: true, t: 0, s: null });
  }

  let last = 0;
  const frame = (now) => {
    const dt = last ? Math.min(0.05, (now - last) / 1000) : 0;
    last = now;
    if (cfg.isActive()) {
      for (const s of streams) {
        s.acc += s.rate * dt;
        while (s.acc >= 1) {
          s.acc -= 1;
          const m = pool.find((q) => q.free);
          if (!m) break;
          m.free = false;
          m.s = s;
          m.t = 0;
          // scatter: lateral spread for views with few, high-rate spokes
          m.ox = cfg.scatter ? (Math.random() * 2 - 1) * cfg.scatter : 0;
          m.oy = cfg.scatter ? (Math.random() * 2 - 1) * cfg.scatter : 0;
          m.el.setAttribute("fill", s.color);
        }
      }
      for (const m of pool) {
        if (m.free) continue;
        m.t += dt / m.s.dur;
        if (m.t >= 1) {
          m.free = true;
          m.el.setAttribute("opacity", 0);
          continue;
        }
        const t = m.t, u = 1 - t;
        const [ax, ay] = m.s.p0, [bx, by] = m.s.p1, [cx2, cy2] = m.s.p2;
        m.el.setAttribute(
          "cx", u * u * ax + 2 * u * t * bx + t * t * cx2 + m.ox);
        m.el.setAttribute(
          "cy", u * u * ay + 2 * u * t * by + t * t * cy2 + m.oy);
        m.el.setAttribute("opacity", 0.95 * Math.sin(Math.PI * t));
      }
    }
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

/* --------------------------------------------------------- money overlay */
/* One overlay, two tabs sharing the radial hub component: taxes flowing
   IN (FY2027 projected general-fund taxes, Council on Revenues) and the
   budget flowing OUT (FY2027 appropriations). Both toolbar buttons open
   it pre-selected to their tab; each tab keeps its ▤ List view, which
   carries the precise numbers. */
const MoneyPanel = {
  built: false,
  init(budget, revenue) {
    if (this.built || !budget || !revenue) return;
    this.built = true;
    const $ = (id) => document.getElementById(id);
    const overlay = $("money-overlay");

    const views = {
      revenue: { el: $("mv-revenue"), tab: $("mt-revenue") },
      budget: { el: $("mv-budget"), tab: $("mt-budget"),
                title: "State Budget · FY" + budget.fy },
    };
    let cur = "revenue";
    // money-in is two screens deep: the funding mix first, then a drill
    // into the taxes that fill the general fund
    let revSub = "sources";
    const subTitles = {
      sources: "Money In · FY" + budget.fy,
      taxes: "Taxes · FY" + revenue.fy +
        (revenue.projected ? " (projected)" : ""),
    };
    const setSub = (s) => {
      revSub = s;
      $("rv-sources").classList.toggle("hidden", s !== "sources");
      $("rv-taxes").classList.toggle("hidden", s !== "taxes");
      if (cur === "revenue")
        $("money-title").textContent = subTitles[s];
    };
    const setView = (v) => {
      cur = v;
      for (const k in views) {
        views[k].el.classList.toggle("hidden", k !== v);
        views[k].tab.classList.toggle("on", k === v);
      }
      if (v === "revenue") setSub("sources");   // always land on the split
      else $("money-title").textContent = views[v].title;
    };
    for (const k in views) {
      views[k].tab.addEventListener("pointerdown", (e) => {
        e.stopPropagation();
        setView(k);
      });
    }
    const wireToolbar = (btnId, view) => {
      $(btnId).addEventListener("pointerdown", (e) => {
        e.stopPropagation();
        if (!overlay.classList.contains("hidden") && cur === view) {
          overlay.classList.add("hidden");
        } else {
          setView(view);
          overlay.classList.remove("hidden");
          Dialog.hide();
        }
      });
    };
    wireToolbar("tb-budget", "budget");
    wireToolbar("tb-revenue", "revenue");
    $("money-close").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      overlay.classList.add("hidden");
    });
    overlay.addEventListener("pointerdown", (e) => {
      if (e.target === overlay) overlay.classList.add("hidden");
    });
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") overlay.classList.add("hidden");
    });

    const wireListToggle = (btnId, rowsId, mapId) => {
      const btn = $(btnId);
      btn.addEventListener("pointerdown", (e) => {
        e.stopPropagation();
        const listOn = $(rowsId).classList.toggle("hidden");
        $(mapId).classList.toggle("hidden", !listOn);
        btn.textContent = listOn ? "▤ List" : "◎ Map";
      });
    };
    // a map animates only while actually on screen — offsetParent is
    // null whenever the overlay, tab, sub-view or List toggle hides it
    const activeWhen = (mapId) => () => $(mapId).offsetParent !== null;

    this.buildSources(budget, $, activeWhen, () => setSub("taxes"));
    this.buildBudget(budget, $, wireListToggle, activeWhen);
    this.buildRevenue(revenue, budget, $, wireListToggle, activeWhen);
    $("rev-back").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      setSub("sources");
    });
    setView("revenue");
  },

  /* Money-in landing screen: the three kinds of money that pay for the
     budget, flowing into the Capitol. The General-funds node drills
     down into the tax mix. */
  buildSources(data, $, activeWhen, drill) {
    const fmt = (v) =>
      v >= 995e6 ? "$" + (v / 1e9).toFixed(v >= 9.95e9 ? 0 : 1) + "B" :
      v >= 1e6 ? "$" + Math.round(v / 1e6) + "M" :
      "$" + Math.round(v / 1e3) + "K";
    const fed = data.departments.reduce((s, d) => s + d.fed, 0);
    const other = data.departments.reduce((s, d) => s + d.other, 0);
    const gf = data.total - fed - other;
    const pct = (v) => Math.round(100 * v / data.total) + "%";

    const FUNDS = [
      { name: "General funds", icon: "💰", color: "#e3b64b", amt: gf,
        onClick: drill,
        who: "The state's own checkbook, filled almost entirely by the " +
          "taxes Hawaiʻi collects — GET, income tax and the rest. The " +
          "Legislature can spend it on anything. Tap the money bag to " +
          "see the taxes." },
      { name: "Federal funds", icon: "🦅", color: "#63a6f0", amt: fed,
        who: "Money from Washington tied to specific programs — the " +
          "Medicaid match, SNAP, highway and airport aid, disaster " +
          "relief. It arrives with rules attached, which is why some " +
          "departments feel federal budget fights." },
      { name: "All other funds", icon: "🧰", color: "#3fbf92", amt: other,
        who: "Money earmarked by law before it ever reaches the general " +
          "fund — special funds like the highway fund, university " +
          "tuition and harbor fees — plus bond borrowing for " +
          "construction." },
    ];

    $("sources-hero").innerHTML =
      "<b>" + fmt(data.total) + "</b> budget — paid for three ways" +
      "<small>" + fmt(gf) + " general funds (state taxes — tap to " +
      "explore) · " + fmt(fed) + " federal · " + fmt(other) +
      " special funds & bonds</small>";

    $("sources-foot").textContent =
      "Means of financing for the FY" + data.fy + " budget (operating + " +
      "capital), all departments. Source: " + data.source + ". General " +
      "funds are the taxes one screen deeper; federal and other money " +
      "is spent through the same departments but never passes through " +
      "the general fund.";

    buildRadialFlow({
      svg: $("sources-svg"),
      detail: $("sources-detail"),
      dir: "in",
      scatter: 7,                // 3 spokes run hot — spread the beads
      hubText: fmt(data.total) + " to spend",
      targetMotes: 110,          // same dollars-per-mote as money out
      isActive: activeWhen("sources-map"),
      defaultDetail: '<span class="dim">Three kinds of money pay for ' +
        "everything the state does. Hover one to see what it is — and " +
        "tap 💰 General funds to meet the taxes that fill it.</span>",
      nodes: FUNDS.map((f) => ({
        label: f.name,
        sub: fmt(f.amt) + " · " + pct(f.amt),
        icon: f.icon,
        total: f.amt,
        streams: [{ amt: f.amt, color: f.color }],
        onClick: f.onClick,
        detail: "<b>" + f.name + "</b> — <b>" + fmt(f.amt) + "</b> · " +
          pct(f.amt) + " of the budget<br>" +
          '<span class="dim">' + f.who + "</span>",
      })),
    });
  },

  buildBudget(data, $, wireListToggle, activeWhen) {
    const fmt = (v) =>
      v >= 995e6 ? "$" + (v / 1e9).toFixed(v >= 9.95e9 ? 0 : 1) + "B" :
      v >= 1e6 ? "$" + Math.round(v / 1e6) + "M" :
      "$" + Math.round(v / 1e3) + "K";

    $("budget-hero").innerHTML =
      "<b>" + fmt(data.total) + "</b> total — " + fmt(data.op) +
      " operating + " + fmt(data.cip) + " capital" +
      "<small>" + data.act + " · " + fmt(data.gfTotal) +
      " of it is general funds (mostly the taxes flowing into the " +
      "Capitol on the map)</small>";

    const rows = $("budget-rows");
    const max = data.departments[0].total;
    for (const d of data.departments) {
      const row = document.createElement("div");
      row.className = "brow";
      const share = (100 * d.total / data.total);
      const shareTxt = share >= 1 ? Math.round(share) + "%" :
        share >= 0.05 ? share.toFixed(1) + "%" : "<0.1%";
      const seg = (v, cls, label) => v / max * 100 < 0.15 ? "" :
        '<i class="' + cls + '" style="width:' + (v / max * 100) +
        '%" title="' + d.short + " — " + label + ": " + fmt(v) + '"></i>';
      row.innerHTML =
        '<span class="bname" title="' + d.name + '">' + d.short + "</span>" +
        '<span class="bbar">' +
        seg(d.gf, "sw-gf", "general funds") +
        seg(d.fed, "sw-fed", "federal funds") +
        seg(d.other, "sw-oth", "other funds") +
        "</span>" +
        '<span class="bval"><b>' + fmt(d.total) + "</b> · " + shareTxt +
        "</span>";
      rows.appendChild(row);
    }

    $("budget-foot").textContent =
      "Total budget (operating + capital) by department, FY2027, all " +
      "means of financing. Source: " + data.source + ". " +
      "Budget & Finance looks large because debt service and employee " +
      "benefits for the whole state government are paid through it.";

    wireListToggle("budget-view", "budget-rows", "budget-map");

    const pct = (v, d) => Math.round(100 * v / d.total) + "%";
    buildRadialFlow({
      svg: $("budget-svg"),
      detail: $("budget-detail"),
      dir: "out",
      hubText: fmt(data.total) + " appropriated",
      targetMotes: 110,          // steady-state, whole diagram
      isActive: activeWhen("budget-map"),
      defaultDetail: '<span class="dim">Hover a department to see its ' +
        "budget and where the money comes from. Gold motes are general " +
        "funds, blue federal, green everything else.</span>",
      nodes: data.departments.map((d) => ({
        label: d.code,
        sub: fmt(d.total),
        total: d.total,
        streams: [
          { amt: d.gf, color: "#e3b64b" },
          { amt: d.fed, color: "#63a6f0" },
          { amt: d.other, color: "#3fbf92" },
        ],
        detail:
          "<b>" + d.name + "</b> — <b>" + fmt(d.total) + "</b> · " +
          Math.round(d.positions).toLocaleString() + " positions<br>" +
          '<span class="dim">General ' + fmt(d.gf) + " (" + pct(d.gf, d) +
          ") · Federal " + fmt(d.fed) + " (" + pct(d.fed, d) +
          ") · Other " + fmt(d.other) + " (" + pct(d.other, d) + ")</span>",
      })),
    });
  },

  buildRevenue(data, budget, $, wireListToggle, activeWhen) {
    const fmtK = (v) =>            // amounts arrive in $ thousands
      v >= 995e3 ? "$" + (v / 1e6).toFixed(v >= 9.95e6 ? 1 : 2) + "B" :
      "$" + Math.round(v / 1e3) + "M";
    const shareTxt = (amt) => {
      const s = 100 * amt / data.total;
      return s >= 1 ? Math.round(s) + "%" : s.toFixed(1) + "%";
    };
    // node labels; the full names live in the detail box and the list
    const SHORT = {
      "General excise & use (GET)": "GET",
      "Individual income tax": "Income",
      "Transient accommodations (TAT)": "TAT",
      "Estate tax": "Estate",
      "Corporate income tax": "Corp",
      "Insurance premiums tax": "Insurance",
      "Public service companies": "Utilities",
      "Conveyance tax": "Convey",
      "Banks & financial corporations": "Banks",
      "Tobacco tax": "Tobacco",
      "Liquor tax": "Liquor",
      "All other taxes & fees": "Other",
    };
    // gold/teal match the island-map streams; green = not on the map
    const color = (t) =>
      t.stream === "income" ? "#e3b64b" :
      t.stream === "get" ? "#4fd8c8" : "#3fbf92";
    // badges for the bigger sources (small nodes skip theirs)
    const ICON = {
      "General excise & use (GET)": "🛒",
      "Individual income tax": "💵",
      "Transient accommodations (TAT)": "🏨",
      "Estate tax": "🏰",
      "Corporate income tax": "🏢",
      "Insurance premiums tax": "☂️",
      "Public service companies": "💡",
      "Conveyance tax": "🏠",
      "Banks & financial corporations": "🏦",
      "Tobacco tax": "🚬",
      "Liquor tax": "🍺",
      "All other taxes & fees": "📦",
    };

    $("revenue-hero").innerHTML =
      "<b>" + fmtK(data.total) + "</b> in state taxes projected to fill " +
      "the FY" + data.fy + " general fund" +
      "<small>Council on Revenues forecast, May 2026 · fees and other " +
      "nontax revenue add ~" + fmtK(data.gf_nontax) + " · taxes " +
      "collected for the counties, rail and the highway fund live " +
      "outside this pot</small>";

    const rows = $("revenue-rows");
    const max = data.taxes[0].amt;
    for (const t of data.taxes) {
      const row = document.createElement("div");
      row.className = "brow";
      row.title = t.who;
      const cls = t.stream === "income" ? "sw-gf"
        : t.stream === "get" ? "sw-get" : "sw-oth";
      row.innerHTML =
        '<span class="bname">' + t.name + (t.stream ? " ★" : "") + "</span>" +
        '<span class="bbar"><i class="' + cls +
        '" style="width:' + (100 * t.amt / max) + '%"></i></span>' +
        '<span class="bval"><b>' + fmtK(t.amt) + "</b> · " + shareTxt(t.amt) +
        "</span>";
      rows.appendChild(row);
    }

    $("revenue-foot").textContent =
      "Projected general-fund tax revenue by type, FY" + data.fy +
      ". Source: " + data.source +
      ". ★ marks the two taxes drawn on the island map (FY2025 " +
      "geography: income tax by ZIP, GET spread by where people live). " +
      "Not in this pot: the counties' GET surcharge (" +
      fmtK(data.county_surcharge) + ", mostly Honolulu rail) and " +
      "special-fund taxes (" + fmtK(data.special_fund_taxes) +
      " — fuel, rental cars, vehicle fees) that are earmarked before " +
      "they reach the general fund. The budget spends federal dollars " +
      "and bond proceeds on top of state taxes — same dollars-per-mote " +
      "scale on both tabs, so the busier budget map is honest.";

    wireListToggle("revenue-view", "revenue-rows", "revenue-map");

    // keep dollars-per-mote equal to the budget tab (110 motes ≙ $24.8B)
    const target = Math.round(110 * (data.total * 1e3) / budget.total);

    buildRadialFlow({
      svg: $("revenue-svg"),
      detail: $("revenue-detail"),
      dir: "in",
      hubText: fmtK(data.total) +
        (data.projected ? " projected" : " collected"),
      targetMotes: target,
      isActive: activeWhen("revenue-map"),
      defaultDetail: '<span class="dim">Hover a tax to see what it is ' +
        "projected to raise and who pays it. Gold motes are the income " +
        "tax and teal the GET — the two streams drawn on the island map " +
        "— green everything else.</span>",
      nodes: data.taxes.map((t) => ({
        label: SHORT[t.name] || t.name.split(" ")[0],
        sub: fmtK(t.amt),
        icon: ICON[t.name],
        total: t.amt,
        streams: [{ amt: t.amt, color: color(t) }],
        detail:
          "<b>" + t.name + "</b> — <b>" + fmtK(t.amt) + "</b> · " +
          shareTxt(t.amt) + " of general-fund taxes<br>" +
          '<span class="dim">' + t.who + "</span>",
      })),
    });
  },
};

/* -------------------------------------------------------- policy overlay */
/* The core game loop: pick spending priorities, then pass the revenue to
   pay for them. Amounts arrive in $ thousands/yr (policies.json,
   hand-curated with a per-item source shown as the row tooltip). Enacted
   policies move the FY2027 budget scoreboard in the bottom-right corner:
   priorities spend from it, revenue policies add to it. Choices persist
   in localStorage. Must init AFTER MoneyPanel so the tb-budget/tb-revenue
   listeners here run in addition to (not instead of) MoneyPanel's. */
const PolicyPanel = {
  built: false,
  external: 0,                 // $K/yr from session decisions (SessionPanel)
  setExternal(k) {
    this.external = k || 0;
    if (this._updateChip) this._updateChip();
  },
  init(budget, data) {
    if (this.built || !budget || !data) return;
    this.built = true;
    const $ = (id) => document.getElementById(id);
    const overlay = $("policy-overlay");
    const fmtK = (v) => {            // $ thousands → compact dollars
      if (!v) return "$0";
      const d = Math.abs(v) * 1e3;
      return d >= 995e6 ? "$" + (d / 1e9).toFixed(1) + "B" :
        "$" + Math.round(d / 1e6) + "M";
    };
    const fmtB = (v) => "$" + (v / 1e9).toFixed(2) + "B";

    // enacted policy ids survive reloads (ignore ids that no longer exist)
    const KEY = "cq-policies";
    const known = new Set(
      [...data.priorities, ...data.revenue].map((p) => p.id));
    let enacted;
    try {
      enacted = new Set(JSON.parse(localStorage.getItem(KEY) || "[]")
        .filter((id) => known.has(id)));
    } catch (e) { enacted = new Set(); }
    const save = () => {
      try { localStorage.setItem(KEY, JSON.stringify([...enacted])); }
      catch (e) { /* private mode — choices last the session only */ }
    };
    const sum = (list) => list.filter((p) => enacted.has(p.id))
      .reduce((s, p) => s + p.amt, 0);

    /* budget scoreboard, bottom right */
    const chip = $("fund-chip");
    const updateChip = () => {
      const spent = sum(data.priorities);
      const raised = sum(data.revenue);
      const sess = PolicyPanel.external;             // session decisions, $K
      const delta = (raised - spent + sess) * 1e3;   // dollars
      chip.innerHTML =
        '<span class="fc-label">FY' + budget.fy + " budget</span>" +
        '<span class="fc-amt">' + fmtB(budget.total + delta) + "</span>" +
        // the consequence line: balance vs the enacted Act 175 figure
        (spent || raised || sess ? '<span class="fc-bal ' +
          (delta < 0 ? "cost" : delta > 0 ? "gain" : "even") + '">' +
          (delta < 0 ? "▼ " + fmtK(-delta / 1e3) + " deficit" :
           delta > 0 ? "▲ " + fmtK(delta / 1e3) + " surplus" :
           "● balanced") + "</span>" : "");
      chip.title =
        "Act 175 (2026): " + fmtB(budget.op) + " operating + " +
        fmtB(budget.cip) + " capital = " + fmtB(budget.total) + "." +
        (spent || raised || sess
          ? "\nYour policies: −" + fmtK(spent) + "/yr invested, +" +
            fmtK(raised) + "/yr new revenue." +
            (sess ? "\nSession decisions: " + (sess > 0 ? "+" : "−") +
              fmtK(Math.abs(sess)) + "/yr." : "") +
            "\n→ " +
            (delta < 0 ? "a " + fmtK(-delta / 1e3) + " hole to fill." :
             delta > 0 ? fmtK(delta / 1e3) + " left over." :
             "exactly balanced.")
          : "\nOpen Policies to invest in priorities — and to raise " +
            "the revenue that pays for them.");
    };
    this._updateChip = updateChip;

    const updateHeros = () => {
      const spent = sum(data.priorities);
      const raised = sum(data.revenue);
      $("prio-hero").innerHTML =
        "<b>" + fmtK(spent) + "/yr</b> invested in what comes next" +
        "<small>Tap Enact to fund a priority. Spending lands on the " +
        "budget scoreboard (bottom right) — cover it from the 💵 Raise " +
        "revenue tab.</small>";
      $("rpol-hero").innerHTML =
        "<b>+" + fmtK(raised) + "/yr</b> in new revenue" +
        "<small>Every option is a real proposal with a real trade-off — " +
        "who pays is as important as how much.</small>";
    };

    const buildRows = (list, rowsEl, kind) => {
      for (const p of list) {
        const row = document.createElement("div");
        row.className = "prow" + (enacted.has(p.id) ? " on" : "");
        row.title = "Source: " + p.src;
        row.innerHTML =
          '<span class="pname"><b>' + p.icon + " " + p.name +
          "</b><small>" + p.who + "</small></span>" +
          '<span class="ptag ' + kind + '">' +
          (kind === "cost" ? "−" : "+") + fmtK(p.amt) + "/yr</span>" +
          '<button class="pgo" type="button"></button>';
        const btn = row.querySelector(".pgo");
        const paint = () => {
          const on = enacted.has(p.id);
          row.classList.toggle("on", on);
          btn.textContent = on ? "✓ Passed" : "Enact";
          btn.title = on ? "Tap to repeal" : "";
        };
        btn.addEventListener("pointerdown", (e) => {
          e.stopPropagation();
          if (enacted.has(p.id)) enacted.delete(p.id);
          else enacted.add(p.id);
          save();
          paint();
          updateChip();
          updateHeros();
        });
        paint();
        rowsEl.appendChild(row);
      }
    };
    buildRows(data.priorities, $("prio-rows"), "cost");
    buildRows(data.revenue, $("rpol-rows"), "gain");

    $("prio-foot").textContent =
      "Price tags are annual, FY2027 scale — Hawaiʻi Appleseed and " +
      "Budget Primer analyses (hover a row for its source). Spending " +
      "here is stylized: real appropriations go through the " +
      "legislature's budget bill.";
    $("rpol-foot").textContent =
      "Revenue estimates are annual — Budget Primer tax-fairness " +
      "analyses and ITEP (hover a row for its source). The GET is the " +
      "biggest lever but the most regressive; the reforms below it " +
      "raise money from those most able to pay.";

    /* tabs + open/close */
    $("policy-title").textContent = "Policies · FY" + budget.fy;
    const views = {
      priorities: { el: $("pv-priorities"), tab: $("pt-priorities") },
      revenue: { el: $("pv-revenue"), tab: $("pt-revenue") },
    };
    const setView = (v) => {
      for (const k in views) {
        views[k].el.classList.toggle("hidden", k !== v);
        views[k].tab.classList.toggle("on", k === v);
      }
    };
    for (const k in views) {
      views[k].tab.addEventListener("pointerdown", (e) => {
        e.stopPropagation();
        setView(k);
      });
    }
    const open = () => {
      $("money-overlay").classList.add("hidden");
      overlay.classList.remove("hidden");
      Dialog.hide();
    };
    $("tb-policy").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      if (overlay.classList.contains("hidden")) open();
      else overlay.classList.add("hidden");
    });
    chip.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      open();
    });
    // the money-overlay toolbar buttons close this overlay (their own
    // handlers stopPropagation, but same-element listeners still run)
    for (const id of ["tb-budget", "tb-revenue"]) {
      $(id).addEventListener("pointerdown", () =>
        overlay.classList.add("hidden"));
    }
    $("policy-close").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      overlay.classList.add("hidden");
    });
    overlay.addEventListener("pointerdown", (e) => {
      if (e.target === overlay) overlay.classList.add("hidden");
    });
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") overlay.classList.add("hidden");
    });

    setView("priorities");
    updateChip();
    updateHeros();
  },
};

/* -------------------------------------------------------- session panel */
/* The disco-flavored core loop. Time passes in TURNS — one turn = one
   week of the legislative session. Each week: an event dialogue pops
   (the two tax traits, PROGRESSIVE and CONSERVATIVE, chime in on
   everything), you can talk story with characters freely, and you get
   exactly ONE action (rally / lobby). Week 0 is the week before session:
   pick up to three bills from policies.json to introduce — that agenda
   IS your session. Decisions move three metrics: Revenue ($K/yr, wired
   into the budget scoreboard via PolicyPanel.setExternal), Working
   Families and The Wealthy & Businesses (0–100 opinion). All content is
   data-driven from map/session.json; the thought cabinet bolts on next. */
const SessionPanel = {
  built: false,
  init(budget, policies, data) {
    if (this.built || !budget || !policies || !data) return;
    this.built = true;
    const $ = (id) => document.getElementById(id);
    const overlay = $("session-overlay");
    const body = $("sess-body");
    const fmtK = (v) => {
      if (!v) return "$0";
      const d = Math.abs(v) * 1e3;
      return d >= 995e6 ? "$" + (d / 1e9).toFixed(1) + "B" :
        "$" + Math.round(d / 1e6) + "M";
    };
    const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");

    /* ---- turn state */
    const KEY = "cq-session";
    const defaults = () => ({
      week: 0, actionWeek: -1, agendaLocked: false, agenda: [],
      eventDone: [], talked: {}, log: [],
      metrics: { revenueK: 0, families: 50, wealthy: 50 },
    });
    let S = defaults();
    try {
      S = Object.assign(defaults(),
        JSON.parse(localStorage.getItem(KEY) || "{}"));
      S.metrics = Object.assign(defaults().metrics, S.metrics);
    } catch (e) { /* fresh campaign */ }
    const save = () => {
      try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {}
    };
    const allPolicies = [
      ...policies.priorities.map((p) => ({ ...p, kind: "cost" })),
      ...policies.revenue.map((p) => ({ ...p, kind: "gain" })),
    ];

    /* ---- calendar */
    const calFor = (w) => {
      const hit = data.calendar.find((c) => c.week === w) || {};
      return {
        week: w,
        title: hit.title || data.weekTitles[w] || "Interim",
        phase: hit.phase || (w === 0 ? "Pre-session" :
          w >= data.sineDieWeek ? "Adjournment" :
          w >= 14 ? "Conference" : "Session"),
        event: hit.event !== undefined ? hit.event :
          (w >= 2 && w < data.sineDieWeek
            ? data.genericEvents[(w - 2) % data.genericEvents.length]
            : null),
        agenda: !!hit.agenda,
        noAction: !!hit.noAction || w > data.sineDieWeek,
        talks: hit.talks ||
          (w >= 1 && w <= data.sineDieWeek ? data.talkDefaults : {}),
      };
    };

    /* ---- metrics */
    const clamp = (v) => Math.max(0, Math.min(100, v));
    const applyFx = (fx) => {
      if (!fx) return "";
      const parts = [];
      if (fx.revenueK) {
        S.metrics.revenueK += fx.revenueK;
        parts.push('<span class="' + (fx.revenueK > 0 ? "gain" : "cost") +
          '">' + (fx.revenueK > 0 ? "+" : "−") +
          fmtK(Math.abs(fx.revenueK)) + "/yr revenue</span>");
      }
      if (fx.families) {
        S.metrics.families = clamp(S.metrics.families + fx.families);
        parts.push('<span class="' + (fx.families > 0 ? "gain" : "cost") +
          '">Working Families ' + (fx.families > 0 ? "+" : "") +
          fx.families + "</span>");
      }
      if (fx.wealthy) {
        S.metrics.wealthy = clamp(S.metrics.wealthy + fx.wealthy);
        parts.push('<span class="' + (fx.wealthy > 0 ? "gain" : "cost") +
          '">The Wealthy &amp; Businesses ' +
          (fx.wealthy > 0 ? "+" : "") + fx.wealthy + "</span>");
      }
      PolicyPanel.setExternal(S.metrics.revenueK);
      save();
      renderHead();
      return parts.length ? '<div class="sd-fx">' +
        parts.join(" · ") + "</div>" : "";
    };

    /* ---- header + metrics bar */
    const renderHead = () => {
      const cal = calFor(S.week);
      $("session-title").textContent = "Session · Week " + S.week;
      $("tb-week-badge").textContent = "W" + S.week;
      $("sess-week").innerHTML =
        "<b>Week " + S.week + " — " + esc(cal.title) + "</b>" +
        "<small>" + esc(cal.phase) + " · one action per week</small>";
      const rev = S.metrics.revenueK;
      $("sess-metrics").innerHTML =
        '<span class="met m-rev ' + (rev < 0 ? "cost" : "gain") + '">💰 ' +
        "Revenue <b>" + (rev < 0 ? "−" : "+") + fmtK(Math.abs(rev)) +
        "/yr</b></span>" +
        '<span class="met m-fam">👪 Working Families <b>' +
        S.metrics.families + '</b><span class="bar"><i style="width:' +
        S.metrics.families + '%"></i></span></span>' +
        '<span class="met m-rich">🎩 The Wealthy &amp; Businesses <b>' +
        S.metrics.wealthy + '</b><span class="bar"><i style="width:' +
        S.metrics.wealthy + '%"></i></span></span>';
    };

    /* ---- dialogue runner (trait voices chime in on every node) */
    const voiceHtml = (voices) => (voices || []).map((v) => {
      const tr = data.traits[v.t];
      return '<div class="sd-voice v-' + v.t + '"><b>' + tr.name +
        " (" + tr.sub.toUpperCase() + ")</b> — " + esc(v.text) + "</div>";
    }).join("");

    const showDialogue = (dlgId, onDone) => {
      const dlg = data.dialogues[dlgId];
      if (!dlg) { onDone(); return; }
      const renderNode = (nodeId) => {
        const n = dlg[nodeId];
        const who = data.characters[n.speaker];
        let html =
          '<div class="sd-speaker"><b>' + who.icon + " " +
          esc(who.name) + "</b><small>" + esc(who.role) + "</small></div>" +
          '<div class="sd-text">' + esc(n.text) + "</div>" +
          voiceHtml(n.voices) +
          '<div class="sd-choices">' +
          n.choices.map((c, i) =>
            '<button type="button" data-i="' + i + '">' + esc(c.label) +
            "</button>").join("") +
          "</div>";
        body.innerHTML = html;
        body.scrollTop = 0;
        for (const btn of body.querySelectorAll(".sd-choices button")) {
          btn.addEventListener("pointerdown", (ev) => {
            ev.stopPropagation();
            const c = n.choices[+btn.dataset.i];
            const fxHtml = applyFx(c.effects);
            S.log.push({ week: S.week, dlg: dlgId, choice: c.label });
            save();
            body.querySelector(".sd-choices").outerHTML =
              '<div class="sd-reply">▸ ' + esc(c.label) + "</div>" +
              (c.reply ? '<div class="sd-reply">' + esc(c.reply) +
                "</div>" : "") + fxHtml +
              (c.goto
                ? '<button class="sd-done" data-goto="' + c.goto +
                  '" type="button">Continue ▸</button>'
                : '<button class="sd-done" type="button">Continue ▸' +
                  "</button>");
            const done = body.querySelector(".sd-done");
            done.addEventListener("pointerdown", (ev2) => {
              ev2.stopPropagation();
              if (done.dataset.goto) renderNode(done.dataset.goto);
              else onDone();
            });
          });
        }
      };
      renderNode("start");
    };

    /* ---- the week hub */
    const renderHub = () => {
      const cal = calFor(S.week);
      const interim = S.week > data.sineDieWeek;
      let html = "";

      // this week's event
      if (cal.event) {
        const done = S.eventDone.includes(S.week);
        html += '<div class="sh-sec">This week</div>';
        html += '<div class="sh-row' + (done ? " done" : "") +
          '" data-ev="1"><span class="shname"><b>📰 ' +
          (done ? "The week's event — handled" :
            "Something needs your attention") +
          "</b><small>" + (done ? "Choices made. The week rolls on." :
            "An event is waiting — the traits have opinions.") +
          "</small></span>" +
          '<button class="shgo" type="button"' + (done ? " disabled" : "") +
          ">" + (done ? "✓ Done" : "Open ▸") + "</button></div>";
      }

      // week-0 agenda picker (up to 3 bills)
      if (cal.agenda && !S.agendaLocked) {
        html += '<div class="sh-sec">Your bill package</div>' +
          '<div class="sh-agenda-cap">Choose up to 3 bills to introduce ' +
          "— this agenda is your session.</div>";
        for (const p of allPolicies) {
          const on = S.agenda.includes(p.id);
          html += '<div class="sh-row" data-pol="' + p.id +
            '"><span class="shname"><b>' + p.icon + " " + esc(p.name) +
            '</b></span><span class="shtag ' + p.kind + '">' +
            (p.kind === "cost" ? "−" : "+") + fmtK(p.amt) + "/yr</span>" +
            '<button class="shgo" type="button">' +
            (on ? "✓ In" : "Add") + "</button></div>";
        }
        html += '<button class="sh-week-end" id="sess-lock" type="button"' +
          (S.agenda.length ? "" : " disabled") + ">Introduce " +
          (S.agenda.length || "your") + " bill" +
          (S.agenda.length === 1 ? "" : "s") + " ▸</button>";
      } else if (S.agendaLocked && S.agenda.length) {
        html += '<div class="sh-sec">Your bills</div>';
        for (const id of S.agenda) {
          const p = allPolicies.find((q) => q.id === id);
          if (p) {
            html += '<div class="sh-row"><span class="shname"><b>' +
              p.icon + " " + esc(p.name) + '</b></span><span class="shtag ' +
              p.kind + '">' + (p.kind === "cost" ? "−" : "+") +
              fmtK(p.amt) + "/yr</span></div>";
          }
        }
      }

      // talk story
      const talkIds = Object.keys(cal.talks || {});
      if (talkIds.length) {
        html += '<div class="sh-sec">Talk story (free)</div>';
        for (const cid of talkIds) {
          const who = data.characters[cid];
          const talked = (S.talked[S.week] || []).includes(cid);
          html += '<div class="sh-row' + (talked ? " done" : "") +
            '" data-talk="' + cid + '"><span class="shname"><b>' +
            who.icon + " " + esc(who.name) + "</b><small>" +
            esc(who.role) + "</small></span>" +
            '<button class="shgo" type="button">' +
            (talked ? "Again ▸" : "Talk ▸") + "</button></div>";
        }
      }

      // the one action
      if (!cal.noAction && !interim) {
        const used = S.actionWeek === S.week;
        html += '<div class="sh-sec">Your action (' +
          (used ? "used this week" : "one per week") + ")</div>";
        for (const aid of Object.keys(data.actions)) {
          const a = data.actions[aid];
          html += '<div class="sh-row" data-act="' + aid +
            '"><span class="shname"><b>' + a.icon + " " + esc(a.name) +
            "</b><small>" + esc(a.desc) + "</small></span>" +
            '<button class="shgo" type="button"' +
            (used ? " disabled" : "") + ">" +
            (used ? "—" : "Act ▸") + "</button></div>";
        }
      }

      // end of week
      if (interim) {
        html += '<div class="sh-sec">Interim</div>' +
          '<div class="sh-agenda-cap">The session is adjourned sine die. ' +
          "What your choices did arrives with the next module.</div>";
      } else if (!(cal.agenda && !S.agendaLocked)) {
        const skipping = !cal.noAction && S.actionWeek !== S.week;
        html += '<button class="sh-week-end" id="sess-next" type="button">' +
          (S.week === data.sineDieWeek ? "Leave the building ▸" :
            "End Week " + S.week + " ▸") + "</button>" +
          (skipping ? '<div class="sh-agenda-cap">Your action is ' +
            "unused — ending the week skips it.</div>" : "");
      }

      body.innerHTML = html;
      body.scrollTop = 0;

      // wiring
      const evRow = body.querySelector('[data-ev] .shgo:not([disabled])');
      if (evRow) evRow.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        runEvent();
      });
      for (const r of body.querySelectorAll("[data-pol]")) {
        r.querySelector(".shgo").addEventListener("pointerdown", (ev) => {
          ev.stopPropagation();
          const id = r.dataset.pol;
          if (S.agenda.includes(id)) {
            S.agenda = S.agenda.filter((x) => x !== id);
          } else if (S.agenda.length < 3) {
            S.agenda.push(id);
          }
          save();
          renderHub();
        });
      }
      const lock = body.querySelector("#sess-lock");
      if (lock) lock.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        if (!S.agenda.length) return;
        S.agendaLocked = true;
        S.log.push({ week: 0, agenda: [...S.agenda] });
        save();
        renderHub();
      });
      for (const r of body.querySelectorAll("[data-talk]")) {
        r.querySelector(".shgo").addEventListener("pointerdown", (ev) => {
          ev.stopPropagation();
          const cid = r.dataset.talk;
          (S.talked[S.week] = S.talked[S.week] || []).push(cid);
          save();
          showDialogue(cal.talks[cid], renderHub);
        });
      }
      for (const r of body.querySelectorAll("[data-act]")) {
        const btn = r.querySelector(".shgo");
        if (btn.disabled) continue;
        btn.addEventListener("pointerdown", (ev) => {
          ev.stopPropagation();
          runAction(r.dataset.act);
        });
      }
      const next = body.querySelector("#sess-next");
      if (next) next.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        advanceWeek();
      });
    };

    const runEvent = () => {
      const cal = calFor(S.week);
      showDialogue(cal.event, () => {
        if (!S.eventDone.includes(S.week)) S.eventDone.push(S.week);
        save();
        renderHub();
      });
    };

    const runAction = (aid) => {
      const a = data.actions[aid];
      S.actionWeek = S.week;
      const fxHtml = applyFx(a.effects);
      S.log.push({ week: S.week, action: aid });
      save();
      body.innerHTML =
        '<div class="sd-speaker"><b>' + a.icon + " " + esc(a.name) +
        "</b><small>your action this week</small></div>" +
        '<div class="sd-text">' + esc(a.result) + "</div>" +
        voiceHtml(a.voices) + fxHtml +
        '<button class="sd-done" type="button">Continue ▸</button>';
      body.querySelector(".sd-done").addEventListener("pointerdown",
        (ev) => { ev.stopPropagation(); renderHub(); });
    };

    const advanceWeek = () => {
      if (S.week > data.sineDieWeek) return;
      S.week += 1;
      save();
      renderHead();
      const cal = calFor(S.week);
      if (cal.event && !S.eventDone.includes(S.week)) runEvent();
      else renderHub();
    };

    /* ---- overlay plumbing */
    const openOverlay = () => {
      $("money-overlay").classList.add("hidden");
      $("policy-overlay").classList.add("hidden");
      overlay.classList.remove("hidden");
      Dialog.hide();
    };
    $("tb-session").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      if (overlay.classList.contains("hidden")) {
        openOverlay();
        const cal = calFor(S.week);
        if (cal.event && !S.eventDone.includes(S.week)) runEvent();
        else renderHub();
      } else overlay.classList.add("hidden");
    });
    // the other overlays' buttons close this one
    for (const id of ["tb-budget", "tb-revenue", "tb-policy",
                      "fund-chip"]) {
      $(id).addEventListener("pointerdown", () =>
        overlay.classList.add("hidden"));
    }
    $("session-close").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      overlay.classList.add("hidden");
    });
    overlay.addEventListener("pointerdown", (e) => {
      if (e.target === overlay) overlay.classList.add("hidden");
    });
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") overlay.classList.add("hidden");
    });
    $("sess-foot").innerHTML =
      "One turn = one week of the legislative session. Events and " +
      "dialogues are illustrative; the fiscal numbers they move ride " +
      "the same FY2027 scoreboard as your policy bills. Characters are " +
      "fictional. <button id=\"sess-reset\" type=\"button\" " +
      "style=\"background:none;border:none;color:#9fb0e8;" +
      "text-decoration:underline;cursor:pointer;font:inherit;" +
      "padding:0\">Restart session</button>";
    $("sess-reset").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      const b = e.target;
      if (b.dataset.arm) {
        S = defaults();
        save();
        PolicyPanel.setExternal(0);
        renderHead();
        runEvent();
      } else {
        b.dataset.arm = "1";
        b.textContent = "Really restart? (tap again)";
        setTimeout(() => {
          b.dataset.arm = "";
          b.textContent = "Restart session";
        }, 2500);
      }
    });

    /* ---- boot: reflect saved revenue, pop the week if it's unplayed */
    PolicyPanel.setExternal(S.metrics.revenueK);
    renderHead();
    const cal0 = calFor(S.week);
    if ((cal0.event && !S.eventDone.includes(S.week)) ||
        (cal0.agenda && !S.agendaLocked)) {
      openOverlay();
      if (cal0.event && !S.eventDone.includes(S.week)) runEvent();
      else renderHub();
    }
  },
};

/* -------------------------------------------------------- island fly-to */
/* The "· Oʻahu ▾" tag on the title chip opens a list of all eight
   islands; picking one flies the camera there — it's ONE continuous map,
   so this is navigation, not a scene switch. The chip label tracks
   whichever island the camera is over ("Hawaiʻi" over open water). */
const IslandUI = {
  built: false,
  scene: null,
  init(scene) {
    this.scene = scene;
    if (this.built) return;
    this.built = true;
    const chip = document.getElementById("island-chip");
    const menu = document.getElementById("island-menu");
    const world = scene.cache.json.get("world");
    if (!world) return;
    for (const isl of world.islands) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = isl.name;
      b.dataset.slug = isl.slug;
      b.addEventListener("pointerdown", (e) => {
        e.stopPropagation();
        menu.classList.add("hidden");
        this.scene.flyTo(isl.slug);
      });
      menu.appendChild(b);
    }
    chip.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      menu.classList.toggle("hidden");
    });
    window.addEventListener("pointerdown", () =>
      menu.classList.add("hidden"));
  },
  update(current) {
    document.getElementById("island-chip").textContent =
      "· " + (current ? current.name : "Hawaiʻi") + " ▾";
    for (const b of document.querySelectorAll("#island-menu button")) {
      b.classList.toggle("on",
        !!current && b.dataset.slug === current.slug);
    }
  },
};

/* ---------------------------------------------------------------- scenes */
class BootScene extends Phaser.Scene {
  constructor() { super("boot"); }
  preload() {
    this.load.json("world", "map/world.json?v=1");
    this.load.json("meta_oahu", "map/oahu.json?v=1");
    this.load.json("flows", "map/tax_flows.json?v=1");
    this.load.json("budget", "map/budget.json?v=1");
    this.load.json("revenue", "map/revenue.json?v=1");
    this.load.json("get_flows", "map/get_flows.json?v=1");
    this.load.json("policies", "map/policies.json?v=1");
    this.load.json("session", "map/session.json?v=1");
  }
  create() {
    const world = this.cache.json.get("world");
    this.load.image("overview",
                    "assets/map/" + world.overview.file + "?v=1");
    // Oʻahu is preloaded — the intro dives into the Capitol
    const oahu = this.cache.json.get("meta_oahu");
    for (const s of oahu.slices) {
      this.load.image("map_" + s.file, "assets/map/" + s.file + "?v=1");
    }
    this.load.image("capitol", "assets/sprites/capitol.png?v=1");
    this.load.image("marker", "assets/sprites/marker.png?v=1");
    for (let i = 0; i < 3; i++) {
      this.load.image("sp" + i, `assets/sprites/sparkle_${i}.png?v=1`);
    }
    this.load.once("complete", () => this.scene.start("world", world));
    this.load.start();
  }
}

class WorldScene extends Phaser.Scene {
  constructor() { super("world"); }

  create(world) {
    this.world = world;
    this.cameras.main.setBackgroundColor(DEEP_BLUE);
    this.cameras.main.setBounds(0, 0, world.w, world.h);

    // zoomed-out backdrop: 1/12-scale stitch of all eight bakes,
    // upscaled — detailed island slices layer over it as you approach
    this.add.image(0, 0, "overview").setOrigin(0, 0)
      .setScale(world.overview.scale).setDepth(-2);

    this.labels = [];
    this.isl = {};                 // slug -> lazy island state
    if (!this.anims.exists("sparkle")) {
      this.anims.create({
        key: "sparkle",
        frames: [{ key: "sp0" }, { key: "sp1" }, { key: "sp2" },
                 { key: "sp1" }, { key: "sp0" }],
        frameRate: 7,
      });
    }
    for (const e of world.islands) {
      this.makeLabel("island", e.name,
                     e.anchor[0] + e.w * e.scale / 2,
                     e.anchor[1] + e.h * e.scale / 2);
    }
    this.buildCapitol(world);
    this.buildFlows(world);
    MoneyPanel.init(
      this.cache.json.get("budget"), this.cache.json.get("revenue"));
    PolicyPanel.init(
      this.cache.json.get("budget"), this.cache.json.get("policies"));
    SessionPanel.init(
      this.cache.json.get("budget"), this.cache.json.get("policies"),
      this.cache.json.get("session"));
    IslandUI.init(this);

    this.setupCamera(world);
    this.setupInput();

    this.ensureIsland("oahu");     // slices preloaded by BootScene
    this.time.addEvent({ delay: 400, loop: true,
                         callback: () => this.manageIslands() });
    this.scale.on("resize", () => {
      this.recomputeMinZoom();
      this.applyLabelScale();
    });
  }

  /* ---- lazy island manager: detailed slices, labels and sparkles load
     when the camera is near and zoomed in; they unload (textures freed)
     when far, leaving the overview backdrop. */
  islandRect(e, grow = 0) {
    return new Phaser.Geom.Rectangle(
      e.anchor[0] - grow, e.anchor[1] - grow,
      e.w * e.scale + 2 * grow, e.h * e.scale + 2 * grow);
  }

  manageIslands() {
    const cam = this.cameras.main;
    const view = cam.worldView;
    const pad = Math.max(view.width, view.height) * 0.5;
    let current = null;
    for (const e of this.world.islands) {
      const st = this.isl[e.slug];
      const nearR = this.islandRect(e, pad);
      const wanted = cam.zoom > 0.06 &&
        Phaser.Geom.Rectangle.Contains(nearR, view.centerX, view.centerY) ||
        (cam.zoom > 0.06 && Phaser.Geom.Rectangle.Overlaps(
          this.islandRect(e), view));
      if (wanted && !st) this.ensureIsland(e.slug);
      else if (!wanted && st && st.state === "on" &&
               (cam.zoom <= 0.05 ||
                !Phaser.Geom.Rectangle.Overlaps(
                  this.islandRect(e, pad * 4), view))) {
        this.unloadIsland(e.slug);
      }
      if (Phaser.Geom.Rectangle.Contains(
            this.islandRect(e), view.centerX, view.centerY)) {
        current = e;
      }
    }
    IslandUI.update(current);
  }

  ensureIsland(slug) {
    if (this.isl[slug]) return;
    this.isl[slug] = { state: "loading", imgs: [], labels: [],
                       sparkles: [], timers: [] };
    const e = this.world.islands.find((i) => i.slug === slug);
    const key = "meta_" + slug;
    const step2 = () => {
      const meta = this.cache.json.get(key);
      const need = meta.slices.filter(
        (s) => !this.textures.exists("map_" + s.file));
      if (!need.length) { this.addIsland(e, meta); return; }
      for (const s of need) {
        this.load.image("map_" + s.file, "assets/map/" + s.file + "?v=1");
      }
      this.load.once("complete", () => this.addIsland(e, meta));
      this.load.start();
    };
    if (this.cache.json.exists(key)) step2();
    else {
      this.load.json(key, "map/" + slug + ".json?v=1");
      this.load.once("complete", step2);
      this.load.start();
    }
  }

  addIsland(e, meta) {
    const st = this.isl[e.slug];
    if (!st || st.state !== "loading") return;   // unloaded while loading
    st.state = "on";
    for (const s of meta.slices) {
      st.imgs.push(this.add.image(
        e.anchor[0] + s.x * e.scale, e.anchor[1] + s.y * e.scale,
        "map_" + s.file).setOrigin(0, 0).setScale(e.scale).setDepth(-1));
    }
    for (const lm of meta.landmarks) {
      st.labels.push(this.makeLabel(
        lm.kind, lm.name,
        e.anchor[0] + lm.px * e.scale, e.anchor[1] + lm.py * e.scale,
        lm.kind === "capitol" ? 26 : 0));
    }
    const pts = Phaser.Utils.Array.Shuffle(meta.sparkles.slice())
      .slice(0, 90);
    for (const [x, y] of pts) {
      const sp = this.add.sprite(
        e.anchor[0] + x * e.scale, e.anchor[1] + y * e.scale, "sp0")
        .setDepth(2).setAlpha(0.9);
      st.sparkles.push(sp);
      st.timers.push(this.time.addEvent({
        delay: 1200 + Math.random() * 5200,
        loop: true,
        callback: () => sp.play("sparkle"),
      }));
    }
    this.applyLabelScale();
  }

  unloadIsland(slug) {
    const st = this.isl[slug];
    if (!st) return;
    delete this.isl[slug];
    if (st.state !== "on") return;
    for (const o of [...st.imgs, ...st.sparkles, ...st.labels]) o.destroy();
    for (const t of st.timers) t.remove();
    this.labels = this.labels.filter((l) => !st.labels.includes(l));
    const meta = this.cache.json.get("meta_" + slug);
    for (const s of meta.slices) this.textures.remove("map_" + s.file);
  }

  /* ---- fly the camera to an island (the menu's action) */
  flyTo(slug) {
    const e = this.world.islands.find((i) => i.slug === slug);
    const cam = this.cameras.main;
    const [sw, sh] = this.viewSize();
    const w = e.w * e.scale, h = e.h * e.scale;
    const z = Phaser.Math.Clamp(
      Math.min(sw / w, sh / h) * 0.92,
      this.minZoom, this.maxZoom);
    this.stopIntro();
    this.tweens.add({
      targets: cam,
      zoom: z,
      scrollX: e.anchor[0] + w / 2 - sw / 2 / z,
      scrollY: e.anchor[1] + h / 2 - sh / 2 / z,
      duration: 1100,
      ease: "Sine.easeInOut",
      onUpdate: () => this.applyLabelScale(),
      onComplete: () => this.applyLabelScale(),
    });
  }

  /* ---- tax inflows: quiet motes drifting from source areas into the
     Capitol. Two streams — gold = individual income tax (DOTAX A-14, real
     ZIP geography), teal = general excise tax (DOTAX island total, spread
     by Census business payroll — see build_get_flows.py). Mote density is
     kept proportional to real dollars across both streams, so the eye
     reads GET as the bigger one, which it is. ---- */
  buildFlows(world) {
    this.flows = null;
    const inc = this.cache.json.get("flows");
    const get = this.cache.json.get("get_flows");
    if (!inc || !inc.zips || !inc.zips.length) return;

    const mote = (key, ring, core) => {
      if (this.textures.exists(key)) return;
      const g = this.make.graphics({ add: false });
      g.fillStyle(ring, 0.5);
      g.fillCircle(3, 3, 3);
      g.fillStyle(core, 1);
      g.fillCircle(3, 3, 1.6);
      g.generateTexture(key, 6, 6);
      g.destroy();
    };
    mote("mote_gold", 0xfff2c0, 0xffe9a0);
    mote("mote_teal", 0xa8f0e6, 0x4fd8c8);

    const dst = new Phaser.Math.Vector2(
      world.capitol[0], world.capitol[1] - 14);
    const SPEED = 42;                 // px/s — a calm drift
    const MIN_DUR = 3.0;              // s — keeps short downtown hops legible
    const MAX_DUR = 60.0;             // s — neighbor-island crossings speed up
    const TARGET_MOTES = 185;         // steady-state on screen, both streams

    const incDollars = inc.totalM * 1e6;
    const getDollars = get ? get.total : 0;
    const grand = incDollars + getDollars;

    const mkStream = (rows, weightOf, dollars, tex, id) => {
      const paths = rows.map((z, i) => {
        const src = new Phaser.Math.Vector2(z.px, z.py);
        const dx = dst.x - src.x, dy = dst.y - src.y;
        const len = Math.max(30, Math.hypot(dx, dy));
        const mid = new Phaser.Math.Vector2(
          (src.x + dst.x) / 2, (src.y + dst.y) / 2);
        const side = (i % 2 ? 1 : -1) * (0.10 + (i % 5) * 0.02);
        mid.x += (-dy / len) * len * side;
        mid.y += (dx / len) * len * side - len * 0.06;
        return { curve: new Phaser.Curves.QuadraticBezier(src, mid, dst),
                 len,
                 dur: Math.min(MAX_DUR, Math.max(MIN_DUR, len / SPEED)),
                 w: weightOf(z), acc: Math.random(), rate: 0 };
      });
      const wTotal = paths.reduce((s, p) => s + p.w, 0) || 1;
      const budget = TARGET_MOTES * (dollars / grand);
      // motes on screen = Σ(rate × duration), so normalise by the
      // WEIGHTED mean duration — GET's weight sits downtown on short
      // paths, and an unweighted mean silently under-draws it.
      const wDur = paths.reduce((s, p) => s + (p.w / wTotal) * p.dur, 0);
      const rateTotal = budget / Math.max(0.5, wDur);
      for (const p of paths) p.rate = rateTotal * (p.w / wTotal);
      return { id, tex, paths, enabled: true };
    };

    const streams = [
      mkStream(inc.zips, (z) => z.taxM, incDollars, "mote_gold", "income"),
    ];
    if (get && get.zips && get.zips.length) {
      streams.push(
        mkStream(get.zips, (z) => z.getM, getDollars, "mote_teal", "get"));
    }

    const pool = [];
    for (let i = 0; i < 300; i++) {
      const im = this.add.image(0, 0, "mote_gold")
        .setDepth(3).setVisible(false).setBlendMode(Phaser.BlendModes.ADD);
      pool.push({ im, t: 0, dur: 1, curve: null, free: true, sid: null });
    }
    this.flows = { streams, pool, tmp: new Phaser.Math.Vector2() };

    const release = (id) => {
      for (const m of this.flows.pool) {
        if (!m.free && m.sid === id) { m.free = true; m.im.setVisible(false); }
      }
    };
    const wire = (elId, stream, label, title) => {
      const chip = document.getElementById(elId);
      if (!chip || !stream) return;
      chip.classList.remove("hidden");
      chip.title = title;
      const setLabel = () => {
        chip.classList.toggle("off", !stream.enabled);
        chip.textContent = (stream.enabled ? "◉" : "○") + " " + label;
      };
      setLabel();
      // scene restarts re-run buildFlows: replace the handler, never stack
      chip.onpointerdown = (e) => {
        e.stopPropagation();
        stream.enabled = !stream.enabled;
        if (!stream.enabled) release(stream.id);
        setLabel();
      };
    };
    wire("flows-chip", streams[0], "Income tax · TY" + inc.year, inc.source);
    if (streams[1]) {
      wire("get-chip", streams[1], "GET · FY" + get.fy,
           get.measured + ". " + get.modeled);
    }
  }

  update(_time, delta) {
    const F = this.flows;
    if (!F) return;
    const dt = Math.min(0.05, delta / 1000);
    // screen-constant motes down to z≈0.07, then they fade to faint
    // gold dust crossing the channels at chain zoom
    const moteScale = Phaser.Math.Clamp(1 / this.cameras.main.zoom, 0.9, 14);
    for (const st of F.streams) {
      if (!st.enabled) continue;
      for (const p of st.paths) {
        p.acc += p.rate * dt;
        while (p.acc >= 1) {
          p.acc -= 1;
          const m = F.pool.find((q) => q.free);
          if (!m) break;
          m.free = false;
          m.sid = st.id;
          m.curve = p.curve;
          m.t = 0;
          m.dur = p.dur;
          m.im.setTexture(st.tex).setVisible(true);
        }
      }
    }
    for (const m of F.pool) {
      if (m.free) continue;
      m.t += dt / m.dur;
      if (m.t >= 1) {
        m.free = true;
        m.im.setVisible(false);
        continue;
      }
      m.curve.getPoint(m.t, F.tmp);
      m.im.setPosition(F.tmp.x, F.tmp.y);
      m.im.setAlpha(0.55 * Math.sin(Math.PI * m.t));
      m.im.setScale(moteScale);
    }
  }

  /* ---- the State Capitol landmark (world position) ---- */
  buildCapitol(world) {
    const [cx, cy] = world.capitol;
    const cap = this.add.image(cx, cy + 6, "capitol")
      .setOrigin(0.5, 0.9).setDepth(cy);
    cap.setInteractive({ useHandCursor: true, pixelPerfect: false });

    const mk = this.add.image(cx, cy - 78, "marker").setDepth(cy + 1);
    this.tweens.add({
      targets: mk, y: mk.y - 8, duration: 550,
      yoyo: true, repeat: -1, ease: "Sine.easeInOut",
    });

    cap.on("pointerup", (pointer) => {
      if (pointer.getDistance() > 8) return;   // was a drag, not a tap
      const fl = this.cache.json.get("flows");
      const money = fl && fl.totalM
        ? "The golden streams you see are real: in tax year " + fl.year +
          ", Hawaiʻi residents owed about $" + (fl.totalM / 1000).toFixed(1) +
          " billion in state income tax, streaming in from every " +
          "island. "
        : "";
      Dialog.show(
        "Hawaiʻi State Capitol",
        "Every state law — and every dollar in Hawaiʻi's budget — passes " +
        "through this building. " + money +
        "Here the Legislature decides how much to collect, and where it " +
        "all goes. (Module 1: Taxes & the Budget — coming soon.)"
      );
    });
    this.capitol = cap;
  }

  /* ---- labels (created per island load + island names at boot) ---- */
  makeLabel(kind, name, x, y, dy = 0) {
    const styles = {
      town: { size: 13, color: "#ffffff", stroke: "#1b2a4a", weight: "800" },
      nature: { size: 12, color: "#eaf6d8", stroke: "#25431f", weight: "700" },
      range: { size: 15, color: "#f0ead2", stroke: "#3d3323", weight: "800" },
      poi: { size: 11, color: "#ffe9a8", stroke: "#4a3a10", weight: "700" },
      capitol: { size: 13, color: "#ffe9a8", stroke: "#4a3a10", weight: "800" },
      island: { size: 17, color: "#eaf2ff", stroke: "#101d5c", weight: "800" },
    };
    const st = styles[kind] || styles.town;
    const txt = this.add.text(x, y + dy, name, {
      fontFamily: '"Avenir Next", "Trebuchet MS", Verdana, sans-serif',
      fontSize: st.size + "px",
      fontStyle: st.weight,
      color: st.color,
      stroke: st.stroke,
      strokeThickness: 4,
      letterSpacing: kind === "range" ? 3 : kind === "island" ? 4 : 1,
    }).setOrigin(0.5, kind === "island" ? 0.5 : 0).setDepth(10000);
    txt._kind = kind;
    this.labels.push(txt);
    return txt;
  }

  applyLabelScale() {
    const z = this.cameras.main.zoom;
    const inv = 1 / z;
    for (const t of this.labels) {
      t.setScale(Math.min(inv, t._kind === "island" ? 60 : 2.6));
      const vis =
        t._kind === "island" ? z <= 0.45 :
        t._kind === "range" ? z >= 0.3 && z <= 1.1 :
        t._kind === "poi" ? z >= 1.6 :
        t._kind === "capitol" ? z >= 0.45 :
        t._kind === "nature" ? z >= 0.6 :
        z >= 0.45;                                   // towns
      t.setVisible(vis);
    }
  }

  /* ---- camera: whole-chain intro dive to the Capitol, then free ---- */
  viewSize() {
    // the canvas can report 0x0 when booted in a hidden tab/webview
    return [this.scale.width || window.innerWidth || 800,
            this.scale.height || window.innerHeight || 450];
  }

  recomputeMinZoom() {
    const [sw, sh] = this.viewSize();
    this.minZoom = Math.max(
      Math.max(sw / this.world.w, sh / this.world.h) * 0.98, 0.008);
  }

  setupCamera(world) {
    const cam = this.cameras.main;
    const [cx, cy] = world.capitol;
    this.recomputeMinZoom();         // the whole archipelago fits
    this.maxZoom = 4;

    cam.centerOn(world.w / 2, world.h / 2);
    cam.setZoom(this.minZoom * 1.02);
    this.introTween = this.tweens.add({
      targets: cam,
      zoom: 1.7,
      scrollX: cx - this.scale.width / 2 / 1.7,
      scrollY: cy - 40 - this.scale.height / 2 / 1.7,
      duration: 4200,
      delay: 700,
      ease: "Sine.easeInOut",
      onUpdate: () => this.applyLabelScale(),
      onComplete: () => this.applyLabelScale(),
    });
  }

  stopIntro() {
    if (this.introTween && this.introTween.isPlaying()) this.introTween.stop();
  }

  setupInput() {
    const cam = this.cameras.main;
    this.input.addPointer(2);

    // drag pan (single pointer)
    this.input.on("pointermove", (p) => {
      if (!p.isDown) return;
      if (this.input.pointer2 && this.input.pointer2.isDown) return; // pinching
      this.stopIntro();
      cam.scrollX -= (p.x - p.prevPosition.x) / cam.zoom;
      cam.scrollY -= (p.y - p.prevPosition.y) / cam.zoom;
    });

    // wheel zoom to cursor
    this.input.on("wheel", (p, _objs, _dx, dy) => {
      this.stopIntro();
      this.zoomAt(p.x, p.y, cam.zoom * (dy > 0 ? 0.88 : 1.14));
    });

    // pinch
    this.pinchDist = 0;
    this.input.on("pointermove", () => {
      const p1 = this.input.pointer1, p2 = this.input.pointer2;
      if (!p1.isDown || !p2.isDown) { this.pinchDist = 0; return; }
      this.stopIntro();
      const d = Phaser.Math.Distance.Between(p1.x, p1.y, p2.x, p2.y);
      if (this.pinchDist > 0) {
        const mx = (p1.x + p2.x) / 2, my = (p1.y + p2.y) / 2;
        this.zoomAt(mx, my, cam.zoom * (d / this.pinchDist));
      }
      this.pinchDist = d;
    });
    this.input.on("pointerup", () => { this.pinchDist = 0; });
  }

  zoomAt(sx, sy, targetZoom) {
    const cam = this.cameras.main;
    const z = Phaser.Math.Clamp(targetZoom, this.minZoom, this.maxZoom);
    const before = cam.getWorldPoint(sx, sy);
    cam.setZoom(z);
    cam.preRender();
    const after = cam.getWorldPoint(sx, sy);
    cam.scrollX += before.x - after.x;
    cam.scrollY += before.y - after.y;
    this.applyLabelScale();
  }
}

/* ---------------------------------------------------------------- boot */
window.addEventListener("load", () => {
  Dialog.init();
  window.__game = new Phaser.Game({
    // Canvas renderer on purpose: the world is one pre-baked image plus a
    // few hundred sprites, and Canvas2D avoids GPU texture-size limits and
    // embedded-webview WebGL quirks.
    type: Phaser.CANVAS,
    parent: "game",
    backgroundColor: DEEP_BLUE,
    pixelArt: true,
    roundPixels: true,
    scale: {
      mode: Phaser.Scale.RESIZE,
      width: window.innerWidth,
      height: window.innerHeight,
    },
    scene: [BootScene, WorldScene],
  });
});
