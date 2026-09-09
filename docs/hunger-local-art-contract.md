# V2.1 hunger local-art contract

This contract is intentionally separate from the approved head, body, eye and
Alpha sources.  The current program-drawn mouth/tongue layer is functional
integration evidence only; it is **not** final or visually accepted artwork.

An art replacement must provide transparent local layers in the compositor's
head-local coordinate system:

| Layer | Required poses | Compositing rule |
| --- | --- | --- |
| mouth interior | closed, open | behind muzzle fur, source-over |
| tongue | open | above mouth interior and below muzzle repair |
| muzzle repair | closed, open | above local mouth layers only |
| tear left/right | small, exaggerated | above the current head, below UI |

Each layer must expose a local anchor relative to the midpoint of the current
eye boxes.  Runtime placement must transform that anchor from the original
pose on every frame; it must never transform the preceding output frame.  The
animation controller supplies only `mouth_open` (`0..1`), `tears_visible`,
`tear_scale`, `phase`, and `animation_id`.  Artwork must not own hunger state,
time, activity priority, input gating, or persistence.

The replacement must preserve the dimensions and bytes of every existing
approved binary asset.  It may be considered complete only after the new local
layers are wired through `PetWindow.present_hunger` and accepted on Windows.
