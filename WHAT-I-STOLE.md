# What this layer borrows

Nothing in this layer is new. It is a small, plain version of a set of ideas that
banking, accounting and database engineering worked out a long time ago, and it is
worth naming them honestly so you know where to read more.

## Double-entry bookkeeping, and the append-only ledger

The oldest one here. Luca Pacioli wrote down the double-entry method in 1494,
describing practice that Venetian merchants were already using. Its defining
property is not the two columns; it is that entries are never erased. A mistake is
corrected by a new, dated entry that reverses the old one, and both stay on the
page.

That is the whole of `_ledger/events.jsonl`. The reason it is worth copying is not
tradition. It is that a record which can be edited is a record that can quietly
change under you, and you will have no way of knowing that it has.

## Event sourcing

The modern software name for the same idea, popularised by Martin Fowler and Greg
Young in the mid-2000s. Instead of storing the current state of a thing and
overwriting it as it changes, you store the sequence of events that happened, and
you derive the current state by replaying them.

Two consequences this layer relies on:

- **You can ask questions of the past that you did not think of in advance.** If you
  had stored only "state: warm", you could never work out later how long they took
  to reply. If you stored the events, you can.
- **Derivation is repeatable.** Run it twice, get the same answer, because events do
  not change. There is a test for exactly this.

The full pattern usually comes with a second half called CQRS, where reads and
writes use different models. That is deliberately not here. At this scale it is
complexity that buys nothing.

## Materialised views

`derive.py` is a materialised view in the database sense: a query over the log,
whose answer can be stored and recalculated whenever it goes stale. The reason it is
never handwritten is the same reason a database will not let you type a value into a
computed column. A field a person maintains by hand starts lying within weeks, and a
stale value looks exactly like a current one.

## Write-ahead logging

The reason the log is append-only text with one complete record per line, flushed
and synced on write, comes from how databases keep their write-ahead logs. Appending
never truncates what is already there, so the worst a badly timed crash can do is
lose the tail of the last line, rather than the file. And because each line is
independently readable, one damaged line does not make the rest unreadable. There is
a test for that too.

## Newline-delimited JSON

The file format is JSON Lines, sometimes written JSONL or NDJSON. It is not a
standards-body format; it is a convention that became common in logging and data
pipelines because it has two properties nothing else has together: you can append to
it without rewriting it, and you can read it with a text editor.

The alternative would be one big JSON array, which would have to be rewritten in
full on every append. Rewriting the entire history to add one line is exactly the
risk this whole system is built to avoid.

## Closed vocabularies and controlled terms

Restricting event types to a fixed list comes from library and archive cataloguing,
where it is called a controlled vocabulary. The point is not tidiness. It is that if
two words can mean the same thing, some of your records will use one and some the
other, and a query for either returns half the answer. Worse, the most common value
can end up being a word no list recognises, which makes that part of the system
unreachable rather than merely untidy.

The escape hatch matters as much as the rule: you can add your own types, but you
add them once, deliberately, in a settings file, rather than by typing a new word
into a record.

## Ageing and time-based state transitions

Parking a thread after a set period of silence is a state machine with a timeout, a
standard piece of protocol design (TCP has several). The reason it belongs in a CRM
is behavioural rather than technical. Nobody wants to be the person who declares a
conversation dead, so nothing gets declared dead, and a large share of a pipeline
becomes deals nobody is actually working. Making it a consequence of the calendar
takes the decision away from the person who does not want to make it.

## Configuration as data

The settings file is the same idea as the record contract in Layer 2, and it comes
from the same place: twelve-factor app configuration, and before that every
Unix program that read a dotfile. The numbers that govern behaviour live somewhere
you can read and change, not buried in code, so there is one place to look when you
want to know what the system currently believes.
