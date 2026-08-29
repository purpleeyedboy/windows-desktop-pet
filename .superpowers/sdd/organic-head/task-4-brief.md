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

