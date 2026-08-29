# Task 4 Report: Assemble the Center Layers and Prove Exact Recomposition

## RED

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_assemble_rig_center.py -q
```

Initial output: `ModuleNotFoundError: No module named 'tools.assemble_rig_center'` during test collection, as expected before the module existed.

During real-source assembly, a second RED case was added for a body-fill pixel beneath a semi-transparent canonical head/neck edge. It failed as expected with `RuntimeError: center recomposition drift: 1 pixels, max 1`.

## Implementation summary

- Added `normalize_fill`, which converts generated fills to RGBA, resizes only proportional 2:3 input to the canonical 512x768 canvas, clips the result to the supplied fixed mask, and clears RGB in fully transparent pixels.
- Added center-layer assembly, exact recomposition validation, PNG emission, and composite SHA-256 reporting.
- Kept AI body and eye fill content hidden from the center reference composite at semi-transparent boundaries by restricting body fill to the static region and limiting eye underlay substitution to fully opaque eye-mask pixels. This preserves exact canonical pixels while still independently normalizing both AI fills.

## GREEN

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_assemble_rig_center.py -q
```

Output:

```text
....                                                                     [100%]
4 passed in 2.39s
```

## Real center assembly

Command:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from tools.assemble_rig_center import assemble_center; print(assemble_center(Path('assets/rig/v1/source'), Path('assets/rig/v1/samples/center')))"
```

Output:

```text
{'changed_pixels': 0, 'maximum_channel_delta': 0, 'composite_sha256': '38c39b03c36eff983a023fc98ab6fbfefaad6098a43d729e000017a48fbfb55c'}
```

## Alpha check

Command:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from tools.rig_center_contract import validate_rgba; files=list(Path('assets/rig/v1/source/layers').glob('*.png'))+[Path('assets/rig/v1/samples/center/composite.png')]; errors={str(p):validate_rgba(p) for p in files if p.suffix=='.png' and p.name not in {'eye_left_mask.png','eye_right_mask.png'}}; print(errors); raise SystemExit(any(errors.values()))"
```

Output (exit 0):

```text
{'assets\\rig\\v1\\source\\layers\\body_base.png': [], 'assets\\rig\\v1\\source\\layers\\eye_left.png': [], 'assets\\rig\\v1\\source\\layers\\eye_right.png': [], 'assets\\rig\\v1\\source\\layers\\head_neck_base.png': [], 'assets\\rig\\v1\\samples\\center\\composite.png': []}
```

## Output inventory

| File | Mode | Size | Non-black RGB in fully transparent pixels |
| --- | --- | --- | --- |
| `body_base.png` | RGBA | 512x768 | 0 |
| `head_neck_base.png` | RGBA | 512x768 | 0 |
| `eye_left.png` | RGBA | 512x768 | 0 |
| `eye_right.png` | RGBA | 512x768 | 0 |
| `eye_left_mask.png` | L | 512x768 | n/a |
| `eye_right_mask.png` | L | 512x768 | n/a |
| `samples/center/composite.png` | RGBA | 512x768 | 0 |

## Commit

`e078a97 assets: assemble exact center rig layers`

## Concerns

None. The initial direct pytest command was blocked by sandbox access to the default pytest temporary directory; the same command passed under the approved normal local execution context.

---

# Review-finding repair (commit pending)

Committed as `735f8d2 fix: retain hidden rig fill layers`.

## Additional RED

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_assemble_rig_center.py -q
```

Output on `e078a97` after adding the review regression tests:

```text
.FF..F                                                                   [100%]
3 failed, 3 passed in 4.21s
```

The failures proved all three expected conditions: gray-mask normalization incorrectly premultiplied RGB (`(100, 50, 25, 64)` instead of `(200, 100, 50, 64)`), safe body-fill pixels were absent from `body_base`, and the temporary-encode failure injection never raised because formal outputs were written directly.

## Repair summary

- `normalize_fill` now preserves straight RGB and calculates only alpha with `ImageChops.multiply(source_alpha, mask)`.
- Body fill now remains in `body_base` wherever the fixed body-fill mask overlaps a fully opaque canonical pixel. The 20 semi-transparent canonical-edge pixels remain excluded, maintaining exact decoded recomposition.
- Eye fill remains in `head_neck_base` only under the fixed eye mask.
- Every formal output is now encoded and decoded-verified as an adjacent temporary PNG before any formal replacement. A pre-replace failure removes temporary files and leaves formal files untouched.

## Additional GREEN and failure injection

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_assemble_rig_center.py -q
```

Output:

```text
......                                                                   [100%]
6 passed in 4.01s
```

The passing suite includes the injected temporary PNG encoding failure: all seven pre-populated sentinel formal outputs remained byte-for-byte unchanged and no `*.tmp.png` files remained.

## Reassembled real center and Alpha validation

```text
{'changed_pixels': 0, 'maximum_channel_delta': 0, 'composite_sha256': '38c39b03c36eff983a023fc98ab6fbfefaad6098a43d729e000017a48fbfb55c'}
{'assets\\rig\\v1\\source\\layers\\body_base.png': [], 'assets\\rig\\v1\\source\\layers\\eye_left.png': [], 'assets\\rig\\v1\\source\\layers\\eye_right.png': [], 'assets\\rig\\v1\\source\\layers\\head_neck_base.png': [], 'assets\\rig\\v1\\samples\\center\\composite.png': []}
```

Real-source body-fill evidence:

```text
{'fixed_body_fill_pixels': 20000, 'safe_opaque_canonical_pixels': 19980, 'body_base_contributing_safe_pixels': 19980}
```

## Output hashes after repair

```text
body_base.png          05f87dc73bc2afad2934d091e89b7d3ac6c5fce960227d7af1309ece25451deb
eye_left.png           efcf482cf657f1360680fc8de73f8985447a80e6d1001d436f01ae7a53e5da69
eye_left_mask.png      8e499cb53f4f144c412a36193835bd4737582f8035d1ed8d8e7ab1f15f31dbdd
eye_right.png          3ccbc026cd84f9deeff32b0d6e760500fd17952e314cc47d0f734ec0b76fb9ae
eye_right_mask.png     ad2b6f7e88702d5074e801840aa410347549db5e9bcbe329e84974851937484f
head_neck_base.png     b1fe1a14208a63506b1c0b1a5b34db02a21e94554c1ff8f2e2cd427a433556ff
composite.png          38c39b03c36eff983a023fc98ab6fbfefaad6098a43d729e000017a48fbfb55c
```
