# Cat Rig Center-Layer Feasibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that the approved canonical cat can be split into a stable center-pose body/head/eye layer pack, with believable hidden shoulder and eye-socket fills, while recomposing to the approved cat exactly and producing visual evidence for the user before any directional or runtime work.

**Architecture:** Preserve the approved idle PNG byte-for-byte as the authority. Generate deterministic masks and guides from fixed, reviewable coordinates; use image generation only for pixels hidden behind the original head and irises; then mask those generated fills so no AI pixel can alter the visible center cat. A Pillow-only assembler reconstructs the center pose and a separate QA writer proves Alpha, identity, seam, and exact-recomposition requirements.

**Tech Stack:** Python 3.12.13, Pillow 11.3.0, NumPy 2.2.6, OpenCV 4.12.0 (offline only), pytest 8, SHA-256, built-in `$imagegen`, PNG/JSON.

## Global Constraints

- Canonical authority is `assets/keyframes/jump/00.png`, exactly `512×768 RGBA`, SHA-256 `48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7`.
- This increment may create only `tools/rig_*`, `tests/test_rig_*`, `assets/rig/v1/source/`, `assets/rig/v1/samples/center/`, and `qa/rig-v1/`; it must not modify `src/desktop_pet`, `desktop_pet.spec`, `assets/keyframes`, existing `qa/<action>`, `qa/kaomoji-release-report.md`, or `交付/`.
- Authoring visible layers are `512×768 RGBA`; masks are `512×768 L`; Alpha-0 RGB in every RGBA output is `(0,0,0)`.
- The original external antialiased Alpha is preserved. Alpha binarization is forbidden; only internal authoring selection masks may use values `0/255`.
- Generated pixels are accepted only inside `body-fill-mask.png` or the two iris masks. Pixels outside those masks always come from the canonical PNG.
- Center recomposition must be byte-equivalent as decoded RGBA pixels to the canonical image: maximum channel delta `0`, changed pixel count `0`.
- Double outlines, transparent holes, pink/purple/color spill, identity drift, and visible shoulder/neck seams are blocking failures.
- This plan ends at the center-layer user gate. It does not generate left/right/up/down poses, blink art, tilt art, runtime rig files, program code, or a new EXE.
- NumPy and OpenCV remain offline-only and must not be imported under `src/desktop_pet` or bundled.

## File Structure

- Create `tools/rig_center_contract.py`: immutable baseline copy, image-mode/size/Alpha checks, SHA-256 helpers.
- Create `tests/test_rig_center_contract.py`: deterministic baseline and rejection tests.
- Create `tools/build_rig_center_guides.py`: fixed selection masks, landmarks, and image-generation guides.
- Create `tests/test_build_rig_center_guides.py`: mask containment, coordinate, and outside-guide identity tests.
- Create `tools/assemble_rig_center.py`: mask generated fills, derive source layers, recompose center, and reject any visible drift.
- Create `tests/test_assemble_rig_center.py`: synthetic partition and generated-pixel containment tests.
- Create `tools/rig_center_qa.py`: contact sheets, background checks, close-ups, diff image, and JSON metrics.
- Create `tests/test_rig_center_qa.py`: artifact and metric contract tests.
- Create `assets/rig/v1/source/canonical-idle.png`: immutable copy of the authority.
- Create `assets/rig/v1/source/authoring.json`: fixed masks, landmarks, source hashes, and AI provenance.
- Create `assets/rig/v1/source/masks/*.png`: dynamic, body-fill, left-iris, and right-iris masks.
- Create `assets/rig/v1/source/guides/*.png`: exact image-generation inputs.
- Create `assets/rig/v1/source/ai/*.png`: normalized body-fill and eye-fill source results.
- Create `assets/rig/v1/source/layers/*.png`: center body, head/neck, eye patches, and eye masks.
- Create `assets/rig/v1/samples/center/composite.png`: exact center reconstruction.
- Create `qa/rig-v1/center-*.png` and `qa/rig-v1/center-stats.json`: review evidence.

---

### Task 1: Immutable Canonical Contract

**Files:**
- Create: `tools/rig_center_contract.py`
- Create: `tests/test_rig_center_contract.py`
- Create: `assets/rig/v1/source/canonical-idle.png`

**Interfaces:**
- Consumes: `assets/keyframes/jump/00.png`.
- Produces: `copy_canonical(source: Path, destination: Path) -> dict[str, object]`, `validate_rgba(path: Path) -> list[str]`, `sha256_path(path: Path) -> str`.

- [ ] **Step 1: Write the failing contract tests**

```python
from pathlib import Path

import pytest
from PIL import Image

from tools.rig_center_contract import CANONICAL_SHA256, copy_canonical, validate_rgba


def make_canonical(path: Path) -> None:
    image = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    image.putpixel((100, 200), (210, 140, 80, 255))
    image.save(path)


def test_copy_canonical_preserves_source_bytes(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.png"
    destination = tmp_path / "rig" / "canonical-idle.png"
    make_canonical(source)
    monkeypatch.setattr("tools.rig_center_contract.CANONICAL_SHA256", __import__("hashlib").sha256(source.read_bytes()).hexdigest())
    report = copy_canonical(source, destination)
    assert destination.read_bytes() == source.read_bytes()
    assert report == {"sha256": __import__("hashlib").sha256(source.read_bytes()).hexdigest(), "mode": "RGBA", "size": [512, 768]}


def test_copy_canonical_rejects_wrong_hash(tmp_path: Path) -> None:
    source = tmp_path / "wrong.png"
    make_canonical(source)
    with pytest.raises(RuntimeError, match="canonical SHA-256"):
        copy_canonical(source, tmp_path / "copy.png")


def test_validate_rgba_rejects_hidden_rgb_and_visible_border(tmp_path: Path) -> None:
    path = tmp_path / "bad.png"
    image = Image.new("RGBA", (512, 768), (1, 2, 3, 0))
    image.putpixel((0, 0), (50, 60, 70, 255))
    image.save(path)
    errors = validate_rgba(path)
    assert "Alpha-0 RGB must be zero" in errors
    assert "outer border must be transparent" in errors
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_rig_center_contract.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'tools.rig_center_contract'`.

- [ ] **Step 3: Implement the immutable contract**

```python
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image


CANVAS = (512, 768)
CANONICAL_SHA256 = "48f710b9811ebf6edc60764bc7a52fd1af4274a761589677df365450d8a2fec7"


def sha256_path(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _border_is_transparent(image: Image.Image) -> bool:
    alpha = image.getchannel("A")
    return not any((
        alpha.crop((0, 0, alpha.width, 1)).getbbox(),
        alpha.crop((0, alpha.height - 1, alpha.width, alpha.height)).getbbox(),
        alpha.crop((0, 0, 1, alpha.height)).getbbox(),
        alpha.crop((alpha.width - 1, 0, alpha.width, alpha.height)).getbbox(),
    ))


def validate_rgba(path: Path) -> list[str]:
    with Image.open(path) as opened:
        if opened.mode != "RGBA" or opened.size != CANVAS:
            return ["expected 512x768 RGBA"]
        image = opened.copy()
    errors: list[str] = []
    if any((r, g, b) != (0, 0, 0) for r, g, b, a in image.getdata() if a == 0):
        errors.append("Alpha-0 RGB must be zero")
    if not _border_is_transparent(image):
        errors.append("outer border must be transparent")
    return errors


def copy_canonical(source: Path, destination: Path) -> dict[str, object]:
    source = Path(source)
    destination = Path(destination)
    actual = sha256_path(source)
    if actual != CANONICAL_SHA256:
        raise RuntimeError(f"canonical SHA-256 mismatch: {actual}")
    errors = validate_rgba(source)
    if errors:
        raise RuntimeError("; ".join(errors))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.read_bytes() != source.read_bytes():
        raise RuntimeError("existing canonical copy differs")
    if not destination.exists():
        destination.write_bytes(source.read_bytes())
    return {"sha256": actual, "mode": "RGBA", "size": [512, 768]}
```

- [ ] **Step 4: Verify GREEN and copy the real authority**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_rig_center_contract.py -q
.\.venv\Scripts\python.exe -c "from pathlib import Path; from tools.rig_center_contract import copy_canonical; print(copy_canonical(Path('assets/keyframes/jump/00.png'), Path('assets/rig/v1/source/canonical-idle.png')))"
```

Expected: all tests pass; the second command prints the approved hash, `RGBA`, and `[512, 768]`.

- [ ] **Step 5: Commit only the isolated contract**

```powershell
git add tools/rig_center_contract.py tests/test_rig_center_contract.py assets/rig/v1/source/canonical-idle.png
git commit -m "assets: lock canonical rig source"
```

### Task 2: Deterministic Masks, Landmarks, and AI Guides

**Files:**
- Create: `tools/build_rig_center_guides.py`
- Create: `tests/test_build_rig_center_guides.py`
- Create: `assets/rig/v1/source/masks/dynamic-head-neck-mask.png`
- Create: `assets/rig/v1/source/masks/body-fill-mask.png`
- Create: `assets/rig/v1/source/masks/eye-left-mask.png`
- Create: `assets/rig/v1/source/masks/eye-right-mask.png`
- Create: `assets/rig/v1/source/guides/body-fill-guide.png`
- Create: `assets/rig/v1/source/guides/eye-fill-guide.png`
- Create: `assets/rig/v1/source/authoring.json`

**Interfaces:**
- Consumes: immutable `canonical-idle.png` and `validate_rgba`.
- Produces: `build_guides(canonical_path: Path, output_root: Path) -> dict[str, object]`; masks are binary L authoring selections and guides preserve all pixels outside their fill masks.

- [ ] **Step 1: Write failing mask and guide tests**

```python
from pathlib import Path

from PIL import Image, ImageChops

from tools.build_rig_center_guides import build_guides


def test_guides_have_fixed_masks_and_preserve_outside_pixels(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.png"
    Image.new("RGBA", (512, 768), (20, 30, 40, 255)).save(canonical)
    report = build_guides(canonical, tmp_path / "source")
    assert report["landmarks"]["nose"] == [118, 397]
    masks = tmp_path / "source" / "masks"
    with Image.open(masks / "dynamic-head-neck-mask.png") as opened:
        dynamic = opened.copy()
    assert dynamic.mode == "L" and dynamic.getbbox() == (24, 202, 264, 565)
    with Image.open(masks / "body-fill-mask.png") as body_fill:
        assert body_fill.getbbox() == (100, 365, 236, 551)
        assert ImageChops.subtract(body_fill, dynamic).getbbox() is None
    with Image.open(masks / "eye-left-mask.png") as left, Image.open(masks / "eye-right-mask.png") as right:
        assert ImageChops.multiply(left, right).getbbox() is None
    with Image.open(tmp_path / "source" / "guides" / "body-fill-guide.png") as guide, Image.open(masks / "body-fill-mask.png") as mask, Image.open(canonical) as source:
        outside = ImageChops.invert(mask)
        assert ImageChops.difference(Image.composite(guide, source, outside), source).getbbox() is None
```

- [ ] **Step 2: Run the tests to verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_build_rig_center_guides.py -q
```

Expected: missing `tools.build_rig_center_guides`.

- [ ] **Step 3: Implement the exact source geometry**

```python
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


CANVAS = (512, 768)
DYNAMIC_POLYGON = ((24, 202), (246, 202), (263, 370), (242, 455), (221, 564), (105, 564), (80, 470), (32, 430))
BODY_FILL_POLYGON = ((105, 390), (168, 365), (220, 390), (235, 450), (215, 550), (132, 550), (100, 470), (110, 440))
EYE_LEFT = (60, 325, 104, 380)
EYE_RIGHT = (139, 319, 184, 375)
LANDMARKS = {
    "ear_left_tip": [38, 222], "ear_left_root": [87, 310],
    "ear_right_tip": [223, 213], "ear_right_root": [194, 312],
    "eye_left": [82, 351], "eye_right": [161, 347],
    "nose": [118, 397], "jaw": [122, 451],
    "neck_left": [93, 454], "neck_right": [205, 454],
    "chest_left": [108, 555], "chest_right": [207, 555],
}


def _polygon(points: tuple[tuple[int, int], ...]) -> Image.Image:
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return mask


def _ellipse(box: tuple[int, int, int, int]) -> Image.Image:
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).ellipse(box, fill=255)
    return mask


def _guide(source: Image.Image, mask: Image.Image) -> Image.Image:
    marker = Image.new("RGBA", CANVAS, (0, 255, 0, 255))
    return Image.composite(marker, source, mask)


def build_guides(canonical_path: Path, output_root: Path) -> dict[str, object]:
    with Image.open(canonical_path) as opened:
        canonical = opened.convert("RGBA")
    output_root = Path(output_root)
    masks = output_root / "masks"
    guides = output_root / "guides"
    masks.mkdir(parents=True, exist_ok=True)
    guides.mkdir(parents=True, exist_ok=True)
    generated = {
        "dynamic-head-neck-mask.png": _polygon(DYNAMIC_POLYGON),
        "body-fill-mask.png": _polygon(BODY_FILL_POLYGON),
        "eye-left-mask.png": _ellipse(EYE_LEFT),
        "eye-right-mask.png": _ellipse(EYE_RIGHT),
    }
    subject = canonical.getchannel("A").point(lambda value: 255 if value else 0)
    for name in ("body-fill-mask.png", "eye-left-mask.png", "eye-right-mask.png"):
        if ImageChops.subtract(generated[name], subject).getbbox() is not None:
            raise RuntimeError(f"{name} extends outside canonical subject")
    for name, image in generated.items():
        image.save(masks / name)
    _guide(canonical, generated["body-fill-mask.png"]).save(guides / "body-fill-guide.png")
    eye_union = Image.new("L", CANVAS, 0)
    eye_union = Image.frombytes("L", CANVAS, bytes(max(a, b) for a, b in zip(generated["eye-left-mask.png"].tobytes(), generated["eye-right-mask.png"].tobytes())))
    _guide(canonical, eye_union).save(guides / "eye-fill-guide.png")
    report = {"canvas": list(CANVAS), "landmarks": LANDMARKS, "masks": sorted(generated)}
    (output_root / "authoring.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
```

- [ ] **Step 4: Verify GREEN and generate real guides**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_build_rig_center_guides.py -q
.\.venv\Scripts\python.exe -c "from pathlib import Path; from tools.build_rig_center_guides import build_guides; build_guides(Path('assets/rig/v1/source/canonical-idle.png'), Path('assets/rig/v1/source'))"
```

Expected: tests pass; four masks, two guides, and `authoring.json` exist. Open both guides and confirm neon green appears only over the internal shoulder/neck fill area and the two irises.

- [ ] **Step 5: Commit deterministic authoring inputs**

```powershell
git add tools/build_rig_center_guides.py tests/test_build_rig_center_guides.py assets/rig/v1/source/masks assets/rig/v1/source/guides assets/rig/v1/source/authoring.json
git commit -m "assets: define center rig authoring masks"
```

### Task 3: Generate Only the Hidden Fill Sources

**Files:**
- Create: `assets/rig/v1/source/ai/body-fill-raw.png`
- Create: `assets/rig/v1/source/ai/eye-fill-raw.png`
- Modify: `assets/rig/v1/source/authoring.json`

**Interfaces:**
- Consumes: the two generated guides and canonical image.
- Produces: two local raster sources plus exact prompts and output SHA-256 values in `authoring.json`. No generated pixel is accepted outside the fixed masks in Task 4.

- [ ] **Step 1: Load the required image-editing skill and inspect both guides**

Read `$imagegen` completely, then inspect `body-fill-guide.png` and `eye-fill-guide.png` at original resolution. If the green body region touches an external antialiased silhouette or either eye ellipse includes nose/eyelid fur, stop and correct Task 2 coordinates before generation.

- [ ] **Step 2: Generate the hidden shoulder/neck fill**

Invoke image editing with `body-fill-guide.png` and `canonical-idle.png` as references and this exact prompt:

```text
Edit the supplied 2:3 cat image guide. Replace only the solid neon-green internal region with the anatomically plausible shoulder, upper chest, and torso fur that would exist behind the removed head and neck of this exact orange-and-white Devon Rex cat. Continue the same short curly fur texture, orange tabby markings, white chest, lighting direction, focus, and photographic detail. Do not add a head, face, eye, ear, collar, bell, leg, text, outline, colored fringe, or background. Preserve the canvas composition and transparent surroundings. The result is a hidden fill source; all non-green content should remain visually aligned with the reference.
```

Save the returned PNG as `assets/rig/v1/source/ai/body-fill-raw.png`. If the service returns the same 2:3 aspect ratio at a larger resolution, retain it unchanged; Task 4 performs the only normalization.

- [ ] **Step 3: Generate the hidden eye-socket fill**

Invoke image editing with `eye-fill-guide.png` and `canonical-idle.png` as references and this exact prompt:

```text
Edit the supplied 2:3 cat image guide. Replace only the two solid neon-green iris regions with the natural eye-socket content behind movable irises for this exact cat: pale green-gray eye interior, subtle eyelid shadow, and the original short fur and lighting at each eye. Keep both eye shapes, eye corners, eyelids, face, nose, markings, proportions, camera, and transparent background aligned exactly. Do not add pupils, irises, extra highlights, extra eyes, text, outline, or colored fringe. This is a hidden underlay, not a new expression.
```

Save the returned PNG as `assets/rig/v1/source/ai/eye-fill-raw.png`.

- [ ] **Step 4: Record local provenance and commit only these isolated sources**

Add to `authoring.json`:

```json
{
  "ai_fill": {
    "tool": "OpenAI image generation image edit",
    "body_guide": "guides/body-fill-guide.png",
    "body_output": "ai/body-fill-raw.png",
    "eye_guide": "guides/eye-fill-guide.png",
    "eye_output": "ai/eye-fill-raw.png",
    "outside_mask_policy": "discard all generated pixels outside fixed masks"
  }
}
```

Compute and add `body_output_sha256` and `eye_output_sha256` using `Get-FileHash`. Then commit:

```powershell
git add assets/rig/v1/source/ai assets/rig/v1/source/authoring.json
git commit -m "assets: add masked rig fill sources"
```

### Task 4: Assemble the Center Layers and Prove Exact Recomposition

**Files:**
- Create: `tools/assemble_rig_center.py`
- Create: `tests/test_assemble_rig_center.py`
- Create: `assets/rig/v1/source/layers/body_base.png`
- Create: `assets/rig/v1/source/layers/head_neck_base.png`
- Create: `assets/rig/v1/source/layers/eye_left.png`
- Create: `assets/rig/v1/source/layers/eye_right.png`
- Create: `assets/rig/v1/source/layers/eye_left_mask.png`
- Create: `assets/rig/v1/source/layers/eye_right_mask.png`
- Create: `assets/rig/v1/samples/center/composite.png`

**Interfaces:**
- Consumes: canonical, four authoring masks, two AI fill sources.
- Produces: `assemble_center(source_root: Path, sample_root: Path) -> dict[str, object]`; generated source pixels are clipped to fill masks and the decoded center composite is exactly canonical.

- [ ] **Step 1: Write failing containment and exact-composite tests**

```python
from pathlib import Path

from PIL import Image, ImageDraw

from tools.assemble_rig_center import assemble_center, normalize_fill


def test_normalize_fill_discards_generated_pixels_outside_mask() -> None:
    generated = Image.new("RGBA", (1024, 1536), (255, 0, 255, 255))
    mask = Image.new("L", (512, 768), 0)
    ImageDraw.Draw(mask).rectangle((100, 200, 140, 240), fill=255)
    result = normalize_fill(generated, mask)
    assert result.getpixel((0, 0)) == (0, 0, 0, 0)
    assert result.getpixel((120, 220)) == (255, 0, 255, 255)


def test_assemble_center_is_exact_and_keeps_ai_hidden(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "masks").mkdir(parents=True)
    (source / "ai").mkdir()
    canonical = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    ImageDraw.Draw(canonical).rectangle((80, 180, 260, 560), fill=(210, 140, 80, 255))
    canonical.save(source / "canonical-idle.png")
    dynamic = Image.new("L", canonical.size, 0)
    ImageDraw.Draw(dynamic).rectangle((80, 180, 220, 460), fill=255)
    body_fill = Image.new("L", canonical.size, 0)
    ImageDraw.Draw(body_fill).rectangle((100, 360, 200, 450), fill=255)
    left = Image.new("L", canonical.size, 0)
    right = Image.new("L", canonical.size, 0)
    ImageDraw.Draw(left).ellipse((110, 240, 130, 260), fill=255)
    ImageDraw.Draw(right).ellipse((160, 240, 180, 260), fill=255)
    for name, image in {"dynamic-head-neck-mask.png": dynamic, "body-fill-mask.png": body_fill, "eye-left-mask.png": left, "eye-right-mask.png": right}.items():
        image.save(source / "masks" / name)
    Image.new("RGBA", canonical.size, (20, 30, 40, 255)).save(source / "ai" / "body-fill-raw.png")
    Image.new("RGBA", canonical.size, (50, 60, 70, 255)).save(source / "ai" / "eye-fill-raw.png")
    report = assemble_center(source, tmp_path / "samples" / "center")
    assert report["changed_pixels"] == 0
    assert report["maximum_channel_delta"] == 0
```

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_assemble_rig_center.py -q
```

Expected: missing `tools.assemble_rig_center`.

- [ ] **Step 3: Implement mask-only normalization and exact partitioning**

```python
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageChops


CANVAS = (512, 768)


def _clean_hidden_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    rgba.putdata([(0, 0, 0, 0) if a == 0 else (r, g, b, a) for r, g, b, a in rgba.getdata()])
    return rgba


def normalize_fill(generated: Image.Image, mask: Image.Image) -> Image.Image:
    rgba = generated.convert("RGBA")
    if rgba.size != CANVAS:
        if rgba.width * CANVAS[1] != rgba.height * CANVAS[0]:
            raise ValueError("generated fill must keep the canonical 2:3 aspect ratio")
        rgba = rgba.resize(CANVAS, Image.Resampling.LANCZOS)
    clipped = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    clipped.paste(rgba, (0, 0), mask)
    return _clean_hidden_rgb(clipped)


def _masked(image: Image.Image, mask: Image.Image) -> Image.Image:
    layer = image.convert("RGBA").copy()
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    return _clean_hidden_rgb(layer)


def _composite(*layers: Image.Image) -> Image.Image:
    result = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer in layers:
        result.alpha_composite(layer)
    return _clean_hidden_rgb(result)


def assemble_center(source_root: Path, sample_root: Path) -> dict[str, object]:
    source_root, sample_root = Path(source_root), Path(sample_root)
    layers_root = source_root / "layers"
    layers_root.mkdir(parents=True, exist_ok=True)
    sample_root.mkdir(parents=True, exist_ok=True)
    with Image.open(source_root / "canonical-idle.png") as opened:
        canonical = opened.convert("RGBA")
    masks = {}
    for stem in ("dynamic-head-neck", "body-fill", "eye-left", "eye-right"):
        with Image.open(source_root / "masks" / f"{stem}-mask.png") as opened:
            masks[stem] = opened.convert("L")
    with Image.open(source_root / "ai" / "body-fill-raw.png") as opened:
        body_fill = normalize_fill(opened, masks["body-fill"])
    with Image.open(source_root / "ai" / "eye-fill-raw.png") as opened:
        eye_fill = normalize_fill(opened, ImageChops.lighter(masks["eye-left"], masks["eye-right"]))
    static_mask = ImageChops.invert(masks["dynamic-head-neck"])
    body_base = _composite(_masked(canonical, static_mask), body_fill)
    eye_underlay = Image.composite(eye_fill, canonical, ImageChops.lighter(masks["eye-left"], masks["eye-right"]))
    head_neck = _masked(eye_underlay, masks["dynamic-head-neck"])
    eye_left = _masked(canonical, masks["eye-left"])
    eye_right = _masked(canonical, masks["eye-right"])
    composite = _composite(body_base, head_neck, eye_left, eye_right)
    difference = ImageChops.difference(composite, canonical)
    changed = sum(1 for pixel in difference.getdata() if pixel != (0, 0, 0, 0))
    maximum = max(max(pixel) for pixel in difference.getdata())
    if changed or maximum:
        raise RuntimeError(f"center recomposition drift: {changed} pixels, max {maximum}")
    outputs = {
        "body_base.png": body_base, "head_neck_base.png": head_neck,
        "eye_left.png": eye_left, "eye_right.png": eye_right,
        "eye_left_mask.png": masks["eye-left"], "eye_right_mask.png": masks["eye-right"],
    }
    for name, image in outputs.items():
        image.save(layers_root / name, optimize=True)
    composite.save(sample_root / "composite.png", optimize=True)
    return {"changed_pixels": changed, "maximum_channel_delta": maximum, "composite_sha256": hashlib.sha256((sample_root / "composite.png").read_bytes()).hexdigest()}
```

- [ ] **Step 4: Verify GREEN, assemble the real center, and run existing Alpha checks**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_assemble_rig_center.py -q
.\.venv\Scripts\python.exe -c "from pathlib import Path; from tools.assemble_rig_center import assemble_center; print(assemble_center(Path('assets/rig/v1/source'), Path('assets/rig/v1/samples/center')))"
.\.venv\Scripts\python.exe -c "from pathlib import Path; from tools.rig_center_contract import validate_rgba; files=list(Path('assets/rig/v1/source/layers').glob('*.png'))+[Path('assets/rig/v1/samples/center/composite.png')]; errors={str(p):validate_rgba(p) for p in files if p.suffix=='.png' and p.name not in {'eye_left_mask.png','eye_right_mask.png'}}; print(errors); raise SystemExit(any(errors.values()))"
```

Expected: tests pass; real report has `changed_pixels: 0` and `maximum_channel_delta: 0`; Alpha validation exits `0`.

- [ ] **Step 5: Commit the center source layers separately**

```powershell
git add tools/assemble_rig_center.py tests/test_assemble_rig_center.py assets/rig/v1/source/layers assets/rig/v1/samples/center
git commit -m "assets: assemble exact center rig layers"
```

### Task 5: Center Visual QA and User Gate

**Files:**
- Create: `tools/rig_center_qa.py`
- Create: `tests/test_rig_center_qa.py`
- Create: `qa/rig-v1/center-contact-sheet.png`
- Create: `qa/rig-v1/center-backgrounds.png`
- Create: `qa/rig-v1/center-closeups.png`
- Create: `qa/rig-v1/center-difference.png`
- Create: `qa/rig-v1/center-stats.json`

**Interfaces:**
- Consumes: canonical, body base, head/neck, eyes, masks, center composite.
- Produces: `write_center_qa(source_root: Path, sample_root: Path, qa_root: Path) -> dict[str, object]`; JSON records exact recomposition, Alpha, layer hashes, mask boxes, AI containment, and artifact names.

- [ ] **Step 1: Write the failing QA artifact test**

```python
from pathlib import Path

from PIL import Image

from tools.rig_center_qa import ARTIFACTS, write_center_qa


def make_valid_center_source(root: Path) -> Path:
    source = root / "source"
    layers = source / "layers"
    sample = root / "samples" / "center"
    layers.mkdir(parents=True)
    sample.mkdir(parents=True)
    canonical = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    for x in range(80, 240):
        for y in range(180, 560):
            canonical.putpixel((x, y), (210, 140, 80, 255))
    canonical.save(source / "canonical-idle.png")
    canonical.save(layers / "body_base.png")
    canonical.save(sample / "composite.png")
    for name in ("head_neck_base.png", "eye_left.png", "eye_right.png"):
        Image.new("RGBA", canonical.size, (0, 0, 0, 0)).save(layers / name)
    for name, box in (("eye_left_mask.png", (110, 240, 130, 260)), ("eye_right_mask.png", (160, 240, 180, 260))):
        mask = Image.new("L", canonical.size, 0)
        from PIL import ImageDraw
        ImageDraw.Draw(mask).ellipse(box, fill=255)
        mask.save(layers / name)
    return source


def test_center_qa_writes_exact_artifact_set(tmp_path: Path) -> None:
    source = make_valid_center_source(tmp_path)
    sample = source.parent / "samples" / "center"
    report = write_center_qa(source, sample, tmp_path / "qa")
    assert set(report["artifacts"]) == set(ARTIFACTS)
    assert report["changed_pixels"] == 0
    assert report["maximum_channel_delta"] == 0
    assert report["alpha_zero_rgb_violations"] == 0
    assert all((tmp_path / "qa" / name).is_file() for name in ARTIFACTS)
    with Image.open(tmp_path / "qa" / "center-backgrounds.png") as image:
        assert image.mode == "RGB"
```

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_rig_center_qa.py -q
```

Expected: missing `tools.rig_center_qa`.

- [ ] **Step 3: Implement deterministic center evidence**

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


ARTIFACTS = (
    "center-contact-sheet.png",
    "center-backgrounds.png",
    "center-closeups.png",
    "center-difference.png",
    "center-stats.json",
)
DISPLAY_HEIGHTS = (180, 280, 420)
BACKGROUNDS = ((255, 255, 255), (128, 128, 128), (0, 0, 0))
CLOSEUPS = {
    "eyes": (48, 304, 194, 390),
    "neck_seam": (72, 420, 236, 580),
    "ears": (20, 196, 254, 326),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _open_rgba(path: Path) -> Image.Image:
    with Image.open(path) as opened:
        return opened.convert("RGBA")


def _render_on(image: Image.Image, height: int, color: tuple[int, int, int]) -> Image.Image:
    width = round(image.width * height / image.height)
    resized = image.resize((width, height), Image.Resampling.LANCZOS)
    background = Image.new("RGBA", (width, height), (*color, 255))
    background.alpha_composite(resized)
    return background.convert("RGB")


def _contact_sheet(items: list[tuple[str, Image.Image]]) -> Image.Image:
    thumb = (160, 240)
    margin, label_height = 10, 24
    sheet = Image.new("RGB", ((thumb[0] + margin) * len(items) + margin, thumb[1] + label_height + 2 * margin), (42, 42, 48))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (label, image) in enumerate(items):
        x = margin + index * (thumb[0] + margin)
        checker = Image.new("RGBA", thumb, (196, 196, 196, 255))
        checker.alpha_composite(image.resize(thumb, Image.Resampling.LANCZOS))
        sheet.paste(checker.convert("RGB"), (x, margin + label_height))
        draw.text((x, margin + 5), label, fill=(255, 255, 255), font=font)
    return sheet


def _background_sheet(composite: Image.Image) -> Image.Image:
    columns = []
    for height in DISPLAY_HEIGHTS:
        rows = [_render_on(composite, height, color) for color in BACKGROUNDS]
        width = max(row.width for row in rows)
        column = Image.new("RGB", (width, sum(row.height for row in rows)), (32, 32, 32))
        top = 0
        for row in rows:
            column.paste(row, ((width - row.width) // 2, top))
            top += row.height
        columns.append(column)
    sheet = Image.new("RGB", (sum(column.width for column in columns), max(column.height for column in columns)), (32, 32, 32))
    left = 0
    for column in columns:
        sheet.paste(column, (left, 0))
        left += column.width
    return sheet


def _closeup_sheet(canonical: Image.Image, composite: Image.Image) -> Image.Image:
    panels = []
    for label, box in CLOSEUPS.items():
        first = canonical.crop(box).resize(((box[2] - box[0]) * 4, (box[3] - box[1]) * 4), Image.Resampling.NEAREST)
        second = composite.crop(box).resize(first.size, Image.Resampling.NEAREST)
        panel = Image.new("RGB", (first.width * 2, first.height + 24), (32, 32, 32))
        panel.paste(first.convert("RGB"), (0, 24))
        panel.paste(second.convert("RGB"), (first.width, 24))
        ImageDraw.Draw(panel).text((5, 6), f"{label}: canonical | composite", fill=(255, 255, 255), font=ImageFont.load_default())
        panels.append(panel)
    width = max(panel.width for panel in panels)
    sheet = Image.new("RGB", (width, sum(panel.height for panel in panels)), (32, 32, 32))
    top = 0
    for panel in panels:
        sheet.paste(panel, (0, top))
        top += panel.height
    return sheet


def write_center_qa(source_root: Path, sample_root: Path, qa_root: Path) -> dict[str, object]:
    source_root, sample_root, qa_root = Path(source_root), Path(sample_root), Path(qa_root)
    qa_root.mkdir(parents=True, exist_ok=True)
    layers_root = source_root / "layers"
    paths = {
        "canonical": source_root / "canonical-idle.png",
        "body_base": layers_root / "body_base.png",
        "head_neck": layers_root / "head_neck_base.png",
        "eye_left": layers_root / "eye_left.png",
        "eye_right": layers_root / "eye_right.png",
        "composite": sample_root / "composite.png",
    }
    images = {name: _open_rgba(path) for name, path in paths.items()}
    difference = ImageChops.difference(images["canonical"], images["composite"])
    difference_pixels = list(difference.getdata())
    changed_pixels = sum(pixel != (0, 0, 0, 0) for pixel in difference_pixels)
    maximum_delta = max(max(pixel) for pixel in difference_pixels)
    rgba_outputs = list(images.values())
    hidden_rgb = sum(
        1 for image in rgba_outputs for r, g, b, a in image.getdata()
        if a == 0 and (r, g, b) != (0, 0, 0)
    )
    outer_border_transparent = all(
        image.getchannel("A").crop(box).getbbox() is None
        for image in rgba_outputs
        for box in ((0, 0, image.width, 1), (0, image.height - 1, image.width, image.height), (0, 0, 1, image.height), (image.width - 1, 0, image.width, image.height))
    )
    _contact_sheet([
        ("canonical", images["canonical"]), ("body_base", images["body_base"]),
        ("head_neck", images["head_neck"]), ("eye_left", images["eye_left"]),
        ("eye_right", images["eye_right"]), ("composite", images["composite"]),
    ]).save(qa_root / "center-contact-sheet.png")
    _background_sheet(images["composite"]).save(qa_root / "center-backgrounds.png")
    _closeup_sheet(images["canonical"], images["composite"]).save(qa_root / "center-closeups.png")
    difference.convert("RGB").point(lambda value: min(255, value * 16)).save(qa_root / "center-difference.png")
    mask_boxes = {}
    for name in ("eye_left_mask.png", "eye_right_mask.png"):
        with Image.open(layers_root / name) as mask:
            mask_boxes[name] = list(mask.getbbox() or ())
    report = {
        "artifacts": list(ARTIFACTS),
        "canonical_sha256": _sha256(paths["canonical"]),
        "layer_sha256": {name: _sha256(path) for name, path in paths.items() if name != "canonical"},
        "mask_boxes": mask_boxes,
        "changed_pixels": changed_pixels,
        "maximum_channel_delta": maximum_delta,
        "alpha_zero_rgb_violations": hidden_rgb,
        "outer_border_transparent": outer_border_transparent,
    }
    (qa_root / "center-stats.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
```

- [ ] **Step 4: Verify GREEN and generate the real QA package**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_rig_center_qa.py -q
.\.venv\Scripts\python.exe -c "from pathlib import Path; from tools.rig_center_qa import write_center_qa; print(write_center_qa(Path('assets/rig/v1/source'), Path('assets/rig/v1/samples/center'), Path('qa/rig-v1')))"
.\.venv\Scripts\python.exe -m pytest tests\test_rig_center_contract.py tests\test_build_rig_center_guides.py tests\test_assemble_rig_center.py tests\test_rig_center_qa.py -q
Select-String -Path src\desktop_pet\*.py -Pattern 'numpy|cv2|opencv'
```

Expected: all new tests pass; the runtime-source scan returns no matches; `center-stats.json` reports zero decoded drift and zero hidden-RGB violations.

- [ ] **Step 5: Perform the required visual review**

Inspect all five QA files at original resolution. Reject this increment if any of these is visible:

- reconstructed shoulder/chest fur points in a different direction, has different sharpness, or looks painted;
- head/neck layer has a cut line, transparent gap, double dark edge, or pink/purple fringe;
- eye underlay contains a pupil/iris, or eye patches clip eyelids/nose fur;
- recomposed center differs from the approved cat, even if numeric Alpha checks pass;
- any layer changes the feet baseline or pixels outside the approved internal masks.

If rejected, modify only the two Task 3 AI fill sources or Task 2 internal masks, rerun Tasks 4–5, and preserve every rejected iteration under `qa/rig-v1/rejected/<timestamp>/`. Do not start directional poses.

- [ ] **Step 6: Commit evidence and request user approval**

```powershell
git add tools/rig_center_qa.py tests/test_rig_center_qa.py qa/rig-v1
git commit -m "qa: verify center rig layer feasibility"
```

Show the user `center-contact-sheet.png`, `center-backgrounds.png`, and `center-closeups.png`. State separately that exact center recomposition and Alpha checks passed, while hidden shoulder-fur naturalness still requires their visual judgment. The next plan, `2026-08-28-five-direction-rig-samples.md`, may be written only after the user approves this center-layer gate.

## Self-Review Checklist

- Spec coverage for this increment: canonical identity, fixed canvas, Alpha preservation, hidden-RGB clearing, body/shoulder fill, independent eye sources, center recomposition, black/white/gray backgrounds, 180/280/420 heights, 400% close-ups, isolation from runtime and old delivery.
- Deliberately deferred by the approved phase gate: five directional deformations, nine-direction orbit preview, blink, idle tilt, `9×5` production grid, runtime manifest, motion coordinator, EXE packaging, Windows runtime QA.
- Rollback: delete only the new `assets/rig/v1`, `qa/rig-v1`, `tools/rig_*`, and `tests/test_rig_*` paths or revert their isolated commits; the stable six-frame program and assets remain untouched.
- Decision receipt: adapt the existing Pillow/NumPy/OpenCV offline toolchain; use image generation only for masked hidden content; do not introduce Live2D, Inochi2D, a GUI editor, GPU runtime, or a new package dependency.
