---
_note: WEEK 3 (2026-10-13: moved from week 2 — week 2 is now the legislator briefing (w2-briefing) and the office-manager scheduling scene (w2-schedule), whose Talk Story pass sets `kawaguchi-date`, read in the office check below; all 'two weeks out' timing is now 'two', since the referral deadline is still week 5; the meeting now opens with a greeting beat — fact-sheet check [pass -> the meeting, fail -> a short brush-off] or small talk about his Japan trip [Talk Story check] — before the old office meeting, now node E; the three bring-something choices in A were cut).  — THE KAWAGUCHI MEETING, moved back here from week 5 on 2026-10-12 (Devin's call, for the weeks-1-to-6 demo: "move his convo from later to 2"). It was week 5's w5-decking, and week 2's Yamamoto courtesy call (w2-yamamoto, talk-yamamoto) was set aside in content/drafts/ to make room; its `yamamoto-open` flag is gone, and w9-souza now reads `souza-intro` instead. NOTHING HERE MAY IMPLY A HEARING OR NOTICE HAS HAPPENED — Finance's referral deadline is still week 5 (chairs.json stages.h-fin). The old decking-day lines (the notice at four, watching it post) were rewritten for week 2. Original week-5 note follows. DEADLINE WEEK, and THE KAWAGUCHI MEETING. Finance's referral deadline is week 5 (chairs.json stages.h-fin), and the date Kawaguchi may have named via the week-1 optional talk (`talk-kawaguchi`) is February 14th — THIS week — so a player who earned `kawaguchi-date` is walking in already owed something. TWO-PART ART carries over unchanged from the original placement: the dialogue-level `art` (w2-finance, the Beretania breezeway) carries the approach, the `office` node overrides it with w2-finance-office; renderNode reads `n.art || dlg.art`. Sets `souza-intro`, spent in w8-crossover and w11-wam — both AFTER this week, so the causality holds now that the meeting sits at week 5 instead of week 2. w9-souza used to read `souza-intro` from here when this was week 2; since the meeting is now three weeks LATER than w9-souza, that scene reads `yamamoto-open` (set in w2-yamamoto) instead — keep it that way, or w4 is checking a flag that cannot exist yet.
art: w2-finance
talks: kawaguchi, office, silva=talk-rep
---

# w2-kawaguchi

## A · start
Fifteen minutes, his scheduler said, and she said it twice. So you wait in the breezeway where the trades come through, watching the courtyard fill and empty and fill. Nothing has been referred to Finance yet, and the lateral file that decides who gets heard this year is two weeks off. Your request made it onto his calendar, which in this hallway does not happen for a courtesy.

- **Procedure:** Read the room right: a chair who wants you to hear something from him instead of off a printout is either doing you a favor or bracing you for a loss. Both cost him time he doesn't have today.
- **Talk Story:** Week three, and the chair of Finance found fifteen minutes for you before there is anything to hear. Chairs don't spend that on a stranger without wanting something back.

-> B

## B · greeting
- art: w2-finance-office
**Rep. Jon Kawaguchi:** You exchange greetings. He barely looks up from the referral sheet. "Hi. How can I help you?"

- **Policy Brain:** Skip the small talk. The numbers are what really matters.
- **Talk Story:** Get to know him a little bit. You'll have time for the policy talk later.

### 1. [Policy Brain 12 red] Hand him a fact sheet and dive straight into your tax agenda.
- mods: influence/25
Pass:
He reads the page, all of it, and then reads the number again. "Who checked this?" You tell him. He puts it under the referral sheet instead of on top of the pile, which is a very small and very specific kind of yes.

- effect: +2 influence
- then: F
Fail:
As you drone on, Kawaguchi's eyes start to glaze over. He fidgets with the pencil on his desk.

- effect: -4 influence
- then: D

### 2. Ask him how his session's been going. Is he getting any downtime?
He looks up for the first time.

- then: C

## C · casual
- art: w2-finance-office
**Rep. Jon Kawaguchi:** He says it's been a busy week, but nothing he hasn't seen before. His eyes light up when he starts talking about his family trip to Japan last month.

- **Talk Story:** A man who lights up about Japan isn't stalling. He just showed you the door he actually keeps open.
- **Procedure:** Fifteen minutes, and the clock is running whichever way this goes. Steer it, or spend it.

### 1. [Procedure 13 white] Steer the conversation back to policy.
- mods: influence/25
// PLACEHOLDER: Devin is rewriting the pass and fail text.
Pass:
You wait for the end of his sentence, thank him for the story, and ask one question about the referral sheet under his hand. He looks at it, then at you, and answers it.

- effect: +2 influence
- then: F
Fail:
He catches the shift and nods, a little sorry to see the trip go. "Right." He glances at the clock and the moment is gone.

- effect: -2 influence
- then: F

### 2. [Talk Story 8 white] Ask him about the trip.
- mods: influence/25
Pass:
Ten minutes of ramen, a bullet train, and a daughter who ordered for the whole table in Japanese. By the end he is leaning back in his chair. "Okay. Now what did you actually come up here for?"

- effect: +2 influence
- then: F
Fail:
"Uh—" You trail off, unable to follow up. He waits a beat, then checks the clock.

- effect: -2 influence
- then: F

## D · brushoff
- art: w2-finance-office
He takes the page and squints at the wall of text and charts as if it's Ancient Greek.

**Rep. Jon Kawaguchi:** "Thanks, uh, for this. I'll look it over later." He says it in a less-than-convincing tone, filing it away among his messy stacks of paper.

- **Educator:** A fact sheet is a document. A sentence is the thing he repeats to Souza. You handed him the document.

### 1. Thank him and go.
Fifteen minutes, and he used four of them. The door closes softly, which is somehow worse.

- then: F

## F · friday
You're back in the hallway outside Finance with everyone else who doesn't have a chair's ear, watching the same door you just walked out of. Nothing posts today. But you know which way he leans now, and that is more than the forty other measures that will get fifteen minutes and a closed door instead of an open one will ever learn about him.

- **Procedure:** Fifteen minutes with the chair is not a hearing, and nothing has been scheduled. Whatever he decides, you will read it standing up in a hallway in two weeks, same as everyone who didn't get the meeting.

### 1. Head back to the office.
You walk out past the same koa door, a few feet closer to the chair's ear than most people ever get.

- effect: 
- then: end
