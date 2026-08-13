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

/* ---------------------------------------------------------------- scenes */
class BootScene extends Phaser.Scene {
  constructor() { super("boot"); }
  preload() {
    this.load.json("meta", "map/oahu.json?v=1");
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
    this.buildLabels(meta);

    this.setupCamera(meta);
    this.setupInput();

    this.scale.on("resize", () => this.applyLabelScale());
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
      Dialog.show(
        "Hawaiʻi State Capitol",
        "Every state law — and every dollar in Hawaiʻi's budget — passes " +
        "through this building. Here the Legislature decides how much to " +
        "collect in taxes, and where it all goes. (Module 1: Taxes & the " +
        "Budget — coming soon. Step inside!)"
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
