import hashlib
import json
import re
from pathlib import Path


class Invalid(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def implementation():
    return digest({p.name: p.read_text(encoding="utf-8") for p in sorted(Path(__file__).parent.glob("*.py"))})


def integer(value, low=0, high=1_000_000):
    if type(value) is not int or not low <= value <= high:
        raise Invalid("bounded_integer_required")


def identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,59}", value):
        raise Invalid("invalid_identifier")


def shape(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise Invalid("unexpected_or_missing_fields:" + keys)


def identifiers(values, maximum=12):
    if not isinstance(values, list) or not 1 <= len(values) <= maximum:
        raise Invalid("invalid_list_size")
    for value in values:
        identity(value)
    if len(set(values)) != len(values):
        raise Invalid("duplicate_identifier")


def objects(values, maximum):
    if not isinstance(values, list) or not 1 <= len(values) <= maximum:
        raise Invalid("invalid_object_list")
    if any(not isinstance(item, dict) or "id" not in item for item in values):
        raise Invalid("object_id_required")
    identifiers([item["id"] for item in values], maximum)


def validate(spec):
    shape(spec, "schema id currency slot_minutes slots budget_cents platforms resources workloads scenarios")
    integer(spec["schema"], 1, 1)
    identity(spec["id"])
    if spec["currency"] != "USD":
        raise Invalid("synthetic_USD_contract_required")
    integer(spec["slot_minutes"], 1, 1440)
    integer(spec["slots"], 1, 24)
    integer(spec["budget_cents"], 0, 1_000_000_000)
    objects(spec["platforms"], 8)
    objects(spec["resources"], 6)
    objects(spec["workloads"], 12)
    objects(spec["scenarios"], 6)
    platforms = {p["id"] for p in spec["platforms"]}
    resources = {r["id"] for r in spec["resources"]}
    workloads = {w["id"] for w in spec["workloads"]}
    for platform in spec["platforms"]:
        shape(platform, "id fixed_cost_cents")
        integer(platform["fixed_cost_cents"])
    for resource in spec["resources"]:
        shape(resource, "id unit")
        if resource["unit"] != "requests":
            raise Invalid("resource_unit_must_be_requests")
    for workload in spec["workloads"]:
        shape(workload, "id owner max_lag_minutes required_capabilities allowed_regions options")
        identity(workload["owner"])
        integer(workload["max_lag_minutes"], 0, 1440)
        identifiers(workload["required_capabilities"])
        identifiers(workload["allowed_regions"])
        objects(workload["options"], 6)
        for option in workload["options"]:
            shape(option, "id platform region capabilities lag_minutes batch_size cost_per_batch_cents resources")
            identity(option["platform"])
            if option["platform"] not in platforms:
                raise Invalid("unknown_platform")
            identity(option["region"])
            identifiers(option["capabilities"])
            integer(option["lag_minutes"], 0, 1440)
            integer(option["batch_size"], 1)
            integer(option["cost_per_batch_cents"], 0, 1000)
            if not isinstance(option["resources"], dict) or not option["resources"] or not set(option["resources"]) <= resources:
                raise Invalid("unknown_or_missing_resource")
            for units in option["resources"].values():
                integer(units, 1, 100)
    for scenario in spec["scenarios"]:
        shape(scenario, "id demands capacities")
        if not isinstance(scenario["demands"], dict) or set(scenario["demands"]) != workloads:
            raise Invalid("complete_workload_demands_required")
        if not isinstance(scenario["capacities"], dict) or set(scenario["capacities"]) != resources:
            raise Invalid("complete_resource_capacities_required")
        for demands in scenario["demands"].values():
            if not isinstance(demands, list) or len(demands) != spec["slots"]:
                raise Invalid("complete_slots_required")
            for demand in demands:
                integer(demand, 0, 100_000)
        for capacity in scenario["capacities"].values():
            shape(capacity, "per_slot total")
            integer(capacity["total"], 0, 1_000_000_000)
            if not isinstance(capacity["per_slot"], list) or len(capacity["per_slot"]) != spec["slots"]:
                raise Invalid("complete_slots_required")
            for units in capacity["per_slot"]:
                integer(units, 0, 1_000_000_000)
    # Worst aggregate arithmetic stays below 2**53, including all allowed options and fees.
    # JSON round-trip detaches nested caller data from the solve's immutable input snapshot.
    return json.loads(canonical(spec))


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Invalid("duplicate_json_key:" + key)
            result[key] = value
        return result
    try:
        return validate(json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise Invalid("invalid_json") from exc
