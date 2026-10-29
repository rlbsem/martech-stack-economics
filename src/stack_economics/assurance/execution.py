"""Bounded durable execution of the existing fixture's selected batch routes."""
import json
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from stack_economics.contracts import digest

from .storage import database, encode, event, rows, verify_authorized


def profile(**changes):
    value = {"window_seconds": 36.0, "workers": 8, "timeout_seconds": 1.0, "max_attempts": 3,
             "retry_seconds": 0.025, "delay_seconds": 0.0003, "ack_delay_seconds": 1.4,
             "faults": [], "capacity_override": {}, "source_delay": {}, "permission": True,
             "recovery_probe_cents": 1}
    if set(changes) - set(value):
        raise ValueError('Unknown execution profile field')
    value.update(changes)
    if (not 0.1 <= value["window_seconds"] <= 60 or not 1 <= value["workers"] <= 16
            or not 1 <= value["max_attempts"] <= 5 or not 0.05 <= value["timeout_seconds"] <= 2
            or not 0 <= value["delay_seconds"] <= 0.01 or not 0 <= value["retry_seconds"] <= 0.1
            or value["recovery_probe_cents"] != 1):
        raise ValueError("Unsupported finite execution profile")
    return value


class Services:
    def __init__(self, directory, spec, runtime, run):
        self.directory, self.spec, self.runtime, self.run = Path(directory), spec, runtime, run
        self.processes, self.urls, self.configs = [], {}, {}

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.epoch_ns = time.time_ns() + 3_000_000_000
        scenario = self.spec["scenarios"][0]
        try:
            for resource in self.spec["resources"]:
                name = resource["id"]
                cap = scenario["capacities"][name]
                if len(set(cap["per_slot"])) != 1:
                    raise ValueError("Local receiver supports constant per-slot capacity only")
                config = {"run": self.run, "resource": name, "epoch_ns": self.epoch_ns,
                          "window_ns": int(self.runtime["window_seconds"] * 1e9), "slots": self.spec["slots"],
                          "per_slot": self.runtime["capacity_override"].get(name, cap["per_slot"][0]),
                          "total": cap["total"], "workflows": [w["id"] for w in self.spec["workloads"]],
                          **{k: self.runtime[k] for k in ("faults", "permission", "delay_seconds", "ack_delay_seconds")}}
                self.configs[name] = config
                config_path, ready = self.directory / (name + '.json'), self.directory / (name + '.ready')
                config_path.write_text(encode(config), encoding="utf-8")
                log = (self.directory / (name + '.log')).open("wb")
                try:
                    process = subprocess.Popen([sys.executable, "-m", "stack_economics.assurance.service",
                                                "--database", str(self.directory / (name + '.sqlite')),
                                                "--config", str(config_path), "--ready", str(ready)],
                                               stdout=log, stderr=log)
                finally:
                    log.close()
                self.processes.append(process)
                deadline = time.monotonic() + 10
                while not ready.exists():
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("Receiver startup failed: " + name)
                    time.sleep(0.02)
                self.urls[name] = json.loads(ready.read_text())["url"]
            if time.time_ns() >= self.epoch_ns:
                raise RuntimeError("Receiver startup consumed execution clock; no workload launched")
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
        for process in self.processes:
            process.wait(timeout=10)

    def snapshot(self):
        # Wait for all bounded delayed acknowledgements before reading independent storage.
        time.sleep(self.runtime["ack_delay_seconds"] + 0.05)
        return {name: {"config": config, **{table: rows(self.directory / (name + '.sqlite'), table)
                                           for table in ("requests", "receipts", "records")}}
                for name, config in self.configs.items()}


def request(url, method, body, timeout):
    opener = build_opener(ProxyHandler({}))  # No environment proxy or credential propagation on loopback.
    data = encode(body).encode() if body is not None else None
    try:
        with opener.open(Request(url, data=data, method=method, headers={"Content-Type": "application/json"}),
                         timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())
    except (TimeoutError, URLError, ConnectionError, json.JSONDecodeError):
        return None, None


def receipt_matches(receipt, body, resource):
    return (isinstance(receipt, dict) and receipt.get("key") == body["key"]
            and receipt.get("body_hash") == digest(body) and receipt.get("count") == len(body["records"])
            and receipt.get("resource") == resource and type(receipt.get("committed_ns")) is int)


def process_batch(control, key, option, urls, runtime, crash_after=None):
    with database(control) as db:
        batch = dict(db.execute("SELECT * FROM batches WHERE key=?", (key,)).fetchone())
        if batch["state"] == "confirmed":
            return
        db.execute("UPDATE batches SET state='running' WHERE key=?", (key,))
    body = json.loads(batch["payload"])
    event(control, key, "dequeued", {})
    for resource in sorted(option["resources"], key=lambda r: (r == 'destination-api', r)):
        units = option["resources"][resource]
        if units != 1:
            raise ValueError("Local contract supports one resource request per batch")
        with database(control) as db:
            db.execute("INSERT OR IGNORE INTO calls VALUES(?,?,?,'planned',0,NULL)", (key, resource, digest(body)))
        while True:
            with database(control) as db:
                call = dict(db.execute("SELECT * FROM calls WHERE key=? AND resource=?", (key, resource)).fetchone())
            if call["body_hash"] != digest(body):
                raise ValueError("Immutable call content changed")
            if call["state"] == "confirmed":
                break
            # Historical receipt reconciliation remains permitted after the deadline or revocation.
            if call["state"] in ("dispatching", "uncertain"):
                status, receipt = request(urls[resource] + '/receipts/' + key, "GET", None,
                                          runtime["timeout_seconds"])
                event(control, key, "probe", {"resource": resource, "status": status})
                if status == 200:
                    if not receipt_matches(receipt, body, resource):
                        event(control, key, "receipt_conflict", {"resource": resource})
                        return finish(control, key, "blocked")
                    with database(control) as db:
                        db.execute("UPDATE calls SET state='confirmed',receipt=? WHERE key=? AND resource=?",
                                   (encode(receipt), key, resource))
                    break
                if status != 404:
                    return finish(control, key, "unresolved")
            if (time.time_ns() >= batch["deadline_ns"] or call["attempts"] >= runtime["max_attempts"]):
                return finish(control, key, "expired" if time.time_ns() >= batch["deadline_ns"] else "exhausted")
            with database(control) as db:
                db.execute("UPDATE calls SET state='dispatching',attempts=attempts+1 WHERE key=? AND resource=?",
                           (key, resource))
            status, receipt = request(urls[resource] + '/batches', "POST", body, runtime["timeout_seconds"])
            event(control, key, "post", {"resource": resource, "status": status})
            if crash_after == resource:
                import os
                os._exit(17)  # Test-only actual process loss after remote effect and before local confirmation.
            if status == 200:
                if not receipt_matches(receipt, body, resource):
                    return finish(control, key, "blocked")
                with database(control) as db:
                    db.execute("UPDATE calls SET state='confirmed',receipt=? WHERE key=? AND resource=?",
                               (encode(receipt), key, resource))
                break
            with database(control) as db:
                db.execute("UPDATE calls SET state=? WHERE key=? AND resource=?",
                           ("uncertain" if status is None else "planned", key, resource))
            if status not in (None, 429, 503):
                return finish(control, key, "blocked")
            time.sleep(runtime["retry_seconds"])
    finish(control, key, "confirmed")


def finish(control, key, state):
    with database(control) as db:
        db.execute("UPDATE batches SET state=? WHERE key=?", (state, key))
    event(control, key, "finished", {"state": state})


def execute(control, spec, plan, scenario_id, runtime, services, ledger, decision):
    verify_authorized(ledger, decision, spec, plan, runtime, services.run, scenario_id)
    if plan["status"] != "optimal":
        raise ValueError("Only verified feasible plans can execute")
    scenario = next(s for s in spec["scenarios"] if s["id"] == scenario_id)
    options = {w["id"]: next(o for o in w["options"] if o["id"] == plan["selection"][w["id"]])
               for w in spec["workloads"]}
    if sum(sum(v) for v in scenario["demands"].values()) > 100_000:
        raise ValueError("Local execution record bound exceeded")
    with closing(sqlite3.connect(control)), ThreadPoolExecutor(max_workers=runtime["workers"]) as pool:
        for slot in range(spec["slots"]):
            due = services.epoch_ns + slot * int(runtime["window_seconds"] * 1e9)
            time.sleep(max(0, (due - time.time_ns()) / 1e9))
            jobs = []
            for work in spec["workloads"]:
                name, option = work["id"], options[work["id"]]
                count = scenario["demands"][name][slot]
                created = time.time_ns()
                delay = runtime["source_delay"].get(name, 0)
                deadline = created + int(work["max_lag_minutes"] / spec["slot_minutes"]
                                         * runtime["window_seconds"] * 1e9)
                for index, offset in enumerate(range(0, count, option["batch_size"])):
                    key = f"{services.run}:{name}:{slot}:{index}"
                    records = [{"id": f"{name}:{slot}:{i}", "operation": "delete" if i % 11 == 0 else "upsert",
                                "fields": {"workflow": name, "synthetic": True, "revision": 1,
                                           "custom_segment": "enterprise" if i % 2 else "mid-market"}}
                               for i in range(offset, min(count, offset + option["batch_size"]))]
                    body = {"key": key, "workflow": name, "slot": slot, "records": records,
                            "batch_size": option["batch_size"]}
                    with database(control) as db:
                        db.execute("INSERT INTO batches(key,workflow,slot,payload,created_ns,ready_ns,deadline_ns) "
                                   "VALUES(?,?,?,?,?,?,?)", (key, name, slot, encode(body), created,
                                                            created + int(delay * 1e9), deadline))
                    event(control, key, "queued", {"records": len(records)})
                    jobs.append((key, option, created + int(delay * 1e9)))
            # Interleave the competing owners rather than always draining one workflow first.
            jobs.sort(key=lambda j: (int(j[0].rsplit(':', 1)[1]), j[0]))

            def run_job(job):
                key, option, ready = job
                time.sleep(max(0, (ready - time.time_ns()) / 1e9))
                process_batch(control, key, option, services.urls, runtime)

            futures = [pool.submit(run_job, job) for job in jobs]
            for future in futures:
                future.result()
    return {table: rows(control, table) for table in ("batches", "calls", "events")}
