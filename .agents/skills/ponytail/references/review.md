# Review

## Load When

Load before merge, when complexity is suspected, or when risk, security, or maintainability needs independent scrutiny. Skip ceremonial review for mechanical changes already proven by deterministic checks.

## Minimal Review

Review correctness, security, maintainability, tests, performance, and scope. Report Critical, Important, and Minor findings with evidence. Do not invent findings to appear thorough.

## Severity

- **Critical:** likely exploit, data loss, or severe correctness or availability failure. Blocks readiness until resolved, except explicit risk-owner acceptance where policy permits.
- **Important:** material maintainability, reliability, security, or test gap. Fix before ship or record an explicit informed tradeoff.
- **Minor:** non-blocking improvement.

## Simplify

Preserve behavior, error semantics, side effects, and ordering. Understand why code exists before removing it. Follow project conventions. Prefer comprehension over line count, remove dead or speculative layers only when proven unnecessary, and keep simplification inside the changed area.

## Red Team

For auth, sensitive data, external input, public APIs, irreversible operations, or high blast radius, actively seek abuse paths, false assumptions, concurrency failures, data loss, hidden coupling, operational cost, and rollback gaps. Give each valid issue an impact and the smallest effective mitigation.

## Future You

Ask whether a maintainer six months later can understand the names, boundaries, rationale, contracts, data formats, operational burden, and reversal path without this chat. Document only non-obvious durable decisions. Do not create speculative extension points.

## Stop

Stop when remaining findings are trivial, accepted tradeoffs, or outside scope. Never loop review on an unchanged artifact.

## Verify

- Every Critical finding is resolved or explicitly accepted by the risk owner where policy permits.
- Every Important finding is fixed before ship or has an explicit informed tradeoff recorded.
- Simplification is a net clarity improvement with behavior preserved.
- High-risk changes have a credible rollback or containment path.
- No unrelated renovation entered the diff.
