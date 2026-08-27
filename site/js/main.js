/* Capitol Quest — Oʻahu overworld
 * Baked pixel-art iso map (see tools/) + Phaser camera/landmarks/UI.
 */

"use strict";

/* PRE-LOAD fallback only. The real sea colour is read at runtime from
   world.json's `deep`, which build_world copies out of the island bakes
   — see WorldScene.create(). This constant only paints the canvas
   before any JSON has loaded, so it just needs to be close; it can
   never be right for both art styles at once, because `--style pixel`
   bakes a different blue than `--style painterly`. */
const DEEP_BLUE = "#185ba0";

/* ONE cache token for everything render_map/build_world bake together:
   the tile PNGs, overview.png, world.json and every <slug>.json. They
   are produced by the same run and are only ever valid as a SET — a
   world.json paired with last bake's tiles is exactly the kind of
   mismatch that spent three rounds looking like a rendering bug.
   The pre-commit cache-bump hook only rewrites `?v=` inside HTML, so
   anything loaded from JS is bumped BY HAND: after re-baking the map,
   raise this ONE number. Content JSON (session/policies/chairs) keeps
   its own token — it changes on a different clock. */
const MAP_V = 8;

/* Cache token for the Capitol interior bake — capitol_scene.png +
   map/capitol.json come out of ONE run of tools/render_capitol.py and
   are only valid as a set (hotspot px are baked against the image).
   Hand-bumped, same rule as MAP_V. */
const CAP_V = 34;
/* THE GAME LANDS IN THE CAPITOL, NOT ON THE MAP (2026-08-24, user's
   call: "make that the default view (replacing the map) for now. keep
   the map in case we want to use it later"). Set to null to put the
   overworld back — that is the ONLY edit needed, and it is why this is
   a switch rather than a rewrite of the boot path:
   - WorldScene still RUNS. It builds the map, the flows and the
     labels and it initialises every panel (Money/Policy/Session/
     Island/Sfx), all of which live in its create(). Booting straight
     into a room instead would leave the whole game uninitialised.
     The map is built, then slept — nothing is deleted, nothing is
     behind a second code path that can rot.
   - The intro dive is SKIPPED and the camera parked where the dive
     would have LANDED, so leaving the room by the stairs arrives on
     the Capitol rather than on a half-tweened archipelago.
   - The week-1 overlay's boot pop is suppressed while this is set
     (see SessionPanel.init) — the point is to land on the room, and
     an overlay that opens over it defeats that. The map and the
     session are both still reachable: take the stairs. */
const START_ROOM = "capitol";
/* Same rule for the House Finance office bake (tools/render_office.py:
   office_finance.png + map/office_finance.json). */
const OFF_V = 2;

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
    href: "assets/sprites/capitol.png?v=2", x: CX - 56, y: CY - 46,
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
    // ONE toolbar button for both halves of the money story: it opens on
    // "↑ Money out" and the tabs carry the player to "↓ Money in". The
    // separate Revenue button was removed 2026-08-15 (user's call) as a
    // duplicate door into the same overlay.
    wireToolbar("tb-budget", "budget");
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
   in localStorage. Must init AFTER MoneyPanel so the tb-budget
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
    // the money-overlay toolbar button closes this overlay (its own
    // handler stopPropagation's, but same-element listeners still run)
    for (const id of ["tb-budget"]) {
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

/* ------------------------------------------------- custom symbol set */
/* The session overlay draws its own glyphs instead of stock emoji —
   monoline 24×24 strokes in currentColor, so every symbol takes the
   color of the text (or pole) it sits in, same rule as the creation
   screen's GLYPH cards. Dots/fills that must stay solid carry their
   own fill="currentColor". Add new keys here, never emoji in JS. */
const SYM = (() => {
  const S = {
    // skills
    fiscal: '<path d="M5 20v-5M10 20v-8M15 20v-11"/>' +
      '<path d="M4 13l6.5-4L17 6l3-1.5"/>' +
      '<circle cx="20" cy="4.3" r="1.7" fill="currentColor" stroke="none"/>',
    procedure: '<path d="M4 20h16V4H4v12h12V8H8v4h4"/>',
    educator: '<path d="M12 6.5C10.5 5 8 4.5 4 4.5V18c4 0 6.5.5 8 2 ' +
      '1.5-1.5 4-2 8-2V4.5c-4 0-6.5.5-8 2Z"/><path d="M12 6.5V20"/>',
    talkstory: '<path d="M4 4.5h9V11H8l-3 3v-3H4z"/>' +
      '<path d="M11 11h9v6.5h-2.5v3l-3-3H11z"/>',
    mobilizing: '<path d="M4 10v4h3l7 4V6l-7 4H4Z"/>' +
      '<path d="M17.5 9.5a4 4 0 0 1 0 5"/><path d="M20 7.5a7 7 0 0 1 0 9"/>',
    basebuilding: '<path d="M12 13V8"/>' +
      '<path d="M12 9c0-3 2-4.5 5-4.5C17 7.5 15 9 12 9Z"/>' +
      '<path d="M12 9c0-3-2-4.5-5-4.5C7 7.5 9 9 12 9Z"/>' +
      '<path d="M4 13h16"/><path d="M12 13v6M12 13l-4.5 4.5M12 13l4.5 4.5"/>',
    // metrics + HUD
    revenue: '<circle cx="12" cy="12" r="7.6"/>' +
      '<path d="M14.5 9.3c-.6-1-4.4-1.3-4.6.6-.2 2 4.6 1.3 4.4 3.4-.2 ' +
      '1.8-3.9 1.7-4.7.6M12 7.3v1.4M12 15.3v1.4"/>',
    support: '<circle cx="9" cy="9" r="2.7"/>' +
      '<path d="M4.5 19c.4-3.2 2.2-5 4.5-5s4.1 1.8 4.5 5"/>' +
      '<circle cx="16.5" cy="10" r="2.2"/>' +
      '<path d="M15.8 14.5c2.4.3 3.7 2 4 4.3"/>',
    influence: '<path d="M6 10a6 6 0 0 1 12 0"/><path d="M12 4V2.5"/>' +
      '<path d="M4.5 10h15"/><path d="M7 13v5M12 13v5M17 13v5"/>' +
      '<path d="M5.5 13h13"/><path d="M5 20.5h14"/>',
    advocate: '<rect x="6" y="4" width="12" height="7" rx="1"/>' +
      '<path d="M12 11v9.5"/><path d="M9 7.5h6"/>',
    event: '<path d="M9 17.5a3 3 0 0 0 6 0"/>' +
      '<path d="M5.5 17.5h13c-1.5-1.5-2-3-2-5.5 0-3-1.6-5.5-4.5-5.5' +
      'S7.5 9 7.5 12c0 2.5-.5 4-2 5.5Z"/><path d="M12 4.5V3"/>',
    intel: '<circle cx="6" cy="18" r="1.8" fill="currentColor" stroke="none"/>' +
      '<path d="M4.5 11.5a8 8 0 0 1 8 8"/>' +
      '<path d="M4.5 5.5a14 14 0 0 1 14 14"/>',
    push: '<path d="M12 21v-4"/>' +
      '<path d="M8.5 4h7l-1 6 2.5 4h-10L9.5 10Z"/>',
    dice: '<rect x="4.5" y="4.5" width="15" height="15" rx="3"/>' +
      '<circle cx="9" cy="9" r="1.4" fill="currentColor" stroke="none"/>' +
      '<circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/>' +
      '<circle cx="15" cy="15" r="1.4" fill="currentColor" stroke="none"/>',
    // characters
    chamber: '<path d="M4 20.5h16"/><path d="M5 20.5V9l7-4.5L19 9v11.5"/>' +
      '<path d="M8.5 12v6M12 12v6M15.5 12v6"/>',
    briefcase: '<rect x="4" y="8" width="16" height="11" rx="2"/>' +
      '<path d="M9 8V6.5A1.5 1.5 0 0 1 10.5 5h3A1.5 1.5 0 0 1 15 6.5V8"/>' +
      '<path d="M4 13h16"/>',
    // your introducers — a filed bill, not a face (house art rule)
    introducer: '<path d="M6.5 3.5h8L18 7v13.5H6.5Z"/>' +
      '<path d="M14 3.5V7h4"/><path d="M9.5 11h5M9.5 14h5"/>' +
      '<path d="M9.2 17.6c1.2-1.4 2-.4 3 .1s1.6.2 2.3-.9"/>',
    clipboard: '<rect x="6" y="5" width="12" height="15" rx="1.5"/>' +
      '<path d="M9.5 5a2.5 2.5 0 0 1 5 0"/>' +
      '<path d="M9 10.5h6M9 13.5h6M9 16.5h4"/>',
    lei: '<circle cx="12" cy="12" r="2"/><circle cx="12" cy="6.4" r="2.5"/>' +
      '<circle cx="17.3" cy="10.2" r="2.5"/>' +
      '<circle cx="15.3" cy="16.5" r="2.5"/>' +
      '<circle cx="8.7" cy="16.5" r="2.5"/>' +
      '<circle cx="6.7" cy="10.2" r="2.5"/>',
    // actions
    rally: '<path d="M6 21V4"/><path d="M6 5h11l-2.5 3.5L17 12H6"/>',
    bench: '<circle cx="12" cy="6.8" r="2.1"/>' +
      '<circle cx="6" cy="16.5" r="2.1"/><circle cx="18" cy="16.5" r="2.1"/>' +
      '<path d="M10.3 8.6 7.2 14.6M13.7 8.6l3.1 6M8.2 17h7.6" opacity=".55"/>',
    building: '<path d="M5 20.5V5h14v15.5"/><path d="M3.5 20.5h17"/>' +
      '<path d="M9 8.5h2M13 8.5h2M9 12h2M13 12h2"/>' +
      '<path d="M10.5 20.5V16h3v4.5"/>',
    // policies (by id)
    meal: '<path d="M4.5 12h15a7.5 7.5 0 0 1-15 0Z"/>' +
      '<path d="M9.5 9c0-1.2 1-1.2 1-2.4M13.5 9c0-1.2 1-1.2 1-2.4" ' +
      'opacity=".7"/>',
    child: '<circle cx="12" cy="7.5" r="3"/>' +
      '<path d="M6.5 20c.5-4 2.7-6.2 5.5-6.2s5 2.2 5.5 6.2"/>',
    cart: '<path d="M4 5h2.5l2 10.5h9L20 8H7"/>' +
      '<circle cx="10" cy="19" r="1.6" fill="currentColor" stroke="none"/>' +
      '<circle cx="16.5" cy="19" r="1.6" fill="currentColor" stroke="none"/>',
    house: '<path d="M4.5 11 12 4.5 19.5 11"/><path d="M6.5 10.5v9h11v-9"/>' +
      '<path d="M10.5 19.5V15h3v4.5"/>',
    chart: '<path d="M4 19.5h16"/><path d="M5 15l4.5-4 3.5 2.5L19 7"/>' +
      '<path d="M15.5 7H19v3.5"/>',
    solar: '<circle cx="12" cy="8" r="3.2"/>' +
      '<path d="M12 2.2v1.6M12 12.2v1.6M5.9 8H4.3M19.7 8h-1.6' +
      'M7.7 3.7 6.6 2.6M17.4 2.6l-1.1 1.1M7.7 12.3l-1.1 1.1' +
      'M17.4 13.4l-1.1-1.1"/>' +
      '<path d="M8.2 16.5h7.6l2.2 4.5H6z"/><path d="M7 21h10"/>',
  };
  // aliases: characters and actions that share a drawing
  S.kawaguchi = S.souza = S.chamber;
  S["rep-x"] = S["sen-x"] = S.introducer;
  S.grange = S.briefcase;
  S.office = S.clipboard;
  S.coalition = S.lei;
  S.lobby = S.building;
  S.ufsm = S.meal;
  S.ctc = S.child;
  S.retitc = S.solar;
  // `cart` has no policy pointing at it since get-half was removed
  // 2026-08-15 — the drawing stays for whenever a GET measure returns
  S.conveyance = S.house;
  S.capgains = S.chart;
  S.wwcr = S.building;
  return S;
})();
const sym = (id, cls) => SYM[id]
  ? '<svg class="sym' + (cls ? " " + cls : "") +
    '" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" ' +
    'aria-hidden="true">' + SYM[id] + "</svg>"
  : "";

/* -------------------------------------------------------- session panel */
/* The disco-flavored core loop. The player is THE ADVOCATE — one
   identity, leading a campaign from OUTSIDE the building. No seat, no
   vote, no floor minute, no co-signing: members carry the bills, the
   player runs the coalition and the argument. Content must never hand
   the player a legislator's powers. Time passes in TURNS — one turn =
   one week of the legislative session. Each week: an intel report
   (accuracy gated per facet by skills — see intelHtml) and an event
   dialogue (the six SKILLS chime in on everything, colored by pole —
   not a left/right trait system). Talk story and actions are NOT a
   weekly allowance — the week's event OPENS them (dialogue-level
   `unlocks`, plus choice-level `effects.unlock`): no event played, no
   doors open. Still at most ONE action per week when one is offered.
   Actions hone the skill they exercise (train() — two uses buy a pip). Week 1
   is Opening Day: allocate skill points and pick the bill package
   that lined-up members will introduce — that package IS your
   session. There is no week 0; the session starts in session. All
   content is data-driven from map/session.json; the thought cabinet
   bolts on next. */
const SessionPanel = {
  built: false,
  init(budget, policies, data, chairData, rateData, scene) {
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
    /* One motion switch for the whole panel. Checked at CALL time, not
       cached — a player can flip the OS setting mid-session. Every
       JS-driven animation below asks this first; the CSS half lives in
       one `prefers-reduced-motion` block. */
    const reduced = () => !!(window.matchMedia &&
      matchMedia("(prefers-reduced-motion: reduce)").matches);

    /* Count a number up to its new value. `fmt` renders each frame, so
       this works for plain integers and for formatted dollars alike.
       A wall-clock timer force-lands the final value: rAF does not fire
       in a hidden tab, and a meter frozen at its OLD number would be
       worse than no animation at all. */
    const countTo = (node, from, to, fmt, ms) => {
      if (!node) return;
      if (reduced() || from === to) { node.textContent = fmt(to); return; }
      const dur = ms || 460;
      const t0 = (window.performance || Date).now();
      let landed = false;
      const land = () => {
        if (landed) return;
        landed = true;
        node.textContent = fmt(to);
      };
      const step = (t) => {
        if (landed) return;
        const k = Math.min(1, ((t || (window.performance || Date).now()) - t0) / dur);
        const e = 1 - Math.pow(1 - k, 3);          // easeOutCubic
        node.textContent = fmt(from + (to - from) * e);
        if (k < 1) requestAnimationFrame(step);
        else land();
      };
      requestAnimationFrame(step);
      setTimeout(land, dur + 120);
    };
    /* esc() deliberately leaves quotes alone — fine for text nodes, but
       it will break straight out of an ATTRIBUTE, and this content is
       full of dialogue in quotation marks. Anything interpolated into
       an attribute value must go through escA instead. Hit live on the
       introducer strip's title (chairs.json `voice` starts with a
       double quote), which produced a spray of junk attributes. */
    const escA = (s) => esc(String(s == null ? "" : s))
      .replace(/"/g, "&quot;");

    /* ---- turn state
       The two opinion meters are NOT halves of one bar. Public Support
       is a stock you spend at hearings and votes; Political Influence
       is a rate that applies to every scheduling decision in the
       building. Same scale, different physics — that asymmetry is the
       teaching point, so never present them as a balance. */
    const KEY = "cq-session";
    // "_"-prefixed keys are doc notes, not skill records — session.json
    // keeps them OUTSIDE this collection, but filter defensively anyway
    const SK = Object.keys(data.skills || {}).filter((k) => k[0] !== "_");
    const skStart = data.skillStart || {};
    const baseSkills = () => {
      const o = {};
      for (const k of SK) o[k] = skStart.base || 1;
      return o;
    };
    /* A bare number is not a self-explanatory quantity — "3" only means
       something once you know the ladder runs to 6. session.json
       `skillStart.ranks` names every level (indexed BY THE VALUE, so
       ranks[1] is what a 1 is called); this is the fallback for a data
       file that predates the list. Content belongs in the JSON.
       The ladder runs to 6, so "Average" names the MIDDLE (3), not the
       floor: every skill starts at 1, Very weak, and is bought up. */
    const RANKS = ["None", "Very weak", "Weak", "Average", "Good",
                   "Great", "Formidable"];
    const rankOf = (v) => {
      const list = skStart.ranks && skStart.ranks.length
        ? skStart.ranks : RANKS;
      return list[Math.max(0, Math.min(list.length - 1, v | 0))] || "";
    };
    const defaults = () => ({
      week: 1, actionWeek: -1, agendaLocked: false, agenda: [],
      eventDone: [], preDone: [], talked: {}, log: [], flags: {}, checks: {},
      unlocks: { week: 0, talks: {}, actions: [] },
      // rapport with your two introducers, keyed by chamber; seeded from
      // chairs.json in seedIntroducers() so the baseline lives with the
      // rest of the editorial data
      intro: {},
      // last week's bill movement, {week, list} — rendered at the top of
      // the hub so the gauntlet is something you watch, not something you
      // discover in a status word
      moves: null,
      bills: [], chairs: {}, pushWeek: -1, pushBill: null,
      skills: baseSkills(), skillPts: skStart.points || 0, train: {},
      metrics: { revenueK: 0, support: 50, influence: 30 },
      /* Where support/influence stood when THIS week opened, so the HUD
         standing cluster can show a trend beside the value. Snapshotted
         at the top of advanceWeek() — before resolveBills() — so the
         arrow the player sees on the map right after ending a turn is
         the one the gauntlet just moved, which is the whole reason a
         trend is worth showing at all. */
      weekBase: { support: 50, influence: 30 },
    });
    let S = defaults();
    try {
      S = Object.assign(defaults(),
        JSON.parse(localStorage.getItem(KEY) || "{}"));
      S.metrics = Object.assign(defaults().metrics, S.metrics);
      S.skills = Object.assign(baseSkills(), S.skills);
      S.train = S.train || {};
      // pre-unlocks saves (before 2026-08-15) had free weekly talk/
      // action defaults; they simply start their current week with no
      // open doors, and the next event re-grants
      S.unlocks = Object.assign({ week: 0, talks: {}, actions: [] },
        S.unlocks || {});
      // saves from before pre-events (2026-08-19) have no preDone list;
      // an empty one is correct — they simply play the pre when they
      // reach a week that has one
      S.preDone = S.preDone || [];
      // pre-introducer saves (before 2026-08-15) just get seeded at the
      // baseline by seedIntroducers(), which is exactly the behaviour
      // they already had — the odds term is zero-centred there
      S.intro = S.intro || {};
      // saves written before the rename carried families/wealthy —
      // migrate them, or an in-progress campaign silently resets
      if (S.metrics.families != null) S.metrics.support = S.metrics.families;
      if (S.metrics.wealthy != null) S.metrics.influence = S.metrics.wealthy;
      delete S.metrics.families;
      delete S.metrics.wealthy;
      // saves from before the HUD standing cluster (2026-08-18) have no
      // week baseline — seed it at TODAY's values so an in-progress
      // campaign opens showing no trend rather than inventing one that
      // reads as a swing the player never caused
      S.weekBase = Object.assign({ support: S.metrics.support,
                                   influence: S.metrics.influence },
                                 S.weekBase || {});
      // pre-2026-08-14 saves carried a week 0 (pre-session, agenda-only) —
      // that week is gone, its agenda step folded into week 1
      if (S.week < 1) { S.week = 1; S.agendaLocked = false; }
      // a save whose bills is not an array (hand-edited storage, or a
      // future shape change) must not brick the boot — migrateBills
      // iterates it before anything can catch the mismatch
      if (!Array.isArray(S.bills)) S.bills = [];
      // Grassroots split into Mobilizing + Base Building (2026-08-14).
      // Seed BOTH halves at the old value rather than dividing it: the
      // player earned that skill under the old rules, and halving it
      // would silently nerf an in-progress campaign — the same failure
      // the metrics migration above exists to prevent. Cap still applies.
      // NB: baseSkills() above has already seeded both halves at `base`,
      // so this must MAX against that, not test for null — an == null
      // guard here would never fire and the migration would silently
      // no-op, dropping the player's investment back to 1.
      if (S.skills.grassroots != null) {
        const g = S.skills.grassroots;
        S.skills.mobilizing = Math.max(S.skills.mobilizing || 0, g);
        S.skills.basebuilding = Math.max(S.skills.basebuilding || 0, g);
        delete S.skills.grassroots;
        if (S.train.grassroots != null) {
          S.train.mobilizing = Math.max(S.train.mobilizing || 0,
            S.train.grassroots);
          S.train.basebuilding = Math.max(S.train.basebuilding || 0,
            S.train.grassroots);
          delete S.train.grassroots;
        }
      }
      // Whip Count retired into Talk Story (2026-08-14, same MAX-not-null
      // reasoning as the grassroots migration above — baseSkills() has
      // already seeded talkstory at `base`). No action ever trained whip
      // (it was intel-only), so there's no S.train.whip to carry over.
      if (S.skills.whip != null) {
        S.skills.talkstory = Math.max(S.skills.talkstory || 0, S.skills.whip);
        delete S.skills.whip;
      }
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
        phase: hit.phase || (w >= data.sineDieWeek ? "Adjournment" :
          w >= 14 ? "Conference" : "Session"),
        event: hit.event !== undefined ? hit.event :
          (w >= 2 && w < data.sineDieWeek
            ? data.genericEvents[(w - 2) % data.genericEvents.length]
            : null),
        // a PRE-event runs before the week's own event and is tracked
        // separately (S.preDone) — a week can carry both, and closing
        // the panel between them must not replay the first
        pre: hit.pre || null,
        // RECESS weeks: neither chamber convenes, so resolveBills skips
        // EVERY gate (not just the chair ones — see the note there) and
        // every deadline stays exactly where it was, which is the lesson
        recess: !!hit.recess,
        // a calendar entry that carries data but is not a milestone
        // keeps its tick off the timeline strips
        milestone: hit.milestone !== false,
        agenda: !!hit.agenda,
        noAction: !!hit.noAction || w > data.sineDieWeek,
        // no weekly defaults — talk story and actions are OPENINGS the
        // week's event grants (see weekOpen/grantUnlocks); a calendar
        // entry may still hard-wire scripted ones
        talks: hit.talks || {},
        actions: hit.actions || [],
      };
    };

    /* ---- what THIS week has opened: scripted calendar grants plus
       whatever the week's event (or a choice inside it) unlocked.
       S.unlocks is per-week — a stale week number means nothing is
       open, so advancing the week closes every door automatically. */
    const weekOpen = () => {
      const cal = calFor(S.week);
      const cur = S.unlocks.week === S.week ? S.unlocks :
        { talks: {}, actions: [] };
      return {
        talks: Object.assign({}, cal.talks, cur.talks),
        acts: [...new Set([...(cal.actions || []), ...cur.actions])],
      };
    };

    /* Grant openings for the current week. `u` = { talks: {cid: dlgId},
       actions: [aid] } — aid "push" opens the work-the-chair rows.
       Returns display names of what NEWLY opened (for the fx line). */
    const grantUnlocks = (u) => {
      if (!u) return [];
      if (S.unlocks.week !== S.week) {
        S.unlocks = { week: S.week, talks: {}, actions: [] };
      }
      const got = [];
      for (const cid of Object.keys(u.talks || {})) {
        if (S.unlocks.talks[cid]) continue;
        S.unlocks.talks[cid] = u.talks[cid];
        got.push((data.characters[cid] || {}).name || cid);
      }
      for (const aid of u.actions || []) {
        if (S.unlocks.actions.includes(aid)) continue;
        S.unlocks.actions.push(aid);
        got.push(aid === "push" ? "Work a chair"
          : (data.actions[aid] || {}).name || aid);
      }
      if (got.length) save();
      return got;
    };

    /* ---- real calendar dates, derived from data.sessionStart (the
       convening date, always the 3rd Wednesday in January) — week 1 is
       that week, each later week is +7 days */
    const DAY_MS = 86400000;
    const sessionStart = data.sessionStart ?
      new Date(data.sessionStart + "T00:00:00") : null;
    const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const fmtDate = (d) => MONTHS[d.getMonth()] + " " + d.getDate();
    const dateRangeFor = (w) => {
      if (!sessionStart) return "";
      const start = new Date(sessionStart.getTime() + (w - 1) * 7 * DAY_MS);
      const end = new Date(start.getTime() + 6 * DAY_MS);
      return (start.getMonth() === end.getMonth()
        ? fmtDate(start) + "–" + end.getDate()
        : fmtDate(start) + " – " + fmtDate(end)) + ", " + end.getFullYear();
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
      if (fx.support) {
        S.metrics.support = clamp(S.metrics.support + fx.support);
        parts.push('<span class="' + (fx.support > 0 ? "gain" : "cost") +
          '">Public Support ' + (fx.support > 0 ? "+" : "") +
          fx.support + "</span>");
      }
      if (fx.influence) {
        S.metrics.influence = clamp(S.metrics.influence + fx.influence);
        parts.push('<span class="' + (fx.influence > 0 ? "gain" : "cost") +
          '">Political Influence ' +
          (fx.influence > 0 ? "+" : "") + fx.influence + "</span>");
      }
      if (fx.flag) S.flags[fx.flag] = S.week;
      // rapport with your introducers — {house: n, senate: n}
      if (fx.rapport) {
        for (const who of Object.keys(fx.rapport)) {
          const n = fx.rapport[who];
          if (!n || S.intro[who] == null) continue;
          S.intro[who] = clamp(S.intro[who] + n);
          parts.push('<span class="' + (n > 0 ? "gain" : "cost") + '">' +
            sym("introducer") + " " + esc(introName(who)) + " " +
            (n > 0 ? "+" : "") + n + "</span>");
        }
      }
      if (fx.skill && S.skills[fx.skill] != null) {
        S.skills[fx.skill] = Math.min(skStart.cap || 6,
          S.skills[fx.skill] + 1);
        parts.push('<span class="gain">' + sym(fx.skill) +
          " " + esc(data.skills[fx.skill].name) + " +1</span>");
      }
      // a choice can open a door the scene itself didn't — same shape
      // as a dialogue-level `unlocks` block
      if (fx.unlock) {
        for (const n of grantUnlocks(fx.unlock)) {
          parts.push('<span class="gain">Opened: ' + esc(n) + "</span>");
        }
      }
      /* syncScore(), NOT setExternal(revenueK) — the bare form dropped
         every enacted bill's contribution off the scoreboard until the
         next resolveBills put it back, so the FY2027 chip flinched by
         the size of the player's own legislation on any week an fx
         landed. It matters more now that a single event can move the
         bottom line by $600M (w7-storm): the chip is where that number
         is supposed to be legible. */
      syncScore();
      save();
      renderHead();
      return parts.length ? '<div class="sd-fx">' +
        parts.join(" · ") + "</div>" : "";
    };

    /* Learn by doing: each action names the skill it exercises
       (session.json `trains`; the push action exercises Procedure), and
       skillStart.honeEvery uses buy one pip, up to the cap. This is the
       only repeatable way to grow a skill after week 0 — one-off event
       grants still ride fx.skill. Returns the fx line to show. */
    const train = (skill) => {
      const sk = data.skills[skill];
      if (!sk) return "";
      if ((S.skills[skill] || 0) >= (skStart.cap || 6)) return "";
      S.train[skill] = (S.train[skill] || 0) + 1;
      if (S.train[skill] >= (skStart.honeEvery || 2)) {
        S.train[skill] = 0;
        S.skills[skill] += 1;
        save();
        return '<div class="sd-fx"><span class="gain">' + sym(skill) + " " +
          esc(sk.name) + " +1 — practice</span></div>";
      }
      save();
      return '<div class="sd-fx"><span class="hone">' + sym(skill) + " " +
        esc(sk.name) + " sharpens — one more week of this</span></div>";
    };

    /* ---- mini timeline: the session's real milestones (crossover,
       conference, sine die…) plotted from data.calendar, with a marker
       for the current week. Milestone dots stagger label rows top/bottom
       so a dozen titles don't collide in the overlay's width; a separate
       round cursor marks the current week even between milestones. */
    /* The milestone list is NOT data.calendar — a calendar entry may
       carry week data (a `pre`, a recess flag) without being a beat the
       player should see plotted. `milestone: false` keeps it off both
       strips; the 940px inner width is what stops the labels colliding
       and it is already carrying twelve. */
    const milestones = () =>
      data.calendar.filter((c) => c.milestone !== false);

    const renderTimeline = () => {
      const el = $("sess-timeline");
      if (!el) return;
      const cal = milestones();
      const span = Math.max(1, data.sineDieWeek - 1);
      const pctOf = (w) => Math.max(0, Math.min(100,
        ((w - 1) / span) * 100));
      const curPct = pctOf(S.week);
      const atMilestone = cal.some((c) => c.week === S.week);
      /* Only ONE label is drawn at rest: the stage the session is
         actually IN — the latest milestone at or before this week. On
         a milestone week that is the current dot; between milestones it
         is the phase you are still inside (week 6 is inside First
         Lateral). Everything else fades in on hover/tap, so the strip
         reads as one legible line instead of twelve competing ones. */
      let stageI = -1;
      cal.forEach((c, i) => { if (c.week <= S.week) stageI = i; });
      let h = '<div class="stl-track"></div>' +
        '<div class="stl-fill" style="width:' + curPct + '%"></div>';
      cal.forEach((c, i) => {
        const state = (c.week < S.week ? "past" :
          c.week === S.week ? "now" : "future") +
          (i === stageI ? " cur-stage" : "");
        // the first/last dot sit at the very edge of the scroll strip —
        // a centered label there would overflow into unreachable
        // negative scroll space, so those two anchor to their dot's
        // outer edge instead of straddling it
        const edge = i === 0 ? " edge-l" :
          i === cal.length - 1 ? " edge-r" : "";
        h += '<button type="button" class="stl-m ' + state +
          (i % 2 ? " lbl-b" : " lbl-t") + edge +
          '" style="left:' + pctOf(c.week) + '%" data-week="' + c.week +
          '"><span class="stl-hit"></span>' +
          '<span class="stl-dot"></span>' +
          '<span class="stl-lbl">' + esc(c.title) + "</span></button>";
      });
      if (!atMilestone) {
        h += '<div class="stl-cursor" style="left:' + curPct +
          '%" title="Week ' + S.week + '"></div>';
      }
      /* Structure: a horizontally scrolling strip (fixed min-width, so
         nine milestone labels never collide on a narrow overlay). The
         readout line that used to sit under it was removed 2026-08-15
         (user's call) to give the dialogue back its vertical space —
         the masthead above already names the current week, and
         hovering/tapping a milestone surfaces its own label. */
      el.innerHTML = '<div class="stl-scroll"><div class="stl-inner">' +
        h + "</div></div>";

      for (const m of el.querySelectorAll(".stl-m")) {
        const on = () => {
          for (const o of el.querySelectorAll(".stl-m")) {
            o.classList.toggle("hot", o === m);
          }
        };
        const off = () => {
          m.classList.remove("hot");
        };
        m.addEventListener("pointerenter", on);
        m.addEventListener("pointerleave", off);
        m.addEventListener("focus", on);
        m.addEventListener("blur", off);
        // touch has no hover: a tap previews and holds until the next
        // tap elsewhere, and never closes the overlay (the panel's own
        // pointerdown handler would otherwise treat it as a backdrop hit)
        m.addEventListener("pointerdown", (ev) => {
          ev.stopPropagation();
          const held = m.classList.contains("hot");
          if (held) { off(); el.classList.remove("reveal"); }
          else { on(); el.classList.add("reveal"); }
        });
      }
      /* `reveal` is the touch equivalent of :hover — tapping anywhere on
         the strip shows every label. Mouse users get the same thing from
         the :hover rule, so this exists purely so a phone can read the
         calendar at all. stopPropagation, or the overlay's backdrop
         handler closes the whole panel on the way past. */
      const scroller = el.querySelector(".stl-scroll");
      if (scroller) scroller.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        el.classList.toggle("reveal");
      });
      // land the strip on the current week, not always its left edge
      requestAnimationFrame(centerTimeline);
    };

    /* Centering has to survive being called while the overlay is
       HIDDEN: renderHead runs on boot, and a display:none scroll box
       reports clientWidth 0 (just its padding), so the math produced a
       nonsense scrollLeft that then stuck — the current week's label
       sat half-clipped off the left edge until the player scrolled.
       Same class of bug as the hidden-boot canvas 0x0 in WorldScene.
       Bail while there's no width and re-run from openOverlay(). */
    const centerTimeline = () => {
      const el = $("sess-timeline");
      const box = el && el.querySelector(".stl-scroll");
      if (!box || box.clientWidth < 40) return;
      const cur = el.querySelector(".stl-m.now") ||
        el.querySelector(".stl-cursor");
      if (!cur) return;
      // scrollIntoView would also scroll the OVERLAY (nearest scrollable
      // ancestor) and yank the panel; set scrollLeft directly, clamped,
      // so only the strip moves
      const max = Math.max(0, box.scrollWidth - box.clientWidth);
      box.scrollLeft = Math.max(0, Math.min(max,
        cur.offsetLeft - box.clientWidth / 2));
    };

    /* ---- session progress on the map HUD, above the End Turn button —
       always visible, not just inside the overlay.
       A PROGRESS BAR since 2026-08-15 (user's call), not the old dot
       strip: at 168px the nine milestone dots were 5px each and read as
       lint. The milestones survive as ticks IN the track, which is what
       they actually are — marks along the run — and the readout gives
       the number the dots could never show. The overlay's full strip is
       still where you go to READ the calendar; this answers "how much
       session is left" at a glance.
       Built ONCE and updated in place (`data-built`), the same lesson
       as renderMetrics: replacing the innerHTML gives the fill no
       previous width to transition from, so it would snap on every
       week instead of sliding. */
    const renderHudTimeline = () => renderProgress($("hud-timeline"),
      "open the session");
    /* ONE renderer for BOTH progress bars — the HUD chip on the map and
       the panel's own compact bar beside the week plate (2026-08-19).
       They are two readings of the same calendar and a second copy of
       this arithmetic is a second chance for them to disagree; the CSS
       is shared the same way, through `.htl`. Only the chrome and the
       tooltip differ, and the chrome is entirely in the stylesheet. */
    const renderProgress = (el, verb) => {
      if (!el) return;
      const span = Math.max(1, data.sineDieWeek - 1);
      const pctOf = (w) => Math.max(0, Math.min(100,
        ((w - 1) / span) * 100));
      if (!el.dataset.built) {
        let ticks = "";
        milestones().forEach((c) => {
          ticks += '<span class="htl-tick" data-week="' + c.week +
            '" style="left:' + pctOf(c.week) + '%"></span>';
        });
        el.innerHTML = '<span class="htl-bar">' +
          '<span class="htl-fill"></span>' + ticks +
          '<span class="htl-head"></span></span>' +
          '<span class="htl-read"></span>';
        el.dataset.built = "1";
      }
      const curPct = pctOf(S.week);
      el.querySelector(".htl-fill").style.width = curPct + "%";
      el.querySelector(".htl-head").style.left = curPct + "%";
      for (const t of el.querySelectorAll(".htl-tick")) {
        t.classList.toggle("past", +t.dataset.week <= S.week);
      }
      const last = data.sineDieWeek;
      el.querySelector(".htl-read").textContent =
        Math.min(S.week, last) + "/" + last;
      // both bars are buttons; the tooltip carries what the milestone
      // labels used to, since a bar has no room for nine names. `verb`
      // is what THIS one opens — the HUD chip opens the session, the
      // panel's bar opens the full strip under itself.
      const cal = calFor(S.week);
      el.title = "Week " + S.week + " of " + last +
        (cal.title ? " · " + cal.title : "") +
        (dateRangeFor(S.week) ? " · " + dateRangeFor(S.week) : "") +
        (verb ? " — " + verb : "");
    };

    /* ---- your standing, ambient on the map (2026-08-18, user's call:
       "show public opinion and influence outside the overlay, in a very
       subdued way").
       TWO meters, not three. Money is deliberately absent: #fund-chip
       already folds the campaign's revenue into the FY2027 figure and
       its surplus/deficit line (updateChip -> PolicyPanel.external), and
       a second money number on the same screen just asks the player to
       reconcile two headline figures. If money ever needs to read
       louder, make that balance line louder — do not add a fourth row
       here.
       Rules that must survive edits:
       - **SUBDUED means no chip.** Every other HUD element is a plate
         with a 2px white border and an outline; this one has no
         background, no border and no shadow, and sits at .58 opacity
         until hovered. The moment it grows chrome it competes with the
         End Turn button directly under it, which is the screen's
         primary verb.
       - **Built ONCE and updated in place** (`data-built`), the same
         lesson as renderMetrics and renderHudTimeline: replacing the
         innerHTML leaves the fill with no previous width to transition
         from, so the bar snaps on every change instead of sliding.
       - **No bump/flash.** Support and influence almost only move
         INSIDE the overlay, where this cluster is behind the scrim, so
         a flash would fire unseen; the overlay's own cards already own
         that job. The one beat it would land on is the turn ritual, and
         the trend arrow covers that better than a flash could.
       - The trend is measured from `S.weekBase`, snapshotted at the top
         of advanceWeek(), so it reads "what this week has done to you"
         and resets cleanly at each turn. */
    const renderHudStanding = () => {
      const el = $("hud-standing");
      if (!el) return;
      const ROWS = [
        { key: "support", cls: "hs-sup", label: "Support",
          tip: "Public support — spent at hearings and floor votes. " +
               "Loud, but only at specific moments." },
        { key: "influence", cls: "hs-inf", label: "Influence",
          tip: "Political influence — your standing inside the " +
               "building. Applies quietly to every scheduling decision." },
      ];
      if (!el.dataset.built) {
        el.innerHTML = ROWS.map((r) =>
          '<div class="hs-row ' + r.cls + '" title="' + esc(r.tip) + '">' +
          '<span class="hs-l">' + esc(r.label) + "</span>" +
          '<span class="hs-v"></span><span class="hs-t"></span>' +
          '<span class="hs-bar"><i></i></span></div>').join("");
        el.dataset.built = "1";
      }
      const base = S.weekBase || {};
      ROWS.forEach((r, i) => {
        const row = el.children[i];
        if (!row) return;
        const v = S.metrics[r.key];
        row.querySelector(".hs-bar i").style.width = v + "%";
        row.querySelector(".hs-v").textContent = Math.round(v);
        // trend since the week opened — no arrow at all when nothing has
        // moved, so a quiet week reads as quiet instead of as a zero
        const was = base[r.key] == null ? v : base[r.key];
        const d = Math.round(v - was);
        const t = row.querySelector(".hs-t");
        t.textContent = d === 0 ? "" : (d > 0 ? "▲" : "▼") + Math.abs(d);
        t.className = "hs-t" + (d > 0 ? " up" : d < 0 ? " down" : "");
      });
    };

    /* ---- the three campaign meters.
       Built ONCE and then updated in place — the old version rebuilt
       the innerHTML on every renderHead, which is why the bars snapped
       instead of sliding (a freshly inserted element has no previous
       width to transition from) and why a number could never count.
       Now a changed value counts up, its bar slides, and the card
       flashes its accent — so an effect line in the dialogue and the
       scoreboard above it read as one system. */
    let metricPrev = null;
    const renderMetrics = () => {
      const el = $("sess-metrics");
      if (!el) return;
      const now = { rev: S.metrics.revenueK, sup: S.metrics.support,
                    inf: S.metrics.influence };
      if (!el.dataset.built) {
        el.innerHTML =
          '<div class="metc m-rev" id="mc-rev" title="Net FY2027 ' +
          'revenue your campaign has moved">' + sym("revenue") +
          '<span class="ml">Revenue</span><span class="mv"></span></div>' +
          '<div class="metc m-sup" id="mc-sup" title="Spent at hearings ' +
          'and floor votes — loud, but only at specific moments">' +
          sym("support") + '<span class="ml">Public Support</span>' +
          '<span class="mv"></span><span class="bar"><i></i></span></div>' +
          '<div class="metc m-inf" id="mc-inf" title="Your standing ' +
          'inside the building — applies quietly to every scheduling ' +
          'decision">' + sym("influence") +
          '<span class="ml">Political Influence</span>' +
          '<span class="mv"></span><span class="bar"><i></i></span></div>';
        el.dataset.built = "1";
      }
      const prev = metricPrev || now;
      const card = (id) => $(id);
      const flash = (id, up) => {
        const c = card(id);
        if (!c || reduced()) return;
        c.classList.remove("bump-up", "bump-down");
        void c.offsetWidth;                    // restart the animation
        c.classList.add(up ? "bump-up" : "bump-down");
      };
      // revenue is signed and formatted; the sign class rides the card
      const rc = card("mc-rev");
      rc.classList.toggle("cost", now.rev < 0);
      rc.classList.toggle("gain", now.rev >= 0);
      countTo(rc.querySelector(".mv"), prev.rev, now.rev,
        (v) => (v < 0 ? "−" : "+") + fmtK(Math.abs(Math.round(v))) + "/yr");
      if (now.rev !== prev.rev) flash("mc-rev", now.rev > prev.rev);
      for (const k of ["sup", "inf"]) {
        const c = card("mc-" + k);
        countTo(c.querySelector(".mv"), prev[k], now[k],
          (v) => String(Math.round(v)));
        c.querySelector(".bar i").style.width = now[k] + "%";
        if (now[k] !== prev[k]) flash("mc-" + k, now[k] > prev[k]);
      }
      metricPrev = now;
    };

    /* ---- header + metrics bar */
    const renderHead = () => {
      const cal = calFor(S.week);
      const dateStr = dateRangeFor(S.week);
      $("tb-week-badge").textContent = "W" + S.week;
      $("tb-week-badge").title = dateStr;
      /* ONE masthead, in the panel's top-left corner: the stamped week
         numeral, the week's name, its phase and real dates. This is the
         old #sess-week row promoted INTO the title-chip slot — the two
         used to sit stacked, both naming the week, and the chip's own
         "The Campaign · Week N" said nothing the plate didn't. */
      $("session-title").innerHTML =
        '<span class="mast-no"><small>Week</small><b>' + S.week +
        "</b></span>" +
        '<span class="mast-t"><b>' + esc(cal.title) + "</b><small>" +
        esc(cal.phase) + (dateStr ? " · " + esc(dateStr) : "") +
        "</small></span>";
      renderTimeline();
      renderProgress($("sess-progress"), "show the calendar");
      renderHudTimeline();
      renderMetrics();
      renderHudStanding();
      renderTurnBtn();
    };

    /* ---- the End Turn button (bottom left, always on the map)
       One turn = one week, so this is the game's primary verb and it
       lives on the HUD, not inside the session overlay. Week 1 is the
       exception: its move is locking the agenda, so the button routes
       into the overlay instead of burning the week. The dot means the
       week still has something unspent (an unplayed event or your one
       action) — ending the turn skips it. */
    const renderTurnBtn = () => {
      const btn = $("turn-chip");
      if (!btn) return;
      const cal = calFor(S.week);
      const interim = S.week > data.sineDieWeek;
      const needAgenda = cal.agenda && !S.agendaLocked;
      // "unspent" = an unplayed event, or an OPENED action still unused —
      // a week whose event granted nothing has nothing pending
      const pending = !interim && !needAgenda &&
        (eventPending(cal) ||
          (!cal.noAction && weekOpen().acts.length &&
            S.actionWeek !== S.week));
      btn.disabled = interim;
      btn.querySelector(".tc-label").textContent = interim ? "Sine die" :
        "Week " + S.week + " · " + cal.title;
      btn.querySelector(".tc-act").innerHTML =
        (interim ? "Session over" :
          needAgenda ? "Set agenda ▸" :
          S.week === data.sineDieWeek ? "Leave the building ▸" :
          "End Turn ▸") +
        (pending ? '<span class="tc-dot" title="This week still has ' +
          'something unspent"></span>' : "");
      btn.title = interim ? "The session has adjourned" :
        needAgenda ? "Pick the bills you'll introduce, then the clock starts" :
        "Advance to week " + (S.week + 1);
    };

    /* ---- skill checks (2d6 + skill vs DC, Disco-style)
       Snake eyes always fail and boxcars always succeed, so the odds
       clamp to 2.8–97.2 — nothing in this building is ever certain.
       The odds are printed ON the button so the player can watch
       influence buy down a difficulty; that visibility is half the
       teaching. WHITE checks can be retried once something has
       actually changed; RED checks are one shot, forever. */
    const DC_NAME = { 6: "Trivial", 8: "Easy", 10: "Medium",
      12: "Challenging", 14: "Formidable", 16: "Legendary",
      18: "Godly", 20: "Heroic" };
    const P2D6 = { 2: 97.2, 3: 97.2, 4: 91.7, 5: 83.3, 6: 72.2, 7: 58.3,
      8: 41.7, 9: 27.8, 10: 16.7, 11: 8.3, 12: 2.8 };
    const oddsFor = (need) =>
      P2D6[Math.max(2, Math.min(12, need))];
    const dcName = (dc) => DC_NAME[dc] ||
      DC_NAME[Object.keys(DC_NAME).map(Number)
        .reduce((a, b) => (Math.abs(b - dc) < Math.abs(a - dc) ? b : a))];

    // one modifier line — returns {n, label} so the roll can show its work
    const modOf = (m) => {
      const per = m.per || 1;
      let n = 0, label = "";
      if (m.add != null && m.from !== "flag") { n = m.add; label = m.label || ""; }
      switch (m.from) {
        case "support":
          n = Math.floor(S.metrics.support / per); label = "Public Support"; break;
        case "influence":
          n = Math.floor(S.metrics.influence / per); label = "Political Influence"; break;
        case "skill":
          n = Math.floor((S.skills[m.id] || 0) / per);
          label = (data.skills[m.id] || {}).name || m.id; break;
        case "flag":
          n = S.flags[m.id] != null ? (m.add != null ? m.add : 1) : 0;
          label = m.label || m.id; break;
        case "chair":   // chairs land in feature 11 step 2; absent = 0
          n = Math.floor(((S.chairs || {})[m.id] || 0) / per);
          label = m.label || "the chair"; break;
        default: break;
      }
      return { n, label };
    };

    const checkMath = (chk) => {
      const skill = S.skills[chk.skill] || 0;
      const mods = (chk.mods || []).map(modOf).filter((m) => m.n);
      const bonus = skill + mods.reduce((a, m) => a + m.n, 0);
      const need = chk.dc - bonus;
      return { skill, mods, bonus, need, odds: oddsFor(need) };
    };

    const rollCheck = (chk) => {
      const m = checkMath(chk);
      const d1 = 1 + Math.floor(ROT.RNG.getUniform() * 6);
      const d2 = 1 + Math.floor(ROT.RNG.getUniform() * 6);
      const sum = d1 + d2;
      const ok = sum === 12 ? true : sum === 2 ? false :
        sum + m.bonus >= chk.dc;
      return Object.assign(m, { d1, d2, sum, total: sum + m.bonus, ok });
    };

    // a red check is spent forever; a white one reopens when the
    // bonus improves — "nothing has changed" is itself a lesson
    const checkState = (key, chk) => {
      const rec = S.checks[key];
      if (!rec) return { done: false };
      if (rec.ok || chk.type === "red") return { done: true, rec };
      return { done: checkMath(chk).bonus <= rec.bonus, rec };
    };

    /* The settled roll card. `.settled` arms the entrance animations
       (dice land, verdict stamps in); `.jack`/`.snake` are the rare
       loud ones — boxcars gets a gold burst, snake eyes a shake. */
    const rollHtml = (chk, r) => {
      const sk = data.skills[chk.skill] || { name: chk.skill };
      const bits = [sk.name + " +" + r.skill].concat(
        r.mods.map((m) => m.label + " +" + m.n));
      const spec = r.sum === 12 ? " jack" : r.sum === 2 ? " snake" : "";
      return '<div class="sd-roll settled ' + (r.ok ? "ok" : "no") +
        " r-" + (chk.type || "white") + spec + '"><b>' +
        (sym(chk.skill) || sym("dice")) + " " +
        esc(sk.name) + ' — <span class="sd-stamp">' +
        (r.ok ? "SUCCESS" : "FAILURE") + "</span>" +
        (r.sum === 12 ? ' <span class="sd-spec">double sixes</span>' :
          r.sum === 2 ? ' <span class="sd-spec">snake eyes</span>' : "") +
        "</b>" +
        "<small>" + sym("dice") +
        ' <span class="die">' + r.d1 + '</span> + <span class="die">' +
        r.d2 + "</span> = " + r.sum + " · " +
        esc(bits.join(" · ")) + " · <b>" + r.total + "</b> vs " +
        chk.dc + " " + dcName(chk.dc).toLowerCase() + "</small></div>";
    };

    /* ---- the roll POPS OUT (2026-08-15, user's call).
       The inline card stays and is still the RECEIPT — the thing the
       player scrolls back to, and the thing that greys out with the
       rest of the transcript. The TRAY is the theatre: a dice tray
       centered over the whole panel, real pip faces tumbling, landing
       in a stagger, the arithmetic ticking in under them and the
       verdict slamming down as a stamp.
       Engineering rules that must survive edits:
       - **JS timers own the state machine; CSS owns only the look.** A
         hidden document freezes the animation clock dead, so no step
         may hang off `animationend` — the tray would never leave and
         would sit on top of the game forever. Same frozen-clock rule
         as screenSwap / wk-open / the deal, but load-bearing here.
       - **The tray never takes input** (`pointer-events: none` on the
         wrapper). The choice strip is already emptied while the dice
         are out, so there is nothing to guard, and a tray that somehow
         outlived its timers must not be able to trap the player.
       - `kill()` is idempotent and ALSO runs on a long safety timeout,
         so the tray is removed and `finish()` runs exactly once even if
         a step is missed. Never make finish() reachable only through
         the happy path. */
    const PIPS = { 1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8],
                   5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8] };
    const pipHtml = (n) => {
      const on = PIPS[n] || PIPS[1];
      let h = "";
      for (let i = 0; i < 9; i++) {
        h += "<i" + (on.indexOf(i) > -1 ? ' class="on"' : "") + "></i>";
      }
      return h;
    };
    /* The die is a real 3D cube now (2026-08-21, user's call: "i want
       the dice to look like they're actually rolling") — six pip faces
       on a .tcube that CSS spins through the air; the flat square that
       flickered its face every 75ms never read as rolling. setFace no
       longer swaps pips: it sets the cube's INLINE transform to the
       orientation that puts face n in front, with a full extra turn on
       each axis so the CSS transition reads as the roll decelerating.
       State lives in the inline style, so a frozen animation clock in
       a hidden tab still shows the right face — the animation is only
       the look, per the tray's house rule. */
    const FACE_ROT = { 1: [0, 0], 2: [0, -90], 3: [-90, 0],
                       4: [90, 0], 5: [0, 90], 6: [0, 180] };
    const dieHtml = () => {
      let h = '<span class="tcube">';
      for (let n = 1; n <= 6; n++) {
        h += '<b class="tf tf' + n + '">' + pipHtml(n) + "</b>";
      }
      return h + "</span>";
    };
    const setFace = (el, n) => {
      const o = FACE_ROT[n] || FACE_ROT[1];
      el.querySelector(".tcube").style.transform =
        "rotateX(" + (o[0] + 360) + "deg) rotateY(" + (o[1] - 360) + "deg)";
      el.dataset.n = n;
    };
    /* The verdict has to be READABLE, not merely shown. T_HOLD is the
       dwell AFTER the stamp lands, and it was 560ms (2026-08-15) —
       with the 300ms fade that gave the player under a second to take
       in SUCCESS/FAILURE plus the arithmetic that produced it, which
       read as the tray slamming shut on the result rather than
       presenting it. Raised to 2200 (2026-08-18, user's call). Judge
       this number against the STAMP, not against mount: the tray is
       alive for T_TUMBLE + T_STAMP before the verdict exists, and the
       player is not reading anything during the tumble. */
    const T_TUMBLE = 820, T_STAMP = 380, T_HOLD = 2200, T_OUT = 300;
    const popTray = (chk, r, onLand, onGone) => {
      const panel = overlay.querySelector(".ovl-panel");
      if (!panel) { onLand(); onGone(); return; }   // no stage, no show
      const sk = data.skills[chk.skill] || { name: chk.skill };
      const bits = [sk.name + " +" + r.skill].concat(
        r.mods.map((m) => m.label + " +" + m.n));
      const spec = r.sum === 12 ? " jack" : r.sum === 2 ? " snake" : "";
      const wrap = document.createElement("div");
      wrap.className = "sd-tray in r-" + (chk.type || "white") + spec;
      wrap.innerHTML =
        '<div class="tray-card">' +
        '<div class="tray-skill">' + (sym(chk.skill) || sym("dice")) +
        " " + esc(sk.name) + "</div>" +
        '<div class="tray-dice"><span class="tdie"></span>' +
        '<span class="tdie"></span></div>' +
        '<div class="tray-dc">vs ' + chk.dc + " · " +
        esc(dcName(chk.dc).toLowerCase()) + "</div>" +
        '<div class="tray-math"></div>' +
        '<div class="tray-stamp"></div></div>';
      panel.appendChild(wrap);
      const dice = wrap.querySelectorAll(".tdie");
      for (const d of dice) d.innerHTML = dieHtml();
      /* The cubes spin in CSS while airborne; this interval is now
         only the SOUND of it. ONE tick per cycle, not one per die —
         two transients 0ms apart phase into a single louder click and
         the dice stop sounding like two objects. SFX.dieTick is
         deliberately almost nothing at this rate; see its note. */
      const iv = setInterval(() => SFX.dieTick(), 75);
      SFX.dieTick();
      let dead = false, landed = false;
      const timers = [];
      const at = (ms, fn) => timers.push(setTimeout(fn, ms));
      // idempotent, and kill() runs it if it somehow hasn't — otherwise
      // an early teardown would leave the receipt reading "the dice are
      // out" forever with the outcome already appended under it
      const land = () => {
        if (landed) return;
        landed = true;
        onLand();
      };
      const kill = () => {
        if (dead) return;
        dead = true;
        clearInterval(iv);
        for (const t of timers) clearTimeout(t);
        land();
        if (wrap.parentNode) wrap.parentNode.removeChild(wrap);
        onGone();
      };
      at(T_TUMBLE, () => {
        clearInterval(iv);
        // class FIRST, faces second: .landed swaps the cube from its
        // spin animation to a transform transition, and the inline
        // transform has to land while that transition is live or the
        // cube snaps to its face instead of rolling into it
        wrap.classList.add("landed");
        setFace(dice[0], r.d1);
        setFace(dice[1], r.d2);
        // the dice slam down staggered in CSS, so they land staggered
        // in the ear too — SFX.dieLand offsets itself by index
        SFX.dieLand(0);
        SFX.dieLand(1);
        wrap.querySelector(".tray-math").innerHTML =
          "<b>" + r.d1 + "</b> + <b>" + r.d2 + "</b> · " +
          esc(bits.join(" · ")) + " · <b>" + r.total + "</b>";
      });
      at(T_TUMBLE + T_STAMP, () => {
        /* The verdict sting fires WITH the stamp, which is the moment
           the result becomes true — the same instant the receipt
           settles and the scene washes. Snake eyes and boxcars get
           their own tail on top, matching the extra 700ms those hold
           for and the gold burst / shake they already carry. */
        if (r.ok) SFX.win(); else SFX.lose();
        if (r.sum === 12) SFX.jackpot();
        else if (r.sum === 2) SFX.snake();
        wrap.classList.add(r.ok ? "ok" : "no");
        wrap.querySelector(".tray-stamp").innerHTML =
          (r.ok ? "SUCCESS" : "FAILURE") +
          (r.sum === 12 ? '<small>double sixes</small>' :
            r.sum === 2 ? '<small>snake eyes</small>' : "");
        land();                         // settle the receipt behind it
      });
      const hold = T_HOLD + (spec ? 700 : 0);
      at(T_TUMBLE + T_STAMP + hold, () => wrap.classList.add("out"));
      at(T_TUMBLE + T_STAMP + hold + T_OUT, kill);
      // …and a backstop, in case any step above was missed
      at(T_TUMBLE + T_STAMP + hold + T_OUT + 4000, kill);
    };

    // the card while the dice are still out — same frame, no verdict
    const rollingHtml = (chk) => {
      const sk = data.skills[chk.skill] || { name: chk.skill };
      return '<div class="sd-roll rolling r-' + (chk.type || "white") +
        '"><b>' + (sym(chk.skill) || sym("dice")) + " " + esc(sk.name) +
        ' — <span class="sd-wait">the dice are out</span></b>' +
        "<small>" + sym("dice") +
        ' <span class="die">?</span> + <span class="die">?</span>' +
        "</small></div>";
    };

    /* ---- dialogue runner (skill voices chime in) */
    /* Disco's dialogue form: NAME – line, every voice in its own color,
       continuation lines hanging under the text rather than the name.
       Skill voices take their color from their POLE (session.json
       skills.*.pole), the way Disco's take theirs from the parent
       attribute — six shades of the same gold is an unreadable wall;
       three families you can learn is not. The old PROGRESSIVE/
       CONSERVATIVE trait system is retired (2026-08-14) — it's the
       player's own instincts commenting, not an ideology. */
    const dash = '<span class="sd-dash">–</span>';
    // voices pipe up one after another — a small stagger per voice (the
    // beat wrapper animates as a whole; each voice re-enters on its own
    // delay on top of that, which reads as the instincts chiming in)
    const voiceHtml = (voices) => (voices || []).map((v, i) => {
      const sk = data.skills[v.t];
      if (!sk) return "";
      return '<div class="sd-voice v-skill p-' + (sk.pole || "bridge") +
        '" style="animation-delay:' + (140 + i * 110) + 'ms"><b>' +
        sym(v.t) + " " + sk.name.toUpperCase() + "</b>" + dash +
        esc(v.text) + "</div>";
    }).join("");

    /* ---- the character card: who you are actually talking to, held on
       screen for the length of the conversation (2026-08-15, user's
       call; rebuilt as a PORTRAIT RAIL 2026-08-18, user's call).
       It is now what the reference actually does: a tall portrait
       ATTACHED TO THE WINDOW — flush against the panel's left frame,
       full height, the transcript reading in a column beside it —
       rather than the wide dossier plate that used to sit above the
       text. The plate was a header the eye skipped past; the rail is a
       person you are standing in front of, which is the entire point of
       keeping them up. The 3:4 drawing below exists FOR that rail: the
       old 80x80 square was a thumbnail and blew up to mush at rail size.
       Layout is CSS-only (`.sd-scene.has-card`, added by showCard) and
       is gated to >=900px — narrow screens keep the horizontal plate,
       which is the right shape when there is no room for a column.
       PORTRAITS ARE FACELESS — the same house rule as the event banners
       and the skill glyphs. A committee desk, a nameplate, shoulders
       and a head in silhouette; no features, ever. The character reads
       as an office and a posture, which is what they are to the player.
       Bigger makes that rule HARDER, not easier: at 180px a silhouette
       has room to look like it is missing a face, so the drawing has to
       carry a lit edge and a real room behind it to read as deliberate.
       Only characters with a `card` in session.json get one, so an
       incidental speaker doesn't get a dossier. */
    /* Drawn in a 120x160 box — a 3:4 PORTRAIT, not the old 80x80
       thumbnail. The rail renders it 180px wide, where the square
       version was a head floating in a lot of nothing. Rules the
       drawing follows, all house rules from the banners:
       - no features, ever; the silhouette and the room do the work
       - ONE gold accent, and for a chair it is the NAMEPLATE
       - one hard key light: the lit edge down the head and shoulder is
         the only non-duotone ink, and it is what stops a big silhouette
         reading as an error. Keep its opacity low — at full strength it
         becomes a second accent and fights the nameplate.
       - the desk CUTS the figure. A whole free-standing body reads as a
         chess piece; a bust behind a desk reads as a man in an office,
         the same draw-order trick the w1 banner's railings use. */
    const PORTRAIT = {
      chairdesk:
        '<svg viewBox="0 0 120 160" aria-hidden="true">' +
        // the room: two high windows with daylight in them, mullioned,
        // over a panelled wall. The windows are the LIGHT SOURCE and
        // they are why the figure has a lit edge at all — without them
        // the rim below reads as an outline rather than as light.
        '<g fill="currentColor">' +
        '<rect x="3" y="9" width="31" height="62" rx="1.5" opacity=".28"/>' +
        '<rect x="86" y="9" width="31" height="62" rx="1.5" opacity=".28"/>' +
        '<rect x="17.5" y="9" width="2" height="62" opacity=".13"/>' +
        '<rect x="100.5" y="9" width="2" height="62" opacity=".13"/>' +
        '<rect x="3" y="37" width="31" height="2" opacity=".13"/>' +
        '<rect x="86" y="37" width="31" height="2" opacity=".13"/>' +
        '<rect x="0" y="84" width="120" height="2.2" opacity=".13"/></g>' +
        // The CHAIR BACK, wider than his shoulders. This is the single
        // element that stops the drawing reading as the universal
        // avatar glyph: a circle on a dome IS that icon, and no amount
        // of lighting fixes it, but a circle on a dome in a chair is a
        // man sitting down. Do not remove it to "simplify".
        '<rect x="25" y="68" width="70" height="58" rx="8" ' +
        'fill="currentColor" opacity=".3"/>' +
        // shoulders, neck and head — silhouette only, no features. The
        // head is an ELLIPSE, not a circle, and the neck is drawn: both
        // are cheap and both push it further from the avatar icon.
        '<path d="M15,126 C15,101 30,87 60,87 C90,87 105,101 105,126 Z" ' +
        'fill="currentColor"/>' +
        '<rect x="52" y="76" width="16" height="13" fill="currentColor"/>' +
        '<ellipse cx="60" cy="61" rx="19.5" ry="22" fill="currentColor"/>' +
        // the key light off the windows, raking the left edge. White at
        // this opacity, NOT a lighter blue: the silhouette is already a
        // pale blue (.cc-art sets the ink), so a tinted rim disappears
        // into it — the first pass used #f4f1e8 at .2 and was invisible
        // at display size.
        '<g fill="none" stroke="#ffffff" stroke-linecap="round" ' +
        'opacity=".34">' +
        '<path d="M60,39 A19.5,22 0 0 0 42,70" stroke-width="3"/>' +
        '<path d="M19,122 C19,103 31,89 55,88" stroke-width="2.6"/></g>' +
        // the collar, cut in the panel ground so it reads as a suit
        '<path d="M49,91 L60,111 L71,91" fill="none" stroke="#0d1234" ' +
        'stroke-width="5" stroke-linejoin="round"/>' +
        // the desk he schedules from: the slab, the paperwork that is
        // the actual job, and the nameplate. The nameplate is the ONE
        // gold accent — house rule is one per drawing, and a chair IS
        // his nameplate. A gavel was tried and cut: it collided with
        // the desk edge and made two accents.
        '<rect x="0" y="122" width="120" height="38" ' +
        'fill="currentColor" opacity=".55"/>' +
        '<rect x="0" y="122" width="120" height="2.8" ' +
        'fill="currentColor"/>' +
        '<g fill="currentColor" opacity=".78">' +
        '<rect x="8" y="127" width="26" height="15" rx="1"/>' +
        '<rect x="11" y="124" width="26" height="15" rx="1"/></g>' +
        '<rect x="45" y="132" width="54" height="17" rx="2" ' +
        'fill="#f2c14e"/>' +
        '<rect x="51" y="139" width="42" height="3.4" rx="1.7" ' +
        'fill="#8a6a15"/></svg>',
    };
    /* The quote is NOT duplicated into session.json — it is read live
       from chairs.json `voice` through the chair whose `char` points
       back at this character, so a chair's own words can never drift
       between the two files. CH is declared later in this same closure
       but only ever READ at call time, long after init has run. */
    const chairVoiceFor = (sid) => {
      const chairs = (typeof CH !== "undefined" && CH.chairs) || {};
      for (const id of Object.keys(chairs)) {
        if (chairs[id].char === sid && chairs[id].voice) {
          return chairs[id].voice;
        }
      }
      return "";
    };
    /* A card may carry a `photo` instead of an `art` drawing: a crop of
       the SAME photograph the character's banner is cut from
       (tools/make_portrait_art.py → assets/portraits/<id>.png). For a
       character who already appears photographically in a banner, a
       drawn silhouette in the rail beside it was two different people;
       the crop cannot drift from the banner because it IS the banner's
       source. `art` is still the route for anyone with no photograph,
       and those stay FACELESS — the house rule is unchanged for
       drawings, the photo is a documented exception for named external
       actors (2026-08-19, user's call).
       Slug-filtered, not esc()'d: this lands in a src attribute and
       esc() deliberately leaves quotes alone. `?v=` here is by hand —
       the pre-commit hook only rewrites tokens inside HTML. */
    const PORTRAIT_V = 2;
    const portraitHtml = (c, sid) => {
      const p = (c.photo || "").replace(/[^a-z0-9_-]/gi, "");
      if (p) {
        return '<img src="assets/portraits/' + p + ".png?v=" +
          PORTRAIT_V + '" alt="">';
      }
      return PORTRAIT[c.art] || sym(sid) || "";
    };
    const charCardHtml = (sid, who) => {
      const c = who.card || {};
      const quote = chairVoiceFor(sid);
      return '<div class="cc-art' + (c.photo ? " cc-photo" : "") + '">' +
        portraitHtml(c, sid) + "</div>" +
        '<div class="cc-body"><div class="cc-name">' +
        esc(who.name || "") + "</div>" +
        '<div class="cc-role">' + esc(c.title || who.role || "") +
        "</div>" +
        ((c.tags || []).length
          ? '<div class="cc-tags">' + c.tags.map((t) =>
            "<span>" + esc(t) + "</span>").join("") + "</div>"
          : "") +
        (c.note ? '<div class="cc-note">' + esc(c.note) + "</div>" : "") +
        (quote ? '<div class="cc-quote">' + esc(quote) + "</div>" : "") +
        "</div>";
    };

    // one spoken line, DE format — speaker in caps and color, role
    // dimmed. `sid` (the character key) picks the custom glyph; the
    // data icon is only a fallback for unmapped characters.
    const saidHtml = (who, text, cls, sid) =>
      '<div class="sd-said' + (cls ? " " + cls : "") + '"><b class="sd-who">' +
      (sym(sid) || (who.icon ? who.icon + " " : "")) +
      esc((who.name || "").toUpperCase()) +
      "</b>" + (who.role ? '<span class="sd-role">' + esc(who.role) +
        "</span>" : "") + dash + esc(text) + "</div>";

    /* The dialogue reader is a RUNNING TRANSCRIPT, the way the reference
       plays it: nothing is replaced, everything accumulates in `.sd-log`.
       When the scene advances, every beat already on screen ages to grey
       (`.sd-past` — opacity + a touch of desaturation, so the colored
       names dim WITH their text instead of glowing out of a grey page),
       the new beat animates in bright, and the view keeps itself pinned
       to the bottom. Choices live in a separate `.sd-play` strip under
       the log — they are UI, not transcript, and vanish once spent
       (the picked one re-enters the log as YOUR line). */
    const showDialogue = (dlgId, onDone) => {
      const dlg = data.dialogues[dlgId];
      if (!dlg) { onDone(); return; }
      overlay.classList.remove("creating");   // a scene is never the select screen
      body.dataset.view = "";
      /* `.sd-pre` is the transcript from BEFORE anyone is on stage —
         the breezeway you waited in, the room before the door opened.
         It is a separate box only so the portrait rail can start where
         the character does; see showCard. */
      body.innerHTML = '<div class="sd-scene">' +
        '<div class="sd-pre" id="sd-pre"></div>' +
        '<div class="sd-card" id="sd-card"></div>' +
        '<div class="sd-log"></div><div class="sd-play"></div></div>';
      const logEl = body.querySelector(".sd-log");
      const preEl = body.querySelector("#sd-pre");
      const play = body.querySelector(".sd-play");
      const cardEl = body.querySelector("#sd-card");
      let shownArt = "";
      /* Bumped by every renderNode. The banner's load handler uses it to
         tell "the image finally decoded on the beat it belongs to" from
         "the player has already advanced" — see the handler for why a
         DOM-shape guard cannot do this job. */
      let renderSeq = 0;
      /* The card follows whoever is SPEAKING, and a node with no
         speaker (narration, the room, your own campaign) leaves it
         alone — you are still standing in front of the same person
         while the prose describes the hallway. */
      let cardWho = "";
      const showCard = (sid) => {
        if (!sid || sid === cardWho) return;
        const who = data.characters[sid];
        if (!who || !who.card) return;
        /* THE PORTRAIT ARRIVES WITH THE PERSON AND NOT ONE BEAT EARLIER
           (2026-08-18, user's call — "if there's an event beforehand, I
           don't want the portrait to show until the time is right").
           Two halves, and the second is the one that is easy to miss:
           - It only ever fires on a node whose `speaker` IS this
             character, so a scene that opens on narration (w5-decking
             waits in the breezeway before Kawaguchi's door opens) shows
             no portrait at all. That half was already true.
           - **The beats already on screen move OUT of the rail's
             column.** Without this, the whole scene reflowed the
             instant he appeared and the breezeway — text and banner
             both, from before he was in the room — ended up sitting
             beside his portrait, retroactively. He was not there yet;
             the transcript should not say he was. So the first time a
             card turns on, everything rendered so far is handed to
             `.sd-pre`, which spans the full width above the rail, and
             the rail governs only what happens from his arrival on.
           A later card SWAP (a second character taking over a scene)
           deliberately does NOT re-split: the rail is already the right
           shape by then, and N sections would just be N narrow columns. */
        const firstArrival = !cardWho;
        cardWho = sid;
        cardEl.innerHTML = charCardHtml(sid, who);
        cardEl.classList.add("on");
        if (firstArrival) {
          while (logEl.firstChild) preEl.appendChild(logEl.firstChild);
        }
        /* `has-card` on the SCENE is what turns the layout into the
           portrait rail — the two-column grid has to be declared on the
           parent, and a scene with no portrait must stay exactly the
           single-column block it has always been (most scenes have no
           card at all, and that path is untouched by this). */
        const sceneEl = body.querySelector(".sd-scene");
        if (sceneEl) sceneEl.classList.add("has-card");
        // restart the entrance when the card swaps mid-scene
        cardEl.classList.remove("in");
        void cardEl.offsetWidth;
        cardEl.classList.add("in");
      };
      // both boxes: the pre-arrival transcript is still the transcript
      const agePast = () => {
        for (const el of preEl.children) el.classList.add("sd-past");
        for (const el of logEl.children) el.classList.add("sd-past");
      };
      const append = (html) => {
        if (!html) return;
        const w = document.createElement("div");
        w.className = "sd-beat";
        w.innerHTML = html;
        logEl.appendChild(w);
      };
      /* keep the newest beat in view without yanking the reader past it:
         land the TOP of the new content near the top of the viewport
         when it is long, or just scroll to the end when it is short.

         `artTop` is the second half of the fix for "the images are hard
         to see" (2026-08-18, user's call). The banner is the scene's
         establishing shot and it arrives in the SAME render as the line
         under it, so the plain rule above — which only ever looks at
         the last beat — scrolled a 480px banner up until 40px of it was
         left, every time, before the player had looked at it. Sizing
         the file up does nothing about that; a taller picture just gets
         scrolled further. So when a render introduces new art, the
         scroll is additionally capped at KEEP of the banner's height,
         which leaves most of the picture on screen with the text and
         the choices still pulled up into view under it.
         Deliberately a CAP and not a jump-to-the-art: forcing scrollTop
         to the banner's top would put the choice strip below the fold
         on every scene that opens with a picture, which trades one
         invisible thing for a worse one. */
      const settle = (artEl) => {
        requestAnimationFrame(() => {
          const last = logEl.lastElementChild;
          if (!last) return;
          /* offsetTop is NOT usable here: the nearest positioned
             ancestor is `.ovl-panel`, not the scrolling `#sess-body`,
             so every offsetTop in this panel is inflated by the whole
             masthead + timeline + meters stack (~191px on a laptop)
             while scrollTop is measured from the body. Both branches
             below were therefore scrolling ~191px too far on every
             beat, which is what pushed a freshly-arrived banner off the
             top of the screen before the player could look at it. Read
             positions off getBoundingClientRect instead — it does not
             care what the offsetParent happens to be. */
          const bTop = body.getBoundingClientRect().top;
          const topOf = (el) =>
            el.getBoundingClientRect().top - bTop + body.scrollTop;
          const lastTop = topOf(last);
          const want = lastTop + play.offsetHeight +
            last.offsetHeight - body.clientHeight;
          let top = Math.min(lastTop - 14, Math.max(0, want));
          if (artEl) {
            /* Hold the banner on screen — but never at the price of the
               player not knowing they have choices. `peek` is the least
               scroll that still shows the top of the choice strip; on a
               normal window it is the smaller number and the art keeps
               ~2/3 of itself, on a short one it wins and the art gives
               ground. An unconditional art cap was tried first and left
               a 720px-tall window showing a picture and no options. */
            const KEEP = 0.68, PEEK = 44;
            const peek = topOf(play) + PEEK - body.clientHeight;
            top = Math.min(top, Math.max(
              topOf(artEl) + artEl.offsetHeight * (1 - KEEP), peek));
          }
          body.scrollTop = Math.max(0, top);
        });
      };

      const renderNode = (nodeId) => {
        renderSeq++;
        const n = dlg[nodeId];
        // no `speaker` = a faceless narrative injection (the campaign,
        // the coalition, the room) rather than a named individual —
        // rendered as unattributed prose, same as a choice's `reply`
        const who = n.speaker ? data.characters[n.speaker] : null;
        showCard(n.speaker);
        // choices with no `check` behave exactly as they always have
        const btnHtml = (c, i) => {
          const num = '<span class="sd-num">' + (i + 1) + ".</span>";
          if (!c.check) {
            return '<button type="button" data-i="' + i + '">' + num +
              '<span class="sd-lbl">' + esc(c.label) + "</span></button>";
          }
          const key = dlgId + ":" + nodeId + ":" + i;
          const st = checkState(key, c.check);
          const m = checkMath(c.check);
          const sk = data.skills[c.check.skill] ||
            { name: c.check.skill };
          /* An ANTE is printed on the button with the odds, for the same
             reason the odds are: an unadvertised charge is not a
             decision, it is a surprise. Only the two meters can be
             staked — anything else in a checked choice's effects block
             still applies, it just isn't priced here. */
          const ante = [];
          if (c.effects) {
            if (c.effects.support) {
              ante.push("Support " + (c.effects.support > 0 ? "+" : "") +
                c.effects.support);
            }
            if (c.effects.influence) {
              ante.push("Influence " + (c.effects.influence > 0 ? "+" : "") +
                c.effects.influence);
            }
          }
          const meta = st.done
            ? (st.rec.ok ? "✓ passed" :
                c.check.type === "red" ? "✗ spent — one shot only" :
                "✗ failed · nothing has changed since")
            : (sym(c.check.skill) || sym("dice")) + " " + sk.name + " · " +
              dcName(c.check.dc) + " · " + m.odds.toFixed(0) + "%" +
              (ante.length ? " · costs " + esc(ante.join(", ")) +
                " either way" : "");
          return '<button type="button" data-i="' + i + '" class="chk c-' +
            (c.check.type || "white") + (st.done ? " spent" : "") + '"' +
            (st.done ? " disabled" : "") + ">" + num +
            '<span class="sd-lbl">' + esc(c.label) +
            '<small class="cmeta p-' + (sk.pole || "bridge") + '">' + meta +
            "</small></span></button>";
        };
        agePast();
        // event banner: `art` on the node, else on the dialogue — drawn
        // once per distinct image, as a beat in the flow (a node-level
        // override like w2's office appends mid-scene). The id is
        // slug-filtered rather than esc()'d — esc() leaves quotes alone,
        // which is fine for text but would break out of an attribute.
        const art = String(n.art || dlg.art || "").replace(/[^a-z0-9_-]/gi, "");
        let artEl = null;
        if (art && art !== shownArt) {
          shownArt = art;
          append('<img class="sd-art" alt="" src="assets/events/' +
            art + '.png">');
          artEl = logEl.lastElementChild;   // the beat wrapping the img
          /* A NOT-YET-DECODED <img> measures 0 tall, and settle() runs
             on the next frame — so on a cold load every scroll sum
             above is computed against a banner that is not there yet,
             and the layout jump when it decodes lands the reader
             somewhere nobody chose. (This is why the old rule looked
             fine while clicking around with a warm cache and dumped the
             banner off screen on a real first visit.) Re-settle once,
             on load, and only while this is still the beat on stage —
             a player who has already advanced must not be yanked. */
          const img = artEl.querySelector("img");
          if (img && !img.complete) {
            const seq = renderSeq;
            img.addEventListener("load", () => {
              // only while this is still the beat on stage — a player
              // who has already advanced must not be yanked back. It
              // has to be a render counter and NOT the log's shape:
              // this runs mid-render, before the spoken beat below is
              // appended, so any child count captured here is stale by
              // the end of the very same renderNode call.
              if (seq === renderSeq) settle(artEl);
            }, { once: true });
          }
        }
        append((who ? saidHtml(who, n.text, "", n.speaker) :
          '<div class="sd-narr">' + esc(n.text) + "</div>") +
          voiceHtml(n.voices));
        play.innerHTML = '<div class="sd-choices">' +
          n.choices.map(btnHtml).join("") + "</div>";
        settle(artEl);
        for (const btn of play.querySelectorAll(".sd-choices button")) {
          if (btn.disabled) continue;
          btn.addEventListener("pointerdown", (ev) => {
            ev.stopPropagation();
            SFX.choice();
            const i = +btn.dataset.i;
            const c = n.choices[i];
            // roll first — the outcome branch decides everything below
            let roll = null, out = c;
            if (c.check) {
              roll = rollCheck(c.check);
              S.checks[dlgId + ":" + nodeId + ":" + i] =
                { ok: roll.ok, week: S.week, bonus: roll.bonus };
              out = (roll.ok ? c.success : c.failure) || {};
            }
            S.log.push(Object.assign(
              { week: S.week, dlg: dlgId, choice: c.label },
              roll ? { check: c.check.skill, dc: c.check.dc,
                       ok: roll.ok, total: roll.total } : {}));
            save();
            // the line you picked reads back as YOUR line; the response
            // stays unattributed because authored `reply` text is a mix
            // of spoken answers and pure narration ("The gallery claps…")
            // — putting a speaker's name on narration would be a lie
            agePast();
            /* the outcome beat. Effects apply HERE, not at pick time —
               with a staged roll the metric cards sit in view above the
               scene, and a support tick landing before the stamp would
               spoil the verdict a beat early */
            const finish = () => {
              /* THE ANTE (2026-08-21): a CHECKED choice's own `effects`
                 block is the stake — paid on commit, win or lose, on
                 top of whichever outcome block lands. It is what lets
                 content spend a meter to reach for something, which is
                 how support is supposed to work and previously never
                 could (nothing in the game spent it). An UNCHECKED
                 choice is unaffected: there `effects` is the outcome
                 itself, and out === c, so this would double-apply —
                 hence the `roll &&` guard.
                 It lands here, inside finish(), and not at pick time,
                 because of the documented rule that no metric may move
                 before the verdict is stamped: a support tick over the
                 dice spoils the roll a beat early. Rendered as its own
                 line, before the outcome's, so the player can see they
                 paid it either way. */
              const anteHtml = roll && c.effects ? applyFx(c.effects) : "";
              const fxHtml = applyFx(out.effects);
              append((out.reply ? '<div class="sd-narr">' +
                esc(out.reply) + "</div>" : "") +
                voiceHtml(out.voices) + anteHtml + fxHtml);
              play.innerHTML = '<button class="sd-done"' +
                (out.goto ? ' data-goto="' + out.goto + '"' : "") +
                ' type="button">Continue ▸</button>';
              settle();
              const done = play.querySelector(".sd-done");
              done.addEventListener("pointerdown", (ev2) => {
                ev2.stopPropagation();
                SFX.choice();
                if (done.dataset.goto) renderNode(done.dataset.goto);
                else onDone();
              });
            };
            if (!roll) {
              append(saidHtml({ name: "You" }, c.label, "sd-you"));
              finish();
              return;
            }
            /* ---- the staged roll: tumble → land → stamp → outcome.
               The choice strip empties for the duration, so nothing is
               clickable while the dice are out. Reduced-motion players
               get the old instant resolution. */
            const RM = window.matchMedia &&
              matchMedia("(prefers-reduced-motion: reduce)").matches;
            if (RM) {
              append(saidHtml({ name: "You" }, c.label, "sd-you") +
                rollHtml(c.check, roll));
              finish();
              return;
            }
            append(saidHtml({ name: "You" }, c.label, "sd-you") +
              rollingHtml(c.check));
            play.innerHTML = "";
            settle();
            // a RED check is spent forever — the room goes quiet for it:
            // everything already in the transcript drops away while the
            // dice are out, so the only lit thing is the roll you can
            // never take back. White checks don't get this.
            const sceneEl = body.querySelector(".sd-scene");
            if (sceneEl && c.check.type === "red") {
              sceneEl.classList.add("hush");
            }
            const beatEl = logEl.lastElementChild;
            const dice = beatEl.querySelectorAll(".die");
            const iv = setInterval(() => {
              for (const d of dice) {
                d.textContent = 1 + Math.floor(Math.random() * 6);
              }
            }, 75);
            /* The tray drives the whole beat now. Its stamp is the
               moment the verdict becomes true, so the receipt settles
               and the scene washes THERE — not when the tray leaves,
               or the transcript would lag the announcement. `finish()`
               waits for the tray to be gone, so effects still land
               after the verdict is shown (the documented rule: a
               support tick before the stamp spoils it). */
            popTray(c.check, roll, () => {
              clearInterval(iv);
              const rollEl = beatEl.querySelector(".sd-roll");
              if (rollEl) rollEl.outerHTML = rollHtml(c.check, roll);
              // verdict wash over the whole scene, restartable
              const scene = body.querySelector(".sd-scene");
              if (scene) {
                scene.classList.remove("hush", "wash-ok", "wash-no");
                void scene.offsetWidth;
                scene.classList.add(roll.ok ? "wash-ok" : "wash-no");
              }
            }, finish);
          });
        }
      };
      renderNode("start");
    };

    /* ---- creation: SELECT INSTINCTS, Disco archetype-screen style.
       Six glyph cards instead of three painted archetypes — same 5-point
       spend underneath (the wiring below targets [data-skill] .skup
       either way). Symbols are inline SVG, duotone: the pole color via
       currentColor, one gold accent per glyph (the overlay's #f2c14e).
       No faces, per the house art rule — the glyphs are the portrait. */
    /* Each glyph's moving parts carry `g-*` classes so the select screen
       can ANIMATE them (CSS, `.skc-art` scope — the glyphs render nowhere
       else). Draw-loop strokes carry pathLength="100" so one shared
       dasharray works for every path regardless of true length. The
       loops are phase-shifted so keyframe 0% is the RESTING drawn state:
       a hidden document freezes the animation clock at currentTime 0,
       and a loop that starts from "invisible" would screenshot as a
       missing limb (same clock rule as screenSwap/countTo). */
    const GLYPH = {
      fiscal:
        '<svg viewBox="0 0 120 84">' +
        // the brain BEHIND the chart — faint currentColor outline, so it
        // reads as the thought under the numbers, not a second subject
        '<g class="g-brain" fill="none" stroke="currentColor" ' +
        'stroke-width="3" stroke-linecap="round" opacity=".18">' +
        '<path d="M24,52 C14,50 12,38 20,32 C16,22 26,12 36,16 ' +
        'C40,6 56,4 62,12 C72,4 88,8 90,20 C100,24 102,38 94,44 ' +
        'C96,54 86,62 76,58 C68,68 52,68 46,60 C38,64 28,60 24,52 Z"/>' +
        '<path d="M46,14 C48,26 44,34 50,44"/>' +
        '<path d="M64,12 C60,26 66,36 60,50"/>' +
        '<path d="M78,18 C74,28 80,38 74,50"/></g>' +
        '<g class="g-bars" fill="currentColor">' +
        '<rect x="16" y="48" width="15" height="24" opacity=".5"/>' +
        '<rect x="39" y="36" width="15" height="36" opacity=".7"/>' +
        '<rect x="62" y="22" width="15" height="50" opacity=".9"/>' +
        "</g>" +
        '<polyline class="g-line" pathLength="100" ' +
        'points="14,54 46,38 72,24 96,13" fill="none" ' +
        'stroke="#f2c14e" stroke-width="4.5" stroke-linecap="round"/>' +
        '<circle class="g-dot" cx="99" cy="12" r="7" fill="#f2c14e"/>' +
        "</svg>",
      procedure:
        '<svg viewBox="0 0 120 84"><path class="g-maze" ' +
        'pathLength="100" d="M10,74 L110,74 L110,10 ' +
        'L10,10 L10,58 L94,58 L94,26 L26,26 L26,44 L72,44" fill="none" ' +
        'stroke="currentColor" stroke-width="5" stroke-linejoin="miter"/>' +
        '<circle class="g-dot" cx="78" cy="44" r="5.5" fill="#f2c14e"/>' +
        "</svg>",
      educator:
        '<svg viewBox="0 0 120 84">' +
        '<path d="M60,66 L18,57 L18,27 L60,36 Z" fill="currentColor" ' +
        'opacity=".35" stroke="currentColor" stroke-width="4" ' +
        'stroke-linejoin="round"/>' +
        '<path d="M60,66 L102,57 L102,27 L60,36 Z" fill="currentColor" ' +
        'opacity=".65" stroke="currentColor" stroke-width="4" ' +
        'stroke-linejoin="round"/>' +
        '<g class="g-rays" stroke="#f2c14e" stroke-width="4" ' +
        'stroke-linecap="round">' +
        '<line x1="60" y1="26" x2="60" y2="8"/>' +
        '<line x1="41" y1="28" x2="30" y2="12"/>' +
        '<line x1="79" y1="28" x2="90" y2="12"/></g></svg>',
      talkstory:
        '<svg viewBox="0 0 120 84">' +
        '<rect x="12" y="12" width="58" height="34" rx="9" ' +
        'fill="currentColor" opacity=".3"/>' +
        '<path d="M26,44 L20,60 L42,46" fill="currentColor" opacity=".3"/>' +
        '<rect x="50" y="28" width="58" height="34" rx="9" fill="none" ' +
        'stroke="currentColor" stroke-width="4.5"/>' +
        '<path d="M94,61 L100,76 L78,62" fill="none" ' +
        'stroke="currentColor" stroke-width="4.5" ' +
        'stroke-linejoin="round"/>' +
        '<g class="g-type" fill="#f2c14e">' +
        '<circle cx="56" cy="37" r="3.6"/>' +
        '<circle cx="66" cy="37" r="3.6"/>' +
        '<circle cx="76" cy="37" r="3.6"/></g></svg>',
      mobilizing:
        '<svg viewBox="0 0 120 84">' +
        '<rect x="12" y="34" width="10" height="18" rx="2" ' +
        'fill="currentColor" opacity=".6"/>' +
        '<path d="M22,36 L22,50 L58,64 L58,22 Z" fill="currentColor" ' +
        'opacity=".9"/>' +
        '<g class="g-waves" fill="none" stroke-linecap="round">' +
        '<path d="M68,32 a14,14 0 0 1 0,22" stroke="currentColor" ' +
        'stroke-width="4.5"/>' +
        '<path d="M78,24 a24,24 0 0 1 0,38" stroke="currentColor" ' +
        'stroke-width="4.5" opacity=".65"/>' +
        '<path d="M88,16 a34,34 0 0 1 0,54" stroke="#f2c14e" ' +
        'stroke-width="4.5"/></g></svg>',
      basebuilding:
        '<svg viewBox="0 0 120 84">' +
        '<path d="M30,34 A30,26 0 1 1 90,34 L82,38 L38,38 Z" ' +
        'fill="currentColor" opacity=".45" stroke="currentColor" ' +
        'stroke-width="4" stroke-linejoin="round"/>' +
        '<rect x="56" y="34" width="8" height="8" fill="currentColor"/>' +
        '<line x1="12" y1="42" x2="108" y2="42" stroke="currentColor" ' +
        'stroke-width="4" stroke-linecap="round"/>' +
        '<g class="g-roots" fill="none" stroke="#f2c14e" ' +
        'stroke-width="4" stroke-linecap="round">' +
        '<path pathLength="100" d="M60,42 C52,52 40,56 32,64"/>' +
        '<path pathLength="100" d="M60,42 C60,56 59,64 58,72"/>' +
        '<path pathLength="100" d="M60,42 C68,52 80,56 88,64"/>' +
        '<path pathLength="100" d="M56,50 C48,54 44,60 42,70"/>' +
        '<path pathLength="100" d="M64,50 C72,54 76,60 78,70"/></g>' +
        '<g class="g-nodes" fill="#f2c14e">' +
        '<circle cx="32" cy="66" r="4"/>' +
        '<circle cx="58" cy="74" r="4"/><circle cx="88" cy="66" r="4"/>' +
        '<circle cx="42" cy="72" r="3"/><circle cx="78" cy="72" r="3"/>' +
        "</g></svg>",
    };

    /* The card footer is a STEPPER, not a one-way ratchet: − and + flank
       the value, with the level's plain-language rank between the pole
       name and the box (a "3" means nothing until you know the ladder).
       − floors at `skStart.base` — a player can undo a pick but never
       spend below where everyone starts — and refunds the point, so the
       screen is fully reversible without leaving it. */
    const skSelectHtml = (cap, PO, order) => {
      const floor = skStart.base || 1;
      let h = '<div class="sk-select">' +
        '<div class="sk-title">Select instincts</div>' +
        '<div class="sk-ptchip"><b>' + S.skillPts + "</b> point" +
        (S.skillPts === 1 ? "" : "s") + " to spend · nothing above " +
        cap + " to start</div>" +
        '<button class="sk-reset" id="sk-reset" type="button"' +
        (S.skillPts >= (skStart.points || 0) ? " disabled" : "") +
        ">↺ Reset</button>" +
        '<div class="skc-grid">';
      for (const p of order) {
        for (const k of SK.filter(
          (q) => (data.skills[q].pole || "bridge") === p)) {
          const s = data.skills[k];
          const v = S.skills[k];
          const at = v >= cap;
          const down = v <= floor;
          h += '<div class="skc p-' + p + (at ? " capped" : "") +
            '" data-skill="' + k + '">' +
            '<div class="skc-art">' + (GLYPH[k] || "") + "</div>" +
            '<div class="skc-name">' + esc(s.name) + "</div>" +
            '<div class="skc-desc">' + esc(s.desc) + "</div>" +
            '<div class="skc-foot"><span class="skc-pole">' +
            esc((PO[p] || {}).name || p) + "</span>" +
            '<span class="skc-rank">' + esc(rankOf(v)) + "</span>" +
            '<span class="skc-step">' +
            '<button class="skdn" type="button" aria-label="Lower ' +
            escA(s.name) + '"' + (down ? " disabled" : "") + ">−</button>" +
            '<span class="skpip">' + v + "</span>" +
            '<button class="skup" type="button" aria-label="Raise ' +
            escA(s.name) + '"' + (at ? " disabled" : "") + ">+</button>" +
            "</span></div></div>";
        }
      }
      return h + "</div></div>";
    };

    /* ---- the creation funnel is a CORRIDOR, and moving along it looks
       like travel: Instincts → Priorities → Revenue, left to right. The
       outgoing screen slides off the way you came from, the incoming one
       arrives from the way you are going, and its cards rise in a short
       stagger behind it. Four rules hold this together:
       - **Only NAVIGATION calls this.** A bump or a policy pick
         re-renders the same screen by calling renderSelect() /
         renderAgendaSelect() directly. Replaying a 470ms slide on every
         + press would be unbearable, so the animation must never live
         in the renderers themselves.
       - **The classes go on the CHILDREN, never on `#sess-body`.** Both
         renderers do `body.innerHTML = …`, which throws the children
         away — so a class parked on a child cannot survive into the next
         render and re-fire the slide. A class on the scroller itself
         would, and would need cleanup timers to not.
       - `swapping` blocks re-entry only for the outgoing half; once the
         new screen is on stage the corridor is walkable again, so a
         quick second click feels responsive instead of dead.
       - **The arrival is force-landed on a wall clock** (CR_LAND), for
         the same reason countTo is: a HIDDEN document freezes the
         animation clock dead — playState stays "running" while
         currentTime never leaves 0 — and `both` fill would hold the
         screen at its `from` keyframe, which is opacity 0. A player who
         clicks Continue and switches tabs would come back to a blank
         creation screen. Stripping the class after the animation's own
         run time is a no-op when it did play (it ended on the natural
         state anyway) and a rescue when it didn't. CR_LAND must stay
         above the longest card stagger + duration (.25s + .38s).
       - Reduced motion resolves instantly — same path as the dice
         roll. Any new animation here goes in that CSS media block too. */
    const CR_OUT = 170, CR_LAND = 700, DEAL_MS = 1000;
    let swapping = false;
    const screenSwap = (fwd, render) => {
      if (reduced()) { body.scrollTop = 0; render(); return; }
      if (swapping) return;
      swapping = true;
      const out = fwd ? "cr-out-l" : "cr-out-r";
      const inn = fwd ? "cr-in-r" : "cr-in-l";
      // strip a still-running arrival first: `swapping` only guards the
      // outgoing half, so a quick second click lands here with cr-in-*
      // still on the children — and the in-rules sit LATER in the
      // stylesheet, so the leftover class would win the `animation`
      // shorthand and the screen would slide IN again instead of out
      for (const el of body.children) {
        el.classList.remove("cr-in-r", "cr-in-l");
        el.classList.add(out);
      }
      setTimeout(() => {
        body.scrollTop = 0;
        render();
        const arrived = [...body.children];
        for (const el of arrived) el.classList.add(inn);
        swapping = false;
        // …and land it whether or not the animation clock ever ran
        setTimeout(() => {
          for (const el of arrived) el.classList.remove(inn);
        }, CR_LAND);
      }, CR_OUT);
    };

    /* ---- creation is its OWN screen, and it comes first. Every entry
       point into the overlay funnels through renderHub, so one early
       bail here is what guarantees a fresh campaign opens on SELECT
       INSTINCTS and nothing else — no intel, no agenda, no event —
       until the points are spent and Continue is pressed. Bumps
       re-render THIS screen (preserving scroll); Continue is the only
       door out, and it stays shut while points remain. */
    const renderSelect = () => {
      // `creating` strips the session panel down to nothing but this
      // screen — week header, timeline, metrics, title chip, close X
      // and footer caption all go (CSS), and the panel goes full-bleed.
      // The class is removed in renderHub, which is the only way out.
      overlay.classList.add("creating");
      const cap = skStart.creationCap || 4;
      const PO = data.poles || {};
      const order = (PO.order || []).filter((p) => PO[p]);
      const left = S.skillPts;
      let html = skSelectHtml(cap, PO, order);
      html += '<button class="sk-begin" id="sk-begin" type="button"' +
        (left > 0 ? " disabled" : "") + ">" +
        (left > 0
          ? "Spend your " + left + " point" + (left > 1 ? "s" : "") +
            " to continue"
          : "Continue ▸") + "</button>";
      /* ENTRANCE vs re-render, decided by what was on stage BEFORE this
         render: a bump/drop/reset rebuilds a grid that already exists
         (no deal — replaying a card deal on every + press would be
         unbearable), while boot, the hub funnel and the ag-skills back
         plate all arrive with no .skc-grid in the body. */
      const entering = !body.querySelector(".skc-grid");
      const keep = body.scrollTop;         // bumps shouldn't jump the page
      body.innerHTML = html;
      body.scrollTop = keep;
      renderTurnBtn();
      if (entering && !reduced()) {
        const grid = body.querySelector(".skc-grid");
        if (grid) {
          // the cards deal out of a loose center stack (.deal in CSS);
          // stripped on a wall clock, same rule as screenSwap/wk-open —
          // a frozen animation clock would hold the hand stacked forever
          grid.classList.add("deal");
          setTimeout(() => grid.classList.remove("deal"), DEAL_MS);
        }
      }
      const floor = skStart.base || 1;
      for (const r of body.querySelectorAll(".skc")) {
        const k = r.dataset.skill;
        const up = r.querySelector(".skup");
        const dn = r.querySelector(".skdn");
        /* The click fires only where the value ACTUALLY moved — after
           the guard, never before it. A capped skill and a skill at the
           floor are both still live tap targets (the card is one big +1
           and the − has to stay clickable exactly where it matters
           most), so playing on entry would click at the player for
           doing nothing, which is worse than silence. */
        const bump = (ev) => {
          ev.stopPropagation();
          if (S.skillPts < 1 || S.skills[k] >= cap) return;
          S.skills[k] += 1;
          S.skillPts -= 1;
          SFX.pip(true);
          save();
          renderSelect();
        };
        const drop = (ev) => {
          ev.stopPropagation();
          if (S.skills[k] <= floor) return;
          S.skills[k] -= 1;
          S.skillPts += 1;
          SFX.pip(false);
          save();
          renderSelect();
        };
        // − is a child of the card, whose own pointerdown is +1, so its
        // handler MUST stopPropagation (it does) or lowering a skill
        // would immediately raise it again
        if (dn && !dn.disabled) dn.addEventListener("pointerdown", drop);
        // the whole card stays a +1 tap target, not just the + box —
        // but only while there is headroom to spend into
        if (up && !up.disabled) {
          up.addEventListener("pointerdown", bump);
          r.addEventListener("pointerdown", bump);
        }
      }
      const reset = body.querySelector("#sk-reset");
      if (reset && !reset.disabled) {
        reset.addEventListener("pointerdown", (ev) => {
          ev.stopPropagation();
          S.skills = baseSkills();
          S.skillPts = skStart.points || 0;
          // one click, not one per point refunded — a reset is a
          // single act, and a burst of six would read as six separate
          // things happening
          SFX.pip(false);
          save();
          renderSelect();
        });
      }
      const go = body.querySelector("#sk-begin");
      if (go && !go.disabled) go.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        // forward down the corridor — renderHub's own bail lands on the
        // agenda screen, since the points are by definition all spent
        screenSwap(true, renderHub);
      });
    };

    /* ---- creation screen two: BUILD YOUR PACKAGE, in TWO STEPS —
       what you're fighting FOR, then how you PAY for it. Same
       archetype-screen treatment as SELECT INSTINCTS (full-bleed
       `creating`, stencil title plate, glyph cards, one plate out),
       with a step rail across the top and a running ledger of the
       package on the footer plate.

       Splitting the pick in two IS the module's argument: the player
       chooses a cost and then has to look at what pays for it, instead
       of reading one flat list where a school-meals bill and a GET
       increase are the same kind of object.
       **There is NO CAP on either step** (2026-08-19, user's call:
       "allow users to choose as many investment priorities as they
       want, same for the tax options"). It used to be ≤3 shared across
       both steps, which made step 2 open with the budget possibly
       already spent — that scarcity was carrying the argument, and the
       argument now has to come from the tally and the gauntlet instead:
       a player who takes all six watches six bills go through the money
       committees and finds out what that costs in weeks and support.
       The floor stays: at least one bill, or there is no campaign.
       `agendaStep` is view state, deliberately NOT in S: reloading
       mid-pick should land you back on step 1 with your picks intact,
       not resume a half-finished wizard. */
    let agendaStep = 0;
    const AG_STEPS = [
      { key: "cost", title: "Choose your priorities",
        lede: "What the campaign is fighting for. These are not bills " +
          "you carry — they set the PRICE. Every one of them spends " +
          "money the state does not currently have.",
        kindLabel: "Invest" },
      { key: "gain", title: "Choose how to pay",
        lede: "These are the bills your introducers actually carry, " +
          "and the only measures the money committees will ever see. " +
          "Raising it is the whole session.",
        kindLabel: "Raise" },
    ];

    const renderAgendaSelect = () => {
      overlay.classList.add("creating");
      body.dataset.view = "";
      const step = AG_STEPS[agendaStep];
      const picked = allPolicies.filter((p) => S.agenda.includes(p.id));
      const mine = allPolicies.filter((p) => p.kind === step.key);
      const costs = picked.filter((p) => p.kind === "cost");
      const gains = picked.filter((p) => p.kind === "gain");
      const spend = costs.reduce((s, p) => s + p.amt, 0);
      const raise = gains.reduce((s, p) => s + p.amt, 0);
      // `n` is the BILL count — the revenue picks — everywhere the word
      // "bill" appears. The priorities are counted separately because
      // they are a price, not legislation.
      const n = gains.length;

      // step rail
      let html = '<div class="sk-select"><div class="ag-rail">';
      AG_STEPS.forEach((s, i) => {
        html += '<div class="ag-step ' +
          (i === agendaStep ? "now" : i < agendaStep ? "past" : "next") +
          '" data-step="' + i + '"><span class="ag-num">' + (i + 1) +
          '</span><span class="ag-lbl">' +
          (s.key === "cost" ? "Priorities" : "Revenue") + "</span></div>";
      });
      html += "</div>" +
        '<div class="sk-title">' + esc(step.title) + "</div>" +
        '<div class="ag-lede">' + esc(step.lede) + "</div>" +
        '<div class="sk-ptchip">' +
        (agendaStep === 0
          ? "<b>" + costs.length + "</b> priorit" +
            (costs.length === 1 ? "y" : "ies") + " chosen" +
            (spend ? " · " + fmtK(spend) + "/yr to find" : "")
          : "<b>" + n + "</b> tax bill" + (n === 1 ? "" : "s") +
            " chosen · " + fmtK(raise) + " of " + fmtK(spend)) +
        "</div><div class=\"agc-grid\">";
      for (const p of mine) {
        const on = S.agenda.includes(p.id);
        html += '<div class="agc ' + p.kind + (on ? " on" : "") +
          '" data-pol="' + p.id + '">' +
          '<div class="agc-art">' + (sym(p.id) || p.icon || "") + "</div>" +
          '<div class="agc-name">' + esc(p.name) + "</div>" +
          '<div class="agc-desc">' + esc(p.who || "") + "</div>" +
          (p.src ? '<div class="agc-src">' + esc(p.src) + "</div>" : "") +
          '<div class="agc-foot"><span class="agc-kind">' +
          step.kindLabel + "</span>" +
          '<span class="agc-amt">' + (p.kind === "cost" ? "−" : "+") +
          fmtK(p.amt) + '/yr</span><span class="agc-pick">' +
          (on ? "✓" : "+") + "</span></div></div>";
      }
      html += "</div></div>";

      // the package ledger rides on the footer, above the plate
      if (picked.length) {
        html += '<div class="ag-tally">' + picked.map((p) =>
          '<span class="agt ' + p.kind + '">' + (sym(p.id) || "") + " " +
          esc(p.name) + "</span>").join("") + "</div>";
      }
      /* There is always a way back up the corridor: from Revenue to
         Priorities, and from Priorities all the way out to the instinct
         screen. Before this, step 1 was a one-way door — you could
         revise your bills forever but never revisit the instincts you
         picked ninety seconds earlier. */
      html += '<div class="ag-nav">' +
        (agendaStep > 0
          ? '<button class="ag-back" id="ag-back" type="button">' +
            '<span class="agb-ar">◂</span>Priorities</button>'
          : '<button class="ag-back" id="ag-skills" type="button">' +
            '<span class="agb-ar">◂</span>Instincts</button>') +
        (agendaStep < AG_STEPS.length - 1
          ? '<button class="sk-begin" id="ag-next" type="button">' +
            "How do we pay for it ▸</button>"
          : '<button class="sk-begin" id="sess-lock" type="button"' +
            (n && costs.length ? "" : " disabled") + ">" +
            /* TWO gates now, and they fail in the order the corridor
               walks: no tax bill means there is no campaign to run,
               and no priority means there is nothing the money is FOR.
               The second message has to name step 1 explicitly — it is
               the one case where the button you are looking at is
               blocked by a screen behind you. */
            (!n ? "Choose at least one tax bill to continue"
              : !costs.length
                ? "◂ Choose a priority for the money to fund"
                : "Hand " + n + " bill" + (n === 1 ? "" : "s") +
                  " to your introducers ▸") + "</button>") +
        "</div>";

      const keep = body.scrollTop;         // bumps shouldn't jump the page
      body.innerHTML = html;
      body.scrollTop = keep;
      renderTurnBtn();
      for (const r of body.querySelectorAll(".agc")) {
        r.addEventListener("pointerdown", (ev) => {
          ev.stopPropagation();
          const id = r.dataset.pol;
          if (S.agenda.includes(id)) {
            S.agenda = S.agenda.filter((x) => x !== id);
          } else {
            S.agenda.push(id);
          }
          save();
          renderAgendaSelect();
        });
      }
      // the rail is navigable too — a player who wants to revise
      // priorities after seeing the price shouldn't have to back out
      // every step change slides, and the direction is which way along
      // the corridor you are walking — a rail jump backwards must not
      // animate forwards or the motion lies about where you went
      const goStep = (i) => {
        if (i === agendaStep) return;
        const fwd = i > agendaStep;
        agendaStep = i;
        screenSwap(fwd, renderAgendaSelect);
      };
      for (const r of body.querySelectorAll(".ag-step")) {
        r.addEventListener("pointerdown", (ev) => {
          ev.stopPropagation();
          goStep(+r.dataset.step);
        });
      }
      const step2 = body.querySelector("#ag-next");
      if (step2) step2.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        goStep(1);
      });
      const back = body.querySelector("#ag-back");
      if (back) back.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        goStep(0);
      });
      // all the way back out of the package and into the instincts —
      // renderSelect is called DIRECTLY, not through renderHub, whose
      // bail would just bounce straight back here once the points are
      // spent (skillPts is 0 by the time anyone reaches this screen)
      const toSkills = body.querySelector("#ag-skills");
      if (toSkills) toSkills.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        screenSwap(false, renderSelect);
      });
      const lock = body.querySelector("#sess-lock");
      if (lock && !lock.disabled) {
        lock.addEventListener("pointerdown", (ev) => {
          ev.stopPropagation();
          if (!S.agenda.length) return;
          S.agendaLocked = true;
          startBills();
          S.log.push({ week: S.week, agenda: [...S.agenda] });
          save();
          // the campaign is formed — now play the week's narrative,
          // if any is still waiting
          const cal = calFor(S.week);
          if (eventPending(cal)) runEvent();
          else renderHub();
        });
      }
    };

    /* ---- the character sheet, Disco-style: skills grouped under the
       campaign function they serve, each group in its own color, the
       level as a numeral rather than a row of dots (a numeral reads at
       a glance and doesn't imply the cap is a progress bar). Grouping +
       labels are data — session.json `poles`.
       The sheet no longer lives on the week hub (2026-08-15, user's
       call): it has its own toolbar tab (tb-instincts → renderSheet)
       and only intrudes on the hub when points are actually spendable. */
    const sheetHtml = () => {
      const cap = skStart.cap || 6;
      const PO = data.poles || {};
      const order = (PO.order || []).filter((p) => PO[p]);
      const seen = {};
      const skRow = (k) => {
        const s = data.skills[k];
        const v = S.skills[k];
        const honing = (S.train[k] || 0) > 0 && v < (skStart.cap || 6);
        return '<div class="sk-row" data-skill="' + k + '">' +
          '<span class="skpip' + (honing ? " honing" : "") + '" title="' +
          v + (honing ? " — honing: one more week of practice" : "") +
          '">' + v + "</span>" +
          '<span class="skname"><b>' + sym(k) + " " + esc(s.name) +
          "</b><small>" + esc(s.desc) + "</small></span>" +
          (S.skillPts > 0
            ? '<button class="skup" type="button"' +
              (v >= cap ? " disabled" : "") + ">+</button>"
            : "") + "</div>";
      };
      let h = '<div class="sk-sheet">';
      for (const p of order) {
        const ks = SK.filter((k) => (data.skills[k].pole || "bridge") === p);
        if (!ks.length) continue;
        ks.forEach((k) => { seen[k] = 1; });
        h += '<div class="sk-col p-' + p + '"><div class="sk-pole"><b>' +
          esc(PO[p].name || p) + "</b><small>" + esc(PO[p].sub || "") +
          "</small></div>" + ks.map(skRow).join("") + "</div>";
      }
      // any skill whose pole is missing from `order` still has to render
      const orphans = SK.filter((k) => !seen[k]);
      if (orphans.length) {
        h += '<div class="sk-col p-bridge">' +
          orphans.map(skRow).join("") + "</div>";
      }
      return h + "</div>";
    };
    const wireSkillUps = (rerender) => {
      for (const r of body.querySelectorAll("[data-skill]")) {
        const up = r.querySelector(".skup");
        if (!up || up.disabled) continue;
        up.addEventListener("pointerdown", (ev) => {
          ev.stopPropagation();
          if (S.skillPts < 1) return;
          S.skills[r.dataset.skill] += 1;
          S.skillPts -= 1;
          save();
          rerender();
        });
      }
    };

    /* the Instincts tab — the sheet as its own view, reachable from
       the toolbar any week. During creation it routes back into the
       renderHub funnel so the select screen stays the only door. */
    const renderSheet = () => {
      if (!S.agendaLocked) { renderHub(); return; }
      overlay.classList.remove("creating");
      body.dataset.view = "sheet";
      body.innerHTML =
        '<div class="sh-sec">Your instincts' +
        (S.skillPts ? " <small>" + S.skillPts + " point" +
          (S.skillPts > 1 ? "s" : "") + " to spend</small>" : "") +
        "</div>" + sheetHtml() +
        '<div class="sh-agenda-cap">Checks roll 2d6 + skill against a ' +
        "difficulty. Support and influence add to the roll — so does " +
        "being the kind of advocate who noticed. What you practice " +
        "each week, you sharpen.</div>";
      body.scrollTop = 0;
      renderTurnBtn();
      wireSkillUps(renderSheet);
    };

    /* ---- the week hub */
    const renderHub = () => {
      // creation is a two-screen funnel: instincts, then the agenda —
      // both full-bleed, and both gated here so every entry point lands
      // on the right screen until the campaign is actually formed
      if (!S.agendaLocked) {
        if (S.skillPts > 0) renderSelect();
        else renderAgendaSelect();
        return;
      }
      overlay.classList.remove("creating");
      body.dataset.view = "hub";
      const cal = calFor(S.week);
      const interim = S.week > data.sineDieWeek;
      let html = "";

      // what the gauntlet did while the week turned — leads the hub,
      // because "did my bill move" is the question the player opened with
      html += movesHtml();

      // the week's intel — what the campaign heard, as well as it can hear
      html += intelHtml();

      // instincts live on their own tab now — the hub only shows the
      // sheet when there is something to actually change (unspent
      // points on an old save)
      if (S.skillPts > 0) {
        html += '<div class="sh-sec">Your instincts <small>' +
          S.skillPts + " point" + (S.skillPts > 1 ? "s" : "") +
          " to spend</small></div>" + sheetHtml();
      }

      html += billLedger(interim);
      html += introStrip();

      // this week's event — the thing that opens every other door.
      // A week carrying a `pre` is not "handled" until BOTH scenes are
      // through, so this asks eventPending rather than eventDone alone.
      const evDone = !eventPending(cal);
      if (cal.event || cal.pre) {
        html += '<div class="sh-sec">This week</div>';
        html += '<div class="sh-row' + (evDone ? " done" : "") +
          '" data-ev="1"><span class="shname"><b>' + sym("event") + " " +
          (evDone ? "The week's event — handled" :
            "Something needs your attention") +
          "</b><small>" + (evDone ? "Choices made. The week rolls on." :
            "An event is waiting — what it opens up depends on how " +
            "it goes.") +
          "</small></span>" +
          '<button class="shgo" type="button"' + (evDone ? " disabled" : "") +
          ">" + (evDone ? "✓ Done" : "Open ▸") + "</button></div>";
      }

      // the agenda picker moved to its own creation screen
      // (renderAgendaSelect); the hub only ever restates a locked
      // agenda, and only until the ledger takes over
      if (S.agenda.length && !S.bills.length) {
        // only when the ledger isn't already showing them — billLedger
        // renders its own "Your bills" section the moment bills exist,
        // and both firing printed the heading twice
        html += gapHtml() + '<div class="sh-sec">Your bills</div>';
        for (const id of S.agenda) {
          const p = allPolicies.find((q) => q.id === id);
          // priorities are the PRICE and live in the gap block above;
          // this list is legislation only
          if (p && p.kind === "gain") {
            html += '<div class="sh-row"><span class="shname"><b>' +
              (sym(p.id) || p.icon) + " " + esc(p.name) +
              '</b></span><span class="shtag ' +
              p.kind + '">+' + fmtK(p.amt) + "/yr</span></div>";
          }
        }
      }

      /* openings — talk story and actions the WEEK has granted. There
         is no weekly allowance any more: an unplayed event means closed
         doors, and an event can grant different doors depending on how
         it went (choice-level fx.unlock). */
      const open = weekOpen();
      const talkIds = Object.keys(open.talks).filter(
        (cid) => data.characters[cid]);
      if (talkIds.length) {
        html += '<div class="sh-sec">Openings — talk story</div>';
        for (const cid of talkIds) {
          const who = data.characters[cid];
          const talked = (S.talked[S.week] || []).includes(cid);
          html += '<div class="sh-row' + (talked ? " done" : "") +
            '" data-talk="' + cid + '"><span class="shname"><b>' +
            (sym(cid) || who.icon) + " " + esc(who.name) + "</b><small>" +
            esc(who.role) + "</small></span>" +
            '<button class="shgo" type="button">' +
            (talked ? "Again ▸" : "Talk ▸") + "</button></div>";
        }
      }

      // the granted action(s) — still at most ONE spend per week
      const canPush = open.acts.includes("push");
      const actIds = open.acts.filter((aid) => data.actions[aid]);
      if (!cal.noAction && !interim && (canPush || actIds.length)) {
        const used = S.actionWeek === S.week;
        html += '<div class="sh-sec">Openings — your move (' +
          (used ? "used this week" : "one per week") + ")</div>";
        if (canPush) {
          for (const b of liveBills()) {
            const sid = b.route[b.stage];
            if (stageOf(sid).gate !== "chair") continue;
            const ch = chairOf(sid);
            if (!ch) continue;
            const stDl = stageOf(sid);
            const dlLeft = stDl.deadline != null ?
              stDl.deadline - S.week : null;
            html += '<div class="sh-row" data-push="' + b.id +
              '"><span class="shname"><b>' + sym("push") + " Work " +
              esc(ch.name) +
              // the offer names what the push is worth AT THIS BILL'S
              // influence, not a constant — the whole point of scaling
              // it is that the player can watch the price of their own
              // standing on the button before spending the week
              "</b><small>spend the week on " + esc(b.name) + " — " +
              Math.round(pushBonus(bInf(b)) * 100) +
              " points of scheduling odds" +
              (dlLeft != null ? ' · <b class="dl' +
                (dlLeft <= 1 ? " dl-soon" : "") + '">' +
                (dlLeft <= 0 ? "deadline week" :
                  "deadline week " + stDl.deadline) + "</b>" : "") +
              "</small></span>" +
              '<button class="shgo" type="button"' +
              (used ? " disabled" : "") +
              ">" + (used ? "—" : "Act ▸") + "</button></div>";
          }
        }
        for (const aid of actIds) {
          const a = data.actions[aid];
          html += '<div class="sh-row" data-act="' + aid +
            '"><span class="shname"><b>' + (sym(aid) || a.icon) + " " +
            esc(a.name) +
            "</b><small>" + esc(a.desc) + "</small></span>" +
            '<button class="shgo" type="button"' +
            (used ? " disabled" : "") + ">" +
            (used ? "—" : "Act ▸") + "</button></div>";
        }
      } else if (!cal.noAction && !interim && evDone && !talkIds.length) {
        // the event granted nothing — say so, or the missing sections
        // read as a bug rather than a closed building
        html += '<div class="sh-sec">Openings</div>' +
          '<div class="sh-agenda-cap">The week didn’t open any ' +
          "doors — no meeting stuck, no moment worth spending. End it " +
          "when you’re ready.</div>";
      }

      // end of week
      if (interim) {
        const enacted = S.bills.filter((b) => b.status === "enacted");
        const raised = enacted.filter((b) => b.kind === "gain")
          .reduce((s, b) => s + b.amtK * b.amtScale, 0);
        const funded = enacted.filter((b) => b.kind === "cost")
          .reduce((s, b) => s + b.amtK * b.amtScale, 0);
        const unheard = S.bills.filter(
          (b) => b.death && b.death.cause === "never heard").length;
        html += '<div class="sh-sec">Sine die</div>' +
          '<div class="sess-score"><b>' + fmtK(raised) + "/yr raised · " +
          fmtK(funded) + "/yr funded</b><small>" +
          // the verdict keys on what actually passed — an earlier version
          // branched on `funded` alone and told a player who had just
          // enacted a revenue bill that nothing became law
          (!enacted.length
            ? "Nothing the campaign carried became law."
            : funded && raised >= funded
              ? "You paid for what you passed."
              : funded
                ? "You funded " + fmtK(funded - raised) + "/yr more than " +
                  "you raised — next year's problem, and it always is."
                : "You raised the money and funded none of it. The surplus " +
                  "is somebody else's argument now.") +
          "</small></div>" +
          (unheard ? '<div class="sh-agenda-cap">' + unheard + " of your bills " +
            "died without a hearing — no vote was taken, and no record " +
            "exists of anyone killing them. That is how most bills die." +
            "</div>" : "");
      } else {
        const skipping = !cal.noAction && S.actionWeek !== S.week &&
          (canPush || actIds.length);
        html += '<button class="sh-week-end" id="sess-next" type="button">' +
          (S.week === data.sineDieWeek ? "Leave the building ▸" :
            "End Week " + S.week + " ▸") + "</button>" +
          (skipping ? '<div class="sh-agenda-cap">An opening is ' +
            "unused — ending the week lets it close.</div>" : "");
      }

      body.innerHTML = html;
      body.scrollTop = 0;
      renderTurnBtn();

      // wiring
      wireSkillUps(renderHub);
      countPm();                     // death cards + any open ledger one
      for (const t of body.querySelectorAll(".pm-tgl")) {
        if (!t.textContent) continue;      // sine die renders it open
        t.addEventListener("pointerdown", (ev) => {
          ev.stopPropagation();
          const bd = t.parentElement.querySelector(".pm-body");
          const nowOpen = !bd.classList.toggle("hidden");
          t.textContent = nowOpen ? "Why it died ▾" : "Why it died ▸";
          // display:none → block restarts the row cascade for free;
          // the count-up needs asking
          if (nowOpen) countPm(bd);
        });
      }
      const evRow = body.querySelector('[data-ev] .shgo:not([disabled])');
      if (evRow) evRow.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        runEvent();
      });
      for (const r of body.querySelectorAll("[data-talk]")) {
        r.querySelector(".shgo").addEventListener("pointerdown", (ev) => {
          ev.stopPropagation();
          const cid = r.dataset.talk;
          (S.talked[S.week] = S.talked[S.week] || []).push(cid);
          save();
          showDialogue(open.talks[cid], renderHub);
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
      for (const r of body.querySelectorAll("[data-push]")) {
        const btn = r.querySelector(".shgo");
        if (btn.disabled) continue;
        btn.addEventListener("pointerdown", (ev) => {
          ev.stopPropagation();
          const b = S.bills.find((x) => x.id === r.dataset.push);
          const ch = chairOf(b.route[b.stage]);
          S.actionWeek = S.week;
          S.pushWeek = S.week;
          S.pushBill = b.id;
          // pushing is inside-game work on THIS bill specifically, so it
          // also raises the bill's own influence, on top of the one-week
          // odds bonus — the two effects overlap in the moment (this
          // week's roll) and then influence's gain persists after.
          // It lands in `earned`, the only per-bill store left: the
          // bill's live number is the campaign's meter plus its tilt
          // plus exactly this. `b` is the actual S.bills element, so
          // mutating it in place mutates the saved state directly.
          b.earned = b.earned || { support: 0, influence: 0 };
          b.earned.influence += (G.pushInfluence || 4);
          S.log.push({ week: S.week, action: "push", bill: b.id });
          const trHtml = train("procedure");
          save();
          renderHead();
          body.innerHTML =
            '<div class="sd-speaker"><b>' + sym("push") +
            " Working the building</b>" +
            "<small>your action this week</small></div>" +
            '<div class="sd-text">' + esc(
              "You spend the week in " + ch.name + "'s outer office, on " +
              b.name + ". You are not the only one waiting.") + "</div>" +
            (ch.voice ? '<div class="sd-reply">' + esc(ch.voice) +
              "</div>" : "") +
            '<div class="sd-fx"><span class="gain">Scheduling odds +' +
            Math.round(pushBonus(bInf(b)) * 100) +
            ' next week</span><span class="gain">' + sym("influence") +
            " " + esc(b.name) +
            "'s influence +" + (G.pushInfluence || 4) +
            "</span></div>" + trHtml +
            '<button class="sd-done" type="button">Continue ▸</button>';
          body.querySelector(".sd-done").addEventListener("pointerdown",
            (e2) => { e2.stopPropagation(); SFX.choice(); renderHub(); });
        });
      }
      const next = body.querySelector("#sess-next");
      if (next) next.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        advanceWeek();
      });
    };

    /* Has this week got narrative still waiting? BOTH halves count — a
       week may carry a `pre` (the storm at week 7) in front of its own
       event, and every gate that decides whether to pop the panel has
       to ask about the pair, not just `cal.event`. */
    const eventPending = (cal) =>
      (!!cal.pre && !S.preDone.includes(S.week)) ||
      (!!cal.event && !S.eventDone.includes(S.week));

    const runEvent = () => {
      const cal = calFor(S.week);
      /* THE PRE RUNS FIRST AND IS MARKED THE MOMENT IT FINISHES, not
         when the week's own event does. The player can close the panel
         in the gap between the two scenes — mark them together and the
         storm replays every time they reopen it. */
      if (cal.pre && !S.preDone.includes(S.week)) {
        const pre = data.dialogues[cal.pre] || {};
        showDialogue(cal.pre, () => {
          if (!S.preDone.includes(S.week)) {
            S.preDone.push(S.week);
            grantUnlocks(pre.unlocks);
          }
          save();
          if (cal.event && !S.eventDone.includes(S.week)) runEvent();
          else renderHub();
        });
        return;
      }
      const dlg = data.dialogues[cal.event] || {};
      showDialogue(cal.event, () => {
        if (!S.eventDone.includes(S.week)) {
          S.eventDone.push(S.week);
          // the event is what opens the week's doors — dialogue-level
          // grants land here; choice-dependent ones already landed via
          // applyFx(fx.unlock) as the choice resolved
          grantUnlocks(dlg.unlocks);
        }
        save();
        renderHub();
      });
    };

    /* A skilled organizer gets more out of the SAME action, not a
       different one: session.json `scale.mods` reuses the identical
       {from, per} shape as check mods (modOf) — e.g. Grassroots turns
       a rally's support up and its influence cost down. Bonuses only
       add (never subtract), same as a check bonus, so this stays
       purely upside for the skill named. */
    const scaledFx = (a) => {
      const fx = Object.assign({}, a.effects || {});
      for (const s of (a.scale || {}).mods || []) {
        const m = modOf(s);
        if (m.n) fx[s.on] = (fx[s.on] || 0) + m.n;
      }
      return fx;
    };

    const runAction = (aid) => {
      const a = data.actions[aid];
      S.actionWeek = S.week;
      const fxHtml = applyFx(scaledFx(a));
      const trHtml = train(a.trains);
      S.log.push({ week: S.week, action: aid });
      save();
      body.innerHTML =
        '<div class="sd-speaker"><b>' + (sym(aid) || a.icon) + " " +
        esc(a.name) +
        "</b><small>your action this week</small></div>" +
        '<div class="sd-text">' + esc(a.result) + "</div>" +
        voiceHtml(a.voices) + fxHtml + trHtml +
        '<button class="sd-done" type="button">Continue ▸</button>';
      body.querySelector(".sd-done").addEventListener("pointerdown",
        (ev) => { ev.stopPropagation(); SFX.choice(); renderHub(); });
    };

    /* Advancing can be triggered from the HUD with the overlay closed —
       an unplayed event must pop the panel itself, or the new week's
       dialogue would render into a hidden body. */
    /* ---- the gauntlet (feature 11 step 2)
       A bill does not pass or fail — it moves, or it stops moving. Every
       committee stage is a CHAIR deciding whether to put it on a hearing
       calendar at all, and the deadline behind that decision is the real
       killer: miss it and the bill is dead with no vote, no roll call and
       no record. That is the most common death in the building.

       The scheduling probability starts from a MEASURED base rate —
       map/hearing_rates.json, regenerated by the Legislative Research
       Tool from the Legislature's own referral sheets, chamber journals
       and hearing notices — and the editorial terms (chair disposition,
       your influence, your support, your weekly action) are added on top.
       Keep those halves separate: the player can read the measured number
       in the tooltip, and it must stay honest. */
    const CH = chairData || { chairs: {}, stages: {}, routes: {}, gate: {} };
    const G = CH.gate || {};
    const RATES = (rateData || {}).committees || {};

    const chairOf = (id) => CH.chairs[id] || null;
    const stageOf = (id) => CH.stages[id] || { label: id, gate: "auto" };
    const routeFor = (kind) => (CH.routes || {})[kind] || [];

    /* ---- your two introducers (2026-08-15)
       The Advocate has no seat, so two members carry the package: the
       House introducer files it and walks it through Finance and the
       House floor, the Senate introducer picks it up at crossover. Who
       is on point is DERIVED from the stage's chamber — never stored per
       bill, because every module-1 bill runs the same House-first route
       and a per-bill copy would drift.

       Rapport (0-100) enters the odds ZERO-CENTRED on
       gate.introBaseline: at the starting value the term is exactly 0,
       so the simulation-calibrated enact-rate bands in the design doc
       still hold for a player who never works the relationship. Only
       the swing away from baseline is new. Do not "simplify" this into
       a plain rapport/div term — that pays out at baseline and silently
       re-tunes every band. */
    const INTROS = CH.introducers || {};
    const introKeys = () =>
      Object.keys(INTROS).filter((k) => k[0] !== "_");
    const introName = (who) => (INTROS[who] || {}).name || who;
    const introRap = (who) => S.intro[who] != null ? S.intro[who]
      : ((INTROS[who] || {}).rapport || 0);
    const seedIntroducers = () => {
      for (const k of introKeys()) {
        if (S.intro[k] == null) S.intro[k] = INTROS[k].rapport || 50;
      }
    };
    // the member carrying a bill at this stage; "both" chambers (conf,
    // final) answer with whichever relationship is stronger — they are
    // both in the room by then
    const carrierFor = (sid) => {
      const cham = stageOf(sid).chamber;
      if (cham && INTROS[cham]) return cham;
      const ks = introKeys();
      if (!ks.length) return null;
      return ks.reduce((a, b) => (introRap(b) > introRap(a) ? b : a));
    };
    const introEdge = (sid, div) => {
      const who = carrierFor(sid);
      if (!who) return 0;
      return (introRap(who) - (G.introBaseline != null ? G.introBaseline : 50)) /
        (div || 400);
    };

    /* Measured hearing rate for THIS committee and THIS kind of tax bill.
       A tax bill is not one thing: pooled across 2025–26 the building
       noticed 43% of tax-credit measures and 25% of measures taxing
       wealth. Averaging those into one "revenue" rate erases the single
       distinction the player is meant to feel, so the bill's tax family
       (policies.json `tax`) picks the cell. Thin cells fall back to the
       committee's all-tax rate, then to every measure — and the export
       records WHICH, so the tooltip never passes a borrowed number off as
       a measured one. */
    const rateFor = (cmte, kind, tax) => {
      const r = RATES[cmte];
      if (!r) return { v: 0.35, basis: "none", n: 0 };
      const cell = tax && r.types ? r.types[tax] : null;
      if (cell && cell.rate != null) {
        return { v: cell.rate, basis: cell.basis, n: cell.referred,
                 fallbackN: r.topic_referred };
      }
      const topic = kind === "gain" ? r.topic_rate : r.approp_rate;
      if (topic != null) {
        return { v: topic, basis: kind === "gain" ? "revenue" : "appropriation",
                 n: kind === "gain" ? r.topic_referred : r.approp_referred };
      }
      return { v: r.rate == null ? 0.35 : r.rate, basis: "all",
               n: r.referred };
    };
    const baseRate = (cmte, kind, tax) => rateFor(cmte, kind, tax).v;

    const TAXLABEL = ((rateData || {}).tax_types) || {};
    const rateNote = (cmte, kind, tax) => {
      const r = RATES[cmte];
      if (!r) return "";
      const g = rateFor(cmte, kind, tax);
      const yrs = ((rateData || {}).sessions || []).join("/");
      const what = g.basis === "type"
        ? (TAXLABEL[tax] || {}).label || tax
        : g.basis === "revenue" ? "tax measures"
        : g.basis === "appropriation" ? "spending measures" : "measures";
      let s = (r.name || cmte) + " noticed " + Math.round(g.v * 100) +
        "% of the " + what.toLowerCase() + " referred to it — n=" + g.n +
        ", sessions " + yrs + ".";
      if (g.basis !== "type" && tax) {
        s += " (Too few " + ((TAXLABEL[tax] || {}).label || tax).toLowerCase() +
          " bills at this committee to measure on their own, so this is its " +
          "rate for all " + (kind === "gain" ? "tax" : "spending") +
          " bills.)";
      }
      return s;
    };

    /* The measured rate is the chance a committee EVER noticed a measure
       across its whole referral window — not a weekly chance. Rolling it
       once a week compounds it into a far easier gate than the data says
       (four weeks at 32% a week is an 79% chance of being heard, which is
       not what House Finance does). Convert the window probability into a
       per-week hazard so the cumulative odds over the stage's window come
       out at exactly the measured number.

       The window is fixed when the bill ENTERS the stage, not recomputed
       from the weeks remaining: recomputing multiplies survival by
       (1-p)^(1/n) · (1-p)^(1/(n-1)) · … whose exponents sum to the harmonic
       number H_n > 1, quietly making every gate easier than measured. */
    const weekHazard = (p, weeksLeft) =>
      weeksLeft <= 1 ? p : 1 - Math.pow(1 - p, 1 / weeksLeft);

    const align = (kind, stance) =>
      stance === "hold" ? 0 :
      (kind === "gain") === (stance === "raise") ? 1 : -1;

    /* ---- A BILL'S SUPPORT AND INFLUENCE ARE DERIVED, NEVER STORED
       (2026-08-21). They used to be absolute numbers copied off the
       campaign's meters ONCE, at agenda lock, and then never written
       again by any code path. Three things followed, all bad:
         - after week 1 the two HUD meters touched no bill's odds at
           all, so a season of rallying changed no hearing probability
           and the meters' own tooltips ("spent at hearings and floor
           votes") were flavour rather than mechanics;
         - agenda lock happens inside the creation funnel, BEFORE any
           event fx can run, so every campaign's bills seeded at
           exactly 50/30 + tilt — the seed was a constant dressed as
           a reading of the player's campaign;
         - dilution (`support < floor`) could therefore never fire,
           because nothing could ever lower a bill's support.
       Now a bill stores only what is genuinely ITS OWN — the family
       `tilt` (editorial, fixed at introduction) and whatever the
       player bought FOR IT (`earned`, currently the push) — and the
       live number is read through the campaign's meter. Same rule as
       targetK()/raisedK(): the campaign already holds this state, and
       a stored copy is just a second version free to drift.
       CALIBRATION INVARIANT: a passive campaign sits at 50/30 all
       session, so these return exactly the old seeds and the
       simulator's passive band is preserved by construction. What
       changes is that an ENGAGED campaign now actually reaches the
       numbers simulate_gauntlet.py has always modelled. */
    const tiltFor = (tax) => (G.familyTilt || {})[tax] ||
      (G.familyTilt || {})._default || {};
    const billMeter = (b, key) => clamp(
      (S.metrics[key] || 0) +
      (((b.tilt || {})[key]) || 0) +
      (((b.earned || {})[key]) || 0));
    const bSup = (b) => billMeter(b, "support");
    const bInf = (b) => billMeter(b, "influence");
    // how far this bill sits from the campaign's own number, for the
    // labels — the point of the readout is that the bill's figure IS
    // your figure, moved by what the bill is and what you spent on it
    const tiltStr = (b, key) => {
      const t = (((b.tilt || {})[key]) || 0) +
        (((b.earned || {})[key]) || 0);
      return t ? (t > 0 ? ", +" : ", −") + Math.abs(t) + " this bill" : "";
    };

    /* THE PUSH SCALES WITH THE INFLUENCE BEHIND IT (2026-08-21). It was
       a flat +0.15 whoever asked. An insider's word to a chair is worth
       more than a stranger's, and the push is the game's most-used verb,
       so this is where the influence meter should bite hardest.
       It is ONE-SIDED ON PURPOSE: `base` IS the old flat 0.15, and the
       steps only ever add, counted from the influence baseline every
       campaign starts at. The first draft scaled from zero
       (base 0.10 + a step per 30 points) and looked fine at a campaign
       influence of 30 — until you remember bills carry a family tilt.
       A wealth measure sits 10 under its campaign, so it fell in the
       first bucket and its push quietly paid 0.10 where it used to pay
       0.15: a stealth nerf to exactly the families the tilt already
       makes hardest. Adding a reward for standing must never take
       something away from a player who has not built any.
       Capped so it can never dwarf the measured base rate. */
    const pushBonus = (inf) => {
      const p = G.push || {};
      const base = p.base != null ? p.base : 0.15;
      const step = p.step != null ? p.step : 0.05;
      const per = p.per != null ? p.per : 30;
      const from = p.from != null ? p.from :
        (G.influenceBaseline != null ? G.influenceBaseline : 30);
      const cap = p.cap != null ? p.cap : 0.30;
      return Math.min(cap,
        base + step * Math.max(0, Math.floor((inf - from) / per)));
    };

    /* DILUTION IS GRADUATED (2026-08-21). It was a cliff: support under
       35 took a flat 15% off, anything above was untouched. With the
       floor unreachable (see above) it never fired at all; with the
       meters now live it would fire as an invisible step the moment a
       bill crossed a line the player cannot see. Graduated instead —
       drifting toward the line costs a little before it costs a lot,
       which is the only version a player can learn from.
       Still multiplicative, still stacks across the two money-committee
       gates, still floored by `min` so dilution alone can never zero a
       bill: killing one stays the job of never-heard / voted-down /
       conference. */
    const dilFactor = (sup) => {
      const dil = G.dilution || {};
      const fl = dil.floor != null ? dil.floor : 45;
      const full = dil.full != null ? dil.full : 15;
      const cut = dil.cut != null ? dil.cut : 0.85;
      if (sup >= fl) return 1;
      const t = Math.min(1, (fl - sup) / Math.max(1, fl - full));
      return 1 - (1 - cut) * t;
    };

    /* Scheduling odds for one bill at one chair, ITEMISED. The parts
       list is not debug output — it is the post-mortem the player reads
       when a bill dies unheard, which is the module's central lesson.
       Keeping the breakdown and the number in one function is what
       guarantees the explanation can never drift from the maths.
       chairOdds() is the thin wrapper everything else calls. */
    const chairOddsParts = (bill, chair) => {
      const disp = (S.chairs[chair.id] != null ? S.chairs[chair.id]
        : chair.disposition) || 0;
      const a = align(bill.kind, chair.stance);
      const g = rateFor(chair.committee, bill.kind, bill.tax);
      const parts = [];
      let p = g.v;
      const add = (n, label) => {
        if (!n) return;
        p += n;
        parts.push({ n: n, label: label });
      };
      // The measured base is the rate for the AVERAGE measure referred to
      // this committee — most of which have nobody carrying them. These
      // three have you. This is the only deliberate adjustment to a
      // measured number in the model; keep it named and keep it small.
      add(G.championed || 0, "your introducer working it");
      add(disp / (G.dispositionDiv || 250),
        (chair.name || "the chair") + "'s disposition");
      /* The bill's OWN numbers — now DERIVED from the campaign's live
         meters plus this bill's tilt (see billMeter). Influence gets a
         bill heard; support only helps here when the chair is already
         aligned, and otherwise does its work at the dilution step in
         resolveBills, not by making the hearing itself easier. That
         asymmetry is the module's teaching and must survive edits. */
      const inf = bInf(bill), sup = bSup(bill);
      add(inf / (G.influenceDiv || 260),
        "this bill's influence (you " + Math.round(S.metrics.influence) +
        tiltStr(bill, "influence") + ")");
      if (a > 0) add(sup / (G.supportDiv || 500),
        "public support (aligned with the chair)");
      // the member carrying it in THIS chamber — zero at baseline
      const car = carrierFor(chair.id);
      add(introEdge(chair.id, G.introDiv),
        car ? introName(car) + "'s standing" : "your introducer");
      // a week-W push resolves during advanceWeek, AFTER S.week became
      // W+1 — accept both offsets or the bought bonus never lands on
      // the actual roll (it did not, before 2026-08-13); advanceWeek
      // clears the push once it has been consumed
      const pushed = S.pushBill === bill.id && S.pushWeek >= 0 &&
        S.week - S.pushWeek <= 1;
      if (pushed) add(pushBonus(inf), "you worked the chair this week");
      return { base: g, parts: parts, pushed: pushed,
        meters: { support: sup, influence: inf },
        p: Math.max(0.02, Math.min(0.95, p)) };
    };
    const chairOdds = (bill, chair) => chairOddsParts(bill, chair).p;
    // sid is optional only so an old call site can't crash; pass it —
    // without it the carrier's floor-management edge silently vanishes
    const floorOdds = (bill, sid) => Math.max(0.05, Math.min(0.95,
      (G.floorBase || 0.55) +
      bSup(bill) / (G.floorSupportDiv || 300) +
      bInf(bill) / (G.floorInfluenceDiv || 400) +
      (sid ? introEdge(sid, G.introFloorDiv) : 0)));

    const seedChairs = () => {
      for (const id of Object.keys(CH.chairs || {})) {
        if (S.chairs[id] == null) S.chairs[id] = CH.chairs[id].disposition || 0;
      }
    };
    /* Two generations of save to carry, and billMeter() reads neither
       of them directly — a bill needs `tilt`/`earned` or every odds
       formula goes NaN (Math.random() < NaN is always false, so bills
       would silently never be heard again).
         - pre-2026-08-13 saves have no support/influence at all;
         - 2026-08-13..08-21 saves have them as ABSOLUTE numbers.
       Both land on the same shape. The family tilt is recomputed from
       chairs.json, and the influence a player actually BOUGHT for a
       bill is recovered exactly from S.log, which has recorded every
       push since the action existed — so the one part of the old
       absolute number that was genuinely the player's own survives the
       change rather than being rounded off into it. Everything else
       goes back to floating with the campaign's meters, which is the
       whole point of the rewrite. */
    const migrateBills = () => {
      for (const b of S.bills) {
        if (b.tilt) continue;                      // already the new shape
        const tilt = tiltFor(b.tax);
        b.tilt = { support: tilt.support || 0,
                   influence: tilt.influence || 0 };
        const pushes = (S.log || []).filter(
          (e) => e && e.action === "push" && e.bill === b.id).length;
        b.earned = { support: 0,
                     influence: pushes * (G.pushInfluence || 4) };
        delete b.support;
        delete b.influence;
      }
    };
    const liveBills = () => S.bills.filter((b) => b.status === "alive");
    const billFmt = (b) => fmtK(Math.round(b.amtK * b.amtScale));

    const startBills = () => {
      if (S.bills.length) return;
      for (const id of S.agenda) {
        const p = allPolicies.find((x) => x.id === id);
        // PRIORITIES ARE NOT BILLS. They set the target (targetK) and
        // stop there; only revenue measures are carried, heard and
        // killed. A cost bill would still route correctly if one ever
        // came back — chairs.json keeps its route — but nothing creates
        // one now.
        if (!p || p.kind !== "gain") continue;
        // Module 1 routes every bill through the two MONEY committees and
        // nothing else — every bill with a dollar figure goes through both,
        // and they are the two hardest gates in the building. The
        // subject-committee stage (and the leadership referral roll that
        // could add or skip it) is deliberately out of scope; chairs.json
        // says how to restore it.
        const route = routeFor(p.kind);
        /* A bill carries only what is ITS OWN: the editorial tilt by tax
           family (chairs.json gate.familyTilt — a wealth-tax bill and a
           GET bill draw on different bases, so they sit at different
           distances from the same coalition) and, later, whatever the
           player buys FOR IT. The live numbers are read through the
           campaign's meters at use time; see billMeter. Storing an
           absolute here is what made every campaign's bills identical,
           since agenda lock always happens before any fx has run. */
        const tilt = tiltFor(p.tax);
        S.bills.push({
          id: p.id, name: p.name, kind: p.kind, amtK: p.amt, tax: p.tax,
          referral: "money",
          tilt: { support: tilt.support || 0,
                  influence: tilt.influence || 0 },
          earned: { support: 0, influence: 0 },
          amtScale: 1, route: route, stage: 0, enteredWeek: 1,
          status: "alive", history: [], death: null,
        });
      }
      save();
    };

    /* Enacted bills spend or raise on the SAME FY2027 scoreboard as
       everything else — a diluted bill simply carries fewer dollars.
       There is no separate "how much survived" stat by design. */
    const billsNetK = () => S.bills.reduce((s, b) =>
      b.status !== "enacted" ? s :
      s + (b.kind === "gain" ? 1 : -1) * b.amtK * b.amtScale, 0);
    /* ---- the module is a REVENUE game (2026-08-19, user's call: "the
       initial investment priorities determine how much revenue you have
       to make up, but the bill process is centered on taxes").
       The priorities are a COMMITMENT, not legislation: picking them
       sets the price the campaign has to cover, and they never enter
       the gauntlet. Only the revenue picks become bills. So the whole
       session now reads as one question — can you raise what you
       promised — and every chair, deadline and roll is about a tax
       measure, which is the half of the building this module is
       actually teaching.
       Both numbers are DERIVED, never stored: `S.agenda` already holds
       every pick and `S.bills` already holds every outcome, so a stored
       target would be a third copy free to drift from either. */
    const targetK = () => allPolicies.reduce((s, p) =>
      p.kind === "cost" && S.agenda.includes(p.id) ? s + p.amt : s, 0);
    const raisedK = () => S.bills.reduce((s, b) =>
      b.status === "enacted" && b.kind === "gain"
        ? s + b.amtK * b.amtScale : s, 0);
    const syncScore = () =>
      PolicyPanel.setExternal(S.metrics.revenueK + billsNetK());

    /* one week of movement, run from advanceWeek()
       Every record pushed here is SERIALISABLE and lands in S.moves —
       "what happened while you weren't looking" is rendered at the top
       of the next hub (movesHtml). Before 2026-08-15 this list was
       computed and thrown away except for its length, so a bill could
       be heard, diluted and killed without the player ever being told
       anything except a status word in the ledger. */
    const resolveBills = () => {
      const events = [];
      const rec = (b, kind, extra) => events.push(Object.assign(
        { id: b.id, name: b.name, kind: kind, stage: b.route[b.stage] },
        extra || {}));
      /* THE MANDATORY RECESS (week 6). During a recess the chambers do
         not convene at all: no committee meets, no floor session is
         held, nothing is scheduled by anyone. So EVERY gate is skipped,
         not just the chair ones — `auto` (introduction) is the single
         exception, because it is bookkeeping rather than a hearing.
         Getting this wrong is easy and silent: a chair-only skip fires
         on NOTHING, because by week 6 anything that cleared House
         Finance (deadline 5) is sitting at h-floor, a `floor` gate, and
         anything still at h-fin is already dead. The recess would have
         cost the player nothing at all.
         What it costs is one ROLL. `window` was fixed at
         `deadline - enteredWeek + 1` when the bill entered the stage, so
         the per-week hazard does not rise to compensate — a skipped week
         is simply one draw the bill never gets, against a deadline that
         has not moved. That is the lesson, and it is why this must never
         be "fixed" by extending the window. */
      const recess = calFor(S.week).recess;
      /* SUPPORT IS A STOCK AND SOMETHING HAS TO SPEND IT (2026-08-21).
         The docs have always described support as "spent at hearings and
         floor votes"; nothing spent it, so it only ever went up. A week
         where a bill sat on the floor calendar and did not get voted is
         exactly that spend — the base turned out for a week that went
         nowhere. Counted ONCE per week however many bills missed: it is
         the campaign's week that was burned, not each bill's, and a
         six-bill package would otherwise drop 12 support in a turn
         purely for having a full agenda. */
      let floorMiss = 0;
      for (const b of liveBills()) {
        const sid = b.route[b.stage];
        const st = stageOf(sid);
        if (st.gate === "auto") {                  // introduction
          b.stage += 1;
          b.enteredWeek = S.week;
          continue;
        }
        const window = Math.max(
          1, (st.deadline || S.week) - (b.enteredWeek || S.week) + 1);
        let moved = false, p = 0;
        if (recess) {
          // one line in the movement report, so a week where nothing
          // happened reads as the recess and not as a broken turn
          rec(b, "recess", { chair: (chairOf(sid) || {}).name,
                             floor: st.gate === "floor" });
          continue;
        }
        if (st.gate === "chair") {
          const ch = Object.assign({ id: sid }, chairOf(sid) || {});
          const od = chairOddsParts(b, ch);
          p = od.p;
          const hz = weekHazard(p, window);
          // keep the DRAW, not just the verdict: a miss that landed just
          // past the line is the week's most interesting news and the
          // only way the player ever feels a near-thing
          const draw = ROT.RNG.getUniform();
          moved = draw < hz;
          // meters ride along so the post-mortem can name the numbers AS
          // THEY STOOD — they are derived now, and recomputing them
          // weeks later would report the campaign's present, not the
          // bill's past (the same reason the odds are snapshotted)
          b.lastOdds = { p: p, base: od.base, parts: od.parts,
                         meters: od.meters,
                         chair: ch.name, committee: ch.committee };
          if (!moved && draw < hz * (G.nearFactor || 1.6)) {
            rec(b, "near", { p: p, chair: ch.name });
          }
          if (moved) {
            rec(b, "heard", { p: p, chair: ch.name });
            // distinct failure mode: influence got it heard; support
            // decides what survives being heard. Separate from — and can
            // stack with — the conference dilution below, so a chronically
            // unpopular bill can come out of committee already thin.
            // Graduated by how far under the floor it sits (dilFactor),
            // and only recorded when it actually took something off.
            const dil = G.dilution || {};
            const sup = bSup(b);
            const f = dilFactor(sup);
            if (f < 1) {
              const before = b.amtScale;
              b.amtScale = Math.max(dil.min != null ? dil.min : 0.4,
                b.amtScale * f);
              if (b.amtScale < before) {
                rec(b, "diluted", { support: sup, factor: f,
                                    scale: b.amtScale, amtK: b.amtK });
              }
            }
          }
        } else if (st.gate === "conf") {
          // Conference dilutes: hold the number or take the deal. This
          // roll is AUTOMATIC and halves the bill on a miss, so it is the
          // highest-stakes check in the game — and unlike a dialogue
          // check the player never opts into it. When Grassroots split
          // into Mobilizing + Base Building (2026-08-14) it therefore
          // takes the BETTER of the two rather than keying on Base
          // Building alone: keying on one half would drop a player who
          // invested in the other from ~58% to ~17% through no fault of
          // their own and quietly move the simulation-calibrated
          // enact-rate bands. Durability is still what conference is
          // ABOUT — that is why Base Building carries the Grange dare,
          // which the player does choose.
          const org = (S.skills.basebuilding || 0) >= (S.skills.mobilizing || 0)
            ? "basebuilding" : "mobilizing";
          /* The influence mod reads THIS BILL's number, not the
             campaign's global one (2026-08-21). Every other gate in the
             game had already been per-bill since 2026-08-13; conference
             was the last place still sourcing the global meter, which
             meant a bill's own tilt and the pushes bought for it
             vanished at the single highest-stakes roll. A literal
             {add,label} mod is how modOf takes a value it can't look
             up itself. */
          const r = rollCheck({ skill: org, dc: G.confDC || 12,
            mods: [{ add: Math.floor(bInf(b) / 30),
                     label: "this bill's influence" }] });
          moved = true;
          if (!r.ok) b.amtScale = 0.5;
          rec(b, "conf", { ok: r.ok, total: r.total, dc: G.confDC || 12,
                           skill: org, scale: b.amtScale, amtK: b.amtK });
        } else {                                    // floor
          p = floorOdds(b, sid);
          const hz = weekHazard(p, window);
          const draw = ROT.RNG.getUniform();
          moved = draw < hz;
          if (!moved) floorMiss += 1;
          if (!moved && draw < hz * (G.nearFactor || 1.6)) {
            rec(b, "near", { p: p, floor: true });
          }
          if (!moved && S.week >= st.deadline) {
            b.status = "dead";
            b.death = { week: S.week, stage: sid, cause: "voted down",
                        odds: { p: p } };
            rec(b, "dead", { cause: "voted down", p: p });
            continue;
          }
        }
        b.history.push({ week: S.week, stage: sid, moved: moved,
          p: Math.round(p * 100),
          pushed: !!(b.lastOdds && b.lastOdds.parts &&
            b.lastOdds.parts.some((x) => /worked the chair/.test(x.label))) });
        if (moved) {
          b.stage += 1;
          b.enteredWeek = S.week;
          if (b.stage >= b.route.length) {
            b.status = "enacted";
            rec(b, "enacted", { amtK: b.amtK, scale: b.amtScale,
                                billKind: b.kind });
          }
        } else if (S.week >= st.deadline) {
          b.status = "dead";
          // snapshot the odds AS THEY STOOD at the moment of death — the
          // post-mortem is read weeks later, by which time the campaign's
          // numbers have moved on and recomputing would quietly lie
          b.death = { week: S.week, stage: sid,
            cause: st.gate === "chair" ? "never heard" : "ran out of clock",
            odds: b.lastOdds || null,
            rolls: b.history.filter((h) => h.stage === sid).length + 1,
            pushed: b.history.some((h) => h.stage === sid && h.pushed) };
          rec(b, "dead", { cause: b.death.cause, p: p });
        }
      }
      // …and the week's bill charged to the base, applied AFTER the loop
      // so bill order can never change anyone's dilution roll
      const burn = G.floorMissSupport != null ? G.floorMissSupport : 2;
      if (floorMiss && burn) {
        const before = S.metrics.support;
        S.metrics.support = clamp(S.metrics.support - burn);
        if (S.metrics.support !== before) {
          events.push({ kind: "burn", n: before - S.metrics.support,
                        bills: floorMiss });
        }
      }
      save();
      syncScore();
      return events;
    };

    /* ---- the week's UPKEEP, run before the building acts.
       INFLUENCE IS A RATE, NOT A RATCHET (2026-08-21). Support is a
       stock you spend (see the floor burn above); influence is standing
       inside a building, and standing decays when you are not in it.
       Without this, "Work the building" was a one-way climb and the
       distinction the two meters are supposed to teach existed only in
       their tooltips.
       It decays only DOWNWARD, toward the baseline every campaign
       starts at: a player whose influence has been knocked below that
       by events has to earn it back, and never drifts up for free.
       So a passive campaign sits exactly at the baseline all session
       and the calibrated bands are untouched — same invariant
       billMeter() is built on.
       It runs during the RECESS too, deliberately: a week when the
       Capitol is shut is precisely when a standing slips. */
    const weekUpkeep = () => {
      const out = [];
      const d = G.influenceDecay != null ? G.influenceDecay : 1;
      const base = G.influenceBaseline != null ? G.influenceBaseline : 30;
      if (d > 0 && S.metrics.influence > base) {
        const before = S.metrics.influence;
        S.metrics.influence = Math.max(base, before - d);
        out.push({ kind: "decay", n: before - S.metrics.influence,
                   to: S.metrics.influence });
      }
      return out;
    };

    /* ---- the weekly intel report (the campaign's ears)
       Every round the campaign hears SOMETHING about each live bill;
       how much of it is true depends on skills, per facet
       (session.json `intel`): Talk Story prices the chairs — below
       `band` you get hallway rumor whose band may be off by one
       (seeded per week+bill, wrong ON PURPOSE — don't "fix" the
       noise), at `band` an honest band, at `exact` the live
       percentage plus the chair's disposition (the number the paid
       lobbyist already has). This was Whip Count's job until it was
       retired 2026-08-14 and folded into Talk Story at the same
       thresholds — reading a chair's real disposition turned out to be
       the same read as reading a coalition partner's. Procedure reads
       the clock — deadline warnings before they are one week out;
       without it you hear about deadlines when they are on top of you.
       Policy Brain puts the MEASURED hearing rate in print — it is
       always in the bill tooltip, but tooltips don't exist on touch.
       The ledger's live odds are gated by the same Talk Story tiers
       (bstatFor); the measured base stays reachable by everyone,
       because it is public data. */
    const IN = data.intel || {};
    const hash32 = (s) => {
      let h = 2166136261;
      for (let i = 0; i < s.length; i++) {
        h ^= s.charCodeAt(i);
        h = Math.imul(h, 16777619);
      }
      return h >>> 0;
    };
    const bandOf = (p) => {
      const bs = IN.bands || [];
      for (let i = 0; i < bs.length; i++) {
        if (p <= bs[i].max) return Object.assign({ i }, bs[i]);
      }
      return Object.assign({ i: Math.max(0, bs.length - 1) },
        bs[bs.length - 1] || { label: "unclear", short: "?" });
    };

    const oddsIntel = (b, sid) => {
      const ch = Object.assign({ id: sid }, chairOf(sid) || {});
      const p = chairOdds(b, ch);
      const o = IN.odds || {};
      const read = S.skills[o.skill || "talkstory"] || 0;
      if (read >= (o.exact || 5)) {
        const disp = (S.chairs[sid] != null ? S.chairs[sid]
          : ch.disposition) || 0;
        return { t: esc(ch.name || "The chair") + " calendars it at <b>" +
          Math.round(p * 100) + "%</b> this week — disposition " + disp +
          ".", src: "someone who knows him well" };
      }
      const band = bandOf(p);
      if (read >= (o.band || 3)) {
        return { t: "A good source puts a hearing at <b>" +
          esc(band.label) + "</b>.", src: "a good source" };
      }
      const bs = IN.bands || [];
      const j = Math.max(0, Math.min(bs.length - 1,
        band.i + (hash32(S.week + ":" + b.id) % 3) - 1));
      return { t: "Hallway word puts a hearing at <b>" +
        esc((bs[j] || band).label) + "</b>.",
        src: "hallway talk — could be wrong" };
    };

    const intelHtml = () => {
      if (S.week < 1 || S.week > data.sineDieWeek) return "";
      const live = liveBills();
      if (!live.length) return "";
      const proc = S.skills[(IN.clock || {}).skill || "procedure"] || 0;
      const fisc = S.skills[(IN.basis || {}).skill || "fiscal"] || 0;
      let h = '<div class="sh-sec">' + sym("intel") +
        " The week’s intel</div>";
      for (const b of live) {
        const sid = b.route[b.stage];
        const st = stageOf(sid);
        const lines = [];
        let src = "around the building";
        if (st.gate === "chair") {
          const o = oddsIntel(b, sid);
          lines.push(o.t);
          src = o.src;
          if (fisc >= ((IN.basis || {}).cite || 3)) {
            const ch = chairOf(sid) || {};
            const g = rateFor(ch.committee, b.kind, b.tax);
            lines.push("The measured floor under all of it: " +
              Math.round(g.v * 100) + "% of " +
              (g.basis === "type"
                ? ((TAXLABEL[b.tax] || {}).label || "such")
                    .toLowerCase() + " measures"
                : "its " + (b.kind === "gain" ? "tax" : "spending") +
                  " measures") + " ever get heard.");
          }
        } else if (st.gate === "conf") {
          lines.push("In conference. The number itself is on the " +
            "table now.");
        } else {
          lines.push("On the floor calendar — the majority follows " +
            "its chairs.");
        }
        if (st.gate !== "conf" && st.deadline != null) {
          const left = st.deadline - S.week;
          if (proc >= ((IN.clock || {}).warn || 3)) {
            lines.push(left <= 0 ? "<b>Deadline week. Now or never.</b>"
              : "Deadline week " + st.deadline + " — " + left +
                " week" + (left === 1 ? "" : "s") + " out.");
          } else if (left <= 1) {
            lines.push(left <= 0
              ? "<b>Someone mentions today is the deadline.</b>"
              : "<b>Someone mentions the deadline is next week.</b>");
          }
        }
        h += '<div class="intel-row"><span class="shname"><b>' +
          esc(b.name) + "</b><small>" + lines.join(" ") +
          '</small></span><span class="isrc">' + esc(src) +
          "</span></div>";
      }
      h += '<div class="sh-agenda-cap">What you hear is only as good ' +
        "as your skills: Talk Story prices the chairs, Procedure reads " +
        "the clock, Policy Brain knows the measured numbers.</div>";
      return h;
    };

    /* the live number is insider knowledge — the ledger prices it only
       as well as you can read the room; floor odds are your own two
       meters, so they stay open */
    const bstatFor = (b, sid, ch) => {
      const st = stageOf(sid);
      if (st.gate === "chair") {
        const o = IN.odds || {};
        const read = S.skills[o.skill || "talkstory"] || 0;
        const p = chairOdds(b, Object.assign({ id: sid }, ch || {}));
        if (read >= (o.exact || 5)) return Math.round(p * 100) + "%";
        if (read >= (o.band || 3)) return esc(bandOf(p).short || "?");
        return "?";
      }
      if (st.gate === "floor") return Math.round(floorOdds(b, sid) * 100) + "%";
      return "—";
    };

    /* A bill's own support/influence explain WHY it's struggling — dying
       unheard (influence) vs surviving thin (support) — so they ride the
       same Talk Story tiers as the odds badge, or a player who can't see
       the odds yet gets a free second readout that means the same thing.
       Reuses bandOf's qualitative ladder for both 0-100 meters, same as
       hearing probability — both answer "how is this looking." */
    const meterNote = (b) => {
      const o = IN.odds || {};
      const read = S.skills[o.skill || "talkstory"] || 0;
      if (read < (o.band || 3)) return "";
      const fmt = (v) => read >= (o.exact || 5)
        ? Math.round(v) : esc(bandOf(v / 100).short || "?");
      return " · " + sym("support") + fmt(bSup(b)) +
        " " + sym("influence") + fmt(bInf(b));
    };

    /* the two members carrying the package — shown once bills exist,
       because that is when "who is on point" starts deciding odds */
    const introStrip = () => {
      const ks = introKeys();
      if (!ks.length || !S.bills.length) return "";
      const live = liveBills();
      const onPoint = {};
      for (const b of live) {
        const w = carrierFor(b.route[b.stage]);
        if (w) onPoint[w] = (onPoint[w] || 0) + 1;
      }
      let h = '<div class="sh-sec">' + sym("introducer") +
        " Your introducers</div><div class=\"intro-strip\">";
      for (const k of ks) {
        const i = INTROS[k];
        const r = introRap(k);
        const n = onPoint[k] || 0;
        h += '<div class="introc' + (n ? " active" : "") +
          '" title="' + escA(i.voice || "") + '">' +
          '<div class="ic-top"><b>' + esc(i.name) + "</b><span>" +
          esc(i.role || "") + "</span></div>" +
          '<div class="ic-bar"><i style="width:' + r + '%"></i></div>' +
          '<div class="ic-foot"><span>Rapport <b>' + r + "</b></span>" +
          (n ? '<span class="ic-on">carrying ' + n + "</span>" :
            '<span class="ic-off">waiting</span>') + "</div></div>";
      }
      return h + "</div>";
    };

    /* ---- the post-mortem: WHY a bill died, in the building's own
       arithmetic. This is the module's central lesson and it used to be
       invisible — a bill went from "alive" to a struck-through line
       reading "never heard" with no account of what it needed. The
       measured floor and every editorial term the player actually moved
       are itemised from the snapshot taken at death (b.death.odds), then
       one counterfactual names the largest lever they did not pull. */
    const pct = (v) => (v >= 0 ? "+" : "−") +
      Math.round(Math.abs(v) * 100) + " pts";
    const postMortem = (b) => {
      const d = b.death || {};
      const o = d.odds;
      if (!o || !o.parts) return "";
      const yrs = ((rateData || {}).sessions || []).join("/");
      const what = o.base.basis === "type"
        ? ((TAXLABEL[b.tax] || {}).label || "such measures").toLowerCase()
        : b.kind === "gain" ? "tax measures" : "spending measures";
      let h = '<div class="pm"><div class="pm-row pm-base"><span>' +
        "Measured floor</span><b>" + Math.round(o.base.v * 100) + "%</b>" +
        "<small>" + esc(o.committee || "The committee") + " heard " +
        Math.round(o.base.v * 100) + "% of the " + esc(what) +
        " referred to it" + (yrs ? " (" + esc(yrs) + ")" : "") +
        "</small></div>";
      for (const p of o.parts) {
        h += '<div class="pm-row ' + (p.n < 0 ? "cost" : "gain") +
          '"><span>' + esc(p.label) + "</span><b>" + pct(p.n) +
          "</b></div>";
      }
      const rolls = d.rolls || 1;
      // data-count drives the count-up when the card becomes visible
      // (countPm) — the number the whole ledger above it adds up to
      h += '<div class="pm-row pm-final"><span>Its real chance of a ' +
        'hearing</span><b data-count="' + Math.round(o.p * 100) + '">' +
        Math.round(o.p * 100) + "%</b><small>" +
        rolls + " week" + (rolls === 1 ? "" : "s") +
        " on the calendar, and it never came up.</small></div>";
      /* The counterfactual — name the biggest lever left unpulled.
         Both numbers come from the DEATH SNAPSHOT (o.meters), never
         from a live read: a bill's meters are derived from the
         campaign's now, and this card is read weeks later. */
      const dInf = o.meters ? o.meters.influence : null;
      const bonus = Math.round(pushBonus(dInf == null ? 30 : dInf) * 100);
      let lesson;
      if (d.cause === "never heard" && !d.pushed) {
        lesson = "You never spent a week working " +
          esc(o.chair || "the chair") + " on this one. That action was " +
          "worth " + bonus + " points of scheduling odds — more than any " +
          "other lever you had.";
      } else if (dInf != null && dInf < 40) {
        lesson = "Its influence never got above " + Math.round(dInf) +
          ". Influence is what gets a bill calendared at all; support " +
          "decides what survives once it is.";
      } else if (d.cause === "never heard") {
        lesson = "You worked it and the number still wasn't enough. That " +
          "is the ordinary outcome here — most measures referred to this " +
          "committee are never heard, and no vote is ever taken on them.";
      } else {
        lesson = "It ran out of calendar. The deadline is the killer far " +
          "more often than the opposition is.";
      }
      return h + '<div class="pm-lesson">' + lesson + "</div></div>";
    };

    /* the arithmetic should build, not just appear: the rows cascade in
       (CSS) and the final percentage counts up to meet them. Run on
       every post-mortem currently on screen — cheap, idempotent, and it
       covers both routes in (the death card, and the ledger toggle). */
    const countPm = (root) => {
      for (const b of (root || body).querySelectorAll(
          ".pm-final b[data-count]")) {
        const to = +b.dataset.count;
        countTo(b, 0, to, (v) => Math.round(v) + "%", 620);
      }
    };

    /* ---- what moved while you weren't looking.
       Rendered at the TOP of the hub for the week after it happened. */
    const movesHtml = () => {
      const mv = (S.moves && S.moves.week === S.week) ? S.moves.list : null;
      if (!mv || !mv.length) return "";
      const line = (m) => {
        switch (m.kind) {
          case "heard":
            return { cls: "won", t: "Heard in committee",
              s: esc(m.chair || "The chair") + " put it on a hearing " +
                 "calendar. It moves." };
          case "near":
            return { cls: "near", t: "Nearly calendared",
              s: m.floor
                ? "It came up short on the floor calendar this week."
                : esc(m.chair || "The chair") + " pulled the file and put " +
                  "it back. At " + Math.round((m.p || 0) * 100) +
                  "% it was close — and close is not a hearing." };
          case "diluted":
            return { cls: "near", t: "Cut on the way through",
              s: "Support was " + Math.round(m.support) + ". It cleared " +
                 "the committee at " + Math.round(m.scale * 100) +
                 "% of the ask — " + fmtK(Math.round(m.amtK * m.scale)) +
                 "/yr." };
          case "conf":
            return { cls: m.ok ? "won" : "near",
              t: m.ok ? "Held the number in conference"
                      : "Halved in conference",
              s: "Rolled " + m.total + " against " + m.dc + " on " +
                 esc((data.skills[m.skill] || {}).name || m.skill) + ". " +
                 (m.ok ? "The number survives." : "It comes out at " +
                   fmtK(Math.round(m.amtK * m.scale)) + "/yr.") };
          case "enacted":
            // its own class, not just "won": becoming law is the rarest
            // thing that happens in this game and looked identical to a
            // committee hearing until now
            return { cls: "won enacted", t: "Enacted",
              s: "It is law. " + fmtK(Math.round(m.amtK * m.scale)) +
                 "/yr" + (m.scale < 1 ? " of the original ask" : "") + "." };
          case "dead":
            return { cls: "dead", t: "Dead — " + esc(m.cause),
              s: m.cause === "never heard"
                ? "No vote was taken. No record exists of anyone killing it."
                : "The clock beat it." };
          case "recess":
            // the recess has to be VISIBLE or the week reads as a bug.
            // Name the cost explicitly: a week skipped against a
            // deadline that did not move to make up for it.
            return { cls: "near", t: "Recess — nothing moved",
              s: (m.floor
                ? "Neither chamber convened, so it was never called."
                : esc(m.chair || "The chair") + " scheduled nothing, " +
                  "because during a recess nobody can.") +
                 " One week gone. The deadline did not move." };
          /* The two CAMPAIGN-level rows: they carry no bill, because
             they happened to the campaign rather than to a measure.
             They are reported for the same reason near-misses are —
             a meter that moves while the panel is shut, with no line
             in the report, reads as a bug in the scoreboard. */
          case "burn":
            return { cls: "near", campaign: true,
              t: "The base spent a week on the floor calendar",
              s: "A vote was expected and never called" +
                 (m.bills > 1 ? " on " + m.bills + " of your bills" : "") +
                 ". Public Support −" + m.n + ". Turnout is a stock: " +
                 "you spend it every week you ask people to show up." };
          case "decay":
            return { cls: "near", campaign: true,
              t: "Influence slipped",
              s: "Political Influence −" + m.n + ", to " + m.to +
                 ". Standing inside the building is a rate, not a " +
                 "ratchet — it needs the week you spend on it." };
          default: return null;
        }
      };
      let h = '<div class="sh-sec">' + sym("event") +
        " Since you ended the week</div>";
      for (const m of mv) {
        const l = line(m);
        if (!l) continue;
        const b = S.bills.find((x) => x.id === m.id);
        // a campaign row has no measure to name, so its headline IS the
        // event; a bill row leads with the bill
        h += '<div class="mv-row ' + l.cls + '"><b>' +
          (l.campaign ? '<span class="mv-what">' + l.t + "</span>"
            : esc(m.name) + ' <span class="mv-what">' + l.t + "</span>") +
          "</b><small>" + l.s + "</small>" +
          (m.kind === "dead" && b ? postMortem(b) : "") + "</div>";
      }
      return h;
    };

    /* ---- THE GAP: what the priorities cost against what the enacted
       tax bills have actually raised. This is the module's scoreboard
       now (2026-08-19) — the session asks one question and this is it,
       so it sits at the top of the ledger rather than being something
       the player reconstructs from six rows.
       It reads honestly at both ends: nothing enacted yet says so
       rather than showing a 0% bar, and overshooting says "raised more
       than you promised" instead of clamping to 100% and looking like
       a job merely finished. */
    const gapHtml = () => {
      const want = targetK();
      if (!want) return "";
      const got = raisedK();
      const pct = Math.max(0, Math.min(100, (got / want) * 100));
      const left = want - got;
      return '<div class="sh-gap' + (left <= 0 ? " met" : "") + '">' +
        '<div class="gap-top"><span class="gap-lbl">' +
        (left <= 0 ? "Your priorities are funded"
          : "To fund your priorities") + "</span>" +
        '<span class="gap-num"><b>' + fmtK(got) + "</b> of " +
        fmtK(want) + "</span></div>" +
        '<div class="gap-bar"><i style="width:' + pct + '%"></i></div>' +
        '<div class="gap-note">' +
        (left > 0
          ? fmtK(left) + "/yr still to raise" +
            (got ? "" : " — nothing enacted yet")
          : "raised " + fmtK(-left) + "/yr more than you promised") +
        "</div></div>";
    };

    const billLedger = (reveal) => {
      if (!S.bills.length) return "";
      let h = gapHtml() + '<div class="sh-sec">Your bills</div>';
      for (const b of S.bills) {
        const sid = b.route[b.stage] || b.route[b.route.length - 1];
        const st = stageOf(sid);
        const ch = chairOf(sid);
        const cls = b.status === "dead" ? "dead" :
          b.status === "enacted" ? "won" : "";
        let line;
        if (b.status === "enacted") {
          line = "Enacted · " + billFmt(b) + "/yr" +
            (b.amtScale < 1 ? " (cut to " + Math.round(b.amtScale * 100) +
              "% along the way)" : "");
        } else if (b.status === "dead") {
          line = "Died week " + b.death.week + " · " + stageOf(b.death.stage).label +
            " — <b>" + b.death.cause + "</b>" +
            (reveal && ch ? "<br>" + esc(ch.name) + "'s disposition toward it: " +
              ((S.chairs[sid] != null ? S.chairs[sid] : ch.disposition) || 0) : "");
          // the account of WHY stays reachable all season, not only on
          // the week of death — collapsed behind a toggle so the ledger
          // stays scannable (at sine die `reveal` opens it by default)
          if (b.death.odds) {
            line += '<span class="pm-tgl" data-pm="' + b.id + '">' +
              (reveal ? "" : "Why it died ▸") + "</span>" +
              '<span class="pm-body' + (reveal ? "" : " hidden") + '">' +
              postMortem(b) + "</span>";
          }
        } else {
          const dlLeft = st.deadline != null ? st.deadline - S.week : null;
          const car = carrierFor(sid);
          line = st.label + " · <b class=\"dl" +
            (dlLeft != null && dlLeft <= 1 ? " dl-soon" : "") +
            "\">deadline week " + st.deadline + "</b>" +
            // both names get a role word: "carried by X · Y" read as
            // two anonymous people standing next to each other
            (car ? " · carried by " + esc(introName(car)) : "") +
            (ch ? " · chair " + esc(ch.name) : "") +
            (b.amtScale < 1 ? " · already cut to " +
              Math.round(b.amtScale * 100) + "%" : "") +
            meterNote(b);
        }
        h += '<div class="bill-row ' + cls + '"' +
          (ch ? ' title="' + escA(rateNote(ch.committee, b.kind, b.tax)) +
            '"' : "") +
          '><span class="shname"><b>' + esc(b.name) + "</b><small>" +
          line + '</small></span><span class="bstat" title="' +
          (b.status === "alive" && bstatFor(b, sid, ch) === "?"
            ? "You don&#39;t know this chair well enough yet."
            : "") + '">' +
          (b.status === "enacted" ? "✓" : b.status === "dead" ? "✕" :
            bstatFor(b, sid, ch)) + "</span></div>";
      }
      return h;
    };

    /* Advancing runs THROUGH the map (map job A): the overlay drops,
       the camera makes one slow move to wherever the new week happens
       (the event's `at` key — map job B), and only then does the week
       open. `beating` gates re-entry: the turn chip stays live on
       screen during the ritual and a double-tap would advance twice. */
    let beating = false;
    const advanceWeek = () => {
      if (S.week > data.sineDieWeek || beating) return;
      /* The week sound lives HERE and not on the button, for the same
         reason the pip's lives after its guard: sine die and a beat
         already in flight both return above this line, and a click at
         a player whose press did nothing is worse than silence. It
         also catches BOTH doors — the End Turn chip and the hub's
         #sess-next — without either being able to drift. */
      SFX.week();
      // BEFORE resolveBills(), so the week's movement counts toward the
      // trend the player reads on the map a moment later
      S.weekBase = { support: S.metrics.support,
                     influence: S.metrics.influence };
      S.week += 1;
      startBills();
      // upkeep FIRST, then the building acts: the week's decay is in
      // force for the rolls that week, and lands inside the trend the
      // player reads on the map (weekBase was snapshotted above)
      const moves = weekUpkeep().concat(resolveBills());
      // stamp the movement report to THIS week so the hub shows it until
      // the next advance; near-misses included — the near record is the
      // only time the player ever feels how close "never heard" ran
      S.moves = moves.length ? { week: S.week, list: moves } : null;
      if (S.pushWeek >= 0 && S.week > S.pushWeek) {   // push consumed
        S.pushWeek = -1;
        S.pushBill = null;
      }
      save();
      renderHead();
      const cal = calFor(S.week);
      // every branch here is a WEEK ARRIVING — the panel comes back up
      // out of the camera ritual, so all three take the ceremonial
      // entrance, not the ordinary reopen
      const openWeek = () => {
        beating = false;
        renderTurnBtn();
        if (moves.length) {
          openOverlay(true);
          renderHub();              // let the player read what happened
          return;
        }
        if (eventPending(cal)) {
          openOverlay(true);
          runEvent();
        } else {
          openOverlay(true);
          renderHub();
        }
      };
      // the ritual: panel drops away, one camera move, week rises back
      const dlg = data.dialogues[cal.event] || {};
      const startBeat = () => {
        overlay.classList.add("hidden");
        // The camera ritual belongs to the MAP. With the Capitol as
        // the main view (2026-08-26) the world scene sleeps under the
        // room, its tween clock with it — weekBeat there would just
        // stall on the 4s fallback. Skip straight to the week.
        if (scene && scene.weekBeat && !scene.sys.isSleeping()) {
          beating = true;
          renderTurnBtn();
          scene.weekBeat(dlg.at || null, openWeek);
        } else {
          openWeek();
        }
      };
      const panel = overlay.querySelector(".ovl-panel");
      if (panel && !reduced() && !overlay.classList.contains("hidden")) {
        // let the panel fall away BEFORE the map takes over, so the
        // hand-off reads as one motion instead of a hard cut
        panel.classList.add("leaving");
        setTimeout(() => {
          panel.classList.remove("leaving");
          startBeat();
        }, 240);
      } else {
        startBeat();
      }
    };

    /* ---- overlay plumbing.
       TWO entrances, and the difference is editorial. Reopening the
       panel you just closed is furniture: it gets the modest 260ms
       `.arriving` rise. A WEEK ARRIVING is an event — the first one on
       boot, and every one the turn ritual lands — so it gets `.wk-open`:
       the scrim fades up, the panel rises further and slower, one sheen
       crosses it, and the masthead, strip, meters and content stagger in
       behind the frame. Reserve it for those two moments; putting it on
       every open would make the Session tab feel ceremonial and the
       actual week feel like nothing.
       `WK_IN` force-lands it on a wall clock for the same reason
       screenSwap and countTo do: a hidden document freezes the animation
       clock, and `both` fill would hold the whole overlay at opacity 0.
       Keep it above the longest child delay + duration. */
    const WK_IN = 900;
    const weekArrive = () => {
      const panel = overlay.querySelector(".ovl-panel");
      // the plain rise and the week arrival both animate .ovl-panel, so
      // the ordinary one has to come off or the two fight over the
      // `animation` shorthand
      if (panel) panel.classList.remove("arriving");
      overlay.classList.remove("wk-open");
      void overlay.offsetWidth;                 // restart the animation
      overlay.classList.add("wk-open");
      setTimeout(() => overlay.classList.remove("wk-open"), WK_IN);
    };
    const openOverlay = (week) => {
      $("money-overlay").classList.add("hidden");
      $("policy-overlay").classList.add("hidden");
      const wasHidden = overlay.classList.contains("hidden");
      overlay.classList.remove("hidden");
      // rise in only when it was actually closed — re-rendering into an
      // already-open panel must not re-animate the frame
      const panel = overlay.querySelector(".ovl-panel");
      if (panel && wasHidden && !reduced()) {
        if (week) {
          weekArrive();
        } else {
          panel.classList.remove("arriving");
          void panel.offsetWidth;
          panel.classList.add("arriving");
        }
      }
      Dialog.hide();
      // the strip could only measure itself once it was visible
      requestAnimationFrame(centerTimeline);
    };
    const toggleSession = () => {
      if (overlay.classList.contains("hidden")) {
        openOverlay();
        const cal = calFor(S.week);
        // skill investment / bill agenda comes first when it's pending —
        // the narrative event follows once that's locked in
        if (cal.agenda && !S.agendaLocked) renderHub();
        else if (eventPending(cal)) runEvent();
        else renderHub();
      } else overlay.classList.add("hidden");
    };
    $("tb-session").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      toggleSession();
    });
    // the Instincts tab: the character sheet as its own view. During
    // creation renderSheet routes back through the renderHub funnel,
    // so the select screens stay the only door into a fresh campaign.
    $("tb-instincts").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      if (!overlay.classList.contains("hidden") &&
          body.dataset.view === "sheet") {
        overlay.classList.add("hidden");
        return;
      }
      openOverlay();
      renderSheet();
    });
    // the HUD mini timeline is a second entry point into the same
    // overlay — a glance-and-tap shortcut that doesn't require finding
    // the toolbar button
    $("hud-timeline").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      toggleSession();
    });
    /* The panel's compact bar opens the full milestone strip beneath
       it. stopPropagation, or the overlay's backdrop handler reads the
       tap as a click-outside and closes the whole panel — the same trap
       the strip's own milestone buttons already dodge.
       centerTimeline has to run AFTER the strip is displayed: it bails
       while the scroll box measures under 40px, which is exactly what a
       display:none box reports, so opening without this re-run leaves
       the strip parked at scrollLeft 0 instead of on the current week. */
    $("sess-progress").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      const open = overlay.classList.toggle("tl-open");
      $("sess-progress").setAttribute("aria-expanded", open ? "true" : "false");
      if (open) requestAnimationFrame(centerTimeline);
    });
    $("turn-chip").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      const cal = calFor(S.week);
      if (S.week > data.sineDieWeek) return;
      if (cal.agenda && !S.agendaLocked) {   // week 1: lock the agenda first
        openOverlay();
        renderHub();
        return;
      }
      advanceWeek();
    });
    // the other overlays' buttons close this one
    for (const id of ["tb-budget", "tb-policy",
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
    /* The footer is the reset affordance and nothing else — the
       explanatory paragraph about The Advocate, the turn structure and
       the fictional cast was removed 2026-08-15 (user's call) so the
       panel's height goes to the dialogue instead. `data.identity` is
       no longer read anywhere in the UI. */
    $("sess-foot").innerHTML =
      "<button id=\"sess-reset\" type=\"button\" " +
      "style=\"background:none;border:none;color:#9fb0e8;" +
      "text-decoration:underline;cursor:pointer;font:inherit;" +
      "padding:0\">Restart session</button>";
    $("sess-reset").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      const b = e.target;
      if (b.dataset.arm) {
        S = defaults();
        seedChairs();
        seedIntroducers();
        save();
        PolicyPanel.setExternal(0);
        renderHead();
        /* A restart is a NEW CAMPAIGN and has to land on the creation
           funnel, exactly the way boot does — it used to call runEvent()
           directly, which walked straight past SELECT INSTINCTS and the
           bill package into week 1's narrative with a default character
           nobody chose (2026-08-19, user's call: "make sure the intro
           screen pops up when the game is restarted too").
           renderHub() is the funnel gate: its early bail sends an unspent
           point pool to renderSelect and an unlocked agenda to
           renderAgendaSelect, which is the documented rule — every entry
           point goes through renderHub rather than testing for the
           screens itself. The branch below mirrors boot exactly so the
           two doors into a fresh campaign cannot drift apart. */
        const cal = calFor(S.week);
        if (cal.agenda && !S.agendaLocked) renderHub();
        else runEvent();
      } else {
        b.dataset.arm = "1";
        b.textContent = "Really restart? (tap again)";
        setTimeout(() => {
          b.dataset.arm = "";
          b.textContent = "Restart session";
        }, 2500);
      }
    });

    /* ---- boot: reflect saved revenue + enacted bills, pop an unplayed week */
    seedChairs();
    seedIntroducers();
    migrateBills();
    syncScore();
    renderHead();
    const cal0 = calFor(S.week);
    // START_ROOM lands the player in a room; an overlay popping over
    // it on boot would defeat that. The funnel is not lost — it is
    // renderHub's early bail, so it fires the moment the session is
    // opened from the map.
    if (!START_ROOM && (eventPending(cal0) ||
        (cal0.agenda && !S.agendaLocked))) {
      openOverlay(true);            // the FIRST week arriving
      // skill investment / bill agenda comes first when it's pending —
      // the narrative event follows once that's locked in (see sess-lock)
      if (cal0.agenda && !S.agendaLocked) renderHub();
      else runEvent();
    }
  },
};

/* -------------------------------------------------------- island fly-to */
/* The "· Oʻahu ▾" tag on the title chip opens a list of all eight
   islands; picking one flies the camera there — it's ONE continuous map,
   so this is navigation, not a scene switch. The chip label tracks
   whichever island the camera is over ("Hawaiʻi" over open water). */
/* The sound toggle. Lives beside the island chip in the title plate,
   not in the toolbar — the four toolbar buttons are DOORS into panels,
   and a fifth button that is a preference would misread as a fifth
   panel. It is wired here, outside every scene and every overlay,
   because sound is global state and the chip is on screen from boot.
   The glyph is drawn, NOT an emoji — the house rule (see SYM at the
   top of this file) is that no stock emoji goes in main.js, and a
   speaker character renders as a different picture on every platform
   anyway. Two waves when sound is on, none when it is off, plus the
   chip's own opacity: no crossed-out slash, which at 11px is mush. */
const SFX_ICON = (on) =>
  '<svg viewBox="0 0 18 18" shape-rendering="crispEdges" ' +
  'aria-hidden="true"><path d="M3 7h3l4-3v10l-4-3H3z" ' +
  'fill="currentColor"/>' +
  (on
    ? '<path d="M12 6v6M15 4v10" stroke="currentColor" ' +
      'stroke-width="1.6" fill="none"/>'
    : "") + "</svg>";
const SfxUI = {
  init() {
    const chip = document.getElementById("sfx-chip");
    if (!chip || !window.SFX) return;
    const paint = () => {
      const off = SFX.muted();
      chip.innerHTML = SFX_ICON(!off);
      chip.classList.toggle("off", off);
      chip.setAttribute("aria-pressed", off ? "false" : "true");
      chip.title = off ? "Sound off — click for sound"
                       : "Sound on — click to mute";
    };
    chip.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      SFX.toggle();
      paint();
    });
    paint();
  },
};

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
    this.load.json("world", "map/world.json?v=" + MAP_V);
    this.load.json("meta_oahu", "map/oahu.json?v=" + MAP_V);
    this.load.json("flows", "map/tax_flows.json?v=1");
    this.load.json("budget", "map/budget.json?v=1");
    this.load.json("revenue", "map/revenue.json?v=1");
    this.load.json("get_flows", "map/get_flows.json?v=1");
    this.load.json("policies", "map/policies.json?v=2");
    // hand-maintained: the pre-commit cache-bump hook only rewrites ?v=
    // refs inside HTML, so a JSON loaded from JS needs bumping BY HAND
    // whenever its content changes (v6 = skillStart.ranks)
    this.load.json("session", "map/session.json?v=12");
    this.load.json("chairs", "map/chairs.json?v=2");
    this.load.json("rates", "map/hearing_rates.json?v=1");
  }
  create() {
    const world = this.cache.json.get("world");
    this.load.image("overview",
                    "assets/map/" + world.overview.file + "?v=" + MAP_V);
    // Oʻahu is preloaded — the intro dives into the Capitol
    const oahu = this.cache.json.get("meta_oahu");
    for (const s of oahu.slices) {
      this.load.image("map_" + s.file, "assets/map/" + s.file + "?v=" + MAP_V);
    }
    this.load.image("capitol", "assets/sprites/capitol.png?v=2");
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
    // Read the sea colour from the BAKE (build_world copies it out of
    // the island metas) rather than trusting the constant. Every island
    // is a rectangle composited on this, so a mismatch draws a visible
    // box around each one — and the constant cannot be right for both
    // art styles at once, since `--style pixel` bakes a different blue.
    // DEEP_BLUE stays as the pre-load fallback only.
    this.cameras.main.setBackgroundColor(world.deep || DEEP_BLUE);
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
      this.cache.json.get("session"), this.cache.json.get("chairs"),
      this.cache.json.get("rates"), this);
    IslandUI.init(this);
    SfxUI.init();

    this.setupCamera(world);
    this.setupInput();

    this.ensureIsland("oahu");     // slices preloaded by BootScene
    this.time.addEvent({ delay: 400, loop: true,
                         callback: () => this.manageIslands() });
    this.scale.on("resize", () => {
      this.recomputeMinZoom();
      this.applyLabelScale();
    });

    // ---- hand straight off to the landing room, if there is one.
    // Everything above has already run, so the map is fully built and
    // every panel is initialised; the scene just goes to sleep behind
    // the room. See START_ROOM.
    if (START_ROOM) {
      this.stopIntro();
      this.parkOnCapitol(world);
      this.scene.switch(START_ROOM);
    }
  }

  /* Put the camera where the intro dive would have ENDED — used when
     a landing room skips the dive, so the stairs arrive on the
     Capitol instead of on the whole archipelago. */
  parkOnCapitol(world) {
    const cam = this.cameras.main;
    const [cx, cy] = world.capitol;
    const z = Math.min(1.7, this.maxZoom);
    cam.setZoom(z);
    cam.centerOn(cx, cy - 40);
    this.applyLabelScale();
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
        this.load.image("map_" + s.file, "assets/map/" + s.file + "?v=" + MAP_V);
      }
      this.load.once("complete", () => this.addIsland(e, meta));
      this.load.start();
    };
    if (this.cache.json.exists(key)) step2();
    else {
      this.load.json(key, "map/" + slug + ".json?v=" + MAP_V);
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

  /* ---- the week beat (map job A): the ritual between turns.
     End Turn closes the overlay, the camera makes one slow move to
     wherever the new week is happening (map job B — an event's `at`
     key), holds a breath, and only then does the week open. The map is
     the CLOCK: the thing you watch while time passes, not scenery
     behind a panel. Spec (from session.json, resolved here):
       null / "capitol"          → the Capitol, standard framing
       { island }                → frame that island (ev-emergency)
       { island, px: [x, y] }    → a point in that island's BAKE pixels,
                                   mapped through anchor + scale (the
                                   same transform chain as landmarks —
                                   never the world frame directly)
     Failure mode: if anything is missing (unknown island, no tweens in
     a hidden pane), call onDone immediately — the ritual must never be
     able to strand the game between weeks. */
  weekBeat(spec, onDone) {
    const done = () => { if (onDone) { const f = onDone; onDone = null; f(); } };
    try {
      const cam = this.cameras.main;
      const [sw, sh] = this.viewSize();
      this.stopIntro();
      if (this.beatTween && this.beatTween.isPlaying()) this.beatTween.stop();
      let x, y, z;
      if (spec && spec.island) {
        const e = this.world.islands.find((i) => i.slug === spec.island);
        if (!e) { done(); return; }
        if (spec.px) {
          x = e.anchor[0] + spec.px[0] * e.scale;
          y = e.anchor[1] + spec.px[1] * e.scale;
          z = 1.1;
        } else {
          const w = e.w * e.scale, h = e.h * e.scale;
          x = e.anchor[0] + w / 2;
          y = e.anchor[1] + h / 2;
          z = Math.min(sw / w, sh / h) * 0.92;
        }
      } else {
        x = this.world.capitol[0];
        y = this.world.capitol[1] - 40;
        z = 1.35;
      }
      z = Phaser.Math.Clamp(z, this.minZoom, this.maxZoom);
      this.beatTween = this.tweens.add({
        targets: cam,
        zoom: z,
        scrollX: x - sw / 2 / z,
        scrollY: y - sh / 2 / z,
        duration: 1600,
        ease: "Sine.easeInOut",
        onUpdate: () => this.applyLabelScale(),
        onComplete: () => {
          this.applyLabelScale();
          // the held breath — the map gets a beat of stillness before
          // the week starts talking again
          this.time.delayedCall(450, done);
        },
      });
      // belt and braces: a hidden tab can throttle the tween clock to a
      // crawl; never let the game wait on it for more than ~4s of wall
      // time (double-fire is impossible — done() nulls onDone)
      setTimeout(done, 4000);
    } catch (e) { done(); }
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

    /* The mote is a STREAK (2026-08-21, user's call, same day as the
       comet: the ball-and-tail comet "looked like sperm" — nothing
       round anywhere now). One thin tapered line, alpha ramping toward
       the head, capped by a short bright DASH instead of a disc; drawn
       pointing +x and rotated to the curve tangent each frame. Same
       speeds, same alpha budget — the length is what makes a slow
       point read as *flow* instead of dust. */
    const mote = (key, ring, core) => {
      if (this.textures.exists(key)) return;
      const g = this.make.graphics({ add: false });
      const N = 14;
      for (let i = 0; i < N; i++) {
        const t = i / (N - 1);                 // 0 = tail, 1 = head
        g.fillStyle(ring, 0.03 + 0.3 * t * t);
        const h = 0.5 + 0.55 * t;              // half-thickness .5 → 1.05
        g.fillRect(1 + t * 17, 3 - h, 2.6, h * 2);
      }
      g.fillStyle(core, 0.95);
      g.fillRect(19, 2.3, 5, 1.4);             // leading dash, not a disc
      g.generateTexture(key, 25, 6);
      g.destroy();
    };
    mote("mote_gold", 0xfff2c0, 0xffe9a0);
    mote("mote_teal", 0xa8f0e6, 0x4fd8c8);
    // soft radial glow for source glints + the Capitol arrival pulse —
    // drawn white so each user tints it to its stream's colour
    if (!this.textures.exists("flow_glow")) {
      const g = this.make.graphics({ add: false });
      for (let r = 12; r >= 1; r--) {
        g.fillStyle(0xffffff, 0.035);          // stacked = radial falloff
        g.fillCircle(13, 13, r);
      }
      g.generateTexture("flow_glow", 26, 26);
      g.destroy();
    }

    const dst = new Phaser.Math.Vector2(
      world.capitol[0], world.capitol[1] - 14);
    const SPEED = 42;                 // px/s — a calm drift
    const MIN_DUR = 3.0;              // s — keeps short downtown hops legible
    const MAX_DUR = 60.0;             // s — neighbor-island crossings speed up
    const TARGET_MOTES = 185;         // steady-state on screen, both streams

    const incDollars = inc.totalM * 1e6;
    const getDollars = get ? get.total : 0;
    const grand = incDollars + getDollars;

    // GET rows carry no area name — borrow the income file's, which
    // covers the same ZIP geography
    const areaByZip = {};
    for (const z of inc.zips) areaByZip[z.zip] = z.area;

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
                 w: weightOf(z), acc: Math.random(), rate: 0,
                 zip: z.zip, area: z.area || areaByZip[z.zip] || "" };
      });
      const wTotal = paths.reduce((s, p) => s + p.w, 0) || 1;
      const budget = TARGET_MOTES * (dollars / grand);
      // motes on screen = Σ(rate × duration), so normalise by the
      // WEIGHTED mean duration — GET's weight sits downtown on short
      // paths, and an unweighted mean silently under-draws it.
      const wDur = paths.reduce((s, p) => s + (p.w / wTotal) * p.dur, 0);
      const rateTotal = budget / Math.max(0.5, wDur);
      for (const p of paths) p.rate = rateTotal * (p.w / wTotal);
      return { id, tex, paths, wTotal, enabled: true };
    };

    const streams = [
      mkStream(inc.zips, (z) => z.taxM, incDollars, "mote_gold", "income"),
    ];
    streams[0].tipShort = "income tax, TY" + inc.year;
    streams[0].tipNote = "";                     // measured: DOTAX by ZIP
    if (get && get.zips && get.zips.length) {
      const gs = mkStream(get.zips, (z) => z.getM, getDollars,
                          "mote_teal", "get");
      // per-ZIP GET is the MODELED half — the tooltip must say so,
      // same rule as the chip tooltip and the revenue footnote
      gs.tipShort = "GET, FY" + get.fy;
      gs.tipNote = "district total, spread modeled by population";
      streams.push(gs);
    }

    const pool = [];
    for (let i = 0; i < 420; i++) {            // headroom for highlight mode
      const im = this.add.image(0, 0, "mote_gold")
        .setDepth(3).setVisible(false).setBlendMode(Phaser.BlendModes.ADD);
      pool.push({ im, t: 0, dur: 1, curve: null, free: true, sid: null,
                  p: null });
    }

    /* ---- "✦ Streams" highlight (2026-08-21): the TEACHING view, one
       tap away, persisted. Ambient stays calm; the toggle adds
         - faint additive ribbons under the top routes, fading OUT
           before the hub (paths, never arrows — and 90 ribbons meeting
           at the Capitol would white it out),
         - breathing glints on the biggest source zips,
         - a slow arrival pulse at the Capitol,
         - slightly brighter, denser motes (RATE_HI / A_HI below).
       Everything lives in F.hi and is torn down by wireHi so stream
       toggles and scene restarts stay clean. */
    const hi = {
      on: localStorage.getItem("cq-flow-hi") === "1",
      ribbons: this.add.graphics().setDepth(2)
        .setBlendMode(Phaser.BlendModes.ADD),
      glints: [],
      pulse: this.add.image(dst.x, dst.y, "flow_glow")
        .setDepth(4).setBlendMode(Phaser.BlendModes.ADD)
        .setTint(0xffe9a0).setVisible(false),
      pulseT: 0, zBucket: -1,
    };
    for (const st of streams) {
      const top = st.paths.slice().sort((a, b) => b.w - a.w).slice(0, 8);
      for (const p of top) {
        const s0 = p.curve.getStartPoint();
        hi.glints.push({
          st, im: this.add.image(s0.x, s0.y, "flow_glow")
            .setDepth(2).setBlendMode(Phaser.BlendModes.ADD)
            .setTint(st.tex === "mote_teal" ? 0x4fd8c8 : 0xffd97a)
            .setVisible(false),
          ph: Math.random() * Math.PI * 2,
        });
      }
      st.top = top;
    }
    this.flows = { streams, pool, hi, tmp: new Phaser.Math.Vector2(),
                   tan: new Phaser.Math.Vector2() };

    /* ---- hover = the receipt (2026-08-21, user's call: "some way to
       quantify tax flows by hovering over them"). Resting the pointer
       near a streak lights its whole route and names the source ZIP
       and the dollars. Acquisition is nearest LIVE mote; after that
       the hover is sticky to the CURVE, so the moving streak doesn't
       carry the tooltip away from under the cursor. The DOM tip is
       reused across scene restarts. */
    let tip = document.getElementById("flow-tip");
    if (!tip) {
      tip = document.createElement("div");
      tip.id = "flow-tip";
      document.body.appendChild(tip);
    }
    tip.classList.remove("show");
    this.flows.tip = tip;
    this.flows.hov = null;
    this.flows.hovG = this.add.graphics().setDepth(4)
      .setBlendMode(Phaser.BlendModes.ADD);
    // overlays cover the canvas: a stale pointer under one must not
    // hold a tooltip on screen
    this.flows.ovls = Array.from(document.querySelectorAll(".ovl"));

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
        if (this.flows && this.flows.redrawHi) this.flows.redrawHi();
      };
    };
    wire("flows-chip", streams[0], "Income tax · TY" + inc.year, inc.source);
    if (streams[1]) {
      wire("get-chip", streams[1], "GET · FY" + get.fy,
           get.measured + ". " + get.modeled);
    }

    const redrawHi = () => {
      const F = this.flows;
      const g = F.hi.ribbons;
      g.clear();
      F.hi.pulse.setVisible(false);
      for (const gl of F.hi.glints) gl.im.setVisible(false);
      if (!F.hi.on) return;
      const lw = Phaser.Math.Clamp(2.2 / this.cameras.main.zoom, 2.2, 30);
      for (const st of F.streams) {
        if (!st.enabled || !st.top) continue;
        const colr = st.tex === "mote_teal" ? 0x4fd8c8 : 0xf2c14e;
        for (const p of st.top) {
          // three segments, dimming toward the hub, stopping short of it
          for (const [t0, t1, a] of [[0.03, 0.55, 0.13],
                                     [0.55, 0.80, 0.08],
                                     [0.80, 0.92, 0.04]]) {
            g.lineStyle(lw, colr, a);
            g.beginPath();
            const q = F.tmp;
            p.curve.getPoint(t0, q);
            g.moveTo(q.x, q.y);
            for (let k = 1; k <= 14; k++) {
              p.curve.getPoint(t0 + (t1 - t0) * (k / 14), q);
              g.lineTo(q.x, q.y);
            }
            g.strokePath();
          }
        }
        for (const gl of F.hi.glints) {
          if (gl.st.enabled) gl.im.setVisible(true);
        }
      }
    };
    this.flows.redrawHi = redrawHi;

    const hiChip = document.getElementById("hi-chip");
    if (hiChip) {
      hiChip.classList.remove("hidden");
      hiChip.title = "Highlight the tax streams: light the biggest " +
        "routes and where they start. Same real dollars, easier to see.";
      const setHi = () => {
        hiChip.classList.toggle("off", !hi.on);
        hiChip.textContent = (hi.on ? "✦" : "✧") + " Streams";
      };
      setHi();
      hiChip.onpointerdown = (e) => {
        e.stopPropagation();
        hi.on = !hi.on;
        localStorage.setItem("cq-flow-hi", hi.on ? "1" : "0");
        setHi();
        redrawHi();
      };
    }
    redrawHi();
  }

  update(time, delta) {
    const F = this.flows;
    if (!F) return;
    const dt = Math.min(0.05, delta / 1000);
    const hiOn = F.hi && F.hi.on;
    // highlight mode: denser and a touch brighter, still calm
    const RATE_HI = hiOn ? 1.5 : 1.0;
    const A_HI = hiOn ? 0.68 : 0.55;
    // screen-constant motes down to z≈0.07, then they fade to faint
    // gold dust crossing the channels at chain zoom
    const moteScale = Phaser.Math.Clamp(1 / this.cameras.main.zoom, 0.9, 14);
    for (const st of F.streams) {
      if (!st.enabled) continue;
      for (const p of st.paths) {
        p.acc += p.rate * RATE_HI * dt;
        while (p.acc >= 1) {
          p.acc -= 1;
          const m = F.pool.find((q) => q.free);
          if (!m) break;
          m.free = false;
          m.sid = st.id;
          m.curve = p.curve;
          m.p = p;
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
      // the streak points down its own path
      m.curve.getTangent(m.t, F.tan);
      m.im.setRotation(Math.atan2(F.tan.y, F.tan.x));
      m.im.setAlpha(A_HI * Math.sin(Math.PI * m.t));
      m.im.setScale(moteScale);
    }
    this.updateHover();
    if (F.hi) this.updateHi(time, dt, moteScale);
  }

  /* ---- flow hover: acquire on the nearest live mote, stay sticky to
     its curve, stroke the whole route and pin a DOM receipt to the
     cursor. All world-space; thresholds are screen px ÷ zoom so the
     feel is constant at any camera height. */
  nearCurve(curve, x, y, thr) {
    const q = this.flows.tan;
    const t2 = thr * thr;
    for (let k = 0; k <= 24; k++) {
      curve.getPoint(k / 24, q);
      const dx = q.x - x, dy = q.y - y;
      if (dx * dx + dy * dy < t2) return true;
    }
    return false;
  }

  updateHover() {
    const F = this.flows;
    const cam = this.cameras.main;
    const ptr = this.input.activePointer;
    let hov = null;
    if (!F.ovls.some((o) => !o.classList.contains("hidden"))) {
      cam.getWorldPoint(ptr.x, ptr.y, F.tmp);
      const wx = F.tmp.x, wy = F.tmp.y;
      const thr = 14 / cam.zoom;
      const cur = F.hov;
      if (cur && cur.st.enabled &&
          this.nearCurve(cur.p.curve, wx, wy, thr * 1.6)) {
        hov = cur;
      } else {
        let best = thr * thr, bm = null;
        for (const m of F.pool) {
          if (m.free || !m.p) continue;
          const dx = m.im.x - wx, dy = m.im.y - wy;
          const d = dx * dx + dy * dy;
          if (d < best) { best = d; bm = m; }
        }
        if (bm) {
          const st = F.streams.find((s) => s.id === bm.sid);
          if (st && st.enabled) hov = { p: bm.p, st };
        }
      }
    }
    const changed = (hov && hov.p) !== (F.hov && F.hov.p);
    F.hov = hov;
    if (!hov) {
      if (changed) { F.hovG.clear(); F.tip.classList.remove("show"); }
      return;
    }
    // restroke every frame: the line width is world px, so it has to
    // track the zoom anyway, and 25 segments is nothing
    const lw = Phaser.Math.Clamp(2.6 / cam.zoom, 2.6, 34);
    const colr = hov.st.tex === "mote_teal" ? 0x4fd8c8 : 0xf2c14e;
    const g = F.hovG;
    g.clear();
    g.lineStyle(lw, colr, 0.3);
    g.beginPath();
    const q = F.tan;
    hov.p.curve.getPoint(0, q);
    g.moveTo(q.x, q.y);
    for (let k = 1; k <= 24; k++) {
      // stop short of the hub, same manners as the highlight ribbons
      hov.p.curve.getPoint((k / 24) * 0.95, q);
      g.lineTo(q.x, q.y);
    }
    g.strokePath();
    if (changed) {
      F.tip.innerHTML = this.tipHtml(hov);
      F.tip.className =
        "show " + (hov.st.tex === "mote_teal" ? "teal" : "gold");
    }
    // follow the cursor; flip at the window edges
    const W = 270, H = 76, pad = 16;
    const x = ptr.x + W + pad > window.innerWidth
      ? ptr.x - W - pad : ptr.x + pad;
    const y = ptr.y + H + pad > window.innerHeight
      ? ptr.y - H - pad : ptr.y + pad;
    F.tip.style.left = x + "px";
    F.tip.style.top = y + "px";
  }

  tipHtml(hov) {
    const esc = (s) =>
      String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
    const p = hov.p, st = hov.st;
    const fm = (m) => m >= 950 ? "$" + (m / 1000).toFixed(1) + "B"
      : m >= 9.5 ? "$" + Math.round(m) + "M"
      : m >= 0.95 ? "$" + m.toFixed(1) + "M"
      : "$" + Math.round(m * 1000) + "K";
    const pct = 100 * p.w / st.wTotal;
    const pctS = pct >= 9.5 ? Math.round(pct) + "%" : pct.toFixed(1) + "%";
    return "<b>" + (p.area ? esc(p.area) : "ZIP " + esc(p.zip)) + "</b>" +
      (p.area ? "<span class='ft-zip'> · ZIP " + esc(p.zip) + "</span>"
              : "") +
      "<div class='ft-line'>" + fm(p.w) + "/yr → the Capitol · " + pctS +
      " of " + esc(st.tipShort) + "</div>" +
      (st.tipNote
        ? "<div class='ft-note'>" + esc(st.tipNote) + "</div>" : "");
  }

  /* the highlight layer's slow life: breathing source glints, the
     arrival pulse, and a ribbon redraw when the zoom has moved enough
     that their screen width drifted (they are stroked in world px). */
  updateHi(time, dt, moteScale) {
    const F = this.flows;
    if (!F.hi.on) return;
    const anyOn = F.streams.some((s) => s.enabled);
    if (!anyOn) return;
    const b = Math.round(Math.log2(this.cameras.main.zoom) * 3);
    if (b !== F.hi.zBucket) {
      F.hi.zBucket = b;
      F.redrawHi();
    }
    for (const gl of F.hi.glints) {
      if (!gl.im.visible) continue;
      const s = 0.8 + 0.2 * Math.sin(time / 900 + gl.ph);
      gl.im.setScale(moteScale * 1.3 * s).setAlpha(0.32 + 0.18 *
        Math.sin(time / 900 + gl.ph));
    }
    // arrival pulse: a ring of light breathing out of the Capitol
    F.hi.pulseT += dt;
    const P = 2.8, t = (F.hi.pulseT % P) / P;
    F.hi.pulse.setVisible(true)
      .setScale(moteScale * (1.0 + 2.6 * t))
      .setAlpha(0.3 * (1 - t) * (1 - t));
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
      Dialog.hide();
      this.scene.switch("capitol");
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
    /* Zoom ceiling dropped 4 → 1.35 with the painterly restyle
       (2026-08-15, user's call). The old ceiling let the camera walk
       right up to individual 18px sprites, which is where a baked map
       stops being a painting and starts being a texture — and the CRPG
       look is built to be READ from a distance, not inspected. 1.35
       still shows a neighbourhood; it just never shows brushstrokes. */
    this.maxZoom = 1.35;

    cam.centerOn(world.w / 2, world.h / 2);
    cam.setZoom(this.minZoom * 1.02);
    // the opening push-in has to land INSIDE the ceiling, so it reads
    // it rather than carrying its own number — a hardcoded 1.7 sailed
    // straight past maxZoom when the ceiling dropped to 1.35
    const introZ = Math.min(1.7, this.maxZoom);
    this.introTween = this.tweens.add({
      targets: cam,
      zoom: introZ,
      scrollX: cx - this.scale.width / 2 / introZ,
      scrollY: cy - 40 - this.scale.height / 2 / introZ,
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

/* ------------------------------------------------ interior rooms */
/* ONE RoomScene class serves every baked interior (FEATURES §4/§5):
   the Capitol gallery ring and the House Finance office, each a
   painted room + hotspot json baked by its tools/render_*.py under
   one version token (CAP_V / OFF_V — bump with the bake). cfg:
     key     scene key ("capitol", "office")
     v       cache token
     json / img   asset paths
     exitTo  where the exit hotspot / Esc goes — "world" drops
             body.in-capitol; a parent ROOM keeps it (HUD stays
             hidden through the whole interior visit)
     enter   {hotspotId: sceneKey} — doors that GO somewhere instead
             of showing their text (finance door -> the office)
     greet   [title, text] shown on entry; suppressed when waking
             from a child room (_skipGreetOnce), so walking back out
             of the office doesn't replay the rotunda speech
   scene.switch() SLEEPS the other scene rather than rebuilding it;
   the world keeps camera, flows and labels untouched underneath. */
class RoomScene extends Phaser.Scene {
  constructor(cfg) { super(cfg.key); this.cfg = cfg; }

  preload() {
    this.load.json(this.cfg.key + "_meta",
                   this.cfg.json + "?v=" + this.cfg.v);
    this.load.image(this.cfg.key + "_img",
                    this.cfg.img + "?v=" + this.cfg.v);
  }

  create() {
    const meta = this.cache.json.get(this.cfg.key + "_meta");
    this.meta = meta;
    this.cameras.main.setBackgroundColor(meta.bg || "#0a0e18");
    // The PNG ships at 1/meta.scale of the SCENE size — the bake
    // supersamples down so its edges are antialiased once, by a real
    // filter, instead of being point-sampled to death at display time
    // (see SS in tools/render_capitol.py). Everything else in this
    // file — hotspot px, label/marker offsets, the zone sizes, meta.w
    // and meta.h — stays in SCENE coordinates, so scaling the sprite
    // back up here is the ONLY place that has to know about it.
    this.ss = meta.scale || 1;
    this.add.image(0, 0, this.cfg.key + "_img")
        .setOrigin(0, 0).setScale(this.ss);
    // A room with a `view` rect zooms CONTINUOUSLY (see fit()), which
    // means non-integer resampling — so its texture switches to LINEAR
    // filtering. The bake is a LANCZOS-supersampled painting, not crisp
    // pixel art, so a filtered scale is the right treatment; per-texture
    // setFilter works on the Canvas renderer (it just takes a frame or
    // two to apply — see CLAUDE.md). Snap-fitted rooms keep NEAREST.
    if (this.cfg.view) {
      this.textures.get(this.cfg.key + "_img")
          .setFilter(Phaser.Textures.FilterMode.LINEAR);
    }

    this.labels = [];
    this.markers = [];
    const styles = {                       // same voice as makeLabel
      door: { size: 13, color: "#ffe9a8", stroke: "#4a3a10" },
      poi: { size: 11, color: "#fff6dc", stroke: "#4a3a10" },
      exit: { size: 13, color: "#eaf2ff", stroke: "#101d5c" },
    };
    for (const h of meta.hotspots) {
      // noExit: this room is the game's home — it has no way out and
      // draws no exit affordance (the Capitol, since 2026-08-26).
      if (h.kind === "exit" && this.cfg.noExit) continue;
      if (h.kind === "door") {
        const mk = this.add.image(h.px, h.py - 30, "marker");
        this.tweens.add({ targets: mk, y: mk.y - 7, duration: 550,
          yoyo: true, repeat: -1, ease: "Sine.easeInOut" });
        this.markers.push(mk);
      }
      const st = styles[h.kind] || styles.poi;
      const lab = this.add.text(h.px, h.py + 8,
        h.kind === "exit" ? "⟵ " + h.name : h.name, {
          fontFamily: '"Avenir Next", "Trebuchet MS", Verdana, sans-serif',
          fontSize: st.size + "px",
          fontStyle: "800",
          color: st.color,
          stroke: st.stroke,
          strokeThickness: 4,
          letterSpacing: 1,
        }).setOrigin(0.5, 0).setDepth(10000);
      this.labels.push(lab);
      // NAMES ARE ON HOVER, NOT PAINTED OVER THE DOORS (user's call
      // 2026-08-24: "don't have those big labels over all the doors").
      // Nine plates of stroked type across a painted room read as a
      // debug overlay and hid the thing they were labelling. The
      // bouncing marker is what says "this door is live" now; the EXIT
      // keeps its label, because the way out must never need hunting.
      if (h.kind !== "exit") lab.setVisible(false);
      const zone = this.add.zone(h.px, h.py + 6, 120, 84)
        .setInteractive({ useHandCursor: true });
      if (h.kind !== "exit") {
        zone.on("pointerover", () => lab.setVisible(true));
        zone.on("pointerout", () => lab.setVisible(false));
      }
      zone.on("pointerup", (pointer) => {
        if (pointer.getDistance() > 8) return;
        if (h.kind === "exit") { this.leave(); return; }
        const go = this.cfg.enter && this.cfg.enter[h.id];
        if (go) { this.enterChild(go); return; }
        Dialog.show(h.name, h.text);
      });
    }

    this.fit();
    this.scale.on("resize", () => this.fit());
    if (!this.cfg.noExit && this.input.keyboard)
      this.input.keyboard.on("keydown-ESC", () => this.leave());
    this.events.on("wake", () => this.enterRoom());
    this.enterRoom();
  }

  enterChild(key) {
    Dialog.hide();
    this._skipGreetOnce = true;       // don't re-greet on the way back
    this.scene.switch(key);
  }

  enterRoom() {
    document.body.classList.add("in-capitol");
    this.fit();
    if (this._skipGreetOnce) { this._skipGreetOnce = false; return; }
    Dialog.show(this.cfg.greet[0], this.cfg.greet[1]);
  }

  /* the room is a painting read whole — fit it to the window */
  fit() {
    // the canvas can report 0x0 when booted in a hidden tab/webview
    const w = this.scale.width || window.innerWidth || 800;
    const h = this.scale.height || window.innerHeight || 600;
    const cam = this.cameras.main;
    /* cfg.view = [x0, y0, x1, y1] in SCENE px: frame THIS rect instead
       of the whole canvas — the bake carries wide ink margins, and the
       main view should spend its pixels on the building (2026-08-26,
       user's call: "the view should be zoomed in more"). The zoom is
       CONTINUOUS here, not snapped: the texture is LINEAR-filtered for
       exactly this room (see create()), so a fractional resample is a
       clean filtered scale, not the uneven nearest-neighbour picking
       the snap rule exists to prevent. Capped at 0.9 — past that the
       840px texture is being blown up ~1.8x and reads as mush. */
    if (this.cfg.view) {
      const [vx0, vy0, vx1, vy1] = this.cfg.view;
      const z = Math.min(0.9, w / (vx1 - vx0), h / (vy1 - vy0));
      cam.setZoom(z);
      cam.centerOn((vx0 + vx1) / 2, (vy0 + vy1) / 2);
      const inv = Math.min(1 / z, 1.7);
      for (const t of this.labels) t.setScale(inv);
      for (const m of this.markers) m.setScale(Math.min(1 / z, 1.6));
      return;
    }
    // SNAP the zoom so one baked pixel covers a WHOLE number of device
    // pixels. The renderer is pixelArt/nearest-neighbour, so a fitted
    // zoom like 0.58 at dpr 2 = 1.161 device px per source px, which
    // duplicates some columns and not others — a regular balustrade
    // comes out with uneven pickets. That irregularity read as "the
    // railing looks off" and no amount of redrawing could fix it.
    // Measured 2026-08-22; keep the snap on any future layout change.
    // With a supersampled bake the quantum is the TEXTURE, not the
    // device: the sprite is drawn at zoom x ss, and that product must
    // be a whole number of texture pixels or we are back to an uneven
    // resample. ss 2 -> halves, and zoom .5 lands on an exact 1:1
    // blit. This also retires a real bug in the dpr form: at dpr 1
    // `Math.max(step, floor(fitZ/1)*1)` could only ever return 1, so
    // dpr-1 users got the room at 1:1 and CROPPED while dpr-2 users
    // got it fitted — the two device classes saw different scenes.
    const dpr = window.devicePixelRatio || 1;
    const fitZ = Math.min(w / this.meta.w, h / this.meta.h);
    const step = this.ss > 1 ? 1 / this.ss : 1 / dpr;
    const z = Math.max(step, Math.floor(fitZ / step) * step);
    cam.setZoom(z);
    cam.centerOn(this.meta.w / 2, this.meta.h / 2);
    const inv = Math.min(1 / z, 1.7);
    for (const t of this.labels) t.setScale(inv);
    for (const m of this.markers) m.setScale(Math.min(1 / z, 1.6));
  }

  leave() {
    if (this.cfg.noExit) return;      // the home room has no way out
    Dialog.hide();
    if (this.cfg.exitTo === "world")
      document.body.classList.remove("in-capitol");
    this.scene.switch(this.cfg.exitTo);
  }
}

const ROOM_CAPITOL = {
  key: "capitol", v: CAP_V,
  json: "map/capitol.json", img: "assets/map/capitol_scene.png",
  // The Capitol is the game's HOME view (2026-08-26): no exit hotspot,
  // no Esc-out — the map sleeps underneath, reachable again only by
  // code (drop noExit and restore exitTo's door if it ever comes back).
  exitTo: "world",
  noExit: true,
  // Content bbox of the bake, measured against the ink (scene px, then
  // a ~24px breathing margin): with the elongated well (rdiamond) the
  // building lives at [392,312..1416,952] of the 1680x1240 canvas.
  // Framing this rect instead of the canvas is what "zoomed in more"
  // means — remeasure after any re-bake that moves the composition
  // (CY, storey heights, WING_EXT).
  view: [368, 288, 1440, 976],
  enter: { finance: "office" },
  greet: ["Hawaiʻi State Capitol",
    "E komo mai — a gallery in the open rotunda. The chambers " +
    "root the courtyard below — Senate toward ʻEwa, House toward " +
    "Diamond Head — and hallways branch deeper into the building, " +
    "to committee rooms and the Level 5 elevators. No dome " +
    "overhead: the sky is Hawaiʻi's capitol dome."],
};
const ROOM_OFFICE = {
  key: "office", v: OFF_V,
  json: "map/office_finance.json", img: "assets/map/office_finance.png",
  exitTo: "capitol",
  enter: null,
  greet: ["House Finance",
    "The Finance chair's suite — koa panels and lamplight. " +
    "Committee staff read every fiscal note in the cubicles; the " +
    "chair works behind the double doors. Every dollar figure in " +
    "the House stops here first."],
};

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
    scene: [BootScene, WorldScene,
            new RoomScene(ROOM_CAPITOL), new RoomScene(ROOM_OFFICE)],
  });
});
