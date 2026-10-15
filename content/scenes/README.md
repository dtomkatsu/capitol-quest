# Scene scripts

Every dialogue in the game — weekly events, generic events, talks — is a
Markdown file here, one per dialogue. The file is named `NN-<id>.md` (`02-w2-yamamoto.md`): the id is what the game uses, and the two-digit prefix only sorts them — the week for scripted scenes, 20 for generic events (`ev-`), 30 for talks (`talk-`). `scenes.py new` picks the prefix for you; renaming a file's prefix never changes the id.
They compile into the `dialogues` block of `site/map/session.json`; nothing
else in that file is touched. **Edit these, never the JSON.** They are plain
text so they can be typed into from the tablet (Paper › Library ›
Documents › Edit).

```
python3 tools/scenes.py new w9-thing        # scaffold, with every skill's slot
python3 tools/scenes.py check               # lint everything
python3 tools/scenes.py build               # lint, then write session.json (+ bump its ?v=)
python3 tools/scenes.py tree w9-thing       # decision tree to mark up -> build/tree-w9-thing.svg
python3 tools/scenes.py map                 # whole session + flag lines -> build/session-map.svg
python3 tools/scenes.py stats               # voice balance, checks per skill, flag ledger
python3 tools/scenes.py show w9-thing       # what it compiles to (debugging)
```

`content/drafts/` holds drafts that are NOT in the game; move one in here
to ship it.

## The format

```
---                                   header: scene-level fields
_note: Free text that ships as _note (any _key: does).
art: w2-finance                       banner, site/assets/events/<art>.png
at: {"island": "hawaii"}              week-beat camera target (JSON)
talks: silva=talk-rep, office, sen-x=talk-sen doors this scene opens (bare id = talk-<id>)
actions: bench, lobby                 ("push" = the call-in-on-a-chair rows)
---

# w5-decking                          title (ignored)

## A · start                          a beat: letter, then id (first = start)
- art: w2-finance-office              beat fields go first
Kawaguchi: "Sit." He doesn't stand.   Name: on the FIRST line = whole beat is theirs
A blank line starts a new paragraph.
- Procedure: A skill voice.           instincts are bullets
- Talk Story: Another one.

### 1. Bring the fiscal note.         a choice
You walk in with one page.            its reply
- Policy Brain: voices can chime in on a reply too
- effect: +1 influence
- then: B                             a beat's letter or id; "end" or blank = scene ends

### 2. [Talk Story 13 red] "Call him."   a dice check: skill, DC, red|white
- mods: influence/25, flag kawaguchi-date +2 "the date he gave you"
- effect: -1 support                  ANTE: paid on commit, win or lose
Pass:
He picks up the phone.
- effect: -2 influence, flag souza-intro
- then: B
Fail:
"In my own office?"
- effect: -4 influence

### 3. [Brain 4+] Lead with the platform.   forced at Policy Brain 4+ (see below)

## B · office
-> C                                  a beat with no choices: Continue to C
```

`// …` lines are notes to yourself; they never ship. Bold is optional
(`**Kawaguchi:**` = `Kawaguchi:`).

**Names.** Skills by display name or short alias — `Policy Brain` /
`Brain`, `Procedure` / `Proc`, `Educator` / `Edu`, `Talk Story` / `Talk`,
`Mobilizing` / `Mob`, `Base Building` / `Base`. Speakers by name or last
name (`Yamamoto`, `Rep. X`, `Silva`) or id. A beat with no speaker is
narration — that is how the player's own campaign talks (faceless, per
CLAUDE.md). Souza never speaks.

**Effects**, comma-separated after `effect:`: `+2 support`, `-1 influence`,
`+6 house` / `-3 senate` (introducer rapport), `-$600M revenue` (also `$K`,
`$B`), `flag some-flag`, `+1 TALK STORY` (a skill pip), `unlock talk
silva=talk-silva`, `unlock action bench`. Blank = nothing happens.

**Mods** on a check: `support/25` (+1 per 25 support), `influence/25`,
`PROCEDURE/3` (+1 per 3 skill), `flag id +2 "label"` (bonus if the flag is
set), `chair h-fin/10 "label"`.

## Writing the skills

The six are the player's instincts arguing with each other — Disco-style,
never a narrator explaining. Each has one job; a line that could belong to
two of them belongs to neither.

| Skill | Pole | Hears… | Sounds like |
|---|---|---|---|
| POLICY BRAIN | wonk | the number, and whether it's real | "876 referrals, and the second-lowest hearing rate in the building. He's quoting his workload." |
| PROCEDURE | wonk | the clock and the rules | "He just drew you the route: Finance, then Ways and Means. Plan for two gates." |
| EDUCATOR | wonk | the sentence that makes it click | "Nobody disputes the numbers. What they don't have is a sentence connecting a recert form to a tax bill." |
| TALK STORY | organizer | the person in front of you | "'Hasn't returned a call since November' isn't a complaint, it's an offer." |
| MOBILIZING | organizer | bodies in the room, now | "This is the building's real acoustics test. Let them hear who the budget is for." |
| BASE BUILDING | organizer | who's still with you in week 14 | "Give them a district and a name, not a coalition letterhead." |

Mobilizing ≠ Base Building: turnout is spiky and fast, durability is slow
and unglamorous. Never let them say the same thing.

Rules of thumb: two or three voices per node; at least one from each pole
when the choice is wonk-vs-organizer; let them disagree. Short — one or two
sentences. **Educator and Mobilizing are badly under-written** (3 lines
each vs. ~20 for the others — run `stats`); reach for them first.

## Decision trees

- **Inside a scene**: beats plus `then:`. Branches can rejoin (three choices
  all `then: B`). Run `tree` to see it.
- **Across scenes, flags are the only memory.** Set one with
  `effect: flag name`; a later scene reads it ONLY as a check mod
  (`flag name +2 "label"`). There is no "show this choice if" — write for
  that. `stats` prints every flag's setters and readers; mind the week
  order (a flag read before it can be set is a bug).
- **Checked choices:** a `then:` directly under the choice heading is where
  BOTH outcomes go. Put one under `Pass:` or `Fail:` only when that outcome
  goes somewhere else — it overrides the shared one.
- **White** checks can be retried when the bonus improves; **red** checks
  are one shot. Both outcomes need real content.
- An event's `talks:`/`actions:` decide what the player can do that week;
  a choice can open more with `unlock`. A generic event that opens
  nothing is a dead week.

## Editing by pen (the tablet loop)

`tree <id> --pages` also writes one page per node (`tree-<id>-A.svg`…) laid out like the game's reader — who speaks, how the beat opens and lands, each instinct's line (silent ones as a dashed slot: write on it to add one), each choice as a numbered card with its reply, ▲/▼ effects and next node, checks drawn as a pass/fail fork, and an empty card to write a new choice in. That is the one to mark up on the tablet; it needs no legend. `tree` draws a scene as a page to mark up: every node has a letter (A, B…)
and every choice a handle (A1, B3), each node shows its six skill chips
(filled = speaks) and has a blank notes box. Mark it and send it back:
an arrow from a choice to a node = go there; circle a hollow chip and
scribble = add that skill's line; strike = cut; margin writing = rewrite or
new choice; a box drawn below = new node. The legend is printed on the page.
Handles are breadth-first from `start`, so the same scene always draws the
same letters.

`map` is the session on one page: a row per week, each scene where it first
plays (talks it opens underneath, repeats listed as "again"), six voice dots
per scene, and every flag as a line from where it is set (●) to where it is
read (▶). A flag nobody reads ends in ○ — a free hook. Draw a line from a
scene to a later week to say "this should matter here".

## Forced choices (an instinct taking over)

`### 1. [Brain 4+] Don't be scared — lead with your policy platform.` marks a
choice that a skill at that level (here Policy Brain 4, "Good") takes out of
the player's hands. No dice. At or above the threshold, that choice is the
only live one: the others stay on screen greyed out and struck through, each
labelled "Policy Brain won't let you", and the forced one reads "your
instinct takes over". Below the threshold it is an ordinary choice. Put the
reply, `effect:` and `then:` under it as usual. At most one forced choice per
node (if two are met, the first in the list wins).

A forced choice may ALSO be a dice check (2026-10-13): write both tags,
`### 1. [Educator 3+] [Educator 12 red] Hand him a fact sheet…`. The skill
forces the ATTEMPT, not the result: the others are greyed out, but the roll
still happens and its odds stay printed on the button.
