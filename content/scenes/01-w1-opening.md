---
_note: Opening Day. The HR1 SNAP/Medicaid material that used to open this scene moved to its own week-3 event (w3-federal) 2026-08-15 — week 1 was doing two jobs and doing neither well. Keep this node about the room and the gap; the federal numbers belong to w3-federal, which is where their data lineage note now lives too.
unlocks._note: Opening Day opens the whole ground floor: the scripted week-1 talks (these used to live on the calendar entry) plus a first walk through the building.
talks: office=w0-briefing, kawaguchi=w1-kawaguchi, grange=w1-grange, coalition, rep-x=talk-rep, sen-x=talk-sen
actions: lobby
---

# w1-opening

## B · start
// DRAFT opening line — Devin is writing this conversation's choices.
**Rep. X:** They're waiting in the alcove off the House corridor, folder under one arm, still wearing the lei from the floor. "There you are. The clerk wants bill forms by Friday, and before my name goes on them I want to hear it from you: what am I carrying, and who's standing behind me when I carry it?"

// placeholder until the choices land: the old flow carries on to the presser
-> C

## C · presser
Opening Day. Lei on every railing, three governors in the gallery — and the press set up on the makai steps, where your campaign has the 9 a.m. slot. One microphone, four minutes, every outlet in town. What's the message?

- **Talk Story:** Four minutes, every outlet in town. Read the room before you read the line.
- **Mobilizing:** Whatever you say, say it loud enough that the back row remembers it Monday.

### 1. "Tax fairness, by name. The register pays more than the penthouse."
The crowd claps. Upstairs, two office doors close quietly. Grange, at the edge of the steps, writes one word on a legal pad.

- effect: +5 support, -4 influence
- then: D

### 2. "Cost of living. Discipline. A budget that doesn't wobble."
Inside, the murmurs are approving. Somewhere on the sidewalk, a coalition text thread goes quiet.

- effect: +5 influence, -3 support
- then: D

### 3. Four minutes of pure aloha — thank everyone, promise nothing.
Warm, safe, forgettable. Three offices call before lunch asking for 'whatever that one-pager was.'

- effect: +1 support, +1 influence
- then: D

## D · carriers
- _note: The bills are already chosen when this plays (agenda lock -> runEvent), so this is the handoff, not a pitch. It exists to put two faces on the sentence 'members carry the bills' before the gauntlet starts.
Room 312, after the cameras leave. Two members are waiting for you, and between them they are the only reason your package exists as paper rather than opinion. Rep. X will file in the House this week and walk it through Finance. Sen. X gets it in April, if it lives that long, and has read exactly none of it yet. "So," Rep. X says, pulling the introduction forms over, "whose name goes first, and what do we do when Finance asks us to cut it?"

- **Procedure:** Introduction is the one step that cannot fail. Everything after it can. Use the free step to set the terms.
- **Talk Story:** Two members, two chambers, one package — and they have not talked to each other about it once. That is your job now, not theirs.

### 1. "Both names on both bills. You two are a team before Finance is a problem."
Sen. X raises an eyebrow at being volunteered, then signs anyway. It costs you something upstairs — leadership notices members pairing off early — and buys you two people who now have to call each other.

- effect: +6 house, +6 senate, -2 influence
- then: end

### 2. "Rep. X leads. Sen. X, stay clean until crossover."
A conventional, competent split. Rep. X takes the weight and the credit. Sen. X gets a package in April with somebody else's fingerprints on it, and remembers that.

- effect: +10 house, -4 senate, +2 influence
- then: end

### 3. [Base Building 12 red] "We cut nothing. Tell Finance the number is the bill."
- mods: support/25, TALK STORY/4
Pass:
Rep. X looks at the forms for a while. "If I say that in Finance, I own it — and if you leave me out there alone, I don't get it back." You tell them who is standing behind them, by name and by number. They file it whole.

- effect: +12 house, +4 senate, +3 support, flag held-the-number
Fail:
"That's a great line for a rally," Rep. X says, not unkindly, "and I'm the one who has to say it to a chair who signs my committee assignments." The forms get filed. A trim is already implied.

- effect: -6 house, -2 support
