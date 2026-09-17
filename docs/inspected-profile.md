# Richard Butts

**AI Systems Architecture · Data Architecture · MarTech / GTM Systems · Analytics Engineering · Enterprise Integration**

I design and build analytics, MarTech, GTM, AI, customer-data, and enterprise integration systems with an emphasis on governed state, temporal correctness, data quality, reliable automation, evaluation, and measurable business outcomes.

My work sits where software behavior meets business truth: what state is authoritative, what an automated system is allowed to change, whether an AI agent is actually safe and better enough to release, who belongs in an audience at a given business time based on what was known at that point, and whether a critical platform can be replaced without destroying meaning or reversibility.

## Selected engineering work

| Project | What it demonstrates |
|---|---|
| **[Enterprise MarTech / AI Control Plane](https://github.com/rlbsem/enterprise-martech-ai-control-plane)** | Governed customer identity, source and field authority, consent, AI action boundaries, human approval, durable execution, retries, uncertain-result recovery, idempotent downstream effects, auditability, PostgreSQL, FastAPI, Docker, and CI. |
| **[Enterprise Agent Runtime & Evaluation](https://github.com/rlbsem/enterprise-agent-runtime-evaluation)** | Agent regression testing, actual local LLM inference, structured tool decisions, evidence grounding, prompt-injection/adversarial evaluation, release gating, shadow/canary evaluation, rollback, runtime observability, and cross-platform CI. |
| **[Temporal Customer Audiences](https://github.com/rlbsem/temporal-customer-audiences)** | Bitemporal customer state, late arrivals and corrections, immutable original versus restated audience generations, clock-driven invalidation, coverage-conditioned activation, selective reevaluation, independent full-evaluator equivalence, destination reconciliation, and cross-platform CI. |
| **[MarTech Migration Assurance](https://github.com/rlbsem/martech-migration-assurance)** | System replacement, consistent snapshots, incremental change transfer, versioned mappings, semantic reconciliation, evidence-bound cutover, crash recovery, reverse migration, rollback safety, and cross-platform CI. |

These are executable portfolio systems, not architecture-only case studies. Each repository separates demonstrated behavior from reference architecture, preserves unfavorable results where they matter, and documents its claim boundary and known limitations.

### Portfolio thesis

1. **Governed enterprise truth:** What business state is authoritative, and what is automation allowed to make true?
2. **Agent-quality truth:** Is a candidate AI agent grounded, safe, and better enough to release?
3. **Temporal customer truth:** Who belongs in an audience at business time T, based on what was known at knowledge time K?
4. **Migration truth:** Can a critical platform be replaced without losing meaning or reversibility?

## Architecture themes

```mermaid
flowchart LR
    A[Enterprise systems + customer events]
    A --> B[Identity + provenance + authoritative state]

    B --> C[Governed Control Plane]
    B --> D[Temporal Audience Engine]
    B --> E[Migration Assurance]

    C --> F[Controlled automation + approvals]
    D --> G[Audience decisions + activation safety]
    E --> H[Cutover + reconciliation + rollback]

    F --> I[Agent Runtime + Evaluation]
    G --> J[Defensible customer truth]
    H --> J
    I --> J

    classDef source fill:#dbeafe,stroke:#2563eb,color:#0f172a,stroke-width:2px;
    classDef foundation fill:#bfdbfe,stroke:#1d4ed8,color:#0f172a,stroke-width:2px;
    classDef capability fill:#93c5fd,stroke:#1e40af,color:#0f172a,stroke-width:2px;
    classDef output fill:#60a5fa,stroke:#1e3a8a,color:#ffffff,stroke-width:2px;

    class A source;
    class B foundation;
    class C,D,E,F,G,H,I capability;
    class J output;
```

**Systems concerns:** canonical identity · source provenance · field ownership · source-of-truth governance · temporal correctness · bitemporal history · No-Regress Logic · durable state · idempotency · retries and exception handling · controlled AI actions · agent evaluation · adversarial testing · audience activation safety · source-coverage evidence · migration assurance · cutover and rollback safety · auditability · cross-system reconciliation

**Core technologies demonstrated across the public repositories:** Python · SQL · PostgreSQL · FastAPI · SQLite / FTS5 · dbt · DuckDB · Airflow · Docker · GitHub Actions · REST APIs · webhooks · local LLM inference

## Professional context

My background spans enterprise ecommerce, B2B SaaS, MarTech, analytics, GTM systems, data architecture, and enterprise integration across **Lorex Technology, LMN (Landscape Management Network), and Groundbreakers Digital**.

Across my career, I have managed more than **$65M in paid media and marketing investment**. At Lorex, annual ecommerce revenue grew from approximately **$55M to $101M** during my tenure. At LMN, I worked across an approximately **$350K/month USD acquisition program** spanning five B2B SaaS products, with CAC improvements of approximately **15–25%**.

At Groundbreakers Digital, I work on data infrastructure, revenue integrity, and M&A systems architecture for home-services and acquisition environments. The focus is not moving data for its own sake. It is governing identity, commercial state, source provenance, reconciliation, and system boundaries so operating and transaction data can be defended.

That commercial operating background is the context behind the technical work in this portfolio: the systems are designed around real constraints such as scale, attribution, customer identity, workflow reliability, platform change, and measurable business outcomes.

## Current focus

The portfolio is intentionally small. I would rather publish a few systems that can survive technical scrutiny than a large collection of toy projects.

Current areas of focus include:

- MarTech / GTM architecture and governed automation
- enterprise AI runtime, evaluation, and release governance
- temporal customer data, audience computation, and activation safety
- platform replacement, cutover, rollback, and migration assurance
- CRM → operations → billing → GL traceability
- revenue integrity and cross-system reconciliation
- post-acquisition integration and governed data migration

## Contact

- GitHub: [@rlbsem](https://github.com/rlbsem)
- Groundbreakers Digital: Data Infrastructure · Revenue Integrity · M&A Systems Architecture

I am especially interested in senior roles spanning **AI systems architecture, MarTech / GTM architecture, customer-data architecture, analytics engineering, data architecture, RevOps systems, and enterprise integration**.
