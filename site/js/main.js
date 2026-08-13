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

/* ---------------------------------------------------------------- budget */
const BudgetPanel = {
  built: false,
  init(data) {
    if (this.built || !data) return;
    this.built = true;
    const $ = (id) => document.getElementById(id);
    const fmt = (v) =>
      v >= 995e6 ? "$" + (v / 1e9).toFixed(v >= 9.95e9 ? 0 : 1) + "B" :
      v >= 1e6 ? "$" + Math.round(v / 1e6) + "M" :
      "$" + Math.round(v / 1e3) + "K";

    $("budget-title").textContent = "State Budget · FY" + data.fy;
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

    const overlay = $("budget-overlay");
    $("tb-budget").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      overlay.classList.toggle("hidden");
      document.getElementById("revenue-overlay").classList.add("hidden");
      Dialog.hide();
    });
    $("budget-close").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      overlay.classList.add("hidden");
    });
    overlay.addEventListener("pointerdown", (e) => {
      if (e.target === overlay) overlay.classList.add("hidden");
    });
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") overlay.classList.add("hidden");
    });
  },
};

/* ---------------------------------------------------------------- revenue */
const RevenuePanel = {
  built: false,
  init(data) {
    if (this.built || !data) return;
    this.built = true;
    const $ = (id) => document.getElementById(id);
    const fmtK = (v) =>            // amounts arrive in $ thousands
      v >= 995e3 ? "$" + (v / 1e6).toFixed(v >= 9.95e6 ? 1 : 2) + "B" :
      "$" + Math.round(v / 1e3) + "M";

    $("revenue-title").textContent = "Revenue Mix · FY" + data.fy;
    const d = data.distribution;
    $("revenue-hero").innerHTML =
      "<b>" + fmtK(data.total) + "</b> in state tax collections, FY" +
      data.fy +
      "<small>Where it went: " + fmtK(d.general_fund) +
      " (87%) to the general fund · " + fmtK(d.counties) +
      " to the counties · " + fmtK(d.special_funds) +
      " to special funds</small>";

    const rows = $("revenue-rows");
    const max = data.taxes[0].amt;
    for (const t of data.taxes) {
      const row = document.createElement("div");
      row.className = "brow";
      row.title = t.who;
      const share = 100 * t.amt / data.total;
      const shareTxt = share >= 1 ? Math.round(share) + "%" :
        share.toFixed(1) + "%";
      const cls = t.stream === "income" ? "sw-gf"
        : t.stream === "get" ? "sw-get" : "sw-fed";
      row.innerHTML =
        '<span class="bname">' + t.name + (t.stream ? " ★" : "") + "</span>" +
        '<span class="bbar"><i class="' + cls +
        '" style="width:' + (100 * t.amt / max) + '%"></i></span>' +
        '<span class="bval"><b>' + fmtK(t.amt) + "</b> · " + shareTxt +
        "</span>";
      rows.appendChild(row);
    }

    $("revenue-foot").textContent =
      "Cash collections by tax type, all funds. Source: " + data.source +
      ". Hover a row for who pays it. ★ marks the two taxes drawn on the " +
      "map: income tax by ZIP (real geography) and GET spread by business " +
      "payroll (DOTAX publishes GET island-wide only). The budget spends " +
      "more than this because federal dollars and bond proceeds are added " +
      "on top of state taxes.";

    const overlay = $("revenue-overlay");
    $("tb-revenue").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      overlay.classList.toggle("hidden");
      document.getElementById("budget-overlay").classList.add("hidden");
      Dialog.hide();
    });
    $("revenue-close").addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      overlay.classList.add("hidden");
    });
    overlay.addEventListener("pointerdown", (e) => {
      if (e.target === overlay) overlay.classList.add("hidden");
    });
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") overlay.classList.add("hidden");
    });
  },
};

/* ---------------------------------------------------------------- scenes */
class BootScene extends Phaser.Scene {
  constructor() { super("boot"); }
  preload() {
    this.load.json("meta", "map/oahu.json?v=1");
    this.load.json("flows", "map/tax_flows.json?v=1");
    this.load.json("budget", "map/budget.json?v=1");
    this.load.json("revenue", "map/revenue.json?v=1");
    this.load.json("get_flows", "map/get_flows.json?v=1");
  }
  create() {
    const meta = this.cache.json.get("meta");
    for (const s of meta.slices) {
      this.load.image("map_" + s.file, "assets/map/" + s.file + "?v=1");
    }
    this.load.image("capitol", "assets/sprites/capitol.png?v=1");
    this.load.image("marker", "assets/sprites/marker.png?v=1");
    for (let i = 0; i < 3; i++) {
      this.load.image("sp" + i, `assets/sprites/sparkle_${i}.png?v=1`);
    }
    this.load.once("complete", () => this.scene.start("world", meta));
    this.load.start();
  }
}

class WorldScene extends Phaser.Scene {
  constructor() { super("world"); }

  create(meta) {
    this.meta = meta;
    this.cameras.main.setBackgroundColor(DEEP_BLUE);
    this.cameras.main.setBounds(0, 0, meta.w, meta.h);

    for (const s of meta.slices) {
      this.add.image(s.x, s.y, "map_" + s.file).setOrigin(0, 0).setDepth(0);
    }

    this.buildSparkles(meta);
    this.buildCapitol(meta);
    this.buildFlows(meta);
    this.buildLabels(meta);
    BudgetPanel.init(this.cache.json.get("budget"));
    RevenuePanel.init(this.cache.json.get("revenue"));

    this.setupCamera(meta);
    this.setupInput();

    this.scale.on("resize", () => this.applyLabelScale());
  }

  /* ---- tax inflows: quiet motes drifting from source areas into the
     Capitol. Two streams — gold = individual income tax (DOTAX A-14, real
     ZIP geography), teal = general excise tax (DOTAX island total, spread
     by Census business payroll — see build_get_flows.py). Mote density is
     kept proportional to real dollars across both streams, so the eye
     reads GET as the bigger one, which it is. ---- */
  buildFlows(meta) {
    this.flows = null;
    const inc = this.cache.json.get("flows");
    const get = this.cache.json.get("get_flows");
    if (!inc || !inc.zips || !inc.zips.length) return;

    const mote = (key, ring, core) => {
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

    const lm = meta.landmarks.find((l) => l.id === "capitol");
    const dst = new Phaser.Math.Vector2(lm.px, lm.py - 14);
    const SPEED = 42;                 // px/s — a calm drift
    const MIN_DUR = 3.0;              // s — keeps short downtown hops legible
    const TARGET_MOTES = 185;         // steady-state on screen, both streams

    const incDollars = inc.totalM * 1e6;
    const getDollars = get ? get.oahuTotal : 0;
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
                 len, dur: Math.max(MIN_DUR, len / SPEED),
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
        mkStream(get.zips, (z) => z.share, getDollars, "mote_teal", "get"));
    }

    const pool = [];
    for (let i = 0; i < 240; i++) {
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
      chip.addEventListener("pointerdown", (e) => {
        e.stopPropagation();
        stream.enabled = !stream.enabled;
        if (!stream.enabled) release(stream.id);
        setLabel();
      });
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
    const moteScale = Phaser.Math.Clamp(1 / this.cameras.main.zoom, 0.9, 3.2);
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

  /* ---- water sparkles ---- */
  buildSparkles(meta) {
    this.anims.create({
      key: "sparkle",
      frames: [{ key: "sp0" }, { key: "sp1" }, { key: "sp2" },
               { key: "sp1" }, { key: "sp0" }],
      frameRate: 7,
    });
    const pts = Phaser.Utils.Array.Shuffle(meta.sparkles.slice()).slice(0, 160);
    for (const [x, y] of pts) {
      const sp = this.add.sprite(x, y, "sp0").setDepth(2).setAlpha(0.9);
      this.time.addEvent({
        delay: 1200 + Math.random() * 5200,
        loop: true,
        callback: () => sp.play("sparkle"),
      });
    }
  }

  /* ---- the State Capitol landmark ---- */
  buildCapitol(meta) {
    const lm = meta.landmarks.find((l) => l.id === "capitol");
    const cap = this.add.image(lm.px, lm.py + 6, "capitol")
      .setOrigin(0.5, 0.9).setDepth(lm.py);
    cap.setInteractive({ useHandCursor: true, pixelPerfect: false });

    const mk = this.add.image(lm.px, lm.py - 78, "marker").setDepth(lm.py + 1);
    this.tweens.add({
      targets: mk, y: mk.y - 8, duration: 550,
      yoyo: true, repeat: -1, ease: "Sine.easeInOut",
    });

    cap.on("pointerup", (pointer) => {
      if (pointer.getDistance() > 8) return;   // was a drag, not a tap
      const fl = this.cache.json.get("flows");
      const money = fl && fl.totalM
        ? "The golden streams you see are real: in tax year " + fl.year +
          ", Oʻahu residents owed about $" + (fl.totalM / 1000).toFixed(1) +
          " billion in state income tax, all flowing here. "
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

  /* ---- place labels ---- */
  buildLabels(meta) {
    this.labels = [];
    const styles = {
      town: { size: 13, color: "#ffffff", stroke: "#1b2a4a", weight: "800" },
      nature: { size: 12, color: "#eaf6d8", stroke: "#25431f", weight: "700" },
      range: { size: 15, color: "#f0ead2", stroke: "#3d3323", weight: "800" },
      poi: { size: 11, color: "#ffe9a8", stroke: "#4a3a10", weight: "700" },
      capitol: { size: 13, color: "#ffe9a8", stroke: "#4a3a10", weight: "800" },
    };
    for (const lm of meta.landmarks) {
      const st = styles[lm.kind] || styles.town;
      const dy = lm.kind === "capitol" ? 26 : 0;
      const txt = this.add.text(lm.px, lm.py + dy, lm.name, {
        fontFamily: '"Avenir Next", "Trebuchet MS", Verdana, sans-serif',
        fontSize: st.size + "px",
        fontStyle: st.weight,
        color: st.color,
        stroke: st.stroke,
        strokeThickness: 4,
        letterSpacing: lm.kind === "range" ? 3 : 1,
      }).setOrigin(0.5, 0).setDepth(10000);
      txt._kind = lm.kind;
      this.labels.push(txt);
    }
    this.applyLabelScale();
  }

  applyLabelScale() {
    const z = this.cameras.main.zoom;
    const inv = 1 / z;
    for (const t of this.labels) {
      t.setScale(Math.min(inv, 2.6));
      const vis =
        t._kind === "range" ? z <= 1.1 :
        t._kind === "poi" ? z >= 1.6 :
        t._kind === "capitol" ? z >= 0.9 :
        true;
      t.setVisible(vis);
    }
  }

  /* ---- camera: intro flight, then free pan/zoom ---- */
  setupCamera(meta) {
    const cam = this.cameras.main;
    const [cx, cy] = meta.camera.capitol;
    const fit = Math.max(
      this.scale.width / meta.w, this.scale.height / meta.h);
    this.minZoom = Math.max(fit * 0.95, 0.22);
    this.maxZoom = 4;

    cam.centerOn(meta.w / 2, meta.h * 0.45);
    cam.setZoom(this.minZoom * 1.02);
    this.introTween = this.tweens.add({
      targets: cam,
      zoom: 1.7,
      scrollX: cx - this.scale.width / 2 / 1.7,
      scrollY: cy - 40 - this.scale.height / 2 / 1.7,
      duration: 3000,
      delay: 500,
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
