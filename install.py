"""
Outliers CRM - Layer 3 - What You Store

Layer 2 gave your records a shape and an identity. It did not fill them in, and
anything you do type into them starts going out of date immediately, on its own,
with nobody touching it.

This layer changes what you store. Instead of descriptions that rot, it stores
events that do not: one line per thing that happened, never edited. Everything
descriptive is then calculated from those events rather than typed.

    python install.py

It finds your CRM, asks two questions, and installs the event log and the
calculations into it.

Nothing here costs money and nothing leaves your computer. No account, no sign-up,
no internet connection required.

Needs: Python 3.8 or newer, and Layer 2 already installed.
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

# The command a member types to start Python: `python3` on a Mac, which has no plain
# `python` command, and `python` everywhere else, as the Windows guides print it.
PY = "python3" if sys.platform == "darwin" else "python"

# The key a member presses. A Mac keyboard's key is Return; Windows keeps Enter, exactly as before
# (Mac build plan V3, wave s1: the Session 7 ruling on the words installers print).
KEY = "Return" if sys.platform == "darwin" else "Enter"

LAYER = 3
LAYER_NAME = "What You Store"
NEEDS_LAYER = 2

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- small helpers

# No colour codes anywhere. Plenty of terminals print them as literal gibberish,
# and a member's first minute with this must not look broken. Plain text works
# everywhere, which is the whole point of the exercise.
BOLD = DIM = OFF = ""


def say(msg=""):
    print(msg, flush=True)


def ask(question, default=None, helptext=None):
    """One plain question. Enter accepts the default."""
    say()
    say(BOLD + question + OFF)
    if helptext:
        say(DIM + "  " + helptext + OFF)
    prompt = "  > " if default is None else "  [%s] > " % default
    try:
        answer = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        say("\nStopped. Nothing was changed.")
        sys.exit(1)
    return answer or (default or "")


def ask_yes(question, default=True):
    d = "Y/n" if default else "y/N"
    a = ask(question, default=d).strip().lower()
    if a in ("y/n", "y/n".upper(), "y", "yes"):
        return True if a != "y/n" else default
    if a in ("n", "no"):
        return False
    return default


def write(path, content):
    """Write a file without ever damaging one that already exists.

    Writes to a temporary file first, then swaps it into place in a single step.
    If anything goes wrong halfway through, the original is untouched. This is a
    habit worth keeping: the notes in here are the record, and there is no copy.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def copy_in(src, dst):
    """Install one file from this repo into the CRM, atomically."""
    write(dst, Path(src).read_text(encoding="utf-8"))



def ensure_gitignore(home, entries):
    """Add lines to the CRM's .gitignore if they are not already there.

    Never rewrites what is in there, only adds. Layer 1 put your records in this
    file so they cannot be published by accident; each layer adds whatever it
    creates that belongs in the same category.
    """
    p = Path(home) / ".gitignore"
    current = p.read_text(encoding="utf-8") if p.exists() else ""
    lines = [ln.strip() for ln in current.splitlines()]
    missing = [e for e in entries if e not in lines]
    if not missing:
        return False
    body = current
    if body and not body.endswith("\n"):
        body += "\n"
    write(p, body + "\n".join(missing) + "\n")
    return True

# ------------------------------------------------------------------ finding the CRM

def looks_like_a_crm(p):
    return (Path(p) / "_layers" / "config.json").exists()


def find_vault():
    # Layer 1 leaves a pointer in the home folder naming wherever the member chose to
    # put their CRM. Checking it first means anyone who declined the default location
    # is not told, wrongly, that they have not done Layer 1 yet.
    pointer = Path.home() / ".outliers-crm"
    guesses = []
    if pointer.exists():
        try:
            noted = pointer.read_text(encoding="utf-8").strip()
            if noted:
                guesses.append(Path(noted))
        except Exception:
            pass
    guesses += [Path.home() / "CRM", Path.cwd(), Path.cwd().parent]
    for g in guesses:
        if looks_like_a_crm(g):
            say()
            say("Found a CRM at: %s" % g)
            if ask_yes("Is that the one?", default=True):
                return Path(g)
            break
    raw = ask("Where is your CRM?",
              default=str(guesses[0]),
              helptext="The folder Layer 1 built. It has a People folder inside it.")
    return Path(raw.strip().strip('"').strip("'")).expanduser()


def previous_layer(home):
    """Return the config from the layer below, or None if this layer cannot run."""
    cfg_path = Path(home) / "_layers" / "config.json"
    if not cfg_path.exists():
        say()
        say("Layer %d needs Layer %d first. Run that one and come back."
            % (LAYER, NEEDS_LAYER))
        say()
        say("  Looked for: %s" % cfg_path)
        say("  Nothing was changed.")
        return None
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except ValueError:
        say()
        say("Layer %d needs Layer %d first. Run that one and come back."
            % (LAYER, NEEDS_LAYER))
        say()
        say("  %s exists but could not be read." % cfg_path)
        return None
    if int(cfg.get("layer", 0)) < NEEDS_LAYER:
        say()
        say("Layer %d needs Layer %d first. Run that one and come back."
            % (LAYER, NEEDS_LAYER))
        say()
        say("  That CRM is on layer %s." % cfg.get("layer"))
        return None
    return cfg


# ---------------------------------------------------------------- the interview

# Words people use for things the base event list already covers. If somebody says
# "a message" there is no point adding a second event type that means the same, so
# this maps the common phrasings onto what already exists.
ALREADY_COVERED = {
    "message_sent": ["message", "messages", "dm", "dms", "email", "emails",
                     "text", "texts", "whatsapp", "sent a message"],
    "reply_received": ["reply", "replies", "response", "they replied"],
    "meeting_held": ["meeting", "meetings", "call", "calls", "zoom",
                     "phone call", "video call", "consultation", "appointment"],
    "call_booked": ["booking", "booked call", "booked", "diary"],
    "comment_made": ["comment", "comments"],
    "connected": ["connection", "connections", "connect", "followed"],
    "joined": ["signed up", "joined", "subscribed", "purchase", "bought"],
}


def tidy(phrase):
    """Drop a leading article, so "a site visit" becomes "site visit"."""
    return re.sub(r"^(a|an|the)\s+", "", str(phrase).strip(), flags=re.I).strip()


def slug_event(phrase):
    s = re.sub(r"[^a-z0-9]+", "_", tidy(phrase).lower()).strip("_")
    return s or "something_happened"


def classify(phrase):
    """Return the existing event type this phrase means, or None if it is new."""
    p = str(phrase).strip().lower()
    for event, words in ALREADY_COVERED.items():
        for w in words:
            if p == w or w in p:
                return event
    return None


def interview(cfg):
    say()
    say(BOLD + "=" * 66 + OFF)
    say(BOLD + "  OUTLIERS CRM   LAYER 3   WHAT YOU STORE" + OFF)
    say(BOLD + "=" * 66 + OFF)
    say()
    say("  There is a difference between a fact and a description.")
    say()
    say("  \"Spoke to her recently\" is a description. It was true when somebody")
    say("  typed it and it started dying the same day, and nothing will tell you")
    say("  when it stops being true.")
    say()
    say("  \"Message sent, 4 June\" is a fact. It is still true in ten years.")
    say()
    say("  This layer stores facts and calculates the descriptions. Two questions.")
    say()
    say(DIM + "  Press %s to accept anything in [brackets]." % KEY + OFF)

    raw = ask("What counts as contact in your business?",
              default="",
              helptext="Separate them with commas. A message, a call and a meeting "
                       "are already covered, so only name anything unusual: a site "
                       "visit, a quote sent, a sample posted, a class attended. " + KEY + " to skip.")

    added, covered = {}, []
    for phrase in [p.strip() for p in raw.split(",") if p.strip()]:
        existing = classify(phrase)
        if existing:
            covered.append((phrase, existing))
            continue
        clean = tidy(phrase)
        added[slug_event(phrase)] = {
            "means": (clean[0].upper() + clean[1:]) if clean else phrase,
            "counts_as_contact": True,
        }

    park = ask("After how long is a quiet conversation dead in your world?",
               default="30",
               helptext="In days. When nothing has happened for this long, the "
                        "system parks the thread on its own, so you never have to "
                        "be the one who decides to give up on it. Thirty days suits "
                        "most people. Long sales cycles want ninety.")
    try:
        park_days = max(1, int(re.sub(r"\D", "", park) or 30))
    except ValueError:
        park_days = 30

    return {
        "added": added,
        "covered": covered,
        "park_days": park_days,
        "people_word": cfg.get("people_word") or "contacts",
    }


# ----------------------------------------------------------------- what we write

def settings_json(answers, existing):
    out = {
        "_comment": [
            "Settings for the calculated fields. You own this file; change a number "
            "and the calculation changes with it.",
            "",
            "park_after_days: how long a thread stays alive with nothing happening "
            "before it parks itself.",
            "refresh_days: how often a person's details are re-checked, by tier. "
            "Active people are re-checked whenever you interact with them, which "
            "costs nothing extra, so their number is zero.",
            "events: your own event types, on top of the built-in list. "
            "counts_as_contact means it moves last-contact and keeps a thread alive.",
        ],
        "park_after_days": answers["park_days"],
        "refresh_days": (existing.get("refresh_days")
                         or {"active": 0, "warm": 30, "cold": 90}),
        "events": dict(existing.get("events") or {}),
    }
    out["events"].update(answers["added"])
    return json.dumps(out, indent=2) + "\n"


def ledger_readme(answers):
    return """# The event log

One line per thing that happened. Never edited, never deleted, only added to.

`events.jsonl` is plain text. Each line is one complete event, so you can open it in
any text editor and read it, and a half-written last line can only ever cost you
that line rather than the file.

## Why nothing in here is ever edited

If the history can be edited, the history can quietly change under you, and you will
have no way of knowing that it has. A correction is a new event, not a rewrite. The
old event stays, because "we thought this happened, then found it had not" is itself
part of the record.

## What a line looks like

    {{"ts": "2026-01-14T09:12:00+00:00", "type": "reply_received",
      "person": "rowan-ashdown", "source": "inbox-export"}}

Four things: when, what kind of thing, who, and where the record came from. The last
one matters more than it looks. A week later, the source is the only thing that
tells a recorded fact apart from something that got in by accident.

## Events with nobody attached

Sometimes an event arrives and nothing can work out who it belongs to. It is still
written, with the raw identifiers kept, and `person` left empty. An event nobody can
attribute is a gap worth investigating, not something to throw away. Discarding
those would make this file look tidier and make every count taken from it wrong.

    {py} _engine/ledger.py stats

tells you how many of those you have.

## Your event types

{types}
"""


def layer_note(answers):
    park = answers["park_days"]
    return """# Layer {n} - {name}

**What it built.** An event log, and the calculations that read it.

**The idea.** A fact and a description are different things. A description states a
condition at the moment somebody wrote it, and it goes wrong on its own afterwards.
An event states that something happened on a date, and that never stops being true.

So the system stores events, and calculates the descriptions.

**What you stop typing.** These fields are now calculated and the contract refuses
them if anything tries to type one by hand:

| Field | Where it comes from |
|---|---|
| `last-contact` | the newest event that counts as contact |
| `conversation-points` | how many messages went each way |
| `relationship-state` | what has happened, and how long ago |
| `refresh-tier` | the state, which decides how often details are re-checked |
| `next-contact-due` | last contact plus the tier's window |
| `last-verified` | the last time a re-check confirmed their role and company |

**How the state is worked out.** A reply or a meeting makes someone active. A
message or a comment from you makes them warming. Silence past {park} days parks the
thread on its own, so nobody has to be the person who decides to give up on it. A
hold beats everything: someone on hold is suppressed regardless of what else
happened.

**Where the files are.**

| File | What it is for |
|---|---|
| `_ledger/events.jsonl` | The log. One line per event. |
| `_engine/ledger.py` | Writes and reads it. Refuses an event type nobody agreed on. |
| `_engine/derive.py` | Calculates every descriptive field from the log. |
| `_engine/settings.json` | Your numbers: the park window, the re-check periods, your own event types. |

Try it:

    {py} _engine/ledger.py types
    {py} _engine/ledger.py stats
    {py} _engine/derive.py quiet 60

**What there is to do now: nothing, honestly.** The calculation is real, but there
are no events to calculate from until something starts recording them, and that is
Layer 4. Anything asked of you today would mean typing events by hand, which is the
admin this whole system exists to avoid.

**What it leaves for Layer 4.** A record of events that nobody is writing. If that
somebody is you, typing, you have reinvented admin, which is the thing that kills
CRMs. Layer 4 fills the log from sources you already own.
""".format(n=LAYER, name=LAYER_NAME, park=park, py=PY)


# ------------------------------------------------------------------------- build

def build(home, answers):
    say()
    say(BOLD + "Installing Layer %d into %s" % (LAYER, home) + OFF)
    say()

    def note(path, what):
        say("  wrote  %-40s %s"
            % (str(Path(path).relative_to(home)).replace("\\", "/"), what))

    engine = home / "_engine"

    for name, what in (("settings.py", "reads your numbers from settings.json"),
                       ("ledger.py", "writes and reads the event log"),
                       ("derive.py", "calculates every descriptive field")):
        p = engine / name
        copy_in(HERE / "crm" / name, p)
        note(p, what)

    existing = {}
    sp = engine / "settings.json"
    if sp.exists():
        try:
            existing = json.loads(sp.read_text(encoding="utf-8"))
        except ValueError:
            existing = {}
    write(sp, settings_json(answers, existing))
    note(sp, "your numbers. yours to edit")

    log = home / "_ledger" / "events.jsonl"
    if log.exists():
        say("  kept   %-40s %s" % ("_ledger/events.jsonl",
                                   "already there, and never overwritten"))
    else:
        write(log, "")
        note(log, "the log itself. empty until Layer 4")

    # what the event vocabulary now looks like, for the log's own README
    sys.path.insert(0, str(engine))
    os.environ["OUTLIERS_CRM_VAULT"] = str(home)
    try:
        import ledger
        known = ledger.types(home)
        contact = ledger.contact_types(home)
    except Exception:
        known, contact = {}, set()
    lines = []
    for k in sorted(known):
        lines.append("- `%s` - %s%s"
                     % (k, known[k], "  (counts as contact)" if k in contact else ""))
    p = home / "_ledger" / "README.md"
    write(p, ledger_readme(answers).format(types="\n".join(lines) or "(none yet)", py=PY))
    note(p, "what the log is and why nothing in it is edited")

    p = home / "_layers" / ("Layer %d - %s.md" % (LAYER, LAYER_NAME))
    write(p, layer_note(answers))
    note(p, "what this layer did, for when you forget")

    if ensure_gitignore(home, ["_ledger/", "__pycache__/", "*.pyc"]):
        say("  added  %-40s keeps your history off any public copy" % (".gitignore",))

    cfg_path = home / "_layers" / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg.update({
        "layer": max(int(cfg.get("layer", 1)), LAYER),
        "park_after_days": answers["park_days"],
        "own_event_types": sorted(answers["added"]),
        "layer_%d_installed" % LAYER: date.today().isoformat(),
    })
    write(cfg_path, json.dumps(cfg, indent=2) + "\n")
    note(cfg_path, "records that Layer %d is in" % LAYER)

    return known, contact


# --------------------------------------------------------------------- now use it

def explain(home, answers, known, contact):
    say()
    say(BOLD + "-" * 66 + OFF)
    say(BOLD + "  What counts as an event" + OFF)
    say(BOLD + "-" * 66 + OFF)
    say()
    say("  The list is small and closed on purpose. Anything not on it is refused.")
    say("  An open list is how a system ends up with six words for one thing and no")
    say("  question that returns the whole answer.")
    say()
    for k in sorted(known):
        say("    %-18s %s%s" % (k, known[k], "  (counts as contact)" if k in contact else ""))
    say()
    if answers["covered"]:
        say("  You named these, and they were already covered:")
        for phrase, event in answers["covered"]:
            say("    %-22s -> %s" % (phrase, event))
        say()
    if answers["added"]:
        say("  You added these:")
        for k, spec in sorted(answers["added"].items()):
            say("    %-22s %s" % (k, spec["means"]))
        say()

    say(BOLD + "-" * 66 + OFF)
    say(BOLD + "  What this will look like on your own data" + OFF)
    say(BOLD + "-" * 66 + OFF)
    say()
    say("  Your log is empty, so the four lines below are INVENTED, purely to show")
    say("  the shape. Rowan Ashdown is not a real person.")
    say()
    say("    2026-01-04  message_sent     rowan-ashdown")
    say("    2026-01-06  reply_received   rowan-ashdown")
    say("    2026-01-09  call_booked      rowan-ashdown")
    say("    2026-01-11  meeting_held     rowan-ashdown")
    say()
    say("  From those four lines, and nothing typed:")
    say()
    say("    last-contact          2026-01-11")
    say("    conversation-points   2")
    say("    relationship-state    active")
    say("    refresh-tier          active")
    say()
    say("  And after %d days with nothing further:" % answers["park_days"])
    say()
    say("    relationship-state    parked")
    say("    parked-reason         %d days since the last contact" % (answers["park_days"] + 1))
    say()
    say("  Nobody decided that. It is a consequence of the dates.")


def finish(home, answers):
    say()
    say(BOLD + "=" * 66 + OFF)
    say(BOLD + "  Done. Your CRM stores facts." + OFF)
    say(BOLD + "=" * 66 + OFF)
    say()
    say("  What changed:")
    say("    - An event log at _ledger/events.jsonl. Append only, never edited.")
    say("    - Six descriptive fields you never type again.")
    say("    - A thread now parks itself after %d quiet days." % answers["park_days"])
    say()
    say("  Read: _layers/Layer %d - %s.md" % (LAYER, LAYER_NAME))
    say()
    say(BOLD + "  What to do now: nothing, honestly." + OFF)
    say("  The calculation is real but there is nothing to calculate from yet, and")
    say("  typing events in by hand would be the admin this whole thing exists to")
    say("  avoid. Layer 4 fills the log from a source you already own, and that is")
    say("  where the CRM starts giving something back.")
    say()


def main():
    say()
    say("  Outliers CRM, Layer %d: %s" % (LAYER, LAYER_NAME))
    home = find_vault()
    cfg = previous_layer(home)
    if cfg is None:
        return 1

    answers = interview(cfg)

    say()
    say("  Installing into:   %s" % home)
    say("  Quiet conversation dies after: %d days" % answers["park_days"])
    say("  Your own event types: %s"
        % (", ".join(sorted(answers["added"])) or "none, the built-in list covers you"))
    if not ask_yes("Go ahead?", default=True):
        say("\nStopped. Nothing was changed.")
        return 1

    known, contact = build(home, answers)
    explain(home, answers, known, contact)
    finish(home, answers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
