import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from .accounting import assess
from .contracts import Invalid, load
from .planner import check_plan, solve


def write_json(path, value):
    """Replace only with a complete report; interrupted writes cannot leave partial JSON at the target."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Plan synthetic integration cost under explicit capacity and semantic constraints.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("solve", "check", "assess"):
        command = sub.add_parser(name)
        command.add_argument("spec", type=Path)
        command.add_argument("--output", type=Path, required=True)
        if name == "solve":
            command.add_argument("--seconds", type=float, default=10.0)
        elif name == "check":
            command.add_argument("--plan", type=Path, required=True)
        else:
            command.add_argument("--selection", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        spec = load(args.spec)
        if args.command == "solve":
            result = solve(spec, seconds=args.seconds)
            code = 0 if result["status"] == "optimal" else 2 if result["status"] == "infeasible" else 3
        elif args.command == "check":
            result = check_plan(spec, json.loads(args.plan.read_text(encoding="utf-8")))
            code = 0
        else:
            result = assess(spec, json.loads(args.selection.read_text(encoding="utf-8")))
            code = 0 if result["feasible"] else 2
        write_json(args.output, result)
        print(f"{args.command}: {result.get('status', 'feasible' if result.get('feasible') else 'infeasible')} -> {args.output}")
        return code
    except (Invalid, OSError, ValueError) as exc:
        print(f"Refused: {exc}")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
