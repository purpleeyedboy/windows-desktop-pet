# Hunger rework — 2026-09-10

Implemented behavior slice (not visual acceptance):
- Persistent fish meter, continuous green-to-red color and numeric percent.
- 20% crossing then 18/16/14/12/10/8/6/4/2% crossings. Large offline jumps coalesce into one current-stage event.
- Exactly 10% stays mild; below 10% is severe. Below 1% keeps critical feedback visible until recovery to at least 1%.
- Upward feeding does not trigger hunger; reaching full from below triggers one spring bubble. Starting full does not spam.
- Four 100-entry short Chinese mood corpora (400 individually written utterances, not thought/suffix combinations), mild/severe/critical shake levels. Severe/critical entries never use laughing endings.
- Pending hunger animation waits for the coordinator and starts its text at the same time.

Evidence for the corpus follow-up: new regression first failed (10 distinct thoughts instead of 100); all 7 feedback tests now pass, including critical startup/recovery/reentry and coalesced offline crossings. Shared-state verification passes. Existing test_hunger.py cannot collect because its old HungerStore API no longer exists in the inherited branch. No Windows runtime is available here, so HUD placement and bubble motion require Windows verification.

Follow-up validation: the focused hunger suite now exercises the current shared-state and authored-frame interfaces (28 passed), including strict levels, restart remainder recovery, retryable/idempotent rewards, interaction blocking and critical-presentation recovery. A shutdown checkpoint race was found and fixed by sampling UTC once before deriving both value and anchor. The 400 phrases are globally distinct as well as unique within each 100-entry mood.

The source builder ran before the asset verifier. Automated checks confirmed the 640×768 anchor, neutral first/last frames, unchanged silhouette Alpha, unchanged RGB outside the declared mouth/tear regions, and five deduplicated packaged PNGs. These pixel checks do not constitute Windows visual acceptance. Existing art remains local mouth/tear composition and MUST NOT be represented as full-cat regeneration. No accepted source asset or existing EXE was overwritten.

Unfinished: Windows-hosted single-function EXE build, Actions artifact/hash evidence, and user Windows desktop visual acceptance. The Linux container has no PowerShell/Windows runtime and this checkout has no Git remote, so it cannot truthfully supply those hosted gates.
