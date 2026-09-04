---
name: desktop-pet-motion-rig
description: Change or review eye, blink, head-neck deformation, idle tilt, and easing behavior without altering approved art.
---

# Desktop Pet Motion Rig

1. Identify whether a value is an actual motion range or a mesh/pose safety boundary.
2. Write and observe focused failing tests for every direction and boundary before production changes.
3. Preserve approved head/body/eye bytes, Alpha, pivots, deformation topology, and established timing unless explicitly authorized.
4. Verify easing at endpoints and interior samples; verify left and right extrema independently.
5. Run focused motion tests, full regressions, compilation, asset hash comparison, and diff checks.
