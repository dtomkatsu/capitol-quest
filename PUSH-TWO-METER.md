# Scoping: should the call-in push read both meters?

The question: the push — now "calls to the chair's office" — scales with
**influence** only. Should it read **public support** too?

Short answer: **yes, and it is safer than it looks.** But the reason to
do it is not the one you'd expect. The influence scaling it already has
does nothing.

Measured against the live JSON with `simulate_gauntlet.py`, 3,000
sessions a cell, seed 7.

---

## Finding 1 — the push you have now is a flat number

The shipped formula steps up every 30 points of the bill's influence,
counted from 30. A wealth bill carries a −10 influence tilt, so the
first step needs **campaign influence 70**. Nothing in a seven-week demo
gets near that.

What the push actually pays, on the demo's wealth tax:

| Campaign meters | Shipped | Two-meter (tuned) |
|---|---|---|
| support 50, influence 30 | 0.15 | 0.18 |
| support 60, influence 30 | 0.15 | 0.20 |
| support 70, influence 34 | 0.15 | 0.22 |
| support 80, influence 38 | 0.15 | 0.24 |
| support 95, influence 57 | 0.15 | 0.30 |

**0.15 in every column.** The player builds a campaign for seven weeks
and the push pays exactly what it paid on day one. "The push scales with
the influence behind it" is true in the code and invisible in play.

So this is not really "add a second meter to a working gradient." It is
"the gradient never starts; give it something it can actually read."

## Finding 2 — the calibration is safe, and structurally so

The thing to protect is the simulator's passive anchor: a passive
campaign must stay at exactly its documented band or the design doc's
numbers stop describing the game.

**A passive campaign never pushes.** So nothing inside `pushBonus` can
move it — not by careful tuning, by construction. Same for the rally,
bench and call-out profiles, which spend their move elsewhere. Measured:

| Profile | Shipped | Two-meter | Change |
|---|---|---|---|
| passive | 2.7% | 2.7% | **0.0** |
| call-out (lobby) | 4.5% | 4.5% | 0.0 |
| rally | 3.8% | 3.8% | 0.0 |
| bench | 4.0% | 4.0% | 0.0 |
| balanced | 6.6% | 7.6% | +1.0 |
| push-first | 9.5% | 12.3% | **+2.8** |

Only the two profiles that actually push move at all. That is the whole
risk surface, and it is small and legible.

**+2.8pp on push-first is the one number to decide about.** It is a 29%
relative increase on the most effective strategy in the game. Either
accept it and update the design doc, or tune it out by widening the
divisors — it is one constant either way.

## Finding 3 — in the demo, the gradient is the smaller lever

Chance the wealth tax is heard by the week-5 deadline:

| Meters | 1 push | 2 pushes | 3 pushes |
|---|---|---|---|
| s50 / i30 | 46% → 47% | 50% → 52% | 54% → 56% |
| s60 / i30 | 46% → 48% | 50% → 53% | 54% → 58% |
| s70 / i34 | 48% → 50% | 52% → 56% | 55% → 61% |
| s80 / i38 | 49% → 53% | 53% → 59% | 57% → 65% |

(shipped → two-meter)

Reading across is the meter gradient; reading down is **how many weeks
you spent on it**. Down is worth far more. The demo grants the push in
weeks 3, 4 and 5, so a player who spends all three is already at 54–57%
on the shipped maths. The second meter adds a few points on top and,
more importantly, makes those points *visible*.

---

## The design question to settle first

`CLAUDE.md` is emphatic:

> support still must not make a hearing easier unless the chair is
> aligned; it does its work at the dilution step

A two-meter push bends that. My argument that it is consistent, not a
violation:

- That rule governs the **standing** term — support sitting there
  passively making an unaligned chair friendlier, which it should not.
- A push is support being **spent**. The documented physics is "support
  is a STOCK that gets spent, influence is a RATE" — and until now
  nothing in the game actually spent it except a missed floor vote.
- A call-in campaign is literally support converting into a chair's
  scheduling decision. If any mechanic should read support, it is this
  one.

But it does mean a high-support campaign gets paid **twice**: once at
dilution, once at scheduling. Which leads to —

**Worth doing at the same time: make the push cost support.** Modelled
below — and it turns out to be the piece that makes the whole change
free.

---

## Recommendation

**Do it**, in this shape:

```
bonus = min(0.30,
            0.15
          + max(0, billSupport   - 50) / 450
          + max(0, billInfluence - 30) / 540)
```

- **Floor stays 0.15.** The existing one-sided rule — a reward for
  standing must never take something from a player who has none — and it
  is why this cannot nerf anybody.
- **Support carries two thirds of the climb, influence one third.** It
  is a call-in campaign; the people are the mechanism and the standing
  is whether the office picks up.
- **Cap stays 0.30**, so it can still never dwarf the measured base rate.
- **Continuous, not bucketed.** Every other term in `chairOdds` is a
  `/div`, and buckets are what made the current version invisible: a
  step the player never reaches teaches nothing, and a step they do
  reach is a cliff they cannot see coming.

Three things to do with it, in order:

1. Decide on the **+2.8pp to push-first** — accept and document, or
   widen the divisors until it lands where you want.
2. Decide on the **support cost**. I would add it.
3. Re-run `simulate_gauntlet.py` and update the bands in
   `DESIGN-11-bills-and-checks.md` §8d/§8e. The doc is explicit that a
   change moving these is a finding to explain, not a number to paper
   over.

About an hour, most of it the re-run and the doc.

---

## The support cost, modelled

A call-in spends your list. Charging the push support turns it into a
genuine stock-spend and kills the double-dip. **12,000 sessions a cell,
standard error ±0.27pp**, so anything under about half a point is noise.

| Design | Push-first | Balanced | Push-first end support |
|---|---|---|---|
| shipped (one meter, free) | 9.51% ±0.27 | 6.27% ±0.22 | 51.0 |
| two-meter, free | 11.81% ±0.29 | 7.54% ±0.24 | 51.0 |
| **two-meter, cost 2** | **9.65% ±0.27** | **7.22% ±0.24** | **43.7** |
| two-meter, cost 3 | 8.97% ±0.26 | 6.98% ±0.23 | 40.2 |

**Cost 2 pays for the gradient exactly.** Push-first lands at 9.65%
against the shipped 9.51% — a difference of 0.14pp against a ±0.27pp
error, i.e. the same number. So you can add the second meter and the
design doc's headline band does not move at all. The free version needed
+2.8pp explained; this one needs nothing explained.

Passive, rally, bench and the call-out stay at exactly their shipped
rates in every row, as before — they never push.

### Two things it does that are arguably improvements

**It narrows push-first's dominance.** The gap over a mixed rotation
goes from 3.24pp to 2.43pp, because balanced gains (6.27 → 7.22) while
push-first holds. The simulator's own notes flag push-first beating
every rotation as a finding rather than a goal; this softens it without
touching anything else.

**It puts a real price on the game's most-repeated verb.** A push-first
campaign now ends the session at 43.7 support instead of 51.0 — it
drains the thing it runs on. The dilution floor is 45, so a wealth bill
(+12 support tilt) still sits safely at 55.7 and the dollar figures
barely move (average scale 0.58 → 0.57). But the pressure is now real
and visible, and for a family with a negative support tilt — GET at −10,
admin at −4 — it would start biting. That is the right shape: spamming
the call-in should eventually cost you the bill's size even when it
works.

### In the demo it is nearly free

Pushing in weeks 3, 4 and 5, chance of a hearing by the deadline:

| Design | start support 55 | start support 65 | support left |
|---|---|---|---|
| shipped (free) | 55% | 55% | 65 |
| two-meter, free | 58% | 59% | 65 |
| **two-meter, cost 2** | **57%** | **59%** | **59** |
| two-meter, cost 3 | 57% | 59% | 56 |

Six points of support over three weeks, against a demo that hands it out
generously and a dilution floor far below. Visible — it is the size of a
bad dialogue choice — without being punishing.

---

## Revised recommendation

**Do both, together.** The two-meter push alone needs a +2.8pp
explanation; the two-meter push *with a cost of 2* needs none.

```
bonus = min(0.30, 0.15
          + max(0, billSupport   - 50) / 450
          + max(0, billInfluence - 30) / 540)
cost  = 2 support, charged when the push is taken
```

What is left to do, in order:

1. Build it — `pushBonus` takes support, `gate.push` gains `supportDiv`,
   `influenceDiv`, `costSupport`. Mirror it in the simulator's port,
   which is the one place the two can silently desync.
2. Print the cost on the button. An unadvertised charge is not a
   decision — the same rule the checked-choice ante already follows.
3. Re-run `simulate_gauntlet.py` at 20k and update §8d/§8e. The bands
   should come back unchanged for every profile except balanced.

About an hour.

