import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import stack_economics

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    paths = [p for folder in ("src", "tests", "scripts", "fixtures", ".github") for p in (ROOT / folder).rglob("*")
             if p.is_file() and p.suffix in (".py", ".json", ".yml") and "__pycache__" not in p.parts]
    paths += [ROOT / "pyproject.toml", ROOT / "requirements.lock"]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    began = time.monotonic()
    output = ROOT / "docs/evidence"
    output.mkdir(parents=True, exist_ok=True)
    work = ROOT / "work/verification" / uuid4().hex
    work.mkdir(parents=True)
    installed = Path(stack_economics.__file__).parent
    for source in (ROOT / "src/stack_economics").glob("*.py"):
        if source.read_bytes() != (installed / source.name).read_bytes():
            raise RuntimeError("Installed package differs from source; reinstall before verification")
    before = manifest()
    def execute(*args):
        subprocess.run([sys.executable, *args], cwd=ROOT, check=True)
    execute("-m", "ruff", "check", "src", "tests", "scripts")
    execute("-m", "pip", "check")
    execute("-m", "pytest", "-q", "--basetemp", str(work / "tests"), "-o", "cache_dir=" + str(work / "cache"),
            "--junitxml", str(output / "tests.xml"))
    execute("scripts/demo.py")
    # Exercise the installed module as a real subprocess, including argument parsing and exit code.
    execute("-m", "stack_economics.cli", "solve", "fixtures/campaign-launch.json", "--output", str(work / "plan.json"))
    execute("-m", "stack_economics.cli", "check", "fixtures/campaign-launch.json", "--plan", str(work / "plan.json"),
            "--output", str(work / "checked.json"))
    assert before == manifest(), "Inputs changed during verification"
    suite = ET.parse(output / "tests.xml").getroot().find("testsuite")
    record = {"executed_at": datetime.now(UTC).isoformat(), "python": platform.python_version(),
              "platform": platform.platform(), "packages": {p: importlib.metadata.version(p) for p in ("numpy", "scipy", "pytest", "ruff")},
              **{k: int(suite.attrib[k]) for k in ("tests", "failures", "errors", "skipped")},
              "seconds": round(time.monotonic() - began, 3), "source_sha256": before,
              "installation": "source" if installed.resolve() == (ROOT / "src/stack_economics").resolve() else "installed_wheel",
              "hosted_ci": "workflow_in_progress" if os.getenv("GITHUB_ACTIONS") else "not_observed",
              "scope": "Local MILP solves, independent integer accounting/exhaustive oracle, CLI and failure injection; synthetic inputs"}
    (output / "verification.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {record['tests']} tests, the complete economics proof and installed CLI round-trip.")


if __name__ == "__main__":
    main()
