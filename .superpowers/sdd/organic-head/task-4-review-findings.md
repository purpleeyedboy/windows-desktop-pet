# Task R4 Review Findings Requiring Fix

Task base: `3fe889a`
Reviewed implementation: `e078a97`

## Critical — body fill contribution is zero

`tools/assemble_rig_center.py` currently masks `body_fill` by `static_mask`. The real 20,000 body-fill mask pixels are all inside the dynamic head/neck mask, so every generated body-fill pixel is deleted. Representative head-group offsets reveal transparent holes.

Fix the layer math so body fill is retained under the movable head. Keep only the part of the fixed body-fill mask where canonical alpha is exactly 255; exclude the 20 semi-transparent canonical-edge pixels so center recomposition remains exact. The reviewer independently proved this keeps 19,980/20,000 body-fill pixels and preserves decoded center `changed_pixels=0`, `maximum_channel_delta=0`.

Add a regression test that fails before the fix and proves body fill contributes to `body_base` in the safe hidden region. Also prove a representative small head-group offset does not expose a transparent hole in that safe body-fill region.

## Important — tests allow zero-contribution false green

Current assembly tests only assert center diff metrics. Add focused assertions that:

- body fill enters `body_base` in the safe opaque-canonical region;
- eye fill enters `head_neck_base`;
- generated contribution remains zero outside each fixed mask;
- a representative small head-group offset does not create a transparent hole in the safe body-fill region;
- the decoded saved center composite is still exactly canonical.

Observe the relevant new tests fail against the current implementation before editing production code, then pass after the fix.

## Important — incorrect straight-alpha handling

`normalize_fill` uses RGBA `paste(..., mask)`, which scales both RGB and Alpha for gray masks. Example: source `(200,100,50,128)`, mask `128` currently becomes `(100,50,25,64)`; correct straight-alpha is `(200,100,50,64)`.

Preserve source RGB and set output alpha to `ImageChops.multiply(source_alpha, mask)`, then clear RGB only where resulting alpha is zero. Add the exact regression example above and observe RED/GREEN.

## Important — partial multi-file output on pre-replace failure

The function currently overwrites output PNGs sequentially. Render and validate all images in memory first. Encode every output to a temporary sibling file, reopen each temporary PNG and verify expected size/mode/pixels, and only after all encodes/decodes succeed replace the formal outputs. On any pre-replace exception, remove temporary files and leave existing formal outputs untouched.

Add a focused failure-injection test that pre-populates sentinel formal outputs, forces a temporary encode/validation failure before replacement, and proves all sentinels remain unchanged with no temporary files left.

## Scope

Fix only `tools/assemble_rig_center.py`, `tests/test_assemble_rig_center.py`, and regenerated Task R4 layer/sample PNGs. Do not modify R1-R3 sources, masks, guides, AI fills, runtime, plan/spec, old QA, or delivery files. Rerun the focused tests, real assembly, exact decoded comparison, and Alpha validation. Append commands and outputs to `task-4-report.md`. Commit the fix separately.
