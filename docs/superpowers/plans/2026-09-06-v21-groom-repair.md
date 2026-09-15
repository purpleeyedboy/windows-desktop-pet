# V2.1 Groom Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development, systematic-debugging, desktop-pet-repo-controller, desktop-pet-motion-rig, desktop-pet-visual-qa, and verification-before-completion.

**Goal:** Replace the rejected autonomous/fake-drawing implementation with a contract-correct grooming feature adapter ready for the shared PR5 foundation and real approved local layers.

**Architecture:** The feature adapter receives the shared clock, RNG, activity permission, state version, animation ID, and cancellation token; it does not create an AppState, queue, clock, store, or global listener. Runtime image composition remains disabled until validated original-paw, vacancy-fill, mouth/tongue, mask, anchor, and safe-frame data are available and the shared coordinator is integrated.

**Tech Stack:** Python 3.11, Pillow, Tk adapter interfaces, PyInstaller/PowerShell.

## Global Constraints

- Preserve approved head/body/eye assets, Alpha, head following, blink, head rotation, and minimum-jerk.
- Remove geometric fake paw/tongue rendering and fixed mouth coordinates.
- Eligibility is 60 seconds of shared explicit-interaction idle plus one 90–300 second randomized wait; ordinary cursor passage and eye-follow targets do not reset it.
- One round fixes one cat-side paw and 3–20 repetitions; each lick is 0.45 seconds and total round duration is at most 13 seconds.
- Do not publish an acceptance candidate before PR5 foundation integration and validated local grooming assets.

## Tasks

- [x] Add failing timing, eligibility, duration, cancellation, identity, and adapter tests.
- [x] Replace target-stability scheduling with shared-idle inputs and correct timings.
- [x] Add the feature adapter protocol and completion identity checks without duplicating shared services.
- [x] Remove the rejected geometric compositor from the runtime path.
- [x] Record required foundation APIs and missing asset manifest explicitly.
- [x] Gate packaging until foundation and assets are supplied.
- [ ] Verify imports, call graph, forbidden-pattern removal, text-only diff, and asset hashes; commit without merging.
