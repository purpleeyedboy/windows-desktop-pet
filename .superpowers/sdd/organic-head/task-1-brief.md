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

