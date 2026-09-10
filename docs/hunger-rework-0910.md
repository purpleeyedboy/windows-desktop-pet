# Hunger rework — 2026-09-10

Implemented behavior slice (not visual acceptance):
- Persistent fish meter, continuous green-to-red color and numeric percent.
- 20% crossing then 18/16/14/12/10/8/6/4/2% crossings. Large offline jumps coalesce into one current-stage event.
- Exactly 10% stays mild; below 10% is severe. Below 1% keeps critical feedback visible until recovery to at least 1%.
- Upward feeding does not trigger hunger; reaching full from below triggers one spring bubble. Starting full does not spam.
- Four 100-entry short Chinese mood corpora (400 individually written utterances, not thought/suffix combinations), mild/severe/critical shake levels. Severe/critical entries never use laughing endings.
- Pending hunger animation waits for the coordinator and starts its text at the same time.

Evidence for the corpus follow-up: new regression first failed (10 distinct thoughts instead of 100); all 7 feedback tests now pass, including critical startup/recovery/reentry and coalesced offline crossings. Shared-state verification passes. Existing test_hunger.py cannot collect because its old HungerStore API no longer exists in the inherited branch. No Windows runtime is available here, so HUD placement and bubble motion require Windows verification.

Unfinished: generated full-cat art, larger mild mouth opening, frame-to-frame visual QA, Windows EXE build. Existing art loader still enforces local mouth/tear composition and MUST NOT be represented as full-cat regeneration. Source builder must run before the existing asset verifier (v1 manifest is generated during packaging). No existing accepted asset or EXE was overwritten.
