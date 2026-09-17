import argparse
from pathlib import Path

from stack_economics.contracts import load
from stack_economics.demo import run

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=root / "docs/evidence")
args = parser.parse_args()
proof = run(load(root / "fixtures/campaign-launch.json"), args.output)
print("Verified constrained optimum, rejected cheap plans, quota tradeoffs, infeasibility and stale-plan refusal.")
print("Report:", args.output / "report.md")
