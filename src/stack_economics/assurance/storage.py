"""Small durable intent queue and append-only architecture decision ledger."""
import json
import sqlite3
import time
from contextlib import contextmanager

from stack_economics.contracts import digest


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@contextmanager
def database(path):
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA synchronous=FULL")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize(path):
    with database(path) as db:
        db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS decisions(
          id TEXT PRIMARY KEY, parent TEXT REFERENCES decisions(id), document TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS transitions(
          sequence INTEGER PRIMARY KEY, decision TEXT REFERENCES decisions(id),
          state TEXT NOT NULL, actor TEXT NOT NULL, at_ns INTEGER NOT NULL, detail TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS immutable_decision_update BEFORE UPDATE ON decisions
          BEGIN SELECT RAISE(ABORT,'immutable decision'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_decision_delete BEFORE DELETE ON decisions
          BEGIN SELECT RAISE(ABORT,'immutable decision'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_transition_update BEFORE UPDATE ON transitions
          BEGIN SELECT RAISE(ABORT,'immutable transition'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_transition_delete BEFORE DELETE ON transitions
          BEGIN SELECT RAISE(ABORT,'immutable transition'); END;
        CREATE TABLE IF NOT EXISTS batches(
          key TEXT PRIMARY KEY, workflow TEXT NOT NULL, slot INTEGER NOT NULL, payload TEXT NOT NULL,
          created_ns INTEGER NOT NULL, ready_ns INTEGER NOT NULL, deadline_ns INTEGER NOT NULL,
          state TEXT NOT NULL DEFAULT 'queued');
        CREATE TABLE IF NOT EXISTS calls(
          key TEXT NOT NULL, resource TEXT NOT NULL, body_hash TEXT NOT NULL, state TEXT NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0, receipt TEXT,
          PRIMARY KEY(key,resource));
        CREATE TABLE IF NOT EXISTS events(
          sequence INTEGER PRIMARY KEY, at_ns INTEGER NOT NULL, key TEXT, kind TEXT, detail TEXT);
        """)


def propose(path, spec, plan, profile, parent=None, context=None):
    if parent:
        with database(path) as db:
            previous = db.execute("SELECT document FROM decisions WHERE id=?", (parent,)).fetchone()
        if not previous:
            raise ValueError("Unknown parent decision")
        original = json.loads(previous[0])["spec"]
        # Capacity/pricing observations may change; semantic/budget requirements cannot silently weaken.
        for field in ("currency", "workloads", "platforms", "budget_cents", "slots", "slot_minutes", "resources"):
            if spec[field] != original[field]:
                raise ValueError("Revision changes protected requirements: " + field)
        if [s["demands"] for s in spec["scenarios"]] != [s["demands"] for s in original["scenarios"]]:
            raise ValueError("Revision changes demand")
    document = {"spec": spec, "plan": plan, "profile": profile, "parent": parent, "context": context}
    identifier = digest(document)
    with database(path) as db:
        db.execute("INSERT INTO decisions VALUES(?,?,?)", (identifier, parent, encode(document)))
    transition(path, identifier, "proposed", "fixture-planner", {"content_hash": identifier})
    return identifier


def transition(path, decision, state, actor, detail):
    allowed = {None: {"proposed"}, "proposed": {"validated", "blocked"},
               "validated": {"authorized"}, "authorized": {"observed"},
               "observed": {"acceptable", "revision_required"}}
    with database(path) as db:
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute("SELECT state FROM transitions WHERE decision=? ORDER BY sequence DESC LIMIT 1",
                           (decision,)).fetchone()
        if state not in allowed.get(prior[0] if prior else None, set()):
            raise ValueError("Invalid architecture transition")
        db.execute("INSERT INTO transitions(decision,state,actor,at_ns,detail) VALUES(?,?,?,?,?)",
                   (decision, state, actor, time.time_ns(), encode(detail)))


def authorize(path, decision, profile, actor="synthetic-operator"):
    from stack_economics.planner import check_plan
    with database(path) as db:
        row = db.execute("SELECT document FROM decisions WHERE id=?", (decision,)).fetchone()
    if not row or digest(json.loads(row[0])["profile"]) != digest(profile):
        raise ValueError("Execution profile differs from immutable decision")
    document = json.loads(row[0])
    check_plan(document["spec"], document["plan"])
    transition(path, decision, "authorized", actor, {"profile_hash": digest(profile)})


def verify_authorized(path, decision, spec, plan, profile, run, scenario):
    from stack_economics.planner import check_plan
    with database(path) as db:
        row = db.execute("SELECT document FROM decisions WHERE id=?", (decision,)).fetchone()
        state = db.execute("SELECT state FROM transitions WHERE decision=? ORDER BY sequence DESC LIMIT 1",
                           (decision,)).fetchone()
    if not row or not state or state[0] != 'authorized':
        raise ValueError('No current authorized decision')
    document = json.loads(row[0])
    if (digest(document) != decision or document['spec'] != spec or document['plan'] != plan
            or document['profile'] != profile or document['context'] != {'run': run, 'scenario': scenario}):
        raise ValueError('Authorized execution content differs')
    check_plan(spec, plan)


def event(path, key, kind, detail):
    with database(path) as db:
        db.execute("INSERT INTO events(at_ns,key,kind,detail) VALUES(?,?,?,?)",
                   (time.time_ns(), key, kind, encode(detail)))


def rows(path, table):
    if table not in {"decisions", "transitions", "batches", "calls", "events", "requests", "receipts", "records"}:
        raise ValueError("Unknown evidence table")
    with database(path) as db:
        return [dict(row) for row in db.execute("SELECT * FROM " + table)]
