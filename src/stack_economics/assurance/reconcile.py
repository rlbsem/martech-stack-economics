"""Independent observer: no solver compiler, accounting helper, or execution imports.

Receiver records and intent state are inspected separately. Monetary amounts below
are fixture-defined synthetic prices, never cloud expenditure or realized savings.
"""
import json
import math
from collections import Counter

from stack_economics.contracts import digest


def reconcile(evidence):
    spec, plan, runtime = evidence["spec"], evidence["plan"], evidence["profile"]
    scenario = next(s for s in spec["scenarios"] if s["id"] == evidence["scenario"])
    options = {w["id"]: next(o for o in w["options"] if o["id"] == plan["selection"][w["id"]])
               for w in spec["workloads"]}
    workflows = {w["id"]: w for w in spec["workloads"]}
    violations, warnings = [], []
    expected = sum(sum(v) for v in scenario["demands"].values())
    fixed = sum(p["fixed_cost_cents"] for p in spec["platforms"]
                if p["id"] in {o["platform"] for o in options.values()})
    predicted_requests = Counter()
    predicted_cost = fixed
    predicted_batches = {}
    for name, option in options.items():
        batches = [math.ceil(n / option["batch_size"]) for n in scenario["demands"][name]]
        predicted_batches[name] = batches
        predicted_cost += sum(batches) * option["cost_per_batch_cents"]
        for resource, units in option["resources"].items():
            predicted_requests[resource] += sum(batches) * units
    batches = {b["key"]: b for b in evidence["control"]["batches"]}
    if len(batches) != len(evidence["control"]["batches"]):
        violations.append("duplicate_control_key")
    sources, keys = {}, set()
    for name, counts in predicted_batches.items():
        for slot, count in enumerate(counts):
            for index in range(count):
                keys.add(f"{evidence['run']}:{name}:{slot}:{index}")
    if keys != set(batches):
        violations.append("source_batch_coverage")
    for key, batch in batches.items():
        body = json.loads(batch["payload"])
        name = batch["workflow"]
        option = options[name]
        if (body["key"] != key or body["workflow"] != name or body["slot"] != batch["slot"]
                or body["batch_size"] != option["batch_size"]
                or not 0 < len(body["records"]) <= option["batch_size"]):
            violations.append("source_batch_contract")
        deadline = batch["created_ns"] + int(workflows[name]["max_lag_minutes"] / spec["slot_minutes"]
                                             * runtime["window_seconds"] * 1e9)
        if deadline != batch["deadline_ns"] or batch["ready_ns"] < batch["created_ns"]:
            violations.append("source_clock_contract")
        for record in body["records"]:
            if record["id"] in sources:
                violations.append("duplicate_source_identity")
            sources[record["id"]] = record
    expected_ids = {f"{name}:{slot}:{index}" for name, values in scenario["demands"].items()
                    for slot, count in enumerate(values) for index in range(count)}
    if set(sources) != expected_ids:
        violations.append("source_record_coverage")
    actual_cost, request_totals, capacities, failures = fixed, {}, [], {}
    client_requests = Counter((e['key'], json.loads(e['detail'])['resource'],
                               'POST' if e['kind'] == 'post' else 'GET')
                              for e in evidence['control']['events'] if e['kind'] in ('post', 'probe'))
    receiver_requests = Counter()
    receipts_by_resource = {}
    for resource in sorted(evidence["receivers"]):
        receiver = evidence["receivers"][resource]
        config = receiver["config"]
        assumed = scenario["capacities"][resource]
        if (config["resource"] != resource or config["run"] != evidence["run"]
                or config["epoch_ns"] != evidence["epoch_ns"]
                or config["window_ns"] != int(runtime["window_seconds"] * 1e9)
                or config["slots"] != spec["slots"] or config["total"] != assumed["total"]
                or config["per_slot"] != runtime["capacity_override"].get(resource, assumed["per_slot"][0])
                or any(config[k] != runtime[k] for k in ("faults", "permission", "delay_seconds", "ack_delay_seconds"))):
            violations.append("receiver_configuration_binding")
        requests = receiver["requests"]
        if len({r["sequence"] for r in requests}) != len(requests):
            violations.append("receiver_journal_identity")
        admitted = Counter()
        arrivals = Counter()
        fail = Counter()
        for request in requests:
            receiver_requests[(request['key'], resource, request['method'])] += 1
            slot = (request["arrived_ns"] - config["epoch_ns"]) // config["window_ns"]
            arrivals[slot] += 1
            if slot != request["slot"] or request["key"] not in batches:
                violations.append("receiver_journal_contract")
                continue
            body = json.loads(batches[request["key"]]["payload"])
            if request["method"] == "POST":
                if (request["body_hash"] != digest(body) or request["size"] != len(body["records"])
                        or resource not in options[body["workflow"]]["resources"]):
                    violations.append("receiver_content_contract")
                if resource == "destination-api":
                    actual_cost += options[body["workflow"]]["cost_per_batch_cents"]
            elif request["method"] == "GET":
                actual_cost += runtime["recovery_probe_cents"]
            else:
                violations.append("receiver_method_contract")
            admitted[slot] += request["admitted"]
            if request["status"] >= 400:
                fail[str(request["status"])] += 1
        for slot, count in admitted.items():
            if count > config["per_slot"] or (count and not 0 <= slot < spec["slots"]):
                violations.append("receiver_admission_quota")
        if sum(admitted.values()) > config["total"]:
            violations.append("receiver_total_quota")
        request_totals[resource] = len(requests)
        failures[resource] = dict(fail)
        capacities.append({"resource": resource, "predicted_requests": predicted_requests[resource],
                           "actual_arrivals": len(requests), "admitted": sum(admitted.values()),
                           "max_arrivals_per_window": max(arrivals.values(), default=0),
                           "arrival_windows_over_capacity": sum(v > config["per_slot"] for v in arrivals.values()),
                           "per_window_limit": config["per_slot"], "horizon_limit": config["total"],
                           "windows": [{"slot": s, "arrivals": arrivals[s], "admitted": admitted[s]}
                                       for s in sorted(arrivals)]})
        receipts = {r["key"]: r for r in receiver["receipts"]}
        if len(receipts) != len(receiver["receipts"]):
            violations.append("duplicate_effect")
        for key, row in receipts.items():
            if key not in batches:
                violations.append("unsourced_receipt")
                continue
            body = json.loads(batches[key]["payload"])
            receipt = json.loads(row["receipt"])
            expected_receipt = {"key": key, "body_hash": digest(body), "count": len(body["records"]),
                                "committed_ns": row["committed_ns"], "resource": resource}
            if row["body_hash"] != digest(body) or receipt != expected_receipt:
                violations.append("receipt_content_conflict")
            commits = [r for r in requests if r["key"] == key and r["method"] == "POST" and r["status"] == 200]
            if not commits or row["committed_ns"] < min(r["arrived_ns"] for r in commits):
                violations.append("receipt_without_observed_commit")
        receipts_by_resource[resource] = receipts
    if set(receipts_by_resource) != {r["id"] for r in spec["resources"]}:
        violations.append("missing_receiver")
    if client_requests != receiver_requests:
        violations.append("client_receiver_request_disagreement")
    for call in evidence['control']['calls']:
        if call['attempts'] != client_requests[(call['key'], call['resource'], 'POST')]:
            violations.append('durable_attempt_disagreement')
    successful, late, unresolved = 0, 0, 0
    freshness, queue_delays = [], []
    expected_records = {}
    per_workflow = {name: {"source_records": sum(scenario["demands"][name]), "committed_records": 0,
                           "on_time_records": 0} for name in workflows}
    for key, batch in batches.items():
        body = json.loads(batch["payload"])
        size, name = len(body["records"]), batch["workflow"]
        complete = all(key in receipts_by_resource.get(r, {}) for r in options[name]["resources"])
        destination = receipts_by_resource.get("destination-api", {}).get(key)
        if destination:
            per_workflow[name]["committed_records"] += size
            for record in body["records"]:
                if record["operation"] == "upsert":
                    expected_records[record["id"]] = record["fields"]
            latency = (destination["committed_ns"] - batch["created_ns"]) / 1e9
            freshness.append(latency)
            if destination["committed_ns"] > batch["deadline_ns"]:
                late += size
            elif complete:
                successful += size
                per_workflow[name]["on_time_records"] += size
        if not complete or batch["state"] != "confirmed":
            unresolved += size
        if batch["state"] == "confirmed" and not complete:
            violations.append("false_local_confirmation")
        for resource in options[name]["resources"]:
            posts = [r for r in evidence["receivers"][resource]["requests"]
                     if r["key"] == key and r["method"] == "POST"]
            if posts:
                queue_delays.append((min(r["arrived_ns"] for r in posts) - batch["created_ns"]) / 1e9)
                if any(r["arrived_ns"] >= batch["deadline_ns"] for r in posts):
                    violations.append("post_arrived_after_deadline")
    actual_records = {r["id"]: json.loads(r["content"])
                      for r in evidence["receivers"].get("destination-api", {}).get("records", [])}
    if actual_records != expected_records:
        violations.append("destination_readback_mismatch")
    for call in evidence["control"]["calls"]:
        remote = receipts_by_resource.get(call["resource"], {}).get(call["key"])
        if call["state"] == "confirmed" and (not remote or call["receipt"] != remote["receipt"]):
            violations.append("local_receipt_mismatch")
    if unresolved:
        violations.append("unresolved_records")
    if late:
        violations.append("freshness_breach")
    if successful != expected:
        violations.append("incomplete_on_time_coverage")
    if actual_cost > spec["budget_cents"]:
        violations.append("synthetic_budget_breach")
    if any(f.get("429") for f in failures.values()):
        warnings.append("receiver_rejections_observed")
    if actual_cost != predicted_cost:
        warnings.append("synthetic_cost_variance")
    queue, peak = 0, 0
    for item in sorted(evidence["control"]["events"], key=lambda e: e["at_ns"]):
        if item["kind"] == "queued":
            queue += 1
        elif item["kind"] == "dequeued":
            queue -= 1
        peak = max(peak, queue)
    return {"acceptable": not violations, "violations": sorted(set(violations)), "observations": warnings,
            "source_records": expected, "on_time_records": successful, "late_records": late,
            "unresolved_records": unresolved, "retained_destination_records": len(actual_records),
            "predicted_cost_cents": predicted_cost, "actual_synthetic_cost_cents": actual_cost,
            "cost_variance_cents": actual_cost - predicted_cost,
            "effective_cents_per_on_time_record": actual_cost / successful if successful else None,
            "predicted_requests": dict(predicted_requests), "actual_requests": request_totals,
            "capacity": capacities, "failures": failures, "workflows": per_workflow,
            "max_freshness_seconds": max(freshness, default=None),
            "max_source_to_request_seconds": max(queue_delays, default=None), "peak_queued_batches": peak,
            "timing_boundary": f"Accelerated local clock: {runtime['window_seconds']} real seconds per "
                               f"{spec['slot_minutes']} modeled minutes; not a production throughput/SLO claim",
            "cost_boundary": "Synthetic fixed platform fees + destination POST attempts at route price + "
                             "one synthetic cent for every receipt GET; no real vendor spend"}
