# Demo gaps — what's left to make weeks 1–7 playable

> **Update 2026-10-14:** blockers 1 and 3 and bugs 4 and 5 are FIXED and
> verified live. Blocker 2 is resolved as (a) — the push is back, so the
> odds are the player's own. What is left is the writing: items 6 and 7.

Audited 2026-10-14 against the live build: scene files, `session.json`,
`chairs.json`, the gate maths, and two headless playthroughs.

The demo is **structurally complete and mechanically broken**. Every week
has a scene, the creation funnel works, the ending screen works. But the
player has no lever on the one thing the demo is about — getting a
hearing — and the most likely outcome is a loss they could not have
avoided.

Everything below is a day or less. The three blockers are about two
hours.

---

## What already works

Verified live, no errors in the console:

- Creation funnel: instincts → priorities → revenue (wealth tax only,
  others greyed).
- Weeks 1–6 all have scenes; week 1 is a four-parter and plays through.
- The hallway (week 1) hands over to the Capitol at the first End Turn.
- Dice checks, the roll tray, skill voices, the transcript reader.
- The bill ledger, the gap bar, intel, the introducer strip.
- Game over when every bill dies; the end-of-demo card and the
  "What you did" summary.
- Sound, the rooms, tap-to-walk, the HUD.

---

## Blockers

### 1. No action is ever unlocked — the player cannot work the chair

**This is the big one.** I checked every scene and every calendar entry
in weeks 1–7: not one unlocks an action. So in the whole demo:

- **"Work the chair" (`push`) never appears.** It is the only thing that
  raises a bill's hearing odds, worth +15 to +20 percentage points.
- Rally, Build the bench and Work the building never appear either.
- The hub shows an "Openings" section with people to talk to, and **no
  "Act" section at all**, every single week.
- Three of the six skills are honed only by actions, so those skills
  can never grow after week 1.

The game is built around spending one move a week. In the demo you never
get one.

**Fix:** add `actions:` to the demo scenes. Week 2 or 3 should grant
`push` (it is the week you meet Kawaguchi, so it reads naturally), and
weeks 3–5 should grant `rally` / `bench` / `lobby`. One line per scene.

### 2. The odds are a coin flip the player cannot influence

With no push available, the wealth tax's chance of being heard by the
week-5 House Finance deadline is **42%**, computed from the shipped
numbers:

| Term | Value |
|---|---|
| Measured base (Finance, wealth-tax bills) | 0.256 |
| Your introducer working it | +0.120 |
| Kawaguchi's disposition | −0.032 |
| The bill's influence | +0.077 |
| **Total chance of a hearing** | **0.421** |

So **58% of demo playthroughs end in Game Over at week 5**, two weeks
before the demo's own ending, with nothing the player did wrong and
nothing they could have done differently.

That is a defensible teaching point in a 16-week campaign with three
bills. It is a bad demo: most people who try it will never see weeks 6
and 7, and the "What you did" summary they land on says they failed.

**Fix, pick one:**
- **(a)** Fix blocker 1 and let the push carry it. With one push the
  odds go to about 57–62%, and the loss becomes the player's own.
- **(b)** Also soften it for the demo — a `demo.oddsFloor`, or give the
  wealth tax a friendlier chair disposition.
- **(c)** Let the demo end at week 7 regardless, and present a dead bill
  as the lesson rather than as a loss. Needs blocker 3 fixed first.

I would do (a), and (c) if there is time.

### 3. The influence gate can lock the player out silently

There is a hard gate at House Finance: **under 28 influence the chair
will not schedule your bill at all.** The probability is zero, not low.

Influence starts at 30. It decays 1 a week and only ever drifts
downward. The demo scenes carry **eight separate −2 influence choices**
and two −4s. In my own playthrough I was sitting at **28** at the end of
week 1 — exactly on the line.

So an ordinary player makes two reasonable-sounding choices, drops to
26, and the demo is unwinnable from week 2 onward. Nothing on screen
says so.

**Fix:** either raise starting influence for the demo, or soften the
negative choices in weeks 1–4, or surface the gate in the intel panel
("under 28 and Finance won't schedule you"). The intel line is the
cheapest and it teaches the mechanic instead of hiding it.

---

## Bugs

### 4. Week 7 has no scene — the demo's last week is dead air

Weeks 2–6 fall back to a generic event when nothing is scripted. Week 7
does not, because the code only assigns generics for weeks *before* the
last one, and the demo moves the last week to 7. Opening week 7 goes
straight to the hub with no narrative at all.

**Fix:** script week 7 (the House floor vote is the obvious subject — it
is what the calendar already calls the week), or let the generic
rotation cover the final week in demo mode. `ev-introducer` is written
for Silva and would work as-is.

### 5. Game Over pre-empts the end-of-demo screen

Ending week 7 advances to week 8 and rolls the bills one more time —
past the demo's last week. In my playthrough the bill was voted down on
the House floor "in week 8", and the player saw **"Game over / your
bills are dead"** instead of the end-of-demo card and the "What you did"
summary that was built for exactly this moment.

**Fix:** at the demo boundary the demo card wins, and bills should not
resolve past the last demo week.

---

## Content gaps

### 6. Four scenes are still placeholder text

Marked `// PLACEHOLDER` in the files, my drafts, not yours:

| Scene | Week | What it is |
|---|---|---|
| `03-w3-kawaguchi` | 3 | the Kawaguchi meeting |
| `04-w4-disaster` | 4 | the hurricane |
| `04-w4-rally` | 5 | rally vs. listening session |
| `05-w5-hearing` | 5 | deadline week, two parts |

The hurricane is nearly yours already. The other three are first drafts
and read like it.

### 7. Eight of ten scenes have no banner art

Only week 1 and the Kawaguchi meeting have a picture. Three banners
exist on disk. The reader looks noticeably plainer on the other weeks.

Each new banner is a photo plus one command, and the recipe is in
`data/raw/events/BANNERS.md`. The hurricane and the hearing room would
earn theirs the most.

### 8. Two lint warnings

- `w4-disaster` has no skill voices. Every other scene has two or three.
- `souza-intro` is read in week 8 but nothing sets it any more. Week 8
  is outside the demo, so this is harmless until the full game returns.

---

## Suggested order

| | Task | Rough time |
|---|---|---|
| 1 | Unlock actions in weeks 2–5 (blocker 1) | 15 min |
| 2 | Surface the influence gate in intel (blocker 3) | 20 min |
| 3 | Fix the demo-boundary ending (bug 5) | 30 min |
| 4 | Write or script week 7 (bug 4) | 30–60 min |
| 5 | Re-run the odds and a full playthrough | 30 min |
| 6 | Rewrite the four placeholder scenes | yours |
| 7 | Two or three banners | 20 min each |

Items 1–5 are the difference between a demo that works and one that
doesn't. That is about two and a half hours. Items 6 and 7 are polish
and can land in any order after.

---

## What to write, in order

The mechanics are fixed; the rest is prose. In priority order, with what
each scene now has to carry.

### 1. `05-w5-hearing` — week 5, the deadline (two parts)

**The most important scene in the demo.** It is where the whole question
resolves, and it is the last week the player can do anything about it.
Both nodes are my draft.

It has to carry three things:
- **The clock.** Friday is the end. A bill not heard is not voted down,
  it just never comes up.
- **The last move.** Working the chair is still available this week —
  this is the final chance to spend it.
- **No verdict.** The scene must not say whether your bill was heard.
  The engine rolls that when the week ends, and the answer arrives on
  the next week's report. Say what the room feels like, not how it came
  out.

### 2. `03-w3-kawaguchi` — week 3, the chair

Now carries more weight than when I drafted it: **week 3 is where the
player is handed "work the chair."** The scene is the introduction to
the one lever they have, so meeting Kawaguchi should make it obvious
that his calendar is the thing standing between them and a hearing —
and that they can come back and press him.

### 3. `04-w4-rally` — week 4, rally vs. listening session

The Mobilizing / Base Building fork, and the week that grants the rally
and the bench. The teaching is that turnout and durability are bought
separately: the rally is loud and fades, the bench is dull and lasts.
Let them actually disagree.

### 4. Week 7 — the demo's ending

Right now it falls back to a generic (leadership leaning on Silva). It
works and it is about the right size, but it is not written as an
ending. A scripted week 7 would send the player out on the demo's own
terms — the House floor vote is what the calendar already calls the
week.

### 5. `04-w4-disaster` — the hurricane

Nearly yours already. It only needs **two or three instinct voices**;
it is the one scene in the demo with none, and the lint flags it.

---

## Two things to watch while you write

**The influence floor is 28, and the demo spends influence freely.**
Weeks 1–4 carry eight −2 influence choices and two −4s. Influence starts
at 30 and only ever drifts down. Two ordinary-looking choices put the
player under the line, where Finance will not schedule them at all. The
gate is now visible in the intel panel, so it is no longer invisible —
but if you want the demo to be winnable by an ordinary player, the
negative choices in weeks 1–4 are where to look.

**Mention the move.** The player now gets one action a week from week 2
on. Scenes that never refer to it leave a mechanic sitting unused in the
hub. A line in weeks 3 and 5 pointing at the chair's calendar is enough.

