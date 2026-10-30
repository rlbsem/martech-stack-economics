"""Independent loopback HTTP contract emulator, with its own durable receiver journal.

No vendor API is impersonated. Every arrival, including probes and rejections, consumes
an observable request; admission capacity is distinct from attempted traffic.
"""
import argparse
import json
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from stack_economics.contracts import digest

from .storage import database, encode


def initialize_receiver(path):
    with database(path) as db:
        db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE requests(sequence INTEGER PRIMARY KEY, arrived_ns INTEGER, slot INTEGER,
          method TEXT, key TEXT, body_hash TEXT, status INTEGER, admitted INTEGER, size INTEGER);
        CREATE TABLE receipts(key TEXT PRIMARY KEY, body_hash TEXT, committed_ns INTEGER, receipt TEXT);
        CREATE TABLE records(id TEXT PRIMARY KEY, content TEXT);
        """)


def serve(path, config, ready):
    initialize_receiver(path)
    keeper = sqlite3.connect(path)  # Keep the WAL open across requests; commits remain synchronous=FULL.
    lock = threading.Lock()
    faults_used = set()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, *args):
            pass

        def respond(self, status, value):
            body = encode(value).encode()
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # Lost acknowledgement is recorded at commit, not invented as a failed effect.

        def do_GET(self):
            if not self.path.startswith("/receipts/"):
                return self.respond(404, {"error": "route"})
            self.process("GET", self.path[len("/receipts/"):], None)

        def do_POST(self):
            if self.path != "/batches":
                return self.respond(404, {"error": "route"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 2_000_000:
                    raise ValueError("length")
                body = json.loads(self.rfile.read(length))
                if (set(body) != {"key", "workflow", "slot", "records", "batch_size"}
                        or body["workflow"] not in config["workflows"]
                        or not isinstance(body["records"], list) or not body["records"]
                        or len(body["records"]) > body["batch_size"]
                        or body["batch_size"] not in (100, 250, 1000)
                        or not body["key"].startswith(config["run"] + ":")):
                    raise ValueError("contract")
                for record in body["records"]:
                    if (set(record) != {"id", "operation", "fields"}
                            or record["operation"] not in ("upsert", "delete")
                            or not record["id"].startswith(body["workflow"] + ":")):
                        raise ValueError("record contract")
            except (ValueError, TypeError, KeyError):
                return self.respond(400, {"error": "contract"})
            self.process("POST", body["key"], body)

        def process(self, method, key, body):
            arrived = time.time_ns()
            slot = (arrived - config["epoch_ns"]) // config["window_ns"]
            body_hash = digest(body) if body else ""
            status, admitted, response = 200, 0, {}
            fault = None
            with lock, database(path) as db:
                db.execute("BEGIN IMMEDIATE")
                used = db.execute("SELECT count(*) FROM requests WHERE admitted=1 AND slot=?", (slot,)).fetchone()[0]
                total = db.execute("SELECT count(*) FROM requests WHERE admitted=1").fetchone()[0]
                if (not 0 <= slot < config["slots"] or used >= config["per_slot"] or total >= config["total"]):
                    status, response = 429, {"error": "arrival_capacity"}
                else:
                    admitted = 1
                    for index, candidate in enumerate(config["faults"]):
                        if (method == "POST" and index not in faults_used
                                and candidate["resource"] == config["resource"]
                                and candidate.get("workflow", body["workflow"]) == body["workflow"]):
                            faults_used.add(index)
                            fault = candidate
                            break
                    if fault and fault["kind"] in ("429", "503"):
                        status, response = int(fault["kind"]), {"error": "injected_transient"}
                    elif method == "POST" and not config["permission"]:
                        status, response = 403, {"error": "fixture_permission_revoked"}
                    else:
                        prior = db.execute("SELECT * FROM receipts WHERE key=?", (key,)).fetchone()
                        if method == "GET":
                            status, response = (200, json.loads(prior["receipt"])) if prior else (404, {"error": "absent"})
                        elif prior:
                            status, response = ((200, json.loads(prior["receipt"])) if prior["body_hash"] == body_hash
                                                else (409, {"error": "content_conflict"}))
                        else:
                            delay = config["delay_seconds"] * (1 + len(body["records"]) % 3)
                            if fault and fault["kind"] == "latency":
                                delay += fault["seconds"]
                            # Independent service processing occurs before committing, including late effects.
                            time.sleep(delay)
                            committed = time.time_ns()
                            if config["resource"] == "destination-api":
                                for record in body["records"]:
                                    if record["operation"] == "delete":
                                        # Seed then delete proves deletion semantics instead of deleting absent rows.
                                        db.execute("INSERT OR IGNORE INTO records VALUES(?,?)", (record["id"], '{}'))
                                        db.execute("DELETE FROM records WHERE id=?", (record["id"],))
                                    else:
                                        db.execute("INSERT OR REPLACE INTO records VALUES(?,?)",
                                                   (record["id"], encode(record["fields"])))
                            response = {"key": key, "body_hash": body_hash, "count": len(body["records"]),
                                        "committed_ns": committed, "resource": config["resource"]}
                            db.execute("INSERT INTO receipts VALUES(?,?,?,?)",
                                       (key, body_hash, committed, encode(response)))
                db.execute("INSERT INTO requests(arrived_ns,slot,method,key,body_hash,status,admitted,size) "
                           "VALUES(?,?,?,?,?,?,?,?)", (arrived, slot, method, key, body_hash, status, admitted,
                                                     len(body["records"]) if body else 0))
            if fault and fault["kind"] == "lost_ack":
                time.sleep(config["ack_delay_seconds"])
            self.respond(status, response)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = False
    Path(ready).write_text(encode({"url": f"http://127.0.0.1:{server.server_port}"}), encoding="utf-8")
    try:
        server.serve_forever(poll_interval=0.05)
    finally:
        keeper.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--ready", required=True)
    args = parser.parse_args()
    serve(args.database, json.loads(Path(args.config).read_text()), args.ready)
