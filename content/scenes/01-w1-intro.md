---
_note: WEEK 1, PART ONE AND TWO. Node A is the narration beat; Continue leads to node B, the dialogue with Rep. Christina Silva (it was the optional talk w1-silva, merged in here 2026-10-12, Devin: "the second dialogue is with that representative Silva"). Then the HANDOFF (node C — the bills go to Silva and Sen. X; it used to close w1-opening), and then the week's own scene, w1-opening, runs the presser. Original note: Week 1's narration beat — the room, the number, before anyone speaks. It runs as week 1's `pre` (calendar), then w1-opening starts at the Rep. X talk. It used to be node A of w1-opening; moved out so it can be edited on its own (2026-10-12, Devin).
art: w1-opening
---

# w1-intro

## A · start
It's the first day of the session. Hundreds of people stream into the Capitol, filling the offices and balconies. Draped in leis, legislators and their staff welcome visitors with tables of plate lunches.

You work your way through the crowd and spot Representative Silva.

-> B

## B · silva
**Rep. Christina Silva:** Rep. Silva finds you by the koa doors, all smiles. "Big session, yeah? The business folks in my district can live with a lot — but the conveyance thing reads like a tax on selling your own house. Help me help you: carve out everything under three million, and I keep them neutral. Friendly, even."

- **Policy Brain:** The bill already exempts owner-occupied homes under the standard threshold — that's not spin, that's the bill text. Cite it and watch her improvise.
- **Base Building:** Neutral-to-friendly from the business caucus is a real asset. Just don't pay for it with language the base will notice missing.

### 1. "It already exempts owner-occupied homes. Read the bill, Representative."
The smile holds, one degree cooler. "Then I will read the bill very... closely."

- effect: +2 support, -2 influence
- then: C

### 2. "Send me your carve-out language. No promises."
"That's all I ask." It is never all she asks.

- effect: +3 influence
- then: C

### 3. [Base Building 12 red] "Say it on the record, then. At the hearing, under your own name."
- mods: support/25
Pass:
The smile finally goes. "I don't usually put things on the record this early." She doesn't put this one there at all. Your bill gets a hearing without a villain in the room.

- effect: +3 support, -2 influence
Fail:
"Happy to!" And she does — warmly, at length, in favor of a version of your bill that does not exist. The committee writes down HER number.

- effect: +2 influence, -4 support

## C · carriers
- _note: The bills are already chosen when this plays (agenda lock -> runEvent), so this is the handoff, not a pitch. It exists to put two faces on the sentence 'members carry the bills' before the gauntlet starts.
Silva walks you down the corridor to Room 312, where Sen. X is already waiting. Between the two of them they are the only reason your package exists as paper rather than opinion. Silva will file in the House this week and walk it through Finance. Sen. X gets it in April, if it lives that long, and has read exactly none of it yet. "So," Silva says, pulling the introduction forms over, "whose name goes first, and what do we do when Finance asks us to cut it?"

- **Procedure:** Introduction is the one step that cannot fail. Everything after it can. Use the free step to set the terms.
- **Talk Story:** Two members, two chambers, one package — and they have not talked to each other about it once. That is your job now, not theirs.

### 1. "Both names on both bills. You two are a team before Finance is a problem."
Sen. X raises an eyebrow at being volunteered, then signs anyway. It costs you something upstairs — leadership notices members pairing off early — and buys you two people who now have to call each other.

- effect: +6 house, +6 senate, -2 influence
- then: end

### 2. "Rep. Silva leads. Sen. X, stay clean until crossover."
A conventional, competent split. Silva takes the weight and the credit. Sen. X gets a package in April with somebody else's fingerprints on it, and remembers that.

- effect: +10 house, -4 senate, +2 influence
- then: end

### 3. [Base Building 12 red] "We cut nothing. Tell Finance the number is the bill."
- mods: support/25, TALK STORY/4
Pass:
Silva looks at the forms for a while. "If I say that in Finance, I own it — and if you leave me out there alone, I don't get it back." You tell them who is standing behind them, by name and by number. They file it whole.

- effect: +12 house, +4 senate, +3 support, flag held-the-number
Fail:
"That's a great line for a rally," Silva says, not unkindly, "and I'm the one who has to say it to a chair who signs my committee assignments." The forms get filed. A trim is already implied.

- effect: -6 house, -2 support
