# PR5 foundation fetch evidence — 2026-09-06

## Requested source

- Repository: `https://github.com/purpleeyedboy/windows-desktop-pet.git`
- Branch: `codex-od26j1`
- Expected commit: `1a02fe9680f28dda07add8b96c78445e0b3c0f59`
- Required document: `docs/v21-runtime-api.md`

## Evidence

1. `git fetch https://github.com/purpleeyedboy/windows-desktop-pet.git codex-od26j1:refs/remotes/pr5/codex-od26j1` failed with `CONNECT tunnel failed, response 403`.
2. `git cat-file -t 1a02fe9680f28dda07add8b96c78445e0b3c0f59` reported that the object is unavailable locally.
3. Searching local reachable and unreachable objects found no commit containing `docs/v21-runtime-api.md`.
4. Direct requests to both `raw.githubusercontent.com/.../codex-od26j1/docs/v21-runtime-api.md` and the codeload branch archive failed with the same proxy `403`.
5. The configured web retrieval endpoint returned `401 Unauthorized` for the requested GitHub/raw URLs.

## Integration decision

No PR5 code was copied, merged, reimplemented, or claimed as integrated. In particular, this run did not invent substitutes for `create_application_services`, `ApplicationServices`, `foundation/runtime.py`, `services.py`, or `regions.py`. The current branch remains at its pre-integration state until the exact PR5 commit/document becomes available in the checkout or through a reachable remote.

No acceptance candidate was produced. No approved asset or user file was read or modified by this fetch audit.
