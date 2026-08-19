/* Capitol Quest — UI sound.
 *
 * The sounds are SYNTHESISED here, at runtime, with the Web Audio API.
 * There are no audio files in this repo and there is nothing to load.
 * Three reasons, in order of how much they matter:
 *
 *   1. LATENCY. These are interface clicks — a pip going up, a dialogue
 *      line being picked. A click that arrives 40ms after the finger
 *      does not read as feedback, it reads as a glitch, and a decoded
 *      sample buffer cannot beat an oscillator that starts on the same
 *      turn of the event loop.
 *   2. It is the same bargain every other asset in this project makes:
 *      the map, the banners, the sprites and the glyphs are all CODE
 *      that produces art, so a change is a diff and not a binary. A
 *      sound designed as eight numbers can be tuned in a text editor.
 *   3. No third-party licence to carry, attribute or get wrong.
 *
 * If a sampled pack (Kenney's UI audio, CC0, is the obvious candidate)
 * is ever wanted instead, everything in the game calls SFX.<name>() and
 * nothing calls an oscillator directly — swap the bodies, keep the
 * names, and no call site changes.
 *
 * ===================================================================
 * HOUSE RULES. These are the audio half of "Disco Elysium's lighting
 * logic, not its brushwork", and the first pass (2026-08-19) broke
 * every one of them — it came out as arcade chiptune and was rejected
 * on the spot ("I don't want cartoony sounds, more serious RPG-like").
 * What was wrong is more useful than what is right, so:
 *
 * - **STRUCK MATERIALS, NEVER MELODY.** The single biggest cartoon
 *   tell was a rising major arpeggio for success and two falling notes
 *   for failure. A tune playing at the player is a mobile game telling
 *   them they did well. A serious verdict is ONE struck object with a
 *   long decay — the ear reads weight and material, not intervals.
 *   Nothing in this file plays more than one pitched event per call.
 * - **NO PITCH LADDER.** The first pass transposed the instinct click
 *   by the skill's RANK, so spending five points walked up a scale.
 *   That is the coin-collect sound, and it is charming exactly once.
 *   A click is a MECHANISM: it makes the same sound every time,
 *   varied only by a few percent of randomness so a fast repeat
 *   doesn't machine-gun.
 * - **NO SQUARE WAVES.** Square and sawtooth are chiptune however they
 *   are enveloped. Body comes from sine partials; everything else is
 *   filtered noise.
 * - **NOISE THROUGH A RESONANT BANDPASS IS THE WHOLE TRICK.** A high-Q
 *   bandpass over a noise burst IS a struck object — the Q sets how
 *   much it rings, the frequency sets how big it is. Wood, felt, a
 *   brass fitting and a stone counter are all the same three numbers.
 * - **DARK.** A master lowpass at 5.2kHz sits over everything. Bright
 *   top end is what makes UI audio sound plastic; the room this game
 *   happens in is wood panelling and paper.
 * - **PERCUSSIVE.** Every voice is under 400ms except the two
 *   verdicts, which earn their tail. This is a reading game — a sound
 *   that rings is a sound heard over the sentence being read.
 * - **MEASURED, not guessed.** "Cartoony" is mostly SPECTRAL CENTROID
 *   (perceived brightness) and decay length, and both are measurable
 *   from the page — tap whatever connects to ctx.destination with an
 *   AnalyserNode and read peak, centroid and audible tail. The tuning
 *   pass that produced these numbers caught two things the code looked
 *   fine for: everything was ~12dB too quiet, and FAILURE was coming
 *   out BRIGHTER than success (2458Hz against 1626Hz), which is
 *   backwards for the duller of two verdicts. Re-measure after any
 *   change to a gain or a filter frequency here.
 *
 * Measured at the destination, 2026-08-19 — peak amplitude and
 * AMPLITUDE-WEIGHTED centroid over the whole event, six takes each
 * (a single-frame centroid at the peak is far too noisy to compare,
 * because a 46ms FFT window lands on the transient for one sound and
 * on the body for the next):
 *
 *     pipUp     peak .061   bright 1644 Hz
 *     pipDown   peak .074   bright 1284 Hz
 *     choice    peak .108   bright  982 Hz
 *     dieLand   peak .091   bright 1168 Hz
 *     win       peak .184   bright  706 Hz
 *     lose      peak .160   bright  437 Hz
 *
 * The ORDER is the design and matters more than any single number:
 * brightness falls from click to commitment to verdict, failure is the
 * dullest thing in the game, and the verdicts are about 3x the level
 * of a click. Everything sits under 1.7kHz, which is what keeps it
 * wood and paper rather than plastic.
 */
window.SFX = (function () {
  "use strict";

  var KEY = "cq-sfx";
  var MASTER = 0.8;
  var ctx = null, bus = null, noiseBuf = null;
  var off = false;
  try { off = localStorage.getItem(KEY) === "off"; } catch (e) { off = false; }

  /* The context is created LAZILY, on the first sound, and every entry
     point is a pointerdown — so it is always born inside a user
     gesture and never trips the autoplay policy. Creating it at load
     would produce a context stuck in "suspended" on most browsers,
     which then swallows the first click of the session. resume() is
     still called every time: a backgrounded tab can suspend it again
     and it comes back silent otherwise. */
  function audio() {
    if (off) return null;
    if (!ctx) {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) { off = true; return null; }     // no Web Audio, no sound
      ctx = new AC();
      // the master lowpass: see the DARK house rule. Everything the
      // game plays goes through it, so brightness is one number and
      // not a decision repeated in nine places.
      var lp = ctx.createBiquadFilter();
      lp.type = "lowpass";
      lp.frequency.value = 5200;
      bus = ctx.createGain();
      bus.gain.value = MASTER;
      bus.connect(lp);
      lp.connect(ctx.destination);
      // 0.6s of white noise, made once and re-pointed at by every
      // transient — allocating a buffer per click is garbage per click
      var n = Math.floor(ctx.sampleRate * 0.6);
      noiseBuf = ctx.createBuffer(1, n, ctx.sampleRate);
      var d = noiseBuf.getChannelData(0);
      for (var i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
    }
    if (ctx.state === "suspended" && ctx.resume) ctx.resume();
    return ctx;
  }

  function out(node, pan) {
    var c = ctx;
    if (pan && c.createStereoPanner) {
      var p = c.createStereoPanner();
      p.pan.value = pan;
      node.connect(p);
      p.connect(bus);
    } else {
      node.connect(bus);
    }
  }

  /* A STRUCK OBJECT. Noise through a resonant bandpass: `freq` is how
     big the thing is, `q` is how much it rings (1-2 = a dull knock on
     wood, 6-12 = something metal), `dur` is the decay. This one
     primitive is the whole percussive palette — a counter on a desk, a
     die on a table and a latch closing are the same three numbers with
     different values. */
  function strike(o) {
    var c = audio();
    if (!c) return;
    var t = c.currentTime + (o.at || 0);
    var src = c.createBufferSource();
    src.buffer = noiseBuf;
    // a few percent of pitch wander, so a fast repeat is not a machine
    // gun — this is the ONLY variation a click gets (see NO PITCH LADDER)
    src.playbackRate.value = 0.9 + Math.random() * 0.2;
    var f = c.createBiquadFilter();
    f.type = "bandpass";
    f.frequency.value = o.freq * (0.97 + Math.random() * 0.06);
    f.Q.value = o.q === undefined ? 2 : o.q;
    var g = c.createGain();
    g.gain.setValueAtTime(o.gain, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + o.dur);
    src.connect(f); f.connect(g);
    out(g, o.pan);
    src.start(t);
    src.stop(t + o.dur + 0.02);
  }

  /* The BODY of a struck thing: a sine partial with a decay, optionally
     dropping in pitch (which is what a soft mallet on something heavy
     does). Sine only — see NO SQUARE WAVES. Two or three of these at
     inharmonic ratios read as one object, not as a chord; a fifth and
     an octave read as music, which is exactly what this file avoids. */
  function body(o) {
    var c = audio();
    if (!c) return;
    var t = c.currentTime + (o.at || 0);
    var osc = c.createOscillator();
    var g = c.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(o.f0, t);
    if (o.f1 && o.f1 !== o.f0) {
      osc.frequency.exponentialRampToValueAtTime(o.f1, t + (o.bend || o.dur));
    }
    // the attack is a ramp, not a step: a gain that jumps from zero
    // adds a click of its own on top of the one that was designed
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(o.gain, t + (o.atk || 0.004));
    g.gain.exponentialRampToValueAtTime(0.0001, t + o.dur);
    osc.connect(g);
    out(g, o.pan);
    osc.start(t);
    osc.stop(t + o.dur + 0.02);
  }

  var API = {
    /* Raising or lowering an instinct — THE click, and the one the
       player hears most (five points across six cards, freely spent
       and refunded). It is a bone counter set down on a wooden desk:
       a dry knock with just enough body to have mass.
       Up and down differ by MATERIAL WEIGHT, not by pitch: down is
       lower, duller and a touch longer, the way setting something back
       down is heavier than picking it up. There is deliberately no
       argument for the skill's rank — see NO PITCH LADDER. */
    pip: function (up) {
      if (up) {
        strike({ freq: 1350, q: 1.8, gain: 0.16, dur: 0.026 });
        strike({ freq: 560, q: 3.8, gain: 0.26, dur: 0.055 });
        body({ f0: 300, f1: 190, dur: 0.05, gain: 0.07, bend: 0.04 });
      } else {
        strike({ freq: 900, q: 1.6, gain: 0.13, dur: 0.032 });
        strike({ freq: 380, q: 3.2, gain: 0.26, dur: 0.075 });
        body({ f0: 205, f1: 130, dur: 0.07, gain: 0.08, bend: 0.055 });
      }
    },

    /* Committing to a dialogue line, or pressing Continue. The same
       family as the pip but heavier and further back — a hardwood
       drawer pushed shut. A pip is an adjustment you will probably
       make again; this is a decision that has landed, so it wants mass
       and a little room rather than brightness. */
    choice: function () {
      strike({ freq: 1050, q: 1.3, gain: 0.09, dur: 0.028 });
      strike({ freq: 300, q: 2.8, gain: 0.30, dur: 0.14 });
      body({ f0: 160, f1: 104, dur: 0.16, gain: 0.12, bend: 0.09 });
    },

    /* One die turning over while the tray tumbles. Called every 75ms,
       so it has to be nearly nothing: at that rate any real volume is
       a rattle can and any pitched content is a drone. Dry wooden
       clatter, randomised, and quiet enough to sit under the tray
       without competing with the verdict it is leading to. */
    dieTick: function () {
      strike({ freq: 1500 + Math.random() * 900, q: 2.4, gain: 0.085,
               dur: 0.016, pan: Math.random() * 0.5 - 0.25 });
    },

    /* The dice hitting the table. Two of them, staggered by `i`, each a
       knock with a real low drop under it — this is the beat that says
       the numbers are final, so it is the loudest thing in the roll
       apart from the verdict. */
    dieLand: function (i) {
      var at = (i || 0) * 0.08;
      var pan = i ? 0.28 : -0.28;
      strike({ freq: 900, q: 1.5, gain: 0.34, dur: 0.05, at: at, pan: pan });
      strike({ freq: 260, q: 2.2, gain: 0.30, dur: 0.13, at: at, pan: pan });
      body({ f0: 150, f1: 62, dur: 0.18, gain: 0.13, at: at, bend: 0.10,
             pan: pan });
    },

    /* THE VERDICT — one struck object, not a tune. Both are the same
       gesture with different materials, which is the point: the game
       is not congratulating or scolding, it is telling you the die is
       cast. Success is brass — brighter partials, a clean ring that
       opens up. Failure is the same strike on something dead: lower,
       inharmonic, and it decays without ever opening. The partial
       ratios are deliberately NOT consonant (1 : 1.51 : 2.44 and
       1 : 1.43 : 2.11) so neither reads as a chord.
       They ring longer than anything else here — up to a second — and
       that is affordable only because the tray already holds for 2.2s
       on the stamp. Do not lengthen them past that hold. */
    win: function () {
      strike({ freq: 1600, q: 1.4, gain: 0.10, dur: 0.03 });
      body({ f0: 392, dur: 0.85, gain: 0.150, atk: 0.008 });
      body({ f0: 592, dur: 0.62, gain: 0.085, atk: 0.010 });
      body({ f0: 957, dur: 0.34, gain: 0.030, atk: 0.012 });
    },
    lose: function () {
      // no bright transient at all: the strike is the DEAD thud, and
      // the measured centroid has to land BELOW win's or failure reads
      // as the brighter, livelier of the two — which it did on the
      // first tuning pass (2458Hz against win's 1626)
      strike({ freq: 380, q: 1.4, gain: 0.16, dur: 0.06 });
      strike({ freq: 165, q: 2.0, gain: 0.26, dur: 0.30 });
      body({ f0: 174, dur: 1.00, gain: 0.160, atk: 0.010 });
      body({ f0: 249, dur: 0.70, gain: 0.060, atk: 0.014 });
    },

    /* Snake eyes and boxcars already get an extra 700ms of hold and
       their own animation (a gold burst / a shake). The sound layers a
       SECOND strike under the verdict rather than adding a flourish on
       top — boxcars ring the same brass again, harder and higher;
       snake eyes drop a dead weight underneath. Still no melody. */
    jackpot: function () {
      strike({ freq: 3000, q: 1.4, gain: 0.13, dur: 0.04, at: 0.20 });
      body({ f0: 588, dur: 1.05, gain: 0.085, atk: 0.008, at: 0.20 });
      body({ f0: 889, dur: 0.72, gain: 0.045, atk: 0.012, at: 0.20 });
    },
    snake: function () {
      strike({ freq: 150, q: 1.4, gain: 0.26, dur: 0.42, at: 0.20 });
      body({ f0: 87, f1: 58, dur: 1.10, gain: 0.11, atk: 0.014,
             bend: 0.55, at: 0.20 });
    },

    muted: function () { return off; },
    /* Toggling ON has to make a sound: it is the only confirmation
       that anything is working, and it also creates the context inside
       the gesture that turned it on. */
    toggle: function () {
      off = !off;
      try { localStorage.setItem(KEY, off ? "off" : "on"); } catch (e) {}
      if (!off) API.pip(true);
      return off;
    },
  };
  return API;
})();
