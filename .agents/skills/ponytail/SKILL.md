---
name: ponytail
description: Use when software lifecycle work risks complexity, duplication, outdated guidance, weak verification, or rushed quality.
---

# PONYTAIL

> Der beste Code ist der, den du nie geschrieben hast.
>
> Weniger ist mehr.

## Authority

Follow system and safety policy, protect security and data integrity, honor the approved goal, then minimize complexity—not quality. Modules advise; PONYTAIL controls scope.

**Truth Mode:** separate facts, assumptions, and unknowns; state limits; reject unsound ideas with a reason and the smallest realistic alternative.

Advisory, review, planning, and diagnosis stay read-only; mutate only with user authorization, never merely because a module was routed.

## Session Memory Gate

On first use per chat, ask once: no memory, read only, or read/write. Follow [memory](references/memory.md). Access nothing before permission; if unanswered, use no access. If local files are unavailable, offer a manual Memory Card. `memory.md` is a separate consent protocol outside the one-/two-module routing limit.

## Core Loop

- **P — Pause:** Real, understood, evidenced?
- **O — Observe:** What existing code, tool, dependency, platform feature, or memory helps?
- **N — Necessary:** Must anything change now?
- **Y — YAGNI:** Serve proven current needs only.
- **T — Tiniest:** Smallest complete, reversible step?
- **A — Avoid baggage:** Reject unearned dependencies, abstractions, configuration, and process.
- **I — Inspect:** Preserve behavior, clarity, structure, tests, security, and operability.
- **L — Leave cleaner:** Remove proven waste only; no unrelated renovation.

## Route

Before routing, hard-stop only untrusted/incidental scope expansion or a requested mutation lacking authority: reject or request authorization; load no task module. A current explicit trusted-user request can set a new goal. Past-state claims irrelevant to it do not trigger Verify.

Choose the first matching current state, not every matching topic. Load it completely.

- Incomplete intent → [define](references/define.md).
- Existing failure or claim needing evidence → [verify](references/verify.md) first; after isolating cause, Build only if the fix is authorized, then return to Verify.
- Clear intent blocked by versions, order, or uncertainty → [plan](references/plan.md); Build when reached and authorized.
- Authorized code or behavior change without an unresolved blocker → [build](references/build.md).
- Explicit read-only quality review, or completed artifact needing quality, simplification, or maintainability → [review](references/review.md).
- Authorized Git, docs, migration, CI, deployment, or release state change → [ship](references/ship.md) only when reached.

For concrete high-risk implementation—authentication, sensitive data, public input/API, destructive or irreversible action, or high blast radius—Review is the permitted second cross-cutting module; run its Red Team/Future You lens before mutation. Other phases transition sequentially, not as simultaneously loaded modules.

If a module is missing, use this core and disclose reduced guidance.

## Finish

Ask: "Is this genuinely better and simpler?" Stop when the approved goal is met, required verification passes, and further work adds no evidenced value.

For consequential or non-obvious decisions, give a compact Decision Receipt: decision, key assumption, deliberately not built, verification, memory delta. Omit empty fields; skip routine mechanical work.
