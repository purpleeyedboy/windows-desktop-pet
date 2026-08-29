# Ship

## Load When

Load for commits, pull requests, CI/CD, documentation, deprecation, migration, deployment, or launch. Skip when no repository or release state changes.

## Minimal Flow

1. Select only the user-authorized operation: local commit, push/PR/CI, deprecation/migration, or release/deployment. Run only applicable branches supported by the host and project.
2. Always confirm exact scope, a clean diff, and passing applicable checks.
3. If a commit is authorized, create one logical commit using repository identity and conventions. Never stage unrelated files or secrets.
4. If push, PR, or CI work is authorized and available, verify the intended remote and ref. Make CI enforce already-required checks only; add no redundant tooling.
5. Create explicitly requested product, user, API, onboarding, or operational documentation when in scope. Optionally add maintainer rationale or an ADR only for durable, non-obvious context.
6. If deprecation or migration is in scope, identify consumers, provide a compatible path, communicate timing, and require evidence before removal.
7. Only for an authorized release, define rollout, health signals, owner, rollback trigger, and rollback action before exposure.

## Higher-Risk Depth

Use staged rollout for large blast radius and mixed-version compatibility where relevant. Define the acceptable recovery point and downtime. Test backup restoration before destructive exposure. Require an explicit, tested rollback or roll-forward/recovery path; do not roll back when doing so would lose newer data.

## Stop

Stop when the authorized operation is complete and its applicable checks pass. For a release, also verify health and close release-specific actions. Do not add release infrastructure without a concrete need.

## Verify

- For a local commit, the commit and intended files match local state.
- After a push, the remote SHA and ref match the intended local commit.
- When CI is present and in scope, required checks pass.
- When documentation or migration is in scope, its recorded status matches reality.
- For a release, monitoring and the rollback or recovery path are usable, not placeholders.
