# Scene scripts

Every dialogue in the game — weekly events, generic events, talks — is a
`.scene` file here, one per dialogue, named for its id. They compile into
the `dialogues` block of `site/map/session.json`; nothing else in that
file is touched. **Edit these, never the JSON.**

```
python3 tools/scenes.py new w9-thing        # scaffold, with every skill's slot
python3 tools/scenes.py check               # lint everything
python3 tools/scenes.py build               # lint, then write session.json (+ bump its ?v=)
python3 tools/scenes.py tree w9-thing       # decision tree to mark up -> build/tree-w9-thing.svg
python3 tools/scenes.py map                 # whole session + flag lines -> build/session-map.svg
python3 tools/scenes.py stats               # voice balance, checks per skill, flag ledger
```

## The format

```
=== w5-decking                       dialogue id = file name
_note: Free text that ships as _note (any _key: does).
art: w2-finance                      banner, site/assets/events/<art>.png
at: {"island": "hawaii"}             week-beat camera target (JSON)
talks: grange, office, rep-x=talk-rep   doors this scene opens (bare id = talk-<id>)
actions: bench, lobby                   ("push" = the work-the-chair rows)

--- start                            a node; the first one must be start
art: w2-finance-office               node fields go before the text
KAWAGUCHI: "Sit." He doesn't stand.  SPEAKER: on the FIRST line = whole node is theirs
Second paragraph — one paragraph per line.
PROCEDURE: A skill voice. Voices come after the text.
TALK STORY: Another one.

* Bring the fiscal note.             a plain choice
  {+1 influence}                     its effects
  You walk in with one page.         its reply (one paragraph per line)
  POLICY BRAIN: voices can chime in on a reply too
  -> office                          go to a node (no arrow = scene ends)

* [TALK STORY 13 red] "Call him."    a checked choice: skill, DC, red|white
  mods: influence/25, flag kawaguchi-date +2 "the date he gave you", PROCEDURE/3
  {-1 support}                       ANTE: paid on commit, win or lose
  pass:
    He picks up the phone.
    {-2 influence, flag souza-intro}
    -> office
  fail:
    "In my own office?"
    {-4 influence}
```

`//` starts a note to yourself; it never ships.

**Names.** Skills by display name, id, or short alias — `POLICY BRAIN` /
`BRAIN`, `PROCEDURE` / `PROC`, `EDUCATOR` / `EDU`, `TALK STORY` / `TALK`,
`MOBILIZING` / `MOB`, `BASE BUILDING` / `BASE`. Speakers by character id in
caps: `KAWAGUCHI`, `GRANGE`, `YAMAMOTO`, `REP-X`, `SEN-X`. A node with no
speaker is narration — that is how the player's own campaign talks
(faceless, per CLAUDE.md). Souza never speaks.

**Effects**, comma-separated in braces: `+2 support`, `-1 influence`,
`+6 house` / `-3 senate` (introducer rapport), `-$600M revenue` (also `$K`,
`$B`), `flag some-flag`, `+1 TALK STORY` (a skill pip), `unlock talk
grange=talk-grange`, `unlock action bench`. `{}` = nothing happens.

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

- **Inside a scene**: nodes plus `->`. Branches can rejoin (three choices
  all `-> office`). Run `tree` to see it.
- **Across scenes, flags are the only memory.** Set one with
  `{flag name}`; a later scene reads it ONLY as a check mod
  (`flag name +2 "label"`). There is no "show this choice if" — write for
  that. `stats` prints every flag's setters and readers; mind the week
  order (a flag read before it can be set is a bug).
- **Checked choices:** a `->` directly under the choice is where BOTH
  outcomes go. Put one inside `pass:` or `fail:` only when that outcome
  goes somewhere else — it overrides the shared one.
- **White** checks can be retried when the bonus improves; **red** checks
  are one shot. Both outcomes need real content.
- An event's `talks:`/`actions:` decide what the player can do that week;
  a choice can open more with `unlock`. A generic event that opens
  nothing is a dead week.

## Editing by pen (the tablet loop)

`tree` draws a scene as a page to mark up: every node has a letter (A, B…)
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
