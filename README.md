**This is the Mac version.** On Windows, use [outliers-crm-03-records](https://github.com/OUTLIERS-ai/outliers-crm-03-records).

# Outliers CRM - Layer 3 - What You Store

Layer 2 gave your records a shape and gave every person one identity. It did not
fill anything in. And whatever you do write down about a person goes out of date on
its own, with nobody touching it and nothing telling you it has happened.

This layer changes what you store.

## The difference between a fact and a description

"Spoke to her recently" is a description. It was true when somebody typed it. It
started dying the same day. Six months later it is actively misleading, and it looks
exactly the same as it did when it was true.

"Message sent, 4 June" is a fact. It is still true in ten years.

A CRM full of descriptions needs constant maintenance to stay honest, and that
maintenance is admin, and admin is what kills CRMs. A CRM full of facts does not.

So: store what happened, calculate the rest.

## Install it

From this folder:

    python3 install.py

It finds your CRM, asks two questions, and installs the event log and the
calculations into it.

If Layer 2 is not installed, this refuses and tells you so. Nothing is changed.

## What it needs beneath it

Layer 2, which needs Layer 1. The installer checks `_layers/config.json` and stops
politely if the layer below is missing.

It also uses Layer 2's identity code: when something records an event it hands over
whatever identifier it happens to have, and Layer 2 is the single thing that decides
which person that is.

## What the installer asks

**What counts as contact in your business?** A message, a call and a meeting are
already covered. What is not covered is whatever is specific to you: a site visit, a
quote sent, a sample posted, a class attended. Anything you name becomes an event
type of its own, and it counts as contact, which means it moves the last-contact
date and keeps a thread alive.

**After how long is a quiet conversation dead in your world?** In days. When nothing
has happened for that long, the system parks the thread on its own. This matters
more than it sounds: without it, threads sit in "active" for a year because nobody
wants to be the person who writes them off, and a quarter of your pipeline becomes
deals nobody is working.

## What gets installed

| File | What it is for |
|---|---|
| `_ledger/events.jsonl` | The log. One line per event, append only. |
| `_ledger/README.md` | What the log is, and why nothing in it is ever edited. |
| `_engine/ledger.py` | Writes and reads the log. Refuses an unknown event type. |
| `_engine/derive.py` | Calculates every descriptive field from the log. |
| `_engine/settings.py` | Reads your numbers from `settings.json`. |
| `_engine/settings.json` | Your numbers. Yours to edit. |
| `_layers/Layer 3 - What You Store.md` | What this layer did, for when you forget. |

## The rules the log follows

**Append only.** Lines are never edited and never deleted. A correction is a new
event, not a rewrite. If history can be edited then history can quietly change under
you, and you will not know that it has.

**One line per event, in plain text.** You can read the file in any text editor. A
half-written last line can only ever cost you that line, not the file.

**The vocabulary is closed.** An event type that is not on the list, and not one you
added, is refused outright. An open vocabulary is how a system ends up with six
words for one thing and no question that returns the whole answer.

**An event nobody can attribute is still recorded.** With the raw identifiers kept
and the person left blank. Dropping those would make the log look tidier and make
every count taken from it wrong.

## What you stop typing

These are all calculated now, and the Layer 2 contract refuses them if anything
tries to type one by hand.

| Field | Where it comes from |
|---|---|
| `last-contact` | the newest event that counts as contact |
| `conversation-points` | how many messages went each way |
| `relationship-state` | what happened, and how long ago |
| `refresh-tier` | the state, which decides how often details are re-checked |
| `next-contact-due` | last contact plus that tier's window |
| `last-verified` | when a re-check last confirmed their role and company |

## How the state is worked out

A hold beats everything: someone you have taken over personally is suppressed
regardless of what else happened.

Otherwise: joining something of yours makes them a client. A reply, a meeting, or a
booking in the diary makes them active. A message or a comment from you makes them
warming. Nothing at all leaves them cold.

Then it ages. Silence past your window parks the thread and records why, and nobody
had to decide anything.

## Try it

In Terminal, from your CRM folder (if your CRM is not at `~/CRM`, put your own folder in the `cd` line):

    cd ~/CRM
    python3 _engine/ledger.py types      the event vocabulary
    python3 _engine/ledger.py stats      how many events, of what kind, from where
    python3 _engine/ledger.py tail 20    the last twenty events
    python3 _engine/derive.py show "a name or link"
    python3 _engine/derive.py quiet 60   who you have not spoken to in 60 days
    python3 _engine/derive.py summary    how many people are in each state

## Run the tests

From the folder you downloaded:

    cd ~/outliers-crm-03-records-mac
    python3 tests/test_ledger_and_derive.py

It builds a scratch folder, writes invented events into it, and deletes it
afterwards. It never touches your records.

## What there is to do now: nothing, honestly

The calculation is real. There is nothing to calculate from yet, because nothing is
writing events, and typing them in by hand would be exactly the admin this system
exists to avoid.

That is Layer 4's job. It points the log at a source you already own, and it fills
itself.

## Requirements

Python 3.8 or newer. Nothing else: no libraries to install, no account, no internet
connection. Runs on macOS and Linux.

This repo is made automatically from outliers-crm-03-records@10de892. To report a problem or suggest a change, use that repo, not this one.
