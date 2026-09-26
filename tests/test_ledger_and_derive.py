"""The record is what happened, and the fields follow from it.

THE RULE (Layer 3): events are what you store. Every descriptive field is calculated
from them and typed by nobody. An event does not go out of date. A description does,
the moment the world moves, and nothing tells you it has.

WHAT SHOULD HAPPEN:
  - appending an event changes the calculated answer
  - calculating twice gives the same answer both times
  - a thread parks itself when it goes quiet, with nobody deciding to give up
  - a fresh reply revives it
  - an event nothing can attribute is still recorded, never dropped
  - the question "who have I not spoken to in 60 days" is answerable from events
  - a stale claim on a record is reported, not silently corrected

Every person in here is invented.

Run:  python tests/test_ledger_and_derive.py
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "crm"))

FAILS = []


def check(label, cond, detail=""):
    ok = bool(cond)
    print(("  PASS  " if ok else "  FAIL  ") + label
          + (("   [" + detail + "]") if detail and not ok else ""))
    if not ok:
        FAILS.append(label)


# A scratch folder. Never point a test at real records.
TMP = Path(tempfile.mkdtemp(prefix="outliers-crm-records-"))
os.environ["OUTLIERS_CRM_VAULT"] = str(TMP)
(TMP / "_engine").mkdir(parents=True)
(TMP / "_engine" / "settings.json").write_text(json.dumps({
    "park_after_days": 30,
    "refresh_days": {"active": 0, "warm": 30, "cold": 90},
    "events": {
        "site_visit": {"means": "you visited their premises", "counts_as_contact": True},
        "quote_sent": {"means": "you sent them a quote", "counts_as_contact": True},
    },
}, indent=2), encoding="utf-8")

import settings                                            # noqa: E402
import ledger                                              # noqa: E402
import derive                                              # noqa: E402

LOG = TMP / "_ledger" / "events.jsonl"


def ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


print("\n=== 1. an event is appended, never overwritten ===")

ledger.emit("connected", person="rowan-ashdown", source="test", ts=ago(40), path=LOG)
ledger.emit("message_sent", person="rowan-ashdown", source="test", ts=ago(38), path=LOG)
first_size = LOG.stat().st_size
ledger.emit("reply_received", person="rowan-ashdown", source="test", ts=ago(37), path=LOG)

check("three events are on file", ledger.count(path=LOG) == 3, str(ledger.count(path=LOG)))
check("the file only ever grew", LOG.stat().st_size > first_size)

print("\n=== 2. the vocabulary is closed ===")

try:
    ledger.emit("had_a_nice_thought", person="rowan-ashdown", path=LOG)
    check("an event type nobody agreed on is refused", False, "it was accepted")
except ValueError as e:
    check("an event type nobody agreed on is refused", True)
    check("and the refusal lists what IS allowed", "message_sent" in str(e), str(e)[:80])

check("your own event types are accepted",
      "site_visit" in ledger.types(), repr(sorted(ledger.types())))
check("and they count as contact if you said they do",
      "site_visit" in ledger.contact_types())
check("an event type that is not contact does not count as contact",
      "details_changed" not in ledger.contact_types())

print("\n=== 3. descriptive fields are calculated, not typed ===")

st = derive.person_state("rowan-ashdown", path=LOG)
check("last contact comes from the newest contact event",
      st.get("last-contact") == ago(37)[:10],
      "%s vs %s" % (st.get("last-contact"), ago(37)[:10]))
check("conversation points count the exchanges",
      st.get("conversation-points") == 2, str(st.get("conversation-points")))
check("a connection on its own is not an exchange",
      st.get("conversation-points") != 3)

print("\n=== 4. the calculation is idempotent ===")

check("calculating twice gives the same answer",
      derive.person_state("rowan-ashdown", path=LOG) == st)

print("\n=== 5. a state ages on its own ===")

check("a thread silent past the window parks itself",
      st.get("relationship-state") == "parked", repr(st.get("relationship-state")))
check("and it says why",
      "days since the last contact" in str(st.get("parked-reason", "")),
      repr(st.get("parked-reason")))

ledger.emit("reply_received", person="rowan-ashdown", source="test", ts=ago(1), path=LOG)
st2 = derive.person_state("rowan-ashdown", path=LOG)
check("a fresh reply revives it", st2.get("relationship-state") == "active",
      repr(st2.get("relationship-state")))
check("and it moves to the active re-check tier",
      st2.get("refresh-tier") == "active", repr(st2.get("refresh-tier")))

print("\n=== 6. one of your own event types moves the same fields ===")

ledger.emit("site_visit", person="mara-quennell", source="test", ts=ago(2), path=LOG)
sv = derive.person_state("mara-quennell", path=LOG)
check("a site visit counts as contact",
      sv.get("last-contact") == ago(2)[:10], repr(sv.get("last-contact")))
check("and it warms the relationship",
      sv.get("relationship-state") in ("warming", "active"),
      repr(sv.get("relationship-state")))

print("\n=== 7. a hold suppresses, a release restores ===")

ledger.emit("message_sent", person="tobias-fenwick", source="test", ts=ago(6), path=LOG)
ledger.emit("held", person="tobias-fenwick", source="test", ts=ago(5), path=LOG)
check("a held person is suppressed",
      derive.person_state("tobias-fenwick", path=LOG).get("relationship-state") == "suppressed")
ledger.emit("released", person="tobias-fenwick", source="test", ts=ago(1), path=LOG)
check("a released person is no longer suppressed",
      derive.person_state("tobias-fenwick", path=LOG).get("relationship-state") != "suppressed")

print("\n=== 8. no events means unobserved, not cold ===")

check("a person with no events yields no calculated state",
      derive.person_state("nobody-at-all", path=LOG) == {})

print("\n=== 9. an event nothing can attribute is recorded, never dropped ===")

ev = ledger.emit("reply_received", person=None, source="test",
                 identifiers=["someone@nowhere.example"], path=LOG)
check("it is written", ev["person"] is None and ev["identifiers"] == ["someone@nowhere.example"])
unattached = [e for e in ledger.events(path=LOG) if not e.get("person")]
check("and it can be found again to investigate", len(unattached) == 1, str(len(unattached)))

print("\n=== 10. a corrupt line does not destroy the history ===")

with open(LOG, "a", encoding="utf-8") as fh:
    fh.write("{ this is not readable\n")
ledger.emit("message_sent", person="rowan-ashdown", source="test", path=LOG)
check("events after a bad line are still read",
      ledger.count(person="rowan-ashdown", path=LOG) >= 5,
      str(ledger.count(person="rowan-ashdown", path=LOG)))

print("\n=== 11. the question a hand-kept CRM cannot answer ===")

ledger.emit("message_sent", person="delia-marchetti", source="test", ts=ago(200), path=LOG)
quiet = derive.quiet_for(60, path=LOG)
names = [r["person"] for r in quiet]
check("someone last spoken to 200 days ago is on the list",
      "delia-marchetti" in names, str(names))
check("someone spoken to today is not", "rowan-ashdown" not in names, str(names))
check("the longest silence sorts first",
      names and names[0] == "delia-marchetti", str(names))
check("every row carries how it got there",
      all(r.get("last-contact") and r.get("relationship-state") for r in quiet))
check("a shorter window returns at least as many people",
      len(derive.quiet_for(10, path=LOG)) >= len(quiet))

print("\n=== 12. drift is reported, not silently corrected ===")

d = derive.drift("rowan-ashdown",
                 {"relationship-state": "cold", "last-contact": "2020-01-01"}, path=LOG)
check("a stale claim on the record is surfaced",
      "relationship-state" in d and "last-contact" in d, repr(d))
check("the claim and the truth are both shown",
      d["relationship-state"][0] == "cold" and d["relationship-state"][1] == "active",
      repr(d["relationship-state"]))
check("asking the question changed nothing",
      derive.person_state("rowan-ashdown", path=LOG).get("relationship-state") == "active")

print("\n=== 13. your settings are what the calculation uses ===")

s = settings.load()
check("the park window is read from your settings", s["park_after_days"] == 30)
check("defaults fill in anything your file does not say",
      set(s["refresh_days"]) == {"active", "warm", "cold"}, repr(s["refresh_days"]))

print("\n=== 14. the log is plain text, one line per event ===")

lines = [l for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
readable = [l for l in lines if l.startswith("{") and l.rstrip().endswith("}")]
check("every line except the deliberately broken one is a complete record",
      len(readable) == len(lines) - 1, "%d of %d" % (len(readable), len(lines)))

shutil.rmtree(TMP, ignore_errors=True)

print("\n%s" % ("ALL PASS" if not FAILS else "FAILURES: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
