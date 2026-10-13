---
_note: WEEK 1, PART ONE AND TWO. Node A is the narration beat; Continue leads to node B, the dialogue with Rep. Christina Silva (it was the optional talk w1-silva, merged in here 2026-10-12, Devin: "the second dialogue is with that representative Silva"). Then the HANDOFF (node C — the bills go to Silva and Sen. X; it used to close w1-opening), then the three-way choice (node D: legislators — the old optional w1-kawaguchi talk, merged as E; the coalition — talk-coalition's text, F; or leave and do policy research — new, G; each ends the scene), and then the week's own scene, w1-opening, runs the presser. Original note: Week 1's narration beat — the room, the number, before anyone speaks. It runs as week 1's `pre` (calendar), then w1-opening starts at the Rep. X talk. It used to be node A of w1-opening; moved out so it can be edited on its own (2026-10-12, Devin).
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
- then: D

### 2. "Rep. Silva leads. Sen. X, stay clean until crossover."
A conventional, competent split. Silva takes the weight and the credit. Sen. X gets a package in April with somebody else's fingerprints on it, and remembers that.

- effect: +10 house, -4 senate, +2 influence
- then: D

### 3. [Base Building 12 red] "We cut nothing. Tell Finance the number is the bill."
- mods: support/25, TALK STORY/4
- then: D
Pass:
Silva looks at the forms for a while. "If I say that in Finance, I own it — and if you leave me out there alone, I don't get it back." You tell them who is standing behind them, by name and by number. They file it whole.

- effect: +12 house, +4 senate, +3 support, flag held-the-number
Fail:
"That's a great line for a rally," Silva says, not unkindly, "and I'm the one who has to say it to a chair who signs my committee assignments." The forms get filed. A trim is already implied.

- effect: -6 house, -2 support

## D · options
The cameras are not set until nine. Silva has the floor session and a gavel to be early for, Sen. X has a bill-drafting office that opens when it opens, and for the first time since you walked in, nobody needs anything from you for an hour.

It is the only free hour of the session, and everyone in the building will spend theirs on someone. Where does yours go?

- **Talk Story:** An hour in a building full of people who are, today, all reachable. By Friday most of them won't be.
- **Policy Brain:** Or the opposite instinct: the building will still be here at nine, and so will every number you haven't read yet.
- **Base Building:** Whoever you spend today on, you will be asking them for something in March. Choose the ones you will still be asking.

### 1. Work the rotunda. Find the chair of House Finance.
You go where the Capitol is loudest, because the person you need is somewhere in it.

- then: E

### 2. Find the coalition's table. Talk to the people who showed up.
Folding tables by the east doors, a printer on an extension cord, and sixty organizations' worth of volunteers in matching shirts.

- then: F

### 3. Leave the building. Go do policy research.
You walk out past the lei stands and the press risers into plain morning light, a laptop bag on one shoulder and a very specific list.

- then: G

## E · chair
**Rep. Jon Kawaguchi:** Kawaguchi doesn't look up from the committee referral sheet. "I schedule what can pass. The bills your people are carrying — I can hear one of them early, IF the ask is trimmed to something the floor survives. Or you keep the full number and wait for me to find a week. Maybe I find one."

- **Policy Brain:** A trimmed bill that passes still moves real dollars. A poster that dies in committee moves none. Run the math before the ego does.
- **Base Building:** Trim it and the base watches you fold on the ask before the fight even starts. That costs more than $25M.
- **Procedure:** He said 'find a week.' Weeks are HIS. But a chair who names a date in front of a witness has spent something he can't unspend.

### 1. Trim the ask. Get the early hearing.
"Smart." He initials the sheet. Your bill just got $25M/yr lighter — and a hearing date.

- effect: -$25M revenue, +3 influence
- then: end

### 2. Hold the number. "Find the week, chair."
A long pause. "Bold." It is not clear that 'bold' is a compliment on this floor.

- effect: +3 support
- then: end

### 3. [Procedure 12 red] "Name the date, chair. In front of your team."
- mods: influence/25, TALK STORY/3
Pass:
He looks around the room, then at you, and writes a date on the referral sheet in pen. "February 14th. Don't make me regret the ink."

- effect: -2 influence, flag kawaguchi-date
Fail:
"In front of staff?" The sheet goes face-down. "I'll find a week." He will not find a week.

- effect: -5 influence

## F · coalition
The coalition count on the wall: 61 orgs on the meals bill, 40 on the credit, 'it's complicated' scrawled next to anything with the word conveyance in it. One big turnout moment fits in a month — whoever asks early gets it.

- **Mobilizing:** This is your actual caucus. The one that shows up in matching shirts.
- **Base Building:** Sixty-one organizations, one shared printer. Respect the logistics or lose the coalition to burnout.

### 1. "Give us two weeks' notice, always."
Noted on the wall. Two weeks is apparently considered a luxury.

- effect: +1 support
- then: end

### 2. [Talk Story 8 white] "Forget the calendar. What does the coalition actually need?"
Pass:
The math on the wall stops for a second. Someone writes: SOMEBODY TO NOT DISAPPEAR IN APRIL. Under it, in smaller writing, three more things — none of them a rally.

- effect: +4 support, flag coalition-trust
Fail:
Same answer as always: bodies at a hearing. You asked a real question in a hallway, which is where real questions go to be small talk.

- effect:

## G · research
Forty minutes across town, a library carrel with a working outlet, and the only reading anyone in this campaign will do all week that is not on a phone in a hallway. You have an hour and room for exactly one stack.

- **Policy Brain:** The real number is never the one on the one-pager. It is two footnotes down, in a table nobody has opened since the last forecast.
- **Educator:** Whatever you read, you will have to say it in a sentence a stranger repeats on the elevator. Read for the sentence.
- **Procedure:** The calendar is already running. Anything you learn about how the building decides is worth more than anything you learn about what it decides.

### 1. The Council on Revenues forecast, line by line.
Nine point eight billion against ten point six, and the footnotes explain why the gap is not an accident. You come away knowing which line items will move first when somebody has to cut.

- effect: +1 POLICY BRAIN, -1 influence
- then: end

### 2. Who actually claims the tax credits, and what for.
A table in a report nobody has opened: the money goes where the paperwork is easy, not where the need is. It is the cleanest sentence you will have all session.

- effect: +1 EDUCATOR, -1 influence
- then: end

### 3. Last session's hearing records. Who was heard, and who was not.
Eight hundred and seventy-six referrals to Finance, and a pattern in which ones got a date. It is a map of the building's habits, drawn by the building.

- effect: +1 PROCEDURE, -1 influence
- then: end
