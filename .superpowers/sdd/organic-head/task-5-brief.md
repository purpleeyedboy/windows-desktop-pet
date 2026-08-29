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
