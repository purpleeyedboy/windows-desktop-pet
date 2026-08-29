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

