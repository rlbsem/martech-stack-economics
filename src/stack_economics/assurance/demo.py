"""Reproducible finite experiments, with immutable per-trial evidence packages."""
import argparse
import copy
import gzip
import json
import os
import platform
import subprocess
import time
from pathlib import Path

from stack_economics.contracts import digest, load
from stack_economics.planner import check_plan, solve

from .execution import Services, execute, profile
from .reconcile import reconcile
from .storage import authorize, encode, initialize, propose, rows, transition


def trial(directory, spec, plan, scenario, runtime, name, ledger, parent=None):
    decision = propose(ledger, spec, plan, runtime, parent, {"run": name, "scenario": scenario})
    if plan["status"] != "optimal":
        transition(ledger, decision, "blocked", "independent-plan-check", {"status": plan["status"]})
        return {"name": name, "decision": decision, "blocked": True, "plan": plan}
    check_plan(spec, plan)
    transition(ledger, decision, "validated", "independent-plan-check", {"assessment_hash": digest(plan["assessment"])})
    authorize(ledger, decision, runtime)
    directory.mkdir(parents=True)
    control = directory / 'control.sqlite'
    initialize(control)
    started = time.time_ns()
    with Services(directory / 'receivers', spec, runtime, name) as services:
        control_snapshot = execute(control, spec, plan, scenario, runtime, services, ledger, decision)
        receiver_snapshot = services.snapshot()
        epoch = services.epoch_ns
    evidence = {"schema": 1, "run": name, "decision": decision, "scenario": scenario,
                "spec": spec, "plan": plan, "profile": runtime, "epoch_ns": epoch,
                "control": control_snapshot, "receivers": receiver_snapshot}
    result = reconcile(evidence)
    transition(ledger, decision, "observed", "independent-observer", {"evidence_hash": digest(evidence)})
    transition(ledger, decision, "acceptable" if result["acceptable"] else "revision_required",
               "independent-observer", {"result_hash": digest(result), "violations": result["violations"]})
    with gzip.open(directory / 'observations.json.gz', 'wt', encoding='utf-8') as stream:
        stream.write(encode(evidence))
    (directory / 'result.json').write_text(encode(result) + '\n', encoding='utf-8')
    return {"name": name, "decision": decision, "parent": parent, "scenario": scenario,
            "evidence_hash": digest(evidence), "result_hash": digest(result), "result": result,
            "seconds": round((time.time_ns() - started) / 1e9, 3)}


def run(root, output, quick=False):
    if output.exists():
        raise ValueError("Evidence output must be a fresh directory; historical runs are never overwritten")
    output.mkdir(parents=True)
    spec = load(root / 'fixtures/campaign-launch.json')
    plan = solve(spec)
    ledger = output / 'decisions.sqlite'
    initialize(ledger)
    scenarios = [s['id'] for s in spec['scenarios']]
    experiments = [("normal", scenarios[0], profile()), ("launch-surge", scenarios[1], profile())]
    if not quick:
        experiments += [
            ("transient-recovery", scenarios[1], profile(faults=[
                {"resource": "destination-api", "kind": "429"},
                {"resource": "crm-api", "kind": "503"},
                {"resource": "destination-api", "kind": "lost_ack", "workflow": "product-enrichment"}])),
            ("delayed-source", scenarios[0], profile(source_delay={"lead-handoff": 6.4})),
            ("slow-destination", scenarios[0], profile(faults=[
                {"resource": "destination-api", "kind": "latency", "seconds": 6.4}])),
            ("shared-quota-pressure", scenarios[1], profile(capacity_override={"crm-api": 60})),
            ("revoked-permission", scenarios[0], profile(permission=False))]
    results = []
    for name, scenario, runtime in experiments:
        print('Executing', name, flush=True)
        results.append(trial(output / name, spec, plan, scenario, runtime, name, ledger))
    if not quick:
        parent = next(r['decision'] for r in results if r['name'] == 'shared-quota-pressure')
        revised = copy.deepcopy(spec)
        for scenario in revised['scenarios']:
            scenario['capacities']['crm-api']['per_slot'] = [60] * spec['slots']
        results.append(trial(output / 'capacity-revision', revised, solve(revised), scenarios[1],
                             profile(capacity_override={'crm-api': 60}), 'capacity-revision', ledger, parent))
        blocked = copy.deepcopy(spec)
        for scenario in blocked['scenarios']:
            scenario['capacities']['crm-api']['per_slot'] = [30] * spec['slots']
        results.append(trial(output / 'capacity-blocked', blocked, solve(blocked), scenarios[1],
                             profile(capacity_override={'crm-api': 30}), 'capacity-blocked', ledger, parent))
    commit = (subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
              if (root / '.git').exists() else os.environ['STACK_ECONOMICS_SOURCE_COMMIT'])
    summary = {"schema": 1, "source_commit": commit, "python": platform.python_version(),
               "platform": platform.platform(), "boundary": "Actual independent local HTTP processes and SQLite; "
               "synthetic data/prices, accelerated clock, no native vendor execution", "trials": results,
               "decisions": rows(ledger, 'decisions'), "transitions": rows(ledger, 'transitions')}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    run(args.root, args.output, args.quick)
