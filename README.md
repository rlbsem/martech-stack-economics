# MarTech Stack Economics

[![Windows + Linux CI](https://github.com/rlbsem/martech-stack-economics/actions/workflows/verify.yml/badge.svg)](https://github.com/rlbsem/martech-stack-economics/actions/workflows/verify.yml)

**Can we reduce integration cost without making launch-day workflows late, losing required data, or exhausting a shared API quota?**

This executable planner selects a cost-minimal integration configuration for a finite set of business workflows. It accounts for shared platform fees, partially filled batches, hourly bursts, total quotas, required data capabilities, permitted processing regions and declared freshness bounds. One configuration must work across every supplied scenario.

**Business impact:** Lower integration costs while protecting critical launch deadlines, data freshness and API capacity. The planner makes decisions defensible: which workflows can share a platform, which require faster routes, and when a proposed saving would compromise execution. The output includes the arithmetic and rejected alternatives a platform architect can discuss with Marketing, Web, Product Marketing and integration owners.

![Executed stack optimization: selected configuration, independent optimum check and capacity tradeoffs](docs/images/optimization-result.svg)

*Generated from the actual solve and independent checks. One configuration must satisfy normal demand and the campaign surge; cheap plans that violate constraints receive no recommendation. [Full accounting and rejected alternatives](docs/evidence/report.md).*

**Start with the [executed proof](docs/evidence/report.md).** Five synthetic workflows span lead handoff, campaign suppression, attribution, web personalization and product enrichment.

| Engineering question | Executed result |
|---|---|
| Does the cheapest normal-day plan survive a campaign surge? | No. Independent accounting identifies the shared quota violations |
| What configuration satisfies both scenarios at minimum modeled cost? | Streaming for three time-sensitive workflows; bulk for two slower workflows |
| How is the optimum checked? | Independent enumeration of all **3,125 configurations** agrees with the MILP solver |
| Can the budget be one cent below the optimum? | No feasible plan; a named constraint conflict is retained |
| Does shrinking capacity merely slow the same architecture? | The optimal configuration changes; at 30 CRM requests/hour, none is feasible |

**Verified synthetic result:** The optimal configuration costs **$7.82 versus $13.40** for the feasible all-premium reference over four hours, while satisfying modeled demand, data freshness and API capacity. Independent enumeration makes the engineering and cost tradeoff reproducible.

## Architecture decision boundary

This engine solves a specific enterprise planning problem: **select the lowest-cost feasible integration configuration** under modeled API quotas, demand, freshness, capacity and capability constraints. It supports architecture decisions; it does not replace the control plane responsible for source authority, execution governance or downstream reconciliation. [Model architecture and decisions](docs/architecture.md).

```mermaid
%%{init: {"theme":"base","themeVariables":{"background":"#10101D","primaryColor":"#2A2A3D","primaryTextColor":"#F0F0FF","primaryBorderColor":"#7C7CAF","lineColor":"#B8B8FF","textColor":"#F0F0FF","secondaryColor":"#181825","tertiaryColor":"#2E2E45","fontFamily":"IBM Plex Sans, Arial, sans-serif","fontSize":"15px","edgeLabelBackground":"#10101D"}}}%%
flowchart TB
    W[Workloads and business requirements] --> C[Closed input contract]
    S[Demand scenarios and shared quotas] --> C
    P[Synthetic route costs and service envelopes] --> C
    C --> M[Integer model compiler]
    M --> O[HiGHS optimizer through SciPy]
    O --> I[Independent integer accountant]
    I --> R[Reviewable configuration and capacity headroom]
    O --> F[Infeasible or unresolved: no recommendation]
    E[Exhaustive small-case oracle] --> V[Compare feasibility and optimum]
    O --> V

    classDef source fill:#181825,stroke:#7C7CAF,color:#F0F0FF,stroke-width:2px;
    classDef foundation fill:#2A2A3D,stroke:#B8B8FF,color:#F0F0FF,stroke-width:2px;
    classDef capability fill:#2A2A3D,stroke:#7C7CAF,color:#F0F0FF,stroke-width:2px;
    classDef output fill:#2E2E45,stroke:#81C5B0,color:#F0F0FF,stroke-width:2px;
    classDef alert fill:#2E2E45,stroke:#E3BC7F,color:#F0F0FF,stroke-width:2px;

    class W,S,P,E source;
    class C foundation;
    class M,O,I,V capability;
    class R output;
    class F alert;
```

The evidence figure is a static projection of the linked JSON, not an application screenshot. Regenerate it with `python docs/images/render.py` after the corresponding evaluation or planning evidence is refreshed.

## Run it

Use Python **3.12**, from the extracted repository root:

```bash
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.lock
python -m pip install --no-deps --no-build-isolation -e .
python scripts/verify.py
```

Verification runs lint, dependency checks, automated tests, independent optimum comparisons and the asserted demonstration, then regenerates source-bound evidence. No API key, model download, cloud account, database or Docker engine is needed.

For an individual decision:

```bash
stack-economics solve fixtures/campaign-launch.json --output work/plan.json
stack-economics check fixtures/campaign-launch.json --plan work/plan.json --output work/check.json
```

`check` recomputes feasibility and accounting and rejects changed assumptions or implementation. It does **not** independently reprove a saved plan's optimality. `solve` establishes the solver optimum and checks the selected configuration independently. [Commands and exit codes](docs/operations.md).

## What is implemented and verified

- **Joint configuration selection:** shared fixed fees are charged once per enabled platform, not once per workflow. Choices cannot change between scenarios.
- **Integer request accounting:** a partial batch consumes a whole request; zero records consume no requests. Hourly and total quotas are both enforced.
- **Hard business constraints:** price cannot override required deletion/field support, permitted regions or freshness bounds.
- **Bounded failure behavior:** infeasible, solver-limited, solver-error and independently rejected results contain no recommendation. Infeasibility explanations distinguish a fully reduced conflict from an unfinished reduction.
- **Independent checks:** a separate integer accountant never imports the compiler; exhaustive enumeration and randomized cases compare feasibility and global cost, not just a solver success flag.
- **Evidence preservation:** the demo retains overloaded and lossy cheap plans, input assumptions, resource headroom, cost lines, capacity tradeoffs and infeasible results.

Python makes the input and accounting readable. SciPy's HiGHS-backed mixed-integer solver handles the coupled discrete choices; it is appropriate where sorting routes by price fails because shared fees and quotas interact. [Architecture and mathematical contract](docs/architecture.md).

## Architecture scope and operating assumptions

This is an independent, synthetic **offline planning system**. Route capability and latency declarations are inputs, not executed vendor integrations or measured service guarantees. Capacity is modeled per hour and per horizon; within-hour queues, network timing, live scheduling, probabilistic demand and unmodeled outages are outside the proof. No campaign is sent and no procurement action is taken.

The original executed verification used local Windows, Python, NumPy and SciPy. [GitHub Actions verification passed on Ubuntu and Windows](https://github.com/rlbsem/martech-stack-economics/actions/runs/38501653389), exercising the solver, independent accountant, exhaustive oracle, failure tests and CLI checks. Those CI results verify the synthetic planning workflow, not external vendor performance.

[Actual validation and limitations](docs/validation.md) · [Generated test/environment record](docs/evidence/verification.json) · [Technical verification record](docs/handoff.md)
