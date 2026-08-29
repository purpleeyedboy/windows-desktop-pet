# Windows Desktop Pet — Cloud Continuation Handoff

## Current checkpoint

- Branch: `codex/desktop-pet-6-frame-alpha`
- Last completed implementation commit before cloud checkpoint: `735f8d2`
- Stable executable preserved in `交付/桌面宠物-6帧猫耳颜文字版.exe`; it is the previous six-frame release, not the unfinished head-follow build.
- The current branch is a work-in-progress checkpoint. Do not label it a completed release.

## Approved objective

Extend the existing six-frame Windows cat desktop pet with:

1. mouse-driven eye, face, head, and neck following using soft asymmetric deformation rather than rigid puppet rotation;
2. natural random blinking;
3. low-probability left/right idle head tilts and return-to-center behavior.

The approved design is in `docs/superpowers/specs/2026-08-28-organic-head-follow-blink-idle-design.md`. The current center-layer feasibility plan is in `docs/superpowers/plans/2026-08-28-rig-center-layer-feasibility.md`.

## Durable progress

Read `.superpowers/sdd/progress.md` and the reports under `.superpowers/sdd/organic-head/` before changing anything.

- R1 complete: immutable canonical source.
- R2 complete: fixed masks, landmarks, and guides.
- R3 complete numerically: hidden body/eye sources, fixed-mask Alpha, provenance.
- R4 complete and independently reviewed: center layers retain hidden body/eye contributions while decoded center recomposition is exactly canonical (`changed_pixels=0`, `maximum_channel_delta=0`).
- R5 blocked on visual quality, not math: focused rig tests passed and containment/Alpha/exactness passed, but the body hidden patch looked painted/blurred and the left eye underlay retained iris/pupil-like content.

The rejected evidence is preserved under `qa/rig-v1/rejected/20260829-085501/`. Current uncommitted R5 generator/test/evidence are included in the cloud checkpoint only to preserve work; they do not represent visual approval.

## Failed approaches and current decision boundary

Do not repeat full-canvas or enlarged-crop built-in image edits without a new hypothesis. Multiple attempts failed:

- full-canvas generation produced soft, long, plug-like chest fur and eye-like underlays;
- targeted corrections still regenerated unrelated pixels and did not fix the masked region;
- localized 4x body crop generation still produced gray blur and vertical long tufts;
- actual transparent output requests repeatedly returned RGB images with a baked checkerboard; deterministic fixed-mask Alpha repair solved only transparency, not texture quality.

The next proposed alternative was local OpenCV neighbor-texture cloning/warping plus seamless blending for the hidden shoulder/chest, and a deterministic neutral gray-green eye base without iris, pupil, slit, ring, or highlight. This content-level OpenCV method has not yet been approved or implemented. Discuss it with the user online before modifying R3 sources.

## Non-negotiable gates

- Use `$ponytail` for all subsequent work.
- Do not alter the stable six-frame release or overwrite prior delivery files.
- Do not start five-direction assets, blink assets, idle tilt assets, runtime integration, or EXE packaging until the user approves the center visual gate.
- Preserve per-pixel Alpha; no Tkinter chroma-key transparency and no pink/purple fringe.
- All generated pixels outside fixed masks are untrusted and must be discarded.
- Center decoded RGBA must remain byte-equivalent to canonical.
- Every task uses a fresh implementer, independent task review, and a final whole-branch review.
- Keep facts, assumptions, unknowns, static checks, runtime checks, and user visual judgment separate.

## Verification evidence

- Cloud checkpoint full suite: `178 passed in 249.41s` on 2026-08-29.
- Full pre-rig baseline: `167 passed`.
- R4 focused assembly after review fixes: `6 passed`; real center `changed_pixels=0`, `maximum_channel_delta=0`; Alpha validation clean.
- R5 focused rig suite: `11 passed`; runtime source scan found no `numpy`, `cv2`, or `opencv` imports.
- R5 visual result: rejected for body texture and left-eye underlay; no R5 completion commit was created before this cloud checkpoint.

Repository skill packaging was verified before upload: all 10 skill directories contain `SKILL.md` frontmatter, no nested `.git` exists, and all 11 repository-scoped `ponytail` payload files match the installed local source by SHA-256.

## Cloud workflow

1. Confirm the repository-scoped skills under `.agents/skills/` are visible, especially `$ponytail`.
2. Read this file, the approved spec/plan, `.superpowers/sdd/progress.md`, and the latest R3-R5 reports.
3. Inspect `qa/rig-v1/rejected/20260829-085501/qa/center-contact-sheet.png` at original resolution.
4. Report receipt and the exact next decision to the user. Do not resume asset mutation until the user confirms the content-level repair method online.
