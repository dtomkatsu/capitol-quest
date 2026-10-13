---
_note: WEEK 2 — THE KAWAGUCHI MEETING, moved back here from week 5 on 2026-10-12 (Devin's call, for the weeks-1-to-6 demo: "move his convo from later to 2"). It was week 5's w5-decking, and week 2's Yamamoto courtesy call (w2-yamamoto, talk-yamamoto) was set aside in content/drafts/ to make room; its `yamamoto-open` flag is gone, and w4-souza now reads `souza-intro` instead. NOTHING HERE MAY IMPLY A HEARING OR NOTICE HAS HAPPENED — Finance's referral deadline is still week 5 (chairs.json stages.h-fin). The old decking-day lines (the notice at four, watching it post) were rewritten for week 2. Original week-5 note follows. DEADLINE WEEK, and THE KAWAGUCHI MEETING. Finance's referral deadline is week 5 (chairs.json stages.h-fin), and the date Kawaguchi may have named via the week-1 optional talk (`talk-kawaguchi`) is February 14th — THIS week — so a player who earned `kawaguchi-date` is walking in already owed something. TWO-PART ART carries over unchanged from the original placement: the dialogue-level `art` (w2-finance, the Beretania breezeway) carries the approach, the `office` node overrides it with w2-finance-office; renderNode reads `n.art || dlg.art`. Sets `souza-intro`, spent in w8-crossover and w11-wam — both AFTER this week, so the causality holds now that the meeting sits at week 5 instead of week 2. w4-souza used to read `souza-intro` from here when this was week 2; since the meeting is now three weeks LATER than w4-souza, that scene reads `yamamoto-open` (set in w2-yamamoto) instead — keep it that way, or w4 is checking a flag that cannot exist yet.
art: w2-finance
talks: kawaguchi, office, rep-x=talk-rep
actions: lobby, push
---

# w2-kawaguchi

## A · start
Fifteen minutes, his scheduler said, and she said it twice. So you wait in the breezeway where the trades come through, watching the courtyard fill and empty and fill. Nothing has been referred to Finance yet, and the lateral file that decides who gets heard this year is three weeks off. Kawaguchi called you up here himself, which nobody in this hallway does for a courtesy.

- **Procedure:** Read the room right: a chair who wants you to hear something from him instead of off a printout is either doing you a favor or bracing you for a loss. Both cost him time he doesn't have today.
- **Talk Story:** Week two, and the chair of Finance found fifteen minutes for you before there is anything to hear. Chairs don't spend that on a stranger without wanting something back.

### 1. Bring the fiscal note. Fifteen minutes, one number.
You leave the binder in the bag and walk in with a single page.

- effect: +1 influence
- then: B

### 2. Bring the caseload pages. Fifteen minutes, one family.
Sixteen thousand five hundred and seventy adults, and one of them with a name and a district.

- effect: +1 support
- then: B

### 3. Bring nothing. Let him say the first thing.
You go up empty-handed, which in this building is either confidence or a mistake, and nobody can tell which until afterward.

- effect: 
- then: B

## B · office
- art: w2-finance-office
**Rep. Jon Kawaguchi:** He doesn't stand. "Sit. The first notices are three weeks out, and I wanted you to hear where you stand from me, not off a phone in that hallway with everyone else." He turns his chair a few degrees toward the window. "Eight hundred and seventy-six measures came to Finance last session. I heard a fraction of them and I'm not apologizing for the fraction." A pause, and this is the part he actually called you up here for. "My problem, if you make my notice in February, is that whatever I hear, Ways and Means hears after me. And Chris Souza hasn't returned a call of mine since November."

- **Policy Brain:** 876 referrals, and this committee hands back one of the two lowest hearing rates in the building. He isn't being dramatic, he's quoting his own workload.
- **Procedure:** He just drew you the route: Finance, then Ways and Means. A bill he hears today is still a bill Souza can bury in April. Plan for two gates, not one.
- **Talk Story:** "Hasn't returned a call since November" isn't a complaint, it's an offer. He wants something carried to the Senate that he can't be seen carrying himself.

### 1. "Then tell me what Ways and Means needs to hear."
He writes two words on a legal pad, tears the sheet off and slides it across: FLOOR, NOT CEILING. "Souza doesn't care what your bill raises. He cares what it costs him in a bad year. Go answer that, and don't tell him I said so."

- effect: +3 influence
- then: C

### 2. "Hear one of ours early, chair. I'll fill your room."
"Everybody fills my room." But he writes something down, which is more than he did in January.

- effect: +3 support, -1 influence
- then: C

### 3. [Talk Story 13 red] "Call him. From this office, while I'm sitting here."
- mods: influence/25, flag kawaguchi-date +2 "the date he gave you", PROCEDURE/3
- then: C
Pass:
He looks at you a long moment, then picks up the desk phone. He does not get Souza. He gets a scheduler — and he uses the chair's voice on her, the one he has not once used on you. "Jon Kawaguchi. Put them on the calendar." He hangs up. "That is the entire favor. Don't spend it saying hello."

- effect: -2 influence, flag souza-intro
Fail:
"In my own office?" He puts one hand flat on the desk, which is as close as this man comes to raising his voice. "When I want the Senate to know what I'm doing, I'll tell them myself."

- effect: -4 influence

## C · friday
You're back in the hallway outside Finance with everyone else who doesn't have a chair's ear, watching the same door you just walked out of. Nothing posts today. But you know which way he leans now, and that is more than the forty other measures that will get fifteen minutes and a closed door instead of an open one will ever learn about him.

- **Procedure:** Fifteen minutes with the chair is not a hearing, and nothing has been scheduled. Whatever he decides, you will read it standing up in a hallway in three weeks, same as everyone who didn't get the meeting.

### 1. Head back to the office.
You walk out past the same koa door, a few feet closer to the chair's ear than most people ever get.

- effect: 
- then: end
